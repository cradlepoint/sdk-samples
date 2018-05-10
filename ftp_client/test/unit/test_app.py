import contextlib
import io
import sys
import time
import unittest
import unittest.mock
import importlib
import ftp_client


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

            importlib.reload(ftp_client)
            ftp_client.send_ftp_file()

            # Pull info out of stdout since this app uses the cs.py log
            # function. This means the logs are converted to prints and
            # go to stdout
            output = out.getvalue().strip()

        # if the test passed, stdout should have captured output
        self.assertIn('FTP login reply: 230 Login successful.', output)
        self.assertIn('FTP STOR reply: 226 Transfer complete.', output)

