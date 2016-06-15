"""
Load Router API "status/product_info" into settings.
"""
import json
import logging
import os.path

from cp_lib.load_settings_json import DEF_GLOBAL_DIRECTORY
from cp_lib.cs_client import CradlepointClient
from cp_lib.app_base import CradlepointRouterOffline

SECTION_PRODUCT_INFO = "product_info"


def load_product_info(sets, client, file_name=None):
    """
    Load Router API "status/product_info" into settings.

    $ cat status/product_info
    {
        "company_name": "Cradlepoint, Inc.",
        "company_url": "http://cradlepoint.com",
        "copyright": "Cradlepoint, Inc. 2016",
        "mac0": "00:30:44:1a:81:9c",
        "manufacturing": {
            "board_ID": "050200",
            "mftr_date": "20141204",
            "serial_num": "MM140459400193"
        },
        "product_name": "IBR1150LPE"
    }

    You have 3 ways to do this. (code does not validate the contents)

    1) if there is a [product_info] section in ./config/settings.ini, then
       this is used and no access to the router is attempted. However,
       this blocks use of the status/product_info/manufacturing data - it
       WILL not be included as of Mar-2016, we don't support sub-sections.

    2) else, if there is a file named ./config/product_info.json (all
       lower case), then this is opened and loaded, merged into settings.

    3) else, if section [router_api] is correct, then REQUESTS is used
       to fetch the actual value, which is merged into
       settings, accessed as self.settings["product_info"].

    :param dict sets: the settings existing before the call
    :param CradlepointClient client: either local or remote cs_client handler
    :param str file_name: for testing, use a name OTHER than default method #2
    :return dict: the merged settings
    """

    if SECTION_PRODUCT_INFO in sets:
        logging.debug("method #1 - is already in ./config/settings.ini")
        return sets

    # check for a file such as "./config/product_info.json"
    if file_name is None:
        file_name = os.path.join(DEF_GLOBAL_DIRECTORY, "product_info.json")

    if os.path.exists(file_name):
        # method #2 - the file exists. Do this indirectly to avoid some
        # Win/Linux relative path issues
        logging.debug("method #2 - load file {}".format(file_name))
        _file_han = open(file_name, "r")
        sets[SECTION_PRODUCT_INFO] = json.load(_file_han)
        _file_han.close()
        return sets

    # is still here, we'll do it the 'hard way' via Router API
    logging.debug("method #3 - use CS Client")
    assert isinstance(client, CradlepointClient)

    save_state = client.show_rsp
    client.show_rsp = False
    result = client.get("status/product_info")
    client.show_rsp = save_state

    if result is None:
        raise CradlepointRouterOffline(
            "Aborting; Router({}) is not accessible".format(client.router_ip))

    if isinstance(result, str):
        result = json.loads(result)

    sets[SECTION_PRODUCT_INFO] = result
    return sets


def split_product_name(value):
        """
        Given a product name like IBR1100, IBR1100LPE, or 2100, split
        into the et the product model as string

        :param str value: the product name
        :return: IBR1100LPE would return as ("IBR1100", "LPE", True)
        :rtype: str, str, bool
        """
        option_start = None
        wifi_offset = 0

        # then reduce/clean up
        value = value.upper()
        if value[0] == 'I':
            # handle the IBR line
            if value[3] == '1':
                # could be 1100/1150, raw might be "IBR1100LPE"
                option_start = 7
                wifi_offset = 5

            elif value[3] == '6':
                # could be 600/650
                if len(value) >= 7 and value[6] == 'B':
                    # could be 600B/650B
                    option_start = 7
                    wifi_offset = 4
                else:  # else just 600/650
                    option_start = 6
                    wifi_offset = 4

            elif value[3] == '3':
                # there is only one base model, but handle IBR300 anyway
                option_start = 6
                wifi_offset = 4

        elif value[0] == 'C':
            # handle the CBA line
            if value[3] == '8':
                # there is only one base model, but handle IBR800 anyway
                option_start = 6
                wifi_offset = 4

        elif value[0] == 'A':
            # handle the AER line - we assume all are AER xxxx
            option_start = 7
            wifi_offset = 5

        elif value[0] == '2':
            # handle the odd-ball AER2100
            if value.startswith("21"):
                value = "AER" + value
            option_start = 7
            wifi_offset = 5

        if option_start is None:
            raise ValueError("Unsupported Model:{}".format(value))

        base = value[:option_start]
        options = value[option_start:]
        wifi = value[wifi_offset] != "5"

        return base, options, wifi
