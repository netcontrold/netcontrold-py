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

_BASIC_CPU_INFO = """
processor	: 0
"""


class TestUtil(TestCase):

    @mock.patch('netcontrold.lib.util.open')
    def test_cpuinfo_basic(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=_BASIC_CPU_INFO).return_value
        ]
        out = util.cpuinfo()
        expected = [{'processor': '0'}]
        self.assertEqual(out, expected)
