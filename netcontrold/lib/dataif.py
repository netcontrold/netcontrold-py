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

__all__ = ['get_pmd_stats',
           'get_pmd_rxqs',
           'get_port_stats',
           'Context'
           ]

import re
import copy
from netcontrold.lib import util

from netcontrold.lib import config
from netcontrold.lib.error import ObjCreateExc, ObjParseExc,\
    ObjConsistencyExc, ObjModelExc, OsCommandExc


class Context():
    pmd_map = {}
    port_to_id = {}
    port_to_cls = {}
    nlog = None
    last_ts = None
    events = []
    log_handler = None


nlog = Context.nlog


class Rxq(object):
    """
    Class to represent the RXQ in the port of a vswitch.

    Attributes
    ----------
    id : int
        id of the rxq
    port : object
        instance of Port class.
        every rxq must be one of the members in port.rxq_map
    """

    def __init__(self, _id=None):
        """
        Initialize Dataif_Rxq object.

        Parameters
        ----------
        _id : int
            the id of the rxq

        Raises
        ------
        ObjCreateExc
            if no id is given as input.
        """

        if _id is None:
            raise ObjCreateExc("Rxq id can not be empty")

        self.id = _id
        self.port = None


class Dataif_Rxq(Rxq):
    """
    Class to represent the RXQ in the datapath of vswitch.

    Attributes
    ----------
    pmd : object
        instance of Dataif_Pmd class.
        rxq's current association with this pmd before rebalance.
    cpu_cyc: list
        cpu cycles used by this rxq in each sampling interval.
    """

    def __init__(self, _id=None):
        """
        Initialize Dataif_Rxq object.

        Parameters
        ----------
        _id : int
            the id of the rxq
        """

        super(Dataif_Rxq, self).__init__(_id)

        self.pmd = None
        self.cpu_cyc = [0, ] * int(config.ncd_samples_max)
        self.rx_cyc = [0, ] * int(config.ncd_samples_max)


class Port(object):
    """
    Class to represent the port in the vswitch.

    Attributes
    ----------
    name : str
        name of this port
    id : int
        id of the port (as in vswitch db)
    numa_id : int
        numa that this port is associated with.
    rxq_map : dict
        map of rxqs that this port is associated with.

    Methods
    -------
    find_rxq_by_id(_id)
        returns rxq associated with this port.
    add_rxq(_id)
        add new rxq or return one if available.
    del_rxq(_id)
        delete rxq from this port.
    """

    def __init__(self, name=None):
        """
        Initialize Port object.

        Parameters
        ----------
        name : str
            the name of the port

        Raises
        ------
        ObjCreateExc
            if no name is given as input.
        """

        if name is None:
            raise ObjCreateExc("Port name can not be empty")

        self.name = name
        self.id = None
        self.numa_id = None
        self.rxq_map = {}

    def find_rxq_by_id(self, _id):
        """
        Return Dataif_Rxq of this id if available in port.rxq_map.
        Otherwise none returned.

        Parameters
        ----------
        _id : int
            id of rxq to search.
        """

        if _id in self.rxq_map:
            return self.rxq_map[_id]

        return None

    def add_rxq(self, _id):
        """
        Add new Dataif_Rxq object for this id in port.rxq_map, if one
        is not already available.

        Parameters
        ----------
        _id : int
            id of rxq to be added.
        """

        # check if this rxq is already available.
        rxq = self.find_rxq_by_id(_id)
        if rxq:
            raise ObjConsistencyExc(
                "rxq %d already exists in %s" % (_id, self.name))

        # create new rxq and add it in our rxq_map.
        rxq = Dataif_Rxq(_id)
        self.rxq_map[_id] = rxq

        # remember the port this rxq is tied with.
        rxq.port = self

        return rxq

    def del_rxq(self, _id):
        """
        Delete Dataif_Rxq object of this id from port.rxq_map.

        Parameters
        ----------
        _id : int
            id of rxq to be deleted.

        Raises
        ------
        ObjConsistencyExc
            if no such rxq is not already available.
        """

        # check if this rxq is already available.
        rxq = self.find_rxq_by_id(_id)
        if not rxq:
            raise ObjConsistencyExc("rxq %d not found" % _id)

        # remove rxq from its map.
        self.rxq_map.pop(_id, None)


def make_dataif_port(port_name=None):
    """
    Factory method to create a class with Port attributes for a given port.
    """

    class Meta(type):

        def __repr__(cls):
            if hasattr(cls, '__cls_repr__'):
                return getattr(cls, '__cls_repr__')()
            else:
                super(Meta, cls).__repr__()

    # Inherit attributes of Port and create a new class.
    class Dataif_Port(Port):
        """
        Class to represent the port in the datapath of vswitch.

        Attributes
        ----------
        name : string
            name of the port the class is created for.
        type: str
            type of this port.
        rx_cyc : list
            samples of packets by this port in RX.
        rx_drop_cyc : list
            samples of dropped packets by this port in RX.
        tx_cyc : list
            samples of packets by this port in TX.
        tx_drop_cyc : list
            samples of dropped packets by this port in TX.
        tx_retry_cyc : list
            samples of transmit retry by this port in TX.
        cyc_idx : int
            current sampling index.
        rxq_rebalanced : dict
            map of PMDs that its each rxq will be associated with.
        rebalance : bool
            in rebalance or not.
        """

        __metaclass__ = Meta

        name = port_name
        type = None
        rx_cyc = [0, ] * int(config.ncd_samples_max)
        rx_drop_cyc = [0, ] * int(config.ncd_samples_max)
        tx_cyc = [0, ] * int(config.ncd_samples_max)
        tx_drop_cyc = [0, ] * int(config.ncd_samples_max)
        tx_retry_cyc = [0, ] * int(config.ncd_samples_max)
        cyc_idx = 0
        rebalance = False

        def __init__(self):
            """
            Initialize Dataif_Port object.

            """
            super(Dataif_Port, self).__init__(self.name)
            self.rxq_rebalanced = {}

        def __eq__(self, other):
            """
            Define the method to compare between objects of this class.
            """
            if not isinstance(other, self.__class__):
                return False

            if not ((self.name == other.name) and
                    (self.type == other.type) and
                    (self.rxq_rebalanced == other.rxq_rebalanced)):
                return False

            # all equals otherwise.
            return True

        def __ne__(self, other):
            return not self.__eq__(other)

        @classmethod
        def __cls_repr__(cls):
            pstr = ""
            pstr += "port %s\n" % cls.name
            pstr += "port %s cyc_idx %d\n" % (cls.name, cls.cyc_idx)
            for i in range(0, len(cls.rx_drop_cyc)):
                rx = cls.rx_cyc[i]
                rxd = cls.rx_drop_cyc[i]
                pstr += "port %s rx_cyc[%d] %d rx_drop_cyc[%d] %d\n" \
                        % (cls.name, i, rx, i, rxd)

            for i in range(0, len(cls.tx_drop_cyc)):
                tx = cls.tx_cyc[i]
                txd = cls.tx_drop_cyc[i]
                pstr += "port %s tx_cyc[%d] %d tx_drop_cyc[%d] %d\n" \
                        % (cls.name, i, tx, i, txd)

            for i in range(0, len(cls.tx_retry_cyc)):
                tx_retry = cls.tx_retry_cyc[i]
                pstr += "port %s tx_retry_cyc[%d] %d\n" \
                        % (cls.name, i, tx_retry)

            return pstr

    if port_name not in Context.port_to_cls:
        Context.port_to_cls[port_name] = Dataif_Port

    return Dataif_Port


class Dataif_Pmd(object):
    """
    Class to represent the PMD thread in the datapath of vswitch.

    Attributes
    ----------
    id : int
        id of the pmd (i.e cpu core id it is pinned)
    numa_id : int
        numa that this pmd is associated with.
    rx_cyc : list
        samples of packets received by this pmd.
    idle_cpu_cyc : list
        samples of idle cpu cycles consumed by this pmd.
    proc_cpu_cyc : list
        samples of processing cpu cycles consumed by this pmd.
    cyc_idx : int
        current sampling index.
    isolated : bool
        whether this pmd is isolated from auto rebalance of vswitch.
    pmd_load : int
        how busy the pmd is.
    port_map : dict
        map of ports associated with this pmd, through rxq(s)
        of this port.

    Methods
    -------
    find_port_by_name(name)
        returns port of this name associated with this pmd.
    find_port_by_id(id)
        returns port of this id associated with this pmd.
    add_port(name)
        add new port or return one if available.
    del_port(name)
        delete port from this pmd.
    count_rxq()
        returns count of all rxqs associated with this pmd.
    """

    def __init__(self, _id=None):
        """
        Initialize Dataif_Pmd object.

        Parameters
        ----------
        _id : int
            id of the pmd.

        Raises
        ------
        ObjCreateExc
            if no name is given as input.
        """

        if _id is None:
            raise ObjCreateExc("PMD id can not be empty")

        self.id = _id
        self.numa_id = None
        self.rx_cyc = [0, ] * int(config.ncd_samples_max)
        self.idle_cpu_cyc = [0, ] * int(config.ncd_samples_max)
        self.proc_cpu_cyc = [0, ] * int(config.ncd_samples_max)
        self.cyc_idx = 0
        self.isolated = None
        self.pmd_load = 0
        self.port_map = {}

    def __repr__(self):
        pstr = ""
        pstr += "pmd %d\n" % self.id
        pstr += "pmd %d numa_id %d\n" % (self.id, self.numa_id)
        for i in range(0, len(self.rx_cyc)):
            elm = self.rx_cyc[i]
            pstr += "pmd %d rx_cyc[%d] %d\n" % (self.id, i, elm)
        for i in range(0, len(self.idle_cpu_cyc)):
            elm = self.idle_cpu_cyc[i]
            pstr += "pmd %d idle_cpu_cyc[%d] %d\n" % (self.id, i, elm)
        for i in range(0, len(self.proc_cpu_cyc)):
            elm = self.proc_cpu_cyc[i]
            pstr += "pmd %d proc_cpu_cyc[%d] %d\n" % (self.id, i, elm)
        pstr += "pmd %d cyc_idx %d\n" % (self.id, self.cyc_idx)
        pstr += "pmd %d isolated %s\n" % (self.id, self.isolated)
        pstr += "pmd %d pmd_load %d\n" % (self.id, self.pmd_load)
        for port_name, port in self.port_map.items():
            pstr += "  port %s\n" % (port_name)
            pstr += "  port %s numa_id %d\n" % (port_name, port.numa_id)
            for rxq_id, rxq in port.rxq_map.items():
                pstr += "    rxq %d\n" % rxq_id
                for i in range(0, len(rxq.cpu_cyc)):
                    elm = rxq.rx_cyc[i]
                    pstr += "    rxq %d rx_cyc[%d] %d\n" % (rxq_id, i, elm)
                    elm = rxq.cpu_cyc[i]
                    pstr += "    rxq %d cpu_cyc[%d] %d\n" % (rxq_id, i, elm)
        return pstr

    def __eq__(self, other):
        """
        Define the method to compare between objects of this class.
        """
        if not isinstance(other, self.__class__):
            return False

        if not ((self.id == other.id) and
                (self.numa_id == other.numa_id) and
                (sorted(self.rx_cyc) == sorted(other.rx_cyc)) and
                (sorted(self.idle_cpu_cyc) == sorted(other.idle_cpu_cyc)) and
                (sorted(self.proc_cpu_cyc) == sorted(other.proc_cpu_cyc)) and
                (self.isolated == other.isolated) and
                (self.pmd_load == other.pmd_load) and
                (self.port_map == other.port_map)):
            return False

        # all equals otherwise.
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def find_port_by_name(self, name):
        """
        Return Dataif_Port of this name, if available in pmd.port_map .
        Otherwise none returned.

        Parameters
        ----------
        name : str
            name of the port to be searched.
        """

        if name in self.port_map:
            return self.port_map[name]

        return None

    def find_port_by_id(self, _id):
        """
        Return Dataif_Port of this _id, if available in pmd.port_map .
        Otherwise none returned.

        Parameters
        ----------
        _id : int
            id of the port to be searched.
        """

        for port in self.port_map.values():
            if port.id == _id:
                return port

        return None

    def add_port(self, name, _id=None, numa_id=None):
        """
        Add new Dataif_Port for this name in pmd.port_map, if one
        is not already available.

        Parameters
        ----------
        name : str
            name of the port to be added.
        _id : int, optional
            id of the port (default is None)
        numa_id : int, optional
            numa id associated with this port (default is None)
        """

        # check if a port of this name already exists.
        port = self.find_port_by_name(name)
        if port:
            raise ObjConsistencyExc(
                "port %s already exists in pmd %d" % (name, self.id))

        # create new port and add it in port_map.
        port_cls = Context.port_to_cls[name]
        port = port_cls()
        self.port_map[name] = port

        # store other input options.
        # TODO: port numa could actually be from sysfs to avoid
        #       any configuration fault.
        port.id = _id
        port.numa_id = numa_id

        return port

    def del_port(self, name):
        """
        Delete Dataif_Port object of this name from pmd.port_map.

        Parameters
        ----------
        name : str
            name of the port to be deleted.

        Raises
        ------
        ObjConsistencyExc
            if no such port is not already available.
        """

        # check if port of this name is already available.
        port = self.find_port_by_name(name)
        if not port:
            raise ObjConsistencyExc("port %s not found" % name)

        # remove this port from port map.
        self.port_map.pop(name, None)

    def count_rxq(self):
        """
        Returns the number of rxqs (of all the ports) pinned with
        this pmd.
        """

        n_rxq = 0

        # aggregate the number of rxqs in each port.
        for port in self.port_map.values():
            n_rxq += len(port.rxq_map)

        return n_rxq


def pmd_load(pmd):
    """
    Calculate pmd load.

    Parameters
    ----------
    pmd : object
        Dataif_Pmd object.
    """

    # Given we have samples of rx packtes, processing and idle cpu
    # cycles of a pmd, calculate load on this pmd.
    # sort counters so that, incremental differences calculated.
    sort_rx_cyc = pmd.rx_cyc[:]
    sort_rx_cyc.sort()
    sort_idle_cyc = pmd.idle_cpu_cyc[:]
    sort_idle_cyc.sort()
    sort_proc_cyc = pmd.proc_cpu_cyc[:]
    sort_proc_cyc.sort()

    rx_sum = sum([j - i for i, j in zip(sort_rx_cyc[:-1], sort_rx_cyc[1:])])
    if rx_sum == 0:
        # no activity without any packet.
        return 0

    idle_sum = sum(
        [j - i for i, j in zip(sort_idle_cyc[:-1], sort_idle_cyc[1:])])
    proc_sum = sum(
        [j - i for i, j in zip(sort_proc_cyc[:-1], sort_proc_cyc[1:])])

    cpp = (idle_sum + proc_sum) / rx_sum
    if cpp == 0:
        # when pmd do not have any rxq configured, dry-run
        # adds proc cpu or deletes idle cpu cycles when
        # assigning rxqs virtually, hence their sum is null.
        # we safely declare this pmd busy (we are still in dry-run).
        pmd_load = 100
    else:
        pcpp = proc_sum / rx_sum
        pmd_load = float((pcpp * 100) / cpp)

    return pmd_load


def update_pmd_load(pmd_map):
    """
    Update pmd for its current load level.

    Parameters
    ----------
    pmd_map : dict
        mapping of pmd id and its Dataif_Pmd object.
    """
    for pmd in pmd_map.values():
        pmd.pmd_load = pmd_load(pmd)

    return None


def pmd_load_variance(pmd_map):
    """
    Get load variance on a set of pmds.

    Parameters
    ----------
    pmd_map : dict
        mapping of pmd id and its Dataif_Pmd object.
    """
    pmd_load_list = list(map(lambda o: o.pmd_load, pmd_map.values()))
    return util.variance(pmd_load_list)


def pmd_need_rebalance(pmd_map):
    """
    Check whether all the pmds have load below its threshold.

    Parameters
    ----------
    pmd_map : dict
        mapping of pmd id and its Dataif_Pmd object.
    """

    nlog = Context.nlog
    pmd_loaded = 0
    for pmd in pmd_map.values():
        if (pmd.pmd_load >= config.ncd_pmd_core_threshold and
                pmd.count_rxq() > 1):
            nlog.debug("pmd %d is loaded more than %d threshold" %
                       (pmd.id, config.ncd_pmd_core_threshold))
            pmd_loaded += 1

    if (len(pmd_map) > pmd_loaded > 0):
        return True

    return False


def get_pmd_stats(pmd_map):
    """
    Collect stats on every pmd running in the system and update
    pmd_map. In every sampling iteration, these stats are stored
    in corresponding sampling slots.

    Parameters
    ----------
    pmd_map : dict
        mapping of pmd id and its Dataif_Pmd object.

    Raises
    ------
    OsCommandExc
        if the given OS command did not succeed for some reason.
    ObjConsistencyExc
        if state of pmds in ncd differ.
    ObjModleExc
        if state of pmds in switch differ.
    """

    nlog = Context.nlog

    # retrieve required data from the vswitch.
    cmd = "ovs-appctl dpif-netdev/pmd-stats-show"
    data = util.exec_host_command(cmd)
    if not data:
        raise OsCommandExc("unable to collect data")

    # current state of pmds
    cur_pmd_l = sorted(pmd_map.keys())

    # sname and sval stores parsed string's key and value.
    sname, sval = None, None
    # current pmd object to be used in every line under parse.
    pmd = None

    for line in data.splitlines():
        if line.startswith("pmd thread"):
            # In below matching line, we retrieve core id (aka pmd id)
            # and core id.
            linesre = re.search(r'pmd thread numa_id (\d+) core_id (\d+):',
                                line)
            numa_id = int(linesre.groups()[0])
            core_id = int(linesre.groups()[1])

            # If in mid of sampling, we should have pmd_map having
            # entry for this core id.
            if core_id in pmd_map:
                pmd = pmd_map[core_id]

                # Check to ensure we are good to go as local should
                # always be used.
                assert(pmd.numa_id == numa_id)

                # Store following stats in new sampling slot.
                pmd.cyc_idx = (pmd.cyc_idx + 1) % config.ncd_samples_max
                nlog.debug("pmd %d in iteration %d" % (pmd.id, pmd.cyc_idx))
            else:
                # Very first sampling for each pmd occur in this
                # clause. Just ensure, no new pmd is added from system
                # reconfiguration.
                if len(pmd_map) != 0 and not pmd:
                    raise ObjConsistencyExc(
                        "trying to add new pmd %d in mid of ncd!.. aborting! ")

                # create new entry in pmd_map for this pmd.
                pmd = Dataif_Pmd(core_id)
                pmd_map[pmd.id] = pmd
                nlog.debug("added pmd %s stats.." % pmd.id)

                # numa id of pmd is of core's.
                pmd.numa_id = numa_id
        elif line.startswith("main thread"):
            # end of pmd stats
            break
        else:
            # From other lines, we retrieve stats of the pmd.
            (sname, sval) = line.split(":")
            sname = re.sub("^\s+", "", sname)
            sval = sval[1:].split()
            if sname == "packets received":
                pmd.rx_cyc[pmd.cyc_idx] = int(sval[0])
            elif sname == "idle cycles":
                pmd.idle_cpu_cyc[pmd.cyc_idx] = int(sval[0])
            elif sname == "processing cycles":
                pmd.proc_cpu_cyc[pmd.cyc_idx] = int(sval[0])

    # new state of pmds.
    new_pmd_l = sorted(pmd_map.keys())

    # skip modelling this object if states differ.
    if len(cur_pmd_l) > 0 and cur_pmd_l != new_pmd_l:
        raise ObjModelExc("pmds count differ")

    return pmd_map


def get_pmd_rxqs(pmd_map):
    """
    Collect info on how rxq is pinned with pmd, from the vswitch.

    Parameters
    ----------
    pmd_map : dict
        mapping of pmd id and its Dataif_Pmd object.

    Raises
    ------
    OsCommandExc
        if the given OS command did not succeed for some reason.
    ObjConsistencyExc
        if state of pmds in ncd differ.
    ObjParseExc
        if unable to retrieve info from switch.
    ObjModleExc
        if state of pmds in switch differ.
    """

    nlog = Context.nlog

    # retrieve required data from the vswitch.
    cmd = "ovs-appctl dpif-netdev/pmd-rxq-show"
    data = util.exec_host_command(cmd)
    if not data:
        raise OsCommandExc("unable to collect data")

    # current state of pmds
    cur_pmd_l = sorted(pmd_map.keys())

    # sname and sval stores parsed string's key and value.
    sname, sval = None, None
    # current pmd object to be used in every line under parse.
    pmd = None

    for line in data.splitlines():
        if line.startswith('pmd thread'):
            # In below matching line, we retrieve core id (aka pmd id)
            # and core id.
            linesre = re.search(r'pmd thread numa_id (\d+) core_id (\d+):',
                                line)
            numa_id = int(linesre.groups()[0])
            core_id = int(linesre.groups()[1])
            if core_id not in pmd_map:
                raise ObjConsistencyExc(
                    "trying to add new pmd %d in mid of ncd!.. aborting! ")
            pmd = pmd_map[core_id]
            assert(pmd.numa_id == numa_id)
            nlog.debug("pmd %d in iteration %d" % (pmd.id, pmd.cyc_idx))

        elif re.match(r'\s.*port: .*', line):
            # From this line, we retrieve cpu usage of rxq.
            linesre = re.search(r'\s.*port:\s([A-Za-z0-9_-]+)\s*'
                                r'queue-id:\s*(\d+)\s*'
                                r'pmd usage:\s*(\d+|NOT AVAIL)\s*?',
                                line)

            pname = linesre.groups()[0]
            qid = int(linesre.groups()[1])
            try:
                qcpu = int(linesre.groups()[2])
            except ValueError:
                qcpu = linesre.groups()[2]
                if (qcpu == 'NOT AVAIL'):
                    raise ObjParseExc("pmd usage unavailable for now")
                else:
                    raise ObjParseExc("error parsing line %s" % line)

            # get the Dataif_Port owning this rxq.
            port = pmd.find_port_by_name(pname)
            if not port:
                port = pmd.add_port(pname)

            # update port attributes now.
            port.id = Context.port_to_id[pname]
            port.numa_id = pmd.numa_id

            port_cls = Context.port_to_cls[pname]
            port_cls.rebalance = True

            # check whether this rxq was being rebalanced.
            if qid in port.rxq_rebalanced:
                raise ObjConsistencyExc(
                    "stale %s object found while parsing rxq in pmd ..")
            else:
                # port not in rebalancing state, so update rxq for its
                # cpu cycles consumed by it.
                rxq = (port.find_rxq_by_id(qid) or port.add_rxq(qid))
                rxq.pmd = pmd
                rxq.port = port
                cur_idx = pmd.cyc_idx
                prev_idx = (cur_idx - 1) % config.ncd_samples_max
                rx_diff = pmd.rx_cyc[cur_idx] - pmd.rx_cyc[prev_idx]
                cpu_diff = pmd.proc_cpu_cyc[
                    cur_idx] - pmd.proc_cpu_cyc[prev_idx]
                qcpu = (qcpu * cpu_diff) / 100
                qrx = (qcpu * rx_diff) / 100

            rxq.cpu_cyc[pmd.cyc_idx] = qcpu
            rxq.rx_cyc[pmd.cyc_idx] = qrx
        else:
            # From other line, we retrieve isolated flag.
            (sname, sval) = line.split(":")
            sname = re.sub("^\s+", "", sname)
            assert(sname == 'isolated ')
            pmd.isolated = {'true': True, 'false': False}[sval[1:]]

    # new state of pmds.
    new_pmd_l = sorted(pmd_map.keys())

    # skip modelling this object if states differ.
    if len(cur_pmd_l) > 0 and cur_pmd_l != new_pmd_l:
        raise ObjModelExc("pmds count differ")

    return pmd_map


def get_port_stats():
    """
    Collect stats on every port in the datapath.
    In every sampling iteration, these stats are stored
    in corresponding sampling slots.

    Raises
    ------
    OsCommandExc
        if the given OS command did not succeed for some reason.
    ObjModleExc
        if state of ports in switch differ.
    """

    nlog = Context.nlog

    # retrieve required data from the vswitch.
    cmd = "ovs-appctl dpctl/show -s"
    data = util.exec_host_command(cmd)
    if not data:
        raise OsCommandExc("unable to collect data")

    # current state of ports
    cur_port_l = sorted(Context.port_to_cls.keys())

    # current port object to be used in every line under parse.
    port = None

    for line in data.splitlines():
        if re.match(r'\s.*port\s(\d+):\s([A-Za-z0-9_-]+) *', line):
            # In below matching line, we retrieve port id and name.
            linesre = re.search(r'\s.*port\s(\d+):\s([A-Za-z0-9_-]+) *', line)
            (pid, pname) = linesre.groups()
            Context.port_to_id[pname] = int(pid)

            # If in mid of sampling, we should have port_to_cls having
            # entry for this port name.
            if pname in Context.port_to_cls:
                port = Context.port_to_cls[pname]
                assert(port.id == pid)

                # Store following stats in new sampling slot.
                port.cyc_idx = (port.cyc_idx + 1) % config.ncd_samples_max
                nlog.debug("port %s in iteration %d" %
                           (port.name, port.cyc_idx))
            else:
                # create new entry in port_to_cls for this port.
                port = make_dataif_port(pname)
                port.id = pid
                nlog.debug("added port %s stats.." % pname)

        elif re.match(r'\s.*RX packets:(\d+) .*? dropped:(\d+) *', line):
            # From other lines, we retrieve stats of the port.
            linesre = re.search(
                r'\s.*RX packets:(\d+) .*? dropped:(\d+) *', line)
            (rx, drop, ) = linesre.groups()
            port.rx_cyc[port.cyc_idx] = int(rx)
            port.rx_drop_cyc[port.cyc_idx] = int(drop)

        elif re.match(r'\s.*TX packets:(\d+) .*? dropped:(\d+) *', line):
            # From other lines, we retrieve stats of the port.
            linesre = re.search(
                r'\s.*TX packets:(\d+) .*? dropped:(\d+) *', line)
            (tx, drop, ) = linesre.groups()
            port.tx_cyc[port.cyc_idx] = int(tx)
            port.tx_drop_cyc[port.cyc_idx] = int(drop)

    # new state of ports.
    new_port_l = sorted(Context.port_to_cls.keys())

    # skip modelling this object if states differ.
    if len(cur_port_l) > 0 and cur_port_l != new_port_l:
        raise ObjModelExc("ports count differ")

    # current port object to be used in every line under parse.
    return None


def get_interface_stats():
    """
    Collect retry stats on every applicable port in the datapath.
    In every sampling iteration, these stats are stored
    in corresponding sampling slots.

    Raises
    ------
    OsCommandExc
        if the given OS command did not succeed for some reason.
    ObjModleExc
        if state of ports in switch differ.
    """

    nlog = Context.nlog

    # retrieve required data from the vswitch.
    cmd = "ovs-vsctl list interface"
    data = util.exec_host_command(cmd)
    if not data:
        raise OsCommandExc("unable to collect data")

    # current state of ports
    cur_port_l = sorted(Context.port_to_cls.keys())

    # current port object to be used in every line under parse.
    port = None

    for line in data.splitlines():
        if re.match(r'\s*name\s.*:\s"*([A-Za-z0-9_-]+)"*', line):
            # In below matching line, we retrieve port id and name.
            linesre = re.search(r'\s*name\s.*:\s"*([A-Za-z0-9_-]+)"*', line)
            (pname, ) = linesre.groups()

            # If in mid of sampling, we should have port_to_cls having
            # entry for this port name.
            if pname in Context.port_to_cls:
                port = Context.port_to_cls[pname]

                nlog.debug("port %s in iteration %d" %
                           (port.name, port.cyc_idx))

        elif re.match(r'\s*type\s.*:\s([a-z]+)', line):
            if not port:
                continue

            # From other lines, we retrieve stats of the port.
            linesre = re.search(
                r'\s*type\s.*:\s([a-z]+)', line)
            (type, ) = linesre.groups()
            port.type = type

            port = None

        elif re.match(r'\s*statistics\s.*:\s{(.*)}', line):
            if not port:
                continue

            # From other lines, we retrieve stats of the port.
            linesre = re.search(
                r'\s*statistics\s.*:\s{(.*)}', line)
            (sval, ) = linesre.groups()
            dval = {sub.split("=")[0]: sub.split("=")[1]
                    for sub in sval.split(", ")}

            if 'tx_retries' in dval:
                port.tx_retry_cyc[port.cyc_idx] = int(dval['tx_retries'])

    # new state of ports.
    new_port_l = sorted(Context.port_to_cls.keys())

    # skip modelling this object if states differ.
    if len(cur_port_l) > 0 and cur_port_l != new_port_l:
        raise ObjModelExc("ports count differ")

    return None


def rebalance_dryrun_by_iq(pmd_map):
    """
    Rebalance pmds based on their current load of traffic in it and
    it is just a dry-run. In every iteration of this dry run, we keep
    re-assigning rxqs to suitable pmds, at the same time we use
    actual load on each rxq to reflect the estimated pmd load after
    every optimization.

    To re-pin rxqs, the logic used is to move idle (or less loaded)
    rx queues into idle (or less loaded) pmds so that, busier rxq is
    given more processing cycles by busy pmd.

    Parameters
    ----------
    pmd_map : dict
        mapping of pmd id and its Dataif_Pmd object.
    """

    nlog = Context.nlog
    n_rxq_rebalanced = 0

    if len(pmd_map) <= 1:
        nlog.debug("not enough pmds to rebalance ..")
        return -1

    # Calculate current load on every pmd.
    update_pmd_load(pmd_map)

    if not pmd_need_rebalance(pmd_map):
        nlog.debug("no pmd needs rebalance ..")
        return -1

    # Sort pmds in pmd_map based on the rxq load, in descending order.
    # Pick the pmd which is more loaded from one end of the list.
    pmd_load_list = sorted(
        pmd_map.values(), key=lambda o: o.pmd_load)

    # Split list into busy and less loaded.
    bpmd_load_list = []
    ipmd_load_list = []
    for pmd in pmd_load_list:
        # pmd load of above configured threshold
        if pmd.pmd_load > config.ncd_pmd_core_threshold:
            bpmd_load_list.append(pmd)

        # skip pmd when its rxq count is one i.e pmd has just one rxq,
        # and this rxq is already busy (hencs, pmd was busy).
        elif (pmd.count_rxq() == 1 and
              pmd.pmd_load >= config.ncd_pmd_core_threshold):
            continue
        # rest of the pmds are less loaded (or idle).
        else:
            ipmd_load_list.insert(0, pmd)

    ipmd = None
    ipmd_gen = (o for o in ipmd_load_list)

    for pmd in bpmd_load_list:
        # As busy and idles (or less loaded) pmds are identified,
        # move less loaded rxqs from busy pmd into idle pmd.
        for port in pmd.port_map.values():
            # A port under dry-run may be empty now.
            if len(port.rxq_map) == 0:
                continue

            # As we pick one or more rxqs for every port in this pmd,
            # we leave atleast one rxq, not to make this busy pmd as
            # idle again.
            if pmd.count_rxq() <= 1:
                continue

            if not ipmd or (ipmd.numa_id != port.numa_id):
                for ipmd in ipmd_gen:
                    # Current pmd and rebalancing pmd should be in same numa.
                    if (ipmd.numa_id == port.numa_id):
                        break
                else:
                    ipmd_gen = (o for o in ipmd_load_list)

            if not ipmd:
                nlog.debug("no rebalancing pmd on this numa..")
                continue

            # Sort rxqs based on their current load, in ascending order.
            pmd_proc_cyc = sum(pmd.proc_cpu_cyc)
            rxq_load_list = sorted(port.rxq_map.values(),
                                   key=lambda o:
                                   ((sum(o.cpu_cyc) * 100) / pmd_proc_cyc))

            # pick one rxq to rebalance and this was least loaded in this pmd.
            try:
                rxq = rxq_load_list.pop(0)
            except IndexError:
                raise ObjConsistencyExc("rxq found empty ..")

            # move this rxq into the rebalancing pmd.
            nlog.info("moving rxq %d (port %s) from pmd %d into idle pmd %d .."
                      % (rxq.id, port.name, pmd.id, ipmd.id))
            iport = ipmd.find_port_by_name(port.name)
            if not iport:
                iport = ipmd.add_port(port.name, port.id, port.numa_id)
            irxq = iport.add_rxq(rxq.id)
            n_rxq_rebalanced += 1
            assert(iport.numa_id == port.numa_id)

            # Copy cpu cycles of this rxq into its clone in
            # in rebalancing pmd (for dry-run).
            irxq.cpu_cyc = copy.deepcopy(rxq.cpu_cyc)
            irxq.rx_cyc = copy.deepcopy(rxq.rx_cyc)

            cur_idx = pmd.cyc_idx
            for i in range(0, config.ncd_samples_max):
                # update rebalancing pmd for cpu cycles and rx count.
                ipmd.proc_cpu_cyc[cur_idx] += irxq.cpu_cyc[cur_idx]
                ipmd.idle_cpu_cyc[cur_idx] -= irxq.cpu_cyc[cur_idx]
                ipmd.rx_cyc[cur_idx] += irxq.rx_cyc[cur_idx]

                # update current pmd for cpu cycles and rx count.
                pmd.proc_cpu_cyc[cur_idx] -= irxq.cpu_cyc[cur_idx]
                pmd.idle_cpu_cyc[cur_idx] += irxq.cpu_cyc[cur_idx]
                pmd.rx_cyc[cur_idx] -= irxq.rx_cyc[cur_idx]

                cur_idx = (cur_idx - 1) % config.ncd_samples_max

            # No more tracking of this rxq in current pmd.
            port.del_rxq(rxq.id)
            port.rxq_rebalanced[rxq.id] = ipmd.id
            irxq.pmd = pmd

            # Calculate current load on every pmd.
            update_pmd_load(pmd_map)

            # check if rebalancing pmd has got enough work.
            update_pmd_load(pmd_map)
            if ipmd.pmd_load >= config.ncd_pmd_core_threshold:
                nlog.info("removing pmd %d from idle pmd list" % ipmd.id)
                ipmd_load_list.remove(ipmd)
                ipmd = None

    return n_rxq_rebalanced


def rebalance_dryrun_by_cyc(pmd_map):
    """
    Rebalance pmds based on their current load of traffic in it and
    it is just a dry-run. In every iteration of this dry run, we keep
    re-assigning rxqs to suitable pmds, at the same time we use
    actual load on each rxq to reflect the estimated pmd load after
    every optimization.

    To re-pin rxqs, the logic used is to order pmds based on top
    consuming rxqs and traverse on this list forward and backward.

    Parameters
    ----------
    pmd_map : dict
        mapping of pmd id and its Dataif_Pmd object.
    """

    nlog = Context.nlog
    n_rxq_rebalanced = 0

    if len(pmd_map) <= 1:
        nlog.debug("not enough pmds to rebalance ..")
        return -1

    # Calculate current load on every pmd.
    update_pmd_load(pmd_map)

    if not pmd_need_rebalance(pmd_map):
        nlog.debug("no pmd needs rebalance ..")
        return -1

    # Sort pmds in pmd_map based on busier rxqs and then use some
    # constant order that system provides, to fill up the list.
    pmd_list = []
    rr_cpus = util.rr_cpu_in_numa()
    for cpu in rr_cpus:
        if cpu in pmd_map:
            pmd_list.append(pmd_map[cpu])

    rxq_list = []
    pmd_rxq_n = {}
    numa_pmd_n = {}
    for pmd in pmd_list:
        pmd_rxq_n[pmd.id] = 0
        if pmd.numa_id not in numa_pmd_n:
            numa_pmd_n[pmd.numa_id] = 0

        numa_pmd_n[pmd.numa_id] += 1
        for port in pmd.port_map.values():
            rxq_list += port.rxq_map.values()

    rxq_load_list = sorted(
        rxq_list, key=lambda o: sum(o.cpu_cyc), reverse=True)
    pmd_list_forward = []
    for rxq in rxq_load_list:
        if rxq.pmd not in pmd_list_forward:
            pmd_list_forward.append(rxq.pmd)

    if (len(pmd_list_forward) < len(pmd_list)):
        for pmd in pmd_list:
            if pmd not in pmd_list_forward:
                pmd_list_forward.append(pmd)

    nlog.debug("cpu numbering based on system info is %s" %
               (",".join(str(x) for x in rr_cpus)))
    nlog.debug("traverse order on pmds based on rxqs is %s" %
               (",".join(str(x.id) for x in pmd_list_forward)))

    pmd_list_reverse = pmd_list_forward[::-1]
    pmd_list = pmd_list_forward
    idx_forward = True

    rpmd = None
    rpmd_gen = (o for o in pmd_list)
    for rxq in rxq_load_list:
        port = rxq.port
        pmd = rxq.pmd

        if len(port.rxq_map) == 0:
            continue

        rpmd = None
        while (not rpmd):
            for rpmd in rpmd_gen:
                # choose pmd from same numa.
                if (rpmd.numa_id == port.numa_id):
                    # for top consuming rxqs.
                    if (pmd_rxq_n[pmd.id] == 0):
                        if(rpmd.id == pmd.id):
                            pmd_rxq_n[pmd.id] += 1
                            break
                        else:
                            continue
                    # owning pmd has already taken topper
                    pmd_rxq_n[rpmd.id] += 1
                    break
            else:
                pmd_rxq_s = sum(map(lambda x: int(x > 0), pmd_rxq_n.values()))
                if (pmd_rxq_s < numa_pmd_n[port.numa_id]):
                    rpmd_gen = (o for o in pmd_list)
                    rpmd = None
                    continue

                # reverse traverse direction
                if idx_forward:
                    pmd_list = pmd_list_reverse
                    idx_forward = False
                else:
                    pmd_list = pmd_list_forward
                    idx_forward = True
                rpmd_gen = (o for o in pmd_list)
                rpmd = None

            if rpmd:
                break

        # check while else for last rpmd

        if not rpmd:
            raise ObjConsistencyExc(
                "no rebalancing pmd on numa(%d) for port %s rxq %d.."
                % (port.numa_id, port.name, rxq.id))

        assert(rpmd.numa_id == port.numa_id)

        if pmd.id == rpmd.id:
            nlog.info("no change needed for rxq %d (port %s) in pmd %d"
                      % (rxq.id, port.name, pmd.id))
            continue

        # move this rxq into the rebalancing pmd.
        nlog.info("moving rxq %d (port %s) from pmd %d into pmd %d .."
                  % (rxq.id, port.name, pmd.id, rpmd.id))
        rport = rpmd.find_port_by_name(port.name)
        if not rport:
            rport = rpmd.add_port(port.name, port.id, port.numa_id)
        rrxq = rport.add_rxq(rxq.id)
        n_rxq_rebalanced += 1
        assert(rport.numa_id == port.numa_id)

        # Copy cpu and rxq cycles of this rxq into its clone in
        # in rebalancing pmd (for dry-run).
        rrxq.cpu_cyc = copy.deepcopy(rxq.cpu_cyc)
        rrxq.rx_cyc = copy.deepcopy(rxq.rx_cyc)

        cur_idx = pmd.cyc_idx
        for i in range(0, config.ncd_samples_max):
            # update rebalancing pmd for cpu cycles and rx count.
            rpmd.proc_cpu_cyc[cur_idx] += rrxq.cpu_cyc[cur_idx]
            rpmd.idle_cpu_cyc[cur_idx] -= rrxq.cpu_cyc[cur_idx]
            rpmd.rx_cyc[cur_idx] += rrxq.rx_cyc[cur_idx]

            # update current pmd for cpu cycles and rx count.
            pmd.proc_cpu_cyc[cur_idx] -= rrxq.cpu_cyc[cur_idx]
            pmd.idle_cpu_cyc[cur_idx] += rrxq.cpu_cyc[cur_idx]
            pmd.rx_cyc[cur_idx] -= rrxq.rx_cyc[cur_idx]

            cur_idx = (cur_idx - 1) % config.ncd_samples_max

        # No more tracking of this rxq in current pmd.
        port.del_rxq(rxq.id)
        port.rxq_rebalanced[rxq.id] = rpmd.id
        rrxq.pmd = pmd

    if n_rxq_rebalanced:
        # Calculate current load on every pmd.
        update_pmd_load(pmd_map)

    return n_rxq_rebalanced


def port_drop_ppm(port):
    """
    Return packet drops from the port stats.

    """
    ret_rxtx = [0, 0]
    rx_sum = sum([j - i for i, j in zip(port.rx_cyc[:-1], port.rx_cyc[1:])])
    rxd_sum = sum(
        [j - i for i, j in zip(port.rx_drop_cyc[:-1], port.rx_drop_cyc[1:])])
    tx_sum = sum([j - i for i, j in zip(port.tx_cyc[:-1], port.tx_cyc[1:])])
    txd_sum = sum(
        [j - i for i, j in zip(port.tx_drop_cyc[:-1], port.tx_drop_cyc[1:])])

    if rx_sum != 0:
        ret_rxtx[0] = (1000000 * rxd_sum) / rx_sum

    if tx_sum != 0:
        ret_rxtx[1] = (1000000 * txd_sum) / tx_sum

    return ret_rxtx


def port_tx_retry(port):
    """
    Return count of tx retry performed, from the port stats.
    """
    return sum(
        [j - i for i, j in zip(port.tx_retry_cyc[:-1], port.tx_retry_cyc[1:])])
