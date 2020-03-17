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
from netcontrold.lib import dataif
from netcontrold.lib.error import ObjConsistencyExc


class TestDataif_add_rxq(TestCase):
    """
    Test for adding rxq to an existing port.
    """

    # setup test environment
    def setUp(self):
        # create one port object
        self.port1 = dataif.Port("port1")

        # add rxq to port object
        self.rxq2 = self.port1.add_rxq(2)

    # Test case:
    #   adding rxq to an existing port and checking whether
    #   it is added or not.
    def test_port_add_rxq_1(self):
        # add rxq to port object
        rxq1 = self.port1.add_rxq(1)

        self.assertEqual(self.port1.find_rxq_by_id(1), rxq1)

    # Test case:
    #   adding already existing rxq to port and checking whether
    #   addition is skipped.
    def test_port_add_rxq_2(self):
        self.assertRaises(ObjConsistencyExc, self.port1.add_rxq, 2)


class TestDataif_del_rxq(TestCase):
    """
    Test for deleting rxq from an existing port.
    """

    # setup test environment
    def setUp(self):
        # create one port object
        self.port1 = dataif.Port("port1")

        # add rxq1 to port object
        self.rxq1 = self.port1.add_rxq(1)

        # add rxq2 to port object
        self.rxq2 = self.port1.add_rxq(2)

    # Test case:
    #   deleting an existing rxq from a port and checking whether
    #   it is deleted or not.
    def test_port_del_rxq_1(self):
        # delete rxq1 from port object
        self.port1.del_rxq(1)

        self.assertEqual(self.port1.find_rxq_by_id(1), None)

    # Test case:
    #   deleting a non existing rxq from a port and checking whether
    #   deletion is skipped.
    def test_port_del_rxq_2(self):
        self.assertRaises(ObjConsistencyExc, self.port1.del_rxq, 3)


class TestDataif_find_rxq(TestCase):
    """
    Test for finding rxq from an existing port.
    """

    # setup test environment
    def setUp(self):
        # create one port object
        self.port1 = dataif.Port("port1")

        # add rxq1 to port object
        self.rxq1 = self.port1.add_rxq(1)

        # add rxq2 to port object
        self.rxq2 = self.port1.add_rxq(2)

    # Test case:
    #   finding an existing rxq from a port and checking whether
    #   it is found or not.
    def test_port_find_rxq_1(self):
        self.assertEqual(self.port1.find_rxq_by_id(1), self.rxq1)

    # Test case:
    #   finding a non existing rxq from a port and checking whether
    #   None is returned.
    def test_port_find_rxq_2(self):
        self.assertEqual(self.port1.find_rxq_by_id(3), None)


class TestDataif_add_port(TestCase):
    """
    Test for adding port to an existing pmd.
    """

    # setup for test environment
    def setUp(self):
        # create one pmd object
        self.pmd1 = dataif.Dataif_Pmd(1)

        # set pmd numa id
        self.pmd1.numa_id = 0

        dataif.make_dataif_port("port2")
        self.port2 = self.pmd1.add_port("port2")
        self.port2.numa_id = self.pmd1.numa_id

    # Test case:
    #   adding port to an existing pmd and checking whether
    #   it is added or not.
    def test_pmd_add_port_1(self):
        # create one port object
        dataif.make_dataif_port("port1")

        # add port object to pmd object
        port1 = self.pmd1.add_port("port1")

        # set port numa id
        port1.numa_id = self.pmd1.numa_id

        self.assertEqual(self.pmd1.find_port_by_name("port1"), port1)

    # Test case:
    #   adding existing port to a pmd and checking whether
    #   addition is skipped.
    def test_pmd_add_port_2(self):
        self.assertRaises(ObjConsistencyExc, self.pmd1.add_port, "port2")


class TestDataif_del_port(TestCase):
    """
    Test for deleting port from an existing pmd.
    """

    # setup for test environment
    def setUp(self):
        # create one pmd object
        self.pmd1 = dataif.Dataif_Pmd(1)

        # set pmd numa id
        self.pmd1.numa_id = 0

        # create port1 object
        dataif.make_dataif_port("port1")

        # add port object to pmd object
        self.port1 = self.pmd1.add_port("port1")

        # set port numa id
        self.port1.numa_id = self.pmd1.numa_id

        # create port3 object
        dataif.make_dataif_port("port3")

        # add port object to pmd object
        self.port3 = self.pmd1.add_port("port3")

        # set port numa id
        self.port3.numa_id = self.pmd1.numa_id

    # Test case:
    #   deleting an existing port from a pmd and checking whether
    #   it is deleted or not.
    def test_pmd_del_port_1(self):
        # delete port1 from pmd object
        self.pmd1.del_port("port1")

        self.assertEqual(self.pmd1.find_port_by_name("port1"), None)

    # Test case:
    #   deleting a non existing port from a pmd and checking whether
    #   deletion is skipped.
    def test_pmd_del_port_2(self):
        self.assertRaises(ObjConsistencyExc, self.pmd1.del_port, "port2")


class TestDataif_find_port(TestCase):
    """
    Test for finding port from an existing pmd.
    """

    # setup for test environment
    def setUp(self):
        # create one pmd object
        self.pmd1 = dataif.Dataif_Pmd(1)

        # set pmd numa id
        self.pmd1.numa_id = 0

        # create port1 object
        dataif.make_dataif_port("port1")

        # add port object to pmd object
        self.port1 = self.pmd1.add_port("port1")

        # set port numa id
        self.port1.numa_id = self.pmd1.numa_id

        # create port3 object
        dataif.make_dataif_port("port3")

        # add port object to pmd object
        self.port3 = self.pmd1.add_port("port3")

        # set port numa id
        self.port3.numa_id = self.pmd1.numa_id

    # Test case:
    #   finding an existing port from a pmd and checking whether
    #   it is found or not.
    def test_pmd_find_port_1(self):
        self.assertEqual(self.pmd1.find_port_by_name("port1"), self.port1)

    # Test case:
    #   finding a non existing port from a pmd and checking whether
    #   None is returned.
    def test_pmd_find_port_2(self):
        self.assertEqual(self.pmd1.find_port_by_name("port2"), None)


class TestDataif_count_rxq_empty(TestCase):
    """
    Test for counting rxq from an empty pmd.
    """

    # setup for test environment
    def setUp(self):
        # create one pmd object
        self.pmd1 = dataif.Dataif_Pmd(1)

        # set pmd numa id
        self.pmd1.numa_id = 0

        # create port1 object
        dataif.make_dataif_port("port1")

        # add port object to pmd object
        self.port1 = self.pmd1.add_port("port1")

        # set port numa id
        self.port1.numa_id = self.pmd1.numa_id

    # Test case:
    #   counting rxq from an empty pmd and checking whether
    #   no rxq is found.
    def test_pmd_count_rxq_1(self):
        self.assertEqual(self.pmd1.count_rxq(), 0)


class TestDataif_count_rxq(TestCase):
    """
    Test for counting rxq from an non empty pmd.
    """

    def setUp(self):
        # create one pmd object
        self.pmd1 = dataif.Dataif_Pmd(1)

        # set pmd numa id
        self.pmd1.numa_id = 0

        # create port1 object
        dataif.make_dataif_port("port1")

        # add port object to pmd object
        self.port1 = self.pmd1.add_port("port1")

        # set port numa id
        self.port1.numa_id = self.pmd1.numa_id

        # create port2 object
        dataif.make_dataif_port("port2")

        # add port object to pmd object
        self.port2 = self.pmd1.add_port("port2")

        # set port numa id
        self.port2.numa_id = self.pmd1.numa_id

        # add rxq1 to port1 object
        self.rxq1 = self.port1.add_rxq(1)

        # add rxq2 to port1 object
        self.rxq2 = self.port1.add_rxq(2)

        # add rxq1 to port2 object
        self.rxq1 = self.port2.add_rxq(1)

    # Test case:
    #   counting rxq from a non empty pmd and checking whether
    #   count is correct or not.
    def test_pmd_count_rxq_2(self):
        self.assertEqual(self.pmd1.count_rxq(), 3)

    # Test case:
    #   counting rxq from a non empty pmd after adding new rxq and checking
    #   whether count is correct.
    def test_pmd_count_rxq_3(self):
        # add rxq3 to port1 object
        _ = self.port1.add_rxq(3)

        # add rxq2 to port2 object
        _ = self.port2.add_rxq(2)

        self.assertEqual(self.pmd1.count_rxq(), 5)

    # Test case:
    #   counting rxq from a non empty pmd after deletion of rxq and checking
    #   whether count is correct
    def test_pmd_count_rxq_4(self):
        # delete rxq2 from port1 object
        self.port1.del_rxq(2)

        self.assertEqual(self.pmd1.count_rxq(), 2)
