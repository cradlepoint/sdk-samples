"""
A reference application to access GNSS on the IBR1700.
See the readme.txt for more details.

"""

import time
import socket

from inetline import ReadLine
from csclient import EventingCSClient

cp = EventingCSClient('ibr1700_gnss')
gnssd_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    cp.log('Starting...')
    gnss_addr = ("127.0.0.1", 17488)

    cp.log("Attempting sock.connect({})".format(gnss_addr))
    gnssd_sock.connect(gnss_addr)

    # Turns on ALL messages. Only way to turn off is to close the socket.
    cp.log("Attempting sock.send(b'ALL\\r\\n')")
    gnssd_sock.sendall(b'ALL\r\n')

    # Enable IMU messages
    cp.log("Attempting sock.send(b'IMU yes\\r\\n')")
    gnssd_sock.sendall(b'IMU yes\n\r')

    receive_line = ReadLine()

    while True:
        # read as much possible
        buf = gnssd_sock.recv(1024)
        # cp.log('buf: {}'.format(buf))

        # push buffer into the state machine for parsing
        for b in buf:
            c = chr(b)
            s = receive_line.recv(c)
            if s is not None:
                # received a full NMEA line!
                cp.log(s)

        time.sleep(10)

except Exception as e:
    cp.log('Exception: {}'.format(e))
finally:
    if gnssd_sock:
        gnssd_sock.shutdown(socket.SHUT_RDWR)
        gnssd_sock.close()
