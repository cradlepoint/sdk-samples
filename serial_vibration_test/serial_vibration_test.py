import os
import time
import socket
import serial

_host = ('192.168.0.1', 5556)
_message = 'Found that the uart port is {}\n'
_port = '/dev/ttyUSB0'
_speed = 9600

def status(port):
    return '{}connected'.format('' if os.path.exists(port) else 'dis')

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind(_host)
    s.listen(1)
    conn, addr = s.accept()
    with conn:
        conn.send('Connected from {} port {}\n'.format(addr[0], addr[1]).encode())

        ser = serial.Serial(_port, _speed, timeout=0)

        prev_state = status(_port)
        conn.send(_message.format(prev_state).encode())

        while True:
            curr_state = status(_port)

            if curr_state != prev_state:
                prev_state = curr_state
                conn.send(_message.format(prev_state).encode())

            try:
                if curr_state == 'connected':
                    if not ser.isOpen():
                        ser.open()

                    if ser.inWaiting():
                        data = ser.read(ser.in_waiting)
                        ser.write(data)

                if curr_state == 'disconnected':
                    if ser.isOpen():
                        ser.close()

                    if ser.inWaiting():
                        ser.flush()

            except:
                pass

            time.sleep(1)
