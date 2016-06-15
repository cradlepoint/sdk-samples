# Test the MODBUS TCP module

import unittest

import cp_lib.modbus.transaction as ia_trans
import cp_lib.modbus.modbus_tcp as mbus_tcp
from cp_lib.modbus.transaction_modbus import ModbusTransaction


class TestModbusTcp(unittest.TestCase):

    def test_request(self):

        tests = [
            {'src': b'\xAB\xCD\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A',
             'seq': b'\xAB\xCD',
             'raw': b'\x01\x03\x00\x00\x00\x0A'},
        ]

        obj = ModbusTransaction()

        for test in tests:
            # loop through all tests

            # print("test:{}".format(test))

            # this won't have the UID in first place - moved to [KEY_SRC_ID]
            msg = test['raw'][1:]

            result = obj.set_request(test['src'], ia_trans.IA_PROTOCOL_MBTCP)
            # print("obj pst:{}".format(obj.attrib))
            self.assertTrue(result)
            self.assertEqual(obj[obj.KEY_REQ_RAW], test['src'])
            self.assertEqual(obj[obj.KEY_REQ_PROTOCOL],
                             ia_trans.IA_PROTOCOL_MBTCP)
            self.assertNotIn(obj.KEY_SRC_ID, obj.attrib)
            self.assertEqual(obj[obj.KEY_REQ], msg)
            self.assertEqual(obj[obj.KEY_SRC_SEQ], test['seq'])

            result = obj.get_request()
            self.assertEqual(result, test['src'])

        return

    def test_sequence_number(self):

        tests = [
            {'src': b'\xAB\xCD\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A',
             'seq': b'\xAB\xCD',
             'raw': b'\x01\x03\x00\x00\x00\x0A'},
        ]

        obj = ModbusTransaction()

        source = b'\xAB\xCD\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A'
        expect = source
        obj.set_request(source, ia_trans.IA_PROTOCOL_MBTCP)
        result = obj.get_request()
        self.assertEqual(result, expect)

        # swap in a new 2-byte sequence
        obj[obj.KEY_SRC_SEQ] = b'\xFF\xEE'
        expect = b'\xFF\xEE\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A'
        result = obj.get_request()
        self.assertEqual(result, expect)

        # swap in a new 1-byte sequence - expect padding with 0x01
        obj[obj.KEY_SRC_SEQ] = b'\x44'
        expect = b'\x44\x01\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A'
        result = obj.get_request()
        self.assertEqual(result, expect)

        # swap in a new n byte sequence - expect padding with 0x01
        obj[obj.KEY_SRC_SEQ] = b''
        expect = b'\x01\x01\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A'
        result = obj.get_request()
        self.assertEqual(result, expect)

        # swap in a new 3 byte sequence - expect truncate to 2 bytes
        obj[obj.KEY_SRC_SEQ] = b'\x05\x06\x07'
        expect = b'\x05\x06\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A'
        result = obj.get_request()
        self.assertEqual(result, expect)

        # swap in a new int sequence
        obj[obj.KEY_SRC_SEQ] = 0
        expect = b'\x00\x00\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A'
        result = obj.get_request()
        self.assertEqual(result, expect)

        obj[obj.KEY_SRC_SEQ] = 0x01
        expect = b'\x00\x01\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A'
        result = obj.get_request()
        self.assertEqual(result, expect)

        # swap in a new int sequence - saved as big-endian
        obj[obj.KEY_SRC_SEQ] = 0x0306
        expect = b'\x03\x06\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A'
        result = obj.get_request()
        self.assertEqual(result, expect)

        # swap in a new int sequence - excess is truncated
        obj[obj.KEY_SRC_SEQ] = 0xFF0306
        expect = b'\x03\x06\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A'
        result = obj.get_request()
        self.assertEqual(result, expect)

        return

    def test_all_request(self):

        tests = [
            {'src': b'\xAB\xCD\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A',
             'raw': b'\x01\x03\x00\x00\x00\x0A',
             'asc': b':01030000000AF2\r\n',
             'rtu': b'\x01\x03\x00\x00\x00\x0A\xC5\xCD',
             'tcp': b'\xAB\xCD\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A'},
        ]

        obj = ModbusTransaction()

        for test in tests:
            # loop through all tests

            # print("test:{}".format(test))

            result = obj.set_request(test['src'], ia_trans.IA_PROTOCOL_MBTCP)
            self.assertEqual(obj[obj.KEY_REQ_PROTOCOL],
                             ia_trans.IA_PROTOCOL_MBTCP)

            # default will be TCP
            result = obj.get_request()
            self.assertEqual(result, test['tcp'])

            # confirm we can pull back as any of the three
            result = obj.get_request(ia_trans.IA_PROTOCOL_MBASC)
            self.assertEqual(result, test['asc'])

            result = obj.get_request(ia_trans.IA_PROTOCOL_MBRTU)
            self.assertEqual(result, test['rtu'])

            result = obj.get_request(ia_trans.IA_PROTOCOL_MBTCP)
            self.assertEqual(result, test['tcp'])

        return

    def test_end_of_message(self):

        tests = [
            {'src': b'\xAB\xCD\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A',
             'result': [b'\xAB\xCD\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A'],
             'extra': None},

            {'src': b'',
             'result': [], 'extra': b''},
            {'src': b'\xAB',
             'result': [], 'extra': b'\xAB'},
            {'src': b'\xAB\xCD',
             'result': [], 'extra': b'\xAB\xCD'},
            {'src': b'\xAB\xCD\x00',
             'result': [], 'extra': b'\xAB\xCD\x00'},
            {'src': b'\xAB\xCD\x00\x00',
             'result': [], 'extra': b'\xAB\xCD\x00\x00'},
            {'src': b'\xAB\xCD\x00\x00\x00',
             'result': [], 'extra': b'\xAB\xCD\x00\x00\x00'},
            {'src': b'\xAB\xCD\x00\x00\x00\x06',
             'result': [], 'extra': b'\xAB\xCD\x00\x00\x00\x06'},
            {'src': b'\xAB\xCD\x00\x00\x00\x06\x01\x03',
             'result': [],
             'extra': b'\xAB\xCD\x00\x00\x00\x06\x01\x03'},
            {'src': b'\xAB\xCD\x00\x00\x00\x06\x01\x03\x00\x00\x00',
             'result': [],
             'extra': b'\xAB\xCD\x00\x00\x00\x06\x01\x03\x00\x00\x00'},

            # here we have bad header values (protocol vers or length)
            {'src': b'\xAB\xCD\x01\x00\x00\x06\x01\x03\x00\x00\x00\x0A',
             'result': None, 'extra': None},
            {'src': b'\xAB\xCD\x00\x02\x00\x06\x01\x03\x00\x00\x00\x0A',
             'result': None, 'extra': None},
            {'src': b'\xAB\xCD\x00\x00\x03\x06\x01\x03\x00\x00\x00\x0A',
             'result': None, 'extra': None},
            {'src': b'\xAB\xCD\x00\x00\x00\x00',
             'result': None, 'extra': None},
            {'src': b'\xAB\xCD\x00\x00\x00\x01\x01',
             'result': None, 'extra': None},

            # this isn't a valid PDU, but follows the rules!
            {'src': b'\xAB\xCD\x00\x00\x00\x02\x01\x03',
             'result': [b'\xAB\xCD\x00\x00\x00\x02\x01\x03'], 'extra': None},

            # try the multiple messages
            {'src': b'\xAB\xCD\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A' +
                    b'\xAB\xCD\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A',
             'result': [b'\xAB\xCD\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A',
                        b'\xAB\xCD\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A'],
             'extra': None},

            {'src': b'\xAB\xCD\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A' +
                    b'\xAB\xCD\x00\x00\x00\x06\x01\x03\x00\x00\x00',
             'result': [b'\xAB\xCD\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A'],
             'extra': b'\xAB\xCD\x00\x00\x00\x06\x01\x03\x00\x00\x00'},
            {'src': b'\xAB\xCD\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A' +
                    b'\xAB\xCD\x00',
             'result': [b'\xAB\xCD\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A'],
             'extra': b'\xAB\xCD\x00'},
            {'src': b'\xAB\xCD\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A' +
                    b'\xAB',
             'result': [b'\xAB\xCD\x00\x00\x00\x06\x01\x03\x00\x00\x00\x0A'],
             'extra': b'\xAB'},
        ]

        for test in tests:
            # loop through all tests

            # print("test:{}".format(test))

            result, extra = mbus_tcp.test_end_of_message(test['src'])
            self.assertEqual(result, test['result'])
            self.assertEqual(extra, test['extra'])

        return


if __name__ == '__main__':
    unittest.main()
