# Test the MODBUS ASCII module

import unittest

import cp_lib.modbus.transaction as ia_trans
import cp_lib.modbus.modbus_asc as mbus_asc
from cp_lib.modbus.transaction_modbus import ModbusTransaction, \
    ModbusBadForm, ModbusBadChecksum


class TestModbusAsc(unittest.TestCase):

    def test_code_ascii(self):

        tests = [
            {'src': b'\x01\x03', 'exp': 0xFC},
            {'src': b'\x01\x03\x00', 'exp': 0xFC},
            {'src': b'\x01\x03\x00\x00', 'exp': 0xFC},
            {'src': b'\x01\x03\x00\x00\x00', 'exp': 0xFC},
            {'src': b'\x01\x03\x00\x00\x00\x0A', 'exp': 0xF2},

            {'src': b'', 'exp': ModbusBadForm},
            {'src': b'\x01', 'exp': ModbusBadForm},
            {'src': '\x01\x03\x00\x00\x00\x0A', 'exp': TypeError},
        ]

        for test in tests:
            # loop through all tests

            # print("test:{}".format(test))

            if test['exp'] == TypeError:
                with self.assertRaises(TypeError):
                    mbus_asc.calc_checksum(test['src'])

            elif test['exp'] == ModbusBadForm:
                with self.assertRaises(ModbusBadForm):
                    mbus_asc.calc_checksum(test['src'])

            else:
                result = mbus_asc.calc_checksum(test['src'])
                self.assertEqual(result, test['exp'])

        return

    def test_encode_to_wire(self):

        tests = [
            {'src': b'\x01\x03\x00\x00\x00\x0A',
             'exp': b':01030000000AF2\r\n'},
            {'src': b'\x01\x03\x00\x00\x00', 'exp': b':0103000000FC\r\n'},
            {'src': b'\x01\x03\x00\x00', 'exp': b':01030000FC\r\n'},
            {'src': b'\x01\x03\x00', 'exp': b':010300FC\r\n'},
            {'src': b'\x01\x03', 'exp': b':0103FC\r\n'},

            {'src': b'\x01', 'exp': ModbusBadForm},
            {'src': b'', 'exp': ModbusBadForm},

            {'src': '\x01\x03\x00\x00\x00\x0A', 'exp': TypeError},
            {'src': None, 'exp': TypeError},
            {'src': [1, 3, 0, 0, 0, 0x0A], 'exp': TypeError},
        ]

        for test in tests:
            # loop through all tests

            # print("test:{}".format(test))

            if test['exp'] == ModbusBadForm:
                with self.assertRaises(ModbusBadForm):
                    mbus_asc.encode_to_wire(test['src'])

            elif test['exp'] == TypeError:
                with self.assertRaises(TypeError):
                    mbus_asc.encode_to_wire(test['src'])

            else:
                result = mbus_asc.encode_to_wire(test['src'])
                self.assertEqual(result, test['exp'])

        return

    def test_decode_from_wire(self):

        # _estimate_length_request

        tests = [
            {'src': b':01030000000AF2\r\n',
             'exp': b'\x01\x03\x00\x00\x00\x0A'},
            {'src': b':0103000000FC\r\n', 'exp': b'\x01\x03\x00\x00\x00'},
            {'src': b':01030000FC\r\n', 'exp': b'\x01\x03\x00\x00'},
            {'src': b':010300FC\r\n', 'exp': b'\x01\x03\x00'},
            {'src': b':0103FC\r\n', 'exp': b'\x01\x03'},

            # fiddle with the EOL - '\r\n' is SPEC, but allow basic combos
            {'src': b':01030000000AF2\r',
             'exp': b'\x01\x03\x00\x00\x00\x0A'},
            {'src': b':01030000000AF2\n',
             'exp': b'\x01\x03\x00\x00\x00\x0A'},
            {'src': b':01030000000AF2',
             'exp': b'\x01\x03\x00\x00\x00\x0A'},

            # bad CRC
            {'src': b':01030000000AFF\r\n',
             'exp': ModbusBadChecksum},

            # bad start
            {'src': b'01030000000AF2\r\n',
             'exp': ModbusBadForm},

            # an odd number of bytes
            {'src': b':0103000000AF2\r\n',
             'exp': ModbusBadForm},

            # non-hex bytes
            {'src': b':0103JAN0000AF2\r\n',
             'exp': ModbusBadForm},

            # bad types
            {'src': ':01030000000AF2\r\n', 'exp': TypeError},
            {'src': 10, 'exp': TypeError},
            {'src': None, 'exp': TypeError},

        ]

        for test in tests:
            # loop through all tests

            # print("test:{}".format(test))

            if test['exp'] == ModbusBadForm:
                with self.assertRaises(ModbusBadForm):
                    mbus_asc.decode_from_wire(test['src'])

            elif test['exp'] == ModbusBadChecksum:
                with self.assertRaises(ModbusBadChecksum):
                    mbus_asc.decode_from_wire(test['src'])

            elif test['exp'] == TypeError:
                with self.assertRaises(TypeError):
                    mbus_asc.decode_from_wire(test['src'])

            else:
                result = mbus_asc.decode_from_wire(test['src'])
                self.assertEqual(result, test['exp'])

        return

    def test_request(self):

        tests = [
            {'src': b':01030000000AF2\r\n',
             'raw': b'\x01\x03\x00\x00\x00\x0A',
             'exp': b':01030000000AF2\r\n'},
        ]

        obj = ModbusTransaction()

        for test in tests:
            # loop through all tests

            # print("test:{}".format(test))

            msg = test['raw'][1:]

            result = obj.set_request(test['src'], ia_trans.IA_PROTOCOL_MBASC)
            # print("obj pst:{}".format(obj.attrib))
            self.assertTrue(result)
            self.assertEqual(obj[obj.KEY_REQ_RAW], test['src'])
            self.assertEqual(obj[obj.KEY_REQ_PROTOCOL],
                             ia_trans.IA_PROTOCOL_MBASC)
            self.assertNotIn(obj.KEY_SRC_ID, obj.attrib)
            self.assertEqual(obj[obj.KEY_REQ], msg)

            result = obj.get_request()
            self.assertEqual(result, test['exp'])

        return

    def test_end_of_message(self):

        tests = [
            {'src': b':01030000000AF2\r\n',
             'result': [b':01030000000AF2\r\n'], 'extra': None},

            {'src': b'',
             'result': None, 'extra': None},
            {'src': b':',
             'result': [], 'extra': b':'},
            {'src': b':0',
             'result': [], 'extra': b':0'},
            {'src': b':01',
             'result': [], 'extra': b':01'},
            {'src': b':010300',
             'result': [], 'extra': b':010300'},
            {'src': b':01030000000',
             'result': [], 'extra': b':01030000000'},
            {'src': b':01030000000AF',
             'result': [], 'extra': b':01030000000AF'},
            {'src': b':01030000000AF2',
             'result': [], 'extra': b':01030000000AF2'},
            {'src': b':01030000000AF2\r',
             'result': [], 'extra': b':01030000000AF2\r'},

            {'src': b':01030000000AF2\r\n:01030000000AF2',
             'result': [b':01030000000AF2\r\n'],
             'extra': b':01030000000AF2'},
            {'src': b':01030000000AF2\r\n:01030000000AF2\r',
             'result': [b':01030000000AF2\r\n'],
             'extra': b':01030000000AF2\r'},
            {'src': b':01030000000AF2\r\n:01030000000AF2\r\n',
             'result': [b':01030000000AF2\r\n', b':01030000000AF2\r\n'],
             'extra': None},
        ]

        for test in tests:
            # loop through all tests

            # print("test:{}".format(test))

            result, extra = mbus_asc.test_end_of_message(test['src'])
            self.assertEqual(result, test['result'])
            self.assertEqual(extra, test['extra'])

        return


if __name__ == '__main__':
    unittest.main()
