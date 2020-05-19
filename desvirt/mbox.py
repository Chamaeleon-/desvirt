import csv


def get_loss(temp):
    # TODO implement LUT
    loss = temp
    return loss


def parse_temperatures(temperature_file):
    with open(temperature_file) as csvfile:
        temperature_lines = csv.reader(csvfile)
        return list(temperature_lines)


class MiddleBox():
    in_tap = None
    out_tap = None
    temperature_file = None
