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
           'exists',
           'variance',
           'rr_cpu_in_numa',
           ]

# Import standard modules
import os
import re
import sys
import socket
import signal
import subprocess
import distutils.spawn
import threading

from netcontrold.lib import error
from netcontrold.lib import config


class Memoize:
    """
    Class to cache function returns.
    """

    forgot = False

    def __init__(self, fn):
        self._fn = fn
        self._cache = dict()

    def __call__(self, *args):
        if (type(self).forgot) or (args not in self._cache):
            self._cache[args] = self._fn(*args)

        return self._cache[args]


def cpuinfo():
    proc_list = []
    with open('/proc/cpuinfo') as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if line == '':
            continue

        regex = re.compile('^(.*?)\s*:\s*(.*)')
        (param, val) = regex.match(line).groups()

        if ((param == 'processor' and val == '') or
            (param == 'core id' and val == '') or
                (param == 'physical id' and val == '')):
            raise ValueError("Value %s cannot be null" % (param))

        if param == 'processor':
            proc_list.append({})

        if(len(proc_list) >= 1):
            proc_list[-1][param] = val
        else:
            raise ValueError("proc_list cannot be empty")

    f.close()
    return proc_list


def numa_cpu_map():
    cpu_list = cpuinfo()
    numa_map = dict()

    for cpu in cpu_list:
        pid = int(cpu['processor'])
        cid = int(cpu['core id'])
        nid = int(cpu['physical id'])

        if nid not in numa_map:
            numa_map[nid] = {}

        if cid not in numa_map[nid]:
            numa_map[nid][cid] = []

        core = numa_map[nid][cid]
        if pid not in core:
            core.append(pid)

    return numa_map


@Memoize
def rr_cpu_in_numa():
    numa_map = numa_cpu_map()
    numa_cpus = []

    for cpus in numa_map.values():
        list = sorted(cpus.values())
        numa_cpus += list

    return sum(numa_cpus, [])


def exec_host_command(cmd):
    try:
        ret = subprocess.check_output(cmd.split()).decode()
    except subprocess.CalledProcessError as e:
        print("Unable to execute command %s: %s" % (cmd, e))
        return 1
    return ret


def exists(file):
    return distutils.spawn.find_executable(file) is not None


def variance(_list):
    mean = sum(_list) / len(_list)
    return sum((item - mean) ** 2 for item in _list) / len(_list)


class Thread(threading.Thread):
    """
    Class to represent thread instance.
    """

    timeout = 60

    def __init__(self, shuteventobj):
        threading.Thread.__init__(self)
        self.ncd_shutdown = shuteventobj


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
            print("Function callback can not be empty to start new service.")
            sys.exit(1)

        self.service_cb = cb
        self.pidfile = pidfile
        self.args = cb_args

    def __exit__(self):
        print("ncd_ctl (PID %d) stops." % os.getpid())
        return 0

    def create(self):
        """
        Create daemon for the service.
        """
        try:
            sys.argv[0] = 'ncd'
            child = os.fork()
        except OSError as e:
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
        except OSError as e:
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

    def config(self):
        """
        Query current config of netcontrold.
        """
        sock_file = config.ncd_socket

        if not os.path.exists(sock_file):
            sys.stderr.write("socket %s not found.. exiting.\n" % sock_file)
            sys.exit(1)

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(sock_file)
        except socket.error as e:
            sys.stderr.write("unable to connect %s: %s\n" % (sock_file, e))
            sys.exit(1)

        try:
            sock.sendall(b"CTLD_CONFIG")
            ack_len = 0
            while (ack_len < len("CTLD_DATA_ACK XXXXXX")):
                data = sock.recv(len("CTLD_DATA_ACK XXXXXX"))
                ack_len += len(data)

            status_len = int(re.findall('\d+', data.decode())[0])
            data_len = 0
            while (data_len < status_len):
                data = sock.recv(status_len).decode()
                data_len += len(data)

            sys.stdout.write(data)

        finally:
            sock.close()

        return 0

    def rebalance(self, rebal_flag):
        """
        Enable or disable rebalance mode.
        """
        sock_file = config.ncd_socket

        if not os.path.exists(sock_file):
            sys.stderr.write("socket %s not found.. exiting.\n" % sock_file)
            sys.exit(1)

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(sock_file)
        except socket.error as e:
            sys.stderr.write("unable to connect %s: %s\n" % (sock_file, e))
            sys.exit(1)

        try:
            if rebal_flag:
                sock.sendall(b"CTLD_REBAL_ON")
            else:
                sock.sendall(b"CTLD_REBAL_OFF")

            ack_len = 0
            while (ack_len < len("CTLD_ACK")):
                data = sock.recv(64)
                ack_len += len(data)

        finally:
            sock.close()

        return 0

    def rebalance_quick(self, quick_flag):
        """
        Enable or disable quick rebalance.
        """
        sock_file = config.ncd_socket

        if not os.path.exists(sock_file):
            sys.stderr.write("socket %s not found.. exiting.\n" % sock_file)
            sys.exit(1)

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(sock_file)
        except socket.error as e:
            sys.stderr.write("unable to connect %s: %s\n" % (sock_file, e))
            sys.exit(1)

        try:
            if quick_flag:
                sock.sendall(b"CTLD_REBAL_QUICK_ON")
            else:
                sock.sendall(b"CTLD_REBAL_QUICK_OFF")

            ack_len = 0
            while (ack_len < len("CTLD_ACK")):
                data = sock.recv(64)
                ack_len += len(data)

        finally:
            sock.close()

        return 0

    def trace(self, trace_flag):
        """
        Enable or disable trace mode.
        """
        sock_file = config.ncd_socket

        if not os.path.exists(sock_file):
            sys.stderr.write("socket %s not found.. exiting.\n" % sock_file)
            sys.exit(1)

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(sock_file)
        except socket.error as e:
            sys.stderr.write("unable to connect %s: %s\n" % (sock_file, e))
            sys.exit(1)

        try:
            if trace_flag:
                sock.sendall(b"CTLD_TRACE_ON")
            else:
                sock.sendall(b"CTLD_TRACE_OFF")

            ack_len = 0
            while (ack_len < len("CTLD_ACK")):
                data = sock.recv(64)
                ack_len += len(data)

        finally:
            sock.close()

        return 0

    def verbose(self, vrb_flag):
        """
        Enable or disable verbose logging.
        """
        sock_file = config.ncd_socket

        if not os.path.exists(sock_file):
            sys.stderr.write("socket %s not found.. exiting.\n" % sock_file)
            sys.exit(1)

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(sock_file)
        except socket.error as e:
            sys.stderr.write("unable to connect %s: %s\n" % (sock_file, e))
            sys.exit(1)

        try:
            if vrb_flag:
                sock.sendall(b"CTLD_VERBOSE_ON")
            else:
                sock.sendall(b"CTLD_VERBOSE_OFF")

            ack_len = 0
            while (ack_len < len("CTLD_ACK")):
                data = sock.recv(64)
                ack_len += len(data)

        finally:
            sock.close()

        return 0

    def status(self):
        """
        Query current status of netcontrold.
        """
        sock_file = config.ncd_socket

        if not os.path.exists(sock_file):
            sys.stderr.write("socket %s not found.. exiting.\n" % sock_file)
            sys.exit(1)

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(sock_file)
        except socket.error as e:
            sys.stderr.write("unable to connect %s: %s\n" % (sock_file, e))
            sys.exit(1)

        try:
            sock.sendall(b"CTLD_STATUS")
            ack_len = 0
            while (ack_len < len("CTLD_DATA_ACK XXXXXX")):
                data = sock.recv(len("CTLD_DATA_ACK XXXXXX"))
                ack_len += len(data)

            status_len = int(re.findall('\d+', data.decode())[0])
            data_len = 0
            while (data_len < status_len):
                data = sock.recv(status_len).decode()
                data_len += len(data)

            sys.stdout.write(data)

        finally:
            sock.close()

        return 0

    def version(self):
        """
        Get version of netcontrold.
        """
        sock_file = config.ncd_socket

        if not os.path.exists(sock_file):
            sys.stderr.write("socket %s not found.. exiting.\n" % sock_file)
            sys.exit(1)

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(sock_file)
        except socket.error as e:
            sys.stderr.write("unable to connect %s: %s\n" % (sock_file, e))
            sys.exit(1)

        try:
            sock.sendall(b"CTLD_VERSION")
            ack_len = 0
            while (ack_len < len("CTLD_DATA_ACK XXXXXX")):
                data = sock.recv(len("CTLD_DATA_ACK XXXXXX"))
                ack_len += len(data)

            status_len = int(re.findall('\d+', data.decode())[0])
            data_len = 0
            while (data_len < status_len):
                data = sock.recv(status_len).decode()
                data_len += len(data)

            sys.stdout.write(data)

        finally:
            sock.close()

        return 0
