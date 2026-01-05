from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3

from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types


class TopologySlicingMacToPort(app_manager.RyuApp):
    """
    Controller SDN basato su Ryu che implementa il Topology Slicing.
    La comunicazione è consentita solo tra coppie di host predefinite,
    forzando l'utilizzo di percorsi specifici all'interno della topologia.
    """

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        """
        Inizializza il controller e le strutture dati necessarie
        per il controllo delle slice topologiche.
        """
        super(TopologySlicingMacToPort, self).__init__(*args, **kwargs)

        # Tabella di apprendimento MAC → porta per ciascuno switch
        self.mac_to_port = {}

        # Indirizzi MAC degli host
        self.mac_h1 = "00:00:00:00:00:01"
        self.mac_h2 = "00:00:00:00:00:02"
        self.mac_h3 = "00:00:00:00:00:03"
        self.mac_h4 = "00:00:00:00:00:04"

        # Coppie di host autorizzate alla comunicazione
        self.allowed_pairs = {
            (self.mac_h1, self.mac_h3),
            (self.mac_h3, self.mac_h1),
            (self.mac_h2, self.mac_h4),
            (self.mac_h4, self.mac_h2)
        }

        # Switch ammessi per ciascuna slice topologica
        self.upper_path_switches = {1, 2, 4}  # Slice video
        self.lower_path_switches = {1, 3, 4}  # Slice HTTP

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """
        Gestisce l'evento di connessione di uno switch al controller.
        Installa una regola di table-miss per inoltrare al controller
        i pacchetti non corrispondenti ad alcun flow.
        """
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER
            )
        ]
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=0,
            match=match,
            instructions=inst
        )
        datapath.send_msg(mod)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        """
        Installa una regola di forwarding sullo switch.
        """
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        if buffer_id:
            mod = parser.OFPFlowMod(
                datapath=datapath,
                buffer_id=buffer_id,
                priority=priority,
                match=match,
                instructions=inst
            )
        else:
            mod = parser.OFPFlowMod(
                datapath=datapath,
                priority=priority,
                match=match,
                instructions=inst
            )

        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        """
        Gestisce i pacchetti ricevuti dal controller e applica
        le politiche di slicing topologico.
        """
        msg = ev.msg
        datapath = msg.datapath
        dpid = datapath.id
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        dst = eth.dst
        src = eth.src

        # Ignora pacchetti LLDP
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        # Inizializza la tabella MAC per lo switch corrente
        self.mac_to_port.setdefault(dpid, {})

        # Apprendimento MAC → porta
        self.mac_to_port[dpid][src] = in_port

        # Verifica se la comunicazione è autorizzata
        if (src, dst) not in self.allowed_pairs:
            self.logger.info(
                "Blocking packet from %s to %s on switch %s",
                src, dst, dpid
            )
            return

        # Controllo del percorso consentito in base alla slice
        if (src == self.mac_h1 and dst == self.mac_h3) or (src == self.mac_h3 and dst == self.mac_h1):
            if dpid not in self.upper_path_switches:
                self.logger.info(
                    "Blocking video slice packet from %s to %s on switch %s",
                    src, dst, dpid
                )
                return
        elif (src == self.mac_h2 and dst == self.mac_h4) or (src == self.mac_h4 and dst == self.mac_h2):
            if dpid not in self.lower_path_switches:
                self.logger.info(
                    "Blocking http slice packet from %s to %s on switch %s",
                    src, dst, dpid
                )
                return

        # Determinazione della porta di uscita
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]
        match = parser.OFPMatch(in_port=in_port, eth_src=src, eth_dst=dst)

        # Installazione del flow
        if msg.buffer_id != ofproto.OFP_NO_BUFFER:
            self.add_flow(datapath, 1, match, actions, msg.buffer_id)
            return
        else:
            self.add_flow(datapath, 1, match, actions)

        # Inoltro del pacchetto
        data = msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None
        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data
        )

        datapath.send_msg(out)
