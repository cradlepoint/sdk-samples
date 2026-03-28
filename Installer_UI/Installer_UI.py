# Installer_UI - Web UI for installers to configure WiFi and run speedtests.

import cp
import json
import os
import socket
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs
from speedtest_ookla import Speedtest


class AppHandler(SimpleHTTPRequestHandler):
    """Handles all HTTP requests for the Installer UI."""

    def do_GET(self):
        """Serve pages and static files."""
        try:
            if self.path == '/' or self.path == '/index.html':
                self._serve_index()
            elif self.path == '/signal':
                self._serve_signal()
            else:
                SimpleHTTPRequestHandler.do_GET(self)
        except Exception as e:
            cp.log('GET error: ' + str(e))
            self._send_json(500, {'success': False, 'result': 'Server error'})

    def do_POST(self):
        """Handle form submissions."""
        try:
            params = self._parse_form()
            if self.path == '/save':
                self._handle_save(params)
            elif self.path == '/speedtest':
                self._handle_speedtest(params)
            else:
                self.send_error(404)
        except Exception as e:
            cp.log('POST error: ' + str(e))
            self._send_json(500, {'success': False, 'result': 'Server error'})

    def _serve_index(self):
        """Render index.html with current SSID."""
        current_ssid = get_ssid()
        html = _read_template('index.html')
        html = html.replace('{{current_ssid}}', str(current_ssid or ''))
        self._send_html(html)

    def _serve_signal(self):
        """Render signal.html with signal quality values."""
        rssi, sinr, rsrp, rsrq = get_signal_quality()
        html = _read_template('signal.html')
        html = html.replace('{{rssi}}', str(rssi or 'N/A'))
        html = html.replace('{{sinr}}', str(sinr or 'N/A'))
        html = html.replace('{{rsrp}}', str(rsrp or 'N/A'))
        html = html.replace('{{rsrq}}', str(rsrq or 'N/A'))
        self._send_html(html)

    def _handle_save(self, params):
        """Process WiFi settings save."""
        installer_password = get_config('installer_password')
        wifi_ssid = params.get('wifi_ssid', '')
        wifi_password = params.get('wifi_password', '')
        password_entered = params.get('password_entered', '')
        if not all([wifi_ssid, wifi_password, password_entered]):
            self._send_json(200, {
                'success': False,
                'result': 'Please enter all fields!'
            })
            return
        if password_entered == installer_password:
            cp.log('Installer changed WiFi SSID to ' + wifi_ssid
                    + ' and password to ' + wifi_password)
            cp.put('config/wlan/radio/0/bss/0/ssid', wifi_ssid)
            cp.put('config/wlan/radio/1/bss/0/ssid', wifi_ssid)
            cp.put('config/wlan/radio/0/bss/0/wpapsk', wifi_password)
            cp.put('config/wlan/radio/1/bss/0/wpapsk', wifi_password)
            self._send_json(200, {
                'success': True,
                'result': 'Success!\nRestarting WiFi...',
                'current_ssid': wifi_ssid
            })
        else:
            cp.log('Incorrect password entered')
            self._send_json(200, {
                'success': False,
                'result': 'Incorrect Password!'
            })

    def _handle_speedtest(self, params):
        """Process speedtest request."""
        installer_password = get_config('installer_password')
        password_entered = params.get('password_entered', '')
        if password_entered == installer_password:
            result = run_speedtest()
            self._send_json(200, {
                'success': True,
                'result': result
            })
        else:
            cp.log('Incorrect password entered')
            self._send_json(200, {
                'success': False,
                'result': 'Incorrect Password!'
            })

    def _parse_form(self):
        """Parse URL-encoded form data from POST body."""
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8')
        content_type = self.headers.get('Content-Type', '')
        if 'multipart/form-data' in content_type:
            return _parse_multipart(body, content_type)
        parsed = parse_qs(body)
        return {k: v[0] for k, v in parsed.items()}

    def _send_html(self, html):
        """Send an HTML response."""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def _send_json(self, code, data):
        """Send a JSON response."""
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass


def _read_template(filename):
    """Read an HTML template file from the app directory."""
    app_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(app_dir, filename)
    with open(filepath, 'r') as f:
        return f.read()


def _parse_multipart(body, content_type):
    """Parse multipart/form-data into a dict of field name -> value."""
    result = {}
    boundary = ''
    for part in content_type.split(';'):
        part = part.strip()
        if part.startswith('boundary='):
            boundary = part.split('=', 1)[1]
            break
    if not boundary:
        return result
    parts = body.split('--' + boundary)
    for part in parts:
        if 'Content-Disposition: form-data;' not in part:
            continue
        header_body = part.split('\r\n\r\n', 1)
        if len(header_body) < 2:
            continue
        header = header_body[0]
        value = header_body[1].rstrip('\r\n')
        name_start = header.find('name="')
        if name_start == -1:
            continue
        name_start += 6
        name_end = header.find('"', name_start)
        name = header[name_start:name_end]
        result[name] = value
    return result


def run_speedtest():
    """Run Ookla speedtest and return formatted results."""
    try:
        cp.log('Starting Speedtest...')
        s = Speedtest(timeout=90)
        s.start()
        r = s.results
        download = '{:.2f}'.format(r.download / 1000 / 1000)
        upload = '{:.2f}'.format(r.upload / 1000 / 1000)
        cp.log('Ookla Speedtest Complete! Results:')
        cp.log('Client ISP: ' + str(r.isp))
        cp.log('Ookla Server: ' + r.server.get('name', 'Unknown'))
        cp.log('Ping: ' + str(r.ping) + 'ms')
        cp.log('Download Speed: ' + download + 'Mb/s')
        cp.log('Upload Speed: ' + upload + 'Mb/s')
        text = ('Carrier: ' + str(r.isp) + '\nServer: '
                + r.server.get('name', 'Unknown') + '\nDL:' + download
                + 'Mbps\nUL:' + upload + 'Mbps\nPing:'
                + '{:.0f}'.format(r.ping) + 'ms')
        return text
    except Exception as e:
        cp.log('Speedtest error: ' + str(e))
        return 'Speedtest failed: ' + str(e)


def get_ssid():
    """Get current WiFi SSID."""
    return cp.get('config/wlan/radio/1/bss/0/ssid')


def get_config(name):
    """Get appdata config value, fallback to serial number."""
    appdata = cp.get('config/system/sdk/appdata')
    try:
        password = [x['value'] for x in appdata if x['name'] == name][0]
        if not password:
            password = cp.get('status/product_info/manufacturing/serial_num')
    except Exception:
        cp.post('config/system/sdk/appdata',
                {'name': name, 'value': ''})
        password = cp.get('status/product_info/manufacturing/serial_num')
    return password


def open_firewall():
    """Open firewall forwarding from Primary LAN to Router Zone."""
    app_fwd = {
        'dst_zone_id': '00000001-695c-3d87-95cb-d0ee2029d0b5',
        'enabled': True,
        'filter_policy_id': '00000000-77db-3b20-980e-2de482869073',
        'src_zone_id': '00000003-695c-3d87-95cb-d0ee2029d0b5'
    }
    forwardings = cp.get('config/security/zfw/forwardings')
    for forwarding in forwardings:
        if (forwarding['src_zone_id'] == app_fwd['src_zone_id']
                and forwarding['dst_zone_id'] == app_fwd['dst_zone_id']):
            return
    cp.post('config/security/zfw/forwardings', app_fwd)
    cp.log('Forwarded Primary LAN Zone to Router Zone'
           ' with Default Allow All policy')


def get_signal_quality():
    """Get cellular signal quality metrics."""
    try:
        dev = cp.get('status/wan/primary_device')
        if dev.startswith('mdm-'):
            diagnostics = cp.get('status/wan/devices/' + dev
                                 + '/diagnostics')
            rssi = diagnostics.get('DBM')
            sinr = diagnostics.get('SINR')
            rsrp = diagnostics.get('RSRP')
            rsrq = diagnostics.get('RSRQ')
            return rssi, sinr, rsrp, rsrq
    except Exception as e:
        cp.log('Signal quality error: ' + str(e))
    return None, None, None, None


if __name__ == '__main__':
    cp.log('Starting... edit Installer Password under System > SDK Data.')
    get_config('installer_password')
    open_firewall()
    server = HTTPServer(('', 8000), AppHandler)
    server.socket.setsockopt(
        socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
    )
    cp.log('Web server started on port 8000')
    server.serve_forever()
