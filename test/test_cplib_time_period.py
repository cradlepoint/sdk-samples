# Test the PARSE DURATION module

import unittest

import cp_lib.time_period as time_period


class TestTimePeriod(unittest.TestCase):

    def test_valid_clean_period_seconds(self):

        # zero is special, as it is not relevant to this function
        seconds = 0
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        # self.assertFalse((60 % seconds) == 0)

        # one is typical TRUE situation - see '7' for typical FALSE situation
        seconds += 1  # == 1
        self.assertTrue(time_period.is_valid_clean_period_seconds(seconds))
        self.assertTrue((60 % seconds) == 0)

        seconds += 1  # == 2
        self.assertTrue(time_period.is_valid_clean_period_seconds(seconds))
        self.assertTrue((60 % seconds) == 0)

        seconds += 1  # == 3
        self.assertTrue(time_period.is_valid_clean_period_seconds(seconds))
        self.assertTrue((60 % seconds) == 0)

        seconds += 1  # == 4
        self.assertTrue(time_period.is_valid_clean_period_seconds(seconds))
        self.assertTrue((60 % seconds) == 0)

        seconds += 1  # == 5
        self.assertTrue(time_period.is_valid_clean_period_seconds(seconds))
        self.assertTrue((60 % seconds) == 0)

        seconds += 1  # == 6
        self.assertTrue(time_period.is_valid_clean_period_seconds(seconds))
        self.assertTrue((60 % seconds) == 0)

        # seven is typical FALSE situation - see any 1 to 6 for typical
        # FALSE situation
        seconds += 1  # == 7
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 8
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 9
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 10
        self.assertTrue(time_period.is_valid_clean_period_seconds(seconds))
        self.assertTrue((60 % seconds) == 0)

        seconds += 1  # == 11
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 12
        self.assertTrue(time_period.is_valid_clean_period_seconds(seconds))
        self.assertTrue((60 % seconds) == 0)

        seconds += 1  # == 13
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 14
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 15
        self.assertTrue(time_period.is_valid_clean_period_seconds(seconds))
        self.assertTrue((60 % seconds) == 0)

        seconds += 1  # == 16
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 17
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 18
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 19
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 20
        self.assertTrue(time_period.is_valid_clean_period_seconds(seconds))
        self.assertTrue((60 % seconds) == 0)

        seconds += 1  # == 21
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 22
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 23
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 24
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 25
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 26
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 27
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 28
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 29
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 30
        self.assertTrue(time_period.is_valid_clean_period_seconds(seconds))
        self.assertTrue((60 % seconds) == 0)

        seconds += 1  # == 31
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 32
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 33
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 34
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 35
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 36
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 37
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 38
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 39
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 40
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 41
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 42
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 43
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 44
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 45
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 46
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 47
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 48
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 49
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 50
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 51
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 52
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 53
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 54
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 55
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 56
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 57
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 58
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 59
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        seconds += 1  # == 60
        self.assertTrue(time_period.is_valid_clean_period_seconds(seconds))
        self.assertTrue((60 % seconds) == 0)

        seconds += 1  # == 61
        self.assertFalse(time_period.is_valid_clean_period_seconds(seconds))
        self.assertFalse((60 % seconds) == 0)

        with self.assertRaises(TypeError):
            time_period.is_valid_clean_period_seconds(None)

        # because we use 'int()' on value, these work as shown despite not
        # being a goal
        self.assertTrue(time_period.is_valid_clean_period_seconds(2.0))
        self.assertTrue(time_period.is_valid_clean_period_seconds('2'))
        # int() rounds 2.1 to be 2 - again, not as desired, but result is
        # largely as expected
        self.assertTrue(time_period.is_valid_clean_period_seconds(2.1))
        self.assertFalse(time_period.is_valid_clean_period_seconds(7.1))

        with self.assertRaises(ValueError):
            time_period.is_valid_clean_period_seconds('2.1')

        with self.assertRaises(ValueError):
            time_period.is_valid_clean_period_seconds('7.1')

        return

    def test_valid_clean_period_minutes(self):

        # zero is special, as it is not relevant to this function
        minutes = 0
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        # self.assertFalse((60 % minutes) == 0)

        # one is typical TRUE situation - see '7' for typical FALSE situation
        minutes += 1  # == 1
        self.assertTrue(time_period.is_valid_clean_period_minutes(minutes))
        self.assertTrue((60 % minutes) == 0)

        minutes += 1  # == 2
        self.assertTrue(time_period.is_valid_clean_period_minutes(minutes))
        self.assertTrue((60 % minutes) == 0)

        minutes += 1  # == 3
        self.assertTrue(time_period.is_valid_clean_period_minutes(minutes))
        self.assertTrue((60 % minutes) == 0)

        minutes += 1  # == 4
        self.assertTrue(time_period.is_valid_clean_period_minutes(minutes))
        self.assertTrue((60 % minutes) == 0)

        minutes += 1  # == 5
        self.assertTrue(time_period.is_valid_clean_period_minutes(minutes))
        self.assertTrue((60 % minutes) == 0)

        minutes += 1  # == 6
        self.assertTrue(time_period.is_valid_clean_period_minutes(minutes))
        self.assertTrue((60 % minutes) == 0)

        # seven is typical FALSE situation - see any 1 to 6 for typical
        # FALSE situation
        minutes += 1  # == 7
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 8
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 9
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 10
        self.assertTrue(time_period.is_valid_clean_period_minutes(minutes))
        self.assertTrue((60 % minutes) == 0)

        minutes += 1  # == 11
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 12
        self.assertTrue(time_period.is_valid_clean_period_minutes(minutes))
        self.assertTrue((60 % minutes) == 0)

        minutes += 1  # == 13
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 14
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 15
        self.assertTrue(time_period.is_valid_clean_period_minutes(minutes))
        self.assertTrue((60 % minutes) == 0)

        minutes += 1  # == 16
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 17
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 18
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 19
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 20
        self.assertTrue(time_period.is_valid_clean_period_minutes(minutes))
        self.assertTrue((60 % minutes) == 0)

        minutes += 1  # == 21
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 22
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 23
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 24
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 25
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 26
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 27
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 28
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 29
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 30
        self.assertTrue(time_period.is_valid_clean_period_minutes(minutes))
        self.assertTrue((60 % minutes) == 0)

        minutes += 1  # == 31
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 32
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 33
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 34
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 35
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 36
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 37
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 38
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 39
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 40
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 41
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 42
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 43
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 44
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 45
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 46
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 47
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 48
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 49
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 50
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 51
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 52
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 53
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 54
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 55
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 56
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 57
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 58
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 59
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        minutes += 1  # == 60
        self.assertTrue(time_period.is_valid_clean_period_minutes(minutes))
        self.assertTrue((60 % minutes) == 0)

        minutes += 1  # == 61
        self.assertFalse(time_period.is_valid_clean_period_minutes(minutes))
        self.assertFalse((60 % minutes) == 0)

        with self.assertRaises(TypeError):
            time_period.is_valid_clean_period_minutes(None)

        # because we use 'int()' on value, these work as shown despite
        # not being a goal
        self.assertTrue(time_period.is_valid_clean_period_minutes(2.0))
        self.assertTrue(time_period.is_valid_clean_period_minutes('2'))
        # int() rounds 2.1 to be 2 - again, not as desired, but result
        # is largely as expected
        self.assertTrue(time_period.is_valid_clean_period_minutes(2.1))
        self.assertFalse(time_period.is_valid_clean_period_minutes(7.1))

        with self.assertRaises(ValueError):
            time_period.is_valid_clean_period_minutes('2.1')

        with self.assertRaises(ValueError):
            time_period.is_valid_clean_period_minutes('7.1')

        return

    def test_valid_clean_period_hours(self):

        # zero is special, as it is not relevant to this function
        hours = 0
        self.assertFalse(time_period.is_valid_clean_period_hours(hours))
        # self.assertFalse((24 % hours) == 0)

        # one is typical TRUE situation - see '7' for typical FALSE situation
        hours += 1  # == 1
        self.assertTrue(time_period.is_valid_clean_period_hours(hours))
        self.assertTrue((24 % hours) == 0)

        hours += 1  # == 2
        self.assertTrue(time_period.is_valid_clean_period_hours(hours))
        self.assertTrue((24 % hours) == 0)

        hours += 1  # == 3
        self.assertTrue(time_period.is_valid_clean_period_hours(hours))
        self.assertTrue((24 % hours) == 0)

        hours += 1  # == 4
        self.assertTrue(time_period.is_valid_clean_period_hours(hours))
        self.assertTrue((24 % hours) == 0)

        hours += 1  # == 5
        self.assertFalse(time_period.is_valid_clean_period_hours(hours))
        self.assertFalse((24 % hours) == 0)

        hours += 1  # == 6
        self.assertTrue(time_period.is_valid_clean_period_hours(hours))
        self.assertTrue((24 % hours) == 0)

        # seven is typical FALSE situation - see any 1 to 6 for
        # typical FALSE situation
        hours += 1  # == 7
        self.assertFalse(time_period.is_valid_clean_period_hours(hours))
        self.assertFalse((24 % hours) == 0)

        hours += 1  # == 8
        self.assertTrue(time_period.is_valid_clean_period_hours(hours))
        self.assertTrue((24 % hours) == 0)

        hours += 1  # == 9
        self.assertFalse(time_period.is_valid_clean_period_hours(hours))
        self.assertFalse((24 % hours) == 0)

        hours += 1  # == 10
        self.assertFalse(time_period.is_valid_clean_period_hours(hours))
        self.assertFalse((24 % hours) == 0)

        hours += 1  # == 11
        self.assertFalse(time_period.is_valid_clean_period_hours(hours))
        self.assertFalse((24 % hours) == 0)

        hours += 1  # == 12
        self.assertTrue(time_period.is_valid_clean_period_hours(hours))
        self.assertTrue((24 % hours) == 0)

        hours += 1  # == 13
        self.assertFalse(time_period.is_valid_clean_period_hours(hours))
        self.assertFalse((24 % hours) == 0)

        hours += 1  # == 14
        self.assertFalse(time_period.is_valid_clean_period_hours(hours))
        self.assertFalse((24 % hours) == 0)

        hours += 1  # == 15
        self.assertFalse(time_period.is_valid_clean_period_hours(hours))
        self.assertFalse((24 % hours) == 0)

        hours += 1  # == 16
        self.assertFalse(time_period.is_valid_clean_period_hours(hours))
        self.assertFalse((24 % hours) == 0)

        hours += 1  # == 17
        self.assertFalse(time_period.is_valid_clean_period_hours(hours))
        self.assertFalse((24 % hours) == 0)

        hours += 1  # == 18
        self.assertFalse(time_period.is_valid_clean_period_hours(hours))
        self.assertFalse((24 % hours) == 0)

        hours += 1  # == 19
        self.assertFalse(time_period.is_valid_clean_period_hours(hours))
        self.assertFalse((24 % hours) == 0)

        hours += 1  # == 20
        self.assertFalse(time_period.is_valid_clean_period_hours(hours))
        self.assertFalse((24 % hours) == 0)

        hours += 1  # == 21
        self.assertFalse(time_period.is_valid_clean_period_hours(hours))
        self.assertFalse((24 % hours) == 0)

        hours += 1  # == 22
        self.assertFalse(time_period.is_valid_clean_period_hours(hours))
        self.assertFalse((24 % hours) == 0)

        hours += 1  # == 23
        self.assertFalse(time_period.is_valid_clean_period_hours(hours))
        self.assertFalse((24 % hours) == 0)

        hours += 1  # == 24
        self.assertTrue(time_period.is_valid_clean_period_hours(hours))
        self.assertTrue((24 % hours) == 0)

        hours += 1  # == 25
        self.assertFalse(time_period.is_valid_clean_period_hours(hours))
        self.assertFalse((24 % hours) == 0)

        with self.assertRaises(TypeError):
            time_period.is_valid_clean_period_hours(None)

        # because we use 'int()' on value, these work as shown despite
        # not being a goal
        self.assertTrue(time_period.is_valid_clean_period_hours(2.0))
        self.assertTrue(time_period.is_valid_clean_period_hours('2'))
        # int() truncates 2.1 to 2 (& 6.9 to 6) - again, not as desired,
        # but result is largely as expected
        self.assertTrue(time_period.is_valid_clean_period_hours(1.9))
        self.assertTrue(time_period.is_valid_clean_period_hours(2.1))
        self.assertTrue(time_period.is_valid_clean_period_hours(6.9))
        self.assertFalse(time_period.is_valid_clean_period_hours(7.1))

        with self.assertRaises(ValueError):
            time_period.is_valid_clean_period_hours('2.1')

        with self.assertRaises(ValueError):
            time_period.is_valid_clean_period_hours('7.1')

        return

    def test_next_sec_or_min(self):

        # since next_minutes_period() just calls next_seconds_period(),
        # there is no need to test both

        # we'll start with a basic test of a '15 sec' period
        period = 15
        self.assertEqual(time_period.next_seconds_period(0, period), 15)
        self.assertEqual(time_period.next_seconds_period(1, period), 15)
        self.assertEqual(time_period.next_seconds_period(5, period), 15)
        self.assertEqual(time_period.next_seconds_period(13, period), 15)
        self.assertEqual(time_period.next_seconds_period(15, period), 30)
        self.assertEqual(time_period.next_seconds_period(16, period), 30)
        self.assertEqual(time_period.next_seconds_period(29, period), 30)
        self.assertEqual(time_period.next_seconds_period(30, period), 45)
        self.assertEqual(time_period.next_seconds_period(31, period), 45)
        self.assertEqual(time_period.next_seconds_period(44, period), 45)
        self.assertEqual(time_period.next_seconds_period(45, period), 60)
        self.assertEqual(time_period.next_seconds_period(46, period), 60)
        self.assertEqual(time_period.next_seconds_period(59, period), 60)
        self.assertEqual(time_period.next_seconds_period(60, period), 75)

        # handle larger values
        self.assertEqual(time_period.next_seconds_period(61, period), 75)
        self.assertEqual(time_period.next_seconds_period(292, period), 300)

        return

    def test_delay_to_next_seconds(self):

        # we'll start with a basic test of a '15 sec' period
        period = 15
        self.assertEqual(
            time_period.delay_to_next_seconds_period(0, period), 15)
        self.assertEqual(
            time_period.delay_to_next_seconds_period(1, period), 14)
        self.assertEqual(
            time_period.delay_to_next_seconds_period(5, period), 10)
        self.assertEqual(
            time_period.delay_to_next_seconds_period(13, period), 2)
        self.assertEqual(
            time_period.delay_to_next_seconds_period(15, period), 15)
        self.assertEqual(
            time_period.delay_to_next_seconds_period(16, period), 14)
        self.assertEqual(
            time_period.delay_to_next_seconds_period(29, period), 1)
        self.assertEqual(
            time_period.delay_to_next_seconds_period(30, period), 15)
        self.assertEqual(
            time_period.delay_to_next_seconds_period(31, period), 14)
        self.assertEqual(
            time_period.delay_to_next_seconds_period(44, period), 1)
        self.assertEqual(
            time_period.delay_to_next_seconds_period(45, period), 15)
        self.assertEqual(
            time_period.delay_to_next_seconds_period(46, period), 14)
        self.assertEqual(
            time_period.delay_to_next_seconds_period(59, period), 1)
        self.assertEqual(
            time_period.delay_to_next_seconds_period(60, period), 15)

        # handle larger values
        self.assertEqual(
            time_period.delay_to_next_seconds_period(61, period), 14)
        self.assertEqual(
            time_period.delay_to_next_seconds_period(292, period), 8)

        # toss a few delay_to_next_minutes_period() tests
        self.assertEqual(
            time_period.delay_to_next_minutes_period(0, period), 15)
        self.assertEqual(
            time_period.delay_to_next_minutes_period(1, period), 14)
        self.assertEqual(
            time_period.delay_to_next_minutes_period(45, period), 15)
        self.assertEqual(
            time_period.delay_to_next_minutes_period(46, period), 14)
        self.assertEqual(
            time_period.delay_to_next_minutes_period(59, period), 1)
        self.assertEqual(
            time_period.delay_to_next_minutes_period(60, period), 15)
        self.assertEqual(
            time_period.delay_to_next_minutes_period(61, period), 14)
        self.assertEqual(
            time_period.delay_to_next_minutes_period(292, period), 8)

        return

    def test_add_remove_cb(self):

        obj = time_period.TimePeriods()

        # print(obj.per_minute) return like "Period:min cb:0 skewed:0"
        # print(obj.per_hour)
        # print(obj.per_day)
        # print(obj.per_month)
        # print(obj.per_year)

        self.assertEqual(obj.per_minute.get_name(), 'min')
        self.assertEqual(obj.per_hour.get_name(), 'hr')
        self.assertEqual(obj.per_day.get_name(), 'day')
        self.assertEqual(obj.per_month.get_name(), 'mon')
        self.assertEqual(obj.per_year.get_name(), 'yr')

        def cb_simple(x):
            print("CB:{0}".format(x))

        def cb_simple_2(x):
            print("CB:{0}".format(x))

        # some simple 1 cb in main list
        self.assertEqual(len(obj.per_minute.cb_list), 0)
        obj.per_minute.add_callback(cb_simple)
        self.assertEqual(len(obj.per_minute.cb_list), 1)
        obj.per_minute.remove_callback(cb_simple)
        self.assertEqual(len(obj.per_minute.cb_list), 0)

        # some simple 2 cb in main list
        obj.per_minute.add_callback(cb_simple_2)
        self.assertEqual(len(obj.per_minute.cb_list), 1)
        self.assertEqual(len(obj.per_minute.cb_list_skewed), 0)
        obj.per_minute.remove_callback(cb_simple)
        self.assertEqual(len(obj.per_minute.cb_list), 1)
        self.assertEqual(len(obj.per_minute.cb_list_skewed), 0)
        obj.per_minute.add_callback(cb_simple)
        self.assertEqual(len(obj.per_minute.cb_list), 2)
        self.assertEqual(len(obj.per_minute.cb_list_skewed), 0)
        obj.per_minute.remove_callback(cb_simple)
        self.assertEqual(len(obj.per_minute.cb_list), 1)
        self.assertEqual(len(obj.per_minute.cb_list_skewed), 0)
        obj.per_minute.remove_callback(cb_simple_2)
        self.assertEqual(len(obj.per_minute.cb_list), 0)
        self.assertEqual(len(obj.per_minute.cb_list_skewed), 0)

        # add to both lists
        obj.per_minute.add_callback(cb_simple_2, skewed=True)
        self.assertEqual(len(obj.per_minute.cb_list), 0)
        self.assertEqual(len(obj.per_minute.cb_list_skewed), 1)
        obj.per_minute.remove_callback(cb_simple)
        self.assertEqual(len(obj.per_minute.cb_list), 0)
        self.assertEqual(len(obj.per_minute.cb_list_skewed), 1)
        obj.per_minute.add_callback(cb_simple)
        self.assertEqual(len(obj.per_minute.cb_list), 1)
        self.assertEqual(len(obj.per_minute.cb_list_skewed), 1)
        obj.per_minute.remove_callback(cb_simple)
        self.assertEqual(len(obj.per_minute.cb_list), 0)
        self.assertEqual(len(obj.per_minute.cb_list_skewed), 1)
        obj.per_minute.remove_callback(cb_simple_2)
        self.assertEqual(len(obj.per_minute.cb_list), 0)
        self.assertEqual(len(obj.per_minute.cb_list_skewed), 0)

        return


def simple_check():
    """A sanity-check routine; not a test"""

    for n in range(1, 61):
        print("%02d = %f" % (n, 60.0/n))

    for n in range(1, 25):
        print("%02d = %f" % (n, 24.0/n))

    return


if __name__ == '__main__':

    # simple_check()

    unittest.main()
