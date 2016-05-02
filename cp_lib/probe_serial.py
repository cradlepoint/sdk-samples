"""
probe (get) the various serial configurations
"""
import json

from cp_lib.app_base import CradlepointAppBase
from cp_lib.parse_data import parse_boolean

"""
Serial in API tree:

./config/system/gpio_actions:
    "serial_gpio_enable": true,

./config/system/gps:
    {
    "connections": [
        {
            "_id_": "00000000-cb35-39e3-bc26-7b4f4c4a",
            "distance_interval_meters": 0,
            "enabled": true,
            "interval": 10,
            "language": "nmea",
            "name": "serial",
            "nmea": {"include_id": true, "prepend_id": false, ...}
            "serial_port": "ttyS1",
            "stationary_distance_threshold_meters": 20,
            "stationary_movement_event_threshold_seconds": 0,
            "stationary_time_interval_seconds": 0,
            "taip": {"include_cr_lf_enabled": false, "provide_al": true, ...}
        }
    ],
    "debug": {"flags": 0, "log_nmea_to_fs": false},
    "enable_gps_keepalive": false,
    "enable_gps_led": false,
    "enabled": true,
    "pwd_enabled": false,
    "taip_vehicle_id": "0000"
    }

./config/system/serial:
    "serial": {
        "enabled": false,
        "serial_port": "ttyS1",
        "status": "Disabled",
        "baud_rate": 9600,
        "byte_parity": 0,
        "byte_size": 8,
        "flow_control": {
            "hardware": false,
            "software": true
        },
        "linefeed": 2,
        "server": {
            "lan": true,
            "lan_admin": true,
            "port": 7218,
            "wan": false
        },
        "stop_bits": 0
    }

./control - non found; in theory some of the ./control/gpio affect pin
    levels when set to GPIO mode, but some do not work

./status/system/serial - not sure what this is
    'serial': {
        'status': 'Disabled'
    },

./status/devices/ethernet-wan/status/info:
    'serial': 'unset', ! this appears to be 'serial number'

On the 1100, these features can use serial:
- redirector
- GPS (optional forward as output-repeater)
- GPIO serial mode
- Console - the 'serial' command

Also, Linux (in theory) allows any/all threads to share opening the port.

"""


class RouterApiBase(object):
    """
    fetch and abstract a block from Router API, such as ./config/system/serial

    To use:
    - create an instance:
        obj = SerialRedirectorConfig(app_base)
    - call refresh() to go read/get values using app-base.cs_client
        object.refresh()

    """

    def __init__(self, app_base, topic=None):
        """
        :param CradlepointAppBase app_base: use for cs_client
        :param str topic: the API path, such as "./config/system/serial"
        :return:
        """
        if topic is None:
            raise ValueError("topic required")

        self.topic = self.validate_topic(topic)
        self.tree = dict()
        self.app_base = app_base
        return

    @staticmethod
    def validate_topic(topic):
        """

        :param str topic:
        :return:
        """
        if isinstance(topic, bytes):
            topic = topic.decode()

        if topic.startswith('./'):
            # chop off the leading './'
            topic = topic[2:]

        elif topic[0] == '.':
            # chop off the leading '.'
            topic = topic[1:]

        elif topic[0] == '/':
            # chop off the leading '/'
            topic = topic[1:]

        if topic.startswith('status'):
            return topic
        elif topic.startswith('config'):
            return topic
        elif topic.startswith('control'):
            return topic
        elif topic.startswith('state'):
            return topic

        raise ValueError("Router API topic lacks valid tree name")

    def refresh(self):
        """
        Cause the action of fetching the
        :return:
        """
        if self.topic is None or self.topic == "":
            raise ValueError("Bad Router API topic")

        # clear the old tree
        self.tree = dict()

        save_state = self.app_base.cs_client.show_rsp
        self.app_base.cs_client.show_rsp = False
        result = self.app_base.cs_client.get(self.topic)
        self.app_base.cs_client.show_rsp = save_state

        if result is None:
            self.app_base.logger.error(
                "Aborting - Router({}) is not accessible".format(
                    self.app_base.cs_client.router_ip))
            return None

        if isinstance(result, str):
            result = json.loads(result)

        self.tree = result

        return result


class SerialRedirectorConfig(RouterApiBase):
    """
    fetch and abstract serial redirector values.

    To use:
    - create an instance:
        obj = SerialRedirectorConfig(app_base)
    - call refresh() to go read/get values using app-base.cs_client
        object.refresh()
    """
    MY_TOPIC = "config/system/serial"

    def __init__(self, app_base):
        """
        :param CradlepointAppBase app_base:
        :return:
        """
        super().__init__(app_base, self.MY_TOPIC)
        return

    def enabled(self, match_name=None):
        """
        Check self.tree, return T/F if is enabled

        :param str match_name: if set like "ttyS1", confirm matches
                               ["serial_port"] setting
        :return:
        """
        tag = "enabled"
        if tag not in self.tree:
            raise KeyError("{}/{} is not present".format(self.topic, tag))

        # get value, insure isn't string like "true" or "0"
        enabled = parse_boolean(self.tree[tag])
        if enabled and match_name is not None:
            # then test the serial_port name
            port_name = self.port_name(full_path=False)
            if match_name != port_name:
                return False
            # else assume is as desired

        return enabled

    def port_name(self, full_path=False):
        """
        Check self.tree, return string like "ttyS1"

        :param bool full_path: if True, prepend the "/dev/", else return raw
        :return:
        """
        tag = "serial_port"
        if tag in self.tree:
            if full_path:
                return "/dev/" + self.tree[tag]
            else:
                return self.tree[tag]

        raise KeyError("{}/{} is not present".format(self.topic, tag))


class SerialGPIOConfig(RouterApiBase):
    """
    fetch and abstract serial redirector values.

    ./config/system/gpio_actions:
        "serial_gpio_enable": true,
    """
    MY_TOPIC = "config/system/gpio_actions"

    def __init__(self, app_base):
        """
        :param CradlepointAppBase app_base:
        :return:
        """
        super().__init__(app_base, self.MY_TOPIC)
        return

    def enabled(self):
        """
        Check self.tree, return T/F if is enabled
        :return:
        """
        tag = "serial_gpio_enable"
        if tag in self.tree:
            # get value, insure isn't string like "true" or "0"
            value = parse_boolean(self.tree[tag])
            return value

        raise KeyError("{}/{} is not present".format(self.topic, tag))


class SerialGpsConfig(RouterApiBase):
    """
    fetch and abstract serial use of GPS values

    If more complex, since we need to parse the "connections" list

    ./config/system/gps:
        {
        "connections": [
            {
                "_id_": "00000000-cb35-39e3-bc26-7b4f4c4a",
                "distance_interval_meters": 0,
                "enabled": true,
                "interval": 10,
                "language": "nmea",
                "name": "silly",
                "nmea": {"include_id": true, "prepend_id": false, ...}
            >>  "serial_port": "ttyS1",
                "stationary_distance_threshold_meters": 20,
                "stationary_movement_event_threshold_seconds": 0,
                "stationary_time_interval_seconds": 0,
                "taip": {"include_cr_lf_enabled": false, ...}
            },
            {
                "_id_": "00000001-cb35-39e3-bc26-7b4f4c4a",
                "distance_interval_meters": 0,
                "enabled": true,
                "interval": 10,
                "language": "nmea",
                "name": "my-self",
                "nmea": {"include_id": true, ...},
            >>  "server": {
                    "lan": true,
                    "port": 9999,
                    "wan": false
                },
                "stationary_distance_threshold_meters": 20,
                "stationary_movement_event_threshold_seconds": 0,
                "stationary_time_interval_seconds": 0,
                "taip": {"include_cr_lf_enabled": false, ...}
            },
            {
                "_id_": "00000002-cb35-39e3-bc26-7b4f4c4a",
            >>  "client": {
                    "num_sentences": 1000,
                    "port": 9998,
                    "server": "127.0.0.1",
                    "time_interval": {
                        "enabled": false,
                        "end_time": "5:00 PM",
                        "start_time": "9:00 AM"
                    },
                    "useudp": false
                },
                "distance_interval_meters": 0,
                "enabled": true,
                "interval": 10,
                "language": "nmea",
                "name": "hollywood",
                "nmea": {"include_id": true, ...}
                "stationary_distance_threshold_meters": 20,
                "stationary_movement_event_threshold_seconds": 0,
                "stationary_time_interval_seconds": 0,
                "taip": {"include_cr_lf_enabled": false, ...}
            }
        ],
    """
    MY_TOPIC = "config/system/gps"

    def __init__(self, app_base):
        """
        :param CradlepointAppBase app_base:
        :return:
        """
        super().__init__(app_base, self.MY_TOPIC)
        return

    def enabled(self, match_name=None):
        """
        Check self.tree, return T/F if is enabled

        :param str match_name: if set like "ttyS1", confirm matches
                               ["serial_port"] setting
        :return:
        """
        # do we really care if base [enabled] is True/False? Would existence
        # of a serial destination impact serial port availability

        tag = "enabled"
        if tag not in self.tree:
            raise KeyError("{}/{} is not present".format(self.topic, tag))

        gps_enabled = parse_boolean(self.tree[tag])
        if not gps_enabled:
            # per FW programmer, if this 'master' setting is false, then
            # any serial config has been released (neutralized)
            return False

        tag = "connections"
        if tag not in self.tree:
            raise KeyError("{}/{} is not present".format(self.topic, tag))

        for destination in self.tree[tag]:
            # check each destination for a "serial_port" value. by default
            # the "name" will be serial, but since user can change we cannot
            # assume it will be "serial" here
            if "serial_port" in destination:
                if match_name is not None:
                    return match_name == destination["serial_port"]
                else:
                    return True

        return False


def probe_if_serial_available(app_base, match_name=None):
    """
    See if any of our configs seem to be using serial port

    the return dictionary has keys:
    [available] = True/False - False is ANY functions is using
    [port_name] "ttyS1" - only exists if 'match_name' passed in
    [serial_gpio] = True/False - True if THIS function is using
    [serial_gps] = True/False - True if THIS function is using
    [serial_redirector] = True/False - True if THIS function is using

    if [serial_gpio] or [serial_gps] or [serial_redirector] is None,
    then the GET of the config failed for specific function

    if ALL three functions are error/None, then [available] is None

    TODO - does throwing error with failed config make sense? I did not
    because I am guessing SOME routers will not have (for example) the
    serial_gpio or gps configs.

    :param CradlepointAppBase app_base: use for cs_client
    :param str match_name: if set like "ttyS1", confirm matches
                           ["serial_port"] setting
    :return:
    :rtype: dict
    """
    result = dict()
    if match_name is not None:
        result["port_name"] = match_name

    serial_in_use = False

    # check the serial redirector configuration
    obj = SerialRedirectorConfig(app_base)
    app_base.logger.info("Fetch {}".format(obj.topic))
    config = obj.refresh()
    if config is None:
        result["serial_redirector"] = None

    else:
        value = obj.enabled(match_name)
        serial_in_use |= value
        result["serial_redirector"] = value
    del obj

    # check the serial gpio configuration
    obj = SerialGPIOConfig(app_base)
    app_base.logger.info("Fetch {}".format(obj.topic))
    config = obj.refresh()
    if config is None:
        result["serial_gpio"] = None

    else:
        # result["serial_gpio"] = obj.enabled(match_name)
        # doesn't show used port name
        value = obj.enabled()
        serial_in_use |= value
        result["serial_gpio"] = value
    del obj

    # check the serial gps dump configuration
    obj = SerialGpsConfig(app_base)
    app_base.logger.info("Fetch {}".format(obj.topic))
    config = obj.refresh()
    if config is None:
        result["serial_gps"] = None

    else:
        value = obj.enabled(match_name)
        serial_in_use |= value
        result["serial_gps"] = obj.enabled(match_name)
    del obj

    if result["serial_redirector"] is None and \
            result["serial_gpio"] is None and result["serial_gps"] is None:
        # if all are None (pad config), then return ["available"] as None
        result["available"] = None

    else:
        # at least one config was good - likely all were
        result["available"] = not serial_in_use

    return result
