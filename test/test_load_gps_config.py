# Test the cp_lib.load_active_wan module

import json
import unittest

from cp_lib.load_gps_config import fetch_gps_config, GpsConfig


class TestFetchGpsConfig(unittest.TestCase):

    def test_fetch(self):
        global base_app

        print("")  # skip paste '.' on line

        result = fetch_gps_config(base_app)
        pretty = json.dumps(result, indent=4, sort_keys=True)

        # if SHOW_SETTINGS_AS_JSON:
        if False:
            file_name = "dump.json"
            print("Write to file:{}".format(file_name))
            file_han = open(file_name, "w")
            file_han.write(pretty)
            file_han.close()

        if False:
            print("Output:{}".format(pretty))

        return

    def test_object(self):
        global base_app

        obj = GpsConfig(base_app)
        self.assertIsNotNone(obj)
        self.assertIsNotNone(obj.data)

        base_app.logger.debug("GPS Enabled:{}".format(obj.is_enabled()))
        base_app.logger.debug("Keepalive Enabled:{}".format(
            obj.keepalive_is_enabled()))
        base_app.logger.debug("GPS to Server:{}".format(obj.get_client_info()))

        return


if __name__ == '__main__':
    from cp_lib.app_base import CradlepointAppBase

    base_app = CradlepointAppBase(call_router=False)
    unittest.main()
