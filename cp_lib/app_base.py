import logging
import sys
from threading import Lock

from cp_lib.data.data_tree import get_item_value, data_tree_clean, \
    get_item_time_duration_to_seconds, put_item


class CradlepointRouterOffline(ConnectionError):
    """
    A general failure to use when the AppBase fails to find the router
    """
    pass


class CradlepointAppBase(object):
    """
    This object holds the data and status during the hand-off from the
    Cradlepoint Router launching your SDK code, and your code running.

    You can either sub-class your code as an instance of CradlepointAppBase,
    or use it as a secondary object to accept the data & status, copy to
    your own code, then launch your code.

    """

    def __init__(self, full_name=None, log_level=None, call_router=True,
                 log_name=None):
        """

        :param str full_name: mod name, such as "network.tcp_echo"
        :param str log_level: allow an over-ride of logging level,
                              if not None, ignore settings
        :param bool call_router: T to fetch router info, else F means
                              do not contact router (may be offline)
        :param str log_name: optional NAME for the logger, to over-ride
                              any settings data
        :return:
        """
        # Import here to avoid circular import issues in sub-class and users
        from cp_lib.cs_client import init_cs_client_on_my_platform
        from cp_lib.load_product_info import load_product_info
        from cp_lib.load_firmware_info import load_firmware_info
        from cp_lib.load_settings_json import load_settings_json
        from cp_lib.cp_logging import get_recommended_logger

        # since we have to unpack these, might as well save results
        self.run_name = None        # like "network/tcp_echo/__init__.py"
        self.app_path = None        # like "network/tcp_echo/", to find files
        self.app_name = None        # like "tcp_echo"
        self.mod_name = None        # like "network.tcp_echo", for importlib

        if full_name is not None:
            # allow no name - for tools like MAKE or TARGET; no app directory
            assert isinstance(full_name, str)
            self.import_full_file_name(full_name)

        # create a data LOCK to allow multi-thread access to settings & data
        self.data_lock = Lock()

        # follow SDK design to load settings, first from ./config, then
        # over-lay from self.app_path.
        self.settings = load_settings_json(self.app_path)
        # convert 'None', 'true', and such strings into true Python values
        data_tree_clean(self.settings)

        # like settings, but into to null & are assumed 100% dynamic (TBD)
        self.data = dict()

        # use the settings to create the more complex logger, including
        # Syslog if appropriate
        try:
            self.logger = get_recommended_logger(
                self.settings, level=log_level, name=log_name)

        except:
            logging.exception('get_recommended_logger() failed')
            raise

        if sys.platform == "linux":
            self.logger.info("Running under full Linux")

        elif sys.platform == "win32":
            self.logger.info("Running under Windows")

        elif sys.platform == "linux2":
            self.logger.info("Running on Cradlepoint router")

        else:
            self.logger.info("Running on platform {}".format(sys.platform))

        # handle Router API client, which is different between PC and router
        try:
            self.cs_client = init_cs_client_on_my_platform(self.logger,
                                                           self.settings)
        except:
            self.logger.exception("CSClient init failed")
            raise

        # show NAME, Description, Version, UUID
        self.show_router_app_info()

        if call_router:
            # load the PRODUCT INFO into settings
            load_product_info(self.settings, self.cs_client)
            try:
                self.logger.info("Cradlepoint router is model:{}".format(
                    self.settings["product_info"]["product_name"]))
            except KeyError:
                pass

            # load the FW INFO into settings
            load_firmware_info(self.settings, self.cs_client)
            try:
                self.logger.info("Cradlepoint router FW is:{}".format(
                    self.settings["fw_info"]["version"]))
            except KeyError:
                pass

        return

    def get_product_name(self, full=False):
        """
        Get the product model as string

        :param bool full: T means return everything; F means 'cut' to
                          smaller subset, ignoring options
        :exception: KeyError if router information is not in self.settings
        :return:
        """
        from cp_lib.load_product_info import split_product_name

        value = self.settings["product_info"]["product_name"]
        """ :type value: str """
        if not full:
            # then reduce/clean up
            # returns IBR1100LPE would return as ("IBR1100", "LPE", True)
            value, options, wifi = split_product_name(value)
            self.settings["product_info"]["product_options"] = options
            self.settings["product_info"]["product_has_wifi"] = wifi
        return value

    def get_setting(self, path, throw_exception=False, force_type=None):
        """
        Given path, like "route_api.local_ip", return raw (likely str)
        value

        If throw_exception=False (the default), then None is returned if the
        setting in 'path' is NOT FOUND, else throw a DataTreeItemNotFound
        exception. This allows distinguishing between an existing setting
        with value None, and one not found.

        Normally, the object returned is 'native' per the settings.json,
        which derived its values from the text settings.INI files.
        This means values are LIKELY string values. You can use force_type to
        do a smart-guess. For example, force_type=bool will cause the values
        (True, 1, "1", "true", "TRUE", "on", "enabled") to all return a
        simple bool() value True.

        :param str path:
        :param bool throw_exception: return None, else DataTreeItemNotFound
        :param type force_type: if not None, try forcing a type
        :return:
        """

        self.data_lock.acquire()
        result = get_item_value(self.settings, path, throw_exception,
                                force_type)
        self.data_lock.release()
        return result

    def get_setting_time_secs(self, path, throw_exception=False):
        """
        Given path, like "route_api.local_ip"

        :param str path:
        :param bool throw_exception: return None, else DataTreeItemNotFound
        :rtype float:
        """
        self.data_lock.acquire()
        result = get_item_time_duration_to_seconds(
            self.settings, path, throw_exception)
        self.data_lock.release()
        return result

    def get_user_data(self, path, throw_exception=False, force_type=None):
        """
        Given path, like "route_api.local_ip", return raw (likely str)
        value

        If throw_exception=False (the default), then None is returned if the
        setting in 'path' is NOT FOUND, else throw a DataTreeItemNotFound
        exception. This allows distinguishing between an existing setting
        with value None, and one not found.

        :param str path:
        :param bool throw_exception: return None, else DataTreeItemNotFound
        :param type force_type: if not None, try forcing a type
        :return:
        """
        self.data_lock.acquire()
        result = get_item_value(self.data, path, throw_exception, force_type)
        self.data_lock.release()
        return result

    def put_user_data(self, path, value, throw_exception=False):
        """
        Given path, like "route_api.local_ip", return raw (likely str)
        value

        If throw_exception=False (the default), then None is returned if the
        setting in 'path' is NOT FOUND, else throw a DataTreeItemNotFound
        exception. This allows distinguishing between an existing setting
        with value None, and one not found.

        :param str path: a path, like 'tank01.level'
        :param value: the value to set
        :param bool throw_exception: return None, else DataTreeItemNotFound
        :return:
        """
        self.data_lock.acquire()
        result = put_item(self.data, path, value, throw_exception)
        self.data_lock.release()
        return result

    def show_router_app_info(self):
        """
        Dump out some of the [application] information

        :return:
        """
        # [application]
        # name=hello_world
        # description=Hello World sample, using 3 subtasks
        # version=1.9
        # uuid=c69cfe79-5f11-4cae-986a-9d568bf96629
        if 'application' in self.settings:
            # it should be, but ignore if not!

            if 'name' in self.settings['application']:
                self.logger.info(
                    "Starting Router App named \"{}\"".format(
                        self.settings['application']['name']))

            if 'description' in self.settings['application']:
                self.logger.info(
                    "App Desc:{}".format(
                        self.settings['application']['description']))

            if 'version' in self.settings['application']:
                self.logger.info(
                    "App Vers:{}".format(
                        self.settings['application']['version']))

            if 'uuid' in self.settings['application']:
                self.logger.info(
                    "App UUID:{}".format(
                        self.settings['application']['uuid']))

        return

    def import_full_file_name(self, dot_name):
        """
        take a name - such as network.tcp_echo, then see if we should run
        either of these:
        - first try ./network/tcp_echo/__init__.py, which must exist plus
          be at least 5 bytes in size
        - second try ./network/tcp_echo/tcp_echo.py, which merely has to exist
        - else throw FileNotFoundError exception

        :param str dot_name: like "network.tcp_echo" or "RouterSDKDemo"
        :return: None
        """
        from cp_lib.app_name_parse import normalize_app_name, \
            get_module_name, get_app_name, get_app_path, get_run_name

        # this handles any combination of:
        # - "network\\tcp_echo\\file.py" or "network\\tcp_echo"
        # - "network/tcp_echo/file.py" or "network/tcp_echo"
        # - "network.tcp_echo.file.py" or "network.tcp_echo"
        names = normalize_app_name(dot_name)

        # normalize will have returned like one of these
        # ["network", "tcp_echo", "__init__.py"]
        # ["network", "tcp_echo", ""]
        # ["tcp_echo", "__init__.py"]
        # ["tcp_echo", ""]
        # ["", "__init__.py"]

        if names[0] == "":
            raise ValueError(
                "SDK App {} must be subdirectory, not ROOT".format(dot_name))

        # will be like "network.tcp_echo"
        self.mod_name = get_module_name(names)

        # will be like "tcp_echo"
        self.app_name = get_app_name(names)

        # will be like "network/tcp_echo/"
        self.app_path = get_app_path(names)

        # see if the main app is like "network/tcp_echo/__init__.py"
        #                     or like "network/tcp_echo/tcp_echo.py"
        self.run_name = get_run_name(names, app_path=self.app_path,
                                     app_name=self.app_name)

        return

    def run(self):
        raise NotImplementedError("AppBase.run() not defined")
