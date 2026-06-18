"""tcpdumpster - Graphical packet capture interface for Cradlepoint routers."""

import cp
import os
import sys
import json
import time
import struct
import socket
import threading
import http.server
import http.client
import ssl
import base64
import urllib.parse
from datetime import datetime


PORT = 7001
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CAPTURE_USER = 'SDKTCPDUMP'
CAPTURE_PASS = ''

# Capture state (shared between threads)
capture_state = {
    'running': False,
    'lines': [],         # Pending lines for UI polling
    'lines_lock': threading.Lock(),
    'pcap_data': b'',   # Accumulated pcap bytes for download
    'thread': None,
    'stop_requested': False,
    'was_in_ap_mode': False,
}


def get_interfaces():
    """Query router for available capture interfaces."""
    interfaces = []

    # WAN devices
    try:
        wan_devices = cp.get('status/wan/devices')
        if wan_devices:
            for uid, device in wan_devices.items():
                info = device.get('info', {})
                status = device.get('status', {})
                conn_state = status.get('connection_state', '')
                iface_name = info.get('iface', '')
                dev_type = info.get('type', '')
                model = info.get('model', '') or info.get('product', '')

                if conn_state == 'connected' and iface_name:
                    interfaces.append({
                        'device': iface_name,
                        'description': model or uid,
                        'type': dev_type,
                        'radio_index': None
                    })
    except Exception as e:
        cp.log(f"Error getting WAN interfaces: {e}")

    # LAN devices
    try:
        lan_devices = cp.get('status/lan/devices')
        if lan_devices:
            for uid, device in lan_devices.items():
                info = device.get('info', {})
                status = device.get('status', {})
                link_state = status.get('link_state', '')
                iface_name = info.get('iface', '')

                if link_state == 'up' and iface_name \
                        and not iface_name.startswith('ath'):
                    interfaces.append({
                        'device': iface_name,
                        'description': 'LAN (' + iface_name + ')',
                        'type': 'ethernet',
                        'radio_index': None
                    })
    except Exception as e:
        cp.log(f"Error getting LAN interfaces: {e}")

    # Wi-Fi monitor interfaces
    try:
        wlan = cp.get('status/wlan')
        if wlan and wlan.get('radio'):
            radios = wlan['radio']
            for i, radio in enumerate(radios):
                # Only show monitor interface if radio is enabled
                try:
                    radio_enabled = cp.get(
                        'config/wlan/radio/' + str(i) + '/enabled')
                except Exception:
                    radio_enabled = False

                if not radio_enabled:
                    continue

                band = radio.get('band', 'Unknown')
                mon_iface = 'mon' + str(i)
                interfaces.append({
                    'device': mon_iface,
                    'description': 'Wi-Fi ' + band + ' (' + mon_iface + ')',
                    'type': 'wifi',
                    'radio_index': i
                })
    except Exception as e:
        cp.log(f"Error getting WLAN interfaces: {e}")

    return interfaces


def get_wifi_channels(radio_index):
    """Get available channels for a Wi-Fi radio."""
    try:
        wlan = cp.get('status/wlan')
        if wlan and wlan.get('radio'):
            radios = wlan['radio']
            if radio_index < len(radios):
                return radios[radio_index].get('channel_list', [])
    except Exception as e:
        cp.log(f"Error getting WiFi channels: {e}")
    return []


def format_mac(data, offset):
    """Format 6 bytes as a MAC address string."""
    return ':'.join(format(data[offset + i], '02x') for i in range(6))


def decode_80211_frame(pkt_data, offset, incl_len):
    """Decode an 802.11 frame after the radiotap header.
    Returns a dict with 'l2' (addresses) and 'l3' (frame type)."""
    if incl_len - offset < 2:
        return {'l2': '', 'l3': '802.11 [short frame]'}

    fc = struct.unpack('<H', pkt_data[offset:offset + 2])[0]
    frame_type = (fc >> 2) & 0x03
    frame_subtype = (fc >> 4) & 0x0F
    to_ds = (fc >> 8) & 0x01
    from_ds = (fc >> 9) & 0x01

    # Frame type names
    mgmt_subtypes = {
        0: 'AssocReq', 1: 'AssocResp', 2: 'ReassocReq',
        3: 'ReassocResp', 4: 'ProbeReq', 5: 'ProbeResp',
        8: 'Beacon', 9: 'ATIM', 10: 'Disassoc',
        11: 'Auth', 12: 'Deauth', 13: 'Action'
    }
    ctrl_subtypes = {
        8: 'BlockAckReq', 9: 'BlockAck', 10: 'PS-Poll',
        11: 'RTS', 12: 'CTS', 13: 'ACK',
        14: 'CF-End', 15: 'CF-End+Ack'
    }
    data_subtypes = {
        0: 'Data', 4: 'Null', 8: 'QoS Data',
        12: 'QoS Null'
    }

    if frame_type == 0:
        # Management frame
        subtype_name = mgmt_subtypes.get(frame_subtype,
                                         'Mgmt(' + str(frame_subtype) + ')')
        if incl_len - offset >= 24:
            da = format_mac(pkt_data, offset + 4)
            sa = format_mac(pkt_data, offset + 10)
            bssid = format_mac(pkt_data, offset + 16)
            return {'l2': '',
                    'l3': '802.11 ' + subtype_name + ' ' + sa
                    + ' > ' + da + ' BSSID=' + bssid}
        return {'l2': '', 'l3': '802.11 ' + subtype_name}

    elif frame_type == 1:
        # Control frame
        subtype_name = ctrl_subtypes.get(frame_subtype,
                                         'Ctrl(' + str(frame_subtype) + ')')
        if incl_len - offset >= 10:
            ra = format_mac(pkt_data, offset + 4)
            return {'l2': '',
                    'l3': '802.11 ' + subtype_name + ' RA=' + ra}
        return {'l2': '', 'l3': '802.11 ' + subtype_name}

    elif frame_type == 2:
        # Data frame
        subtype_name = data_subtypes.get(frame_subtype,
                                         'Data(' + str(frame_subtype) + ')')
        if incl_len - offset >= 24:
            if to_ds == 0 and from_ds == 0:
                da = format_mac(pkt_data, offset + 4)
                sa = format_mac(pkt_data, offset + 10)
                return {'l2': '',
                        'l3': '802.11 ' + subtype_name + ' ' + sa
                        + ' > ' + da}
            elif to_ds == 0 and from_ds == 1:
                da = format_mac(pkt_data, offset + 4)
                sa = format_mac(pkt_data, offset + 16)
                return {'l2': '',
                        'l3': '802.11 ' + subtype_name + ' ' + sa
                        + ' > ' + da}
            elif to_ds == 1 and from_ds == 0:
                sa = format_mac(pkt_data, offset + 10)
                da = format_mac(pkt_data, offset + 16)
                return {'l2': '',
                        'l3': '802.11 ' + subtype_name + ' ' + sa
                        + ' > ' + da}
            else:
                ra = format_mac(pkt_data, offset + 4)
                ta = format_mac(pkt_data, offset + 10)
                return {'l2': '',
                        'l3': '802.11 ' + subtype_name + ' TA=' + ta
                        + ' RA=' + ra}
        return {'l2': '', 'l3': '802.11 ' + subtype_name}

    return {'l2': '',
            'l3': '802.11 type=' + str(frame_type) + ' sub='
            + str(frame_subtype)}


def decode_packet(pkt_data, incl_len, ts_sec, ts_usec, linktype):
    """Decode a pcap packet and return a dict with l2 and l3 display lines."""
    ts_str = datetime.fromtimestamp(ts_sec).strftime('%H:%M:%S')
    ts_str += '.' + str(ts_usec).zfill(6)

    l2_prefix = ''

    # Radiotap / 802.11 monitor mode (linktype 127)
    if linktype == 127:
        if incl_len < 4:
            return {'l2': '', 'l3': ts_str + ' [short radiotap frame]'}
        # Radiotap header: version(1) + pad(1) + length(2 LE)
        rt_len = struct.unpack('<H', pkt_data[2:4])[0]
        if rt_len > incl_len:
            rt_len = incl_len
        frame_result = decode_80211_frame(pkt_data, rt_len, incl_len)
        return {'l2': frame_result['l2'],
                'l3': ts_str + ' ' + frame_result['l3']}

    # Determine IP offset and EtherType/protocol based on linktype
    if linktype == 113:
        # Linux cooked capture (SLL) - 16 byte header
        if incl_len < 16:
            return {'l2': '', 'l3': ts_str + ' [short SLL frame]'}
        proto_type = struct.unpack('!H', pkt_data[14:16])[0]
        ip_offset = 16
        # SLL has source address at bytes 6-11 (6 bytes)
        src_mac = format_mac(pkt_data, 6)
        l2_prefix = src_mac + ' > ?? '
    elif linktype == 101:
        # Raw IP - no link-layer header
        if incl_len < 1:
            return {'l2': '', 'l3': ts_str + ' [empty]'}
        version = (pkt_data[0] >> 4) & 0x0F
        if version == 4:
            proto_type = 0x0800
        elif version == 6:
            proto_type = 0x86DD
        else:
            return {'l2': '', 'l3': ts_str + ' Raw IP v' + str(version)}
        ip_offset = 0
    else:
        # Ethernet (linktype 1) - 14 byte header
        if incl_len < 14:
            return {'l2': '', 'l3': ts_str + ' [short frame]'}
        proto_type = struct.unpack('!H', pkt_data[12:14])[0]
        ip_offset = 14
        dst_mac = format_mac(pkt_data, 0)
        src_mac = format_mac(pkt_data, 6)
        l2_prefix = src_mac + ' > ' + dst_mac + ' '

    # Build L3 line
    l3_line = ''
    if proto_type == 0x0800 and incl_len >= ip_offset + 20:
        ihl = (pkt_data[ip_offset] & 0x0F) * 4
        proto = pkt_data[ip_offset + 9]
        src_ip = socket.inet_ntoa(pkt_data[ip_offset + 12:ip_offset + 16])
        dst_ip = socket.inet_ntoa(pkt_data[ip_offset + 16:ip_offset + 20])
        total_len = struct.unpack(
            '!H', pkt_data[ip_offset + 2:ip_offset + 4])[0]

        tp_offset = ip_offset + ihl
        if proto == 6 and incl_len >= tp_offset + 4:
            src_port = struct.unpack(
                '!H', pkt_data[tp_offset:tp_offset + 2])[0]
            dst_port = struct.unpack(
                '!H', pkt_data[tp_offset + 2:tp_offset + 4])[0]
            l3_line = ('IP ' + src_ip + '.' + str(src_port)
                       + ' > ' + dst_ip + '.' + str(dst_port)
                       + ': TCP (' + str(total_len) + ')')
        elif proto == 17 and incl_len >= tp_offset + 4:
            src_port = struct.unpack(
                '!H', pkt_data[tp_offset:tp_offset + 2])[0]
            dst_port = struct.unpack(
                '!H', pkt_data[tp_offset + 2:tp_offset + 4])[0]
            l3_line = ('IP ' + src_ip + '.' + str(src_port)
                       + ' > ' + dst_ip + '.' + str(dst_port)
                       + ': UDP (' + str(total_len) + ')')
        elif proto == 1:
            l3_line = ('IP ' + src_ip + ' > ' + dst_ip
                       + ': ICMP (' + str(total_len) + ')')
        else:
            l3_line = ('IP ' + src_ip + ' > ' + dst_ip
                       + ': proto ' + str(proto)
                       + ' (' + str(total_len) + ')')
    elif proto_type == 0x0806:
        l3_line = 'ARP'
    elif proto_type == 0x86DD:
        l3_line = 'IPv6 (' + str(incl_len) + ')'
    else:
        l3_line = 'Proto 0x' + format(proto_type, '04x')

    return {'l2': l2_prefix, 'l3': ts_str + ' ' + l3_line}


def add_line(pkt_info):
    """Add a packet info dict to the pending output for UI polling."""
    with capture_state['lines_lock']:
        capture_state['lines'].append(pkt_info)


def capture_thread_func(iface, count, timeout, filter_str,
                        wifichannel, wifichannelwidth):
    """Background thread that streams pcap from the router tcpdump API."""
    try:
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = timestamp + '.pcap'

        # Router rejects count=0 AND timeout=0 with HTTP 400.
        # UI validates this, but guard here too just in case.
        if count == 0 and timeout == 0:
            timeout = 600

        # Build query params using urlencode for proper escaping
        params = urllib.parse.urlencode({
            'iface': iface,
            'args': filter_str or '',
            'wifichannel': wifichannel or '',
            'wifichannelwidth': wifichannelwidth or '',
            'wifiextrachannel': '',
            'timeout': str(timeout),
            'count': str(count),
            'url': ''
        })

        path = '/api/tcpdump/' + filename + '?' + params
        cp.log('Capture request: ' + path)

        # Connect to router's own HTTP API (localhost on router)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        # Use the credentials created at startup
        auth_str = base64.b64encode(
            (CAPTURE_USER + ':' + CAPTURE_PASS).encode()).decode()
        headers = {'Authorization': 'Basic ' + auth_str}

        conn = http.client.HTTPSConnection('127.0.0.1', context=ctx)
        conn.request('GET', path, headers=headers)

        resp = conn.getresponse()

        if resp.status == 302:
            # First-login redirect — re-issue request to follow it
            location = resp.headers.get('Location', '')
            cp.log('Got 302 redirect to: ' + location)
            # Read and discard redirect body
            resp.read()
            conn.close()
            # Retry the request (router accepts second attempt after redirect)
            conn = http.client.HTTPSConnection('127.0.0.1', context=ctx)
            conn.request('GET', path, headers=headers)
            resp = conn.getresponse()

        if resp.status != 200:
            body = ''
            try:
                body = resp.read(512).decode('utf-8', errors='replace')
            except Exception:
                pass
            add_line({'l2': '', 'l3': 'Error: capture API returned HTTP '
                     + str(resp.status) + ' - ' + body})
            cp.log('Capture API error ' + str(resp.status) + ': ' + body)
            capture_state['running'] = False
            return

        # Read pcap global header (24 bytes)
        pcap_header = resp.read(24)
        if len(pcap_header) < 24:
            add_line({'l2': '', 'l3': 'Error: failed to read pcap header'})
            capture_state['running'] = False
            return

        capture_state['pcap_data'] = pcap_header
        linktype = struct.unpack('<I', pcap_header[20:24])[0]
        pkt_num = 0

        # Read packets until stream ends or stop requested
        while not capture_state['stop_requested']:
            pkt_hdr = resp.read(16)
            if len(pkt_hdr) < 16:
                break  # Stream ended

            ts_sec, ts_usec, incl_len, orig_len = struct.unpack(
                '<IIII', pkt_hdr)
            pkt_data = resp.read(incl_len)
            if len(pkt_data) < incl_len:
                break

            # Accumulate for download
            capture_state['pcap_data'] += pkt_hdr + pkt_data
            pkt_num += 1

            # Decode and add display line
            line = decode_packet(pkt_data, incl_len, ts_sec, ts_usec,
                                 linktype)
            add_line(line)

        conn.close()

    except Exception as e:
        add_line({'l2': '', 'l3': 'Capture error: ' + str(e)})
        cp.log(f"Capture thread error: {e}")
    finally:
        # Disable monitor mode if this was a Wi-Fi capture that started from AP mode
        if iface.startswith('mon') and capture_state.get('was_in_ap_mode'):
            try:
                cp.put('control/wlan/monitor_mode', False)
                cp.log('Sent disable monitor mode after capture on ' + iface)
                time.sleep(3)
                state = cp.get('status/wlan/state')
                if state == 'On':
                    add_line({'l2': '', 'l3': 'Router is now serving '
                             'Wi-Fi clients.'})
                else:
                    # Poll up to 5 more times
                    restored = False
                    for _ in range(5):
                        add_line({'l2': '',
                                  'l3': 'Checking radio status...'})
                        time.sleep(3)
                        state = cp.get('status/wlan/state')
                        if state == 'On':
                            add_line({'l2': '', 'l3': 'Router is now '
                                     'serving Wi-Fi clients.'})
                            restored = True
                            break
                    if not restored:
                        add_line({'l2': '', 'l3': 'Router is still in '
                                 'monitor mode. Please use the router\'s '
                                 'NCOS UI to disable monitor mode.'})
            except Exception as e:
                cp.log(f"Error disabling monitor mode: {e}")
                add_line({'l2': '', 'l3': 'Error disabling monitor mode: '
                         + str(e)})
        capture_state['running'] = False


class TCPDumpsterHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler for the tcpdumpster web UI."""

    def translate_path(self, path):
        """Serve files from the app directory."""
        # Strip query string
        path = path.split('?')[0]
        if path == '/' or path == '':
            path = '/index.html'
        return os.path.join(SCRIPT_DIR, path.lstrip('/'))

    def do_GET(self):
        """Handle GET requests."""
        path = self.path.split('?')[0]

        if path == '/api/interfaces':
            self.send_json({'interfaces': get_interfaces()})
        elif path == '/api/wifi_channels':
            # Parse radio index from query
            query = self.path.split('?')[1] if '?' in self.path else ''
            radio = 0
            for part in query.split('&'):
                if part.startswith('radio='):
                    try:
                        radio = int(part.split('=')[1])
                    except ValueError:
                        pass
            channels = get_wifi_channels(radio)
            self.send_json({'channels': channels})
        elif path == '/api/packets':
            self.handle_get_packets()
        elif path == '/api/download_pcap':
            self.handle_download_pcap()
        elif path == '/api/wlan_state':
            self.handle_wlan_state()
        else:
            # Serve static files
            super().do_GET()

    def do_POST(self):
        """Handle POST requests."""
        path = self.path.split('?')[0]

        if path == '/api/start_capture':
            self.handle_start_capture()
        elif path == '/api/stop_capture':
            self.handle_stop_capture()
        elif path == '/api/verify_filter':
            self.handle_verify_filter()
        else:
            self.send_error(404)

    def handle_start_capture(self):
        """Start a packet capture."""
        content_len = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_len)
        try:
            params = json.loads(body.decode())
        except Exception:
            self.send_json({'error': 'Invalid JSON'})
            return

        if capture_state['running']:
            self.send_json({'error': 'Capture already running'})
            return

        if not CAPTURE_PASS:
            self.send_json({'error': 'Capture user not initialized'})
            return

        iface = params.get('iface', 'any')
        count = params.get('count', 0)
        timeout_val = params.get('timeout', 0)
        filter_str = params.get('filter', '')
        wifichannel = params.get('wifichannel', '')
        wifichannelwidth = params.get('wifichannelwidth', '')
        was_in_monitor = params.get('was_in_monitor', False)

        # Reset state
        capture_state['running'] = True
        capture_state['stop_requested'] = False
        capture_state['pcap_data'] = b''
        capture_state['was_in_ap_mode'] = (
            iface.startswith('mon') and not was_in_monitor)
        with capture_state['lines_lock']:
            capture_state['lines'] = []

        # Start capture thread
        t = threading.Thread(
            target=capture_thread_func,
            args=(iface, count, timeout_val, filter_str,
                  wifichannel, wifichannelwidth),
            daemon=True
        )
        t.start()
        capture_state['thread'] = t

        self.send_json({'status': 'started'})

    def handle_stop_capture(self):
        """Stop an active capture."""
        capture_state['stop_requested'] = True
        # Send stop to router API
        try:
            cp.put('control/system/tcpdump', {'stop': True})
        except Exception as e:
            cp.log(f"Error sending stop: {e}")
        self.send_json({'status': 'stopping'})

    def handle_wlan_state(self):
        """Return the current WLAN state."""
        try:
            state = cp.get('status/wlan/state')
            self.send_json({'state': state})
        except Exception as e:
            self.send_json({'state': 'unknown', 'error': str(e)})

    def handle_verify_filter(self):
        """Verify a BPF filter using tcpdump -d."""
        content_len = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_len)
        try:
            params = json.loads(body.decode())
        except Exception:
            self.send_json({'valid': False, 'error': 'Invalid JSON'})
            return

        filter_str = params.get('filter', '').strip()
        if not filter_str:
            self.send_json({'valid': False,
                            'error': 'No filter provided'})
            return

        try:
            output = cp.execute_cli(
                'tcpdump -d ' + filter_str, timeout=5)
            if output is None:
                self.send_json({
                    'valid': False,
                    'error': 'Unable to execute tcpdump -d'})
            elif 'syntax error' in output.lower() or 'error' in output.lower():
                self.send_json({'valid': False, 'error': output})
            else:
                self.send_json({'valid': True})
        except Exception as e:
            self.send_json({'valid': False, 'error': str(e)})

    def handle_get_packets(self):
        """Return pending packet lines and capture status."""
        with capture_state['lines_lock']:
            lines = capture_state['lines'][:]
            capture_state['lines'] = []

        status = 'capturing' if capture_state['running'] else 'stopped'
        self.send_json({'lines': lines, 'status': status})

    def handle_download_pcap(self):
        """Serve the captured pcap data as a file download."""
        data = capture_state['pcap_data']
        if not data:
            self.send_error(404, 'No capture data available')
            return

        hostname = ''
        try:
            hostname = cp.get('config/system/system_id') or 'router'
        except Exception:
            hostname = 'router'

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = hostname + '_' + ts + '.pcap'

        self.send_response(200)
        self.send_header('Content-Type', 'application/vnd.tcpdump.pcap')
        self.send_header('Content-Disposition',
                         'attachment; filename="' + filename + '"')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, obj):
        """Send a JSON response."""
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass


def warmup_auth(username, password):
    """Make a throwaway request to absorb the first-login 302 redirect."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        auth_str = base64.b64encode(
            (username + ':' + password).encode()).decode()
        headers = {'Authorization': 'Basic ' + auth_str}

        conn = http.client.HTTPSConnection('127.0.0.1', context=ctx)
        conn.request('GET', '/api/status/system', headers=headers)
        resp = conn.getresponse()
        resp.read()  # drain body
        cp.log('Auth warmup: HTTP ' + str(resp.status))
        conn.close()

        # If we got 302, do it again — second request should succeed
        if resp.status == 302:
            conn = http.client.HTTPSConnection('127.0.0.1', context=ctx)
            conn.request('GET', '/api/status/system', headers=headers)
            resp = conn.getresponse()
            resp.read()
            cp.log('Auth warmup retry: HTTP ' + str(resp.status))
            conn.close()

        return resp.status == 200
    except Exception as e:
        cp.log('Auth warmup error: ' + str(e))
        return False


def main():
    """Main entry point."""
    global CAPTURE_PASS
    cp.log('Starting tcpdumpster...')

    # Create temp user for tcpdump API auth (reused for all captures)
    for attempt in range(3):
        try:
            user_result = cp.ensure_fresh_user(CAPTURE_USER, 'admin')
            if user_result and user_result.get('success'):
                CAPTURE_PASS = user_result.get('password', '')
                cp.log('Created capture user ' + CAPTURE_USER
                       + ' (attempt ' + str(attempt + 1) + ')')

                # Warm up the auth — absorbs the first-login 302 redirect
                if warmup_auth(CAPTURE_USER, CAPTURE_PASS):
                    cp.log('Auth warmup succeeded')
                else:
                    cp.log('WARNING: Auth warmup did not get 200')
                break
            else:
                err = (user_result.get('error', 'unknown')
                       if user_result else 'None returned')
                cp.log('WARNING: Failed to create capture user (attempt '
                       + str(attempt + 1) + '): ' + str(err))
        except Exception as e:
            cp.log('WARNING: Error creating capture user (attempt '
                   + str(attempt + 1) + '): ' + str(e))
        if attempt < 2:
            time.sleep(2)

    if not CAPTURE_PASS:
        cp.log('ERROR: Could not create capture user after 3 attempts')

    # SO_REUSEADDR must be set before bind - override server_bind
    class ReusableHTTPServer(http.server.HTTPServer):
        allow_reuse_address = True

    server = ReusableHTTPServer(('', PORT), TCPDumpsterHandler)

    cp.log('Web server started on port ' + str(PORT))

    try:
        server.serve_forever()
    except Exception as e:
        cp.log('Server error: ' + str(e))
    finally:
        cp.log('Shutting down — cleaning up capture user...')
        try:
            cp.delete_user(CAPTURE_USER)
            cp.log('Deleted capture user ' + CAPTURE_USER)
        except Exception as e:
            cp.log('Warning: failed to delete capture user: ' + str(e))


if __name__ == '__main__':
    main()
