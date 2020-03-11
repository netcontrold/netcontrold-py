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

    def setUp(self):
        self.port1 = dataif.Port("port1")

    def test_port_add_rxq_1(self):
        rxq1 = self.port1.add_rxq(1)
        self.assertEqual(self.port1.find_rxq_by_id(1), rxq1)

    def test_port_add_rxq_2(self):
        rxq2 = self.port1.add_rxq(2)
        with self.assertRaises(ObjConsistencyExc):
            self.port1.add_rxq(2)


class TestDataif_del_rxq(TestCase):

    def setUp(self):
        self.port1 = dataif.Port("port1")
        self.rxq1 = self.port1.add_rxq(1)
        self.rxq2 = self.port1.add_rxq(2)

    def test_port_del_rxq_1(self):
        self.port1.del_rxq(1)
        self.assertEqual(self.port1.find_rxq_by_id(1), None)

    def test_port_del_rxq_2(self):
        with self.assertRaises(ObjConsistencyExc):
            self.port1.del_rxq(3)


class TestDataif_find_rxq(TestCase):

    def setUp(self):
        self.port1 = dataif.Port("port1")
        self.rxq1 = self.port1.add_rxq(1)
        self.rxq2 = self.port1.add_rxq(2)

    def test_port_find_rxq_1(self):
        self.assertEqual(self.port1.find_rxq_by_id(1), self.rxq1)

    def test_port_find_rxq_2(self):
        self.assertEqual(self.port1.find_rxq_by_id(3), None)
