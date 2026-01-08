from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib.packet import udp
from ryu.lib.packet import tcp
from ryu.lib.packet import icmp


class ServiceSlicing(app_manager.RyuApp):
    # Versione di OpenFlow utilizzata
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(ServiceSlicing, self).__init__(*args, **kwargs)

        # Tabella MAC → porta per ciascun datapath (switch)
        # outport = self.mac_to_port[dpid][mac_address]
        self.mac_to_port = {
            1: {
                "00:00:00:00:00:01": 3,
                "00:00:00:00:00:02": 4
            },
            4: {
                "00:00:00:00:00:03": 3,
                "00:00:00:00:00:04": 4
            },
        }

        # Porta UDP utilizzata per identificare una specifica slice
        self.slice_TCport = 9999

        # Mappatura slice → porta di uscita per ciascun switch
        # outport = self.slice_ports[dpid][slicenumber]
        self.slice_ports = {
            1: {1: 1, 2: 2},
            4: {1: 1, 2: 2}
        }

        # Switch di bordo (edge / end switches)
        self.end_swtiches = [1, 4]

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """Gestione dell’evento di connessione dello switch"""
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Flow di default (table-miss): inoltra i pacchetti al controller
        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER
            )
        ]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions):
        """Installa una flow entry nello switch"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions
            )
        ]

        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=inst
        )

        datapath.send_msg(mod)

    def _send_package(self, msg, datapath, in_port, actions):
        """Invia il pacchetto immediatamente tramite PacketOut"""
        data = None
        ofproto = datapath.ofproto

        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = datapath.ofproto_parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )

        datapath.send_msg(out)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        """Gestione dei pacchetti ricevuti dal controller"""
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        # Ignora pacchetti LLDP
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst = eth.dst
        src = eth.src
        dpid = datapath.id

        # Forwarding basato su MAC conosciuti
        if dpid in self.mac_to_port:
            if dst in self.mac_to_port[dpid]:
                out_port = self.mac_to_port[dpid][dst]
                actions = [
                    datapath.ofproto_parser.OFPActionOutput(out_port)
                ]

                match = datapath.ofproto_parser.OFPMatch(
                    eth_dst=dst
                )

                self.add_flow(datapath, 1, match, actions)
                self._send_package(msg, datapath, in_port, actions)

            # UDP verso porta slice dedicata
            elif (
                pkt.get_protocol(udp.udp) and
                pkt.get_protocol(udp.udp).dst_port == self.slice_TCport
            ):
                slice_number = 1
                out_port = self.slice_ports[dpid][slice_number]

                match = datapath.ofproto_parser.OFPMatch(
                    in_port=in_port,
                    eth_dst=dst,
                    eth_type=ether_types.ETH_TYPE_IP,
                    ip_proto=0x11,  # UDP
                    udp_dst=self.slice_TCport,
                )

                actions = [
                    datapath.ofproto_parser.OFPActionOutput(out_port)
                ]

                self.add_flow(datapath, 2, match, actions)
                self._send_package(msg, datapath, in_port, actions)

            # UDP verso altre porte
            elif pkt.get_protocol(udp.udp):
                slice_number = 2
                out_port = self.slice_ports[dpid][slice_number]

                match = datapath.ofproto_parser.OFPMatch(
                    in_port=in_port,
                    eth_dst=dst,
                    eth_src=src,
                    eth_type=ether_types.ETH_TYPE_IP,
                    ip_proto=0x11,  # UDP
                    udp_dst=pkt.get_protocol(udp.udp).dst_port,
                )

                actions = [
                    datapath.ofproto_parser.OFPActionOutput(out_port)
                ]

                self.add_flow(datapath, 1, match, actions)
                self._send_package(msg, datapath, in_port, actions)

            # Traffico TCP
            elif pkt.get_protocol(tcp.tcp):
                slice_number = 2
                out_port = self.slice_ports[dpid][slice_number]

                match = datapath.ofproto_parser.OFPMatch(
                    in_port=in_port,
                    eth_dst=dst,
                    eth_src=src,
                    eth_type=ether_types.ETH_TYPE_IP,
                    ip_proto=0x06,  # TCP
                )

                actions = [
                    datapath.ofproto_parser.OFPActionOutput(out_port)
                ]

                self.add_flow(datapath, 1, match, actions)
                self._send_package(msg, datapath, in_port, actions)

            # Traffico ICMP
            elif pkt.get_protocol(icmp.icmp):
                slice_number = 2
                out_port = self.slice_ports[dpid][slice_number]

                match = datapath.ofproto_parser.OFPMatch(
                    in_port=in_port,
                    eth_dst=dst,
                    eth_src=src,
                    eth_type=ether_types.ETH_TYPE_IP,
                    ip_proto=0x01,  # ICMP
                )

                actions = [
                    datapath.ofproto_parser.OFPActionOutput(out_port)
                ]

                self.add_flow(datapath, 1, match, actions)
                self._send_package(msg, datapath, in_port, actions)

        # Flood sui nodi non terminali
        elif dpid not in self.end_swtiches:
            out_port = ofproto.OFPP_FLOOD
            actions = [
                datapath.ofproto_parser.OFPActionOutput(out_port)
            ]

            match = datapath.ofproto_parser.OFPMatch(
                in_port=in_port
            )

            self.add_flow(datapath, 1, match, actions)
            self._send_package(msg, datapath, in_port, actions)
