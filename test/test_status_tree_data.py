# Test the cp_lib.status_tree_data module

import logging
import unittest
import uuid

from cp_lib.app_base import CradlepointAppBase
from cp_lib.status_tree_data import StatusTreeData

# set to None to get random one
USE_UUID = "ae151650-4ce9-4337-ab6b-a16f886be569"


class TestStatusTreeData(unittest.TestCase):

    def test_startup(self):
        """
        :return:
        """
        global USE_UUID

        print()  # move past the '.'

        app_base = CradlepointAppBase("simple.do_it")
        if USE_UUID is None:
            USE_UUID = str(uuid.uuid4())

        app_base.logger.debug("UUID:{}".format(USE_UUID))

        obj = StatusTreeData(app_base)
        try:
            obj.set_uuid(USE_UUID)

        except ValueError:
            app_base.logger.error("No APPS installed")
            raise

        obj.clear_data()
        # if True:
        #     return

        # if this is a FRESH system, then first get will be NULL/NONE
        result = obj.get_data()
        self.assertEqual(obj.data, dict())

        result = obj.put_data(force=True)
        app_base.logger.debug("data:{}".format(result))
        self.assertEqual(obj.clean, True)

        obj.set_data_value('health', 100.0)
        self.assertEqual(obj.clean, False)

        result = obj.put_data(force=True)
        app_base.logger.debug("data:{}".format(result))

        return

if __name__ == '__main__':
    # logging.basicConfig(level=logging.INFO)
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
