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
        self.assertIn('Starting Server:', res.text)
        self.assertIn('Web Message is: Hello World from Cradlepoint router!', res.text)
        self.assertIn('Received Get request:', res.text)
        self.assertNotIn('Exception occurred!', res.text)

        # Try to access the server that the app started in the router.
        # The port must be open in the router firewall.
        res = requests.get('http://{}:9001'.format(self.DEV_CLIENT_IP))
        self.assertIn('Hello World from Cradlepoint router!', res.text)
        self.assertEquals(200, res.status_code)
