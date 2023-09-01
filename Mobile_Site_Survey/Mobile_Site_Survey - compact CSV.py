"""Mobile Site Survey -  Drive testing application for cellular diagnostics with speedtests.

Access web interface on port 8000.  Results CSV files can be accessed on port 8001.
Collects GPS, interface diagnostics, and speedtests and writes results to csv file.
Also supports https://5g-ready.io for data aggregation and export.
Results are also put in the description field for easy viewing in NCM devices grid.
Delete the description to run a manual test.

Supports timed testing (for stationary), and all WAN interface types (mdm, wwan, ethernet)
and slave "surveyors" (other routers) than can synchronize tests with the master.

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

results_dir = 'results'

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
        config = get_config('Mobile_Site_Survey')
        config["results"] = dispatcher.results
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
            dispatcher.config["packet_loss"] = bool(self.get_argument('packet_loss'))
        except:
            dispatcher.config["packet_loss"] = False
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

        save_config(dispatcher.config)
        cp.log(f'Saved new config: {dispatcher.config}')
        self.redirect('/')
        return


class Dispatcher:
    """Event Handler for tests"""
    config = {}
    modems = []
    pings = {}
    results = ''
    surveyors = []
    manual = False
    timestamp = None
    total_bytes = {}
    lat, long, accuracy = None, None, None
    serial_number, mac_address, router_id = None, None, None

    def __init__(self):
        self.serial_number = cp.get('status/product_info/manufacturing/serial_num')
        self.mac_address = cp.get('status/product_info/mac0')
        self.router_id = cp.get('status/ecm/client_id')
        self.config = get_config('Mobile_Site_Survey')

    def loop(self):
        last_location = None
        next_timer = None
        while True:
            try:
                self.modems = get_connected_wans()
                # Run pings:
                if self.config["packet_loss"]:
                    for modem in self.modems:
                        if not self.pings.get(modem):
                            self.pings[modem] = {"tx": 0, "rx": 0}
                        iface = cp.get(f'status/wan/devices/{modem}/info/iface')
                        pong = ping('8.8.8.8', iface)
                        debug_log(json.dumps(pong))
                        # Track total tx/rx per modem to calculate loss between points
                        self.pings[modem]["tx"] += pong["tx"]
                        self.pings[modem]["rx"] += pong["rx"]
                        debug_log(
                            f'Cumulative ping results for {modem}: {self.pings[modem]["rx"]} of {self.pings[modem]["tx"]}')

                # CHECK TIMER:
                if self.config["enable_timer"]:
                    if next_timer is None:
                        next_timer = time.time()
                    if time.time() >= next_timer:
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
                        cp.log('---> Starting Survey <---')
                        for modem in self.modems:
                            if not self.total_bytes.get(modem):
                                self.total_bytes[modem] = 0
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
                            pretty_timestamp = datetime.datetime.fromtimestamp(self.timestamp).strftime(
                                '%Y-%m-%d %H:%M:%S')
                            title = f' 📅 {pretty_timestamp} 📍{dispatcher.lat}, {dispatcher.long} '
                            bar = '〰〰'
                            self.results = f'  {bar}{title}{bar}\n\n' + self.results
                            cp.put('config/routing/policies', routing_policies)
                            cp.put('config/routing/tables', routing_tables)
                        cp.log('---> Survey Complete <---')
                        self.timestamp = None
                        self.manual = False
                        last_location = latlong
                time.sleep(0.1)
            except Exception as e:
                cp.log(f'Exception in dispatcher loop: {e}')


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
    fix = cp.get('status/gps/fix')
    try:
        lat_deg = fix['latitude']['degree']
        lat_min = fix['latitude']['minute']
        lat_sec = fix['latitude']['second']
        lon_deg = fix['longitude']['degree']
        lon_min = fix['longitude']['minute']
        lon_sec = fix['longitude']['second']
        lat = dec(lat_deg, lat_min, lat_sec)
        long = dec(lon_deg, lon_min, lon_sec)
        accuracy = fix.get('accuracy')
        return lat, long, accuracy
    except:
        return None, None, None

def get_location_DR():
    """Return latitude and longitude from PCPTMINR (Dead Reckoning) as floats"""
    try:
        nmea = cp.get('status/gps/nmea')
        for sentence in nmea:
            fields = sentence.split(',')
            if fields[0] == '$PCPTMINR':
                lat = fields[2]
                long = fields[3]
                accuracy = round((float(fields[8]) + float(fields[9]))/2, 2)
                return lat, long, accuracy
    except Exception as e:
        cp.logger.exception(e)
        return None, None, None

def get_connected_wans():
    """Return list of connected WAN interfaces"""
    wans = []
    devices = cp.get('status/wan/devices')
    if not dispatcher.config["all_wans"]:
        devices = [x for x in devices if x.startswith('mdm')]
    for device in devices:
        if cp.get(f'status/wan/devices/{device}/status/connection_state') == 'connected':
            wans.append(device)
    return wans

def save_config(config):
    try:
        appdata = cp.get('config/system/sdk/appdata')
        for data in appdata:
            if data["name"] == 'Mobile_Site_Survey':
                cp.put(f'config/system/sdk/appdata/{data["_id_"]}/value', json.dumps(config))
                return
    except Exception as e:
        cp.logger.exception(e)

def get_appdata(name):
    try:
        appdata = cp.get('config/system/sdk/appdata')
        return json.loads([x["value"] for x in appdata if x["name"] == name][0])
    except Exception as e:
        return None

def get_config(name):
    config = get_appdata(name)
    if not config:
        config = settings
        cp.post('config/system/sdk/appdata', {"name": name, "value": json.dumps(config)})
        cp.log(f'No config found - Saved default config: {config}')
    return config

def dec(deg, min, sec):
    """Return decimal version of lat or long from deg, min, sec"""
    if str(deg)[0] == '-':
        dec = deg - (min / 60) - (sec / 3600)
    else:
        dec = deg + (min / 60) + (sec / 3600)
    return round(dec, 5)


def debug_log(msg):
    """Write log when in debug mode"""
    if dispatcher.config["debug"]:
        cp.log(msg)

def log_all(msg, logs):
    """Write consistent messages across all logs"""
    logstamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cp.log(msg)
    logs.append(f'{logstamp} {msg}')
    dispatcher.results = f'{msg}\n\n' + dispatcher.results

def ping(host, iface):
    """Ping host and return dict of results"""
    try:
        start = {"bind_ip": False, "deadline": "Same as timeout", "df": "do", "family": "inet", "fwmark": None,
                 "host": host, "iface": iface, "interval": 0.5, "num": 10, "size": 56, "srcaddr": None, "timeout": 15}

        cp.put('control/ping/start', {})
        cp.put('control/ping/status', '')
        cp.put('control/ping/start', start)
        pingstats = start
        try_count = 0
        while try_count < 30:
            result = cp.get('control/ping')
            if result.get('status') in ["error", "done"]:
                break
            time.sleep(0.5)
            try_count += 1
        else:
            pingstats['error'] = "No Results - Execution Timed Out"
            return pingstats
        # Parse results text
        parsedresults = result.get('result').split('\n')
        i = 0
        index = 1
        for item in parsedresults:
            if item[0:3] == "---": index = i + 1
            i += 1
        try:
            pingstats['tx'] = int(parsedresults[index].split(' ')[0])
            pingstats['rx'] = int(parsedresults[index].split(' ')[3])
            pingstats['loss'] = float(parsedresults[index].split(' ')[6].split('%')[0])
            pingstats['min'] = float(parsedresults[index + 1].split(' ')[5].split('/')[0])
            pingstats['avg'] = float(parsedresults[index + 1].split(' ')[5].split('/')[1])
            pingstats['max'] = float(parsedresults[index + 1].split(' ')[5].split('/')[2])
        except Exception as e:
            cp.log(f'Exception parsing ping results: {e}')
        return pingstats
    except Exception as e:
        cp.log(f'Exception in PING: {e}')


def run_tests(sim):
    """Main testing function - multithreaded by Dispatcher"""
    download, upload, latency = 0.0, 0.0, 0.0
    bytes_sent, bytes_received, packet_loss_percent = 0, 0, 0
    share = ''
    source_ip = None
    ookla = None
    logs = []

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
        time.sleep(1)

        # Instantiate Ookla with source_ip from sim
        retries = 0
        while retries < 5:
            try:
                ookla = Speedtest(source_address=source_ip)
                break
            except:
                cp.log(f'Ookla failed to start for source {source_ip} on {sim}.  Trying again...')
                time.sleep(1)
                retries += 1
                pass
        else:
            log_all(f'Ookla startup exceeded retries for source {source_ip} on {sim}')
            raise Exception
    except Exception as e:
        msg = f'Exception in routing: {e}'
        log_all(msg, logs)

    wan_info = cp.get(f'status/wan/devices/{sim}/info')
    wan_type = wan_info.get('type')
    iface = wan_info.get('iface')

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

    # Latency test:
    pong = ping('8.8.8.8', iface)
    if pong.get('loss') == 100.0:
        latency = 'FAIL'
    else:
        latency = round(pong.get('avg'))

    # Ookla Speedtest
    try:
        retries = 0
        while retries < 3:
            try:
                ookla.get_best_server()
                break
            except Exception as e:
                retries += 1
                cp.log(f'Attempt {retries} of 3 to get_best_server() failed: {e}')
                raise Exception

        logstamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logs.append(f'{logstamp} Starting Download Test on {product} {carrier}.')
        cp.log(f'Starting Download Test on {product} {carrier}.')
        ookla.download()  # Ookla Download Test
        if wan_type == 'mdm':  # Capture CA Bands for modems
            diagnostics = cp.get(f'status/wan/devices/{sim}/diagnostics')
        logstamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logs.append(f'{logstamp} Starting Upload Test on {product} {carrier}.')
        cp.log(f'Starting Upload Test on {product} {carrier}.')
        ookla.upload(pre_allocate=False)  # Ookla upload test
        logstamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logs.append(f'{logstamp} Speedtest Complete on {product} {carrier}.')
        cp.log(f'Speedtest Complete on {product} {carrier}.')

        # Format results
        if not download:
            download = 0.0
        download = round(ookla.results.download / 1000 / 1000, 2)
        if not upload:
            upload = 0.0
        upload = round(ookla.results.upload / 1000 / 1000, 2)
        latency = round(ookla.results.ping)
        bytes_sent = ookla.results.bytes_sent or 0
        bytes_received = ookla.results.bytes_received or 0
        share = ookla.results.share()
        debug_log(f'bytes_sent: {bytes_sent} bytes_received: {bytes_received}')
        dispatcher.total_bytes[sim] += bytes_sent + bytes_received
    except Exception as e:
        msg = f'Exception in run_tests() for {product} {carrier}: {e}'
        log_all(msg, logs)

    # Calculate packet loss
    try:
        if dispatcher.config["packet_loss"]:
            tx = dispatcher.pings[sim]["tx"]
            rx = dispatcher.pings[sim]["rx"]
            if tx == rx:
                packet_loss_percent = 0
            else:
                packet_loss_percent = round((tx-rx)/tx*100)
            dispatcher.pings[sim]["rx"] = 0
            dispatcher.pings[sim]["tx"] = 0
        else:
            tx, rx, packet_loss_percent = 0, 0, 0
    except Exception as e:
        cp.log(f'Exception calculating packet loss: {e}')

    # Log results
    pretty_timestamp = datetime.datetime.fromtimestamp(dispatcher.timestamp).strftime('%Y-%m-%d %H:%M:%S')
    try:
        row = [pretty_timestamp, dispatcher.lat, dispatcher.long, dispatcher.accuracy,
               carrier, download, upload, latency, packet_loss_percent, bytes_sent, bytes_received, share]
        if wan_type == 'wwan':
            row = row + [str(x).replace(',', ' ') for x in diagnostics.values()]
        elif wan_type == 'mdm':
            cell_id = diagnostics.get('CELL_ID')
            rfband = diagnostics.get('RFBAND')
            scell0 = diagnostics.get("BAND_SCELL0")
            scell1 = diagnostics.get("BAND_SCELL1")
            scell2 = diagnostics.get("BAND_SCELL2")
            scell3 = diagnostics.get("BAND_SCELL3")
            serdis = diagnostics.get('SERDIS')
            if serdis == '5G':
                serdis = diagnostics.get('SRVC_TYPE_DETAILS', '5G')
            dbm = diagnostics.get('DBM')
            sinr = diagnostics.get('SINR')
            rsrp = diagnostics.get('RSRP')
            rsrq = diagnostics.get('RSRQ')
            sinr_5g = diagnostics.get('SINR_5G')
            rsrp_5g = diagnostics.get('RSRP_5G')
            rsrq_5g = diagnostics.get('RSRQ_5G')
            rfband_5g = diagnostics.get('RFBAND_5G')
            row = row + [dbm, sinr, rsrp, rsrq, sinr_5g, rsrp_5g, rsrq_5g, cell_id, serdis, rfband, rfband_5g, scell0, scell1, scell2, scell3]
        debug_log(f'ROW: {row}')
        text = ','.join(str(x) for x in row) + '\n'
        logstamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logs.append(f'{logstamp} Results: {text}')
        cp.log(f'Results: {text}')
        # cp.put('config/system/desc', text[:1000])
        pretty_results = f'                   📶 {carrier} ⏱{latency}ms ⇄ {packet_loss_percent}% loss ({rx} of {tx})\n' \
                         f'                   ↓{download}Mbps ↑{upload}Mbps 📈 {round(dispatcher.total_bytes[sim] / 1000 / 1000)}MB used.'
        log_all(pretty_results, logs)
    except Exception as e:
        msg = f'Exception formatting results: {e}'
        log_all(msg, logs)

    # Write to CSV:
    if dispatcher.config["write_csv"]:
        filename = f'Mobile Site Survey - ICCID {iccid}.csv'.replace(':', '')

        # CREATE results_dir if it doesnt exist:
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)

        # CREATE CSV IF IT DOESNT EXIST:
        debug_log(' '.join(os.listdir(results_dir)))
        if not os.path.isfile(f'{results_dir}/{filename}'):
            logstamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            logs.append(f'{logstamp} {filename} not found.')
            cp.log(f'{filename} not found.')
            with open(f'{results_dir}/{filename}', 'wt') as f:
                header = ['Timestamp', 'Lat', 'Long', 'Accuracy', 'Carrier', 'Download', 'Upload',
                          'Latency', 'Packet Loss Percent', 'bytes_sent', 'bytes_received', 'Results Image']
                if diagnostics:
                    if wan_type == 'wwan':
                        header = header + [*diagnostics]
                    elif wan_type =='mdm':
                        header = header + ['DBM', 'SINR', 'RSRP', 'RSRQ', 'SINR_5G', 'RSRP_5G', 'RSRQ_5G', 'Cell ID',
                                           'Serice Display', 'RF Band', 'RF Band 5G', 'SCELL0', 'SCELL1', 'SCELL2', 'SCELL3',]
                line = ','.join(header) + '\n'
                f.write(line)
            logstamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            logs.append(f'{logstamp} Created new {filename} file.')
            cp.log(f'Created new {filename} file.')

        # APPEND TO CSV:
        try:
            with open(f'{results_dir}/{filename}', 'a') as f:
                f.write(text)
                debug_log(f'Successfully wrote to {filename}.')
        except Exception as e:
            msg = f'Unable to write to {filename}. {e}'
            log_all(msg, logs)

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
            sinr_5g = diagnostics.get('SINR_5G')
            rsrp_5g = diagnostics.get('RSRP_5G')
            rsrq_5g = diagnostics.get('RSRQ_5G')
            rfband_5g = diagnostics.get('RFBAND_5G')
            if wan_type == 'wwan':
                cell_id = diagnostics.get('SSID')
                serdis = diagnostics.get('mode')
                band = diagnostics.get('channel')
                rssi = diagnostics.get('signal_strength')
            else:
                cell_id = diagnostics.get('CELL_ID')
                serdis = diagnostics.get('SERDIS')
                if serdis == '5G':
                    serdis = diagnostics.get('SRVC_TYPE_DETAILS', '5G')
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
                "rfband_5g": str(rfband_5g),
                "scell0": str(scell0),
                "scell1": str(scell1),
                "scell2": str(scell2),
                "scell3": str(scell3),
                "rssi": str(rssi),
                "sinr": str(sinr),
                "sinr_5g": str(sinr_5g),
                "rsrp": str(rsrp),
                "rsrp_5g": str(rsrp_5g),
                "rsrq": str(rsrq),
                "rsrq_5g": str(rsrq_5g),
                "download": str(round(download, 2)),
                "upload": str(round(upload, 2)),
                "latency": str(latency),
                "packet_loss_percent": packet_loss_percent,
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
            # retries
            retries = 0
            while retries < 5:
                try:
                    req = requests.post(url, headers=headers, json=payload)
                    if req.status_code < 300:
                        break
                except Exception as e:
                    cp.log(f'Exception in POST: {e}')
                    time.sleep(1)
                retries += 1
            cp.log(f'HTTP POST Result: {req.status_code} {req.text}')
        except Exception as e:
            msg = f'Exception in Send to Server: {e}'
            log_all(msg, logs)

def manual_test(path, value, *args):
    if not value:
        debug_log('Blank Description - Executing Manual Test')
        dispatcher.manual = True

if __name__ == "__main__":
    cp = EventingCSClient('Mobile Site Survey')
    cp.log('Starting...')
    
    # Wait for WAN connection
    while not cp.get('status/wan/connection_state') == 'connected':
        time.sleep(1)
    time.sleep(3)
        
    dispatcher = Dispatcher()
    Thread(target=dispatcher.loop, daemon=True).start()
    cp.on('put','config/system/desc', manual_test)
    application = tornado.web.Application([
        (r"/config", ConfigHandler),
        (r"/submit", SubmitHandler),
        (r"/test", TestHandler),
        (r"/(.*)", tornado.web.StaticFileHandler,
         {"path": os.path.dirname(__file__), "default_filename": "index.html"})
    ])
    application.listen(8000)
    tornado.ioloop.IOLoop.instance().start()
