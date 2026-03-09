import streamlit as st
import pandas as pd
from datetime import datetime
import urllib.parse
import os
from streamlit_webrtc import webrtc_streamer, VideoProcessorBase, RTCConfiguration
import av
import cv2
from pyzbar.pyzbar import decode

# --- 1. CONFIGURAÇÕES E BANCO DE DADOS ---
st.set_page_config(page_title="Bicicletaria do Parque - Master", layout="wide")
DB_FILE = "dados_parque.csv"
RTC_CONFIG = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

def carregar_banco():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE).to_dict('records')
    return []

def salvar_banco(dados):
    pd.DataFrame(dados).to_csv(DB_FILE, index=False, encoding='utf-8-sig')

if 'ordens' not in st.session_state: st.session_state.ordens = carregar_banco()
if 'pecas_temp' not in st.session_state: st.session_state.pecas_temp = []
if 'mo_temp' not in st.session_state: st.session_state.mo_temp = []

# --- 2. SCANNER OTIMIZADO ---
class BarcodeProcessor(VideoProcessorBase):
    def __init__(self): self.last_barcode = None
    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        barcodes = decode(gray)
        for b in barcodes:
            self.last_barcode = b.data.decode('utf-8')
            (x, y, w, h) = b.rect
            cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 3)
        return av.VideoFrame.from_ndarray(img, format="bgr24")

# --- 3. ESTILO VISUAL ---
st.markdown("""
    <style>
    .stButton>button { height: 3.5em; width: 100%; border-radius: 12px; font-weight: bold; background-color: #007bff; color: white; }
    .card-os { padding: 15px; border-radius: 10px; background-color: white; border-left: 6px solid #28a745; margin-bottom: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); color: black; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. NAVEGAÇÃO ---
st.sidebar.title("🚲 Bicicletaria do Parque")
menu = st.sidebar.radio("Navegação", ["➕ Novo Check-in", "🛠️ Painel da Oficina (Agenda)", "🔎 Histórico de Clientes", "📊 Gestão Financeira"])

# --- ABA 1: NOVO CHECK-IN ---
if menu == "➕ Novo Check-in":
    st.title("➕ Nova Ordem de Serviço")
    
    with st.container():
        c1, c2 = st.columns(2)
        nome = c1.text_input("Cliente").title()
        whats = c1.text_input("WhatsApp (DDD+Número)")
        bike = c2.text_input("Modelo/Cor da Bike")
        mec = c2.selectbox("Mecânico Responsável", ["Anderson", "Alex", "Jonny", "Renato", "Mateus"])

    st.write("---")
    st.subheader("📷 Vistoria Obrigatória (3 Fotos)")
    st.info("💡 Clique nos botões para abrir a câmera. Se necessário, alterne para a câmera traseira no seu celular.")
    f1 = st.file_uploader("Foto 1: Lado Direito", type=['png', 'jpg', 'jpeg'])
    f2 = st.file_uploader("Foto 2: Lado Esquerdo", type=['png', 'jpg', 'jpeg'])
    f3 = st.file_uploader("Foto 3: Detalhe/Dano", type=['png', 'jpg', 'jpeg'])
    obs_v = st.text_area("Notas da Vistoria (Riscos, amassados, estado geral)")

    st.write("---")
    col_p, col_m = st.columns(2)
    with col_p:
        st.subheader("🛒 Peças (Scanner IA)")
        ctx = webrtc_streamer(key="barcode_scan", video_processor_factory=BarcodeProcessor, rtc_configuration=RTC_CONFIG,
                             media_stream_constraints={"video": {"facingMode": "environment"}, "audio": False})
        p_nome = st.text_input("Nome da Peça")
        if ctx.video_processor and ctx.video_processor.last_barcode:
            st.success(f"Lido: {ctx.video_processor.last_barcode}")
            if not p_nome: p_nome = f"Ref: {ctx.video_processor.last_barcode}"
        p_val = st.number_input("Valor Peça (R$)", min_value=0.0)
        if st.button("➕ Adicionar Peça"): st.session_state.pecas_temp.append({"item": p_nome, "valor": p_val})

    with col_m:
        st.subheader("🛠️ Mão de Obra")
        m_desc = st.text_input("Descrição do Serviço")
        m_val = st.number_input("Valor MO (R$)", min_value=0.0)
        if st.button("➕ Adicionar MO"): st.session_state.mo_temp.append({"item": m_desc, "valor": m_val})

    total = sum(i['valor'] for i in st.session_state.pecas_temp + st.session_state.mo_temp)
    st.subheader(f"💰 Total Orçamento: R$ {total:.2f}")

    if st.button("🚀 SALVAR E ENVIAR ORÇAMENTO"):
        itens_txt = "\n".join([f"• {i['item']}: R$ {i['valor']:.2f}" for i in st.session_state.pecas_temp + st.session_state.mo_temp])
        nova_os = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "data_entrada": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "cliente": nome, "telefone": whats, "bike": bike, "mecanico": mec,
            "obs": obs_v, "itens": itens_txt, "total": total, "status": "Pendente",
            "inicio_servico": "", "fim_servico": ""
        }
        st.session_state.ordens.append(nova_os)
        salvar_banco(st.session_state.ordens)
        
        # LINHA CORRIGIDA ABAIXO
        msg = f"*Bicicletaria do Parque*\nOlá {nome}!\nOrçamento da {bike}:\n\n{itens_txt}\n\n*Total: R$ {total:.2f}*\nPodemos iniciar?"
        msg_enc = urllib.parse.quote(msg)
        st.markdown(f'<a href="https://api.whatsapp.com/send?phone=55{whats}&text={msg_enc}" target="_blank"><button style="background-color:#25d366; color:white; border:none; height:60px; width:100%; border-radius:12px; font-weight:bold;">📲 ENVIAR ORÇAMENTO WHATSAPP</button></a>', unsafe_allow_html=True)
        
        st.session_state.pecas_temp = []; st.session_state.mo_temp = []
        st.success("Ordem de Serviço salva com sucesso!")

# --- ABA 2: PAINEL DA OFICINA (AGENDA E STATUS) ---
elif menu == "🛠️ Painel da Oficina (Agenda)":
    st.title("🛠️ Gestão de Serviços")
    status_filtro = st.selectbox("Status:", ["Todos", "Pendente", "Em Andamento", "Finalizado"])
    
    for o in st.session_state.ordens:
        if status_filtro != "Todos" and o['status'] != status_filtro: continue
        if o['status'] == "Entregue": continue
        
        with st.expander(f"🚲 {o['cliente']} | {o['bike']} - [{o['status']}]"):
            st.write(f"**Mecânico:** {o['mecanico']} | **Entrada:** {o['data_entrada']}")
            st.write(f"**Itens:**\n{o['itens']}")
            
            c1, c2, c3 = st.columns(3)
            if o['status'] == "Pendente" and c1.button("▶️ Iniciar Cavalete", key=f"ini_{o['id']}"):
                o['status'] = "Em Andamento"; o['inicio_servico'] = datetime.now().strftime("%H:%M")
                salvar_banco(st.session_state.ordens); st.rerun()
            
            if o['status'] == "Em Andamento" and c2.button("🏁 Finalizar (Aviso WhatsApp)", key=f"fim_{o['id']}"):
                o['status'] = "Finalizado"; o['fim_servico'] = datetime.now().strftime("%H:%M")
                salvar_banco(st.session_state.ordens)
                msg_p = f"Olá {o['cliente']}! Sua {o['bike']} está pronta na *Bicicletaria do Parque*! ✅ Total: R$ {o['total']:.2f}"
                st.markdown(f'[📲 Avisar no WhatsApp](https://api.whatsapp.com/send?phone=55{o["telefone"]}&text={urllib.parse.quote(msg_p)})')
            
            if o['status'] == "Finalizado" and c3.button("📦 Confirmar Entrega", key=f"ret_{o['id']}"):
                o['status'] = "Entregue"; salvar_banco(st.session_state.ordens); st.rerun()

            if o['inicio_servico']: 
                st.info(f"⏱️ Início: {o['inicio_servico']} | Fim: {o.get('fim_servico', 'Executando...')}")

# --- ABA 3: HISTÓRICO ---
elif menu == "🔎 Histórico de Clientes":
    st.title("🔎 Consultar Clientes")