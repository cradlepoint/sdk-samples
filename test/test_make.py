# Test the Monnit Protocol code

import unittest
import logging
import os.path
# noinspection PyUnresolvedReferences
import shutil

import make


class TestMake(unittest.TestCase):

    def test_confirm_dir_exists(self):

        maker = make.TheMaker()

        # just do the ./build, as it can be empty by default
        test_name = "build"

        # make sure it doesn't exist as file or dir
        maker._remove_name_no_error(test_name)

        # 1st confirm, will create as directory
        self.assertFalse(os.path.exists(test_name))
        maker._confirm_dir_exists(test_name, "Test dir")
        self.assertTrue(os.path.exists(test_name))
        self.assertTrue(os.path.isdir(test_name))

        # 2nd confirm, will leave alone
        maker._confirm_dir_exists(test_name, "Test dir")
        self.assertTrue(os.path.exists(test_name))
        self.assertTrue(os.path.isdir(test_name))

        # make sure it doesn't exist as file or dir
        test_save_name = test_name + maker.SDIR_SAVE_EXT
        maker._remove_name_no_error(test_name)
        maker._remove_name_no_error(test_save_name)

        self.assertFalse(os.path.exists(test_name))
        self.assertFalse(os.path.exists(test_save_name))

        # create a dummy file, should cause to be renamed test_save_name
        file_handle = open(test_name, "w")
        file_handle.write("Hello there!")
        file_handle.close()

        # so now, common file 'blocks' our directory; we'll rename to .save & make anyway
        self.assertTrue(os.path.exists(test_name))
        self.assertFalse(os.path.exists(test_save_name))

        maker._confirm_dir_exists(test_name, "Test blocked dir")

        self.assertTrue(os.path.exists(test_name))
        self.assertTrue(os.path.isdir(test_name))

        self.assertTrue(os.path.exists(test_save_name))
        self.assertTrue(os.path.isfile(test_save_name))

        # we just leave ./build/ existing - is okay
        maker._remove_name_no_error(test_save_name)

        return

    def test_install_sh(self):

        def _make_temp_file(file_name: str):
            """Given file name (path), make file containing the name"""
            _han = open(file_name, 'w')
            _han.write(file_name)
            _han.close()
            return

        def _validate_contents(file_name: str, expected: str):
            """Confirm file contains 'expected' data"""
            _han = open(file_name, 'r')
            _data = _han.read()
            _han.close()
            return _data == expected

        # quick test of the _make_temp_file and _validate_contents
        data = os.path.join("test", "shiny_shoes.txt")
        _make_temp_file(data)
        self.assertTrue(_validate_contents(data, data))
        os.remove(data)

        maker = make.TheMaker()
        maker.load_settings_json()

        test_install_name = "test_install.sh"
        maker.force_settings_dict({'name': 'tcp_echo'})
        maker.force_settings_dict({'path': os.path.join("network", "tcp_echo")})

        app_file_name = os.path.join(maker.get_app_path(), test_install_name)
        cfg_file_name = os.path.join(make.SDIR_CONFIG, test_install_name)
        dst_file_name = os.path.join(make.SDIR_BUILD, test_install_name)

        # start, make sure none exist
        maker._remove_name_no_error(app_file_name)
        maker._remove_name_no_error(cfg_file_name)
        maker._remove_name_no_error(dst_file_name)

        # test fresh creation (& re-creation) a default INSTALL file - no source exists
        self.assertFalse(os.path.exists(app_file_name))
        self.assertFalse(os.path.exists(cfg_file_name))
        self.assertFalse(os.path.exists(dst_file_name))

        maker.create_install_sh(test_install_name)
        self.assertFalse(os.path.exists(app_file_name))
        self.assertFalse(os.path.exists(cfg_file_name))
        self.assertTrue(os.path.exists(dst_file_name))

        maker.create_install_sh(test_install_name)
        self.assertFalse(os.path.exists(app_file_name))
        self.assertFalse(os.path.exists(cfg_file_name))
        self.assertTrue(os.path.exists(dst_file_name))

        # start, make sure none exist
        maker._remove_name_no_error(app_file_name)
        maker._remove_name_no_error(cfg_file_name)
        maker._remove_name_no_error(dst_file_name)

        # now try using the config file (no dev supplies app file)
        _make_temp_file(cfg_file_name)

        self.assertFalse(os.path.exists(app_file_name))
        self.assertTrue(os.path.exists(cfg_file_name))
        self.assertFalse(os.path.exists(dst_file_name))

        maker.create_install_sh(test_install_name)
        self.assertFalse(os.path.exists(app_file_name))
        self.assertTrue(os.path.exists(cfg_file_name))
        self.assertTrue(os.path.exists(dst_file_name))
        self.assertTrue(_validate_contents(dst_file_name, cfg_file_name))

        # start, make sure none exist
        maker._remove_name_no_error(app_file_name)
        maker._remove_name_no_error(cfg_file_name)
        maker._remove_name_no_error(dst_file_name)

        # now try using the dev supplies file, assume no global config file
        _make_temp_file(app_file_name)

        self.assertTrue(os.path.exists(app_file_name))
        self.assertFalse(os.path.exists(cfg_file_name))
        self.assertFalse(os.path.exists(dst_file_name))

        maker.create_install_sh(test_install_name)
        self.assertTrue(os.path.exists(app_file_name))
        self.assertFalse(os.path.exists(cfg_file_name))
        self.assertTrue(os.path.exists(dst_file_name))
        self.assertTrue(_validate_contents(dst_file_name, app_file_name))

        # repeat, but this time global config exists & is ignored
        maker._remove_name_no_error(dst_file_name)
        _make_temp_file(cfg_file_name)

        self.assertTrue(os.path.exists(app_file_name))
        self.assertTrue(os.path.exists(cfg_file_name))
        self.assertFalse(os.path.exists(dst_file_name))

        maker.create_install_sh(test_install_name)
        self.assertTrue(os.path.exists(app_file_name))
        self.assertTrue(os.path.exists(cfg_file_name))
        self.assertTrue(os.path.exists(dst_file_name))
        self.assertTrue(_validate_contents(dst_file_name, app_file_name))

        # start, make sure none exist
        maker._remove_name_no_error(app_file_name)
        maker._remove_name_no_error(cfg_file_name)
        maker._remove_name_no_error(dst_file_name)

        return

    def test_start_sh(self):

        maker = make.TheMaker()
        maker.load_settings_json()

        def _make_temp_file(file_name: str):
            """Given file name (path), make file containing the name"""
            _han = open(file_name, 'w')
            _han.write(file_name)
            _han.close()
            return

        def _validate_contents(file_name: str, expected: str):
            """Confirm file contains 'expected' data"""
            _han = open(file_name, 'r')
            _data = _han.read()
            _han.close()
            return _data == expected

        # quick test of the _make_temp_file and _validate_contents
        data = os.path.join("test", "shiny_shoes.txt")
        _make_temp_file(data)
        self.assertTrue(_validate_contents(data, data))
        os.remove(data)

        maker = make.TheMaker()
        maker.load_settings_json()

        test_install_name = "test_start.sh"
        maker.force_settings_dict({'name': 'tcp_echo'})
        maker.force_settings_dict({'path': os.path.join("network", "tcp_echo")})

        app_file_name = os.path.join(maker.get_app_path(), test_install_name)
        cfg_file_name = os.path.join(make.SDIR_CONFIG, test_install_name)
        dst_file_name = os.path.join(make.SDIR_BUILD, test_install_name)

        # start, make sure none exist
        maker._remove_name_no_error(app_file_name)
        maker._remove_name_no_error(cfg_file_name)
        maker._remove_name_no_error(dst_file_name)

        # test fresh creation (& re-creation) a default INSTALL file - no source exists
        self.assertFalse(os.path.exists(app_file_name))
        self.assertFalse(os.path.exists(cfg_file_name))
        self.assertFalse(os.path.exists(dst_file_name))

        maker.create_install_sh(test_install_name)
        self.assertFalse(os.path.exists(app_file_name))
        self.assertFalse(os.path.exists(cfg_file_name))
        self.assertTrue(os.path.exists(dst_file_name))

        maker.create_install_sh(test_install_name)
        self.assertFalse(os.path.exists(app_file_name))
        self.assertFalse(os.path.exists(cfg_file_name))
        self.assertTrue(os.path.exists(dst_file_name))

        # start, make sure none exist
        maker._remove_name_no_error(app_file_name)
        maker._remove_name_no_error(cfg_file_name)
        maker._remove_name_no_error(dst_file_name)

        # now try using the config file (no dev supplies app file)
        _make_temp_file(cfg_file_name)

        self.assertFalse(os.path.exists(app_file_name))
        self.assertTrue(os.path.exists(cfg_file_name))
        self.assertFalse(os.path.exists(dst_file_name))

        maker.create_install_sh(test_install_name)
        self.assertFalse(os.path.exists(app_file_name))
        self.assertTrue(os.path.exists(cfg_file_name))
        self.assertTrue(os.path.exists(dst_file_name))
        self.assertTrue(_validate_contents(dst_file_name, cfg_file_name))

        # start, make sure none exist
        maker._remove_name_no_error(app_file_name)
        maker._remove_name_no_error(cfg_file_name)
        maker._remove_name_no_error(dst_file_name)

        # now try using the dev supplies file, assume no global config file
        _make_temp_file(app_file_name)

        self.assertTrue(os.path.exists(app_file_name))
        self.assertFalse(os.path.exists(cfg_file_name))
        self.assertFalse(os.path.exists(dst_file_name))

        maker.create_install_sh(test_install_name)
        self.assertTrue(os.path.exists(app_file_name))
        self.assertFalse(os.path.exists(cfg_file_name))
        self.assertTrue(os.path.exists(dst_file_name))
        self.assertTrue(_validate_contents(dst_file_name, app_file_name))

        # repeat, but this time global config exists & is ignored
        maker._remove_name_no_error(dst_file_name)
        _make_temp_file(cfg_file_name)

        self.assertTrue(os.path.exists(app_file_name))
        self.assertTrue(os.path.exists(cfg_file_name))
        self.assertFalse(os.path.exists(dst_file_name))

        maker.create_install_sh(test_install_name)
        self.assertTrue(os.path.exists(app_file_name))
        self.assertTrue(os.path.exists(cfg_file_name))
        self.assertTrue(os.path.exists(dst_file_name))
        self.assertTrue(_validate_contents(dst_file_name, app_file_name))

        # start, make sure none exist
        maker._remove_name_no_error(app_file_name)
        maker._remove_name_no_error(cfg_file_name)
        maker._remove_name_no_error(dst_file_name)

        return


if __name__ == '__main__':
    # logging.basicConfig(level=logging.INFO)
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
