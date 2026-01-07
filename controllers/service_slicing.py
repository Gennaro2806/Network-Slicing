from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3

from ryu.lib.packet import packet, ethernet, ether_types, udp, tcp, icmp


class ServiceSlicing(app_manager.RyuApp):
    """
    Controller SDN che implementa il Service Slicing.
    Il traffico viene instradato su slice diverse in base
    al protocollo di trasporto e alle porte di destinazione.
    """

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        """
        Inizializza le strutture dati per il forwarding e
        la classificazione dei servizi.
        """
        super(ServiceSlicing, self).__init__(*args, **kwargs)

        # Tabelle MAC → porta per gli switch di bordo
        self.mac_to_port = {
            1: {"00:00:00:00:00:01": 3, "00:00:00:00:00:02": 4},
            4: {"00:00:00:00:00:03": 3, "00:00:00:00:00:04": 4},
        }

        # Porta UDP utilizzata per identificare una slice dedicata
        self.slice_TCport = 9999

        # Porte di uscita associate a ciascuna slice per switch
        self.slice_ports = {
            1: {1: 1, 2: 2},
            4: {1: 1, 2: 2},
        }

        # Switch di accesso alla rete
        self.end_switches = [1, 4]

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """
        Gestisce la connessione dello switch e installa
        la regola di table-miss.
        """
        datapath = ev.msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)
        ]
        self.add_flow(datapath, 0, match, actions)
        self.logger.info("Switch %s connected - table-miss installed", datapath.id)

    def add_flow(self, datapath, priority, match, actions):
        """
        Installa una regola di forwarding sullo switch.
        """
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath,
                                priority=priority,
                                match=match,
                                instructions=inst)
        datapath.send_msg(mod)

    def _send_packet(self, msg, datapath, in_port, actions):
        """
        Inoltra il pacchetto verso la porta selezionata.
        """
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath,
                                  buffer_id=msg.buffer_id,
                                  in_port=in_port,
                                  actions=actions,
                                  data=data)
        datapath.send_msg(out)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        """
        Gestisce i pacchetti in ingresso e applica
        le politiche di service slicing.
        """
        msg = ev.msg
        datapath = msg.datapath
        dpid = datapath.id
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        # Ignora pacchetti LLDP
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst = eth.dst
        src = eth.src

        # -------- Edge MAC forwarding --------
        if dpid in self.mac_to_port and dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
            actions = [parser.OFPActionOutput(out_port)]
            match = parser.OFPMatch(eth_dst=dst)
            self.add_flow(datapath, 2, match, actions)
            self._send_packet(msg, datapath, in_port, actions)
            return

        # -------- UDP traffic --------
        udp_pkt = pkt.get_protocol(udp.udp)
        if udp_pkt:
            slice_number = 1 if udp_pkt.dst_port == self.slice_TCport else 2
            out_port = self.slice_ports.get(dpid, {}).get(slice_number, ofproto.OFPP_FLOOD)

            match = parser.OFPMatch(
                in_port=in_port,
                eth_dst=dst,
                eth_src=src,
                eth_type=ether_types.ETH_TYPE_IP,
                ip_proto=0x11,  # UDP
                udp_dst=udp_pkt.dst_port
            )
            actions = [parser.OFPActionOutput(out_port)]
            priority = 2 if slice_number == 1 else 1
            self.add_flow(datapath, priority, match, actions)
            self._send_packet(msg, datapath, in_port, actions)
            return

        # -------- TCP traffic --------
        tcp_pkt = pkt.get_protocol(tcp.tcp)
        if tcp_pkt:
            slice_number = 2
            out_port = self.slice_ports.get(dpid, {}).get(slice_number, ofproto.OFPP_FLOOD)

            match = parser.OFPMatch(
                in_port=in_port,
                eth_dst=dst,
                eth_src=src,
                eth_type=ether_types.ETH_TYPE_IP,
                ip_proto=0x06  # TCP
            )
            actions = [parser.OFPActionOutput(out_port)]
            self.add_flow(datapath, 1, match, actions)
            self._send_packet(msg, datapath, in_port, actions)
            return

        # -------- ICMP traffic --------
        icmp_pkt = pkt.get_protocol(icmp.icmp)
        if icmp_pkt:
            slice_number = 2
            out_port = self.slice_ports.get(dpid, {}).get(slice_number, ofproto.OFPP_FLOOD)

            match = parser.OFPMatch(
                in_port=in_port,
                eth_dst=dst,
                eth_src=src,
                eth_type=ether_types.ETH_TYPE_IP,
                ip_proto=0x01  # ICMP
            )
            actions = [parser.OFPActionOutput(out_port)]
            self.add_flow(datapath, 1, match, actions)
            self._send_packet(msg, datapath, in_port, actions)
            return

        # -------- Core switch forwarding --------
        if dpid not in self.end_switches:
            out_port = ofproto.OFPP_FLOOD
            actions = [parser.OFPActionOutput(out_port)]
            match = parser.OFPMatch(in_port=in_port)
            self.add_flow(datapath, 1, match, actions)
            self._send_packet(msg, datapath, in_port, actions)
