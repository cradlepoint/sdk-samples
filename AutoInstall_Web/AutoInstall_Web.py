"""AutoInstall_Web - AutoInstall SIM Installer Application
Web interface that accepts a password, and when entered correctly, runs the auto-install process.
Detects SIMs per appdata sims (all, local, or captive), tests each with Ookla speed test,
collects diagnostics. Default: reprioritizes WAN profiles by download speed. When group_by_sim or
group_by_carrier is set, only moves router to NCM group (no WAN config changes). If appdata autostart
is set, starts the process automatically without user input."""

import cp
import tornado.web
import json
import time
import threading
import datetime
import os
import re
import configparser
import mimetypes
import socket
import requests
from speedtest_ookla import Speedtest
import ncm

def get_ui_logo():
    """Get base64 logo from appdata 'logo' (case insensitive). Returns None if not set."""
    val = get_config('logo')
    if val is None or not str(val).strip():
        return None
    s = str(val).strip()
    if s.startswith('data:'):
        return s
    return 'data:image/png;base64,' + s

def get_ui_logo_dark():
    """Get base64 dark-mode logo from appdata 'logo_dark' (case insensitive). Returns None if not set."""
    val = get_config('logo_dark')
    if val is None or not str(val).strip():
        return None
    s = str(val).strip()
    if s.startswith('data:'):
        return s
    return 'data:image/png;base64,' + s

def get_ui_title():
    """Get panel title from appdata 'title' (case insensitive). Default 'AutoInstall'."""
    val = get_config('title')
    if val is not None and str(val).strip():
        return str(val).strip()
    return 'AutoInstall'

def get_ui_text():
    """Get intro text from appdata 'text' (case insensitive). Default 'Enter password to start auto-install process.'"""
    val = get_config('text')
    if val is not None and str(val).strip():
        return str(val).strip()
    return 'Enter password to start auto-install process.'

class FaviconHandler(tornado.web.RequestHandler):
    """Avoid 404 for favicon.ico and similar browser requests."""
    def get(self):
        self.set_status(204)
        self.finish()

class DefaultHandler(tornado.web.RequestHandler):
    """Catch unmatched requests to avoid 404 Future exception."""
    def get(self):
        self.set_status(204)
        self.finish()

    def head(self):
        self.set_status(204)
        self.finish()

    def post(self):
        self.set_status(204)
        self.finish()

class FallbackStaticHandler(tornado.web.RequestHandler):
    """Serves static files if they exist; otherwise redirects to /. Avoids 404 Future exception."""
    def initialize(self, path):
        self.root = os.path.abspath(path)

    def _handle_path(self, path, write_body=True):
        if not path or path.endswith('/'):
            self.redirect('/')
            return
        abspath = os.path.abspath(os.path.join(self.root, path))
        if not abspath.startswith(self.root):
            self.redirect('/')
            return
        if os.path.isdir(abspath):
            self.redirect('/')
            return
        if not os.path.isfile(abspath):
            self.redirect('/')
            return
        content_type = mimetypes.guess_type(abspath)[0] or 'application/octet-stream'
        self.set_header('Content-Type', content_type)
        if write_body:
            with open(abspath, 'rb') as f:
                self.write(f.read())
        self.finish()

    def get(self, path):
        self._handle_path(path, write_body=True)

    def head(self, path):
        self._handle_path(path, write_body=False)

class MainHandler(tornado.web.RequestHandler):
    """Handles / endpoint requests."""
    def get(self):
        """Return index.html to UI."""
        self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.set_header('Pragma', 'no-cache')
        try:
            version = get_version()
            system_id = get_system_id()
            logo = get_ui_logo()
            logo_dark = get_ui_logo_dark()
            title = get_ui_title()
            text = get_ui_text()
            self.render("index.html", version=version, system_id=system_id, logo=logo, logo_dark=logo_dark, title=title, text=text)
        except Exception as e:
            cp.log(f'Error loading index.html: {e}')
            self.write('Error loading index.html')

class InstallHandler(tornado.web.RequestHandler):
    """Handles install/ endpoint requests."""
    def post(self):
        """Return install results JSON to UI."""
        installer_password = get_password()
        password_entered = self.get_argument('password_entered')
        
        if password_entered != installer_password:
            cp.log('Incorrect password entered')
            self.write(json.dumps({
                'success': False,
                'result': 'Incorrect Password!'
            }))
            return
        
        # Password correct, start auto-install process
        cp.log('Password correct, starting auto-install process')
        self.write(json.dumps({
            'success': True,
            'result': 'Starting auto-install process...'
        }))
        
        # Run auto-install in background
        thread = threading.Thread(target=run_auto_install)
        thread.daemon = True
        thread.start()

class CancelHandler(tornado.web.RequestHandler):
    """Handles cancel request to stop the running auto-install process."""
    def post(self):
        global install_cancelled
        install_cancelled = True
        cp.log('Auto-install cancel requested')
        self.write(json.dumps({'success': True, 'result': 'Cancel requested'}))

class StatusHandler(tornado.web.RequestHandler):
    """Handles status/ endpoint requests."""
    def get(self):
        """Return current installation status."""
        global switch_in_progress
        try:
            status_file = 'install_status.json'
            status = {'status': 'idle', 'message': '', 'progress': 0}
            try:
                with open(status_file, 'r') as f:
                    status = json.loads(f.read())
            except:
                pass
            status['switching'] = switch_in_progress
            self.write(json.dumps(status))
        except Exception as e:
            cp.log(f'Error getting status: {e}')
            self.write(json.dumps({'status': 'error', 'message': str(e)}))

class LogHandler(tornado.web.RequestHandler):
    """Handles log file download requests."""
    def get(self):
        """Return log file for download."""
        global log_filename
        try:
            self.set_header('Content-Type', 'text/plain')
            self.set_header('Content-Disposition', f'attachment; filename="{log_filename}"')
            try:
                with open(log_filename, 'r') as f:
                    self.write(f.read())
            except:
                self.write('Log file not found or empty.')
        except Exception as e:
            cp.log(f'Error getting log file: {e}')
            self.write(f'Error: {str(e)}')

class LogViewHandler(tornado.web.RequestHandler):
    """Handles log file viewing requests for UI display."""
    def get(self):
        """Return log file content and filename as JSON."""
        global log_filename
        try:
            try:
                with open(log_filename, 'r') as f:
                    content = f.read()
                self.write(json.dumps({'success': True, 'content': content, 'filename': log_filename}))
            except:
                self.write(json.dumps({'success': True, 'content': 'Log file not found or empty.'}))
        except Exception as e:
            cp.log(f'Error getting log file: {e}')
            self.write(json.dumps({'success': False, 'content': f'Error: {str(e)}'}))

class SignalHandler(tornado.web.RequestHandler):
    """Handles /signal endpoint for signal meter display."""
    def get(self):
        """Return connected SIM signal diagnostics for meter display. When switching, shows target SIM status."""
        global switch_in_progress, switch_target_sim
        try:
            sims = find_sims()
            all_available = all_sims_available(sims)
            try:
                with open('install_status.json', 'r') as f:
                    st = json.loads(f.read())
                install_running = st.get('status') == 'running'
                install_target_sim = st.get('target_sim')
            except Exception:
                install_running = False
                install_target_sim = None
            extra = {'all_sims_available': all_available, 'switching': switch_in_progress, 'install_running': install_running}
            display_sim = None
            connected_sim = None
            wan_devs = cp.get('status/wan/devices') or {}
            for uid, status in wan_devs.items():
                if uid.startswith('mdm-'):
                    conn_state = status.get('status', {}).get('connection_state')
                    if conn_state == 'connected':
                        connected_sim = uid
                        break
            if switch_in_progress and switch_target_sim:
                display_sim = switch_target_sim
            elif install_running and install_target_sim:
                display_sim = install_target_sim
            else:
                display_sim = connected_sim
            if not display_sim:
                summary_label = 'DISCONNECTED'
                port = None
                sim_slot = None
                carrier = None
                label = None
                for uid, dev_status in wan_devs.items():
                    if uid.startswith('mdm-'):
                        try:
                            s = cp.get(f'status/wan/devices/{uid}/status/summary')
                            if s is not None and str(s).strip():
                                summary_label = str(s).strip()
                            port = get_display_port(uid)
                            sim_slot = get_sim_slot(uid)
                            diag = cp.get(f'status/wan/devices/{uid}/diagnostics') or {}
                            if (diag.get('CARRID') or '').strip():
                                carrier = (diag.get('CARRID') or '').strip()
                            srvc = (diag.get('SRVC_TYPE') or '').strip().upper()
                            if srvc:
                                label = '5G' if ('5G' in srvc or 'NR' in srvc) else '4G'
                            break
                        except:
                            pass
                parts = [p for p in (port, sim_slot, carrier, label) if p]
                header = (' '.join(parts) + ': ' + summary_label) if parts else summary_label
                out = {'connected': False, 'disconnected': True, 'header': header}
                out.update(extra)
                self.write(json.dumps(out))
                return
            diagnostics = cp.get(f'status/wan/devices/{display_sim}/diagnostics') or {}
            carrier = (diagnostics.get('CARRID') or '').strip() or None
            port = get_display_port(display_sim)
            sim_slot = get_sim_slot(display_sim)
            srvc_type = (diagnostics.get('SRVC_TYPE') or '').strip().upper()
            use_5g = srvc_type and ('5G' in srvc_type or 'NR' in srvc_type)
            if use_5g:
                rsrp_val = diagnostics.get('RSRP_5G')
                rsrq_val = diagnostics.get('RSRQ_5G')
                rsrp_key = 'RSRP_5G'
                rsrq_key = 'RSRQ_5G'
                label = '5G'
            else:
                rsrp_val = diagnostics.get('RSRP')
                rsrq_val = diagnostics.get('RSRQ')
                rsrp_key = 'RSRP'
                rsrq_key = 'RSRQ'
                label = '4G' if srvc_type else None
            summary_label = 'DISCONNECTED'
            try:
                s = cp.get(f'status/wan/devices/{display_sim}/status/summary')
                if s is not None and str(s).strip():
                    summary_label = str(s).strip()
            except:
                pass
            parts = [p for p in (port, sim_slot, carrier, label) if p]
            header = (' '.join(parts) + ': ' + summary_label) if parts else summary_label
            is_connected = (connected_sim == display_sim)
            out = {
                'connected': is_connected,
                'disconnected': not is_connected,
                'header': header,
                'carrier': carrier,
                'port': port,
                'sim': sim_slot,
                'label': label,
                'rsrp': rsrp_val,
                'rsrq': rsrq_val,
                'rsrp_key': rsrp_key,
                'rsrq_key': rsrq_key
            }
            out.update(extra)
            self.write(json.dumps(out))
        except Exception as e:
            cp.log(f'Error getting signal: {e}')
            err_out = {'connected': False, 'error': str(e)}
            try:
                sims = find_sims()
                err_out['all_sims_available'] = all_sims_available(sims)
            except Exception:
                err_out['all_sims_available'] = False
            err_out['switching'] = switch_in_progress
            err_out['install_running'] = False
            self.write(json.dumps(err_out))

class ConnectHandler(tornado.web.RequestHandler):
    """Handles /connect endpoint - set first SIM def_conn_state to alwayson."""
    def post(self):
        """Set the first SIM's rule def_conn_state to alwayson. Requires password."""
        try:
            installer_password = get_password()
            password_entered = self.get_argument('password_entered', None)
            if not password_entered or password_entered != installer_password:
                cp.log('Connect: incorrect or missing password')
                self.write(json.dumps({'success': False, 'result': 'Incorrect Password!'}))
                return
            sims = find_sims()
            if not sims:
                self.write(json.dumps({'success': False, 'result': 'No SIMs found'}))
                return
            sim_list = list(sims.keys())
            rule_states = {}
            ensure_sims_have_distinct_rules(sim_list, rule_states)
            ensure_original_rule_states_captured(sim_list, rule_states)
            first_sim = sim_list[0]
            if switch_to_sim(first_sim, sim_list, rule_states):
                self.write(json.dumps({'success': True, 'result': 'First SIM set to always on'}))
            else:
                self.write(json.dumps({'success': False, 'result': 'Failed to set first SIM'}))
        except Exception as e:
            cp.log(f'Error in connect: {e}')
            self.write(json.dumps({'success': False, 'result': str(e)}))

def _do_switch_sims(next_sim, sim_list):
    """Background thread: run switch_to_sim and clear switch_in_progress."""
    global switch_in_progress, switch_target_sim
    try:
        rule_states = {}
        ensure_sims_have_distinct_rules(sim_list, rule_states)
        switch_to_sim(next_sim, sim_list, rule_states)
    except Exception as e:
        cp.log(f'Error in switch_sims background: {e}')
    finally:
        switch_in_progress = False
        switch_target_sim = None

class SwitchSimsHandler(tornado.web.RequestHandler):
    """Handles /switch_sims endpoint - cycle to next SIM."""
    def post(self):
        """Switch to the next SIM in the list. Requires password. Runs in background thread."""
        global switch_in_progress, switch_target_sim
        try:
            installer_password = get_password()
            password_entered = self.get_argument('password_entered', None)
            if not password_entered or password_entered != installer_password:
                cp.log('Switch SIMs: incorrect or missing password')
                self.write(json.dumps({'success': False, 'result': 'Incorrect Password!'}))
                return
            sims = find_sims()
            if len(sims) < 2:
                self.write(json.dumps({'success': False, 'result': 'Need at least 2 SIMs to switch'}))
                return
            wan_devs = cp.get('status/wan/devices') or {}
            current_sim = None
            for uid, status in wan_devs.items():
                if uid.startswith('mdm-') and uid in sims:
                    if status.get('status', {}).get('connection_state') == 'connected':
                        current_sim = uid
                        break
            sim_list = list(sims.keys())
            if not current_sim:
                current_sim = sim_list[0]
            idx = sim_list.index(current_sim) if current_sim in sim_list else 0
            next_idx = (idx + 1) % len(sim_list)
            next_sim = sim_list[next_idx]
            ensure_original_rule_states_captured(sim_list)
            switch_in_progress = True
            switch_target_sim = next_sim
            thread = threading.Thread(target=_do_switch_sims, args=(next_sim, sim_list))
            thread.daemon = True
            thread.start()
            sim_slot = get_sim_slot(next_sim) or next_sim
            port_display = get_display_port(next_sim) or get_sim_port(next_sim) or ''
            port_sim = (port_display + ' ' + sim_slot).strip() if (port_display or sim_slot) else sim_slot
            self.write(json.dumps({'success': True, 'result': 'Switching to ' + port_sim + ' - this may take a few minutes...'}))
        except Exception as e:
            switch_in_progress = False
            switch_target_sim = None
            cp.log(f'Error in switch_sims: {e}')
            self.write(json.dumps({'success': False, 'result': str(e)}))

def get_config(name):
    """Get config from appdata."""
    try:
        appdata = cp.get('config/system/sdk/appdata')
        if appdata:
            return next((x.get("value") for x in appdata if x.get("name", "").lower() == name.lower()), None)
    except:
        return None

def has_appdata(name):
    """Return True if appdata entry exists (any value)."""
    try:
        appdata = cp.get('config/system/sdk/appdata') or []
        return any(x.get("name", "").lower() == name.lower() for x in appdata)
    except Exception:
        return False

def use_group_mode():
    """True if group_by_sim or group_by_carrier appdata exists. When True, only move to NCM group; do not reprioritize WAN."""
    return has_appdata('group_by_sim') or has_appdata('group_by_carrier')

def use_carrier_matching():
    """True if matching by carrier. False if group_by_sim appdata exists (match by SIM slot)."""
    return not has_appdata('group_by_sim')

def get_web_port():
    """Get web server port from appdata 'AutoInstall_Web_port' (case insensitive). Default 8000."""
    try:
        val = get_config('AutoInstall_Web_port')
        if val is not None and str(val).strip():
            port = int(str(val).strip())
            if 1 <= port <= 65535:
                return port
        return 8000
    except (ValueError, TypeError) as e:
        cp.log(f'Invalid AutoInstall_Web_port appdata, using 8000: {e}')
        return 8000

def get_password():
    """Get password from SDK data 'installer_password' or use serial number as fallback."""
    try:
        # Try to get password from SDK data (case-insensitive lookup)
        appdata = cp.get('config/system/sdk/appdata')
        password = next((x["value"] for x in appdata if x.get("name", "").lower() == "installer_password"), None)
        if password:
            cp.log('Using password from SDK data.')
            return password
        else:
            cp.log('Using serial number as password. To set a custom password, add SDK Data "installer_password" in the router configuration.')
            return cp.get_serial_number()
    except Exception as e:
        cp.log(f'Error getting password. Using serial number as fallback. {e}')
        return cp.get_serial_number()

def get_version():
    """Get version from package.ini file."""
    try:
        package = configparser.ConfigParser()
        package.read('package.ini')
        major = package.get('AutoInstall_Web', 'version_major')
        minor = package.get('AutoInstall_Web', 'version_minor')
        patch = package.get('AutoInstall_Web', 'version_patch')
        return f'{major}.{minor}.{patch}'
    except Exception as e:
        cp.log(f'Error reading version from package.ini: {e}')
        return '0.0.0'

def get_system_id():
    """Get router system_id."""
    try:
        return cp.get('config/system/system_id') or 'unknown'
    except Exception as e:
        cp.log(f'Error getting system_id: {e}')
        return 'unknown'

def get_min_speed():
    """Get minimum download speed (Mbps) from appdata 'min_speed' (case insensitive). Returns None if not set (no minimum)."""
    val = get_config('min_speed')
    if val is None or not str(val).strip():
        return None
    try:
        return float(str(val).strip())
    except (ValueError, TypeError):
        return None

def get_diagnostic_fields():
    """Get diagnostic fields from SDK data 'diagnostics' or use default list."""
    default_fields = ['DBM', 'SINR', 'RSRP', 'RSRQ', 'RFBAND', 'SRVC_TYPE', 'SRVC_TYPE_DETAILS']
    try:
        # Try to get diagnostic fields from SDK data (case-insensitive lookup)
        appdata = cp.get('config/system/sdk/appdata')
        diagnostics_value = next((x["value"] for x in appdata if x.get("name", "").lower() == "diagnostics"), None)
        if diagnostics_value and diagnostics_value.strip():
            # Parse comma-separated list and trim whitespace
            fields = [field.strip() for field in diagnostics_value.split(',') if field.strip()]
            if fields:
                return fields
        return default_fields
    except Exception as e:
        cp.log(f'Error getting diagnostic fields. Using defaults. {e}')
        return default_fields

# Global variable for log filename
log_filename = 'install_log.txt'

# Global flag for switch-in-progress (allows /signal to be served during long switch)
switch_in_progress = False
switch_target_sim = None  # SIM we are switching TO (for status/meter display)

# Global flag for install cancel request
install_cancelled = False

class InstallCancelledException(Exception):
    pass

def install_cancelled_check():
    global install_cancelled
    if install_cancelled:
        raise InstallCancelledException('Cancelled by user')

# Original def_conn_state per rule (captured before we ever modify); used to revert on switch/cleanup
original_rule_states = {}

# Rule IDs created by ensure_sims_have_distinct_rules (for cleanup/deletion)
created_rule_ids = set()


def write_results_appdata(sims):
    """Write a one-line parseable results string to appdata 'results'.
    Format: timestamp | port sim carrier dl:Xmbps ul:Xmbps score:X | port sim carrier dl:Xmbps ul:Xmbps score:X
    Sorted by download speed descending."""
    try:
        timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        sorted_sims = sorted(sims.keys(), key=lambda s: sims[s].get('download', 0.0), reverse=True)
        parts = [timestamp]
        for sim_device in sorted_sims:
            diag = sims[sim_device].get('diagnostics', {}) or {}
            carrier = (diag.get('CARRID') or '').strip() or 'Unknown'
            iccid = diag.get('ICCID', '')
            down = sims[sim_device].get('download', 0.0)
            up = sims[sim_device].get('upload', 0.0)
            port_display = get_display_port(sim_device) or get_sim_port(sim_device) or ''
            sim_slot = get_sim_slot(sim_device) or ''
            prefix = (port_display + ' ' + sim_slot).strip()
            score, lbl = rsrp_rsrq_to_score(diag)
            sim_part = prefix + ' ' + carrier
            if iccid:
                sim_part += ' ICCID=' + iccid
            sim_part += ' dl:%.2fmbps ul:%.2fmbps' % (down, up)
            if score is not None:
                sim_part += ' score:%d' % score
            parts.append(sim_part)
        results_string = ' | '.join(parts)
        cp.put_appdata('results', results_string)
        cp.log(f'Wrote results to appdata: {results_string}')
        write_log(f'Wrote results to appdata')
    except Exception as e:
        cp.log(f'Error writing results to appdata: {e}')
        write_log(f'Error writing results to appdata: {e}')

def write_log(message):
    """Write message to log file with timestamp."""
    global log_filename
    try:
        timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f'[{timestamp}] {message}\n'
        with open(log_filename, 'a') as f:
            f.write(log_entry)
    except:
        pass

def set_install_target_sim(sim_uid):
    """Update only target_sim in install_status.json. Call at start of each SIM iteration so status summary shows correct SIM immediately."""
    try:
        with open('install_status.json', 'r') as f:
            st = json.loads(f.read())
    except Exception:
        return
    if st.get('status') == 'running':
        st['target_sim'] = sim_uid
        try:
            with open('install_status.json', 'w') as f:
                f.write(json.dumps(st))
        except Exception:
            pass

def update_status(status, message, progress=0, target_sim=None):
    """Update installation status and log file. target_sim: device uid (mdm-xxx) for status summary during autoinstall."""
    status_data = {
        'status': status,
        'message': message,
        'progress': progress
    }
    if target_sim is not None:
        status_data['target_sim'] = target_sim
    if status in ('complete', 'error'):
        status_data.pop('target_sim', None)
    try:
        with open('install_status.json', 'w') as f:
            f.write(json.dumps(status_data))
    except:
        pass
    
    # Write to log file
    write_log(f'[{status.upper()}] {message} (Progress: {progress}%)')

def rsrp_rsrq_to_score(diagnostics):
    """Compute 0-100 signal score from RSRP/RSRQ. Returns (score, label) where label is '4G', '5G', or None."""
    if not diagnostics or not isinstance(diagnostics, dict):
        return None, None
    srvc = (diagnostics.get('SRVC_TYPE') or '').strip().upper()
    use_5g = srvc and ('5G' in srvc or 'NR' in srvc)
    if use_5g:
        rsrp = diagnostics.get('RSRP_5G')
        rsrq = diagnostics.get('RSRQ_5G')
        label = '5G'
    else:
        rsrp = diagnostics.get('RSRP')
        rsrq = diagnostics.get('RSRQ')
        label = '4G' if srvc else None
    try:
        r = float(rsrp) if rsrp is not None else -140.0
        q = float(rsrq) if rsrq is not None else -19.5
    except (TypeError, ValueError):
        return None, None
    rsrp_score = max(0, min(100, (r + 140) / 96 * 100))
    rsrq_score = max(0, min(100, (q + 19.5) / 16.5 * 100))
    score = int(round((rsrp_score + rsrq_score) / 2))
    return score, label

def get_sims_filter():
    """Get sims filter from appdata 'sims'. Returns 'all', 'local', or 'captive'. Default: 'all'."""
    val = get_config('sims')
    if val is not None and str(val).strip():
        v = str(val).strip().lower()
        if v in ('all', 'local', 'captive'):
            return v
    return 'all'

def find_sims():
    """Detect available SIMs. Filter by appdata 'sims': 'all' (default), 'local' (no remote/product_name), or 'captive' (has remote/product_name)."""
    sims = {}
    timeout = 0
    sims_filter = get_sims_filter()
    while True:
        wan_devs = cp.get('status/wan/devices') or {}
        for uid, status in wan_devs.items():
            if uid.startswith('mdm-'):
                error_text = status.get('status', {}).get('error_text', '')
                if error_text:
                    if 'NOSIM' in error_text:
                        continue
                if sims_filter == 'captive':
                    try:
                        product_name = cp.get(f'status/wan/devices/{uid}/info/remote/product_name')
                        if product_name is not None:
                            sims[uid] = status
                        else:
                            cp.log(f'Skipping {uid}: sims=captive but remote/product_name is null')
                    except Exception as e:
                        cp.log(f'Error checking remote/product_name for {uid}: {e}')
                        continue
                elif sims_filter == 'local':
                    try:
                        product_name = cp.get(f'status/wan/devices/{uid}/info/remote/product_name')
                        if product_name is None or not str(product_name).strip():
                            sims[uid] = status
                        else:
                            cp.log(f'Skipping {uid}: sims=local but remote/product_name is populated')
                    except Exception as e:
                        cp.log(f'Error checking remote/product_name for {uid}: {e}')
                        continue
                else:
                    sims[uid] = status
        num_sims = len(sims)
        if num_sims >= 1:
            break
        if timeout >= 10:
            cp.log('Timeout: Did not find any SIMs')
            break
        time.sleep(2)
        timeout += 1
    return sims

def modem_state(sim, state):
    """Wait until modem reaches given state. Timeout is 15 minutes."""
    start_time = time.time()
    timeout_seconds = 900  # 15 minutes
    sleep_seconds = 5
    conn_path = f'status/wan/devices/{sim}/status/connection_state'
    port = get_display_port(sim) or get_sim_port(sim) or '?'
    sim_slot = get_sim_slot(sim) or '?'
    label = f'{port} {sim_slot}'
    cp.log(f'Connecting {label}')
    while True:
        install_cancelled_check()
        conn_state = cp.get(conn_path)
        elapsed = time.time() - start_time
        cp.log(f'Waiting for {label} to connect. Current State={conn_state}, Elapsed: {int(elapsed)}s')

        # If modem is suspended, reset it to recover
        try:
            summary = cp.get(f'status/wan/devices/{sim}/status/summary')
            if summary is not None:
                summary_str = str(summary).lower()
                if 'suspended' in summary_str:
                    cp.log(f'{label} status summary contains "suspended" - resetting modem')
                    cp.put(f'control/wan/devices/{sim}/reset', 1)
        except Exception as e:
            cp.log(f'Warning: Error checking summary for {label}: {e}')
        if conn_state == state:
            break
        if elapsed >= timeout_seconds:
            cp.log(f'Timeout waiting on {label} after {int(elapsed)}s')
            raise Exception(f'Timeout waiting for {label} to connect')
        time.sleep(min(sleep_seconds, 45))
        sleep_seconds += 5
    elapsed = time.time() - start_time
    cp.log(f'{label} connected after {int(elapsed)}s')
    return True

def resolve_speedtest_server_ips():
    """Resolve speedtest server IPs for routing. Returns list of IP addresses."""
    ip_addresses = []
    
    # Resolve speedtest.net base URL
    try:
        url_ip_addresses = socket.gethostbyname_ex("config.speedtest.net")[2]
        ip_addresses.extend(url_ip_addresses)
        cp.log(f'Resolved config.speedtest.net to IPs: {url_ip_addresses}')
    except (socket.gaierror, socket.herror) as e:
        cp.log(f'Error resolving config.speedtest.net: {e}')
    
    # Fetch speedtest server list from config URL
    config_url = "https://www.speedtest.net/api/embed/trial/config"
    try:
        r = requests.get(config_url, headers={"Accept": "application/json"}, timeout=10)
        r.raise_for_status()
        data = r.json()
        servers = data.get("servers", [])
        
        # Resolve each server hostname to IP
        for server in servers:
            server_hostname = server.get("host", "").split(":")[0]
            if server_hostname:
                try:
                    ip_address = socket.gethostbyname(server_hostname)
                    if ip_address not in ip_addresses:
                        ip_addresses.append(ip_address)
                except (socket.gaierror, socket.herror) as e:
                    # IPv6 or other resolution issue - skip
                    cp.log(f'Could not resolve {server_hostname}: {e}')
                    continue
    except requests.exceptions.RequestException as e:
        cp.log(f'Error fetching speedtest server list: {e}')
    except Exception as e:
        cp.log(f'Unexpected error resolving speedtest servers: {e}')
    
    cp.log(f'Resolved {len(ip_addresses)} speedtest server IPs')
    return ip_addresses

#
# NOTE: WAN affinity routing/steering is intentionally not used in this application.
# The working approach is:
# - Switch SIMs by setting def_conn_state to "alwayson" for the active SIM and disabling all other SIM profiles
# - Route speedtest traffic by adding host routes in the main routing table (speedtest2 approach)
# - On cleanup, restore def_conn_state and disabled to original values
#

def add_speedtest_routes(sim_device, server_ips):
    """Add routes for speedtest server IPs to force traffic through specific modem interface.
    Only adds routes if device has a gateway (is connected).
    Returns list of route info dicts (IP and device) for cleanup."""
    route_info = []
    
    if not server_ips:
        return route_info
    
    # Check if device has a gateway (is connected) before adding routes
    try:
        ipinfo = cp.get(f'status/wan/devices/{sim_device}/status/ipinfo')
        gateway = ipinfo.get('gateway') if ipinfo else None
        if not gateway:
            port_sim = (get_display_port(sim_device) or '') + ' ' + (get_sim_slot(sim_device) or '')
            port_sim = port_sim.strip() or 'SIM'
            cp.log(f'Skipping route creation for {port_sim}: device not connected (no gateway)')
            write_log(f'Skipping route creation for {port_sim}: device not connected (no gateway)')
            return route_info
    except Exception as e:
        port_sim = (get_display_port(sim_device) or '') + ' ' + (get_sim_slot(sim_device) or '')
        port_sim = port_sim.strip() or 'SIM'
        cp.log(f'Error checking gateway for {port_sim}: {e}')
        write_log(f'Error checking gateway for {port_sim}: {e}')
        return route_info
    
    # Get current routes list
    try:
        routes = cp.get('config/routing/tables/0/routes/')
        if not isinstance(routes, list):
            routes = []
    except Exception as e:
        cp.log(f'Error getting routes: {e}')
        routes = []
    
    # Add new routes to the list
    for ip in server_ips:
        try:
            # Create route entry
            route_data = {
                "auto_gateway": True,
                "dev": sim_device,
                "distribute": False,
                "ip_network": f"{ip}/32",
                "netallow": False
            }
            
            # Check if route already exists
            route_exists = False
            for existing_route in routes:
                if existing_route.get('ip_network') == f"{ip}/32" and existing_route.get('dev') == sim_device:
                    route_exists = True
                    break
            
            if not route_exists:
                routes.append(route_data)
                route_info.append({'ip': ip, 'dev': sim_device})
        except Exception as e:
            cp.log(f'Error adding route for {ip}/32: {e}')
            write_log(f'Error adding route for {ip}/32: {e}')
    
    # Put the updated routes list back
    if route_info:
        try:
            cp.put('config/routing/tables/0/routes/', routes)
            cp.log(f'Updated routes list with {len(route_info)} new route(s)')
        except Exception as e:
            cp.log(f'Error updating routes list: {e}')
            write_log(f'Error updating routes list: {e}')
    
    return route_info

def remove_speedtest_routes(route_info_list):
    """Remove speedtest routes by matching IP addresses and device.
    route_info_list can be a list of dicts with 'ip' and 'dev' keys, or a list of IP strings (legacy)."""
    if not route_info_list:
        return
    
    # Get routes from table 0
    try:
        routes = cp.get('config/routing/tables/0/routes/')
        if not routes:
            cp.log('No routes found in table 0 for cleanup')
            return
        
        # Routes is a list
        if not isinstance(routes, list):
            cp.log('Routes is not a list, cannot clean up')
            return
        
        # Build set of routes to remove (for efficient lookup)
        routes_to_remove = set()
        for route_info in route_info_list:
            try:
                # Handle both dict format and legacy string format
                if isinstance(route_info, dict):
                    target_ip = route_info.get('ip')
                    target_dev = route_info.get('dev')
                else:
                    # Legacy: just an IP string
                    target_ip = route_info
                    target_dev = None
                
                if not target_ip:
                    continue
                
                # Find routes matching this IP and optionally device
                for idx, route in enumerate(routes):
                    route_ip_network = route.get('ip_network', '')
                    route_ip_part = route_ip_network.split('/')[0] if '/' in route_ip_network else route_ip_network
                    route_dev = route.get('dev', '')
                    
                    # Match by IP, and optionally by device if specified
                    if target_ip == route_ip_part:
                        if target_dev is None or target_dev == route_dev:
                            routes_to_remove.add(idx)
            except Exception as e:
                cp.log(f'Error processing route info: {e}')
        
        # Remove routes in reverse order to maintain indices
        removed_count = 0
        for idx in sorted(routes_to_remove, reverse=True):
            try:
                routes.pop(idx)
                removed_count += 1
            except Exception as e:
                cp.log(f'Error removing route at index {idx}: {e}')
        
        # Put the updated routes list back
        if removed_count > 0:
            try:
                cp.put('config/routing/tables/0/routes/', routes)
                cp.log(f'Removed {removed_count} speedtest route(s)')
            except Exception as e:
                cp.log(f'Error updating routes list: {e}')
                write_log(f'Error updating routes list: {e}')
        else:
            cp.log('No speedtest routes were removed')
    except Exception as e:
        cp.log(f'Error getting routes for cleanup: {e}')
        write_log(f'Error getting routes for cleanup: {e}')

def all_sims_available(sims):
    """Return True if all SIMs have status.summary == 'available' (case-insensitive)."""
    if not sims:
        return False
    for uid in sims:
        try:
            s = cp.get(f'status/wan/devices/{uid}/status/summary')
            if s is None or str(s).strip().lower() != 'available':
                return False
        except Exception:
            return False
    return True

def get_rule_display_name(rule_id):
    """Get trigger_name for a rule, or rule_id if no trigger_name. For user-facing logs."""
    try:
        rule = cp.get(f'config/wan/rules2/{rule_id}')
        if rule:
            name = rule.get('trigger_name')
            if name is not None and str(name).strip():
                return str(name).strip()
    except Exception:
        pass
    return rule_id

def get_sim_rule_id(sim_device):
    """Get the rule _id_ for a SIM device from its config."""
    try:
        config = cp.get(f'status/wan/devices/{sim_device}/config')
        if config and isinstance(config, dict):
            rule_id = config.get('_id_')
            return rule_id
    except Exception as e:
        cp.log(f'Error getting rule ID for {sim_device}: {e}')
    return None

def get_sim_slot(sim_device):
    """Get the SIM slot (e.g., 'SIM1', 'SIM2') for a device."""
    try:
        sim_info = cp.get(f'status/wan/devices/{sim_device}/info/sim')
        if sim_info:
            return sim_info.upper()  # e.g., "sim1" -> "SIM1"
    except:
        pass
    return None

def get_sim_port(sim_device):
    """Get the port (e.g., 'int1', 'int2') for a device."""
    try:
        port_info = cp.get(f'status/wan/devices/{sim_device}/info/port')
        if port_info:
            return str(port_info).lower()
    except:
        pass
    return None

def get_display_port(sim_device):
    """Get user-facing port label: 'int1'->'Internal' or 'Captive', 'modem1'->'MC400'. Returns raw port if unmapped."""
    port = get_sim_port(sim_device)
    if not port:
        return None
    port_lower = str(port).lower()
    if port_lower.startswith('modem'):
        return 'MC400'
    if port_lower.startswith('int'):
        try:
            product_name = cp.get(f'status/wan/devices/{sim_device}/info/remote/product_name')
            if product_name is not None and str(product_name).strip():
                return 'Captive'
        except Exception:
            pass
        return 'Internal'
    return port

def get_rule_id_by_trigger(port, sim_lower):
    """Find rule _id_ by trigger_string. Used for reprioritize to avoid status/wan/devices mapping issues."""
    try:
        trigger_string = 'type|is|mdm%%sim|is|%s%%port|is|%s' % (sim_lower, port)
        rules = cp.get('config/wan/rules2') or []
        if isinstance(rules, dict):
            rules = list(rules.values()) if rules else []
        elif not isinstance(rules, list):
            rules = []
        for r in rules:
            if not isinstance(r, dict):
                continue
            if r.get('trigger_string') == trigger_string:
                return r.get('_id_')
    except Exception as e:
        cp.log(f'Error finding rule by trigger: {e}')
    return None

def reprioritize_wan_by_speed(sims):
    """Reprioritize WAN profiles by download speed. Only considers tested SIMs.
    Fastest SIM gets lowest priority number (highest WAN priority), others right behind.
    Gets lowest priority of ANY modem rule (trigger_string starts with type|is|mdm).
    Slowest tested SIM gets 0.1 below that; each faster SIM gets 0.1 lower. Priorities
    must not match any existing - uses finer granularity (0.01) if needed.
    Uses rule_id from status/wan/devices/{device}/config/_id_ for PUT - that method works.
    """
    try:
        # Build sim -> (rule_id, port, sim, carrier, download)
        # Rule ID must come from status/wan/devices/{device}/config/_id_ (get_sim_rule_id)
        # If two SIMs share the same rule_id, try get_rule_id_by_trigger for per-SIM rules
        sim_info = {}
        rule_id_to_sims = {}
        for sim_device in sims:
            rule_id = get_sim_rule_id(sim_device)
            if not rule_id:
                cp.log(f'Skipping {sim_device}: no rule_id from status/wan/devices config')
                continue
            port = get_sim_port(sim_device) or 'unknown'
            display_port = get_display_port(sim_device) or port
            sim_slot = get_sim_slot(sim_device)
            sim_lower = sim_slot.lower() if sim_slot else 'unknown'
            diagnostics = sims[sim_device].get('diagnostics', {})
            carrier = (diagnostics.get('CARRID') or '').strip() or ''
            download = sims[sim_device].get('download', 0.0)
            score, lbl = rsrp_rsrq_to_score(diagnostics)
            sim_info[sim_device] = {'rule_id': rule_id, 'port': port, 'display_port': display_port, 'sim': sim_lower, 'carrier': carrier, 'download': download, 'score': score, 'label': lbl}
            rule_id_to_sims.setdefault(rule_id, []).append(sim_device)

        # Resolve shared rule_ids: if multiple SIMs map to the same rule, try per-SIM trigger lookup
        for rule_id, sim_list in list(rule_id_to_sims.items()):
            if len(sim_list) <= 1:
                continue
            cp.log(f'Rule {get_rule_display_name(rule_id)} shared by {len(sim_list)} SIMs, resolving per-SIM rules')
            for sim_device in sim_list:
                info = sim_info[sim_device]
                per_sim_rule_id = get_rule_id_by_trigger(info['port'], info['sim'])
                if per_sim_rule_id and per_sim_rule_id != rule_id:
                    cp.log(f'Resolved {sim_device} to per-SIM rule {get_rule_display_name(per_sim_rule_id)}')
                    sim_info[sim_device]['rule_id'] = per_sim_rule_id
                    rule_id_to_sims.setdefault(per_sim_rule_id, []).append(sim_device)
            # Remove devices that got reassigned from the shared list
            remaining = [s for s in sim_list if sim_info[s]['rule_id'] == rule_id]
            if remaining:
                rule_id_to_sims[rule_id] = remaining
            else:
                del rule_id_to_sims[rule_id]

        sim_to_rule_id = dict((s, sim_info[s]['rule_id']) for s in sim_info)
        sorted_sims = sorted(sim_info.keys(), key=lambda s: sim_info[s]['download'], reverse=True)
        if not sorted_sims:
            return

        # Get all modem rules (trigger_string starts with "type|is|mdm") and their priorities
        rules = cp.get('config/wan/rules2') or []
        if isinstance(rules, dict):
            rules = list(rules.values()) if rules else []
        elif not isinstance(rules, list):
            rules = []
        modem_priorities = []
        our_rule_ids = set(sim_to_rule_id.values())
        for r in rules:
            if not isinstance(r, dict):
                continue
            ts = r.get('trigger_string') or ''
            if not str(ts).startswith('type|is|mdm'):
                continue
            p = r.get('priority')
            if isinstance(p, (int, float)):
                modem_priorities.append((r.get('_id_'), p))

        # Existing priorities we must not match (from modem rules we are NOT updating)
        existing_priorities = set()
        min_priority = 10.0
        for rid, p in modem_priorities:
            if rid not in our_rule_ids:
                existing_priorities.add(p)
            if p < min_priority:
                min_priority = p
        if min_priority >= 10:
            min_priority = 2.0

        # Slowest gets base = min - step, each faster gets step lower. Must not match existing.
        def build_priorities(step):
            base = min_priority - step  # slowest gets this
            result = {}
            n = len(sorted_sims)
            for i, sim_device in enumerate(sorted_sims):
                rule_id = sim_to_rule_id.get(sim_device)
                if rule_id:
                    pri = base - step * (n - 1 - i)
                    result[rule_id] = round(pri, 10)
            return result

        for step in (0.1, 0.01, 0.001, 0.0001):
            rule_priority_map = build_priorities(step)
            conflict = any(pri in existing_priorities for pri in rule_priority_map.values())
            if not conflict:
                break

        # Update slowest-first (backup first, then primary) so FailoverFailback
        # policy does not overwrite our change when we promote the fastest to primary.
        items_sorted = sorted(rule_priority_map.items(), key=lambda x: -x[1])

        # Try per-rule updates first
        any_failed = False
        for rule_id, new_priority in items_sorted:
            sim_device = rule_id_to_sims.get(rule_id, [None])[0]
            try:
                cp.put(f'config/wan/rules2/{rule_id}/priority', new_priority)
                time.sleep(0.3)
                rule = cp.get(f'config/wan/rules2/{rule_id}')
                actual = rule.get('priority') if rule else None
                ok = actual is not None and abs(float(actual) - float(new_priority)) < 0.01
                if not ok:
                    any_failed = True
                info = sim_info.get(sim_device, {}) if sim_device else {}
                log_parts = [p for p in (info.get('display_port', ''), info.get('sim', ''), info.get('carrier', '')) if p] if info else [str(rule_id)]
                score_str = ''
                if info.get('score') is not None:
                    lbl = info.get('label') or '4G/5G'
                    score_str = f', {lbl} Score: {info["score"]}'
                dl = info.get('download', 0)
                verified = 'verified' if ok else 'verify failed (got %s)' % (actual,)
                cp.log(f'Set priority {new_priority} for {" ".join(log_parts)} (download: {dl:.2f}Mbps{score_str}) [{verified}]')
            except Exception as e:
                any_failed = True
                cp.log(f'Error setting priority for rule {rule_id}: {e}')

        # Fallback: bulk update entire rules2 if per-rule updates did not persist
        if any_failed:
            try:
                rules_raw = cp.get('config/wan/rules2')
                if rules_raw is not None:
                    modified = False
                    if isinstance(rules_raw, dict):
                        for key, r in rules_raw.items():
                            if isinstance(r, dict) and r.get('_id_') in rule_priority_map:
                                r['priority'] = rule_priority_map[r['_id_']]
                                modified = True
                        if modified:
                            cp.put('config/wan/rules2', rules_raw)
                            cp.log('Applied priority changes via bulk rules2 update')
                    elif isinstance(rules_raw, list):
                        for r in rules_raw:
                            if isinstance(r, dict) and r.get('_id_') in rule_priority_map:
                                r['priority'] = rule_priority_map[r['_id_']]
                                modified = True
                        if modified and rules_raw:
                            cp.put('config/wan/rules2', rules_raw)
                            cp.log('Applied priority changes via bulk rules2 update')
                    if modified:
                        time.sleep(0.5)
            except Exception as e:
                cp.log(f'Bulk rules2 update failed: {e}')

        cp.log('WAN profiles reprioritized by download speed')
    except Exception as e:
        cp.log(f'Error reprioritizing WAN: {e}')
        write_log(f'Error reprioritizing WAN: {e}')

def ensure_original_rule_states_captured(all_sims, rule_states=None):
    """Capture original def_conn_state and disabled for all SIM rules before we ever modify.
    If rule_states is provided (e.g. after ensure_sims_have_distinct_rules), also add any rules
    from it - newly created per-SIM rules may not be returned by get_sim_rule_id yet."""
    global original_rule_states
    for sim_device in all_sims:
        rule_id = get_sim_rule_id(sim_device)
        if rule_id and rule_id not in original_rule_states:
            try:
                rule = cp.get(f'config/wan/rules2/{rule_id}')
                if rule:
                    original_rule_states[rule_id] = {
                        'def_conn_state': rule.get('def_conn_state'),
                        'disabled': rule.get('disabled', False),
                    }
            except Exception as e:
                cp.log(f'Error capturing original rule state for {get_rule_display_name(rule_id)}: {e}')
    if rule_states:
        for rule_id, state in rule_states.items():
            if rule_id not in original_rule_states:
                original_rule_states[rule_id] = dict(state)
                cp.log(f'Captured original state for rule {get_rule_display_name(rule_id)} from rule_states')

def _restore_def_conn_state_from_originals(rule_ids):
    """Restore def_conn_state to original for given rule IDs. Used when switching away from a SIM."""
    global original_rule_states
    for rule_id in rule_ids:
        state = original_rule_states.get(rule_id)
        if not state:
            continue
        orig_def = state.get('def_conn_state')
        try:
            if orig_def is not None:
                cp.put(f'config/wan/rules2/{rule_id}/def_conn_state', orig_def)
                cp.log(f'Reverted def_conn_state to "{orig_def}" for {get_rule_display_name(rule_id)}')
            else:
                try:
                    cp.delete(f'config/wan/rules2/{rule_id}/def_conn_state')
                except Exception:
                    try:
                        cp.put(f'config/wan/rules2/{rule_id}/def_conn_state', '')
                    except Exception:
                        pass
        except Exception as e:
            cp.log(f'Error reverting def_conn_state for {get_rule_display_name(rule_id)}: {e}')

def _capture_rule_state(rule_states, rule_id):
    """Capture original def_conn_state and disabled for a rule if not already captured."""
    if rule_id in rule_states:
        return
    try:
        rule = cp.get(f'config/wan/rules2/{rule_id}')
        if rule:
            rule_states[rule_id] = {
                'def_conn_state': rule.get('def_conn_state'),
                'disabled': rule.get('disabled', False),
            }
    except Exception as e:
        cp.log(f'Error capturing rule state for {get_rule_display_name(rule_id)}: {e}')

def _create_rule_for_sim(base_rule, port, sim_lower, carrier, rule_states, priority_add=0.1, display_port=None):
    """Create a duplicate rule with trigger_string/trigger_name for a specific SIM. Returns new rule _id_ or None.
    If a rule with the same trigger_string already exists, reuses it instead of creating a duplicate.
    priority_add is added to base priority (default 0.1) for the new profile.
    display_port is used for trigger_name (e.g. Internal, Captive, MC400); port is used for trigger_string matching."""
    global created_rule_ids
    try:
        if not isinstance(base_rule, dict):
            cp.log(f'base_rule is not a dict: {type(base_rule)}')
            return None
        port_display = display_port if display_port else port
        trigger_string = 'type|is|mdm%%sim|is|%s%%port|is|%s' % (sim_lower, port)

        # Check if a rule with this trigger_string already exists (avoid duplicates)
        existing_rules = cp.get('config/wan/rules2') or []
        if isinstance(existing_rules, dict):
            existing_rules = list(existing_rules.values()) if existing_rules else []
        elif not isinstance(existing_rules, list):
            existing_rules = []
        for r in existing_rules:
            if not isinstance(r, dict):
                continue
            if r.get('trigger_string') == trigger_string:
                existing_id = r.get('_id_')
                if existing_id:
                    cp.log(f'Rule with trigger_string already exists: {existing_id}, reusing')
                    _capture_rule_state(rule_states, existing_id)
                    # Do NOT add to created_rule_ids — this is an existing rule, not one we created
                    return existing_id

        new_rule = dict(base_rule)
        new_rule.pop('_id_', None)
        base_priority = base_rule.get('priority', 100)
        if isinstance(base_priority, (int, float)):
            new_rule['priority'] = base_priority + priority_add
        else:
            new_rule['priority'] = 100 + priority_add
        name_parts = [p for p in (port_display, sim_lower) if p and str(p).lower() != 'unknown']
        trigger_name = ' '.join(name_parts) if name_parts else '%s %s' % (port_display, sim_lower)
        new_rule['trigger_string'] = trigger_string
        new_rule['trigger_name'] = trigger_name
        res = cp.post('config/wan/rules2', new_rule)
        new_id = None
        if isinstance(res, dict):
            data = res.get('data')
            if isinstance(data, dict):
                new_id = data.get('_id_')
            elif data is not None:
                new_id = data
            if not new_id:
                new_id = res.get('_id_')
        elif res is not None:
            new_id = res
        if not new_id:
            rules = cp.get('config/wan/rules2') or []
            if isinstance(rules, dict):
                rules = list(rules.values()) if rules else []
            elif not isinstance(rules, list):
                rules = []
            for r in rules:
                if not isinstance(r, dict):
                    continue
                if r.get('trigger_string') == trigger_string:
                    new_id = r.get('_id_')
                    break
        if new_id:
            _capture_rule_state(rule_states, new_id)
            created_rule_ids.add(new_id)
        return new_id
    except Exception as e:
        cp.log(f'Error creating rule for SIM: {e}')
        return None

def ensure_sims_have_distinct_rules(all_sims, rule_states):
    """If two or more SIMs share the same rule, create a new WAN profile per SIM by POSTing a copy (no _id_) with new trigger_string. Do not modify the existing rule."""
    try:
        rule_id_to_sims = {}
        sim_info = {}
        for sim_device in all_sims:
            rule_id = get_sim_rule_id(sim_device)
            if not rule_id:
                continue
            port = get_sim_port(sim_device) or 'unknown'
            display_port = get_display_port(sim_device) or port
            sim_slot = get_sim_slot(sim_device)
            sim_lower = sim_slot.lower() if sim_slot else 'unknown'
            carrier = ''
            try:
                diag = cp.get(f'status/wan/devices/{sim_device}/diagnostics')
                if diag:
                    carrier = (diag.get('CARRID') or '').strip() or ''
            except:
                pass
            sim_info[sim_device] = {'rule_id': rule_id, 'port': port, 'display_port': display_port, 'sim': sim_lower, 'carrier': carrier}
            rule_id_to_sims.setdefault(rule_id, []).append(sim_device)
        for rule_id, sim_list in rule_id_to_sims.items():
            if len(sim_list) <= 1:
                continue
            base_rule = cp.get(f'config/wan/rules2/{rule_id}')
            if not base_rule:
                cp.log(f'Could not get rule {get_rule_display_name(rule_id)} for separation')
                continue
            _capture_rule_state(rule_states, rule_id)
            for idx, sim_device in enumerate(sim_list):
                info = sim_info[sim_device]
                port = info['port']
                display_port = info['display_port']
                sim_lower = info['sim']
                carrier = info['carrier']
                new_id = _create_rule_for_sim(base_rule, port, sim_lower, carrier, rule_states, priority_add=0.1 * (idx + 1), display_port=display_port)
                if new_id:
                    rule_label = get_rule_display_name(new_id)
                    cp.log(f'Created distinct rule {rule_label}')
                    write_log(f'Created distinct rule {rule_label}')
                time.sleep(0.5)
    except Exception as e:
        cp.log(f'Error ensuring distinct rules: {e}')
        write_log(f'Error ensuring distinct rules: {e}')

def switch_to_sim(active_sim, all_sims, rule_states):
    """Disable all other SIM rules, set active SIM to alwayson, wait for connection."""
    try:
        active_rule_id = get_sim_rule_id(active_sim)
        if not active_rule_id:
            port_sim = (get_display_port(active_sim) or '') + ' ' + (get_sim_slot(active_sim) or '')
            port_sim = port_sim.strip() or 'SIM'
            cp.log(f'Could not find rule ID for {port_sim}')
            return False
        _capture_rule_state(rule_states, active_rule_id)
        port_display = get_display_port(active_sim) or get_sim_port(active_sim) or ''
        sim_slot_str = get_sim_slot(active_sim) or ''
        port_sim = (port_display + ' ' + sim_slot_str).strip() if (port_display or sim_slot_str) else 'SIM'

        # Step 1: Disable ALL other SIM rules first
        other_rule_ids = set()
        for sim_device in all_sims:
            if sim_device == active_sim:
                continue
            rule_id = get_sim_rule_id(sim_device)
            if rule_id and rule_id != active_rule_id:
                other_rule_ids.add(rule_id)
        for rule_id in other_rule_ids:
            _capture_rule_state(rule_states, rule_id)
            cp.put(f'config/wan/rules2/{rule_id}/disabled', True)
            cp.log(f'Disabled rule {get_rule_display_name(rule_id)}')
            write_log(f'Disabled rule {get_rule_display_name(rule_id)}')
        time.sleep(2)

        # Step 2: Enable active SIM rule with alwayson
        cp.put(f'config/wan/rules2/{active_rule_id}/disabled', False)
        cp.put(f'config/wan/rules2/{active_rule_id}/def_conn_state', 'alwayson')
        cp.log(f'Set {port_sim} rule {get_rule_display_name(active_rule_id)} to alwayson')
        write_log(f'Set {port_sim} rule {get_rule_display_name(active_rule_id)} to alwayson')

        # Step 3: Wait for active SIM to connect
        timeout_sec = 300
        poll_interval = 5
        elapsed = 0
        connected = False
        while elapsed < timeout_sec:
            install_cancelled_check()
            conn_state = cp.get(f'status/wan/devices/{active_sim}/status/connection_state')
            if conn_state == 'connected':
                connected = True
                break
            try:
                summary = cp.get(f'status/wan/devices/{active_sim}/status/summary')
                if summary is not None and 'suspended' in str(summary).lower():
                    cp.log(f'{port_sim} suspended, resetting modem')
                    cp.put(f'control/wan/devices/{active_sim}/reset', 1)
            except Exception:
                pass
            cp.log(f'Waiting for {port_sim}. State={conn_state}, Elapsed={int(elapsed)}s')
            time.sleep(poll_interval)
            elapsed += poll_interval

        # Step 4: Re-enable other rules only after connected
        if connected:
            for rule_id in other_rule_ids:
                try:
                    cp.put(f'config/wan/rules2/{rule_id}/disabled', False)
                    cp.log(f'Re-enabled rule {get_rule_display_name(rule_id)}')
                except Exception as e:
                    cp.log(f'Could not re-enable rule {get_rule_display_name(rule_id)}: {e}')
        else:
            cp.log(f'{port_sim} did not connect within {timeout_sec}s')
            write_log(f'{port_sim} did not connect within {timeout_sec}s')
        return True
    except Exception as e:
        port_sim = (get_display_port(active_sim) or '') + ' ' + (get_sim_slot(active_sim) or '')
        port_sim = port_sim.strip() or 'SIM'
        cp.log(f'Error switching to {port_sim}: {e}')
        write_log(f'Error switching to {port_sim}: {e}')
        return False

def cleanup_wan_profile_changes(rule_states):
    """Restore def_conn_state and disabled to defaults for all modified rules.
    Delete def_conn_state (default ondemand) and delete disabled (default enabled)
    so profiles return to a clean state regardless of prior captures.
    Also deletes any per-SIM rules created by ensure_sims_have_distinct_rules."""
    global created_rule_ids
    if not rule_states and not created_rule_ids:
        return
    # First restore state on all tracked rules (excluding ones we'll delete)
    for rule_id in rule_states:
        if rule_id in created_rule_ids:
            continue  # Will be deleted below
        try:
            try:
                cp.delete(f'config/wan/rules2/{rule_id}/def_conn_state')
                cp.log(f'Deleted def_conn_state for {get_rule_display_name(rule_id)}')
            except Exception as e:
                cp.log(f'Could not delete def_conn_state for {get_rule_display_name(rule_id)}: {e}')
            try:
                cp.put(f'config/wan/rules2/{rule_id}/disabled', False)
                cp.log(f'Enabled {get_rule_display_name(rule_id)}')
            except Exception as e:
                cp.log(f'Could not enable {get_rule_display_name(rule_id)}: {e}')
        except Exception as e:
            cp.log(f'Error restoring {get_rule_display_name(rule_id)}: {e}')
    # Delete per-SIM rules that were created during this run
    for rule_id in list(created_rule_ids):
        try:
            rule_label = get_rule_display_name(rule_id)
            cp.delete(f'config/wan/rules2/{rule_id}')
            cp.log(f'Deleted created per-SIM rule {rule_label}')
        except Exception as e:
            cp.log(f'Error deleting created rule {rule_id}: {e}')
    created_rule_ids.clear()

def cleanup_all_speedtest_routes_for_device(sim_device):
    """Clean up any leftover speedtest routes for a specific device."""
    try:
        routes = cp.get('config/routing/tables/0/routes/')
        if not routes:
            return
        
        # Routes is a list
        if not isinstance(routes, list):
            return
        
        # Filter out speedtest routes for this device (32-bit netmask indicates specific host route)
        original_count = len(routes)
        routes = [route for route in routes if not (route.get('dev') == sim_device and route.get('ip_network', '').endswith('/32'))]
        removed_count = original_count - len(routes)
        
        # Put the updated routes list back if any were removed
        if removed_count > 0:
            try:
                cp.put('config/routing/tables/0/routes/', routes)
                port_sim = (get_display_port(sim_device) or '') + ' ' + (get_sim_slot(sim_device) or '')
                port_sim = port_sim.strip() or 'SIM'
                cp.log(f'Cleaned up {removed_count} leftover speedtest route(s) for {port_sim}')
            except Exception as e:
                cp.log(f'Error updating routes list during cleanup: {e}')
    except Exception as e:
        port_sim = (get_display_port(sim_device) or '') + ' ' + (get_sim_slot(sim_device) or '')
        port_sim = port_sim.strip() or 'SIM'
        cp.log(f'Error cleaning up leftover routes for {port_sim}: {e}')

def do_speedtest(sim, carrier_name=None):
    """Run Ookla speedtest using binary and return TCP down and TCP up in Mbps."""
    route_info = None
    try:
        # Check if ookla binary exists
        if not os.path.exists('ookla'):
            cp.log('Ookla binary not found')
            return 0.0, 0.0
        
        sim_slot = get_sim_slot(sim)
        port_display = get_display_port(sim) or get_sim_port(sim) or ''
        sim_label = (port_display + ' ' + (sim_slot or '')).strip() or ''
        if sim_label:
            sim_label = sim_label + ' '

        # Ensure we always have a carrier name for logging (best-effort)
        if not carrier_name:
            try:
                diagnostics = cp.get(f'status/wan/devices/{sim}/diagnostics')
                if diagnostics:
                    carrier_name = diagnostics.get('CARRID', '') or ''
            except:
                carrier_name = carrier_name or ''

        carrier_info = f' ({carrier_name})' if carrier_name else ''

        # Get the IP address of the SIM device for optional source binding
        source_ip = None
        try:
            ipinfo = cp.get(f'status/wan/devices/{sim}/status/ipinfo')
            if ipinfo:
                source_ip = ipinfo.get('ip_address')
        except Exception as e:
            cp.log(f'Warning: Could not get IP address for {sim_label}: {e}')
        
        # Resolve speedtest server IPs and add host routes via this SIM (speedtest2 approach)
        try:
            server_ips = resolve_speedtest_server_ips()
            if server_ips:
                route_info = add_speedtest_routes(sim, server_ips)
                if route_info:
                    cp.log(f'Added {len(route_info)} speedtest routes via {sim_label}')
                    write_log(f'Added {len(route_info)} speedtest routes via {sim_label}')
                    # Give routes a moment to take effect
                    time.sleep(1)
        except Exception as e:
            cp.log(f'Warning: Could not add speedtest routes: {e}')
            write_log(f'Warning: Could not add speedtest routes: {e}')

        cp.log(f'Running Ookla speedtest on {sim_label}{carrier_info}...')
        write_log(f'Running Ookla speedtest on {sim_label}{carrier_info}...')
        
        # Capture bytes in/out before speedtest for RouterBytesTotal
        bytes_in_before = None
        bytes_out_before = None
        try:
            bytes_in_before = cp.get(f'status/wan/devices/{sim}/stats/in')
        except Exception as e:
            cp.log(f'Warning: Could not read bytes in before speedtest for {sim_label}: {e}')
        try:
            bytes_out_before = cp.get(f'status/wan/devices/{sim}/stats/out')
        except Exception as e:
            cp.log(f'Warning: Could not read bytes out before speedtest for {sim_label}: {e}')

        # Create Speedtest instance; keep source_address if we have it, but rely on routes
        if source_ip:
            speedtest = Speedtest(source_address=source_ip, timeout=90)
            cp.log(f'Binding speedtest to source IP: {source_ip}')
        else:
            speedtest = Speedtest(timeout=90)
            cp.log('No source IP available, running speedtest without source binding (routes only)')
        
        # Run full bidirectional test (download + upload)
        speedtest.download_and_upload()
        
        if speedtest.results:
            # Convert from bits per second to Mbps and get latency in ms
            down = speedtest.results.download / 1000000  # bps to Mbps
            up = speedtest.results.upload / 1000000  # bps to Mbps
            latency = getattr(speedtest.results, 'ping', 0) or 0

            # Capture bytes in/out after speedtest and compute deltas
            bytes_in_after = None
            bytes_out_after = None
            try:
                bytes_in_after = cp.get(f'status/wan/devices/{sim}/stats/in')
            except Exception as e:
                cp.log(f'Warning: Could not read final bytes in for {sim_label}: {e}')
            try:
                bytes_out_after = cp.get(f'status/wan/devices/{sim}/stats/out')
            except Exception as e:
                cp.log(f'Warning: Could not read final bytes out for {sim_label}: {e}')

            bytes_used_in = None
            bytes_used_out = None
            bytes_used_total = None
            try:
                if bytes_in_before is not None and bytes_in_after is not None:
                    bytes_used_in = int(bytes_in_after) - int(bytes_in_before)
                if bytes_out_before is not None and bytes_out_after is not None:
                    bytes_used_out = int(bytes_out_after) - int(bytes_out_before)
                if bytes_used_in is not None or bytes_used_out is not None:
                    if bytes_used_in is None:
                        bytes_used_in = 0
                    if bytes_used_out is None:
                        bytes_used_out = 0
                    bytes_used_total = bytes_used_in + bytes_used_out
            except Exception as e:
                cp.log(f'Warning: Could not compute bytes used for {sim_label}: {e}')

            # Get ISP from Ookla results (client dict or top-level isp in result)
            ookla_isp = ''
            try:
                client = getattr(speedtest.results, 'client', {}) or {}
                if isinstance(client, dict):
                    ookla_isp = client.get('isp') or client.get('isp_name') or ''
                if not ookla_isp and hasattr(speedtest.results, 'isp'):
                    ookla_isp = speedtest.results.isp or ''
            except Exception:
                pass

            # Get ICCID and score from diagnostics if available
            iccid = ''
            score_info = ''
            try:
                diagnostics = cp.get(f'status/wan/devices/{sim}/diagnostics')
                if diagnostics:
                    iccid = diagnostics.get('ICCID', '')
                    score, lbl = rsrp_rsrq_to_score(diagnostics)
                    if score is not None:
                        score_info = f' {lbl or "4G/5G"} Score: {score}' if lbl else f' Score: {score}'
            except:
                pass
            sim_slot = get_sim_slot(sim)
            sim_label = f'{sim_slot} ' if sim_slot else ''
            iccid_info = f' ICCID={iccid}' if iccid else ''
            isp_info = f' OoklaISP: {ookla_isp}' if ookla_isp else ''
            bytes_info = ''
            if bytes_used_total is not None:
                bytes_info = f' RouterBytesTotal: {bytes_used_total}B'

            cp.log(f'Speedtest complete for {sim_label}{carrier_info}{iccid_info}. '
                   f'Download: {down:.2f}Mbps Upload: {up:.2f}Mbps Latency: {latency:.2f}ms{isp_info}{bytes_info}{score_info}')
            write_log(f'Speedtest complete for {sim_label}{carrier_info}{iccid_info}. '
                      f'Download: {down:.2f}Mbps Upload: {up:.2f}Mbps Latency: {latency:.2f}ms{isp_info}{bytes_info}{score_info}')
            return down, up
        else:
            sim_slot = get_sim_slot(sim)
            sim_label = f'{sim_slot} ' if sim_slot else ''
            cp.log(f'No results from speedtest on {sim_label}{carrier_info}')
            return 0.0, 0.0
    except Exception as e:
        sim_slot = get_sim_slot(sim)
        sim_label = f'{sim_slot} ' if sim_slot else ''
        carrier_info = f' ({carrier_name})' if carrier_name else ''
        error_msg = f'Error running speedtest on {sim_label}{carrier_info}: {e}'
        cp.log(error_msg)
        write_log(error_msg)
        return 0.0, 0.0
    finally:
        # Clean up speedtest host routes from main table
        try:
            if route_info:
                remove_speedtest_routes(route_info)
        except Exception as e:
            cp.log(f'Error cleaning up speedtest routes: {e}')

def test_sim(device, sims):
    """Get diagnostics, run speedtest for a SIM with retries."""
    try:
        if modem_state(device, 'connected'):
            # Get diagnostics
            diagnostics = cp.get(f'status/wan/devices/{device}/diagnostics')
            sims[device]['diagnostics'] = diagnostics
            carrier_name = diagnostics.get('CARRID', '')
            
            # Log detailed diagnostics using configurable fields
            sim_slot = get_sim_slot(device)
            port_display = get_display_port(device) or get_sim_port(device) or ''
            port_sim = (port_display + ' ' + (sim_slot or '')).strip() if (port_display or sim_slot) else (sim_slot or 'SIM')
            iccid = diagnostics.get('ICCID', '')
            diag_fields = get_diagnostic_fields()
            diag_parts = [f'CARRID={carrier_name}']
            if iccid:
                diag_parts.append(f'ICCID={iccid}')
            for field in diag_fields:
                diag_parts.append(f'{field}={diagnostics.get(field)}')
            diag_msg = f'Modem Diagnostics for {port_sim}: {", ".join(diag_parts)}'
            cp.log(diag_msg)
            write_log(diag_msg)
            
            # Do speedtest with carrier name - retry up to 3 times (2 retries)
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                install_cancelled_check()
                download, upload = do_speedtest(device, carrier_name)
                if download > 0.0 or upload > 0.0:
                    # Success - at least one speed is > 0
                    sims[device]['download'] = download
                    sims[device]['upload'] = upload
                    return True
                else:
                    if attempt < max_attempts:
                        carrier_info = f' ({carrier_name})' if carrier_name else ''
                        retry_msg = f'Speedtest attempt {attempt} failed for {port_sim}{carrier_info}, retrying...'
                        cp.log(retry_msg)
                        write_log(retry_msg)
                        time.sleep(2)  # Wait before retry
            
            # All attempts failed
            carrier_info = f' ({carrier_name})' if carrier_name else ''
            error_msg = f'All {max_attempts} speedtest attempts failed for {port_sim}{carrier_info}'
            cp.log(error_msg)
            write_log(error_msg)
            sims[device]['download'] = sims[device]['upload'] = 0.0
            return False
    except Exception as e:
        port_display = get_display_port(device) or get_sim_port(device) or ''
        sim_slot = get_sim_slot(device) or ''
        port_sim = (port_display + ' ' + sim_slot).strip() if (port_display or sim_slot) else 'SIM'
        error_msg = f'Error testing {port_sim}: {e}'
        cp.log(error_msg)
        write_log(error_msg)
        sims[device]['download'] = sims[device]['upload'] = 0.0
        return False

def get_ncm_api_keys():
    """Get NCM API keys from router certificate management."""
    return cp.get_ncm_api_keys()

def get_ncm_groups(api_keys):
    """Get all groups from NCM API using ncm library."""
    try:
        ncm.set_api_keys(api_keys)
        # Try to get all groups at once using limit="all"
        try:
            groups = ncm.get_groups(limit='all')
            if groups:
                cp.log(f'Retrieved {len(groups)} groups from NCM (using limit=all)')
                return groups
        except:
            pass
        
        # If limit="all" doesn't work, use pagination with limit=500
        all_groups = []
        limit = 500
        offset = 0
        
        while True:
            groups = ncm.get_groups(limit=limit, offset=offset)
            if not groups:
                break
            all_groups.extend(groups)
            # If we got fewer than the limit, we've reached the end
            if len(groups) < limit:
                break
            offset += limit
        
        cp.log(f'Retrieved {len(all_groups)} groups from NCM (using pagination)')
        return all_groups
    except Exception as e:
        cp.log(f"Error getting NCM groups: {e}")
        return None

def match_carrier_group(carrier_name, groups, fastest_sim_device=None):
    """Match group by carrier name (default) or SIM slot (if appdata 'group_by_sim' exists).
    Returns (group_id, group_name) or None."""
    if not groups:
        return None
    use_carrier = use_carrier_matching()
    group_keyword = cp.get_appdata('group_keyword') or 'prod'
    group_keyword_upper = group_keyword.upper()
    if use_carrier:
        # Use existing carrier matching logic
        if not carrier_name:
            return None
        
        # Normalize carrier name variations
        carrier_upper = carrier_name.upper()
        if 'VZW' in carrier_upper or 'VERIZON' in carrier_upper:
            carrier_name = 'Verizon'
        elif 'ATT' in carrier_upper or 'AT&T' in carrier_upper:
            carrier_name = 'ATT'
        elif 'TMO' in carrier_upper or 'T-MOBILE' in carrier_upper:
            carrier_name = 'T-Mobile'
        
        # Strip special characters from carrier name, keep only alphanumeric, dashes, and underscores
        carrier_clean = re.sub(r'[^a-zA-Z0-9\-_]', '', carrier_name)
        
        if not carrier_clean:
            return None
        
        carrier_clean_upper = carrier_clean.upper()
        
        for group in groups:
            group_name = group.get('name', '')
            group_name_upper = group_name.upper()
            # Check if group name contains both the keyword and carrier name
            if group_keyword_upper in group_name_upper and carrier_clean_upper in group_name_upper:
                # Return group ID (extract from resource_url or use id field)
                group_id = group.get('id')
                if not group_id:
                    # Extract ID from resource_url if id not available
                    resource_url = group.get('resource_url', '')
                    if resource_url:
                        parts = resource_url.rstrip('/').split('/')
                        group_id = parts[-1] if parts else None
                if group_id:
                    return (group_id, group_name)
    else:
        # Use SIM slot matching (when group_by_sim appdata exists)
        if not fastest_sim_device:
            return None
        
        # Get SIM slot identifier from the fastest SIM device
        sim_slot = None
        try:
            sim_info = cp.get(f'status/wan/devices/{fastest_sim_device}/info/sim')
            if sim_info:
                sim_slot = sim_info.upper()  # e.g., "sim1" -> "SIM1"
        except Exception as e:
            cp.log(f'Error getting SIM slot for {fastest_sim_device}: {e}')
            return None
        
        if not sim_slot:
            return None
        
        # Get port for dual-modem disambiguation (e.g., "Internal SIM1" vs "MC400 SIM1")
        port_display = get_display_port(fastest_sim_device)
        
        # Search groups: try port+sim first (e.g., "Internal SIM1"), fall back to sim-only
        for group in groups:
            group_name = group.get('name', '')
            group_name_upper = group_name.upper()
            if group_keyword_upper not in group_name_upper:
                continue
            if sim_slot not in group_name_upper:
                continue
            # If port is available, prefer groups that also contain the port name
            if port_display and port_display.upper() in group_name_upper:
                group_id = group.get('id')
                if not group_id:
                    resource_url = group.get('resource_url', '')
                    if resource_url:
                        parts = resource_url.rstrip('/').split('/')
                        group_id = parts[-1] if parts else None
                if group_id:
                    return (group_id, group_name)
        
        # Fallback: match by keyword + sim_slot only (no port distinction)
        for group in groups:
            group_name = group.get('name', '')
            group_name_upper = group_name.upper()
            if group_keyword_upper in group_name_upper and sim_slot in group_name_upper:
                group_id = group.get('id')
                if not group_id:
                    resource_url = group.get('resource_url', '')
                    if resource_url:
                        parts = resource_url.rstrip('/').split('/')
                        group_id = parts[-1] if parts else None
                if group_id:
                    return (group_id, group_name)
    
    return None

def set_router_group(router_id, group_id, api_keys):
    """Set router group in NCM using ncm library and verify success."""
    try:
        ncm.set_api_keys(api_keys)
        instance = ncm.get_ncm_instance()
        return instance.v2.assign_router_to_group(router_id, group_id)
    except Exception as e:
        cp.log(f"Error setting router group: {e}")
        write_log(f"Error setting router group: {e}")
        return False

def run_auto_install():
    """Main auto-install process."""
    global log_filename, install_cancelled
    install_cancelled = False
    global created_rule_ids
    created_rule_ids = set()
    rule_states = {}
    sims = {}
    try:
        # Get system_id and version for log filename and header
        system_id = get_system_id()
        version = get_version()
        timestamp = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        log_filename = f'AutoInstall_{system_id}_{timestamp}.txt'
        try:
            start_timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            with open(log_filename, 'w') as f:
                f.write('AutoInstall Log\n')
                f.write('=' * 50 + '\n')
                f.write(f'Version: {version}\n')
                f.write(f'System ID: {system_id}\n')
                f.write(f'Started: {start_timestamp}\n')
                f.write('=' * 50 + '\n\n')
        except:
            pass
        
        update_status('running', 'Starting auto-install process...', 5)
        time.sleep(0.5)
        install_cancelled_check()
        cp.log('Starting auto-install process...')
        
        # Wait for WAN connection
        update_status('running', 'Waiting for WAN connection...', 10)
        time.sleep(0.5)
        install_cancelled_check()
        cp.wait_for_wan_connection()
        
        update_status('running', 'Detecting SIMs...', 15)
        time.sleep(0.5)
        install_cancelled_check()
        sims = find_sims()
        if not sims:
            update_status('error', 'No SIMs found', 0)
            time.sleep(0.5)
            return
        num_sims = len(sims)
        if num_sims < 2:
            error_msg = f'At least 2 SIMs required, found {num_sims}'
            cp.log(error_msg)
            write_log(error_msg)
            update_status('error', error_msg, 0)
            time.sleep(0.5)
            return
        cp.log(f'Found {num_sims} SIM(s) to test')
        write_log(f'Found {num_sims} SIM(s) to test')
        
        # Clean up any leftover speedtest routes from previous runs
        for sim in sims:
            cleanup_all_speedtest_routes_for_device(sim)
        
        # Only get API keys and groups when moving to group or writing custom1/custom2
        api_keys = None
        groups = []
        needs_api_keys = use_group_mode() or has_appdata('custom1') or has_appdata('custom2')
        if needs_api_keys:
            update_status('running', 'Getting NCM API keys...', 17)
            time.sleep(0.5)
            api_keys = get_ncm_api_keys()
            if not api_keys or not all([api_keys.get('X-ECM-API-ID'), api_keys.get('X-ECM-API-KEY'), api_keys.get('X-CP-API-ID'), api_keys.get('X-CP-API-KEY')]):
                update_status('error', 'Missing NCM API keys', 0)
                time.sleep(0.5)
                return
            
            if use_group_mode():
                update_status('running', 'Getting NCM groups...', 19)
                time.sleep(0.5)
                groups = get_ncm_groups(api_keys)
                if not groups:
                    update_status('error', 'Failed to get NCM groups', 0)
                    time.sleep(0.5)
                    return
        
        # Track original def_conn_state and disabled per rule for cleanup
        rule_states = {}
        
        # Find which SIM is currently connected by checking connection_state
        connected_sim = None
        for sim in sims:
            try:
                status = cp.get(f'status/wan/devices/{sim}/status')
                if status and status.get('connection_state') == 'connected':
                    connected_sim = sim
                    break
            except:
                continue
        
        # If no connected SIM found, try to find one that's connecting
        if not connected_sim:
            for sim in sims:
                try:
                    status = cp.get(f'status/wan/devices/{sim}/status')
                    if status and status.get('connection_state') in ['connecting', 'authenticating']:
                        connected_sim = sim
                        break
                except:
                    continue
        
        # If still no connected SIM, use the first one and wait for connection
        if not connected_sim:
            connected_sim = list(sims.keys())[0]
        
        # Build ordered list: connected first, then the rest
        sims_to_test = [connected_sim] + [s for s in sims if s != connected_sim]
        # If two SIMs share the same rule, separate them by duplicating with trigger_string per port/sim
        ensure_sims_have_distinct_rules(list(sims.keys()), rule_states)
        ensure_original_rule_states_captured(list(sims.keys()), rule_states)
        time.sleep(2)
        progress_base = 20
        progress_per_sim = int((78 - progress_base) / max(1, num_sims))
        progress_half = max(1, progress_per_sim // 2)
        tested_count = 0
        for idx, current_sim in enumerate(sims_to_test):
            install_cancelled_check()
            set_install_target_sim(current_sim)
            prev_sim = sims_to_test[idx - 1] if idx > 0 else None
            sim_number = None
            try:
                sim_info = cp.get(f'status/wan/devices/{current_sim}/info/sim')
                if sim_info:
                    sim_number = sim_info.upper()
            except:
                pass
            sim_label = sim_number if sim_number else f'SIM {idx + 1}/{num_sims}'
            port = get_display_port(current_sim) or get_sim_port(current_sim) or ''
            carrier_name = ''
            try:
                diag = cp.get(f'status/wan/devices/{current_sim}/diagnostics')
                if diag:
                    carrier_name = diag.get('CARRID', '') or ''
            except:
                pass
            port_sim = (port + ' ' + sim_label).strip() if (port or sim_label) else sim_label
            carrier_suffix = f' ({carrier_name})' if carrier_name else ''
            sim_start = progress_base + idx * progress_per_sim
            prog_testing = sim_start + progress_half
            sim_already_connected = (idx == 0)
            if not sim_already_connected:
                prog_switch = sim_start
                update_status('running', f'Switching to {port_sim}{carrier_suffix}...', prog_switch, target_sim=current_sim)
                time.sleep(0.5)
                if not switch_to_sim(current_sim, list(sims.keys()), rule_states):
                    update_status('running', 'Normalizing Config...', prog_switch)
                    time.sleep(0.5)
                    cleanup_wan_profile_changes(rule_states)
                    update_status('error', f'Failed to switch to {port_sim}{carrier_suffix}', 0)
                    time.sleep(0.5)
                    return
                time.sleep(3)
                if not modem_state(current_sim, 'connected'):
                    error_msg = f'Failed to connect {port_sim}{carrier_suffix} after activating'
                    cp.log(error_msg)
                    write_log(error_msg)
                    update_status('running', 'Normalizing Config...', prog_switch)
                    time.sleep(0.5)
                    cleanup_wan_profile_changes(rule_states)
                    update_status('error', error_msg, 0)
                    time.sleep(0.5)
                    return
            diagnostics = cp.get(f'status/wan/devices/{current_sim}/diagnostics')
            carrier_name = diagnostics.get('CARRID', '') if diagnostics else ''
            carrier_info = f' ({carrier_name})' if carrier_name else ''
            update_status('running', f'Testing {port_sim}{carrier_info}...', prog_testing, target_sim=current_sim)
            time.sleep(0.5)
            if not test_sim(current_sim, sims):
                error_msg = f'Failed to test {port_sim}{carrier_info} after all retries'
                cp.log(error_msg)
                write_log(error_msg)
                update_status('running', 'Normalizing Config...', prog_testing)
                time.sleep(0.5)
                cleanup_wan_profile_changes(rule_states)
                update_status('error', error_msg, 0)
                time.sleep(0.5)
                return
            tested_count += 1
        update_status('running', 'Normalizing Config...', 80)
        time.sleep(0.5)
        cleanup_wan_profile_changes(rule_states)
        time.sleep(2)
        update_status('running', 'Waiting for WAN Connection...', 82)
        time.sleep(0.5)
        cp.wait_for_wan_connection()
        
        # Find fastest SIM
        router_id = cp.get('status/ecm/client_id')
        fastest_sim = None
        fastest_download = 0.0
        for sim in sims:
            download = sims[sim].get('download', 0.0)
            if download > fastest_download:
                fastest_download = download
                fastest_sim = sim
        
        if fastest_sim:
                fastest_diagnostics = sims[fastest_sim].get('diagnostics', {})
                carrier = fastest_diagnostics.get('CARRID', '')
                iccid = fastest_diagnostics.get('ICCID', '')
                iccid_info = f', ICCID: {iccid}' if iccid else ''
                score_info = ''
                score, lbl = rsrp_rsrq_to_score(fastest_diagnostics)
                if score is not None:
                    score_info = f', {lbl or "4G/5G"} Score: {score}' if lbl else f', Score: {score}'
                sim_slot = get_sim_slot(fastest_sim)
                port_display = get_display_port(fastest_sim) or get_sim_port(fastest_sim) or ''
                port_sim = (port_display + ' ' + (sim_slot or '')).strip() if (port_display or sim_slot) else (sim_slot or fastest_sim)
                result_msg = f'Fastest SIM: {port_sim} with {fastest_download:.2f}Mbps download, Carrier: {carrier}{iccid_info}{score_info}'
                cp.log(result_msg)
                write_log(result_msg)
                
                min_speed = get_min_speed()
                if min_speed is not None and fastest_download < min_speed:
                    error_msg = f'No SIM meets minimum speed {min_speed}Mbps. Fastest: {fastest_download:.2f}Mbps'
                    cp.log(error_msg)
                    write_log(error_msg)
                    update_status('error', error_msg, 0)
                    time.sleep(0.5)
                    return
                
                if carrier or fastest_sim:
                    group_match = None
                    group_id = None
                    group_name = None
                    if use_group_mode():
                        if not router_id:
                            update_status('error', 'Router not connected to NCM (required for group mode)', 0)
                            time.sleep(0.5)
                            return
                        group_match = match_carrier_group(carrier, groups, fastest_sim)
                        if group_match:
                            group_id, group_name = group_match
                            if use_carrier_matching():
                                cp.log(f'Matched group "{group_name}" using carrier matching (carrier: {carrier})')
                                write_log(f'Matched group "{group_name}" using carrier matching (carrier: {carrier})')
                            else:
                                sim_slot = get_sim_slot(fastest_sim)
                                sim_slot_str = sim_slot if sim_slot else 'unknown'
                                cp.log(f'Matched group "{group_name}" using SIM slot matching (SIM: {sim_slot_str})')
                                write_log(f'Matched group "{group_name}" using SIM slot matching (SIM: {sim_slot_str})')
                    else:
                        update_status('running', 'Reprioritizing WAN profiles by download speed...', 86)
                        time.sleep(0.5)
                        reprioritize_wan_by_speed(sims)
                    
                    # Flush log file before reading for alert
                    try:
                        with open(log_filename, 'a') as f:
                            f.flush()
                            os.fsync(f.fileno())
                    except:
                        pass

                    # Send alert PREEMPTIVELY (before moving router to group or if no match)
                    # (Once router is moved, the app is removed, so we must send alert now)
                    # Alert contains the current install log contents
                    try:
                        appdata = cp.get('config/system/sdk/appdata')
                        disable_alerts = next((x["value"] for x in appdata if x.get("name", "").lower() == "disable_alerts"), None)
                        if disable_alerts is None:
                            # Build alert message with structured format
                            try:
                                # Extract Started timestamp from log file
                                started_timestamp = None
                                try:
                                    with open(log_filename, 'r') as f:
                                        for line in f:
                                            if line.startswith('Started:'):
                                                started_timestamp = line.split('Started:')[1].strip()
                                                break
                                except:
                                    pass
                                
                                # Build alert message with SIM results
                                alert_parts = ['AutoInstall Results']
                                
                                if started_timestamp:
                                    alert_parts.append(f'Started: {started_timestamp}')
                                
                                if use_group_mode():
                                    if group_match:
                                        alert_parts.append(f'Group: {group_name}')
                                    else:
                                        if use_carrier_matching():
                                            alert_parts.append(f'Group: No matching group found for carrier: {carrier}')
                                        else:
                                            sim_slot = get_sim_slot(fastest_sim)
                                            sim_slot_str = sim_slot if sim_slot else 'unknown'
                                            alert_parts.append(f'Group: No matching group found for SIM: {sim_slot_str}')
                                else:
                                    alert_parts.append('WAN reprioritized by download speed')
                                
                                # Get diagnostic fields for formatting
                                diag_fields = get_diagnostic_fields()
                                
                                # Add SIM results
                                for sim in sims:
                                    # Get actual SIM number from modem status
                                    sim_number = None
                                    try:
                                        sim_info = cp.get(f'status/wan/devices/{sim}/info/sim')
                                        if sim_info:
                                            sim_number = sim_info.upper()  # e.g., "sim1" -> "SIM1"
                                    except:
                                        pass
                                    
                                    sim_diagnostics = sims[sim].get('diagnostics', {})
                                    sim_carrier = sim_diagnostics.get('CARRID', 'Unknown')
                                    sim_iccid = sim_diagnostics.get('ICCID', '')
                                    sim_download = sims[sim].get('download', 0.0)
                                    sim_upload = sims[sim].get('upload', 0.0)
                                    
                                    port_display = get_display_port(sim) or get_sim_port(sim) or ''
                                    sim_label = sim_number if sim_number else sim
                                    prefix = (port_display + ' ' + sim_label).strip() if (port_display or sim_label) else sim_label
                                    sim_part = f'{prefix} | {sim_carrier}'
                                    if sim_iccid:
                                        sim_part += f' ICCID={sim_iccid}'
                                    sim_part += f' - Download: {sim_download:.2f}Mbps, Upload: {sim_upload:.2f}Mbps'
                                    score, lbl = rsrp_rsrq_to_score(sim_diagnostics)
                                    if score is not None:
                                        sim_part += f', {lbl or "4G/5G"} Score: {score}' if lbl else f', Score: {score}'
                                    
                                    # Add diagnostics
                                    diag_values = []
                                    for field in diag_fields:
                                        diag_value = sim_diagnostics.get(field)
                                        if diag_value is not None:
                                            diag_values.append(f'{field}={diag_value}')
                                    
                                    if diag_values:
                                        sim_part += ', ' + ', '.join(diag_values)
                                    
                                    alert_parts.append(sim_part)
                                
                                alert_message = ' | '.join(alert_parts)
                                
                                # Limit alert message length to avoid protocol/size issues
                                if len(alert_message) > 4000:
                                    alert_message = alert_message[:3997] + '...'
                                
                                cp.log(f'Created structured alert message: {len(alert_message)} characters')
                            except Exception as e:
                                cp.log(f'Error building alert message: {e}')
                                write_log(f'Error building alert message: {e}')
                                # Fallback to basic message if build fails
                                if use_group_mode() and group_match:
                                    alert_message = f'AutoInstall Results | Group: {group_name} | Error building alert: {e}'
                                elif use_group_mode():
                                    if use_carrier_matching():
                                        alert_message = f'AutoInstall Results | No matching group found for carrier: {carrier} | Error building alert: {e}'
                                    else:
                                        sim_slot = get_sim_slot(fastest_sim)
                                        sim_slot_str = sim_slot if sim_slot else 'unknown'
                                        alert_message = f'AutoInstall Results | No matching group found for SIM: {sim_slot_str} | Error building alert: {e}'
                                else:
                                    alert_message = f'AutoInstall Results | WAN reprioritized | Error building alert: {e}'
                            cp.alert(alert_message)
                            update_status('running', 'Sending results alert...', 90)
                            time.sleep(1)  # Sleep 1 second for alert to be sent
                        else:
                            cp.log('Alerts disabled via SDK appdata "disable_alerts"')
                    except Exception as e:
                        cp.log(f'Error checking/sending results alert: {e}')
                    
                    # Check for custom1/custom2 appdata and set NCM custom fields (requires API keys)
                    try:
                        custom1_exists = has_appdata('custom1')
                        custom2_exists = has_appdata('custom2')
                        if (custom1_exists or custom2_exists) and api_keys and router_id:
                            # Build results string
                            timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                            result_parts = []
                            
                            # Get diagnostic fields for formatting (use a subset: DBM, SINR, SRVC_TYPE)
                            diag_fields_subset = ['DBM', 'SINR', 'SRVC_TYPE']
                            
                            for sim in sims:
                                # Get actual SIM number from modem status
                                sim_number = None
                                try:
                                    sim_info = cp.get(f'status/wan/devices/{sim}/info/sim')
                                    if sim_info:
                                        sim_number = sim_info.upper()  # e.g., "sim1" -> "SIM1"
                                except:
                                    pass
                                
                                sim_diagnostics = sims[sim].get('diagnostics', {})
                                sim_carrier = sim_diagnostics.get('CARRID', 'Unknown')
                                sim_iccid = sim_diagnostics.get('ICCID', '')
                                sim_download = sims[sim].get('download', 0.0)
                                sim_upload = sims[sim].get('upload', 0.0)
                                
                                port_display = get_display_port(sim) or get_sim_port(sim) or ''
                                sim_label = sim_number if sim_number else sim
                                prefix = (port_display + ' ' + sim_label).strip() if (port_display or sim_label) else sim_label
                                sim_part = f'{prefix} | {sim_carrier}'
                                if sim_iccid:
                                    sim_part += f' ICCID={sim_iccid}'
                                sim_part += f' dl: {sim_download:.2f}Mbps, ul: {sim_upload:.2f}Mbps'
                                score, lbl = rsrp_rsrq_to_score(sim_diagnostics)
                                if score is not None:
                                    sim_part += f', {lbl or "4G/5G"} Score: {score}' if lbl else f', Score: {score}'
                                
                                # Add selected diagnostics
                                diag_values = []
                                for field in diag_fields_subset:
                                    diag_value = sim_diagnostics.get(field)
                                    if diag_value is not None:
                                        diag_values.append(f'{field}={diag_value}')
                                
                                if diag_values:
                                    sim_part += ', ' + ', '.join(diag_values)
                                
                                result_parts.append(sim_part)
                            
                            results_string = f'{timestamp} ' + ' | '.join(result_parts)
                            
                            if custom1_exists:
                                try:
                                    ncm.set_api_keys(api_keys)
                                    instance = ncm.get_ncm_instance()
                                    result = instance.v2.set_custom1(router_id, results_string)
                                    if result and isinstance(result, str) and result.startswith('ERROR:'):
                                        cp.log(f'Error setting custom1: {result}')
                                    else:
                                        cp.log(f'Set custom1: {results_string}')
                                except Exception as e:
                                    cp.log(f'Error setting custom1: {e}')
                            
                            if custom2_exists:
                                try:
                                    ncm.set_api_keys(api_keys)
                                    instance = ncm.get_ncm_instance()
                                    result = instance.v2.set_custom2(router_id, results_string)
                                    if result and isinstance(result, str) and result.startswith('ERROR:'):
                                        cp.log(f'Error setting custom2: {result}')
                                    else:
                                        cp.log(f'Set custom2: {results_string}')
                                except Exception as e:
                                    cp.log(f'Error setting custom2: {e}')
                    except Exception as e:
                        cp.log(f'Error checking/setting custom fields: {e}')
                    
                    if use_group_mode() and group_match:
                        update_status('running', f'Moving router to group: {group_name}...', 95)
                        time.sleep(0.5)
                        write_results_appdata(sims)
                        complete_msg = 'Auto-install process complete!'
                        cp.log(complete_msg)
                        write_log(complete_msg)
                        try:
                            with open(log_filename, 'a') as f:
                                f.flush()
                                os.fsync(f.fileno())
                        except:
                            pass 
                        update_status('complete', complete_msg, 100)
                        time.sleep(0.5)
                                
                        # Move the router (this will remove the app if successful)
                        result = set_router_group(router_id, group_id, api_keys)
                        
                        # Check for errors: result can be False, an error string starting with "ERROR:", or None
                        if result is False or (isinstance(result, str) and result.startswith('ERROR:')):
                            # Move failed - update status back to error (app is still running)
                            error_msg = f'Failed to set router group: {result if result else "Connection error"}'
                            cp.log(error_msg)
                            write_log(error_msg)
                            
                            # Write final failure message
                            failure_msg = 'Auto-install process failed!'
                            cp.log(failure_msg)
                            write_log(failure_msg)
                            
                            # Flush log file to ensure error is written
                            try:
                                with open(log_filename, 'a') as f:
                                    f.flush()
                                    os.fsync(f.fileno())
                            except:
                                pass
                            
                            # Update UI status to error
                            update_status('error', error_msg, 0)
                            time.sleep(0.5)
                            return
                        # If successful, app is removed so we can't update status (but it's already at 100%)
                    elif use_group_mode() and not group_match:
                        # Group mode but no matching group - fail
                        if use_carrier_matching():
                            no_group_msg = f'No matching group found for carrier: {carrier}'
                            error_status_msg = f'No matching group found for carrier: {carrier}'
                        else:
                            sim_slot = get_sim_slot(fastest_sim)
                            sim_slot_str = sim_slot if sim_slot else 'unknown'
                            no_group_msg = f'No matching group found for SIM: {sim_slot_str}'
                            error_status_msg = f'No matching group found for SIM: {sim_slot_str}'
                        
                        cp.log(no_group_msg)
                        write_log(no_group_msg)
                        update_status('error', error_status_msg, 0)
                        cp.log('Auto-install process failed!')
                        time.sleep(0.5)
                        return False
                    else:
                        # Reprioritize mode - complete successfully
                        write_results_appdata(sims)
                        complete_msg = 'Auto-install process complete! WAN reprioritized by download speed.'
                        cp.log(complete_msg)
                        # Build SIM lines for UI (format: Internal SIM1 | T-Mobile | 150.1Mbps)
                        sorted_by_download = sorted(sims.keys(), key=lambda s: sims[s].get('download', 0.0), reverse=True)
                        result_lines = []
                        for sim_device in sorted_by_download:
                            diag = sims[sim_device].get('diagnostics', {}) or {}
                            carrier = (diag.get('CARRID') or '').strip() or 'Unknown'
                            down = sims[sim_device].get('download', 0.0)
                            port_display = get_display_port(sim_device) or get_sim_port(sim_device) or ''
                            sim_slot = get_sim_slot(sim_device)
                            sim_display = (sim_slot or sim_device).upper() if (sim_slot or sim_device) else ''
                            prefix = (port_display + ' ' + sim_display).strip() if (port_display or sim_display) else ''
                            line = (prefix + ' | ' if prefix else '') + carrier + ' | %.1fMbps' % down
                            result_lines.append(line)
                            cp.log(line)
                            write_log(line)
                        display_msg = complete_msg + '\n' + '\n'.join(result_lines) if result_lines else complete_msg
                        update_status('complete', display_msg, 100)
                        time.sleep(0.5)
                else:
                    no_carrier_msg = 'No carrier information available'
                    cp.log(no_carrier_msg)
                    write_log(no_carrier_msg)
                    update_status('error', 'No carrier information available', 0)
                    cp.log('Auto-install process failed!')
                    time.sleep(0.5)
                    return False
        else:
            min_speed = get_min_speed()
            if min_speed is not None:
                error_msg = f'No SIM meets minimum speed {min_speed}Mbps. No SIM had successful speedtest.'
                cp.log(error_msg)
                write_log(error_msg)
                update_status('error', error_msg, 0)
                time.sleep(0.5)
                return
        
    except InstallCancelledException:
        cp.log('Auto-install cancelled by user')
        write_log('Auto-install cancelled by user')
        update_status('running', 'Normalizing Config...', 86)
        time.sleep(0.5)
        if rule_states:
            cleanup_wan_profile_changes(rule_states)
        for sim_device in sims:
            cleanup_all_speedtest_routes_for_device(sim_device)
        update_status('error', 'Cancelled by user', 0)
        time.sleep(0.5)
    except Exception as e:
        cp.log(f'Error in auto-install process: {e}')
        write_log(f'Error in auto-install process: {e}')
        update_status('running', 'Normalizing Config...', 86)
        time.sleep(0.5)
        all_rules_to_restore = dict(rule_states) if rule_states else {}
        global original_rule_states
        for rid in original_rule_states:
            if rid not in all_rules_to_restore:
                all_rules_to_restore[rid] = {}
        if all_rules_to_restore:
            cleanup_wan_profile_changes(all_rules_to_restore)
        for sim_device in sims:
            cleanup_all_speedtest_routes_for_device(sim_device)
        update_status('error', f'Error: {str(e)}', 0)
        cp.log('Auto-install process failed!')
        time.sleep(0.5)

if __name__ == '__main__':
    cp.log('Starting...')
    web_port = get_web_port()
    cp.log('Access the web interface at http://<router-ip>:%d/' % web_port)
    get_password()
    application = tornado.web.Application(
        [
            (r"/install", InstallHandler),
            (r"/cancel", CancelHandler),
            (r"/status", StatusHandler),
            (r"/signal", SignalHandler),
            (r"/connect", ConnectHandler),
            (r"/switch_sims", SwitchSimsHandler),
            (r"/log", LogHandler),
            (r"/logview", LogViewHandler),
            (r"/favicon\.ico", FaviconHandler),
            (r"/", MainHandler),
            (r"/(.*)", FallbackStaticHandler, {"path": "./"}),
        ],
        default_handler_class=DefaultHandler,
    )
    application.listen(web_port)
    if has_appdata('autostart'):
        if has_appdata('results'):
            cp.log('Autostart enabled but results already exist - skipping. Delete "results" appdata to re-run.')
        else:
            cp.log('Autostart enabled, no results found - starting auto-install process')
            def delayed_autostart():
                time.sleep(3)
                run_auto_install()
            thread = threading.Thread(target=delayed_autostart)
            thread.daemon = True
            thread.start()
    tornado.ioloop.IOLoop.instance().start()
