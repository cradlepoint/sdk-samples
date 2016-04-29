"""
Simple Load settings, assume is JSON only. Follow this logic:
1) if settings.json exists in root directory, load it and STOP
2) else
2a)   load ./config/settings
2b)   load ./{project}/settings
"""
import json
import logging
import os
import sys

from cp_lib.load_settings_json import DEF_GLOBAL_DIRECTORY, DEF_SETTINGS_FILE_NAME, DEF_JSON_EXT, SECTION_NAME_LIST, \
    SECTION_APPLICATION, SECTION_LOGGING, SECTION_ROUTER_API
from make import EXIT_CODE_BAD_FORM

DEF_INI_EXT = ".ini"
DEF_SAVE_EXT = ".save"

# set to None to suppress adding comments to the settings.json files
ADD_JSON_COMMENT_KEY = "_comment"


def load_sdk_ini_as_dict(app_dir_path=None, file_name=None):
    """
    Follow Router SDK Design:
     1) first load ./config/settings.ini - if it exists
     2) second load /{project}/settings.ini - if it exists, and smartly merge into .config values

    :param str app_dir_path: the base directory of our project, like network/tcp_echo/
    :param str file_name: pass in alternative name - mainly for testing, else use DEF_FILE_NAME
    :return dict:
    """
    if file_name is None:
        file_name = DEF_SETTINGS_FILE_NAME

    # start by loading the globals or ./config/settings.ini
    ini_name = os.path.join(DEF_GLOBAL_DIRECTORY, file_name + DEF_INI_EXT)
    logging.debug("Load Global Settings from {}".format(ini_name))
    _sets = load_ini_as_dict(ini_name)

    if app_dir_path is not None:
        ini_name = os.path.join(app_dir_path, file_name + DEF_INI_EXT)
        if os.path.exists(ini_name):
            # load the app-specific settings, manually handle file - avoid potential path issues ..
            logging.debug("Load App Project Settings from {}".format(ini_name))
            _sets = load_ini_as_dict(ini_name, _sets)
        else:
            logging.debug("There is no settings file {}".format(ini_name))

    return _sets


def load_ini_as_dict(ini_name, pre_dict=None):
    """
    - Locate and read a single INI
    - force our expected sections headers to lower case
    - if pre_dict exists, walk through and smartly 'merge' new data over old

    :param str ini_name: relative directory path to the INI file (which may NOT exist)
    :param dict pre_dict: any existing settings, which we want new INI loaded data to over-write
    :return dict: the prepared data as dict
    """
    import configparser

    if not os.path.isfile(ini_name):
        # if this INI file DOES NOT exist, return - existence is not this module's responsibility!
        # logging.debug("INI file {} does NOT exist".format(ini_path))
        return pre_dict

    # LOAD IN THE INI FILE, using the Python library
    config = configparser.ConfigParser()
    # READ indirectly, as config.read() tries to open cp_lib/config/file.ini, not config/file.ini
    file_han = open(ini_name, "r")
    try:
        config.read_file(file_han)

    except configparser.DuplicateOptionError as e:
        logging.error(str(e))
        logging.error("Aborting MAKE")
        sys.exit(EXIT_CODE_BAD_FORM)

    finally:
        file_han.close()
    # logging.debug("  Sections:{}".format(config.sections()))

    # convert INI/ConfigParser to Python dictionary
    settings = {}
    for section in config.sections():

        section_tag = section.lower()
        if section_tag not in SECTION_NAME_LIST:
            # we make sure 'expected' sections are lower case, otherwise allow any case-mix
            # example: [application] must be lower-case, but [TcpStuff] is fine
            section_tag = section

        settings[section_tag] = {}
        # note: 'section' is the old possibly mixed case name; section_tag might be lower case
        for key, val in config.items(section):
            settings[section_tag][key] = val

    # add OPTIONAL comments to the file - set ADD_JSON_COMMENT_KEY = None to disable
    if ADD_JSON_COMMENT_KEY is not None:
        comments = {
            SECTION_APPLICATION: "Settings for the application being built.",
            SECTION_LOGGING: "Settings for the application debug/syslog/logging function.",
            SECTION_ROUTER_API: "Settings to allow accessing router API in development mode."
        }
        for section in comments:
            if section in settings:
                settings[section][ADD_JSON_COMMENT_KEY] = comments[section]

    if pre_dict is None:
        # no pre-existing data, then return as-is
        return settings

    # else smartly merge new data into old, not 'replacing' sections
    assert isinstance(pre_dict, dict)
    for key, data in settings.items():
        if key in pre_dict:
            # update/merge existing section (not replace)
            pre_dict[key].update(data)
        else:
            # set / replace new sections
            pre_dict[key] = data

    return pre_dict


def copy_config_ini_to_json():
    # copy the globals or ./config/settings.ini to ./config/settings.json
    name = os.path.join(DEF_GLOBAL_DIRECTORY, DEF_SETTINGS_FILE_NAME + DEF_INI_EXT)
    logging.debug("Copy Global Settings from INI to JSON ")
    _sets = load_ini_as_dict(name)

    name = os.path.join(DEF_GLOBAL_DIRECTORY, DEF_SETTINGS_FILE_NAME + DEF_JSON_EXT)
    save_root_settings_json(_sets, name)
    return


def save_root_settings_json(sets, file_name=None):
    """

    :param sets:
    :param file_name:

    :param dict sets: the settings as Python dict
    :param str file_name: pass in alternative name - mainly for testing, else use DEF_FILE_NAME
    :return:
    """
    if file_name is None:
        file_name = DEF_SETTINGS_FILE_NAME + DEF_JSON_EXT

    logging.info("Save settings to {}".format(file_name))
    lines = json.dumps(sets, indent=4, sort_keys=True)
    file_han = open(file_name, 'wb')
    for line in lines:
        # cooked = line + '\n'
        file_han.write(line.encode())
    file_han.close()
