# Test the cp_lib.probe_serial module

import json
import unittest

import cp_lib.probe_serial as probe_serial

PPRINT_RESULT = True


class TestSerialRedirectorConfig(unittest.TestCase):

    def test_serial_redirect(self):
        global base_app

        print("")  # skip paste '.' on line

        obj = probe_serial.SerialRedirectorConfig(base_app)
        base_app.logger.info("Fetch {}".format(obj.topic))
        result = obj.refresh()

        self.assertIsNotNone(result)

        if PPRINT_RESULT:
            print(json.dumps(result, indent=4, sort_keys=True))

        if True:
            # these would only be true in some situations
            expect_port = "ttyS1"
            self.assertFalse(obj.enabled())
            self.assertFalse(obj.enabled(expect_port))
            self.assertFalse(obj.enabled("fifth_port"))
            self.assertEqual(obj.port_name(), expect_port)

        return

    def test_serial_gpio(self):
        global base_app

        print("")  # skip paste '.' on line

        obj = probe_serial.SerialGPIOConfig(base_app)
        base_app.logger.info("Fetch {}".format(obj.topic))
        result = obj.refresh()

        self.assertIsNotNone(result)

        if PPRINT_RESULT:
            print(json.dumps(result, indent=4, sort_keys=True))

        if True:
            # these would only be true in some situations
            self.assertFalse(obj.enabled())

        return

    def test_serial_gps(self):
        global base_app

        print("")  # skip paste '.' on line

        obj = probe_serial.SerialGpsConfig(base_app)
        base_app.logger.info("Fetch {}".format(obj.topic))
        result = obj.refresh()

        self.assertIsNotNone(result)

        if PPRINT_RESULT:
            print(json.dumps(result, indent=4, sort_keys=True))

        if True:
            # these would only be true in some situations
            expect_port = "ttyS1"
            if False:
                # for when is true in actual config of 1100
                self.assertTrue(obj.enabled())
                self.assertTrue(obj.enabled(expect_port))
            else:
                self.assertFalse(obj.enabled())
                self.assertFalse(obj.enabled(expect_port))

            # this one will always be False
            self.assertFalse(obj.enabled("fifth_port"))

        return

    def test_probe_if_serial_available(self):
        global base_app

        print("")  # skip paste '.' on line

        result = probe_serial.probe_if_serial_available(base_app)

        if PPRINT_RESULT:
            print(json.dumps(result, indent=4, sort_keys=True))

        # these would only be true in some situations
        expect_port = "ttyS1"
        result = probe_serial.probe_if_serial_available(base_app,expect_port)

        if PPRINT_RESULT:
            print(json.dumps(result, indent=4, sort_keys=True))

        return


if __name__ == '__main__':
    from cp_lib.app_base import CradlepointAppBase

    base_app = CradlepointAppBase()

    unittest.main()
