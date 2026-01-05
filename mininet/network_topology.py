from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import OVSKernelSwitch, RemoteController
from mininet.cli import CLI
from mininet.link import TCLink

class NetworkSlicingTopo(Topo):
    def __init__(self):

        """
        NetworkSlicingTopo

        Classe che definisce una topologia di rete con 4 switch e 4 host, simulando due "slice" di rete:
        - Traffico video (s1-s2-s4, 10 Mbps).
        - Traffico HTTP (s1-s3-s4, 1 Mbps).
        """
        # Inizializza la topologia
        Topo.__init__(self)

        # Configurazioni per host e link
        host_config = dict(inNamespace=True)
        http_link_config = dict(bw=1)  # Link HTTP
        video_link_config = dict(bw=10)  # Link video
        host_link_config = dict()

        # Creazione degli switch
        for i in range(4):
            sconfig = {"dpid": "%016x" % (i + 1)}
            self.addSwitch(f"s{i + 1}", **sconfig)

        # Creazione degli host con indirizzi MAC unici
        for i in range(4):
            mac_addr = f"00:00:00:00:00:{i + 1:02x}"
            self.addHost(f"h{i + 1}", mac=mac_addr, **host_config)

        # Collegamenti tra gli switch
        self.addLink("s1", "s2", **video_link_config)
        self.addLink("s2", "s4", **video_link_config)
        self.addLink("s1", "s3", **http_link_config)
        self.addLink("s3", "s4", **http_link_config)

        # Collegamenti tra host e switch
        self.addLink("h1", "s1", **host_link_config)
        self.addLink("h2", "s1", **host_link_config)
        self.addLink("h3", "s4", **host_link_config)
        self.addLink("h4", "s4", **host_link_config)

topos = {"network_slicing_topo": (lambda: NetworkSlicingTopo())}

if __name__ == '__main__':
    """
    Avvia la rete Mininet con la topologia definita e il controller Ryu.
    Consente di interagire con la rete tramite la CLI di Mininet.
    """
    topo = NetworkSlicingTopo()
    # Crea la rete Mininet con la topologia e il controller remoto
    net = Mininet(topo=topo, switch=OVSKernelSwitch, build=False, autoSetMacs=True, autoStaticArp=True, link=TCLink)
    controller = RemoteController('c1', ip="127.0.0.1", port=6633)
    
    # Aggiungi il controller alla rete
    net.addController(controller)
    
    # Costruisci e avvia la rete
    net.build()
    net.start()

    # Avvia la CLI per interagire con la rete
    CLI(net)

    # Ferma la rete
    net.stop()
