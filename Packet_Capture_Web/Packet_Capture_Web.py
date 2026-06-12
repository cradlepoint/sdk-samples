"""Packet_Capture_Web - Web interface for packet capture management.
Provides a UI for configuring, running, and managing packet captures on
Cradlepoint routers. Supports Download, CloudShark, and Custom URL modes."""

import cp
import os
import sys
import json
import time
import threading
import socket
import signal
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

PORT = 8000
CAPTURES_DIR = 'captures'
META_DIR = 'captures/meta'

# Global state
capture_running = False
capture_status = ''
capture_thread = None
capture_loop = False
capture_stop_requested = False
disk_alert_sent = False
server = None

os.makedirs(CAPTURES_DIR, exist_ok=True)
os.makedirs(META_DIR, exist_ok=True)


def load_defaults():
    """Load saved defaults from appdata."""
    try:
        val = cp.get_appdata('pcap_defaults')
        if val and isinstance(val, str) and val.strip():
            return json.loads(val)
    except Exception as e:
        cp.log('Error loading defaults from appdata: ' + str(e))
    return {}


def save_defaults_file(options):
    """Save defaults to appdata."""
    try:
        # Include auto_start in the saved options
        cp.put_appdata('pcap_defaults', json.dumps(options))
        return True
    except Exception as e:
        cp.log('Error saving defaults to appdata: ' + str(e))
        return False


def get_interfaces():
    """Get available network interfaces matching NCOS style."""
    interfaces = [{'value': 'any', 'label': 'Any'}]
    seen_ifaces = set()

    # --- WAN devices (individual modem/ethernet ifaces) ---
    device_profile_map = {}
    try:
        wan_devs = cp.get('status/wan/devices')
        if wan_devs and isinstance(wan_devs, dict):
            for uid, dev in wan_devs.items():
                if not isinstance(dev, dict):
                    continue
                config = dev.get('config', {}) or {}
                profile_id = config.get('_id_', '')
                if profile_id:
                    device_profile_map[uid] = profile_id
                info = dev.get('info', {}) or {}
                iface = info.get('iface', '')
                if iface:
                    diag = dev.get('diagnostics', {}) or {}
                    carrier = (diag.get('CARRID') or '').strip()
                    if uid.startswith('mdm-'):
                        short_id = uid.replace('mdm-', '')[:8]
                        parts = [short_id]
                        if carrier:
                            parts.append(carrier)
                        label = '-'.join(parts) + ' (wan)'
                    else:
                        label = uid + ' (wan)'
                    interfaces.append({'value': iface, 'label': label})
                    seen_ifaces.add(iface)
    except Exception as e:
        cp.log('Error getting WAN devices: ' + str(e))

    # --- WAN profiles (trigger_name only) ---
    try:
        rules = cp.get('config/wan/rules2')
        if rules and isinstance(rules, list):
            for rule in rules:
                if isinstance(rule, dict):
                    rule_id = rule.get('_id_', '')
                    trigger_name = rule.get('trigger_name', '')
                    if rule_id and trigger_name:
                        label = trigger_name + ' (wan profile)'
                        interfaces.append({
                            'value': rule_id,
                            'label': label
                        })
    except Exception as e:
        cp.log('Error getting WAN rules: ' + str(e))

    # --- LAN Networks (from config/lan for UUIDs + status for names) ---
    try:
        lan_config = cp.get('config/lan')
        if lan_config and isinstance(lan_config, list):
            for item in lan_config:
                if not isinstance(item, dict):
                    continue
                net_name = item.get('name', '')
                net_uuid = item.get('_id_', '')
                if net_name and net_uuid:
                    label = net_name + ' (network)'
                    interfaces.append({
                        'value': net_uuid,
                        'label': label
                    })
    except Exception as e:
        cp.log('Error getting LAN networks: ' + str(e))

    # --- Build SSID map from wlan config ---
    ssid_map = {}
    try:
        wlan_config = cp.get('config/wlan')
        if wlan_config and isinstance(wlan_config, dict):
            radio_list = wlan_config.get('radio', []) or []
            if isinstance(radio_list, list):
                for radio_idx, radio in enumerate(radio_list):
                    if not isinstance(radio, dict):
                        continue
                    bss_list = radio.get('bss', []) or []
                    for bss_idx, bss in enumerate(bss_list):
                        if isinstance(bss, dict):
                            bss_ssid = bss.get('ssid', '')
                            if bss_ssid and bss_ssid != 'unconfigured':
                                if bss_idx == 0:
                                    key = 'wireless' + str(radio_idx)
                                else:
                                    key = ('wireless' + str(radio_idx)
                                           + '_' + str(bss_idx))
                                ssid_map[key] = bss_ssid
    except Exception as e:
        cp.log('Error getting WLAN config for SSIDs: ' + str(e))

    # --- LAN device interfaces ---
    try:
        lan_devs = cp.get('status/lan/devices')
        if lan_devs and isinstance(lan_devs, dict):
            for uid, dev in lan_devs.items():
                if not isinstance(dev, dict):
                    continue
                info = dev.get('info', {}) or {}
                iface = info.get('iface', '')
                if iface and iface not in seen_ifaces:
                    is_wlan = 'wlan' in uid or 'wireless' in uid
                    if is_wlan:
                        # WLAN: "{SSID} (WLAN 2.4GHz/5GHz)"
                        freq = '2.4GHz'
                        if 'wireless1' in uid:
                            freq = '5GHz'
                        wlan_key = uid.replace('wlan-', '')
                        ssid = ssid_map.get(wlan_key, uid)
                        label = ssid + ' (WLAN ' + freq + ')'
                    else:
                        # Ethernet LAN: "VLAN {vid} - {uid}"
                        vid = info.get('vid', '')
                        if vid:
                            label = 'VLAN ' + str(vid) + ' - ' + uid
                        else:
                            label = uid + ' (lan)'
                    interfaces.append({
                        'value': iface,
                        'label': label
                    })
                    seen_ifaces.add(iface)
    except Exception as e:
        cp.log('Error getting LAN devices: ' + str(e))

    return interfaces


def get_capture_files():
    """Get list of saved capture files with metadata."""
    files = []
    try:
        if not os.path.exists(CAPTURES_DIR):
            return files
        for fname in os.listdir(CAPTURES_DIR):
            fpath = os.path.join(CAPTURES_DIR, fname)
            if os.path.isfile(fpath) and fname.endswith('.pcap'):
                stat = os.stat(fpath)
                meta = load_meta(fname)
                pkt_count = None
                if meta and 'packet_count' in meta:
                    pkt_count = meta.get('packet_count')
                files.append({
                    'filename': fname,
                    'size': stat.st_size,
                    'datetime': datetime.fromtimestamp(
                        stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'timestamp': stat.st_mtime,
                    'options': meta,
                    'packets': pkt_count
                })
        files.sort(key=lambda x: x['timestamp'], reverse=True)
    except Exception as e:
        cp.log('Error listing capture files: ' + str(e))
    return files


def save_meta(filename, options):
    """Save capture options metadata for a file."""
    try:
        meta_path = os.path.join(META_DIR, filename + '.json')
        with open(meta_path, 'w') as f:
            f.write(json.dumps(options))
    except Exception as e:
        cp.log('Error saving meta for ' + filename + ': ' + str(e))


def load_meta(filename):
    """Load capture options metadata for a file."""
    try:
        meta_path = os.path.join(META_DIR, filename + '.json')
        if os.path.exists(meta_path):
            with open(meta_path, 'r') as f:
                return json.loads(f.read())
    except Exception as e:
        cp.log('Error loading meta for ' + filename + ': ' + str(e))
    return None


def count_pcap_packets(filepath):
    """Count packets in a pcap file by reading record headers."""
    try:
        count = 0
        with open(filepath, 'rb') as f:
            header = f.read(24)
            if len(header) < 24:
                return 0
            while True:
                rec_hdr = f.read(16)
                if len(rec_hdr) < 16:
                    break
                incl_len = int.from_bytes(rec_hdr[8:12], 'little')
                f.seek(incl_len, 1)
                count += 1
        return count
    except Exception as e:
        cp.log('Error counting packets: ' + str(e))
    return None


def get_disk_usage():
    """Get disk usage from router."""
    try:
        data = cp.get('status/mount/disk_usage')
        if data and isinstance(data, dict):
            free = data.get('free_bytes', 0)
            total = data.get('total_bytes', 1)
            used = total - free
            pct = round((used / total) * 100, 1) if total > 0 else 0
            return {
                'free_bytes': free,
                'total_bytes': total,
                'used_bytes': used,
                'percent_used': pct
            }
    except Exception as e:
        cp.log('Error getting disk usage: ' + str(e))
    return {'free_bytes': 0, 'total_bytes': 1, 'used_bytes': 0,
            'percent_used': 0}


def delete_oldest_capture():
    """Delete the oldest capture file. Returns filename or None."""
    try:
        files = []
        for fname in os.listdir(CAPTURES_DIR):
            fpath = os.path.join(CAPTURES_DIR, fname)
            if os.path.isfile(fpath) and fname.endswith('.pcap'):
                files.append((fpath, os.stat(fpath).st_mtime, fname))
        if not files:
            return None
        files.sort(key=lambda x: x[1])
        oldest_path, _, oldest_name = files[0]
        os.remove(oldest_path)
        meta_path = os.path.join(META_DIR, oldest_name + '.json')
        if os.path.exists(meta_path):
            os.remove(meta_path)
        cp.log('Deleted oldest capture: ' + oldest_name)
        return oldest_name
    except Exception as e:
        cp.log('Error deleting oldest capture: ' + str(e))
    return None


def check_disk_threshold(threshold_pct, action, send_alert=False):
    """Check if disk is over threshold. Returns True if capture should stop."""
    global disk_alert_sent
    disk = get_disk_usage()
    if disk['percent_used'] >= threshold_pct:
        cp.log('Disk threshold reached: ' + str(disk['percent_used'])
               + '% used (threshold: ' + str(threshold_pct) + '%)')
        # Send alert once
        if send_alert and not disk_alert_sent:
            free_mb = int(disk['free_bytes'] / 1048576)
            total_mb = int(disk['total_bytes'] / 1048576)
            used_mb = int(disk['used_bytes'] / 1048576)
            msg = ('Disk ' + str(disk['percent_used']) + '% full ('
                   + str(used_mb) + ' MB used / '
                   + str(total_mb) + ' MB total, '
                   + str(free_mb) + ' MB free)')
            try:
                cp.alert(msg)
                cp.log('Disk alert sent: ' + msg)
            except Exception as e:
                cp.log('Error sending disk alert: ' + str(e))
            disk_alert_sent = True
        if action == 'delete_oldest':
            deleted = delete_oldest_capture()
            if deleted:
                # Re-check after delete
                disk2 = get_disk_usage()
                if disk2['percent_used'] >= threshold_pct:
                    return True  # Still over, stop
                return False  # Freed enough, continue
            return True  # Nothing to delete, stop
        else:
            return True  # action == 'stop'
    else:
        # Below threshold — reset alert flag
        if disk_alert_sent:
            disk_alert_sent = False
    return False


def generate_capture_filename():
    """Generate filename as {router_name}_{datetime}.pcap."""
    try:
        router_name = cp.get('config/system/system_id') or 'router'
        # Sanitize: only allow alphanumeric, dash, underscore
        safe_name = ''
        for c in router_name:
            if c.isalnum() or c in ('-', '_'):
                safe_name += c
            else:
                safe_name += '_'
        if not safe_name:
            safe_name = 'router'
    except Exception as e:
        cp.log('Error getting system_id for filename: ' + str(e))
        safe_name = 'router'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return safe_name + '_' + timestamp + '.pcap'


def run_capture(options):
    """Run a packet capture with the given options. Supports looping."""
    global capture_running, capture_status, capture_loop
    global capture_stop_requested
    capture_running = True
    capture_stop_requested = False
    loop_enabled = options.get('loop', False)
    threshold_pct = float(options.get('disk_threshold', 80))
    disk_action = options.get('disk_action', 'stop')
    send_alert = options.get('send_alert', False)
    iteration = 0

    # Check disk BEFORE doing anything
    disk = get_disk_usage()
    if disk['percent_used'] >= threshold_pct:
        capture_status = ('Stopped: disk already at '
                          + str(disk['percent_used']) + '% (limit '
                          + str(threshold_pct) + '%)')
        cp.log('Capture not started: disk at '
               + str(disk['percent_used']) + '% >= '
               + str(threshold_pct) + '%')
        capture_running = False
        return

    # Credentials for tcpdump REST API
    capture_user = None
    capture_password = None

    try:
        import urllib.request
        import urllib.parse
        import urllib.error

        interface = options.get('interface', 'any')
        iface_label = options.get('interface_label', interface)
        arguments = options.get('arguments', '')
        timeout_val = int(options.get('timeout', 30))
        count_val = int(options.get('count', 0))
        mode = options.get('mode', 'download')
        url = options.get('url', '')
        cloudshark_token = options.get('cloudshark_token', '')

        # Build URL based on mode
        capture_url = ''
        if mode == 'cloudshark' and cloudshark_token:
            capture_url = ('https://www.cloudshark.org/captures?token='
                           + cloudshark_token)
        elif mode == 'custom' and url:
            capture_url = url

        # Create a dedicated user for tcpdump REST access
        # Use alphanumeric-only password to avoid HTTP Basic Auth issues
        capture_status = 'Setting up capture user...'
        temp_user = 'SDKTCPDUMP'
        # Delete existing user first
        try:
            cp.delete_user(temp_user)
            time.sleep(3)  # Wait for shadow file cleanup
        except Exception:
            pass
        # Generate safe password (alphanumeric only)
        import hashlib
        safe_pw = hashlib.md5(
            str(time.time()).encode()
        ).hexdigest()[:16]
        create_result = cp.create_user(temp_user, safe_pw, 'admin')
        if not create_result or not create_result.get('success'):
            capture_status = ('Error: Failed to create capture user: '
                              + str(create_result))
            cp.log('Failed to create capture user: '
                   + str(create_result))
            return
        capture_user = temp_user
        capture_password = safe_pw
        cp.log('Capture user created, waiting for auth propagation')

        # Get router IP for REST calls
        device_ip = cp.get('config/lan/0/ip_address') or '127.0.0.1'

        # Wait for auth system to recognize user, verify with test
        auth_ready = False
        for attempt in range(5):
            time.sleep(2)
            try:
                test_url = 'http://' + device_ip + '/api/status/fw_info'
                pwd_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
                pwd_mgr.add_password(
                    None, 'http://' + device_ip,
                    capture_user, capture_password)
                auth_handler = urllib.request.HTTPBasicAuthHandler(
                    pwd_mgr)
                test_opener = urllib.request.build_opener(auth_handler)
                test_opener.open(test_url, timeout=5)
                auth_ready = True
                cp.log('Auth verified on attempt ' + str(attempt + 1))
                break
            except urllib.error.HTTPError as he:
                if he.code == 401:
                    cp.log('Auth not ready, attempt '
                           + str(attempt + 1) + '/5')
                    continue
                auth_ready = True
                break
            except Exception as te:
                cp.log('Auth test error: ' + str(te))
                continue

        if not auth_ready:
            capture_status = 'Error: Auth not ready after retries'
            cp.log('User created but auth never became ready')
            return

        cp.log('Capture user ready: ' + capture_user)

        # Create opener for all capture modes
        pwd_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        pwd_mgr.add_password(None, 'http://' + device_ip,
                             capture_user, capture_password)
        auth_handler = urllib.request.HTTPBasicAuthHandler(pwd_mgr)
        opener = urllib.request.build_opener(auth_handler)

        # === STREAM MODE ===
        if options.get('stream', False):
            capture_stop_requested = False  # Ensure clean state
            capture_status = 'Streaming on ' + iface_label + '...'
            cp.log('Starting stream capture: interface=' + interface
                   + ' filter=' + arguments)

            params = {
                'iface': interface,
                'args': arguments,
                'wifichannel': '',
                'wifichannelwidth': '',
                'wifiextrachannel': '',
                'timeout': 86400,
                'count': '',
                'url': capture_url
            }
            query = urllib.parse.urlencode(params)
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            pcap_filename = timestamp + '.pcap'
            tcpdump_url = ('http://localhost/api/tcpdump/'
                           + pcap_filename + '?' + query)

            final_name = generate_capture_filename()
            local_path = os.path.join(CAPTURES_DIR, final_name)
            stop_reason = ''

            # Save meta immediately with unknown stop reason
            # so if app is killed, the file still has options
            meta_initial = dict(options)
            meta_initial['stop_reason'] = 'unknown'
            save_meta(final_name, meta_initial)

            try:
                import requests as req
                # Flush any stale capture with a 1-second throwaway
                flush_params = {
                    'iface': interface,
                    'args': arguments,
                    'wifichannel': '',
                    'wifichannelwidth': '',
                    'wifiextrachannel': '',
                    'timeout': 1,
                    'count': 1,
                    'url': ''
                }
                flush_query = urllib.parse.urlencode(flush_params)
                flush_url = ('http://localhost/api/tcpdump/flush.pcap?'
                             + flush_query)
                try:
                    flush_resp = req.get(
                        flush_url,
                        auth=(capture_user, capture_password),
                        timeout=5
                    )
                    flush_resp.close()
                except Exception:
                    pass
                cp.log('Stream: opening ' + tcpdump_url)
                resp = req.get(
                    tcpdump_url,
                    auth=(capture_user, capture_password),
                    stream=True,
                    timeout=None
                )
                cp.log('Stream: status=' + str(resp.status_code)
                       + ' encoding='
                       + str(resp.headers.get(
                           'Transfer-Encoding', 'none')))
                if resp.status_code != 200:
                    capture_status = ('Error: HTTP '
                                      + str(resp.status_code))
                    cp.log('Stream HTTP error: '
                           + str(resp.status_code))
                    return
                total_bytes = 0
                disk_check_counter = 0
                with open(local_path, 'wb') as out_f:
                    for chunk in resp.iter_content(
                            chunk_size=4096):
                        if capture_stop_requested:
                            break
                        if chunk:
                            out_f.write(chunk)
                            out_f.flush()
                            total_bytes += len(chunk)
                            size_kb = total_bytes / 1024
                            if size_kb < 1024:
                                size_str = (str(int(size_kb))
                                            + ' KB')
                            else:
                                size_str = (
                                    str(round(size_kb / 1024, 1))
                                    + ' MB')
                            capture_status = ('Streaming: '
                                              + size_str
                                              + ' captured')
                            disk_check_counter += 1
                            if disk_check_counter >= 25:
                                disk_check_counter = 0
                                if check_disk_threshold(
                                        threshold_pct,
                                        disk_action,
                                        send_alert):
                                    stop_reason = 'disk_full'
                                    capture_status = (
                                        'Stopped: disk threshold'
                                        ' (' + size_str
                                        + ' saved)')
                                    cp.log('Stream stopped: disk'
                                           ' threshold at '
                                           + str(total_bytes)
                                           + ' bytes')
                                    break
                resp.close()
                cp.log('Stream ended: ' + str(total_bytes)
                       + ' bytes written')
            except Exception as e:
                if not capture_stop_requested:
                    cp.log('Stream error: ' + str(e))
                    stop_reason = 'error'

            # Determine stop reason if not already set
            if capture_stop_requested and stop_reason == '':
                stop_reason = 'user_stop'

            # Save if we got data
            if (os.path.exists(local_path)
                    and os.path.getsize(local_path) > 24):
                meta = dict(options)
                meta['stop_reason'] = stop_reason
                meta['packet_count'] = count_pcap_packets(local_path)
                save_meta(final_name, meta)
                fsize = os.path.getsize(local_path)
                reason_text = ''
                if stop_reason == 'disk_full':
                    reason_text = ' [disk full]'
                elif stop_reason == 'user_stop':
                    reason_text = ' [stopped]'
                capture_status = ('Stream saved: ' + final_name
                                  + ' (' + str(int(fsize / 1024))
                                  + ' KB)' + reason_text)
                cp.log('Stream saved: ' + final_name + ' ('
                       + str(fsize) + ' bytes) reason='
                       + stop_reason)
            elif os.path.exists(local_path):
                os.remove(local_path)
                capture_status = 'Stream ended (no data captured)'
            else:
                capture_status = 'Stream ended (no file)'
            return

        # === LOOP/NORMAL MODE ===
        while True:
            if capture_stop_requested:
                capture_status = 'Stopped by user'
                break

            # Check disk before starting
            if check_disk_threshold(threshold_pct, disk_action,
                                    send_alert):
                capture_status = 'Stopped: disk threshold reached'
                cp.log('Capture stopped: disk threshold')
                break

            iteration += 1
            suffix = (' (loop ' + str(iteration) + ')'
                      if loop_enabled else '')
            capture_status = ('Capturing on ' + iface_label
                              + '...' + suffix)
            cp.log('Starting capture' + suffix + ': interface='
                   + interface + ' filter=' + arguments
                   + ' timeout=' + str(timeout_val)
                   + ' count=' + str(count_val))

            # Generate filename
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            pcap_filename = timestamp + '.pcap'

            # Build tcpdump REST URL
            params = {
                'iface': interface,
                'args': arguments,
                'wifichannel': '',
                'wifichannelwidth': '',
                'wifiextrachannel': '',
                'timeout': timeout_val,
                'count': count_val,
                'url': capture_url
            }
            query = urllib.parse.urlencode(params)
            tcpdump_url = ('http://' + device_ip + '/api/tcpdump/'
                           + pcap_filename + '?' + query)

            # The tcpdump API blocks until capture is done, then
            # returns pcap binary data
            final_name = generate_capture_filename()
            local_path = os.path.join(CAPTURES_DIR, final_name)

            capture_start_time = time.time()
            try:
                urllib.request.install_opener(opener)
                # Use urlopen with timeout instead of urlretrieve
                # to prevent hanging on down interfaces
                req_timeout = timeout_val + 30  # grace period
                response = opener.open(
                    tcpdump_url, timeout=req_timeout)
                with open(local_path, 'wb') as out_f:
                    while True:
                        chunk = response.read(65536)
                        if not chunk:
                            break
                        out_f.write(chunk)
                response.close()
            except urllib.error.HTTPError as e:
                if capture_stop_requested:
                    capture_status = 'Stopped by user'
                    break
                capture_status = 'Error: HTTP ' + str(e.code) + suffix
                cp.log('Capture HTTP error: ' + str(e))
                break
            except Exception as e:
                if capture_stop_requested:
                    capture_status = 'Stopped by user'
                    break
                capture_status = 'Error: ' + str(e) + suffix
                cp.log('Capture error: ' + str(e))
                break

            capture_elapsed = time.time() - capture_start_time

            # Verify file was saved
            if os.path.exists(local_path):
                file_size = os.path.getsize(local_path)
                if file_size > 0:
                    # Check for suspiciously fast completion
                    if (timeout_val > 10
                            and capture_elapsed < 5
                            and count_val == 0):
                        os.remove(local_path)
                        capture_status = ('Warning: capture completed '
                                          'in ' + str(int(capture_elapsed))
                                          + 's (interface may be down)'
                                          + suffix)
                        cp.log('Capture too fast ('
                               + str(int(capture_elapsed))
                               + 's for ' + str(timeout_val)
                               + 's timeout) - interface likely down')
                        break
                    meta_dl = dict(options)
                    meta_dl['packet_count'] = count_pcap_packets(
                        local_path)
                    save_meta(final_name, meta_dl)
                    capture_status = 'Saved: ' + final_name + suffix
                    cp.log('Capture saved: ' + final_name
                           + ' (' + str(file_size) + ' bytes)')
                else:
                    os.remove(local_path)
                    capture_status = 'Error: Empty capture' + suffix
                    cp.log('Empty capture file, removed')
                    break
            else:
                capture_status = 'Error: File not saved' + suffix
                cp.log('Capture file not found at ' + local_path)
                break

            if not loop_enabled:
                break

            # Brief pause between loops
            time.sleep(2)

    except Exception as e:
        capture_status = 'Error: ' + str(e)
        cp.log('Capture error: ' + str(e))
    finally:
        capture_running = False
        capture_loop = False
        # Clean up capture user
        try:
            cp.delete_user('SDKTCPDUMP')
            cp.log('Deleted capture user SDKTCPDUMP')
        except Exception as e:
            cp.log('Error deleting capture user: ' + str(e))


def stop_capture():
    """Stop a running capture."""
    global capture_status, capture_stop_requested
    capture_stop_requested = True
    try:
        cp.stop_packet_capture()
        capture_status = 'Stopping...'
        cp.log('Capture stop requested')
    except Exception as e:
        capture_status = 'Error stopping: ' + str(e)
        cp.log('Error stopping capture: ' + str(e))


class CaptureHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the packet capture web interface."""

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def send_json(self, data, status=200):
        """Send a JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def send_file(self, filepath, content_type, filename=None):
        """Send a file response."""
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            if filename:
                self.send_header('Content-Disposition',
                                 'attachment; filename="' + filename + '"')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_json({'error': str(e)}, 500)

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == '/' or path == '/index.html':
            self.serve_index()
        elif path == '/api/interfaces':
            self.send_json(get_interfaces())
        elif path == '/api/status':
            self.send_json({
                'running': capture_running,
                'status': capture_status
            })
        elif path == '/api/disk':
            self.send_json(get_disk_usage())
        elif path == '/api/defaults':
            self.send_json(load_defaults())
        elif path == '/api/files':
            self.send_json(get_capture_files())
        elif path.startswith('/api/download/'):
            filename = unquote(path[14:])
            filepath = os.path.join(CAPTURES_DIR, filename)
            if os.path.exists(filepath) and '..' not in filename:
                self.send_file(filepath, 'application/octet-stream', filename)
            else:
                self.send_json({'error': 'File not found'}, 404)
        elif path.startswith('/api/meta/'):
            filename = unquote(path[10:])
            meta = load_meta(filename)
            if meta:
                self.send_json(meta)
            else:
                self.send_json({'error': 'No metadata found'}, 404)
        elif path.startswith('/static/'):
            self.serve_static(path)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'

        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {}

        if path == '/api/start':
            self.handle_start(data)
        elif path == '/api/stop':
            self.handle_stop()
        elif path == '/api/defaults':
            if save_defaults_file(data):
                self.send_json({'success': True})
            else:
                self.send_json({'error': 'Failed to save'}, 500)
        elif path == '/api/autostart':
            defaults = load_defaults()
            current = defaults.get('auto_start', False)
            defaults['auto_start'] = not current
            if save_defaults_file(defaults):
                self.send_json({'success': True,
                                'auto_start': not current})
            else:
                self.send_json({'error': 'Failed to save'}, 500)
        elif path == '/api/rename':
            self.handle_rename(data)
        elif path == '/api/delete':
            self.handle_delete(data)
        else:
            self.send_json({'error': 'Not found'}, 404)

    def handle_start(self, data):
        """Start a packet capture."""
        global capture_thread, capture_running
        if capture_running:
            self.send_json({'error': 'Capture already running'}, 400)
            return
        # Wait for previous thread to fully exit
        if capture_thread and capture_thread.is_alive():
            capture_thread.join(timeout=5)
        capture_thread = threading.Thread(target=run_capture, args=(data,))
        capture_thread.daemon = True
        capture_thread.start()
        self.send_json({'success': True, 'message': 'Capture started'})

    def handle_stop(self):
        """Stop a running capture."""
        if not capture_running:
            self.send_json({'error': 'No capture running'}, 400)
            return
        stop_capture()
        self.send_json({'success': True, 'message': 'Capture stopped'})

    def handle_rename(self, data):
        """Rename a capture file."""
        old_name = data.get('old_name', '')
        new_name = data.get('new_name', '')
        if not old_name or not new_name:
            self.send_json({'error': 'Missing filename'}, 400)
            return
        if not new_name.endswith('.pcap'):
            new_name = new_name + '.pcap'
        if '..' in old_name or '..' in new_name:
            self.send_json({'error': 'Invalid filename'}, 400)
            return
        old_path = os.path.join(CAPTURES_DIR, old_name)
        new_path = os.path.join(CAPTURES_DIR, new_name)
        if not os.path.exists(old_path):
            self.send_json({'error': 'File not found'}, 404)
            return
        if os.path.exists(new_path):
            self.send_json({'error': 'File already exists'}, 400)
            return
        try:
            os.rename(old_path, new_path)
            # Rename meta too
            old_meta = os.path.join(META_DIR, old_name + '.json')
            new_meta = os.path.join(META_DIR, new_name + '.json')
            if os.path.exists(old_meta):
                os.rename(old_meta, new_meta)
            self.send_json({'success': True, 'new_name': new_name})
        except Exception as e:
            self.send_json({'error': str(e)}, 500)

    def handle_delete(self, data):
        """Delete a capture file."""
        filename = data.get('filename', '')
        if not filename or '..' in filename:
            self.send_json({'error': 'Invalid filename'}, 400)
            return
        filepath = os.path.join(CAPTURES_DIR, filename)
        if not os.path.exists(filepath):
            self.send_json({'error': 'File not found'}, 404)
            return
        try:
            os.remove(filepath)
            meta_path = os.path.join(META_DIR, filename + '.json')
            if os.path.exists(meta_path):
                os.remove(meta_path)
            self.send_json({'success': True})
        except Exception as e:
            self.send_json({'error': str(e)}, 500)

    def serve_index(self):
        """Serve the main index.html page."""
        try:
            with open('index.html', 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(('Error: ' + str(e)).encode('utf-8'))

    def serve_static(self, path):
        """Serve static files."""
        # Remove leading slash
        filepath = path[1:]
        if '..' in filepath:
            self.send_response(403)
            self.end_headers()
            return
        if not os.path.exists(filepath):
            self.send_response(404)
            self.end_headers()
            return

        content_types = {
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.html': 'text/html',
            '.woff': 'font/woff',
            '.woff2': 'font/woff2',
            '.ttf': 'font/ttf',
            '.svg': 'image/svg+xml',
            '.png': 'image/png',
            '.ico': 'image/x-icon'
        }
        ext = os.path.splitext(filepath)[1].lower()
        content_type = content_types.get(ext, 'application/octet-stream')

        try:
            with open(filepath, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_response(500)
            self.end_headers()


def start_server():
    """Start the HTTP server."""
    global server
    try:
        server = HTTPServer(('', PORT), CaptureHandler)
        server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.serve_forever()
    except Exception as e:
        cp.log('Error starting web server: ' + str(e))


def backfill_packet_counts():
    """Count packets for any pcap files missing packet_count in meta."""
    try:
        if not os.path.exists(CAPTURES_DIR):
            return
        for fname in os.listdir(CAPTURES_DIR):
            fpath = os.path.join(CAPTURES_DIR, fname)
            if not os.path.isfile(fpath) or not fname.endswith('.pcap'):
                continue
            meta = load_meta(fname)
            if meta and 'packet_count' in meta:
                continue
            # Count packets and update meta
            count = count_pcap_packets(fpath)
            if count is not None:
                if meta is None:
                    meta = {}
                meta['packet_count'] = count
                save_meta(fname, meta)
                cp.log('Backfill: ' + fname + ' = '
                       + str(count) + ' packets')
    except Exception as e:
        cp.log('Error in backfill_packet_counts: ' + str(e))


def main():
    """Main entry point."""
    # Start web server in a thread
    server_thread = threading.Thread(target=start_server)
    server_thread.daemon = True
    server_thread.start()

    cp.log('Packet_Capture_Web running on port ' + str(PORT))

    # Backfill packet counts for existing files
    try:
        backfill_packet_counts()
    except Exception as e:
        cp.log('Backfill error: ' + str(e))

    # Auto-start capture if enabled in defaults
    try:
        defaults = load_defaults()
        if defaults.get('auto_start', False):
            cp.log('Auto-start enabled, starting capture...')
            # Ensure stream flag matches mode
            if defaults.get('mode') == 'stream':
                defaults['stream'] = True
            time.sleep(3)  # Let web server settle
            auto_thread = threading.Thread(
                target=run_capture, args=(defaults,))
            auto_thread.daemon = True
            auto_thread.start()
    except Exception as e:
        cp.log('Auto-start error: ' + str(e))

    # Keep main thread alive
    try:
        while True:
            time.sleep(60)
    except Exception as e:
        cp.log('Main loop error: ' + str(e))
    finally:
        if server:
            server.shutdown()
        cp.log('Packet_Capture_Web stopped')


if __name__ == '__main__':
    main()
