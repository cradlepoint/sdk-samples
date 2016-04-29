# Test the cp_lib.load_settings module

import logging
import os.path
# noinspection PyUnresolvedReferences
import shutil
import unittest


class TestLoadSettings(unittest.TestCase):

    def test_load_settings(self):
        import copy
        import tools.make_load_settings as load_settings
        from cp_lib.load_settings_json import load_settings_json, DEF_GLOBAL_DIRECTORY, DEF_JSON_EXT
        from cp_lib.load_settings_ini import save_root_settings_json

        print("")

        glob_data = [
            "[logging]",
            "level = debug",
            "",
            "[router_api]",
            "local_ip = 192.168.1.1",
            "user_name = admin",
            "password = 441b1702"
        ]

        app_data = [
            "[application]",
            "name = tcp_echo",
            "description = Run a basic TCP socket echo server and client",
            "path = network/tcp_echo",
            "uuid = 7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c",
        ]

        all_data = copy.deepcopy(glob_data)
        all_data.extend(app_data)

        def _make_ini_file(file_name: str, data_list: list):
            """Given file name (path), make file containing the name"""
            _han = open(file_name, 'w')
            for line in data_list:
                _han.write(line + "\n")
            _han.close()
            # logging.debug("Write Global INI")
            return

        test_file_name = "test_load"

        global_dir = DEF_GLOBAL_DIRECTORY
        global_path = os.path.join(global_dir, test_file_name + load_settings.DEF_INI_EXT)
        # logging.debug("GLB:[{}]".format(global_path))

        app_dir = "network\\tcp_echo"
        app_path = os.path.join(app_dir, test_file_name + load_settings.DEF_INI_EXT)
        # logging.debug("APP:[{}]".format(app_path))

        save_path = test_file_name + DEF_JSON_EXT

        logging.info("TEST: only global exists, but is incomplete:[{}]".format(global_path))
        self._remove_name_no_error(global_path)
        self._remove_name_no_error(app_path)
        self._remove_name_no_error(save_path)

        _make_ini_file(global_path, glob_data)
        self.assertTrue(os.path.isfile(global_path))
        self.assertFalse(os.path.isfile(app_path))
        self.assertFalse(os.path.isfile(save_path))

        with self.assertRaises(KeyError):
            # we lack an apps section
            result = load_settings.load_settings(app_dir, test_file_name)

        self._remove_name_no_error(global_path)

        _make_ini_file(global_path, all_data)
        self.assertTrue(os.path.isfile(global_path))
        self.assertFalse(os.path.isfile(app_path))

        expect = {
            "application": {
                "uuid": "7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c",
                "path": "network/tcp_echo",
                "name": "tcp_echo",
                "_comment": "Settings for the application being built.",
                "description": "Run a basic TCP socket echo server and client"
            },
            "router_api": {
                "password": "441b1702",
                "_comment": "Settings to allow accessing router API in development mode.",
                "local_ip": "192.168.1.1",
                "user_name": "admin"
            },
            "logging": {
                "level": "debug",
                "_comment": "Settings for the application debug/syslog/logging function."
            }
        }
        logging.info("TEST: only global exists, is now complete:[{}]".format(global_path))
        result = load_settings.load_settings(app_dir, test_file_name)
        self.assertEqual(result, expect)

        logging.info("TEST: only APP exists:[{}]".format(global_path))
        self._remove_name_no_error(global_path)
        self._remove_name_no_error(app_path)

        _make_ini_file(app_path, app_data)
        self.assertFalse(os.path.isfile(global_path))
        self.assertTrue(os.path.isfile(app_path))

        # we lack an apps section
        result = load_settings.load_settings(app_dir, test_file_name)

        expect = {
            "application": {
                "path": "network/tcp_echo",
                "description": "Run a basic TCP socket echo server and client",
                "name": "tcp_echo",
                "uuid": "7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c",
                "_comment": "Settings for the application being built."
            }
        }
        self.assertEqual(result, expect)

        self._remove_name_no_error(global_path)
        self._remove_name_no_error(app_path)

        logging.info("TEST: both exists, is complete:[{}]".format(global_path))
        _make_ini_file(global_path, glob_data)
        _make_ini_file(app_path, app_data)

        self.assertTrue(os.path.isfile(global_path))
        self.assertTrue(os.path.isfile(app_path))

        expect = {
            "application": {
                "uuid": "7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c",
                "path": "network/tcp_echo",
                "name": "tcp_echo",
                "_comment": "Settings for the application being built.",
                "description": "Run a basic TCP socket echo server and client"
            },
            "router_api": {
                "password": "441b1702",
                "_comment": "Settings to allow accessing router API in development mode.",
                "local_ip": "192.168.1.1",
                "user_name": "admin"
            },
            "logging": {
                "level": "debug",
                "_comment": "Settings for the application debug/syslog/logging function."
            }
        }
        result = load_settings.load_settings(app_dir, test_file_name)
        self.assertEqual(result, expect)

        # result is now our 'full' settings
        logging.info("TEST: save to root, is complete:[{}]".format(global_path))
        self.assertFalse(os.path.isfile(save_path))
        save_root_settings_json(result, save_path)
        self.assertTrue(os.path.isfile(save_path))

        self._remove_name_no_error(global_path)
        self._remove_name_no_error(app_path)

        result = load_settings_json(file_name=test_file_name)
        # logging.debug("")
        # logging.debug("Load Result:[{}]".format(json.dumps(result)))
        # logging.debug("")
        # logging.debug("Load Expect:[{}]".format(json.dumps(expect)))
        # logging.debug("")

        self.assertEqual(result, expect)

        self._remove_name_no_error(save_path)

        return

    def test_fix_uuid(self):
        """
        add or replace the "uuid" data in the app's INI file

        TODO - also handle JSON, but for now we ignore this.

        :return:
        """

        import tools.make_load_settings as load_settings
        import uuid

        print("")

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

        value = str(uuid.uuid4())
        logging.info("Creating random UUID={}".format(value))

        load_settings.fix_up_uuid(ini_name, value, backup=False)

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

        value = str(uuid.uuid4())
        logging.info("Creating random UUID={}".format(value))

        load_settings.fix_up_uuid(ini_name, value, backup=False)

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

        print("")

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

        load_settings.increment_app_version(ini_name)

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

        load_settings.increment_app_version(ini_name)

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
