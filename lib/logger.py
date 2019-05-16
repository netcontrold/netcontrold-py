# Copyright notice to be added
#

import inspect
import datetime
from error import LogExc

__all__ = ['Logger']

class Logger(object):
    """
    Log abstract for different mechanisms in reporting tool behavior.
    """
    def __init__(self,level=0):
        """
        Constructor of Log.
        
        Parameter:
        level - defines the amount of verboseness in reporting logs
            Value 0 - Info (Default)
            Value 1 - Warning
            Value 2 - Critical
        
        Return:
        Log instance. 
        """
        self.set_level(level)
        
    def set_level(self, level):
        """
        Set new level in Log instance.
        
        Parameter:
        level - new log level to be set.
        
        Return:
        None
        """
        
        if not (0 <= level <= 2):
            raise LogExc("Unsupported log level %d. Specifiy 0, 1 or 2 only")
                
        self.__level = level
        
    def __log(self, level, *args):
        """
        Called of this function wants to log a message.
        """
        if (len(args) == 1):
            args = args[0]
            if (len(args) == 1):
                args = args[0]

        # at present, we do only logging in console
        stack = inspect.stack()
        if 'self' in stack[2][0].f_locals:
            banner = "%s.%s" %(
                stack[2][0].f_locals["self"].__class__.__name__,
                stack[2][0].f_code.co_name)
        else:
            banner = stack[2][0].f_code.co_name

        if (self.__level >= 2):
            return "%s %s: %s" %(datetime.datetime.utcnow(),
                banner, args)
        else:
            return "%s: %s" %(banner, args)

    def info(self, *args):
        """
        Information be shown
        """
        if (self.__level >= 0):
            print self.__log(0, args)
    
    def debug(self, *args):
        """
        Information along with debug info shown
        """
        if (self.__level >= 1):
            print self.__log(1, args)

    def critical(self, *args):
        """
        Critical info be shown. Useful to debug whole code path.
        """
        if (self.__level >= 2):
            print self.__log(2, args)
