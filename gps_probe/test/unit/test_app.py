import contextlib
import io
import sys
import unittest
import unittest.mock
import importlib


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

    def mock_get_enabled(self, base, query='', tree=0):
        if base == '/config/system/gps/enabled':
            # return True for GPS enabled
            return {"data": True}

        elif base == '/status/gps':
            # return typical GPS data
            return {
                    "connections": {},
                    "fix": {
                        "age": 0.0015553960110992193,
                        "altitude_meters": 863.6,
                        "ground_speed_knots": 0.2,
                        "heading": 0.0,
                        "latitude": {
                            "degree": 43.0,
                            "minute": 37.0,
                            "second": 10.636800000004882
                        },
                        "lock": True,
                        "longitude": {
                            "degree": -116.0,
                            "minute": 12.0,
                            "second": 20.923799999978882
                        },
                        "satellites": 11,
                        "time": 144624
                    },
                    "lastpos": {
                        "age": 166376.77638764298,
                        "latitude": 43.619608666666663,
                        "longitude": -116.20575066666666,
                        "timestamp": 104.50716987900001
                    },
                    "nmea": [
                        "$GPRMC,144624.000,A,4337.17728,N,11612.34873,W,0.2,0.0,180518,,,A*7C",
                        "$GPGGA,144624.000,4337.17728,N,11612.34873,W,1,11,0.9,863.60,M,-18.6,M,,*59",
                        "$GNGNS,144624.000,4337.17728,N,11612.34873,W,AANNN,11,0.9,0863.6,-18.6,,*23",
                        "$GPVTG,0.0,T,,M,0.2,N,0.3,K,A*0C",
                        "$GPGST,144624.000,31.0,15.0,10.2,0.4,14.3,11.2,11.5*66",
                        "$GPGBS,144624.000,14.3,11.2,11.5,,,,*41",
                        "$GNGSA,A,3,27,07,23,16,30,26,09,,,,,,1.4,0.9,1.1*2A",
                        "$GNGSA,A,3,80,68,87,78,,,,,,,,,1.4,0.9,1.1*26",
                        "$GPGSV,3,1,09,09,73,311,27,23,65,123,28,07,44,271,18,16,43,053,26*79",
                        "$GPGSV,3,2,09,27,22,104,23,30,17,261,28,26,16,043,17,03,15,182,15*70",
                        "$GPGSV,3,3,09,08,11,141,21,,,,,,,,,,,,*4F",
                        "$GLGSV,2,1,08,79,73,347,22,68,39,165,31,78,36,039,27,80,28,244,30*66",
                        "$GLGSV,2,2,08,70,24,327,,87,09,031,30,87,09,031,,88,07,075,22*6C"
                    ],
                    "ploop": {},
                    "schedule": {},
                    "state": 1
                }

    def mock_get_disabled(self, base, query='', tree=0):
        if base == '/config/system/gps/enabled':
            # return False for GPS disabled
            return {"data": False}
        return {}

    def test_app(self):
        import cs
        # capture output to test on
        with self._capture_output() as (out, err):
            # augment cs.CSClient().get to return mock data
            cs.CSClient().get = unittest.mock.Mock(side_effect=self.mock_get_enabled)

            gps_probe = importlib.import_module('gps_probe')

            # Pull info out of stdout since this app uses the cs.py log
            # function. This means the logs are converted to prints and
            # go to stdout
            output = out.getvalue().strip()

        # if the test passed, stdout should have captured output
        self.assertIn('GPS Function is Enabled', output)
        self.assertIn('"nmea": [', output)
        self.assertIn('"fix": {', output)
        self.assertIn('"lastpos": {', output)

        with self._capture_output() as (out, err):
            # augment cs.CSClient().get to return mock data gps is disabled
            cs.CSClient().get = unittest.mock.Mock(side_effect=self.mock_get_disabled)
            importlib.reload(gps_probe)

            # Pull info out of stdout since this app uses the cs.py log
            # function. This means the logs are converted to prints and
            # go to stdout
            output = out.getvalue().strip()

        # if the test passed, stdout should have captured output
        self.assertIn('GPS Function is NOT Enabled', output)
