import streamlit as st
import pandas as pd
import time
import os

# Configurazione della pagina per una visualizzazione ampia
st.set_page_config(
    page_title="SDN Slicing Dashboard",
    layout="wide",
    page_icon="📡"
)

# Percorsi dei file
DATA_FILE = "traffic_data.csv"
STANDARD_LOG = "test_results.log"
CAPACITY_LOG = "capacity_test_results.log"

# --- SIDEBAR ---
st.sidebar.title("Configurazione Dashboard")
auto_refresh = st.sidebar.checkbox("🟢 Monitoraggio Live", value=True)
st.sidebar.info("""
**Istruzioni:**
1. Avvia Ryu e la Topologia.
2. Avvia `monitor_network.py`.
3. Esegui i test dal terminale.
""")

st.title("📡 SDN Network Slicing & Capacity Dashboard")

# Funzione per caricare i dati CSV
def load_data():
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame()
    return pd.read_csv(DATA_FILE)

df = load_data()

# --- DEFINIZIONE TAB ---
tab1, tab2 = st.tabs(["📈 Analisi Performance Real-Time", "📄 Registri e Log dei Test"])

# --- TAB 1: GRAFICI E METRICHE ---
with tab1:
    if not df.empty:
        # Metriche in primo piano (ultimi valori rilevati)
        last_row = df.iloc[-1]
        m1, m2, m3, m4 = st.columns(4)
        
        m1.metric("Throughput Attuale", f"{last_row['Mbps']} Mbps")
        
        # Mostra latenza e jitter solo se il link è attivo (loss < 100)
        if last_row['Loss'] < 100:
            m2.metric("Latenza (RTT)", f"{last_row['Latency']} ms")
            m3.metric("Jitter", f"{last_row['Jitter']} ms")
        else:
            m2.metric("Latenza (RTT)", "N/A")
            m3.metric("Jitter", "N/A")
            
        m4.metric("Packet Loss", f"{last_row['Loss']}%", 
                  delta="⚠️ CRITICO" if last_row['Loss'] > 10 else "OK", 
                  delta_color="inverse")

        # --- Grafico Banda ---
        st.subheader("Banda Passante per Slice (Mbps)")
        st.line_chart(df, x="Timestamp", y="Mbps", color="Interface")

        # --- Grafici Qualità (Latenza e Loss) ---
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.subheader("Andamento Latenza (ms)")
            # Puliamo i dati per non mostrare picchi d'errore quando il link cade
            df_clean = df[df['Loss'] < 100]
            st.area_chart(df_clean, x="Timestamp", y="Latency", color="Interface")
            
        with col_right:
            st.subheader("Perdita Pacchetti (%)")
            st.bar_chart(df, x="Timestamp", y="Loss", color="Interface")
    else:
        st.warning("⚠️ Nessun dato rilevato nel file CSV. Assicurati che 'monitor_network.py' sia in esecuzione con sudo.")

# --- TAB 2: VISUALIZZAZIONE LOG ---
with tab2:
    st.header("Visualizzazione Risultati Test")
    
    # Selezione del tipo di test da visualizzare
    test_choice = st.radio(
        "Seleziona il report da visualizzare:",
        ["Verifica Standard (iperf/ping)", "Capacity Stress Test (Analisi Saturazione)"],
        horizontal=True
    )
    
    # Determina quale file aprire
    selected_file = STANDARD_LOG if "Verifica" in test_choice else CAPACITY_LOG
    
    col_btn1, col_btn2 = st.columns([1, 5])
    with col_btn1:
        if st.button("🔄 Aggiorna Log"):
            st.rerun()

    if os.path.exists(selected_file):
        with open(selected_file, "r") as f:
            log_content = f.read()
            # Visualizzazione del log in un'area di testo spaziosa
            st.text_area(f"Contenuto di: {selected_file}", log_content, height=600)
            
            # Funzione di download per la relazione
            st.download_button(
                label="📥 Scarica Log per la Relazione",
                data=log_content,
                file_name=selected_file,
                mime="text/plain"
            )
    else:
        st.info(f"Il file `{selected_file}` non esiste ancora. Esegui lo script corrispondente nel terminale.")

# --- LOGICA DI REFRESH ---
if auto_refresh:
    time.sleep(1)
    st.rerun()