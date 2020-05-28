import csv
import math
import threading
from typing import Optional
from desvirt.vif import VirtualInterface
from desvirt.vnet import VirtualNet


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

    def __init__(self, from_if: VirtualInterface, to_if: VirtualInterface, net: VirtualNet, distance: float,
                 noise_floor: float, sensitivity_offset: float, tx_power: float, frequency: float = 2440,
                 temperature_file: str = None):
        self.thread = threading.Thread(target=self.box())
        self.from_if = from_if
        self.to_if = to_if
        self.name = f'mb-{self.from_if.nicname}-{self.to_if.nicname}'
        self.number = MiddleBox.number
        self.in_if = VirtualInterface(macaddr=None, up=True, net=net, nicname=f'{self.name}-in', create=True,
                                          node=None, tap=f'mb{self.number}i')
        self.out_if = VirtualInterface(macaddr=None, up=True, net=net, nicname=f'{self.name}-out', create=True,
                                           node=None, tap=f'mb{self.number}o')
        MiddleBox.number = MiddleBox.number + 1
        self.distance = distance  # in meters
        self.noise_floor = noise_floor
        self.sensitivity_offset = sensitivity_offset
        self.tx_power = tx_power
        self.frequency = frequency  # in megahertz
        self.fspl = 20 * math.log10(distance) + 20 * math.log10(frequency) - 27.55
        self.temperature_file = temperature_file

    def start(self):
        temperatures = parse_temperatures(self.temperature_file)
        # TODO start box process thread
        self.thread.start()

    def delete(self):
        # if self.thread is not None:
        #     self.thread.join()
        if self.in_if and self.out_if is not None:
            self.out_if.delete()
            self.in_if.delete()

    def __del__(self):
        self.delete()

    def box(self):
        # TODO alter passing packages
        pass

    def calculate_rx_power(self) -> Optional[float]:
        # TODO add temp offset
        if (self.tx_power - self.fspl) > (self.noise_floor + self.sensitivity_offset):
            return self.tx_power - self.fspl
        else:
            return None

    def get_temp_signal_offset(self, temp: float):
        # TODO implement LUT
        loss = temp
        return loss

    def calculate_ber(self) -> float:
        snr = self.calculate_rx_power() / self.noise_floor
        return min(8 * math.exp(-0.6 * (snr + 0.5)), 1.0)
