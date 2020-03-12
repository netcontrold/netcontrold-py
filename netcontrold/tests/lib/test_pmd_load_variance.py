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
from unittest import TestCase
from unittest import mock
from netcontrold.lib import dataif
from netcontrold.lib import config

_FX_CPU_INFO = """
processor       : 0
core id         : 0
physical id     : 0

processor       : 1
core id         : 1
physical id     : 0

processor       : 2
core id         : 0
physical id     : 0

processor       : 3
core id         : 1
physical id     : 0
"""


class Test_pmd_load_variance_OnePmd(TestCase):


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
        fx_pmd = dataif.Dataif_Pmd(self.core_id)

        # let it be in numa 0.
        fx_pmd.numa_id = 0

        # add some cpu consumption for this pmd.
        for i in range(0, config.ncd_samples_max):
            fx_pmd.idle_cpu_cyc[i] = (1000 + (100 * i))
            fx_pmd.proc_cpu_cyc[i] = (5000 + (500 * i))
            fx_pmd.rx_cyc[i] = (10000 + (100 * i))

        self.pmd_map[self.core_id] = fx_pmd
        return

   
    def test_one_rxq(self):
        # retrieve pmd object.
        pmd = self.pmd_map[self.core_id]

        # one dummy port is required for this test.
        port_name = 'virtport'

        # create port class of name 'virtport'.
        dataif.make_dataif_port(port_name)

        # add port object into pmd.
        fx_port = pmd.add_port(port_name)
        fx_port.numa_id = pmd.numa_id

        # add a dummy rxq into port.
        fx_rxq = fx_port.add_rxq(0)

        # add some cpu consumption for this rxq.
        for i in range(0, config.ncd_samples_max):
            fx_rxq.cpu_cyc[i] = (1000 + (100 * i))
        
        dataif.update_pmd_load(self.pmd_map)
        n_reb_rxq = dataif.pmd_load_variance(self.pmd_map)

        self.assertEqual(n_reb_rxq, 0)

        # del port object from pmd.
        pmd.del_port(port_name)
