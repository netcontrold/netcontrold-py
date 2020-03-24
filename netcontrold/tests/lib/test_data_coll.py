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
from netcontrold.lib import config
from netcontrold.lib import util
import pdb
import copy


def mock_pmd_stats(*args):
    return """pmd thread numa_id 0 core_id 1:
  packets received: 12768937477
  packet recirculations: 0
  avg. datapath passes per packet: 1.00
  emc hits: 12768883657
  smc hits: 0
  megaflow hits: 49909
  avg. subtable lookups per megaflow hit: 1.28
  miss with success upcall: 3911
  miss with failed upcall: 0
  avg. packets per output batch: 9.37
  idle cycles: 160922398216850 (93.95%)
  processing cycles: 10370482753684 (6.05%)
  avg cycles per packet: 13414.81 (171292880970534/12768937477)
  avg processing cycles per packet: 812.16 (10370482753684/12768937477)
pmd thread numa_id 0 core_id 13:
  packets received: 31402827829
  packet recirculations: 0
  avg. datapath passes per packet: 1.00
  emc hits: 31402809758
  smc hits: 0
  megaflow hits: 14434
  avg. subtable lookups per megaflow hit: 1.48
  miss with success upcall: 3637
  miss with failed upcall: 0
  avg. packets per output batch: 27.05
  idle cycles: 150444796438208 (87.83%)
  processing cycles: 20847810403960 (12.17%)
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
  avg. packets per output batch: 1.00"""


def mock_pmd_rxqs(*args):
    return """pmd thread numa_id 0 core_id 1:
  isolated : false
  port: virtport1   queue-id:  0  pmd usage:  0 %
pmd thread numa_id 0 core_id 13:
  isolated : false
  port: virtport2   queue-id:  0  pmd usage:  0 %"""


class TestDataif_Collection(TestCase):
    """
    Test for getting pmd stats.
    """

    # create an empty pmd_map
    pmd_map = dict()

    def setUp(self):
        # turn off limited info shown in assert failure for pmd object.
        self.maxDiff = None

        # a noop handler for debug info log.
        class NlogNoop(object):

            def debug(self, *args):
                None

        dataif.Context.nlog = NlogNoop()

        # create one pmd object.
        self.fx_pmd_1 = dataif.Dataif_Pmd(1)

        # let it be in numa 0.
        self.fx_pmd_1.numa_id = 0

        # add it to pmd_map
        self.pmd_map[1] = self.fx_pmd_1

        # one dummy port is required for this test.
        port_name1 = 'virtport1'

        # create port class of name 'virtport1'.
        dataif.make_dataif_port(port_name1)

        # add port object into pmd.
        fx_port = self.fx_pmd_1.add_port(port_name1)
        fx_port.numa_id = self.fx_pmd_1.numa_id

        # create another pmd object.
        self.fx_pmd_2 = dataif.Dataif_Pmd(13)

        # let it be in numa 0.
        self.fx_pmd_2.numa_id = 0

        # one dummy port is required for this test.
        port_name2 = 'virtport2'

        # add it to pmd_map
        self.pmd_map[13] = self.fx_pmd_2

        # create port class of name 'virtport2'.
        dataif.make_dataif_port(port_name2)

        # add port object into pmd.
        fx_port = self.fx_pmd_2.add_port(port_name2)
        fx_port.numa_id = self.fx_pmd_2.numa_id

        return

    # Test case:
    #   getting pmd stats from get_pmd_stats function and checking if
    #   declared pmd_map is modified or not
    @mock.patch('netcontrold.lib.util.exec_host_command', mock_pmd_stats)
    def test_get_pmd_stats_1(self):
        # create a copy of original pmd_map
        expected = copy.deepcopy(self.pmd_map)

        # copy both original pmd objects
        expected_pmd_1 = expected[1]
        expected_pmd_2 = expected[13]

        # calling get_pmd_stats function. pmd_map is modified here
        out = dataif.get_pmd_stats(self.pmd_map)

        # copy both modified pmd objects
        out_pmd_1 = out[1]
        out_pmd_2 = out[13]

        # check if original and modified pmd_map objects are different.
        # if __eq__ returns false , then pmd objects are modified
        self.assertEqual(out_pmd_1.__eq__(expected_pmd_1), False)
        self.assertEqual(out_pmd_2.__eq__(expected_pmd_2), False)
