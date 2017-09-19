"""
Assuming the Cradlepoint router is configured to forward NMEA sentences 
to a localhost port, open the port as a server and receive the streaming
GSP data.

"""

import argparse
import socket
import time
import gc
import cs
import gps_nmea

APP_NAME = 'gps_localhost'


def run_router_app():
    """
    """
    # cs.CSClient().log(APP_NAME, "Settings({})".format(sets))

    host_ip = 'localhost'
    host_port = 9999
    buffer_size = 1024

    gps = gps_nmea.NmeaStatus()

    # set True to parse GPS time (as ['gps_utc']), else omit
    gps.date_time = False
    # set True to parse speed over ground (as ['knots'] & ['kmh']), else omit
    gps.speed = True
    # set True to parse altitude (as ['alt'], else omit
    gps.altitude = False
    # set True to include DDMM.MM string (as ['lat_ddmm' & 'long_ddmm'], else omit
    gps.coor_ddmm = False
    # set True to parse lat/log as decimal (as ['lat', 'long]), else omit
    gps.coor_dec = True

    while True:
        # define the socket resource, including the type (stream == "TCP")
        address = (host_ip, host_port)
        cs.CSClient().log(APP_NAME, "Preparing GPS Listening on {}".format(address))
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # attempt to actually lock resource, which may fail if unavailable
        #   (see BIND ERROR note)
        try:
            sock.bind(address)
        except OSError as msg:
            cs.CSClient().log(APP_NAME, "socket.bind() failed - {}".format(msg))

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
            cs.CSClient().log(APP_NAME, "Waiting on TCP socket %d" % host_port)
            client, address = sock.accept()
            cs.CSClient().log(APP_NAME, "Accepted connection from {}".format(address))

            # for cellular, ALWAYS enable TCP Keep Alive (see KEEP ALIVE note)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

            # set non-blocking so we can do a manual timeout (use of select()
            # is better ... but that's another sample)
            # client.setblocking(0)

            while True:
                cs.CSClient().log(APP_NAME, "Waiting to receive data")
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

                    cs.CSClient().log(APP_NAME,
                                      "See({})".format(gps.get_attributes()))
                    # client.send(data)
                else:
                    break

                time.sleep(1.0)

            cs.CSClient().log(APP_NAME, "Client disconnected")
            client.close()

            # since this server is expected to run on a small embedded system,
            # free up memory ASAP (see MEMORY note)
            del client
            gc.collect()

    return 0


def action(command):
    try:
        # Log the action for the app.
        cs.CSClient().log(APP_NAME, 'action({})'.format(command))

        if command == 'start':
            run_router_app()

        elif command == 'stop':
            # Nothing on stop
            pass

    except Exception as ex:
        cs.CSClient().log(APP_NAME, 'Problem with {} on {}! ex: {}'.format(APP_NAME, command, ex))
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('opt')
    args = parser.parse_args()

    cs.CSClient().log(APP_NAME, 'args: {})'.format(args))
    opt = args.opt.strip()
    if opt not in ['start', 'stop']:
        cs.CSClient().log(APP_NAME, 'Failed to run command: {}'.format(opt))
        exit()

    action(opt)
