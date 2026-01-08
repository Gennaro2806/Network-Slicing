import time

def read_rx_bytes(interface):
    with open(f"/sys/class/net/{interface}/statistics/rx_bytes") as f:
        return int(f.read())

def measure_throughput(interface, interval=1):
    rx1 = read_rx_bytes(interface)
    time.sleep(interval)
    rx2 = read_rx_bytes(interface)

    # Mbps
    return (rx2 - rx1) * 8 / 1_000_000
