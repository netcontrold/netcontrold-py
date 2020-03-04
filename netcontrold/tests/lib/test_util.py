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

from netcontrold.lib import util

# Create dumy file to fool function

_BASIC_CPU_INFO_Negative = """
core id         : 0
processor       : 0
physical id     : 0
core id         : 1
processor       : 1
physical id     : 0
"""

_BASIC_CPU_INFO_Positive = """
processor       : 0
core id         : 0
physical id     : 0

processor       : 1
core id         : 0
physical id     : 0

processor       : 2
core id         : 1
physical id     : 0

processor       : 3
core id         : 1
physical id     : 0
"""

_BASIC_CPU_INFO_Processorid_NULL = """
processor       :
physical id     : 0
core id         : 1
processor       :
physical id     : 0
"""


_BASIC_CPU_INFO_coreid_NULL = """
processor       : 0
physical id     : 0
core id         :
processor       : 1
physical id     : 0
core id         :
"""


_BASIC_CPU_INFO_physical_NULL = """
processor       :
physical id     : 0
core id         : 1
processor       :
physical id     : 0
"""


class TestUtil_cpuinfo(TestCase):

    @mock.patch('netcontrold.lib.util.open')
    def test_cpuinfo_Negative(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=_BASIC_CPU_INFO_Negative).return_value
        ]
        self.assertRaises(ValueError, util.cpuinfo)

    @mock.patch('netcontrold.lib.util.open')
    def test_cpuinfo_Processorid(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(
                read_data=_BASIC_CPU_INFO_Processorid_NULL).return_value]
        self.assertRaises(ValueError, util.cpuinfo)

    @mock.patch('netcontrold.lib.util.open')
    def test_cpuinfo_coreid(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(
                read_data=_BASIC_CPU_INFO_coreid_NULL).return_value]
        self.assertRaises(ValueError, util.cpuinfo)

    @mock.patch('netcontrold.lib.util.open')
    def test_cpuinfo_physical(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(
                read_data=_BASIC_CPU_INFO_physical_NULL).return_value]
        self.assertRaises(ValueError, util.cpuinfo)

    @mock.patch('netcontrold.lib.util.open')
    def test_cpuinfo_basic(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=_BASIC_CPU_INFO_Positive).return_value
        ]
        expected = [{'processor': '0', 'core id': '0', 'physical id': '0'},
                    {'processor': '1', 'core id': '0', 'physical id': '0'},
                    {'processor': '2', 'core id': '1', 'physical id': '0'},
                    {'processor': '3', 'core id': '1', 'physical id': '0'}]
        out = util.cpuinfo()
        self.assertEqual(out, expected)

    @mock.patch('netcontrold.lib.util.open')
    def test_cpuinfo_is_empty(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data="").return_value
        ]
        out = util.cpuinfo()
        expected = []
        self.assertEqual(out, expected)


class TestUtil_numa_cpu_map(TestCase):

    @mock.patch('netcontrold.lib.util.open')
    def test_numa_cpu_map_Negative(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=_BASIC_CPU_INFO_Negative).return_value
        ]
        self.assertRaises(ValueError, util.numa_cpu_map)

    @mock.patch('netcontrold.lib.util.open')
    def test_numa_cpu_map_Processorid(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(
                read_data=_BASIC_CPU_INFO_Processorid_NULL).return_value]
        self.assertRaises(ValueError, util.numa_cpu_map)

    @mock.patch('netcontrold.lib.util.open')
    def test_numa_cpu_map_coreid(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(
                read_data=_BASIC_CPU_INFO_coreid_NULL).return_value]
        self.assertRaises(ValueError, util.numa_cpu_map)

    @mock.patch('netcontrold.lib.util.open')
    def test_numa_cpu_map_physical(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(
                read_data=_BASIC_CPU_INFO_physical_NULL).return_value]
        self.assertRaises(ValueError, util.numa_cpu_map)

    @mock.patch('netcontrold.lib.util.open')
    def test_numa_cpu_map_basic(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=_BASIC_CPU_INFO_Positive).return_value
        ]
        out = util.numa_cpu_map()
        expected = {0: {0: [0, 1], 1: [2, 3]}}
        self.assertEqual(out, expected)


class TestUtil_rr_cpu_in_numa(TestCase):

    @mock.patch('netcontrold.lib.util.open')
    def test_rr_cpu_in_numa_Negative(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=_BASIC_CPU_INFO_Negative).return_value
        ]
        self.assertRaises(ValueError, util.rr_cpu_in_numa)

    @mock.patch('netcontrold.lib.util.open')
    def test_rr_cpu_in_numa_Processorid(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(
                read_data=_BASIC_CPU_INFO_Processorid_NULL).return_value]
        self.assertRaises(ValueError, util.rr_cpu_in_numa)

    @mock.patch('netcontrold.lib.util.open')
    def test_rr_cpu_in_numa_basic(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=_BASIC_CPU_INFO_Positive).return_value
        ]
        out = util.rr_cpu_in_numa()
        expected = [0, 1, 2, 3]
        self.assertEqual(out, expected)
