==============================
Overview of Netcontrold daemon
==============================

What is netcontrold ?
---------------------

Netcontrold is Network control daemon, which is used to *monitor* and *control* various network events associated with data and control plane processing in a vSwitch (eg OpenvSwitch). 
The idea is to infer from stats (and events) that vSwitch will generate, during the period when network performance is dropping (due to spurious packet drops, latency jitter and packet re-ordering) and control(in other words to react) to these events by generating sequence of actions in compliance with the format that vSwitch would accept and respond.
For an instance, in case of OpenvSwitch as vSwitch, when a PMD thread is unhealthy (eg overloaded than its compute capacity) and throughput drops between VNFs (eg packet drops in TX), this daemon will understand the overall state of PMD and react by re-balancing PMD threads.
If needed, it will also try to isolate busy (and healthy) PMD thread from other threads, based on traffic conditions observed in it.

How to use netcontrold ?
------------------------

Netcontrold is a daemon process, which spawns few of its helper threads in parallel and accomplishes its objective. It's launch is simple as you run below command:

	python ncd_src/ncd.py [optional_params]
	
	optional_params:
	
		-h|--help 				to show this help message.
		-t|--timeout <N_sec>	to stop netcontrold itself after N sec. 
		-c|--control_count <N>  to control vSwitch "N" times and stop itself.



