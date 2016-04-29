# Test the cp_lib.split.version module

import logging
import unittest


class TestBufferDump(unittest.TestCase):

    def test_buffer_dump(self):
        """
        Test buffer to lines function
        :return:
        """
        from cp_lib.buffer_dump import buffer_dump

        tests = [
            {"msg": None, "dat": None, "asc": False,
             "exp": ['dump:None, data=None']},
            {"msg": None, "dat": None, "asc": True,
             "exp": ['dump:None, data=None']},
            {"msg": "null", "dat": None, "asc": False,
             "exp": ['dump:null, data=None']},
            {"msg": "null", "dat": None, "asc": True,
             "exp": ['dump:null, data=None']},

            {"msg": "fruit", "dat": "Apple", "asc": False,
             "exp": ['dump:fruit, len=5', '[000] 41 70 70 6C 65']},
            {"msg": "fruit", "dat": "Apple", "asc": True,
             "exp": ['dump:fruit, len=5', '[000] 41 70 70 6C 65 \'Apple\'']},
            {"msg": "fruit", "dat": b"Apple", "asc": False,
             "exp": ['dump:fruit, len=5 bytes()', '[000] 41 70 70 6C 65']},
            {"msg": "fruit", "dat": b"Apple", "asc": True,
             "exp": ['dump:fruit, len=5 bytes()', '[000] 41 70 70 6C 65 b\'Apple\'']},

            {"msg": "fruit", "dat": "Apple\n", "asc": False,
             "exp": ['dump:fruit, len=6', '[000] 41 70 70 6C 65 0A']},
            {"msg": "fruit", "dat": "Apple\n", "asc": True,
             "exp": ['dump:fruit, len=6', '[000] 41 70 70 6C 65 0A \'Apple\\n\'']},
            {"msg": "fruit", "dat": b"Apple\n", "asc": False,
             "exp": ['dump:fruit, len=6 bytes()', '[000] 41 70 70 6C 65 0A']},
            {"msg": "fruit", "dat": b"Apple\n", "asc": True,
             "exp": ['dump:fruit, len=6 bytes()', '[000] 41 70 70 6C 65 0A b\'Apple\\n\'']},

            {"msg": "fruit nl", "dat": "Apple\r\n\0", "asc": False,
             "exp": ['dump:fruit nl, len=8', '[000] 41 70 70 6C 65 0D 0A 00']},
            {"msg": "fruit nl", "dat": "Apple\r\n\0", "asc": True,
             "exp": ['dump:fruit nl, len=8', '[000] 41 70 70 6C 65 0D 0A 00 \'Apple\\r\\n\\x00\'']},
            {"msg": "fruit nl", "dat": b"Apple\r\n\0", "asc": False,
             "exp": ['dump:fruit nl, len=8 bytes()',
                     '[000] 41 70 70 6C 65 0D 0A 00']},
            {"msg": "fruit nl", "dat": b"Apple\r\n\0", "asc": True,
             "exp": ['dump:fruit nl, len=8 bytes()',
                     '[000] 41 70 70 6C 65 0D 0A 00 b\'Apple\\r\\n\\x00\'']},

            {"msg": "longer", "dat": "Apple\nIs found in the country of my birth\n", "asc": False,
             "exp": ['dump:longer, len=42',
                     '[000] 41 70 70 6C 65 0A 49 73 20 66 6F 75 6E 64 20 69',
                     '[016] 6E 20 74 68 65 20 63 6F 75 6E 74 72 79 20 6F 66',
                     '[032] 20 6D 79 20 62 69 72 74 68 0A']},
            {"msg": "longer", "dat": "Apple\nIs found in the country of my birth\n", "asc": True,
             "exp": ['dump:longer, len=42',
                     '[000] 41 70 70 6C 65 0A 49 73 20 66 6F 75 6E 64 20 69' +
                     ' \'Apple\\nIs found i\'',
                     '[016] 6E 20 74 68 65 20 63 6F 75 6E 74 72 79 20 6F 66' +
                     ' \'n the country of\'',
                     '[032] 20 6D 79 20 62 69 72 74 68 0A \' my birth\\n\'']},
            {"msg": "longer", "dat": b"Apple\nIs found in the country of my birth\n", "asc": False,
             "exp": ['dump:longer, len=42 bytes()',
                     '[000] 41 70 70 6C 65 0A 49 73 20 66 6F 75 6E 64 20 69',
                     '[016] 6E 20 74 68 65 20 63 6F 75 6E 74 72 79 20 6F 66',
                     '[032] 20 6D 79 20 62 69 72 74 68 0A']},
            {"msg": "longer", "dat": b"Apple\nIs found in the country of my birth\n", "asc": True,
             "exp": ['dump:longer, len=42 bytes()',
                     '[000] 41 70 70 6C 65 0A 49 73 20 66 6F 75 6E 64 20 69' +
                     ' b\'Apple\\nIs found i\'',
                     '[016] 6E 20 74 68 65 20 63 6F 75 6E 74 72 79 20 6F 66' +
                     ' b\'n the country of\'',
                     '[032] 20 6D 79 20 62 69 72 74 68 0A b\' my birth\\n\'']},

            {"msg": "Modbus", "dat": "\x01\x1F\x00\x01\x02\x03\x04\x05\x06\x08\x09", "asc": False,
             "exp": ['dump:Modbus, len=11',
                     '[000] 01 1F 00 01 02 03 04 05 06 08 09']},
            {"msg": "Modbus", "dat": b"\x01\x1F\x00\x01\x02\x03\x04\x05\x06\x08\x09", "asc": False,
             "exp": ['dump:Modbus, len=11 bytes()',
                     '[000] 01 1F 00 01 02 03 04 05 06 08 09']},
            {"msg": "Modbus+", "asc": False,
             "dat": "\x01\x1F\x00\x01\x02\x03\x04\x05\x06\x08\x09\x00\x01\x02\x03\x04\x05\x06\x08",
             "exp": ['dump:Modbus+, len=19',
                     '[000] 01 1F 00 01 02 03 04 05 06 08 09 00 01 02 03 04',
                     '[016] 05 06 08']},
            {"msg": "Modbus+", "asc": False,
             "dat": b"\x01\x1F\x00\x01\x02\x03\x04\x05\x06\x08\x09\x00\x01\x02\x03\x04\x05\x06\x08",
             "exp": ['dump:Modbus+, len=19 bytes()',
                     '[000] 01 1F 00 01 02 03 04 05 06 08 09 00 01 02 03 04',
                     '[016] 05 06 08']},

        ]

        for test in tests:
            # logging.debug("Test:{}".format(test))

            result = buffer_dump(test['msg'], test['dat'], test['asc'])
            for line in result:
                logging.debug("   {}".format(line))
            self.assertEqual(result, test['exp'])

            logging.debug("")

        return

    def test_logger_buffer_dump(self):
        """
        Test buffer to lines function
        :return:
        """
        from cp_lib.buffer_dump import logger_buffer_dump

        tests = [
            {"msg": "fruit", "dat": "Apple", "asc": False,
             "exp": ['dump:fruit, len=5', '[000] 41 70 70 6C 65']},
            {"msg": "fruit", "dat": "Apple", "asc": True,
             "exp": ['dump:fruit, len=5', '[000] 41 70 70 6C 65 \'Apple\'']},
            {"msg": "fruit", "dat": b"Apple", "asc": False,
             "exp": ['dump:fruit, len=5 bytes()', '[000] 41 70 70 6C 65']},
            {"msg": "fruit", "dat": b"Apple", "asc": True,
             "exp": ['dump:fruit, len=5 bytes()', '[000] 41 70 70 6C 65 b\'Apple\'']},

            {"msg": "longer", "dat": "Apple\nIs found in the country of my birth\n", "asc": False,
             "exp": ['dump:longer, len=42',
                     '[000] 41 70 70 6C 65 0A 49 73 20 66 6F 75 6E 64 20 69',
                     '[016] 6E 20 74 68 65 20 63 6F 75 6E 74 72 79 20 6F 66',
                     '[032] 20 6D 79 20 62 69 72 74 68 0A']},
            {"msg": "longer", "dat": "Apple\nIs found in the country of my birth\n", "asc": True,
             "exp": ['dump:longer, len=42',
                     '[000] 41 70 70 6C 65 0A 49 73 20 66 6F 75 6E 64 20 69' +
                     ' \'Apple\\nIs found i\'',
                     '[016] 6E 20 74 68 65 20 63 6F 75 6E 74 72 79 20 6F 66' +
                     ' \'n the country of\'',
                     '[032] 20 6D 79 20 62 69 72 74 68 0A \' my birth\\n\'']},
            {"msg": "longer", "dat": b"Apple\nIs found in the country of my birth\n", "asc": False,
             "exp": ['dump:longer, len=42 bytes()',
                     '[000] 41 70 70 6C 65 0A 49 73 20 66 6F 75 6E 64 20 69',
                     '[016] 6E 20 74 68 65 20 63 6F 75 6E 74 72 79 20 6F 66',
                     '[032] 20 6D 79 20 62 69 72 74 68 0A']},
            {"msg": "longer", "dat": b"Apple\nIs found in the country of my birth\n", "asc": True,
             "exp": ['dump:longer, len=42 bytes()',
                     '[000] 41 70 70 6C 65 0A 49 73 20 66 6F 75 6E 64 20 69' +
                     ' b\'Apple\\nIs found i\'',
                     '[016] 6E 20 74 68 65 20 63 6F 75 6E 74 72 79 20 6F 66' +
                     ' b\'n the country of\'',
                     '[032] 20 6D 79 20 62 69 72 74 68 0A b\' my birth\\n\'']},

            {"msg": "Modbus", "dat": "\x01\x1F\x00\x01\x02\x03\x04\x05\x06\x08\x09", "asc": False,
             "exp": ['dump:Modbus, len=11',
                     '[000] 01 1F 00 01 02 03 04 05 06 08 09']},
            {"msg": "Modbus", "dat": b"\x01\x1F\x00\x01\x02\x03\x04\x05\x06\x08\x09", "asc": False,
             "exp": ['dump:Modbus, len=11 bytes()',
                     '[000] 01 1F 00 01 02 03 04 05 06 08 09']},
            {"msg": "Modbus+", "asc": False,
             "dat": "\x01\x1F\x00\x01\x02\x03\x04\x05\x06\x08\x09\x00\x01\x02\x03\x04\x05\x06\x08",
             "exp": ['dump:Modbus+, len=19',
                     '[000] 01 1F 00 01 02 03 04 05 06 08 09 00 01 02 03 04',
                     '[016] 05 06 08']},
            {"msg": "Modbus+", "asc": False,
             "dat": b"\x01\x1F\x00\x01\x02\x03\x04\x05\x06\x08\x09\x00\x01\x02\x03\x04\x05\x06\x08",
             "exp": ['dump:Modbus+, len=19 bytes()',
                     '[000] 01 1F 00 01 02 03 04 05 06 08 09 00 01 02 03 04',
                     '[016] 05 06 08']},

        ]

        logging.info("")

        logger = logging.getLogger('unitest')
        logger.setLevel(logging.DEBUG)

        for test in tests:
            # logging.debug("Test:{}".format(test))

            logger_buffer_dump(logger, test['msg'], test['dat'], test['asc'])
            logging.info("")

        return

if __name__ == '__main__':
    # logging.basicConfig(level=logging.INFO)
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
