from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types

class TopologySlicingMacToPort(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(TopologySlicingMacToPort, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        # MAC address degli host
        self.mac_h1 = "00:00:00:00:00:01"
        self.mac_h2 = "00:00:00:00:00:02"
        self.mac_h3 = "00:00:00:00:00:03"
        self.mac_h4 = "00:00:00:00:00:04"

        # Coppie autorizzate (slice)
        self.allowed_pairs = {
            (self.mac_h1, self.mac_h3),
            (self.mac_h3, self.mac_h1),
            (self.mac_h2, self.mac_h4),
            (self.mac_h4, self.mac_h2),
        }
        # Mappatura switch ammessi
        self.upper_path_switches = {1, 2, 4}
        self.lower_path_switches = {1, 3, 4}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=0, match=match, instructions=inst)
        datapath.send_msg(mod)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id, priority=priority, match=match, instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority, match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        dpid = datapath.id
        parser = datapath.ofproto_parser
        in_port = msg.match["in_port"]
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        dst = eth.dst
        src = eth.src

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port

        if (src, dst) not in self.allowed_pairs:
            return

        # Verifica compatibilità dpid con la slice
        if (src == self.mac_h1 and dst == self.mac_h3) or (src == self.mac_h3 and dst == self.mac_h1):
            if dpid not in self.upper_path_switches:
                return
        elif (src == self.mac_h2 and dst == self.mac_h4) or (src == self.mac_h4 and dst == self.mac_h2):
            if dpid not in self.lower_path_switches:
                return

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = datapath.ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]
        match = parser.OFPMatch(in_port=in_port, eth_src=src, eth_dst=dst)
        self.add_flow(datapath, 1, match, actions)
        
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id, in_port=in_port, actions=actions, data=msg.data if msg.buffer_id == datapath.ofproto.OFP_NO_BUFFER else None)
        datapath.send_msg(out)