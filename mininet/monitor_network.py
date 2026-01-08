import time
import csv
import os
import subprocess

DATA_FILE = "traffic_data.csv"

# Associazioni: Interfaccia -> [Etichetta, Host Sorgente, IP Destinazione]
INTERFACES = {
    "s1-eth1": {"label": "Video Slice (10 Mbps)", "src": "h1", "target": "10.0.0.3"},
    "s1-eth2": {"label": "Standard Slice (1 Mbps)", "src": "h2", "target": "10.0.0.4"}
}

THRESHOLD_MBPS = 0.05
HEARTBEAT_INTERVAL = 5

def get_host_pid(host):
    pid = subprocess.getoutput(f"ps -eo pid,cmd | grep 'mininet:{host}' | grep -v grep | awk '{{print $1}}'").strip()
    return pid

def get_tx_bytes(interface):
    path = f"/sys/class/net/{interface}/statistics/tx_bytes"
    try:
        with open(path, "r") as f: return int(f.read())
    except: return None

def get_performance_stats(src_host, target_ip):
    """Esegue il ping dall'interno del namespace dell'host sorgente."""
    pid = get_host_pid(src_host)
    if not pid: return 0, 0, 100
    
    # Usiamo ping standard con timeout brevi per non bloccare il monitor
    cmd = f"sudo nsenter -t {pid} -n ping -c 3 -i 0.2 -W 1 {target_ip}"
    res = subprocess.getoutput(cmd)
    
    try:
        # Parsing rtt min/avg/max/mdev = 0.052/0.062/0.072/0.010 ms
        if "avg" in res:
            stats_line = [line for line in res.split('\n') if 'rtt' in line][0]
            values = stats_line.split('=')[1].strip().split('/')
            latency = float(values[1])
            jitter = float(values[3].split()[0]) # mdev è una buona approssimazione del jitter
            
            loss_line = [line for line in res.split('\n') if 'packet loss' in line][0]
            loss = float(loss_line.split('%')[0].split()[-1])
            return latency, jitter, loss
        else:
            return 0, 0, 100
    except:
        return 0, 0, 100

def monitor():
    with open(DATA_FILE, "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "Interface", "Mbps", "Latency", "Jitter", "Loss"])

    print("Monitoraggio Intelligente (Ping dai Namespace) avviato...")
    prev_bytes = {iface: get_tx_bytes(iface) for iface in INTERFACES}
    last_write_time = 0
    was_active = {iface: False for iface in INTERFACES}

    while True:
        time.sleep(1)
        current_time_str = time.strftime("%H:%M:%S")
        current_time_unix = time.time()
        data_to_write = []
        should_heartbeat = (current_time_unix - last_write_time) >= HEARTBEAT_INTERVAL

        for iface, cfg in INTERFACES.items():
            curr = get_tx_bytes(iface)
            if curr is None: continue
            
            mbps = round(((curr - prev_bytes[iface]) * 8) / 1000000.0, 3)
            prev_bytes[iface] = curr
            
            if mbps > THRESHOLD_MBPS or was_active[iface] or should_heartbeat:
                lat, jit, loss = get_performance_stats(cfg['src'], cfg['target'])
                data_to_write.append([current_time_str, cfg['label'], mbps, lat, jit, loss])
                was_active[iface] = (mbps > THRESHOLD_MBPS)

        if data_to_write:
            with open(DATA_FILE, "a", newline='') as f:
                writer = csv.writer(f)
                writer.writerows(data_to_write)
            last_write_time = current_time_unix

if __name__ == "__main__":
    if os.geteuid() != 0: print("Usa sudo!"); exit()
    monitor()