import subprocess
import shlex
import logging
import threading

from .vif import VirtualInterface
from .vnet import VirtualNet
from .mbox import MiddleBox

"""                                                             
defines a virtual net with lossy links                          
provides methods to configure the links using tc and ebtables   
"""


class LossyNet(VirtualNet):
    def __init__(self, name, create=False):
        self.mark_counter = 0
        self.chain_name = name.upper()
        self.iflist = []

        VirtualNet.__init__(self,name,create)

    # sets new bit error and schedules the next timer
    # def set_and_schedule_loss(self, to_tap, mark, packet_loss, delay):
    #     for e in to_tap.temp_iter:
    #         timer = e[0]
    #         if timer == "LOOP":
    #             continue
    #         else:
    #             timer = int(e[0])
    #         bit_error_rate = int(get_loss(e[1]))
    #         # set bit error with netem TODO keep track on subprocesses
    #         self.tc('qdisc replace dev %s parent 1:%d netem loss %d%% delay %dms corrupt %d%%' % (to_tap.tap, mark+10, packet_loss, delay, bit_error_rate), timeout=timer)
    #         # sleep(timer)         # set subprocess.run timeout instead

    def create(self):
        VirtualNet.create(self)
        
        # self.ebtables('-N %s -P DROP' % self.chain_name)
        # self.ebtables('-A OUTPUT --logical-in %s -j %s' %(self.name, self.chain_name))
        self.ebtables(f'-t filter -A INPUT --logical-in {self.name} -j DROP')
        self.ebtables(f'-t filter -A OUTPUT --logical-out {self.name} -j DROP')
        self.ebtables(f'-t filter -A FORWARD --logical-out {self.name} -j DROP')


    def delete(self):
        for iface in self.iflist:
            self.delif(iface)

        VirtualNet.delete(self)
        
        # self.ebtables('-D OUTPUT --logical-in %s -j %s' %(self.name, self.chain_name))
        # self.ebtables('-X %s' % self.chain_name)
        # TODO clean up other rules
        # self.ebtables(f'-t nat -F POSTROUTING')
        # self.ebtables(f'-t nat -F PREROUTING')

    def add_link(self, from_tap: VirtualInterface, to_tap: VirtualInterface, bandwidth='250kbit', packet_loss=0,
                 delay=0, distance=10, noise_floor=-30, sensitivity_offset=5, tx_power=3, temperature_file="temp"):
        box = MiddleBox(from_tap, to_tap, self, int(distance), noise_floor, sensitivity_offset, tx_power,
                        temperature_file=temperature_file, packetloss=packet_loss, delay=delay)
        # create links between from and to and box taps
        # middlebox_in_tap = box.in_if.tap
        # middlebox_out_tap = box.out_if.tap
        box.start()
        logging.getLogger("").info("%s: New link from %s to %s, rate=%s, loss=%s, delay=%s" % (self.name, from_tap.tap, to_tap.tap, bandwidth, packet_loss, delay))

        # to_tap.mark = self.get_mark()
        # # self.ebtables('-A %s -i %s -o %s -j mark --mark-set %d' % (self.chain_name, from_tap.tap, middlebox_in_tap, mark_in))
        # # self.ebtables(f'-t nat -A PREROUTING -i {from_tap.tap} -j DROP')
        # self.ebtables(f'-t nat -A PREROUTING --logical-in {self.name} -i {box.in_if.tap} -j DROP')  # rule3
        # self.ebtables(f'-t nat -A PREROUTING --logical-in {self.name} -i {from_tap.tap} -d {to_tap.macaddr} -j dnat --to-destination {box.in_if.macaddr}')  # rule1
        # self.ebtables(f'-t nat -A PREROUTING --logical-in {self.name} -i {box.out_if.tap} -d ! 01:00:00:00:00:00/01:00:00:00:00:00 -j dnat --to-destination {to_tap.macaddr} --dnat-target CONTINUE')  # rule2
        # self.ebtables(f'-t nat -A PREROUTING --logical-in {self.name} -i {box.out_if.tap} -j mark --mark-set {to_tap.mark}')  # rule6
        # self.ebtables(f'-t nat -A POSTROUTING --logical-out {self.name} -o {box.out_if.tap} -j DROP')  # rule4
        # self.ebtables(f'-t nat -A POSTROUTING --logical-out {self.name} -s ! {from_tap.macaddr} -o {box.in_if.tap} -j DROP')  # rule5
        # self.ebtables(f'-t nat -A POSTROUTING --logical-out {self.name} -o {to_tap.tap} --mark ! {to_tap.mark} -j DROP')  # rule7

        # self.ebtables(f'-t nat -A PREROUTING -d {to_tap.macaddr} -j DROP')
        # self.ebtables(f'-t nat -A POSTROUTING -s {box.out_if.macaddr} -j snat --to-source {to_tap.macaddr}')


        # self.tc('class add dev %s parent 1:1 classid 1:%d htb rate %s ceil %s' %(middlebox_in_tap, mark_in+10, bandwidth, bandwidth))
        # self.tc('qdisc add dev %s parent 1:%d netem loss %d%% delay %dms' % (middlebox_in_tap, mark_in+10, packet_loss, delay))
        # self.tc('filter add dev %s parent 1: protocol all handle %d fw flowid 1:%d' % (middlebox_in_tap, mark_in, mark_in+10))

        # mark_out = self.get_mark()
        # self.ebtables('-A %s -i %s -o %s -j mark --mark-set %d' % (self.chain_name, middlebox_out_tap, to_tap.tap, mark_out))

        # self.tc('class add dev %s parent 1:1 classid 1:%d htb rate %s ceil %s' %(to_tap.tap, mark_in+10, bandwidth, bandwidth))
        # self.tc('qdisc add dev %s parent 1:%d netem loss %d%% delay %dms' % (to_tap.tap, mark_in+10, packet_loss, delay))
        # self.tc('filter add dev %s parent 1: protocol all handle %d fw flowid 1:%d' % (to_tap.tap, mark_in, mark_in+10))

    def get_mark(self):
        self.mark_counter += 1
        return self.mark_counter

    @staticmethod
    def ebtables(command):
        cmd = 'sudo ebtables %s' % command
        logging.getLogger("").debug(cmd)
        status = subprocess.call(shlex.split(cmd))

    @staticmethod
    def tc(command, timeout=None):
        cmd = 'sudo tc %s' % command
        logging.getLogger("").debug(cmd)
        if timeout is not None:
            try:
                # docs says: If the timeout expires, the child process will be killed and waited for.
                status = subprocess.call(shlex.split(cmd), timeout=timeout)
            except subprocess.TimeoutExpired:
                logging.getLogger("").debug("tc: subprocess.TimeoutExpired")
        else:
            status = subprocess.call(shlex.split(cmd))

    def addif(self, ifname, setup=True):
        logging.getLogger("").debug("Net %s adding if %s." %(self.name, ifname))
        self.iflist.append(ifname)
        if setup:
            # self.tc('qdisc add dev %s root handle 1: htb default 1' % ifname)
            # self.tc('class add dev %s parent 1: classid 1:1 htb rate 100mbit ceil 100mbit' % ifname)
            # self.tc('class add dev %s parent 1:1 classid 1:10 htb rate 100mbit ceil 100mbit' % ifname)
            # self.tc('qdisc add dev %s parent 1:10 netem loss 100%%' % ifname)

            VirtualNet.addif(self,ifname)

    def delif(self, ifname):
        logging.getLogger("").debug("lossnet removing interface %s" %ifname)
        self.tc("qdisc del dev %s root" % ifname)
        VirtualNet.delif(self,ifname)

