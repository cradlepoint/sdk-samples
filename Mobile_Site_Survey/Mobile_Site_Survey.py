"""Mobile Site Survey -  Drive testing application for cellular diagnostics with speedtests.

Collects GPS, interface diagnostics, and speedtests and writes results to csv file.
Also supports https://5g-ready.io for data aggregation and export.
Separate ftp_server.py runs on port 2121 for file access.

Supports timed testing (for stationary), and all WAN interface types (mdm, wwan, ethernet)
and slave "surveyors" that can be linked and synced.

See readme.txt for details

"""

from csclient import EventingCSClient
from threading import Thread
import concurrent.futures
from speedtest import Speedtest
from geopy import distance
from settings import settings
import requests
import tornado.web
import json
import os
import time
import datetime

config_path = 'config/hotspot/tos/text'
ftp_dir = 'FTP'


class TestHandler(tornado.web.RequestHandler):
    """Handles test/ endpoint requests."""

    def get(self):
        """Execute test and refresh"""
        try:
            dispatcher.timestamp = float(self.get_argument('timestamp'))
        except:
            dispatcher.timestamp = None
        if dispatcher.timestamp:
            cp.log(f'Remote Test Executed by {self.request.remote_ip} with timestamp: {dispatcher.timestamp}.')
        else:
            cp.log('Manual Test Executed.')
            time.sleep(1)
        dispatcher.manual = True
        self.redirect('/')
        return


class ConfigHandler(tornado.web.RequestHandler):
    """Handles config/ endpoint requests."""

    def get(self):
        """Return app config in JSON for web UI."""
        config = get_config()
        self.write(json.dumps(config))
        return


class SubmitHandler(tornado.web.RequestHandler):
    """Handles submit/ endpoint requests."""

    def get(self):
        """Parse args and update and save config."""
        try:
            dispatcher.config["server_url"] = self.get_argument('server_url')
            dispatcher.config["server_token"] = self.get_argument('server_token')
        except Exception as e:
            cp.log(f'Exception in config submit: {e}')
        try:
            surveyors = self.get_argument('surveyors')
            if surveyors:
                surveyors = surveyors.split(',')
                surveyors = [x.strip() for x in surveyors]
                dispatcher.config["surveyors"] = surveyors

        except Exception as e:
            cp.log(f'Exception parsing surveyors: {e}')
            dispatcher.config["surveyors"] = []
        try:
            dispatcher.config["min_distance"] = int(self.get_argument('min_distance'))
        except:
            dispatcher.config["min_distance"] = 0
        try:
            dispatcher.config["min_time"] = int(self.get_argument('min_time'))
        except:
            dispatcher.config["min_time"] = 0
        try:
            dispatcher.config["enable_surveyors"] = bool(self.get_argument('enable_surveyors'))
        except:
            dispatcher.config["enable_surveyors"] = False
        try:
            dispatcher.config["speedtests"] = bool(self.get_argument('speedtests'))
        except:
            dispatcher.config["speedtests"] = False
        try:
            dispatcher.config["write_csv"] = bool(self.get_argument('write_csv'))
        except:
            dispatcher.config["write_csv"] = False
        try:
            dispatcher.config["send_to_server"] = bool(self.get_argument('send_to_server'))
        except:
            dispatcher.config["send_to_server"] = False
        try:
            dispatcher.config["full_diagnostics"] = bool(self.get_argument('full_diagnostics'))
        except:
            dispatcher.config["full_diagnostics"] = False
        try:
            dispatcher.config["include_logs"] = bool(self.get_argument('include_logs'))
        except:
            dispatcher.config["include_logs"] = False
        try:
            dispatcher.config["debug"] = bool(self.get_argument('debug'))
        except:
            dispatcher.config["debug"] = False
        try:
            dispatcher.config["enabled"] = bool(self.get_argument('enabled'))
        except:
            dispatcher.config["enabled"] = False
        try:
            dispatcher.config["enable_timer"] = bool(self.get_argument('enable_timer'))
        except:
            dispatcher.config["enable_timer"] = False
        try:
            dispatcher.config["all_wans"] = bool(self.get_argument('all_wans'))
        except:
            dispatcher.config["all_wans"] = False

        cp.put(config_path, json.dumps(dispatcher.config))
        cp.log(f'Saved new config: {dispatcher.config}')
        self.redirect('/')
        return


class Dispatcher:
    """Event Handler for tests"""
    config = {}
    modems = []
    surveyors = []
    manual = False
    timestamp = None
    total_bytes = 0
    lat, long, accuracy = None, None, None
    serial_number, mac_address, router_id = None, None, None

    def __init__(self):
        self.serial_number = cp.get('status/product_info/manufacturing/serial_num')
        self.mac_address = cp.get('status/product_info/mac0')
        self.router_id = cp.get('status/ecm/client_id')
        self.config = get_config()

    def loop(self):
        last_location = None
        next_timer = None
        while True:
            try:
                # CHECK TIMER:
                if self.config["enable_timer"]:
                    if next_timer is None:
                        next_timer = time.time() + self.config["min_time"]
                    else:
                        if time.time() > next_timer:
                            cp.log('Starting timed test.')
                            next_timer = time.time() + self.config["min_time"]
                            self.manual = True

                # Verify GPS lock:
                gps_lock = cp.get('/status/gps/fix/lock')
                if self.config["enabled"] and not self.manual and not gps_lock:
                    cp.log('No GPS lock.  Waiting 2 seconds.')
                    time.sleep(2)
                if (self.config["enabled"] and gps_lock) or self.manual:
                    self.lat, self.long, self.accuracy = get_location()
                    latlong = (self.lat, self.long)

                    # CHECK FOR MINIMUM DISTANCE:
                    too_close = False
                    if last_location is not None:
                        dist = distance.distance(latlong, last_location).m
                        if dist < self.config["min_distance"] and not self.manual:
                            cp.log(
                                f'Vehicle within {self.config["min_distance"]}M of last location. Waiting 2 seconds!')
                            too_close = True
                            time.sleep(2)

                    # RUN TESTS:
                    if (self.config["enabled"] and not too_close) or self.manual:
                        cp.log('---> Starting Mobile Site Survey <---')
                        self.modems = get_connected_wans()
                        if self.timestamp is None:  # If not triggered remotely
                            self.timestamp = datetime.datetime.now().timestamp()
                            if self.config["enable_surveyors"]:
                                for surveyor in self.config["surveyors"]:
                                    Thread(target=Surveyor.start, args=(surveyor, self.timestamp), daemon=True).start()
                        if self.modems:
                            routing_policies = cp.get('config/routing/policies')
                            routing_tables = cp.get('config/routing/tables')
                            with concurrent.futures.ThreadPoolExecutor(len(self.modems)) as executor:
                                executor.map(run_tests, self.modems)
                            cp.put('config/routing/policies', routing_policies)
                            cp.put('config/routing/tables', routing_tables)
                        if not self.total_bytes:
                            self.total_bytes = 0.0
                        megabytes = round(self.total_bytes / 1000 / 1000)
                        cp.log(f'Total data used since app start: {megabytes} MB.')
                        self.timestamp = None
                        self.manual = False
                        last_location = latlong
            except Exception as e:
                cp.log(e)


class Surveyor:
    """Sends HTTP Requests to remote router"""

    @staticmethod
    def start(ip_address, timestamp):
        """Sends HTTP request to start survey"""
        try:
            cp.log(f'Starting Surveyor at {ip_address}')
            url = f'http://{ip_address}:8000/test'
            req = requests.get(url, params={"timestamp": timestamp}, timeout=2)
            cp.log(f'Surveyor {ip_address} response: {req.status_code}')
        except Exception as e:
            cp.log(f'Exception starting surveyor: {ip_address} {e}')
        return


def get_location():
    """Return latitude and longitude as floats"""
    # convert latitude to decimal
    lat_deg = cp.get('/status/gps/fix/latitude/degree') or 0
    lat_min = cp.get('/status/gps/fix/latitude/minute') or 0
    lat_sec = cp.get('/status/gps/fix/latitude/second') or 0
    lat = dec(lat_deg, lat_min, lat_sec)

    # convert longitude to decimal
    lon_deg = cp.get('/status/gps/fix/longitude/degree') or 0
    lon_min = cp.get('/status/gps/fix/longitude/minute') or 0
    lon_sec = cp.get('/status/gps/fix/longitude/second') or 0
    long = dec(lon_deg, lon_min, lon_sec)

    accuracy = cp.get('status/gps/fix/accuracy')

    return lat, long, accuracy
    

def get_connected_wans():
    """Return list of connected WAN interfaces"""
    wans = []
    devices = cp.get('status/wan/devices')
    if not dispatcher.config["all_wans"]:
        devices = [x for x in devices if x.startswith('mdm')]
    for device in devices:
        if cp.get(f'status/wan/devices/{device}/status/connection_state') == 'connected':
            wans.append(device)
    debug_log(f'get_connected_wans(): {wans}')
    return wans


def get_config():
    """Return app config from router configuration"""
    try:
        config = json.loads(cp.get(config_path))
    except:
        cp.log(f'No config found - Setting defaults.')
        config = settings
        cp.put(config_path, json.dumps(config))
    return config


def dec(deg, min, sec):
    """Return decimal version of lat or long from deg, min, sec"""
    if str(deg)[:1] == '-':
        dec = deg - (min / 60) - (sec / 3600)
    else:
        dec = deg + (min / 60) + (sec / 3600)
    return dec


def debug_log(msg):
    """Write log when in debug mode"""
    if dispatcher.config["debug"]:
        cp.log(msg)


def ping(host, srcaddr):
    """Ping host and return dict of results"""
    try:
        start = {"host": host, "srcaddr": srcaddr}
        cp.put('control/ping/start', {})
        cp.put('control/ping/start', start)
        result = {}
        pingstats = start
        try_count = 0
        while try_count < 15:
            result = cp.get('control/ping')
            if result and result.get('status') in ["error", "done"]:
                break
            time.sleep(2)
            try_count += 1
        if try_count == 15:
            pingstats['error'] = "No Results - Execution Timed Out"
        else:
            # Parse results text
            parsedresults = result.get('result').split('\n')
            i = 0
            index = 1
            for item in parsedresults:
                if item[0:3] == "---": index = i + 1
                i += 1
            pingstats['tx'] = int(parsedresults[index].split(' ')[0])
            pingstats['rx'] = int(parsedresults[index].split(' ')[3])
            pingstats['loss'] = float(parsedresults[index].split(' ')[6].split('%')[0])
            pingstats['min'] = float(parsedresults[index + 1].split(' ')[5].split('/')[0])
            pingstats['avg'] = float(parsedresults[index + 1].split(' ')[5].split('/')[1])
            pingstats['max'] = float(parsedresults[index + 1].split(' ')[5].split('/')[2])
        return pingstats
    except Exception as e:
        cp.log(f'Exception in PING: {e}')


def run_tests(sim):
    """Main testing function - multithreaded by Dispatcher"""
    download, upload, latency = 0.0, 0.0, 0.0
    bytes_sent, bytes_received = 0, 0
    share = ''
    source_ip = None
    ookla = None
    logs = []

    """Perform diagnostics and speedtests as configured"""
    # ROUTING - Packets sourced from modem IP egress modem device:
    try:
        source_ip = cp.get(f'status/wan/devices/{sim}/status/ipinfo/ip_address')
        cp.put('config/routing/policies/0/priority', 10)

        route_table = {"name": f'MSS-{sim}', "routes": [{"netallow": False, "ip_network": "0.0.0.0/0", "dev": sim, "auto_gateway": True}]}
        req = cp.post('config/routing/tables/', route_table)
        route_table_index = req["data"]
        route_table_id = cp.get(f'config/routing/tables/{route_table_index}/_id_')
        time.sleep(1)
        route_policy = {"ip_version": "ip4", "priority": 1, "table": route_table_id, "src_ip_network": source_ip}
        cp.post(f'config/routing/policies/', route_policy)

        time.sleep(1)  # Let the route simma down
        temptables = cp.get('config/routing/tables')
        temppolicies = cp.get('config/routing/policies')
        debug_log(f'Tables: {temptables} --- Policies: {temppolicies}')
        ookla = Speedtest(source_address=source_ip)
    except Exception as e:
        logstamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logs.append(f'{logstamp} Exception in routing: {e}')
        cp.log(f'Exception in routing: {e}')

    wan_type = cp.get(f'status/wan/devices/{sim}/info/type')

    # GET MODEM DIAGNOSTICS:
    if wan_type == 'mdm':
        diagnostics = cp.get(f'status/wan/devices/{sim}/diagnostics')
        carrier = diagnostics.get('CARRID')
        iccid = diagnostics.get('ICCID')
        product = diagnostics.get('PRD')
    elif wan_type == 'wwan':
        diagnostics = cp.get(f'status/wan/devices/{sim}/diagnostics')
        carrier = source_ip
        iccid = diagnostics.get('SSID')
        product = sim
    else:  # Ethernet
        diagnostics = {}
        carrier = source_ip
        iccid = sim
        product = sim

    # RUN SPEEDTESTS or latency:
    if not dispatcher.config["speedtests"]:
        pong = ping('8.8.8.8', srcaddr=source_ip)
        if pong.get('loss') == 100.0:
            latency = 'FAIL'
        else:
            latency = pong.get('avg')
    else:
        try:
            ookla.get_best_server()
            logstamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            logs.append(f'{logstamp} Starting Download Test on {product} {carrier}.')
            cp.log(f'Starting Download Test on {product} {carrier}.')
            ookla.download()
            if wan_type == 'mdm':  # Capture CA Bands for modems
                diagnostics = cp.get(f'status/wan/devices/{sim}/diagnostics')
            logstamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            logs.append(f'{logstamp} Starting Upload Test on {product} {carrier}.')
            cp.log(f'Starting Upload Test on {product} {carrier}.')
            ookla.upload(pre_allocate=False)
            logstamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            logs.append(f'{logstamp} Speedtest Complete on {product} {carrier}.')
            cp.log(f'Speedtest Complete on {product} {carrier}.')
            if not download:
                download = 0.0
            download = round(ookla.results.download / 1000 / 1000, 2)
            if not upload:
                upload = 0.0
            upload = round(ookla.results.upload / 1000 / 1000, 2)
            latency = ookla.results.ping
            bytes_sent = ookla.results.bytes_sent
            bytes_received = ookla.results.bytes_received
            share = ookla.results.share()
            dispatcher.total_bytes += bytes_sent + bytes_received
        except Exception as e:
            logstamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            logs.append(f'{logstamp} Exception in ookla_speedtest for {product} {carrier}: {e}')
            cp.log(f'Exception in ookla_speedtest for {product} {carrier}: {e}')

    try:
        pretty_timestamp = datetime.datetime.fromtimestamp(dispatcher.timestamp).strftime('%Y-%m-%d %H:%M:%S')
        row = [pretty_timestamp, dispatcher.lat, dispatcher.long, dispatcher.accuracy,
               download, upload, latency, bytes_sent, bytes_received, share]
        if wan_type in ['mdm', 'wwan']:
            row = row + [str(x).replace(',', ' ') for x in diagnostics.values()]
        debug_log(f'ROW: {row}')
        text = ','.join(str(x) for x in row) + '\n'
        logstamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logs.append(f'{logstamp} Results: {text}')
        cp.log(f'Results: {text}')
        cp.put('config/system/desc', text[:1000])
    except Exception as e:
        logstamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logs.append(f'{logstamp} Exception formatting results: {e}')
        cp.log(f'Exception formatting results: {e}')

    # Write to CSV:
    if dispatcher.config["write_csv"]:
        filename = f'Mobile Site Survey - ICCID {iccid}.csv'.replace(':', '')

        # CREATE ftp_dir if it doesnt exist:
        if not os.path.exists(ftp_dir):
            os.makedirs(ftp_dir)

        # CREATE CSV IF IT DOESNT EXIST:
        debug_log(' '.join(os.listdir(ftp_dir)))
        if not os.path.isfile(f'{ftp_dir}/{filename}'):
            logstamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            logs.append(f'{logstamp} {filename} not found.')
            cp.log(f'{filename} not found.')
            with open(f'{ftp_dir}/{filename}', 'wt') as f:
                header = ['Timestamp', 'Lat', 'Long', 'Accuracy', 'Download', 'Upload',
                          'Latency', 'bytes_sent', 'bytes_received', 'Results Image']
                if diagnostics:
                    header = header + [*diagnostics]
                line = ','.join(header) + '\n'
                f.write(line)
            logstamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            logs.append(f'{logstamp} Created new {filename} file.')
            cp.log(f'Created new {filename} file.')

        # APPEND TO CSV:
        try:
            with open(f'{ftp_dir}/{filename}', 'a') as f:
                f.write(text)
                debug_log(f'Successfully wrote to {filename}.')
        except Exception as e:
            logstamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            logs.append(f'{logstamp} Unable to write to {filename}. {e}')
            cp.log(f'Unable to write to {filename}. {e}')

    # SEND TO SERVER:
    if dispatcher.config["send_to_server"]:
        try:
            scell0 = diagnostics.get("BAND_SCELL0")
            scell1 = diagnostics.get("BAND_SCELL1")
            scell2 = diagnostics.get("BAND_SCELL2")
            scell3 = diagnostics.get("BAND_SCELL3")
            sinr = diagnostics.get('SINR')
            rsrp = diagnostics.get('RSRP')
            rsrq = diagnostics.get('RSRQ')
            if wan_type == 'wwan':
                cell_id = diagnostics.get('SSID')
                serdis = diagnostics.get('mode')
                band = diagnostics.get('channel')
                rssi = diagnostics.get('signal_strength')
            else:
                cell_id = diagnostics.get('CELL_ID')
                serdis = diagnostics.get('SERDIS')
                band = diagnostics.get('RFBAND')
                rssi = diagnostics.get('DBM')
            payload = {
                "serial_number": dispatcher.serial_number,
                "mac_address": dispatcher.mac_address,
                "router_id": dispatcher.router_id,
                "timestamp": pretty_timestamp,
                "latitude": str(dispatcher.lat),
                "longitude": str(dispatcher.long),
                "accuracy": str(dispatcher.accuracy),
                "carrier": carrier,
                "cell_id": str(cell_id),
                "service_display": str(serdis),
                "rf_band": str(band),
                "scell0": str(scell0),
                "scell1": str(scell1),
                "scell2": str(scell2),
                "scell3": str(scell3),
                "rssi": str(rssi),
                "sinr": str(sinr),
                "rsrp": str(rsrp),
                "rsrq": str(rsrq),
                "download": str(round(download, 2)),
                "upload": str(round(upload, 2)),
                "latency": str(latency),
                "bytes_sent": bytes_sent,
                "bytes_received": bytes_received,
                "results_url": share
            }
            if dispatcher.config["full_diagnostics"]:
                payload["diagnostics"] = json.dumps(diagnostics)
            if dispatcher.config["include_logs"]:
                payload["logs"] = ';  '.join(logs)
            url = dispatcher.config["server_url"]
            if dispatcher.config["server_token"]:
                headers = {'Content-Type': 'application/json',
                           'Authorization': f'Bearer {dispatcher.config["server_token"]}'}
            else:
                headers = {'Content-Type': 'application/json'}
            debug_log(f'HTTP POST - URL: {url}')
            debug_log(f'HTTP POST - Headers: {headers}')
            debug_log(f'HTTP POST - Payload: {payload}')
            req = requests.post(url, headers=headers, json=payload)
            cp.log(f'HTTP POST Result: {req.status_code} {req.text}')
        except Exception as e:
            logstamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            logs.append(f'{logstamp} Exception in Send to Server: {e}')
            cp.log(f'Exception in Send to Server: {e}')


if __name__ == "__main__":
    cp = EventingCSClient('Mobile Site Survey')
    cp.log('Starting...')
    
    # Wait for WAN connection
    while not cp.get('status/ecm/state') == 'connected':
        time.sleep(1)
    time.sleep(3)
        
    dispatcher = Dispatcher()
    Thread(target=dispatcher.loop, daemon=True).start()
    application = tornado.web.Application([
        (r"/config", ConfigHandler),
        (r"/submit", SubmitHandler),
        (r"/test", TestHandler),
        (r"/(.*)", tornado.web.StaticFileHandler,
         {"path": os.path.dirname(__file__), "default_filename": "index.html"}),
        (r"/FTP", tornado.web.StaticFileHandler,
         {"path": os.path.dirname(__file__) + '/FTP'})
    ])
    application.listen(8000)
    tornado.ioloop.IOLoop.current().start()
