#!/usr/bin/env python3
"""
Power Dashboard for Cradlepoint Router
Comprehensive power usage tracking with web interface on port 8000
"""

import cp
import time
import json
import threading
import os
import signal
import sys
from datetime import datetime
import http.server
import socketserver

# Global variables for data storage
power_data = []
data_lock = threading.Lock()

# Global web server reference for cleanup
web_server = None
shutdown_requested = False

# Default thresholds
HIGH_THRESHOLD = 12.1
MED_THRESHOLD = 11.5

# File storage configuration
DATA_DIR = "tmp/power_dashboard_data"
POWER_FILE = f"{DATA_DIR}/power_data.json"
STATS_FILE = f"{DATA_DIR}/stats.json"

# Data retention settings - will be calculated dynamically based on interval
MAX_DATA_POINTS = None  # Will be calculated as 30 days worth of data based on interval
IN_MEMORY_POINTS = None  # Will be calculated as 24 hours worth of data based on interval

# Interval tracking file
INTERVAL_FILE = f"{DATA_DIR}/interval.json"

# Global variables for min/max power tracking
min_current = None
max_current = None
min_current_timestamp = None
max_current_timestamp = None

min_total = None
max_total = None
min_total_timestamp = None
max_total_timestamp = None

min_voltage = None
max_voltage = None
min_voltage_timestamp = None
max_voltage_timestamp = None

# Global variables for lights functionality
last_lights_update = None
lights_interval = None

# Global variables for signal functionality
last_signal_update = None
signal_interval = None

# Global variable for tracking voltage threshold state for alerts
previous_threshold_state = None

# Global variable for router model
router_model = None
adc_channel_enabled = False

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_requested, web_server
    cp.log(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True
    if web_server:
        cp.log("Shutting down web server...")
        web_server.shutdown()
        web_server.server_close()
    sys.exit(0)

def is_lights_enabled():
    """Check if lights functionality is enabled"""
    try:
        lights_appdata = cp.get_appdata('power_dashboard_lights')
        return lights_appdata is not None
    except Exception as e:
        cp.log(f"Error checking power_dashboard_lights: {e}")
        return False

def is_signal_enabled():
    """Check if signal functionality is enabled"""
    try:
        signal_appdata = cp.get_appdata('power_dashboard_signal')
        return signal_appdata is not None
    except Exception as e:
        cp.log(f"Error checking power_dashboard_signal: {e}")
        return False

def get_lights_interval():
    """Get lights update interval from appdata with default"""
    try:
        # Default 5 minutes (300 seconds)
        default_interval = 300
        
        try:
            interval_appdata = cp.get_appdata('power_dashboard_lights_interval')
            if interval_appdata:
                return int(interval_appdata)
        except Exception as e:
            cp.log(f"Error getting power_dashboard_lights_interval from appdata: {e}")
        
        return default_interval
    except Exception as e:
        cp.log(f"Error getting lights interval: {e}")
        return 300  # Return default on error

def get_signal_interval():
    """Get signal update interval from appdata with default"""
    try:
        # Default 5 minutes (300 seconds)
        default_interval = 300
        
        try:
            interval_appdata = cp.get_appdata('power_dashboard_signal_interval')
            if interval_appdata:
                return int(interval_appdata)
        except Exception as e:
            cp.log(f"Error getting power_dashboard_signal_interval from appdata: {e}")
        
        return default_interval
    except Exception as e:
        cp.log(f"Error getting signal interval: {e}")
        return 300  # Return default on error

def get_web_server_port():
    """Get web server port from appdata with default"""
    try:
        # Default port 8000
        default_port = 8000
        
        try:
            port_appdata = cp.get_appdata('power_dashboard_port')
            if port_appdata:
                return int(port_appdata)
        except Exception as e:
            cp.log(f"Error getting power dashboard port from appdata: {e}")
        return default_port  # Return default on error
    except Exception as e:
        cp.log(f"Error getting web server port: {e}")
        return default_port  # Return default on error

def get_voltage_thresholds():
    """Get voltage thresholds from appdata with defaults"""
    try:     
        # Initialize with defaults
        high = HIGH_THRESHOLD
        med = MED_THRESHOLD
        
        # Check for appdata overrides
        try:
            high_appdata = cp.get_appdata('power_dashboard_high')
            if high_appdata:
                high = float(high_appdata)
        except Exception as e:
            cp.log(f"Error getting power_dashboard_high from appdata: {e}")
        
        try:
            med_appdata = cp.get_appdata('power_dashboard_med')
            if med_appdata:
                med = float(med_appdata)
        except Exception as e:
            cp.log(f"Error getting power_dashboard_med from appdata: {e}")
        
        return high, med
    except Exception as e:
        cp.log(f"Error getting voltage thresholds: {e}")
        return HIGH_THRESHOLD, MED_THRESHOLD  # Return defaults on error

def get_voltage_indicator(voltage, high_threshold, med_threshold):
    """Get visual indicator for voltage level"""
    if voltage is None or voltage == 0:
        return "⚫"  # No voltage data - black circle
    elif voltage >= high_threshold:
        return "🟢"  # High voltage - green circle
    elif voltage >= med_threshold:
        return "🟡"  # Medium voltage - yellow circle
    else:
        return "🔴"  # Low voltage - red circle

def get_voltage_threshold_state(voltage, high_threshold, med_threshold):
    """Get threshold state as string for comparison"""
    if voltage is None or voltage == 0:
        return "none"
    elif voltage >= high_threshold:
        return "high"
    elif voltage >= med_threshold:
        return "medium"
    else:
        return "low"

def get_signal_stats():
    """Get modem signal statistics"""
    try:
        primary_device = cp.get_wan_primary_device()
        if not primary_device:
            return None
        
        diagnostics = cp.get_wan_modem_diagnostics(primary_device)
        if not diagnostics:
            return None
        
        # Extract signal stats
        dbm = diagnostics.get('dbm', 'N/A')
        sinr = diagnostics.get('sinr', 'N/A')
        rsrp = diagnostics.get('rsrp', 'N/A')
        rsrq = diagnostics.get('rsrq', 'N/A')
        
        return {
            'dbm': dbm,
            'sinr': sinr,
            'rsrp': rsrp,
            'rsrq': rsrq
        }
    except Exception as e:
        cp.log(f"Error getting signal stats: {e}")
        return None

def format_signal_stats(signal_stats):
    """Format signal stats as a pretty string"""
    if not signal_stats:
        return ""
    
    try:
        dbm = signal_stats.get('dbm') or 'N/A'
        sinr = signal_stats.get('sinr') or 'N/A'
        rsrp = signal_stats.get('rsrp') or 'N/A'
        rsrq = signal_stats.get('rsrq') or 'N/A'
        
        # Format as: DBM: -85dBm | SINR: 15dB | RSRP: -95dBm | RSRQ: -10dB
        # Handle cases where values might already have units
        dbm_str = str(dbm) if 'dBm' in str(dbm) or dbm == 'N/A' else f"{dbm}dBm"
        sinr_str = str(sinr) if 'dB' in str(sinr) or sinr == 'N/A' else f"{sinr}dB"
        rsrp_str = str(rsrp) if 'dBm' in str(rsrp) or rsrp == 'N/A' else f"{rsrp}dBm"
        rsrq_str = str(rsrq) if 'dB' in str(rsrq) or rsrq == 'N/A' else f"{rsrq}dB"
        
        return f"DBM: {dbm_str} | SINR: {sinr_str} | RSRP: {rsrp_str} | RSRQ: {rsrq_str}"
    except Exception as e:
        cp.log(f"Error formatting signal stats: {e}")
        return ""

def create_asset_id_message(power_info, voltage_indicator):
    """Create asset ID message with voltage indicator and power info"""
    try:
        voltage = power_info.get('voltage', 0)
        current = power_info.get('current', 0)
        total = power_info.get('total', 0)
        timestamp = power_info.get('timestamp', '')
        
        # Format power values to 2 decimal places, handle None values
        if voltage is None or voltage == 0:
            voltage_str = "N/A"
        else:
            voltage_str = f"{voltage:.2f}V"
        
        current_str = f"{current:.2f}A" if current is not None else "N/A"
        total_str = f"{total:.2f}W" if total is not None else "N/A"
        
        # Create message with voltage indicator and power info
        msg = f"{voltage_indicator} {voltage_str} | {current_str} | {total_str}"
        
        return msg
    except Exception as e:
        cp.log(f"Error creating asset ID message: {e}")
        return f"{voltage_indicator} Power Dashboard"

def get_power_info_r980_s400():
    """Get power info for R980 and S400 models"""
    try:
        power_usage = None
        while not power_usage:
            power_usage = cp.get('status/power_usage')
        total_power = power_usage.get('total', 0)
        voltage = power_usage.get('voltage', 0)
        current = power_usage.get('current', 0)
        
        result = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'current': current,
            'total': total_power,
            'voltage': voltage
        }
        return result
    except Exception as e:
        cp.log(f"Error getting power info for R980/S400: {e}")
        return None

def get_power_info_r920_r1900_s700_ibr1700_ibr600c_e3000():
    """Get power info for R920, R1900, S700, IBR1700, IBR600C, E3000 models"""
    try:
        # Get watts from standard path
        power_usage = None
        while not power_usage:
            power_usage = cp.get('status/power_usage')
        total_power = power_usage.get('total', 0)
        
        # Try to get current from standard path (may not be available)
        current = power_usage.get('current', 0)
        
        # Get voltage from ADC channel
        voltage = None
        try:
            adc_voltage = cp.get('status/system/adc/channel/1/voltage')
            if adc_voltage is not None:
                voltage = adc_voltage
        except Exception as e:
            cp.log(f"Error getting voltage from ADC channel: {e}")
            voltage = 0
        
        result = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'current': current,
            'total': total_power,
            'voltage': voltage
        }
        return result
    except Exception as e:
        cp.log(f"Error getting power info for R920/R1900/S700/IBR1700/IBR600C/E3000: {e}")
        return None

def get_power_info():
    """Get current power information from router based on model"""
    global router_model, adc_channel_enabled
    
    # Check if model is supported
    if router_model == 'IBR900':
        cp.log("Error: IBR900 model is not supported for power monitoring")
        return None
    
    # Route to model-specific function
    if router_model in ['R980', 'S400']:
        return get_power_info_r980_s400()
    elif router_model in ['R920', 'R1900', 'S700', 'IBR1700', 'IBR600C', 'E3000']:
        # Enable ADC channel for models that use it (one-time setup)
        if not adc_channel_enabled:
            cp.put('config/system/adc/channel/1/enabled', True)
            adc_channel_enabled = True
        return get_power_info_r920_r1900_s700_ibr1700_ibr600c_e3000()
    else:
        # Unknown model - try default path
        cp.log(f"Warning: Unknown router model {router_model}, trying default power_usage path")
        try:
            power_usage = None
            while not power_usage:
                power_usage = cp.get('status/power_usage')
            total_power = power_usage.get('total', 0)
            voltage = power_usage.get('voltage', 0)
            current = power_usage.get('current', 0)
            
            result = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'current': current,
                'total': total_power,
                'voltage': voltage
            }
            return result
        except Exception as e:
            cp.log(f"Error getting power info with default path: {e}")
            return None

def ensure_data_directory():
    """Ensure the data directory exists"""
    try:
        # Create directory with parents if they don't exist
        # This ensures tmp/ is created if it doesn't exist
        os.makedirs(DATA_DIR, exist_ok=True)
        # Verify it was created successfully
        if not os.path.exists(DATA_DIR):
            raise Exception(f"Directory {DATA_DIR} still does not exist after creation attempt")
    except Exception as e:
        cp.log(f"Error creating data directory: {e}")
        # Try to create tmp/ first if needed
        try:
            tmp_dir = "tmp"
            if not os.path.exists(tmp_dir):
                os.makedirs(tmp_dir, exist_ok=True)
                cp.log(f"Created tmp directory: {tmp_dir}")
            # Try creating DATA_DIR again
            os.makedirs(DATA_DIR, exist_ok=True)
        except Exception as e2:
            cp.log(f"Error creating tmp directory: {e2}")

def load_data_from_file(filename):
    """Load data from JSON file with corruption handling"""
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                data = json.load(f)
                # Validate that we got a list
                if not isinstance(data, list):
                    cp.log(f"Invalid data format in {filename}: expected list, got {type(data)}")
                    return []
                return data
        return []
    except json.JSONDecodeError as e:
        cp.log(f"JSON corruption detected in {filename}: {e}")
        cp.log(f"Attempting to recover by backing up corrupted file")
        try:
            # Backup the corrupted file
            backup_filename = filename + '.corrupted'
            os.rename(filename, backup_filename)
            cp.log(f"Corrupted file backed up as {backup_filename}")
        except Exception as backup_error:
            cp.log(f"Failed to backup corrupted file: {backup_error}")
        return []
    except Exception as e:
        cp.log(f"Error loading data from {filename}: {e}")
        return []

def save_data_to_file(data, filename):
    """Save data to JSON file with atomic write"""
    try:
        # Validate data before writing
        if not isinstance(data, (list, dict)):
            cp.log(f"Invalid data type for {filename}: {type(data)}")
            return False
        
        # Ensure the directory exists before writing
        # Create all parent directories including tmp/ if needed
        directory = os.path.dirname(filename)
        if directory:
            # Always ensure directory exists (os.makedirs handles parent directories)
            os.makedirs(directory, exist_ok=True)
            # Verify it was created successfully before proceeding
            if not os.path.exists(directory):
                raise Exception(f"Directory {directory} does not exist and could not be created")
        
        # Create temporary file for atomic write
        temp_filename = filename + '.tmp'
        
        # Write to temporary file first
        with open(temp_filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Validate the written JSON by reading it back
        try:
            with open(temp_filename, 'r') as f:
                json.load(f)  # This will raise an exception if JSON is invalid
        except json.JSONDecodeError as e:
            cp.log(f"Generated invalid JSON for {filename}: {e}")
            # Clean up temp file
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
            return False
        
        # Atomic move: rename temp file to final file
        if os.path.exists(filename):
            os.remove(filename)
        os.rename(temp_filename, filename)
        return True
        
    except Exception as e:
        cp.log(f"Error saving data to {filename}: {e}")
        # Clean up temp file if it exists
        temp_filename = filename + '.tmp'
        if os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
            except:
                pass
        return False

def clear_data_files():
    """Clear all data files to start fresh"""
    try:
        if os.path.exists(POWER_FILE):
            os.remove(POWER_FILE)
            cp.log("Cleared power data file")
        if os.path.exists(STATS_FILE):
            os.remove(STATS_FILE)
            cp.log("Cleared stats file")
    except Exception as e:
        cp.log(f"Error clearing data files: {e}")

def load_stats_from_file():
    """Load min/max stats from file"""
    global min_current, max_current, min_current_timestamp, max_current_timestamp
    global min_total, max_total, min_total_timestamp, max_total_timestamp
    global min_voltage, max_voltage, min_voltage_timestamp, max_voltage_timestamp
    
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r') as f:
                stats = json.load(f)
                min_current = stats.get('min_current')
                max_current = stats.get('max_current')
                min_current_timestamp = stats.get('min_current_timestamp')
                max_current_timestamp = stats.get('max_current_timestamp')
                min_total = stats.get('min_total')
                max_total = stats.get('max_total')
                min_total_timestamp = stats.get('min_total_timestamp')
                max_total_timestamp = stats.get('max_total_timestamp')
                min_voltage = stats.get('min_voltage')
                max_voltage = stats.get('max_voltage')
                min_voltage_timestamp = stats.get('min_voltage_timestamp')
                max_voltage_timestamp = stats.get('max_voltage_timestamp')
                cp.log("Loaded stats from file")
    except Exception as e:
        cp.log(f"Error loading stats from file: {e}")

def save_stats_to_file():
    """Save min/max stats to file"""
    try:
        stats = {
            'min_current': min_current,
            'max_current': max_current,
            'min_current_timestamp': min_current_timestamp,
            'max_current_timestamp': max_current_timestamp,
            'min_total': min_total,
            'max_total': max_total,
            'min_total_timestamp': min_total_timestamp,
            'max_total_timestamp': max_total_timestamp,
            'min_voltage': min_voltage,
            'max_voltage': max_voltage,
            'min_voltage_timestamp': min_voltage_timestamp,
            'max_voltage_timestamp': max_voltage_timestamp
        }
        save_data_to_file(stats, STATS_FILE)
    except Exception as e:
        cp.log(f"Error saving stats to file: {e}")

def save_interval_to_file(interval):
    """Save the current interval to file"""
    try:
        with open(INTERVAL_FILE, 'w') as f:
            json.dump({'interval': interval}, f)
    except Exception as e:
        cp.log(f"Error saving interval: {e}")

def load_interval_from_file():
    """Load the saved interval from file"""
    try:
        if os.path.exists(INTERVAL_FILE):
            with open(INTERVAL_FILE, 'r') as f:
                data = json.load(f)
                return data.get('interval')
    except Exception as e:
        cp.log(f"Error loading interval: {e}")
    return None

def clear_all_data():
    """Clear all data files when interval changes"""
    try:
        if os.path.exists(POWER_FILE):
            os.remove(POWER_FILE)
            cp.log("Cleared power data file")
        if os.path.exists(STATS_FILE):
            os.remove(STATS_FILE)
            cp.log("Cleared stats file")
        if os.path.exists(INTERVAL_FILE):
            os.remove(INTERVAL_FILE)
            cp.log("Cleared interval file")
    except Exception as e:
        cp.log(f"Error clearing data files: {e}")

def clear_corrupted_data():
    """Clear corrupted data files and start fresh"""
    try:
        # Remove main data files
        for filename in [POWER_FILE, STATS_FILE, INTERVAL_FILE]:
            if os.path.exists(filename):
                os.remove(filename)
                cp.log(f"Removed {filename}")
        
        # Remove any corrupted backup files
        for filename in [POWER_FILE + '.corrupted', STATS_FILE + '.corrupted']:
            if os.path.exists(filename):
                os.remove(filename)
                cp.log(f"Removed corrupted backup {filename}")
        
        # Remove any temporary files
        for filename in [POWER_FILE + '.tmp', STATS_FILE + '.tmp']:
            if os.path.exists(filename):
                os.remove(filename)
                cp.log(f"Removed temp file {filename}")
        
        cp.log("All corrupted data cleared - starting fresh")
    except Exception as e:
        cp.log(f"Error clearing corrupted data: {e}")


def power_monitor():
    """Background thread to monitor power usage"""
    global min_current, max_current, min_current_timestamp, max_current_timestamp
    global min_total, max_total, min_total_timestamp, max_total_timestamp
    global min_voltage, max_voltage, min_voltage_timestamp, max_voltage_timestamp
    global power_data, last_lights_update, lights_interval, shutdown_requested
    global previous_threshold_state, last_signal_update, signal_interval
    
    # Ensure data directory exists
    ensure_data_directory()
    
    # Get interval from appdata at startup only
    interval = 300  # Default 5 minutes
    try:
        appdata_value = cp.get_appdata('power_dashboard_interval')
        if appdata_value:
            interval = int(appdata_value)
    except Exception as e:
        cp.log(f"Error getting appdata, using default interval: {e}")
    
    cp.log(f"Power monitoring interval set to {interval} seconds")
    
    # Check if interval has changed from saved value
    saved_interval = load_interval_from_file()
    if saved_interval is not None and saved_interval != interval:
        cp.log(f"Interval changed from {saved_interval} to {interval} seconds - clearing all data")
        clear_all_data()
        # Reset global variables
        min_current = None
        max_current = None
        min_current_timestamp = None
        max_current_timestamp = None
        min_total = None
        max_total = None
        min_total_timestamp = None
        max_total_timestamp = None
        min_voltage = None
        max_voltage = None
        min_voltage_timestamp = None
        max_voltage_timestamp = None
        power_data = []
    else:
        # Load existing data and stats only if interval hasn't changed
        power_data = load_data_from_file(POWER_FILE)
        if not power_data:  # If data loading failed due to corruption
            cp.log("No valid data found - starting fresh")
            clear_corrupted_data()
        else:
            load_stats_from_file()
    
    # Save the current interval
    save_interval_to_file(interval)
    
    # Calculate data retention points based on interval
    global MAX_DATA_POINTS, IN_MEMORY_POINTS
    # 30 days worth of data: 30 days * 24 hours * 3600 seconds / interval
    MAX_DATA_POINTS = int(30 * 24 * 3600 / interval)
    # 24 hours worth of data: 24 hours * 3600 seconds / interval  
    IN_MEMORY_POINTS = int(24 * 3600 / interval)
    cp.log(f"Data retention updated: MAX_DATA_POINTS={MAX_DATA_POINTS}, IN_MEMORY_POINTS={IN_MEMORY_POINTS}")
    
    # Initialize lights functionality
    lights_interval = get_lights_interval()
    last_lights_update = None
    if is_lights_enabled():
        lights_path = cp.get_appdata('power_dashboard_lights_path') or 'config/system/asset_id'
    
    # Initialize signal functionality
    signal_interval = get_signal_interval()
    last_signal_update = None
    if is_signal_enabled():
        signal_path = cp.get_appdata('power_dashboard_signal_path') or 'config/system/asset_id'
    
    # Track if this is the first iteration (startup)
    is_first_iteration = True
        
    while not shutdown_requested:
        try:
            
            power_info = get_power_info()
            
            if power_info:
                # Get voltage thresholds for alerting
                high_threshold, med_threshold = get_voltage_thresholds()
                current_voltage = power_info['voltage']
                current_threshold_state = get_voltage_threshold_state(current_voltage, high_threshold, med_threshold)
                
                # Handle voltage threshold alerts
                try:
                    if is_first_iteration:
                        # On startup, send alert only if voltage is not high and not unavailable
                        if current_threshold_state != "high" and current_threshold_state != "none":
                            if current_voltage is not None and current_voltage != 0:
                                voltage_str = f"{current_voltage:.2f}V"
                            else:
                                voltage_str = "N/A"
                            
                            if current_threshold_state == "low":
                                alert_msg = f"Power Dashboard: Low voltage alert - {voltage_str} (below {med_threshold}V)"
                            else:  # medium
                                alert_msg = f"Power Dashboard: Medium voltage alert - {voltage_str} (below {high_threshold}V)"
                            cp.alert(alert_msg)
                            cp.log(f"Startup voltage alert sent: {alert_msg}")
                        previous_threshold_state = current_threshold_state
                        is_first_iteration = False
                    else:
                        # During regular operation, send alert only when threshold changes
                        # Do not send alerts if voltage is unavailable (state "none")
                        if previous_threshold_state is not None and current_threshold_state != previous_threshold_state and current_threshold_state != "none":
                            if current_voltage is not None and current_voltage != 0:
                                voltage_str = f"{current_voltage:.2f}V"
                            else:
                                voltage_str = "N/A"
                            
                            # Build alert message based on state transition
                            if current_threshold_state == "high":
                                alert_msg = f"Power Dashboard: Voltage returned to high - {voltage_str}"
                            elif current_threshold_state == "medium":
                                if previous_threshold_state == "high":
                                    alert_msg = f"Power Dashboard: Voltage dropped to medium - {voltage_str} (below {high_threshold}V)"
                                else:  # from low
                                    alert_msg = f"Power Dashboard: Voltage improved to medium - {voltage_str}"
                            elif current_threshold_state == "low":
                                alert_msg = f"Power Dashboard: Low voltage alert - {voltage_str} (below {med_threshold}V)"
                            
                            cp.alert(alert_msg)
                            cp.log(f"Voltage threshold change alert: {previous_threshold_state} -> {current_threshold_state}: {alert_msg}")
                        
                        # Always update previous state to track current threshold
                        previous_threshold_state = current_threshold_state
                except Exception as e:
                    cp.log(f"Error sending voltage alert: {e}")
                
                # Check if lights are enabled and it's time to update
                current_time = time.time()
                
                if is_lights_enabled():
                    if last_lights_update is None or (current_time - last_lights_update) >= lights_interval:
                        # Get voltage thresholds and create asset ID message
                        high_threshold, med_threshold = get_voltage_thresholds()
                        voltage_indicator = get_voltage_indicator(power_info['voltage'], high_threshold, med_threshold)
                        asset_id_msg = create_asset_id_message(power_info, voltage_indicator)
                        
                        # Append signal stats if signal is enabled
                        if is_signal_enabled():
                            signal_stats = get_signal_stats()
                            if signal_stats:
                                signal_str = format_signal_stats(signal_stats)
                                if signal_str:
                                    asset_id_msg = f"{asset_id_msg} | {signal_str}"
                        
                        lights_path = cp.get_appdata('power_dashboard_lights_path') or 'config/system/asset_id'
                        cp.put(lights_path, asset_id_msg)
                        last_lights_update = current_time
                
                # Check if signal is enabled (but lights are not) and it's time to update
                elif is_signal_enabled():
                    if last_signal_update is None or (current_time - last_signal_update) >= signal_interval:
                        signal_stats = get_signal_stats()
                        if signal_stats:
                            signal_msg = format_signal_stats(signal_stats)
                            if signal_msg:
                                signal_path = cp.get_appdata('power_dashboard_signal_path') or 'config/system/asset_id'
                                cp.put(signal_path, signal_msg)
                                last_signal_update = current_time

                with data_lock:
                    # Store power data immediately
                    power_data.append(power_info)
                    
                    # Keep only recent data in memory for fast access
                    if len(power_data) > IN_MEMORY_POINTS:
                        power_data = power_data[-IN_MEMORY_POINTS:]
                    
                    # Save data to file immediately
                    if not save_data_to_file(power_data, POWER_FILE):
                        cp.log("Failed to save power data - skipping this write")
                        continue
                    
                    # Update current min/max tracking
                    current_current = power_info['current']
                    current_timestamp = power_info['timestamp']
                    
                    if min_current is None or current_current < min_current:
                        min_current = current_current
                        min_current_timestamp = current_timestamp
                        save_stats_to_file()
                    
                    if max_current is None or current_current > max_current:
                        max_current = current_current
                        max_current_timestamp = current_timestamp
                        save_stats_to_file()
                    
                    # Update total min/max tracking
                    current_total = power_info['total']
                    
                    if min_total is None or current_total < min_total:
                        min_total = current_total
                        min_total_timestamp = current_timestamp
                        save_stats_to_file()
                    
                    if max_total is None or current_total > max_total:
                        max_total = current_total
                        max_total_timestamp = current_timestamp
                        save_stats_to_file()
                    
                    # Update voltage min/max tracking
                    current_voltage = power_info['voltage']
                    
                    if min_voltage is None or current_voltage < min_voltage:
                        min_voltage = current_voltage
                        min_voltage_timestamp = current_timestamp
                        save_stats_to_file()
                    
                    if max_voltage is None or current_voltage > max_voltage:
                        max_voltage = current_voltage
                        max_voltage_timestamp = current_timestamp
                        save_stats_to_file()
                
            
            time.sleep(interval)
            
        except Exception as e:
            cp.log(f"Error in power monitor: {e}")
            time.sleep(interval)

def create_html_page():
    """Create the HTML page for the web interface"""
    device_name = cp.get_name()
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>Power Dashboard</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f8f9fa;
            color: #333;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 0;
            border-radius: 0;
            box-shadow: none;
        }
        .header {
            background: #343a40;
            color: white;
            padding: 20px 30px;
            margin-bottom: 0;
            border-bottom: none;
            max-width: 1000px;
            margin-left: auto;
            margin-right: auto;
        }
        
        .time-range-selector {
            text-align: center;
            margin-bottom: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            border: 1px solid #e9ecef;
            max-width: 1000px;
            margin-left: auto;
            margin-right: auto;
        }
        
        .time-range-selector label {
            font-weight: 600;
            margin-right: 10px;
            color: #495057;
        }
        
        .time-range-selector select {
            padding: 8px 12px;
            border: 1px solid #ced4da;
            border-radius: 4px;
            background: white;
            font-size: 14px;
            color: #495057;
        }
        .header h1 {
            margin: 0;
            font-size: 2.2em;
            font-weight: 600;
        }
        .device-name {
            font-size: 1.1em;
            font-weight: 500;
            color: rgba(255, 255, 255, 0.9);
            margin-top: 8px;
        }
        .current-time {
            font-size: 1.2em;
            font-weight: bold;
            color: #007cba;
            margin-top: 10px;
            font-family: 'Courier New', monospace;
        }
        .main-content {
            padding: 30px;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-bottom: 30px;
            max-width: 1000px;
            margin-left: auto;
            margin-right: auto;
        }
        .stats-row-2 {
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 15px;
            margin-bottom: 30px;
            max-width: 1000px;
            margin-left: auto;
            margin-right: auto;
        }
        @media (max-width: 1200px) {
            .stats-row-2 {
                grid-template-columns: repeat(3, 1fr);
            }
        }
        @media (max-width: 768px) {
            .stats {
                grid-template-columns: repeat(2, 1fr);
            }
            .stats-row-2 {
                grid-template-columns: repeat(2, 1fr);
            }
        }
        .stat-card {
            background: white;
            padding: 10px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid #e9ecef;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: transform 0.2s ease;
        }
        .stat-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }
        .stat-card.current {
            border-left: 4px solid #20b2aa;
        }
        .stat-card.total {
            border-left: 4px solid #28a745;
        }
        .stat-card.voltage {
            border-left: 4px solid #dc3545;
        }
        .stat-value {
            font-size: 1.1em;
            font-weight: 700;
            color: #333;
            margin-bottom: 5px;
        }
        .stat-label {
            color: #6c757d;
            margin-top: 0;
            font-size: 0.9em;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .stat-timestamp {
            color: #adb5bd;
            font-size: 0.75em;
            margin-top: 8px;
            font-weight: 400;
        }
        .loading-indicator {
            background: #e3f2fd;
            border: 2px solid #2196f3;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            margin: 20px 0;
            display: block;
        }
        .loading-spinner {
            width: 40px;
            height: 40px;
            border: 4px solid #f3f3f3;
            border-top: 4px solid #2196f3;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .loading-text {
            font-size: 1.2em;
            color: #1976d2;
            font-weight: bold;
            margin-bottom: 10px;
        }
        .loading-progress {
            color: #666;
            font-size: 0.9em;
        }
        .chart-container {
            background: white;
            padding: 25px;
            border-radius: 8px;
            margin-bottom: 25px;
            position: relative;
            height: 300px;
            max-width: 1000px;
            margin-left: auto;
            margin-right: auto;
            overflow: hidden;
            border: 1px solid #e9ecef;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .chart-container canvas {
            max-height: 100%;
            max-width: 100%;
        }
        .chart-title {
            font-size: 1.3em;
            font-weight: 600;
            color: #333;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #343a40;
        }
        .data-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 25px;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .data-table th, .data-table td {
            border: none;
            padding: 12px 15px;
            text-align: left;
        }
        .data-table th {
            background: #343a40;
            color: white;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-size: 0.85em;
        }
        .data-table tr:nth-child(even) {
            background-color: #f8f9fa;
        }
        .data-table tr:hover {
            background-color: #e9ecef;
        }
        .footer {
            text-align: center;
            margin-top: 20px;
            color: #666;
            font-size: 0.9em;
        }
        .controls {
            text-align: center;
            margin-bottom: 20px;
        }
        .btn {
            background: #343a40;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            cursor: pointer;
            margin: 25px 0;
            font-size: 16px;
            font-weight: 600;
            transition: all 0.3s ease;
            box-shadow: 0 2px 4px rgba(52, 58, 64, 0.3);
        }
        .btn:hover {
            background: #2c3136;
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(52, 58, 64, 0.4);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Power Dashboard</h1>
            <div class="device-name" id="device-name">""" + device_name + """</div>
        </div>
        
        <div class="main-content">
        
        <div class="stats">
            <div class="stat-card total">
                <div class="stat-value" id="current-total">--</div>
                <div class="stat-label">Power (W)</div>
            </div>
            <div class="stat-card voltage">
                <div class="stat-value" id="current-voltage">--</div>
                <div class="stat-label">Voltage (V)</div>
            </div>
            <div class="stat-card current">
                <div class="stat-value" id="current-current">--</div>
                <div class="stat-label">Current (A)</div>
            </div>
        </div>
        
        <div class="stats-row-2">
            <div class="stat-card total">
                <div class="stat-value" id="min-total">--</div>
                <div class="stat-label">Min Power (W)</div>
                <div class="stat-timestamp" id="min-total-timestamp">--</div>
            </div>
            <div class="stat-card total">
                <div class="stat-value" id="max-total">--</div>
                <div class="stat-label">Max Power (W)</div>
                <div class="stat-timestamp" id="max-total-timestamp">--</div>
            </div>
            <div class="stat-card voltage">
                <div class="stat-value" id="min-voltage">--</div>
                <div class="stat-label">Min Voltage (V)</div>
                <div class="stat-timestamp" id="min-voltage-timestamp">--</div>
            </div>
            <div class="stat-card voltage">
                <div class="stat-value" id="max-voltage">--</div>
                <div class="stat-label">Max Voltage (V)</div>
                <div class="stat-timestamp" id="max-voltage-timestamp">--</div>
            </div>
            <div class="stat-card current">
                <div class="stat-value" id="min-current">--</div>
                <div class="stat-label">Min Current (A)</div>
                <div class="stat-timestamp" id="min-current-timestamp">--</div>
            </div>
            <div class="stat-card current">
                <div class="stat-value" id="max-current">--</div>
                <div class="stat-label">Max Current (A)</div>
                <div class="stat-timestamp" id="max-current-timestamp">--</div>
            </div>
        </div>
        
        <div class="time-range-selector">
            <label for="timeRange">Time Range:</label>
            <select id="timeRange" onchange="updateTimeRange()">
                <option value="live">Live</option>
                <option value="hour">Hour</option>
                <option value="day" selected>Day</option>
                <option value="week">Week</option>
                <option value="month">Month</option>
            </select>
        </div>
        
        <div class="loading-indicator" id="loading-indicator" style="display: none;">
            <div class="loading-spinner"></div>
            <div class="loading-text">Loading data...</div>
        </div>
        
        <div class="chart-container">
            <h3 class="chart-title">Power (W) Over Time</h3>
            <canvas id="powerChart" width="969" height="300" style="display: block; box-sizing: border-box; height: 90%; width: 100%;"></canvas>
        </div>
        
        <div class="chart-container">
            <h3 class="chart-title">Voltage (V) Over Time</h3>
            <canvas id="voltageChart" width="969" height="300" style="display: block; box-sizing: border-box; height: 90%; width: 100%;"></canvas>
        </div>
        
        <div class="chart-container">
            <h3 class="chart-title">Current (A) Over Time</h3>
            <canvas id="currentChart" width="969" height="300" style="display: block; box-sizing: border-box; height: 90%; width: 100%;"></canvas>
        </div>
        
        <div class="controls">
            <button class="btn" onclick="downloadCSV()">Download CSV Report</button>
        </div>
        
        <div class="chart-container">
            <h3>Recent Power Data</h3>
            <table class="data-table" id="dataTable">
                <thead>
                    <tr>
                <th>Time</th>
                <th>Power (W)</th>
                <th>Voltage (V)</th>
                <th>Current (A)</th>
                    </tr>
                </thead>
                <tbody id="dataTableBody">
                </tbody>
            </table>
        </div>
        
        </div>
        <div class="footer">
            <p>Power Dashboard Web Application | Last updated: <span id="last-update">--</span></p>
        </div>
    </div>

    <script>
        let powerChart;
        let voltageChart;
        let currentChart;
        
        // Initialize power chart
        function initPowerChart() {
            const canvas = document.getElementById('powerChart');
            const ctx = canvas.getContext('2d');
            // Explicit sizing per Cursor rules: canvas 320px internal, 300px CSS, width fills container
            try {
                const w = canvas.parentElement ? canvas.parentElement.clientWidth : canvas.width;
                if (w) canvas.width = w;
            } catch (e) {}
            canvas.height = 320;
            
            powerChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Power (W)',
                        data: [],
                        borderColor: '#28a745',
                        backgroundColor: 'rgba(40, 167, 69, 0.1)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: false,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false,
                    },
                    scales: {
                        x: {
                            type: 'category',
                            display: true,
                            title: {
                                display: true,
                                text: 'Time'
                            },
                            ticks: {
                                display: true,
                                font: {
                                    size: 12
                                },
                                maxRotation: 45,
                                minRotation: 0
                            }
                        },
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Power (W)'
                            },
                            ticks: {
                                callback: function(value) {
                                    return parseFloat(value.toFixed(3)) + 'W';
                                }
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top'
                        },
                        tooltip: {
                            callbacks: {
                                title: function(context) {
                                    return 'Time: ' + context[0].label;
                                },
                                label: function(context) {
                                    const value = context.parsed.y;
                                    const label = context.dataset.label;
                                    if (label.includes('Current')) {
                                        return label + ': ' + value.toFixed(3) + 'A';
                                    } else if (label.includes('Total')) {
                                        return label + ': ' + value.toFixed(3) + 'W';
                                    } else if (label.includes('Voltage')) {
                                        return label + ': ' + value.toFixed(3) + 'V';
                                    }
                                    return label + ': ' + value.toFixed(3);
                                }
                            }
                        }
                    },
                    layout: {
                        padding: {
                            top: 10,
                            bottom: 10
                        }
                    }
                }
            });
        }
        
        // Initialize voltage chart
        function initVoltageChart() {
            const canvas = document.getElementById('voltageChart');
            const ctx = canvas.getContext('2d');
            // Explicit sizing per Cursor rules: canvas 320px internal, 300px CSS, width fills container
            try {
                const w = canvas.parentElement ? canvas.parentElement.clientWidth : canvas.width;
                if (w) canvas.width = w;
            } catch (e) {}
            canvas.height = 320;
            
            voltageChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Voltage (V)',
                        data: [],
                        borderColor: '#dc3545',
                        backgroundColor: 'rgba(220, 53, 69, 0.1)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: false,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false,
                    },
                    scales: {
                        x: {
                            type: 'category',
                            display: true,
                            title: {
                                display: true,
                                text: 'Time'
                            },
                            ticks: {
                                display: true,
                                font: {
                                    size: 12
                                },
                                maxRotation: 45,
                                minRotation: 0
                            }
                        },
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Voltage (V)'
                            },
                            ticks: {
                                callback: function(value) {
                                    return parseFloat(value.toFixed(3)) + 'V';
                                }
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top'
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const value = context.parsed.y;
                                    return 'Voltage: ' + parseFloat(value.toFixed(3)) + 'V';
                                }
                            }
                        }
                    }
                }
            });
        }
        
        // Initialize current chart
        function initCurrentChart() {
            const canvas = document.getElementById('currentChart');
            const ctx = canvas.getContext('2d');
            // Explicit sizing per Cursor rules: canvas 320px internal, 300px CSS, width fills container
            try {
                const w = canvas.parentElement ? canvas.parentElement.clientWidth : canvas.width;
                if (w) canvas.width = w;
            } catch (e) {}
            canvas.height = 320;
            
            currentChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Current (A)',
                        data: [],
                        borderColor: '#007cba',
                        backgroundColor: 'rgba(0, 124, 186, 0.1)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: false,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false,
                    },
                    scales: {
                        x: {
                            type: 'category',
                            display: true,
                            title: {
                                display: true,
                                text: 'Time'
                            },
                            ticks: {
                                display: true,
                                font: {
                                    size: 12
                                },
                                maxRotation: 45,
                                minRotation: 0
                            }
                        },
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Current (A)'
                            },
                            ticks: {
                                callback: function(value) {
                                    return parseFloat(value.toFixed(3)) + 'A';
                                }
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top'
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const value = context.parsed.y;
                                    return 'Current: ' + parseFloat(value.toFixed(3)) + 'A';
                                }
                            }
                        }
                    }
                }
            });
        }
        
        // Update power chart with data
        function updatePowerChart(data) {
            console.log('updatePowerChart called with data:', data);
            
            if (!data || data.length === 0) {
                console.log('No data to update charts');
                return;
            }
            
            // For category scales, we need labels and simple data arrays
            // Create two-line labels: first line is time, second line is date
            const labels = data.map(item => {
                const timestamp = item.timestamp;
                // Parse "YYYY-MM-DD HH:MM:SS" format
                const [datePart, timePart] = timestamp.split(' ');
                const [year, month, day] = datePart.split('-');
                const [hour, minute, second] = timePart.split(':');
                
                // Return array for two-line label: [time, date]
                // Second line: MM-DD-YY format
                const shortYear = year.slice(-2); // Get last 2 digits of year
                return [`${hour}:${minute}:${second}`, `${month}-${day}-${shortYear}`];
            });
            const powerData = data.map(item => item.total);
            const voltageData = data.map(item => item.voltage);
            const currentData = data.map(item => item.current);
            
            console.log('Updating charts with data:', { labels, powerData, voltageData, currentData });
            
            if (powerChart) {
                powerChart.data.labels = labels;
                powerChart.data.datasets[0].data = powerData;
                powerChart.update('none');
                console.log('Power chart updated');
            }
            
            if (voltageChart) {
                voltageChart.data.labels = labels;
                voltageChart.data.datasets[0].data = voltageData;
                voltageChart.update('none');
                console.log('Voltage chart updated');
            }
            
            if (currentChart) {
                currentChart.data.labels = labels;
                currentChart.data.datasets[0].data = currentData;
                currentChart.update('none');
                console.log('Current chart updated');
            }
        }
        
        // Update statistics
        function updateStats(powerData, minCurrent, maxCurrent, minCurrentTimestamp, maxCurrentTimestamp, minTotal, maxTotal, minTotalTimestamp, maxTotalTimestamp, minVoltage, maxVoltage, minVoltageTimestamp, maxVoltageTimestamp) {
            if (powerData.length > 0) {
                const latest = powerData[powerData.length - 1];
                document.getElementById('current-current').textContent = parseFloat(latest.current.toFixed(3)) + 'A';
                document.getElementById('current-total').textContent = parseFloat(latest.total.toFixed(3)) + 'W';
                document.getElementById('current-voltage').textContent = parseFloat(latest.voltage.toFixed(3)) + 'V';
                document.getElementById('last-update').textContent = latest.timestamp;
                
                // Update min/max values
                if (minCurrent !== null) {
                    document.getElementById('min-current').textContent = parseFloat(minCurrent.toFixed(3)) + 'A';
                    document.getElementById('min-current-timestamp').textContent = minCurrentTimestamp || '--';
                }
                if (maxCurrent !== null) {
                    document.getElementById('max-current').textContent = parseFloat(maxCurrent.toFixed(3)) + 'A';
                    document.getElementById('max-current-timestamp').textContent = maxCurrentTimestamp || '--';
                }
                if (minTotal !== null) {
                    document.getElementById('min-total').textContent = parseFloat(minTotal.toFixed(3)) + 'W';
                    document.getElementById('min-total-timestamp').textContent = minTotalTimestamp || '--';
                }
                if (maxTotal !== null) {
                    document.getElementById('max-total').textContent = parseFloat(maxTotal.toFixed(3)) + 'W';
                    document.getElementById('max-total-timestamp').textContent = maxTotalTimestamp || '--';
                }
                if (minVoltage !== null) {
                    document.getElementById('min-voltage').textContent = parseFloat(minVoltage.toFixed(3)) + 'V';
                    document.getElementById('min-voltage-timestamp').textContent = minVoltageTimestamp || '--';
                }
                if (maxVoltage !== null) {
                    document.getElementById('max-voltage').textContent = parseFloat(maxVoltage.toFixed(3)) + 'V';
                    document.getElementById('max-voltage-timestamp').textContent = maxVoltageTimestamp || '--';
                }
            }
        }
        
        // Update current time
        function updateTime() {
            // Time display was removed from UI, so this function is no longer needed
        }
        
        function updateTimeRange() {
            const timeRange = document.getElementById('timeRange').value;
            console.log('Time range changed to:', timeRange);
            
            // Clear any existing intervals
            if (liveUpdateInterval) {
                clearInterval(liveUpdateInterval);
                liveUpdateInterval = null;
            }
            if (regularUpdateInterval) {
                clearInterval(regularUpdateInterval);
                regularUpdateInterval = null;
            }
            
            if (timeRange === 'live') {
                // Live mode: poll every 1 second
                liveDataBuffer = []; // Clear buffer when switching to live
                updateLiveData(); // Initial update
                liveUpdateInterval = setInterval(updateLiveData, 1000);
            } else {
                // Regular mode: use saved data with 2 second polling
                updateAllData(); // Initial update
                regularUpdateInterval = setInterval(updateAllData, 2000);
            }
        }
        
        function filterDataByTimeRange(data, timeRange) {
            if (!data || data.length === 0) return data;
            
            // Live mode should not use this function, but handle it gracefully
            if (timeRange === 'live') {
                return data;
            }
            
            const now = new Date();
            let cutoffTime;
            
            switch(timeRange) {
                case 'hour':
                    cutoffTime = new Date(now.getTime() - 60 * 60 * 1000); // 1 hour ago
                    break;
                case 'day':
                    cutoffTime = new Date(now.getTime() - 24 * 60 * 60 * 1000); // 1 day ago
                    break;
                case 'week':
                    cutoffTime = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000); // 1 week ago
                    break;
                case 'month':
                    cutoffTime = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000); // 1 month ago
                    break;
                default:
                    return data;
            }
            
            return data.filter(item => {
                // Parse the timestamp format "YYYY-MM-DD HH:MM:SS"
                const timestamp = item.timestamp;
                if (!timestamp) return false;
                
                // Extract year, month, day, hour, minute, second from "YYYY-MM-DD HH:MM:SS"
                const parts = timestamp.split(' ');
                if (parts.length !== 2) return false;
                
                const datePart = parts[0]; // "YYYY-MM-DD"
                const timePart = parts[1]; // "HH:MM:SS"
                
                const [year, month, day] = datePart.split('-').map(Number);
                const [hour, minute, second] = timePart.split(':').map(Number);
                
                // Create date with full year
                const itemTime = new Date(year, month - 1, day, hour, minute, second);
                
                return itemTime >= cutoffTime;
            });
        }
        
        // Update loading indicator
        function updateLoadingIndicator(isLoading) {
            const loadingIndicator = document.getElementById('loading-indicator');
            
            if (isLoading) {
                loadingIndicator.style.display = 'block';
            } else {
                loadingIndicator.style.display = 'none';
            }
        }
        
        // Update data table
        function updateTable(powerData) {
            const tbody = document.getElementById('dataTableBody');
            tbody.innerHTML = '';
            
            // Show last 20 data points
            const recentData = powerData.slice(-20).reverse();
            
            for (let i = 0; i < recentData.length; i++) {
                const item = recentData[i];
                
                const row = tbody.insertRow();
                row.innerHTML = `
                    <td>${item.timestamp}</td>
                    <td>${parseFloat(item.total.toFixed(3))}W</td>
                    <td>${parseFloat(item.voltage.toFixed(3))}V</td>
                    <td>${parseFloat(item.current.toFixed(3))}A</td>
                `;
            }
        }
        
        // Live data buffer (rolling buffer for last 5 minutes)
        let liveDataBuffer = [];
        const LIVE_BUFFER_SIZE = 300; // 5 minutes at 1 second intervals
        let liveUpdateInterval = null;
        let regularUpdateInterval = null;
        
        // Fetch data from server
        // Fetch data from server (like WAN dashboard)
        function fetchData() {
            return fetch('/api/power-data').then(r => r.json());
        }
        
        // Fetch live data from server (current power reading)
        function fetchLiveData() {
            return fetch('/api/live-power-data').then(r => r.json());
        }
        
        // Update live data (1 second polling)
        function updateLiveData() {
            fetchLiveData().then(data => {
                if (data && data.timestamp) {
                    // Add new data point to buffer
                    liveDataBuffer.push(data);
                    
                    // Keep only last LIVE_BUFFER_SIZE points
                    if (liveDataBuffer.length > LIVE_BUFFER_SIZE) {
                        liveDataBuffer = liveDataBuffer.slice(-LIVE_BUFFER_SIZE);
                    }
                    
                    // Update charts with live buffer data
                    updatePowerChart(liveDataBuffer);
                    
                    // Update stats with latest data point
                    updateStats([data], null, null, null, null, null, null, null, null, null, null, null, null);
                    
                    // Update table with last 20 points from buffer
                    updateTable(liveDataBuffer.slice(-20));
                }
            }).catch(error => {
                console.error('Error fetching live data:', error);
            });
        }
        
        // Update all data (charts, stats, table)
        function updateAllData() {
            fetchData().then(data => {
                console.log('Fetched data:', data);
                if (data.power_data && data.power_data.length > 0) {
                    // Get current time range selection
                    const timeRange = document.getElementById('timeRange').value;
                    
                    // Filter data based on time range
                    const filteredData = filterDataByTimeRange(data.power_data, timeRange);
                    
                    console.log('Filtered data for', timeRange, ':', filteredData.length, 'points');
                    
                    // Update charts with filtered data
                    updatePowerChart(filteredData);
                    
                    // Update stats with original data (not filtered) to show overall min/max
                    updateStats(data.power_data, data.min_current, data.max_current, data.min_current_timestamp, data.max_current_timestamp, data.min_total, data.max_total, data.min_total_timestamp, data.max_total_timestamp, data.min_voltage, data.max_voltage, data.min_voltage_timestamp, data.max_voltage_timestamp);
                    
                    // Update table with filtered data
                    updateTable(filteredData);
                } else {
                    console.log('No data available yet, will retry...');
                }
            }).catch(error => {
                console.error('Error fetching data:', error);
            });
        }
        
        // Refresh data (SSE handles this automatically)
        // Download CSV
        function downloadCSV() {
            fetch('/api/csv-report')
                .then(response => response.json())
                .then(data => {
                    const blob = new Blob([data.csv_content], { type: 'text/csv' });
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = data.filename;
                    a.click();
                    window.URL.revokeObjectURL(url);
                });
        }
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            // Load Chart.js and time adapter from CDN
            const chartScript = document.createElement('script');
            chartScript.src = 'https://cdn.jsdelivr.net/npm/chart.js';
            chartScript.onload = function() {
                const timeAdapterScript = document.createElement('script');
                timeAdapterScript.src = 'https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns';
                timeAdapterScript.onload = function() {
                    // Initialize charts first
                    initPowerChart();
                    initVoltageChart();
                    initCurrentChart();
                    
                    // Wait a moment for charts to be ready, then load data
                    setTimeout(function() {
                        // Check initial time range and start appropriate polling
                        const timeRange = document.getElementById('timeRange').value;
                        if (timeRange === 'live') {
                            liveDataBuffer = [];
                            updateLiveData();
                            liveUpdateInterval = setInterval(updateLiveData, 1000);
                        } else {
                            updateAllData();
                            regularUpdateInterval = setInterval(updateAllData, 2000);
                        }
                    }, 100);
                };
                document.head.appendChild(timeAdapterScript);
            };
            document.head.appendChild(chartScript);
        });
    </script>
</body>
</html>
    """
    return html


def start_web_server():
    """Start a simple HTTP server on configured port (default 8000)"""
    global web_server, shutdown_requested
    
    # Get port from appdata, default to 8000
    preferred_port = get_web_server_port()
    
    class PowerTrackerHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/':
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(create_html_page().encode())
            elif self.path == '/api/power-data':
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                with data_lock:
                    data = {
                        'power_data': power_data,
                        'min_current': min_current,
                        'max_current': max_current,
                        'min_current_timestamp': min_current_timestamp,
                        'max_current_timestamp': max_current_timestamp,
                        'min_total': min_total,
                        'max_total': max_total,
                        'min_total_timestamp': min_total_timestamp,
                        'max_total_timestamp': max_total_timestamp,
                        'min_voltage': min_voltage,
                        'max_voltage': max_voltage,
                        'min_voltage_timestamp': min_voltage_timestamp,
                        'max_voltage_timestamp': max_voltage_timestamp,
                        'is_loading': False
                    }
                self.wfile.write(json.dumps(data).encode())
            elif self.path == '/api/live-power-data':
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                # Get current power info directly from router (not from saved data)
                power_info = get_power_info()
                if power_info:
                    self.wfile.write(json.dumps(power_info).encode())
                else:
                    self.wfile.write(json.dumps({'error': 'Could not get power info'}).encode())
            elif self.path == '/api/csv-report':
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                # Generate filename with router name and timestamp
                router_name = cp.get_name()
                timestamp = datetime.now().strftime('%m-%d-%Y_%H-%M-%S')
                filename = f"{router_name}_power_report_{timestamp}.csv"
                
                # Generate CSV content
                csv_content = "Timestamp,Power (W),Voltage (V),Current (A)\n"
                
                # Load full data from file for CSV
                full_power_data = load_data_from_file(POWER_FILE)
                for item in full_power_data:
                    csv_content += f"{item['timestamp']},{item['total']:.3f},{item['voltage']:.3f},{item['current']:.3f}\n"
                
                # Return JSON with filename and CSV content
                response_data = {
                    'filename': filename,
                    'csv_content': csv_content
                }
                
                self.wfile.write(json.dumps(response_data).encode())
            else:
                self.send_response(404)
                self.end_headers()
    
    

    # Try to bind to preferred port first, then try next ports if needed
    max_port = preferred_port + 100
    ports_to_try = [preferred_port] + list(range(preferred_port + 1, max_port + 1))
    
    for port in ports_to_try:
        try:
            cp.log(f"Starting web server on port {port}")
            web_server = socketserver.TCPServer(("", port), PowerTrackerHandler)
            cp.log(f"Web server started on port {port}")
            break
        except OSError as e:
            if "Address already in use" in str(e) or "Address in use" in str(e):
                cp.log(f"Port {port} is in use, trying next port...")
                continue
            else:
                cp.log(f"Error binding to port {port}: {e}")
                continue
    else:
        cp.log("Error: Could not find an available port")
        return
    
    try:
        while not shutdown_requested:
            web_server.handle_request()
    except Exception as e:
        cp.log(f"Error in web server: {e}")
    finally:
        if web_server:
            cp.log("Closing web server...")
            web_server.server_close()


"""Main application entry point"""
cp.log("Starting Power Dashboard Web Application...")

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

cp.wait_for_uptime(min_uptime_seconds=30)

# Check router model and verify support
router_model = cp.get_product_type()
while not router_model:
    router_model = cp.get_product_type()
router_model = router_model.split('-')[0]
cp.log(f"Router model: {router_model}")
if router_model == 'IBR900':
    cp.log("Error: IBR900 model is not supported for power monitoring")
    cp.log("Power Dashboard will not start on IBR900 routers")
    sys.exit(1)
elif router_model:
    cp.log(f"Router model {router_model} is supported")
    # Enable ADC channel for models that use it at startup
    if router_model in ['R920', 'R1900']:
        cp.put('config/system/adc/channel/1/enabled', True)
        adc_channel_enabled = True
else:
    cp.log("Warning: Could not detect router model, continuing with default paths")

# Start power monitoring in background thread
monitor_thread = threading.Thread(target=power_monitor, daemon=True)
monitor_thread.start()
cp.log("Power monitoring thread started")

# Start web server
start_web_server()

