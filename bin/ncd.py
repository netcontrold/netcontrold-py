#!/usr/bin/env python
# Copyright notice to be added
#
from abc import abstractmethod
import threading
import signal
import os
import sys
import time
import re
import argparse
from time import sleep
from Queue import Queue

ncd_root = os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))
ncd_lib = os.path.join(ncd_root, 'lib')
sys.path.insert(0, ncd_lib)

import dataif_pmd
import dataif_port
from logger import nlog
import util
import ctrlact_common
from error import NCDShutdown, PmdObjCreateError, ParseError

ncd_threads = {'collect': None,
               'monitor': None,
               'analyzer': None
               }


# pipe to exchange pmd between collect and monitor threads
obj_queue_c2a = Queue()
    
class DataSrc(object):
    def __init__(self):
        # name of data source
        self._name = None
        # type of this source. Possible values are
        #   'host-command'
        self._type = None
        # define source (command for eg)
        self._src = None
        # location of data
        self._result = None
        # location of processed data
        self._obj_result = None
    
    def collect_data(self):
        self._result = util.exec_host_command(self._src)
    
    @abstractmethod
    def parse(self):
        pass
    
    def get_result(self):
        return self._result

    def get_obj_result(self):
        return self._obj_result
    
class PmdRxq(DataSrc):
    def __init__(self):
        self._name = "pmd-rxq-show"
        self._type = "host-command"
        self._src = "ovs-appctl dpif-netdev/pmd-rxq-show"
                
    def parse(self):
        """
        Parses pmd-rxq-show and update each pmd in given list.
        Each pmd object is updated with:
            1. port (and its queues) it handles
            2. whether isolated from other pmd or not
            
        """
        iter_level = 0
        sname, sval = None, None
        pmdo = None
        pmdelmp = None
        self._obj_result = {}

        for line in self._result.splitlines():
            
            if line.startswith("pmd thread"):
                linesre = re.search(r'pmd thread numa_id (\d+) core_id (\d+):',
                                    line)
                (nid, cid) = linesre.groups()
                if iter_level == 0:
                    # just new pmd info starts here
                    pmdo = dataif_pmd.Pmd()
                    iter_level += 1
                else:
                    # already in pmd_iter, so stop previous iteration
                    self._obj_result[pmdo.get_id()] = pmdo
                    nlog.debug("added pmd %s info.." %pmdo.get_id())
                    pmdo = dataif_pmd.Pmd()
                    iter_level = 1
                    
                pmdelmp = pmdo.stats_to_elem('numa_id')
                pmdo.set_elem(pmdelmp, int(nid))
                pmdelmp = pmdo.stats_to_elem('core_id')
                pmdo.set_elem(pmdelmp, int(cid))

            elif iter_level == 1:
                linesre = re.search(r'\s.* port: (\w+) .* queue-id:  (\d+) .* pmd usage:\s+(\d+|NOT AVAIL)\s*?',
                                    line)
                if linesre:
                    (pname, qid, qcpu) = linesre.groups()
                    if (qcpu == 'NOT AVAIL'):
                        # rxq stats not available at this time, skip this iteration.
                        raise ParseError("rxq stats not available")

                    pobj = dataif_port.Port(name=pname)
                    pobj.add_queue(qid)
                    qobj = pobj.get_queue(qid)
                    qobj.set_cpu_usage(int(qcpu))
                    pmdo.add_port(pobj)
                    
                else:
                    (sname, sval) = line.split(":")
                    assert(sname[2:] == 'isolated ')
                    pmdelmp = pmdo.stats_to_elem(sname[2:])
                    pmdo.set_elem(pmdelmp, {'true':True, 'false':False}[sval[1:]])
            
            else:
                # nothing to parse
                pass
        else:
            # all lines are parsed, so update last pmdo.
            self._obj_result[pmdo.get_id()] = pmdo
            nlog.debug("added pmd %s info.." %pmdo.get_id())

        return None

class PmdStats(DataSrc):
    def __init__(self):
        self._name = "pmd-stats-show"
        self._type = "host-command"
        self._src = "ovs-appctl dpif-netdev/pmd-stats-show"
        
    def __add_pmd_rxq__(self, other_pmd):
        for oid in other_pmd.get_obj_result().keys():
            other_pmdo = other_pmd.get_obj_result()[oid]
            pmdo = self.get_obj_result()[oid]
            
            # copy isolated attribute from rxq show
            pmdo._isolated = other_pmdo._isolated

            # add port info from other_pmd
            for port in other_pmdo._ports:
                pmdo.add_port(port)
        return self
    
    def __add_port_id__(self, dpmap):
        for pmd in self.get_obj_result().values():
            for port in pmd._ports:
                # set port id for this port name
                port._id = dpmap.get_obj_result()[port.get_name()]
        return self
                
    def __add__(self, other_obj):
        if isinstance(other_obj, PmdRxq):
            return self.__add_pmd_rxq__(other_obj)
        elif isinstance(other_obj, DpathPorts):
            return self.__add_port_id__(other_obj)
        else:
            raise PmdObjCreateError("Unsupported data for PMD to parse and add")
        
        return None

    def __iadd__(self, other_obj):
        return self.__add__(other_obj)
          
    def parse(self):
        """
        Parses pmd-stats-show and returns list of pmd objects.
        Each pmd object contains information of handled queues.
        """
        iter_level = 0
        sname, sval = None, None
        pmdo = None
        pmdelmp = None
        self._obj_result = {}
        for line in self._result.splitlines():
            if line.startswith("pmd thread"):
                if iter_level == 0:
                    # just new pmd info starts here
                    pmdo = dataif_pmd.Pmd()
                    iter_level += 1
                else:
                    # already in pmd_iter, so stop previous iteration
                    self._obj_result[pmdo.get_id()] = pmdo
                    nlog.debug("added pmd %s info.." %pmdo.get_id())
                    pmdo = dataif_pmd.Pmd()
                    iter_level = 1
                    
                linesre = re.search(r'pmd thread numa_id (\d+) core_id (\d+):', 
                                    line)
                pmdelmp = pmdo.stats_to_elem('numa_id')
                pmdo.set_elem(pmdelmp, int(linesre.group(1)))
                pmdelmp = pmdo.stats_to_elem('core_id')
                pmdo.set_elem(pmdelmp, int(linesre.group(2)))
            
            elif iter_level == 1:
                (sname, sval) = line.split(":")
                pmdelmp = pmdo.stats_to_elem(sname[2:])
                if not pmdelmp:
                    continue

                if pmdelmp in ('_cpp', '_pcpp'):
                    sval = float(sval[1:].split()[0])
                else:
                    sval = int(sval[1:].split()[0])

                pmdo.set_elem(pmdelmp, sval)
    
            else:
                # nothing to parse
                pass
        
        else:
            # all lines are parsed, so update last pmdo.
            self._obj_result[pmdo.get_id()] = pmdo
            nlog.debug("added pmd %s info.." %pmdo.get_id())

        return None

class DpathPorts(DataSrc):
    def __init__(self):
        self._name = "dpctl-show"
        self._type = "host-command"
        self._src = "ovs-appctl dpctl/show"

    def parse(self):
        """
        Parses dpctl-show and creates port ID/Name mapping.
        """
        self._obj_result = {}
            
        for line in self._result.splitlines():
            linesre = re.search(r'\s.* port (\d+): (.*?) ', line)
            if linesre:
                (pid, pname) = linesre.groups()
                self._obj_result[pname] = int(pid)
                
        return None

class NcdWorker(threading.Thread):
    '''
    Worker thread abstraction for various NCD threads.
    '''
    # Global control variables for the threads
    timeout = 60
    count = 1
    
    def __init__(self, shuteventobj):
        threading.Thread.__init__(self)
        self.ncd_shutdown = shuteventobj
    
class NcdCollector(NcdWorker):
    def __init__(self, eobj):
        NcdWorker.__init__(self, eobj)
    
    def run(self):
        pmdsto = PmdStats()
        pmdrxqo = PmdRxq()
        dportmap = DpathPorts()
        
        while (not self.ncd_shutdown.is_set()):
            # Every 1 sec, we collect various required logs and pass the constructed
            # NCD data (Pmd'port'queue) to analyzer for creating control actions.
            sleep(1)
            # Collect required data from various sources.
            # For now, we depend on pmd and rxq stats.
            pmdsto.collect_data()
            pmdrxqo.collect_data()
            dportmap.collect_data()
    
            # update pmd stats from rxq.
            try:
                pmdrxqo.parse()
            except ParseError, e:
                nlog.debug(e)
                continue

            pmdsto.parse()
            dportmap.parse()
            pmdsto += pmdrxqo
            pmdsto += dportmap
            
            # Analyse each pmd and generate control action(s).
            obj_queue_c2a.put(pmdsto.get_obj_result())
    
            # Wait until analyzer has completed the analysis on these pmds.
            nlog.debug("collector waiting for analyzer to process ..")
            if not self.ncd_shutdown.is_set:
                obj_queue_c2a.join()

        nlog.info("collector thread stops now ..")
        return

class NcdMonitor(NcdWorker):
    def __init__(self, eobj):
        NcdWorker.__init__(self, eobj)
    
    def run(self):       
        while (not self.ncd_shutdown.is_set()):
            # Every 1 sec, we monitor the overall health of PMDs across system
            # resources. This monitoring need not only rely on internals of vSwitch,
            # but the data from kernel, userspace events etc.
            sleep(1)
            
            # TODO:
            # check if a lcore used by PMD is running only the PMD thread. This 
            # info is available in proc/sched_debug -> cpu# -> runnable_tasks.
            # ksoftirqd for eg should not be scheduled in pmd lcore.
            pass
        
        nlog.info("monitor thread stops now ..")
        return

class NcdAnalyzer(NcdWorker):
    def __init__(self, eobj):
        NcdWorker.__init__(self, eobj)
    
    def run(self):
        pending_analysis_n = NcdAnalyzer.count
        cobj = ctrlact_common.PmdCtrl()

        while (not self.ncd_shutdown.is_set() and pending_analysis_n):
            # Every 1 sec, we check if there is NCD data in pipeline and if so,
            # process them and create control actions. For now, only when control
            # action is completed (including acknowledgement from vswitch), we take 
            # new set of data for new analysis. But, this separate thread will
            # improve parallelism to work with multiple data sources (eg info from
            # guest and make control actions async.
            sleep(1)
            
            if not obj_queue_c2a.qsize():
                continue
            
            pmdsto = obj_queue_c2a.get()
            
            # create control action now.
            if cobj.apply_algo(pmdsto):
                pending_analysis_n -= 1
            
            # sync with collect thread now.
            nlog.debug("collector can resume process now ..")
            obj_queue_c2a.task_done()
            
        else:
            # Inform collector thread to resume shutdown instead.
            try:
                obj_queue_c2a.task_done()
            except ValueError:
                # it is ok to ignore if called once again.
                nlog.debug("already in sync with collector")
                pass

        nlog.info("analyzer thread stops now ..")
        return

def ncd_start():
    try:
        ncd_threads['collect'].start()
        ncd_threads['monitor'].start()
        ncd_threads['analyzer'].start()
    except threading.ThreadError, e:
        nlog.info("Failed to start NCD threads: %s" %e)
        ncd_stop()
        return False
    
    nlog.info("started all ncd threads ..")
    return True


def ncd_stop():
    ncd_threads['collect'].ncd_shutdown.set()
    ncd_threads['monitor'].ncd_shutdown.set()
    ncd_threads['analyzer'].ncd_shutdown.set()
    raise NCDShutdown

def ncd_kill(signal, frame):
    nlog.info("Got signal %s, stopping NCD threads .." %signal)
    ncd_stop()

def ncd_init():
    """
    This is foremost function executed by NCD. Normally, below threads
    are started which run in parallel for:
    1. Collecting various logs through supported commands in vswitch
       and trigger each associated parser.
    2. Monitoring external control events to NCD eg. start/stop NCD
    3. House keeping activities based on available info from vswitch.
       Eg. Analyzing PMD and ports and create action plans.  
    """
    shutdown_event = threading.Event()
    tobj = NcdCollector(shutdown_event)
    tobj.daemon = True
    ncd_threads['collect'] = tobj
    
    tobj = NcdMonitor(shutdown_event)
    tobj.daemon = True
    ncd_threads['monitor'] = tobj
    
    tobj = NcdAnalyzer(shutdown_event)    
    tobj.daemon = True
    ncd_threads['analyzer'] = tobj

def ncd_main():
    argpobj = argparse.ArgumentParser(prog='ncd.py', description='NCD options:')
    argpobj.add_argument('-t', '--timeout',
        type=int,
        default=60,
        help='to stop NCD after these secs (default: 60)')

    argpobj.add_argument('-c', '--count',
        type=int,
        default=1,
        help='to stop NCD after these counts on controlling (default: 1)')

    argpobj.add_argument('-v', '--verbose',
        type=int,
        default=0,
        help='verbose level for output (default: 0)')

    args = argpobj.parse_args()

    if not (0 <= args.verbose <= 2):
        nlog.info("verbose level should be 0, 1 or 2. exiting ..")
        sys.exit(1)
    nlog.set_level(args.verbose)

    NcdWorker.count = args.count
    NcdWorker.timeout = args.timeout
    
    signal.signal(signal.SIGINT, ncd_kill)
    signal.signal(signal.SIGTERM, ncd_kill)
    ncd_init()

    if not ncd_start():
        nlog.info("NCD fails to start its threads .. Exiting")
        sys.exit(1)

    try:
        countsec = NcdWorker.timeout
        while(countsec):
            time.sleep(1)
            countsec -= 1
            for tname in ncd_threads.keys():
                thread = ncd_threads[tname]
                if not thread.is_alive():
                    nlog.debug("Thread %s is not alive, stopping all threads" %tname)
                    ncd_stop()
                    break
        else:
            raise NCDShutdown
    except NCDShutdown:
        # Received shutdown indication from user.
        ncd_threads['collect'].ncd_shutdown.set()
        ncd_threads['monitor'].ncd_shutdown.set()
        ncd_threads['analyzer'].ncd_shutdown.set()

    ncd_threads['collect'].join()
    ncd_threads['monitor'].join()
    ncd_threads['analyzer'].join()
    
    nlog.info("Exiting NCD ..")    
    sys.exit(0)

if __name__ == "__main__":
    ncd_main()
