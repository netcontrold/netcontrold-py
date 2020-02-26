|Generic badge|

.. |Generic badge| image:: https://github.com/netcontrold/netcontrold-py/workflows/CI/badge.svg?branch=master
   :target: https://github.com/netcontrold/netcontrold-py/workflows/CI/badge.svg?branch=master
   
Netcontrold
===========

Netcontrold optimizes Poll Mode Driver (PMD) threads in the OpenVSwitch for
a balanced load in the data plane processing. Netcontrold runs a daemon which
periodically monitors various stats in the OpenVSwitch for PMD threads, RXQ
of various ports that the PMD handles, analyze and apply appropriate load
balance instructions in the virtual switch to distribute data plane load
uniformly across PMD threads.

Netcontrold performs below key tasks after its daemon starts:

 * Collect stats from vswitch
 * Check if PMDs need rebalance dry-runs
 * Execute dry-run(s) on PMDs
 * If dry-run yields better load balance, instruct vswitch.

Features
--------

 * Rebalance mode (load balance on PMD threads)
 * Trace mode (call back user script in the event of heavy packet drops)
 * Enable/disable its modes in run time.

Usage
-----

+------------------------------+
|  usage: ncd_ctl CMD          |
|                              |
|  CMD in one of the below:    |
|  start                       |
|  stop                        |
|  restart                     |
|  status                      |
|  config show                 |
|  config rebalance <on|off>   |
|  config trace <on|off>       |
|  config verbose <on|off>     |
|  version                     |
+------------------------------+

