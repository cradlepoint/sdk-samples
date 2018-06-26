"""
A reference application to access GNSS on the IBR1700.
See the readme.txt for more details.

"""

import time
import socket
import settings

from inetline import ReadLine
from app_logging import AppLogger


# Create an AppLogger for logging to syslog in NCOS.
log = AppLogger()


try:
    log.debug('Starting {}'.format(settings.APP_NAME))
    gnss_addr = ("127.0.0.1", 17488)

    gnssd_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    log.debug("Attempting sock.connect({})".format(gnss_addr))
    gnssd_sock.connect(gnss_addr)

    # Turns on ALL messages. Only way to turn off is to close the socket.
    log.debug("Attempting sock.send(b'ALL\\r\\n')")
    gnssd_sock.sendall(b'ALL\r\n')

    # Enable IMU messages
    log.debug("Attempting sock.send(b'IMU yes\\r\\n')")
    gnssd_sock.sendall(b'IMU yes\n\r')

    receive_line = ReadLine()

    while True:
        # read as much possible
        buf = gnssd_sock.recv(1024)
        # log.debug('buf: {}'.format(buf))

        # push buffer into the state machine for parsing
        for b in buf:
            c = chr(b)
            s = receive_line.recv(c)
            if s is not None:
                # received a full NMEA line!
                log.info(s)

        time.sleep(10)

except Exception as e:
    log.error('Exception: {}'.format(e))
finally:
    if gnssd_sock:
        gnssd_sock.shutdown(socket.SHUT_RDWR)
        gnssd_sock.close()
