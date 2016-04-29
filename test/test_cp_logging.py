# Test the cp_lib.cp_logging module

import json
import logging
import os.path
import shutil
import unittest

import cp_lib.cp_logging as cp_logging


class TestCpLogging(unittest.TestCase):

    TEST_FILE_NAME_INI = "test/test.ini"
    TEST_FILE_NAME_JSON = "test/test.json"

    def test_settings(self):
        """
        Test the raw/simple handling of 1 INI to JSON in any directory
        :return:
        """

        # start with NO changes
        logging.info("test #0 - all defaults")
        settings = cp_logging._process_settings()
        # logging.debug("settings={}".format(settings))

        self.assertIsNone(settings[cp_logging.SETS_FILE])
        self.assertIsNone(settings[cp_logging.SETS_SYSLOG_IP])

        self.assertEqual(settings[cp_logging.SETS_NAME], cp_logging.DEF_NAME)
        self.assertEqual(settings[cp_logging.SETS_LEVEL], logging.INFO)

        logging.info("test #1 - confirm the LEVEL setting")
        tests = [
            ("10", logging.DEBUG),
            (10, logging.DEBUG),
            ("debug", logging.DEBUG),
            ("Debug", logging.DEBUG),
            ("DEBUG", logging.DEBUG),

            (-10, ValueError),
            (10.0, ValueError),
            ("Junk", ValueError),
            ("", ValueError),
            (None, ValueError),
        ]

        for test in tests:
            value = test[0]
            expect = test[1]

            # logging.info("")
            # logging.debug("Level={0}, type={1}".format(value, type(value)))
            ini_data = [
                "[application]",
                "name = tcp_echo",
                "",
                "[logging]",
                "level = {}".format(value),
            ]
            settings = self._make_ini_file(ini_data)

            if expect == ValueError:
                with self.assertRaises(ValueError):
                    cp_logging._process_settings(settings)
            else:
                settings = cp_logging._process_settings(settings)
                self.assertEqual(settings[cp_logging.SETS_LEVEL], expect)

        logging.info("test #2 - confirm the NAME setting")

        expect = "tcp_echo"
        ini_data = [
            "[application]",
            "name = tcp_echo",
        ]
        settings = self._make_ini_file(ini_data)
        settings = cp_logging._process_settings(settings)
        self.assertEqual(settings[cp_logging.SETS_NAME], expect)

        expect = "runny"
        ini_data = [
            "[application]",
            "name = tcp_echo",
            "",
            "[logging]",
            "name = {}".format(expect),
        ]
        settings = self._make_ini_file(ini_data)
        settings = cp_logging._process_settings(settings)
        self.assertEqual(settings[cp_logging.SETS_NAME], expect)

        # expect = "" (empty string - is ValueError)
        ini_data = [
            "[application]",
            "name = tcp_echo",
            "",
            "[logging]",
            "name = ",
        ]
        settings = self._make_ini_file(ini_data)
        with self.assertRaises(ValueError):
            cp_logging._process_settings(settings)

        logging.info("test #3 - confirm the LOG FILE NAME setting")
        tests = [
            ("log.txt", "log.txt"),
            ("test/log.txt", "test/log.txt"),
            ("", None),
            ]

        for test in tests:
            value = test[0]
            expect = test[1]

            ini_data = [
                "[application]",
                "name = tcp_echo",
                "",
                "[logging]",
                "log_file = {}".format(expect),
            ]
            settings = self._make_ini_file(ini_data)
            settings = cp_logging._process_settings(settings)
            self.assertEqual(settings[cp_logging.SETS_FILE], expect)

        logging.info("test #4 - confirm the SYSLOG SERVER setting")
        tests = [
            ("192.168.0.10", "192.168.0.10", 514),
            (' ("192.168.0.10", 514)', "192.168.0.10", 514),
            ('["192.168.0.10", 514]', "192.168.0.10", 514),
            ('("10.4.23.10", 8514)', "10.4.23.10", 8514),
            ("", None, 514),
            ('("", 8514)', ValueError, 0),
            ('("10.4.23.10", -1)', ValueError, 0),
            ('("10.4.23.10", 0x10000)', ValueError, 0),
            ]

        for test in tests:
            value = test[0]
            expect_ip = test[1]
            expect_port = test[2]

            ini_data = [
                "[application]",
                "name = tcp_echo",
                "",
                "[logging]",
                "syslog = {}".format(value),
            ]
            settings = self._make_ini_file(ini_data)

            if expect_ip == ValueError:
                with self.assertRaises(ValueError):
                    cp_logging._process_settings(settings)
            else:
                settings = cp_logging._process_settings(settings)
                self.assertEqual(settings[cp_logging.SETS_SYSLOG_IP], expect_ip)
                if expect_ip is not None:
                    self.assertEqual(settings[cp_logging.SETS_SYSLOG_PORT], expect_port)

        # clean up the temp file
        self._remove_name_no_error(self.TEST_FILE_NAME_INI)
        self._remove_name_no_error(self.TEST_FILE_NAME_JSON)
        self._remove_name_no_error(self.TEST_FILE_NAME_JSON + ".save")

        return

    def _make_ini_file(self, data_list: list):
        """Bounce settings through INI and JSON"""
        from cp_lib.load_settings import propagate_ini_to_json

        _han = open(self.TEST_FILE_NAME_INI, 'w')
        for line in data_list:
            _han.write(line + "\n")
        _han.close()

        propagate_ini_to_json(self.TEST_FILE_NAME_INI, self.TEST_FILE_NAME_JSON)
        file_han = open(self.TEST_FILE_NAME_JSON, "r")
        settings = json.load(file_han)
        file_han.close()

        return settings

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
