# create Cradlepoint's recommended logger instance

import logging
import logging.handlers
import sys

# local imports
import cp_lib.hw_status as hw_status
from cp_lib.load_settings_json import SECTION_APPLICATION
from cp_lib.unquote_string import unquote_string

# modify this directly, if you care to
DEF_FORMAT = "%(levelname)s:%(name)s:%(message)s"
DEF_NAME = "main"
DEF_SYSLOG_PORT = 514
DEF_SYSLOG_PRI = logging.handlers.SysLogHandler.LOG_LOCAL0

SETS_LEVEL = "level"
SETS_NAME = "trace_name"
SETS_FILE = "log_file_name"
SETS_SYSLOG_IP = "syslog_ip"
SETS_SYSLOG_PORT = "syslog_port"
SETS_SYSLOG_PRI = "syslog_pri"
SETS_FORMAT = "format"
# SETS_LEVEL, SETS_NAME, SETS_FILE, SETS_SYSLOG, SETS_FORMAT


def get_recommended_logger(sets=None, level=None, name=None):
    """
    The recommended logger uses direct Syslog to local IP for < INFO level

    When level >= INFO, it blends with router's native Syslog

    :param dict sets: settings
    :param level: allow direct 'over-ride' of the level in the settings file
                  (used by MAKE.PY)
    :param str name: optional NAME for logger, to over-ride any settings data
    :return:
    """

    try:
        settings = _process_settings(sets, name)

    except:
        logging.exception('Test failed')
        raise

    if level is not None:
        # process the over-ride
        settings[SETS_LEVEL] = _process_level(level)

    logger = logging.getLogger(settings[SETS_NAME])
    logger.setLevel(settings[SETS_LEVEL])

    formatter = logging.Formatter(settings[SETS_FORMAT])

    # SETS_LEVEL, SETS_NAME, SETS_FILE, SETS_SYSLOG, SETS_FORMAT

    if settings[SETS_SYSLOG_IP] is not None:
        # then create the address parameter
        if settings[SETS_SYSLOG_IP] == '/dev/log':
            # for the Linux system log, we've no port number etc
            syslog_address = settings[SETS_SYSLOG_IP]
        else:
            syslog_address = (settings[SETS_SYSLOG_IP],
                              settings[SETS_SYSLOG_PORT])
    else:
        syslog_address = None

    # CONSOLE - STDOUT destination
    # if not hw_status.am_running_on_router():

    # LOG FILE on DISK - when NOT on router
    if settings[SETS_FILE] is not None:
        # then add the file logger, but never on the router!
        handler = logging.handlers.RotatingFileHandler(
            filename=settings[SETS_FILE])
        handler.setLevel(settings[SETS_LEVEL])
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.info(
            "Logging - enabled log file={}".format(settings[SETS_FILE]))

    # SYSLOG server - when NOT on router
    if syslog_address is not None:
        handler = logging.handlers.SysLogHandler(
            address=syslog_address, facility=settings[SETS_SYSLOG_PRI])
        handler.setLevel(settings[SETS_LEVEL])
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.info("Logging - enabled syslog={}".format(syslog_address))

    # else:  # we are running on the router
    #     if syslog_address is not None:
    #         # special for router
    #         if settings[SETS_LEVEL] >= logging.INFO:
    #             # we are in deploy mode, or running on a Cradlepoint router
    #             syslog_address = '/dev/log'
    #
    #         handler = logging.handlers.SysLogHandler(
    #             address=syslog_address, facility=settings[SETS_SYSLOG_PRI])
    #         handler.setLevel(settings[SETS_LEVEL])
    #         handler.setFormatter(formatter)
    #         logger.addHandler(handler)
    #         logger.debug(
    #             "Logging - enabled ROUTER syslog={}".format(syslog_address))

    return logger


def _process_settings(sets=None, name=None):
    """
    Parse out and validate the settings. Since they may be imported from
    INI and/or JSON, we may need to convert some values from text to
    "as expected"

    :param dict sets: settings
    :param str name: optional NAME for logger, to over-ride any settings data
    :return dict:
    """

    # set the defaults
    settings = {
        SETS_LEVEL: logging.INFO,
        SETS_NAME: DEF_NAME,
        SETS_FILE: None,
        SETS_SYSLOG_IP: None,
        SETS_FORMAT: DEF_FORMAT,

    }

    if sets is None:
        return settings

    # print(json.dumps(sets, ensure_ascii=True, indent=4))

    if "logging" in sets:
        # prep the settings
        local_sets = sets["logging"]

        if "level" in local_sets:
            # handle the LOGGING level, such as INFO or DEBUG or 10
            settings[SETS_LEVEL] = _process_level(local_sets["level"])

        if name is None:
            if "name" in local_sets:
                # handle the LOGGING name, as used in trace output
                value = unquote_string(local_sets["name"])
                settings[SETS_NAME] = value

            elif "application" in sets and "name" in sets["application"]:
                value = sets["application"]["name"]
                settings[SETS_NAME] = value

            # else assume DEF_NAME is okay
        else:
            settings[SETS_NAME] = name

        if "log_file" in local_sets:
            # handle the log file name, if None then no logging is done
            value = unquote_string(local_sets["log_file"])
            if value.lower() in ("none", "", "null"):
                # allow the log file to be explicitly disabled
                value = None
            settings[SETS_FILE] = value

        # special - disable syslog when run on PC
        if sys.platform in ('win32', 'linux') and 'pc_syslog' in local_sets:
            # this setting should be missing, or forced to boolean before
            # we reach here
            if not local_sets['pc_syslog']:
                # then False, so disable Syslog
                settings[SETS_SYSLOG_IP] = None

        elif "syslog_ip" in local_sets:
            # handle the SYSLOG server IP
            value = unquote_string(local_sets["syslog_ip"]).lower()
            if value in ("none", "", "null"):
                settings[SETS_SYSLOG_IP] = None

            elif value == '/dev/log' and sys.platform == 'win32':
                # for windows, try localhost
                settings[SETS_SYSLOG_IP] = '127.0.0.1'

            else:
                settings[SETS_SYSLOG_IP] = value

            if "syslog_port" in local_sets:
                # handle the SYSLOG server PORT (assume UDP for now)
                value = unquote_string(local_sets["syslog_port"])
                settings[SETS_SYSLOG_PORT] = int(value)
            else:
                settings[SETS_SYSLOG_PORT] = DEF_SYSLOG_PORT

            if "syslog_pri" in local_sets:
                # handle the SYSLOG server FACILITY
                value = unquote_string(local_sets["syslog_pri"])
                settings[SETS_SYSLOG_PRI] = int(value)
            else:
                settings[SETS_SYSLOG_PRI] = DEF_SYSLOG_PRI

    # try a few special case settings
    if settings[SETS_NAME] is None or settings[SETS_NAME] == DEF_NAME:
        # then see if the ["application"] sections has a value
        if SECTION_APPLICATION in sets and "name" in sets[SECTION_APPLICATION]:
            # then use the global sample name
            settings[SETS_NAME] = sets[SECTION_APPLICATION]["name"]
        else:
            settings[SETS_NAME] = DEF_NAME

    assert isinstance(settings[SETS_NAME], str)
    if len(settings[SETS_NAME]) < 1:
        # LOGGING wants logger name to be non-empty
        raise ValueError("Logger name must be string - not \"{}\"".format(settings[SETS_NAME]))

    # these must be true
    assert isinstance(settings[SETS_LEVEL], int)
    if settings[SETS_LEVEL] < 0:
        # LOGGING wants values 0 or greater
        raise ValueError(
            "Logging level must as expected by LOGGING module, not {}".format(settings[SETS_LEVEL]))

    assert settings[SETS_FILE] is None or isinstance(settings[SETS_FILE], str)
    assert settings[SETS_SYSLOG_IP] is None or isinstance(settings[SETS_SYSLOG_IP], str)
    if SETS_SYSLOG_PORT in settings:
        assert isinstance(settings[SETS_SYSLOG_PORT], int)
        if not (1 < settings[SETS_SYSLOG_PORT] < 0xFFFF):
            # LOGGING wants syslog PORT to be 1 to 65535
            raise ValueError(
                "Logger syslog UDP PORT is invalid \"{}\"".format(settings[SETS_SYSLOG_PORT]))
        if len(settings[SETS_SYSLOG_IP]) < 1:
            # LOGGING wants syslog IP to be non-empty - can be DNS?
            raise ValueError(
                "Logger syslog IP must be string - not \"{}\"".format(settings[SETS_SYSLOG_IP]))

    return settings


def _process_level(value):
    """
    Given an input (as string or int) convert to LOGGING level value

    :param value:
    """

    # allow settings.ini to use names like level=debug, logging._nameToLevel[] will throw exception
    name_to_level = {
        'CRITICAL': logging.CRITICAL,
        'ERROR': logging.ERROR,
        'WARN': logging.WARNING,
        'WARNING': logging.WARNING,
        'INFO': logging.INFO,
        'DEBUG': logging.DEBUG,
        'NOTSET': logging.NOTSET
    }

    if isinstance(value, str):
        # handle the LOGGING level, such as INFO or DEBUG or 10
        value = unquote_string(value)
        try:
            # start assuming is int, but it is probably str of int
            value = int(value)

        except ValueError:
            # if here, then try if string like INFO, force to UPPER()
            try:
                value = name_to_level[value.upper()]

            except KeyError:
                raise ValueError("Logging level must as expected by Python LOGGING" +
                                 "module - not {}".format(value))

    if not isinstance(value, int):
        raise TypeError("Logging value must be string or int")

    return value
