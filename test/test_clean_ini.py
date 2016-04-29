# Test the cp_lib.clean_ini module

import logging
import os.path
import shutil
import unittest

from cp_lib.clean_ini import clean_ini_file, DEF_BACKUP_EXT


class TestCleanIni(unittest.TestCase):

    TEST_FILE_NAME_INI = "test/test.ini"

    def test_settings(self):
        """
        Test the raw/simple handling of 1 INI to JSON in any directory
        :return:
        """

        data_list = [
            "",
            "# Global settings",
            "",
            "[Logging]",
            "level = debug",
            "name = silly_toes",
            "log_file = trace.txt",
            "#server = (\"192.168.0.10\", 514)",
            "",
            "",
            "[router_api]",
            "local_ip = 192.168.1.1",
            "user_name = admin",
            "password =441b1702",
            "",
            "",
        ]

        # make the original bad-ish file
        _han = open(self.TEST_FILE_NAME_INI, 'w')
        for line in data_list:
            _han.write(line + "\n")
        _han.close()

        test_file_name_bak = self.TEST_FILE_NAME_INI + DEF_BACKUP_EXT
        self._remove_name_no_error(test_file_name_bak)

        self.assertTrue(os.path.exists(self.TEST_FILE_NAME_INI))
        self.assertFalse(os.path.exists(test_file_name_bak))

        clean_ini_file(self.TEST_FILE_NAME_INI, backup=True)

        self.assertTrue(os.path.exists(self.TEST_FILE_NAME_INI))
        self.assertTrue(os.path.exists(test_file_name_bak))

        # self.assertEqual(settings[cp_logging.SETS_NAME], cp_logging.DEF_NAME)

        # clean up the temp file
        # self._remove_name_no_error(self.TEST_FILE_NAME_INI)

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
