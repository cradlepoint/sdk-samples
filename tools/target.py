import ipaddress
import logging
import os
import subprocess
import sys

from cp_lib.app_base import CradlepointAppBase
# from cp_lib.cs_client import CradlepointClient

DEF_TARGET_INI = "config/target.ini"
DEF_INTERFACE = "Local Area Connection"
DEF_COMPUTER_IP_LAST_OCTET = 6

PING_COUNT = 3

# set this to True to force the router's syslog message to include
#   the UTF8 flag, else set to False
SYSLOG_UTF8_FLAG = False

# suppress interface show like: Configuration for interface "Loopback ...
LIST_INTERFACE_NO_LOOPBACK = True

# suppress interface show like: Config for interface "VMware or VirtualBox
LIST_INTERFACE_NO_VM = True


class TheTarget(CradlepointAppBase):

    ACTION_DEFAULT = "show"
    ACTION_NAMES = ("ping", "reboot", "set", "show", "syslog")
    ACTION_HELP = {
        "ping": "Ping my router",
        "reboot": "Reboot my router",
        "set":
            "given an alias/nickname, edit the ./config/settings.ini to match",
        "show": "Show Interfaces / IP Info",
        "syslog":
            "Check router 'system logging' - show status, force to be syslog",
    }

    def __init__(self):
        """Basic Init"""
        from cp_lib.load_settings_ini import copy_config_ini_to_json

        if not os.path.isfile("./config/settings.json"):
            # make sure we have at least a basic ./config/settings.json
            copy_config_ini_to_json()

        # we don't contact router for model/fw - will do in sanity_check,
        # IF the command means contact router
        CradlepointAppBase.__init__(self, call_router=False, log_name="target")

        self.action = self.ACTION_DEFAULT

        self.verbose = True

        # the one 'target' we are working on (if given)
        self.target_alias = None

        # the data loaded from the TARGET.INI file
        self.target_dict = None

        # the one computer interface we are targeting
        self.target_interface = DEF_INTERFACE

        # save IP related to target and/or the interface
        self.target_my_ip = None
        self.target_my_net = None
        self.target_router_ip = None

        return

    def run(self):
        """Dummy to satisfy CradlepointAppBase"""
        return

    def main(self):
        """

        :return int: code for sys.exit()
        """

        result = 0
        self.logger.info("Target Action:{0}".format(self.action))

        # the data loaded from the TARGET.INI file
        self.target_dict = self.load_target_ini()

        try:
            self.target_interface = self.settings["router_api"]["interface"]
        except KeyError:
            pass

        self.target_my_ip, self.target_my_net = self.get_interface_ip_info(
            self.target_interface)

        self.logger.info("Target Alias:{0}".format(self.target_alias))
        self.logger.info("Target Interface, Name:{0}".format(
            self.target_interface))
        self.logger.info("Target Interface, PC IP:{0}".format(
            self.target_my_ip))
        self.logger.info("Target Interface, Network:{0}".format(
            self.target_my_net))

        if self.action == "ping":
            result = self.action_ping()

        elif self.action == "set":
            result = self.action_set()

        elif self.action == "show":
            result = self.action_show()

        elif self.action == "syslog":
            result = self.action_syslog()

        return result

    def action_ping(self, name=None):
        """
        Attempt to ping the router

        :param str name: optional alias name, matching a section in TARGET.INI
        """
        if name is None:
            # note that target_alias might also be None
            name = self.target_alias

        ping_ip = self.get_router_ip(name)

        result = 0

        if ping_ip is None:
            if name is not None:
                # then
                self.logger.debug(
                    "PING - assume HOST can resolve name:{}".format(name))
                ping_ip = ipaddress.IPv4Address(name)
            else:
                self.logger.error("Cannot PING - not enough target info given")
                result = -1

        if ping_ip is not None:
            if sys.platform == "win32":
                command = ["ping", "-n", str(PING_COUNT), ping_ip.exploded]
            else:
                command = ["ping", "-c", str(PING_COUNT), ping_ip.exploded]

            result = subprocess.call(command)
            if result:
                self.logger.error(
                    "PING {} failed - return code:{}".format(ping_ip, result))
            else:
                self.logger.info("PING {} was good".format(ping_ip))

        return result

    def action_reboot(self, name=None):
        """
        Go to our router, and reboot it

        :param str name: optional alias name, matching a section in TARGET.INI
        :return int: value intended for sys.exit()
        """
        if name is None:
            # note that target_alias might also be None
            name = self.target_alias

        reboot_ip = self.get_router_ip(name)

        self.logger.info(
            "Reboot our active development router({})".format(reboot_ip))
        url = "http://{0}/api/control/system/reboot".format(
            self.get_router_ip())
        # we do need the 2nd quotes here
        # data = {"data": '\x7A\x16'}
        data = {"data": "true"}

        # result = self._do_action(url, data=data, post=True)
        # if result == 0:
        #     self.logger.info("SDK reboot successful")

        return 0

    def action_set(self, name=None, ini_name=None):
        """
        Given a alias from target.ini, edit the ./config/settings.ini to
        make the alias the active target

        :param str name: the alias or section name in target.ini to use
        :param str ini_name: optionally, change the name of the
                             ./config/settings.ini (for testing)
        :return:
        """
        from cp_lib.load_settings_json import DEF_GLOBAL_DIRECTORY, \
            DEF_SETTINGS_FILE_NAME

        if name is None:
            # if nothing passed in, assume is the alias from command line
            name = self.target_alias

        if ini_name is None:
            # if no alternative file name passed in,
            #       use default of "./config/settings.ini"
            ini_name = os.path.join(DEF_GLOBAL_DIRECTORY,
                                    DEF_SETTINGS_FILE_NAME + ".ini")

        if name not in self.target_dict:
            self.logger.error("SET failed - target name {} is unknown")
            return -1

        # these are the only supported fields in section [router_api]
        user_name = self.target_dict[name].get("user_name", None)
        interface = self.target_dict[name].get("interface", None)
        local_ip = self.target_dict[name].get("local_ip", None)
        password = self.target_dict[name].get("password", None)

        if local_ip is None:
            syslog_ip = None
        else:
            syslog_ip = self.make_computer_ip(local_ip)

        self.logger.debug("SET: open file:{}".format(ini_name))
        try:
            with open(ini_name) as _file_han:
                source = _file_han.readlines()

        except FileNotFoundError:
            self.logger.error(
                "SET failed - settings file {} not found".format(ini_name))
            return -1

        dst = []
        state = "out"
        changed = False
        for line in source:
            value = line.strip()

            if len(value) == 0:
                # these always copy verbatim, but we reset to no special mode
                state = "out"

            elif value[0] == ';':
                # these always copy verbatim, with no change of state
                pass

            elif state == "out":
                # then seeking our sections
                if value.startswith("[router_api"):
                    state = "api"

                if value.startswith("[logging"):
                    state = "log"

            else:  # assume we're inside on of the sections

                if state == "api":
                    if user_name is not None and \
                            value.startswith("user_name"):
                        # change out the user_name
                        value = "user_name={}".format(user_name)
                        changed = True

                    elif interface is not None and \
                            value.startswith("interface"):
                        # change out the interface
                        value = "interface={}".format(interface)
                        changed = True

                    elif local_ip is not None and \
                            value.startswith("local_ip"):
                        # change out the local_ip
                        value = "local_ip={}".format(local_ip)
                        changed = True

                    elif password is not None and \
                            value.startswith("password"):
                        # change out the password
                        value = "password={}".format(password)
                        changed = True

                elif state == "log":
                    if syslog_ip is not None and \
                            value.startswith("syslog_ip"):
                        # change out the syslog_ip
                        value = "syslog_ip={}".format(syslog_ip)
                        changed = True

            dst.append(value)

            temp = line.strip()
            if temp != value:
                self.logger.debug("SET: [{}] > [{}]".format(temp, value))
            # else:
            #     self.logger.debug("SET: [{}] no change".format(value))

        if not changed:
            self.logger.info("SET: nothing changed - doing nothing")
            result = 0

        else:
            bak_name = ini_name + ".bak"
            if os.access(bak_name, os.F_OK):
                # remove any old backup
                os.remove(bak_name)

            # save the original
            os.rename(ini_name, bak_name)

            # save out the file
            self.logger.debug("SET: rewriting file:{}".format(ini_name))
            with open(ini_name, "w") as _file_han:
                for line in dst:
                    _file_han.write(line + '\n')

            # change the computer's IP
            if interface is None:
                # use the 'new' interface, else our default
                interface = self.target_interface

            if syslog_ip is None:
                # this is problem
                raise ValueError

            result = self.set_computer_ip(interface, syslog_ip)

        return result

    def action_syslog(self, name=None):
        if name is None:
            # note that target_alias might also be None
            name = self.target_alias

        router_ip = self.get_router_ip(name)

        if router_ip is None:
            self.logger.error(
                "Cannot check Syslog - not enough target info given")
            return -1

        result = self.cs_client.get("config/system/logging")
        if not isinstance(result, dict):
            # some error?
            self.logger.error("get of config/system/logging failed")
            return -2

        # FW 6.1 example of get("config/system/logging")
        # {"console": false, "firewall": false, "max_logs": 1000,
        #  "services": []
        #  "modem_debug": {"lvl_error": false, "lvl_info": false,
        #                  "lvl_trace": false, "lvl_warn": false },
        #  "enabled": true,  - show always be true?
        #  "level": "debug", - set to "debug" or "info", etc
        #  "remoteLogging": {
        #       "enabled": true, - set T to enable remote syslog
        #       "serverAddr": "192.168.30.6", - set to IP of syslog server
        #       "system_id": false, - always set False (for now)
        #       "utf8_bom": false, - always set false (for now)
        # },

        # assume everything is as expected
        logging_setting_good = True

        logging_level = result.get("level", None)
        self.logger.info("{}: Logging level = {}".format(
            router_ip.exploded, logging_level))
        # self.logger.debug("{}:control/system/logging/level = {}".format(
        #       router_ip.exploded, logging_level))

        syslog_enabled = False
        syslog_ip = None

        if "remoteLogging" not in result:
            self.logger.error(
                "{}:config/system/logging/remoteLogging is not present".format(
                    router_ip.exploded))
            logging_setting_good = False

        else:
            syslog_enabled = result["remoteLogging"].get("enabled", False)
            syslog_ip = result["remoteLogging"].get("serverAddr", None)

        if syslog_enabled:
            self.logger.info(
                "{}: Remote Syslog logging is enabled".format(
                    router_ip.exploded))
            # self.logger.debug(
            # "{}:control/system/logging/remoteLogging/enabled = True".format(
            #     router_ip.exploded))

            if syslog_ip is None:
                logging_setting_good = False
            else:
                self.logger.info("{}: Remote Syslog IP address is {}".format(
                    router_ip.exploded, syslog_ip))
            # self.logger.debug(
            # "{}:control/system/logging/remoteLogging/serverAddr = {}".format(
            #     router_ip.exploded, syslog_ip))
        else:
            self.logger.info(
                "{}: Remote Syslog logging is disabled".format(
                    router_ip.exploded))
            # self.logger.debug(
            # "{}:control/system/logging/remoteLogging/enabled = False".format(
            #     router_ip.exploded))
            logging_setting_good = False

        if not logging_setting_good:
            # then at least one setting is not as desired
            desired = {"enabled": True, "level": "debug",
                       "remoteLogging": {"enabled": True,
                                         "utf8_bom": SYSLOG_UTF8_FLAG}}
            if syslog_ip is None:
                # if no IP, use this computer's IP from the active interface
                syslog_ip = self.target_my_ip.explode

            desired["remoteLogging"]["serverAddr"] = syslog_ip
            self.logger.debug("desire:{}".format(desired))

            """ :type self.cs_client: CradlepointClient"""
            value = "debug"
            result = self.cs_client.put("config/system/logging",
                                        {"level": value})
            if result != value:
                self.logger.error(
                    "PUT logging/level = {} failed, result={}".format(
                        value, result))

            # false is 'not a boolean'
            # False is 'not a boolean'
            # "0" is not a boolean
            value = False
            result = self.cs_client.put(
                "config/system/logging/remoteLogging", {"enabled": value})
            if result != value:
                self.logger.error(
                    "PUT logging/remoteLogging/enabled={}".format(value) +
                    " failed, result={}".format(result))

        return 0

    def action_show(self):
        """
        Do simplified dump/display of interfaces, assuming multi-homed computer

        """
        self.logger.info("")
        self.logger.info("Show Interfaces:")

        report = self.list_interfaces()
        for line in report:
            self.logger.info("{}".format(line))
        return 0

    def load_target_ini(self, ini_name=None):
        """
        Convert the ./config/target.ini into a dictionary

        Assume we start with INI like this:
        [AER2100]
        local_ip=192.168.21.1
        password=4416ec79

        Want a dict() like this:
        {
            "AER2100": {
                "local_ip": "192.168.21.1",
                "password": "4416ec79"
            }
        }

        :param str ini_name: relative directory path to the INI file -
                             in None, assume ./config/target.ini
        :return dict: the prepared data as dict
        """
        import configparser

        if ini_name is None:
            ini_name = DEF_TARGET_INI

        target_dict = dict()

        if not os.path.isfile(ini_name):
            # if INI file DOES NOT exist, return - existence is not
            #       this module's responsibility!
            self.logger.debug(
                "Target INI file {} does NOT exist".format(ini_name))
            return target_dict

        self.logger.debug("Read TARGET.INI file:{}".format(ini_name))

        # LOAD IN THE INI FILE, using the Python library
        target_config = configparser.ConfigParser()
        # READ indirectly, config.read() tries to open cp_lib/config/file.ini,
        #       not config/file.ini
        file_han = open(ini_name, "r")
        try:
            target_config.read_file(file_han)

        except configparser.DuplicateOptionError as e:
            self.logger.error(str(e))
            self.logger.error("Aborting TARGET")
            sys.exit(-1)

        finally:
            file_han.close()
        self.logger.debug("  Sections:{}".format(target_config.sections()))

        # convert INI/ConfigParser to Python dictionary
        for section in target_config.sections():

            target_dict[section] = {}
            # note: 'section' is the old possibly mixed case name;
            #       section_tag might be lower case
            for key, val in target_config.items(section):
                target_dict[section][key] = val

        return target_dict

    def get_router_ip(self, name=None):
        """
        Given name, or self.target_interface, try to guess what router IP is

        :param str name: optional alias name
        :return: the IP as IPv4Address() object, or None
        :rtype: ipaddress.IPv4Address
        """
        router_ip = None

        if name is None:
            # then just ping the Router on self.target_interface
            if self.target_my_net is not None:
                self.logger.debug(
                    "Get Router IP - see if we have router on " +
                    "interface:{}".format(self.target_interface))
                # walk through our target list looking for first
                #       router IP on targeted interface,
                # which is like:
                # "AER2100": {
                #     "local_ip": "192.168.21.1",
                #     "password": "4416ec79"
                # }
                for router in self.target_dict:
                    # self.logger.debug("Check IP of router:{}".format(router))
                    try:
                        router_ip = ipaddress.IPv4Address(
                            self.target_dict[router]["local_ip"])

                    except KeyError:
                        self.logger.warning(
                            'Router[{}] lacks an ["local_ip"] value'.format(
                                router))
                        continue

                    except ipaddress.AddressValueError:
                        self.logger.warning(
                            'Router[{}] has invalid ["local_ip"] value'.format(
                                router))
                        continue

                    if router_ip in self.target_my_net:
                        # this is first router found in correct subnet, use it
                        self.logger.debug(
                            "Found router[{}] with ".format(router) +
                            "IP[{}] in correct subnet".format(router_ip))
                        break

                    # else self.logger.debug("try another")
            # else leave as None, router_ip = None

        else:  # try to find the alias
            if name in self.target_dict:
                self.logger.debug(
                    "Get Router IP - try to find IP of alias:{}".format(name))
                try:
                    router_ip = self.target_dict[name]["local_ip"]
                    self.logger.debug(
                        "Get Router IP - alias as IP:{}".format(router_ip))
                    router_ip = ipaddress.IPv4Address(router_ip)

                except KeyError:
                    self.logger.warning(
                        'Router[{}] lacks an ["local_ip"] value'.format(name))
                    return -1

                except ipaddress.AddressValueError:
                    self.logger.warning(
                        'Router[{}] has invalid ["local_ip"] value'.format(
                            name))
                    return -1

            # else leave as None

        return router_ip

    def scan_ini_get_ip_from_name(self, name):
        """
        Given a name (a section in target.ini)
            return the ["local_ip"] value as IPv4Address object

        :param str name:
        :return:
        :rtype: ipaddress.IPv4Address, bool
        """
        self.logger.debug("Given name:{}, scan for local_ip".format(name))

        # walk through our target list looking for first router IP on
        #       targeted interface,
        # which is like:
        # "AER2100": {
        #     "local_ip": "192.168.21.1",
        #     "password": "4416ec79"
        # }
        router_ip = None
        in_subnet = False
        if name in self.target_dict:
            try:
                router_ip = ipaddress.IPv4Address(
                    self.target_dict[name]["local_ip"])

            except ipaddress.AddressValueError:
                self.logger.warning(
                    'Router[{}] has invalid ["local_ip"] value'.format(name))

            if self.target_my_net is not None:
                # check if it is in our subnet
                in_subnet = router_ip in self.target_my_net
                self.logger.debug(
                    "IP[{}] is within current subnet".format(router_ip))

        self.logger.debug(
            "Found router[{}] with IP[{}]".format(name, router_ip))
        return router_ip, in_subnet

    def get_interface_ip_info(self, interface_name, report=None):
        """
        Given an interface name, return the computer's IP and network info.

        For example if interface_name == "ENet USB-1", returns 192.168.30.6
        [   "",
            "Configuration for interface \"ENet MB\"",
            "    IP Address:                           192.168.0.10",
            "    Subnet Prefix:                        192.168.0.0/24",
            "    Default Gateway:                      192.168.0.1",
            "",
            "Configuration for interface \"ENet USB-1\"",
            "    IP Address:                           192.168.30.6",
            "    Subnet Prefix:                        192.168.30.0/24",
            ""
        ]

        :param str interface_name: which interface we are targeting
                                   (from TARGET.INI or default)
        :param list report: a saved report, if any
        """
        if report is None:
            report = self.list_interfaces()

        self.logger.debug("Get IP for interface:{}".format(interface_name))

        my_ip = None
        my_net = None

        interface_name = '\"' + interface_name + '\"'
        _index = 0
        found_interface = False
        while _index < len(report):
            value = report[_index].strip()
            """ :type value: str """
            if len(value) > 0:
                match_cfg = "Configuration for interface"
                if value.startswith(match_cfg):
                    # then we are in the "Configuration for interface ..."
                    value = value[len(match_cfg):].strip()
                    if value == interface_name:
                        # self.logger.debug(
                        #   "Found Cfg interface:{}".format(value))
                        found_interface = True
                        match_ip = "IP Address:"
                        match_net = "Subnet Prefix:"
                        while len(report[_index]) > 0:
                            # walk through this configuration only
                            _index += 1
                            value = report[_index].strip()
                            # self.logger.debug("loop:{}".format(value))

                            if value.startswith(match_ip):
                                # like "IP Address: 192.168.30.6"
                                value = value[len(match_ip):].strip()
                                my_ip = ipaddress.IPv4Address(value)

                            if value.startswith(match_net):
                                # like "Subnet Prefix:
                                #       192.168.30.0/24 (mask 255.255.255.0)"
                                value = value[len(match_net):].strip()
                                offset = value.find(" ")
                                if offset >= 0:
                                    value = value[:offset]
                                my_net = ipaddress.IPv4Network(value)
                    # else:
                    #     self.logger.debug(
                    #        "Skip undesired Cfg interface:{}".format(value))
            _index += 1

        if found_interface:
            if my_ip is None:
                self.logger.error(
                    "Found Interface:{}, failed to find IP address".format(
                        interface_name))
            # else:
            #     self.logger.debug(
            #        "IP for interface:{} is {}".format(interface_name, my_ip))

            if my_net is None:
                self.logger.error(
                    "Found Interface:{}, failed to find NETWORK Prefix".format(
                        interface_name))
            # else:
            #     self.logger.debug(
            #           "NET for interface:{} is {}".format(interface_name,
            #                                               my_net))

        else:
            self.logger.error(
                "Failed to find Interface:{}".format(interface_name))
        return my_ip, my_net

    @staticmethod
    def make_computer_ip(router_ip, last_octet=DEF_COMPUTER_IP_LAST_OCTET):
        """
        Given the router's IP, edit to make this computer's IP
            (assuming we are consistent)

        :param router_ip:
        :type router_ip: str or ipaddress.IPv4Address
        :param int last_octet:
        :return str:
        """
        if isinstance(router_ip, str):
            # ensure is IPv4 value
            router_ip = ipaddress.IPv4Address(router_ip)

        value = router_ip.exploded.split('.')
        assert len(value) == 4
        return "{0}.{1}.{2}.{3}".format(value[0], value[1],
                                        value[2], last_octet)

    @staticmethod
    def trim_ip_to_4(value):
        """
        handle things like 192.168.30.0/24 or 192.168.30.0:8080, which
        we might obtain from various shelled reports.

        :param str value: the string to trim
        """
        value = value.strip()
        offset = value.find('/')
        if offset >= 0:
            value = value[:offset]

        offset = value.find(':')
        if offset >= 0:
            value = value[:offset]

        value = ipaddress.IPv4Address(value)
        # will throw ipaddress.AddressValueError if bad

        return value.exploded

    def list_interfaces(self):
        """
        Dump of interfaces, cleaned to be only as wanted. Might be like:

        [   "",
            "Configuration for interface \"ENet MB\"",
            "    IP Address:            192.168.0.10",
            "    Subnet Prefix:         192.168.0.0/24 (mask 255.255.255.0)",
            "    Default Gateway:       192.168.0.1",
            "",
            "Configuration for interface \"ENet USB-1\"",
            "    IP Address:            192.168.30.6",
            "    Subnet Prefix:         192.168.30.0/24 (mask 255.255.255.0)",
            ""
        ]
        """
        if sys.platform != "win32":
            raise NotImplementedError

        command = ["netsh", "interface", "ip", "show", "config"]

        result = subprocess.check_output(command, universal_newlines=True)
        # use of universal_newlines=True means return is STR not BYTES
        """ :type result: str"""
        result = result.split("\n")
        # for line in result:
        #     self.logger.debug("Line:{}".format(line))

        report = []

        # use in_configuration to hide interfaces we don't want
        #       - like hide 127.0.0.1 / localhost
        in_configuration = False

        # use last_was_blank to suppress consecutive blanks
        last_was_blank = False

        # suppress 'rogue' subnet or gateway, without IP
        #       (idle DHCP interface might do this)
        seen_ip_address = False

        # delay output of 'Configuration ' announcement until we have
        # at least 1 other value like IP, etc.
        hold_config_line = None
        for line in result:
            # we'll ONLY show certain lines, discard all else
            test = line.strip()

            if len(test) < 1:
                # then blank line - keep for visual prettiness
                in_configuration = False
                if last_was_blank:
                    continue
                last_was_blank = True
                report.append(line)

            elif test.startswith("Configuration"):
                # Configuration for interface "ENet MB" continue
                if LIST_INTERFACE_NO_LOOPBACK and test.find("Loopback") > 0:
                    # skip: interface "Loopback Pseudo-Interface 1"
                    continue

                if LIST_INTERFACE_NO_VM:
                    if test.find("VMware") > 0:
                        # skip: interface "VMware Network Adapter VM1"
                        continue
                    if test.find("VirtualBox") > 0:
                        # skip: interface "VirtualBox Host-Only Network"
                        continue

                in_configuration = True
                seen_ip_address = False
                hold_config_line = line

            elif test.startswith("IP Address"):
                # Configuration for interface "ENet MB" continue
                if not in_configuration:
                    continue

                if hold_config_line:
                    # add the delayed config line.
                    report.append(hold_config_line)
                    hold_config_line = None

                seen_ip_address = True
                last_was_blank = False
                report.append(line)

            elif test.startswith("Subnet Prefix"):
                # Configuration for interface "ENet MB" continue
                if in_configuration and seen_ip_address:
                    # only add if we've seen an "Ip Address" line
                    last_was_blank = False
                    report.append(line)

            elif test.startswith("Default Gateway"):
                # Configuration for interface "ENet MB" continue
                if in_configuration and seen_ip_address:
                    # only add if we've seen an "Ip Address" line
                    last_was_blank = False
                    report.append(line)

        # else:
        #     # self.logger.debug("skip:{}".format(line))
        #     continue

        return report

    @staticmethod
    def get_whoami():
        """
        Fetch 'whoami' to enable running priviledged subprocess

        [   "",
            "Configuration for interface \"ENet MB\"",
            "    IP Address:           192.168.0.10",
            "    Subnet Prefix:        192.168.0.0/24 (mask 255.255.255.0)",
            "    Default Gateway:      192.168.0.1",
            "",
            "Configuration for interface \"ENet USB-1\"",
            "    IP Address:           192.168.30.6",
            "    Subnet Prefix:        192.168.30.0/24 (mask 255.255.255.0)",
            ""
        ]
        """
        if sys.platform == "win32":

            command = ["whoami"]

            result = subprocess.check_output(command, universal_newlines=True)
            # use of universal_newlines=True means return is STR not BYTES
            """ :type result: str"""
            # we'll have a EOL at the end, so strip off
            return result.strip()

        else:
            raise NotImplementedError

    def set_computer_ip(self, interface, syslog_ip):
        """
        To set a fixed IP:
            netsh interface ip set address name="Local Area Connection"
                static 192.168.0.1 255.255.255.0 192.168.0.254

        To set DHCP:
            netsh interface ip set address name="Local Area Connection"
                source=dhcp

        :param str interface: The interface name, such "Local Area Connection"
        :param str syslog_ip: The IP for syslog, such "192.168.0.6"
        """
        whoami = self.get_whoami()
        self.logger.debug("WhoAmI={}".format(whoami))

        if sys.platform == "win32":
            # then use Windows method - note, it will pause & ask YOU for
            #   your whoami password

            command = ['runas', '/noprofile', '/user:' + whoami,
                       'netsh interface ip set address \"' + interface +
                       '\" static ' + syslog_ip + ' 255.255.255.0']

            self.logger.debug("{}".format(command))
            self.logger.warning("!!")
            self.logger.warning(
                "Enter the password for user:{}".format(whoami))

            result = subprocess.check_output(command, universal_newlines=True)
            # use of universal_newlines=True means return is STR not BYTES
            """ :type result: str"""
            result = result.split("\n")
            self.logger.debug("netsh:{}".format(result))
            return result

        else:
            raise NotImplementedError

    def dump_help(self, args):
        """

        :param list args: the command name
        :return:
        """
        print("Syntax:")
        print('   {} -m <action> <router_alias>'.format(args[0]))
        print()
        print("   Default action = {}".format(self.ACTION_DEFAULT))
        for command in self.ACTION_NAMES:
            print()
            print("- action={0}".format(command))
            print("    {0}".format(self.ACTION_HELP[command]))

        return

if __name__ == "__main__":

    target = TheTarget()

    if len(sys.argv) < 2:
        target.dump_help(sys.argv)
        sys.exit(-1)

    # if cmdline is only "make", then run as "make build" but we'll
    # expect ["name"] in global sets

    # save this, just in case we care later
    utility_name = sys.argv[0]

    index = 1
    while index < len(sys.argv):
        # loop through an process the parameters

        if sys.argv[index] in ('-m', '-M'):
            # then what follows is the mode/action
            action = sys.argv[index + 1].lower()
            if action in target.ACTION_NAMES:
                # then it is indeed an action
                target.action = action
            else:
                target.logger.error(
                    "Aborting, Unknown action:{}".format(action))
                print("")
                target.dump_help(sys.argv)
                sys.exit(-1)
            index += 1  # need an extra ++ as -m includes 2 params

        elif sys.argv[index] in ('-v', '-V', '+v', '+V'):
            # switch the logger to DEBUG from INFO
            target.verbose = True

        else:
            # assume this is the app path
            target.target_alias = sys.argv[index]

        index += 1  # get to next setting

    if target.verbose:
        logging.basicConfig(level=logging.DEBUG)
        target.logger.setLevel(level=logging.DEBUG)

    else:
        logging.basicConfig(level=logging.INFO)
        target.logger.setLevel(level=logging.INFO)
        # quiet INFO messages from requests module,
        #       "requests.packages.urllib3.connection pool"
        logging.getLogger('requests').setLevel(logging.WARNING)

    _result = target.main()
    if _result != 0:
        logging.error("return is {}".format(_result))

    sys.exit(_result)
