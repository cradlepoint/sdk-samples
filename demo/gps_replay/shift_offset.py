"""
This is a standalone script, to be run on a PC. It reads a previously
created file (likely created by save_replay.py), renames and creates a
new file with the "offset" field shifted by some time.

The goal is to prepare a file to be appended to another.
"""
import os

from cp_lib.app_base import CradlepointAppBase
from cp_lib.parse_data import clean_string, parse_float

DEF_REPLAY_FILE = 'gps_log.json'


def run_router_app(app_base, adjust_seconds):
    """

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :param float adjust_seconds:
    :return:
    """

    replay_file_name = DEF_REPLAY_FILE

    section = "gps"
    if section in app_base.settings:
        # then load dynamic values
        temp = app_base.settings[section]

        if "replay_file" in temp:
            replay_file_name = clean_string(temp["replay_file"])

    if not os.path.isfile(replay_file_name):
        app_base.logger.error(
            "Replay file({}) not found".format(replay_file_name))
        raise FileNotFoundError

    app_base.logger.info(
        "Replay file is named:{}".format(replay_file_name))

    backup_file_name = replay_file_name + '.bak'
    app_base.logger.info(
        "Backup file is named:{}".format(backup_file_name))

    os.rename(src=replay_file_name, dst=backup_file_name)

    file_in = open(backup_file_name, "r")
    file_out = open(replay_file_name, "w")

    while True:
        # loop forever

        # this is a dictionary
        dict_in = read_in_line(file_in)
        if dict_in is None:
            app_base.logger.warning("Close Replay file")
            break

        else:
            dict_in["offset"] += adjust_seconds
            result = '{"offset":%d, "data":"%s"},\n' % (dict_in["offset"],
                                                        dict_in["data"])
            file_out.write(result)

    file_in.close()
    file_out.close()

    return 0


def read_in_line(_file_han):

    while True:
        line_in = _file_han.readline().strip()
        if line_in is None or len(line_in) == 0:
            break

        if line_in[0] == '{':
            # then assume like {"offset":1, "data":$GPGGA,094013.0 ... },
            if line_in[-1] == ',':
                line_in = line_in[:-1]

            return eval(line_in)

        # else, get next line

    return None

if __name__ == "__main__":
    import sys
    from cp_lib.load_settings_ini import copy_config_ini_to_json, \
        load_sdk_ini_as_dict
    from cp_lib.parse_duration import TimeDuration

    copy_config_ini_to_json()

    app_path = "demo/gps_replay"
    my_app = CradlepointAppBase(app_path, call_router=False)
    # force a heavy reload of INI (app base normally only finds JSON)
    my_app.settings = load_sdk_ini_as_dict(app_path)

    if len(sys.argv) == 2:
        # assume is numeric seconds
        shifter = parse_float(sys.argv[1])

    elif len(sys.argv) >= 3:
        # assume is tagged time, like "15 min"
        period = TimeDuration(sys.argv[1] + ' ' + sys.argv[2])
        shifter = parse_float(period.get_seconds())

    else:
        my_app.logger.warning("You need to append the time in seconds")
        sys.exit(-1)

    my_app.logger.info("Time shifter = {} seconds".format(shifter))

    _result = run_router_app(my_app, shifter)

    my_app.logger.info("Exiting, status code is {}".format(_result))
    sys.exit(_result)
