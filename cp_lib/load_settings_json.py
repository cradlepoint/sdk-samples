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

DEF_GLOBAL_DIRECTORY = "config"
DEF_SETTINGS_FILE_NAME = "settings"
DEF_JSON_EXT = ".json"

# The expected section headers in SETTINGS.INI - we don't technically need here, but place
# here to avoid needing to add the load_settings_ini file to our SDK upload TAR.GZIP
SECTION_APPLICATION = "application"
SECTION_LOGGING = "logging"
SECTION_ROUTER_API = "router_api"
SECTION_NAME_LIST = (SECTION_APPLICATION, SECTION_LOGGING, SECTION_ROUTER_API)


def load_settings_json(app_dir_path=None, global_dir_path=None, file_name=None):
    """
    Simple Load settings, assume is JSON only. Follow this logic:
    1) if settings.json exists in root directory, load it and STOP
    2) else
    2a)   load ./config/settings.json
    2b)   load ./{project}/settings.json

    :param str app_dir_path: relative directory path to the app directory (ignored if None)
    :param str global_dir_path: relative directory path to the global settings (assume 'config' if)
    :param str file_name: pass in alternative name - mainly for testing, else use DEF_FILE_NAME
    :return dict: the settings as Python dictionary
    """
    if file_name is None:
        # this is normally true - only expect an alternative file name during testing
        file_name = DEF_SETTINGS_FILE_NAME

    if file_name.endswith(DEF_JSON_EXT):
        # if filename ends in .json, chop it off
        file_name = file_name[:len(DEF_JSON_EXT)]

    # LOGIC 1 - see if the file exists in ROOT, if so load & exit
    json_name = file_name + DEF_JSON_EXT
    if os.path.exists(json_name):
        # this is normal form
        settings = {}
        return _smart_merge_sets(json_name, settings)

    if global_dir_path is None:
        # if None, swap in default, which may be like ./config
        global_dir_path = DEF_GLOBAL_DIRECTORY

    # save the paths
    settings = {"app_dir": app_dir_path, "glob_dir": global_dir_path, "base_name": file_name}

    # LOGIC 2A - try the base/shared settings
    json_name = os.path.join(global_dir_path, file_name + DEF_JSON_EXT)
    if os.path.exists(json_name):
        # load the global settings, manually handle the file - avoid potential path issues
        # such as with ConfigParser
        logging.info("Load Global Settings from {}".format(json_name))
        settings = _smart_merge_sets(json_name, settings)
    else:
        logging.debug("There is no settings file {}".format(json_name))

    # LOGIC 2B - add/merge in the project settings
    if app_dir_path is not None:
        json_name = os.path.join(app_dir_path, file_name + DEF_JSON_EXT)
        if os.path.exists(json_name):
            # load the app-specific settings, manually handle file - avoid potential path issues...
            logging.info("Load App Settings from {}".format(json_name))
            settings = _smart_merge_sets(json_name, settings)
        else:
            logging.debug("There is no settings file {}".format(json_name))
    # else SKIP the app, because not important or defined yet

    return settings


def _smart_merge_sets(source_name, existing_sets):
    """
    Merge the CONFIG or APP settings, without displacing.

    Just 'update()' dict would cause new [section] to 100% replace the original, but we want to MERGE
    not replace. Note: we only handle the first level sections.

    :param str source_name: the file to load JSON data from
    :param dict existing_sets: the existing settings, with is merged from file. File settings over-write existing
    :return dict:
    """
    _file_han = open(source_name, "r")
    sets = json.load(_file_han)
    assert isinstance(sets, dict)
    for key, data in sets.items():
        if key in existing_sets:
            existing_sets[key].update(data)
        else:
            existing_sets[key] = data
    _file_han.close()
    return existing_sets
