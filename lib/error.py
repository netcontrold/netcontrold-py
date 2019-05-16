# Copyright notice to be added
__all__ = ['LogExc',
           'ObjCreateExc',
           'ObjParseExc',
           'ObjConsistencyExc',
           'NcdShutdownExc',
           'OsCommandExc'
           ]

class NcdException(Exception):
    '''
    Base class for all exceptions
    '''
    def __init__(self, error):
        Exception.__init__(self, error)
        self.error = error
        
    def __str__(self):
        return("%s" %self.error)
    
class LogExc(NcdException):
    '''Exception raised by logging handler'''
    pass

class ObjCreateExc(NcdException):
    '''Exception raised while creating Dataif objects'''
    pass

class ObjParseExc(NcdException):
    '''Exception raised while parsing for Dataif objects'''
    pass

class ObjConsistencyExc(NcdException):
    '''Exception raised when there is inconsistency in Dataif object'''
    
class NcdShutdownExc(Exception):
    '''Graceful shutdown indication to ncd'''
    pass
class OsCommandExc(Exception):
    '''Exceptions caught in running OS command'''