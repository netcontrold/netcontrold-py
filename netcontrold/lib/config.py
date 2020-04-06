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

# Maximum number of times to collect various stats from the vswitch
# before using them for rebalance calculation. Larger the value,
# better the estimation in dry run of this tool (before applying
# rebalanced pmds), at the same time larger the time taken to
# arrive at conclusion for rebalance, as decided by sample interval.
# Input param "--sample-interval" option available.
ncd_samples_max = 6

# Minimum improvement in the pmd load values calculated in
# each sampling iteration. This value judges on whether all the PMDs
# have arrived at a balanced equilibrium. Smaller the value, better
# the load balance in all PMDs,  at the same time larger the time
# taken by tool arrive at conclusion for rebalance.
ncd_pmd_load_improve_min = 25

# Minimum per core load threshold to trigger rebalance, if the pmd load
# is above this threshold.
ncd_pmd_core_threshold = 95

# Minimum interval for vswitch to reach steady state, following
# pmd reconfiguration.
ncd_vsw_wait_min = 0

# Store location for the logs created and its maximum size.
ncd_log_file = "/var/log/netcontrold/ncd.log"
ncd_log_max_KB = 1024
ncd_log_max_backup_n = 1

# Minimum threshold (in ppm) for packet drop to call back trace actions.
ncd_cb_pktdrop_min = 10000

# Unix socket file
ncd_socket = "/var/run/netcontrold/ncd_ctrld.sock"
