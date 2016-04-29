# Test the tools.split.version module

import json
import logging
import os.path
import unittest

from tools.module_dependency import BuildDependencyList


class TestModuleDependency(unittest.TestCase):

    def test_get_file_dependency_list(self):
        """
        Test the one-file module
        :return:
        """

        obj = BuildDependencyList()
        path_name = None
        logging.info("get_file_dependency_list(\"{}\") bad type".format(path_name))
        with self.assertRaises(TypeError):
            obj.add_file_dependency(path_name)
        path_name = 23
        with self.assertRaises(TypeError):
            obj.add_file_dependency(path_name)

        path_name = "not here"
        logging.info("get_file_dependency_list(\"{}\") doesn't exist".format(path_name))
        obj = BuildDependencyList()
        result = obj.add_file_dependency(path_name)
        self.assertIsNone(result)

        path_name = os.path.join("network", "tcp_echo")
        logging.info("get_file_dependency_list(\"{}\") is dir not file".format(path_name))
        obj = BuildDependencyList()
        result = obj.add_file_dependency(path_name)
        self.assertIsNone(result)

        path_name = os.path.join("network", "tcp_echo", "settings.json.save")
        logging.info("get_file_dependency_list(\"{}\") doesn't exist".format(path_name))
        obj = BuildDependencyList()
        result = obj.add_file_dependency(path_name)
        self.assertIsNone(result)

        path_name = os.path.join("network", "tcp_echo", "tcp_echo.py")
        expect = ['cp_lib.cp_logging', 'cp_lib.hw_status', 'cp_lib.load_settings']
        logging.info("get_file_dependency_list(\"{}\") doesn't exist".format(path_name))
        obj = BuildDependencyList()
        result = obj.add_file_dependency(path_name)
        self.assertEqual(result, expect)

        # "cp_lib.clean_ini": [],
        path_name = os.path.join("cp_lib", "clean_ini.py")
        logging.info("get_file_dependency_list(\"{}\") test a built-in".format(path_name))
        expect = []
        obj = BuildDependencyList()
        result = obj.add_file_dependency(path_name)
        self.assertEqual(result, expect)

        # "cp_lib.cp_logging": ["cp_lib.hw_status", "cp_lib.load_settings"],
        path_name = os.path.join("cp_lib", "cp_logging.py")
        logging.info("get_file_dependency_list(\"{}\") test a built-in".format(path_name))
        expect = ["cp_lib.hw_status", "cp_lib.load_settings", "cp_lib.clean_ini", "cp_lib.split_version"]
        obj = BuildDependencyList()
        result = obj.add_file_dependency(path_name)
        self.assertEqual(result, expect)

        # "cp_lib.hw_status": [],
        path_name = os.path.join("cp_lib", "hw_status.py")
        logging.info("get_file_dependency_list(\"{}\") test a built-in".format(path_name))
        expect = []
        obj = BuildDependencyList()
        result = obj.add_file_dependency(path_name)
        self.assertEqual(result, expect)

        # "cp_lib.load_settings": ["cp_lib.clean_ini", "cp_lib.split_version"],
        path_name = os.path.join("cp_lib", "load_settings.py")
        logging.info("get_file_dependency_list(\"{}\") test a built-in".format(path_name))
        expect = ["cp_lib.clean_ini", "cp_lib.split_version"]
        obj = BuildDependencyList()
        result = obj.add_file_dependency(path_name)
        self.assertEqual(result, expect)

        # "cp_lib.split_version": []
        path_name = os.path.join("cp_lib", "split_version.py")
        logging.info("get_file_dependency_list(\"{}\") test a built-in".format(path_name))
        expect = []
        obj = BuildDependencyList()
        result = obj.add_file_dependency(path_name)
        self.assertEqual(result, expect)

        return

if __name__ == '__main__':
    # logging.basicConfig(level=logging.INFO)
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
