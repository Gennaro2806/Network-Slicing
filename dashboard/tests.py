from mininet_api import run_on_host
import time

# -------------------------
# PING
# -------------------------

def ping_test(src, dst_ip, count):
    cmd = f"ping -c {count} {dst_ip}"
    return run_on_host(src, cmd)

# -------------------------
# IPERF
# -------------------------

def start_iperf_server(host):
    run_on_host(
        host,
        "iperf -s -u -p 9999 > /tmp/iperf_server.log 2>&1 &"
    )
    time.sleep(1)

def iperf_udp_test(src, dst_ip, bandwidth, duration):
    """
    bandwidth: int (Mbps)
    duration: int (s)
    """
    cmd = f"iperf -c {dst_ip} -u -p 9999 -b {bandwidth}M -t {duration}"
    return run_on_host(src, cmd)
