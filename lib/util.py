# Copyright notice to be added

__all__ = ['exec_host_command',
           'variance',
           ]

# Import standard modules
import subprocess

def exec_host_command(cmd):
    try:
        ret = subprocess.check_output(cmd.split())
    except subprocess.CalledProcessError, e:
        print ("Unable to execute command %s: %s" %(cmd, e))
        return 1
    return ret

def variance(list):
    mean = sum(list) / len(list)
    return sum((item - mean) ** 2 for item in list) / len(list)
