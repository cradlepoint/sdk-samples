import contextlib
import io
import sys
import time
import unittest
import unittest.mock
import importlib
import requests
import simple_custom_dashboard

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

            importlib.reload(simple_custom_dashboard)
            dashboard_thread = Thread(target=simple_custom_dashboard.start_server, args=(), daemon=True)
            dashboard_thread.start()

            # Need a delay to allow some time for the threads to start
            time.sleep(3)

            response = requests.get('http://localhost:9001')

            # Pull info out of stdout since this app uses the cs.py log
            # function. This means the logs are converted to prints and
            # go to stdout
            output = err.getvalue().strip()

        # if the test passed, response should have the http get reply and logs
        # should have captured in output
        self.assertIn('Starting Server:', output)
        self.assertNotIn('Exception occurred!', output)
        self.assertIn('Simple Custom Dashboard', response.text)
        self.assertEquals(200, response.status_code)

