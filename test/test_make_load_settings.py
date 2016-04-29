# Test the tools.make_settings module - for some weird reason, I can't run this from ./tests

import logging
import os.path
import shutil
import unittest

# for internal test of tests - allow temp files to be left on disk
REMOVE_TEMP_FILE = True


class TestLoadSettings(unittest.TestCase):

    def test_line_find_section(self):
        from tools.make_load_settings import _line_find_section

        print("")  # skip paste '.' on line

        logging.info("TEST _line_find_section")
        tests = [
            (None, False),
            ("", False),
            ("[]", False),
            ("[application]", True),
            ("  [Application]", True),
            (" [aPPlication]  # comments", True),
            ("[APPLICATION]", True),
            ("[aplication]", False),
            ("  name = tcp_echo", False),
            ("description = Run a basic TCP socket echo server and client", False),
            ("path = network/tcp_echo", False),
            ("uuid = 7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c", False),
            (" [build]", False),
            (" [RouterApiStuff]", False),
        ]

        for test in tests:
            source = test[0]
            expect = test[1]
            self.assertEqual(_line_find_section(source, name='application'), expect)
        return

    def test_load_settings(self):

        from tools.make_load_settings import DEF_GLOBAL_DIRECTORY, DEF_INI_EXT, load_settings

        def _make_global_ini_file(file_name: str):
            """Given file name (path), make file containing the name"""
            data = [
                "[logging]",
                "level = debug",
                "syslog_ip = 192.168.1.6",
                "",
                "[router_api]",
                "local_ip = 192.168.1.1",
                "user_name = admin",
                "password = 441b1702"
            ]

            _han = open(file_name, 'w')
            for line in data:
                _han.write(line + "\n")
            _han.close()
            # logging.debug("Write Global INI")
            return

        def _make_app_ini_file(file_name: str):
            """Given file name (path), make file containing the name"""
            data = [
                "[logging]",
                "level = info",
                # this one NOT changed! "syslog_ip = 192.168.1.6",
                "",
                "[application]",
                "name = tcp_echo",
                "description = Run a basic TCP socket echo server and client",
                "path = network/tcp_echo",
                "uuid = 7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c",
            ]

            _han = open(file_name, 'w')
            for line in data:
                _han.write(line + "\n")
            _han.close()
            # logging.debug("Write APP INI")
            return

        print("")  # skip paste '.' on line

        test_file_name = "test_load"

        logging.info("TEST: load proj over global, merge correctly")
        global_dir = DEF_GLOBAL_DIRECTORY
        global_path = os.path.join(global_dir, test_file_name + DEF_INI_EXT)
        # logging.debug("GLB:[{}]".format(global_path))
        _make_global_ini_file(global_path)

        app_dir = "network\\tcp_echo"
        app_path = os.path.join(app_dir, test_file_name + DEF_INI_EXT)
        # logging.debug("APP:[{}]".format(app_path))
        _make_app_ini_file(app_path)

        result = load_settings(app_dir, global_dir, test_file_name)
        # logging.debug("Load Result:[{}]".format(json.dumps(result, sort_keys=True, indent=2)))

        # confirm worked! APP changed logging level, but not syslog_ip
        self.assertNotEqual("debug", result["logging"]["level"])
        self.assertEqual("info", result["logging"]["level"])
        self.assertEqual("192.168.1.6", result["logging"]["syslog_ip"])

        # clean up the temp file
        if REMOVE_TEMP_FILE:
            self._remove_name_no_error(global_path)
            self._remove_name_no_error(app_path)

        return

    def test_fix_uuid(self):
        """
        add or replace the "uuid" data in the app's INI file

        TODO - also handle JSON, but for now we ignore this.

        :return:
        """
        import uuid
        import tools.make_load_settings as load_settings
        import configparser

        print("")  # skip paste '.' on line

        sets = {"app_dir": "test", "base_name": "test_uuid"}

        ini_name = os.path.join(sets["app_dir"], sets["base_name"] + load_settings.DEF_INI_EXT)

        data = ["[logging]",
                "level = debug",
                "",
                "[application]",
                "name = tcp_echo",
                "description = Run a basic TCP socket echo server and client",
                "path = network/tcp_echo",
                "uuid = 7042c8fd-fe7a-4846-aed1-original",
                "",
                "[router_api]",
                "local_ip = 192.168.1.1",
                "user_name = admin",
                "password = 441b1702"
                ]

        _han = open(ini_name, 'w')
        for line in data:
            _han.write(line + "\n")
        _han.close()

        logging.info("TEST - over-write old UUID")
        expect = str(uuid.uuid4())
        load_settings.fix_up_uuid(ini_name, expect, backup=REMOVE_TEMP_FILE)

        # confirm it worked!
        config = configparser.ConfigParser()
        file_han = open(ini_name, "r")
        config.read_file(file_han)
        file_han.close()
        # logging.debug("  uuid:{}".format(config["application"]["uuid"]))
        self.assertEqual(expect, config["application"]["uuid"])

        data = ["[logging]",
                "level=debug",
                "",
                "[application]",
                "name=tcp_echo",
                "description=Run a basic TCP socket echo server and client",
                "path=network/tcp_echo",
                "",
                "[router_api]",
                "local_ip=192.168.1.1",
                "user_name=admin",
                "password=441b1702"
                ]

        _han = open(ini_name, 'w')
        for line in data:
            _han.write(line + "\n")
        _han.close()

        logging.info("TEST - add missing UUID")
        expect = str(uuid.uuid4())
        load_settings.fix_up_uuid(ini_name, expect, backup=REMOVE_TEMP_FILE)

        # confirm it worked!
        config = configparser.ConfigParser()
        file_han = open(ini_name, "r")
        config.read_file(file_han)
        file_han.close()
        # logging.debug("  uuid:{}".format(config["application"]["uuid"]))
        self.assertEqual(expect, config["application"]["uuid"])

        if REMOVE_TEMP_FILE:
            self._remove_name_no_error(ini_name)
            self._remove_name_no_error(ini_name + load_settings.DEF_SAVE_EXT)

        return

    def test_incr_version(self):
        """
        add or replace the "uuid" data in the app's INI file

        TODO - also handle JSON, but for now we ignore this.

        :return:
        """
        import tools.make_load_settings as load_settings
        import configparser

        print("")  # skip paste '.' on line

        sets = {"app_dir": "test", "base_name": "test_version"}

        ini_name = os.path.join(sets["app_dir"], sets["base_name"] + load_settings.DEF_INI_EXT)

        data = ["[logging]",
                "level = debug",
                "",
                "[application]",
                "name = tcp_echo",
                "description = Run a basic TCP socket echo server and client",
                "path = network/tcp_echo",
                "version = 3.45",
                "",
                "[router_api]",
                "local_ip = 192.168.1.1",
                "user_name = admin",
                "password = 441b1702"
                ]

        _han = open(ini_name, 'w')
        for line in data:
            _han.write(line + "\n")
        _han.close()

        logging.info("TEST - increment existing version")
        expect = "3.46"
        load_settings.increment_app_version(ini_name, incr_version=True)

        # confirm it worked!
        config = configparser.ConfigParser()
        file_han = open(ini_name, "r")
        config.read_file(file_han)
        file_han.close()
        # logging.debug("  version:{}".format(config["application"]["version"]))
        self.assertEqual(expect, config["application"]["version"])

        logging.info("TEST - don't increment existing version")
        expect = "3.46"
        load_settings.increment_app_version(ini_name, incr_version=False)

        # confirm it worked!
        config = configparser.ConfigParser()
        file_han = open(ini_name, "r")
        config.read_file(file_han)
        file_han.close()
        # logging.debug("  version:{}".format(config["application"]["version"]))
        self.assertEqual(expect, config["application"]["version"])

        if REMOVE_TEMP_FILE:
            self._remove_name_no_error(ini_name)
            self._remove_name_no_error(ini_name + load_settings.DEF_SAVE_EXT)

        data = ["[logging]",
                "level = debug",
                "",
                "[application]",
                "name = tcp_echo",
                "description = Run a basic TCP socket echo server and client",
                "path = network/tcp_echo",
                "",
                "[router_api]",
                "local_ip = 192.168.1.1",
                "user_name = admin",
                "password = 441b1702"
                ]

        _han = open(ini_name, 'w')
        for line in data:
            _han.write(line + "\n")
        _han.close()

        logging.info("TEST - missing version")
        expect = "1.0"
        load_settings.increment_app_version(ini_name)

        # confirm it worked!
        config = configparser.ConfigParser()
        file_han = open(ini_name, "r")
        config.read_file(file_han)
        file_han.close()
        # logging.debug("  version:{}".format(config["application"]["version"]))
        self.assertEqual(expect, config["application"]["version"])

        if REMOVE_TEMP_FILE:
            self._remove_name_no_error(ini_name)
            self._remove_name_no_error(ini_name + load_settings.DEF_SAVE_EXT)

        return

    @staticmethod
    def _remove_name_no_error(file_name):
        """
        Just remove if exists
        :param str file_name: the file
        :return:
        """
        if os.path.isdir(file_name):
            shutil.rmtree(file_name)

        else:
            try:  # second, try if common file
                os.remove(file_name)
            except FileNotFoundError:
                pass
        return


if __name__ == '__main__':
    # logging.basicConfig(level=logging.INFO)
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
