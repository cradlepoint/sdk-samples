# Test the demo.redlion_cub.cub5_protocol module

# as of 2016, mu 4-wire RJ11 cable has 4 wires:
# 1) black: rdc D+
# 2) red: rdc D-
# 3) green: rdc SG
# 4) yellow: N/C

import logging
import time
import unittest

from demo.redlion_cub5.cub5_protocol import RedLionCub5


class TestRedLionCub5(unittest.TestCase):

    def test_format_node_address(self):
        global _logger

        print("")  # skip paste '.' on line

        obj = RedLionCub5()
        obj.force_use_node_address = False

        tests = [
            (0, ''), (1, 'N1'), (2, 'N2'), (3, 'N3'), (4, 'N4'), (5, 'N5'),
            (6, 'N6'), (7, 'N7'), (8, 'N8'), (9, 'N9'), (10, 'N10'),
            (11, 'N11'), (12, 'N12'), (13, 'N13'), (14, 'N14'), (15, 'N15'),
            (16, 'N16'), (17, 'N17'), (18, 'N18'), (19, 'N19'), (20, 'N20'),
            (21, 'N21'), (22, 'N22'), (23, 'N23'), (24, 'N24'), (25, 'N25'),
            (26, 'N26'), (27, 'N27'), (28, 'N28'), (29, 'N29'), (30, 'N30'),
            (31, 'N31'), (32, 'N32'), (33, 'N33'), (34, 'N34'), (35, 'N35'),
            (36, 'N36'), (37, 'N37'), (38, 'N38'), (39, 'N39'), (40, 'N40'),
            (41, 'N41'), (42, 'N42'), (43, 'N43'), (44, 'N44'), (45, 'N45'),
            (46, 'N46'), (47, 'N47'), (48, 'N48'), (49, 'N49'), (50, 'N50'),
            (51, 'N51'), (52, 'N52'), (53, 'N53'), (54, 'N54'), (55, 'N55'),
            (56, 'N56'), (57, 'N57'), (58, 'N58'), (59, 'N59'), (60, 'N60'),
            (61, 'N61'), (62, 'N62'), (63, 'N63'), (64, 'N64'), (65, 'N65'),
            (66, 'N66'), (67, 'N67'), (68, 'N68'), (69, 'N69'), (70, 'N70'),
            (71, 'N71'), (72, 'N72'), (73, 'N73'), (74, 'N74'), (75, 'N75'),
            (76, 'N76'), (77, 'N77'), (78, 'N78'), (79, 'N79'), (80, 'N80'),
            (81, 'N81'), (82, 'N82'), (83, 'N83'), (84, 'N84'), (85, 'N85'),
            (86, 'N86'), (87, 'N87'), (88, 'N88'), (89, 'N89'), (90, 'N90'),
            (91, 'N91'), (92, 'N92'), (93, 'N93'), (94, 'N94'), (95, 'N95'),
            (96, 'N96'), (97, 'N97'), (98, 'N98'), (99, 'N99')
        ]

        for test in tests:
            source = test[0]
            expect = test[1]

            result = obj.format_node_address_string(source)
            self.assertEqual(result, expect)

        # test the 'N0'
        obj.force_use_node_address = True
        source = 0
        expect = 'N0'
        result = obj.format_node_address_string(source)
        self.assertEqual(result, expect)
        obj.force_use_node_address = False

        # test the range
        source = obj.NODE_MIN - 1
        with self.assertRaises(AssertionError):
            obj.format_node_address_string(source)
        source = obj.NODE_MAX + 1
        with self.assertRaises(AssertionError):
            obj.format_node_address_string(source)

        # a few internal tests
        tests = [
            (0, ''), (1, 'N1'), (48, 'N48'), (98, 'N98'), (99, 'N99'),
            (None, ValueError), ('1', ValueError), ('hello', ValueError),
            (98.0, ValueError)
        ]

        for test in tests:
            source = test[0]
            expect = test[1]
            # print("test:{}".format(test))

            if expect == ValueError:
                with self.assertRaises(ValueError):
                    obj.set_node_address(source)

            else:
                obj.set_node_address(source)
                result = obj.format_node_address_string()
                self.assertEqual(result, expect)

        return

    def test_format_read(self):
        global _logger

        print("")  # skip paste '.' on line

        obj = RedLionCub5()

        tests = [
            {'adr': 0, 'id': 'CTA', 'exp': 'TA*'},
            {'adr': 5, 'id': 'CTA', 'exp': 'N5TA*'},
            {'adr': 5, 'id': 'RTE', 'exp': 'N5TC*'},
            {'adr': 15, 'id': 'SFA', 'exp': 'N15TD*'},
            {'adr': 15, 'id': 'SFB', 'exp': 'N15TE*'},
            {'adr': 5, 'id': 'SP1', 'exp': 'N5TF*'},
            {'adr': 5, 'id': 'SP2', 'exp': 'N5TG*'},
            {'adr': 5, 'id': 'CLD', 'exp': 'N5TH*'},
        ]

        for test in tests:
            obj.set_node_address(test['adr'])
            result = obj.format_read_value(test['id'])
            self.assertEqual(result, test['exp'])

        # test the range
        obj.set_node_address(5)
        with self.assertRaises(AttributeError):
            # due to lack of .upper()
            obj.format_read_value(None)

        with self.assertRaises(KeyError):
            # due to NOT being in self.MAP_ID
            obj.format_read_value('silly')

        return

    def test_parse(self):
        global _logger

        print("")  # skip paste '.' on line

        obj = RedLionCub5()

        tests = [
            {'src': b'   CTA           0\r\n',
             'exp': {'adr': 0, 'id': 'CTA', 'data': 0, 'status': True,
                     'raw': 'CTA           0'}},
            {'src': '   CTA           0\r\n',
             'exp': {'adr': 0, 'id': 'CTA', 'data': 0, 'status': True,
                     'raw': 'CTA           0'}},
            {'src': b'   CTA          25\r\n',
             'exp': {'adr': 0, 'id': 'CTA', 'data': 25, 'status': True,
                     'raw': 'CTA          25'}},
            {'src': '   CTA          25\r\n',
             'exp': {'adr': 0, 'id': 'CTA', 'data': 25, 'status': True,
                     'raw': 'CTA          25'}},
        ]

        for test in tests:
            result = obj.parse_response(test['src'])
            # _logger.info("result {}".format(result))
            self.assertEqual(result, test['exp'])

        return

    def test_serial(self):
        global _logger

        if False:
            _logger.warning("Skip serial test due to flag")

        else:
            import serial

            name = "COM5"
            baud = 9600
            _logger.info("Open port {}".format(name))
            ser = serial.Serial(name, baudrate=baud, bytesize=8,
                                parity=serial.PARITY_NONE, timeout=1.0)

            send = b'TA*'
            _logger.info("Write {}".format(send))
            ser.write(send)
            result = ser.read(50)
            _logger.info("Read {}".format(result))

            time.sleep(1.0)

            send = b'TB*'
            _logger.info("Write {}".format(send))
            ser.write(send)
            result = ser.read(50)
            _logger.info("Read {}".format(result))

            ser.close()

if __name__ == '__main__':

    # logging.basicConfig(level=logging.INFO)
    logging.basicConfig(level=logging.DEBUG)

    _logger = logging.getLogger('unittest')
    _logger.setLevel(logging.DEBUG)

    unittest.main()
