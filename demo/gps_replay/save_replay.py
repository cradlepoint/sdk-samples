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
from cp_lib.parse_data import clean_string
# from cp_lib.gps_nmea import NmeaStatus

# set your interface port below; due to Windows FW, you may not be able
# to use 'localhost' if you have multiple interfaces
DEF_HOST_IP = '192.168.35.6'
DEF_HOST_PORT = 9999
DEF_BUFFER_SIZE = 1024
DEF_REPLAY_FILE = 'gps_log.json'


def run_router_app(app_base):
    """

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :return:
    """
    # logger.debug("Settings({})".format(sets))

    host_ip = DEF_HOST_IP
    host_port = DEF_HOST_PORT
    buffer_size = DEF_BUFFER_SIZE
    replay_file_name = DEF_REPLAY_FILE

    # we are reading the settings from sample gps_localhost
    section = "gps"
    if section in app_base.settings:
        # then load dynamic values
        host_ip = clean_string(
            app_base.settings[section].get("host_ip", DEF_HOST_IP))
        host_port = int(
            app_base.settings[section].get("host_port", DEF_HOST_PORT))
        buffer_size = int(
            app_base.settings[section].get("buffer_size", DEF_BUFFER_SIZE))
        replay_file_name = clean_string(
            app_base.settings[section].get("replay_file", DEF_REPLAY_FILE))

    # replay_file = gps_replay.json

    # make sure our log file exists & is empty
    file_han = open(replay_file_name, "w")
    file_han.write("[\n")
    file_han.close()

    while True:
        # define the socket resource, including the type (stream == "TCP")
        address = (host_ip, host_port)
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
                        result = '{"offset":%d, "data":"%s"},\n' % (offset, line)
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

    my_app = CradlepointAppBase("gps/gps_localhost")
    _result = run_router_app(my_app)
    my_app.logger.info("Exiting, status code is {}".format(_result))
    sys.exit(_result)
