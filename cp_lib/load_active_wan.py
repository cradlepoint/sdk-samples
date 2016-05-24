"""
Load Router API "status/wan/devices/mdm-xx"
"""
from cp_lib.app_base import CradlepointAppBase, CradlepointRouterOffline

KEY_NAME = 'name'
KEY_ACTIVE = "connected"
KEY_LIVE_GPS = 'gps'


class ActiveWan(object):
    """
    fetch router's WAN data, allowing questions to be asked

    :param CradlepointAppBase app_base:
    """
    def __init__(self, app_base):
        self.app_base = app_base
        self.data = None
        self.refresh()
        return

    def refresh(self):
        self.data = fetch_active_wan(self.app_base)
        return

    def get_imei(self):
        """
        Scan for the first imei value.

        ['imei'] is IMEI string (or info.serial)

        :return:
        """
        if self.data[KEY_ACTIVE]['imei'] not in (None, "", "unset"):
            # assume 'active' if it seems valid
            return self.data[KEY_ACTIVE]['imei']

        for key, value in self.data.items():
            # else get first valid seeming one
            if 'imei' in value and value['imei'] not in (None, "", "unset"):
                return value['imei']

    def supports_gps(self):
        """
        Scan for the first wan claiming 'support_gps'

        ['supports_gps'] is T/F based on modem hw (or info.supports_gps)

        :return:
        """
        if self.data[KEY_LIVE_GPS] not in (None, {}):
            # then we have a fix
            return True

        # slightly special - we might support GPS, but not yet have a fix
        for key, value in self.data.items():
            # else get first valid seeming one
            if value.get('supports_gps', False):
                # then at least 1 claims support
                return True

        # else, none claimed to support gps
        return False

    def get_live_gps_data(self):
        """
        return last-seen GPS data

        :return:
        """
        return self.data[KEY_LIVE_GPS]


def fetch_active_wan(app_base, return_raw=False):
    """
    Load Router API "/status/wan/devices" into settings.

    If return_raw=True, you'' receive the full dict returned via the
        status API tree

    Else if return_raw=False, you receive a reduced dict. In the base level,
        it will contain the same dict() as "/status/wan/devices", however
        there will be 1 extra, as ["active"] which is an alias to the
        modem currently serving as the uplink

    Example:
    output['mdm-436abc4f'] = {"connection_state": "disconnected", ...}
    output['mdm-43988388'] = {"connection_state": "connected", ...}
    output['active'] = {"connection_state": "connected", ...}

    But remember that in this example,
        output['mdm-43988388'] == output['active'] in every way - even
        memory allocation, so changing output['mdm-43988388']['imei'] also
        changes output['active']['imei'] !!

    Since the ['name'] key is added, you can see that
    output['mdm-436abc4f']['name'] == 'mdm-436abc4f'
    output['mdm-43988388']['name'] == 'mdm-43988388'
    output['active']['name'] == 'mdm-43988388'

    :param CradlepointAppBase app_base:
    :param bool return_raw: if True, return API data as-is, else REDUCE
    :return dict: the merged settings
    """
    import json

    assert isinstance(app_base, CradlepointAppBase)

    save_state = app_base.cs_client.show_rsp
    app_base.cs_client.show_rsp = False
    result = app_base.cs_client.get("/status/wan/devices")
    app_base.cs_client.show_rsp = save_state

    if result is None:
        raise CradlepointRouterOffline(
            "Aborting - Router({}) is not accessible".format(
                app_base.cs_client.router_ip))

    if isinstance(result, str):
        result = json.loads(result)

    if not return_raw:
        # then 'reduce' complexity as defined in make_modem_dict()

        # the base section with have multiple modem and wired/wan sections.
        # most cellular products have '2' modems, which is a fake design
        # to support 2 SIM
        wan_items = []
        for key, value in result.items():
            wan_items.append(key)

        # sort in-place, just to make life easier
        wan_items.sort()

        output = dict()

        for modem in wan_items:
            output[modem] = _make_modem_dict(modem, result[modem])

            # the 'first' WAN we find which is 'connected' becomes
            # output['active']
            if KEY_ACTIVE not in output:
                if output[modem]['connection_state'].lower() == 'connected':
                    output[KEY_ACTIVE] = output[modem]

            # set up the GPS source
            if KEY_LIVE_GPS not in output:
                if output[modem].get('supports_gps', False):
                    # then we claim to support
                    if 'gps' in output[modem] and \
                                    len(output[modem]['gps']) > 0:
                        output[KEY_LIVE_GPS] = output[modem]['gps']

        # we shouldn't change 'result' until out of the loop
        if KEY_ACTIVE not in output:
            output[KEY_ACTIVE] = None
        if KEY_LIVE_GPS not in output:
            output[KEY_LIVE_GPS] = None
        result = output

    return result


def _make_modem_dict(modem_name, xdct):
    """
    Given an API dict, plus modem name, create our simpler reduced dict. If
    all goes well, it will contain:
    ['imei'] is IMEI string (or info.serial)
    ['supports_gps'] is T/F based on modem hw (or info.supports_gps)
    ['tech'] is string like 'lte/3G' based on modem hw (or info.tech)
    ['summary'] string like 'connected' or 'configure error' (status.summary)
    ['connection_state'] string like 'disconnected' or 'connected'
                        (status.connection_state)
    ['uptime'] None or float, seconds 'up' (status.uptime)
    ['gps'] dict. Empty if no lock, else last data (status.gps)
    ['ipinfo'] dict. Empty if no link, else cellular IP data (status.ipinfo)

    ['gps'] may be like:
        {'nmea':
          {'GPVTG': '$GPVTG,,T,0.0,M,0.0,N,0.0,K,A*0D\r\n',
           'GPGGA': '$GPGGA,183820.0,4500.815065,N,09320.092759,W,1,06,0.8,
                     282.8,M,-33.0,M,,*6B\r\n',
           'GPRMC': '$GPRMC,183820.0,A,4500.815065,N,09320.092759,W,0.0,,
                     110516,0.0,E,A*3D\r\n'},
           'fix':
              {'age': 45.68415999998978,
               'lock': True,
               'satellites': 6,
               'time': 183820,
               'longitude': {'minute': 20, 'second': 5.5644001960754395,
                             'degree': -93},
               'latitude': {'minute': 0, 'second': 48.902400970458984,
                            'degree':45}
        }}

    ['ipinfo'] may be like:
        {'ip_address': '10.109.130.98'
         'netmask': '255.255.255.252',
         'gateway': '10.109.130.97',
         'dns': ['172.26.38.1', '172.26.38.2']}

    :param str modem_name: the official name
    :param xdct: the dictionary at /status/wan/devices/modem_name
    :return:
    :rtype: dict
    """
    result = dict()
    result[KEY_NAME] = modem_name
    result['path'] = "/status/wan/devices" + "/" + modem_name

    if "info" in xdct:
        temp = xdct['info']
        if "serial" in temp:
            if temp['serial'] in (None, "", "unset"):
                result['imei'] = None
            else:
                result['imei'] = temp['serial']
        if "supports_gps" in temp:
            result['supports_gps'] = temp['supports_gps']
        else:
            result['supports_gps'] = False
        if "tech" in temp:
            result['tech'] = temp['tech']
    if "status" in xdct:
        temp = xdct['status']
        if "summary" in temp:
            result['summary'] = temp['summary']
        if "connection_state" in temp:
            result['connection_state'] = temp['connection_state']
        if "uptime" in temp:
            result['uptime'] = temp['uptime']
        if "gps" in temp:
            result['gps'] = temp['gps']
        else:
            result['gps'] = {}
        if "ipinfo" in temp:
            result['ipinfo'] = temp['ipinfo']

    return result
