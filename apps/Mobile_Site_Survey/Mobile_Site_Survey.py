import cp
from threading import Thread, Lock
import concurrent.futures
import speedtest
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

            # Which engines this build can run, so the UI only offers those.
            config["available_engines"] = [
                {"value": engine, "label": speedtest.engine_label(engine)}
                for engine in speedtest.available_engines()
            ]

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

        # Text and select fields are read explicitly. They are deliberately kept
        # out of config_fields below, where a missing argument is coerced to
        # 0/False - that would wipe the value instead of leaving it alone.
        try:
            engine = self.get_argument('speedtest_engine', '').strip().lower()
            if engine:
                dispatcher.config["speedtest_engine"] = engine
        except Exception as e:
            cp.log(f'Exception parsing speedtest_engine: {e}')

        try:
            dispatcher.config["iperf3_server"] = self.get_argument(
                'iperf3_server', '').strip()
        except Exception as e:
            cp.log(f'Exception parsing iperf3_server: {e}')

        try:
            ports = self.get_argument('iperf3_ports', '').strip()
            dispatcher.config["iperf3_ports"] = ports or settings["iperf3_ports"]
        except Exception as e:
            cp.log(f'Exception parsing iperf3_ports: {e}')

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
        # Apply the engine change straight away so it takes effect on the next
        # survey without restarting the app.
        apply_speedtest_config(dispatcher.config)
        self.redirect('/')


class ResultsHandler(tornado.web.RequestHandler):
    """Handles results/ endpoint requests."""

    def get(self):
        try:
            files = os.listdir("./results")
            url = self.request.full_url().replace('http://aoobm-cp-connector', 'https://aoobm-cp-connector').replace('?', '')
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
                if not pong:
                    continue
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
            with concurrent.futures.ThreadPoolExecutor(len(self.modems)) as executor:
                executor.map(run_tests, self.modems)
            # Format UTC timestamp for display
            pretty_timestamp = time.strftime('%H:%M:%S  %m/%d/%Y', time.gmtime(self.timestamp))
            pretty_lat = '{:.6f}'.format(float(self.lat)) if self.lat is not None else '0.000000'
            pretty_lon = '{:.6f}'.format(float(self.long)) if self.long is not None else '0.000000'
            # Title will be added with the detailed results in run_tests function
            # NOTE: Per-modem routing (created by source_route()) is intentionally left in
            # place across survey cycles instead of being torn down and recreated every run.
            # It's idempotent (see source_route()), so repeated cycles don't rewrite
            # config/routing/* unless something actually changed. Rewriting config/ on every
            # cycle was causing constant NCM config syncs. Cleanup of stale MSS routing
            # entries happens once at startup via initialize_routing().

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
        # Copy the defaults rather than aliasing the settings dict.
        config = dict(settings)
        config['speedtest_engine'] = speedtest.default_engine()
        cp.post('config/system/sdk/appdata', {"name": name, "value": json.dumps(config)})
        cp.log(f'No config found - Saved default config: {config}')
    else:  # Update config with any new settings
        if config.get('dead_reckoning') is None:
            config['dead_reckoning'] = settings['dead_reckoning']
        # Only offer engines this build can actually run. A missing key, the old
        # "auto" value, or an engine whose binary is not bundled all resolve to
        # the best available engine so the UI select always has a match.
        if config.get('speedtest_engine') not in speedtest.available_engines():
            config['speedtest_engine'] = speedtest.default_engine()
        if config.get('iperf3_server') is None:
            # Migrate the legacy combined "host:start-end" speedtest_url value.
            host, _, ports = (config.get('speedtest_url') or '').partition(':')
            host = host.strip()
            if host and 'speedtest.net' not in host:
                config['iperf3_server'] = host
                if ports.strip() and config.get('iperf3_ports') is None:
                    config['iperf3_ports'] = ports.strip()
            else:
                config['iperf3_server'] = settings['iperf3_server']
        if config.get('iperf3_ports') is None:
            config['iperf3_ports'] = settings['iperf3_ports']
        config.pop('speedtest_url', None)
        save_config(config, 'Mobile_Site_Survey')
    return config


def apply_speedtest_config(config):
    """Push the speedtest settings into the speedtest module and log the result."""
    try:
        speedtest.configure(
            engine=config.get('speedtest_engine'),
            iperf3_server=config.get('iperf3_server', ''),
            iperf3_ports=config.get('iperf3_ports', ''))
        problem = speedtest.engine_error()
        if problem:
            cp.log(f'Speedtest engine: {speedtest.describe_engine()} '
                   f'| WARNING: {problem}')
        else:
            cp.log(f'Speedtest engine: {speedtest.describe_engine()}')
    except Exception as e:
        cp.log(f'Exception applying speedtest config: {e}')

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


def log_progress(msg, logs):
    """Log test progress to syslog and the app logs, but not the UI results panel."""
    logstamp = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
    cp.log(msg)
    logs.append(f'{logstamp} {msg}')


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


def _normalize_to_list(obj):
    """Normalize API response to list for iteration. Handles dict (id-keyed) or list."""
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        return list(obj.values()) if obj else []
    return []


# NCOS routing identity model - these two objects are NOT addressed the same way:
#
#   config/routing/tables    entries expose an "_id_" UUID. Routing policies
#                            reference a table by that UUID in their "table"
#                            field. Tables are still stored in an array, so a
#                            DELETE needs the current numeric index (resolve the
#                            UUID to an index first).
#
#   config/routing/policies  entries have NO "_id_" field at all (confirmed
#                            against the DTD and live routers). A policy is only
#                            addressable by its numeric collection index. POST
#                            returns that index in the response "data" field.
#
# Never do `policy.get('_id_')` - it always returns None, which previously made
# MSS think policy creation had failed and made every cleanup pass a no-op.


def _delete_policies_by_index(indexes, label):
    """Delete routing policies by numeric index.

    Policies live in an array, so deleting one shifts the indexes of every
    later entry. Always delete from highest index to lowest.
    """
    for idx in sorted(set(indexes), reverse=True):
        try:
            cp.delete(f'config/routing/policies/{idx}')
            time.sleep(0.1)
        except Exception as e:
            cp.log(f'Failed to delete {label} policy at index {idx}: {e}')


def _delete_tables_by_index(indexes, label):
    """Delete routing tables by numeric index, highest index first."""
    for idx in sorted(set(indexes), reverse=True):
        try:
            cp.delete(f'config/routing/tables/{idx}')
            time.sleep(0.1)
        except Exception as e:
            cp.log(f'Failed to delete {label} table at index {idx}: {e}')


def _delete_table_by_id(table_id):
    """Delete a routing table given its _id_ UUID.

    Resolves the UUID to its current numeric collection index, because index
    addressing is what works consistently across NCOS platforms.
    """
    if not table_id:
        return
    try:
        tables = _normalize_to_list(cp.get('config/routing/tables'))
        for idx, table in enumerate(tables):
            if isinstance(table, dict) and table.get("_id_") == table_id:
                cp.delete(f'config/routing/tables/{idx}')
                return
        # Compatibility fallback for platforms that accept UUID addressing
        cp.delete(f'config/routing/tables/{table_id}')
    except Exception as e:
        cp.log(f'Failed to delete route table {table_id}: {e}')


def cleanup_mss_routing():
    """Remove all MSS-related route tables and policies from previous runs.
    Must delete policies that reference MSS tables first, then delete the tables."""
    try:
        route_tables = _normalize_to_list(cp.get('config/routing/tables'))

        # Find MSS route table UUIDs by name (e.g. MSS-mdm-75613315)
        mss_table_ids = set()
        for table in route_tables:
            if not isinstance(table, dict):
                continue
            name = table.get("name")
            if name and "MSS" in name:
                table_id = table.get("_id_")
                if table_id is not None:
                    mss_table_ids.add(table_id)

        if not mss_table_ids:
            return

        # Delete policies referencing MSS tables first (required before deleting
        # the tables). Policies are addressed by numeric index only.
        route_policies = _normalize_to_list(cp.get('config/routing/policies'))
        stale_policy_indexes = [
            idx for idx, policy in enumerate(route_policies)
            if isinstance(policy, dict) and policy.get("table") in mss_table_ids
        ]
        _delete_policies_by_index(stale_policy_indexes, 'stale MSS')

        # Re-get tables after policy deletion, then delete by numeric index
        route_tables = _normalize_to_list(cp.get('config/routing/tables'))
        stale_table_indexes = [
            idx for idx, table in enumerate(route_tables)
            if isinstance(table, dict) and table.get("_id_") in mss_table_ids
        ]
        _delete_tables_by_index(stale_table_indexes, 'stale MSS')

        cp.log('Cleaned up MSS route tables and policies from previous run')
    except Exception as e:
        cp.log(f'Exception in cleanup_mss_routing(): {e}')


def cleanup_duplicate_routing():
    """Clean up duplicate routing policies and tables, keeping only one per unique identifier."""
    try:
        route_policies = _normalize_to_list(cp.get('config/routing/policies'))

        # Duplicate policies - keep the first entry per referenced table.
        # Policies have no _id_, so track the numeric index of the duplicates.
        seen_tables = set()
        policies_to_delete = []
        for idx, policy in enumerate(route_policies):
            if not isinstance(policy, dict):
                continue
            table_id = policy.get("table")
            if not table_id:
                continue
            if table_id in seen_tables:
                policies_to_delete.append(idx)
            else:
                seen_tables.add(table_id)

        _delete_policies_by_index(policies_to_delete, 'duplicate')

        # Duplicate tables - keep the first entry per table name. Re-read after
        # the policy deletes above so indexes reflect current state.
        route_tables = _normalize_to_list(cp.get('config/routing/tables'))
        seen_names = set()
        tables_to_delete = []
        for idx, table in enumerate(route_tables):
            if not isinstance(table, dict):
                continue
            table_name = table.get("name")
            if not table_name:
                continue
            if table_name in seen_names:
                tables_to_delete.append(idx)
            else:
                seen_names.add(table_name)

        _delete_tables_by_index(tables_to_delete, 'duplicate')

    except Exception as e:
        cp.log(f'Exception in cleanup_duplicate_routing(): {e}')

def initialize_routing():
    """Initialize routing by cleaning up MSS leftovers and duplicates at startup."""
    try:
        cleanup_mss_routing()
        cleanup_duplicate_routing()
        cp.log("Routing cleanup completed - ready for device-specific routing")
    except Exception as e:
        cp.log(f'Exception in initialize_routing(): {e}')

def source_route(sim):
    """Configure source routing for sim IP to egress through sim device.
    Returns source IP of sim."""
    try:
        source_ip = cp.get(f'status/wan/devices/{sim}/status/ipinfo/ip_address')
        if cp.get('config/routing/policies/0/priority') != 10:
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

        # Check if this route table exists by name. Tables DO expose an _id_ UUID
        # and that UUID is what a routing policy references in its "table" field.
        route_tables = _normalize_to_list(cp.get('config/routing/tables'))
        route_table_id = None
        for table in route_tables:
            if isinstance(table, dict) and table.get("name") == f'MSS-{sim}':
                route_table_id = table.get("_id_")
                break

        # If not found, create it. POST returns a numeric collection index in
        # "data"; GET that index to read the table's _id_ UUID.
        if not route_table_id:
            req = cp.post('config/routing/tables/', route_table)
            if not req:
                raise Exception("Failed to create route table - post returned None")
            route_table_index = req.get("data")
            if route_table_index is None:
                raise Exception("Failed to create route table - no data in response")
            table_response = cp.get(f'config/routing/tables/{route_table_index}')
            if not table_response or not isinstance(table_response, dict):
                raise Exception("Failed to retrieve created route table")
            route_table_id = table_response.get("_id_")
            if route_table_id is None:
                raise Exception("Created route table does not have _id_ field")
            cp.log(f'Created route table MSS-{sim} '
                   f'index={route_table_index} id={route_table_id}')
            time.sleep(1)

        # Now prepare the desired route policy
        route_policy = {
            "ip_version": "ip4",
            "priority": 1,
            "table": route_table_id,
            "src_ip_network": source_ip
        }

        # Look for an existing policy for this table. Policies have NO _id_ field,
        # so they are identified and addressed purely by numeric list index.
        route_policies = _normalize_to_list(cp.get('config/routing/policies'))
        existing_policy_index = None
        existing_policy = None
        for idx, policy in enumerate(route_policies):
            if isinstance(policy, dict) and policy.get("table") == route_table_id:
                existing_policy_index = idx
                existing_policy = policy
                break

        if existing_policy_index is not None:
            # Update in place only if something actually changed, so repeated
            # survey cycles don't rewrite config/ and trigger NCM config syncs.
            needs_update = any(
                existing_policy.get(k) != v for k, v in route_policy.items()
            )
            if needs_update:
                cp.put(f'config/routing/policies/{existing_policy_index}', route_policy)
                time.sleep(1)
            policy_index = existing_policy_index
        else:
            resp = cp.post('config/routing/policies/', route_policy)
            if not resp:
                _delete_table_by_id(route_table_id)
                raise Exception("Failed to create route policy - post returned None")
            policy_index = resp.get("data")
            if policy_index is None:
                _delete_table_by_id(route_table_id)
                raise Exception("Failed to create route policy - no index in response")
            cp.log(f'Created route policy for MSS-{sim} index={policy_index}')
            time.sleep(1)

        # Verify by content, not by looking for an _id_ that policies never have
        pol_obj = cp.get(f'config/routing/policies/{policy_index}')
        if not pol_obj or not isinstance(pol_obj, dict):
            raise Exception(f'Cannot read route policy at index {policy_index}')
        verified = all(pol_obj.get(k) == v for k, v in route_policy.items())
        if not verified:
            raise Exception(
                f'Route policy verification failed at index {policy_index}. '
                f'Expected {route_policy} got {pol_obj}'
            )
        return source_ip
    except Exception as e:
        msg = f'Exception in source_route(): {e}'
        log_all(msg, [])
        return None


def run_tests(modem):
    """Main testing function - multithreaded by Dispatcher"""
    download, upload = 0.0, 0.0
    latency, jitter = None, None
    bytes_sent, bytes_received, total_mb_used, packet_loss_percent = 0, 0, 0, 0
    share = ''
    server = ''
    engine = ''
    cur_plmn = None  # Initialize cur_plmn to avoid "referenced before assignment" error
    st = None
    logs = []

    wan_info = cp.get(f'status/wan/devices/{modem}/info') or {}
    wan_type = wan_info.get('type')
    iface = wan_info.get('iface')

    # The WAN IP labels non-modem interfaces and binds the speedtest to this
    # device. Read it up front so it is available even when speedtests are off.
    source_ip = cp.get(f'status/wan/devices/{modem}/status/ipinfo/ip_address')

    run_speedtest = bool(dispatcher.config.get("speedtests"))
    if run_speedtest:
        engine_problem = speedtest.engine_error()
        if engine_problem:
            log_all(f'Skipping speedtest on {modem}: {engine_problem}', logs)
            run_speedtest = False

    if run_speedtest:
        # ROUTING - iPerf3 and Ookla need packets sourced from the modem IP to
        # egress the modem device. netperf pins the WAN itself through its
        # ifc_wan option, so it needs no config/routing entries at all.
        if speedtest.needs_source_routing():
            try:
                source_ip = source_route(modem)
                if not source_ip:
                    msg = f'Failed to configure source routing for {modem}'
                    log_all(msg, logs)
                    return
            except Exception as e:
                msg = f'Exception in routing: {e}'
                log_all(msg, logs)
        engine = speedtest.resolve_engine()
        try:
            st = Speedtest(source_address=source_ip, interface=iface, device=modem)
        except Exception as e:
            msg = f'Exception in speedtest startup: {e}'
            log_all(msg, logs)
            run_speedtest = False

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

    if run_speedtest and st:
        # Speedtest - start() measures download, upload and latency together.
        try:
            log_progress(f'Starting {speedtest.describe_engine()} speedtest on '
                         f'{product} {carrier}.', logs)
            st.start()
            if wan_type == 'mdm':  # Capture CA Bands for modems
                diagnostics = cp.get(
                    f'status/wan/devices/{modem}/diagnostics') or diagnostics
            log_progress(f'Speedtest Complete on {product} {carrier}.', logs)

            # Format results
            try:
                download = round(st.results.download / 1000 / 1000, 2)
                upload = round(st.results.upload / 1000 / 1000, 2)
                # Latency stays a whole number of milliseconds so the value
                # posted to the server keeps its existing shape.
                if st.results.ping is not None:
                    latency = round(st.results.ping)
                if st.results.jitter is not None:
                    jitter = round(st.results.jitter, 1)
                bytes_sent = st.results.bytes_sent
                bytes_received = st.results.bytes_received
                # Blank for netperf, which picks its own server internally.
                server = st.results.server.get("host", "")
                share = st.results.share()
                engine = st.results.engine or engine
            except Exception as e:
                cp.log(f'Exception formatting speedtest results: {e}')

            debug_log(f'bytes_sent: {bytes_sent} bytes_received: {bytes_received}')
            dispatcher.total_bytes[modem] += bytes_sent + bytes_received
            total_mb_used = round(dispatcher.total_bytes[modem] / 1000 / 1000, 2)
        except Exception as e:
            msg = f'Exception running speedtest for {product} {carrier}: {e}'
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
               carrier, download, upload, latency, jitter, packet_loss_percent,
               bytes_sent, bytes_received, share, engine, server]
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
            
        # netperf reports no server, so show the engine and only append a server
        # when there is one.
        engine_display = engine or 'no speedtest'
        if server:
            engine_display = f'{engine_display}  {server}'

        pretty_results = title + f' ┣┅┅┅  ☏{carrier} {cur_plmn}  ⇄ {packet_loss_percent}% loss ({tx - rx} of {tx})\n' \
                         f' ┣┅┅┅  ↓{download}Mbps  ↑{upload}Mbps  ⏱{latency}ms  ∿{jitter}ms\n' \
                         f' ┣┅┅┅  ⛁ {engine_display}\n' \
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
                          'Latency', 'Jitter', 'Packet Loss Percent', 'bytes_sent',
                          'bytes_received', 'Results Image', 'Engine', 'Server']
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

    # Detect bundled speedtest binaries once, before any config is read.
    speedtest.detect_binaries()

    dispatcher = Dispatcher()
    # Configure the selected speedtest engine
    cp.log(f'Speedtest engines available: '
           f'{", ".join(speedtest.available_engines())}')
    apply_speedtest_config(dispatcher.config)
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
