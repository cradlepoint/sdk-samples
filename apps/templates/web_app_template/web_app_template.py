#!/usr/bin/env python3
"""
Web App Template Server
Serves the web app template using Python's built-in HTTP server
with API endpoints for help content and device info.
"""

import http.server
import socketserver
import os
import sys
import json

try:
    import configparser
except ImportError:
    import ConfigParser as configparser

try:
    import cp
    # Check if we're truly on a router by looking for the NCOS socket
    ON_ROUTER = os.path.exists('/var/tmp/cs.sock')
except ImportError:
    ON_ROUTER = False

# Default port
PORT = 8000

# Resolve paths relative to this script
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_STATIC_DIR = os.path.join(_SCRIPT_DIR, 'static')

# MIME types for static file serving
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
    """Read package.ini and return the version string and app name.

    Returns:
        Tuple of (app_name, version_string) e.g. ('web_app_template', '1.0.0').
    """
    ini_path = os.path.join(_SCRIPT_DIR, 'package.ini')
    app_name = 'web_app_template'
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
    """Read the readme.md file content for the help modal.

    Checks multiple locations: script directory then /app/ for on-router.

    Returns:
        The readme content as a string.
    """
    candidates = [
        os.path.join(_SCRIPT_DIR, 'readme.md'),
        os.path.join(_SCRIPT_DIR, 'README.md'),
    ]
    if ON_ROUTER:
        candidates.append('/app/readme.md')
        candidates.append('/app/README.md')

    for path in candidates:
        try:
            with open(path, 'r') as f:
                return f.read()
        except (IOError, OSError):
            continue
    return 'Help documentation not available.'


def _get_device_info():
    """Get router info via cp module (when on-router) or placeholder values.

    Returns:
        Dict with router_model, serial_number, mac_address,
        firmware_version, and app_version.
    """
    _, app_version = _read_package_ini()

    info = {
        'router_model': 'N/A',
        'serial_number': 'N/A',
        'mac_address': 'N/A',
        'firmware_version': 'N/A',
        'app_version': app_version,
    }

    if ON_ROUTER:
        try:
            model = cp.get('status/product_info/product_name')
            if model:
                info['router_model'] = str(model)
        except Exception:
            pass

        try:
            serial = cp.get('status/product_info/manufacturing/serial_num')
            if serial:
                info['serial_number'] = str(serial)
        except Exception:
            pass

        try:
            mac = cp.get('status/product_info/mac0')
            if mac:
                info['mac_address'] = str(mac)
        except Exception:
            pass

        try:
            fw = cp.get('status/fw_info/major_version')
            fw_minor = cp.get('status/fw_info/minor_version')
            fw_patch = cp.get('status/fw_info/patch_version')
            if fw and fw_minor:
                parts = [str(fw), str(fw_minor)]
                if fw_patch:
                    parts.append(str(fw_patch))
                info['firmware_version'] = '.'.join(parts)
        except Exception:
            pass
    else:
        # Running locally — try REST API via cp module if available
        try:
            # Ensure cp can find sdk_settings.ini by searching up from script dir
            settings_path = None
            search_dir = _SCRIPT_DIR
            for _ in range(5):
                candidate = os.path.join(search_dir, 'sdk_settings.ini')
                if os.path.exists(candidate):
                    settings_path = candidate
                    break
                search_dir = os.path.dirname(search_dir)

            if settings_path:
                cfg = configparser.ConfigParser()
                cfg.read(settings_path)
                sdk_section = dict(cfg.items('sdk')) if cfg.has_section('sdk') else {}
                dev_ip = sdk_section.get('dev_client_ip', '')
                dev_user = sdk_section.get('dev_client_username', '')
                dev_pass = sdk_section.get('dev_client_password', '')

                if dev_ip:
                    import requests
                    base_url = 'https://{}/api'.format(dev_ip)
                    auth = (dev_user, dev_pass)

                    def _rest_get(path):
                        try:
                            r = requests.get(
                                '{}/{}/'.format(base_url, path),
                                auth=auth, verify=False, timeout=5)
                            if r.status_code == 200:
                                data = r.json()
                                if isinstance(data, dict) and 'data' in data:
                                    return data['data']
                                return data
                        except Exception:
                            pass
                        return None

                    model = _rest_get('status/product_info/product_name')
                    if model:
                        info['router_model'] = str(model)
                    serial = _rest_get('status/product_info/manufacturing/serial_num')
                    if serial:
                        info['serial_number'] = str(serial)
                    mac = _rest_get('status/product_info/mac0')
                    if mac:
                        info['mac_address'] = str(mac)
                    fw = _rest_get('status/fw_info/major_version')
                    fw_minor = _rest_get('status/fw_info/minor_version')
                    fw_patch = _rest_get('status/fw_info/patch_version')
                    if fw and fw_minor:
                        parts = [str(fw), str(fw_minor)]
                        if fw_patch:
                            parts.append(str(fw_patch))
                        info['firmware_version'] = '.'.join(parts)
        except Exception:
            pass

    return info


class AppRequestHandler(http.server.BaseHTTPRequestHandler):
    """Custom request handler with API routes and static file serving."""

    def do_GET(self):
        """Route GET requests to the appropriate handler."""
        path = self.path.split('?')[0]  # Strip query string

        if path == '/' or path == '/index.html':
            self._serve_file('index.html', 'text/html; charset=utf-8')
        elif path == '/your_web_app.html':
            self._serve_file('your_web_app.html', 'text/html; charset=utf-8')
        elif path == '/api/help':
            self._handle_api_help()
        elif path == '/api/info':
            self._handle_api_info()
        elif path.startswith('/static/'):
            self._handle_static(path)
        else:
            # Try to serve as a file from script dir
            rel = path.lstrip('/')
            full = os.path.join(_SCRIPT_DIR, rel)
            if os.path.isfile(full):
                _, ext = os.path.splitext(full)
                ctype = _MIME_TYPES.get(ext.lower(), 'application/octet-stream')
                self._serve_file(rel, ctype)
            else:
                self.send_error(404)

    def _serve_file(self, rel_path, content_type):
        """Serve a file relative to the script directory."""
        file_path = os.path.join(_SCRIPT_DIR, rel_path)
        try:
            with open(file_path, 'rb') as f:
                body = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.end_headers()
            self.wfile.write(body)
        except (IOError, OSError):
            self.send_error(404)

    def _handle_static(self, path):
        """Serve static files from the static/ directory."""
        rel_path = path[len('/static/'):]
        # Prevent directory traversal
        rel_path = rel_path.replace('..', '')
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
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.end_headers()
            self.wfile.write(body)
        except (IOError, OSError, BrokenPipeError, ConnectionResetError):
            pass

    def _handle_api_help(self):
        """Serve the readme.md content as plain text."""
        content = _read_help_content()
        body = content.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _handle_api_info(self):
        """Serve device and app info as JSON."""
        info = _get_device_info()
        body = json.dumps(info).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """Override to customize log format."""
        if ON_ROUTER:
            try:
                cp.log(format % args)
            except Exception:
                pass
        else:
            sys.stderr.write("%s - - [%s] %s\n" %
                             (self.address_string(),
                              self.log_date_time_string(),
                              format % args))


def main():
    """Start the HTTP server."""
    app_name, version = _read_package_ini()

    if ON_ROUTER:
        cp.log('Starting {} v{}...'.format(app_name, version))

    try:
        with socketserver.TCPServer(("", PORT), AppRequestHandler) as httpd:
            if ON_ROUTER:
                cp.log('Web server started on port {}'.format(PORT))
            else:
                print("=" * 60)
                print("{} v{}".format(app_name, version))
                print("=" * 60)
                print("Server running at: http://0.0.0.0:{}".format(PORT))
                print("Serving directory: {}".format(_SCRIPT_DIR))
                print("\nPress Ctrl+C to stop the server")
                print("=" * 60)

            httpd.serve_forever()

    except KeyboardInterrupt:
        if not ON_ROUTER:
            print("\n\nServer stopped by user.")
        sys.exit(0)
    except OSError as e:
        if e.errno == 48 or e.errno == 98:  # Address already in use
            msg = "Port {} is already in use.".format(PORT)
            if ON_ROUTER:
                cp.log('ERROR: {}'.format(msg))
            else:
                print("\nError: {}".format(msg))
        else:
            msg = "Failed to start server: {}".format(e)
            if ON_ROUTER:
                cp.log('ERROR: {}'.format(msg))
            else:
                print("\nError: {}".format(msg))
        sys.exit(1)


if __name__ == "__main__":
    main()
