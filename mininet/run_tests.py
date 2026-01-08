import subprocess
import time
import os
import sys

LOG_FILE = "test_results.log"

def fix_perms(path):
    if os.path.exists(path) and "SUDO_UID" in os.environ:
        os.chown(path, int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"]))

def log(msg):
    print(msg)
    with open(LOG_FILE, "a") as f: f.write(msg + "\n")
    fix_perms(LOG_FILE)

def run_host_cmd(host, command, wait=False):
    """
    Esegue un comando nell'host. 
    Se wait=False, prova a lanciarlo in background reale usando nohup.
    """
    pid = subprocess.getoutput(f"ps -eo pid,cmd | grep 'mininet:{host}' | grep -v grep | awk '{{print $1}}'").strip()
    if not pid: return "Host non trovato"
    
    if "iperf -s" in command:
        # Forza l'esecuzione in background totale per evitare blocchi
        full_cmd = f"sudo nsenter -t {pid} -n nohup {command} > /dev/null 2>&1 &"
        subprocess.Popen(full_cmd, shell=True)
        return f"Server iPerf avviato su {host}"
    else:
        full_cmd = f"sudo nsenter -t {pid} -n {command}"
        return subprocess.getoutput(full_cmd)

def main():
    # Pulizia iniziale
    subprocess.run("sudo pkill iperf", shell=True, stderr=subprocess.DEVNULL)
    with open(LOG_FILE, "w") as f: f.write("--- REPORT TEST SDN AVANZATO ---\n")
    fix_perms(LOG_FILE)
    
    log(f"Inizio sessione: {time.strftime('%H:%M:%S')}")
    
    # --- TEST 1: PING ---
    log("\n[1] Verifica Connettività (H1 -> H3):")
    res_ping = run_host_cmd("h1", "ping -c 4 10.0.0.3")
    log(res_ping)

    # --- TEST 2: VIDEO SLICE (UDP 9999) ---
    log("\n[2] Test Video Slice (UDP 9999) - Target 10Mbps:")
    run_host_cmd("h3", "iperf -s -u -p 9999") # Avvia server
    time.sleep(2) # Attesa cruciale per attivazione server
    
    log("Generazione traffico in corso...")
    # Eseguiamo il client (questo deve essere bloccante per durare 10s)
    res_video = run_host_cmd("h1", "iperf -c 10.0.0.3 -u -p 9999 -b 10M -t 10")
    log(res_video)
    
    # --- TEST 3: STANDARD SLICE (TCP) ---
    log("\n[3] Test Standard Slice (TCP) - Target 1Mbps:")
    run_host_cmd("h4", "iperf -s") # Avvia server su H4
    time.sleep(2)
    
    log("Generazione traffico in corso...")
    res_tcp = run_host_cmd("h2", "iperf -c 10.0.0.4 -t 10")
    log(res_tcp)

    # Pulizia finale
    subprocess.run("sudo pkill iperf", shell=True)
    log(f"\nFine test: {time.strftime('%H:%M:%S')}")

if __name__ == "__main__":
    if os.geteuid() != 0: 
        print("Esegui con sudo!"); sys.exit()
    main()