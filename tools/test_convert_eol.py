# Test the tools.convert_eol module

import logging
import unittest

from tools.convert_eol import convert_eol_linux


class TestConvertEol(unittest.TestCase):

    def test_convert_eol_linux(self):
        """
        :return:
        """

        convert_eol_linux("build")

        return


if __name__ == '__main__':
    # logging.basicConfig(level=logging.INFO)
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
