# misc Cradlepoint Hardware Status routines

import time
import sys

# technically, could also fetch the router FW build time
# EARLIEST_REALISTIC_TIME = time.mktime(
# time.strptime("2016-01-01", "%Y-%m-%d"))
EARLIEST_REALISTIC_TIME = 1451628000.0

# status of the primary (desired) cellular link; tower link means tower
# linked, but not using for uplink
WAN_PRI_CELL_TOWER_LINK = 0x1
WAN_PRI_UPLINK = 0x2
# status of the secondary (less-desired) cellular link
WAN_SEC_CELL_TOWER_LINK = 0x10
WAN_SEC_UPLINK = 0x20
# status of the wired/broadband links active
WAN_WIFI_UPLINK = 0x100
WAN_WIRE_UPLINK = 0x200

# these are all the valid ways we uplink to internet
WAN_IS_CONNECTED = WAN_PRI_UPLINK | WAN_SEC_UPLINK | WAN_WIFI_UPLINK | \
                   WAN_WIRE_UPLINK


def am_running_on_router():
    """
    True if code is running on Cradlepoint router
    :return:
    """
    # return not sys.platform in ("win32", "linux")
    return sys.platform == "linux2"


def router_time_is_valid(force_time=None):
    """
    True if router time has been validated - else time.time() is jan-01-1970.

    For now, we just watch value. TBD - get quality or event direct from FW

    :param int force_time: for testing, pass in a 'fake' time.time() value.
    :return bool: True if time.time() returns something useful
    """
    if not force_time:
        force_time = time.time()
    return force_time > EARLIEST_REALISTIC_TIME


def router_wan_status():
    """
    Return an int of bit values which defines the uplink-to-wan status,
    such as if cellular is in use, etc

    For now, we just watch value. TBD - get quality or event direct from FW

    :return int: return bits
    """
    return WAN_WIRE_UPLINK


def router_wan_online():
    """
    True if router has uplink by any means to the internet.

    :return bool: True if time.time() returns something useful
    """
    return True

