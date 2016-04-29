# Test the cp_lib.load_product_info module

import copy
import json
import logging
import os.path
import shutil
import unittest

from cp_lib.load_product_info import load_product_info, \
    SECTION_PRODUCT_INFO, split_product_name

# for internal test of tests - allow temp files to be left on disk
REMOVE_TEMP_FILE = True


class TestLoadProductInfo(unittest.TestCase):

    def test_method_1_ini(self):

        print("")  # skip paste '.' on line

        # make a DEEP copy, to make sure we do not 'pollute' any other tests
        _my_settings = copy.deepcopy(_settings)

        # since do not test values, only need a fake ["product_info"] section
        _my_settings[SECTION_PRODUCT_INFO] = True

        if False:
            print("Settings after Method #1 test")
            print(json.dumps(_my_settings, indent=4, sort_keys=True))

        result = load_product_info(_my_settings, _client)
        self.assertEqual(result, _my_settings)

        return

    def test_method_2_file(self):

        print("")  # skip paste '.' on line

        test_file_name = "test/test_product_info.json"

        # make a raw JSON string
        data = '{"company_name":"Cradlepoint, Inc.","company_url": ' + \
            '"http://cradlepoint.com","copyright":"Cradlepoint, Inc. ' + \
            '2016","mac0": "00:30:44:1a:81:9c","manufacturing":{"board' + \
            '_ID":"050200","mftr_date":"20141204","serial_num":"MM1404' + \
            '59400193"},"product_name": "IBR1150LPE"}'

        _logger.debug("Make temp file:{}".format(test_file_name))
        _han = open(test_file_name, 'w')
        _han.write(data)
        _han.close()

        # make a DEEP copy, to make sure we do not 'pollute' any other tests
        _my_settings = copy.deepcopy(_settings)
        self.assertFalse("product_info" in _my_settings)

        if False:
            print("Settings before Method #2 test")
            print(json.dumps(_my_settings, indent=4, sort_keys=True))

        result = load_product_info(_my_settings, _client,
                                   file_name=test_file_name)
        self.assertTrue("product_info" in result)

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
        self.assertFalse("product_info" in _my_settings)

        if False:
            print("Settings before Method #3 test")
            print(json.dumps(_my_settings, indent=4, sort_keys=True))

        result = load_product_info(_my_settings, _client)
        self.assertTrue("product_info" in result)

        # if SHOW_SETTINGS_AS_JSON:
        if False:
            print("Settings after Method #3 test")
            print(json.dumps(result, indent=4, sort_keys=True))

        return

    def test_split_product_name(self):

        print("")  # skip paste '.' on line

        _logger.debug("test split_product_name")

        tests = [
            {'src': "IBR350", 'exp': ("IBR350", "", False)},
            {'src': "IBR300AT", 'exp': ("IBR300", "AT", True)},

            {'src': "IBR600", 'exp': ("IBR600", "", True)},
            {'src': "IBR600AT", 'exp': ("IBR600", "AT", True)},
            {'src': "IBR650", 'exp': ("IBR650", "", False)},
            {'src': "IBR650AT", 'exp': ("IBR650", "AT", False)},

            {'src': "IBR600B", 'exp': ("IBR600B", "", True)},
            {'src': "IBR600BAT", 'exp': ("IBR600B", "AT", True)},
            {'src': "IBR650B", 'exp': ("IBR650B", "", False)},
            {'src': "IBR650BAT", 'exp': ("IBR650B", "AT", False)},

            {'src': "CBA850", 'exp': ("CBA850", "", False)},
            {'src': "CBA800AT", 'exp': ("CBA800", "AT", True)},

            {'src': "IBR1100", 'exp': ("IBR1100", "", True)},
            {'src': "IBR1100AT", 'exp': ("IBR1100", "AT", True)},
            {'src': "ibr1100LPE", 'exp': ("IBR1100", "LPE", True)},
            {'src': "IBR1150", 'exp': ("IBR1150", "", False)},
            {'src': "IBR1150AT", 'exp': ("IBR1150", "AT", False)},
            {'src': "ibr1150LPE", 'exp': ("IBR1150", "LPE", False)},

            {'src': "AER1600", 'exp': ("AER1600", "", True)},
            {'src': "AER1600AT", 'exp': ("AER1600", "AT", True)},
            {'src': "AER1600LPE", 'exp': ("AER1600", "LPE", True)},
            {'src': "AER1650", 'exp': ("AER1650", "", False)},
            {'src': "AER1650AT", 'exp': ("AER1650", "AT", False)},
            {'src': "AER1650LPE", 'exp': ("AER1650", "LPE", False)},

            # a bit fake, as we'll always see "2100"
            {'src': "AER2100", 'exp': ("AER2100", "", True)},
            {'src': "AER2100AT", 'exp': ("AER2100", "AT", True)},
            {'src': "AER2100LPE", 'exp': ("AER2100", "LPE", True)},
            {'src': "AER2150", 'exp': ("AER2150", "", False)},
            {'src': "AER2150AT", 'exp': ("AER2150", "AT", False)},
            {'src': "AER2150LPE", 'exp': ("AER2150", "LPE", False)},

            {'src': "2100", 'exp': ("AER2100", "", True)},
            {'src': "2100AT", 'exp': ("AER2100", "AT", True)},
            {'src': "2100LPE", 'exp': ("AER2100", "LPE", True)},
            {'src': "2150", 'exp': ("AER2150", "", False)},
            {'src': "2150AT", 'exp': ("AER2150", "AT", False)},
            {'src': "2150LPE", 'exp': ("AER2150", "LPE", False)},

            {'src': "AER3100", 'exp': ("AER3100", "", True)},
            {'src': "AER3100AT", 'exp': ("AER3100", "AT", True)},
            {'src': "AER3100LPE", 'exp': ("AER3100", "LPE", True)},
            {'src': "AER3150", 'exp': ("AER3150", "", False)},
            {'src': "AER3150AT", 'exp': ("AER3150", "AT", False)},
            {'src': "AER3150LPE", 'exp': ("AER3150", "LPE", False)},
        ]

        for test in tests:
            result = split_product_name(test['src'])
            self.assertEqual(result, test['exp'])

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
