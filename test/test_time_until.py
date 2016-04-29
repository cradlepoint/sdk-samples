# Test the cp_lib.app_base module

import logging
import time
import unittest

import cp_lib.time_until as time_until


class TestTimeUntil(unittest.TestCase):

    def test_seconds_until_next_minute(self):
        """
        :return:
        """

        print()  # move past the '.'

        now = time.time()
        logging.debug("Now = {} sec".format(time.asctime()))

        result = time_until.seconds_until_next_minute(now)
        logging.debug("Result = {} sec".format(result))

        # self.assertTrue(os.path.exists(expect))

        return


if __name__ == '__main__':
    # logging.basicConfig(level=logging.INFO)
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
