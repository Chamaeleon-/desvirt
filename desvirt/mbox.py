import csv
import math
import subprocess
import threading
import random
from time import sleep
from typing import Optional, Union

from scapy.layers import l2

from desvirt.vif import VirtualInterface
from desvirt.vnet import VirtualNet
import scapy.supersocket
from scapy import sendrecv, packet, layers, all
from scapy.utils import hexdump, wrpcap


def parse_temperatures(temperature_file):
    with open(temperature_file) as csvfile:
        temperature_lines = csv.reader(csvfile)
        return list(temperature_lines)


class MiddleBox:
    list_of_boxes = []
    thread = None
    temp_offset_lut = None
    in_if = None
    out_if = None
    number = 0

    def __init__(self, from_if: VirtualInterface, to_if: VirtualInterface, net, distance: float,
                 noise_floor: float, sensitivity_offset: float, tx_power: float, frequency: float = 2440,
                 delay: float = 0, packetloss: float = 0, temperature_file: str = None):
        self.from_if = from_if
        self.to_if = to_if
        self.name = f'mb-{self.from_if.nicname}-{self.to_if.nicname}'
        self.number = MiddleBox.number
        MiddleBox.number = MiddleBox.number + 1
        self.delay = delay  # in seconds
        self.packet_loss = packetloss  # in percentage
        self.distance = distance  # in meters
        self.noise_floor = noise_floor  # in dB
        self.sensitivity_offset = sensitivity_offset  # in dB
        self.tx_power = tx_power  # in dB
        self.frequency = frequency  # in megahertz
        self.fspl = 20 * math.log10(distance) + 20 * math.log10(frequency) - 27.55
        self.temperature_file = temperature_file
        # self.in_if = VirtualInterface(macaddr=None, up=True, net=net, nicname=f'{self.name}-in', create=True,
        #                                   node=None, tap=f'mb{self.number}i')
        # self.out_if = VirtualInterface(macaddr=None, up=True, net=net, nicname=f'{self.name}-out', create=True,
        #                                    node=None, tap=f'mb{self.number}o')
        # self.ingoing = scapy.supersocket.TunTapInterface(iface=self.in_if.tap)
        # self.outgoing = scapy.supersocket.TunTapInterface(iface=self.out_if.tap)
        MiddleBox.list_of_boxes.append(self)
        self.stopbox = threading.Event()

    def start(self):
        # temperatures = parse_temperatures(self.temperature_file)
        # start box process thread
        print("start middlebox")
        self.thread = threading.Thread(target=self.box, daemon=True)
        self.thread.start()

    def delete(self):
        # if self.thread is not None:
        #     self.thread.join()
        if self.in_if and self.out_if is not None:
            self.stopbox.set()
            self.thread.join(2.0)
            # self.ingoing.close()
            # self.outgoing.close()
            sleep(1.5)
            self.out_if.delete()
            self.in_if.delete()

    def stop_sniff(self, p: packet.Packet) -> bool:
        return self.stopbox.isSet()

    def box(self):
        bpf_filter = f"ether src host {self.from_if.macaddr} and ether dst host {self.to_if.macaddr}"
        print(f"BPF in mb{self.number}: {bpf_filter}")
        sendrecv.bridge_and_sniff(self.from_if.tap, self.to_if.tap, filter=bpf_filter, xfrm12=self.alter_pkt,
                                  xfrm21=self.block_pkt, stop_filter=self.stop_sniff)

    def alter_pkt(self, p: packet.Packet) -> Union[packet.Packet, bool]:
        """Return True to forward, False to drop and Packet so send an alternative packet"""
        wrpcap(f"/home/linda/Documents/MA/2020-ma-fliss-riot-simulation/evaluation/temp{self.number}.cap",
               p, append=True)
        payload = p.payload
        # print(payload.show()
        # p[scapy.all.Ether].show()
        ether = scapy.all.Ether(dst=p[scapy.all.Ether].dst, src=p[scapy.all.Ether].src, type=p[scapy.all.Ether].type)
        if payload is not None:
            payload = scapy.utils.corrupt_bits(payload, p=self.calculate_ber(), n=None)
            p = ether / scapy.all.IPv6(payload)
            p.show()

        if self.packet_loss > 0 and random.randint(0, 100) < self.packet_loss:  # apply packet loss
            return False
        if self.delay > 0:  # apply packet delay
            sleep(self.delay)
        return True

    def block_pkt(self, p: packet.Packet) -> bool:
        return False

    def calculate_rx_power(self) -> Optional[float]:
        # TODO add temp offset
        if (self.tx_power - self.fspl) > (self.noise_floor + self.sensitivity_offset):
            return self.tx_power - self.fspl
        else:
            return 1

    def get_temp_signal_offset(self, temp: float):
        # TODO implement LUT
        loss = temp
        return loss

    def calculate_ber(self) -> float:
        snr = self.calculate_rx_power() / self.noise_floor
        return min(8 * math.exp(-0.6 * (snr + 0.5)), 1.0)
