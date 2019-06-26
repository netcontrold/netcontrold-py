#
#  Copyright (c) 2019 Red Hat, Inc.
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

__all__ = ['exec_host_command',
           'variance',
           ]

# Import standard modules
import subprocess

def exec_host_command(cmd):
    try:
        ret = subprocess.check_output(cmd.split())
    except subprocess.CalledProcessError, e:
        print ("Unable to execute command %s: %s" %(cmd, e))
        return 1
    return ret

def variance(_list):
    mean = sum(_list) / len(_list)
    return sum((item - mean) ** 2 for item in _list) / len(_list)
