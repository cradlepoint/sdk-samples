import contextlib
import io
import threading
import sys
import time
import unittest
import unittest.mock
from unittest.mock import MagicMock
import importlib
import ping

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
            # augment time.sleep so we don't spend time in it
            time.sleep = unittest.mock.Mock(return_value=None)

            importlib.reload(ping)

            # pull info out of stderr 
            eout = err.getvalue().strip()

        # if the test passed, stderr should have captured output
        self.assertIn('ping result', eout)
