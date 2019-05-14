# Copyright notice to be added
from abc import abstractmethod
from dataif_port import Port
from logger import nlog
from util import exec_host_command
import copy

__all__ = ['PmdCtrl']

# This module defines abstraction of actions that interacts sends to vSwitch.
# Each derived action has its semantic of execution.

class Ctrl(object):
    """
    Class interface to control the interface
    """
    def __init__(self):
        pass
    
    @abstractmethod
    def __exec(self):
        pass
    
    def apply_algo(self):
        pass
    

class PmdCtrl(Ctrl):
    """
    Representation of controlling Pmd.
    """
    def __init__(self):
        pass
    
    def apply_algo(self, pobj_map):
        # Refer algorithm in doc/ncd_implementation.rst
        idle_pmdobj_map = {}
        busy_pmdobj_list = []
        reload_pmdobj_list = []
        n_act = 0

        # prepare list of idle pmds
        for pmd_id in sorted(pobj_map.keys()):
            port_count = pobj_map[pmd_id].get_ports_count()
            if port_count == 0:
                nlog.info("pmd %d is empty." %pmd_id)
                idle_pmdobj_map[pmd_id] = pobj_map.pop(pmd_id)
            else:
                nlog.debug("pmd %d has %d ports" %(pmd_id, port_count))
                iport_count = pobj_map[pmd_id].get_idle_ports_count()
                if iport_count == 0:
                    nlog.info("pmd %d is idle." %pmd_id)
                    idle_pmdobj_map[pmd_id] = pobj_map.pop(pmd_id)

        # iterate each pmd now
        for pmd_id in sorted(pobj_map.keys()):
            pobj = pobj_map[pmd_id]
            # current pmd load
            try:
                pmd_load = int(pobj._pcpp/pobj._cpp * 100)
            except ZeroDivisionError:
                pmd_load = 0

            if (pmd_load > 90):
                # 100% pmd is not actually observed when there are multiple queues in it.
                nlog.debug("busy pmd %d found.." %pmd_id)
                if (len(pobj._ports) > 1):
                    if (len(idle_pmdobj_map) == 0):
                        nlog.debug("busy pmd %d is ignored.." %pmd_id)
                        busy_pmdobj_list.append(pobj)
                        continue

                    for port in pobj._ports:
                        # sorted listof rxqs based on its cpu usage
                        rxq_load_list = sorted(port._que_list,
                            key=lambda o: o._cpu_usage * int(pobj._pcpp))
                
                        for rxq in rxq_load_list:
                            if (rxq._cpu_usage <= (100/len(pobj._ports)) and len(idle_pmdobj_map)):
                                # try to assign idle pmd from same numa
                                for id, pmd in idle_pmdobj_map.items():
                                    if port._numa_id == pmd._numa_id:
                                        ipmd_id, ipmd = idle_pmdobj_map.pop(id)
                                        break
                                else:
                                    ipmd_id, ipmd = idle_pmdobj_map.popitem()

                                # move less busy rxq into first idle PMD
                                nport = copy.deepcopy(port)
                                nport.del_queue(nport.get_queue(rxq._id))
                                nport.add_queue(rxq._id)
                                nque = nport.get_queue(rxq._id)
                                nque.set_cpu_usage(rxq.get_cpu_usage())
                                ipmd.add_port(nport)
                                port.del_queue(rxq)
                                if not len(port._que_list):
                                    pobj.del_port(port)

                                nlog.info("rxq %d (port %s) is moved into idle pmd %d .."
                                    %(rxq.get_id(), port.get_name(), ipmd_id))
                                reload_pmdobj_list.append(ipmd)
                                n_act += 1


        # update idle pmd ports for rest of the queues from original mapping
        port_to_pmdq = {}
        for pmd_id in sorted(pobj_map.keys()):
            pobj = pobj_map[pmd_id]
            for port in pobj._ports:
                qid = port._que_list[0]._id
                if port.get_id() in port_to_pmdq:
                    port_to_pmdq[port.get_id()] += ",%d:%d" %(qid, pmd_id)
                else:
                    port_to_pmdq[port.get_id()] = "%d:%d" %(qid, pmd_id)
                
        for pobj in reload_pmdobj_list:
            for port in pobj._ports:
                aff_str = ""
                for rxq in port._que_list:
                    aff_str += "%d:%d," %(rxq.get_id(), pobj.get_id())
                    if port_to_pmdq.has_key(port.get_id()):
                        aff_str += port_to_pmdq[port.get_id()]

                cmd = "ovs-vsctl set Interface %s other_config:pmd-rxq-affinity=%s" %(port, aff_str)
                nlog.critical("executing %s" %cmd)
                exec_host_command(cmd)

        return n_act
