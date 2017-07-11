"""
A basic Modbus/TCP to RTU bridge
"""

import socket
import select
import serial
import time
import gc
from threading import Event

from cp_lib.app_base import CradlepointAppBase
from cp_lib.buffer_dump import logger_buffer_dump
from cp_lib.modbus.transaction import validate_ia_protocol, \
    IA_PROTOCOL_MBTCP, IA_PROTOCOL_MBRTU, IA_PROTOCOL_MBASC
from cp_lib.modbus.transaction_modbus import ModbusTransaction, \
    ModbusBadForm, ModbusBadChecksum
from cp_lib.parse_data import parse_integer, clean_string
from cp_lib.parse_duration import TimeDuration
from cp_lib.probe_serial import SerialGPIOConfig, SerialRedirectorConfig, \
    SerialGpsConfig


# used to prevent long-term blocking
DEF_SELECT_TIMEOUT = 5.0

# to help clear out TIME_WAIT state on server, delay before existing
# set to 0/None to skip this
DEF_TIME_WAIT_DELAY = None


def run_router_app(app_base):
    """

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :return:
    """
    # logger.debug("Settings({})".format(sets))

    # first, confirm no other function using serial
    value = SerialRedirectorConfig(app_base)
    value.refresh()
    if value.enabled():
        app_base.logger.error("Serial Redirector Function is Active!")
        app_base.logger.error("Aborting SDK application")
        return -3
    app_base.logger.debug("Good: Serial Redirector Function is Disabled.")

    value = SerialGpsConfig(app_base)
    value.refresh()
    if value.enabled():
        app_base.logger.error("Serial GPS Echo Function is Active!")
        app_base.logger.error("Aborting SDK application")
        return -4
    app_base.logger.debug("Good: Serial GPS Function is Disabled.")

    value = SerialGPIOConfig(app_base)
    value.refresh()
    if value.enabled():
        app_base.logger.error("Serial GPIO Function is Active!")
        app_base.logger.error("Aborting SDK application")
        return -5
    app_base.logger.debug("Good: Serial GPIO Function is Disabled.")

    server_loop = ModbusBridge()
    server_loop.logger = app_base.logger

    if "modbus_ip" in app_base.settings:
        temp = app_base.settings["modbus_ip"]
        if "host_ip" in temp:
            # assume is string of correct format
            server_loop.host_ip = clean_string(temp["host_ip"])

        if "host_port" in temp:
            # force to integer
            server_loop.host_port = parse_integer(temp["host_port"])

        if "idle_timeout" in temp:
            # support seconds, or like '5 min'
            duration = TimeDuration(clean_string(temp["idle_timeout"]))
            server_loop.idle_timeout = duration.get_seconds()

        if "protocol" in temp:
            value = validate_ia_protocol(clean_string(temp["protocol"]))
            if value not in (IA_PROTOCOL_MBTCP, IA_PROTOCOL_MBRTU,
                             IA_PROTOCOL_MBASC):
                raise ValueError(
                    "Invalid IP-packed Modbus Protocol {}".format(type(value)))
            server_loop.host_protocol = value

    if "modbus_serial" in app_base.settings:
        temp = app_base.settings["modbus_serial"]
        if "port_name" in temp:
            server_loop.serial_name = clean_string(temp["port_name"])

        if "baud_rate" in temp:
            server_loop.serial_baud = parse_integer(temp["baud_rate"])

        if "parity" in temp:
            server_loop.serial_baud = parse_integer(temp["baud_rate"])

        if "protocol" in temp:
            value = validate_ia_protocol(clean_string(temp["protocol"]))
            # confirm is serial, so RTU or ASCII
            if value not in (IA_PROTOCOL_MBRTU, IA_PROTOCOL_MBASC):
                raise ValueError(
                    "Invalid Serial Modbus Protocol {}".format(type(value)))
            server_loop.serial_protocol = value

    # this should run forever
    try:
        result = server_loop.run_loop()

    except KeyboardInterrupt:
        result = 0

    return result


class ModbusBridge(object):

    # note in router, 'localhost' literally means only internal
    DEF_HOST_IP = ''
    DEF_HOST_PORT = 8512
    DEF_HOST_PROTOCOL = IA_PROTOCOL_MBTCP
    DEF_IDLE_TIMEOUT = 300

    DEF_SERIAL_PORT = '/dev/ttyS1'
    DEF_SERIAL_BAUD = 9600
    DEF_SERIAL_PARITY = 'N'
    DEF_SERIAL_PROTOCOL = IA_PROTOCOL_MBRTU

    def __init__(self):

        # thread-safe event to halt execution
        self.running = Event()
        self.running.set()

        # various server settings
        self.host_ip = self.DEF_HOST_IP
        self.host_port = self.DEF_HOST_PORT
        self.host_protocol = self.DEF_HOST_PROTOCOL

        # used to abort an idle client connection
        self.idle_timeout = self.DEF_IDLE_TIMEOUT
        self.last_activity = time.time()

        self.serial_name = self.DEF_SERIAL_PORT
        self.serial_baud = self.DEF_SERIAL_BAUD
        self.serial_parity = self.DEF_SERIAL_PARITY
        self.serial_protocol = self.DEF_SERIAL_PROTOCOL
        self.ser = None

        self.logger = None

        # hold our server socket
        self.server = None
        self._rd_ready = None

        # this is our object to hold, parse, and transmute packets
        self.modbus = ModbusTransaction()

        return

    def run_loop(self):
        """
        The main outer loop - make sure server is listening

        :return:
        """

        result_code = 0

        try:
            while self.running.is_set():

                try:
                    # this opens the self.server
                    self.server = self.bind_server()

                except ConnectionError:
                    # we exit, because if we cannot secure the resource, the
                    # failure is very likely permanent. ideally would cause
                    # a reboot
                    self.running.clear()
                    result_code = -1
                    break

                # here, self.server should magically be valid and open
                self._rd_ready = [self.server]

                while self.running.is_set():
                    # loop forever
                    _rd, _wr, _x = select.select(self._rd_ready, [], [],
                                                 DEF_SELECT_TIMEOUT)

                    # handle the inputs/receives
                    for sock in _rd:
                        if sock == self.server:
                            # then is a new client
                            self.accept_client()

                        else:
                            # this is a client
                            data = sock.recv(1024)
                            if not data:
                                # then client socket closed/failed
                                self.remove_client(sock)

                            else:
                                try:
                                    result = self.handle_data(data)

                                except ConnectionError:
                                    # if Serial() open fails, ConnectionError
                                    # is thrown; no point remaining in loop
                                    self.running.clear()
                                    result_code = -2
                                    break

                                if result:
                                    sock.send(result)

                                else:
                                    # then hand-up!
                                    self.remove_client(sock)

                    # for now, ignore the _wr, and _x lists

                    if len(self._rd_ready) < 2:
                        # then no client, the DEF_SELECT_TIMEOUT happened
                        self.logger.debug("waiting")

                    elif self.idle_timeout is not None:
                        # then we have a client, so check the idle_timeout
                        delta = time.time() - self.last_activity
                        if delta > self.idle_timeout:
                            self.logger.warning("Idle Timeout!")
                            for sock in self._rd_ready:
                                if sock != self.server:
                                    self.remove_client(sock)

                        else:
                            self.logger.debug(
                                "idle:{} sec".format(round(delta, 2)))

                    # loop up

        finally:
            # do some clean up
            # self.logger.debug("Do Clean-Up")
            if self.server is not None:
                self.logger.debug("TCP server is not None, try cleanup")
                try:
                    self.server.close()
                    time.sleep(1.0)
                    del self.server
                except:
                    self.logger.exception("server.close() failed")
                    raise

            if self.ser is not None:
                self.logger.debug("Serial port is not None, try cleanup")
                try:
                    self.ser.close()
                    time.sleep(1.0)
                    del self.ser
                except:
                    self.logger.exception("Serial.close() failed")
                    raise

        # force garbage collection
        gc.collect()

        if DEF_TIME_WAIT_DELAY:
            self.logger.debug("Final TIME_WAIT delay:{} sec".format(
                DEF_TIME_WAIT_DELAY))
            time.sleep(DEF_TIME_WAIT_DELAY)

        # we're to stop running
        return result_code

    def bind_server(self):
        """
        Wrap the bind process
        :return:
        """
        # define the socket resource, including the type (stream == "TCP")
        bind_address = (self.host_ip, self.host_port)
        self.logger.debug("Preparing TCP socket {}".format(bind_address))
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # try to speed up reuse
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # attempt to actually lock resource, which may fail if unavailable
        try:
            self.server.bind(bind_address)
        except OSError as msg:
            self.logger.error("socket.bind() failed - {}".format(msg))
            self.server.close()
            self.server = None
            self.logger.error("TCP server socket closed")
            raise ConnectionError

        # only allow 1 client at a time
        self.server.listen(1)
        self.logger.info("Waiting on TCP {}, protocol:{}".format(
            bind_address, self.host_protocol))

        return self.server

    def accept_client(self):
        """
        have a nibble on the server line, reel in client

        :return:
        """
        client, address = self.server.accept()
        self.logger.info("Accepted connection from {}".format(address))

        # for cellular, ALWAYS enable TCP Keep Alive
        client.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

        self._rd_ready.append(client)
        self.last_activity = time.time()
        return

    def remove_client(self, client):
        """
        have a nibble on the server line, reel in client

        :return:
        """
        self.logger.info("Client disconnected")

        client.close()

        if client in self._rd_ready:
            self._rd_ready.remove(client)

        # try to force faster memory clean-up
        gc.collect()
        return

    def handle_data(self, data):
        """

        :param bytes data:
        :return:
        """
        logger_buffer_dump(self.logger, "TCP-REQ", data)
        self.last_activity = time.time()

        response = None

        try:
            # parse the MB/TCP request
            self.modbus.set_request(data, self.host_protocol)
            # self.logger.debug("REQ:{}".format(self.modbus.attrib))

        except (ModbusBadForm, ModbusBadChecksum):
            # this could be a bad setting
            self.logger.warning("Bad Modbus Form")
            return None

        # retrieve as MB/RTU request
        modbus_rtu = self.modbus.get_request(self.serial_protocol)
        # self.logger.debug("SER:{}".format(modbus_rtu))

        # if Serial() open fails, we'll throw ConnectionError, which this
        # code assumes the CALLER of handle_data() handles
        response = self.send_serial(modbus_rtu)
        if response and len(response):
            # parse the MB/RTU in
            try:
                self.modbus.set_response(response, self.serial_protocol)
                response = self.modbus.get_response(self.host_protocol)

            except ModbusBadForm:
                # this could be a bad setting
                self.logger.warning("Bad Modbus Form")
                response = None

            except ModbusBadChecksum:
                # likely line noise or loose wire
                self.logger.warning("Bad Checksum")
                response = None

        else:
            # in truth, if client is:
            #  Modbus/TCP - should return exception 0x0B
            # Modbus/RTU - no response
            self.logger.debug("No response")
            response = None

        if response is None:
            # then re-form as the correct err response, which may be None
            response = self.modbus.get_no_response_error(self.host_protocol)

        logger_buffer_dump(self.logger, "TCP-RSP", response)
        # else was in error, hang-up
        return response

    def send_serial(self, data):
        """
        Send what is assumed a Modbus serial packet. If the serial port is
        NOT open (so self.ser == None), this this routine tries to open it.

        If the open fails, a ConnectError is raised, which is the SDK apps'
        signal to quit/abort running.

        :param bytes data: the Modbus serial message, which could be either
                           Modbus/RTU or ASCII
        :return: the response data, which might be b'' (empty/no response)
        """
        import logging

        if self.ser is None:
            self.logger.info("Open serial port:{}".format(self.serial_name))
            try:
                self.ser = serial.Serial(
                    port=self.serial_name, baudrate=self.serial_baud,
                    bytesize=8, parity=self.serial_parity, stopbits=1,
                    timeout=1, xonxoff=0, rtscts=0)
                self.ser.setDTR(True)
                # self.ser.setRTS(True)

            except serial.SerialException:
                self.ser = None
                self.logger.exception("Open of serial port failed")
                raise ConnectionError("Open of serial port failed")

            self.logger.info("Serial Protocol:{}".format(self.serial_protocol))

        if self.logger.getEffectiveLevel() <= logging.DEBUG:
            if self.serial_protocol == IA_PROTOCOL_MBASC:
                # for ASCII, just print as string
                self.logger.debug("ASC-REQ:{}".format(data))
            else:  # for RTU, we want HEX form
                logger_buffer_dump(self.logger, "RTU-REQ", data)

        self.ser.write(data)

        # we have 1 second response timeout in the Serial() open
        time.sleep(0.25)
        response = self.ser.read(256)

        if self.logger.getEffectiveLevel() <= logging.DEBUG:
            if response is None or response == b'':
                self.logger.debug("SER-RSP:None/No response")
            elif self.serial_protocol == IA_PROTOCOL_MBASC:
                # for ASCII, just print as string
                self.logger.debug("ASC-RSP:{}".format(response))
            else:  # for RTU, we want HEX form
                logger_buffer_dump(self.logger, "RTU-RSP", response)

        return response

if __name__ == "__main__":
    import sys

    my_app = CradlepointAppBase("serial_port/mbus_simple_bridge",
                                call_router=False)

    _result = run_router_app(my_app)
    my_app.logger.info("Exiting, status code is {}".format(_result))
    sys.exit(_result)
