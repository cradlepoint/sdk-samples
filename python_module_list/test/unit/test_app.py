import contextlib
import io
import sys
import time
import unittest
import unittest.mock
import importlib
import python_module_list


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

            importlib.reload(python_module_list)
            python_module_list.log_module_list()

            # pull info out of stderr 
            output = err.getvalue().strip()

        # if the test passed, stderr should have captured output
        self.assertIn('---------- Python Version:', output)
        self.assertIn('---------- Module Count=', output)

        self.assertNotIn('Exception occurred!', output)
