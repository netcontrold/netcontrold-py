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


class TestRebalDryrunRR_OnePmd(TestCase):
    """
    Test rebalance for one or more rxq handled by one pmd.
    """

    pmd_map = dict()
    core_id = 0

    # setup test environment
    def setUp(self):
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
        n_reb_rxq = dataif.rebalance_dryrun_rr(self.pmd_map)

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
        n_reb_rxq = dataif.rebalance_dryrun_rr(self.pmd_map)

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
    fx_port2 = pmd1.add_port(port2_name)
    fx_port2.numa_id = pmd1.numa_id
    fx_port3 = pmd2.add_port(port3_name)
    fx_port3.numa_id = pmd2.numa_id
    fx_port4 = pmd2.add_port(port4_name)
    fx_port4.numa_id = pmd2.numa_id

    # add a dummy rxq into port.
    fx_p1rxq = fx_port1.add_rxq(0)
    fx_p1rxq.pmd = pmd1
    fx_p2rxq = fx_port2.add_rxq(0)
    fx_p2rxq.pmd = pmd1
    fx_p3rxq = fx_port3.add_rxq(0)
    fx_p3rxq.pmd = pmd2
    fx_p4rxq = fx_port4.add_rxq(0)
    fx_p4rxq.pmd = pmd2

    # add some cpu consumption for these rxqs.
    # order of rxqs based on cpu consumption: rxqp3,rxqp1,rxqp2,rxqp4
    for i in range(0, config.ncd_samples_max):
        fx_p1rxq.cpu_cyc[i] = (3000 + (100 * i))
        fx_p2rxq.cpu_cyc[i] = (2000 + (200 * i))
        fx_p3rxq.cpu_cyc[i] = (4000 + (300 * i))
        fx_p4rxq.cpu_cyc[i] = (1000 + (400 * i))


class TestRebalDryrunRR_TwoPmd(TestCase):
    """
    Test rebalance for one or more rxq handled by twp pmds.
    """

    pmd_map = dict()
    core1_id = 0
    core2_id = 1

    # setup test environment
    def setUp(self):
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
        n_reb_rxq = dataif.rebalance_dryrun_rr(self.pmd_map)

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
    #   1. rxqp1(pmd1)
    #      rxqp2(pmd1) -NOREB-> rxqp2(pmd1)
    #        -  (pmd2)
    #
    #   2. rxqp1(pmd1) --+
    #      rxqp2(pmd1)    \    rxqp2(pmd1)
    #        -  (pmd2)     +-> rxqp1(reb_pmd2)
    #
    @mock.patch('netcontrold.lib.util.open')
    def test_two_rxq_lnuma(self, mock_open):
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
        n_reb_rxq = dataif.rebalance_dryrun_rr(self.pmd_map)

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
    #   With two threads from same numa, where each pmd thread is handling
    #   two single-queued ports. check whether rebalance is performed.
    #   Scope is to check if rxq frpm a pmd which was a rebalancing pmd
    #   before is assigned other pmd successfully.
    #
    #   order of rxqs based on cpu consumption: rxqp3,rxqp1,rxqp2,rxqp4
    #   order of pmds for rebalance dryrun: pmd1,pmd2,pmd2,pmd1
    #
    #   1. rxqp1(pmd1)    +-> rxqp3(reb_pmd1)
    #      rxqp2(pmd1)   /
    #      rxqp3(pmd2) -+
    #      rxqp4(pmd2)
    #
    #   2. rxqp1(pmd1) -+     rxqp3(reb_pmd1)
    #      rxqp2(pmd1)   \
    #      rxqp3(pmd2)    +-> rxqp1(reb_pmd2)
    #      rxqp4(pmd2)
    @mock.patch('netcontrold.lib.util.open')
    def test_four_rxq_lnuma(self, mock_open):
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
        n_reb_rxq = dataif.rebalance_dryrun_rr(self.pmd_map)

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
        port3 = pmd2.find_port_by_name('virtport3')
        self.assertEqual(port1.rxq_rebalanced[0], pmd2.id)
        self.assertEqual(port3.rxq_rebalanced[0], pmd1.id)

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
    def test_one_rxq_rnuma(self):
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
        n_reb_rxq = dataif.rebalance_dryrun_rr(self.pmd_map)

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
