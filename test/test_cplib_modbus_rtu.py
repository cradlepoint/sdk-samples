# Test the MODBUS RTU module

import unittest

import cp_lib.modbus.transaction as ia_trans
import cp_lib.modbus.modbus_rtu as mbus_rtu
from cp_lib.modbus.transaction_modbus import ModbusTransaction, \
    ModbusBadForm, ModbusBadChecksum


class TestModbusRtu(unittest.TestCase):

    def test_checksum(self):

        tests = [
            {'src': b"\xEA\x03\x00\x00\x00\x64", 'exp': 0x3A53},
            {'src': b"\x4b\x03\x00\x2c\x00\x37", 'exp': 0xbfcb},
            {'src': b"\x0d\x01\x00\x62\x00\x33", 'exp': 0x0ddd},

            {'src': b'', 'exp': ModbusBadForm},
            {'src': b'\x01', 'exp': ModbusBadForm},
            {'src': '\x01\x03\x00\x00\x00\x0A', 'exp': TypeError},
        ]

        for test in tests:
            # loop through all tests

            # print("test:{}".format(test))

            if test['exp'] == TypeError:
                with self.assertRaises(TypeError):
                    mbus_rtu.calc_checksum(test['src'])

            elif test['exp'] == ModbusBadForm:
                with self.assertRaises(ModbusBadForm):
                    mbus_rtu.calc_checksum(test['src'])

            else:
                result = mbus_rtu.calc_checksum(test['src'])
                self.assertEqual(result, test['exp'])

        return

    def test_encode_to_wire(self):

        tests = [
            {'src': b'\x01\x03\x00\x00\x00\x0A',
             'exp': b'\x01\x03\x00\x00\x00\x0A\xC5\xCD'},
            {'src': b'\x01\x03\x00\x00\x00',
             'exp': b'\x01\x03\x00\x00\x00\x19\x84'},

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
                    mbus_rtu.encode_to_wire(test['src'])

            elif test['exp'] == TypeError:
                with self.assertRaises(TypeError):
                    mbus_rtu.encode_to_wire(test['src'])

            else:
                result = mbus_rtu.encode_to_wire(test['src'])
                self.assertEqual(result, test['exp'])

        return

    def test_decode_from_wire(self):

        tests = [
            {'exp': b'\x01\x03\x00\x00\x00\x0A',
             'src': b'\x01\x03\x00\x00\x00\x0A\xC5\xCD'},
            {'exp': b'\x01\x03\x00\x00\x00',
             'src': b'\x01\x03\x00\x00\x00\x19\x84'},

            # bad CRC
            {'src': b'\x01\x03\x00\x00\x00\x0A\xC5\x00',
             'exp': ModbusBadChecksum},

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
                    mbus_rtu.decode_from_wire(test['src'])

            elif test['exp'] == ModbusBadChecksum:
                with self.assertRaises(ModbusBadChecksum):
                    mbus_rtu.decode_from_wire(test['src'])

            elif test['exp'] == TypeError:
                with self.assertRaises(TypeError):
                    mbus_rtu.decode_from_wire(test['src'])

            else:
                result = mbus_rtu.decode_from_wire(test['src'])
                self.assertEqual(result, test['exp'])

        return

    def test_request(self):

        tests = [
            {'src': b'\x01\x03\x00\x00\x00\x0A\xC5\xCD',
             'raw': b'\x01\x03\x00\x00\x00\x0A',
             'exp': b'\x01\x03\x00\x00\x00\x0A\xC5\xCD'},
        ]

        obj = ModbusTransaction()

        for test in tests:
            # loop through all tests

            # print("test:{}".format(test))

            # this won't have the UID in first place - moved to [KEY_SRC_ID]
            msg = test['raw'][1:]

            result = obj.set_request(test['src'], ia_trans.IA_PROTOCOL_MBRTU)
            # print("obj pst:{}".format(obj.attrib))
            self.assertTrue(result)
            self.assertEqual(obj[obj.KEY_REQ_RAW], test['src'])
            self.assertEqual(obj[obj.KEY_REQ_PROTOCOL],
                             ia_trans.IA_PROTOCOL_MBRTU)
            self.assertNotIn(obj.KEY_SRC_ID, obj.attrib)
            self.assertEqual(obj[obj.KEY_REQ], msg)

            result = obj.get_request()
            self.assertEqual(result, test['exp'])

        return

    def test_end_of_message_request(self):

        tests = [
            # the common functions
            {'src': b'\x01\x01\x00\x00\x00\x0A\xAA\xBB',
             'result': [b'\x01\x01\x00\x00\x00\x0A\xAA\xBB'], 'extra': None},
            {'src': b'\x01\x02\x00\x00\x00\x0A\xAA\xBB',
             'result': [b'\x01\x02\x00\x00\x00\x0A\xAA\xBB'], 'extra': None},
            {'src': b'\x01\x03\x00\x00\x00\x0A\xAA\xBB',
             'result': [b'\x01\x03\x00\x00\x00\x0A\xAA\xBB'], 'extra': None},
            {'src': b'\x01\x04\x00\x00\x00\x0A\xAA\xBB',
             'result': [b'\x01\x04\x00\x00\x00\x0A\xAA\xBB'], 'extra': None},
            {'src': b'\x01\x05\x00\x00\x00\x0A\xAA\xBB',
             'result': [b'\x01\x05\x00\x00\x00\x0A\xAA\xBB'], 'extra': None},
            {'src': b'\x01\x06\x00\x00\x00\x0A\xAA\xBB',
             'result': [b'\x01\x06\x00\x00\x00\x0A\xAA\xBB'], 'extra': None},
            {'src': b'\x01\x0F\x00\x00\x00\x0A\x02\xAA\xBB\xCC\xDD',
             'result': [b'\x01\x0F\x00\x00\x00\x0A\x02\xAA\xBB\xCC\xDD'],
             'extra': None},
            {'src': b'\x01\x10\x00\x00\x00\x0A\x02\xAA\xBB\xCC\xDD',
             'result': [b'\x01\x10\x00\x00\x00\x0A\x02\xAA\xBB\xCC\xDD'],
             'extra': None},

            # build up
            {'src': b'\x01',
             'result': [], 'extra': b'\x01'},
            {'src': b'\x01\x01',
             'result': [], 'extra': b'\x01\x01'},
            {'src': b'\x01\x01\x00',
             'result': [], 'extra': b'\x01\x01\x00'},
            {'src': b'\x01\x01\x00\x00',
             'result': [], 'extra': b'\x01\x01\x00\x00'},
            {'src': b'\x01\x01\x00\x00\x00',
             'result': [], 'extra': b'\x01\x01\x00\x00\x00'},
            {'src': b'\x01\x01\x00\x00\x00\x0A',
             'result': [], 'extra': b'\x01\x01\x00\x00\x00\x0A'},
            {'src': b'\x01\x01\x00\x00\x00\x0A\xAA',
             'result': [], 'extra': b'\x01\x01\x00\x00\x00\x0A\xAA'},

            {'src': b'\x01', 'result': [], 'extra': b'\x01'},
            {'src': b'\x01\x10', 'result': [], 'extra': b'\x01\x10'},
            {'src': b'\x01\x10\x00', 'result': [], 'extra': b'\x01\x10\x00'},
            {'src': b'\x01\x10\x00\x00',
             'result': [], 'extra': b'\x01\x10\x00\x00'},
            {'src': b'\x01\x10\x00\x00\x00',
             'result': [], 'extra': b'\x01\x10\x00\x00\x00'},
            {'src': b'\x01\x10\x00\x00\x00\x0A',
             'result': [], 'extra': b'\x01\x10\x00\x00\x00\x0A'},
            {'src': b'\x01\x10\x00\x00\x00\x0A\x02',
             'result': [], 'extra': b'\x01\x10\x00\x00\x00\x0A\x02'},
            {'src': b'\x01\x10\x00\x00\x00\x0A\x02\xAA',
             'result': [], 'extra': b'\x01\x10\x00\x00\x00\x0A\x02\xAA'},
            {'src': b'\x01\x10\x00\x00\x00\x0A\x02\xAA\xBB',
             'result': [], 'extra': b'\x01\x10\x00\x00\x00\x0A\x02\xAA\xBB'},
            {'src': b'\x01\x10\x00\x00\x00\x0A\x02\xAA\xBB\xCC',
             'result': [],
             'extra': b'\x01\x10\x00\x00\x00\x0A\x02\xAA\xBB\xCC'},

            # multiple lines
            {'src': b'\x01\x01\x00\x00\x00\x0A\xAA\xBB' +
                    b'\x01\x01\x00\x00\x00\x0A\xAA\xBB',
             'result': [b'\x01\x01\x00\x00\x00\x0A\xAA\xBB',
                        b'\x01\x01\x00\x00\x00\x0A\xAA\xBB'], 'extra': None},
            {'src': b'\x01\x01\x00\x00\x00\x0A\xAA\xBB' +
                    b'\x01\x01\x00\x00\x00\x0A\xAA\xBB\x05',
             'result': [b'\x01\x01\x00\x00\x00\x0A\xAA\xBB',
                        b'\x01\x01\x00\x00\x00\x0A\xAA\xBB'],
             'extra': b'\x05'},
            {'src': b'\x01\x01\x00\x00\x00\x0A\xAA\xBB' +
                    b'\x01\x01\x00\x00\x00\x0A\xAA',
             'result': [b'\x01\x01\x00\x00\x00\x0A\xAA\xBB'],
             'extra': b'\x01\x01\x00\x00\x00\x0A\xAA'},
            {'src': b'\x01\x01\x00\x00\x00\x0A\xAA\xBB' +
                    b'\x01\x01',
             'result': [b'\x01\x01\x00\x00\x00\x0A\xAA\xBB'],
             'extra': b'\x01\x01'},
            {'src': b'\x01\x01\x00\x00\x00\x0A\xAA\xBB' +
                    b'\x01',
             'result': [b'\x01\x01\x00\x00\x00\x0A\xAA\xBB'],
             'extra': b'\x01'},

            # unknown functions
            {'src': b'\x01\x64\x00\xAA\xBB',
             'result': [b'\x01\x64\x00\xAA\xBB'], 'extra': None},

        ]

        for test in tests:
            # loop through all tests

            # print("test:{}".format(test))

            result, extra = mbus_rtu.test_end_of_message(test['src'],
                                                         is_request=True)
            self.assertEqual(result, test['result'])
            self.assertEqual(extra, test['extra'])

        return


if __name__ == '__main__':
    unittest.main()
