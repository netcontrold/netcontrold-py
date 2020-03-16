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
from netcontrold.lib.error import NcdException, ObjConsistencyExc


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
