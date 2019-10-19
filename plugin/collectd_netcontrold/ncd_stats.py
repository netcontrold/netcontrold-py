import collectd
import socket
import os
import re
from netcontrold.lib import config

SOCKET = config.ncd_socket


def config_func(config):
    for node in config.children:
        key = node.key
        val = node.values[0]

        if key == 'Socket':
            SOCKET = val
            collectd.info('ncd_stats plugin: using socket %s' % SOCKET)
        else:
            collectd.info('ncd_stats plugin: unknown config key "%s"' % key)


def read_func():
    if not os.path.exists(SOCKET):
        collectd.error("socket %s not found.. exiting.\n" % SOCKET)
        return

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(SOCKET)
    except socket.error as e:
        collectd.error("unable to connect %s: %s\n" % (SOCKET, e))
        return

    try:
        sock.sendall("CTLD_REBAL_CNT")
        ack_len = 0
        while (ack_len < len("CTLD_DATA_ACK XXXXXX")):
            data = sock.recv(len("CTLD_DATA_ACK XXXXXX"))
            ack_len += len(data)

        status_len = int(re.findall('\d+', data)[0])
        data_len = 0
        while (data_len < status_len):
            data = sock.recv(status_len)
            data_len += len(data)

    finally:
        sock.close()

    # Dispatch value to collectd
    val = collectd.Values(type='count')
    val.plugin = 'ncd_stats'
    val.dispatch(values=[data])


collectd.register_config(config_func)
collectd.register_read(read_func)
