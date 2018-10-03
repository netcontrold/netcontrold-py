# Copyright notice to be added
#
# Port representation in vSwitch
#

from error import PmdObjCreateError

__all__ = ['RxQueue']

class RxQueue(object):
    """
    Representation of queue
    """
    def __init__(self, id=None):
        if id is None:
            raise PmdObjCreateError("RxQ id can not be empty")
        self._id = id
        self._port = None
        self._cpu_usage = None
        
    def get_id(self):
        return self._id
           
    def get_port(self):
        return self._port
    
    def set_port(self, pobj):
        self._port = pobj
        
    def get_cpu_usage(self):
        return self._cpu_usage
    
    def set_cpu_usage(self, cu):
        self._cpu_usage = cu
            
class Port(object):
    """
    Representation of port
    """
    def __init__(self, name=None, id=None):
        self._id = id
        self._name = name
        self._numa_id = None
        self._que_list = []
        self._pkt_rx = None
            
    def get_id(self):
        return self._id

    def get_name(self):
        return self._name
    
    def __repr__(self):
        return self._name
    
    def get_numa_id(self):
        return self._numa_id
    
    def add_queue(self, qid):
        qobj = RxQueue(int(qid))
        self._que_list.insert(0, qobj)
        qobj.set_port(self)
        return 0
    
    def del_queue(self, qobj):
        self._que_list.remove(qobj)
        return 0
    
    def get_queue(self, _id=0):
        qobj = None
        for q in self._que_list:
            if q._id == int(_id):
                qobj = q

        return qobj
