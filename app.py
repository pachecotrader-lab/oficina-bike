import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import urllib.parse
import os
import requests
from bs4 import BeautifulSoup
from streamlit_webrtc import webrtc_streamer, VideoProcessorBase, RTCConfiguration
import av
import cv2
from pyzbar.pyzbar import decode

# --- CONFIGURAÇÃO MASTER ---
st.set_page_config(page_title="Bicicletaria do Parque - Sistema Profissional", page_icon="🚲", layout="wide")

# ARQUIVO DE BANCO DE DADOS (PERMANENTE)
DB_FILE = "dados_bicicletaria_parque.csv"

# Carregamento Seguro de Dados
def carregar_dados():
    if os.path.exists(DB_FILE):
        try:
            df = pd.read_csv(DB_FILE)
            return df.to_dict('records')
        except: return []
    return []

def salvar_dados(lista):
    df = pd.DataFrame(lista)
    df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')

# Inicialização de Memória
if 'ordens' not in st.session_state: st.session_state.ordens = carregar_dados()
if 'pecas_temp' not in st.session_state: st.session_state.pecas_temp = []
if 'servicos_temp' not in st.session_state: st.session_state.servicos_temp = []

# --- ESTILO PARA ANDROID (BOTÕES LARGOS) ---
st.markdown("""
    <style>
    div.stButton > button:first-child { height: 3.5em; width: 100%; font-size: 18px; font-weight: bold; border-radius: 12px; background-color: #007BFF; color: white; }
    .historico-card { padding: 15px; border-radius: 10px; background-color: white; border-left: 6px solid #28a745; margin-bottom: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); color: black; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES TÉCNICAS ---
def gerar_wpp(tel, msg):
    return f"https://api.whatsapp.com/send?phone=55{tel}&text={urllib.parse.quote(msg)}"

class BarcodeProcessor(VideoProcessorBase):
    def __init__(self): self.last_barcode = None
    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        barcodes = decode(img)
        for b in barcodes: self.last_barcode = b.data.decode('utf-8')
        return av.VideoFrame.from_ndarray(img, format="bgr24")

# --- MENU ---
st.sidebar.title("Bicicletaria do Parque")
menu = st.sidebar.radio("Navegação", ["➕ Novo Check-in", "🛠️ Painel da Oficina", "🔎 Histórico do Cliente", "📊 Relatório Geral"])

# --- 1. CHECK-IN COMPLETO (FOTO + SCANNER + MO) ---
if menu == "➕ Novo Check-in":
    st.title("➕ Nova Ordem de Serviço")
    
    col1, col2 = st.columns(2)
    with col1:
        nome = st.text_input("Nome do Cliente").strip().title()
        tel = st.text_input("WhatsApp (DDD+Número)")
    with col2:
        bike = st.text_input("Modelo/Cor da Bike")
        mec = st.selectbox("Mecânico Responsável", ["Anderson", "Alex", "Jonny", "Renato", "Mateus"])
    
    st.write("---")
    st.subheader("📷 Vistoria e Fotos")
    foto = st.camera_input("Tire uma foto da bike agora")
    obs = st.text_area("Notas de Vistoria (Riscos, detalhes)")
    
    st.divider()
    cp, cm = st.columns(2)
    with cp:
        st.subheader("🛒 Peças (Scanner IA)")
        ctx = webrtc_streamer(key="scanner", video_processor_factory=BarcodeProcessor, 
                        media_stream_constraints={"video": {"facingMode": "environment"}, "audio": False})
        p_n = st.text_input("Nome da Peça (ou via Scanner)")
        p_v = st.number_input("Valor Peça (R$)", min_value=0.0)
        if st.button("➕ Add Peça"): st.session_state.pecas_temp.append({"item": p_n, "valor": p_v})
            
    with cm:
        st.subheader("🛠️ Mão de Obra")
        m_n = st.text_input("Descrição do Serviço")
        m_v = st.number_input("Valor MO (R$)", min_value=0.0)
        if st.button("➕ Add Mão de Obra"): st.session_state.servicos_temp.append({"item": m_n, "valor": m_v})

    total = sum(i['valor'] for i in st.session_state.pecas_temp + st.session_state.servicos_temp)
    st.subheader(f"💰 Total: R$ {total:.2f}")

    if st.button("🚀 SALVAR E ENVIAR ORÇAMENTO"):
        resumo = "\n".join([f"• {i['item']}: R$ {i['valor']:.2f}" for i in st.session_state.pecas_temp + st.session_state.servicos_temp])
        os_final = {
            "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "cliente": nome, "telefone": tel, "bike": bike, "mecanico": mec,
            "obs": obs, "itens": resumo, "total": total, "status": "Pendente"
        }
        st.session_state.ordens.append(os_final)
        salvar_dados(st.session_state.ordens)
        
        msg = f"*Bicicletaria do Parque*\nOlá {nome}!\nOrçamento da {bike}:\n\n{resumo}\n\n*Total:* R$ {total:.2f}\nPodemos iniciar?"
        st.markdown(f'<a href="{gerar_wpp(tel, msg)}" target="_blank"><button style="background-color:#25d366; color:white; width:100%; border:none; height:60px; border-radius:12px; font-weight:bold; cursor:pointer;">📲 ENVIAR ORÇAMENTO WHATSAPP</button></a>', unsafe_allow_html=True)
        
        st.session_state.pecas_temp = []; st.session_state.servicos_temp = []
        st.success("OS salva no histórico permanente!")

# --- 2. PAINEL DA OFICINA ---
elif menu == "🛠️ Painel da Oficina":
    st.title("🛠️ Serviços para Executar")
    ativas = [o for o in st.session_state.ordens if o['status'] == "Pendente"]
    for idx, o in enumerate(ativas):
        with st.expander(f"🚲 {o['cliente']} - {o['bike']} (Mec: {o['mecanico']})"):
            st.write(f"**Serviços:**\n{o['itens']}")
            if st.button(f"✅ Finalizar e Avisar Cliente", key=f"f_{idx}"):
                o['status'] = "Concluído"
                salvar_dados(st.session_state.ordens)
                msg_p = f"Olá {o['cliente']}! Sua {o['bike']} está PRONTA na *Bicicletaria do Parque*! ✅ Total: R$ {o['total']:.2f}"
                st.markdown(f'[📲 Avisar no WhatsApp]({gerar_wpp(o["telefone"], msg_p)})')

# --- 3. HISTÓRICO COMPLETO ---
elif menu == "🔎 Histórico do Cliente":
    st.title("🔎 Consultar Histórico")
    busca = st.text_input("Buscar por Nome ou Telefone:").strip().title()
    if busca:
        hist = [o for o in st.session_state.ordens if busca in o['cliente'] or busca in str(o['telefone'])]
        for h in reversed(hist):
            st.markdown(f"""<div class="historico-card">
                📅 <strong>{h['data']}</strong> - {h['bike']}<br>
                🛠️ <strong>Itens:</strong> {h['itens'].replace('\n', ' | ')}<br>
                💰 <strong>Total:</strong> R$ {h['total']:.2f} | 👨‍🔧 <strong>Mecânico:</strong> {h['mecanico']}
            </div>""", unsafe_allow_html=True)

# --- 4. RELATÓRIOS ---
elif menu == "📊 Relatório Geral":
    st.title("📊 Relatório de Vendas")
    if st.session_state.ordens:
        df = pd.DataFrame(st.session_state.ordens)
        st.dataframe(df)
        st.download_button("📥 Baixar Planilha Excel", df.to_csv(index=False).encode('utf-8-sig'), "relatorio_parque.csv")