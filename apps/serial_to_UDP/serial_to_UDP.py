
# serial_to_UDP - Reads serial interface data and forwards via UDP
# to one or more destinations. Serial port settings live in the router
# config (config/system/serial); UDP settings live in SDK appdata.
import cp
import serial
import socket
import errno
import time
import json
import os
import http.server
from threading import Thread, Lock

cp.log('Starting serial_to_UDP...')

# Appdata field holding UDP source/destination settings as a single JSON object:
#   {"destinations": [{"ip": "...", "port": ...}, ...],
#    "udp_src_ip": "...", "udp_src_port": ...}
# udp_src_ip/udp_src_port are optional. When absent, the source defaults to
# config/lan/0/ip_address on DEFAULT_SRC_PORT. Defaults are never written to
# appdata so NCM group configs are not overridden.
APP_DATA_KEY = 'serial_to_UDP'
WEB_PORT = 8000

# Source defaults
DEFAULT_SRC_PORT = 5000
DEFAULT_SRC_IP_PATH = 'config/lan/0/ip_address'
FALLBACK_SRC_IP = '0.0.0.0'

# Bound on how many destinations we will hold/forward to
MAX_DESTINATIONS = 32

# Router serial configuration
SERIAL_CONFIG_PATH = 'config/system/serial'

# Parity mapping: router config value -> pyserial constant.
# Values verified against /api/dtd/config/system/serial (0=None, 1=Even,
# 2=Odd, 3=Mark, 4=Space).
PARITY_MAP = {
    0: serial.PARITY_NONE,
    1: serial.PARITY_EVEN,
    2: serial.PARITY_ODD,
    3: serial.PARITY_MARK,
    4: serial.PARITY_SPACE,
}

# Stop bits mapping: router config value -> pyserial constant (0=1, 1=1.5, 2=2)
STOPBITS_MAP = {
    0: serial.STOPBITS_ONE,
    1: serial.STOPBITS_ONE_POINT_FIVE,
    2: serial.STOPBITS_TWO,
}

# Selectable serial settings, taken from the router DTD for
# config/system/serial. Sent to the web UI to build the form.
SERIAL_OPTIONS = {
    'serial_port': [['ttyUSB0', 'Serial / USB'], ['ttyACM0', 'ACM']],
    'baud_rate': [[50, '50'], [75, '75'], [110, '110'], [134, '134'],
                  [150, '150'], [200, '200'], [300, '300'], [600, '600'],
                  [1200, '1200'], [1800, '1800'], [2400, '2400'],
                  [4800, '4800'], [9600, '9600'], [19200, '19200'],
                  [38400, '38400'], [57600, '57600'], [115200, '115200'],
                  [230400, '230400'], [460800, '460800'], [500000, '500000'],
                  [576000, '576000'], [921600, '921600'], [1000000, '1000000'],
                  [1152000, '1152000'], [1500000, '1500000'],
                  [2000000, '2000000'], [2500000, '2500000'],
                  [3000000, '3000000'], [3500000, '3500000'],
                  [4000000, '4000000']],
    'byte_size': [[5, '5 Bits'], [6, '6 Bits'], [7, '7 Bits'], [8, '8 Bits']],
    'byte_parity': [[0, 'None'], [1, 'Even'], [2, 'Odd'], [3, 'Mark'],
                    [4, 'Space']],
    'stop_bits': [[0, '1'], [1, '1.5'], [2, '2']],
}

# Serial fields the UI may write back to the router config
SERIAL_SELECT_FIELDS = ('serial_port', 'baud_rate', 'byte_size', 'byte_parity',
                        'stop_bits')
SERIAL_BOOL_FIELDS = ('enabled',)
SERIAL_FLOW_FIELDS = ('hardware', 'software')

# Reload signalling between the web thread and the forwarding loop
_reload_lock = Lock()
_reload_udp = False
_reload_serial = False

# Runtime counters shown in the web UI
_stats = {
    'started': time.time(),
    'bytes_read': 0,
    'datagrams_sent': 0,
    'send_errors': 0,
    'last_rx': None,
    'serial_open': False,
    'serial_error': None,
}


def request_reload(udp=False, serial_cfg=False):
    """Ask the forwarding loop to re-read UDP and/or serial settings."""
    global _reload_udp, _reload_serial
    with _reload_lock:
        if udp:
            _reload_udp = True
        if serial_cfg:
            _reload_serial = True


def take_reload():
    """Consume pending reload flags. Returns (udp, serial_cfg)."""
    global _reload_udp, _reload_serial
    with _reload_lock:
        udp, serial_cfg = _reload_udp, _reload_serial
        _reload_udp = False
        _reload_serial = False
    return udp, serial_cfg


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def is_valid_ipv4(value):
    """Return True if value is a valid dotted-quad IPv4 address string."""
    parts = str(value).strip().split('.')
    if len(parts) != 4:
        return False
    for part in parts:
        if not part.isdigit() or len(part) > 3:
            return False
        if int(part) > 255:
            return False
    return True


def is_valid_port(value):
    """Return True if value is a port number between 1 and 65535."""
    try:
        port = int(value)
    except (TypeError, ValueError):
        return False
    return 1 <= port <= 65535


# ---------------------------------------------------------------------------
# UDP settings (SDK appdata)
# ---------------------------------------------------------------------------

def get_default_src_ip():
    """Default UDP source IP: the router's primary LAN address."""
    try:
        ip = cp.get(DEFAULT_SRC_IP_PATH)
        if ip and is_valid_ipv4(ip):
            return str(ip)
        cp.log('Could not read %s, using %s' % (DEFAULT_SRC_IP_PATH, FALLBACK_SRC_IP))
    except Exception as e:
        cp.log('Error reading %s: %s' % (DEFAULT_SRC_IP_PATH, e))
    return FALLBACK_SRC_IP


def parse_destinations(raw):
    """Coerce raw destination entries into a list of {'ip', 'port'} dicts.

    Accepts a list of dicts, or "ip:port" strings. Invalid entries are kept
    as-is so validation can report a useful message.
    """
    destinations = []
    if not isinstance(raw, list):
        return destinations
    for entry in raw[:MAX_DESTINATIONS]:
        if isinstance(entry, dict):
            ip = str(entry.get('ip', '')).strip()
            port = entry.get('port')
        elif isinstance(entry, str) and ':' in entry:
            ip, _, port = entry.partition(':')
            ip = ip.strip()
            port = port.strip()
        else:
            continue
        if ip == '' and port in (None, ''):
            continue
        destinations.append({'ip': ip, 'port': port})
    return destinations


def normalize_udp_settings(data):
    """Apply defaults to a raw settings dict read from appdata or the UI."""
    data = data or {}

    destinations = parse_destinations(data.get('destinations'))
    if not destinations and data.get('udp_dest_ip'):
        # Migrate the older single-destination format
        destinations = [{'ip': str(data.get('udp_dest_ip')).strip(),
                         'port': data.get('udp_dest_port')}]

    src_ip = str(data.get('udp_src_ip') or '').strip()
    src_ip_is_default = src_ip == ''
    if src_ip_is_default:
        src_ip = get_default_src_ip()

    src_port = data.get('udp_src_port')
    src_port_is_default = src_port in (None, '')
    if src_port_is_default:
        src_port = DEFAULT_SRC_PORT

    return {
        'destinations': destinations,
        'udp_src_ip': src_ip,
        'udp_src_port': src_port,
        'src_ip_is_default': src_ip_is_default,
        'src_port_is_default': src_port_is_default,
    }


def load_udp_settings():
    """Read UDP settings from appdata and apply defaults. Always returns a dict."""
    raw = None
    try:
        raw = cp.get_appdata(APP_DATA_KEY)
    except Exception as e:
        cp.log('Error reading %s appdata: %s' % (APP_DATA_KEY, e))
    data = {}
    if raw:
        try:
            data = json.loads(raw)
        except (ValueError, TypeError) as e:
            cp.log('Invalid JSON in %s appdata: %s' % (APP_DATA_KEY, e))
            data = {}
    return normalize_udp_settings(data)


def validate_udp_settings(settings):
    """Validate normalized UDP settings. Returns an error string, or None."""
    destinations = settings.get('destinations') or []
    if not destinations:
        return 'At least one UDP destination is required'
    if len(destinations) > MAX_DESTINATIONS:
        return 'No more than %d destinations are allowed' % MAX_DESTINATIONS
    seen = set()
    for index, dest in enumerate(destinations, start=1):
        if not is_valid_ipv4(dest.get('ip')):
            return 'Destination %d: "%s" is not a valid IPv4 address' % (
                index, dest.get('ip'))
        if not is_valid_port(dest.get('port')):
            return 'Destination %d: port must be a number between 1 and 65535' % index
        key = (str(dest.get('ip')).strip(), int(dest.get('port')))
        if key in seen:
            return 'Destination %d: %s:%d is listed more than once' % (
                index, key[0], key[1])
        seen.add(key)
    if not is_valid_ipv4(settings.get('udp_src_ip')):
        return 'Source IP is not a valid IPv4 address'
    if not is_valid_port(settings.get('udp_src_port')):
        return 'Source port must be a number between 1 and 65535'
    return None


def save_udp_settings(settings):
    """Persist UDP settings to appdata as JSON.

    Source IP/port are only written when the user supplied them, so defaults
    never overwrite values pushed from an NCM group config.
    """
    payload = {
        'destinations': [
            {'ip': str(d['ip']).strip(), 'port': int(d['port'])}
            for d in settings['destinations']
        ]
    }
    if not settings.get('src_ip_is_default'):
        payload['udp_src_ip'] = str(settings['udp_src_ip']).strip()
    if not settings.get('src_port_is_default'):
        payload['udp_src_port'] = int(settings['udp_src_port'])
    cp.put_appdata(APP_DATA_KEY, json.dumps(payload))


def describe_destinations(settings):
    """Human readable "ip:port, ip:port" list for logging."""
    return ', '.join('%s:%s' % (d['ip'], d['port'])
                     for d in settings.get('destinations') or []) or 'none'


# ---------------------------------------------------------------------------
# Serial settings (router config)
# ---------------------------------------------------------------------------

def get_serial_config():
    """Read serial interface configuration from the router config tree."""
    try:
        config = cp.get(SERIAL_CONFIG_PATH)
        if not config:
            cp.log('ERROR: Could not read serial config from router')
            return None
        cp.log('Serial config: port=%s baud=%s bits=%s parity=%s stop=%s '
               'flow_hw=%s flow_sw=%s' % (
                   config.get('serial_port'),
                   config.get('baud_rate'),
                   config.get('byte_size'),
                   config.get('byte_parity'),
                   config.get('stop_bits'),
                   (config.get('flow_control') or {}).get('hardware'),
                   (config.get('flow_control') or {}).get('software'),
               ))
        return config
    except Exception as e:
        cp.log('ERROR reading serial config: %s' % e)
        return None


def serial_config_for_ui(config):
    """Reduce the router serial config to the fields the web UI edits."""
    config = config or {}
    flow = config.get('flow_control') or {}
    return {
        'enabled': bool(config.get('enabled', False)),
        'serial_port': config.get('serial_port', 'ttyUSB0'),
        'baud_rate': config.get('baud_rate', 9600),
        'byte_size': config.get('byte_size', 8),
        'byte_parity': config.get('byte_parity', 0),
        'stop_bits': config.get('stop_bits', 0),
        'flow_control': {
            'hardware': bool(flow.get('hardware', False)),
            'software': bool(flow.get('software', False)),
        },
        'status': config.get('status', ''),
    }


def build_serial_payload(data):
    """Validate a serial settings payload from the UI.

    Returns (payload, error). payload is a dict suitable for a single PUT to
    SERIAL_CONFIG_PATH; the router merges it into the existing struct.
    """
    if not isinstance(data, dict):
        return None, 'Invalid request body'

    payload = {}

    for field in SERIAL_SELECT_FIELDS:
        if field not in data:
            continue
        value = data[field]
        allowed = SERIAL_OPTIONS[field]
        if isinstance(allowed[0][0], int):
            try:
                value = int(value)
            except (TypeError, ValueError):
                return None, '%s must be a number' % field
        else:
            value = str(value).strip()
        if value not in [option[0] for option in allowed]:
            return None, '%s value "%s" is not supported' % (field, value)
        payload[field] = value

    for field in SERIAL_BOOL_FIELDS:
        if field in data:
            payload[field] = bool(data[field])

    flow = data.get('flow_control')
    if isinstance(flow, dict):
        flow_payload = {}
        for field in SERIAL_FLOW_FIELDS:
            if field in flow:
                flow_payload[field] = bool(flow[field])
        # The router rejects both flow control modes at once, so catch it
        # here and report a readable message instead of a raw validation dump.
        if flow_payload.get('hardware') and flow_payload.get('software'):
            return None, ('Hardware and software flow control cannot be '
                          'enabled at the same time')
        if flow_payload:
            payload['flow_control'] = flow_payload

    if not payload:
        return None, 'No serial settings provided'
    return payload, None


def save_serial_config(payload):
    """Write serial settings to the router config in one PUT.

    A single struct PUT is used rather than per-leaf writes so the router
    validates the whole change at once. A rejected change leaves the existing
    config untouched instead of half-applied.

    Returns an error message string, or None on success.
    """
    result = cp.put(SERIAL_CONFIG_PATH, payload)
    if not result:
        return 'No response from router when writing serial config'
    if result.get('status') not in ('ok', True) and result.get('success') is not True:
        reason = result.get('data')
        if isinstance(reason, dict) and reason.get('reason'):
            return 'Router rejected the change: %s' % reason['reason']
        return 'Router rejected the change: %s' % reason
    return None


# ---------------------------------------------------------------------------
# Web UI
# ---------------------------------------------------------------------------

class SettingsHandler(http.server.SimpleHTTPRequestHandler):
    """Serves the web UI plus a JSON API for UDP and serial settings."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs)

    def do_GET(self):
        try:
            if self.path == '/api/settings':
                self._get_settings()
            elif self.path == '/api/serial':
                self._get_serial()
            elif self.path == '/api/status':
                self._get_status()
            else:
                super().do_GET()
        except Exception as e:
            cp.log('Error handling GET %s: %s' % (self.path, e))
            try:
                self._send_json(500, {'error': 'Internal error'})
            except Exception:
                pass

    def do_POST(self):
        if self.path == '/api/settings':
            self._post_settings()
        elif self.path == '/api/serial':
            self._post_serial()
        else:
            self.send_error(404)

    # -- GET handlers ------------------------------------------------------

    def _get_settings(self):
        settings = load_udp_settings()
        self._send_json(200, {
            'destinations': settings['destinations'],
            'udp_src_ip': '' if settings['src_ip_is_default'] else settings['udp_src_ip'],
            'udp_src_port': '' if settings['src_port_is_default'] else settings['udp_src_port'],
            'default_src_ip': get_default_src_ip(),
            'default_src_port': DEFAULT_SRC_PORT,
            'max_destinations': MAX_DESTINATIONS,
        })

    def _get_serial(self):
        config = get_serial_config()
        if config is None:
            self._send_json(502, {'error': 'Could not read serial config from router'})
            return
        self._send_json(200, {
            'serial': serial_config_for_ui(config),
            'options': SERIAL_OPTIONS,
        })

    def _get_status(self):
        last_rx = _stats['last_rx']
        self._send_json(200, {
            'serial_open': _stats['serial_open'],
            'serial_error': _stats['serial_error'],
            'bytes_read': _stats['bytes_read'],
            'datagrams_sent': _stats['datagrams_sent'],
            'send_errors': _stats['send_errors'],
            'last_rx_ago': None if last_rx is None else int(time.time() - last_rx),
            'uptime': int(time.time() - _stats['started']),
        })

    # -- POST handlers -----------------------------------------------------

    def _read_json_body(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        return json.loads(body.decode('utf-8'))

    def _post_settings(self):
        try:
            data = self._read_json_body()
        except Exception as e:
            cp.log('Error parsing settings POST body: %s' % e)
            self._send_json(400, {'success': False, 'error': 'Invalid request body'})
            return

        settings = normalize_udp_settings(data)
        error = validate_udp_settings(settings)
        if error:
            self._send_json(400, {'success': False, 'error': error})
            return

        try:
            save_udp_settings(settings)
        except Exception as e:
            cp.log('Error saving UDP settings: %s' % e)
            self._send_json(500, {'success': False, 'error': 'Failed to save settings'})
            return

        cp.log('Saved UDP settings: source %s:%s -> %s' % (
            settings['udp_src_ip'], settings['udp_src_port'],
            describe_destinations(settings)))
        request_reload(udp=True)
        self._send_json(200, {'success': True})

    def _post_serial(self):
        try:
            data = self._read_json_body()
        except Exception as e:
            cp.log('Error parsing serial POST body: %s' % e)
            self._send_json(400, {'success': False, 'error': 'Invalid request body'})
            return

        payload, error = build_serial_payload(data)
        if error:
            self._send_json(400, {'success': False, 'error': error})
            return

        try:
            error = save_serial_config(payload)
        except Exception as e:
            cp.log('Error saving serial config: %s' % e)
            self._send_json(500, {'success': False, 'error': 'Failed to save serial settings'})
            return

        if error:
            cp.log('Serial config write failed: %s' % error)
            self._send_json(400, {'success': False, 'error': error})
            return

        cp.log('Saved serial settings to router config: %s' % payload)
        request_reload(serial_cfg=True)
        self._send_json(200, {'success': True})

    # -- helpers -----------------------------------------------------------

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        cp.log(format % args)


def start_web_server():
    """Start the settings web UI. Runs forever; call in a daemon thread."""
    try:
        server = http.server.HTTPServer(('0.0.0.0', WEB_PORT), SettingsHandler)
        server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        cp.log('Web UI started on port %d' % WEB_PORT)
        server.serve_forever()
    except Exception as e:
        cp.log('ERROR: Web server failed to start: %s' % e)


# ---------------------------------------------------------------------------
# Serial / UDP plumbing
# ---------------------------------------------------------------------------

def open_serial(config):
    """Open the serial port using router configuration."""
    port = '/dev/%s' % config.get('serial_port', 'ttyUSB0')
    baud = int(config.get('baud_rate', 9600))
    bytesize = int(config.get('byte_size', 8))
    parity = PARITY_MAP.get(config.get('byte_parity', 0), serial.PARITY_NONE)
    stopbits = STOPBITS_MAP.get(config.get('stop_bits', 0), serial.STOPBITS_ONE)

    flow = config.get('flow_control') or {}
    xonxoff = bool(flow.get('software', False))
    rtscts = bool(flow.get('hardware', False))

    ser = serial.Serial(
        port=port,
        baudrate=baud,
        bytesize=bytesize,
        parity=parity,
        stopbits=stopbits,
        xonxoff=xonxoff,
        rtscts=rtscts,
        timeout=1
    )
    cp.log('Opened serial port: %s @ %d baud (%s%s%s)' % (
        port, baud, bytesize, parity, stopbits))
    return ser


def open_udp_socket(src_ip, src_port):
    """Create and bind the UDP socket to the source address."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((src_ip, int(src_port)))
    cp.log('UDP socket bound to %s:%s' % (src_ip, src_port))
    return sock


def forward(sock, data, destinations):
    """Send one payload to every destination. Returns True if the socket died."""
    for dest in destinations:
        try:
            sock.sendto(data, (dest['ip'], int(dest['port'])))
            _stats['datagrams_sent'] += 1
        except socket.error as e:
            _stats['send_errors'] += 1
            cp.log('UDP send to %s:%s failed: %s' % (dest['ip'], dest['port'], e))
            # Errors like ENETUNREACH are per-destination; a bad or
            # unbound socket needs a rebind.
            if getattr(e, 'errno', None) in (errno.EBADF, errno.ENOTSOCK):
                return True
    return False


def close_quietly(resource):
    """Close a socket or serial port, ignoring errors."""
    if resource is None:
        return
    try:
        resource.close()
    except Exception:
        pass


def main():
    """Main loop: read serial data and forward to all UDP destinations."""
    Thread(target=start_web_server, daemon=True).start()

    settings = load_udp_settings()
    settings_error = validate_udp_settings(settings)
    if settings_error:
        cp.log('UDP settings incomplete (%s). Configure destinations in the '
               'web UI on port %d.' % (settings_error, WEB_PORT))
    else:
        cp.log('Forwarding serial data from %s:%s to %s' % (
            settings['udp_src_ip'], settings['udp_src_port'],
            describe_destinations(settings)))

    serial_config = get_serial_config()
    ser = None
    sock = None
    last_no_dest_log = 0.0
    last_serial_retry = 0.0

    try:
        while True:
            try:
                reload_udp, reload_serial = take_reload()

                if reload_udp:
                    new_settings = load_udp_settings()
                    if (new_settings['udp_src_ip'], str(new_settings['udp_src_port'])) != \
                            (settings['udp_src_ip'], str(settings['udp_src_port'])):
                        close_quietly(sock)
                        sock = None
                    settings = new_settings
                    settings_error = validate_udp_settings(settings)
                    cp.log('UDP settings reloaded: source %s:%s -> %s' % (
                        settings['udp_src_ip'], settings['udp_src_port'],
                        describe_destinations(settings)))

                if reload_serial:
                    close_quietly(ser)
                    ser = None
                    _stats['serial_open'] = False
                    serial_config = get_serial_config()
                    last_serial_retry = 0.0

                if serial_config is None:
                    serial_config = get_serial_config()
                    if serial_config is None:
                        time.sleep(10)
                        continue

                if ser is None:
                    if time.time() - last_serial_retry < 5:
                        time.sleep(1)
                        continue
                    last_serial_retry = time.time()
                    try:
                        ser = open_serial(serial_config)
                        _stats['serial_open'] = True
                        _stats['serial_error'] = None
                    except Exception as e:
                        _stats['serial_open'] = False
                        _stats['serial_error'] = str(e)
                        cp.log('Could not open serial port: %s. Retrying...' % e)
                        continue

                if sock is None and not settings_error:
                    try:
                        sock = open_udp_socket(settings['udp_src_ip'],
                                               settings['udp_src_port'])
                    except Exception as e:
                        cp.log('Could not bind UDP socket to %s:%s: %s' % (
                            settings['udp_src_ip'], settings['udp_src_port'], e))
                        time.sleep(5)
                        continue

                # Always drain the serial port so the buffer does not grow
                # while destinations are unconfigured.
                data = ser.read(1024)
                if not data:
                    continue
                _stats['bytes_read'] += len(data)
                _stats['last_rx'] = time.time()

                if settings_error or sock is None:
                    now = time.time()
                    if now - last_no_dest_log > 60:
                        last_no_dest_log = now
                        cp.log('Discarding serial data: %s' % settings_error)
                    continue

                if forward(sock, data, settings['destinations']):
                    close_quietly(sock)
                    sock = None

            except serial.SerialException as e:
                cp.log('Serial error: %s. Reconnecting...' % e)
                close_quietly(ser)
                ser = None
                _stats['serial_open'] = False
                _stats['serial_error'] = str(e)
                time.sleep(5)
            except socket.error as e:
                cp.log('UDP socket error: %s. Recreating socket...' % e)
                close_quietly(sock)
                sock = None
                time.sleep(2)
            except Exception as e:
                cp.log('Unexpected error in forwarding loop: %s' % e)
                time.sleep(5)

    except Exception as e:
        cp.log('Fatal error: %s' % e)
    finally:
        close_quietly(ser)
        close_quietly(sock)
        cp.log('serial_to_UDP stopped.')


main()
