import subprocess
import time
import os
import sys
import pandas as pd

# File di riferimento
LOG_FILE = "capacity_test_results.log"
DATA_FILE = "traffic_data.csv"

def fix_perms(path):
    """Sblocca i permessi del log per l'utente non-root."""
    if os.path.exists(path) and "SUDO_UID" in os.environ:
        os.chown(path, int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"]))

def log(msg):
    """Stampa a video e scrive nel file di log."""
    print(msg)
    with open(LOG_FILE, "a") as f: f.write(msg + "\n")
    fix_perms(LOG_FILE)

def get_loss_from_csv():
    """Legge il packet loss in tempo reale dal CSV senza bloccare il file."""
    try:
        if not os.path.exists(DATA_FILE):
            return 0.0
        
        # Apriamo in modalità lettura con 'newline' per evitare conflitti
        with open(DATA_FILE, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            if len(lines) < 2: # Solo header o vuoto
                return 0.0
            
            # Scorriamo il file al contrario per trovare l'ultima riga della Standard Slice
            for line in reversed(lines):
                parts = line.strip().split(',')
                # Assicurati che l'indice coincida con la colonna 'Loss' 
                # Se il CSV è: Timestamp, Interface, Mbps, Latency, Jitter, Loss -> Loss è l'indice 5
                if len(parts) >= 6 and "Standard" in parts[1]:
                    try:
                        loss_value = float(parts[5])
                        return loss_value
                    except ValueError:
                        continue
        return 0.0
    except Exception as e:
        print(f"Errore accesso CSV: {e}")
        return 0.0

def run_host_cmd(host, command):
    """Esegue un comando nel namespace dell'host Mininet."""
    pid = subprocess.getoutput(f"ps -eo pid,cmd | grep 'mininet:{host}' | grep -v grep | awk '{{print $1}}'").strip()
    if not pid: return "Host non trovato"
    return subprocess.getoutput(f"sudo nsenter -t {pid} -n {command}")

def main():
    # Pulizia iniziale di eventuali processi iperf rimasti appesi
    subprocess.run("sudo pkill iperf", shell=True, stderr=subprocess.DEVNULL)
    
    with open(LOG_FILE, "w") as f: 
        f.write(f"--- ANALISI DI SATURAZIONE: {time.strftime('%H:%M:%S')} ---\n")
    fix_perms(LOG_FILE)

    log("Avvio Server iPerf su H4 (Destinazione)...")
    pid_h4 = subprocess.getoutput(f"ps -eo pid,cmd | grep 'mininet:h4' | grep -v grep | awk '{{print $1}}'").strip()
    subprocess.Popen(f"sudo nsenter -t {pid_h4} -n iperf -s -u > /dev/null 2>&1", shell=True)
    time.sleep(2)

    # Parametri del test
    current_bw = 0.2
    step = 0.1  # Step più piccolo (100Kbps) per una precisione maggiore
    threshold = 10.0

    log(f"Target: Rilevare il limite della Standard Slice (Soglia Loss > {threshold}%)")
    log("--------------------------------------------------------------------------")

    while True:
        log(f">>> Incremento carico: {current_bw:.2f} Mbps")
        
        # Genera traffico per 4 secondi
        run_host_cmd("h2", f"iperf -c 10.0.0.4 -u -b {current_bw}M -t 4")
        
        # Breve attesa per permettere al monitor di scrivere nel CSV
        time.sleep(1.2)
        
        # Controllo della perdita pacchetti
        current_loss = get_loss_from_csv()
        log(f"   [Monitor] Perdita rilevata: {current_loss}%")

        if current_loss > threshold:
            log(f"\n[!!!] SOGLIA SUPERATA: {current_loss}%")
            log(f"Il limite della slice è stato raggiunto a {current_bw:.2f} Mbps.")
            break
            
        # Sicurezza per evitare loop infiniti se qualcosa non va nel monitor
        if current_bw >= 5.0:
            log("\n[?] Test interrotto: raggiunto limite di sicurezza di 5 Mbps senza rilevare loss.")
            break
            
        current_bw += step

    # Pulizia e chiusura
    subprocess.run("sudo pkill iperf", shell=True)
    log("\n--- TEST TERMINATO CON SUCCESSO ---")

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Errore: lo script deve essere eseguito con sudo!")
    else:
        main()