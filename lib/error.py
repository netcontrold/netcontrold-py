# Copyright notice to be added
__all__ = ['LoggerError',
           'PmdObjCreateError',
           'NCDShutdown'
           ]

class Error(Exception):
    '''
    Base class for all exceptions
    '''
    def __init__(self, error):
        Exception.__init__(self, error)
        self.error = error
        
    def __str__(self):
        return("%s" %self.error)
    
class LoggerError(Error):
    '''Exception raised by logging handler'''
    pass

class PmdObjCreateError(Error):
    '''Exception raised while creating PMD objects'''
    pass

class ParseError(Error):
    '''Exception raised while parsing logs'''
    pass

class NCDShutdown(Exception):
    '''
    Graceful shutdown indication to ncd
    '''
    pass
