"""
Load Router API "config/system/gps" settings.
"""

from cp_lib.app_base import CradlepointAppBase, CradlepointRouterOffline


class GpsConfig(object):
    """
    fetch router's GPS config, allowing questions to be asked

    :param CradlepointAppBase app_base:
    """
    def __init__(self, app_base):
        self.app_base = app_base
        self.data = None
        self.refresh()
        return

    def refresh(self):
        self.data = fetch_gps_config(self.app_base)
        return

    def is_enabled(self):
        """
        return if GPS is enabled. We say False if data is bad!

        :return bool: T/F
        """
        if self.data is None:
            return False

        return self.data.get("enabled", False)

    def keepalive_is_enabled(self):
        """
        return if GPS Keepalive is enabled.

        Allow KeyError if our data is bad. Technically, do not call
        this if self.is_enabled() == False

        :return bool: T/F
        """
        return self.data.get("enable_gps_keepalive", False)

    def get_client_info(self):
        """
        return the FIRST instance of a client (we send to server)

        Allow KeyError if our data is bad. Technically, do not call
        this if self.is_enabled() == False

        :return bool: T/F
        :rtype: None or (str, int)
        """
        if "connections" in self.data:
            for client in self.data["connections"]:
                # test each sender / client
                # self.app_base.logger.debug("client:{}".format(client))
                if "client" in client:
                    # then found gps/connections[]/client
                    if client.get("enabled", False):
                        # then found gps/connections[]/enabled == True
                        server_ip = client["client"].get("server", None)
                        server_port = client["client"].get("port", None)
                        if server_ip is not None and server_port is not None:
                            return server_ip, int(server_port)

        # if still here, we don't have, so return None
        return None


def fetch_gps_config(app_base, return_raw=True):
    """
    Load Router API "config/system/gps" and answer things about it.

    $ cat config/system/gps
    {
    "connections": [
        {
            "_id_": "00000000-cb35-39e3-bc26-fd7b4f4c4a",
            "client": {
                "port": 9999,
                "server": "192.168.35.6",
                "time_interval": {
                    "enabled": false,
                    "end_time": "5:00 PM",
                    "start_time": "9:00 AM"
                }
            },
            "distance_interval_meters": 0,
            "enabled": true,
            "interval": 10,
            "language": "nmea",
            "name": "my pc",
            "stationary_distance_threshold_meters": 20,
            "stationary_movement_event_threshold_seconds": 0,
            "stationary_time_interval_seconds": 0
        }
    ],
    "debug": {
        "flags": 0,
        "log_nmea_to_fs": false
    },
    "enable_gps_keepalive": true,
    "enable_gps_led": false,
    "enabled": true,
    "pwd_enabled": false,
    "taip_vehicle_id": "0000"
    }

    :param CradlepointAppBase app_base:
    :param bool return_raw: if True, return API data as-is, else REDUCE
    :return dict: the merged settings
    """
    import json

    assert isinstance(app_base, CradlepointAppBase)

    save_state = app_base.cs_client.show_rsp
    app_base.cs_client.show_rsp = False
    result = app_base.cs_client.get("config/system/gps")
    app_base.cs_client.show_rsp = save_state

    if result is None:
        raise CradlepointRouterOffline(
            "Aborting - Router({}) is not accessible".format(
                app_base.cs_client.router_ip))

    if isinstance(result, str):
        result = json.loads(result)

    if return_raw:
        # for future use, and common module
        pass

    return result
