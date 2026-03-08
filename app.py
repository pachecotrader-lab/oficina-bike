import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import urllib.parse
import os
from streamlit_webrtc import webrtc_streamer, VideoProcessorBase
import av
import cv2
from pyzbar.pyzbar import decode

# --- 1. CONFIGURAÇÃO E BANCO DE DADOS ---
st.set_page_config(page_title="Bicicletaria do Parque", layout="wide")
DB_FILE = "dados_oficina_parque.csv"

def carregar_banco():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE).to_dict('records')
    return []

def salvar_banco(dados):
    pd.DataFrame(dados).to_csv(DB_FILE, index=False, encoding='utf-8-sig')

if 'ordens' not in st.session_state: st.session_state.ordens = carregar_banco()
if 'pecas_temp' not in st.session_state: st.session_state.pecas_temp = []
if 'mo_temp' not in st.session_state: st.session_state.mo_temp = []

# --- 2. FERRAMENTAS TÉCNICAS (WHATSAPP E SCANNER) ---
def link_wpp(tel, msg):
    return f"https://api.whatsapp.com/send?phone=55{tel}&text={urllib.parse.quote(msg)}"

class BarcodeProcessor(VideoProcessorBase):
    def __init__(self): self.last_barcode = None
    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        barcodes = decode(img)
        for b in barcodes: self.last_barcode = b.data.decode('utf-8')
        return av.VideoFrame.from_ndarray(img, format="bgr24")

# --- 3. ESTILO VISUAL (ANDROID) ---
st.markdown("""
    <style>
    .stButton>button { height: 3.5em; width: 100%; font-size: 18px; border-radius: 12px; font-weight: bold; }
    .card { padding: 15px; border-radius: 10px; background-color: white; border-left: 6px solid #007bff; margin-bottom: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); color: black; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. MENU LATERAL ---
st.sidebar.title("🚲 Bicicletaria do Parque")
aba = st.sidebar.radio("Escolha a tarefa:", ["➕ Check-in (Entrada)", "🛠️ Oficina (Execução)", "🔎 Histórico do Cliente", "📊 Relatórios"])

# --- ABA 1: CHECK-IN (FOTO + SCANNER + MO) ---
if aba == "➕ Check-in (Entrada)":
    st.title("➕ Nova Entrada de Bike")
    
    with st.expander("📝 Dados do Cliente e Bike", expanded=True):
        c1, c2 = st.columns(2)
        nome = c1.text_input("Nome do Cliente").title()
        whats = c1.text_input("WhatsApp (com DDD)")
        bike = c2.text_input("Modelo/Cor da Bicicleta")
        mecanico = c2.selectbox("Mecânico Responsável", ["Anderson", "Alex", "Jonny", "Renato", "Mateus"])

    st.subheader("📷 Vistoria (Segurança)")
    foto = st.camera_input("Tire foto da bike na chegada")
    obs_v = st.text_area("Descreva o estado da bike (riscos, peças frouxas, etc)")

    st.divider()
    col_p, col_m = st.columns(2)
    with col_p:
        st.subheader("🛒 Peças (Scanner IA)")
        webrtc_streamer(key="scan", video_processor_factory=BarcodeProcessor, 
                        media_stream_constraints={"video": {"facingMode": "environment"}, "audio": False})
        p_nome = st.text_input("Nome da Peça")
        p_val = st.number_input("Preço da Peça", min_value=0.0)
        if st.button("➕ Adicionar Peça"):
            st.session_state.pecas_temp.append({"item": p_nome, "preco": p_val})

    with col_m:
        st.subheader("🛠️ Mão de Obra")
        m_desc = st.text_input("O que será feito?")
        m_val = st.number_input("Valor do Serviço", min_value=0.0)
        if st.button("➕ Adicionar Serviço"):
            st.session_state.mo_temp.append({"item": m_desc, "preco": m_val})

    # Resumo Final
    st.divider()
    total = sum(i['preco'] for i in st.session_state.pecas_temp + st.session_state.mo_temp)
    st.subheader(f"💰 Total do Orçamento: R$ {total:.2f}")

    if st.button("🚀 SALVAR E GERAR ORÇAMENTO"):
        resumo_texto = "\n".join([f"• {i['item']}: R$ {i['preco']:.2f}" for i in st.session_state.pecas_temp + st.session_state.mo_temp])
        nova_os = {
            "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "cliente": nome, "whatsapp": whats, "bike": bike, "mecanico": mecanico,
            "obs": obs_v, "itens": resumo_texto, "valor": total, "status": "Pendente", "entrega": ""
        }
        st.session_state.ordens.append(nova_os)
        salvar_banco(st.session_state.ordens)
        
        msg = f"*Bicicletaria do Parque*\nOlá {nome}, orçamento da {bike}:\n\n{resumo_texto}\n\n*Total:* R$ {total:.2f}\nPodemos iniciar?"
        st.markdown(f'<a href="{link_wpp(whats, msg)}" target="_blank"><button style="background-color:#25d366; color:white; border:none; height:60px; width:100%; border-radius:12px; font-weight:bold;">📲 ENVIAR ORÇAMENTO WHATSAPP</button></a>', unsafe_allow_html=True)
        
        st.session_state.pecas_temp = []; st.session_state.mo_temp = []
        st.success("OS Salva com sucesso!")

# --- ABA 2: OFICINA (AVISO DE PRONTO) ---
elif aba == "🛠️ Oficina (Execução)":
    st.title("🛠️ Painel da Oficina")
    pendentes = [o for o in st.session_state.ordens if o['status'] == "Pendente"]
    for idx, os_p in enumerate(pendentes):
        with st.expander(f"🚲 {os_p['cliente']} - {os_p['bike']} (Mec: {os_p['mecanico']})"):
            st.write(f"**Serviços:**\n{os_p['itens']}")
            if st.button(f"✅ Finalizar e Avisar Cliente", key=f"f_{idx}"):
                os_p['status'] = "Concluído"
                os_p['entrega'] = datetime.now().strftime("%d/%m/%Y %H:%M")
                salvar_banco(st.session_state.ordens)
                msg_p = f"Olá {os_p['cliente']}! Sua {os_p['bike']} está PRONTA na *Bicicletaria do Parque*! ✅ Valor: R$ {os_p['valor']:.2f}"
                st.markdown(f'[📲 Avisar no WhatsApp]({link_wpp(os_p["whatsapp"], msg_p)})')

# --- ABA 3: HISTÓRICO (CRM E BUSCA) ---
elif aba == "🔎 Histórico do Cliente":
    st.title("🔎 Histórico de Visitas")
    busca = st.text_input("Busque por Nome ou Telefone:").title()
    if busca:
        resultados = [o for o in st.session_state.ordens if busca in o['cliente'] or busca in str(o['whatsapp'])]
        for r in reversed(resultados):
            st.markdown(f"""
            <div class="card">
                📅 <strong>Data:</strong> {r['data']} | 👨‍🔧 <strong>Mecânico:</strong> {r['mecanico']}<br>
                🚲 <strong>Bike:</strong> {r['bike']}<br>
                🛠️ <strong>Histórico:</strong> {r['itens'].replace('\n', ' | ')}<br>
                💰 <strong>Valor:</strong> R$ {r['valor']:.2f} | ✅ <strong>Status:</strong> {r['status']}
            </div>
            """, unsafe_allow_html=True)
            # Botão de Pós-Venda para bikes entregues
            if r['status'] == "Concluído":
                msg_pos = f"Olá {r['cliente']}! Como ficou o pedal com a {r['bike']}? 🚲 Se gostou, nos avalie no Google!"
                st.markdown(f'[📲 Enviar Pós-Venda]({link_wpp(r["whatsapp"], msg_pos)})')

# --- ABA 4: RELATÓRIOS ---
elif aba == "📊 Relatórios":
    st.title("📊 Gestão Financeira")
    if st.session_state.ordens:
        df = pd.DataFrame(st.session_state.ordens)
        st.write(f"**Total de OS no sistema:** {len(df)}")
        st.write(f"**Faturamento Total Bruto:** R$ {df['valor'].sum():.2f}")
        st.dataframe(df)
        st.download_button("📥 Baixar Planilha Completa", df.to_csv(index=False).encode('utf-8-sig'), "bicicletaria_parque_dados.csv")