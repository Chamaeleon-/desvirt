import subprocess
import shlex

from .vnet import VirtualNet

class LossyNet(VirtualNet):
    def __init__(self, name, create=False):
        self.mark_counter = 0
        self.chain_name = name.upper()
        self.iflist = []
        
        VirtualNet.__init__(self,name,create)

    def create(self):
        VirtualNet.create(self)
        
        self.ebtables('-N %s -P DROP' % self.chain_name)
        self.ebtables('-A FORWARD --logical-in %s -j %s' %(self.name, self.chain_name))

    def delete(self):
        for iface in self.iflist:
            self.delif(iface)

        VirtualNet.delete(self)
        
        self.ebtables('-D FORWARD --logical-in %s -j %s' %(self.name, self.chain_name))
        self.ebtables('-X %s' % self.chain_name)

    def add_link(self, from_tap, to_tap, bandwidth='100mbit', packet_loss=0):
        print("%s: New link from %s to %s, rate=%s, loss=%s" % (self.name, from_tap, to_tap, bandwidth, packet_loss))

        mark = self.get_mark()
        self.ebtables('-A %s -i %s -o %s -j mark --mark-set %d' % (self.chain_name, from_tap, to_tap, mark))

        self.tc('class add dev %s parent 1:1 classid 1:%d htb rate %s ceil %s' %(to_tap, mark+10, bandwidth, bandwidth))
        self.tc('qdisc add dev %s parent 1:%d netem loss %d%%' % (to_tap, mark+10, packet_loss))
        self.tc('filter add dev %s parent 1: protocol all handle %d fw flowid 1:%d' % (to_tap, mark, mark+10))

    def get_mark(self):
        self.mark_counter += 1
        return self.mark_counter

    def ebtables(self, command):
        cmd = 'sudo ebtables %s' % command
        #print(cmd)
        status = subprocess.call(shlex.split(cmd.encode("utf-8")))

    def tc(self, command):
        cmd = 'sudo tc %s' % command
        #print(cmd)
        status = subprocess.call(shlex.split(cmd.encode("utf-8")))

    def addif(self, ifname, setup=True):
#        print("Net %s adding if %s." %(self.name, ifname))
        self.iflist.append(ifname)
        if setup:
            self.tc('qdisc add dev %s root handle 1: htb default 1' % ifname)
            self.tc('class add dev %s parent 1: classid 1:1 htb rate 100mbit ceil 100mbit' % ifname)
            self.tc('class add dev %s parent 1:1 classid 1:10 htb rate 100mbit ceil 100mbit' % ifname)
            self.tc('qdisc add dev %s parent 1:10 netem loss 100%%' % ifname)

            VirtualNet.addif(self,ifname)

    def delif(self, ifname):
        #print("lossnet removing interface %s" %ifname)
        self.tc("qdisc del dev %s root" % ifname)
        VirtualNet.delif(self,ifname)

