# dead_reckoning - Cradlepoint Python SDK Application for GPS Dead Reckoning
# dead_reckoning will extract lat/lon from PCPTMINR NMEA sentence and inject into GPRMC and GPGGA sentences
# and correct posMode and quality values.
# It also provides the ability to send sentences not available in the UI such as GNGSA, GPGSV, and GLGSV
# Load the app and configure settings in System > SDK Data

import json
import socket
import socketserver
import serial
import time
from csclient import EventingCSClient
from pynmeagps import NMEAReader, NMEAMessage

class handler(socketserver.BaseRequestHandler):
    listen_port = 10000
    servers = [{"hostname": "server.example.com", "port": 5005, "protocol": "tcp"}]
    add_sentences = []
    fix_sentences = ["$GPRMC", "$GPGGA"]
    DR_LAT, DR_LON = None, None
    debug = False
    def handle(self):
        try:
            data = self.request.recv(2048).decode()
            debug_log(f'Received NMEA data:\n{data}')
            data = data.split('\r\n')
            PCPTMINR = None
            for line in data:
                if '$PCPTMINR' in line:
                    PCPTMINR = line
            if PCPTMINR:
                try:
                    PCPTMINR = PCPTMINR.split(',')
                    if PCPTMINR[0][0] != '$':
                        PCPTMINR.pop(0)
                    self.DR_LAT, self.DR_LON = float(PCPTMINR[2]), float(PCPTMINR[3])
                    debug_log(f'DR: lat: {self.DR_LAT} lon: {self.DR_LON}')
                except Exception as e:
                    debug_log(f'Exception handling PCPTMINR: {e}')
            sentences = []
            identifier = ''
            for line in data:
                if line:
                    line = line.split(',')
                    # Detect identifier:
                    if line[0][0] == '$':
                        identifier = ''
                        msg_identity = line[0]
                        sentence = ','.join(line)
                    else:
                        identifier = line[0] + ','
                        msg_identity = line[1]
                        sentence = ','.join(line[1:])

                    if msg_identity in self.fix_sentences:
                        fixed_sentence = fix_NMEA(sentence, self.DR_LAT, self.DR_LON)
                        sentences.append(f'{identifier}{fixed_sentence}')
                    else:
                        sentences.append(f'{identifier}{sentence}\r\n')
            # Add Sentences
            nmea = cp.get('status/gps/nmea')
            for sentence in nmea:
                if sentence.split(',')[0] in self.add_sentences:
                    sentences.append(f'{identifier}{sentence}\r\n')
            # Send Sentences to Servers
            send_sentences(sentences)
        except Exception as e:
            cp.logger.exception(f'Exception in handler: {e}')

def fix_NMEA(data, DR_LAT, DR_LON):
    msg = NMEAReader.parse(data, validate=0x00)
    debug_log(f'Before Fix: {msg}')
    # GPRMC Sentences:
    if msg.identity == 'GPRMC':
        status = msg.status
        posMode = msg.posMode
        if posMode == 'N' or status == 'V':
            debug_log(f'FIXING GPRMC SENTENCE!')
            debug_log(f'DR_LAT: {DR_LAT} DR_LON: {DR_LON}')
            if posMode == 'N':
                posMode = 'E'
            if status == 'V':
                status = 'A'
                if DR_LAT and DR_LON:
                    lat, lon = DR_LAT, DR_LON
                else:
                    debug_log('Dead reckoning detected from GPRMC status=V but no PCPTMINR location available!')
                    lat, lon = None, None
                message = NMEAMessage(msg.talker, msg.msgID, 0, time=msg.time, status=status, lat=lat, NS=msg.NS,
                                      lon=lon, EW=msg.EW, spd=msg.spd, cog=msg.cog, date=msg.date, mv=msg.mv,
                                      mvEW=msg.mvEW, posMode=posMode)
        else:  # Status is not 'V' so passthrough msg
            message = msg
    # GPGGA Sentences:
    elif msg.identity == 'GPGGA':
        lat, lon = msg.lat, msg.lon
        quality = msg.quality
        if quality == 0:
            debug_log(f'FIXING GPGGA SENTENCE!')
            quality = 6
            if DR_LAT and DR_LON:
                lat, lon = DR_LAT, DR_LON
            else:
                debug_log('Dead reckoning detected from GPGGA quality=6 but no PCPTMINR location available!')
            message = NMEAMessage(msg.talker, msg.msgID, 0, time=msg.time, lat=lat, NS=msg.NS,
                              lon=lon, EW=msg.EW, quality=quality,  numSV=msg.numSV, HDOP=msg.HDOP,
                              alt=msg.alt, altUnit=msg.altUnit, sep=msg.sep, sepUnit=msg.sepUnit, diffAge=msg.diffAge,
                              diffStation=msg.diffStation)
        else:  # Quality not 0 so passthrough msg
            message = msg
    else:  # Unknown identity - catch all, passthrough
        message = msg
    debug_log(f'After Fix: {message}')
    return fixtimeprecision(message.serialize().decode())


# From FTS App
def fixtimeprecision(nmea):
    """Fix the time precision of GGA/RMC messages.

    NCOS reports timestamps with 3 digits after decimal point, but the FDNY MDT expects LAT to start at a certain position, so it NEEDS 2 decimal places.
    """
    prefix, timestamp, rest = nmea.split(',', 2)
    return nmeafixchecksum(','.join([prefix, timestamp[:9], rest]))


# From FTS App
def nmeafixchecksum(nmea):
    nmea = nmea[:-2] + ('%02X' % nmeachecksum(nmea))
    return nmea


# From FTS App
def nmeachecksum(payload):
    # assert payload[0] == '$' and payload[-3] == '*'
    cksum = 0
    for by in payload[1:-3]:  # Ignore leading $ and trailing checksum.
        cksum = cksum ^ ord(by)
    return cksum

def send_sentences(sentences):
    for server in handler.servers:
        if server["protocol"] == 'tcp':
            my_server = socket.socket()
            try:
                my_server.connect((server["hostname"], server["port"]))
                for sentence in sentences:
                    my_server.sendall(sentence.encode())
                    debug_log(f'Sent TCP to {server["hostname"]}:{server["port"]} - {sentence}')
                    time.sleep(0.05)
            except Exception as e:
                cp.logger.exception(f'Failed to send to server {server["hostname"]} {server["port"]} - {e}')
        elif server["protocol"] == 'udp':
            my_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                my_server.connect((server["hostname"], server["port"]))
                for sentence in sentences:
                    my_server.send(sentence.encode())
                    debug_log(f'Sent UDP to {server["hostname"]}:{server["port"]} - {sentence}')
                    time.sleep(0.05)
            except Exception as e:
                cp.logger.exception(f'Failed to send to server {server["hostname"]} {server["port"]} - {e}')
        elif server["protocol"] == 'serial':
            try:
                with serial.Serial('/dev/ttyS1', 9600, timeout=1) as ser:
                    cp.log("Open /dev/ttyS1: %s" % ser)
                    for sentence in sentences:
                        ser.write(sentence.encode())
                    time.sleep(0.1)
            except Exception as e:
                cp.logger.exception(f'Failed to send to serial: {e}')

def get_appdata(name):
    try:
        appdata = cp.get('config/system/sdk/appdata')
        return json.loads([x["value"] for x in appdata if x["name"] == name][0])
    except Exception as e:
        return None

def get_config(name):
    config = get_appdata(name)
    if config:
        handler.listen_port = config["listen_port"]
        handler.servers = config["servers"]
        handler.add_sentences = config["add_sentences"]
        handler.debug = config["debug"]
        cp.log(f'Loaded config: {config}')
    else:
        config = {
            "listen_port": handler.listen_port,
            "servers": handler.servers,
            "add_sentences": handler.add_sentences,
            "debug": handler.debug
        }
        cp.post('config/system/sdk/appdata', {"name": name, "value": json.dumps(config)})
        cp.log(f'Saved config: {config}')

def enable_GPS_send_to_server():
    try:
        connections = cp.get('config/system/gps/connections/')
        for connection in connections:
            if connection["name"] == 'dead_reckoning':
                return
        cp.log('Enabling GPS Send-to-server to localhost:10000 to enable Dead Reckoning NMEA.')
        gps_config = {
            "client": {
                "destination": "server",
                "num_sentences": 1000,
                "port": 10000,
                "server": "127.0.0.1",
                "time_interval": {
                    "enabled": False,
                    "end_time": "5:00 PM",
                    "start_time": "9:00 AM"
                },
                "useudp": True
            },
            "distance_interval_meters": 0,
            "enabled": True,
            "interval": 5,
            "language": "nmea",
            "name": "dead_reckoning",
            "nmea": {
                "custom_id": "system_id",
                "custom_string": "",
                "include_id": True,
                "prepend_id": False,
                "provide_gga": True,
                "provide_gns": True,
                "provide_inr": True,
                "provide_obd": True,
                "provide_rmc": True,
                "provide_vtg": True
            },
            "stationary_distance_threshold_meters": 20,
            "stationary_movement_event_threshold_seconds": 0,
            "stationary_time_interval_seconds": 0,
            "taip": {
                "include_cr_lf_enabled": False,
                "provide_al": True,
                "provide_cp": True,
                "provide_id": False,
                "provide_ln": True,
                "provide_pv": True,
                "report_msg_checksum_enabled": True,
                "vehicle_id_reporting_enabled": True
            }
        }
        cp.post('config/system/gps/connections', gps_config)
    except Exception as e:
        cp.logger.exception(e)

def debug_log(msg):
    if handler.debug:
        cp.log(msg)

if __name__ == '__main__':
    cp = EventingCSClient('dead_reckoning')
    cp.log(f'Starting...')
    enable_GPS_send_to_server()
    get_config('dead_reckoning')
    cp.log(f'Binding to port {handler.listen_port}')
    server = socketserver.TCPServer(('', handler.listen_port), handler, bind_and_activate=False)
    server.allow_reuse_address = True
    server.server_bind()
    server.server_activate()
    server.serve_forever()
