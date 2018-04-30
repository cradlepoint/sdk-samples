import requests
import unittest

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
        self.assertIn('Hello World!', res.text)
