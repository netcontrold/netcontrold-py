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

from netcontrold.app import ncd
from netcontrold.lib import dataif
from netcontrold.lib import config

_BASIC_CPU_INFO = """
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

    @mock.patch('netcontrold.lib.dataif.open')
    def setUp(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=_BASIC_CPU_INFO).return_value
        ]
        self.pmd_map = dict()
        self.pmd_map = dataif.get_pmd_stats({})


#   @mock.patch('netcontrold.app.ncd.open')

    def test_numa_cpu_map_positive(self, mock_open):
        #       mock_open.side_effect = [
        #           mock.mock_open(read_data=_BASIC_CPU_INFO).return_value
     #       ]
        out = dataif.pmd_load_variance(self.pmd_map)
        expected = 65  # this is a random value just to check
        self.assertEqual(out, expected)
