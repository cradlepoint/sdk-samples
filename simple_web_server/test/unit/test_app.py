import contextlib
import io
import sys
import time
import unittest
import unittest.mock
import importlib
import requests
import simple_web_server

from threading import Thread


class TestApp(unittest.TestCase):

    @contextlib.contextmanager
    def _capture_output(self):
        new_out, new_err = io.StringIO(), io.StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        try:
            sys.stdout, sys.stderr = new_out, new_err
            yield sys.stdout, sys.stderr
        finally:
            sys.stdout, sys.stderr = old_out, old_err

    def test_app(self):

        # capture output to test on
        with self._capture_output() as (out, err):

            importlib.reload(simple_web_server)
            web_server_thread = Thread(target=simple_web_server.start_server, args=(), daemon=True)
            web_server_thread.start()

            # Need a delay to allow some time for the threads to start
            time.sleep(2)

            res = requests.get('http://localhost:9001')

            # Pull info out of stdout since this app uses the cs.py log
            # function. This means the logs are converted to prints and
            # go to stdout
            output = out.getvalue().strip()

        # if the test passed, response should have the http get reply and logs
        # should have captured in output
        self.assertIn('Starting Server:', output)
        self.assertIn('Received Get request:', output)
        self.assertIn('Web Message is: Hello World from Cradlepoint router!', output)
        self.assertNotIn('Exception occurred!', output)

        self.assertEquals(200, res.status_code)
        self.assertIn('Hello World from Cradlepoint router!', res.text)

