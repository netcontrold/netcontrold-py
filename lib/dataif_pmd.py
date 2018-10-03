# Copyright notice to be added
#
# This module defines interfaces that interact with Poll Mode Driver (pmd) in 
# vSwitch.

#__all__ = ['Pmd', 'pmd_obj_map']

from dataif_common import Dataif

# PMD object store.
# Every pmd is identified by .get_id().
pmd_obj_map = {}

class Pmd(Dataif):
    """
    Representation of PMD
    """
    def __init__(self):
        # Below PMD data are extracted from pmd related stats from vSwitch.
        self._id = None
        self._numa_id = None
        self._pkt_rx = None
        self._hit_emc = None
        self._hit_smc = None
        self._hit_mf = None
        self._cpp = 0
        self._pcpp = 0
        self._pc = 0
        self._isolated = False
        self._ports = []
    
        # Whether to re-balance this PMD or not.
        self._to_rebal = False
        
    
    def get_id(self):
        return self._id
    
    def set_elem(self, elemname, elemval):
        setattr(self, elemname, elemval)
    
    def add_port(self, pobj):
        self._ports.append(pobj)
    
    def del_port(self, pobj):
        self._ports.remove(pobj)
    
    def get_ports_count(self):
        return len(self._ports)

    def get_idle_ports_count(self):
        totport = 0
        for pobj in self._ports:
            totcpu = 0
            for qobj in pobj._que_list:
                totcpu += qobj._cpu_usage
            totport += 1 if totcpu else 0
        return totport
        
    def stats_to_elem(self, stat_entry):
        map_stat_elem = {
            'core_id': '_id',
            'numa_id': '_numa_id',
            'packets received': '_pkt_rx',
            'emc hits': '_hit_emc',
            'smc hits': '_hit_smc',
            'megaflow hits': '_hit_mf',
            'avg cycles per packet': '_cpp',
            'avg processing cycles per packet': '_pcpp',
            'processing cycles': '_pc',
            'isolated ': '_isolated',
            'port': '_port'
        }
        
        return map_stat_elem.get(stat_entry)
