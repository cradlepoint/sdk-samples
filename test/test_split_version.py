# Test the cp_lib.split.version module

import logging
import unittest


class TestSplitVersion(unittest.TestCase):

    def test_split_version(self):
        """
        Test the raw/simple handling of 1 INI to JSON in any directory
        :return:
        """
        from cp_lib.split_version import split_version_string

        tests = [
            (None, None, None, None, None),
            (None, "3", 3, 0, 0),
            (None, "3.4", 3, 4, 0),
            (None, "3.4.7", 3, 4, 7),
            ("9.65", None, 9, 65, 0),
            ("9.65", "3", 9, 65, 0),
            ("9.65", "3.4", 9, 65, 0),
            ("9.65", "3.4.7", 9, 65, 0),
            ("9.65.beta", None, 9, 65, "beta"),
            ("9.65.B", "3", 9, 65, "B"),
            ("9.65.beta", "3.4", 9, 65, "beta"),

            # bad types
            (9.65, None, TypeError, 65, 0),
            (9, None, TypeError, 65, 0),
        ]

        for test in tests:
            # logging.debug("Test:{}".format(test))
            source = test[0]
            source_default = test[1]
            expect_major = test[2]
            expect_minor = test[3]
            expect_patch = test[4]

            if expect_major == TypeError:
                with self.assertRaises(TypeError):
                    split_version_string(source)

            else:
                if source_default is None:
                    major, minor, patch = split_version_string(source)
                else:
                    major, minor, patch = split_version_string(source, source_default)

                self.assertEqual(major, expect_major)
                self.assertEqual(minor, expect_minor)
                self.assertEqual(patch, expect_patch)

        return

    def test_split_version_dict(self):
        """
        :return:
        """
        from cp_lib.split_version import split_version_save_to_dict, SETS_NAME_MAJOR, SETS_NAME_MINOR, SETS_NAME_PATCH

        tests = [
            (None, None, None, None, None),
            (None, "3", 3, 0, 0),
            (None, "3.4", 3, 4, 0),
            (None, "3.4.7", 3, 4, 7),
            ("9.65", None, 9, 65, 0),
            ("9.65", "3", 9, 65, 0),
            ("9.65", "3.4", 9, 65, 0),
            ("9.65", "3.4.7", 9, 65, 0),
            ("9.65.beta", None, 9, 65, "beta"),
            ("9.65.B", "3", 9, 65, "B"),
            ("9.65.beta", "3.4", 9, 65, "beta"),
        ]

        base = dict()

        for test in tests:
            # logging.debug("Test:{}".format(test))
            source = test[0]
            source_default = test[1]
            expect_major = test[2]
            expect_minor = test[3]
            expect_patch = test[4]

            if SETS_NAME_MAJOR in base:
                base.pop(SETS_NAME_MAJOR)

            if SETS_NAME_MINOR in base:
                base.pop(SETS_NAME_MINOR)

            if SETS_NAME_PATCH in base:
                base.pop(SETS_NAME_PATCH)

            self.assertFalse(SETS_NAME_MAJOR in base)
            self.assertFalse(SETS_NAME_MINOR in base)
            self.assertFalse(SETS_NAME_PATCH in base)

            if expect_major == TypeError:
                with self.assertRaises(TypeError):
                    split_version_save_to_dict(source, base)

            else:
                if source_default is None:
                    split_version_save_to_dict(source, base)
                else:
                    split_version_save_to_dict(source, base, source_default)

                self.assertEqual(base[SETS_NAME_MAJOR], expect_major)
                self.assertEqual(base[SETS_NAME_MINOR], expect_minor)
                self.assertEqual(base[SETS_NAME_PATCH], expect_patch)

        base = dict()
        base["fw_info"] = dict()

        for test in tests:
            # logging.debug("Test:{}".format(test))
            source = test[0]
            source_default = test[1]
            expect_major = test[2]
            expect_minor = test[3]
            expect_patch = test[4]

            if SETS_NAME_MAJOR in base["fw_info"]:
                base["fw_info"].pop(SETS_NAME_MAJOR)

            if SETS_NAME_MINOR in base["fw_info"]:
                base["fw_info"].pop(SETS_NAME_MINOR)

            if SETS_NAME_PATCH in base["fw_info"]:
                base["fw_info"].pop(SETS_NAME_PATCH)

            self.assertFalse(SETS_NAME_MAJOR in base["fw_info"])
            self.assertFalse(SETS_NAME_MINOR in base["fw_info"])
            self.assertFalse(SETS_NAME_PATCH in base["fw_info"])

            if expect_major == TypeError:
                with self.assertRaises(TypeError):
                    split_version_save_to_dict(source, base, section="fw_info")

            else:
                if source_default is None:
                    split_version_save_to_dict(source, base, section="fw_info")
                else:
                    split_version_save_to_dict(source, base, source_default, section="fw_info")

                self.assertEqual(base["fw_info"][SETS_NAME_MAJOR], expect_major)
                self.assertEqual(base["fw_info"][SETS_NAME_MINOR], expect_minor)
                self.assertEqual(base["fw_info"][SETS_NAME_PATCH], expect_patch)

        return

    def test_sets_version_str(self):
        """
        :return:
        """
        from cp_lib.split_version import split_version_save_to_dict, sets_version_to_str

        tests = [
            (None, None, None),
            (None, "3", "3.0.0"),
            (None, "3.4", "3.4.0"),
            (None, "3.4.7", "3.4.7"),
            ("9.65", None, "9.65.0"),
            ("9.65", "3", "9.65.0"),
            ("9.65", "3.4", "9.65.0"),
            ("9.65", "3.4.7", "9.65.0"),
            ("9.65.beta", None, "9.65.beta"),
            ("9.65.B", "3", "9.65.B"),
            ("9.65.beta", "3.4", "9.65.beta"),
        ]

        base = dict()

        for test in tests:
            # logging.debug("Test:{}".format(test))
            source = test[0]
            source_default = test[1]
            expect = test[2]

            if source_default is None:
                split_version_save_to_dict(source, base)
            else:
                split_version_save_to_dict(source, base, source_default)

            result = sets_version_to_str(base)
            self.assertEqual(result, expect)

        base = dict()
        base["fw_info"] = dict()

        for test in tests:
            # logging.debug("Test:{}".format(test))
            source = test[0]
            source_default = test[1]
            expect = test[2]

            if source_default is None:
                split_version_save_to_dict(source, base, section="fw_info")
            else:
                split_version_save_to_dict(source, base, source_default, section="fw_info")

            result = sets_version_to_str(base, section="fw_info")
            self.assertEqual(result, expect)

        return


if __name__ == '__main__':
    # logging.basicConfig(level=logging.INFO)
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
