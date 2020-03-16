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
        variance_value = dataif.pmd_load_variance(self.pmd_map)

        self.assertEqual(variance_value, 0)

        # del port object from pmd.
        pmd.del_port(port_name)

    # Test case:
    #   With one pmd thread handling few one single-queue ports
    def test_many_ports(self):
        # retrieve pmd object.
        pmd = self.pmd_map[self.core_id]

        # one few dummy ports required for this test.
        for port_name in ('virtport1', 'virtport2', 'virtport3'):

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
        variance_value = dataif.pmd_load_variance(self.pmd_map)

        self.assertEqual(variance_value, 0)

        for port_name in ('virtport1', 'virtport2', 'virtport3'):
            pmd.del_port(port_name)

# Fixture:
#   create two pmd thread objects where in, each has one single-queued port.


def fx_2pmd_for_1rxq_each(testobj):
    # retrieve pmd object.
    pmd1 = testobj.pmd_map[testobj.core1_id]
    pmd2 = testobj.pmd_map[testobj.core2_id]

    # one dummy port is required for this test.
    port1_name = 'virtport1'
    port2_name = 'virtport2'

    # create port class of name 'virtport'.
    dataif.make_dataif_port(port1_name)
    dataif.make_dataif_port(port2_name)

    # add port object into pmd.
    fx_port1 = pmd1.add_port(port1_name)
    fx_port1.numa_id = pmd1.numa_id
    fx_port2 = pmd2.add_port(port2_name)
    fx_port2.numa_id = pmd2.numa_id

    # add a dummy rxq into port.
    fx_p1rxq = fx_port1.add_rxq(0)
    fx_p1rxq.pmd = pmd1
    fx_p2rxq = fx_port2.add_rxq(0)
    fx_p2rxq.pmd = pmd2

    # add some cpu consumption for these rxqs.
    for i in range(0, config.ncd_samples_max):
        fx_p1rxq.cpu_cyc[i] = (1000 + (100 * i))
        fx_p2rxq.cpu_cyc[i] = (2000 + (200 * i))


# Fixture:
#   Create two pmd thread objects where in, one pmd has two single-queued
#   ports, while the other is idle (without any port/rxq).
def fx_1pmd_for_2rxq(testobj):
    # retrieve pmd object.
    pmd1 = testobj.pmd_map[testobj.core1_id]

    # one dummy port is required for this test.
    port1_name = 'virtport1'
    port2_name = 'virtport2'

    # create port class of name 'virtport'.
    dataif.make_dataif_port(port1_name)
    dataif.make_dataif_port(port2_name)

    # add port object into pmd.
    fx_port1 = pmd1.add_port(port1_name)
    fx_port1.numa_id = pmd1.numa_id

    # add second port as well into pmd 1
    fx_port2 = pmd1.add_port(port2_name)
    fx_port2.numa_id = pmd1.numa_id

    # add a dummy rxq into port.
    fx_p1rxq = fx_port1.add_rxq(0)
    fx_p1rxq.pmd = pmd1
    fx_p2rxq = fx_port2.add_rxq(0)
    fx_p2rxq.pmd = pmd1

    # add some cpu consumption for these rxqs.
    for i in range(0, config.ncd_samples_max):
        fx_p1rxq.cpu_cyc[i] = (1000 + (100 * i))
        fx_p2rxq.cpu_cyc[i] = (2000 + (200 * i))


class Test_pmd_load_variance_TwoPmd(TestCase):
    """
    Test variance_value for one or more rxq handled by twp pmds.
    """

    pmd_map = dict()
    core1_id = 0
    core2_id = 1

    # setup test environment
    def setUp(self):
        # turn off limited info shown in assert failure for pmd object.
        self.maxDiff = None

        # a noop handler for debug info log.
        class NlogNoop(object):

            def info(self, *args):
                None

            def debug(self, *args):
                None

        dataif.Context.nlog = NlogNoop()

        # create one pmd object.
        fx_pmd1 = dataif.Dataif_Pmd(self.core1_id)
        fx_pmd2 = dataif.Dataif_Pmd(self.core2_id)

        # let it be in numa 0.
        fx_pmd1.numa_id = 0
        fx_pmd2.numa_id = 0

        # add some cpu consumption for these pmds.
        for i in range(0, config.ncd_samples_max):
            fx_pmd1.idle_cpu_cyc[i] = (1 + (1 * i))
            fx_pmd1.proc_cpu_cyc[i] = (900 + (90 * i))
            fx_pmd1.rx_cyc[i] = (1000 + (100 * i))

        for i in range(0, config.ncd_samples_max):
            fx_pmd2.idle_cpu_cyc[i] = (1000 + (100 * i))
            fx_pmd2.proc_cpu_cyc[i] = (9500 + (950 * i))
            fx_pmd2.rx_cyc[i] = (10000 + (1000 * i))

        self.pmd_map[self.core1_id] = fx_pmd1
        self.pmd_map[self.core2_id] = fx_pmd2
        return

    # Test case:
    #   With two threads from same numa, each handling only one single-queued
    #   port, variance_value
    def test_one_rxq_lnuma(self):
        # set different numa for pmds
        pmd1 = self.pmd_map[self.core1_id]
        pmd2 = self.pmd_map[self.core2_id]

        pmd1.numa_id = 0
        pmd2.numa_id = 0

        fx_2pmd_for_1rxq_each(self)

        dataif.update_pmd_load(self.pmd_map)
        variance_value = dataif.pmd_load_variance(self.pmd_map)

        self.assertEqual(int(variance_value), 17)

        # del port object from pmd.
        # TODO: create fx_ post deletion routine for clean up
        pmd1.del_port('virtport1')
        pmd2.del_port('virtport2')

    # Test case:
    #   With two threads from same numa, where one pmd thread is handling
    #   two single-queued ports, while the other is doing nothing,
    #   check variance_value.
    @mock.patch('netcontrold.lib.util.open')
    def test_two_rxq_lnuma(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=_FX_CPU_INFO).return_value
        ]

        # set different numa for pmds
        pmd1 = self.pmd_map[self.core1_id]
        pmd2 = self.pmd_map[self.core2_id]

        pmd1.numa_id = 0
        pmd2.numa_id = 0

        fx_1pmd_for_2rxq(self)

        dataif.update_pmd_load(self.pmd_map)
        variance_value = dataif.pmd_load_variance(self.pmd_map)

        self.assertEqual(int(variance_value), 17)

        # del port object from pmd.
        # TODO: create fx_ post deletion routine for clean up
        pmd1.del_port('virtport1')
        pmd1.del_port('virtport2')

    # Test case:
    #   With two threads from different numa, each handling one single-queued
    #   port, check variance_value.
    def test_one_rxq_rnuma(self):
        # set different numa for pmds
        pmd1 = self.pmd_map[self.core1_id]
        pmd2 = self.pmd_map[self.core2_id]

        pmd1.numa_id = 0
        pmd2.numa_id = 1

        fx_2pmd_for_1rxq_each(self)

        dataif.update_pmd_load(self.pmd_map)
        variance_value = dataif.pmd_load_variance(self.pmd_map)

        self.assertEqual(int(variance_value), 17)
        pmd1.del_port('virtport1')
        pmd2.del_port('virtport2')
