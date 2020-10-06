import csv
import logging
import math
import threading
import random
import time
from time import sleep
from typing import Optional, Union
from desvirt.vif import VirtualInterface
from desvirt.vnet import VirtualNet
import scapy.supersocket
from scapy import sendrecv, packet, all
from scapy.utils import hexdump, wrpcap

initial_time: float = time.perf_counter_ns()


def parse_temperatures(temperature_file: str) -> iter:
    if temperature_file is None:
        return iter([(0, 15)])
    with open(temperature_file) as csvfile:
        temperature_lines = csv.reader(csvfile)
        i = iter(list(temperature_lines))
        print(i)
        return i


def get_time() -> float:
    t = time.perf_counter_ns() - initial_time
    print(f'time: {t}')
    return t


def calculate_flips(ber: float, number_of_bits: int) -> int:
    flips: int = 0
    for i in range(number_of_bits):
        if random.random() < ber:
            flips = flips + 1
    return flips


class MiddleBox:
    list_of_boxes = []
    thread = None
    number = 0

    def __init__(self, from_if: VirtualInterface, to_if: VirtualInterface, net: VirtualNet, distance: float, noise_floor: float, sensitivity_offset: float, tx_power: float, frequency: float = 2440, delay: float = 0, packetloss: float = 0, temperature_file: str = None):
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
        self.temperature_file = './temp'#temperature_file
        self.temperature_lines = parse_temperatures(self.temperature_file)
        self.current_temperature = (0, 0)
        MiddleBox.list_of_boxes.append(self)
        self.stopbox = threading.Event()

    def get_temperature(self) -> float:
        t = get_time()
        logging.getLogger("").debug("called get_temperature")
        if self.current_temperature[0] == 0:
            new_line: tuple = tuple(next(self.temperature_lines))
            print(new_line)
            self.current_temperature: tuple = (self.current_temperature[0] + float(new_line[0]), new_line[1])
            return float(self.current_temperature[1])
        if t <= self.current_temperature[0]:
            print(self.current_temperature)
            return float(self.current_temperature[1])
        while self.current_temperature[0] > t:
            new_line: tuple = tuple(next(self.temperature_lines))
            print(new_line)
            if new_line[0] == "LOOP":
                continue
            self.current_temperature: tuple = (self.current_temperature[0] + float(new_line[0]), new_line[1])
        print(f'temp tuple: {self.current_temperature}')
        return float(self.current_temperature[1])

    def start(self):
        # start box process thread
        print("start middlebox")
        self.thread = threading.Thread(target=self.box, daemon=True)
        self.thread.start()

    def stop_sniff(self, p: packet.Packet) -> bool:
        return self.stopbox.isSet()

    def box(self):
        bpf_filter = f"ether src host {self.from_if.macaddr} and ether dst host {self.to_if.macaddr}"
        print(f"BPF in mb{self.number}: {bpf_filter}")
        sendrecv.bridge_and_sniff(self.from_if.tap, self.to_if.tap, filter=bpf_filter, xfrm12=self.alter_pkt,
                                  xfrm21=self.block_pkt, stop_filter=self.stop_sniff)

    def alter_pkt(self, p: packet.Packet) -> Union[packet.Packet, bool]:
        # """Return True to forward, False to drop and Packet so send an alternative packet"""
        # wrpcap(f"/home/linda/Documents/MA/2020-ma-fliss-riot-simulation/evaluation/temp{self.number}.cap",
        #        p, append=True)
        ber = self.calculate_ber()
        print(f'BER: {ber}')
        # ber = 0.0001
        if (self.packet_loss > 0 and random.randint(0, 100) < self.packet_loss) or ber == 1:  # apply packet loss
            return False
        payload = p.payload
        p.show()
        ether = scapy.all.Ether(dst=p[scapy.all.Ether].dst, src=p[scapy.all.Ether].src, type=p[scapy.all.Ether].type)
        # ether.type = 0xa0ed ?
        if payload is not None:
            number_of_bit_flips = calculate_flips(ber, len(payload)*8)
            payload = scapy.utils.corrupt_bits(payload, n=number_of_bit_flips)
            p = ether / payload
            p.show()
        if self.delay > 0:  # apply packet delay
            sleep(self.delay)
        return p

    def block_pkt(self, p: packet.Packet) -> bool:
        return False

    def calculate_rx_power(self) -> Optional[float]:
        # add temp offset
        offset: float = self.get_temp_signal_offset(self.get_temperature())
        print(f'Offset: {offset}')
        if (self.tx_power - self.fspl + offset) > (self.noise_floor + self.sensitivity_offset):
            return self.tx_power - self.fspl + offset
        else:
            return None

    def calculate_ber(self) -> float:
        rx: float = self.calculate_rx_power()
        if not rx:
            return 1
        snr: float = rx - self.noise_floor
        print(f'SNR: {snr}')
        if snr < 0:
            snr = 0
        # for ber on chip codes use: return min(8 * math.exp(-0.6 * (snr + 0.5)), 1.0)
        ber: float = math.exp(-0.6 * (snr + 0.5))
        return self.limit_ber(ber)

    def limit_ber(self, ber: float) -> float:
        # ber = round(ber, 6)
        if ber > 0.99:
            ber = 0.99
        elif ber < 0:
            ber = 0
        return ber

    def get_temp_signal_offset(self, temp: float) -> float:
        if temp <= 3.0:
            return 0.6
        if temp <= 4.0:
            return 0.55
        if temp <= 5.0:
            return 0.6
        if temp <= 6.0:
            return 0.6
        if temp <= 7.0:
            return 0.6
        if temp <= 8.0:
            return 2.24
        if temp <= 9.0:
            return 0.68
        if temp <= 10.0:
            return 0.22
        if temp <= 11.0:
            return 2.13
        if temp <= 12.0:
            return 1.07
        if temp <= 13.0:
            return -1.92
        if temp <= 14.0:
            return -4.4
        if temp <= 15.0:
            return -2.73
        if temp <= 16.0:
            return -3.26
        if temp <= 17.0:
            return -1.73
        if temp <= 18.0:
            return -3.03
        if temp <= 19.0:
            return -1.8
        if temp <= 20.0:
            return -3.9
        if temp <= 21.0:
            return -4.57
        if temp <= 22.0:
            return -4.4
        if temp <= 23.0:
            return -4.28
        if temp <= 24.0:
            return -4.03
        if temp <= 25.0:
            return -4.0
        if temp <= 26.0:
            return -4.0
        if temp <= 27.0:
            return -3.71
        if temp <= 28.0:
            return -3.4
        if temp <= 29.0:
            return -3.52
        if temp <= 30.0:
            return -3.4
        if temp <= 31.0:
            return -3.81
        if temp <= 32.0:
            return -3.68
        return -4.0
