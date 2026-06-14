Application Name
================
ping_sample


Application Version
===================
1.0


NCOS Devices Supported
======================
ALL


External Requirements
=====================
None


Application Purpose
===================
Contains ping function and example usage.

def ping(host, **kwargs):
    """
    :param host: string
        destination IP address to ping
    :param kwargs:
        "num": number of pings to send. Default is 4
        "srcaddr": source IP address.  If blank NCOS uses primary WAN.
    :return:
        dict {
            "tx": int - number of pings transmitted
            "rx": int - number of pings received
            "loss": float - percentage of lost pings (e.g. "25.0")
            "min": float - minimum round trip time in milliseconds
            "max": float - maximum round trip time in milliseconds
            "avg": float - average round trip time in milliseconds
            "error" string - error message if not successful
    requirements:
    cp = SDK CS Client.  (e.g. CSClient() or EventingCSClient())
    """

Expected Output
===============
Ping output to 8.8.8.8

