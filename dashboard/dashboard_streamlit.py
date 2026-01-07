# ==========================================================
# Dashboard Streamlit – Network Slicing
# ==========================================================
# Questa applicazione permette di visualizzare i risultati
# ottenuti nei test eseguiti sui tre controller Ryu.
# Funzionalità:
# - caricamento automatico dei file CSV
# - visualizzazione tabellare dei risultati
# - grafici comparativi tra le diverse slice
# - analisi specifica del dynamic slicing
# ==========================================================

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

RESULT_DIR = "./results"

# ----------------------------------------------------------
# Funzione: load_csv
# ----------------------------------------------------------
# Carica un file CSV dalla cartella results e restituisce
# un dataframe Pandas. Se il file non esiste restituisce None.
# Serve a gestire in modo sicuro il caricamento dati.
# ----------------------------------------------------------
def load_csv(filename):
    try:
        path = f"{RESULT_DIR}/{filename}"
        df = pd.read_csv(path)
        return df
    except Exception as e:
        st.warning(f"Impossibile caricare {filename}: {e}")
        return None


# ----------------------------------------------------------
# Funzione: plot_throughput
# ----------------------------------------------------------
# Genera un grafico semplice del throughput medio per ogni
# coppia di host presente nel dataframe fornito.
# Non vengono specificati colori per rispettare le regole.
# ----------------------------------------------------------
def plot_throughput(df, title):
    if df is None or df.empty:
        st.info("Nessun dato disponibile per il grafico.")
        return

    data = df["throughput_mbps"].dropna()

    plt.figure()
    plt.plot(data)
    plt.title(title)
    st.pyplot(plt)


# ----------------------------------------------------------
# MAIN APPLICATION
# ----------------------------------------------------------

st.title("Network Slicing – Risultati dei Test")

# Sidebar per selezionare la fase
st.sidebar.header("Selezione Fase")
phase = st.sidebar.selectbox(
    "Scegli quale fase visualizzare",
    ["Topology Slicing", "Service Slicing Statico", "Service Slicing Dinamico"]
)

# Caricamento dei CSV
topo_df = load_csv("topology_results.csv")
static_df = load_csv("static_results.csv")
dynamic_df = load_csv("dynamic_results.csv")

# ----------------------------------------------------------
# Visualizzazione Topology Slicing
# ----------------------------------------------------------
# Mostra i risultati del primo controller, evidenziando
# pacchetti bloccati e coppie autorizzate.
# ----------------------------------------------------------
if phase == "Topology Slicing":
    st.header("Topology Slicing Controller")

    if topo_df is not None:
        st.dataframe(topo_df)

        st.subheader("Grafico Throughput TCP")
        tcp = topo_df[topo_df["protocol"] == "TCP"]
        plot_throughput(tcp, "Throughput TCP – Topology Slicing")

        st.subheader("Esito blocchi ICMP")
        blocked = topo_df[topo_df["result"] == "blocked"]
        st.write(blocked)

# ----------------------------------------------------------
# Visualizzazione Service Slicing Statico
# ----------------------------------------------------------
# Permette di osservare come il secondo controller
# classifichi il traffico in modo statico.
# ----------------------------------------------------------
elif phase == "Service Slicing Statico":
    st.header("Service Slicing Statico")

    if static_df is not None:
        st.dataframe(static_df)

        st.subheader("Throughput UDP porta 9999")
        udp_video = static_df[static_df["protocol"] == "UDP_9999"]
        plot_throughput(udp_video, "Throughput UDP – Video Slice (Statico)")

# ----------------------------------------------------------
# Visualizzazione Service Slicing Dinamico
# ----------------------------------------------------------
# Questa è la parte più innovativa della dashboard:
# Mostra chiaramente il comportamento BE con e senza
# congestione e il ripristino automatico.
# ----------------------------------------------------------
elif phase == "Service Slicing Dinamico":
    st.header("Service Slicing Dinamico")

    if dynamic_df is not None:
        st.dataframe(dynamic_df)

        st.subheader("Confronto Best Effort")
        be = dynamic_df[dynamic_df["protocol"].str.contains("UDP_BE")]
        plot_throughput(be, "Throughput BE – Dynamic Slicing")

        st.subheader("Stress Test Throughput")
        stress = dynamic_df[dynamic_df["protocol"].str.contains("UDP_BE_")]
        plot_throughput(stress, "Throughput BE con banda crescente")

# ----------------------------------------------------------

st.subheader("Confronto Generale tra Slice")

# Grafico comparativo TCP tra statico e topology
if topo_df is not None and static_df is not None:
    plt.figure()
    plt.plot(topo_df[topo_df["protocol"] == "TCP"]["throughput_mbps"])
    plt.plot(static_df[static_df["protocol"] == "TCP"]["throughput_mbps"])
    plt.title("Confronto TCP – Topology vs Static Slicing")
    st.pyplot(plt)

st.write("Dashboard completata.")
