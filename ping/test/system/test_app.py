import requests
import unittest

class TestApp(unittest.TestCase):
     # added by the make.py system test runner if set in sdk_settings.ini
     DEV_CLIENT_IP = ''
     DEV_CLIENT_USER = ''
     DEV_CLIENT_PASS = ''

     def test_running(self):
          # assume basic auth first
          res = requests.get('http://{}/api/status/log'.format(self.DEV_CLIENT_IP),
                    auth=(self.DEV_CLIENT_USER, self.DEV_CLIENT_PASS))

          # if basic auth fails, try digest for FW prior to 6.5.0
          if 'authentication failure' in res.text:
               res = requests.get('http://{}/api/status/log'.format(self.DEV_CLIENT_IP),
                         auth=requests.auth.HTTPDigestAuth(self.DEV_CLIENT_USER,
                              self.DEV_CLIENT_PASS))

          # if test passes, log should contain output
          self.assertIn('ping result', res.text)
