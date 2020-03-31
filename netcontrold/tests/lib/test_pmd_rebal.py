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
physical id     : 0

processor       : 3
core id         : 1
physical id     : 0

processor       : 4
core id         : 0
physical id     : 0

processor       : 5
core id         : 1
physical id     : 0

processor       : 6
core id         : 0
physical id     : 0

processor       : 7
core id         : 1
physical id     : 0
"""


class TestRebalDryrun_OnePmd(TestCase):
    """
    Test rebalance for one or more rxq handled by one pmd.
    """

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
            fx_pmd.idle_cpu_cyc[i] = (1000 + (100 * i))
            fx_pmd.proc_cpu_cyc[i] = (5000 + (500 * i))
            fx_pmd.rx_cyc[i] = (10000 + (100 * i))

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
            fx_rxq.cpu_cyc[i] = (1000 + (100 * i))

        # test dryrun
        n_reb_rxq = dataif.rebalance_dryrun_by_cyc(self.pmd_map)

        # validate results
        # 1. no rxqs be rebalanced.
        self.assertEqual(n_reb_rxq, 0)

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
                fx_rxq.cpu_cyc[i] = (1000 + (100 * i))

        # test dryrun
        n_reb_rxq = dataif.rebalance_dryrun_by_cyc(self.pmd_map)

        # validate results
        # 1. no rxqs be rebalanced.
        self.assertEqual(n_reb_rxq, 0)

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
        fx_p1rxq.cpu_cyc[i] = (1000 + (100 * i))
        fx_p2rxq.cpu_cyc[i] = (2000 + (200 * i))


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
        fx_p1rxq.cpu_cyc[i] = (1000 + (100 * i))
        fx_p2rxq.cpu_cyc[i] = (2000 + (200 * i))


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
        fx_p1rxq.cpu_cyc[i] = (4000 + (400 * i))
        fx_p2rxq.cpu_cyc[i] = (3000 + (300 * i))
        fx_p3rxq.cpu_cyc[i] = (2000 + (200 * i))
        fx_p4rxq.cpu_cyc[i] = (1000 + (100 * i))

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
        fx_p1rxq1.cpu_cyc[i] = (4000 + (400 * i))
        fx_p2rxq2.cpu_cyc[i] = (3000 + (300 * i))
        fx_p2rxq1.cpu_cyc[i] = (2000 + (200 * i))
        fx_p1rxq2.cpu_cyc[i] = (1000 + (100 * i))


class TestRebalDryrun_TwoPmd(TestCase):
    """
    Test rebalance for one or more rxq handled by twp pmds.
    """

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
            fx_pmd1.idle_cpu_cyc[i] = (1 + (1 * i))
            fx_pmd1.proc_cpu_cyc[i] = (900 + (90 * i))
            fx_pmd1.rx_cyc[i] = (1000 + (100 * i))

        for i in range(0, config.ncd_samples_max):
            fx_pmd2.idle_cpu_cyc[i] = (1000 + (100 * i))
            fx_pmd2.proc_cpu_cyc[i] = (9500 + (950 * i))
            fx_pmd2.rx_cyc[i] = (10000 + (100 * i))

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
        n_reb_rxq = dataif.rebalance_dryrun_by_cyc(self.pmd_map)

        # validate results
        # 1. all two rxqs be rebalanced.
        self.assertEqual(n_reb_rxq, 0, "no rebalance expected")
        # 2. each pmd is not updated.
        self.assertEqual(
            (pmd_map[self.core1_id] == pmd1), True)
        self.assertEqual(
            (pmd_map[self.core2_id] == pmd2), True)

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

        # create rxq
        fx_2pmd_one_empty(self)

        # update pmd load values
        dataif.update_pmd_load(self.pmd_map)

        # copy original pmd objects
        pmd_map = copy.deepcopy(self.pmd_map)

        # test dryrun
        n_reb_rxq = dataif.rebalance_dryrun_by_cyc(self.pmd_map)

        # validate results
        # 1. all two rxqs be rebalanced.
        self.assertEqual(n_reb_rxq, 2, "two rxqs to be rebalanced")
        # 2. each pmd is updated.
        self.assertEqual(
            (pmd_map[self.core1_id] != pmd1), True)
        self.assertEqual(
            (pmd_map[self.core2_id] != pmd2), True)
        # 3. check rxq map after dryrun.
        port1 = pmd1.find_port_by_name('virtport1')
        port2 = pmd1.find_port_by_name('virtport2')
        # 3.a rxqp2 remains in pmd1
        self.assertEqual(port2.rxq_rebalanced, {})
        self.assertEqual(port2.find_rxq_by_id(0).pmd.id, pmd1.id)
        # 3.a rxqp1 moves into pmd2
        self.assertEqual(port1.rxq_rebalanced[0], pmd2.id)

        # del port object from pmd.
        # TODO: create fx_ post deletion routine for clean up
        pmd1.del_port('virtport1')
        pmd1.del_port('virtport2')

    # Test case:
    #   With two threads from same numa, where each pmd thread is  handling
    #   one queue from two-queued ports. check whether rebalance is performed.
    #   Scope is to check if rebalancing done on pmd that already has same
    #   port but different rxq.
    #
    #   order of rxqs based on cpu consumption: rxq1p1,rxq2p2,rxq1p2,rxq2p1
    #   order of pmds for rebalance dryrun: pmd1,pmd2,pmd2,pmd1
    #
    #   1. rxq1p1(pmd1) -NOREB-> rxq1p1(pmd1)
    #      rxq2p2(pmd2) -NOREB-> rxq2p2(pmd2)
    #      rxq1p2(pmd1)
    #      rxq2p1(pmd2)
    #
    #   2. rxq1p1(pmd1) -NOREB-> rxq1p1(pmd1)
    #      rxq2p2(pmd2) -NOREB-> rxq2p2(pmd2)
    #      rxq1p2(pmd1) --+--+-> rxq1p2(reb_pmd2)
    #      rxq2p1(pmd2) --+--+-> rxq2p1(reb_pmd1)
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

        # update pmd load values
        dataif.update_pmd_load(self.pmd_map)

        # copy original pmd objects
        pmd_map = copy.deepcopy(self.pmd_map)

        # test dryrun
        n_reb_rxq = dataif.rebalance_dryrun_by_cyc(self.pmd_map)

        # validate results
        # 1. all four rxqs be rebalanced.
        self.assertEqual(n_reb_rxq, 4, "four rxqs to be rebalanced")
        # 2. each pmd is updated.
        self.assertEqual(
            (pmd_map[self.core1_id] != pmd1), True)
        self.assertEqual(
            (pmd_map[self.core2_id] != pmd2), True)
        # 3. check rxq map after dryrun.
        port11 = pmd1.find_port_by_name('virtport1')
        port12 = pmd2.find_port_by_name('virtport1')
        port21 = pmd1.find_port_by_name('virtport2')
        port22 = pmd2.find_port_by_name('virtport2')
        self.assertEqual(port11.rxq_rebalanced, {})
        self.assertEqual(port22.rxq_rebalanced, {})
        self.assertEqual(port21.rxq_rebalanced[0], pmd2.id)
        self.assertEqual(port12.rxq_rebalanced[1], pmd1.id)

        # del port object from pmd.
        # TODO: create fx_ post deletion routine for clean up
        pmd1.del_port('virtport1')
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
        n_reb_rxq = dataif.rebalance_dryrun_by_cyc(self.pmd_map)

        # validate results
        # 1. all four rxqs be rebalanced.
        self.assertEqual(n_reb_rxq, 4, "four rxqs to be rebalanced")
        # 2. each pmd is updated.
        self.assertEqual(
            (pmd_map[self.core1_id] != pmd1), True)
        self.assertEqual(
            (pmd_map[self.core2_id] != pmd2), True)
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
    #   With two threads from pmd of one numa, rebalance should be
    #   skipped even though a pmd from other numa is available and
    #   empty.
    #   Scope is to check if nonlocal pmd continues be empty after dryrun.
    #
    #   order of rxqs based on cpu consumption: rxqp2,rxqp1
    #
    #   1. rxqp1(pmd1N0)
    #      rxqp2(pmd1N0) -NOREB-> rxqp2(pmd1N0)
    #        -  (pmd2N1)
    #
    #   2. rxqp1(pmd1N0) -NOREB-> rxqp1(pmd1N0)
    #      rxqp2(pmd1N0)          rxqp2(pmd1N0)
    #        -  (pmd2N1)
    #
    def test_two_1rxq_rnuma(self):
        # set different numa for pmds
        pmd1 = self.pmd_map[self.core1_id]
        pmd2 = self.pmd_map[self.core2_id]
        pmd1.numa_id = 0
        pmd2.numa_id = 1

        # create rxq
        fx_2pmd_one_empty(self)

        # update pmd load values
        dataif.update_pmd_load(self.pmd_map)

        # copy original pmd objects
        pmd_map = copy.deepcopy(self.pmd_map)

        # test dryrun
        n_reb_rxq = dataif.rebalance_dryrun_by_cyc(self.pmd_map)

        # validate results
        # 1. no rxq be rebalanced.
        self.assertEqual(n_reb_rxq, 2, "rebalance only in local numa expected")
        # 2. no pmd is updated.
        self.assertEqual(
            (pmd_map[self.core1_id] == pmd1), True)
        self.assertEqual(
            (pmd_map[self.core2_id] == pmd2), True)
        # 3. check rxq map after dryrun.
        port1 = pmd1.find_port_by_name('virtport1')
        port2 = pmd1.find_port_by_name('virtport2')
        # 3.a rxqp2 remains in pmd1
        self.assertEqual(port2.rxq_rebalanced, {})
        self.assertEqual(port2.find_rxq_by_id(0).pmd.id, pmd1.id)
        # 3.a rxqp1 moves into pmd2
        self.assertEqual(port1.rxq_rebalanced, {})
        self.assertEqual(port1.find_rxq_by_id(0).pmd.id, pmd1.id)

        # del port object from pmd.
        # TODO: create fx_ post deletion routine for clean up
        pmd1.del_port('virtport1')
        pmd1.del_port('virtport2')

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
        fx_p1rxq.cpu_cyc[i] = (8000 + (800 * i))
        fx_p2rxq.cpu_cyc[i] = (7000 + (700 * i))
        fx_p3rxq.cpu_cyc[i] = (6000 + (600 * i))
        fx_p4rxq.cpu_cyc[i] = (5000 + (500 * i))
        fx_p5rxq.cpu_cyc[i] = (4000 + (400 * i))
        fx_p6rxq.cpu_cyc[i] = (3000 + (300 * i))
        fx_p7rxq.cpu_cyc[i] = (2000 + (200 * i))
        fx_p8rxq.cpu_cyc[i] = (1000 + (100 * i))


class TestRebalDryrun_FourPmd(TestCase):
    """
    Test rebalance for one or more rxq handled by twp pmds.
    """

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
            fx_pmd1.idle_cpu_cyc[i] = (1 + (1 * i))
            fx_pmd1.proc_cpu_cyc[i] = (900 + (90 * i))
            fx_pmd1.rx_cyc[i] = (1000 + (100 * i))

        for i in range(0, config.ncd_samples_max):
            fx_pmd2.idle_cpu_cyc[i] = (1000 + (100 * i))
            fx_pmd2.proc_cpu_cyc[i] = (9500 + (950 * i))
            fx_pmd2.rx_cyc[i] = (10000 + (100 * i))

        for i in range(0, config.ncd_samples_max):
            fx_pmd3.idle_cpu_cyc[i] = (2000 + (200 * i))
            fx_pmd3.proc_cpu_cyc[i] = (29500 + (2950 * i))
            fx_pmd3.rx_cyc[i] = (20000 + (200 * i))

        for i in range(0, config.ncd_samples_max):
            fx_pmd4.idle_cpu_cyc[i] = (3000 + (100 * i))
            fx_pmd4.proc_cpu_cyc[i] = (39500 + (3950 * i))
            fx_pmd4.rx_cyc[i] = (30000 + (100 * i))

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
        n_reb_rxq = dataif.rebalance_dryrun_by_cyc(self.pmd_map)

        # validate results
        # 1. all four rxqs be rebalanced.
        self.assertEqual(n_reb_rxq, 8, "eight rxqs to be rebalanced")
        # 2. each pmd is updated.
        self.assertEqual(
            (pmd_map[self.core1_id] != pmd1), True)
        self.assertEqual(
            (pmd_map[self.core2_id] != pmd2), True)
        self.assertEqual(
            (pmd_map[self.core3_id] != pmd3), True)
        self.assertEqual(
            (pmd_map[self.core4_id] != pmd4), True)
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

# TODO:
# We could reuse cycles based test as above for testing any rebalance
# logic, meaning except for desired dryrun results, setup and test inputs
# remain same.


class TestRebalDryrunIQ_OnePmd(TestCase):
    """
    Test rebalance for one or more rxq handled by one pmd.
    """

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
            fx_pmd.idle_cpu_cyc[i] = (1000 + (100 * i))
            fx_pmd.proc_cpu_cyc[i] = (5000 + (500 * i))
            fx_pmd.rx_cyc[i] = (10000 + (100 * i))

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
            fx_rxq.cpu_cyc[i] = (1000 + (100 * i))

        n_reb_rxq = dataif.rebalance_dryrun_by_iq(self.pmd_map)

        self.assertEqual(n_reb_rxq, 0)

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
                fx_rxq.cpu_cyc[i] = (1000 + (100 * i))

        n_reb_rxq = dataif.rebalance_dryrun_by_iq(self.pmd_map)

        self.assertEqual(n_reb_rxq, 0)

        for port_name in ('virtport1', 'virtport2', 'virtport3'):
            pmd.del_port(port_name)


class TestRebalDryrunIQ_TwoPmd(TestCase):
    """
    Test rebalance for one or more rxq handled by twp pmds.
    """

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
            fx_pmd1.idle_cpu_cyc[i] = (1 + (1 * i))
            fx_pmd1.proc_cpu_cyc[i] = (900 + (90 * i))
            fx_pmd1.rx_cyc[i] = (1000 + (100 * i))

        for i in range(0, config.ncd_samples_max):
            fx_pmd2.idle_cpu_cyc[i] = (1000 + (100 * i))
            fx_pmd2.proc_cpu_cyc[i] = (9500 + (950 * i))
            fx_pmd2.rx_cyc[i] = (10000 + (100 * i))

        self.pmd_map[self.core1_id] = fx_pmd1
        self.pmd_map[self.core2_id] = fx_pmd2
        return

    # Test case:
    #   With two threads from same numa, each handling only one single-queued
    #   port, check whether rebalance is skipped.
    def test_one_rxq_lnuma(self):
        # set different numa for pmds
        pmd1 = self.pmd_map[self.core1_id]
        pmd2 = self.pmd_map[self.core2_id]

        pmd1.numa_id = 0
        pmd2.numa_id = 0

        fx_2pmd_each_1rxq(self)

        dataif.update_pmd_load(self.pmd_map)
        pmd_map = copy.deepcopy(self.pmd_map)
        n_reb_rxq = dataif.rebalance_dryrun_by_iq(self.pmd_map)

        self.assertEqual(n_reb_rxq, 0, "no rebalance expected")
        self.assertEqual(
            (pmd_map[self.core1_id] == self.pmd_map[self.core1_id]), True)
        self.assertEqual(
            (pmd_map[self.core2_id] == self.pmd_map[self.core2_id]), True)

        # del port object from pmd.
        # TODO: create fx_ post deletion routine for clean up
        pmd1.del_port('virtport1')
        pmd2.del_port('virtport2')

    # Test case:
    #   With two threads from same numa, where one pmd thread is handling
    #   two single-queued ports, while the other is doing nothing,
    #   check whether rebalance is performed.
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

        fx_2pmd_one_empty(self)

        dataif.update_pmd_load(self.pmd_map)
        pmd_map = copy.deepcopy(self.pmd_map)
        n_reb_rxq = dataif.rebalance_dryrun_by_iq(self.pmd_map)

        self.assertEqual(n_reb_rxq, 1, "one rxq to be rebalanced")
        self.assertEqual(
            (pmd_map[self.core1_id] != self.pmd_map[self.core1_id]), True)
        self.assertEqual(
            (pmd_map[self.core2_id] != self.pmd_map[self.core2_id]), True)

        # del port object from pmd.
        # TODO: create fx_ post deletion routine for clean up
        pmd1.del_port('virtport1')
        pmd1.del_port('virtport2')

    # Test case:
    #   With two threads from different numa, each handling one single-queued
    #   port, check rebalance is skipped.
    def test_one_rxq_rnuma(self):
        # set different numa for pmds
        pmd1 = self.pmd_map[self.core1_id]
        pmd2 = self.pmd_map[self.core2_id]

        pmd1.numa_id = 0
        pmd2.numa_id = 1

        fx_2pmd_each_1rxq(self)

        dataif.update_pmd_load(self.pmd_map)
        pmd_map = copy.deepcopy(self.pmd_map)
        n_reb_rxq = dataif.rebalance_dryrun_by_iq(self.pmd_map)

        self.assertEqual(n_reb_rxq, 0, "no rebalance expected")
        self.assertEqual(
            (pmd_map[self.core1_id] == self.pmd_map[self.core1_id]), True)
        self.assertEqual(
            (pmd_map[self.core2_id] == self.pmd_map[self.core2_id]), True)

        # del port object from pmd.
        # TODO: create fx_ post deletion routine for clean up
        pmd1.del_port('virtport1')
        pmd2.del_port('virtport2')
