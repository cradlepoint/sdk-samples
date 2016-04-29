# Test the PARSE DATA module

import unittest

from cp_lib.unquote_string import unquote_string


class TestUnquoteString(unittest.TestCase):

    def test_isolate_numeric(self):

        tests = [
            {'src': "Hello", 'exp': "Hello"},
            {'src': " Hello", 'exp': " Hello"},
            {'src': " Hello ", 'exp': " Hello "},
            {'src': "'Hello", 'exp': "'Hello"},
            {'src': "'Hello'", 'exp': "Hello"},
            {'src': '"Hello"', 'exp': 'Hello'},
            {'src': '"Hello', 'exp': '"Hello'},

            {'src': " 'Hello'", 'exp': "Hello"},
            {'src': "'Hello' ", 'exp': "Hello"},
            {'src': " 'Hello' ", 'exp': "Hello"},
            {'src': ' "Hello"', 'exp': 'Hello'},
            {'src': '"Hello" ', 'exp': 'Hello'},
            {'src': ' "Hello" ', 'exp': 'Hello'},

            {'src': "", 'exp': ""},
            {'src': " ", 'exp': " "},
            {'src': "'", 'exp': "'"},
            {'src': " '", 'exp': " '"},
            {'src': " '' ", 'exp': ""},
            {'src': None, 'exp': None},
            {'src': 10, 'exp': 10},
            {'src': 10.0, 'exp': 10.0},
        ]

        for test in tests:
            result = unquote_string(test['src'])
            self.assertEqual(result, test['exp'])

        # with self.assertRaises(ValueError):
        #     # value must have number str
        #     isolate_numeric_from_string("")
        #     isolate_numeric_from_string(" \n")
        #     isolate_numeric_from_string("hello")

        return

if __name__ == '__main__':
    unittest.main()
