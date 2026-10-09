"""dsds_wan_verify - connectivity verification and failover for DSDS modems.

Dual SIM Dual Standby modems expose both SIM slots as separate WAN
devices but can only connect one at a time. Swapping slots takes about
30 seconds, which is fast enough to treat as a failover action rather
than a maintenance operation.

This app:
  * runs per-slot IP Verify ping tests, bound to that slot's WAN device,
    with only the connected slot's test armed
  * runs per-slot HTTP GET/HEAD tests from the app, source-bound to the
    slot's WAN IP
  * watches signal metrics on both slots - including the disconnected one,
    which a DSDS modem keeps reporting - and fails over or back on
    configurable thresholds
  * serves a web UI for configuration and live status

See readme.md for the API details and measured switch timing.
"""

import json
import os
import signal
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import appconfig
import cp
import dsds
import monitor as monitor_mod

PORT = 8000
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_STATIC_DIR = os.path.join(_SCRIPT_DIR, 'static')

_MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.ttf': 'font/ttf',
    '.json': 'application/json',
}

MON = None
SERVER = None
_shutdown = threading.Event()


def _app_version():
    try:
        import configparser
        parser = configparser.ConfigParser()
        parser.read(os.path.join(_SCRIPT_DIR, 'package.ini'))
        for section in parser.sections():
            return '%s.%s.%s' % (
                parser.get(section, 'version_major', fallback='0'),
                parser.get(section, 'version_minor', fallback='0'),
                parser.get(section, 'version_patch', fallback='0'))
    except Exception:
        pass
    return '0.0.0'


def _device_info():
    info = {'app_version': _app_version(), 'router_model': 'N/A',
            'serial_number': 'N/A', 'mac_address': 'N/A',
            'firmware_version': 'N/A'}
    for field, path in (('router_model', 'status/product_info/product_name'),
                        ('serial_number',
                         'status/product_info/manufacturing/serial_num'),
                        ('mac_address', 'status/product_info/mac0')):
        try:
            value = cp.get(path)
            if value:
                info[field] = str(value)
        except Exception:
            pass
    try:
        parts = [cp.get('status/fw_info/major_version'),
                 cp.get('status/fw_info/minor_version'),
                 cp.get('status/fw_info/patch_version')]
        parts = [str(p) for p in parts if p is not None]
        if parts:
            info['firmware_version'] = '.'.join(parts)
    except Exception:
        pass
    return info


class Handler(BaseHTTPRequestHandler):
    """Web UI and JSON API."""

    server_version = 'dsds_wan_verify'

    def log_message(self, fmt, *args):
        # The router log is shared; HTTP access lines would drown out the
        # app's own messages.
        pass

    # -- response helpers -----------------------------------------------

    def _send(self, body, content_type, status=200, extra=None):
        if isinstance(body, str):
            body = body.encode('utf-8')
        try:
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, data, status=200):
        self._send(json.dumps(data), 'application/json; charset=utf-8', status)

    def _file(self, path, content_type):
        try:
            with open(path, 'rb') as handle:
                self._send(handle.read(), content_type)
        except (IOError, OSError):
            self._send('Not found', 'text/plain; charset=utf-8', 404)

    def _body(self):
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except (TypeError, ValueError):
            return {}
        if length <= 0:
            return {}
        try:
            raw = self.rfile.read(length).decode('utf-8')
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    # -- routing ---------------------------------------------------------

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ('/', '/index.html'):
            self._file(os.path.join(_SCRIPT_DIR, 'index.html'),
                       'text/html; charset=utf-8')
        elif path == '/api/status':
            self._json(MON.snapshot())
        elif path == '/api/config':
            # `slot` is the flat default set; `slot_by_key` carries the
            # per-slot variant, which differs because the default
            # priority is derived from the SIM number. A client seeding a
            # never-configured slot should prefer slot_by_key.
            self._json({'slots': MON.conf['slots'],
                        'defaults': {
                            'slot': appconfig.SLOT_DEFAULTS,
                            'slot_by_key': {
                                key: appconfig.slot_defaults(key)
                                for key in (MON.slots or {})},
                        },
                        'metrics': [{'key': k, 'label': l, 'unit': u}
                                    for k, l, u in dsds.SIGNAL_METRICS]})
        elif path == '/api/info':
            self._json(_device_info())
        elif path == '/api/help':
            for name in ('readme.md', 'README.md'):
                full = os.path.join(_SCRIPT_DIR, name)
                if os.path.isfile(full):
                    self._file(full, 'text/plain; charset=utf-8')
                    return
            self._send('No readme found.', 'text/plain; charset=utf-8', 404)
        elif path.startswith('/static/'):
            self._static(path)
        else:
            self._send('Not found', 'text/plain; charset=utf-8', 404)

    def _static(self, path):
        rel = path[len('/static/'):].replace('..', '')
        full = os.path.join(_STATIC_DIR, rel)
        if not os.path.isfile(full):
            self._send('Not found', 'text/plain; charset=utf-8', 404)
            return
        ext = os.path.splitext(full)[1].lower()
        self._file(full, _MIME_TYPES.get(ext, 'application/octet-stream'))

    def do_POST(self):
        path = urlparse(self.path).path
        data = self._body()

        if path == '/api/config':
            self._save_config(data)
        elif path == '/api/switch':
            self._manual_switch()
        elif path == '/api/http_test':
            self._adhoc_http(data)
        elif path == '/api/clear_tests':
            self._clear_tests()
        else:
            self._json({'error': 'not found'}, 404)

    # -- actions ---------------------------------------------------------

    def _save_config(self, data):
        incoming_slots = data.get('slots')
        if not isinstance(incoming_slots, dict):
            self._json({'error': 'expected {"slots": {...}}'}, 400)
            return

        if not appconfig.save({'slots': incoming_slots}):
            self._json({'error': 'could not write config to appdata'}, 500)
            return
        conf = MON.reload_config()
        cp.log('Configuration updated via web UI')
        self._json({'ok': True, 'slots': conf['slots']})

    def _manual_switch(self):
        ok, message = MON.do_switch('requested from the web UI', manual=True)
        self._json({'ok': ok, 'message': message}, 200 if ok else 400)

    def _adhoc_http(self, data):
        """Run an HTTP test right now, so a URL can be checked before saving."""
        import verify
        slot_key = data.get('slot')
        slots = MON.slots or {}
        slot = slots.get(slot_key)
        if not slot:
            self._json({'error': 'unknown slot %r' % slot_key}, 400)
            return
        if not slot.get('connected') or not slot.get('ip_address'):
            self._json({'error': 'slot %s is not connected, so an HTTP test '
                                 'cannot be sourced from it'
                                 % dsds.slot_label(slot)}, 400)
            return
        try:
            timeout = float(data.get('timeout') or 2)
        except (TypeError, ValueError):
            timeout = 2.0
        # Retries included, so Test Now reports the same verdict the
        # monitored test would rather than failing on a single blip.
        try:
            retry_count = max(0, min(10, int(data.get('retry_count') or 0)))
        except (TypeError, ValueError):
            retry_count = 0
        try:
            retry_interval = max(1.0, min(60.0, float(
                data.get('retry_interval') or 2)))
        except (TypeError, ValueError):
            retry_interval = 2.0

        ok, detail = verify.http_check_with_retries(
            url=str(data.get('url') or '').strip(),
            method=str(data.get('method') or 'GET'),
            timeout=max(1.0, min(120.0, timeout)),
            source_ip=slot['ip_address'],
            expect_status=data.get('expect_status') or [],
            verify_tls=bool(data.get('verify_tls')),
            retry_count=retry_count,
            retry_interval=retry_interval,
            stop_event=_shutdown,
        )
        detail['ok'] = ok
        self._json(detail)

    def _clear_tests(self):
        import verify
        try:
            verify.remove_all_managed()
            MON._reconcile_signature = None
            with MON.lock:
                MON.armed_tests = {}
                MON.ping_results = {}
            self._json({'ok': True})
        except Exception as e:
            self._json({'error': str(e)}, 500)


def serve():
    global SERVER
    try:
        # Threaded, because several endpoints legitimately block for a
        # long time: a manual switch takes ~30s and a retrying HTTP test
        # can take (retries + 1) x timeout. On a single-threaded server
        # those would freeze the dashboard and its status polling.
        SERVER = ThreadingHTTPServer(('', PORT), Handler)
        SERVER.daemon_threads = True
        SERVER.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        cp.log('Web server started on port %d' % PORT)
        SERVER.serve_forever()
    except OSError as e:
        cp.log('Could not start web server on port %d: %s' % (PORT, e))
    except Exception as e:
        cp.log('Web server error: %s' % e)


def _handle_signal(signum, frame):
    cp.log('Received signal %s, shutting down' % signum)
    _shutdown.set()
    if SERVER:
        try:
            threading.Thread(target=SERVER.shutdown, daemon=True).start()
        except Exception:
            pass


def main():
    global MON
    cp.log('Starting dsds_wan_verify v%s...' % _app_version())

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _handle_signal)
        except (ValueError, OSError):
            pass

    # Share the shutdown event so an HTTP worker sleeping between
    # retries exits promptly instead of holding up the restart.
    MON = monitor_mod.Monitor(stop_event=_shutdown)

    thread = threading.Thread(target=serve, name='web')
    thread.daemon = True
    thread.start()

    slots = dsds.discover_slots()
    if slots:
        for key in sorted(slots):
            slot = slots[key]
            cp.log('Found DSDS slot %s: instance %s, %s%s'
                   % (dsds.slot_label(slot), slot.get('dsds_instance'),
                      slot.get('connection_state'),
                      ' (active)' if slot.get('active_sib') else ''))
    else:
        cp.log('No DSDS modem found yet. The app will keep looking; the web '
               'UI is available on port %d.' % PORT)

    # Only tests that can *fail* a slot count as arming it. A failback
    # minimum on its own just gates where the app may move to.
    #
    # Walked over the DISCOVERED slots rather than over MON.conf['slots'],
    # which only lists slots that have something stored in appdata. Ping
    # and signal are on by default, so a router with nothing stored is
    # fully armed while that dict is empty - reading the dict directly
    # would report "no tests enabled" on exactly the fresh install where
    # the defaults are doing the work.
    configured = [key for key in (slots or {})
                  if any(appconfig.slot_config(MON.conf, key).get(flag)
                         for flag in ('ping_enabled', 'http_enabled',
                                      'signal_enabled'))]
    if configured:
        cp.log('Failover is armed for slot(s) %s. A switch costs ~30s of '
               'downtime, so it only fires after a configured test fails '
               'repeatedly.' % ', '.join(sorted(configured)))
    else:
        cp.log('No tests are enabled yet, so no slot can fail and nothing '
               'will switch. Configure ping, signal, or HTTP tests per SIM '
               'slot in the web UI on port %d.' % PORT)

    while not _shutdown.is_set():
        try:
            MON.tick()
        except SystemExit:
            raise
        except Exception as e:
            cp.log('Monitor error: %s' % e)
        _shutdown.wait(monitor_mod.POLL_INTERVAL)

    cp.log('dsds_wan_verify stopped')


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        cp.log('Fatal error: %s' % exc)
        # restart = true in package.ini means the router relaunches the app
        # whenever the process exits, so falling off the end here would
        # become a hot restart loop. Idle instead.
        try:
            while True:
                time.sleep(60)
        except Exception:
            sys.exit(1)
