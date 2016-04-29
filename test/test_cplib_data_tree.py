# Test the PARSE DATA module
import sys
import unittest

from cp_lib.data.data_tree import DataTreeItemNotFound, DataTreeItemBadValue, \
    get_item, get_item_bool, get_item_int, data_tree_clean, \
    get_item_float, get_item_time_duration_to_seconds, put_item

# mimic a settings.ini config
data_tree = {
    "logging": {
        "level": "debug",
        "syslog_ip": "192.168.35.6",
        "pc_syslog": False,
    },
    "router_api": {
        "user_name": None,
        "interface": "null",
        "local_ip": "192.168.35.1",
        "password": "441b537e",
        # we nest one more level to check depth
        "application": {
            "name": "make",
            "firmware": "6.1",
            "restart": "true",
            "reboot": True,
            "other": {
                "able": True,
                "babble": False,
                "cable": None,
            }
        },
    },
    "startup": {
        "boot_delay_max": "5 min",
        "boot_delay_for_time": True,
        "boot_delay_for_wan": True,
        "exit_delay": "30 sec",
    }
}


class TestParseDataTree(unittest.TestCase):

    def test_get_item(self):

        # this one's not there, so expect None
        self.assertEqual(None, get_item(data_tree, ""))
        self.assertEqual(None, get_item(data_tree, "apple"))
        self.assertEqual(None, get_item(data_tree,
                                        "router_api.apple"))
        self.assertEqual(None, get_item(data_tree,
                                        "router_api.apple.core"))

        # here want the exception thrown, not to return None
        with self.assertRaises(DataTreeItemNotFound):
            get_item(data_tree, "", throw_exception=True)
            get_item(data_tree, "apple", throw_exception=True)
            get_item(data_tree, "router_api.apple", throw_exception=True)
            get_item(data_tree, "router_api.apple.core", throw_exception=True)

        # however, confirm None which is found is returned as None
        self.assertEqual(None, get_item(
            data_tree, "router_api.user_name", throw_exception=True))
        self.assertEqual(None, get_item(
            data_tree, "router_api.application.other.cable",
            throw_exception=True))

        self.assertEqual("debug", get_item(data_tree, "logging.level"))
        self.assertEqual("192.168.35.6", get_item(data_tree,
                                                  "logging.syslog_ip"))
        self.assertEqual(False, get_item(data_tree, "logging.pc_syslog"))

        self.assertEqual(None, get_item(data_tree, "router_api.user_name"))
        self.assertEqual("null", get_item(data_tree, "router_api.interface"))
        self.assertEqual("192.168.35.1", get_item(data_tree,
                                                  "router_api.local_ip"))
        self.assertEqual("441b537e", get_item(data_tree,
                                              "router_api.password"))

        self.assertEqual("make", get_item(data_tree,
                                          "router_api.application.name"))
        self.assertEqual("6.1", get_item(data_tree,
                                         "router_api.application.firmware"))
        self.assertEqual("true", get_item(data_tree,
                                          "router_api.application.restart"))
        self.assertEqual(True, get_item(data_tree,
                                        "router_api.application.reboot"))

        self.assertEqual(True, get_item(data_tree,
                                        "router_api.application.other.able"))
        self.assertEqual(False, get_item(
            data_tree, "router_api.application.other.babble"))
        self.assertEqual(None, get_item(
            data_tree, "router_api.application.other.cable"))

        self.assertEqual("5 min", get_item(data_tree,
                                           "startup.boot_delay_max"))
        self.assertEqual(True, get_item(data_tree,
                                        "startup.boot_delay_for_time"))
        self.assertEqual(True, get_item(data_tree,
                                        "startup.boot_delay_for_wan"))
        self.assertEqual("30 sec", get_item(data_tree, "startup.exit_delay"))

        with self.assertRaises(TypeError):
            # first param must be dict()
            get_item(None, "startup.exit_delay")
            get_item(True, "startup.exit_delay")
            get_item(10, "startup.exit_delay")
            get_item("Hello", "startup.exit_delay")

        with self.assertRaises(TypeError):
            # second param must be str()
            get_item(data_tree, None)
            get_item(data_tree, True)
            get_item(data_tree, 10)

        self.assertEqual(None, get_item(data_tree, ""))

        # check a few sub-tree pulls
        self.assertEqual(data_tree["logging"],
                         get_item(data_tree, "logging"))
        self.assertEqual(data_tree["router_api"],
                         get_item(data_tree, "router_api"))
        self.assertEqual(data_tree["router_api"]["application"],
                         get_item(data_tree, "router_api.application"))
        self.assertEqual(data_tree["router_api"]["application"]["other"],
                         get_item(data_tree, "router_api.application.other"))

        return

    def test_data_tree_clean(self):
        # mimic a settings.ini config

        # make new tree, since we change the tree items
        _data_tree = {
            "logging": {
                "level": "debug",
                "syslog_ip": "false",
                "pc_syslog": False,
            },
            "router_api": {
                "user_name": None,
                "interface": "null",
                "local_ip": "192.168.35.1",
                "password": "none",
                "application": {
                    "name": "make",
                    "firmware": "6.1",
                    "restart": "tRUe",
                    "reboot": True,
                },
            },
        }

        # check everything is as expected
        self.assertEqual("debug", get_item(_data_tree, "logging.level"))
        self.assertEqual("false", get_item(_data_tree, "logging.syslog_ip"))
        self.assertEqual(False, get_item(_data_tree, "logging.pc_syslog"))

        self.assertEqual(None, get_item(_data_tree, "router_api.user_name"))
        self.assertEqual("null", get_item(_data_tree, "router_api.interface"))
        self.assertEqual("192.168.35.1", get_item(_data_tree,
                                                  "router_api.local_ip"))
        self.assertEqual("none", get_item(_data_tree, "router_api.password"))

        self.assertEqual("make", get_item(_data_tree,
                                          "router_api.application.name"))
        self.assertEqual("6.1", get_item(_data_tree,
                                         "router_api.application.firmware"))
        self.assertEqual("tRUe", get_item(_data_tree,
                                          "router_api.application.restart"))
        self.assertEqual(True, get_item(_data_tree,
                                        "router_api.application.reboot"))

        # now we go through & clean
        data_tree_clean(_data_tree)

        self.assertEqual("debug", get_item(_data_tree, "logging.level"))
        self.assertEqual(False, get_item(_data_tree, "logging.syslog_ip"))
        self.assertEqual(False, get_item(_data_tree, "logging.pc_syslog"))

        self.assertEqual(None, get_item(_data_tree, "router_api.user_name"))
        self.assertEqual(None, get_item(_data_tree, "router_api.interface"))
        self.assertEqual("192.168.35.1", get_item(_data_tree,
                                                  "router_api.local_ip"))
        self.assertEqual(None, get_item(_data_tree, "router_api.password"))

        self.assertEqual("make", get_item(_data_tree,
                                          "router_api.application.name"))
        self.assertEqual("6.1", get_item(_data_tree,
                                         "router_api.application.firmware"))
        self.assertEqual(True, get_item(_data_tree,
                                        "router_api.application.restart"))
        self.assertEqual(True, get_item(_data_tree,
                                        "router_api.application.reboot"))

        return

    def test_get_item_bool(self):

        mini_tree = {
            "are_true": {
                "a": True,
                "b": "t",
                "c": "T",
                "d": "true",
                "e": "tRUe",
                "f": "TRUE",
                "g": "on",
                "h": "On",
                "i": "ON",
                "j": "enable",
                "k": "enabled",
                "l": 1,
                "m": '1',
                "are_false": {
                    "a": False,
                    "b": "f",
                    "c": "F",
                    "d": "false",
                    "e": "faLSe",
                    "f": "FALSE",
                    "g": "off",
                    "h": "Off",
                    "i": "OFF",
                    "j": "disable",
                    "k": "disabled",
                    "l": 0,
                    "m": '0',
                },
            },
            "junk": {
                "a": None,
                "b": 10,
                "c": 'Hello',
                "d": {'g': True},
                "e": (True, 10),
            }
        }

        self.assertTrue(get_item_bool(mini_tree, "are_true.a"))
        self.assertTrue(get_item_bool(mini_tree, "are_true.b"))
        self.assertTrue(get_item_bool(mini_tree, "are_true.c"))
        self.assertTrue(get_item_bool(mini_tree, "are_true.d"))
        self.assertTrue(get_item_bool(mini_tree, "are_true.e"))
        self.assertTrue(get_item_bool(mini_tree, "are_true.f"))
        self.assertTrue(get_item_bool(mini_tree, "are_true.g"))
        self.assertTrue(get_item_bool(mini_tree, "are_true.h"))
        self.assertTrue(get_item_bool(mini_tree, "are_true.i"))
        self.assertTrue(get_item_bool(mini_tree, "are_true.j"))
        self.assertTrue(get_item_bool(mini_tree, "are_true.k"))
        self.assertTrue(get_item_bool(mini_tree, "are_true.l"))
        self.assertTrue(get_item_bool(mini_tree, "are_true.m"))

        self.assertFalse(get_item_bool(mini_tree, "are_true.are_false.a"))
        self.assertFalse(get_item_bool(mini_tree, "are_true.are_false.b"))
        self.assertFalse(get_item_bool(mini_tree, "are_true.are_false.c"))
        self.assertFalse(get_item_bool(mini_tree, "are_true.are_false.d"))
        self.assertFalse(get_item_bool(mini_tree, "are_true.are_false.e"))
        self.assertFalse(get_item_bool(mini_tree, "are_true.are_false.f"))
        self.assertFalse(get_item_bool(mini_tree, "are_true.are_false.g"))
        self.assertFalse(get_item_bool(mini_tree, "are_true.are_false.h"))
        self.assertFalse(get_item_bool(mini_tree, "are_true.are_false.i"))
        self.assertFalse(get_item_bool(mini_tree, "are_true.are_false.j"))
        self.assertFalse(get_item_bool(mini_tree, "are_true.are_false.k"))
        self.assertFalse(get_item_bool(mini_tree, "are_true.are_false.l"))
        self.assertFalse(get_item_bool(mini_tree, "are_true.are_false.m"))

        # just check the bool items
        self.assertFalse(get_item_bool(data_tree, "logging.pc_syslog"))
        self.assertTrue(get_item_bool(data_tree,
                                      "router_api.application.restart"))
        self.assertTrue(get_item_bool(data_tree,
                                      "router_api.application.reboot"))
        self.assertTrue(get_item_bool(data_tree,
                                      "router_api.application.other.able"))
        self.assertFalse(get_item_bool(data_tree,
                                       "router_api.application.other.babble"))
        self.assertTrue(get_item_bool(data_tree,
                                      "startup.boot_delay_for_time"))
        self.assertTrue(get_item_bool(data_tree,
                                      "startup.boot_delay_for_wan"))

        with self.assertRaises(DataTreeItemBadValue):
            # none of these are Boolean.
            get_item_bool(mini_tree, "junk.a")
            get_item_bool(mini_tree, "junk.b")
            get_item_bool(mini_tree, "junk.c")
            get_item_bool(mini_tree, "junk.d")
            get_item_bool(mini_tree, "junk.e")

        return

    def test_get_item_integer(self):

        mini_tree = {
            "okay": {
                "a": 10,
                "b": "13",
                "c": "  99",
                "d": "0x13",
            },
            "junk": {
                "a": None,
                "b": True,
                "c": 'Hello',
                "d": {'g': True},
                "e": (True, 10),
            }
        }

        self.assertEqual(10, get_item_int(mini_tree, "okay.a"))
        self.assertEqual(13, get_item_int(mini_tree, "okay.b"))
        self.assertEqual(99, get_item_int(mini_tree, "okay.c"))
        self.assertEqual(19, get_item_int(mini_tree, "okay.d"))

        with self.assertRaises(DataTreeItemBadValue):
            # none of these are integers.
            get_item_int(mini_tree, "junk.a")
            get_item_int(mini_tree, "junk.b")
            get_item_int(mini_tree, "junk.c")
            get_item_int(mini_tree, "junk.d")
            get_item_int(mini_tree, "junk.e")

        return

    def test_get_item_float(self):

        mini_tree = {
            "okay": {
                "a": 10,
                "b": "13",
                "c": "  99",
                "d": 10.1,
                "e": "13.2 ",
                "f": "  99.3",
            },
            "junk": {
                "a": None,
                "b": True,
                "c": 'Hello',
                "d": {'g': True},
                "e": (True, 10),
            }
        }

        self.assertEqual(10.0, get_item_float(mini_tree, "okay.a"))
        self.assertEqual(13.0, get_item_float(mini_tree, "okay.b"))
        self.assertEqual(99.0, get_item_float(mini_tree, "okay.c"))

        self.assertEqual(10.1, get_item_float(mini_tree, "okay.d"))
        self.assertEqual(13.2, get_item_float(mini_tree, "okay.e"))
        self.assertEqual(99.3, get_item_float(mini_tree, "okay.f"))

        with self.assertRaises(DataTreeItemBadValue):
            # none of these are floats.
            get_item_float(mini_tree, "junk.a")
            get_item_float(mini_tree, "junk.b")
            get_item_float(mini_tree, "junk.c")
            get_item_float(mini_tree, "junk.d")
            get_item_float(mini_tree, "junk.e")

        return

    def test_get_item_time_duration(self):

        mini_tree = {
            "okay": {
                "a": 10,
                "b": "13",
                "c": "  99",

                "d": 10.1,
                "e": "13.2 ",
                "f": "  99.3",

                "g": "10 sec",
                "h": "10 min",
                "i": "10 hour",
            },
            "junk": {
                "a": None,
                "b": True,
                "c": 'Hello',
                "d": {'g': True},
                "e": (True, 10),
            }
        }

        self.assertEqual(10.0, get_item_time_duration_to_seconds(mini_tree,
                                                                 "okay.a"))
        self.assertEqual(13.0, get_item_time_duration_to_seconds(mini_tree,
                                                                 "okay.b"))
        self.assertEqual(99.0, get_item_time_duration_to_seconds(mini_tree,
                                                                 "okay.c"))

        self.assertEqual(10.1, get_item_time_duration_to_seconds(mini_tree,
                                                                 "okay.d"))
        self.assertEqual(13.2, get_item_time_duration_to_seconds(mini_tree,
                                                                 "okay.e"))
        self.assertEqual(99.3, get_item_time_duration_to_seconds(mini_tree,
                                                                 "okay.f"))

        self.assertEqual(10.0, get_item_time_duration_to_seconds(mini_tree,
                                                                 "okay.g"))
        self.assertEqual(600.0, get_item_time_duration_to_seconds(mini_tree,
                                                                  "okay.h"))
        self.assertEqual(36000.0, get_item_time_duration_to_seconds(mini_tree,
                                                                    "okay.i"))

        with self.assertRaises(DataTreeItemBadValue):
            # none of these are time durations.
            get_item_time_duration_to_seconds(mini_tree, "junk.a")
            get_item_time_duration_to_seconds(mini_tree, "junk.b")
            get_item_time_duration_to_seconds(mini_tree, "junk.c")
            get_item_time_duration_to_seconds(mini_tree, "junk.d")
            get_item_time_duration_to_seconds(mini_tree, "junk.e")

        return

    def test_put_item(self):

        test_tree = dict()

        with self.assertRaises(TypeError):
            put_item(None, "usa", "USA")
            put_item(test_tree, 10, "USA")

        put_item(test_tree, "minnesota", "MN")
        print("tree:{}".format(test_tree))

        return

if __name__ == '__main__':
    unittest.main()
