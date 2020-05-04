import requests
import unittest


# This test expects the app to have been installed and uninstalled.
class TestApp(unittest.TestCase):
    # added by the make.py system test runner if set in sdk_settings.ini
    DEV_CLIENT_IP = ''
    DEV_CLIENT_USER = ''
    DEV_CLIENT_PASS = ''

    def test_running(self):
        # assume basic first
        res = requests.get('http://{}/api/status/log'.format(self.DEV_CLIENT_IP),
                           auth=(self.DEV_CLIENT_USER, self.DEV_CLIENT_PASS))

        # if basic failed try Digest for FW prior to 6.5.0
        if 'authentication failure' in res.text:
            res = requests.get('http://{}/api/status/log'.format(self.DEV_CLIENT_IP),
                               auth=requests.auth.HTTPDigestAuth(self.DEV_CLIENT_USER,
                                                                 self.DEV_CLIENT_PASS))

        # if the test passed, log should contain output
        self.assertIn('MQTT connect reply to test.mosquitto.org, 1883: Connection Accepted.', res.text)
        self.assertIn('MQTT Client connection results: Connection Accepted.', res.text)
        self.assertIn('Published msg received. topic: /status/gps/lastpos', res.text)
        self.assertIn('Published msg received. topic: /status/wan/connection_state', res.text)
        self.assertIn('Published msg received. topic: /status/system/modem_temperature', res.text)
        self.assertIn('MQTT published file:', res.text)

        self.assertNotIn('Exception in publish_file().', res.text)
        self.assertNotIn('Exception in publish_thread().', res.text)
        self.assertNotIn('Exception in start_mqtt()!', res.text)
        self.assertNotIn('Exception during start_app()!', res.text)
