# splunk_conntrack.py
# This app tails the conntrack table and sends new connections to Splunk.

import cp
import time
import requests

def send_data_to_splunk(data):
    headers = {
        "Authorization": f"Splunk {SPLUNK_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Create a simple string message from the connection data
    try:
        # Extract key connection information for a readable message
        conn_id = data.get('id', 'unknown')
        proto = data.get('proto', 'unknown')
        orig_src = data.get('orig_src', 'unknown')
        orig_dst = data.get('orig_dst', 'unknown')
        orig_src_port = data.get('orig_src_port', 'unknown')
        orig_dst_port = data.get('orig_dst_port', 'unknown')
        status = data.get('status', 'unknown')
        
        event_message = f"Connection {conn_id}: {orig_src}:{orig_src_port} -> {orig_dst}:{orig_dst_port} (proto={proto}, status={status})"
    except Exception as e:
        cp.log(f'Failed to create event message: {e}')
        event_message = str(data)
    
    # Use the simplest possible payload structure
    payload = {
        "event": event_message
    }
    
    response = requests.post(SPLUNK_URL, json=payload, headers=headers, verify=False)
    if response.status_code != 200:
        cp.log(f'Failed to send data to Splunk: {response.text}')
    return response.status_code == 200


# App starts here
cp.log('Starting...')

# Keep track of seen connection IDs
seen_connections = set()

while True:
    try:
        # Get Splunk URL and token from app data
        SPLUNK_URL = cp.get_appdata('splunk_url')
        SPLUNK_TOKEN = cp.get_appdata('splunk_token')
        if not SPLUNK_URL or not SPLUNK_TOKEN:
            cp.log('No entry for splunk_url or splunk_token in app data, sleeping for 60 seconds')
            time.sleep(60)
            continue

        # Get conntrack data
        conntrack = cp.get('status/firewall/conntrack')
        
        # Get current connection IDs
        current_conn_ids = {conn.get('id') for conn in conntrack if conn.get('id')}
        
        # Remove connections that are no longer in conntrack
        removed_connections = seen_connections - current_conn_ids
        if removed_connections:
            cp.log(f'Removing {len(removed_connections)} expired connections from seen_connections')
            seen_connections -= removed_connections
        
        # Process each connection
        for conn in conntrack:
            conn_id = conn.get('id')
            
            # If this is a new connection, send it to Splunk
            if conn_id and conn_id not in seen_connections:
                seen_connections.add(conn_id)
                send_data_to_splunk(conn)
        
    except Exception as e:
        cp.logger.exception(e)
    
    time.sleep(5)