# Network-Slicing
Network slicing di una topologia con controller ryu e mininet.
Contenuto della repository:

## Cartella controllers
Questa cartella contiene i controller Ryu utilizzati per implementare il network slicing:
- `service_slicing.py`: Controller per il service slicing.
- `topology_slicing.py`: Controller per il topology slicing.

## Cartella mininet
Questa cartella contiene gli script e i file relativi alla simulazione di rete con Mininet:
- `network_topology.py`: File che implementa la topologia di rete utilizzata nella simulazione.
- `dashboard.py`: Dashboard basata su Streamlit per visualizzare i dati e le metriche della rete.
- `monitor_network.py`: Script che monitora la rete in background, raccogliendo dati sul traffico e sulle prestazioni.
- `capacity_test.py`: Script per eseguire test di carico sulla rete.
- `run_tests.py`: Script per eseguire test automatici sulla topologia e sui controller.

## Come usare questo progetto

Per utilizzare il progetto aprire 5 terminali e lanciare i comandi indicati di seguito.

1. Primo terminale (topologia Mininet):
	 - ```cd ./mininet```
     - ```sudo python3 ./network_topology.py```

2. Secondo terminale (controller Ryu):
	 - ```cd ./controllers```
     - ```ryu-manager ./*_slicing.py```

3. Terzo terminale (monitoring):
	 - ```cd ./mininet```
     - ```sudo python3 monitor_network.py```

4. Quarto terminale (dashboard):
	 - ```cd ./mininet```
     - ```streamlit run ./dashboard.py```

5. Quinto terminale (test o capacity):
	 - ```cd ./mininet```
     - ```sudo python3 ./run_tests.py #oppure ./capacity_test.py```

     
Note:
- Assicurarsi di avere i permessi necessari per avviare Mininet (su Linux spesso è richiesto `sudo`).
- Verificare che `ryu-manager` e `streamlit` siano installati e disponibili nel PATH.

