# Test the PARSE DURATION module

import unittest
import random

from cp_lib.parse_duration import TimeDuration


class TestParseDuration(unittest.TestCase):

    def test_parse_time_duration(self):

        obj = TimeDuration()

        self.assertEqual(obj.parse_time_duration_to_seconds(1), 1.0)
        self.assertEqual(obj.get_period_as_string(), "1 sec")

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('1'), 1.0)
        self.assertEqual(obj.get_period_as_string(), "1 sec")

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('01'), 1.0)
        self.assertEqual(obj.get_period_as_string(), "1 sec")

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('0x01'), 1.0)
        self.assertEqual(obj.get_period_as_string(), "1 sec")

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('1 ms'), 0.001)
        self.assertEqual(obj.get_period_as_string(), '1 ms')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('1 msec'), 0.001)
        self.assertEqual(obj.get_period_as_string(), '1 ms')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('1 sec'), 1.0)
        self.assertEqual(obj.get_period_as_string(), '1 sec')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds(b'1 sec'), 1.0)
        self.assertEqual(obj.get_period_as_string(), '1 sec')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('1 second'), 1.0)
        self.assertEqual(obj.get_period_as_string(), '1 sec')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('1 min'), 60.0)
        self.assertEqual(obj.get_period_as_string(), '1 min')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('1 minute'), 60.0)
        self.assertEqual(obj.get_period_as_string(), '1 min')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('1 minutes'), 60.0)
        self.assertEqual(obj.get_period_as_string(), '1 min')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('1 hr'), 3600.0)
        self.assertEqual(obj.get_period_as_string(), '1 hr')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('1 HR'), 3600.0)
        self.assertEqual(obj.get_period_as_string(), '1 hr')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('1 Hours'), 3600.0)
        self.assertEqual(obj.get_period_as_string(), '1 hr')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('1 day'), 86400.0)
        self.assertEqual(obj.get_period_as_string(), '1 day')

        # note: these handled, but have NO 'seconds' result
        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('1 month'), None)
        self.assertEqual(obj.get_period_as_string(), '1 mon')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('1 year'), None)
        self.assertEqual(obj.get_period_as_string(), '1 yr')

        # repeat with more than 1 - a random value
        seed = random.randint(101, 999)
        source = "{0} ms".format(seed)
        expect_sec = seed * 0.001
        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds(source),
                         expect_sec)
        self.assertEqual(obj.get_period_as_string(), source)

        seed = random.randint(2, 59)
        source = "{0} sec".format(seed)
        expect_sec = seed * 1.0
        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds(source),
                         expect_sec)
        self.assertEqual(obj.get_period_as_string(), source)

        seed = random.randint(2, 59)
        source = "{0} min".format(seed)
        expect_sec = seed * 60.0
        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds(source),
                         expect_sec)
        self.assertEqual(obj.get_period_as_string(), source)

        seed = random.randint(2, 23)
        source = "{0} hr".format(seed)
        expect_sec = seed * 3600.0
        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds(source),
                         expect_sec)
        self.assertEqual(obj.get_period_as_string(), source)

        seed = random.randint(2, 9)
        source = "{0} day".format(seed)
        expect_sec = seed * 86400.0
        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds(source),
                         expect_sec)
        self.assertEqual(obj.get_period_as_string(), source)

        # note: these handled, but have NO 'seconds' result
        seed = random.randint(2, 9)
        source = "{0} mon".format(seed)
        expect_sec = None
        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds(source),
                         expect_sec)
        self.assertEqual(obj.get_period_as_string(), source)

        seed = random.randint(2, 9)
        source = "{0} yr".format(seed)
        expect_sec = None
        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds(source),
                         expect_sec)
        self.assertEqual(obj.get_period_as_string(), source)

        return

    def test_parse_time_duration_plus_minus(self):

        obj = TimeDuration()
        # check the signs - +/- to allow things like "do 5 minutes before X"

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('+1 ms'), 0.001)
        self.assertEqual(obj.get_period_as_string(), '1 ms')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('-1 ms'), -0.001)
        self.assertEqual(obj.get_period_as_string(), '-1 ms')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('+1 sec'), 1.0)
        self.assertEqual(obj.get_period_as_string(), '1 sec')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds(b'-1 sec'), -1.0)
        self.assertEqual(obj.get_period_as_string(), '-1 sec')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('+1 min'), 60.0)
        self.assertEqual(obj.get_period_as_string(), '1 min')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('-5 min'), -300.0)
        self.assertEqual(obj.get_period_as_string(), '-5 min')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('+2 hr'), 7200.0)
        self.assertEqual(obj.get_period_as_string(), '2 hr')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('-3 hr'), -10800.0)
        self.assertEqual(obj.get_period_as_string(), '-3 hr')

        # confirm the UTC 'decoration' is ignored,
        # including ('z', 'zulu', 'gm', 'utc', 'uct')
        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('+1 ms utc'),
                         0.001)
        self.assertEqual(obj.get_period_as_string(), '1 ms')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('-1 ms UTC'),
                         -0.001)
        self.assertEqual(obj.get_period_as_string(), '-1 ms')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('+1 sec z'),
                         1.0)
        self.assertEqual(obj.get_period_as_string(), '1 sec')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds(b'-1 sec Z'), -1.0)
        self.assertEqual(obj.get_period_as_string(), '-1 sec')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('+1 min gm'), 60.0)
        self.assertEqual(obj.get_period_as_string(), '1 min')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('-5 min GM'),
                         -300.0)
        self.assertEqual(obj.get_period_as_string(), '-5 min')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('+2 hr uct'),
                         7200.0)
        self.assertEqual(obj.get_period_as_string(), '2 hr')

        obj.reset()
        self.assertEqual(obj.parse_time_duration_to_seconds('-3 hr zulu'),
                         -10800.0)
        self.assertEqual(obj.get_period_as_string(), '-3 hr')

        return

    def test_utc_decoration(self):

        obj = TimeDuration()

        self.assertFalse(obj._decode_utc_element('1 ms'))
        self.assertTrue(obj._decode_utc_element('1 ms utc'))

        self.assertFalse(obj._decode_utc_element('1 sec'))
        self.assertTrue(obj._decode_utc_element('1 sec ZulU'))

        self.assertFalse(obj._decode_utc_element('1 min'))
        self.assertTrue(obj._decode_utc_element('1 min GM'))

        self.assertFalse(obj._decode_utc_element('1 hr'))
        self.assertTrue(obj._decode_utc_element('1 hr Z'))

        self.assertFalse(obj._decode_utc_element('1 day'))
        self.assertTrue(obj._decode_utc_element('1 day UCT'))

        self.assertFalse(obj._decode_utc_element('1 mon'))
        self.assertTrue(obj._decode_utc_element('1 mon UTC'))

        return

    def test_tag_decode(self):

        obj = TimeDuration()

        self.assertEqual(obj.decode_time_tag('ms'), obj.DURATION_MSEC)
        self.assertEqual(obj.decode_time_tag('msec'), obj.DURATION_MSEC)
        self.assertEqual(obj.decode_time_tag('millisecond'), obj.DURATION_MSEC)
        self.assertEqual(obj.decode_time_tag('milliseconds'),
                         obj.DURATION_MSEC)
        self.assertEqual(obj.get_tag_as_string(obj.DURATION_MSEC), 'ms')

        self.assertEqual(obj.decode_time_tag('sec'), obj.DURATION_SECOND)
        self.assertEqual(obj.decode_time_tag('second'), obj.DURATION_SECOND)
        self.assertEqual(obj.decode_time_tag('seconds'), obj.DURATION_SECOND)
        self.assertEqual(obj.get_tag_as_string(obj.DURATION_SECOND), 'sec')
        self.assertEqual(obj.get_tag_as_string(0), 'sec')

        self.assertEqual(obj.decode_time_tag('min'), obj.DURATION_MINUTE)
        self.assertEqual(obj.decode_time_tag('minute'), obj.DURATION_MINUTE)
        self.assertEqual(obj.decode_time_tag('minutes'), obj.DURATION_MINUTE)
        self.assertEqual(obj.get_tag_as_string(obj.DURATION_MINUTE), 'min')

        self.assertEqual(obj.decode_time_tag('hr'), obj.DURATION_HOUR)
        self.assertEqual(obj.decode_time_tag('hour'), obj.DURATION_HOUR)
        self.assertEqual(obj.decode_time_tag('hours'), obj.DURATION_HOUR)
        self.assertEqual(obj.get_tag_as_string(obj.DURATION_HOUR), 'hr')

        self.assertEqual(obj.decode_time_tag('dy'), obj.DURATION_DAY)
        self.assertEqual(obj.decode_time_tag('day'), obj.DURATION_DAY)
        self.assertEqual(obj.decode_time_tag('days'), obj.DURATION_DAY)
        self.assertEqual(obj.get_tag_as_string(obj.DURATION_DAY), 'day')

        self.assertEqual(obj.decode_time_tag('mon'), obj.DURATION_MONTH)
        self.assertEqual(obj.decode_time_tag('month'), obj.DURATION_MONTH)
        self.assertEqual(obj.decode_time_tag('months'), obj.DURATION_MONTH)
        self.assertEqual(obj.get_tag_as_string(obj.DURATION_MONTH), 'mon')

        self.assertEqual(obj.decode_time_tag('yr'), obj.DURATION_YEAR)
        self.assertEqual(obj.decode_time_tag('year'), obj.DURATION_YEAR)
        self.assertEqual(obj.decode_time_tag('years'), obj.DURATION_YEAR)
        self.assertEqual(obj.get_tag_as_string(obj.DURATION_YEAR), 'yr')

        obj.reset()
        with self.assertRaises(ValueError):
            obj.get_tag_as_string(-1)
            obj.get_tag_as_string(7)
            obj.decode_time_tag('homey')

        with self.assertRaises(TypeError):
            obj.get_tag_as_string('hello')
            obj.decode_time_tag(None)
            obj.decode_time_tag(3)

        return


if __name__ == '__main__':
    unittest.main()
