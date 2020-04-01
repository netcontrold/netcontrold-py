#
#  Copyright (c) 2020 Red Hat, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at:
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
from unittest import mock
from unittest import TestCase

from netcontrold.lib import dataif
import copy


# A noop handler for netcontrold logging.
class NlogNoop(object):

    def info(self, *args):
        prefix = "%s> " % (self.__class__.__name__)
        print("%s %s" % (prefix, "".join(args)))

    def debug(self, *args):
        prefix = "%s> " % (self.__class__.__name__)
        print("%s %s" % (prefix, "".join(args)))


def mock_pmd_stats(*args):
    stats = """pmd thread numa_id 0 core_id 1:
  packets received: 1000
  packet recirculations: 0
  avg. datapath passes per packet: 1.00
  emc hits: 12768883657
  smc hits: 0
  megaflow hits: 49909
  avg. subtable lookups per megaflow hit: 1.28
  miss with success upcall: 3911
  miss with failed upcall: 0
  avg. packets per output batch: 9.37
  idle cycles: 1100 (93.95%)
  processing cycles: 1200 (6.05%)
  avg cycles per packet: 13414.81 (171292880970534/12768937477)
  avg processing cycles per packet: 812.16 (10370482753684/12768937477)
pmd thread numa_id 0 core_id 13:
  packets received: 3000
  packet recirculations: 0
  avg. datapath passes per packet: 1.00
  emc hits: 31402809758
  smc hits: 0
  megaflow hits: 14434
  avg. subtable lookups per megaflow hit: 1.48
  miss with success upcall: 3637
  miss with failed upcall: 0
  avg. packets per output batch: 27.05
  idle cycles: 3100 (87.83%)
  processing cycles: 3200 (12.17%)
  avg cycles per packet: 5454.69 (171292606842168/31402827829)
  avg processing cycles per packet: 663.88 (20847810403960/31402827829)
main thread:
  packets received: 108
  packet recirculations: 0
  avg. datapath passes per packet: 1.00
  emc hits: 0
  smc hits: 0
  megaflow hits: 34
  avg. subtable lookups per megaflow hit: 1.00
  miss with success upcall: 74
  miss with failed upcall: 0
  avg. packets per output batch: 1.00"""  # noqa: E501
    return stats


def mock_pmd_rxqs(*args):
    stats = """pmd thread numa_id 0 core_id 1:
  isolated : false
  port: port1   queue-id:  0  pmd usage:  0 %
pmd thread numa_id 0 core_id 13:
  isolated : false
  port: port2   queue-id:  0  pmd usage:  0 %"""  # noqa: E501
    return stats


def mock_port_stats(*args):
    stats = """netdev@ovs-netdev:
  lookups: hit:0 missed:0 lost:0
  flows: 0
  port 1: port1 (tap)
    RX packets:5 errors:0 dropped:2 overruns:0 frame:0
    TX packets:5 errors:0 dropped:3 aborted:0 carrier:0
    collisions:0
    RX bytes:0  TX bytes:0
  port 2: port2 (tap)
    RX packets:5 errors:0 dropped:2 overruns:0 frame:0
    TX packets:5 errors:0 dropped:3 aborted:0 carrier:0
    collisions:0
    RX bytes:0  TX bytes:0"""  # noqa: E501
    return stats


def mock_interface_stats(*args):
    stats = """_uuid               : 583d9020-a49a-4c5d-902d-dfcaa41e2911
admin_state         : up
bfd                 : {}
bfd_status          : {}
cfm_fault           : []
cfm_fault_status    : []
cfm_flap_count      : []
cfm_health          : []
cfm_mpid            : []
cfm_remote_mpids    : []
cfm_remote_opstate  : []
duplex              : []
error               : []
external_ids        : {}
ifindex             : 6656773
ingress_policing_burst: 0
ingress_policing_rate: 0
lacp_current        : []
link_resets         : 0
link_speed          : []
link_state          : down
lldp                : {}
mac                 : []
mac_in_use          : "00:00:00:00:00:00"
mtu                 : 1500
mtu_request         : []
name                : "port1"
ofport              : 201
ofport_request      : 201
options             : {n_rxq="1", n_txq="1", vhost-server-path="/var/lib/vhost_sockets/dpdkvhost2"}
other_config        : {}
statistics          : {"rx_1024_to_1522_packets"=0, "rx_128_to_255_packets"=0, "rx_1523_to_max_packets"=0, "rx_1_to_64_packets"=0, "rx_256_to_511_packets"=0, "rx_512_to_1023_packets"=0, "rx_65_to_127_packets"=0, rx_bytes=0, rx_dropped=0, rx_errors=0, rx_packets=0, tx_bytes=0, tx_dropped=0, tx_packets=0, tx_retries=0}
status              : {mode=client, status=disconnected}
type                : dpdkvhostuserclient

_uuid               : 3f97b403-2fe3-490f-8b24-8f9b80eb7aed
admin_state         : up
bfd                 : {}
bfd_status          : {}
cfm_fault           : []
cfm_fault_status    : []
cfm_flap_count      : []
cfm_health          : []
cfm_mpid            : []
cfm_remote_mpids    : []
cfm_remote_opstate  : []
duplex              : full
error               : []
external_ids        : {}
ifindex             : 6054325
ingress_policing_burst: 0
ingress_policing_rate: 0
lacp_current        : []
link_resets         : 0
link_speed          : 10000000000
link_state          : up
lldp                : {}
mac                 : []
mac_in_use          : "24:6e:96:c4:2f:ea"
mtu                 : 1500
mtu_request         : []
name                : "port2"
ofport              : 11
ofport_request      : 11
options             : {dpdk-devargs="0000:19:00.1", n_rxq="1", n_rxq_desc="4096", n_txq="1", n_txq_desc="4096"}
other_config        : {}
statistics          : {flow_director_filter_add_errors=0, flow_director_filter_remove_errors=0, mac_local_errors=1, mac_remote_errors=0, "rx_128_to_255_packets"=0, "rx_1_to_64_packets"=0, "rx_256_to_511_packets"=0, "rx_512_to_1023_packets"=0, "rx_65_to_127_packets"=0, rx_broadcast_packets=0, rx_bytes=0, rx_crc_errors=0, rx_dropped=0, rx_errors=0, rx_fcoe_crc_errors=0, rx_fcoe_dropped=0, rx_fcoe_mbuf_allocation_errors=0, rx_fragment_errors=0, rx_illegal_byte_errors=0, rx_jabber_errors=0, rx_length_errors=0, rx_mac_short_packet_dropped=0, rx_management_dropped=0, rx_management_packets=0, rx_mbuf_allocation_errors=0, rx_missed_errors=0, rx_oversize_errors=0, rx_packets=0, "rx_priority0_dropped"=0, "rx_priority0_mbuf_allocation_errors"=0, "rx_priority1_dropped"=0, "rx_priority1_mbuf_allocation_errors"=0, "rx_priority2_dropped"=0, "rx_priority2_mbuf_allocation_errors"=0, "rx_priority3_dropped"=0, "rx_priority3_mbuf_allocation_errors"=0, "rx_priority4_dropped"=0, "rx_priority4_mbuf_allocation_errors"=0, "rx_priority5_dropped"=0, "rx_priority5_mbuf_allocation_errors"=0, "rx_priority6_dropped"=0, "rx_priority6_mbuf_allocation_errors"=0, "rx_priority7_dropped"=0, "rx_priority7_mbuf_allocation_errors"=0, rx_undersize_errors=0, "tx_128_to_255_packets"=0, "tx_1_to_64_packets"=0, "tx_256_to_511_packets"=0, "tx_512_to_1023_packets"=0, "tx_65_to_127_packets"=0, tx_broadcast_packets=0, tx_bytes=0, tx_dropped=0, tx_errors=0, tx_management_packets=0, tx_multicast_packets=0, tx_packets=0}
status              : {driver_name=net_ixgbe, if_descr="DPDK 18.11.2 net_ixgbe", if_type="6", link_speed="10Gbps", max_hash_mac_addrs="4096", max_mac_addrs="127", max_rx_pktlen="1518", max_rx_queues="128", max_tx_queues="64", max_vfs="0", max_vmdq_pools="64", min_rx_bufsize="1024", numa_id="0", pci-device_id="0x10fb", pci-vendor_id="0x8086", port_no="1"}
type                : dpdk"""  # noqa: E501
    return stats


class TestDataif_Collection(TestCase):
    """
    Test for getting pmd stats.
    """

    # create an empty pmd_map
    pmd_map = dict()

    def setUp(self):
        # turn off limited info shown in assert failure for pmd object.
        self.maxDiff = None

        dataif.Context.nlog = NlogNoop()

        # create one pmd object.
        fx_pmd_1 = dataif.Dataif_Pmd(1)

        # let it be in numa 0.
        fx_pmd_1.numa_id = 0

        # add it to pmd_map
        self.pmd_map[1] = fx_pmd_1

        # create port class of name 'port1'.
        dataif.make_dataif_port("port1")

        # add port object into pmd.
        port1 = fx_pmd_1.add_port("port1")
        port1.numa_id = fx_pmd_1.numa_id

        # add rxq to port object
        rxq_1 = port1.add_rxq(0)  # noqa: F841

        # create another pmd object.
        fx_pmd_2 = dataif.Dataif_Pmd(13)

        # let it be in numa 0.
        fx_pmd_2.numa_id = 0

        # add it to pmd_map
        self.pmd_map[13] = fx_pmd_2

        # create port class of name 'port2'.
        dataif.make_dataif_port("port2")

        # add port object into pmd.
        port2 = fx_pmd_2.add_port("port2")
        port2.numa_id = fx_pmd_2.numa_id

        # add rxq to port object
        rxq_2 = port2.add_rxq(0)  # noqa: F841

        return

    # Test case:
    #   getting pmd stats from get_pmd_stats function and checking if
    #   declared pmd_map is modified or not
    @mock.patch('netcontrold.lib.util.exec_host_command', mock_pmd_stats)
    def test_get_pmd_stats_1(self):
        # create a copy of original pmd_map
        expected = copy.deepcopy(self.pmd_map)

        # modify pmd_1 object to expected
        expected_pmd_1 = expected[1]
        expected_pmd_1.rx_cyc[expected_pmd_1.cyc_idx] = 1000
        expected_pmd_1.idle_cpu_cyc[expected_pmd_1.cyc_idx] = 1100
        expected_pmd_1.proc_cpu_cyc[expected_pmd_1.cyc_idx] = 1200

        # modify pmd_2 object to expected
        expected_pmd_2 = expected[13]
        expected_pmd_2.rx_cyc[expected_pmd_2.cyc_idx] = 3000
        expected_pmd_2.idle_cpu_cyc[expected_pmd_2.cyc_idx] = 3100
        expected_pmd_2.proc_cpu_cyc[expected_pmd_2.cyc_idx] = 3200

        # calling get_pmd_stats function. pmd_map is modified here
        out = dataif.get_pmd_stats(self.pmd_map)

        # modified pmd objects
        out_pmd_1 = out[1]
        out_pmd_2 = out[13]

        # check if original and modified pmd_map objects are different.
        # if __eq__ returns false , then pmd objects are modified
        self.assertEqual(
            out_pmd_1,
            expected_pmd_1,
            "pmd 1 stats to be matched")

        self.assertEqual(
            out_pmd_2,
            expected_pmd_2,
            "pmd 2 stats to be matched")

    # Test case:
    #   getting interface stats from get_interface_stats function and checking
    #   if declared port objects are modified or not
    @mock.patch('netcontrold.lib.util.exec_host_command', mock_interface_stats)
    def test_get_interface_stats_1(self):
        # create a copy of original port1
        pmd1 = self.pmd_map[1]
        port1 = pmd1.find_port_by_name('port1')
        expected_port1 = copy.deepcopy(port1)

        # modify these to expected
        expected_port1.type = "dpdkvhostuserclient"
        expected_port1.tx_retry_cyc[expected_port1.cyc_idx] = 0

        # calling get_interface_stats function.port1 object is modified here
        dataif.get_interface_stats()

        # check if expected and modified port1 objects are same
        self.assertEqual(port1, expected_port1, "port 1 to be matched")

        # create a copy of original port2
        pmd2 = self.pmd_map[13]
        port2 = pmd2.find_port_by_name('port2')
        expected_port2 = copy.deepcopy(port2)

        # modify these to expected
        expected_port2.type = "dpdk"
        expected_port2.tx_retry_cyc[expected_port2.cyc_idx] = 0

        # calling get_interface_stats function.port2 object is modified here
        dataif.get_interface_stats()

        # check if expected and modified port2 objects are same
        self.assertEqual(port2, expected_port2, "port 2 to be matched")
