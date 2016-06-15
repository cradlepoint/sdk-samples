"""
This is a standalone script, to be run on a PC. It reads a previously
created file (likely created by save_replay.py), then acts like a cradlepoint
router sending the data in a REPLAY mode.

The replay file format is pseudo-JSON, as it will be like:
[
{"offset":1, "data":$GPGGA,094013.0,4334.784909,N,11612.766448,W,1 (...) *60},
{"offset":3, "data":$GPGGA,094023.0,4334.784913,N,11612.766463,W,1 (...) *61},
{"offset":13, "data":$GPGGA,094034.0,4334.784922,N,11612.766471,W, (...) *67},

"offset" is the number of seconds since the start of the replay save, which
are used during replay to delay and meter out the sentences in a realistic
manner. We'll also need to 'edit' the known sentences to add new TIME and
DATE values.
"""
import os
import socket
import time

from cp_lib.app_base import CradlepointAppBase, CradlepointRouterOffline
from cp_lib.parse_data import clean_string, parse_integer
from cp_lib.load_gps_config import GpsConfig
import cp_lib.gps_nmea as gps_nmea

DEF_REPLAY_FILE = 'gps_log.json'


def run_router_app(app_base):
    """

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :return:
    """
    # logger.debug("Settings({})".format(sets))

    replay_file_name = DEF_REPLAY_FILE

    try:
        # use Router API to fetch any configured data
        config = GpsConfig(app_base)
        host_ip, host_port = config.get_client_info()
        del config

    except CradlepointRouterOffline:
        host_ip = None
        host_port = 0

    section = "gps"
    if section in app_base.settings:
        # then load dynamic values
        temp = app_base.settings[section]

        # check on our localhost port (not used, but to test)
        if "host_ip" in temp:
            # then OVER-RIDE what the router told us
            app_base.logger.warning("Settings OVER-RIDE router host_ip")
            value = clean_string(temp["host_ip"])
            app_base.logger.warning("was:{} now:{}".format(host_ip, value))
            host_ip = value

        if "host_port" in temp:
            # then OVER-RIDE what the router told us
            app_base.logger.warning("Settings OVER-RIDE router host_port")
            value = parse_integer(temp["host_port"])
            app_base.logger.warning("was:{} now:{}".format(host_port, value))
            host_port = value

        if "replay_file" in temp:
            replay_file_name = clean_string(temp["replay_file"])

    app_base.logger.debug("GPS destination:({}:{})".format(host_ip, host_port))

    if not os.path.isfile(replay_file_name):
        app_base.logger.error(
            "Replay file({}) not found".format(replay_file_name))
        raise FileNotFoundError

    app_base.logger.info(
        "Replay file is named:{}".format(replay_file_name))

    # define the socket resource, including the type (stream == "TCP")
    address = (host_ip, host_port)
    app_base.logger.info("Will connect on {}".format(address))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    sock.connect(address)

    file_han = None
    start_time = time.time()

    try:
        while True:
            # loop forever
            if file_han is None:
                # reopen the file
                file_han = open(replay_file_name, "r")
                start_time = time.time()

            # this
            line_in = read_in_line(file_han)
            if line_in is None:
                app_base.logger.warning("Close Replay file")
                file_han.close()
                break

            else:
                wait_time = start_time + line_in['offset']
                now = time.time()
                if wait_time > now:
                    delay = wait_time - now
                    app_base.logger.debug("Delay %0.1f sec" % delay)
                    time.sleep(delay)

                nmea_out = gps_nmea.fix_time_sentence(line_in['data']).strip()
                nmea_out += '\r\n'
                app_base.logger.debug("out:{}".format(nmea_out))

                sock.send(nmea_out.encode())

                time.sleep(0.1)

    finally:
        app_base.logger.info("Closing client socket")
        sock.close()

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

    copy_config_ini_to_json()

    app_path = "demo/gps_replay"
    my_app = CradlepointAppBase(app_path, call_router=False)
    # force a heavy reload of INI (app base normally only finds JSON)
    my_app.settings = load_sdk_ini_as_dict(app_path)

    _result = run_router_app(my_app)
    my_app.logger.info("Exiting, status code is {}".format(_result))
    sys.exit(_result)
