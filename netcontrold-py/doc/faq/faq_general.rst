== == == == == == == == ==
FAQ of Netcontrold
== == == == == == == == ==

1. Can this tool be used with openvswitch - 2.6 ?
-----------------------------------------------
Not with current version of this code.
Why ?. This tool depends on cpu usage of every rxq as pmd - rxq - show command reports. This stat is not available in openvswitch - 2.6. Hence, this tool can not know cpu usage by rxqs.

2. Is this tool a daemon ?
--------------------------
Yes. It runs endlessly until it is killed. If needed, we develop stop / start commands externally, but not needed with the current features it support.

3. Are there additional resources created / consumed by this tool in the Open_vswitch ?
-------------------------------------------------------------------------------------
No. Netcontrold runs entirely as a standalone monitoring tool, but in the context of the Open vSwitch. There is no overhead created by this tool in the datapath of vswitch.

4.  What is the maximum count of samples this tool collects ?
-------------------------------------------------------------
At the maximum before a dry - run is performed(when pmds are unbalanced), “ncd_samples_max” amount of samples are collected for rebalance estimation and it is “6” by default. However, its frequency of sampling Is configurable with user option “- -sample - interval”, which is 10 sec by default. This is to align sampling interval with that of OVS internal counters, so that ovs - appctl(rxq - show) output that this tool depends on is in sync with real amount of packets.

5.  What is the rebalance interval used for ?
---------------------------------------------
As this tool triggers collection of multiple iterations of samples and their dry - run for rebalance optimization, at some point we would need the tool to apply appropriate command in vswitch to bring estimation alive. Sometimes, it might be annoying to often rebalance the vswitch when we know there is breathing time for vswitch to reach steady state by nature of incoming traffic. With rebalance interval(default or “--rebalance - interval”), the tool will wait for this interval to elapse before applying new rebalance state in the vswitch.

6. What will happen to existing PMDs once the Netcontrold takes control over them ?
-----------------------------------------------------------------------------------
When manually pinning rxqs as netcontrold does, existing PMDs become isolated meaning that, Open vswitch will not use them for non - isolated RXQs created in the future. To avoid all pmds isolated and hence blocking new ports in the datapath, netcontrold leaves one pmd in every NUMA as non - isolated pmd, at the same time it ensures that, newer rxq assignment is actually applied across all the pmds. Hence, no pmd is left unused.
