#!/usr/bin/env python3
"""cell_survey - Cellular network survey web app.

Serves a web UI that:
  - detects the router's modems (one per physical port, default int1),
  - shows the selected modem's connection state, carrier, and signal levels,
  - runs an AT network survey (AT#CSURV) over the modem's AT channel,
  - groups the detected cells by carrier (PLMN), and
  - can force the modem onto a chosen PLMN via config/wan/rules2.

Pure-stdlib http.server; all modem work goes through the cp module. The survey
runs in a background thread and the UI polls /api/survey/status for progress.
"""

import http.server
import json
import os
import signal
import socket
import socketserver
import sys
import threading

try:
    import configparser
except ImportError:
    import ConfigParser as configparser

import cp
import modems
import survey

PORT = 8000

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_STATIC_DIR = os.path.join(_SCRIPT_DIR, 'static')

_runner = survey.SurveyRunner()

_MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.ttf': 'font/ttf',
    '.json': 'application/json',
}


def _read_package_ini():
    """Return (app_name, version_string) from package.ini."""
    ini_path = os.path.join(_SCRIPT_DIR, 'package.ini')
    app_name = 'cell_survey'
    version = '0.0.0'
    try:
        config = configparser.ConfigParser()
        config.read(ini_path)
        for section in config.sections():
            app_name = section
            major = config.get(section, 'version_major', fallback='0')
            minor = config.get(section, 'version_minor', fallback='0')
            patch = config.get(section, 'version_patch', fallback='0')
            version = '{}.{}.{}'.format(major, minor, patch)
            break
    except Exception:
        pass
    return app_name, version


def _read_help_content():
    """Return readme.md text for the help modal."""
    for path in (os.path.join(_SCRIPT_DIR, 'readme.md'),
                 os.path.join(_SCRIPT_DIR, 'README.md'),
                 '/app/readme.md'):
        try:
            with open(path, 'r') as f:
                return f.read()
        except (IOError, OSError):
            continue
    return 'Help documentation not available.'


def _get_device_info():
    """Router/app info for the Device Info modal."""
    _, app_version = _read_package_ini()
    info = {
        'router_model': 'N/A',
        'serial_number': 'N/A',
        'mac_address': 'N/A',
        'firmware_version': 'N/A',
        'app_version': app_version,
    }
    try:
        model = cp.get('status/product_info/product_name')
        if model:
            info['router_model'] = str(model)
        serial = cp.get('status/product_info/manufacturing/serial_num')
        if serial:
            info['serial_number'] = str(serial)
        mac = cp.get('status/product_info/mac0')
        if mac:
            info['mac_address'] = str(mac)
        info['firmware_version'] = cp.get_firmware_version()
    except Exception:
        pass
    return info


class AppRequestHandler(http.server.BaseHTTPRequestHandler):
    """Static file serving plus the cell_survey JSON API."""

    def do_GET(self):
        path = self.path.split('?')[0]
        if path in ('/', '/index.html'):
            self._serve_file('index.html', 'text/html; charset=utf-8')
        elif path == '/api/help':
            self._send_text(_read_help_content())
        elif path == '/api/info':
            self._send_json(_get_device_info())
        elif path == '/api/modems':
            self._send_json({'modems': modems.list_modems(),
                             'default_port': modems.DEFAULT_PORT})
        elif path == '/api/modem':
            self._send_json(modems.modem_status(self._query('port')))
        elif path == '/api/survey/status':
            self._send_json(_runner.snapshot())
        elif path.startswith('/static/'):
            self._handle_static(path)
        else:
            rel = path.lstrip('/')
            full = os.path.join(_SCRIPT_DIR, rel)
            if os.path.isfile(full):
                _, ext = os.path.splitext(full)
                ctype = _MIME_TYPES.get(ext.lower(), 'application/octet-stream')
                self._serve_file(rel, ctype)
            else:
                self.send_error(404)

    def do_POST(self):
        path = self.path.split('?')[0]
        body = self._read_body()
        if path == '/api/survey/start':
            self._handle_survey_start(body)
        elif path == '/api/lock':
            self._handle_lock(body)
        elif path == '/api/unlock':
            self._handle_unlock(body)
        else:
            self.send_error(404)

    # --- API handlers -----------------------------------------------------

    def _handle_survey_start(self, body):
        port = body.get('port') or modems.DEFAULT_PORT
        modem = None
        for m in modems.list_modems():
            if m['port'] == port:
                modem = m
                break
        if not modem:
            self._send_json({'ok': False,
                             'message': 'No modem on port {}'.format(port)})
            return
        if not modem.get('iface'):
            self._send_json({'ok': False,
                             'message': 'Modem {} has no AT interface'.format(
                                 port)})
            return
        if not modems.is_supported(modem.get('mfg_model')):
            self._send_json({'ok': False,
                             'message': 'The AT network survey is only '
                                        'supported on Telit FE990/FN990 '
                                        'modules. This modem ({}) is not '
                                        'supported.'.format(
                                            modem.get('mfg_model') or 'unknown')})
            return
        if _runner.is_running():
            self._send_json({'ok': False,
                             'message': 'A survey is already running.'})
            return
        started = _runner.start(modem['iface'], modem.get('uid'),
                                modem.get('mfg_model', ''))
        self._send_json({'ok': started,
                         'message': 'Survey started' if started
                                    else 'Could not start survey.'})

    def _handle_lock(self, body):
        config_id = body.get('config_id')
        plmn = body.get('plmn')
        self._send_json(modems.lock_plmn(config_id, plmn))

    def _handle_unlock(self, body):
        config_id = body.get('config_id')
        self._send_json(modems.unlock(config_id))

    # --- helpers ----------------------------------------------------------

    def _query(self, key):
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(self.path).query)
        return (qs.get(key) or [None])[0]

    def _read_body(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            return json.loads(raw.decode('utf-8'))
        except Exception:
            return {}

    def _serve_file(self, rel_path, content_type):
        file_path = os.path.join(_SCRIPT_DIR, rel_path)
        try:
            with open(file_path, 'rb') as f:
                body = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
        except (IOError, OSError):
            self.send_error(404)

    def _handle_static(self, path):
        rel_path = path[len('/static/'):].replace('..', '')
        file_path = os.path.join(_STATIC_DIR, rel_path)
        if not os.path.isfile(file_path):
            self.send_error(404)
            return
        _, ext = os.path.splitext(file_path)
        content_type = _MIME_TYPES.get(ext.lower(), 'application/octet-stream')
        try:
            with open(file_path, 'rb') as f:
                body = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
        except (IOError, OSError, BrokenPipeError, ConnectionResetError):
            pass

    def _send_json(self, obj):
        try:
            body = json.dumps(obj).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send_text(self, text):
        body = text.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return  # keep the router log clean; app logs via cp.log where useful


class ThreadingHTTPServer(socketserver.ThreadingMixIn,
                          http.server.HTTPServer):
    """Threaded server so survey polling doesn't block other requests."""
    daemon_threads = True
    allow_reuse_address = True


def main():
    app_name, version = _read_package_ini()
    cp.log('Starting {} v{}...'.format(app_name, version))
    # Warm the PLMN table so the first survey response is fast.
    survey.load_plmn_table()

    def _shutdown(signum, frame):
        cp.log('cell_survey stopping (signal {}).'.format(signum))
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        httpd = ThreadingHTTPServer(('', PORT), AppRequestHandler)
        httpd.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        cp.log('cell_survey web server started on port {}'.format(PORT))
        httpd.serve_forever()
    except OSError as e:
        cp.log('ERROR starting server on port {}: {}'.format(PORT, e))
        # Park so a one-shot failure idles instead of hot-restart looping.
        while True:
            import time
            time.sleep(60)


if __name__ == '__main__':
    main()
