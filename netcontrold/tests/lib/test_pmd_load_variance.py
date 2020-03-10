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

import copy
from unittest import mock
from unittest import TestCase

from netcontrold.app import ncd
from netcontrold.lib import dataif
from netcontrold.lib import config

_BASIC_DATA = """
pmd thread numa_id 0 core_id 22:
    emc hits:17461158
    megaflow hits:0
    avg. subtable lookups per hit:0.00
    miss:0
    lost:0
    polling cycles:4948219259 (25.81%)
    processing cycles:14220835107 (74.19%)
    avg cycles per packet: 1097.81 (19169054366/17461158)
    avg processing cycles per packet: 814.43 (14220835107/17461158)
--
pmd thread numa_id 0 core_id 2:
    emc hits:14874381
    megaflow hits:0
    avg. subtable lookups per hit:0.00
    miss:0
    lost:0
    polling cycles:5460724802 (29.10%)
    processing cycles:13305794333 (70.90%)
    avg cycles per packet: 1261.67 (18766519135/14874381)
    avg processing cycles per packet: 894.54 (13305794333/14874381)
"""



class TestUtil_pmd_load_variance(TestCase):

    pmd_map = dict()
    core_id = 0
    
    # setup test environment
    def setUp(self):
        # turn off limited info shown in assert failure for pmd object.
        self.maxDiff = None

        # a noop handler for debug info log.
        class NlogNoop(object):

            def debug(self, *args):
                None

        dataif.Context.nlog = NlogNoop()

        # create one pmd object.
        self.pmd = dataif.Dataif_Pmd(self.core_id)

        # let it be in numa 0.
        self.pmd.numa_id = 0

        # add some cpu consumption for this pmd.
        for i in range(0, config.ncd_samples_max):
            self.pmd.idle_cpu_cyc[i] = (1000 + (100 * i))
            self.pmd.proc_cpu_cyc[i] = (5000 + (500 * i))
            self.pmd.rx_cyc[i] = (10000 + (100 * i))

        #print(self.pmd)
        self.pmd_map[self.core_id] = self.pmd
        return

    @mock.patch('netcontrold.lib.dataif.open')
    def test_pmd_load_positive(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=_BASIC_DATA).return_value
        ]
        pmd_load=dataif.pmd_load(self.pmd)
        dataif.update_pmd_load(self.pmd_map)
        out = dataif.pmd_load_variance(self.pmd_map)
        expected = 0 
        self.assertEqual(out, expected)