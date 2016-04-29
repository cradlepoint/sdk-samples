"""
Fancier, "Load settings", including converting a "settings.ini" into
settings.json

The Router SDK Sample design is the following:
1) confirm ./{project}/settings.ini exists, and there is [application] section
2) if ./{project}/settings.ini, [application] section lacks "uuid", add one
3) if ./{project}/settings.ini, [application] section lacks "version", add 1.0
4) if make has '-i' option, the open ./{project}/settings.ini and increment
                                "version" minor value
5) look for ./config/settings.ini, if found read this in
6) look for ./{project}/settings.ini, read this in, smartly over-laying
                                sections from ./config
7) return the final settings as python dictionary (not saved!)
"""
import logging
import os
import os.path
import shutil

from cp_lib.load_settings_ini import DEF_SETTINGS_FILE_NAME, DEF_INI_EXT, \
    load_sdk_ini_as_dict, SECTION_APPLICATION, SECTION_LOGGING, \
    SECTION_ROUTER_API

DEF_SAVE_EXT = ".save"

DEF_VERSION = "1.0"


def validate_project_settings(app_dir_path, increment_version=False):
    """
    1) Confirm a project settings.ini exists, else throw exception
    2) confirm it has an [application] section, else throw exception
    3) confirm [application] section has "uuid", add random one if not
    4) confirm [application] section has "version", add "1.0" if not
    5) if increment_version is True, then increment MINOR value of a
        pre-existing version

    :param str app_dir_path: the subdirectory path to the settings.ini file
    :param bool increment_version: if True, increment MINOR value from version
    :return None:
    """

    # 1) Confirm a project settings.ini exists, else throw exception
    if not os.path.isdir(app_dir_path):
        # validate that {project}.settings.ini exists
        raise FileNotFoundError("SDK app directory not found.")

    # 2) confirm it has an [application] section, else throw exception
    file_name = os.path.join(app_dir_path, DEF_SETTINGS_FILE_NAME +
                             DEF_INI_EXT)
    logging.debug("Confirm {} has [application] section".format(file_name))
    if not _confirm_has_application_section(file_name):
        raise KeyError("SDK app settings.ini requires [application] section")

    # 3) confirm [application] section has "uuid", add random one if not
    logging.debug("Confirm {} has 'uuid' value".format(file_name))
    fix_up_uuid(file_name)

    # 4) confirm [application] section has "version", add "1.0" if not
    # 5) if increment_version is True, then increment MINOR value of a
    #       pre-existing version
    logging.debug("Confirm {} has 'version' value".format(file_name))
    increment_app_version(file_name, increment_version)

    return


def load_settings(app_dir_path=None, file_name=None):
    """

    :param str app_dir_path: relative directory path to the app directory
                             (ignored if None)
    :param str file_name: pass in alternative name - mainly for testing,
                          else use DEF_FILE_NAME
    :return dict: the settings as Python dictionary
    """
    if file_name is None:
        file_name = DEF_SETTINGS_FILE_NAME

    _sets = load_sdk_ini_as_dict(app_dir_path, file_name)

    # handle any special processing
    if SECTION_APPLICATION in _sets:
        _sets = _special_section_application(_sets)
    else:
        raise KeyError("Application config requires an [application] section")

    if SECTION_LOGGING in _sets:
        _sets = _special_section_logging(_sets)
    # this doesn't need to exist

    if SECTION_ROUTER_API in _sets:
        _sets = _special_section_router_api(_sets)
    # this doesn't need to exist

    return _sets


def _special_section_application(sets):
    """Handle any special processing for the [application] INI section"""
    if "name" not in sets[SECTION_APPLICATION]:
        raise KeyError("config [application] section requires 'name' setting")

    if "path" not in sets[SECTION_APPLICATION]:
        # if no path, assume matches NAME setting
        sets[SECTION_APPLICATION]["path"] = sets[SECTION_APPLICATION]["name"]

    return sets


def _special_section_logging(sets):
    """Handle any special processing for the [logging] INI section"""
    return sets


def _special_section_router_api(sets):
    """Handle any special processing for the [router_api] INI section"""

    # if we have password, but no USER, then assume user is default of "admin"
    if "password" in sets[SECTION_ROUTER_API] and \
            "user_name" not in sets[SECTION_ROUTER_API]:
        sets[SECTION_ROUTER_API]["user_name"] = "admin"

    return sets


def _confirm_has_application_section(ini_name):
    """
    Run through the text file, confirm it has [application] section.
    Although we desire ONLY [application], we allow INI to have
    [Application] or any case-mix

    Throw FileNotFoundError is the file doesn't exist!

    :param str ini_name: the relative file name of the INI to test
    :return bool: T if [application] was found, else F
    """
    if not os.path.isfile(ini_name):
        raise FileNotFoundError(
            "Project INI file missing:{}".format(ini_name))

    # logging.debug("_confirm_has_application_section({})".format(ini_name))

    file_han = open(ini_name, "r")
    try:
        for line in file_han:
            if _line_find_section(line, 'application'):
                # logging.debug("Section [application] was found")
                return True
    finally:
        file_han.close()

    return False


def _line_find_section(line, name):
    """
    Given a line from file, confirm if this line is like [section],
    ignoring case

    :param line name: the source line
    :param str name: the section name desired
    :return bool:
    """
    if line is None:
        return False

    # remove all white space
    line = line.strip()
    if len(line) < 2 or line[0] != '[':
        # then line is not [section], so no need to even compare
        return False

    return line.lower().startswith('[' + name.lower() + ']')


def fix_up_uuid(ini_name, use_uuid=None, backup=False):
    """
    Given a new UUID, write into INI (if it exists)

    :param str ini_name: the INI file name (assume exists at this point)
    :param str use_uuid: optional UUID string to use
    :param bool backup: T to backup INI
    :return:
    """
    global _uuid

    def _do_my_tweak(old_line):
        """
        Create our special line

        :param old_line:
        :return str: the line to include in file
        """
        import uuid
        global _uuid

        if old_line is None or old_line == "":
            # we hit end-of-section [application] without finding "uuid"
            logging.debug("Fix UUID - adding random, because it is missing")
            if use_uuid is None:
                _uuid = uuid.uuid4()
            return "uuid=%s\n" % _uuid

        elif use_uuid is None:
            # logging.debug("Fix UUID - keep it as is")
            return old_line + '\n'

        else:  # we are replacing the line, but don't care about the old
            return "uuid=%s\n" % uuid.uuid4()

    _uuid = use_uuid

    # logging.debug("Fix UUID - try INI as {}".format(ini_name))
    _find_item_in_app_section(ini_name, 'uuid', _do_my_tweak, backup)
    return


def increment_app_version(ini_name, incr_version=False, backup=False):
    """
    Find an existing "version" string as major/minor and incr it

    :param str ini_name:
    :param bool incr_version:
    :param bool backup: T to backup INI
    :return:
    """
    global _incr_ver

    def _do_my_tweak(old_line):
        """
        Create our special line

        :param old_line:
        :return str: the line to include in file
        """
        global _incr_ver
        from cp_lib.split_version import split_version_string

        if old_line is None or old_line == "":
            # we hit end-of-section [application] without finding "version"
            # logging.debug("Fix Version - adding, because it is missing")
            version = DEF_VERSION

        elif _incr_ver:
            # we have old line, so parse it in & incr
            offset = old_line.find("=")
            assert offset >= 0
            value = old_line[offset + 1:].strip()
            major, minor = split_version_string(value)
            minor += 1
            version = "%d.%d" % (major, minor)
            logging.debug(
                "Fix Version - increment from {} to {}".format(value, version))

        else:
            # logging.debug("Fix Version - use old line({})".format(old_line))
            # there is old line, but we're NOT incrementing
            return old_line + '\n'

        # here we are changing the old line - either adding, or incrementing
        return "version=%s\n" % version

    _incr_ver = incr_version

    # then exists, first walk through, find [application]
    # logging.debug("Increment APP version - try INI as {}".format(ini_name))
    _find_item_in_app_section(ini_name, 'version', _do_my_tweak, backup)

    return


def _find_item_in_app_section(ini_name, set_name, process, backup=False):
    """
    Scan INI file for [application] section, seek either the requested item,
    or end of the app section, call 'process' to explain what to do

    :param str ini_name: the INI file name (assume exists at this point)
    :param str set_name:
    :param process: the process call-back
    :param bool backup: T to backup INI
    :return:
    """
    # logging.debug("Seek tag({}) in {}".format(set_name, ini_name))
    state_start = 0
    state_in_app = 1
    state_past = 2

    state = state_start

    lines = []

    file_han = open(ini_name, "r")
    for line in file_han:

        if state == state_start:
            # seek the [application] section - we have not found yet
            if _line_find_section(line, SECTION_APPLICATION):
                # logging.debug("Found [application]")
                state = state_in_app

        elif state == state_in_app:
            # we have seen the [application] section, so seek 'set_name'
            #   or end of section
            clean_line = line.strip()
            if len(clean_line) < 1:
                result = process(None)
                # logging.debug(
                #   "Hit end of section, add line ({})".format(result.strip()))
                lines.append(result)
                state = state_past
                # continue down & append the blank line

            elif clean_line.startswith(set_name):
                result = process(clean_line)
                # logging.debug(
                #   "Found {}, add line ({})".format(set_name, result.strip()))
                lines.append(result)
                state = state_past
                continue  # loop up, no append of old data

        else:  # we are past our spot
            pass

        lines.append(line)

    # handle if we hit EOF before blank line - if not, we should be in
    #   state 'state_past'
    if state == state_in_app:
        result = process(None)
        # logging.debug("Hit end of file, add line ({})".format(result))
        lines.append(result)

    file_han.close()

    if backup:
        shutil.copyfile(ini_name, os.path.join(ini_name + DEF_SAVE_EXT))

    # rewrite the file - force to Linux
    file_han = open(ini_name, 'wb')
    for line in lines:
        line = line.strip() + '\n'
        file_han.write(line.encode())
    file_han.close()

    return
