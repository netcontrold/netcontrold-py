====================================
Implementation of Netcontrold daemon
====================================

Netcontrold daemon achieves controlling vSwitch for its better efficiency (load
balance, no packet drops, more network throughput) by monitoring and analyzing 
vSwitch events continuously. As vSwitch carries lot of stats in its various 
components and interfaces, parallelism is required by netcontrold to cater
its multi-functioning (collect stats, analyse and execute actions) ability.
Hence, it requires below helper threads, of which each individually performs 
its own tasks, and at the same time they exchange each other the processed stats
and internal control information.

  ncd_main_process
     |
     ncd_init
     |
     |_ ncd_collect <- Thread #1
     |_ ncd_analyse <- Thread #2
     |_ ncd_monitor <- Thread #3
     |
     ncd_shutdown

Various stats from vSwitch are abstracted into DataSrc derivatives (Eg PMD 
and RXq stats). Various interfaces for these stats are abstracted into DataIf 
derivatives (Eg PMD thread). These objects are exchanged between the above 
threads and each thread takes out what information it would need and execute 
corresponding actions that object would define.

	+-----------+-------------------------------------------------+
	| Thread    | ncd_collect                                     |
    +-----------+-------------------------------------------------+
    | Scope     | Collect stats from vSwitch.                     |
    +-----------+-------------------------------------------------+
    | Data_In   | DataSrc                                         |
    +-----------+-------------------------------------------------+
    | Operations| Create Dataif on every Datasrc                  |
    |           | Parse Datasrc and update Dataif                 |
    +-------------------------------------------------------------+
    | Data_Out  | hashmap[Dataif_Id:Dataif]                       |
    +-----------+-------------------------------------------------+
    

	+-----------+-------------------------------------------------+
	| Thread    | ncd_analyse                                     |
    +-----------+-------------------------------------------------+
    | Scope     | Analyse available stats and create control      |
    |           | actions.                                        |
    +-----------+-------------------------------------------------+
    | Data_In   | hashmap[Dataif_Id:Dataif]                       |
    +-----------+-------------------------------------------------+
    | Operations| Parse Datasrc for load on Dataif                |
    |           | Create CtrlAct and execute its *Algorithm (1)*. |
    |           | Refer Algorithm section for more details.       |
    +-------------------------------------------------------------+
    | Data_Out  | None                                            |
    +-----------+-------------------------------------------------+


	+-----------+-------------------------------------------------+
	| Thread    | ncd_monitor                                     |
    +-----------+-------------------------------------------------+
    | Scope     | Monitor vSwitch resources.                      |
    +-----------+-------------------------------------------------+
    | Data_In   | DataSrc                                         |
    |           | ResourcePhyCPU                                  |
    |           | CmdNCDStop                                      |                   
    |           | CmdNCDReset                                     |
    +-----------+-------------------------------------------------+
    | Operations| Parse Datasrc for load on Dataif                |
    |           | Parse ResourceCPU for interruptible tasks       |
    |           | Receive NCD stop/reset commands from user       |
    |           |                                                 |
    |           | Bail out Dataif if interruptible tasks too many&|
    |           |   Another free Dataif available                 |
    |           | Stop NCD if CmdNCDStop received                 |
    |           | Destroy DataIf and Datasrc if CmdNCDReset is    |
    |           |   received.                                     | 
    +-------------------------------------------------------------+
    | Data_Out  | None                                            |
    +-----------+-------------------------------------------------+
    
Algorithm (1):
-------------

Average processing cycles per packet (PCPP) in PMD stats reflect the ingress 
traffic rate on an average for that PMD. It is cumulative addition of traffic 
on all queues that PMD handled. Hence, it could be used to calculate the load 
of that PMD as below:

Terms:
  CPU_Hz - processing cycles of CPU assigned to the PMD in one sec
  PCPP - average processing cycles per packet handled by the PMD
  ACPP - all cycles (processing and idle) per packet handled by the PMD
  N_RXQ - number of RXQs configured currently in PMD
  PMD_USAGE - % usage of PMD processing cycles by a RX queue in it

PCPP value reflects an average number of cpu cycles used to move a packet from
ingress port into the datapath. ACPP value is variation of PCPP to also add 
idle CPU cycles into account. So, when PMD is entirely busy and has reached its
maximum operating capacity (or to say, not idle because of continuous polling 
on all of its queues), PCPP would be equal to ACPP.

Pseudo code:

# List of idle PMDs
Empty_PMDs_list = [ PMD if EMPTY(PMD.RXQs) for each PMD ]
Busy_PMDs_list = [ ]

for each PMD {
	# List of RXQs in PMD, in the order of incrementing PMD_USAGE
	RXQ_list = [ RXQ from sort(RXQ_list, increment(PMD_USAGE)) ]
	
	# Lits of RXQs in PMD based on incrementing PMD usage
	RXQ_load_list = [ PCPP*PMD_USAGE for each RXQ]
	RXQ_load_list = [ RXQ from sort(RXQ_load_list, increment(value) ]

	# current PMD load
	PMD_LOAD = PCPP/ACPP*100
	
	# record best ACPP at this time
	MIN_CPP = ACPP
	
	If (ACPP == PCPP) {
		#  PMD is 100% loaded
		
		if (COUNT(RXQs) > 1) {
			# More than one RXQs handled. Try to free any of these.
			if EMPTY(Empty_PMDs_list) {
				# No Empty PMD available to free some current PMD cycles.
				RETURN None
			}
			
			# Empty PMD available.
			for each RXQ in RXQ_list {
				# Ideally, PMD usage should have been equally shared by RXQs.
				if (PMD_USAGE <= 100/COUNT(RXQs)) {
					# less busy RXQ is more suitable for this idle PMD.
					RETURN ControlAction {
						Set CPU Affinity of RXQ to Empty PMD's CPU
						REMOVE(Empty_PMDs_list, PMD)
					}
				}
				# Ignore RXQ whose PMD usage is already good.
				noop
			}
		}        
    	else {
    		# Only one RXQ in this PMD.
    		# PMD is already 100% busy, so move it to Busy_PMDs_list
			INSERT(Busy_PMDs_list, PMD)
		}
	}
	else {
		# PMD is not 100% loaded, so it can accommodate other less busy RXQ.
		# POP_HEAD to release value at index 0 of list. It would be the RXQ 
		# which consumes least PMD cycles than other RXQs.
		RXQ = POP_HEAD(RXQ_load_list)
		Return ControlAction {
			Set CPU Affinity of RXQ to current PMD's CPU
			REMOVE(RXQ_load_list,RXQ)
		}
	}
}

RETURN ControlAction {
	Instruct ncd_collect thread for stats refresh
}
