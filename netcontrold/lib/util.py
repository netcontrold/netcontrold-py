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

__all__ = ['exec_host_command',
           'variance',
           ]

# Import standard modules
import os
import sys
import signal
import subprocess

from netcontrold.lib import error


def exec_host_command(cmd):
    try:
        ret = subprocess.check_output(cmd.split())
    except subprocess.CalledProcessError, e:
        print ("Unable to execute command %s: %s" % (cmd, e))
        return 1
    return ret


def variance(_list):
    mean = sum(_list) / len(_list)
    return sum((item - mean) ** 2 for item in _list) / len(_list)


class Service:
    """
    Class to represent Service instance.
    """

    def __init__(self, cb=None, cb_args=None, pidfile=os.devnull):
        """
        Initialize Service object.

        Parameters
        ----------
        cb : function object
            service call back function
        cb_args : list
            list of args
        pidfile : string
            process ID file.
        """
        if not cb:
            print "Function callback can not be empty to start new service."
            sys.exit(1)

        self.service_cb = cb
        self.pidfile = pidfile
        self.args = cb_args

    def __exit__(self):
        print ("ncd_ctl (PID %d) stops." % os.getpid())
        return 0

    def create(self):
        """
        Create daemon for the service.
        """
        try:
            sys.argv[0] = 'ncd'
            child = os.fork()
        except OSError, e:
            sys.stderr.write("Unable to create daemon (%s)\n" % e.strerror)
            return 1

        if child == 0:
            try:
                self.service_cb(self.args)
            except error.NcdShutdownExc:
                sys.stdout.write("Netcontrold is stopped!..\n")

            sys.exit(0)
        else:
            sys.stdout.write("Started new service (PID %d) for %s\n"
                             % (child, self.service_cb.__name__))

            with open(self.pidfile, 'w') as fh:
                fh.write("%d" % child)
                fh.close()

        return 0

    def start(self):
        """
        Start the service.
        """
        pid = None

        if os.path.exists(self.pidfile):
            try:
                fh = open(self.pidfile, 'r')
            except IOError:
                sys.stderr.write("unable to open %s\n" % self.pidfile)
                sys.exit(1)

            pid = int(fh.read().strip())
            fh.close()

        if pid:
            sys.stderr.write("Service (PID %d) already running.\n" % pid)
            sys.exit(1)

        # Start the daemon
        return(self.create())

    def stop(self):
        """
        Stop the service.
        """
        try:
            fh = open(self.pidfile, 'r')
        except IOError:
            sys.stderr.write("unable to open %s\n" % self.pidfile)
            sys.exit(1)

        pid = int(fh.read().strip())
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError, e:
            if not str(e).find("No such process"):
                sys.stderr.write("unable to kill %d\n" % pid)
                sys.exit(1)

        if os.path.exists(self.pidfile):
            os.remove(self.pidfile)

        return 0

    def restart(self):
        """
        Restart the service.
        """
        self.stop()
        self.start()
