import csv
import math
import threading
from desvirt import vif


def parse_temperatures(temperature_file):
    with open(temperature_file) as csvfile:
        temperature_lines = csv.reader(csvfile)
        return list(temperature_lines)


class MiddleBox:
    in_if = None
    out_if = None
    distance = None  # in meters
    noise_floor = None
    sensitivity_offset = None
    tx_power = None
    frequency = 2440  # in megahertz
    fspl = 20 * math.log10(distance) + 20 * math.log10(frequency) - 27.55
    temperature_file = None
    temp_offset_lut = None

    def __init__(self, distance, noise_floor, sensitivity_offset, tx_power, frequency=2440, temperature_file=None):
        self.thread = threading.Thread(target=self.box())
        self.in_if = vif.VirtualInterface.create()
        self.out_if = vif.VirtualInterface.create()
        self.distance = distance
        self.noise_floor = noise_floor
        self.sensitivity_offset = sensitivity_offset
        self.tx_power = tx_power
        self.frequency = frequency
        self.temperature_file = temperature_file

    def start(self):
        temperatures = parse_temperatures(self.temperature_file)
        # TODO start box process thread
        self.thread.start()

    def delete(self):
        self.thread.join()
        self.out_if.delete()
        self.in_if.delete()

    def __del__(self):
        self.delete()

    def box(self):
        # TODO alter passing packages
        pass

    def calculate_rx_power(self):
        # TODO add temp offset
        if (self.tx_power - self.fspl) > (self.noise_floor + self.sensitivity_offset):
            return self.tx_power - self.fspl
        else:
            return False

    def get_temp_signal_offset(self, temp):
        # TODO implement LUT
        loss = temp
        return loss

    def calculate_ber(self):
        snr = self.calculate_rx_power()/self.noise_floor
        return min(8 * math.exp(-0.6 * (snr + 0.5)), 1.0)
