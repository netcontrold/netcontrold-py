# Copyright notice to be added
#
# This module defines abstraction of interfaces that interacts with vSwitch.
# Each interface defines its own implementation of how the interaction to be
# happened. Objective of this abstraction is to provide skeleton for the data
# modeling.
from abc import abstractmethod

__all__ = ['Dataif']

class Dataif(object):
    """
    Class interface to collect data from vSwitch
    """
    def __init__(self):
        """
        Constructor for Dataif
        """
        self._id = None
        pass
    
    @abstractmethod
    def __query(self):
        """
        Interface to query all data associated with this data model
        """
        pass
    
    @abstractmethod
    def __exec_action(self, act):
        """
        Interface to execute action
        """
        act.__exec()
    
 
