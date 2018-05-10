import contextlib
import io
import sys
import unittest.mock
import importlib
import send_to_server


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

            importlib.reload(send_to_server)
            send_to_server.post_to_server()

            # pull info out of stderr 
            output = out.getvalue().strip()

        # if the test passed, stderr should have captured output
        self.assertIn('data sent, http response code: 200', output)

        self.assertNotIn('Exception occurred!', output)
