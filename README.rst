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
 * Debug mode (call back user script in the event of heavy packet drops)
 * Enable/disable its modes in run time.

Usage
-----
ncd_ctl is CLI to control Netcontrold daemon process.
..
..
  ncd_ctl [start/stop/restart/status/rebalance-on/rebalance-off/debug-on/debug-off]
  