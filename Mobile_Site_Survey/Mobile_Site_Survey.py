import cp
from threading import Thread, Lock
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
import configparser

results_dir = 'results'
dispatcher = None


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
            # Set timestamp immediately for manual tests so indicator shows
            if dispatcher:
                dispatcher.timestamp = time.time()  # time.time() always returns UTC timestamp

        if dispatcher:
            dispatcher.manual = True
        self.redirect('/')
        return


class ClearHandler(tornado.web.RequestHandler):
    """Handles clear/ endpoint requests."""

    def get(self):
        """Clear the dispatcher results"""
        if dispatcher:
            dispatcher.results = ''
        self.redirect('/')
        return


class ConfigHandler(tornado.web.RequestHandler):
    """Handles config/ endpoint requests."""

    def get(self):
        """Return app config in JSON for web UI."""
        try:
            config = get_config('Mobile_Site_Survey')
            if dispatcher:
                config["results"] = dispatcher.results
                config["version"] = dispatcher.version
            else:
                config["results"] = ""
                config["version"] = "1.0.0"
            
            # Add GPS lock status
            try:
                config["gps_lock"] = cp.get('/status/gps/fix/lock')
            except:
                config["gps_lock"] = False
                
            # Add survey running status
            if dispatcher:
                config["survey_running"] = dispatcher.timestamp is not None
                # Calculate total data used across all modems
                total_data_mb = 0.0
                if dispatcher.total_bytes:
                    total_bytes_sum = sum(dispatcher.total_bytes.values())
                    total_data_mb = round(total_bytes_sum / 1000 / 1000, 2)
                config["total_data_used_mb"] = total_data_mb
            else:
                config["survey_running"] = False
                config["total_data_used_mb"] = 0.0
                
            self.write(json.dumps(config))
            return
        except Exception as e:
            cp.log(f'Exception in ConfigHandler: {e}')
            self.write(json.dumps({"error": str(e)}))


class SubmitHandler(tornado.web.RequestHandler):
    """Handles submit/ endpoint requests."""

    def get(self):
        """Parse args and update and save config."""
        if not dispatcher:
            self.redirect('/')
            return
            
        try:
            dispatcher.config["server_url"] = self.get_argument('server_url')
            dispatcher.config["server_token"] = self.get_argument('server_token')
        except Exception as e:
            cp.log(f'Exception in config submit: {e}')

        try:
            surveyors = self.get_argument('surveyors')
            if surveyors:
                surveyors = [x.strip() for x in surveyors.split(',')]
                dispatcher.config["surveyors"] = surveyors
        except Exception as e:
            cp.log(f'Exception parsing surveyors: {e}')
            dispatcher.config["surveyors"] = []

        # Define configuration fields and their corresponding types
        config_fields = {
            "min_distance": int,
            "min_time": int,
            "enable_surveyors": bool,
            "speedtests": bool,
            "packet_loss": bool,
            "write_csv": bool,
            "send_to_server": bool,
            "full_diagnostics": bool,
            "include_logs": bool,
            "debug": bool,
            "enabled": bool,
            "enable_timer": bool,
            "all_wans": bool
        }

        # Function to safely get and convert arguments
        def get_argument_safe(arg_name, arg_type, default):
            try:
                value = self.get_argument(arg_name)
                if arg_type == bool:
                    return bool(int(value))  # Convert to int first to handle "0" or "1" strings
                return arg_type(value)
            except:
                return default

        # Iterate over config fields and update dispatcher.config
        for field, field_type in config_fields.items():
            dispatcher.config[field] = get_argument_safe(field, field_type, default=(0 if field_type == int else False))

        save_config(dispatcher.config, 'Mobile_Site_Survey')
        cp.log(f'Saved new config: {dispatcher.config}')
        self.redirect('/')


class ResultsHandler(tornado.web.RequestHandler):
    """Handles results/ endpoint requests."""

    def get(self):
        try:
            files = os.listdir("./results")
            url = self.request.full_url().replace('http://aoobm-haproxy', 'https://aoobm-haproxy').replace('?', '')
            files_paths = sorted([f"{url}/{f}" for f in files])
            self.render("template.html", items=files_paths)
        except Exception as e:
            cp.log(f'Exception in ResultsHandler: {e}')


class Dispatcher:
    """Event Handler for tests"""

    def __init__(self):
        self.config = {}
        self.modems = []
        self.pings = {}
        self.results = ''
        self.version = ''
        self.surveyors = []
        self.manual = False
        self.timestamp = None
        self.total_bytes = {}
        self.lat, self.long, self.accuracy = None, None, None
        self.serial_number, self.mac_address, self.router_id = None, None, None
        self.ping_lock = Lock()  # Lock for thread-safe ping counter operations

        self._initialize_dispatcher()

    def _initialize_dispatcher(self):
        self.serial_number = cp.get('status/product_info/manufacturing/serial_num')
        self.mac_address = cp.get('status/product_info/mac0')
        self.config = get_config('Mobile_Site_Survey')
        package = configparser.ConfigParser()
        package.read('package.ini')
        major = package.get('Mobile_Site_Survey', 'version_major')
        minor = package.get('Mobile_Site_Survey', 'version_minor')
        patch = package.get('Mobile_Site_Survey', 'version_patch')
        self.version = f'{major}.{minor}.{patch}'
        cp.log(f'Version: {self.version}')
        if self.config.get("dead_reckoning"):
            enable_GPS_send_to_server()

    def loop(self):
        last_location = None
        next_timer = None
        self.router_id = cp.get('status/ecm/client_id') or 0
        while True:
            try:
                self.modems = get_connected_wans()
                self._run_pings()
                next_timer = self._check_timer(next_timer)
                gps_lock = cp.get('/status/gps/fix/lock')

                if self._should_run_test(gps_lock):
                    latlong = self._get_location()
                    too_close = self._check_minimum_distance(last_location, latlong)

                    if self.config.get("enabled") and not too_close or self.manual:
                        self._start_survey(latlong)
                        last_location = latlong

                time.sleep(1)
            except Exception as e:
                cp.log(f'Exception in dispatcher loop: {e}')

    def _run_pings(self):
        if self.config.get("packet_loss"):
            for modem in self.modems:
                if not self.pings.get(modem):
                    self.pings[modem] = {"tx": 0, "rx": 0}
                iface = cp.get(f'status/wan/devices/{modem}/info/iface')
                pong = ping('8.8.8.8', iface)
                debug_log(json.dumps(pong))

                if pong.get('tx') and pong.get('rx'):
                    # Thread-safe accumulation of ping counters
                    with self.ping_lock:
                        self.pings[modem]["tx"] += pong["tx"]
                        self.pings[modem]["rx"] += pong["rx"]
                debug_log(
                    f'Cumulative ping results for {modem}: {self.pings[modem]["rx"]} of {self.pings[modem]["tx"]}')

    def _check_timer(self, next_timer):
        if self.config.get("enable_timer"):
            if next_timer is None:
                next_timer = time.time()
            if time.time() >= next_timer:
                cp.log('Starting timed test.')
                next_timer = time.time() + self.config.get("min_time", 0)
                self.manual = True
        return next_timer

    def _should_run_test(self, gps_lock):
        return (self.config.get("enabled") and gps_lock) or any([self.manual, self.config.get("dead_reckoning")])

    def _get_location(self):
        if self.config.get("dead_reckoning"):
            self.lat, self.long, self.accuracy = get_location_DR()
        else:
            self.lat, self.long, self.accuracy = get_location()
        return self.lat, self.long

    def _check_minimum_distance(self, last_location, latlong):
        if last_location is not None:
            dist = distance.distance(latlong, last_location).m
            if dist < self.config.get("min_distance", 0) and not self.manual:
                # Minimum distance has not been met, wait 1 second and check again
                time.sleep(1)
                return True
        return False

    def _start_survey(self, latlong):
        cp.log('---> Starting Survey <---')
        self._initialize_modems()
        if self.timestamp is None:  # If not triggered remotely
            self.timestamp = time.time()  # time.time() always returns UTC timestamp
            self._start_surveyors()
        self._run_tests_on_modems()
        cp.log('---> Survey Complete <---')
        self.timestamp = None
        self.manual = False

    def _initialize_modems(self):
        for modem in self.modems:
            if not self.total_bytes.get(modem):
                self.total_bytes[modem] = 0

    def _start_surveyors(self):
        if self.config.get("enable_surveyors"):
            for surveyor in self.config.get("surveyors", []):
                Thread(target=Surveyor.start, args=(surveyor, self.timestamp), daemon=True).start()

    def _run_tests_on_modems(self):
        if self.modems:
            routing_policies = cp.get('config/routing/policies')
            routing_tables = cp.get('config/routing/tables')
            with concurrent.futures.ThreadPoolExecutor(len(self.modems)) as executor:
                executor.map(run_tests, self.modems)
            # Format UTC timestamp for display
            pretty_timestamp = time.strftime('%H:%M:%S  %m/%d/%Y', time.gmtime(self.timestamp))
            pretty_lat = '{:.6f}'.format(float(self.lat)) if self.lat is not None else '0.000000'
            pretty_lon = '{:.6f}'.format(float(self.long)) if self.long is not None else '0.000000'
            # Title will be added with the detailed results in run_tests function

            cp.put('config/routing/policies', routing_policies)
            cp.put('config/routing/tables', routing_tables)

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


def enable_GPS_send_to_server():
    try:
        connections = cp.get('config/system/gps/connections/')
        for connection in connections:
            if connection["name"] == 'MSS':
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
            "name": "MSS",
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
        cp.log(f'Exception in enable_GPS_send_to_server: {e}')


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
        lon = dec(lon_deg, lon_min, lon_sec)
        accuracy = fix.get('accuracy')
        return lat, lon, accuracy
    except:
        return None, None, None


def get_location_DR():
    """If GPRMC Sentence indicates invalid data ('V') return latitude and longitude from PCPTMINR (Dead Reckoning) as floats"""
    try:
        DR = False
        nmea = cp.get('status/gps/nmea')
        for sentence in nmea:
            fields = sentence.split(',')
            if fields[0] == '$GPRMC':
                DR = fields[2] == 'V'
            if fields[0] == '$PCPTMINR':
                lat = fields[2]
                lon = fields[3]
                accuracy = round((float(fields[8]) + float(fields[9])) / 2, 2)
                if lat == 0.0 and lon == 0.0:
                    return get_location()
        if DR:
            return lat, lon, accuracy
        return get_location()
    except Exception as e:
        cp.log(f'Exception in get_location_DR: {e}')
        return get_location()


def get_connected_wans():
    """Return list of connected WAN interfaces"""
    wans = []
    devices = []
    while not devices:
        devices = cp.get('status/wan/devices')
    if not dispatcher.config["all_wans"]:
        devices = [x for x in devices if x.startswith('mdm')]
    for device in devices:
        if cp.get(f'status/wan/devices/{device}/status/connection_state') == 'connected':
            wans.append(device)
    return wans


def save_config(config, name):
    try:
        appdata = cp.get('config/system/sdk/appdata')
        for data in appdata:
            if data["name"] == name:
                cp.put(f'config/system/sdk/appdata/{data["_id_"]}/value', json.dumps(config))
                return
    except Exception as e:
        cp.log(f'Exception in save_config: {e}')


def get_config(name):
    """Retrieve the configuration for the given name."""
    appdata = cp.get('config/system/sdk/appdata')
    try:
        config = json.loads([x["value"] for x in appdata if x["name"] == name][0])
    except:
        config = settings
        cp.post('config/system/sdk/appdata', {"name": name, "value": json.dumps(config)})
        cp.log(f'No config found - Saved default config: {config}')
    else:  # Update config with any new settings
        if config.get('dead_reckoning') is None:
            config['dead_reckoning'] = settings['dead_reckoning']
        if config.get('speedtest_url') is None:
            config['speedtest_url'] = settings['speedtest_url']
        save_config(config, 'Mobile_Site_Survey')
    return config

def dec(deg, min, sec):
    """Return decimal version of lat or long from deg, min, sec"""
    if str(deg)[0] == '-':
        dec = deg - (min / 60) - (sec / 3600)
    else:
        dec = deg + (min / 60) + (sec / 3600)
    return round(dec, 6)


def debug_log(msg):
    """Write log when in debug mode"""
    if dispatcher.config["debug"]:
        cp.log(msg)


def log_all(msg, logs):
    """Write consistent messages across all logs"""
    logstamp = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
    cp.log(msg)
    logs.append(f'{logstamp} {msg}')
    dispatcher.results = f'{msg}\n\n' + dispatcher.results[:32000]


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


def cleanup_duplicate_routing():
    """Clean up duplicate routing policies and tables, keeping only one per unique identifier."""
    try:
        # Get all policies and tables
        route_policies = cp.get('config/routing/policies')
        route_tables = cp.get('config/routing/tables')
        
        # Clean up duplicate policies - keep only one per table
        # This ensures each table has exactly one policy
        seen_tables = set()
        policies_to_delete = []
        
        for policy in route_policies:
            table_id = policy.get("table")
            if table_id and table_id in seen_tables:
                # Found duplicate table - mark for deletion
                policies_to_delete.append(policy["_id_"])
            elif table_id:
                # First time seeing this table - keep it
                seen_tables.add(table_id)
        
        # Delete duplicate policies
        for policy_id in policies_to_delete:
            try:
                cp.delete(f'config/routing/policies/{policy_id}')
                time.sleep(0.1)
            except Exception as e:
                cp.log(f'Failed to delete policy {policy_id}: {e}')
        
        # Clean up duplicate tables - keep only one per table name
        # This ensures each modem device has exactly one table
        seen_names = set()
        tables_to_delete = []
        
        for table in route_tables:
            table_name = table.get("name")
            if table_name and table_name in seen_names:
                tables_to_delete.append(table["_id_"])
            elif table_name:
                seen_names.add(table_name)
        
        # Delete duplicate tables
        for table_id in tables_to_delete:
            try:
                cp.delete(f'config/routing/tables/{table_id}')
                time.sleep(0.1)
            except Exception as e:
                cp.log(f'Failed to delete table {table_id}: {e}')
                
    except Exception as e:
        cp.log(f'Exception in cleanup_duplicate_routing(): {e}')

def initialize_routing():
    """Initialize routing by cleaning up duplicates once at startup."""
    try:
        cleanup_duplicate_routing()
        cp.log("Routing cleanup completed - ready for device-specific routing")
    except Exception as e:
        cp.log(f'Exception in initialize_routing(): {e}')

def source_route(sim):
    """Configure source routing for sim IP to egress through sim device.
    Returns source IP of sim."""
    try:
        source_ip = cp.get(f'status/wan/devices/{sim}/status/ipinfo/ip_address')
        cp.put('config/routing/policies/0/priority', 10)
        
        # First, prepare the desired route table definition
        route_table = {
            "name": f'MSS-{sim}',
            "routes": [
                {
                    "netallow": False,
                    "ip_network": "0.0.0.0/0",
                    "dev": sim,
                    "auto_gateway": True
                }
            ]
        }

        # Check if this route table exists by name
        route_tables = cp.get('config/routing/tables')
        route_table_id = None
        for table in route_tables:
            if table.get("name") == f'MSS-{sim}':
                route_table_id = table["_id_"]
                break

        # If not found, create it
        if not route_table_id:
            req = cp.post('config/routing/tables/', route_table)
            route_table_index = req.get("data")
            route_table_id = cp.get(f'config/routing/tables/{route_table_index}/_id_')
            time.sleep(1)

        # Now prepare the desired route policy
        route_policy = {
            "ip_version": "ip4",
            "priority": 1,
            "table": route_table_id,
            "src_ip_network": source_ip
        }

        # Check if a policy already exists for this table and update/create as needed
        # This ensures we update the existing policy for this modem even if IP changed
        route_policies = cp.get('config/routing/policies')
        existing_policy_id = None
        for policy in route_policies:
            if policy.get("table") == route_table_id:
                existing_policy_id = policy["_id_"]
                break

        # If policy exists, update it; if not, create it
        if existing_policy_id:
            cp.put(f'config/routing/policies/{existing_policy_id}', route_policy)
            time.sleep(1)
        else:
            cp.post('config/routing/policies/', route_policy)
            time.sleep(1)
        return source_ip
    except Exception as e:
        msg = f'Exception in source_route(): {e}'
        log_all(msg, [])
        return None


def run_tests(modem):
    """Main testing function - multithreaded by Dispatcher"""
    download, upload, latency = 0.0, 0.0, 0.0
    bytes_sent, bytes_received, total_mb_used, packet_loss_percent = 0, 0, 0, 0
    share = ''
    server = None
    cur_plmn = None  # Initialize cur_plmn to avoid "referenced before assignment" error
    source_ip = None
    ookla = None
    logs = []

    if dispatcher.config.get("speedtests"):
        # ROUTING - Packets sourced from modem IP egress modem device:
        try:
            source_ip = source_route(modem)
            if not source_ip:
                msg = f'Failed to configure source routing for {modem}'
                log_all(msg, logs)
                return
        except Exception as e:
            msg = f'Exception in routing: {e}'
            log_all(msg, logs)
        try:
            # Instantiate Ookla with source_ip from modem
            retries = 0
            while retries < 5:
                try:
                    ookla = Speedtest(source_address=source_ip)
                    break
                except:
                    retries += 1
                    cp.log(f'Ookla failed to start for source {source_ip} on {modem}.  Trying again...')
                    time.sleep(1)
            else:
                log_all(f'Ookla is not accepting connections at the time.  Please try again later.  Device: {modem}', logs)
                return
        except Exception as e:
            msg = f'Exception in Ookla startup: {e}'
            log_all(msg, logs)

    wan_info = cp.get(f'status/wan/devices/{modem}/info')
    wan_type = wan_info.get('type')
    iface = wan_info.get('iface')

    # GET MODEM DIAGNOSTICS:
    if wan_type == 'mdm':
        diagnostics = cp.get(f'status/wan/devices/{modem}/diagnostics')
        carrier = diagnostics.get('CARRID')
        homecarrier = diagnostics.get('HOMECARRID')
        if homecarrier != carrier:
            carrier = f'{carrier}/{homecarrier}'
        iccid = diagnostics.get('ICCID')
        product = diagnostics.get('PRD')
    elif wan_type == 'wwan':
        diagnostics = cp.get(f'status/wan/devices/{modem}/diagnostics')
        carrier = source_ip
        iccid = diagnostics.get('SSID')
        product = modem
    else:  # Ethernet
        diagnostics = {}
        carrier = source_ip
        iccid = modem
        product = modem
        cur_plmn = None

    latency = None

    # Calculate packet loss
    try:
        if dispatcher.config.get("packet_loss"):
            # Thread-safe atomic get and reset of ping counters
            with dispatcher.ping_lock:
                tx = dispatcher.pings[modem]["tx"]
                rx = dispatcher.pings[modem]["rx"]
                
                # Safety check: ensure rx doesn't exceed tx (can happen due to race conditions)
                if rx > tx:
                    cp.log(f'Warning: Received packets ({rx}) exceed transmitted packets ({tx}) for {modem}. This indicates a race condition.')
                    rx = tx  # Cap rx at tx to prevent negative packet loss
                
                # Reset counters atomically after reading
                dispatcher.pings[modem]["rx"] = 0
                dispatcher.pings[modem]["tx"] = 0
            
            if tx == 0:
                packet_loss_percent = 0
            elif tx == rx:
                packet_loss_percent = 0
            else:
                packet_loss_percent = round((tx - rx) / tx * 100)
        else:
            tx, rx, packet_loss_percent = 0, 0, 0
    except Exception as e:
        cp.log(f'Exception calculating packet loss: {e}')
        tx, rx, packet_loss_percent = 0, 0, 0

    if dispatcher.config.get("speedtests"):
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

            logstamp = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
            logs.append(f'{logstamp} Starting Download Test on {product} {carrier}.')
            cp.log(f'Starting Download Test on {product} {carrier}.')
            ookla.download()  # Ookla Download Test
            if wan_type == 'mdm':  # Capture CA Bands for modems
                diagnostics = cp.get(f'status/wan/devices/{modem}/diagnostics')
            logstamp = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
            logs.append(f'{logstamp} Starting Upload Test on {product} {carrier}.')
            cp.log(f'Starting Upload Test on {product} {carrier}.')
            ookla.upload(pre_allocate=False)  # Ookla upload test
            logstamp = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
            logs.append(f'{logstamp} Speedtest Complete on {product} {carrier}.')
            cp.log(f'Speedtest Complete on {product} {carrier}.')

            # Format results
            try:
                download = round(ookla.results.download / 1000 / 1000, 2)
                upload = round(ookla.results.upload / 1000 / 1000, 2)
                latency = round(ookla.results.ping)
                bytes_sent = ookla.results.bytes_sent
                bytes_received = ookla.results.bytes_received
                server = ookla.results.server["host"]
                share = ookla.results.share()
            except Exception as e:
                cp.log(f'Exception formatting Ookla results: {e}')

            debug_log(f'bytes_sent: {bytes_sent} bytes_received: {bytes_received}')
            dispatcher.total_bytes[modem] += bytes_sent + bytes_received
            total_mb_used = round(dispatcher.total_bytes[modem] / 1000 / 1000, 2)
        except Exception as e:
            msg = f'Exception running Ookla speedtest for {product} {carrier}: {e}'
            log_all(msg, logs)

    # SEND TO SERVER:
    # Use time.gmtime() to ensure UTC time regardless of system timezone
    pretty_timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(dispatcher.timestamp))
    post_success = '✓ Done'
    if dispatcher.config.get("send_to_server"):
        try:
            post_success = '⇪ 5g-ready:❌   '
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
                pci, cur_plmn, lac, tac = None, None, None, None
            else:
                cell_id = diagnostics.get('CELL_ID')
                pci = diagnostics.get('PHY_CELL_ID')
                cur_plmn = diagnostics.get('CUR_PLMN')
                tac = diagnostics.get('TAC')
                lac = diagnostics.get('LAC')
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
                "cur_plmn": str(cur_plmn),
                "tac": str(tac),
                "lac": str(lac),
                "cell_id": str(cell_id),
                "pci": str(pci),
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
                "results_url": share,
                "version": dispatcher.version
            }
            if dispatcher.config.get("full_diagnostics"):
                payload["diagnostics"] = json.dumps(diagnostics)
            if dispatcher.config.get("include_logs"):
                payload["logs"] = ';  '.join(logs)
            url = dispatcher.config.get("server_url")
            headers = {'Content-Type': 'application/json'}
            if dispatcher.config.get("server_token"):
                headers['Authorization'] = f'Bearer {dispatcher.config["server_token"]}'

            debug_log(f'HTTP POST - URL: {url}')
            debug_log(f'HTTP POST - Headers: {headers}')
            debug_log(f'HTTP POST - Payload: {payload}')

            # retries
            retries = 0
            while retries < 5:
                try:
                    req = requests.post(url, headers=headers, json=payload)
                    if req.status_code < 300:
                        post_success = '⇪ 5g-ready:✓️   '
                        break
                except Exception as e:
                    cp.log(f'Exception in POST: {e}')
                    time.sleep(1)
                retries += 1
            cp.log(f'HTTP POST Result: {req.status_code} {req.text}')
        except Exception as e:
            msg = f'Exception in Send to Server: {e}'
            log_all(msg, logs)

    # Log results
    try:
        row = [pretty_timestamp, dispatcher.lat, dispatcher.long, dispatcher.accuracy,
               carrier, download, upload, latency, packet_loss_percent, bytes_sent, bytes_received, share]
        if wan_type == 'wwan' or (wan_type == 'mdm' and dispatcher.config.get("full_diagnostics")):
            row = row + [str(x).replace(',', ' ') for x in diagnostics.values()]
        elif wan_type == 'mdm' and not dispatcher.config.get("full_diagnostics"):
            cell_id = diagnostics.get('CELL_ID')
            pci = diagnostics.get('PHY_CELL_ID')
            nr_cell_id = diagnostics.get('NR_CELL_ID')
            cur_plmn = diagnostics.get('CUR_PLMN')
            if not cur_plmn:
                cur_plmn = cp.get(f'status/wan/devices/{modem}/diagnostics/CUR_PLMN')
            tac = diagnostics.get('TAC')
            lac = diagnostics.get('LAC')
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
            row = row + [dbm, sinr, rsrp, rsrq, sinr_5g, rsrp_5g, rsrq_5g, cell_id, pci, cur_plmn, tac, lac, nr_cell_id,
                         serdis, rfband, rfband_5g, scell0, scell1, scell2, scell3]
        debug_log(f'ROW: {row}')
        text = ','.join(str(x) for x in row) + '\n'
        logstamp = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
        logs.append(f'{logstamp} Results: {text}')
        cp.log(f'Results: {text}')
        # cp.put('config/system/desc', text[:1000])
        # Get timestamp and coordinates for the title
        if dispatcher:
            pretty_timestamp = time.strftime('%H:%M:%S  %m/%d/%Y', time.gmtime(dispatcher.timestamp))
            pretty_lat = '{:.6f}'.format(float(dispatcher.lat)) if dispatcher.lat is not None else '0.000000'
            pretty_lon = '{:.6f}'.format(float(dispatcher.long)) if dispatcher.long is not None else '0.000000'
            
            title = f' ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n' \
                    f' ┣┅➤  {pretty_timestamp}   ⌖{pretty_lat}, {pretty_lon} \n'
        else:
            title = ''
            
        pretty_results = title + f' ┣┅┅┅  ☏{carrier} {cur_plmn}  ⇄ {packet_loss_percent}% loss ({tx - rx} of {tx})\n' \
                         f' ┣┅┅┅  ↓{download}Mbps  ↑{upload}Mbps  ⏱{latency}ms\n' \
                         f' ┣┅┅┅  ⛁ {server}\n' \
                         f' ┗┅┅┅  {post_success}'
        log_all(pretty_results, logs)
    except Exception as e:
        msg = f'Exception formatting results: {e}'
        text = msg
        log_all(msg, logs)

    # Write to CSV:
    if dispatcher.config.get("write_csv"):
        diag = ''
        if dispatcher.config.get("full_diagnostics"):
            diag = ' Diagnostics'
        filename = f'Mobile Site Survey v{dispatcher.version} - ICCID {iccid}{diag}.csv'.replace(':', '')

        # CREATE results_dir if it doesn't exist:
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)

        # CREATE CSV IF IT DOESN'T EXIST:
        debug_log(' '.join(os.listdir(results_dir)))
        if not os.path.isfile(f'{results_dir}/{filename}'):
            logstamp = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
            logs.append(f'{logstamp} {filename} not found.')
            cp.log(f'{filename} not found.')
            with open(f'{results_dir}/{filename}', 'wt') as f:
                header = ['Timestamp', 'Lat', 'Long', 'Accuracy', 'Carrier', 'Download', 'Upload',
                          'Latency', 'Packet Loss Percent', 'bytes_sent', 'bytes_received', 'Results Image']
                if diagnostics:
                    if wan_type == 'wwan' or (wan_type == 'mdm' and dispatcher.config.get("full_diagnostics")):
                        header = header + [*diagnostics]
                    elif wan_type == 'mdm' and not dispatcher.config.get("full_diagnostics"):
                        header = header + ['DBM', 'SINR', 'RSRP', 'RSRQ', 'SINR_5G', 'RSRP_5G', 'RSRQ_5G', 'Cell ID',
                                           'PCI', 'CUR_PLMN', 'TAC', 'LAC', 'NR Cell ID', 'Serice Display', 'RF Band',
                                           'RF Band 5G', 'SCELL0', 'SCELL1', 'SCELL2', 'SCELL3']
                line = ','.join(header) + '\n'
                f.write(line)
            logstamp = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
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


def manual_test(path, value, *args):
    if not value:
        debug_log('Executing Manual Test')
        dispatcher.manual = True


if __name__ == "__main__":
    cp.log('Starting...')

    # Wait for WAN connection
    while not cp.get('status/wan/connection_state') == 'connected':
        time.sleep(1)
    time.sleep(3)

    dispatcher = Dispatcher()
    # Initialize routing cleanup once at startup
    initialize_routing()
    Thread(target=dispatcher.loop, daemon=True).start()
    cp.register('put', 'config/system/desc', manual_test)
    application = tornado.web.Application([
        (r"/config", ConfigHandler),
        (r"/submit", SubmitHandler),
        (r"/results", ResultsHandler),
        (r"/test", TestHandler),
        (r"/clear", ClearHandler),
        (r"/(.*)", tornado.web.StaticFileHandler,
         {"path": os.path.dirname(__file__), "default_filename": "index.html"})
    ])
    
    # Try ports from 8000-8100 until we find an open one
    import socket
    found_port = None
    for port in range(8000, 8101):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(('0.0.0.0', port))
                found_port = port
                break
            except OSError:
                continue
    if found_port is None:
        cp.log('ERROR: No available ports found between 8000-8100!')
        exit(1)
    cp.log(f'Web interface available on port {found_port}')
    application.listen(found_port)
    tornado.ioloop.IOLoop.instance().start()
