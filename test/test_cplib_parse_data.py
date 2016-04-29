# Test the PARSE DATA module

import unittest

from cp_lib.parse_data import isolate_numeric_from_string, parse_float, \
    parse_float_string, parse_integer, \
    parse_integer_string, parse_boolean, parse_none


class TestParseData(unittest.TestCase):

    def test_isolate_numeric(self):

        self.assertEqual(isolate_numeric_from_string(" 0"), "0")
        self.assertEqual(isolate_numeric_from_string("hello0"), "0")
        self.assertEqual(isolate_numeric_from_string(" 99"), "99")
        self.assertEqual(isolate_numeric_from_string(" -99rate"), "-99")
        self.assertEqual(isolate_numeric_from_string(" 0.0 "), "0.0")
        self.assertEqual(isolate_numeric_from_string(" 99.9% "), "99.9")
        self.assertEqual(isolate_numeric_from_string(" -99.9 \n"), "-99.9")

        self.assertEqual(isolate_numeric_from_string("' 0.0"), "0.0")
        self.assertEqual(isolate_numeric_from_string("\"99.9"), "99.9")
        self.assertEqual(isolate_numeric_from_string("[-99.9"), "-99.9")
        self.assertEqual(isolate_numeric_from_string("(123,"), "123")
        self.assertEqual(isolate_numeric_from_string("' 0.0'"), "0.0")
        self.assertEqual(isolate_numeric_from_string("\"99.9\""), "99.9")
        self.assertEqual(isolate_numeric_from_string("[-99.9]"), "-99.9")
        self.assertEqual(isolate_numeric_from_string("(123)"), "123")

        # only the first numeric sequence returned!
        self.assertEqual(isolate_numeric_from_string("1, 2, 3"), "1")
        self.assertEqual(isolate_numeric_from_string("rate = 123 seconds"),
                         "123")
        self.assertEqual(isolate_numeric_from_string("rate = 123 and 99"),
                         "123")

        with self.assertRaises(TypeError):
            # value must be str
            isolate_numeric_from_string(None)
            isolate_numeric_from_string(99)
            isolate_numeric_from_string(99.9)

        with self.assertRaises(ValueError):
            # value must have number str
            isolate_numeric_from_string("")
            isolate_numeric_from_string(" \n")
            isolate_numeric_from_string("hello")

        return

    def test_parse_integer(self):

        self.assertEqual(parse_integer(None, none_is_zero=False), None)
        self.assertEqual(parse_integer(0, none_is_zero=False), 0)
        self.assertEqual(parse_integer(99, none_is_zero=False), 99)
        self.assertEqual(parse_integer(-99, none_is_zero=False), -99)
        self.assertEqual(parse_integer(0.0, none_is_zero=False), 0.0)
        self.assertEqual(parse_integer(99.0, none_is_zero=False), 99.0)
        self.assertEqual(parse_integer(-99.0, none_is_zero=False), -99.0)
        self.assertEqual(parse_integer("0", none_is_zero=False), 0)
        self.assertEqual(parse_integer("99", none_is_zero=False), 99)
        self.assertEqual(parse_integer("-99", none_is_zero=False), -99)

        self.assertEqual(parse_integer(None, none_is_zero=True), 0)

        self.assertEqual(parse_integer(" 0", none_is_zero=False), 0)
        self.assertEqual(parse_integer(" 99", none_is_zero=False), 99)
        self.assertEqual(parse_integer(" -99", none_is_zero=False), -99)
        self.assertEqual(parse_integer(" 0 ", none_is_zero=False), 0)
        self.assertEqual(parse_integer(" 99 ", none_is_zero=False), 99)
        self.assertEqual(parse_integer(" -99 ", none_is_zero=False), -99)
        self.assertEqual(parse_integer(" 0\n", none_is_zero=False), 0)
        self.assertEqual(parse_integer(" 99\n", none_is_zero=False), 99)
        self.assertEqual(parse_integer(" -99\n", none_is_zero=False), -99)

        with self.assertRaises(ValueError):
            parse_integer("\"99\"")
            parse_integer("[99]")

        return

    def test_parse_integer_string(self):

        self.assertEqual(parse_integer_string("0"), 0)
        self.assertEqual(parse_integer_string("99"), 99)
        self.assertEqual(parse_integer_string("-99"), -99)
        self.assertEqual(parse_integer_string("0.0"), 0)
        self.assertEqual(parse_integer_string("99.2"), 99)
        self.assertEqual(parse_integer_string("-99.8"), -100)
        self.assertEqual(parse_integer_string(" 0.0"), 0)
        self.assertEqual(parse_integer_string(" 99.0\n"), 99)
        self.assertEqual(parse_integer_string("a -99.0"), -99)
        self.assertEqual(parse_integer_string("\"0.0\""), 0)
        self.assertEqual(parse_integer_string("[99.0]"), 99)
        self.assertEqual(parse_integer_string("(-99.0)"), -99)

        with self.assertRaises(TypeError):
            parse_integer_string(None)
            parse_integer_string(99)

        return

    def test_parse_float(self):

        self.assertEqual(parse_float(None, none_is_zero=True), 0.0)
        self.assertEqual(parse_float(None, none_is_zero=False), None)

        self.assertEqual(parse_float(99), 99.0)
        self.assertEqual(parse_float(-99), -99.0)
        self.assertEqual(parse_float(0.0), 0.0)
        self.assertEqual(parse_float(99.0), 99)
        self.assertEqual(parse_float(-99.0), -99)
        self.assertEqual(parse_float("0"), 0.0)
        self.assertEqual(parse_float("99"), 99.0)
        self.assertEqual(parse_float("-99"), -99.0)
        self.assertEqual(parse_float("0.0"), 0.0)
        self.assertEqual(parse_float("99.0"), 99.0)
        self.assertEqual(parse_float("-99.0"), -99.0)

        return

    def test_parse_float_string(self):

        self.assertEqual(parse_float_string("0"), 0.0)
        self.assertEqual(parse_float_string("99"), 99.0)
        self.assertEqual(parse_float_string("-99"), -99.0)
        self.assertEqual(parse_float_string("0.0"), 0.0)
        self.assertEqual(parse_float_string("99.0"), 99.0)
        self.assertEqual(parse_float_string("-99.0"), -99.0)
        self.assertEqual(parse_float_string(" 0.0"), 0.0)
        self.assertEqual(parse_float_string(" 99.0"), 99.0)
        self.assertEqual(parse_float_string("a -99.0"), -99.0)
        self.assertEqual(parse_float_string("\"0.0\""), 0.0)
        self.assertEqual(parse_float_string("[99.0]"), 99.0)
        self.assertEqual(parse_float_string("(-99.0)"), -99.0)

        with self.assertRaises(TypeError):
            parse_float_string(None)
            parse_float_string(99)
            parse_float_string(99.00)

    def test_parse_boolean(self):

        self.assertEqual(parse_boolean(None, none_is_false=True), False)

        # typical bool(value)
        self.assertEqual(parse_boolean(-99), True)
        self.assertEqual(parse_boolean(-1), True)
        self.assertEqual(parse_boolean(0), False)
        self.assertEqual(parse_boolean(1), True)
        self.assertEqual(parse_boolean(99), True)

        # handle str
        self.assertEqual(parse_boolean("0"), False)
        self.assertEqual(parse_boolean(" 0 "), False)
        self.assertEqual(parse_boolean("1"), True)
        self.assertEqual(parse_boolean(" 1 "), True)

        self.assertEqual(parse_boolean(" F "), False)
        self.assertEqual(parse_boolean(" f "), False)
        self.assertEqual(parse_boolean("t"), True)
        self.assertEqual(parse_boolean(" T"), True)

        self.assertEqual(parse_boolean("FALSE"), False)
        self.assertEqual(parse_boolean("False"), False)
        self.assertEqual(parse_boolean("false"), False)
        self.assertEqual(parse_boolean("TRUE"), True)
        self.assertEqual(parse_boolean("True"), True)
        self.assertEqual(parse_boolean("true"), True)

        self.assertEqual(parse_boolean("OFF"), False)
        self.assertEqual(parse_boolean("Off"), False)
        self.assertEqual(parse_boolean("off"), False)
        self.assertEqual(parse_boolean("ON"), True)
        self.assertEqual(parse_boolean("On"), True)
        self.assertEqual(parse_boolean("on"), True)

        self.assertEqual(parse_boolean("disable"), False)
        self.assertEqual(parse_boolean("enable"), True)

        # handle bytes
        self.assertEqual(parse_boolean(b"0"), False)
        self.assertEqual(parse_boolean(b" 0 "), False)
        self.assertEqual(parse_boolean(b"1"), True)
        self.assertEqual(parse_boolean(b" 1 "), True)

        self.assertEqual(parse_boolean(b" F "), False)
        self.assertEqual(parse_boolean(b" f "), False)
        self.assertEqual(parse_boolean(b"t"), True)
        self.assertEqual(parse_boolean(b" T"), True)

        self.assertEqual(parse_boolean(b"FALSE"), False)
        self.assertEqual(parse_boolean(b"False"), False)
        self.assertEqual(parse_boolean(b"false"), False)
        self.assertEqual(parse_boolean(b"TRUE"), True)
        self.assertEqual(parse_boolean(b"True"), True)
        self.assertEqual(parse_boolean(b"true"), True)

        self.assertEqual(parse_boolean(b"OFF"), False)
        self.assertEqual(parse_boolean(b"Off"), False)
        self.assertEqual(parse_boolean(b"off"), False)
        self.assertEqual(parse_boolean(b"ON"), True)
        self.assertEqual(parse_boolean(b"On"), True)
        self.assertEqual(parse_boolean(b"on"), True)

        self.assertEqual(parse_boolean(b"disable"), False)
        self.assertEqual(parse_boolean(b"enable"), True)

        with self.assertRaises(ValueError):
            parse_boolean(None, none_is_false=False)
            parse_boolean("happy")
            parse_boolean([1, 2, 3])

        return

    def test_parse_none(self):

        self.assertEqual(parse_none(None), None)

        self.assertEqual(parse_none(""), None)
        self.assertEqual(parse_none("NONE"), None)
        self.assertEqual(parse_none("None"), None)
        self.assertEqual(parse_none("none"), None)
        self.assertEqual(parse_none("NULL"), None)
        self.assertEqual(parse_none("Null"), None)
        self.assertEqual(parse_none("null"), None)
        self.assertEqual(parse_none("  none"), None)
        self.assertEqual(parse_none("\'none\'"), None)

        self.assertEqual(parse_none(b""), None)
        self.assertEqual(parse_none(b"None"), None)
        self.assertEqual(parse_none(b"Null"), None)

        with self.assertRaises(ValueError):
            parse_none(10)
            parse_none("happy")
            parse_none([1, 2, 3])

        return

if __name__ == '__main__':
    unittest.main()
