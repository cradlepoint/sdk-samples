# Test the cp_lib.load_firmware_info module

import copy
import json
import logging
import os.path
import shutil
import unittest

from cp_lib.load_firmware_info import load_firmware_info, SECTION_FW_INFO

# for internal test of tests - allow temp files to be left on disk
REMOVE_TEMP_FILE = True


class TestLoadFirmwareInfo(unittest.TestCase):

    def test_method_1_ini(self):

        print("")  # skip paste '.' on line

        # make a DEEP copy, to make sure we do not 'pollute' any other tests
        _my_settings = copy.deepcopy(_settings)

        # since we do not test values, all need is a fake ["fw_info"] section
        # but module will try to create ["version"]: "6.1"
        _my_settings[SECTION_FW_INFO] = {"major_version": 6,
                                         "minor_version": 1}

        if False:
            print("Settings after Method #1 test")
            print(json.dumps(_my_settings, indent=4, sort_keys=True))

        result = load_firmware_info(_my_settings, _client)
        self.assertEqual(result, _my_settings)

        return

    def test_method_2_file(self):

        print("")  # skip paste '.' on line

        test_file_name = "test/test_fw_info.json"

        # make a raw JSON string
        data = '{"major_version":6, "fw_update_available":false, "upgrade' +\
            '_patch_version":0, "upgrade_minor_version":0, "build_version' +\
            '":"0310fce", "build_date":"WedJan1300: 23: 15MST2016", "minor' +\
            '_version":1, "upgrade_major_version":0, "manufacturing_up' +\
            'grade":false, "build_type":"FIELD[build]", "custom_defaults":' +\
            'false, "patch_version":0}'

        _logger.debug("Make temp file:{}".format(test_file_name))
        _han = open(test_file_name, 'w')
        _han.write(data)
        _han.close()

        # make a DEEP copy, to make sure we do not 'pollute' any other tests
        _my_settings = copy.deepcopy(_settings)
        self.assertFalse("fw_info" in _my_settings)

        if False:
            print("Settings before Method #2 test")
            print(json.dumps(_my_settings, indent=4, sort_keys=True))

        result = load_firmware_info(_my_settings, _client,
                                    file_name=test_file_name)
        self.assertTrue("fw_info" in result)

        if False:
            print("Settings after Method #2 test")
            print(json.dumps(result, indent=4, sort_keys=True))

        if REMOVE_TEMP_FILE:
            _logger.debug("Delete temp file:{}".format(test_file_name))
            self._remove_name_no_error(test_file_name)

        return

    def test_method_3_url(self):

        print("")  # skip paste '.' on line

        # make a DEEP copy, to make sure we do not 'pollute' any other tests
        _my_settings = copy.deepcopy(_settings)
        self.assertFalse("fw_info" in _my_settings)

        if False:
            print("Settings before Method #3 test")
            print(json.dumps(_my_settings, indent=4, sort_keys=True))

        result = load_firmware_info(_my_settings, _client)
        self.assertTrue("fw_info" in result)

        # if SHOW_SETTINGS_AS_JSON:
        if False:
            print("Settings after Method #3 test")
            print(json.dumps(result, indent=4, sort_keys=True))

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
    from cp_lib.cs_client import init_cs_client_on_my_platform
    from cp_lib.load_settings_ini import load_sdk_ini_as_dict

    # logging.basicConfig(level=logging.INFO)
    logging.basicConfig(level=logging.DEBUG)

    _logger = logging.getLogger('unittest')
    _logger.setLevel(logging.DEBUG)

    # we pass in no APP Dir, so just read the .config data
    _settings = load_sdk_ini_as_dict()
    # _logger.debug("sets:{}".format(_settings))

    # handle the Router API client, which is different between PC
    # testing and router HW
    try:
        _client = init_cs_client_on_my_platform(_logger, _settings)
    except:
        _logger.exception("CSClient init failed")
        raise

    unittest.main()
