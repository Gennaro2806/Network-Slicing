import streamlit as st
import pandas as pd
import time

from tests import ping_test, start_iperf_server, iperf_udp_test
from metrics import measure_throughput

# -------------------------
# PAGE SETUP
# -------------------------

st.set_page_config(
    page_title="Network Slicing Dashboard",
    layout="wide"
)

st.title("📡 Network Slicing – Simple Monitoring Dashboard")

st.markdown(
    """
    This dashboard provides **basic real-time monitoring**
    and **traffic generation tests** for a Mininet-based SDN network.
    """
)

# -------------------------
# SIDEBAR
# -------------------------

st.sidebar.header("Test Parameters")

src_host = st.sidebar.selectbox(
    "Source Host",
    ["h1", "h2"]
)

dst_ip = st.sidebar.selectbox(
    "Destination IP",
    ["10.0.0.3", "10.0.0.4"]
)

test_type = st.sidebar.selectbox(
    "Test Type",
    ["Ping", "iPerf UDP"]
)

ping_count = st.sidebar.slider(
    "Ping Count",
    1, 20, 5
)

iperf_duration = st.sidebar.slider(
    "iPerf Duration (s)",
    1, 30, 10
)

iperf_bw = st.sidebar.slider(
    "UDP Bandwidth (Mbps)",
    1, 20, 5
)

run_test = st.sidebar.button("Run Test")

# -------------------------
# TEST EXECUTION
# -------------------------

if run_test:

    if test_type == "Ping":
        st.subheader("📶 Ping Test Output")
        output = ping_test(src_host, dst_ip, ping_count)
        st.text(output)

    if test_type == "iPerf UDP":
        st.subheader("🎥 iPerf UDP Test Output")
        start_iperf_server("h3")
        output = iperf_udp_test(
            src_host,
            dst_ip,
            iperf_bw,
            iperf_duration
        )
        st.text(output)

# -------------------------
# REAL-TIME MONITORING
# -------------------------

st.subheader("📊 Real-Time Throughput (s1-eth1)")

data = []

placeholder = st.empty()

for _ in range(10):
    try:
        thr = measure_throughput("s1-eth1")
        data.append(thr)

        df = pd.DataFrame(data, columns=["Mbps"])
        placeholder.line_chart(df)

        time.sleep(1)
    except:
        st.warning("Interface not available")
        break
