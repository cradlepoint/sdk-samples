"""
This is a standalone script, to be run on a PC. It receives GPS data
on a localhost port & writes to a replay file.

The format is pseudo-JSON, as it will be like:
[
{"offset":1, "data":$GPGGA,094013.0,4334.784909,N,11612.766448,W,1 (...) *60},
{"offset":3, "data":$GPGGA,094023.0,4334.784913,N,11612.766463,W,1 (...) *61},
{"offset":13, "data":$GPGGA,094034.0,4334.784922,N,11612.766471,W, (...) *67},

Notice it starts with a '[', but like won't end with ']' - assuming you
abort the creation uncleanly. You can manually add one if you wish.

"offset" is the number of seconds since the start of the replay save, which
are used during replay to delay and meter out the sentences in a realistic
manner. We'll also need to 'edit' the known sentences to add new TIME and
DATE values.
"""
import socket
import time
import gc

from cp_lib.app_base import CradlepointAppBase
from cp_lib.load_gps_config import GpsConfig
from cp_lib.parse_data import clean_string, parse_integer

DEF_BUFFER_SIZE = 1024
DEF_REPLAY_FILE = 'gps_log.json'


def run_router_app(app_base):
    """

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :return:
    """
    buffer_size = DEF_BUFFER_SIZE
    replay_file_name = DEF_REPLAY_FILE

    # use Router API to fetch any configured data
    config = GpsConfig(app_base)
    host_ip, host_port = config.get_client_info()
    del config

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

        if "buffer_size" in temp:
            buffer_size = parse_integer(temp["buffer_size"])

        if "replay_file" in temp:
            replay_file_name = clean_string(temp["replay_file"])

    app_base.logger.debug("GPS source:({}:{})".format(host_ip, host_port))

    # make sure our log file exists & is empty
    file_han = open(replay_file_name, "w")
    file_han.write("[\n")
    file_han.close()

    address = (host_ip, host_port)

    while True:
        # define the socket resource, including the type (stream == "TCP")
        app_base.logger.info("Preparing GPS Listening on {}".format(address))
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # attempt to actually lock resource, which may fail if unavailable
        #   (see BIND ERROR note)
        try:
            sock.bind(address)
        except OSError as msg:
            app_base.logger.error("socket.bind() failed - {}".format(msg))

            # technically, Python will close when 'sock' goes out of scope,
            # but be disciplined and close it yourself. Python may warning
            # you of unclosed resource, during runtime.
            try:
                sock.close()
            except OSError:
                pass

            # we exit, because if we cannot secure the resource, the errors
            # are likely permanent.
            return -1

        # only allow 1 client at a time
        sock.listen(3)

        while True:
            # loop forever
            start_time = time.time()

            app_base.logger.info("Waiting on TCP socket %d" % host_port)
            client, address = sock.accept()
            app_base.logger.info("Accepted connection from {}".format(address))

            # for cellular, ALWAYS enable TCP Keep Alive (see KEEP ALIVE note)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

            # set non-blocking so we can do a manual timeout (use of select()
            # is better ... but that's another sample)
            # client.setblocking(0)

            while True:
                app_base.logger.debug("Waiting to receive data")
                data = client.recv(buffer_size)
                # data is type() bytes, to echo we don't need to convert
                # to str to format or return.
                if data:
                    # assume we have multiple sentences per segment recv'd
                    data = data.decode().split()

                    print("data:{}".format(data))

                    file_han = open(replay_file_name, "a")
                    offset = int(time.time() - start_time)

                    for line in data:
                        result = '{"offset":%d, "data":"%s"},\n' % (offset,
                                                                    line)
                        file_han.write(result)

                    app_base.logger.debug("Wrote at offset:{}".format(offset))

                else:
                    break

                time.sleep(1.0)

            app_base.logger.info("Client disconnected")
            client.close()

            # since this server is expected to run on a small embedded system,
            # free up memory ASAP (see MEMORY note)
            del client
            gc.collect()

    return 0


if __name__ == "__main__":
    import sys
    from cp_lib.load_settings_ini import copy_config_ini_to_json, \
        load_sdk_ini_as_dict

    copy_config_ini_to_json()

    app_path = "demo/gps_replay"
    my_app = CradlepointAppBase(app_path)
    # force a heavy reload of INI (app base normally only finds JSON)
    my_app.settings = load_sdk_ini_as_dict(app_path)

    _result = run_router_app(my_app)
    my_app.logger.info("Exiting, status code is {}".format(_result))
    sys.exit(_result)
