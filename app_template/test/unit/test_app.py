import contextlib
import io
import sys
import time
import unittest
import unittest.mock
import importlib
import app_template


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

            # augment time.sleep so when it is called it will throw an exception
            # immediately instead of looping forever so we can exit the test
            mock = unittest.mock.Mock(side_effect=Exception('quick exit'))
            time.sleep = mock

            importlib.reload(app_template)
            app_template.action('start')
            app_template.action('stop')

            # pull info out of stderr 
            eout = err.getvalue().strip()

        # if the test passed, stderr should have captured output
        self.assertIn('start_app()', eout)
        self.assertIn('stop_app()', eout)
