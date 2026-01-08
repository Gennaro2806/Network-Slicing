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

