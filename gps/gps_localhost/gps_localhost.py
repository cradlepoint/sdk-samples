"""
Received GPS, assuming the router's GPS function sends new data (sentences)
to a localhost port
"""

import socket
import time
import gc

from cp_lib.app_base import CradlepointAppBase
from cp_lib.gps_nmea import NmeaStatus
from cp_lib.parse_data import parse_boolean


DEF_HOST_IP = 'localhost'
DEF_HOST_PORT = 9999
DEF_BUFFER_SIZE = 1024


def run_router_app(app_base):
    """

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :return:
    """
    # logger.debug("Settings({})".format(sets))

    host_ip = DEF_HOST_IP
    host_port = DEF_HOST_PORT
    buffer_size = DEF_BUFFER_SIZE

    gps = NmeaStatus()

    section = "gps"
    if section in app_base.settings:
        # then load dynamic values
        host_ip = app_base.settings[section].get("host_ip", DEF_HOST_IP)
        host_port = int(app_base.settings[section].get("host_port",
                                                       DEF_HOST_PORT))
        buffer_size = int(app_base.settings[section].get("buffer_size",
                                                         DEF_BUFFER_SIZE))

        gps.date_time = parse_boolean(
            app_base.settings[section].get("date_time", gps.DEF_DATE_TIME))
        gps.speed = parse_boolean(
            app_base.settings[section].get("speed", gps.DEF_SPEED))
        gps.altitude = parse_boolean(
            app_base.settings[section].get("altitude", gps.DEF_ALTITUDE))
        gps.coor_ddmm = parse_boolean(
            app_base.settings[section].get("coor_ddmm", gps.DEF_COOR_DDMM))
        gps.coor_dec = parse_boolean(
            app_base.settings[section].get("coor_dec", gps.DEF_COOR_DEC))

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
                    data = data.decode().split()

                    gps.start()
                    for line in data:
                        result = gps.parse_sentence(line)
                        if not result:
                            break
                    gps.publish()

                    app_base.logger.debug(
                        "See({})".format(gps.get_attributes()))
                    # client.send(data)
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
