# Test the MODBUS transaction module

import unittest

from cp_lib.modbus.transaction_modbus import ModbusTransaction


class TestModbusTrans(unittest.TestCase):

    def test_estimate_length_request(self):

        # _estimate_length_request

        tests = [
            {'src': b'\x01\x01\x00\x01\x00\x0A', 'exp': 6},
            {'src': b'\x01\x01\x00\x01\x00\x0A\x44\x2A', 'exp': 6},
            {'src': b'\x01\x02\x00\x01\x00\x0A', 'exp': 6},
            {'src': b'\x01\x03\x00\x01\x00\x0A', 'exp': 6},
            {'src': b'\x01\x04\x00\x01\x00\x0A', 'exp': 6},
            {'src': b'\x01\x05\x00\x01\x00\x0A', 'exp': 6},
            {'src': b'\x01\x06\x00\x01\x00\x0A', 'exp': 6},
            {'src': b'\x01\x0F\x02\x00\x01', 'exp': 5},
            {'src': b'\x01\x10\x02\x00\x01', 'exp': 5},

            {'src': '\x01\x01\x00\x01\x00\x0A', 'exp': 6},

            {'src': b'\x01\x00\x02\x00\x01', 'exp': ValueError},
        ]

        obj = ModbusTransaction()

        for test in tests:
            # loop through all tests

            if test['exp'] == ValueError:
                with self.assertRaises(ValueError):
                    obj._estimate_length_request(test['src'])

                pass
            else:
                result = obj._estimate_length_request(test['src'])
                self.assertEqual(result, test['exp'])

        return

#

    def test_parse_rtu(self):

        # _estimate_length_request

        tests = [
            {'src': b'\x01\x01\x00\x01\x00\x0A', 'exp': 6},
            {'src': b'\x01\x01\x00\x01\x00\x0A\x44\x2A', 'exp': 6},
            {'src': b'\x01\x02\x00\x01\x00\x0A', 'exp': 6},
            {'src': b'\x01\x03\x00\x01\x00\x0A', 'exp': 6},
            {'src': b'\x01\x04\x00\x01\x00\x0A', 'exp': 6},
            {'src': b'\x01\x05\x00\x01\x00\x0A', 'exp': 6},
            {'src': b'\x01\x06\x00\x01\x00\x0A', 'exp': 6},
            {'src': b'\x01\x0F\x02\x00\x01', 'exp': 5},
            {'src': b'\x01\x10\x02\x00\x01', 'exp': 5},

            {'src': '\x01\x01\x00\x01\x00\x0A', 'exp': 6},

            {'src': b'\x01\x00\x02\x00\x01', 'exp': ValueError},
        ]

        obj = ModbusTransaction()

        for test in tests:
            # loop through all tests

            if test['exp'] == ValueError:
                with self.assertRaises(ValueError):
                    obj._parse_rtu(test['src'])

                pass
            else:
                obj._parse_rtu(test['src'])
                # self.assertEqual(result, test['exp'])
                self.assertEqual(obj['cooked_protocol'],
                                 obj.IA_PROTOCOL_MBRTU)

        return

    def test_code_ascii(self):

        # _estimate_length_request

        tests = [
            {'src': b':01010001000A66\r\n', 'exp': 6},
        ]

        obj = ModbusTransaction()

        for test in tests:
            # loop through all tests

            if test['exp'] == ValueError:
                with self.assertRaises(ValueError):
                    obj._parse_rtu(test['src'])

                pass
            else:
                obj._parse_rtu(test['src'])
                self.assertEqual(result, test['exp'])
                self.assertEqual(obj['cooked_protocol'],
                                 obj.IA_PROTOCOL_MBRTU)

        return

if __name__ == '__main__':
    unittest.main()
