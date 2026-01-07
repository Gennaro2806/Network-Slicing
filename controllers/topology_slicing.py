from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3

from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types


class TopologySlicingMacToPort(app_manager.RyuApp):
    """
    Controller SDN che implementa il Topology Slicing
    basato su MAC address e percorsi consentiti.
    """

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(TopologySlicingMacToPort, self).__init__(*args, **kwargs)

        # Tabella MAC → porta per ogni switch
        self.mac_to_port = {}

        # MAC address degli host
        self.mac_h1 = "00:00:00:00:00:01"
        self.mac_h2 = "00:00:00:00:00:02"
        self.mac_h3 = "00:00:00:00:00:03"
        self.mac_h4 = "00:00:00:00:00:04"

        # Coppie di host autorizzate (slice)
        self.allowed_pairs = {
            (self.mac_h1, self.mac_h3),
            (self.mac_h3, self.mac_h1),
            (self.mac_h2, self.mac_h4),
            (self.mac_h4, self.mac_h2),
        }

        # Switch ammessi per ciascuna slice
        self.upper_path_switches = {1, 2, 4}  # H1 ↔ H3
        self.lower_path_switches = {1, 3, 4}  # H2 ↔ H4

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """
        Installa la regola di table-miss.
        """
        datapath = ev.msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER
            )
        ]

        inst = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions
            )
        ]

        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=0,
            match=match,
            instructions=inst
        )
        datapath.send_msg(mod)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        """
        Installa una regola di forwarding.
        """
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        inst = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions
            )
        ]

        if buffer_id is not None:
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
        Gestisce i pacchetti in ingresso applicando
        il topology slicing.
        """
        msg = ev.msg
        datapath = msg.datapath
        dpid = datapath.id
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        # Ignora LLDP
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        src = eth.src
        dst = eth.dst

        # Inizializza la tabella MAC per questo switch
        self.mac_to_port.setdefault(dpid, {})

        # Apprendimento MAC
        self.mac_to_port[dpid][src] = in_port

        # Verifica se la comunicazione è consentita
        if (src, dst) not in self.allowed_pairs:
            self.logger.info("Flusso bloccato: %s -> %s", src, dst)
            return

        # Controllo slice topologica
        if (src, dst) in {(self.mac_h1, self.mac_h3), (self.mac_h3, self.mac_h1)}:
            if dpid not in self.upper_path_switches:
                self.logger.info(
                    "H1-H3 attraversa switch NON ammesso (dpid=%s)", dpid
                )
                return

        if (src, dst) in {(self.mac_h2, self.mac_h4), (self.mac_h4, self.mac_h2)}:
            if dpid not in self.lower_path_switches:
                self.logger.info(
                    "H2-H4 attraversa switch NON ammesso (dpid=%s)", dpid
                )
                return

        # Determina la porta di uscita
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # Installa la regola
        match = parser.OFPMatch(
            in_port=in_port,
            eth_src=src,
            eth_dst=dst
        )

        if msg.buffer_id != ofproto.OFP_NO_BUFFER:
            self.add_flow(datapath, 1, match, actions, msg.buffer_id)
            return
        else:
            self.add_flow(datapath, 1, match, actions)

        # Invia il pacchetto
        data = msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None
        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data
        )
        datapath.send_msg(out)
