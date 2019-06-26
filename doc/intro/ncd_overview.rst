== == == == == == == == == == == == == == ==
Overview of Netcontrold daemon
== == == == == == == == == == == == == == ==

What is netcontrold ?
---------------------

Netcontrold is load optimization tool for OVS / DPDK Poll Mode Driver(PMD) threads. By running this tool, an operator can know in advance best optimization that can be done with PMD threads in terms of load balancing them.

How to use netcontrold ?
------------------------

    usage:
        ncd.py[-h][-i REBALANCE_INTERVAL][-n REBALANCE_N]
        [-s SAMPLE_INTERVAL] [https: // www.google.com /] [-v VERBOSE]

    NCD options:

    optional arguments:
        -h, --help            show this help message and exit
        -i REBALANCE_INTERVAL, --rebalance - interval REBALANCE_INTERVAL
            interval in seconds between each re - balance(default:
                                                          60)
        -n REBALANCE_N, --rebalance - n REBALANCE_N
            maximum number of rebalance attempts(default: 1)
        -s SAMPLE_INTERVAL, --sample - interval SAMPLE_INTERVAL
            interval in seconds between each sampling(default:
                                                      10)
        --iq                  rebalance by idle - queue logic(default: False)
        -v VERBOSE, --verbose VERBOSE
            verbose level for output(default: 0)
