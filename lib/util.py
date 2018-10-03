# Copyright notice to be added
from logger import nlog

__all__ = ['exec_host_command',
           ]

# Import standard modules
import subprocess

def exec_host_command(cmd):
    try:
        ret = subprocess.check_output(cmd.split())
    except subprocess.CalledProcessError, e:
        nlog.info("Unable to execute command %s: %s" %(cmd, e))
        return 1
    return ret
