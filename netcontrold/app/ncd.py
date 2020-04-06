#!/usr/bin/env python3
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

__all__ = ['ncd_main']

# import system libraries
import re
import signal
import time
import argparse
import sys
import socket
import os
import logging
import threading
from logging.handlers import RotatingFileHandler
from datetime import datetime

import netcontrold
from netcontrold.lib import config
from netcontrold.lib import dataif
from netcontrold.lib import util
from netcontrold.lib import error


class RebalContext(dataif.Context):
    rebal_mode = False
    rebal_quick = False
    rebal_tick = 0
    rebal_tick_n = 0
    apply_rebal = False


class TraceContext(dataif.Context):
    trace_mode = False


nlog = None


class CtlDThread(util.Thread):

    def __init__(self, eobj):
        util.Thread.__init__(self, eobj)

    def run(self):
        sock_file = config.ncd_socket

        try:
            os.unlink(sock_file)
        except OSError:
            if os.path.exists(sock_file):
                raise

        os.makedirs(os.path.dirname(sock_file), exist_ok=True)

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        nlog.info("starting ctld on %s" % sock_file)
        sock.bind(sock_file)
        sock.listen(1)

        while (not self.ncd_shutdown.is_set()):
            conn, client = sock.accept()

            try:
                cmd = conn.recv(24).decode()

                ctx = dataif.Context
                rctx = RebalContext
                tctx = TraceContext

                if cmd == 'CTLD_TRACE_ON':
                    if not tctx.trace_mode:
                        nlog.info("turning on trace mode ..")
                        tctx.trace_mode = True
                    else:
                        nlog.info("trace mode already on ..!")

                    conn.sendall(b"CTLD_ACK")

                elif cmd == 'CTLD_TRACE_OFF':
                    if tctx.trace_mode:
                        nlog.info("turning off trace mode ..")
                        tctx.trace_mode = False
                    else:
                        nlog.info("trace mode already off ..!")

                    conn.sendall(b"CTLD_ACK")

                elif cmd == 'CTLD_REBAL_ON':
                    if not rctx.rebal_mode:
                        nlog.info("turning on rebalance mode ..")
                        rctx.rebal_mode = True
                    else:
                        nlog.info("rebalance mode already on ..!")

                    conn.sendall(b"CTLD_ACK")

                elif cmd == 'CTLD_REBAL_OFF':
                    if rctx.rebal_mode:
                        nlog.info("turning off rebalance mode ..")
                        rctx.rebal_mode = False
                    else:
                        nlog.info("rebalance mode already off ..!")

                    conn.sendall(b"CTLD_ACK")

                elif cmd == 'CTLD_REBAL_QUICK_ON':
                    if not rctx.rebal_quick:
                        nlog.info("turning on rebalance quick mode ..")
                        rctx.rebal_quick = True
                    else:
                        nlog.info("rebalance quick mode already on ..!")

                    conn.sendall(b"CTLD_ACK")

                elif cmd == 'CTLD_REBAL_QUICK_OFF':
                    if rctx.rebal_quick:
                        nlog.info("turning off rebalance quick mode ..")
                        rctx.rebal_quick = False
                    else:
                        nlog.info("rebalance quick mode already off ..!")

                    conn.sendall(b"CTLD_ACK")

                elif cmd == 'CTLD_VERBOSE_ON':
                    fh = ctx.log_handler
                    if fh.level == logging.INFO:
                        nlog.info("turning on verbose mode ..")
                        fh.setLevel(logging.DEBUG)
                    else:
                        nlog.info("verbose mode already on ..!")

                    conn.sendall(b"CTLD_ACK")

                elif cmd == 'CTLD_VERBOSE_OFF':
                    fh = ctx.log_handler
                    if fh.level == logging.DEBUG:
                        nlog.info("turning off verbose mode ..")
                        fh.setLevel(logging.INFO)
                    else:
                        nlog.info("verbose mode already off ..!")

                    conn.sendall(b"CTLD_ACK")

                elif cmd == 'CTLD_REBAL_CNT':
                    n = 0
                    if rctx.rebal_mode:
                        n = len(rctx.rebal_stat)
                        for (x, y, z) in ctx.events:
                            if y == 'rebalance':
                                n += 1

                    conn.sendall(b"CTLD_DATA_ACK %6d" % (len(str(n))))
                    conn.sendall(str(n).encode())

                elif cmd == 'CTLD_CONFIG':
                    status = "trace mode:"
                    if tctx.trace_mode:
                        status += " on\n"
                    else:
                        status += " off\n"

                    status += "rebalance mode:"
                    if rctx.rebal_mode:
                        status += " on\n"
                    else:
                        status += " off\n"

                    status += "rebalance quick:"
                    if rctx.rebal_quick:
                        status += " on\n"
                    else:
                        status += " off\n"

                    status += "verbose log:"
                    fh = ctx.log_handler
                    if fh.level == logging.DEBUG:
                        status += " on\n"
                    else:
                        status += " off\n"

                    conn.sendall(b"CTLD_DATA_ACK %6d" % (len(status)))
                    conn.sendall(status.encode())

                elif cmd == 'CTLD_STATUS':
                    status = "%-16s | %-12s | %s\n" % ('Interface',
                                                       'Event', 'Time stamp')
                    status += ('-' * 17) + '+' + ('-' * 14) + '+' + ('-' * 28)
                    status += '\n'

                    for (x, y, z) in ctx.events:
                        status += "%-16s | %-12s | %s\n" % (x, y, z)

                    conn.sendall(b"CTLD_DATA_ACK %6d" % (len(status)))
                    conn.sendall(status.encode())

                elif cmd == 'CTLD_VERSION':
                    status = "netcontrold v%s\n" % netcontrold.__version__
                    ret = util.exec_host_command("ovs-vsctl -V")
                    if ret == 1:
                        status += "openvswitch (unknown)\n"
                    else:
                        parse = re.match("ovs-vsctl \(Open vSwitch\) (.*?)\n",
                                         ret)
                        status += "openvswitch v%s\n" % parse[1]

                    conn.sendall(b"CTLD_DATA_ACK %6d" % (len(status)))
                    conn.sendall(status.encode())

                else:
                    nlog.info("unknown control command %s" % cmd)

            finally:
                conn.close()

        return


def collect_data(n_samples, s_sampling):
    """
    Collect various stats and rxqs mapping of every pmd in the vswitch.

    Parameters
    ----------
    n_samples : int
        number of samples

    s_sampling: int
        sampling interval
    """

    ctx = dataif.Context
    rctx = RebalContext

    # collect samples of pmd and rxq stats.
    idx_max = n_samples
    idx_gen = (o for o in range(0, idx_max))
    while True:
        try:
            next(idx_gen)
        except StopIteration:
            break

        try:
            rctx.rebal_tick += 1
            dataif.get_port_stats()
            dataif.get_interface_stats()
            dataif.get_pmd_stats(ctx.pmd_map)
            dataif.get_pmd_rxqs(ctx.pmd_map)
        except (error.OsCommandExc,
                error.ObjCreateExc,
                error.ObjConsistencyExc,
                error.ObjParseExc,
                error.ObjModelExc) as e:
            # report error event
            now = datetime.now()
            now_ts = now.strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(e, error.OsCommandExc):
                nlog.warn("unable to collect data: %s" % e)
                ctx.events.append(("switch", "error", now_ts))
                raise error.NcdShutdownExc

            elif isinstance(e, error.ObjCreateExc):
                nlog.warn("unable to create object: %s" % e)
                ctx.events.append(("ncd", "error", now_ts))
                raise error.NcdShutdownExc

            elif isinstance(e, error.ObjConsistencyExc):
                nlog.warn("inconsistency in collected data: %s" % e)
                ctx.events.append(("ncd", "error", now_ts))
                raise error.NcdShutdownExc

            elif isinstance(e, error.ObjModelExc):
                nlog.warn("switch states changed: %s" % e)
                ctx.events.append(("ncd", "retry_model", now_ts))

                # reset collected data
                ctx.pmd_map.clear()
                ctx.port_to_cls.clear()
                ctx.port_to_id.clear()

                # restart iterations
                idx_gen.close()
                idx_max = config.ncd_samples_max
                idx_gen = (o for o in range(0, idx_max))
                continue

            elif isinstance(e, error.ObjParseExc):
                nlog.warn("unable to parse info: %s" % e)
                ctx.events.append(("ncd", "retry_parse", now_ts))

                # reset collected data
                ctx.pmd_map.clear()
                ctx.port_to_cls.clear()
                ctx.port_to_id.clear()

                # restart iterations
                idx_gen.close()
                idx_max = config.ncd_samples_max
                idx_gen = (o for o in range(0, idx_max))
                time.sleep(s_sampling)
                continue

            else:
                nlog.error("unhandled exception: %s" % e)
                ctx.events.append(("ncd", "exception", now_ts))
                raise error.NcdShutdownExc

        time.sleep(s_sampling)

    now = datetime.now()
    ctx.last_ts = now.strftime("%Y-%m-%d %H:%M:%S")
    dataif.update_pmd_load(ctx.pmd_map)

    return ctx


def rebalance_switch(pmd_map):
    """
    Issue appropriate actions in vswitch to rebalance.

    Parameters
    ----------
    pmd_map : dict
        mapping of pmd id and its Dataif_Pmd object.
    """

    port_to_pmdq = {}
    non_isol_pmds = []
    numa = 0
    for pmd_id, pmd in pmd_map.items():
        # leave one pmd in every numa as non-isolated.
        if pmd.numa_id == numa:
            non_isol_pmds.append(pmd)
            numa += 1
            continue

        for port_name, port in pmd.port_map.items():
            if port_name not in port_to_pmdq and len(port.rxq_map) != 0:
                port_to_pmdq[port_name] = ""
            for rxq_id in port.rxq_map:
                port_to_pmdq[port_name] += "%d:%d," % (rxq_id, pmd_id)

    # refresh ports info and check for any port removed now.
    ctx = dataif.Context
    ctx.port_to_id.clear()
    dataif.get_port_stats()
    cmd = ""
    for port_name, pmdq in port_to_pmdq.items():
        if port_name not in ctx.port_to_id:
            now = datetime.now()
            now_ts = now.strftime("%Y-%m-%d %H:%M:%S")
            nlog.info("not setting affinity for an unavailable port %s"
                      % (port_name))
            ctx.events.append((port_name, "skip", now_ts))
            continue
        cmd += "-- set Interface %s other_config:pmd-rxq-affinity=%s " % (
            port_name, pmdq)

    # ensure non-isolated pmd carry new rxqs, arriving from other pmds.
    for pmd in non_isol_pmds:
        for port_name, port in pmd.port_map.items():
            if port_name not in ctx.port_to_id:
                now = datetime.now()
                now_ts = now.strftime("%Y-%m-%d %H:%M:%S")
                nlog.info("not resetting affinity for unavailable port %s"
                          % (port_name))
                ctx.events.append((port_name, "skip", now_ts))
                continue
            if port_name not in port_to_pmdq:
                cmd += "-- remove Interface %s other_config pmd-rxq-affinity "\
                    % (port_name)
    return "ovs-vsctl --no-wait %s" % cmd


def ncd_kill(signal, frame):
    ctx = dataif.Context
    nlog.critical("Got signal %s, doing required clean up .." % signal)

    # reset rebalance settings in ports
    cmd = ""
    for port_name, port in ctx.port_to_cls.items():
        # skip port that we did not rebalance.
        if not port.rebalance:
            continue

        cmd += "-- remove Interface %s other_config pmd-rxq-affinity " % (
            port_name)

    if cmd:
        ret = util.exec_host_command("ovs-vsctl --no-wait %s" % cmd)
        if ret == 0:
            nlog.info("removed pmd-rxq-affinity in rebalanced ports.")
        else:
            nlog.warn("removing pmd-rxq-affinity failed for some ports.")
            nlog.warn("you may check ovs-vsctl --no-wait %s" % cmd)

    raise error.NcdShutdownExc


def ncd_main(argv):
    # input options
    argpobj = argparse.ArgumentParser(
        prog='ncd.py', description='control network load on pmd')

    argpobj.add_argument('-s', '--sample-interval',
                         type=int,
                         default=10,
                         help='seconds between each sampling (default: 10)')

    argpobj.add_argument('-t', '--trace',
                         required=False,
                         action='store_true',
                         default=False,
                         help='operate in trace mode',
                         )

    argpobj.add_argument('--trace-cb',
                         type=str,
                         default='ncd_cb_pktdrop',
                         help='trace mode callback '
                         '(default: ncd_cb_pktdrop)')

    argpobj.add_argument('-r', '--rebalance',
                         required=False,
                         action='store_true',
                         default=True,
                         help="operate in rebalance mode",
                         )

    argpobj.add_argument('--rebalance-interval',
                         type=int,
                         default=60,
                         help='seconds between each re-balance '
                         '(default: 60)')

    argpobj.add_argument('--rebalance-n',
                         type=int,
                         default=1,
                         help='rebalance dry-runs at the max (default: 1)')

    argpobj.add_argument('--rebalance-iq',
                         action='store_true',
                         default=False,
                         help='rebalance by iterative queues logic '
                                '(default: False)')

    argpobj.add_argument('-q', '--quiet',
                         action='store_true',
                         default=False,
                         help='no logging in terminal (default: False)')

    argpobj.add_argument('-v', '--verbose',
                         action='store_true',
                         default=False,
                         help='trace logging (default: False)')

    args = argpobj.parse_args(argv)

    # check input to ncd
    ncd_trace = args.trace
    ncd_trace_cb = args.trace_cb
    ncd_rebal = args.rebalance

    if ncd_trace and not util.exists(ncd_trace_cb):
        print("no such program %s exists!" % ncd_trace_cb)
        sys.exit(1)

    # set verbose level
    os.makedirs(os.path.dirname(config.ncd_log_file), exist_ok=True)
    fh = RotatingFileHandler(config.ncd_log_file,
                             maxBytes=(config.ncd_log_max_KB * 1024),
                             backupCount=config.ncd_log_max_backup_n)

    fh_fmt = logging.Formatter(
        "%(asctime)s|%(name)s|%(levelname)s|%(message)s")
    fh.setFormatter(fh_fmt)
    if args.verbose:
        fh.setLevel(logging.DEBUG)
    else:
        fh.setLevel(logging.INFO)

    ch = logging.StreamHandler(sys.stdout)
    ch_fmt = logging.Formatter("%(message)s")
    ch.setFormatter(ch_fmt)
    ch.setLevel(logging.INFO)

    global nlog
    nlog = logging.getLogger('ncd')
    nlog.setLevel(logging.DEBUG)
    nlog.addHandler(fh)
    if not args.quiet:
        nlog.addHandler(ch)

    ctx = dataif.Context
    ctx.nlog = nlog
    ctx.log_handler = fh
    pmd_map = ctx.pmd_map

    # set sampling interval to collect data
    ncd_sample_interval = args.sample_interval

    # set interval between each re-balance
    ncd_rebal_interval = args.rebalance_interval

    # set rebalance dryrun count
    ncd_rebal_n = args.rebalance_n

    # set iterative queue rebalance algorithm
    ncd_iq_rebal = args.rebalance_iq

    # set rebalance method.
    if ncd_iq_rebal:
        rebalance_dryrun = dataif.rebalance_dryrun_by_iq
    else:
        # round robin logic to rebalance.
        rebalance_dryrun = dataif.rebalance_dryrun_by_cyc

        # restrict only one dry run for cycles based mode.
        ncd_rebal_n = 1

    # set check point to call rebalance in vswitch
    rctx = RebalContext
    rctx.rebal_tick_n = ncd_rebal_interval / ncd_sample_interval

    if ncd_rebal:
        # adjust length of the samples counter
        config.ncd_samples_max = min(
            ncd_rebal_interval / ncd_sample_interval, config.ncd_samples_max)

        rctx.rebal_mode = True
        rctx.rebal_quick = True

    config.ncd_samples_max = int(config.ncd_samples_max)

    # set signal handler to abort ncd
    signal.signal(signal.SIGINT, ncd_kill)
    signal.signal(signal.SIGTERM, ncd_kill)

    tctx = TraceContext
    if ncd_trace:
        tctx.trace_mode = True

    # start ctld thread to monitor control command and dispatch
    # necessary action.
    shutdown_event = threading.Event()
    tobj = CtlDThread(shutdown_event)
    tobj.daemon = True

    try:
        tobj.start()
    except threading.ThreadError:
        nlog.info("failed to start ctld thread ..")
        sys.exit(1)

    prev_var = 0
    cur_var = 0
    ncd_samples_max = config.ncd_samples_max
    min_sample_i = 0

    # begin rebalance dry run
    while (1):
        try:
            collect_data(ncd_samples_max, ncd_sample_interval)
            min_sample_i += ncd_samples_max

            nlog.info("current pmd load:")
            for pmd_id in sorted(pmd_map.keys()):
                pmd = pmd_map[pmd_id]
                nlog.info("pmd id %d load %d" % (pmd_id, pmd.pmd_load))

            cur_var = dataif.pmd_load_variance(pmd_map)
            nlog.info("current pmd load variance: %d" % cur_var)

            # do not trace if rebalance dry-run in progress.
            if tctx.trace_mode:
                pmd_cb_list = []
                for pname in sorted(ctx.port_to_cls.keys()):
                    port = ctx.port_to_cls[pname]
                    drop = dataif.port_drop_ppm(port)
                    drop_min = config.ncd_cb_pktdrop_min
                    tx_retry = dataif.port_tx_retry(port)
                    do_cb = False
                    if drop[0] > drop_min:
                        nlog.info("port %s drop_rx %d ppm above %d ppm" %
                                  (port.name, drop[0], drop_min))
                        ctx.events.append((port.name, "rx_drop", ctx.last_ts))
                        do_cb = True

                    if drop[1] > drop_min:
                        nlog.info("port %s drop_tx %d ppm above %d ppm" %
                                  (port.name, drop[1], drop_min))
                        ctx.events.append((port.name, "tx_drop", ctx.last_ts))
                        do_cb = True

                    if tx_retry > config.ncd_samples_max:
                        nlog.info("port %s tx_retry %d above %d" %
                                  (port.name, tx_retry,
                                   config.ncd_samples_max))
                        ctx.events.append((port.name, "tx_retry", ctx.last_ts))
                        do_cb = True

                    if not do_cb:
                        # no pmd needs to be traceged.
                        continue

                    for pmd_id in sorted(pmd_map.keys()):
                        pmd = pmd_map[pmd_id]
                        if (pmd.find_port_by_name(port.name)):
                            pmd_cb_list.insert(0, pmd_id)

                if (len(pmd_cb_list) > 0):
                    pmds = " ".join(list(map(str, set(pmd_cb_list))))
                    cmd = "%s %s" % (ncd_trace_cb, pmds)
                    nlog.info("executing callback %s" % cmd)
                    data = util.exec_host_command(cmd)
                    nlog.info(data)

            if not rctx.rebal_mode:
                continue

            # At the minimum for deriving current load on pmds, all of
            # the sampling counters (of size config.ncd_samples_max) have
            # to be filled "every time" before other evaluations done.
            #
            # However, for quick rebalance, we fill all the counters
            # once, and then keep rolling with one counter across old
            # stats so that, we reduce time to sample before kicking off
            # rebalance (from sampling config.ncd_samples_max counters
            # to only one.
            #
            # As ovs internally refers all its 6 sample counters for any
            # stats we query, it is absolutely fine we roll with one
            # new sample and retain old n-1 samples to check for current
            # state of pmd and rxqs.
            #
            if rctx.rebal_quick and (min_sample_i >= config.ncd_samples_max):
                ncd_samples_max = 1
                min_sample_i = (config.ncd_samples_max - 1)
            else:
                ncd_samples_max = config.ncd_samples_max

            # dry-run pmd rebalance.
            rebal_rxq_n = 0
            if pmd_map:
                for i in range(0, ncd_rebal_n):
                    n = 0
                    n = rebalance_dryrun(pmd_map)
                    if (n > 0):
                        rebal_rxq_n += n

            # restart sampling when no dry-run performed.
            if rebal_rxq_n == 0:
                nlog.info("no dryrun performed.")
                continue

            else:
                # compare previous and current state of pmds.
                prev_var = cur_var
                cur_var = dataif.pmd_load_variance(pmd_map)
                nlog.info("pmd load after dry run:")
                for pmd_id in sorted(pmd_map.keys()):
                    pmd = pmd_map[pmd_id]
                    nlog.info("pmd id %d load %d" % (pmd_id, pmd.pmd_load))

                nlog.info("pmd load variance: previous %d, after dry run %d" %
                          (prev_var, cur_var))

                if (cur_var < prev_var):
                    diff = (prev_var - cur_var) * 100 / prev_var
                    if diff > config.ncd_pmd_load_improve_min:
                        rctx.apply_rebal = True

                # check if balance state of all pmds is reached
                if rctx.apply_rebal:
                    # check if rebalance call needed really.
                    if (rctx.rebal_tick >= rctx.rebal_tick_n):
                        rctx.rebal_tick = 0
                        cmd = rebalance_switch(pmd_map)
                        ctx.events.append(("pmd", "rebalance", ctx.last_ts))
                        nlog.info(
                            "vswitch command for current optimization is: %s"
                            % cmd)
                        rctx.apply_rebal = False

                        if (util.exec_host_command(cmd) == 1):
                            nlog.info(
                                "problem running this command.. "
                                "check vswitch!")
                            now = datetime.now()
                            now_ts = now.strftime("%Y-%m-%d %H:%M:%S")
                            ctx.events.append(("switch", "error", now_ts))

                        # sleep for few seconds before thrashing current
                        # dry-run
                        nlog.info(
                            "waiting for %d seconds "
                            "before new dry runs begin.."
                            % config.ncd_vsw_wait_min)
                        time.sleep(config.ncd_vsw_wait_min)
                    else:
                        nlog.info("minimum rebalance interval not met!"
                                  " now at %d sec"
                                  % (rctx.rebal_tick * ncd_sample_interval))
                else:
                    nlog.info("no new optimization found ..")

                # reset collected data
                pmd_map.clear()
                ctx.port_to_cls.clear()
                ctx.port_to_id.clear()
                ncd_samples_max = config.ncd_samples_max
                min_sample_i = 0

                nlog.info("dry-run reset.")

        except error.NcdShutdownExc:
            nlog.info("Exiting NCD ..")
            tobj.ncd_shutdown.set()
            sys.exit(1)

    tobj.join()


if __name__ == "__main__":
    ncd_main(sys.argv[1:])
    sys.exit(0)
