# Test the gps.gps_gate.gps_gate_nmea module
import logging
import unittest

import demo.gps_gate.gps_gate_nmea as nmea


class TestGpsGateNmea(unittest.TestCase):

    def test_distance_meters(self):
        global base_app

        # note: had to manually confirm 'import math' works on router

        base_app.logger.info("TEST Haversine formula for distance")
        base_app.logger.setLevel(logging.INFO)

        lon1 = -93.334702
        lat1 = 45.013432
        base_app.logger.info("MSP long:{} lat:{}".format(lon1, lat1))

        lon2 = -116.20599500000003
        lat2 = 43.6194842
        base_app.logger.info("BOI long:{} lat:{}".format(lon2, lat2))

        obj = nmea.NmeaCollection(base_app.logger)
        delta = obj._distance_meters(lon1, lat1, lon2, lat2)
        base_app.logger.info(
            "Distance MSP to BOI = {} km".format(delta * 1000.0))

        # delta is in meters, not KM
        self.assertEqual(int(delta), 1820118)

        # this returns 1820 KM, by highway is 2347.7 KM
        # by cgs network .com = 1845 KM

        return

    def test_set_distance_filter(self):
        global base_app

        base_app.logger.info("TEST set_distance_filter()")
        base_app.logger.setLevel(logging.INFO)

        obj = nmea.NmeaCollection(base_app.logger)

        min_limit = obj.DISTANCE_FILTER_LIMITS[0]
        max_limit = obj.DISTANCE_FILTER_LIMITS[1]
        base_app.logger.debug("Min:{} Max:{}".format(min_limit, max_limit))
        # distance tests, in meters - alternate
        tests = [
            {'inp': '', 'out': None},
            {'inp': '100', 'out': 100.0},
            {'inp': None, 'out': None},
            {'inp': '100.0', 'out': 100.0},
            {'inp': 0, 'out': None},
            {'inp': 100, 'out': 100.0},
            {'inp': '0', 'out': None},
            {'inp': 100.0, 'out': 100.0},
            {'inp': '0', 'out': None},

            # test clamps
            {'inp': min_limit, 'out': min_limit},
            {'inp': '0', 'out': None},
            {'inp': min_limit - 0.9, 'out': min_limit},
            {'inp': '0', 'out': None},
            {'inp': -1, 'out': min_limit},

            {'inp': '0', 'out': None},
            {'inp': max_limit, 'out': max_limit},
            {'inp': '0', 'out': None},
            {'inp': max_limit + 0.9, 'out': max_limit},
            {'inp': '0', 'out': None},
            {'inp': 99999999, 'out': max_limit},

            {'inp': 'why?', 'out': ValueError},
            {'inp': b'why?', 'out': ValueError},
            {'inp': (1, 2), 'out': ValueError},
        ]

        self.assertTrue(obj.CLAMP_SETTINGS)

        if obj.DISTANCE_FILTER_DEF is None:
            self.assertIsNone(obj.distance_filter)
        else:
            self.assertIsNotNone(obj.distance_filter)

        for test in tests:

            base_app.logger.debug("TEST {}".format(test))

            if test['out'] == ValueError:
                with self.assertRaises(ValueError):
                    obj.set_distance_filter(test['inp'])

            else:
                obj.set_distance_filter(test['inp'])
                self.assertEqual(obj.distance_filter, test['out'])

        # repeat tests with
        obj.CLAMP_SETTINGS = False
        self.assertFalse(obj.CLAMP_SETTINGS)

        # distance tests, in meters - alternate
        tests = [
            {'inp': '', 'out': None},
            {'inp': '100', 'out': 100.0},
            {'inp': None, 'out': None},
            {'inp': '100.0', 'out': 100.0},
            {'inp': 0, 'out': None},
            {'inp': 100, 'out': 100.0},
            {'inp': '0', 'out': None},
            {'inp': 100.0, 'out': 100.0},
            {'inp': '0', 'out': None},

            # test clamps
            {'inp': min_limit, 'out': min_limit},
            {'inp': '0', 'out': None},
            {'inp': min_limit - 0.9, 'out': ValueError},
            {'inp': '0', 'out': None},
            {'inp': -1, 'out': ValueError},

            {'inp': '0', 'out': None},
            {'inp': max_limit, 'out': max_limit},
            {'inp': '0', 'out': None},
            {'inp': max_limit + 0.9, 'out': ValueError},
            {'inp': '0', 'out': None},
            {'inp': 99999999, 'out': ValueError},
        ]

        for test in tests:

            base_app.logger.debug("TEST {}".format(test))

            if test['out'] == ValueError:
                with self.assertRaises(ValueError):
                    obj.set_distance_filter(test['inp'])

            else:
                obj.set_distance_filter(test['inp'])
                self.assertEqual(obj.distance_filter, test['out'])

        return

    def test_set_speed_filter(self):
        global base_app

        base_app.logger.info("TEST set_speed_filter()")
        base_app.logger.setLevel(logging.INFO)

        obj = nmea.NmeaCollection(base_app.logger)

        min_limit = obj.SPEED_FILTER_LIMITS[0]
        max_limit = obj.SPEED_FILTER_LIMITS[1]
        base_app.logger.debug("Min:{} Max:{}".format(min_limit, max_limit))
        # distance tests, in meters - alternate
        tests = [
            {'inp': '', 'out': None},
            {'inp': '100', 'out': 100.0},
            {'inp': None, 'out': None},
            {'inp': '100.0', 'out': 100.0},
            {'inp': 0, 'out': None},
            {'inp': 100, 'out': 100.0},
            {'inp': '0', 'out': None},
            {'inp': 100.0, 'out': 100.0},
            {'inp': '0', 'out': None},

            # test clamps
            {'inp': min_limit, 'out': min_limit},
            {'inp': '0', 'out': None},
            {'inp': min_limit - 0.9, 'out': min_limit},
            {'inp': '0', 'out': None},
            {'inp': -1, 'out': min_limit},

            {'inp': '0', 'out': None},
            {'inp': max_limit, 'out': max_limit},
            {'inp': '0', 'out': None},
            {'inp': max_limit + 0.9, 'out': max_limit},
            {'inp': '0', 'out': None},
            {'inp': 99999999, 'out': max_limit},

            {'inp': 'why?', 'out': ValueError},
            {'inp': b'why?', 'out': ValueError},
            {'inp': (1, 2), 'out': ValueError},
        ]

        self.assertTrue(obj.CLAMP_SETTINGS)

        if obj.SPEED_FILTER_DEF is None:
            self.assertIsNone(obj.speed_filter)
        else:
            self.assertIsNotNone(obj.speed_filter)

        for test in tests:

            base_app.logger.debug("TEST {}".format(test))

            if test['out'] == ValueError:
                with self.assertRaises(ValueError):
                    obj.set_speed_filter(test['inp'])

            else:
                obj.set_speed_filter(test['inp'])
                self.assertEqual(obj.speed_filter, test['out'])

        return

    def test_set_direction_filter(self):
        global base_app

        base_app.logger.info("TEST set_direction_filter()")
        base_app.logger.setLevel(logging.INFO)

        obj = nmea.NmeaCollection(base_app.logger)

        min_limit = obj.DIRECTION_FILTER_LIMITS[0]
        max_limit = obj.DIRECTION_FILTER_LIMITS[1]
        base_app.logger.debug("Min:{} Max:{}".format(min_limit, max_limit))
        # distance tests, in meters - alternate
        tests = [
            {'inp': '', 'out': None},
            {'inp': '100', 'out': 100.0},
            {'inp': None, 'out': None},
            {'inp': '100.0', 'out': 100.0},
            {'inp': 0, 'out': None},
            {'inp': 100, 'out': 100.0},
            {'inp': '0', 'out': None},
            {'inp': 100.0, 'out': 100.0},
            {'inp': '0', 'out': None},

            # test clamps
            {'inp': min_limit, 'out': min_limit},
            {'inp': '0', 'out': None},
            {'inp': min_limit - 0.9, 'out': min_limit},
            {'inp': '0', 'out': None},
            {'inp': -1, 'out': min_limit},

            {'inp': '0', 'out': None},
            {'inp': max_limit, 'out': max_limit},
            {'inp': '0', 'out': None},
            {'inp': max_limit + 0.9, 'out': max_limit},
            {'inp': '0', 'out': None},
            {'inp': 99999999, 'out': max_limit},

            {'inp': 'why?', 'out': ValueError},
            {'inp': b'why?', 'out': ValueError},
            {'inp': (1, 2), 'out': ValueError},
        ]

        self.assertTrue(obj.CLAMP_SETTINGS)

        if obj.DIRECTION_FILTER_DEF is None:
            self.assertIsNone(obj.direction_filter)
        else:
            self.assertIsNotNone(obj.direction_filter)

        for test in tests:

            base_app.logger.debug("TEST {}".format(test))

            if test['out'] == ValueError:
                with self.assertRaises(ValueError):
                    obj.set_direction_filter(test['inp'])

            else:
                obj.set_direction_filter(test['inp'])
                self.assertEqual(obj.direction_filter, test['out'])

        return

    def test_set_direction_threshold(self):
        global base_app

        base_app.logger.info("TEST set_direction_threshold()")
        base_app.logger.setLevel(logging.INFO)

        obj = nmea.NmeaCollection(base_app.logger)

        min_limit = obj.DIRECTION_THRESHOLD_LIMITS[0]
        max_limit = obj.DIRECTION_THRESHOLD_LIMITS[1]
        base_app.logger.debug("Min:{} Max:{}".format(min_limit, max_limit))
        # distance tests, in meters - alternate
        tests = [
            {'inp': '', 'out': None},
            {'inp': '100', 'out': 100.0},
            {'inp': None, 'out': None},
            {'inp': '100.0', 'out': 100.0},
            {'inp': 0, 'out': None},
            {'inp': 100, 'out': 100.0},
            {'inp': '0', 'out': None},
            {'inp': 100.0, 'out': 100.0},
            {'inp': '0', 'out': None},

            # test clamps
            {'inp': min_limit, 'out': min_limit},
            {'inp': '0', 'out': None},
            {'inp': min_limit - 0.9, 'out': min_limit},
            {'inp': '0', 'out': None},
            {'inp': -1, 'out': min_limit},

            {'inp': '0', 'out': None},
            {'inp': max_limit, 'out': max_limit},
            {'inp': '0', 'out': None},
            {'inp': max_limit + 0.9, 'out': max_limit},
            {'inp': '0', 'out': None},
            {'inp': 99999999, 'out': max_limit},

            {'inp': 'why?', 'out': ValueError},
            {'inp': b'why?', 'out': ValueError},
            {'inp': (1, 2), 'out': ValueError},
        ]

        self.assertTrue(obj.CLAMP_SETTINGS)

        if obj.DIRECTION_FILTER_DEF is None:
            self.assertIsNone(obj.direction_threshold)
        else:
            self.assertIsNotNone(obj.direction_threshold)

        for test in tests:

            base_app.logger.debug("TEST {}".format(test))

            if test['out'] == ValueError:
                with self.assertRaises(ValueError):
                    obj.set_direction_threshold(test['inp'])

            else:
                obj.set_direction_threshold(test['inp'])
                self.assertEqual(obj.direction_threshold, test['out'])

        return

    def test_set_time_filter(self):
        global base_app

        base_app.logger.info("TEST set_time_filter()")
        base_app.logger.setLevel(logging.DEBUG)

        obj = nmea.NmeaCollection(base_app.logger)

        min_limit = obj.TIME_FILTER_LIMITS[0]
        max_limit = obj.TIME_FILTER_LIMITS[1]
        base_app.logger.debug("Min:{} Max:{}".format(min_limit, max_limit))
        tests = [
            {'inp': '', 'out': None},
            {'inp': '100', 'out': 100.0},
            {'inp': None, 'out': None},
            {'inp': '100.0', 'out': 100.0},
            {'inp': 0, 'out': None},
            {'inp': 100, 'out': 100.0},
            {'inp': '0', 'out': None},
            {'inp': 100.0, 'out': 100.0},
            {'inp': '0', 'out': None},

            # test clamps
            {'inp': min_limit, 'out': min_limit},
            {'inp': '0', 'out': None},
            {'inp': min_limit - 0.9, 'out': min_limit},
            {'inp': '0', 'out': None},
            {'inp': -1, 'out': min_limit},

            {'inp': '0', 'out': None},
            {'inp': max_limit, 'out': max_limit},
            {'inp': '0', 'out': None},
            {'inp': max_limit + 0.9, 'out': max_limit},
            {'inp': '0', 'out': None},
            {'inp': 99999999, 'out': max_limit},

            {'inp': 'why?', 'out': ValueError},
            {'inp': b'why?', 'out': ValueError},
            {'inp': (1, 2), 'out': ValueError},

            # test the SPECIAL values with time-tags
            {'inp': '1 sec', 'out': min_limit},
            {'inp': '5 sec', 'out': min_limit},
            {'inp': '10 sec', 'out': min_limit},

            {'inp': '15 sec', 'out': 15.0},
            {'inp': '5 min', 'out': 300.0},
            {'inp': '5 hr', 'out': 18000.0},
            {'inp': '20 hr', 'out': 72000.0},
            {'inp': '24 hr', 'out': 86400.0},
            {'inp': '1 day', 'out': 86400.0},

            {'inp': '25 day', 'out': max_limit},
            {'inp': '2 day', 'out': max_limit},
        ]

        self.assertTrue(obj.CLAMP_SETTINGS)

        if obj.TIME_FILTER_DEF is None:
            self.assertIsNone(obj.time_filter)
        else:
            self.assertIsNotNone(obj.time_filter)

        for test in tests:

            base_app.logger.debug("TEST {}".format(test))

            if test['out'] == ValueError:
                with self.assertRaises(ValueError):
                    obj.set_time_filter(test['inp'])

            else:
                obj.set_time_filter(test['inp'])
                self.assertEqual(obj.time_filter, test['out'])

        return


if __name__ == '__main__':
    from cp_lib.app_base import CradlepointAppBase

    base_app = CradlepointAppBase(call_router=False)
    unittest.main()
