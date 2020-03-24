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
__all__ = ['LogExc',
           'ObjCreateExc',
           'ObjParseExc',
           'ObjConsistencyExc',
           'ObjModelExc',
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
        return("%s" % self.error)


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


class ObjModelExc(NcdException):
    '''Exception raised when unable add Dataif object in modelling'''


class NcdShutdownExc(Exception):
    '''Graceful shutdown indication to ncd'''
    pass


class OsCommandExc(Exception):
    '''Exceptions caught in running OS command'''
