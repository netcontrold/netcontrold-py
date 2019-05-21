#!/usr/bin/env python
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

# include NCD library
import sys
import os

ncd_root = os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))
ncd_lib = os.path.join(ncd_root, 'lib')
sys.path.insert(0, ncd_lib)

from logger import Logger
import util
from error import *

# import system libraries
import signal
import time
import re
import argparse
import copy

# Global variables used by this application.
nlog = Logger()
port_to_id = {}

# Maximum number of times to collect various stats from the vswitch
# before using them for rebalance calculation. Larger the value,
# better the estimation in dry run of this tool (before applying 
# rebalanced pmds), at the same time larger the time taken to 
# arrive at conclusion for rebalance, as decided by sample interval.
# Input param "--sample-interval" option available. 
ncd_samples_max = 6

# Maximum variance allowed in the pmd load values calculated in
# each sampling iteration. This value judges on whether all the PMDs
# have arrived at a balanced equilibrium. Smaller the value, better 
# the load balance in all PMDs,  at the same time larger the time
# taken by tool arrive at conclusion for rebalance.
ncd_pmd_load_variance_max = 100

# Minimum per core load threshold to trigger rebalance, if the pmd load
# is above this threshold.
ncd_pmd_core_threshold = 50

class Dataif_Rxq(object):
    """
    Class to represent the RXQ in the datapath of vswitch.
    
    Attributes
    ----------
    id : int
        id of the rxq
    port : object
        instance of Dataif_Port class.
        every rxq must be one of the members in port.rxq_map     
    pmd : object
        instance of Dataif_Pmd class.
        rxq's current association with this pmd before rebalance.
    cpu_cyc: list
        cpu cycles used by this rxq in each sampling interval.
    """
    
    def __init__(self, id=None):
        """
        Initialize Dataif_Rxq object.
        
        Parameters
        ----------
        id : int
            the id of the rxq
        
        Raises
        ------
        ObjCreateExc
            if no id is given as input.            
        """
        
        if id is None:
            raise ObjCreateExc("Rxq id can not be empty")
        
        self.id = id
        self.port = None
        self.pmd = None
        self.cpu_cyc = [0, ] * ncd_samples_max

class Dataif_Port(object):
    """
    Class to represent the port in the datapath of vswitch.
    
    Attributes
    ----------
    name : str
        name of this port
    id : int
        id of the port (as in vswitch db)
    numa_id : int
        numa that this port is associated with.    
    rxq_map : dict
        map of rxqs that this port is associated with.
    rxq_rebalanced : dict
        map of PMDs that its each rxq will be associated with. 
        
    Methods
    -------
    find_rxq_by_id(id)
        returns rxq associated with this port.
    add_rxq(id)
        add new rxq or return one if available.
    del_rxq(id)
        delete rxq from this port.
    """

    def __init__(self, name=None):
        """
        Initialize Dataif_Port object.
        
        Parameters
        ----------
        name : str
            the name of the port

        Raises
        ------
        ObjCreateExc
            if no name is given as input.            
        """

        if name is None:
            raise ObjCreateExc("Port name can not be empty")
                
        self.name = name
        self.id = None
        self.numa_id = None
        self.rxq_map = {}
        self.rxq_rebalanced = {}
    
    def find_rxq_by_id(self, id):
        """
        Return Dataif_Rxq of this id if available in port.rxq_map.
        Otherwise none returned.
        
        Parameters
        ----------
        id : int
            id of rxq to search.
        """
        
        if self.rxq_map.has_key(id):
            return self.rxq_map[id]
        
        return None

    def add_rxq(self, id):
        """
        Add new Dataif_Rxq object for this id in port.rxq_map, if one
        is not already available.
        
        Parameters
        ----------
        id : int
            id of rxq to be added.
        """
        
        # check if this rxq is already available.
        rxq = self.find_rxq_by_id(id)
        if rxq:
            return rxq
        
        # create new rxq and add it in our rxq_map.
        rxq = Dataif_Rxq(id)
        self.rxq_map[id] = rxq
        
        # remember the port this rxq is tied with.
        rxq.port = self
        
        # caller to ensure assigning the pmd that this rxq is 
        # currently tied with. This assignment should not be
        # changed until we complete rebalance dry-run. 
        rxq.pmd = None
        
        return rxq
    
    def del_rxq(self, id):
        """
        Delete Dataif_Rxq object of this id from port.rxq_map.
        
        Parameters
        ----------
        id : int
            id of rxq to be deleted.
        
        Raises
        ------
        ObjConsistencyExc
            if no such rxq is not already available.
        """
        
        # check if this rxq is already available.
        rxq = self.find_rxq_by_id(id)
        if not rxq:
            raise ObjConsistencyExc("rxq %d not found" %id)

        # remove rxq from its map.
        self.rxq_map.pop(id, None)
       
class Dataif_Pmd(object):
    """
    Class to represent the PMD thread in the datapath of vswitch.
    
    Attributes
    ----------
    id : int
        id of the pmd (i.e cpu core id it is pinned)
    numa_id : int
        numa that this pmd is associated with.
    rx_cyc : list
        samples of packets received by this pmd.
    idle_cpu_cyc : list
        samples of idle cpu cycles consumed by this pmd.
    proc_cpu_cyc : list
        samples of processing cpu cycles consumed by this pmd.
    cyc_idx : int
        current sampling index.
    isolated : bool
        whether this pmd is isolated from auto rebalance of vswitch.
    pmd_load : int
        how busy the pmd is.
    port_map : dict
        map of ports associated with this pmd, through rxq(s)
        of this port.
    
    Methods
    -------
    find_port_by_name(name)
        returns port of this name associated with this pmd.
    find_port_by_id(id)
        returns port of this id associated with this pmd.
    add_port(name)
        add new port or return one if available.
    del_port(name)
        delete port from this pmd.
    count_rxq()
        returns count of all rxqs associated with this pmd.
    """

    def __init__(self, id=None):
        """
        Initialize Dataif_Pmd object.
        
        Parameters
        ----------
        id : int
            id of the pmd.

        Raises
        ------
        ObjCreateExc
            if no name is given as input.            
        """

        if id is None:
            raise ObjCreateExc("PMD id can not be empty")

        self.id = id
        self.numa_id = None
        self.rx_cyc = [0, ] * ncd_samples_max
        self.idle_cpu_cyc = [0, ] * ncd_samples_max
        self.proc_cpu_cyc = [0, ] * ncd_samples_max
        self.cyc_idx = 0
        self.isolated = None
        self.pmd_load = 0
        self.port_map = {}

    def __repr__(self):
        str = ""
        str += "pmd %d\n" %self.id
        str += "pmd %d numa_id %d\n" %(self.id, self.numa_id)
        for i in range(0, len(self.rx_cyc)):
            elm = self.rx_cyc[i]
            str += "pmd %d rx_cyc[%d] %d\n" %(self.id, i, elm)
        for i in range(0, len(self.idle_cpu_cyc)):
            elm = self.idle_cpu_cyc[i]
            str += "pmd %d idle_cpu_cyc[%d] %d\n" %(self.id, i, elm)
        for i in range(0, len(self.proc_cpu_cyc)):
            elm = self.proc_cpu_cyc[i]
            str += "pmd %d proc_cpu_cyc[%d] %d\n" %(self.id, i, elm)
        str += "pmd %d cyc_idx %d\n" %(self.id, self.cyc_idx)
        str += "pmd %d isolated %s\n" %(self.id, self.isolated)
        str += "pmd %d pmd_load %d\n" %(self.id, self.pmd_load)
        for port_name, port in self.port_map.items():
            str += "  port %s\n" %(port_name)
            str += "  port %s numa_id %d\n" %(port_name, port.numa_id)
            for rxq_id, rxq in port.rxq_map.items():
                str += "    rxq %d\n" %rxq_id
                for i in range(0, len(rxq.cpu_cyc)):
                    elm = rxq.cpu_cyc[i]
                    str += "    rxq %d cpu_cyc[%d] %d\n" %(rxq_id, i, elm)
        return str
        
    def find_port_by_name(self, name):
        """
        Return Dataif_Port of this name, if available in pmd.port_map .
        Otherwise none returned.
        
        Parameters
        ----------
        name : str
            name of the port to be searched.
        """

        if self.port_map.has_key(name):
            return self.port_map[name]
        
        return None

    def find_port_by_id(self, id):
        """
        Return Dataif_Port of this id, if available in pmd.port_map .
        Otherwise none returned.
        
        Parameters
        ----------
        id : int
            id of the port to be searched.
        """

        for port in self.port_map.values():
            if port.id == id:
                return port
            
        return None

    def add_port(self, name, id=None, numa_id=None):
        """
        Add new Dataif_Port for this name in pmd.port_map, if one
        is not already available.
        
        Parameters
        ----------
        name : str
            name of the port to be added.
        id : int, optional
            id of the port (default is None)
        numa_id : int, optional
            numa id associated with this port (default is None)
        """

        # check if a port of this name already exists.
        port = self.find_port_by_name(name)
        if port:
            return port
        
        # create new port and add it in port_map.
        port = Dataif_Port(name)
        self.port_map[name] = port
        
        # store other input options.
        # TODO: port numa could actually be from sysfs to avoid
        #       any configuration fault.
        port.id = id
        port.numa_id = numa_id
        
        return port
        
    def del_port(self, name):
        """
        Delete Dataif_Port object of this name from pmd.port_map.
        
        Parameters
        ----------
        name : str
            name of the port to be deleted.
        
        Raises
        ------
        ObjConsistencyExc
            if no such port is not already available.
        """

        # check if port of this name is already available.
        port = self.find_port_by_name(name)
        if not port:
            raise ObjConsistencyExc("port %s not found" %name)

        # remove this port from port map.
        self.port_map.pop(name, None)

    def count_rxq(self):
        """
        Returns the number of rxqs (of all the ports) pinned with
        this pmd.    
        """
        
        n_rxq = 0

        # aggregate the number of rxqs in each port.
        for port in self.port_map.values():
            n_rxq += len(port.rxq_map)

        return n_rxq
    
def upd_port_to_id():
    """
    Update global variable port_to_id to reflect current association of
    name of the each port and its id. This map could be used to extract
    id of the port from its name.
    
    Raises
    ------
    OsCommandExc
        if the given OS command did not succeed for some reason. 
    """
    
    global port_to_id
    
    # retrieve required data from the vswitch.
    cmd = "ovs-appctl dpctl/show"
    data = util.exec_host_command(cmd)
    if not data:   
        raise OsCommandExc("unable to collect data(%s)" %cmd)

    # parse each line from the output and update port_to_id map.
    for line in data.splitlines():
        linesre = re.search(r'\s.*port\s(\d+):\s(\w+) *', line)
        if linesre:
            (pid, pname) = linesre.groups()
            port_to_id[pname] = int(pid)

    return None

def get_pmd_stats(pmd_map):
    """
    Collect stats on every pmd running in the system and update 
    pmd_map. In every sampling iteration, these stats are stored
    in corresponding sampling slots.

    Parameters
    ----------
    pmd_map : dict
        mapping of pmd id and its Dataif_Pmd object.
        
    Raises
    ------
    OsCommandExc
        if the given OS command did not succeed for some reason.
    """
    
    # retrieve required data from the vswitch.
    cmd = "ovs-appctl dpif-netdev/pmd-stats-show"
    data = util.exec_host_command(cmd)
    if not data:
        raise OsCommandExc("unable to collect data")

    # sname and sval stores parsed string's key and value.
    sname, sval = None, None
    # current pmd object to be used in every line under parse.
    pmd = None

    for line in data.splitlines():
        if line.startswith("pmd thread"):
            # In below matching line, we retrieve core id (aka pmd id)
            # and core id.
            linesre = re.search(r'pmd thread numa_id (\d+) core_id (\d+):', 
                                line)
            numa_id = int(linesre.groups()[0])
            core_id = int(linesre.groups()[1])

            # If in mid of sampling, we should have pmd_map having
            # entry for this core id.
            if pmd_map.has_key(core_id):
                pmd = pmd_map[core_id]
                
                # Check to ensure we are good to go as local should
                # always be used.
                assert(pmd.numa_id == numa_id)
                
                # Store following stats in new sampling slot.
                pmd.cyc_idx = (pmd.cyc_idx + 1) % ncd_samples_max
                nlog.debug("pmd %d in iteration %d" %(pmd.id, pmd.cyc_idx))
            else:
                # Very first sampling for each pmd occur in this
                # clause. Just ensure, no new pmd is added from system
                # reconfiguration.
                if len(pmd_map) != 0 and not pmd:
                    raise ObjConsistencyExc("trying to add new pmd %d in mid of ncd!.. aborting! ")
                
                # create new entry in pmd_map for this pmd.
                pmd = Dataif_Pmd(core_id)
                pmd_map[pmd.id] = pmd
                nlog.debug("added pmd %s stats.." %pmd.id)
                
                # numa id of pmd is of core's.
                pmd.numa_id = numa_id
        elif line.startswith("main thread"):
            # end of pmd stats
            break
        else:
            # From other lines, we retrieve stats of the pmd.
            (sname, sval) = line.split(":")
            sname = re.sub("^\s+", "", sname)
            sval = sval[1:].split()
            if sname == "packets received":
                pmd.rx_cyc[pmd.cyc_idx] = int(sval[0])
            elif sname == "idle cycles":
                pmd.idle_cpu_cyc[pmd.cyc_idx] = int(sval[0])
            elif sname == "processing cycles":
                pmd.proc_cpu_cyc[pmd.cyc_idx] = int(sval[0])
                
    return pmd_map

def get_pmd_rxqs(pmd_map):
    """
    Collect info on how rxq is pinned with pmd, from the vswitch.

    Parameters
    ----------
    pmd_map : dict
        mapping of pmd id and its Dataif_Pmd object.
        
    Raises
    ------
    OsCommandExc
        if the given OS command did not succeed for some reason.
    """
    
    # retrieve required data from the vswitch.
    cmd = "ovs-appctl dpif-netdev/pmd-rxq-show"
    data = util.exec_host_command(cmd)
    if not data:   
        raise OsCommandExc("unable to collect data")

    # sname and sval stores parsed string's key and value.
    sname, sval = None, None
    # current pmd object to be used in every line under parse.
    pmd = None
    
    for line in data.splitlines():
        if line.startswith('pmd thread'):
            # In below matching line, we retrieve core id (aka pmd id)
            # and core id.
            linesre = re.search(r'pmd thread numa_id (\d+) core_id (\d+):',
                                line)
            numa_id = int(linesre.groups()[0])
            core_id = int(linesre.groups()[1])
            if not pmd_map.has_key(core_id):
                raise ObjConsistencyExc("trying to add new pmd %d in mid of ncd!.. aborting! ")
            pmd = pmd_map[core_id]
            assert(pmd.numa_id == numa_id)
            nlog.debug("pmd %d in iteration %d" %(pmd.id, pmd.cyc_idx))

        elif re.match(r'\s.*port: .*', line):
            # From this line, we retrieve cpu usage of rxq.
            linesre = re.search(r'\s.*port:\s(\w+)\s*queue-id:\s*(\d+)\s*pmd usage:\s*(\d+|NOT AVAIL)\s*?',
                                line)
            
            pname = linesre.groups()[0]
            qid = int(linesre.groups()[1])
            try:
                qcpu = int(linesre.groups()[2])
            except ValueError:
                qcpu = linesre.groups()[2]
                if (qcpu == 'NOT AVAIL'):
                    # rxq stats not available at this time, skip this iteration.
                    qcpu = 0
                else:
                    raise ObjParseExc("error parsing line %s" %line)

            # get the Dataif_Port owning this rxq.
            port = pmd.find_port_by_name(pname)
            if not port:
                # TO-DO: stop rebalance if pmd is assigned manually 
                # a new port that this run is not aware of.
                port = pmd.add_port(pname)
            
            # update port attributes now.
            port.id = port_to_id[pname]
            port.numa_id = pmd.numa_id
            
            # check whether this rxq was being rebalanced.
            if port.rxq_rebalanced.has_key(qid):
                # In dry-run, we need to update cpu cycles consumed by
                # this rxq (through current pmd), into the processing 
                # cycles of the rebalancing pmd. Then the load of the 
                # rebalancing pmd could be estimated appropriately.
                reb_pmd_id = port.rxq_rebalanced[qid]
                reb_pmd = pmd_map[reb_pmd_id]
                reb_port = reb_pmd.find_port_by_name(port.name)
                rxq = reb_port.find_rxq_by_id(qid)
                # qcpu is in percentage in this data, so we convert it
                # into actual cycles using processing cycles that this
                # pmd consumed.
                # qrx is approximate count of packets that this rxq
                # received.
                qrx = qcpu * pmd.rx_cyc[pmd.cyc_idx]
                qcpu *= pmd.proc_cpu_cyc[pmd.cyc_idx]
                # update rebalancing pmd for cpu cycles and rx count.
                reb_pmd.proc_cpu_cyc[pmd.cyc_idx] += qcpu
                reb_pmd.idle_cpu_cyc[pmd.cyc_idx] -= qcpu
                reb_pmd.rx_cyc[pmd.cyc_idx] += qrx
            else:
                # port not in rebalancing state, so update rxq for its
                # cpu cycles consumed by it.
                rxq = port.add_rxq(qid)
                rxq.pmd = pmd
                rxq.port = port
                qcpu *= pmd.proc_cpu_cyc[pmd.cyc_idx]
            
            rxq.cpu_cyc[pmd.cyc_idx] = qcpu
        else:
            # From other line, we retrieve isolated flag.
            (sname, sval) = line.split(":")
            sname = re.sub("^\s+", "", sname)
            assert(sname == 'isolated ')
            pmd.isolated = {'true':True, 'false':False}[sval[1:]]
            
    return pmd_map

def rebalance_dryrun(pmd_map):
    """
    Rebalance pmds based on their current load of traffic in it and
    it is just a dry-run. In every iteration of this dry run, we keep
    re-assigning rxqs to suitable pmds, at the same time we use 
    actual load on each rxq to reflect the estimated pmd load after
    every optimization.
    
    To re-pin rxqs, the logic used is to move idle (or less loaded) 
    rx queues into idle (or less loaded) pmds so that, busier rxq is
    given more processing cycles by busy pmd.

    Parameters
    ----------
    pmd_map : dict
        mapping of pmd id and its Dataif_Pmd object.
    """
    
    for pmd_id, pmd in pmd_map.items():
        # Given we have samples of rx packtes, processing and idle cpu
        # cycles of a pmd, we do variance on these samples to derive
        # how close these values are. Instead of average which could
        # potentially hide spike in samples, variance yields better
        # balance on these samples first, as these values decide pmd
        # load as below.
        rx_var = util.variance(pmd.rx_cyc)
        idle_var = util.variance(pmd.idle_cpu_cyc)
        proc_var = util.variance(pmd.proc_cpu_cyc)

        try:
            cpp = (idle_var+proc_var)/rx_var
            pcpp = proc_var/rx_var
            pmd.pmd_load = float((pcpp*100)/cpp)
        except ZeroDivisionError:
            # When a pmd is really idle and also yet to be picked for
            # rebalancing other rxqs, its rx packets count could still
            # be zero, hence we get zero division exception.
            # It is okay to declare this pmd as idle again.
            pmd.pmd_load = 0

    # Sort pmds in pmd_map based on the rxq load, in descending order.
    # Pick the pmd which is more loaded from one end of the list.
    pmd_load_list = sorted(pmd_map.values(), key=lambda o: o.pmd_load, reverse=True)
    
    # Split list into busy and less loaded.
    bpmd_load_list = []
    ipmd_load_list = []
    for pmd in pmd_load_list:
        # pmd load of above configured threshold 
        if pmd.pmd_load > ncd_pmd_core_threshold:
            bpmd_load_list.append(pmd)

        # skip pmd when its rxq count is one i.e pmd has just one rxq,
        # and this rxq is already busy (hencs, pmd was busy).
        elif pmd.count_rxq() == 1:
            continue
        # rest of the pmds are less loaded (or idle).
        else:
            ipmd_load_list.append(pmd)
            
    for pmd in bpmd_load_list:       
        # As busy and idles (or less loaded) pmds are identified,
        # move less loaded rxqs from busy pmd into idle pmd.
        for port in pmd.port_map.values():
            # As we pick one or more rxqs for every port in this pmd,
            # we leave atleast one rxq, not to make this busy pmd as
            # idle again.
            if pmd.count_rxq() <= 1:
                continue

            ipmd = None
            for i in ipmd_load_list:
                # Current pmd and rebalancing pmd should be in same numa.
                if (i.numa_id != port.numa_id):
                    continue
                
                ipmd = ipmd_load_list.pop(0)
                break
            
            if not ipmd:
                nlog.debug("no more pmd available to accept new rxqs..")
                break 

            # Sort rxqs based on their current load, in ascending order.
            pmd_proc_cyc = pmd.proc_cpu_cyc[pmd.cyc_idx]
            rxq_load_list = sorted(port.rxq_map.values(),
                key=lambda o: ((o.cpu_cyc[pmd.cyc_idx] * 100)/pmd_proc_cyc))

            # pick one rxq to rebalance and this was least loaded in this pmd.    
            rxq = rxq_load_list.pop(0)
            
            # move this rxq into the rebalancing pmd.
            iport = ipmd.add_port(port.name, id=port.id, numa_id=port.numa_id)
            nlog.info("moving rxq %d (port %s) from pmd %d into idle pmd %d .."
                %(rxq.id, port.name, pmd.id, ipmd.id))
            irxq = iport.add_rxq(rxq.id)
            assert(iport.numa_id == port.numa_id)
            
            # Copy cpu cycles of this rxq into its clone in
            # in rebalancing pmd (for dry-run).
            irxq.cpu_cyc = copy.deepcopy(rxq.cpu_cyc)
            
            # No more tracking of this rxq in current pmd.              
            port.del_rxq(rxq.id)
            
            # Until dry-run is completed and rebalance completed,
            # this rxq should know its current pmd, even it is
            # with rebalancing pmd. Only then, we can derive cpu
            # usage of this rxq from its current pmd (as we scan
            # data in each sampling interval).
            opmd = rxq.pmd
            oport = opmd.find_port_by_name(port.name)
            oport.rxq_rebalanced[rxq.id] = ipmd.id
            irxq.pmd = opmd

    return pmd_map

def pmd_need_rebalance(pmd_map):
    """
    Check whether all the pmds have arrived at the balanced equilibrium.
    Also,  pmd load is above minimum threshold.

    Parameters
    ----------
    pmd_map : dict
        mapping of pmd id and its Dataif_Pmd object.
    """
    
    pmd_load_list = map(lambda o: o.pmd_load, pmd_map.values())
    mean = sum(pmd_load_list)/len(pmd_load_list)
    var = util.variance(pmd_load_list)

    if (var >= ncd_pmd_load_variance_max and mean >= ncd_pmd_core_threshold):
        return True

    return False

def collect_data(pmd_map):
    """
    Collect various stats and rxqs mapping of every pmd in the vswitch.

    Parameters
    ----------
    pmd_map : dict
        mapping of pmd id and its Dataif_Pmd object.
    """

    upd_port_to_id()
    upd_pmd_map = get_pmd_stats(pmd_map)
    return get_pmd_rxqs(upd_pmd_map)

def rebalance_switch(pmd_map):
    """
    Issue appropriate actions in vswitch to rebalance.

    Parameters
    ----------
    pmd_map : dict
        mapping of pmd id and its Dataif_Pmd object.
    """

    port_to_pmdq = {}
    for pmd_id, pmd in pmd_map.items():
        nlog.critical(pmd)
        for port_name, port in pmd.port_map.items():
           if not port_to_pmdq.has_key(port_name):
               port_to_pmdq[port_name] = ""
           for rxq_id in port.rxq_map:
               port_to_pmdq[port_name] += "%d:%d," %(rxq_id, pmd_id)

    cmd = ""
    for port_name, pmdq in port_to_pmdq.items():
        cmd += "-- set Interface %s other_config:pmd-rxq-affinity=%s " %(port_name, pmdq)

    return "ovs-vsctl %s" %cmd

def ncd_kill(signal, frame):
    nlog.info("Got signal %s, stopping NCD .." %signal)
    raise NcdShutdownExc

def ncd_main():
    # input options
    argpobj = argparse.ArgumentParser(prog='ncd.py', description='NCD options:')
    argpobj.add_argument('-i', '--rebalance-interval',
        type=int,
        default=60,
        help='interval in seconds between each re-balance (default: 60)')

    argpobj.add_argument('-n', '--rebalance-n',
        type=int,
        default=-1,
        help='maximum number of rebalance attempts (default: infinite)')

    argpobj.add_argument('-s', '--sample-interval',
        type=int,
        default=5,
        help='interval in seconds between each sampling (default: 5)')

    argpobj.add_argument('-v', '--verbose',
        type=int,
        default=0,
        help='verbose level for output (default: 0)')

    args = argpobj.parse_args()

    # set verbose level
    if not (0 <= args.verbose <= 2):
        nlog.info("verbose level should be 0, 1 or 2. exiting ..")
        sys.exit(1)
    nlog.set_level(args.verbose)

    # set interval between each re-balance
    ncd_rebal_interval = args.rebalance_interval
    ncd_rebal_n = args.rebalance_n
    ncd_sample_interval = args.sample_interval
    
    # set signal handler to abort ncd
    signal.signal(signal.SIGINT, ncd_kill)
    signal.signal(signal.SIGTERM, ncd_kill)
    
    # adjust length of the samples counter
    global ncd_samples_max
    ncd_samples_max = min(ncd_rebal_interval / ncd_sample_interval, ncd_samples_max)
    sample_tick = 0
    
    # set check point to call rebalance in vswitch
    rebal_tick_n = ncd_rebal_interval/ncd_sample_interval
    rebal_tick = 0
    rebal_i = 0
    
    initial_pmd_map = {}
    for i in range(0, ncd_samples_max):
        initial_pmd_map = collect_data(initial_pmd_map)

    if len(initial_pmd_map) < 2:
        nlog.info("required at least two pmds to check rebalance..")
        sys.exit(1)

    nlog.info("pmd load before rebalancing by this tool:")
    for pmd_id in sorted(initial_pmd_map.keys()):
        pmd = initial_pmd_map[pmd_id]
        rx_var = util.variance(pmd.rx_cyc)
        idle_var = util.variance(pmd.idle_cpu_cyc)
        proc_var = util.variance(pmd.proc_cpu_cyc)

        try:
            cpp = (idle_var+proc_var)/rx_var
            pcpp = proc_var/rx_var
            pmd.pmd_load = float((pcpp*100)/cpp)
        except ZeroDivisionError:
            pmd.pmd_load = 0

        nlog.info("pmd id %d load %d" %(pmd_id, pmd.pmd_load))

    # begin rebalance dry run
    pmd_map = {}
    while (1):
        try:
            # collect samples of pmd and rxq stats.
            pmd_map = collect_data(pmd_map)
            sample_tick += 1
            
            if (sample_tick < ncd_samples_max):
                time.sleep(ncd_sample_interval)
                rebal_tick += 1
                continue
            
            # all samples collected.
            sample_tick = 0
            
            # dry run on collected stats
            pmd_map = rebalance_dryrun(pmd_map)
            rebal_i += 1
            nlog.info("pmd load in dry run(%d):" %rebal_i)
            for pmd_id in sorted(pmd_map.keys()):
                pmd = pmd_map[pmd_id]
                nlog.info("pmd id %d load %d" %(pmd_id, pmd.pmd_load))
     
            # check if balance state of all pmds is reached           
            if not pmd_need_rebalance(pmd_map):
                nlog.info("new pmd load estimated is:")
                for pmd_id in sorted(pmd_map.keys()):
                    pmd = pmd_map[pmd_id]
                    nlog.info("pmd id %d load %d" %(pmd_id, pmd.pmd_load))
     
                # check if it is time to issue rebalance in vswitch
                if not (rebal_tick < rebal_tick_n):
                    nlog.info("dry runs stopping at rebalancing interval (%d sec)" %ncd_rebal_interval)
                    nlog.info("vswitch command for current optimization is: %s" %rebalance_switch(pmd_map))
                
                    # sleep for few seconds before thrashing current dry-run
                    nlog.info("waiting for 5 seconds before new dry runs begin..")
                    time.sleep(5)
                    
                    # reset collected data
                    pmd_map = {}
                    rebal_tick = 0

            else:
               if (ncd_rebal_n > 0 and rebal_i > ncd_rebal_n):
                    # We reached maximum allowable dry runs, but
                    # pmd load variance is still above than permitted
                    # limit. So, we stop here as it is asked for so.
                    nlog.info("reached maximum count(%d) of dry runs.." %ncd_rebal_n)
                    nlog.info("vswitch command for current optimization is: %s" %rebalance_switch(pmd_map))
                    return

        except NcdShutdownExc:
            
            nlog.info("Exiting NCD ..")    
            sys.exit(1)
            
if __name__ == "__main__":
    ncd_main()
    sys.exit(0)
