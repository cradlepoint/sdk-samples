"""
PRTG Agent - Collects system and modem data, pushes to PRTG HTTP Push Data Advanced sensor.
Includes a web UI for configuration management.
"""

import cp
import json
import os
import re
import socket
import threading
import time
import http.server

# --- Constants ---
APP_NAME = 'prtg_agent'
WEB_PORT = 8000
DEFAULT_INTERVAL = 60
DEFAULT_PRTG_PORT_HTTP = 5050
DEFAULT_PRTG_PORT_HTTPS = 5051
DEFAULT_PROTOCOL = 'http'

# Default paths to collect data from (supports wildcards)
DEFAULT_PATHS = [
    'status/system/cpu',
    'status/system/load_avg',
    'status/system/memory/memtotal',
    'status/system/memory/memfree',
    'status/system/memory/memavailable',
    'status/system/uptime',
    'status/system/temperature',
    'status/wan/devices/*/diagnostics/CARRID',
    'status/wan/devices/*/diagnostics/DBM',
    'status/wan/devices/*/diagnostics/RSRP',
    'status/wan/devices/*/diagnostics/RSRQ',
    'status/wan/devices/*/diagnostics/SINR',
    'status/wan/devices/*/diagnostics/RSRP_5G',
    'status/wan/devices/*/diagnostics/RSRQ_5G',
    'status/wan/devices/*/diagnostics/SINR_5G',
    'status/wan/devices/*/diagnostics/SS',
    'status/wan/devices/*/diagnostics/RFBAND',
    'status/wan/devices/*/diagnostics/SRVC_TYPE',
    'status/wan/devices/*/diagnostics/MODEMTEMP',
    'status/wan/devices/*/status/connection_state',
    'status/wan/devices/*/status/signal_strength',
]


def get_config():
    """Load configuration from appdata. Returns dict with defaults for missing fields."""
    config = {
        'server': '',
        'port': '',
        'token': '',
        'interval': str(DEFAULT_INTERVAL),
        'protocol': DEFAULT_PROTOCOL,
        'paths': json.dumps(DEFAULT_PATHS),
    }
    for key in config:
        value = cp.get_appdata(key)
        if value:
            config[key] = value
    return config


def save_config(config):
    """Save configuration to appdata."""
    for key, value in config.items():
        cp.put_appdata(key, value)


def resolve_wildcard_path(path):
    """
    Resolve a path with wildcards into actual path/value pairs.
    Supports * as a wildcard for one path segment.
    Returns list of (resolved_path, value) tuples.
    """
    parts = path.split('/')
    wildcard_idx = None
    for i, part in enumerate(parts):
        if part == '*':
            wildcard_idx = i
            break

    if wildcard_idx is None:
        # No wildcard, just get the value directly
        value = cp.get(path)
        if value is not None:
            return [(path, value)]
        return []

    # Get the parent path up to the wildcard
    parent_path = '/'.join(parts[:wildcard_idx])
    parent_data = cp.get(parent_path)
    if not parent_data or not isinstance(parent_data, dict):
        return []

    results = []
    remaining_parts = parts[wildcard_idx + 1:]
    remaining_path = '/'.join(remaining_parts)

    for key in parent_data:
        if remaining_path:
            full_path = '{}/{}/{}'.format(parent_path, key, remaining_path)
            # Recurse in case there are more wildcards
            results.extend(resolve_wildcard_path(full_path))
        else:
            full_path = '{}/{}'.format(parent_path, key)
            value = parent_data[key]
            if value is not None:
                results.append((full_path, value))

    return results


def collect_data(paths):
    """
    Collect data from all configured paths.
    Returns list of (channel_name, value, is_float) tuples.
    """
    channels = []
    # Cache device friendly names to avoid repeated lookups
    device_names = _get_device_names()

    for path in paths:
        try:
            resolved = resolve_wildcard_path(path)
            for resolved_path, value in resolved:
                # Build a readable channel name from the path
                channel_name = make_channel_name(resolved_path, device_names)
                # Skip non-numeric values for PRTG channels (store as text message)
                numeric_value, is_float = parse_numeric(value)
                if numeric_value is not None:
                    channels.append((channel_name, numeric_value, is_float))
        except Exception as e:
            cp.log('Error collecting {}: {}'.format(path, e))
    return channels


def _get_device_names():
    """
    Build a map of device_id -> friendly name using info/product or info fields.
    e.g. 'ethernet-wan' -> 'Multi Gigabit Ethernet Switch'
         'mdm-abcd1234' -> 'int1 sim1' or product name
    """
    names = {}
    try:
        devices = cp.get('status/wan/devices') or {}
        for dev_id in devices:
            info = cp.get('status/wan/devices/{}/info'.format(dev_id))
            if not info:
                continue
            # Try product field first (user-confirmed it exists)
            product = info.get('product', '')
            if product:
                names[dev_id] = product
            elif info.get('type') == 'mdm':
                # For modems, use port + sim
                port = info.get('port', '')
                sim = info.get('sim', '')
                parts = [p for p in [port, sim] if p]
                names[dev_id] = ' '.join(parts) if parts else dev_id
            else:
                # Ethernet: use port
                port = info.get('port', '')
                names[dev_id] = port if port else dev_id
    except Exception as e:
        cp.log('Error getting device names: {}'.format(e))
    return names


def make_channel_name(path, device_names=None):
    """
    Convert a full API path to a concise PRTG channel name.
    e.g. status/wan/devices/mdm-12345/diagnostics/RSRP_5G -> 'int1 sim1 RSRP_5G'
    """
    if device_names is None:
        device_names = {}

    parts = path.split('/')
    # For WAN device paths, include friendly device name and the leaf field
    if 'wan/devices' in path and len(parts) >= 5:
        device_id = parts[3]  # e.g. mdm-12345, ethernet-wan
        leaf = parts[-1]
        friendly = device_names.get(device_id, device_id)
        return '{} {}'.format(friendly, leaf)
    # For system paths
    if path.startswith('status/system/'):
        remainder = path[len('status/system/'):]
        return remainder.replace('/', ' ')
    # Fallback: last two segments
    return '/'.join(parts[-2:]) if len(parts) >= 2 else parts[-1]


def parse_numeric(value):
    """
    Try to parse a value as numeric. Returns (number, is_float) or (None, False).
    Handles string numbers from diagnostics (e.g. "-85", "23.4").
    """
    if isinstance(value, (int, float)):
        is_float = isinstance(value, float) or '.' in str(value)
        return value, is_float
    if isinstance(value, str):
        # Strip whitespace and try numeric parse
        value = value.strip()
        if not value:
            return None, False
        try:
            if '.' in value:
                return float(value), True
            return int(value), False
        except (ValueError, TypeError):
            return None, False
    if isinstance(value, dict):
        # For objects like cpu {user, nice, system}, flatten
        return None, False
    return None, False


def get_unit_for_channel(channel_name):
    """Determine PRTG unit based on channel name."""
    name_lower = channel_name.lower()
    if 'cpu' in name_lower or 'load' in name_lower:
        return 'CPU'
    if 'memory' in name_lower or 'mem' in name_lower:
        return 'BytesFile'
    if 'temperature' in name_lower or 'temp' in name_lower:
        return 'Temperature'
    if 'uptime' in name_lower:
        return 'TimeSeconds'
    if 'signal' in name_lower or 'ss' == name_lower.split()[-1]:
        return 'Percent'
    return 'Custom'


def get_custom_unit(channel_name):
    """Determine custom unit string for channel."""
    name_lower = channel_name.lower()
    if 'rsrp' in name_lower or 'dbm' in name_lower:
        return 'dBm'
    if 'rsrq' in name_lower:
        return 'dB'
    if 'sinr' in name_lower:
        return 'dB'
    return ''


def build_prtg_xml(channels, message=''):
    """
    Build PRTG-compatible XML from collected channel data.
    channels: list of (channel_name, value, is_float) tuples
    Always includes router hostname and serial number in the text message.
    """
    # Get router identity for the text field
    hostname = cp.get_name() or 'unknown'
    serial = cp.get_serial_number() or 'unknown'

    xml_parts = ['<?xml version="1.0" encoding="UTF-8" ?>']
    xml_parts.append('<prtg>')

    for channel_name, value, is_float in channels:
        xml_parts.append('  <result>')
        xml_parts.append('    <channel>{}</channel>'.format(escape_xml(channel_name)))
        xml_parts.append('    <value>{}</value>'.format(value))
        if is_float:
            xml_parts.append('    <float>1</float>')
        unit = get_unit_for_channel(channel_name)
        xml_parts.append('    <unit>{}</unit>'.format(unit))
        if unit == 'Custom':
            custom_unit = get_custom_unit(channel_name)
            if custom_unit:
                xml_parts.append('    <customunit>{}</customunit>'.format(
                    escape_xml(custom_unit)))
        xml_parts.append('  </result>')

    # Always include hostname and serial in the text message
    text_parts = ['hostname={}'.format(hostname), 'serial={}'.format(serial)]
    if message:
        text_parts.append(message)
    xml_parts.append('  <text>{}</text>'.format(escape_xml(' | '.join(text_parts))))

    xml_parts.append('</prtg>')
    return '\n'.join(xml_parts)


def escape_xml(text):
    """Escape special XML characters."""
    text = str(text)
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&apos;')
    return text


def push_to_prtg(xml_data, config):
    """Send XML data to PRTG HTTP Push Data Advanced sensor via POST."""
    server = config.get('server', '')
    port = config.get('port', '')
    token = config.get('token', '')
    protocol = config.get('protocol', DEFAULT_PROTOCOL)

    if not server or not token:
        cp.log('PRTG push skipped: server or token not configured')
        return False

    # Use protocol-appropriate default port if not specified
    if not port:
        port = str(DEFAULT_PRTG_PORT_HTTPS if protocol == 'https' else DEFAULT_PRTG_PORT_HTTP)

    try:
        port_int = int(port)
    except (ValueError, TypeError):
        port_int = DEFAULT_PRTG_PORT_HTTPS if protocol == 'https' else DEFAULT_PRTG_PORT_HTTP

    url = '{}://{}:{}/{}'.format(protocol, server, port_int, token)
    cp.log('Pushing data to PRTG: {}'.format(url))

    try:
        import requests
        headers = {'Content-Type': 'application/xml'}
        resp = requests.post(url, data=xml_data, headers=headers, timeout=30,
                             verify=False)
        cp.log('PRTG response: {} {}'.format(resp.status_code, resp.text[:200]))
        return resp.status_code == 200
    except Exception as e:
        cp.log('Error pushing to PRTG: {}'.format(e))
        return False


# --- Web Server ---

class PRTGAgentHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for the PRTG Agent web UI and API."""

    def log_message(self, format, *args):
        """Suppress default logging, use cp.log instead."""
        pass

    def _send_response(self, code, content_type, body):
        """Helper to send an HTTP response."""
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.end_headers()
        if isinstance(body, str):
            self.wfile.write(body.encode('utf-8'))
        else:
            self.wfile.write(body)

    def _send_json(self, data, code=200):
        """Send a JSON response."""
        self._send_response(code, 'application/json', json.dumps(data))

    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/' or self.path == '/index.html':
            self._serve_file('index.html', 'text/html')
        elif self.path.startswith('/static/'):
            self._serve_static(self.path[1:])
        elif self.path == '/api/config':
            self._handle_get_config()
        elif self.path == '/api/status':
            self._handle_get_status()
        elif self.path == '/api/preview':
            self._handle_preview()
        else:
            self._send_response(404, 'text/plain', 'Not Found')

    def do_POST(self):
        """Handle POST requests."""
        if self.path == '/api/config':
            self._handle_save_config()
        elif self.path == '/api/push_now':
            self._handle_push_now()
        else:
            self._send_response(404, 'text/plain', 'Not Found')

    def _serve_file(self, filename, content_type):
        """Serve a file from the app directory."""
        app_dir = os.path.dirname(os.path.abspath(__file__))
        filepath = os.path.join(app_dir, filename)
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            self._send_response(200, content_type, content)
        except FileNotFoundError:
            self._send_response(404, 'text/plain', 'File not found')

    def _serve_static(self, path):
        """Serve static assets with proper MIME types."""
        app_dir = os.path.dirname(os.path.abspath(__file__))
        filepath = os.path.join(app_dir, path)

        # Security: prevent path traversal
        filepath = os.path.realpath(filepath)
        if not filepath.startswith(os.path.realpath(app_dir)):
            self._send_response(403, 'text/plain', 'Forbidden')
            return

        mime_types = {
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.html': 'text/html',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon',
            '.woff': 'font/woff',
            '.woff2': 'font/woff2',
            '.ttf': 'font/ttf',
            '.eot': 'application/vnd.ms-fontobject',
        }
        ext = os.path.splitext(filepath)[1].lower()
        content_type = mime_types.get(ext, 'application/octet-stream')

        try:
            mode = 'r' if ext in ('.css', '.js', '.html', '.svg') else 'rb'
            with open(filepath, mode) as f:
                content = f.read()
            if isinstance(content, str):
                content = content.encode('utf-8')
            self._send_response(200, content_type, content)
        except FileNotFoundError:
            self._send_response(404, 'text/plain', 'File not found')

    def _handle_get_config(self):
        """Return current configuration as JSON."""
        config = get_config()
        # Parse paths from JSON string to list for the UI
        try:
            config['paths'] = json.loads(config['paths'])
        except (json.JSONDecodeError, TypeError):
            config['paths'] = DEFAULT_PATHS
        self._send_json(config)

    def _handle_get_status(self):
        """Return current agent status."""
        global last_push_time, last_push_success, push_count
        status = {
            'last_push_time': last_push_time,
            'last_push_success': last_push_success,
            'push_count': push_count,
            'running': agent_running,
        }
        self._send_json(status)

    def _handle_preview(self):
        """Preview the data that would be collected and sent."""
        config = get_config()
        try:
            paths = json.loads(config['paths'])
        except (json.JSONDecodeError, TypeError):
            paths = DEFAULT_PATHS

        channels = collect_data(paths)
        xml = build_prtg_xml(channels, 'Preview data collection')
        preview = {
            'channels': [{'name': c[0], 'value': c[1], 'float': c[2]} for c in channels],
            'xml': xml,
            'channel_count': len(channels),
        }
        self._send_json(preview)

    def _handle_save_config(self):
        """Save configuration from POST body."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)

            # Validate required fields
            config = {
                'server': data.get('server', ''),
                'port': str(data.get('port', '')),
                'token': data.get('token', ''),
                'interval': str(data.get('interval', DEFAULT_INTERVAL)),
                'protocol': data.get('protocol', DEFAULT_PROTOCOL),
            }

            # Handle paths - store as JSON string
            paths = data.get('paths', DEFAULT_PATHS)
            if isinstance(paths, list):
                config['paths'] = json.dumps(paths)
            else:
                config['paths'] = json.dumps(DEFAULT_PATHS)

            save_config(config)
            cp.log('Configuration saved')
            self._send_json({'success': True, 'message': 'Configuration saved'})
        except Exception as e:
            cp.log('Error saving config: {}'.format(e))
            self._send_json({'success': False, 'message': str(e)}, code=400)

    def _handle_push_now(self):
        """Trigger an immediate data push to PRTG."""
        try:
            config = get_config()
            try:
                paths = json.loads(config['paths'])
            except (json.JSONDecodeError, TypeError):
                paths = DEFAULT_PATHS

            channels = collect_data(paths)
            if not channels:
                self._send_json({'success': False, 'message': 'No data collected'})
                return

            xml = build_prtg_xml(channels, 'Manual push from web UI')
            success = push_to_prtg(xml, config)
            self._send_json({
                'success': success,
                'message': 'Push successful' if success else 'Push failed',
                'channels': len(channels),
            })
        except Exception as e:
            cp.log('Error in push_now: {}'.format(e))
            self._send_json({'success': False, 'message': str(e)}, code=500)


# --- Agent State ---
last_push_time = 0
last_push_success = False
push_count = 0
agent_running = True


def data_collection_loop():
    """Main loop that collects and pushes data at the configured interval."""
    global last_push_time, last_push_success, push_count, agent_running

    cp.log('Data collection loop started')

    while agent_running:
        try:
            config = get_config()
            try:
                interval = int(config.get('interval', DEFAULT_INTERVAL))
            except (ValueError, TypeError):
                interval = DEFAULT_INTERVAL

            # Only push if server and token are configured
            server = config.get('server', '')
            token = config.get('token', '')

            if server and token:
                try:
                    paths = json.loads(config.get('paths', '[]'))
                except (json.JSONDecodeError, TypeError):
                    paths = DEFAULT_PATHS

                channels = collect_data(paths)
                if channels:
                    xml = build_prtg_xml(channels, '{} channels'.format(len(channels)))
                    success = push_to_prtg(xml, config)
                    last_push_time = time.time()
                    last_push_success = success
                    push_count += 1
                    cp.log('Push #{}: {} channels, success={}'.format(
                        push_count, len(channels), success))
                else:
                    cp.log('No data collected from configured paths')
            else:
                cp.log('PRTG server/token not configured, skipping push')

            # Sleep in small increments to allow quick shutdown
            for _ in range(interval):
                if not agent_running:
                    break
                time.sleep(1)

        except Exception as e:
            cp.log('Error in collection loop: {}'.format(e))
            time.sleep(10)

    cp.log('Data collection loop stopped')


def start_web_server():
    """Start the web server in a daemon thread."""
    app_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(app_dir)

    server = http.server.HTTPServer(('', WEB_PORT), PRTGAgentHandler)
    server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    cp.log('Web server started on port {}'.format(WEB_PORT))
    server.serve_forever()


def main():
    """Main entry point."""
    global agent_running

    cp.log('Starting PRTG Agent')

    # Start web server in daemon thread
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()

    # Run data collection in the main thread
    try:
        data_collection_loop()
    except Exception as e:
        cp.log('Fatal error: {}'.format(e))
    finally:
        agent_running = False
        cp.log('PRTG Agent stopped')


if __name__ == '__main__':
    main()
