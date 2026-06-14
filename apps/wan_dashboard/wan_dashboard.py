"""
WAN Dashboard - Live Traffic Monitoring with Multiple Timeframes
"""

import cp
import time
import json
import os
import threading
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

class WANDashboard:
    def __init__(self):
        cp.log("Starting WAN Dashboard...")
        
        # Wait for NTP
        cp.wait_for_ntp()
        
        # Get router name for titles, handle IDNA encoding issues
        try:
            raw_name = cp.get_name() or "Router"
            # Store original name for display and sanitized name for webserver
            self.router_name = raw_name  # Original name for display
            self.router_name_safe = self._sanitize_hostname(raw_name)  # Sanitized for webserver
        except UnicodeError:
            # Handle hostnames with invalid characters for IDNA encoding
            self.router_name = "Router"
            self.router_name_safe = "Router"
        
        # Get port from appdata with default of 8000
        port = cp.get_appdata('wan_dashboard_port') or '8000'
        try:
            self.base_port = int(port)
            if self.base_port < 1 or self.base_port > 65535:
                cp.log(f"Invalid port value '{port}' (must be 1-65535), using default 8000")
                self.base_port = 8000
        except (ValueError, TypeError):
            cp.log(f"Invalid port value '{port}', using default 8000")
            self.base_port = 8000
        
        # Actual port will be set during server startup (may differ if port is in use)
        self.port = self.base_port
        
        # Get WAN Rate appdata configuration (for asset_id updates)
        # Check if asset_id updates are disabled (default: enabled)
        # If appdata field exists (even if empty), disable updates
        disable_asset_id = cp.get_appdata('wan_rate_disable')
        self.asset_id_updates_enabled = (disable_asset_id is None)
        
        # Always initialize these values (even if disabled) to avoid AttributeError
        # wan_rate_report_interval - seconds between asset_id updates (default: 300)
        wan_rate_report_interval = cp.get_appdata('wan_rate_report_interval') or '300'
        try:
            self.wan_rate_report_interval = int(wan_rate_report_interval)
            if self.wan_rate_report_interval < 60:
                cp.log(f"wan_rate_report_interval too small ({self.wan_rate_report_interval}s), using minimum 60s")
                self.wan_rate_report_interval = 60
        except (ValueError, TypeError):
            cp.log(f"Invalid wan_rate_report_interval value '{wan_rate_report_interval}', using default 300s")
            self.wan_rate_report_interval = 300
        
        # wan_rate_buffer_size - number of seconds of data to average (default: 300 = 5 minutes)
        wan_rate_buffer_size = cp.get_appdata('wan_rate_buffer_size') or '300'
        try:
            self.wan_rate_buffer_size = int(wan_rate_buffer_size)
            if self.wan_rate_buffer_size < 60:
                cp.log(f"wan_rate_buffer_size too small ({self.wan_rate_buffer_size}s), using minimum 60s")
                self.wan_rate_buffer_size = 60
        except (ValueError, TypeError):
            cp.log(f"Invalid wan_rate_buffer_size value '{wan_rate_buffer_size}', using default 300s")
            self.wan_rate_buffer_size = 300
        
        # wan_rate_output_path - where to write the asset_id data (default: '/config/system/asset_id')
        self.wan_rate_output_path = cp.get_appdata('wan_rate_output_path') or '/config/system/asset_id'
        
        if self.asset_id_updates_enabled:
            cp.log(f"WAN Rate asset_id updates ENABLED.  Webserver started on port {self.port}.  Report interval: {self.wan_rate_report_interval}s.  Buffer size: {self.wan_rate_buffer_size}s.  Output path: {self.wan_rate_output_path}")
        else:
            cp.log(f"WAN Rate asset_id updates DISABLED (wan_rate_disable appdata field exists).  Webserver started on port {self.port}")
        
        # Per-device data storage
        # devices_data[device_id]['timeframes'][tf] = { 'in':[], 'out':[], 'timestamps':[], 'conn':[] (live only) }
        # devices_data[device_id]['status'] = 'connected'|'disconnected'
        self.devices_data = {}
        
        # Previous counters per-device for rate calculation
        # prev_counters[device_id] = { 'in': bytes, 'out': bytes, 't': epoch }
        self.prev_counters = {}
        
        # Track devices that have ever connected (controls initial graph creation)
        self.seen_connected = set()

        # Data persistence - MUST be done before starting threads
        self.data_dir = "wan_data"
        self._ensure_data_dir()
        self._load_data()

        # Threading control
        self.running = True
        
        # Start data collection thread
        self.data_thread = threading.Thread(target=self._collect_data, daemon=True)
        self.data_thread.start()
        
        # Start averages calculation thread
        self.averages_thread = threading.Thread(target=self._calculate_averages, daemon=True)
        self.averages_thread.start()
        
        # Start HTTP server
        self.start_server()
    
    def _sanitize_hostname(self, hostname):
        """Clean hostname to be safe for webserver while preserving readability."""
        if not hostname or hostname == "Router":
            return "Router"
        
        # Remove or replace problematic characters for IDNA encoding
        # Keep alphanumeric, hyphens, and dots, replace others with hyphens
        import re
        sanitized = re.sub(r'[^a-zA-Z0-9\-\.]', '-', hostname)
        
        # Remove multiple consecutive hyphens
        sanitized = re.sub(r'-+', '-', sanitized)
        
        # Remove leading/trailing hyphens
        sanitized = sanitized.strip('-')
        
        # Ensure it's not empty and not too long
        if not sanitized or len(sanitized) > 63:
            return "Router"
        
        # Test if it can be encoded with IDNA
        try:
            sanitized.encode('idna')
            return sanitized
        except UnicodeError:
            # If still problematic, use a safe fallback
            return "Router"
    
    def _ensure_data_dir(self):
        """Create data directory if it doesn't exist."""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                if not os.path.exists(self.data_dir):
                    os.makedirs(self.data_dir, exist_ok=True)
                    # Data directory created
                
                # Verify directory was created
                if not os.path.exists(self.data_dir):
                    raise Exception(f"Directory {self.data_dir} still does not exist after creation")
                
                # Ensure seen_connected file exists
                seen_file = os.path.join(self.data_dir, 'seen_connected.json')
                if not os.path.exists(seen_file):
                    with open(seen_file, 'w') as f:
                        json.dump([], f)
                    # Seen connected file created
                
                # Data directory setup successful
                return  # Success, exit the method
                
            except Exception as e:
                cp.log(f"Attempt {attempt + 1} failed to create data directory: {e}")
                if attempt < max_attempts - 1:
                    # Try a different directory name
                    self.data_dir = f"wan_data_{attempt + 1}"
                    cp.log(f"Trying alternative directory: {self.data_dir}")
                else:
                    # Final attempt failed
                    cp.log(f"All attempts failed to create data directory. App may not save data properly.")
                    self.data_dir = "tmp_wan_data"  # Last resort

    def _save_seen_connected(self):
        try:
            # Always ensure directory exists before saving
            if not os.path.exists(self.data_dir):
                os.makedirs(self.data_dir, exist_ok=True)
                cp.log(f"Recreated data directory: {self.data_dir}")
            seen_file = os.path.join(self.data_dir, 'seen_connected.json')
            with open(seen_file, 'w') as f:
                json.dump(sorted(list(self.seen_connected)), f)
        except Exception as e:
            cp.log(f'Error saving seen_connected: {e}')

    def _load_seen_connected(self):
        try:
            seen_file = os.path.join(self.data_dir, 'seen_connected.json')
            if os.path.exists(seen_file):
                with open(seen_file, 'r') as f:
                    items = json.load(f)
                    if isinstance(items, list):
                        self.seen_connected = set(items)
        except Exception as e:
            cp.log(f'Error loading seen_connected: {e}')
    
    def _get_data_file_path(self, timeframe, device_id):
        """Get file path for a specific timeframe and device."""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
        device_dir = os.path.join(self.data_dir, device_id)
        if not os.path.exists(device_dir):
            os.makedirs(device_dir, exist_ok=True)
        return os.path.join(device_dir, f"{timeframe}_data.json")
    
    def _save_data(self, timeframe, device_id):
        """Save data for a specific timeframe and device to file."""
        try:
            # Always ensure data directory exists before saving
            if not os.path.exists(self.data_dir):
                os.makedirs(self.data_dir, exist_ok=True)
                cp.log(f"Recreated data directory: {self.data_dir}")
            file_path = self._get_data_file_path(timeframe, device_id)
            tf_data = self.devices_data.get(device_id, {}).get('timeframes', {}).get(timeframe, {})
            data_to_save = {
                'in': tf_data.get('in', []),
                'out': tf_data.get('out', []),
                'timestamps': tf_data.get('timestamps', []),
                'conn': tf_data.get('conn', [])
            }
            with open(file_path, 'w') as f:
                json.dump(data_to_save, f)
        except Exception as e:
            cp.log(f"Error saving {timeframe} data for {device_id}: {e}")
    
    def _load_data(self):
        """Load all per-device data from files on startup."""
        try:
            if not os.path.exists(self.data_dir):
                return
            self._load_seen_connected()
            for device_id in os.listdir(self.data_dir):
                device_path = os.path.join(self.data_dir, device_id)
                if not os.path.isdir(device_path):
                    continue
                self._ensure_device_structure(device_id)
                for timeframe in ['live', '5min_24h', 'hourly_week', 'daily_year']:
                    file_path = self._get_data_file_path(timeframe, device_id)
                    if os.path.exists(file_path):
                        with open(file_path, 'r') as f:
                            loaded_data = json.load(f)
                            tf = self.devices_data[device_id]['timeframes'][timeframe]
                            tf['in'] = loaded_data.get('in', [])
                            tf['out'] = loaded_data.get('out', [])
                            tf['timestamps'] = loaded_data.get('timestamps', [])
                            tf['conn'] = loaded_data.get('conn', [])
                            if tf['timestamps']:
                                self.seen_connected.add(device_id)
                        # Data loaded for device
        except Exception as e:
            cp.log(f"Error loading per-device data: {e}")
        
        # Clean up seen_connected list - remove devices that have never actually connected
        self._cleanup_seen_connected()
    
    def _cleanup_seen_connected(self):
        """Remove devices from seen_connected that have never actually been connected."""
        try:
            devices_to_remove = set()
            for device_id in list(self.seen_connected):
                # Check if device has any 'connected' states in any timeframe
                has_connected_data = False
                if device_id in self.devices_data:
                    for timeframe in ['live', '5min_24h', 'hourly_week', 'daily_year']:
                        conn_data = self.devices_data[device_id]['timeframes'][timeframe].get('conn', [])
                        if 'connected' in conn_data:
                            has_connected_data = True
                            break
                
                if not has_connected_data:
                    devices_to_remove.add(device_id)
            
            # Remove devices that have never been connected
            if devices_to_remove:
                self.seen_connected -= devices_to_remove
                self._save_seen_connected()
                cp.log(f"Cleaned up seen_connected: removed {len(devices_to_remove)} devices that never connected")
        except Exception as e:
            cp.log(f"Error cleaning up seen_connected: {e}")
    
    def _cleanup_old_data(self, timeframe, device_id):
        """Clean up old data to prevent files from growing too large."""
        try:
            if timeframe == 'live':
                # Keep only last 300 points (5 minutes at 1 second intervals)
                max_points = 300
            elif timeframe == '5min_24h':
                # Keep only last 288 points (24 hours at 5 minute intervals)
                max_points = 288
            elif timeframe == 'hourly_week':
                # Keep only last 168 points (1 week at 1 hour intervals)
                max_points = 168
            elif timeframe == 'daily_year':
                # Keep only last 365 points (1 year at 1 day intervals)
                max_points = 365
            else:
                return
            
            tf = self.devices_data.get(device_id, {}).get('timeframes', {}).get(timeframe)
            if not tf:
                return
            if len(tf['timestamps']) > max_points:
                trim_count = len(tf['timestamps']) - max_points
                tf['in'] = tf['in'][trim_count:]
                tf['out'] = tf['out'][trim_count:]
                tf['timestamps'] = tf['timestamps'][trim_count:]
                tf['conn'] = tf.get('conn', [])[trim_count:]
        except Exception as e:
            cp.log(f"Error cleaning up {timeframe} data for {device_id}: {e}")

    def _ensure_device_structure(self, device_id):
        """Ensure the device data structures exist."""
        if device_id not in self.devices_data:
            self.devices_data[device_id] = {
                'status': 'disconnected',
                'display': device_id,
                'timeframes': {
                    'live': {'in': [], 'out': [], 'timestamps': [], 'conn': []},
                    '5min_24h': {'in': [], 'out': [], 'timestamps': [], 'conn': []},
                    'hourly_week': {'in': [], 'out': [], 'timestamps': [], 'conn': []},
                    'daily_year': {'in': [], 'out': [], 'timestamps': [], 'conn': []}
                }
            }
            # Backfill with disconnected zero data for new devices
            self._backfill_device_data(device_id)
        if device_id not in self.prev_counters:
            self.prev_counters[device_id] = {'in': None, 'out': None, 't': None}

    def _backfill_device_data(self, device_id):
        """Backfill a new device with disconnected zero data to align timelines."""
        try:
            # Get the current time and calculate backfill periods
            current_time = datetime.now()
            
            # For live data: backfill last 5 minutes (300 seconds)
            live_tf = self.devices_data[device_id]['timeframes']['live']
            for i in range(300):
                backfill_time = current_time - timedelta(seconds=299-i)
                timestamp = backfill_time.strftime('%H:%M:%S')
                live_tf['in'].append(0.0)
                live_tf['out'].append(0.0)
                live_tf['timestamps'].append(timestamp)
                live_tf['conn'].append('disconnected')
            
            # For 5min averages: backfill last 24 hours (288 5-minute periods)
            tf5 = self.devices_data[device_id]['timeframes']['5min_24h']
            for i in range(288):
                backfill_time = current_time - timedelta(minutes=5*(287-i))
                timestamp = backfill_time.strftime('%H:%M')
                tf5['in'].append(0.0)
                tf5['out'].append(0.0)
                tf5['timestamps'].append(timestamp)
                tf5['conn'].append('disconnected')
            
            # For hourly averages: backfill last week (168 hours)
            tf_hourly = self.devices_data[device_id]['timeframes']['hourly_week']
            for i in range(168):
                backfill_time = current_time - timedelta(hours=167-i)
                timestamp = backfill_time.strftime('%Y-%m-%dT%H:00:00')
                tf_hourly['in'].append(0.0)
                tf_hourly['out'].append(0.0)
                tf_hourly['timestamps'].append(timestamp)
                tf_hourly['conn'].append('disconnected')
            
            # For daily averages: backfill last year (365 days)
            tf_daily = self.devices_data[device_id]['timeframes']['daily_year']
            for i in range(365):
                backfill_time = current_time - timedelta(days=364-i)
                timestamp = backfill_time.strftime('%Y-%m-%dT00:00:00')
                tf_daily['in'].append(0.0)
                tf_daily['out'].append(0.0)
                tf_daily['timestamps'].append(timestamp)
                tf_daily['conn'].append('disconnected')
                
        except Exception as e:
            cp.log(f"Error backfilling data for {device_id}: {e}")

    def _backfill_all_devices_after_offline(self, offline_duration):
        """Backfill all existing devices with disconnected zero data after router offline."""
        try:
            # Calculate how many data points to add based on offline duration
            seconds_offline = int(offline_duration)
            
            for device_id in list(self.seen_connected):
                # For live data: add disconnected zero points for each second offline
                live_tf = self.devices_data[device_id]['timeframes']['live']
                current_time = datetime.now()
                
                for i in range(seconds_offline):
                    backfill_time = current_time - timedelta(seconds=seconds_offline-i)
                    timestamp = backfill_time.strftime('%H:%M:%S')
                    live_tf['in'].append(0.0)
                    live_tf['out'].append(0.0)
                    live_tf['timestamps'].append(timestamp)
                    live_tf['conn'].append('disconnected')
                
                # Trim to keep only last 300 points
                if len(live_tf['in']) > 300:
                    trim_count = len(live_tf['in']) - 300
                    live_tf['in'] = live_tf['in'][trim_count:]
                    live_tf['out'] = live_tf['out'][trim_count:]
                    live_tf['timestamps'] = live_tf['timestamps'][trim_count:]
                    live_tf['conn'] = live_tf['conn'][trim_count:]
                
        except Exception as e:
            cp.log(f"Error backfilling devices after offline: {e}")

    def _get_device_display_name(self, device_id):
        """Build a human-friendly name for a device based on its type and info fields."""
        try:
            dev_type = cp.get(f"/status/wan/devices/{device_id}/info/type") or ''
            if dev_type == 'mdm':
                port = cp.get(f"/status/wan/devices/{device_id}/info/port") or ''
                sim = cp.get(f"/status/wan/devices/{device_id}/info/sim") or ''
                carrier = cp.get(f"/status/wan/devices/{device_id}/info/carrier_id") or ''
                # Carrier first, then device id, then port+sim
                return f"{carrier} - {device_id} - {port} {sim}".strip()
            elif dev_type == 'ethernet':
                port_name = cp.get(f"/status/wan/devices/{device_id}/info/port_name")
                if isinstance(port_name, dict) and port_name:
                    try:
                        first_key = sorted(list(port_name.keys()))[0]
                        name = port_name.get(first_key, '')
                    except Exception:
                        name = ''
                else:
                    name = port_name or ''
                # Port name first, then device id
                return f"{name} - {device_id}".strip()
            else:
                return device_id
        except Exception:
            return device_id

    def _list_devices(self):
        """Return a mapping of device_id -> connection_state using /status/wan/devices."""
        devices_resp = None
        while not devices_resp:
            devices_resp = cp.get('/status/wan/devices')
        result = {}
        if isinstance(devices_resp, dict):
            for dev_name, dev_obj in devices_resp.items():
                try:
                    state = dev_obj.get('status', {}).get('connection_state')
                    if not state:
                        state = cp.get(f"/status/wan/devices/{dev_name}/status/connection_state")
                    if not state:
                        cp.log('No connection state found for {dev_name}!!')
                        state = 'disconnected'
                except Exception as e:
                    cp.log(f"Error getting connection state for {dev_name}: {e}")
                    state = 'disconnected'
                result[dev_name] = state
        return result
    
    def _get_all_devices_traffic(self):
        """Get traffic data and connection_state for all devices in one call."""
        try:
            devices_resp = None
            while not devices_resp:
                devices_resp = cp.get('/status/wan/devices')
            
            result = {}
            if isinstance(devices_resp, dict):
                for device_id, device_info in devices_resp.items():
                    try:
                        in_stats = device_info.get('stats', {}).get('in')
                        out_stats = device_info.get('stats', {}).get('out')
                        conn_state = device_info.get('status', {}).get('connection_state')
                        
                        current_in = float(in_stats) if in_stats else 0.0
                        current_out = float(out_stats) if out_stats else 0.0
                        current_time = time.time()
                        
                        prev = self.prev_counters.get(device_id, {'in': None, 'out': None, 't': None})
                        if prev['in'] is None:
                            self.prev_counters[device_id] = {'in': current_in, 'out': current_out, 't': current_time}
                            result[device_id] = {'in': 0.0, 'out': 0.0, 'state': conn_state}
                        else:
                            time_delta = current_time - (prev['t'] or current_time)
                            if time_delta > 0:
                                in_rate = (current_in - (prev['in'] or 0.0)) / time_delta
                                out_rate = (current_out - (prev['out'] or 0.0)) / time_delta
                            else:
                                in_rate = 0.0
                                out_rate = 0.0
                            
                            # update prev
                            self.prev_counters[device_id] = {'in': current_in, 'out': current_out, 't': current_time}
                            result[device_id] = {'in': in_rate * 8, 'out': out_rate * 8, 'state': conn_state}
                            
                    except Exception as e:
                        cp.log(f"Error processing device {device_id}: {e}")
                        result[device_id] = {'in': 0.0, 'out': 0.0, 'state': 'disconnected'}
            
            return result
        except Exception as e:
            cp.log(f"Error getting all devices traffic: {e}")
            return {}
    
    def _collect_data(self):
        """Background thread to collect traffic data every 1 second."""
        # cp.log("Starting data collection thread")
        last_collection_time = time.time()
        while self.running:
            try:
                current_time = time.time()
                # Check if we've been offline (gap > 10 seconds indicates router was offline)
                if current_time - last_collection_time > 10:
                    # Router was offline, backfill all existing devices
                    self._backfill_all_devices_after_offline(current_time - last_collection_time)
                
                # Get all device traffic data in one call
                all_devices_traffic = self._get_all_devices_traffic()
                current_time_str = datetime.now().strftime('%H:%M:%S')
                
                for device_id, traffic_data in all_devices_traffic.items():
                    conn_state = traffic_data['state']
                    
                    # Only collect data for devices that are currently connected or have ever connected
                    if not (conn_state == 'connected' or device_id in self.seen_connected):
                        continue
                    
                    self._ensure_device_structure(device_id)
                    self.devices_data[device_id]['status'] = conn_state
                    if conn_state == 'connected':
                        self.seen_connected.add(device_id)
                        self._save_seen_connected()
                    
                    tf_live = self.devices_data[device_id]['timeframes']['live']

                    # gap fill
                    if len(tf_live['timestamps']) > 0:
                        last_timestamp = tf_live['timestamps'][-1]
                        last_time = datetime.strptime(last_timestamp, '%H:%M:%S')
                        current_time_obj = datetime.strptime(current_time_str, '%H:%M:%S')
                        time_diff = (current_time_obj - last_time).total_seconds()
                        if time_diff > 3:
                            gap_seconds = int(time_diff) - 1
                            for i in range(gap_seconds):
                                gap_time = last_time + timedelta(seconds=i+1)
                                gap_ts = gap_time.strftime('%H:%M:%S')
                                tf_live['in'].append(0.0)
                                tf_live['out'].append(0.0)
                                tf_live['timestamps'].append(gap_ts)
                                tf_live['conn'].append('disconnected')

                    tf_live['in'].append(traffic_data['in'])
                    tf_live['out'].append(traffic_data['out'])
                    tf_live['timestamps'].append(current_time_str)
                    tf_live['conn'].append(traffic_data['state'])

                    # Keep only last 300
                    self._cleanup_old_data('live', device_id)
                    # Save live data
                    self._save_data('live', device_id)
                
                # cp.log(f'Collected data: in={traffic["in"]:.2f} bps, out={traffic["out"]:.2f} bps')
                
                # Update last collection time
                last_collection_time = time.time()
                time.sleep(1)  # Collect data every 1 second
                
            except Exception as e:
                cp.log(f'Error in data collection: {e}')
                time.sleep(3)
    
    def _calculate_averages(self):
        """Background thread to calculate averages at appropriate intervals."""
        # cp.log("Starting averages calculation thread")
        
        # Track last calculation times
        last_5min_calc = time.time()
        last_hourly_calc = time.time()
        last_daily_calc = time.time()
        last_asset_id_update = time.time()
        
        while self.running:
            try:
                current_time = time.time()
                
                # Update asset_id with averages at configured interval (similar to WAN Rate app)
                # Only update if asset_id updates are enabled
                if self.asset_id_updates_enabled and current_time - last_asset_id_update >= self.wan_rate_report_interval:
                    total_avg_in = 0.0
                    total_avg_out = 0.0
                    device_count = 0
                    
                    # Use configured buffer size to determine how many seconds of data to average
                    buffer_points = min(self.wan_rate_buffer_size, 300)  # Cap at 300 since we keep max 300 points
                    
                    for device_id in list(self.seen_connected):
                        tf_live = self.devices_data[device_id]['timeframes']['live']
                        if len(tf_live['in']) >= buffer_points:
                            # Get the last buffer_points seconds of data (collected at 1 second intervals)
                            recent_in = tf_live['in'][-buffer_points:]
                            recent_out = tf_live['out'][-buffer_points:]
                            recent_conn = tf_live['conn'][-buffer_points:]
                            
                            # Calculate average for this device
                            avg_in = sum(recent_in) / len(recent_in)
                            avg_out = sum(recent_out) / len(recent_out)
                            
                            # Only count devices that were connected during this period
                            if 'connected' in recent_conn:
                                total_avg_in += avg_in
                                total_avg_out += avg_out
                                device_count += 1
                    
                    # Update asset_id with aggregated averages (similar to WAN Rate app)
                    if device_count > 0:
                        self._update_asset_id_with_averages(total_avg_in, total_avg_out)
                    
                    last_asset_id_update = current_time
                
                # Calculate 5-minute averages every 5 minutes (300 seconds) for each device
                if current_time - last_5min_calc >= 300:
                    for device_id in list(self.seen_connected):
                        tf_live = self.devices_data[device_id]['timeframes']['live']
                        if len(tf_live['in']) >= 300:
                            recent_in = tf_live['in'][-300:]
                            recent_out = tf_live['out'][-300:]
                            recent_conn = tf_live['conn'][-300:]
                            avg_in = sum(recent_in) / len(recent_in)
                            avg_out = sum(recent_out) / len(recent_out)
                            # If ANY point was connected during this period, mark as connected
                            connected_count = recent_conn.count('connected')
                            total_count = len(recent_conn)
                            avg_conn = 'connected' if 'connected' in recent_conn else 'disconnected'
                            cp.log(f"5min avg for {device_id}: {connected_count}/{total_count} connected points, result: {avg_conn}")
                            timestamp = datetime.now().strftime('%H:%M')
                            tf5 = self.devices_data[device_id]['timeframes']['5min_24h']
                            tf5['in'].append(avg_in)
                            tf5['out'].append(avg_out)
                            tf5['timestamps'].append(timestamp)
                            tf5['conn'].append(avg_conn)
                            # trim & save
                            self._cleanup_old_data('5min_24h', device_id)
                            self._save_data('5min_24h', device_id)
                    
                    last_5min_calc = current_time
                    # cp.log(f'Calculated 5-minute average: in={avg_in:.2f}, out={avg_out:.2f}')
                
                # Calculate hourly averages every hour (3600 seconds) per device
                if current_time - last_hourly_calc >= 3600:
                    for device_id in list(self.seen_connected):
                        tf5 = self.devices_data[device_id]['timeframes']['5min_24h']
                        recent_in = tf5['in'][-12:] if len(tf5['in']) >= 12 else [0] * 12
                        recent_out = tf5['out'][-12:] if len(tf5['out']) >= 12 else [0] * 12
                        recent_conn = tf5['conn'][-12:] if len(tf5['conn']) >= 12 else ['disconnected'] * 12
                        while len(recent_in) < 12:
                            recent_in.insert(0, 0)
                            recent_out.insert(0, 0)
                            recent_conn.insert(0, 'disconnected')
                        avg_in = sum(recent_in) / len(recent_in)
                        avg_out = sum(recent_out) / len(recent_out)
                        # If ANY 5-minute period was connected, mark as connected
                        avg_conn = 'connected' if 'connected' in recent_conn else 'disconnected'
                        timestamp = datetime.now().strftime('%Y-%m-%dT%H:00:00')
                        th = self.devices_data[device_id]['timeframes']['hourly_week']
                        th['in'].append(avg_in)
                        th['out'].append(avg_out)
                        th['timestamps'].append(timestamp)
                        th['conn'].append(avg_conn)
                        self._cleanup_old_data('hourly_week', device_id)
                        self._save_data('hourly_week', device_id)
                    last_hourly_calc = current_time
                    # cp.log(f'Calculated hourly average: in={avg_in:.2f}, out={avg_out:.2f}')
                
                # Calculate daily averages every day (86400 seconds) per device
                if current_time - last_daily_calc >= 86400:
                    for device_id in list(self.seen_connected):
                        th = self.devices_data[device_id]['timeframes']['hourly_week']
                        recent_in = th['in'][-24:] if len(th['in']) >= 24 else [0] * 24
                        recent_out = th['out'][-24:] if len(th['out']) >= 24 else [0] * 24
                        recent_conn = th['conn'][-24:] if len(th['conn']) >= 24 else ['disconnected'] * 24
                        while len(recent_in) < 24:
                            recent_in.insert(0, 0)
                            recent_out.insert(0, 0)
                            recent_conn.insert(0, 'disconnected')
                        avg_in = sum(recent_in) / len(recent_in)
                        avg_out = sum(recent_out) / len(recent_out)
                        # If ANY hour was connected, mark as connected
                        avg_conn = 'connected' if 'connected' in recent_conn else 'disconnected'
                        timestamp = datetime.now().strftime('%Y-%m-%dT00:00:00')
                        td = self.devices_data[device_id]['timeframes']['daily_year']
                        td['in'].append(avg_in)
                        td['out'].append(avg_out)
                        td['timestamps'].append(timestamp)
                        td['conn'].append(avg_conn)
                        self._cleanup_old_data('daily_year', device_id)
                        self._save_data('daily_year', device_id)
                    last_daily_calc = current_time
                    # cp.log(f'Calculated daily average: in={avg_in:.2f}, out={avg_out:.2f}')
                
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                cp.log(f'Error in averages calculation: {e}')
                time.sleep(60)
    
    def _format_bandwidth(self, bps):
        """Format bandwidth with appropriate unit (similar to WAN Rate app)."""
        if bps >= 1000000000:  # >= 1 Gbps
            return f"{round(bps / 1000000000, 1)} Gbps"
        elif bps >= 1000000:   # >= 1 Mbps
            return f"{round(bps / 1000000, 1)} Mbps"
        elif bps >= 1000:      # >= 1 Kbps
            return f"{round(bps / 1000, 1)} Kbps"
        else:
            return f"{round(bps, 1)} Bps"
    
    def _update_asset_id_with_averages(self, avg_ibps, avg_obps):
        """Update the configured field with average bandwidth data (similar to WAN Rate app)."""
        try:
            # Format with appropriate units
            ibps_formatted = self._format_bandwidth(avg_ibps)
            obps_formatted = self._format_bandwidth(avg_obps)
            
            # Create human-readable format with Unicode arrows
            human_readable = f"↓ {ibps_formatted}, ↑ {obps_formatted}"
            
            # Truncate to 255 characters if needed (asset_id field limit)
            if len(human_readable) > 255:
                human_readable = human_readable[:255]
            
            # Store in the configured field path
            result = cp.put(self.wan_rate_output_path, human_readable)
            
            if result and result.get('status') == 'ok':
                cp.log(f'Updated {self.wan_rate_output_path} with average rates: {human_readable}')
            else:
                cp.log(f'Failed to update {self.wan_rate_output_path}: {result}')
                
        except Exception as e:
            cp.log(f'Error updating {self.wan_rate_output_path}: {e}')
    
    def _convert_and_scale_data(self, data):
        """Convert and scale data with appropriate units."""
        try:
            in_data = data.get('in', [])
            out_data = data.get('out', [])
            
            if not in_data and not out_data:
                return {'in': [], 'out': []}, {'unit': 'bps', 'divisor': 1.0, 'suffix': 'bps'}
            
            all_values = in_data + out_data
            max_value = max(all_values) if all_values else 0
            
            # Determine appropriate unit
            if max_value >= 1e9:  # >= 1 Gbps
                unit = 'Gbps'
                divisor = 1e9
                suffix = 'Gbps'
            elif max_value >= 1e6:  # >= 1 Mbps
                unit = 'Mbps'
                divisor = 1e6
                suffix = 'Mbps'
            elif max_value >= 1e3:  # >= 1 Kbps
                unit = 'Kbps'
                divisor = 1e3
                suffix = 'Kbps'
            else:  # < 1 Kbps
                unit = 'bps'
                divisor = 1.0
                suffix = 'bps'
            
            converted_in = [x / divisor for x in in_data] if in_data else []
            converted_out = [x / divisor for x in out_data] if out_data else []
            
            return {
                'in': converted_in,
                'out': converted_out
            }, {
                'unit': unit,
                'divisor': divisor,
                'suffix': suffix
            }
            
        except Exception as e:
            cp.log(f'Error converting and scaling data: {e}')
            return {'in': [], 'out': []}, {'unit': 'bps', 'divisor': 1.0, 'suffix': 'bps'}
    
    def _serve_data(self, timeframe, device_id=None):
        """Serve data for the specified timeframe and device."""
        try:
            if not device_id:
                return {'labels': [], 'inData': [], 'outData': [], 'units': {'suffix': 'bps'}}
            device = self.devices_data.get(device_id)
            if not device:
                return {'labels': [], 'inData': [], 'outData': [], 'units': {'suffix': 'bps'}}
            actual_timeframe = timeframe if timeframe in device['timeframes'] else 'live'
            data = device['timeframes'][actual_timeframe]
            converted_data, unit_info = self._convert_and_scale_data(data)
            
            result = {
                'labels': data['timestamps'],
                'inData': converted_data.get('in', []),
                'outData': converted_data.get('out', []),
                'units': unit_info,
                'connData': data.get('conn', [])
            }
            
            # cp.log(f'Returning data: {len(result["labels"])} points, units: {unit_info["suffix"]}')
            return result
        except Exception as e:
            cp.log(f'Error serving data: {e}')
            return {'labels': [], 'inData': [], 'outData': [], 'units': {'suffix': 'bps'}}

    def _list_devices_ordered(self):
        """Return ordered list of device ids by priority, then connected first, then disconnected."""
        devices_states = self._list_devices()
        for dev, state in devices_states.items():
            self._ensure_device_structure(dev)
            self.devices_data[dev]['status'] = state
            self.devices_data[dev]['display'] = self._get_device_display_name(dev)
        # Update seen set for currently connected devices
        for d, s in devices_states.items():
            if s == 'connected':
                self.seen_connected.add(d)
        self._save_seen_connected()
        
        # Get priority for each device
        device_priorities = {}
        for dev in devices_states.keys():
            try:
                priority = cp.get(f"/status/wan/devices/{dev}/config/priority") or 0
                device_priorities[dev] = int(priority)
            except Exception:
                device_priorities[dev] = 0
        
        # Sort by priority (lower number = higher priority), then by connection status
        connected = [d for d, s in devices_states.items() if s == 'connected']
        disconnected = [d for d, s in devices_states.items() if s != 'connected' and d in self.seen_connected]
        
        # Sort each group by priority
        connected.sort(key=lambda d: device_priorities.get(d, 0))
        disconnected.sort(key=lambda d: device_priorities.get(d, 0))
        
        names = {d: self.devices_data.get(d, {}).get('display', d) for d in (connected + disconnected)}
        return {'connected': connected, 'disconnected': disconnected, 'names': names}
    
    
    def _generate_html_report(self, timeframe, device_id=None):
        """Generate HTML report for a timeframe across all interfaces."""
        try:
            # Aggregate per-device datasets for the selected timeframe
            ordered = self._list_devices_ordered()
            device_ids = ordered.get('connected', []) + ordered.get('disconnected', [])
            if not device_ids:
                return '<html><body><h1>No device data available</h1></body></html>'
            sample_dev = device_ids[0]
            actual_timeframe = timeframe if timeframe in self.devices_data[sample_dev]['timeframes'] else 'live'
            # Determine units using a combined view for scaling consistency
            all_in = []
            all_out = []
            for dev in device_ids:
                tf = self.devices_data[dev]['timeframes'][actual_timeframe]
                all_in += tf.get('in', [])
                all_out += tf.get('out', [])
            converted_all, unit_info = self._convert_and_scale_data({'in': all_in, 'out': all_out})
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            units = unit_info.get('suffix', 'bps')
            
            # Map timeframes to duration descriptions
            timeframe_descriptions = {
                'live': '5 Minutes',
                '5min_24h': '24 Hours', 
                'hourly_week': '1 Week',
                'daily_year': '1 Year'
            }
            
            # Build per-device charts and per-device tables separately
            per_device_charts = ''
            per_device_tables = ''
            for dev in device_ids:
                display_name = self.devices_data.get(dev, {}).get('display', dev)
                tf = self.devices_data[dev]['timeframes'][actual_timeframe]
                conv, _ = self._convert_and_scale_data(tf)
                labels_json = json.dumps(tf.get('timestamps', []))
                in_json = json.dumps(conv.get('in', []))
                out_json = json.dumps(conv.get('out', []))
                conn_json = json.dumps(tf.get('conn', []))
                # Build table rows per device
                rows = ''
                for i, ts in enumerate(tf.get('timestamps', [])):
                    if timeframe == 'live' and (':' in ts and 'T' not in ts):
                        current_date = datetime.now().strftime('%Y-%m-%d')
                        iso_ts = f"{current_date}T{ts}"
                    else:
                        iso_ts = ts
                    in_val = conv.get('in', [])[i] if i < len(conv.get('in', [])) else 0
                    out_val = conv.get('out', [])[i] if i < len(conv.get('out', [])) else 0
                    rows += f'<tr><td>{iso_ts}</td><td>{in_val:.2f}</td><td>{out_val:.2f}</td><td>{(in_val+out_val):.2f}</td></tr>'
                # Chart section only
                status = self.devices_data.get(dev, {}).get('status', '')
                chart_section = (
                    '<div class="chart-container"><h3>' + (display_name + (' - ' + status if status else '')) + '</h3><canvas id="chart_' + dev + '"></canvas></div>'
                    + '<script>'
                    + '(function(){\n'
                    + 'const ctx = document.getElementById("chart_' + dev + '").getContext("2d");\n'
                    + 'const labels = ' + labels_json + ';\n'
                    + 'const inData = ' + in_json + ';\n'
                    + 'const outData = ' + out_json + ';\n'
                    + 'const connData = ' + conn_json + ';\n'
                    + 'const datasets = [];\n'
                    + '// Process data with connection state coloring\n'
                    + 'let lastState = null;\n'
                    + 'let currentInSegment = { data: [], backgroundColor: [], borderColor: [], pointBackgroundColor: [], pointBorderColor: [] };\n'
                    + 'let currentOutSegment = { data: [], backgroundColor: [], borderColor: [], pointBackgroundColor: [], pointBorderColor: [] };\n'
                    + 'for (let i = 0; i < inData.length; i++) {\n'
                    + '  const state = connData[i] || "disconnected";\n'
                    + '  const inValue = inData[i];\n'
                    + '  const outValue = outData[i];\n'
                    + '  if (lastState !== state) {\n'
                    + '    // Save previous segments if they exist\n'
                    + '    if (currentInSegment.data.length > 0) {\n'
                    + '      if (lastState === "connected") {\n'
                    + '        datasets.push({\n'
                    + '          label: "Traffic IN",\n'
                    + '          data: currentInSegment.data,\n'
                    + '          backgroundColor: currentInSegment.backgroundColor,\n'
                    + '          borderColor: currentInSegment.borderColor,\n'
                    + '          pointBackgroundColor: currentInSegment.pointBackgroundColor,\n'
                    + '          pointBorderColor: currentInSegment.pointBorderColor,\n'
                    + '          borderWidth: 2, fill: false, tension: 0.1, pointStyle: "circle", radius: 3\n'
                    + '        });\n'
                    + '        datasets.push({\n'
                    + '          label: "Traffic OUT",\n'
                    + '          data: currentOutSegment.data,\n'
                    + '          backgroundColor: currentOutSegment.backgroundColor,\n'
                    + '          borderColor: currentOutSegment.borderColor,\n'
                    + '          pointBackgroundColor: currentOutSegment.pointBackgroundColor,\n'
                    + '          pointBorderColor: currentOutSegment.pointBorderColor,\n'
                    + '          borderWidth: 2, fill: true, tension: 0.1, pointStyle: "circle", radius: 3\n'
                    + '        });\n'
                    + '      } else {\n'
                    + '        // For disconnected, show only one line (use IN data as it will be 0)\n'
                    + '        datasets.push({\n'
                    + '          label: "Disconnected",\n'
                    + '          data: currentInSegment.data,\n'
                    + '          backgroundColor: currentInSegment.backgroundColor,\n'
                    + '          borderColor: currentInSegment.borderColor,\n'
                    + '          pointBackgroundColor: currentInSegment.pointBackgroundColor,\n'
                    + '          pointBorderColor: currentInSegment.pointBorderColor,\n'
                    + '          borderWidth: 2, fill: false, tension: 0.1, pointStyle: "circle", radius: 3\n'
                    + '        });\n'
                    + '      }\n'
                    + '    }\n'
                    + '    // Reset for new segment\n'
                    + '    currentInSegment = { data: Array(i).fill(NaN), backgroundColor: [], borderColor: [], pointBackgroundColor: [], pointBorderColor: [] };\n'
                    + '    currentOutSegment = { data: Array(i).fill(NaN), backgroundColor: [], borderColor: [], pointBackgroundColor: [], pointBorderColor: [] };\n'
                    + '    lastState = state;\n'
                    + '  }\n'
                    + '  // Add data to current segments\n'
                    + '  currentInSegment.data.push(inValue);\n'
                    + '  currentOutSegment.data.push(outValue);\n'
                    + '  if (state === "connected") {\n'
                    + '    currentInSegment.backgroundColor.push("rgba(229,62,62,0.1)");\n'
                    + '    currentInSegment.borderColor.push("#e53e3e");\n'
                    + '    currentInSegment.pointBackgroundColor.push("#e53e3e");\n'
                    + '    currentOutSegment.backgroundColor.push("rgba(56,161,105,0.1)");\n'
                    + '    currentOutSegment.borderColor.push("#38a169");\n'
                    + '    currentOutSegment.pointBackgroundColor.push("#38a169");\n'
                    + '  } else {\n'
                    + '    currentInSegment.backgroundColor.push("rgba(113,128,150,0.1)");\n'
                    + '    currentInSegment.borderColor.push("#a0aec0");\n'
                    + '    currentInSegment.pointBackgroundColor.push("#a0aec0");\n'
                    + '    currentOutSegment.backgroundColor.push("rgba(113,128,150,0.1)");\n'
                    + '    currentOutSegment.borderColor.push("#a0aec0");\n'
                    + '    currentOutSegment.pointBackgroundColor.push("#a0aec0");\n'
                    + '  }\n'
                    + '  currentInSegment.pointBorderColor.push("#fff");\n'
                    + '  currentOutSegment.pointBorderColor.push("#fff");\n'
                    + '}\n'
                    + '// Handle final segments\n'
                    + 'if (currentInSegment.data.length > 0) {\n'
                    + '  if (lastState === "connected") {\n'
                    + '    datasets.push({\n'
                    + '      label: "Traffic IN",\n'
                    + '      data: currentInSegment.data,\n'
                    + '      backgroundColor: currentInSegment.backgroundColor,\n'
                    + '      borderColor: currentInSegment.borderColor,\n'
                    + '      pointBackgroundColor: currentInSegment.pointBackgroundColor,\n'
                    + '      pointBorderColor: currentInSegment.pointBorderColor,\n'
                    + '      borderWidth: 2, fill: false, tension: 0.1, pointStyle: "circle", radius: 3\n'
                    + '    });\n'
                    + '    datasets.push({\n'
                    + '      label: "Traffic OUT",\n'
                    + '      data: currentOutSegment.data,\n'
                    + '      backgroundColor: currentOutSegment.backgroundColor,\n'
                    + '      borderColor: currentOutSegment.borderColor,\n'
                    + '      pointBackgroundColor: currentOutSegment.pointBackgroundColor,\n'
                    + '      pointBorderColor: currentOutSegment.pointBorderColor,\n'
                    + '      borderWidth: 2, fill: true, tension: 0.1, pointStyle: "circle", radius: 3\n'
                    + '    });\n'
                    + '  } else {\n'
                    + '    datasets.push({\n'
                    + '      label: "Disconnected",\n'
                    + '      data: currentInSegment.data,\n'
                    + '      backgroundColor: currentInSegment.backgroundColor,\n'
                    + '      borderColor: currentInSegment.borderColor,\n'
                    + '      pointBackgroundColor: currentInSegment.pointBackgroundColor,\n'
                    + '      pointBorderColor: currentInSegment.pointBorderColor,\n'
                    + '      borderWidth: 2, fill: false, tension: 0.1, pointStyle: "circle", radius: 3\n'
                    + '    });\n'
                    + '  }\n'
                    + '}\n'
                    + 'new Chart(ctx, { type: "line", data: { labels: labels, datasets: datasets }, options: { responsive: true, maintainAspectRatio: false, animation: { duration: 0 }, plugins: { legend: { display: true, labels: { usePointStyle: true } } }, scales: { x: { title: { display: true, text: "Time" } }, y: { title: { display: true, text: "' + units + '" }, beginAtZero: true } } } });\n'
                    + '})();'
                    + '</script>'
                )
                per_device_charts += chart_section
                # Table section only
                table_section = (
                    '<h4>Raw Data - ' + (display_name + (' - ' + status if status else '')) + '</h4>'
                    + '<table><thead><tr><th>Timestamp</th><th>Traffic IN (' + units + ')</th><th>Traffic OUT (' + units + ')</th><th>Total (' + units + ')</th></tr></thead><tbody>' + rows + '</tbody></table>'
                )
                per_device_tables += table_section
            
            # Generate HTML report
            html_report = f'''<!DOCTYPE html>
<html>
<head>
    <title>WAN Network Monitor Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #2d3748; margin-bottom: 10px; }}
        h2 {{ color: #4a5568; margin-bottom: 20px; }}
        .chart-container {{ height: 400px; margin: 20px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ border: 1px solid #e2e8f0; padding: 8px; text-align: left; }}
        th {{ background-color: #f7fafc; font-weight: bold; }}
        tr:nth-child(even) {{ background-color: #f7fafc; }}
        .summary {{ background: #edf2f7; padding: 15px; border-radius: 5px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="summary">
            <h1>WAN Bandwidth Report - {timeframe_descriptions.get(actual_timeframe, actual_timeframe.upper())} - {self.router_name}</h1>
            <p><strong>Generated:</strong> {timestamp}</p>
        </div>
        {per_device_charts}
        <hr />
        {per_device_tables}
    </div>
</body>
</html>'''
            
                    # cp.log(f'Generated HTML report with {data_points} data points')
            return html_report
        except Exception as e:
            cp.log(f'Error generating HTML report: {e}')
            return f'<html><body><h1>Error generating report: {e}</h1></body></html>'
    
    def start_server(self):
        """Start HTTP server."""
        dashboard = self  # Reference to the dashboard instance
        
        class DashboardHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed_url = urlparse(self.path)
                path = parsed_url.path
                query_params = parse_qs(parsed_url.query)
                
                if path == '/':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>WAN Dashboard - """ + dashboard.router_name + """</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #2d3748; margin-bottom: 20px; text-align: center; }
        .chart-section { margin: 30px 0; }
        .chart-container { height: 300px; margin: 20px 0; }
        .timeframe-btn { margin: 10px 5px; padding: 8px 16px; background: #4299e1; color: white; border: none; border-radius: 5px; cursor: pointer; }
        .timeframe-btn:hover { background: #3182ce; }
        .download-btn { margin: 10px 5px; padding: 8px 16px; background: #38a169; color: white; border: none; border-radius: 5px; cursor: pointer; }
        .download-btn:hover { background: #2f855a; }
        .chart-title { font-size: 18px; font-weight: bold; margin-bottom: 10px; color: #4a5568; }
    </style>
</head>
<body>
    <div class="container">
        <h1>WAN Dashboard - """ + dashboard.router_name + """</h1>
        <div style="text-align:center; margin-bottom: 16px; display:flex; gap:8px; justify-content:center; flex-wrap:wrap;">
            <button class="timeframe-btn" onclick="switchTf('live')">Live - 5min</button>
            <button class="timeframe-btn" onclick="switchTf('5min_24h')">5min averages - 24hr</button>
            <button class="timeframe-btn" onclick="switchTf('hourly_week')">Hourly averages - 1wk</button>
            <button class="timeframe-btn" onclick="switchTf('daily_year')">Daily averages - 1yr</button>
        </div>
        <div style="text-align:center; margin-bottom: 16px;">
            <button class="download-btn" onclick="downloadReportAll()">Download Current Report</button>
        </div>
        <div id="graphs"></div>
    </div>
    <script>
        let charts = {};
        let currentTf = 'live';
        let deviceOrder = [];

        function switchTf(tf){
            currentTf = tf;
            
            // Update button styles to show active timeframe
            document.querySelectorAll('.timeframe-btn').forEach(btn => {
                if (btn.onclick && btn.onclick.toString().includes(`switchTf('${tf}')`)) {
                    btn.style.backgroundColor = '#2d3748'; // Dark blue for active
                    btn.style.color = 'white';
                    btn.style.fontWeight = 'bold';
                } else {
                    btn.style.backgroundColor = '#4299e1'; // Blue for inactive
                    btn.style.color = 'white';
                    btn.style.fontWeight = 'normal';
                }
            });
            
            // update existing charts without rebuilding DOM, deviceOrder retained
            if (deviceOrder && deviceOrder.length){
                deviceOrder.forEach(dev => loadDeviceData(currentTf, dev, `chart_${dev}`));
            } else {
                renderGraphs();
            }
        }

        function fetchDevices(){
            return fetch('/api/devices').then(r=>r.json());
        }

        function renderGraphs(){
            fetchDevices().then(list => rebuildGraphs(list));
        }

        function rebuildGraphs(list){
            const container = document.getElementById('graphs');
            
            // Properly destroy existing charts before clearing
            Object.keys(charts).forEach(chartId => {
                if (charts[chartId]) {
                    charts[chartId].destroy();
                    delete charts[chartId];
                }
            });
            
            container.innerHTML = '';
            
            // Only show interfaces that are connected OR have been seen connected before
            const connectedDevices = list.connected || [];
            const seenConnectedDevices = list.seen_connected || [];
            const devicesToShow = [...new Set([...connectedDevices, ...seenConnectedDevices])];
            
            deviceOrder = devicesToShow;
            devicesToShow.forEach(dev=>{
                const status = list.connected.includes(dev) ? 'connected' : 'disconnected';
                const display = (list.names && list.names[dev]) ? list.names[dev] : dev;
                const card = document.createElement('div');
                card.className = 'chart-section';
                
                
                card.innerHTML = `<div class=\"chart-title\">${display} - <span style=\"color:${status==='connected'?'#38a169':'#718096'}\">${status}</span></div><div class=\"chart-container\"><canvas id=\"chart_${dev}\"></canvas></div>`;
                container.appendChild(card);
                loadDeviceData(currentTf, dev, `chart_${dev}`);
            });
        }

        function refreshDevices(){
            fetchDevices().then(list =>{
                const newOrder = [...list.connected, ...list.disconnected];
                if (newOrder.join(',') !== deviceOrder.join(',')){
                    rebuildGraphs(list);
                }
            });
        }

        function loadDeviceData(tf, device, chartId){
            fetch(`/api/data?timeframe=${tf}&device=${encodeURIComponent(device)}`)
                .then(r=>r.json())
                .then(data=>updateDeviceChart(chartId, data));
        }

        function splitByConn(arr, conn){
            const connected = arr.map((v,i)=> conn[i]==='connected'? v : null);
            const disconnected = arr.map((v,i)=> conn[i]!=='connected'? v : null);
            return {connected, disconnected};
        }

                    function updateDeviceChart(chartId, data){
                        const ctx = document.getElementById(chartId).getContext('2d');
                        const connData = data.connData || [];
                        const inData = data.inData || [];
                        const outData = data.outData || [];
                        
                        // Simple approach: create datasets based on connection state
                        const inConnected = inData.map((val, i) => connData[i] === 'connected' ? val : null);
                        const outConnected = outData.map((val, i) => connData[i] === 'connected' ? val : null);
                        const inDisconnected = inData.map((val, i) => connData[i] !== 'connected' ? val : null);
                        const outDisconnected = outData.map((val, i) => connData[i] !== 'connected' ? val : null);
                        
                        const datasets = [
                            {
                                label: 'Traffic IN',
                                data: inConnected,
                                borderColor: '#e53e3e',
                                backgroundColor: 'rgba(229,62,62,0.1)',
                                borderWidth: 2,
                                fill: false,
                                tension: 0.1,
                                pointStyle: 'circle',
                                radius: 3
                            },
                            {
                                label: 'Traffic OUT',
                                data: outConnected,
                                borderColor: '#38a169',
                                backgroundColor: 'rgba(56,161,105,0.1)',
                                borderWidth: 2,
                                fill: true,
                                tension: 0.1,
                                pointStyle: 'circle',
                                radius: 3
                            },
                            {
                                label: 'Disconnected',
                                data: inDisconnected,
                                borderColor: '#a0aec0',
                                backgroundColor: 'rgba(160,174,192,0.1)',
                                borderWidth: 2,
                                fill: false,
                                tension: 0.1,
                                pointStyle: 'circle',
                                radius: 3
                            }
                        ];
                        
                        if (!charts[chartId]){
                            charts[chartId] = new Chart(ctx, {
                                type: 'line',
                                data: { labels: data.labels, datasets: datasets },
                                options: {responsive:true, maintainAspectRatio:false, animation:{duration:0}, plugins:{ legend:{ labels:{ usePointStyle:true } } }, scales:{x:{title:{display:true,text:'Time'}}, y:{title:{display:true,text:data.units?.suffix||'bps'}, beginAtZero:true}}}
                            });
                        } else {
                            const chart = charts[chartId];
                            chart.data.labels = data.labels;
                            chart.data.datasets[0].data = inConnected;
                            chart.data.datasets[1].data = outConnected;
                            chart.data.datasets[2].data = inDisconnected;
                            chart.options.scales.y.title.text = data.units?.suffix || 'bps';
                            chart.update('none');
                        }
                    }

        function downloadReportAll(){
            window.open(`/api/report?timeframe=${currentTf}&download=true`, '_blank');
        }

        // initial render with button highlighting
        switchTf(currentTf);
        renderGraphs();
        // live updates without redraw
        setInterval(()=>{ if(currentTf==='live') deviceOrder.forEach(dev=>loadDeviceData(currentTf, dev, `chart_${dev}`)); }, 1000);
        // device list polling and slower timeframe updates
        setInterval(()=>{ refreshDevices(); if(currentTf!=='live') deviceOrder.forEach(dev=>loadDeviceData(currentTf, dev, `chart_${dev}`)); }, 5000);
    </script>
</body>
</html>"""
                    self.wfile.write(html_content.encode())
                
                elif path == '/api/data':
                    timeframe = query_params.get('timeframe', ['live'])[0]
                    device = query_params.get('device', [None])[0]
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    data = dashboard._serve_data(timeframe, device)
                    # cp.log(f'API request for {timeframe}: returning {len(data.get("labels", []))} data points')
                    self.wfile.write(json.dumps(data).encode())
                elif path == '/api/devices':
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    ordered_devices = dashboard._list_devices_ordered()
                    # Add seen_connected list to the response
                    ordered_devices['seen_connected'] = list(dashboard.seen_connected)
                    self.wfile.write(json.dumps(ordered_devices).encode())
                
                elif path == '/api/report':
                    timeframe = query_params.get('timeframe', ['live'])[0]
                    device = query_params.get('device', [None])[0]
                    download = query_params.get('download', ['false'])[0] == 'true'
                    
                    if download:
                        # Generate HTML report for download
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html')
                        
                        # Map internal timeframe names to filename prefixes
                        filename_mapping = {
                            'live': '5min',
                            '5min_24h': '24h',
                            'hourly_week': 'week',
                            'daily_year': 'year'
                        }
                        filename_prefix = filename_mapping.get(timeframe, timeframe)
                        
                        self.send_header('Content-Disposition', f'attachment; filename="wan_report_{filename_prefix}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html"')
                        self.end_headers()
                        html_report = dashboard._generate_html_report(timeframe, device)
                        self.wfile.write(html_report.encode())
                    else:
                        # Return JSON data for client-side processing
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        data = dashboard._serve_data(timeframe, device)
                        self.wfile.write(json.dumps(data).encode())
                
                else:
                    self.send_response(404)
                    self.end_headers()
        
        try:
            # Create custom HTTP server that bypasses IDNA encoding issues
            class CustomHTTPServer(HTTPServer):
                def server_bind(self):
                    # Override server_bind to avoid hostname resolution issues
                    import socket
                    self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    self.socket.bind(self.server_address)
                    self.server_address = self.socket.getsockname()
            
            # Try to bind to the configured port, fallback to next 100 ports if in use
            import socket
            server = None
            actual_port = None
            max_attempts = 100
            
            for attempt in range(max_attempts):
                try_port = dashboard.base_port + attempt
                if try_port > 65535:
                    cp.log(f"Error: Port {try_port} exceeds maximum port number (65535)")
                    break
                
                try:
                    # Test if port is available by trying to bind
                    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    test_socket.bind(('0.0.0.0', try_port))
                    test_socket.close()
                    
                    # Port is available, create and start the server
                    server = CustomHTTPServer(('0.0.0.0', try_port), DashboardHandler)
                    actual_port = try_port
                    dashboard.port = actual_port
                    cp.log(f"WAN Dashboard server started on port {actual_port}")
                    server.serve_forever()
                    break
                    
                except OSError as e:
                    if "Address already in use" in str(e) or "already in use" in str(e).lower():
                        if attempt < max_attempts - 1:
                            # Try next port
                            cp.log(f"Port {try_port} is in use, trying next port...")
                            continue
                        else:
                            cp.log(f"Error: Could not find an available port after {max_attempts} attempts")
                            return
                    else:
                        # Different OSError, log and try next port
                        if attempt < max_attempts - 1:
                            cp.log(f"Error testing port {try_port}: {e}, trying next port...")
                            continue
                        else:
                            cp.log(f"Error: Could not find an available port after {max_attempts} attempts: {e}")
                            return
                except Exception as e:
                    # Other exceptions, log and try next port
                    if attempt < max_attempts - 1:
                        cp.log(f"Error with port {try_port}: {e}, trying next port...")
                        continue
                    else:
                        cp.log(f"Error: Could not start server after {max_attempts} attempts: {e}")
                        return
                
        except UnicodeError as e:
            cp.log(f'IDNA encoding error - hostname contains invalid characters: {e}')
            cp.log('Server failed to start due to hostname encoding issues')
        except Exception as e:
            cp.log(f'Error starting server: {e}')


# Apps will never be imported, therefore do not need if __name__ == "__main__":
dashboard = WANDashboard()
