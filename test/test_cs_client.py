# Test the cp_lib.cs_client module

import logging
import unittest


class TestCsClient(unittest.TestCase):

    def test_content_length(self):
        """
        Test buffer to lines function
        :return:
        """
        from cp_lib.cs_client import _fetch_content_length

        tests = [
            {"dat": 'content-length: 12\n\r', "len": 12,
             "exp": ''},
            {"dat": 'content-length: 12\n\r\n\r\n"IBR1150LPE"', "len": 0,
             "exp": '"IBR1150LPE"'},
            {"dat": 'content-length: 189', "len": 189,
             "exp": ''},
            {"dat": 'content-length: 189\n\r\n\r\n{"connections": [], "taip_'
                    'vehicle_id": "0000", "enable_gps_keepalive": false, "de'
                    'bug": {"log_nmea_to_fs": false, "flags": 0}, "enable_gp'
                    's_led": false, "pwd_enabled": false, "enabled": true}',
             "len": 0,
             "exp": '{"connections": [], "taip_vehicle_id": "0000", "enable_'
                    'gps_keepalive": false, "debug": {"log_nmea_to_fs": false'
                    ', "flags": 0}, "enable_gps_led": false, "pwd_enabled":'
                    ' false, "enabled": true}'},
        ]

        logger = logging.getLogger('unittest')
        logger.setLevel(logging.DEBUG)

        for test in tests:
            # logging.debug("Test:{}".format(test))

            # _fetch_content_length(data, logger=None):
            data_length, all_data = _fetch_content_length(test['dat'], logger)
            self.assertEqual(data_length, test['len'])
            self.assertEqual(all_data, test['exp'])

            logging.debug("")

        return


if __name__ == '__main__':
    # logging.basicConfig(level=logging.INFO)
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
