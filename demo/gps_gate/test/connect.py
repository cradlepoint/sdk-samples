# Test the gps.gps_gate.gps_gate_protocol module

import socket
import time

import demo.gps_gate.gps_gate_protocol as protocol
from cp_lib.gps_nmea import fix_time_sentence
from cp_lib.load_gps_config import GpsConfig
from cp_lib.load_active_wan import ActiveWan
from cp_lib.parse_data import clean_string, parse_integer

# Here is a sample TRACE of this code running
#
# INFO:make:GpsGate: Setting IMEI:353547060660845
# INFO:make:GpsGate: Setting Server URL:64.46.40.178
# INFO:make:GpsGate: Setting user name:Admin
# INFO:make:GpsGate: Setting new PASSWORD:****
# INFO:make:Preparing to connect on TCP socket ('64.46.40.178', 30175)
# DEBUG:make:get_next() entry state:offline
# DEBUG:make:get_next() exit state:login
# DEBUG:make:Req(b'$FRLIN,IMEI,353547060660845,*47\r\n')
# DEBUG:make:Rsp(b'$FRSES,83*76\r\n')
# DEBUG:make:Recording server SESSION:83
# DEBUG:make:get_next() entry state:session
# DEBUG:make:get_next() exit state:wait_ver
# DEBUG:make:Req(b'$FRVER,1,1,Cradlepoint 1.0*27\r\n')
# DEBUG:make:Rsp(b'$FRVER,1,1,GpsGate Server 3.0.0.2583*3E\r\n')
# DEBUG:make:Recording server TITLE:GpsGate Server 3.0.0.2583
# DEBUG:make:get_next() entry state:have_ver
# DEBUG:make:get_next() exit state:update
# DEBUG:make:Req(b'$FRCMD,,_getupdaterules,Inline*1E')
# DEBUG:make:Rsp(b'$FRRET,IBR350,_getupdaterules,Nmea,5*6F\r\n')
# DEBUG:make:Rsp(b'$FRVAL,DistanceFilter,500.0*67\r\n$FRVAL,TimeFilter,
#              60.0*42\r\n$FRVAL,SpeedFilter,2.8*0C\r\n$FRVAL,DirectionFilter,
#              30.0*37\r\n$FRVAL,DirectionThreshold,10.0*42\r\n')
# DEBUG:make:NMEA.set_distance_filter = 500.0 m
# DEBUG:make:NMEA.set_time_filter = 60.0 sec
# DEBUG:make:NMEA.set_speed_filter = 2.8 m/sec
# DEBUG:make:NMEA.set_direction_filter = 30.0 deg
# DEBUG:make:NMEA.set_direction_threshold = 10.0 m
# ERROR:make:No response - jump from loop!
# DEBUG:make:get_next() entry state:ready
# DEBUG:make:get_next() exit state:forwarding
# DEBUG:make:Req(b'$FRWDT,NMEA*78')
# DEBUG:make:Req(b'$GPGGA,143736.0,4334.784909,N,11612.766448,W,1,09,0.9,
#                  830.6,M,-11.0,M,,*6B\r\n')


def run_client():
    global base_app

    obj = protocol.GpsGate(base_app.logger)

    # base_app.logger.debug("sets:{}".format(base_app.settings))

    # set a few defaults
    imei = "353547060660845"
    gps_gate_url = "64.46.40.178"
    gps_gate_port = 30175

    if "gps_gate" in base_app.settings:
        # then we do have a customer config
        temp = base_app.settings["gps_gate"]

        # check on our localhost port (not used, but to test)
        config = GpsConfig(base_app)
        host_ip, host_port = config.get_client_info()
        if "host_ip" in temp:
            # then OVER-RIDE what the router told us
            base_app.logger.warning("Settings OVER-RIDE router host_ip")
            value = clean_string(temp["host_ip"])
            base_app.logger.warning("was:{} now:{}".format(host_ip, value))
            host_ip = value

        if "host_port" in temp:
            # then OVER-RIDE what the router told us
            base_app.logger.warning("Settings OVER-RIDE router host_port")
            value = parse_integer(temp["host_port"])
            base_app.logger.warning("was:{} now:{}".format(host_port, value))
            host_port = value

        base_app.logger.debug("GPS source:({}:{})".format(host_ip, host_port))
        del config

        # check on our cellular details
        config = ActiveWan(base_app)
        imei = config.get_imei()
        if "imei" in temp:
            # then OVER-RIDE what the router told us
            base_app.logger.warning("Settings OVER-RIDE router IMEI")
            value = clean_string(temp["imei"])
            base_app.logger.warning("was:{} now:{}".format(imei, value))
            imei = value
        del config

        if "gps_gate_url" in temp:
            # load the settings.ini value
            gps_gate_url = clean_string(temp["gps_gate_url"])

        if "gps_gate_port" in temp:
            # load the settings.ini value
            gps_gate_port = parse_integer(temp["gps_gate_port"])

    obj.set_imei(imei)
    obj.set_server_url(gps_gate_url)
    obj.set_server_port(gps_gate_port)

    # we never need these!
    # obj.set_username('Admin')
    # obj.set_password(':Vm78!!')

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    sock.settimeout(2.0)
    address = (obj.gps_gate_url, obj.gps_gate_port)

    base_app.logger.info(
        "Preparing to connect on TCP socket {}".format(address))

    # attempt to actually lock the resource, which may fail if unavailable
    #   (see CONNECT ERROR note)
    try:
        sock.connect(address)
    except OSError as msg:
        base_app.logger.error("socket.connect() failed - {}".format(msg))

        return -1

    # first test - try our user name:
    # Req = $FRLIN,, Admin,12Ne*14\r\n
    # Rsp = $FRERR,AuthError,Wrong username or password*56\r\n

    # second test - try our IMEI:
    # Req = $FRLIN,IMEI,353547060660845,*47\r\n
    # Rsp = $FRSES,75*7F\r\n

    # expect Req = $FRLIN,IMEI,353547060660845,*47\r\n
    request = obj.get_next_client_2_server()
    base_app.logger.debug("Req({})".format(request))
    sock.send(request)

    # expect Rsp = $FRSES,75*7F\r\n
    try:
        response = sock.recv(1024)
        base_app.logger.debug("Rsp({})".format(response))
        result = obj.parse_message(response)
        if not result:
            base_app.logger.debug("parse result({})".format(result))
    except socket.timeout:
        base_app.logger.error("No response - one was expected!")
        return -1

    # expect Req = $FRVER,1,1,Cradlepoint 1.0*27\r\n
    request = obj.get_next_client_2_server()
    base_app.logger.debug("Req({})".format(request))
    sock.send(request)

    # expect Rsp = $FRVER,1,1,GpsGate Server 3.0.0.2583*3E\r\n
    try:
        response = sock.recv(1024)
        base_app.logger.debug("Rsp({})".format(response))
        result = obj.parse_message(response)
        if not result:
            base_app.logger.debug("parse result({})".format(result))
    except socket.timeout:
        base_app.logger.error("No response - one was expected!")
        return -1

    # expect Req = $FRCMD,,_getupdaterules,Inline*1E
    request = obj.get_next_client_2_server()
    base_app.logger.debug("Req({})".format(request))
    sock.send(request)

    # expect Rsp = $FRRET,User1,_getupdaterules,Nmea,2*07
    try:
        response = sock.recv(1024)
        base_app.logger.debug("Rsp({})".format(response))
        result = obj.parse_message(response)
        if not result:
            base_app.logger.debug("parse result({})".format(result))
    except socket.timeout:
        base_app.logger.error("No response - one was expected!")
        return -1

    # now we LOOP and process the rules!
    while True:
        # expect Rsp = $FRVAL,DistanceFilter,500.0*67
        try:
            response = sock.recv(1024)
            base_app.logger.debug("Rsp({})".format(response))
            result = obj.parse_message(response)
            if not result:
                base_app.logger.debug("parse result({})".format(result))
        except socket.timeout:
            base_app.logger.error("No response - jump from loop!")
            break

    # expect Req = b"$FRWDT,NMEA*78"
    request = obj.get_next_client_2_server()
    base_app.logger.debug("Req({})".format(request))
    sock.send(request)
    # this message has NO response!

    # our fake data, time-fixed to me NOW
    request = fix_time_sentence("$GPGGA,094013.0,4334.784909,N,11612.7664" +
                                "48,W,1,09,0.9,830.6,M,-11.0,M,,*60")
    request = request.encode()
    base_app.logger.debug("Req({})".format(request))
    sock.send(request)

    # this message has NO response!
    time.sleep(2.0)

    sock.close()

    return 0


if __name__ == '__main__':
    from cp_lib.app_base import CradlepointAppBase
    import tools.make_load_settings

    app_name = 'demo.gps_gate'

    # we share the settings.ini in demo/gps_gate/settings.ini
    base_app = CradlepointAppBase(full_name=app_name, call_router=False)

    # force a full make/read of {app_path}/settings.ini
    base_app.settings = tools.make_load_settings.load_settings(
        base_app.app_path)

    run_client()
