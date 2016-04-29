# Test the cp_lib.app_base module

import logging
import os
import unittest


class TestAppBase(unittest.TestCase):

    def test_import_full_file_name(self):
        """
        :return:
        """
        from cp_lib.app_base import CradlepointAppBase

        print()  # move past the '.'

        if True:
            return

        name = "network.tcp_echo"
        obj = CradlepointAppBase(name)

        # here, INIT is used, it exists and is larger than trivial (5 bytes)
        # we want the tcp-echo.py to exist, but won't use
        expect = os.path.join("network", "tcp_echo", "tcp_echo.py")
        self.assertTrue(os.path.exists(expect))

        expect = os.path.join("network", "tcp_echo", "__init__.py")
        self.assertTrue(os.path.exists(expect))
        logging.info("TEST names when {} can be run_name".format(expect))

        self.assertEqual(obj.run_name, expect)
        expect = os.path.join("network", "tcp_echo") + os.sep
        self.assertEqual(obj.app_path, expect)
        self.assertEqual(obj.app_name, "tcp_echo")
        self.assertEqual(obj.mod_name, "network.tcp_echo")

        name = "RouterSDKDemo"
        obj = CradlepointAppBase(name)

        # here, the app name is used (the INIT is empty / zero bytes)
        expect = os.path.join("RouterSDKDemo", "__init__.py")
        self.assertTrue(os.path.exists(expect))
        logging.info(
            "TEST names when {} is too small to be run_name".format(expect))

        expect = os.path.join(name, name) + ".py"
        self.assertTrue(os.path.exists(expect))
        logging.info("TEST names when {} can be run_name".format(expect))

        self.assertEqual(obj.run_name, expect)
        expect = name + os.sep
        self.assertEqual(obj.app_path, expect)
        self.assertEqual(obj.app_name, "RouterSDKDemo")
        self.assertEqual(obj.mod_name, "RouterSDKDemo")

        return

    def test_normalize_app_name(self):
        """
        :return:
        """
        from cp_lib.app_name_parse import normalize_app_name, \
            get_module_name, get_app_name, get_app_path
        # TODO - test get_run_name()!
        import os

        print()  # move past the '.'

        logging.info("TEST normalize_app_name()")
        tests = [
            ("network\\tcp_echo\\file.py", ["network", "tcp_echo", "file.py"]),
            ("network\\tcp_echo\\file", ["network", "tcp_echo", "file", ""]),
            ("network\\tcp_echo\\", ["network", "tcp_echo", ""]),
            ("network\\tcp_echo", ["network", "tcp_echo", ""]),

            ("network/tcp_echo/file.py", ["network", "tcp_echo", "file.py"]),
            ("network/tcp_echo/file", ["network", "tcp_echo", "file", ""]),
            ("network/tcp_echo/", ["network", "tcp_echo", ""]),
            ("network/tcp_echo", ["network", "tcp_echo", ""]),

            ("network.tcp_echo.file.py", ["network", "tcp_echo", "file.py"]),
            ("network.tcp_echo.file", ["network", "tcp_echo", "file", ""]),
            ("network.tcp_echo.", ["network", "tcp_echo", ""]),
            ("network.tcp_echo", ["network", "tcp_echo", ""]),

            ("network", ["network", ""]),
            ("network.py", ["", "network.py"]),
        ]

        for test in tests:
            source = test[0]
            expect = test[1]

            result = normalize_app_name(source)
            # logging.debug(
            #   "normalize_app_name({0}) = {1}".format(source, result))

            self.assertEqual(result, expect)

        logging.info("TEST get_module_name()")
        tests = [
            ("network\\tcp_echo\\file.py", "network.tcp_echo"),
            ("network\\tcp_echo\\file", "network.tcp_echo.file"),
            ("network\\tcp_echo", "network.tcp_echo"),

            ("network/tcp_echo/file.py", "network.tcp_echo"),
            ("network/tcp_echo/file", "network.tcp_echo.file"),
            ("network/tcp_echo", "network.tcp_echo"),

            ("network.tcp_echo.file.py", "network.tcp_echo"),
            ("network.tcp_echo.file", "network.tcp_echo.file"),
            ("network.tcp_echo", "network.tcp_echo"),

            ("network", "network"),
            ("network.py", ""),
        ]

        for test in tests:
            source = test[0]
            expect = test[1]

            result = get_module_name(source)
            # logging.debug(
            #   "get_module_name({0}) = {1}".format(source, result))

            self.assertEqual(result, expect)

        logging.info("TEST get_app_name()")
        tests = [
            ("network\\tcp_echo\\file.py", "tcp_echo"),
            ("network\\tcp_echo\\file", "file"),
            ("network\\tcp_echo", "tcp_echo"),

            ("network/tcp_echo/file.py", "tcp_echo"),
            ("network/tcp_echo/file", "file"),
            ("network/tcp_echo", "tcp_echo"),

            ("network.tcp_echo.file.py", "tcp_echo"),
            ("network.tcp_echo.file", "file"),
            ("network.tcp_echo", "tcp_echo"),

            ("network", "network"),
            ("network.py", ""),
        ]

        for test in tests:
            source = test[0]
            expect = test[1]

            result = get_app_name(source)
            # logging.debug("get_app_name({0}) = {1}".format(source, result))

            self.assertEqual(result, expect)

        logging.info(
            "TEST get_app_path(), with native os.sep, = \'{}\'".format(os.sep))
        tests = [
            ("network\\tcp_echo\\file.py",
             os.path.join("network", "tcp_echo") + os.sep),
            ("network\\tcp_echo\\file",
             os.path.join("network", "tcp_echo", "file") + os.sep),
            ("network\\tcp_echo",
             os.path.join("network", "tcp_echo") + os.sep),

            ("network/tcp_echo/file.py",
             os.path.join("network", "tcp_echo") + os.sep),
            ("network/tcp_echo/file",
             os.path.join("network", "tcp_echo", "file") + os.sep),
            ("network/tcp_echo",
             os.path.join("network", "tcp_echo") + os.sep),

            ("network.tcp_echo.file.py",
             os.path.join("network", "tcp_echo") + os.sep),
            ("network.tcp_echo.file",
             os.path.join("network", "tcp_echo", "file") + os.sep),
            ("network.tcp_echo",
             os.path.join("network", "tcp_echo") + os.sep),

            ("network", "network" + os.sep),
            ("network.py", ""),
        ]

        for test in tests:
            source = test[0]
            expect = test[1]

            result = get_app_path(source)
            # logging.debug("get_module_name({0})={1}".format(source, result))

            self.assertEqual(result, expect)

        logging.info("TEST get_app_path(), forced LINUX separator of \'/\'")
        tests = [
            ("network\\tcp_echo\\file.py", "network/tcp_echo/"),
            ("network\\tcp_echo\\file", "network/tcp_echo/file/"),
            ("network\\tcp_echo", "network/tcp_echo/"),

            ("network/tcp_echo/file.py", "network/tcp_echo/"),
            ("network/tcp_echo/file", "network/tcp_echo/file/"),
            ("network/tcp_echo", "network/tcp_echo/"),

            ("network.tcp_echo.file.py", "network/tcp_echo/"),
            ("network.tcp_echo.file", "network/tcp_echo/file/"),
            ("network.tcp_echo", "network/tcp_echo/"),

            ("network", "network/"),
            ("network.py", ""),
        ]

        for test in tests:
            source = test[0]
            expect = test[1]

            result = get_app_path(source, separator='/')
            # logging.debug("get_module_name({0})={1}".format(source, result))

            self.assertEqual(result, expect)

        logging.info("TEST get_app_path(), forced WINDOWS separator of \'\\\'")
        tests = [
            ("network\\tcp_echo\\file.py", "network\\tcp_echo\\"),
            ("network\\tcp_echo\\file", "network\\tcp_echo\\file\\"),
            ("network\\tcp_echo", "network\\tcp_echo\\"),

            ("network/tcp_echo/file.py", "network\\tcp_echo\\"),
            ("network/tcp_echo/file", "network\\tcp_echo\\file\\"),
            ("network/tcp_echo", "network\\tcp_echo\\"),

            ("network.tcp_echo.file.py", "network\\tcp_echo\\"),
            ("network.tcp_echo.file", "network\\tcp_echo\\file\\"),
            ("network.tcp_echo", "network\\tcp_echo\\"),

            ("network", "network\\"),
            ("network.py", ""),
        ]

        for test in tests:
            source = test[0]
            expect = test[1]

            result = get_app_path(source, separator='\\')
            # logging.debug("get_module_name({0})={1}".format(source, result))

            self.assertEqual(result, expect)

        logging.warning("TODO - we don't TEST get_run_name()")

        return

    def test_normalize_path_separator(self):
        """
        :return:
        """
        from cp_lib.app_name_parse import normalize_path_separator
        import os

        print()  # move past the '.'

        logging.info("TEST normalize_path_separator() to Windows Style")
        tests = [
            ("network\\tcp_echo\\file.py", "network\\tcp_echo\\file.py"),
            ("network\\tcp_echo\\file", "network\\tcp_echo\\file"),
            ("network\\tcp_echo", "network\\tcp_echo"),

            ("network\\tcp_echo/file.py", "network\\tcp_echo\\file.py"),

            ("network/tcp_echo/file.py", "network\\tcp_echo\\file.py"),
            ("network/tcp_echo/file", "network\\tcp_echo\\file"),
            ("network/tcp_echo", "network\\tcp_echo"),

            ("network.tcp_echo.file.py", "network.tcp_echo.file.py"),

            ("network", "network"),
            ("network.py", "network.py"),
        ]

        for test in tests:
            source = test[0]
            expect = test[1]

            result = normalize_path_separator(source, separator="\\")
            # logging.debug(
            #   "normalize_path_separator({0}) = {1}".format(source, result))
            self.assertEqual(result, expect)

        logging.info("TEST normalize_path_separator() to Linux Style")
        tests = [
            ("network\\tcp_echo\\file.py", "network/tcp_echo/file.py"),
            ("network\\tcp_echo\\file", "network/tcp_echo/file"),
            ("network\\tcp_echo", "network/tcp_echo"),

            ("network\\tcp_echo/file", "network/tcp_echo/file"),

            ("network/tcp_echo/file.py", "network/tcp_echo/file.py"),
            ("network/tcp_echo/file", "network/tcp_echo/file"),
            ("network/tcp_echo", "network/tcp_echo"),

            ("network.tcp_echo.file.py", "network.tcp_echo.file.py"),

            ("network", "network"),
            ("network.py", "network.py"),
        ]

        for test in tests:
            source = test[0]
            expect = test[1]

            result = normalize_path_separator(source, separator="/")
            # logging.debug(
            # "normalize_path_separator({0}) = {1}".format(source, result))
            self.assertEqual(result, expect)

        logging.info(
            "TEST normalize_path_separator(), native os.sep = \'{}\'".format(
                os.sep))
        tests = [
            ("network\\tcp_echo\\file.py",
             os.path.join("network", "tcp_echo", "file.py")),
            ("network\\tcp_echo\\file",
             os.path.join("network", "tcp_echo", "file")),
            ("network\\tcp_echo",
             os.path.join("network", "tcp_echo")),

            ("network\\tcp_echo/file.py",
             os.path.join("network", "tcp_echo", "file.py")),

            ("network/tcp_echo/file.py",
             os.path.join("network", "tcp_echo", "file.py")),
            ("network/tcp_echo/file",
             os.path.join("network", "tcp_echo", "file")),
            ("network/tcp_echo",
             os.path.join("network", "tcp_echo")),

            ("network.tcp_echo.file.py", "network.tcp_echo.file.py"),

            ("network", "network"),
            ("network.py", "network.py"),
        ]

        for test in tests:
            source = test[0]
            expect = test[1]

            result = normalize_path_separator(source)
            # logging.debug(
            #   "normalize_path_separator({0}) = {1}".format(source, result))
            self.assertEqual(result, expect)

        return

    def test_get_settings(self):
        """
        :return:
        """
        from cp_lib.app_base import CradlepointAppBase

        print()  # move past the '.'

        # we'll just use this as example, assuming .config/setting.ini
        # and
        name = "network.tcp_echo"
        obj = CradlepointAppBase(name, call_router=False)

        # just slam in a known 'data tree'
        obj.settings = {
            'application': {
                'firmware': '6.1',
                'name': 'make',
                'restart': 'true',
                'reboot': True,
                'sleeping': 'On',
                'explosion': 'enabled',
            },
            'router_api': {
                'user_name': 'admin',
                'interface': 'ENet USB-1',
                'password': '441b1702',
                'local_ip': '192.168.1.1'
            },
            'logging': {
                'syslog_ip': '192.168.1.6',
                'pc_syslog': 'false',
                'level': 'debug'
            },
            'startup': {
                'boot_delay_for_wan': 'True',
                'exit_delay': '30 sec',
                'boot_delay_max': '5 min',
                'bomb_delay': 17,
                'rain_delay': '19',
                'boot_delay_for_time': 'True'
            },
            'glob_dir': 'config',
            'base_name': 'settings',
            'app_dir': 'network\\tcp_echo\\',
        }

        logging.info("TEST simple get_setting(), without force_type")
        self.assertEqual("make",
                         obj.get_setting("application.name"))
        self.assertEqual("6.1",
                         obj.get_setting("application.firmware"))
        self.assertEqual(True,
                         obj.get_setting("application.reboot"))

        logging.info("TEST get_setting(), with force_type=bool")
        self.assertEqual("true",
                         obj.get_setting("application.restart"))
        self.assertEqual(True,
                         obj.get_setting("application.restart",
                                         force_type=bool))
        self.assertEqual(True,
                         obj.get_setting("application.reboot"))
        self.assertEqual(True,
                         obj.get_setting("application.reboot",
                                         force_type=bool))
        self.assertEqual(1,
                         obj.get_setting("application.reboot",
                                         force_type=int))
        self.assertEqual("On",
                         obj.get_setting("application.sleeping"))
        self.assertEqual(True,
                         obj.get_setting("application.sleeping",
                                         force_type=bool))
        self.assertEqual("enabled",
                         obj.get_setting("application.explosion"))
        self.assertEqual(True,
                         obj.get_setting("application.explosion",
                                         force_type=bool))
        # doesn't exist, but force to String means "None"
        self.assertEqual(None,
                         obj.get_setting("application.not_exists",
                                         force_type=bool))

        with self.assertRaises(ValueError):
            # string 'true' can't be forced to int, bool True can
            obj.get_setting("application.name", force_type=bool)

        logging.info("TEST get_setting(), with force_type=str")
        # [restart] is already string, but [reboot] is bool(True)
        self.assertEqual("true",
                         obj.get_setting("application.restart",
                                         force_type=str))
        self.assertEqual("True",
                         obj.get_setting("application.reboot",
                                         force_type=str))
        # doesn't exist, & force to String does not means "None"
        self.assertEqual(None,
                         obj.get_setting("application.not_exists"))
        self.assertEqual(None,
                         obj.get_setting("application.not_exists",
                                         force_type=str))

        logging.info("TEST get_setting_time_secs()")
        self.assertEqual(
            "30 sec", obj.get_setting("startup.exit_delay"))
        self.assertEqual(
            30.0, obj.get_setting_time_secs("startup.exit_delay"))

        self.assertEqual(
            "5 min",  obj.get_setting("startup.boot_delay_max"))
        self.assertEqual(
            300.0,  obj.get_setting_time_secs("startup.boot_delay_max"))

        self.assertEqual(
            17, obj.get_setting("startup.bomb_delay"))
        self.assertEqual(
            17.0, obj.get_setting_time_secs("startup.bomb_delay"))

        self.assertEqual(
            "19", obj.get_setting("startup.rain_delay"))
        self.assertEqual(
            19.0, obj.get_setting_time_secs("startup.rain_delay"))

        with self.assertRaises(ValueError):
            # string 'true' can't be forced to int, bool True can
            obj.get_setting("application.restart", force_type=int)

        return


if __name__ == '__main__':
    # logging.basicConfig(level=logging.INFO)
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
