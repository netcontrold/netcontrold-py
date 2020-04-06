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
import pytest
from unittest import TestCase
from unittest import mock
from netcontrold.lib import dataif
from netcontrold.lib import config
from netcontrold.lib import util

# A noop handler for netcontrold logging.


class NlogNoop(object):

    def info(self, *args):
        prefix = "%s> " % (self.__class__.__name__)
        print("%s %s" % (prefix, "".join(args)))

    def debug(self, *args):
        prefix = "%s> " % (self.__class__.__name__)
        print("%s %s" % (prefix, "".join(args)))


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

_FX_4X2CPU_INFO = """
processor       : 0
core id         : 0
physical id     : 0

processor       : 1
core id         : 1
physical id     : 0

processor       : 2
core id         : 0
physical id     : 1

processor       : 3
core id         : 1
physical id     : 1

processor       : 4
core id         : 0
physical id     : 0

processor       : 5
core id         : 1
physical id     : 0

processor       : 6
core id         : 0
physical id     : 1

processor       : 7
core id         : 1
physical id     : 1
"""

# -----------------------------------------------------------------------------
# Guidelines for setting pmd and rxq countes:
# -----------------------------------------------------------------------------
#
# rxq.cpu_cyc:
#   Number of cpu cycles consumed by a rxq during sample period.
#
# rxq.rx_cyc:
#   Number of packets received by a rxq during sample period.
#
# pmd.proc_cpu_cyc:
#   Number of cpu cycles consumed by a pmd since its stats start/reset.
#
# pmd.idle_cpu_cyc:
#   Number of cpu cycles not consumed by a pmd since its stats start/reset.
#
# pmd.rx_cyc:
#   Number of packets received by a pmd since its stats start/reset.
#
# Testobj.setup()
#   In setting up test environment, one or more pmd could be created for the
#   tests in that suite to use. By default, setup() function should create
#   a pmd for its load capacity at 96 % (i.e 1 % more than rebalance
#   threshold).
#
#   pmd.proc_cpu_cyc = 96
#   pmd.idle_cpu_cyc = 04
#   pmd.rx_cyc = 96
#
#   Hence that pmd would be shown at 96 % load capacity. When there are more
#   than one pmd to be created, at the minimum setting up one pmd to exceed
#   rebalance threshold value is must. The other pmds should setup load
#   capacity for 90 % in similar counter settings as above.
#
#   pmd.proc_cpu_cyc = 90
#   pmd.idle_cpu_cyc = 10
#   pmd.rx_cyc = 90
#
#   In all above, rx_cyc of a pmd should always reflect at proc_cpu_cyc
#   of that pmd for an easier calculation (i.e one packet per cpu cyc).
#
#   One or more rxq participating in a pmd for its load capacity, should
#   split proc_cpu_cyc among themself for a suitable rxq consumption level.
#
#   For eg, rxq1 and rxq2 in a pmd of load level 70 % could have
#   rxq1.cpu_cyc = 50
#   rxq1.rx_cyc = 50
#   rxq2.cpu_cyc = 20
#   rxq2.rx_cyc = 20
#
#   Every test should modify the default values provided by setup() function
#   for that test suite or fx_ function which was for a common usage across
#   the tests.
# -----------------------------------------------------------------------------


class TestRebalDryrun_OnePmd(TestCase):
    """
    Test rebalance for one or more rxq handled by one pmd.
    """

    rebalance_dryrun = dataif.rebalance_dryrun_by_cyc
    pmd_map = dict()
    core_id = 0

    # setup test environment
    def setUp(self):
        util.Memoize.forgot = True

        # turn off limited info shown in assert failure for pmd object.
        self.maxDiff = None

        dataif.Context.nlog = NlogNoop()

        # create one pmd object.
        fx_pmd = dataif.Dataif_Pmd(self.core_id)

        # let it be in numa 0.
        fx_pmd.numa_id = 0

        # add some cpu consumption for this pmd.
        for i in range(0, config.ncd_samples_max):
            fx_pmd.idle_cpu_cyc[i] = (4 * (i + 1))
            fx_pmd.proc_cpu_cyc[i] = (96 * (i + 1))
            fx_pmd.rx_cyc[i] = (96 * (i + 1))

        self.pmd_map[self.core_id] = fx_pmd
        return

    # Test case:
    #   With one pmd thread handling only one single-queue port, check whether
    #   rebalance is skipped.
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
            fx_rxq.cpu_cyc[i] = (96 * (i + 1))
            fx_rxq.rx_cyc[i] = (96 * (i + 1))

        # test dryrun
        n_reb_rxq = type(self).rebalance_dryrun(self.pmd_map)

        # validate results
        # 1. no rxqs be rebalanced.
        self.assertEqual(n_reb_rxq, -1)
        # 2. check pmd load
        self.assertEqual(dataif.pmd_load(pmd), 96)

        # del port object from pmd.
        pmd.del_port(port_name)

    # Test case:
    #   With one pmd thread handling few one single-queue ports, check whether
    #   rebalance is skipped.
    def test_many_rxq(self):
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
                fx_rxq.cpu_cyc[i] = (32 * (i + 1))
                fx_rxq.rx_cyc[i] = (32 * (i + 1))

        # test dryrun
        n_reb_rxq = type(self).rebalance_dryrun(self.pmd_map)

        # validate results
        # 1. no rxqs be rebalanced.
        self.assertEqual(n_reb_rxq, -1)
        # 2. check pmd load
        self.assertEqual(dataif.pmd_load(pmd), 96)

        # del port object from pmd.
        for port_name in ('virtport1', 'virtport2', 'virtport3'):
            pmd.del_port(port_name)


# Fixture:
#   create two pmd thread objects where in, each has one single-queued port.
def fx_2pmd_each_1rxq(testobj):
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
        fx_p1rxq.cpu_cyc[i] = (96 * (i + 1))
        fx_p1rxq.rx_cyc[i] = (96 * (i + 1))
        fx_p2rxq.cpu_cyc[i] = (90 * (i + 1))
        fx_p2rxq.rx_cyc[i] = (90 * (i + 1))


# Fixture:
#   Create two pmd thread objects where in, one pmd has two single-queued
#   ports, while the other is idle (without any port/rxq).
def fx_2pmd_one_empty(testobj):
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

    # add second port as well into pmd 1 for imbalance.
    fx_port2 = pmd1.add_port(port2_name)
    fx_port2.numa_id = pmd1.numa_id

    # add a dummy rxq into port.
    fx_p1rxq = fx_port1.add_rxq(0)
    fx_p1rxq.pmd = pmd1
    fx_p2rxq = fx_port2.add_rxq(0)
    fx_p2rxq.pmd = pmd1

    # add some cpu consumption for these rxqs.
    for i in range(0, config.ncd_samples_max):
        fx_p1rxq.cpu_cyc[i] = (6 * (i + 1))
        fx_p1rxq.rx_cyc[i] = (6 * (i + 1))
        fx_p2rxq.cpu_cyc[i] = (90 * (i + 1))
        fx_p2rxq.rx_cyc[i] = (90 * (i + 1))


# Fixture:
#   Create two pmd thread objects where in, each pmd has two single-queued
#   ports.
def fx_2pmd_each_2rxq(testobj):
    # retrieve pmd object.
    pmd1 = testobj.pmd_map[testobj.core1_id]
    pmd2 = testobj.pmd_map[testobj.core2_id]

    # one dummy port is required for this test.
    port1_name = 'virtport1'
    port2_name = 'virtport2'
    port3_name = 'virtport3'
    port4_name = 'virtport4'

    # create port class of name 'virtport'.
    dataif.make_dataif_port(port1_name)
    dataif.make_dataif_port(port2_name)
    dataif.make_dataif_port(port3_name)
    dataif.make_dataif_port(port4_name)

    # add port object into pmd.
    fx_port1 = pmd1.add_port(port1_name)
    fx_port1.numa_id = pmd1.numa_id
    fx_port2 = pmd2.add_port(port2_name)
    fx_port2.numa_id = pmd2.numa_id
    fx_port3 = pmd1.add_port(port3_name)
    fx_port3.numa_id = pmd1.numa_id
    fx_port4 = pmd2.add_port(port4_name)
    fx_port4.numa_id = pmd2.numa_id

    # add a dummy rxq into port.
    fx_p1rxq = fx_port1.add_rxq(0)
    fx_p1rxq.pmd = pmd1
    fx_p2rxq = fx_port2.add_rxq(0)
    fx_p2rxq.pmd = pmd2
    fx_p3rxq = fx_port3.add_rxq(0)
    fx_p3rxq.pmd = pmd1
    fx_p4rxq = fx_port4.add_rxq(0)
    fx_p4rxq.pmd = pmd2

    # add some cpu consumption for these rxqs.
    # order of rxqs based on cpu consumption: rxqp1,rxqp2,rxqp3,rxqp4
    for i in range(0, config.ncd_samples_max):
        fx_p1rxq.cpu_cyc[i] = (70 * (i + 1))
        fx_p1rxq.rx_cyc[i] = (6 * (i + 1))
        fx_p2rxq.cpu_cyc[i] = (65 * (i + 1))
        fx_p2rxq.rx_cyc[i] = (6 * (i + 1))
        fx_p3rxq.cpu_cyc[i] = (26 * (i + 1))
        fx_p3rxq.rx_cyc[i] = (6 * (i + 1))
        fx_p4rxq.cpu_cyc[i] = (25 * (i + 1))
        fx_p4rxq.rx_cyc[i] = (6 * (i + 1))

# Fixture:
#   Create two pmd thread objects where in, two queued ports split
#   among pmds.


def fx_2pmd_each_1p2rxq(testobj):
    # retrieve pmd object.
    pmd1 = testobj.pmd_map[testobj.core1_id]
    pmd2 = testobj.pmd_map[testobj.core2_id]

    # dummy ports required for this test.
    port1_name = 'virtport1'
    port2_name = 'virtport2'

    # create port class of name 'virtport'.
    dataif.make_dataif_port(port1_name)
    dataif.make_dataif_port(port2_name)

    # add port object into pmd.
    fx_port11 = pmd1.add_port(port1_name)
    fx_port11.numa_id = pmd1.numa_id
    fx_port22 = pmd2.add_port(port2_name)
    fx_port22.numa_id = pmd2.numa_id
    fx_port21 = pmd1.add_port(port2_name)
    fx_port21.numa_id = pmd1.numa_id
    fx_port12 = pmd2.add_port(port1_name)
    fx_port12.numa_id = pmd2.numa_id

    # add a dummy rxq into port.
    fx_p1rxq1 = fx_port11.add_rxq(0)
    fx_p1rxq1.pmd = pmd1
    fx_p2rxq2 = fx_port22.add_rxq(1)
    fx_p2rxq2.pmd = pmd2
    fx_p2rxq1 = fx_port21.add_rxq(0)
    fx_p2rxq1.pmd = pmd1
    fx_p1rxq2 = fx_port12.add_rxq(1)
    fx_p1rxq2.pmd = pmd2

    # add some cpu consumption for these rxqs.
    # order of rxqs based on cpu consumption: rxq1p1,rxq2p2,rxq1p2,rxq2p1
    for i in range(0, config.ncd_samples_max):
        fx_p1rxq1.cpu_cyc[i] = (90 * (i + 1))
        fx_p2rxq2.cpu_cyc[i] = (60 * (i + 1))
        fx_p1rxq2.cpu_cyc[i] = (30 * (i + 1))
        fx_p2rxq1.cpu_cyc[i] = (6 * (i + 1))


class TestRebalDryrun_TwoPmd(TestCase):
    """
    Test rebalance for one or more rxq handled by two pmds.
    """

    rebalance_dryrun = dataif.rebalance_dryrun_by_cyc
    pmd_map = dict()
    core1_id = 0
    core2_id = 1

    # setup test environment
    def setUp(self):
        util.Memoize.forgot = True

        # turn off limited info shown in assert failure for pmd object.
        self.maxDiff = None

        dataif.Context.nlog = NlogNoop()

        # create one pmd object.
        fx_pmd1 = dataif.Dataif_Pmd(self.core1_id)
        fx_pmd2 = dataif.Dataif_Pmd(self.core2_id)

        # let it be in numa 0.
        fx_pmd1.numa_id = 0
        fx_pmd2.numa_id = 0

        # add some cpu consumption for these pmds.
        for i in range(0, config.ncd_samples_max):
            fx_pmd1.idle_cpu_cyc[i] = (4 * (i + 1))
            fx_pmd1.proc_cpu_cyc[i] = (96 * (i + 1))
            fx_pmd1.rx_cyc[i] = (100 * (i + 1))

        for i in range(0, config.ncd_samples_max):
            fx_pmd2.idle_cpu_cyc[i] = (10 * (i + 1))
            fx_pmd2.proc_cpu_cyc[i] = (90 * (i + 1))
            fx_pmd2.rx_cyc[i] = (100 * (i + 1))

        self.pmd_map[self.core1_id] = fx_pmd1
        self.pmd_map[self.core2_id] = fx_pmd2
        return

    # Test case:
    #   With two threads from same numa, each handling only one single-queued
    #   port, check whether rebalance is skipped.
    def test_one_rxq_lnuma(self):
        # set same numa for pmds
        pmd1 = self.pmd_map[self.core1_id]
        pmd2 = self.pmd_map[self.core2_id]
        pmd1.numa_id = 0
        pmd2.numa_id = 0

        # create rxq
        fx_2pmd_each_1rxq(self)

        # update pmd load values
        dataif.update_pmd_load(self.pmd_map)

        # copy original pmd objects
        pmd_map = copy.deepcopy(self.pmd_map)

        # test dryrun
        n_reb_rxq = type(self).rebalance_dryrun(self.pmd_map)

        # validate results
        # 1. all two rxqs be rebalanced.
        self.assertEqual(n_reb_rxq, -1, "no rebalance expected")
        # 2. each pmd is not updated.
        self.assertEqual(pmd_map[self.core1_id], pmd1)
        self.assertEqual(pmd_map[self.core2_id], pmd2)
        # 3. check pmd load
        self.assertEqual(dataif.pmd_load(pmd1), 96)
        self.assertEqual(dataif.pmd_load(pmd2), 90)

        # del port object from pmd.
        # TODO: create fx_ post deletion routine for clean up
        pmd1.del_port('virtport1')
        pmd2.del_port('virtport2')

    # Test case:
    #   With two threads from same numa, where one pmd thread is handling
    #   two single-queued ports, while the other pmd is empty,
    #   check whether rebalance is performed.
    #   Scope is to check if only one rxq is moved to empty pmd.
    #
    #   order of rxqs based on cpu consumption: rxqp2,rxqp1
    #   order of pmds for rebalance dryrun: pmd1,pmd2
    #
    #   1. rxqp2(pmd1) -NOREB-> rxqp2(pmd1)
    #      rxqp1(pmd1)
    #        -  (pmd2)
    #
    #   2. rxqp2(pmd1) -NOREB-> rxqp2(pmd1)
    #      rxqp1(pmd1) --+--+-> rxqp1(reb_pmd2)
    #
    @mock.patch('netcontrold.lib.util.open')
    def test_two_1rxq_with_empty_lnuma(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=_FX_CPU_INFO).return_value
        ]

        # set same numa for pmds
        pmd1 = self.pmd_map[self.core1_id]
        pmd2 = self.pmd_map[self.core2_id]
        pmd1.numa_id = 0
        pmd2.numa_id = 0

        # let pmd2 be idle
        for i in range(0, config.ncd_samples_max):
            pmd2.idle_cpu_cyc[i] = (100 * (i + 1))
            pmd2.proc_cpu_cyc[i] = (0 * (i + 1))
            pmd2.rx_cyc[i] = (0 * (i + 1))

        # create rxq
        fx_2pmd_one_empty(self)

        # update pmd load values
        dataif.update_pmd_load(self.pmd_map)

        # copy original pmd objects
        pmd_map = copy.deepcopy(self.pmd_map)

        # test dryrun
        n_reb_rxq = type(self).rebalance_dryrun(self.pmd_map)

        # validate results
        # 1. all two rxqs be rebalanced.
        self.assertEqual(n_reb_rxq, 1, "one rxq to be rebalanced")
        # 2. each pmd is updated.
        self.assertNotEqual(pmd_map[self.core1_id], pmd1)
        self.assertNotEqual(pmd_map[self.core2_id], pmd2)
        # 3. check rxq map after dryrun.
        port1 = pmd1.find_port_by_name('virtport1')
        port2 = pmd1.find_port_by_name('virtport2')
        # 3.a rxqp2 remains in pmd1
        self.assertEqual(port2.rxq_rebalanced, {})
        self.assertEqual(port2.find_rxq_by_id(0).pmd.id, pmd1.id)
        # 3.a rxqp1 moves into pmd2
        self.assertEqual(port1.rxq_rebalanced[0], pmd2.id)
        # 4. check pmd load
        self.assertEqual(dataif.pmd_load(pmd1), 90)
        self.assertEqual(dataif.pmd_load(pmd2), 6)

        # del port object from pmd.
        # TODO: create fx_ post deletion routine for clean up
        pmd1.del_port('virtport1')
        pmd1.del_port('virtport2')

    # Test case:
    #   With two threads from same numa, where each pmd thread is  handling
    #   one queue from two-queued ports. check whether rebalance is performed.
    #   Scope is to check if rxq affinity is retained.
    #
    #   order of rxqs based on cpu consumption: rxq1p1,rxq2p2,rxq2p1,rxq1p2
    #   order of pmds for rebalance dryrun: pmd1,pmd2,pmd2,pmd1
    #
    #   1. rxq1p1(pmd1) 90% -NOREB-> rxq1p1(pmd1)
    #      rxq1p2(pmd1)  6% -NOREB-> rxq1p2(pmd1)
    #      rxq2p2(pmd2) 60% -NOREB-> rxq2p2(pmd2)
    #      rxq2p1(pmd2) 30% -NOREB-> rxq2p1(pmd1)
    #
    @mock.patch('netcontrold.lib.util.open')
    def test_two_1p2rxq_lnuma_norb(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=_FX_CPU_INFO).return_value
        ]

        # set same numa for pmds
        pmd1 = self.pmd_map[self.core1_id]
        pmd2 = self.pmd_map[self.core2_id]
        pmd1.numa_id = 0
        pmd2.numa_id = 0

        # create rxq
        fx_2pmd_each_1p2rxq(self)

        # update pmd load values
        dataif.update_pmd_load(self.pmd_map)

        # copy original pmd objects
        pmd_map = copy.deepcopy(self.pmd_map)

        # test dryrun
        n_reb_rxq = type(self).rebalance_dryrun(self.pmd_map)

        # validate results
        # 1. all four rxqs be rebalanced.
        self.assertEqual(n_reb_rxq, 0, "no rebalance expected")
        # 2. each pmd is updated.
        self.assertEqual(pmd_map[self.core1_id], pmd1)
        self.assertEqual(pmd_map[self.core2_id], pmd2)
        # 3. check rxq map after dryrun.
        port11 = pmd1.find_port_by_name('virtport1')
        port12 = pmd2.find_port_by_name('virtport1')
        port21 = pmd1.find_port_by_name('virtport2')
        port22 = pmd2.find_port_by_name('virtport2')
        self.assertEqual(port11.rxq_rebalanced, {})
        self.assertEqual(port22.rxq_rebalanced, {})
        self.assertEqual(port21.rxq_rebalanced, {})
        self.assertEqual(port12.rxq_rebalanced, {})
        # 4. check pmd load
        self.assertEqual(dataif.pmd_load(pmd1), 96)
        self.assertEqual(dataif.pmd_load(pmd2), 90)

        # del port object from pmd.
        # TODO: create fx_ post deletion routine for clean up
        pmd1.del_port('virtport1')
        pmd2.del_port('virtport2')

    # Test case:
    #   With two threads from same numa, where each pmd thread is  handling
    #   one queue from two-queued ports. check whether rebalance is performed.
    #   Scope is to check if rebalancing is not done on pmd that already
    #   has same port but different rxq.
    #   ( For now rebalance is allowed by switch, so follow)
    #
    #   order of rxqs based on cpu consumption: rxq2p2,rxq1p1,rxq1p3,
    #                                           rxq1p2,rxq2p1
    #   order of pmds for rebalance dryrun: pmd2,pmd1,pmd1,pmd2,pmd2
    #
    #   1. rxq1p1(pmd1) 66% -NOREB-> rxq1p1(pmd1)
    #      rxq1p3(pmd1) 22%
    #      rxq1p2(pmd1)  8%
    #      rxq2p2(pmd2) 86% -NOREB-> rxq2p2(pmd2)
    #      rxq2p1(pmd2)  4%
    #
    #   2. rxq2p2(pmd2) 86% -NOREB-> rxq2p2(pmd2)
    #      rxq1p1(pmd1) 66% -NOREB-> rxq1p1(pmd1)
    #      rxq1p3(pmd1) 22% -NOREB-> rxq1p3(pmd1)
    #      rxq1p2(pmd1)  8% --+--+-> rxq1p2(reb_pmd2)
    #      rxq2p1(pmd2)  4% -NOREB-> rxq2p1(pmd2)

    #
    @mock.patch('netcontrold.lib.util.open')
    def test_two_1p2rxq_lnuma(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=_FX_CPU_INFO).return_value
        ]

        # set same numa for pmds
        pmd1 = self.pmd_map[self.core1_id]
        pmd2 = self.pmd_map[self.core2_id]
        pmd1.numa_id = 0
        pmd2.numa_id = 0

        # create rxq
        fx_2pmd_each_1p2rxq(self)

        # we need an extra port to break retaining some ports.
        dataif.make_dataif_port('virtport3')
        port31 = pmd1.add_port('virtport3')
        port31.numa_id = pmd1.numa_id
        p3rxq1 = port31.add_rxq(0)
        p3rxq1.pmd = pmd1

        # update some cpu consumption for these rxqs.
        # order of rxqs based on cpu consumption:
        # rxq2p2,rxq1p1,rxq1p3,rxq1p2,rxq2p1
        port11 = pmd1.find_port_by_name('virtport1')
        port12 = pmd2.find_port_by_name('virtport1')
        port21 = pmd1.find_port_by_name('virtport2')
        port22 = pmd2.find_port_by_name('virtport2')
        p1rxq1 = port11.find_rxq_by_id(0)
        p1rxq2 = port12.find_rxq_by_id(1)
        p2rxq1 = port21.find_rxq_by_id(0)
        p2rxq2 = port22.find_rxq_by_id(1)

        for i in range(0, config.ncd_samples_max):
            p2rxq2.cpu_cyc[i] = (86 * (i + 1))
            p1rxq1.cpu_cyc[i] = (66 * (i + 1))
            p3rxq1.cpu_cyc[i] = (22 * (i + 1))
            p2rxq1.cpu_cyc[i] = (8 * (i + 1))
            p1rxq2.cpu_cyc[i] = (4 * (i + 1))

        # update pmd load values
        dataif.update_pmd_load(self.pmd_map)

        # copy original pmd objects
        pmd_map = copy.deepcopy(self.pmd_map)

        # test dryrun
        n_reb_rxq = type(self).rebalance_dryrun(self.pmd_map)

        # validate results
        # 1. all four rxqs be rebalanced.
        self.assertEqual(n_reb_rxq, 1, "one rxq to be rebalanced")
        # 2. each pmd is updated.
        self.assertNotEqual(pmd_map[self.core1_id], pmd1)
        self.assertNotEqual(pmd_map[self.core2_id], pmd2)
        # 3. check rxq map after dryrun.
        self.assertEqual(port11.rxq_rebalanced, {})
        self.assertEqual(port22.rxq_rebalanced, {})
        self.assertEqual(port31.rxq_rebalanced, {})
        self.assertEqual(port21.rxq_rebalanced[0], pmd2.id)
        self.assertEqual(port12.rxq_rebalanced, {})
        # 4. check pmd load
        self.assertEqual(dataif.pmd_load(pmd1), 88)
        self.assertEqual(dataif.pmd_load(pmd2), 98)

        # del port object from pmd.
        # TODO: create fx_ post deletion routine for clean up
        pmd1.del_port('virtport1')
        pmd1.del_port('virtport3')
        pmd2.del_port('virtport2')

    # Test case:
    #   With two threads from same numa, where each pmd thread is handling
    #   two single-queued ports. check whether rebalance is performed.
    #   Scope is to check if rxq from a pmd which was a rebalancing pmd
    #   before, is assigned other pmd successfully.
    #
    #   order of rxqs based on cpu consumption: rxqp1,rxqp2,rxqp3,rxqp4
    #   order of pmds for rebalance dryrun: pmd1,pmd2,pmd2,pmd1
    #
    #   1. rxqp1(pmd1) -NOREB-> rxqp1(pmd1)
    #      rxqp2(pmd2) -NOREB-> rxqp2(pmd2)
    #      rxqp3(pmd1) --+--+-> rxqp3(reb_pmd2)
    #      rxqp4(pmd2)
    #
    #   2. rxqp1(pmd1) -NOREB-> rxqp1(pmd1)
    #      rxqp2(pmd2) -NOREB-> rxqp2(pmd2)
    #      rxqp3(pmd1) --+--+-> rxqp3(reb_pmd2)
    #      rxqp4(pmd2) --+--+-> rxqp4(reb_pmd1)
    #
    @mock.patch('netcontrold.lib.util.open')
    def test_four_1rxq_lnuma(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=_FX_CPU_INFO).return_value
        ]

        # set same numa for pmds
        pmd1 = self.pmd_map[self.core1_id]
        pmd2 = self.pmd_map[self.core2_id]
        pmd1.numa_id = 0
        pmd2.numa_id = 0

        # create rxq
        fx_2pmd_each_2rxq(self)

        # update pmd load values
        dataif.update_pmd_load(self.pmd_map)

        # copy original pmd objects
        pmd_map = copy.deepcopy(self.pmd_map)

        # test dryrun
        n_reb_rxq = type(self).rebalance_dryrun(self.pmd_map)

        # validate results
        # 1. all four rxqs be rebalanced.
        self.assertEqual(n_reb_rxq, 2, "two rxqs to be rebalanced")
        # 2. each pmd is updated.
        self.assertNotEqual(pmd_map[self.core1_id], pmd1)
        self.assertNotEqual(pmd_map[self.core2_id], pmd2)
        # 3. check rxq map after dryrun.
        port1 = pmd1.find_port_by_name('virtport1')
        port2 = pmd2.find_port_by_name('virtport2')
        port3 = pmd1.find_port_by_name('virtport3')
        port4 = pmd2.find_port_by_name('virtport4')
        self.assertEqual(port1.rxq_rebalanced, {})
        self.assertEqual(port2.rxq_rebalanced, {})
        self.assertEqual(port3.rxq_rebalanced[0], pmd2.id)
        self.assertEqual(port4.rxq_rebalanced[0], pmd1.id)

        # del port object from pmd.
        # TODO: create fx_ post deletion routine for clean up
        pmd1.del_port('virtport1')
        pmd2.del_port('virtport2')

    # Test case:
    #   With two threads from same numa, where each pmd thread is handling
    #   two single-queued ports. Of them, only one rxq is busy while the
    #   rest are idle. check whether rebalance is not moving busy rxq
    #   from its pmd, while rest (which are idle rxqs) could be repinned
    #   accordingly.
    #
    #   order of rxqs based on cpu consumption: rxqp4 (and some order on
    #                                           rxqp2,rxqp3,rxqp4)
    #   order of pmds for rebalance dryrun: pmd1,pmd2,pmd2,pmd1
    #
    #   1. rxqp1(pmd1)
    #      rxqp2(pmd2)
    #      rxqp3(pmd1)
    #      rxqp4(pmd2) -NOREB-> rxqp4(pmd2)
    #
    @mock.patch('netcontrold.lib.util.open')
    def test_four_1rxq_skip_lnuma(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=_FX_CPU_INFO).return_value
        ]

        # set same numa for pmds
        pmd1 = self.pmd_map[self.core1_id]
        pmd2 = self.pmd_map[self.core2_id]
        pmd1.numa_id = 0
        pmd2.numa_id = 0

        # create rxq
        fx_2pmd_each_2rxq(self)

        # except one rxq, let rest be idle.
        port1 = pmd1.find_port_by_name('virtport1')
        port2 = pmd2.find_port_by_name('virtport2')
        port3 = pmd1.find_port_by_name('virtport3')
        port4 = pmd2.find_port_by_name('virtport4')
        p1rxq = port1.find_rxq_by_id(0)
        p2rxq = port2.find_rxq_by_id(0)
        p3rxq = port3.find_rxq_by_id(0)
        p4rxq = port4.find_rxq_by_id(0)
        for i in range(0, config.ncd_samples_max):
            p1rxq.cpu_cyc[i] = 0
            p2rxq.cpu_cyc[i] = 0
            p3rxq.cpu_cyc[i] = 0
            p4rxq.cpu_cyc[i] = (98 * (i + 1))

        # fix cpu consumption for these pmds.
        for i in range(0, config.ncd_samples_max):
            pmd1.idle_cpu_cyc[i] = (100 * (i + 1))
            pmd1.proc_cpu_cyc[i] = (0 + (0 * i))
            pmd1.rx_cyc[i] = (0 * (i + 1))

        for i in range(0, config.ncd_samples_max):
            pmd2.idle_cpu_cyc[i] = (2 * (i + 1))
            pmd2.proc_cpu_cyc[i] = (98 * (i + 1))
            pmd2.rx_cyc[i] = (98 * (i + 1))

        # update pmd load values
        dataif.update_pmd_load(self.pmd_map)

        # copy original pmd objects
        pmd_map = copy.deepcopy(self.pmd_map)

        # test dryrun
        n_reb_rxq = type(self).rebalance_dryrun(self.pmd_map)

        # validate results
        # 1. all four rxqs be rebalanced.
        self.assertEqual(n_reb_rxq, 0, "expected no rebalance")
        # 2. each pmd is not updated.
        self.assertEqual(pmd_map[self.core1_id], pmd1)
        self.assertEqual(pmd_map[self.core2_id], pmd2)
        # 3. check rxq map after dryrun.
        self.assertEqual(port1.rxq_rebalanced, {})
        self.assertEqual(port2.rxq_rebalanced, {})
        self.assertEqual(port3.rxq_rebalanced, {})
        self.assertEqual(port4.rxq_rebalanced, {})
        # 3.a and dry-run did not break original pinning.
        self.assertEqual(p4rxq.pmd.id, pmd2.id)

        # del port object from pmd.
        # TODO: create fx_ post deletion routine for clean up
        pmd1.del_port('virtport1')
        pmd2.del_port('virtport2')
        pmd1.del_port('virtport3')
        pmd2.del_port('virtport4')

    # Test case:
    #   With two threads from same numa, where each pmd thread is handling
    #   two single-queued ports. Of them, all are busy. check whether
    #   rebalance is skipped.
    #
    #   order of rxqs based on cpu consumption: N/A
    #   order of pmds for rebalance dryrun: N/A
    #
    #   1. rxqp1(pmd1)
    #      rxqp2(pmd2)
    #      rxqp3(pmd1)
    #      rxqp4(pmd2)
    #
    @mock.patch('netcontrold.lib.util.open')
    def test_4busy_1rxq_skip_lnuma(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=_FX_CPU_INFO).return_value
        ]

        # set same numa for pmds
        pmd1 = self.pmd_map[self.core1_id]
        pmd2 = self.pmd_map[self.core2_id]
        pmd1.numa_id = 0
        pmd2.numa_id = 0

        # create rxq
        fx_2pmd_each_2rxq(self)

        # fix cpu consumption for these pmds.
        for i in range(0, config.ncd_samples_max):
            pmd1.idle_cpu_cyc[i] = (4 * (i + 1))
            pmd1.proc_cpu_cyc[i] = (96 * (i + 1))
            pmd1.rx_cyc[i] = (96 * (i + 1))

        for i in range(0, config.ncd_samples_max):
            pmd1.idle_cpu_cyc[i] = (10 * (i + 1))
            pmd1.proc_cpu_cyc[i] = (90 * (i + 1))
            pmd1.rx_cyc[i] = (90 * (i + 1))

        # update pmd load values
        dataif.update_pmd_load(self.pmd_map)

        # copy original pmd objects
        pmd_map = copy.deepcopy(self.pmd_map)

        # test dryrun
        n_reb_rxq = type(self).rebalance_dryrun(self.pmd_map)

        # validate results
        port1 = pmd1.find_port_by_name('virtport1')
        port2 = pmd2.find_port_by_name('virtport2')
        port3 = pmd1.find_port_by_name('virtport3')
        port4 = pmd2.find_port_by_name('virtport4')
        # 1. all four rxqs be rebalanced.
        self.assertEqual(n_reb_rxq, -1, "skip rebalance")
        # 2. each pmd is not updated.
        self.assertEqual(pmd_map[self.core1_id], pmd1)
        self.assertEqual(pmd_map[self.core2_id], pmd2)
        # 3. check rxq map after dryrun.
        self.assertEqual(port1.rxq_rebalanced, {})
        self.assertEqual(port2.rxq_rebalanced, {})
        self.assertEqual(port3.rxq_rebalanced, {})
        self.assertEqual(port4.rxq_rebalanced, {})

        # del port object from pmd.
        # TODO: create fx_ post deletion routine for clean up
        pmd1.del_port('virtport1')
        pmd2.del_port('virtport2')
        pmd1.del_port('virtport3')
        pmd2.del_port('virtport4')


# Fixture:
#   Create four pmd thread objects where in, each pmd has two single-queued
#   ports.


def fx_4pmd_each_2rxq(testobj):
    # retrieve pmd object.
    pmd1 = testobj.pmd_map[testobj.core1_id]
    pmd2 = testobj.pmd_map[testobj.core2_id]
    pmd3 = testobj.pmd_map[testobj.core3_id]
    pmd4 = testobj.pmd_map[testobj.core4_id]

    # one dummy port is required for this test.
    port1_name = 'virtport1'
    port2_name = 'virtport2'
    port3_name = 'virtport3'
    port4_name = 'virtport4'
    port5_name = 'virtport5'
    port6_name = 'virtport6'
    port7_name = 'virtport7'
    port8_name = 'virtport8'

    # create port class of name 'virtport'.
    dataif.make_dataif_port(port1_name)
    dataif.make_dataif_port(port2_name)
    dataif.make_dataif_port(port3_name)
    dataif.make_dataif_port(port4_name)
    dataif.make_dataif_port(port5_name)
    dataif.make_dataif_port(port6_name)
    dataif.make_dataif_port(port7_name)
    dataif.make_dataif_port(port8_name)

    # add port object into pmd.
    fx_port1 = pmd1.add_port(port1_name)
    fx_port1.numa_id = pmd1.numa_id
    fx_port2 = pmd2.add_port(port2_name)
    fx_port2.numa_id = pmd2.numa_id
    fx_port3 = pmd3.add_port(port3_name)
    fx_port3.numa_id = pmd3.numa_id
    fx_port4 = pmd4.add_port(port4_name)
    fx_port4.numa_id = pmd4.numa_id
    fx_port5 = pmd1.add_port(port5_name)
    fx_port5.numa_id = pmd1.numa_id
    fx_port6 = pmd2.add_port(port6_name)
    fx_port6.numa_id = pmd2.numa_id
    fx_port7 = pmd3.add_port(port7_name)
    fx_port7.numa_id = pmd3.numa_id
    fx_port8 = pmd4.add_port(port8_name)
    fx_port8.numa_id = pmd4.numa_id

    # add a dummy rxq into port.
    fx_p1rxq = fx_port1.add_rxq(0)
    fx_p1rxq.pmd = pmd1
    fx_p2rxq = fx_port2.add_rxq(0)
    fx_p2rxq.pmd = pmd2
    fx_p3rxq = fx_port3.add_rxq(0)
    fx_p3rxq.pmd = pmd3
    fx_p4rxq = fx_port4.add_rxq(0)
    fx_p4rxq.pmd = pmd4
    fx_p5rxq = fx_port5.add_rxq(0)
    fx_p5rxq.pmd = pmd1
    fx_p6rxq = fx_port6.add_rxq(0)
    fx_p6rxq.pmd = pmd2
    fx_p7rxq = fx_port7.add_rxq(0)
    fx_p7rxq.pmd = pmd3
    fx_p8rxq = fx_port8.add_rxq(0)
    fx_p8rxq.pmd = pmd4

    # add some cpu consumption for these rxqs.
    # order of rxqs based on cpu consumption: rxqp1,rxqp2,..rxqp8
    for i in range(0, config.ncd_samples_max):
        fx_p1rxq.cpu_cyc[i] = (76 * (i + 1))
        fx_p2rxq.cpu_cyc[i] = (75 * (i + 1))
        fx_p3rxq.cpu_cyc[i] = (74 * (i + 1))
        fx_p4rxq.cpu_cyc[i] = (73 * (i + 1))
        fx_p5rxq.cpu_cyc[i] = (20 * (i + 1))
        fx_p6rxq.cpu_cyc[i] = (15 * (i + 1))
        fx_p7rxq.cpu_cyc[i] = (11 * (i + 1))
        fx_p8rxq.cpu_cyc[i] = (7 * (i + 1))


class TestRebalDryrun_FourPmd(TestCase):
    """
    Test rebalance for one or more rxq handled by four pmds.
    """

    rebalance_dryrun = dataif.rebalance_dryrun_by_cyc
    pmd_map = dict()
    core1_id = 0
    core2_id = 1
    core3_id = 4
    core4_id = 5

    # setup test environment
    def setUp(self):
        util.Memoize.forgot = True

        # turn off limited info shown in assert failure for pmd object.
        self.maxDiff = None

        dataif.Context.nlog = NlogNoop()

        # create one pmd object.
        fx_pmd1 = dataif.Dataif_Pmd(self.core1_id)
        fx_pmd2 = dataif.Dataif_Pmd(self.core2_id)
        fx_pmd3 = dataif.Dataif_Pmd(self.core3_id)
        fx_pmd4 = dataif.Dataif_Pmd(self.core4_id)

        # let it be in numa 0.
        fx_pmd1.numa_id = 0
        fx_pmd2.numa_id = 0
        fx_pmd3.numa_id = 0
        fx_pmd4.numa_id = 0

        # add some cpu consumption for these pmds.
        for i in range(0, config.ncd_samples_max):
            fx_pmd1.idle_cpu_cyc[i] = (4 * (i + 1))
            fx_pmd1.proc_cpu_cyc[i] = (96 * (i + 1))
            fx_pmd1.rx_cyc[i] = (96 * (i + 1))

        for i in range(0, config.ncd_samples_max):
            fx_pmd2.idle_cpu_cyc[i] = (10 * (i + 1))
            fx_pmd2.proc_cpu_cyc[i] = (90 * (i + 1))
            fx_pmd2.rx_cyc[i] = (90 * (i + 1))

        for i in range(0, config.ncd_samples_max):
            fx_pmd3.idle_cpu_cyc[i] = (15 * (i + 1))
            fx_pmd3.proc_cpu_cyc[i] = (85 * (i + 1))
            fx_pmd3.rx_cyc[i] = (85 * (i + 1))

        for i in range(0, config.ncd_samples_max):
            fx_pmd4.idle_cpu_cyc[i] = (20 * (i + 1))
            fx_pmd4.proc_cpu_cyc[i] = (80 * (i + 1))
            fx_pmd4.rx_cyc[i] = (80 * (i + 1))

        self.pmd_map[self.core1_id] = fx_pmd1
        self.pmd_map[self.core2_id] = fx_pmd2
        self.pmd_map[self.core3_id] = fx_pmd3
        self.pmd_map[self.core4_id] = fx_pmd4
        return

    # Test case:
    #   With four threads from same numa, where each pmd thread is handling
    #   two single-queued ports. check whether rebalance is performed.
    #   Scope is to check if rxq from a pmd which was a rebalancing pmd
    #   before, is assigned other pmd successfully.
    #
    #   order of rxqs based on cpu consumption: rxqp1,rxqp2,rxqp3,rxqp4
    #   order of pmds for rebalance dryrun: pmd1,pmd2,pmd3,pmd4
    #
    #   1. rxqp1(pmd1) -NOREB-> rxqp1(pmd1)
    #      rxqp2(pmd2) -NOREB-> rxqp2(pmd2)
    #      rxqp3(pmd3) -NOREB-> rxqp3(pmd3)
    #      rxqp4(pmd4) -NOREB-> rxqp4(pmd4)
    #      rxqp5(pmd1)
    #      rxqp6(pmd2)
    #      rxqp7(pmd3)
    #      rxqp8(pmd4)
    #
    #   2. rxqp1(pmd1) -NOREB-> rxqp1(pmd1)
    #      rxqp2(pmd2) -NOREB-> rxqp2(pmd2)
    #      rxqp3(pmd3) -NOREB-> rxqp3(pmd3)
    #      rxqp4(pmd4) -NOREB-> rxqp4(pmd4)
    #      rxqp5(pmd1) --+--+-> rxqp5(pmd4)
    #      rxqp6(pmd2) --+--+-> rxqp6(pmd3)
    #      rxqp7(pmd3) --+--+-> rxqp7(pmd2)
    #      rxqp8(pmd4) --+--+-> rxqp8(pmd1)
    #
    @mock.patch('netcontrold.lib.util.open')
    def test_eight_1rxq_lnuma(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=_FX_4X2CPU_INFO).return_value
        ]

        # set same numa for pmds
        pmd1 = self.pmd_map[self.core1_id]
        pmd2 = self.pmd_map[self.core2_id]
        pmd3 = self.pmd_map[self.core3_id]
        pmd4 = self.pmd_map[self.core4_id]
        pmd1.numa_id = 0
        pmd2.numa_id = 0
        pmd3.numa_id = 0
        pmd4.numa_id = 0

        # create rxq
        fx_4pmd_each_2rxq(self)

        # update pmd load values
        dataif.update_pmd_load(self.pmd_map)

        # copy original pmd objects
        pmd_map = copy.deepcopy(self.pmd_map)

        # test dryrun
        n_reb_rxq = type(self).rebalance_dryrun(self.pmd_map)

        # validate results
        # 1. all four rxqs be rebalanced.
        self.assertEqual(n_reb_rxq, 4, "four rxqs to be rebalanced")
        # 2. each pmd is updated.
        self.assertNotEqual(pmd_map[self.core1_id], pmd1)
        self.assertNotEqual(pmd_map[self.core2_id], pmd2)
        self.assertNotEqual(pmd_map[self.core3_id], pmd3)
        self.assertNotEqual(pmd_map[self.core4_id], pmd4)
        # 3. check rxq map after dryrun.
        port1 = pmd1.find_port_by_name('virtport1')
        port2 = pmd2.find_port_by_name('virtport2')
        port3 = pmd3.find_port_by_name('virtport3')
        port4 = pmd4.find_port_by_name('virtport4')
        port5 = pmd1.find_port_by_name('virtport5')
        port6 = pmd2.find_port_by_name('virtport6')
        port7 = pmd3.find_port_by_name('virtport7')
        port8 = pmd4.find_port_by_name('virtport8')
        self.assertEqual(port1.rxq_rebalanced, {})
        self.assertEqual(port2.rxq_rebalanced, {})
        self.assertEqual(port3.rxq_rebalanced, {})
        self.assertEqual(port4.rxq_rebalanced, {})
        self.assertEqual(port5.rxq_rebalanced[0], pmd4.id)
        self.assertEqual(port6.rxq_rebalanced[0], pmd3.id)
        self.assertEqual(port7.rxq_rebalanced[0], pmd2.id)
        self.assertEqual(port8.rxq_rebalanced[0], pmd1.id)

        # del port object from pmd.
        # TODO: create fx_ post deletion routine for clean up
        pmd1.del_port('virtport1')
        pmd2.del_port('virtport2')
        pmd3.del_port('virtport3')
        pmd4.del_port('virtport4')


# Fixture:
#   Create two pmd thread objects per numa where in, one pmd has three
#   single-queued ports, while the other is idle (without any port/rxq).
def fx_2pmd_one_empty_per_numa(testobj):
    # retrieve pmd object.
    pmd1 = testobj.pmd_map[testobj.core1_id]
    pmd3 = testobj.pmd_map[testobj.core3_id]

    # dummy ports required for this test.
    port1_name = 'virtport1'
    port2_name = 'virtport2'
    port3_name = 'virtport3'
    port4_name = 'virtport4'
    port5_name = 'virtport5'
    port6_name = 'virtport6'

    # create port class of name 'virtport'.
    dataif.make_dataif_port(port1_name)
    dataif.make_dataif_port(port2_name)
    dataif.make_dataif_port(port3_name)
    dataif.make_dataif_port(port4_name)
    dataif.make_dataif_port(port5_name)
    dataif.make_dataif_port(port6_name)

    # add port object into pmd.
    fx_port1 = pmd1.add_port(port1_name)
    fx_port1.numa_id = pmd1.numa_id
    fx_port2 = pmd1.add_port(port2_name)
    fx_port2.numa_id = pmd1.numa_id
    fx_port3 = pmd1.add_port(port3_name)
    fx_port3.numa_id = pmd1.numa_id
    fx_port4 = pmd3.add_port(port4_name)
    fx_port4.numa_id = pmd3.numa_id
    fx_port5 = pmd3.add_port(port5_name)
    fx_port5.numa_id = pmd3.numa_id
    fx_port6 = pmd3.add_port(port6_name)
    fx_port6.numa_id = pmd3.numa_id

    # add a dummy rxq into port.
    fx_p1rxq = fx_port1.add_rxq(0)
    fx_p1rxq.pmd = pmd1
    fx_p2rxq = fx_port2.add_rxq(0)
    fx_p2rxq.pmd = pmd1
    fx_p3rxq = fx_port3.add_rxq(0)
    fx_p3rxq.pmd = pmd1
    fx_p4rxq = fx_port4.add_rxq(0)
    fx_p4rxq.pmd = pmd3
    fx_p5rxq = fx_port5.add_rxq(0)
    fx_p5rxq.pmd = pmd3
    fx_p6rxq = fx_port6.add_rxq(0)
    fx_p6rxq.pmd = pmd3

    # add some cpu consumption for these rxqs.
    # order of rxqs based on cpu consumption: rxqp2,rxqp1,rxqp3,
    #                                         rxqp5,rxqp4,rxqp6
    for i in range(0, config.ncd_samples_max):
        fx_p2rxq.cpu_cyc[i] = (66 * (i + 1))
        fx_p1rxq.cpu_cyc[i] = (20 * (i + 1))
        fx_p3rxq.cpu_cyc[i] = (10 * (i + 1))
        fx_p5rxq.cpu_cyc[i] = (66 * (i + 1))
        fx_p4rxq.cpu_cyc[i] = (20 * (i + 1))
        fx_p6rxq.cpu_cyc[i] = (10 * (i + 1))


class TestRebalDryrun_FourPmd_Numa(TestCase):
    """
    Test rebalance for one or more rxq handled by four pmds.
    """

    rebalance_dryrun = dataif.rebalance_dryrun_by_cyc
    pmd_map = dict()
    core1_id = 0
    core2_id = 1
    core3_id = 6
    core4_id = 7

    # setup test environment
    def setUp(self):
        util.Memoize.forgot = True

        # turn off limited info shown in assert failure for pmd object.
        self.maxDiff = None

        dataif.Context.nlog = NlogNoop()

        # create one pmd object.
        fx_pmd1 = dataif.Dataif_Pmd(self.core1_id)
        fx_pmd2 = dataif.Dataif_Pmd(self.core2_id)
        fx_pmd3 = dataif.Dataif_Pmd(self.core3_id)
        fx_pmd4 = dataif.Dataif_Pmd(self.core4_id)

        # let it be in numa 0.
        fx_pmd1.numa_id = 0
        fx_pmd2.numa_id = 0
        fx_pmd3.numa_id = 1
        fx_pmd4.numa_id = 1

        # add some cpu consumption for these pmds.
        for i in range(0, config.ncd_samples_max):
            fx_pmd1.idle_cpu_cyc[i] = (4 * (i + 1))
            fx_pmd1.proc_cpu_cyc[i] = (96 * (i + 1))
            fx_pmd1.rx_cyc[i] = (96 * (i + 1))

        for i in range(0, config.ncd_samples_max):
            fx_pmd2.idle_cpu_cyc[i] = (10 * (i + 1))
            fx_pmd2.proc_cpu_cyc[i] = (90 * (i + 1))
            fx_pmd2.rx_cyc[i] = (90 * (i + 1))

        for i in range(0, config.ncd_samples_max):
            fx_pmd3.idle_cpu_cyc[i] = (15 * (i + 1))
            fx_pmd3.proc_cpu_cyc[i] = (85 * (i + 1))
            fx_pmd3.rx_cyc[i] = (85 * (i + 1))

        for i in range(0, config.ncd_samples_max):
            fx_pmd4.idle_cpu_cyc[i] = (20 * (i + 1))
            fx_pmd4.proc_cpu_cyc[i] = (80 * (i + 1))
            fx_pmd4.rx_cyc[i] = (80 * (i + 1))

        self.pmd_map[self.core1_id] = fx_pmd1
        self.pmd_map[self.core2_id] = fx_pmd2
        self.pmd_map[self.core3_id] = fx_pmd3
        self.pmd_map[self.core4_id] = fx_pmd4
        return

    # Test case:
    #   With two threads per numa, where one pmd thread is handling
    #   two single-queued ports, while the other pmd is empty,
    #   check whether rebalance is performed in each numa.
    #   Scope is to check if only one rxq is moved to empty pmd
    #   within numa affinity.
    #
    #   order of rxqs based on cpu consumption: rxqp2,rxqp1,rxqp5,rxqp4
    #   order of pmds for rebalance dryrun: pmd1N0,pmd3N1,pmd2N0,pmd4N1
    #
    #   1. rxqp2(pmd1N0) -NOREB-> rxqp2(pmd1N0)
    #      rxqp1(pmd1N0)
    #        -  (pmd2N0)
    #
    #   2  rxqp5(pmd3N1) -NOREB-> rxqp5(pmd3N0)
    #      rxqp4(pmd3N1)
    #        -  (pmd4N1)
    #
    #   3. rxqp2(pmd1N0) -NOREB-> rxqp2(pmd1N0)
    #      rxqp1(pmd1N0) --+--+-> rxqp1(reb_pmd2N0)
    #
    #   4. rxqp5(pmd3N1) -NOREB-> rxqp5(pmd3N1)
    #      rxqp4(pmd3N1) --+--+-> rxqp4(reb_pmd4N1)
    #
    @mock.patch('netcontrold.lib.util.open')
    def test_two_1rxq_with_empty_per_numa(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=_FX_4X2CPU_INFO).return_value
        ]

        # set numa for pmds
        self.core1_id = 0
        self.core2_id = 1
        self.core3_id = 6
        self.core4_id = 7
        pmd1 = self.pmd_map[self.core1_id]
        pmd2 = self.pmd_map[self.core2_id]
        pmd3 = self.pmd_map[self.core3_id]
        pmd4 = self.pmd_map[self.core4_id]

        # create rxq
        fx_2pmd_one_empty_per_numa(self)

        # delete excess ports in pmds
        pmd1.del_port('virtport3')
        pmd3.del_port('virtport6')

        # update pmd load values
        dataif.update_pmd_load(self.pmd_map)

        # copy original pmd objects
        pmd_map = copy.deepcopy(self.pmd_map)

        # test dryrun
        n_reb_rxq = type(self).rebalance_dryrun(self.pmd_map)

        # validate results
        # 1. all two rxqs be rebalanced.
        self.assertEqual(n_reb_rxq, 2, "two rxqs to be rebalanced")
        # 2. each pmd is updated.
        self.assertNotEqual(pmd_map[self.core1_id], pmd1)
        self.assertNotEqual(pmd_map[self.core2_id], pmd2)
        self.assertNotEqual(pmd_map[self.core3_id], pmd3)
        self.assertNotEqual(pmd_map[self.core4_id], pmd4)
        # 3. check rxq map after dryrun.
        port1 = pmd1.find_port_by_name('virtport1')
        port2 = pmd1.find_port_by_name('virtport2')
        port4 = pmd3.find_port_by_name('virtport4')
        port5 = pmd3.find_port_by_name('virtport5')
        port2reb = pmd2.find_port_by_name('virtport1')
        port4reb = pmd4.find_port_by_name('virtport4')
        # 3.a rxqp2 remains in pmd1
        self.assertEqual(port2.rxq_rebalanced, {})
        self.assertEqual(port2.find_rxq_by_id(0).pmd.id, pmd1.id)
        # 3.b rxqp3 remains in pmd3
        self.assertEqual(port5.rxq_rebalanced, {})
        self.assertEqual(port5.find_rxq_by_id(0).pmd.id, pmd3.id)
        # 3.c rxqp1 moves from pmd1 to pmd2
        self.assertEqual(port1.rxq_rebalanced[0], pmd2.id)
        self.assertIsNone(port1.find_rxq_by_id(0))
        # 3.c.0 and dry-run did not break original pinning.
        rxqp2reb = port2reb.find_rxq_by_id(0)
        self.assertEqual(rxqp2reb.pmd.id, pmd1.id)
        # 3.d rxqp4 moves from pmd3 to pmd4
        self.assertEqual(port4.rxq_rebalanced[0], pmd4.id)
        self.assertIsNone(port4.find_rxq_by_id(0))
        # 3.d.0 and dry-run did not break original pinning.
        rxqp4reb = port4reb.find_rxq_by_id(0)
        self.assertEqual(rxqp4reb.pmd.id, pmd3.id)

        # del port object from pmd.
        # TODO: create fx_ post deletion routine for clean up
        pmd1.del_port('virtport1')
        pmd1.del_port('virtport2')
        pmd3.del_port('virtport5')
        pmd3.del_port('virtport4')

    # Test case:
    #   With two threads per numa, where one pmd thread is handling
    #   three single-queued ports in first numa, with the other pmd being
    #   idle, at the same time pmds in other numa are entirely idle.
    #   Check whether rebalance is performed in only first numa.
    #   Scope is to check if only one rxq is moved to empty pmd
    #   within numa affinity.
    #
    #   order of rxqs based on cpu consumption: rxqp2,rxqp1,rxqp3
    #   order of pmds for rebalance dryrun: pmd1N0,pmd3N1,pmd2N0,pmd4N1
    #
    #   1. rxqp2(pmd1N0) -NOREB-> rxqp2(pmd1N0)
    #      rxqp1(pmd1N0)
    #      rxqp3(pmd1N0)
    #        -  (pmd2N0)
    #
    #        -  (pmd3N1)
    #        -  (pmd4N1)
    #
    #   2. rxqp2(pmd1N0) -NOREB-> rxqp2(pmd1N0)
    #      rxqp1(pmd1N0) --+--+-> rxqp1(reb_pmd2N0)
    #      rxqp3(pmd1N0)
    #
    #        -  (pmd3N1)
    #        -  (pmd4N1)
    #
    #   3. rxqp2(pmd1N0) -NOREB-> rxqp2(pmd1N0)
    #      rxqp1(pmd1N0) --+--+-> rxqp1(reb_pmd2N0)
    #      rxqp3(pmd1N0) --+--+-> rxqp3(reb_pmd2N0)
    #
    #        -  (pmd3N1)
    #        -  (pmd4N1)
    #
    @mock.patch('netcontrold.lib.util.open')
    def test_two_1rxq_with_empty_one_numa(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=_FX_4X2CPU_INFO).return_value
        ]

        # set numa for pmds
        self.core1_id = 0
        self.core2_id = 1
        self.core3_id = 6
        self.core4_id = 7
        pmd1 = self.pmd_map[self.core1_id]
        pmd2 = self.pmd_map[self.core2_id]
        pmd3 = self.pmd_map[self.core3_id]
        pmd4 = self.pmd_map[self.core4_id]

        # create rxq
        fx_2pmd_one_empty_per_numa(self)

        # empty pmd threads in second numa
        pmd3.del_port('virtport4')
        pmd3.del_port('virtport5')
        pmd3.del_port('virtport6')

        # update pmd load values
        dataif.update_pmd_load(self.pmd_map)

        # copy original pmd objects
        pmd_map = copy.deepcopy(self.pmd_map)

        # test dryrun
        n_reb_rxq = type(self).rebalance_dryrun(self.pmd_map)

        # validate results
        # 1. two rxqs be rebalanced in numa 1.
        self.assertEqual(n_reb_rxq, 2, "two rxqs to be rebalanced")
        # 2. each pmd is updated, except numa 2.
        self.assertNotEqual(pmd_map[self.core1_id], pmd1)
        self.assertNotEqual(pmd_map[self.core2_id], pmd2)
        self.assertEqual(pmd_map[self.core3_id], pmd3)
        self.assertEqual(pmd_map[self.core4_id], pmd4)
        # 3. check rxq map after dryrun.
        port1 = pmd1.find_port_by_name('virtport1')
        port2 = pmd1.find_port_by_name('virtport2')
        port3 = pmd1.find_port_by_name('virtport3')
        port1reb = pmd2.find_port_by_name('virtport1')
        port3reb = pmd2.find_port_by_name('virtport3')
        # 3.a rxqp2 remains in pmd1
        self.assertEqual(port2.rxq_rebalanced, {})
        self.assertEqual(port2.find_rxq_by_id(0).pmd.id, pmd1.id)
        # 3.b rxqp1 moves from pmd1 to pmd2
        self.assertEqual(port1.rxq_rebalanced[0], pmd2.id)
        self.assertIsNone(port1.find_rxq_by_id(0))
        # 3.b.0 and dry-run did not break original pinning.
        rxqp1reb = port1reb.find_rxq_by_id(0)
        self.assertEqual(rxqp1reb.pmd.id, pmd1.id)
        # 3.c rxqp3 moves from pmd1 to pmd2
        self.assertEqual(port3.rxq_rebalanced[0], pmd2.id)
        self.assertIsNone(port3.find_rxq_by_id(0))
        # 3.c.0 and dry-run did not break original pinning.
        rxqp3reb = port3reb.find_rxq_by_id(0)
        self.assertEqual(rxqp3reb.pmd.id, pmd1.id)
        # 3.d no port moved into numa 1
        self.assertEqual(pmd3.count_rxq(), 0)
        self.assertEqual(pmd4.count_rxq(), 0)

        # del port object from pmd.
        # TODO: create fx_ post deletion routine for clean up
        pmd1.del_port('virtport1')
        pmd1.del_port('virtport2')


class TestRebalDryrunIQ_OnePmd(TestRebalDryrun_OnePmd):
    """
    Test rebalance for one or more rxq handled by one pmd.
    """

    rebalance_dryrun = dataif.rebalance_dryrun_by_iq
    pmd_map = dict()
    core_id = 0


class TestRebalDryrunIQ_TwoPmd(TestRebalDryrun_TwoPmd):
    """
    Test rebalance for one or more rxq handled by two pmds.
    """

    rebalance_dryrun = dataif.rebalance_dryrun_by_iq
    pmd_map = dict()
    core1_id = 0
    core2_id = 1

    @pytest.mark.skip(reason="not applicable")
    def test_four_1rxq_lnuma(self, mock_open):
        ...

    @pytest.mark.skip(reason="not applicable")
    def test_four_1rxq_skip_lnuma(self, mock_open):
        ...

    @pytest.mark.skip(reason="not applicable")
    def test_two_1p2rxq_lnuma(self, mock_open):
        ...

    @pytest.mark.skip(reason="not applicable")
    def test_two_1p2rxq_lnuma_norb(self, mock_open):
        ...


class TestRebalDryrunIQ_FourPmd(TestRebalDryrun_FourPmd):
    """
    Test rebalance for one or more rxq handled by four pmds.
    """

    rebalance_dryrun = dataif.rebalance_dryrun_by_iq
    pmd_map = dict()
    core1_id = 0
    core2_id = 1
    core3_id = 4
    core4_id = 5

    @pytest.mark.skip(reason="not applicable")
    def test_eight_1rxq_lnuma(self, mock_open):
        ...


class TestRebalDryrunIQ_FourPmd_Numa(TestRebalDryrun_FourPmd_Numa):
    """
    Test rebalance for one or more rxq handled by four pmds.
    """

    rebalance_dryrun = dataif.rebalance_dryrun_by_cyc
    pmd_map = dict()
    core1_id = 0
    core2_id = 1
    core3_id = 6
    core4_id = 7
