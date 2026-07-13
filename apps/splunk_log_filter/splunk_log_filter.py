# splunk_log_filter.py
# This app tails /var/log/messages and sends filtered lines to Splunk.

import cp
import time
import requests
from subprocess import Popen, PIPE

def get_router_info():
    """Fetch router identifiers for Splunk event metadata."""
    info = {}
    try:
        system = cp.get('status/system')
        if system:
            info['hostname'] = system.get('system_id', '')
            info['serial_number'] = system.get('serial_number', '')
            info['mac'] = system.get('mac', '')
        fw = cp.get('status/fw_info')
        if fw:
            info['firmware_version'] = fw.get('major_version', '')
    except Exception as e:
        cp.log(f"Error getting router info: {e}")
    return info


def send_data_to_splunk(data, router_info):
    headers = {
        "Authorization": f"Splunk {SPLUNK_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "event": data,
        "host": router_info.get('hostname', ''),
        "fields": {
            "serial_number": router_info.get('serial_number', ''),
            "mac": router_info.get('mac', ''),
            "firmware_version": router_info.get('firmware_version', '')
        }
    }

    response = requests.post(SPLUNK_URL, json=payload, headers=headers, verify=False)
    if response.status_code != 200:
        cp.log(f'Failed to send data to Splunk: {response.text}')
    return response.status_code == 200

def process_logs(splunk_filters, router_info):
    """Tails /var/log/messages and sends filtered lines to Splunk.
    
    If splunk_filters is empty, all log lines are sent.
    """
    if splunk_filters:
        cp.log(f"Starting log processing, filtering for: {splunk_filters}")
    else:
        cp.log("Starting log processing, no filters configured - sending all logs")
    cmd = ['/usr/bin/tail', '/var/log/messages', '-n1', '-F']
    process = Popen(cmd, stdout=PIPE, stderr=PIPE)

    for line in iter(process.stdout.readline, b''):
        line_str = line.decode('utf-8', errors='ignore').strip()
        if not splunk_filters or any(f.lower() in line_str.lower() for f in splunk_filters):
            send_data_to_splunk(line_str, router_info)

    # Log any errors from the tail process
    stderr_output = process.stderr.read().decode('utf-8', errors='ignore')
    if stderr_output:
        cp.log(f"tail process error: {stderr_output}")

# App starts here
cp.log('Starting...')

while True:
    try:
        # Get Splunk configuration from app data
        SPLUNK_URL = cp.get_appdata('splunk_url')
        SPLUNK_TOKEN = cp.get_appdata('splunk_token')
        
        app_data = cp.get('config/system/sdk/appdata')
        splunk_filters = []
        if app_data:
            splunk_filters = [
                item.get('value').strip() for item in app_data
                if item.get('name', '').startswith('splunk_filter') and item.get('value')
            ]

        if not all([SPLUNK_URL, SPLUNK_TOKEN]):
            cp.log('Splunk URL or Token not configured. Sleeping for 60 seconds.')
            time.sleep(60)
            continue

        router_info = get_router_info()
        process_logs(splunk_filters, router_info)

    except Exception as e:
        cp.logger.exception(e)

