import contextlib
import io
import sys
import time
import unittest
import unittest.mock
import importlib
import mqtt_app

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

            importlib.reload(mqtt_app)
            mqtt_thread = Thread(target=mqtt_app.start_mqtt, args=(), daemon=True)
            mqtt_thread.start()

            publish = Thread(target=mqtt_app.publish_thread, args=(), daemon=True)
            publish.start()

            # Need a delay to allow some time for the threads to start
            time.sleep(4)

            # Pull info out of stdout since this app uses the cs.py log
            # function. This means the logs are converted to prints and
            # go to stdout
            output = err.getvalue().strip()

        # if the test passed, stdout should have captured output
        self.assertIn('MQTT connect reply to test.mosquitto.org, 1883: Connection Accepted.', output)
        self.assertIn('MQTT Client connection results: Connection Accepted.', output)
        self.assertIn('Published msg received. topic: /status/gps/lastpos', output)
        self.assertIn('Published msg received. topic: /status/wan/connection_state', output)
        self.assertIn('Published msg received. topic: /status/system/modem_temperature', output)
        self.assertIn('MQTT published file:', output)

        self.assertNotIn('Exception in publish_file().', output)
        self.assertNotIn('Exception in publish_thread().', output)
        self.assertNotIn('Exception in start_mqtt()!', output)
        self.assertNotIn('Exception during start_app()!', output)
