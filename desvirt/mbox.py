import csv
import math
from desvirt import vif


def parse_temperatures(temperature_file):
    with open(temperature_file) as csvfile:
        temperature_lines = csv.reader(csvfile)
        return list(temperature_lines)


class MiddleBox:
    in_if = None
    out_if = None
    from_if = None
    to_if = None
    temperature_file = None
    distance = None  # in meters
    noise_floor = None
    sensitivity = None
    tx_power = None
    temp_offset_lut = None
    frequency = 2440  # in megahertz
    fspl = 20 * math.log10(distance) + 20 * math.log10(frequency) - 27.55

    def __init__(self):
        self.in_if = vif.VirtualInterface.create()
        self.out_if = vif.VirtualInterface.create()

    def start(self):
        temperatures = parse_temperatures(self.temperature_file)
        # TODO start box process thread
        pass

    def box(self):
        # TODO alter passing packages
        pass

    def calculate_rx_power(self):
        pass

    def get_temp_signal_offset(self, temp):
        # TODO implement LUT
        loss = temp
        return loss

    def calculate_ber(self):
        #TODO implement ber
        pass