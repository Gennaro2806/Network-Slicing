import subprocess
import time
import os
import sys

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

def get_max_loss_from_recent_csv(num_rows=5):
    """
    Legge le ultime righe del CSV e restituisce il valore MASSIMO di loss 
    trovato per la Standard Slice tra le ultime 'num_rows' occorrenze.
    """
    try:
        if not os.path.exists(DATA_FILE):
            return 0.0
        
        found_losses = []
        with open(DATA_FILE, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            # Analizziamo il file a ritroso
            for line in reversed(lines):
                parts = line.strip().split(',')
                # Indici: 1=Interface, 5=Loss
                if len(parts) >= 6 and "Standard" in parts[1]:
                    try:
                        found_losses.append(float(parts[5]))
                    except ValueError:
                        continue
                
                # Ci fermiamo quando abbiamo raccolto abbastanza campioni recenti
                if len(found_losses) >= num_rows:
                    break
        
        return max(found_losses) if found_losses else 0.0
    except Exception as e:
        print(f"Errore accesso CSV: {e}")
        return 0.0

def run_host_cmd(host, command, background=False):
    """Esegue un comando nel namespace dell'host Mininet."""
    pid = subprocess.getoutput(f"ps -eo pid,cmd | grep 'mininet:{host}' | grep -v grep | awk '{{print $1}}'").strip()
    if not pid: return "Host non trovato"
    
    full_cmd = f"sudo nsenter -t {pid} -n {command}"
    if background:
        subprocess.Popen(f"nohup {full_cmd} > /dev/null 2>&1 &", shell=True)
        return "Comando avviato in background"
    else:
        return subprocess.getoutput(full_cmd)

def main():
    start_test_time = time.time()
    TIMEOUT_LIMIT = 100 # Timer di sicurezza 100 secondi
    
    # Pulizia iniziale
    subprocess.run("sudo pkill iperf", shell=True, stderr=subprocess.DEVNULL)
    
    with open(LOG_FILE, "w") as f: 
        f.write(f"--- CAPACITY TEST (Soglia > 10% | Timeout 100s) ---\n")
    fix_perms(LOG_FILE)

    log("Avvio Server iPerf su H4...")
    run_host_cmd("h4", "iperf -s -u", background=True)
    time.sleep(2)

    current_bw = 0.2
    step = 0.1
    threshold = 10.0

    log(f"Inizio test di saturazione. Tempo limite: {TIMEOUT_LIMIT}s")
    log("--------------------------------------------------------------------------")

    while True:
        # 1. Controllo Timer di Sicurezza
        elapsed = time.time() - start_test_time
        if elapsed >= TIMEOUT_LIMIT:
            log(f"\n[!] STOP: Raggiunto timer limite di {TIMEOUT_LIMIT} secondi.")
            break

        log(f"\n>>> Carico: {current_bw:.2f} Mbps (Tempo trascorso: {int(elapsed)}s)")
        
        # 2. Genera traffico (3 secondi di iperf per velocizzare il test)
        run_host_cmd("h2", f"iperf -c 10.0.0.4 -u -b {current_bw}M -t 3")
        
        # 3. Attesa per il monitoraggio
        time.sleep(1.5)
        
        # 4. Controllo robusto del Loss (Analisi ultime 5 righe)
        current_loss = get_max_loss_from_recent_csv(num_rows=5)
        log(f"   [Monitor CSV] Massimo Loss recente rilevato: {current_loss}%")

        # 5. Condizione di interruzione
        if current_loss > threshold:
            log(f"\n[!!!] SOGLIA {threshold}% SUPERATA!")
            log(f"La slice è collassata a {current_bw:.2f} Mbps con perdita del {current_loss}%.")
            break
            
        current_bw += step
        
        if current_bw > 5.0:
            log("\nFine test: raggiunta capacità massima di sicurezza (5 Mbps).")
            break

    # Pulizia finale
    subprocess.run("sudo pkill iperf", shell=True)
    duration = int(time.time() - start_test_time)
    log(f"\n--- TEST COMPLETATO IN {duration} SECONDI ---")

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Errore: devi eseguire con sudo!")
    else:
        main()