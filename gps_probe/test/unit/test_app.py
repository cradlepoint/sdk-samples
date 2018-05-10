import contextlib
import io
import sys
import time
import unittest
import unittest.mock
import importlib
import gps_probe


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

            importlib.reload(gps_probe)

            # Pull info out of stdout since this app uses the cs.py log
            # function. This means the logs are converted to prints and
            # go to stdout
            output = out.getvalue().strip()

        # if the test passed, stdout should have captured output
        self.assertIn('GPS Function is Enabled', output)
        self.assertIn('"nmea": [', output)
        self.assertIn('"fix": {', output)
        self.assertIn('"lastpos": {', output)
