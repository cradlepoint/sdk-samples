"""
Load Router API "status/fw_info" into settings.
"""
import json
import logging
import os.path
import sys

from cp_lib.load_settings_json import DEF_GLOBAL_DIRECTORY
from cp_lib.cs_client import CradlepointClient

SECTION_FW_INFO = "fw_info"


def load_firmware_info(sets, client, file_name=None):
    """
    Load Router API "status/fw_info" into settings.

    $ cat status/fw_info
    'fw_info': {
        'major_version': 6,
        'fw_update_available': False,
        'upgrade_patch_version': 0,
        'upgrade_minor_version': 0,
        'build_version': '0310fce',
        'build_date': 'WedJan1300: 23: 15MST2016',
        'minor_version': 1,
        'upgrade_major_version': 0,
        'manufacturing_upgrade': False,
        'build_type': 'FIELD[build]',
        'custom_defaults': False,
        'patch_version': 0
    },

    You have 3 ways to do this. ( The code does not validate the contents )

    1) if there is a [fw_info] section in ./config/settings.ini, then this
       is used and no access to the router is attempted.

    2) else, if there is a file named ./config/fw_info.json (all lower case),
       then this is opened and loaded, merged into settings.

    3) else, if section [router_api] is correct, then REQUESTS is used
       to fetch the actual value, which is merged into settings, accessed
       as self.settings["fw_info"].

    :param dict sets: the settings existing before the call
    :param CradlepointClient client: either local or remote cs_client handler
    :param str file_name: for testing, use name OTHER than default, method #2
    :return dict: the merged settings
    """
    from cp_lib.split_version import sets_version_to_str

    if SECTION_FW_INFO in sets:
        logging.debug("method #1 - is already in ./config/settings.ini")
        sets[SECTION_FW_INFO]["version"] = sets_version_to_str(sets,
                                                               SECTION_FW_INFO)
        return sets

    # check for a file such as "./config/fw_info.json"
    if file_name is None:
        file_name = os.path.join(DEF_GLOBAL_DIRECTORY, "fw_info.json")

    if os.path.exists(file_name):
        # method #2 - the file exists. Do this indirectly to avoid some
        # Win/Linux relative path issues
        logging.debug("method #2 - load file {}".format(file_name))
        _file_han = open(file_name, "r")
        sets[SECTION_FW_INFO] = json.load(_file_han)
        _file_han.close()
        sets[SECTION_FW_INFO]["version"] = sets_version_to_str(sets,
                                                               SECTION_FW_INFO)
        return sets

    # is still here, we'll do it the 'hard way' via Router API
    logging.debug("method #3 - use CS Client")
    assert isinstance(client, CradlepointClient)

    save_state = client.show_rsp
    client.show_rsp = False
    result = client.get("status/fw_info")
    client.show_rsp = save_state

    if result is None:
        logging.error("Aborting - Router({}) is not accessible".format(
            client.router_ip))
        sys.exit(-1)

    if isinstance(result, str):
        result = json.loads(result)

    sets[SECTION_FW_INFO] = result
    sets[SECTION_FW_INFO]["version"] = sets_version_to_str(sets,
                                                           SECTION_FW_INFO)
    return sets
