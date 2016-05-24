"""
Received GPS, assuming the router's GPS function sends new data (sentences)
to a localhost port
"""

import socket
import time
import gc

from cp_lib.app_base import CradlepointAppBase
from cp_lib.load_active_wan import ActiveWan
from cp_lib.load_gps_config import GpsConfig
from cp_lib.parse_data import clean_string, parse_integer

from demo.gps_gate.gps_gate_protocol import GpsGate


DEF_BUFFER_SIZE = 1024


def run_router_app(app_base):
    """

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :return:
    """
    # logger.debug("Settings({})".format(sets))

    # handle the GPS_GATE protocol
    gps_gate = GpsGate(app_base.logger)

    # process the SETTINGS file
    section = "gps_gate"
    if section not in app_base.settings:
        # this is unlikely!
        app_base.logger.warning(
            "Aborting: No [%s] section in settings.ini".format(section))
        return -1

    else:
        # then load dynamic values
        temp = app_base.settings[section]

        app_base.logger.debug(
            "[{}] section = {}".format(section, temp))

        # settings for our LISTENER for router GPS output
        buffer_size = int(temp.get("buffer_size", DEF_BUFFER_SIZE))

        # check on our localhost port (not used, but to test)
        config = GpsConfig(app_base)
        host_ip, host_port = config.get_client_info()
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

        app_base.logger.debug("GPS source:({}:{})".format(host_ip, host_port))
        del config

        # settings defining the GpsGate interactions
        if "gps_gate_url" in temp:
            gps_gate.set_server_url(temp["gps_gate_url"])
        if "gps_gate_port" in temp:
            gps_gate.set_server_port(temp["gps_gate_port"])
        if "gps_gate_transport" in temp:
            gps_gate.set_server_transport(temp["gps_gate_transport"])

        if "username" in temp:
            gps_gate.set_username(temp["username"])
        if "password" in temp:
            gps_gate.set_password(temp["password"])
        if "server_version" in temp:
            gps_gate.set_server_version(temp["server_version"])
        if "client" in temp:
            gps_gate.set_client_name(temp["client"])

        if "IMEI" in temp:
            gps_gate.set_imei(temp["IMEI"])
        elif "imei" in temp:
            # handle upper or lower case, just because ...
            gps_gate.set_imei(temp["imei"])

        # we can pre-set the filters here, but Gpsgate may try to override
        if "distance_filter" in temp:
            gps_gate.nmea.set_distance_filter(temp["distance_filter"])
        if "time_filter" in temp:
            gps_gate.nmea.set_time_filter(temp["time_filter"])
        if "speed_filter" in temp:
            gps_gate.nmea.set_speed_filter(temp["speed_filter"])
        if "direction_filter" in temp:
            gps_gate.nmea.set_direction_filter(temp["direction_filter"])
        if "direction_threshold" in temp:
            gps_gate.nmea.set_direction_threshold(temp["direction_threshold"])

    # check the cell modem/gps sources
    wan_data = ActiveWan(app_base)
    # app_base.logger.info("WAN data {}".format(wan_data['active']))

    value = wan_data.get_imei()
    if gps_gate.client_imei is None:
        # only take 'live' value if setting.ini was NOT included
        gps_gate.set_imei(value)
    else:
        app_base.logger.warning(
            "Using settings.ini IMEI, ignoring cell modem's value")

    if not wan_data.supports_gps():
        app_base.logger.warning(
            "cell modem claims no GPS - another source might exist")

    if wan_data.get_live_gps_data() in (None, {}):
        app_base.logger.warning(
            "cell modem has no last GPS data")
    else:
        app_base.logger.debug("GPS={}".format(wan_data.get_live_gps_data()))

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

                    # gps.start()
                    for line in data:
                        try:
                            pass
                            # result = gps.parse_sentence(line)
                            # if not result:
                            #     break

                        except ValueError:
                            app_base.logger.warning(
                                "Bad NMEA sentence:[{}]".format(line))
                            raise

                    # gps.publish()
                    # app_base.logger.debug(
                    #     "See({})".format(gps.get_attributes()))
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

    my_app = CradlepointAppBase("gps/gps_gate")
    _result = run_router_app(my_app)
    my_app.logger.info("Exiting, status code is {}".format(_result))
    sys.exit(_result)
