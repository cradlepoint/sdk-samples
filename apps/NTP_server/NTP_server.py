"""NTP_server - an NTP server for the router that gets its time from GPS, plus a web UI.

Why this exists
---------------
Cradlepoint routers have no battery-backed real-time clock, so they boot at the 1970 epoch and
depend on NTP to learn the real time. On a router with GPS but no reachable internet NTP server,
this app fills that gap: it derives UTC from the GPS receiver and serves it over NTP so the
router (and any LAN client) can discipline its clock.

Time source
-----------
Poll status/gps/nmea and treat each change in the sentence array as a new GPS second. This is
consistent across router models (R1900, R2400, ...), unlike the GNSS daemon socket whose timing
sentences differ by hardware. NCOS publishes the array with a modest, somewhat drifting delay (a
few tenths of a second), which a fixed latency constant corrects for. Each epoch gives one
sample: (GPS UTC time + latency) - monotonic clock at arrival. A polled sample can only ever
arrive late, so the largest offset in a short window is the least-delayed one, closest to the
true GPS second; NTP replies on UDP port 1123 (configurable) are built from it.

Deferred NTP bind
-----------------
The NTP port is not opened until the first GPS fix is acquired. A router without an RTC polls
NTP once at startup (the poll interval can be up to 24h), so an early reply sent before GPS lock
would be unsynchronized (stratum 16), get discarded by the client, and leave the clock wrong
until the next long poll cycle. Keeping the socket closed until there is real GPS time means that
boot poll simply goes unanswered and the client retries on its normal backoff, getting a usable
stratum-1 reply the moment the port opens. If GPS is lost after startup, the server keeps
answering from the monotonic clock for a holdover period, then reports itself unsynchronized so
clients stop trusting it.

Status is published continuously
--------------------------------
status/ntp_gps is published from the very first second, including while still waiting for a fix
('state': 'waiting'), so an operator (or the web UI) can watch progress. It is NOT gated on GPS.

Web UI
------
A small web dashboard (default port 8000) shows all of the status, and lets a user set the
router's clock either from their browser's current time or from a manually picked date/time,
using control/system/clock/set_time. Handy for a router that has no time source at all yet.
"""
import http.server
import json
import os
import signal
import socket
import socketserver
import struct
import threading
import time
from collections import deque
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple

import cp
from pynmeagps import NMEAReader

APP_NAME = 'NTP_server'

STATUS_PATH = 'status/ntp_gps'  # app publishes its own sync state here (RAM only, not persisted)
CLOCK_SET_PATH = 'control/system/clock/set_time'  # PUT a Unix epoch to set the router clock

DEFAULT_PORT = 1123
DEFAULT_HOLDOVER = 300        # seconds to keep serving after the last GPS sample
STATUS_TREE_LATENCY = 0.8     # GPS second -> status/gps/nmea publish delay, added to each sample

WEB_PORT_BASE = 8000          # web UI port; if busy, step by WEB_PORT_STEP up to WEB_PORT_MAX
WEB_PORT_STEP = 10
WEB_PORT_MAX = 8100

TIME_SENTENCES = ('RMC', 'ZDA', 'GGA', 'GLL')
MAX_DATE_SKEW = 5.0           # seconds a time-of-day sentence may differ from the RMC/ZDA time
POLL_INTERVAL = 0.2           # seconds between status/gps/nmea reads
MAX_POLL_GAP = 0.5            # discard an edge if the polls around it were further apart

SAMPLE_WINDOW = 30            # offset samples kept (about 30 s at 1 Hz)
STEP_THRESHOLD = 1.0          # GPS time disagreeing with the estimate by more resets the window
DRIFT_RATE = 15e-6            # assumed free-run drift of the monotonic clock (s/s)

NTP_EPOCH_OFFSET = 2208988800  # seconds from 1900-01-01 to 1970-01-01
NTP_PACKET_LEN = 48
NTP_PRECISION = -20            # ~1 microsecond clock read resolution
REFID_GPS = b'GPS\x00'
REFID_INIT = b'INIT'

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_STATIC_DIR = os.path.join(_SCRIPT_DIR, 'static')

_MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.ttf': 'font/ttf',
    '.json': 'application/json',
}

running = True


class GpsClock:
    """Maps the local monotonic clock to GPS UTC time using per-epoch samples."""

    def __init__(self, holdover: float):
        self.holdover = holdover
        self.lock = threading.Lock()
        self.offsets = deque(maxlen=SAMPLE_WINDOW)  # gps_unix - monotonic
        self.last_sample_mono = None  # type: Optional[float]
        self.source = 'none'
        self.sentence = None  # type: Optional[str]  NMEA sentence the latest time came from

    def _best_offset(self) -> Optional[float]:
        if not self.offsets:
            return None
        # A polled sample can only arrive late, shrinking its offset. The largest offset in the
        # window is the least-delayed, hence closest to the true GPS second.
        return max(self.offsets)

    def add_sample(self, gps_unix: float, mono: float, source: str,
                   sentence: Optional[str] = None) -> None:
        offset = gps_unix - mono
        with self.lock:
            best = self._best_offset()
            if source != self.source:
                if self.offsets:
                    cp.log(f'Time source changed {self.source} -> {source}, resetting samples')
                self.offsets.clear()
                self.source = source
            elif best is not None and abs(offset - best) > STEP_THRESHOLD:
                cp.log(f'GPS time stepped by {offset - best:+.3f}s, resetting samples')
                self.offsets.clear()
            self.offsets.append(offset)
            self.last_sample_mono = mono
            # The winning sentence can alternate epoch to epoch (GGA vs RMC); track it for
            # display only, separately from `source`, so it never triggers a window reset.
            self.sentence = sentence

    def now(self) -> Optional[float]:
        """Current GPS-derived Unix time, or None if unsynchronized."""
        mono = time.monotonic()
        with self.lock:
            if not self.offsets or self.last_sample_mono is None:
                return None
            if mono - self.last_sample_mono > self.holdover:
                return None
            return mono + self._best_offset()

    def snapshot(self) -> Tuple[Optional[float], float, Optional[float], int]:
        """Returns (reference_time, dispersion_s, sample_age_s, sample_count)."""
        mono = time.monotonic()
        with self.lock:
            if not self.offsets or self.last_sample_mono is None:
                return None, 0.0, None, 0
            age = mono - self.last_sample_mono
            # Dispersion: spread of the middle of the window around the estimate, so a rare
            # outlier does not dominate. 10th-to-90th percentile band.
            ordered = sorted(self.offsets)
            lo = ordered[max(0, len(ordered) // 10)]
            hi = ordered[min(len(ordered) - 1, len(ordered) * 9 // 10)]
            ref = self.last_sample_mono + self._best_offset()
            return ref, (hi - lo) + age * DRIFT_RATE, age, len(self.offsets)


def get_appdata_number(name: str, default: float, cast=float):
    """Read a numeric appdata value, falling back to the default in code."""
    try:
        value = cp.get_appdata(name)
        if value not in (None, ''):
            return cast(value)
    except Exception as e:
        cp.log(f'Invalid appdata {name}: {e}, using {default}')
    return default


def set_router_clock(epoch: float) -> Tuple[bool, str]:
    """Set the router's system clock to the given Unix epoch via the control tree.

    Returns (ok, message). cp.put returns different envelopes on-router vs local REST, so check
    both 'status' and 'success' keys (see coding-standards.md).
    """
    try:
        epoch = int(round(float(epoch)))
    except (TypeError, ValueError):
        return False, 'invalid time value'
    if epoch < 946684800:  # 2000-01-01; reject obviously bogus (e.g. still-1970) values
        return False, 'time value is implausibly early'
    try:
        result = cp.put(CLOCK_SET_PATH, epoch)
        ok = True
        if isinstance(result, dict):
            if result.get('status') not in (None, 'ok') or result.get('success') is False:
                ok = False
        if ok:
            cp.log(f'Router clock set to {epoch} '
                   f'({time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(epoch))})')
            return True, 'clock set'
        return False, f'router rejected clock set: {result}'
    except Exception as e:
        cp.log(f'Error setting router clock: {e}')
        return False, str(e)


# ---------------------------------------------------------------------------------------------
# Time source: status/gps/nmea polling
# ---------------------------------------------------------------------------------------------

def time_sentences(sentences) -> Tuple[str, ...]:
    """The time-bearing sentences (any talker: GP, GN, GL...) in a status/gps/nmea snapshot."""
    return tuple(s.strip() for s in sentences
                 if isinstance(s, str) and s[3:6] in TIME_SENTENCES)


def nmea_to_unix(sentences: Tuple[str, ...]) -> Optional[Tuple[float, str]]:
    """Freshest GPS UTC time in a status-tree snapshot, as (unix_time, sentence_id), or None
    without a fix.

    The date comes from RMC (or ZDA). The time of day is the newest one among RMC, ZDA and
    fix-valid GGA/GLL, because RMC/ZDA in the status tree can lag GGA by one epoch. The returned
    sentence_id is the full NMEA id of the sentence that supplied the chosen time of day, e.g.
    'GPGGA' or 'GNRMC'.
    """
    day = None          # type: Optional[date]
    day_time = None     # time of day of the sentence that supplied the date
    times = []          # type: List[Tuple[object, str]]  (time_of_day, sentence_id)
    has_fix = False
    for sentence in sentences:
        try:
            msg = NMEAReader.parse(sentence)
        except Exception:
            continue
        msg_time = getattr(msg, 'time', None)
        if not msg_time:
            continue
        msg_id = msg.msgID
        if msg_id == 'RMC':
            if msg.status != 'A' or not msg.date:
                continue
            has_fix = True
            day, day_time = msg.date, msg_time
        elif msg_id == 'ZDA':
            try:
                if day is None:
                    day, day_time = date(msg.year, msg.month, msg.day), msg_time
            except Exception:
                continue
        elif msg_id == 'GGA':
            if not msg.quality:
                continue
            has_fix = True
        elif msg_id == 'GLL':
            if msg.status != 'A':
                continue
            has_fix = True
        # getattr(msg, 'identity', ...) is the full id incl. talker, e.g. 'GPGGA'.
        times.append((msg_time, getattr(msg, 'identity', msg_id)))

    if not has_fix or day is None or day_time is None:
        return None

    anchor = datetime.combine(day, day_time)
    best = None     # type: Optional[datetime]
    best_id = None  # type: Optional[str]
    for msg_time, sentence_id in times:
        candidate = datetime.combine(day, msg_time)
        diff = (candidate - anchor).total_seconds()
        if diff < -43200:       # time of day wrapped past midnight after the dated sentence
            candidate += timedelta(days=1)
        elif diff > 43200:      # dated sentence is already past midnight
            candidate -= timedelta(days=1)
        if abs((candidate - anchor).total_seconds()) > MAX_DATE_SKEW:
            continue
        if best is None or candidate > best:
            best, best_id = candidate, sentence_id
    if best is None:
        return None
    return best.replace(tzinfo=timezone.utc).timestamp(), best_id


def run_status_tree(clock: GpsClock) -> None:
    """Poll status/gps/nmea until shutdown, feeding one sample per publish."""
    last_key = None             # type: Optional[Tuple[str, ...]]
    last_poll_mono = None       # type: Optional[float]
    while running:
        try:
            sentences = cp.get('status/gps/nmea')
            mono = time.monotonic()
            key = time_sentences(sentences) if isinstance(sentences, list) else None
            # A change seen between two closely spaced polls is a usable edge. The first
            # snapshot (or one after a poll gap) could be up to a second old.
            if key and key != last_key:
                if last_key is not None and last_poll_mono is not None \
                        and mono - last_poll_mono <= MAX_POLL_GAP:
                    result = nmea_to_unix(key)
                    if result is not None:
                        gps_unix, sentence = result
                        clock.add_sample(gps_unix + STATUS_TREE_LATENCY, mono,
                                         'status/gps/nmea', sentence)
                last_key = key
            last_poll_mono = mono
        except Exception as e:
            cp.log(f'GPS poll error: {e}')
            last_poll_mono = None
            time.sleep(1)
        time.sleep(POLL_INTERVAL)


# ---------------------------------------------------------------------------------------------
# NTP server
# ---------------------------------------------------------------------------------------------

def to_ntp(unix_time: float) -> int:
    """Unix time to a 64-bit NTP timestamp (32.32 fixed point)."""
    t = unix_time + NTP_EPOCH_OFFSET
    seconds = int(t)
    fraction = int((t - seconds) * 4294967296)
    return ((seconds & 0xFFFFFFFF) << 32) | (fraction & 0xFFFFFFFF)


def to_short(seconds: float) -> int:
    """Seconds to NTP short format (16.16 fixed point), clamped."""
    return min(max(int(seconds * 65536), 0), 0xFFFFFFFF)


class NtpServer:
    """Minimal SNTP/NTP server (RFC 5905 server mode) backed by GpsClock."""

    def __init__(self, clock: GpsClock, port: int):
        self.clock = clock
        self.port = port
        self.requests = 0
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.settimeout(1.0)
        self.sock.bind(('0.0.0.0', port))

    def build_reply(self, request: bytes, recv_time: Optional[float]) -> Optional[bytes]:
        first = request[0]
        version = (first >> 3) & 0x07
        mode = first & 0x07
        if mode != 3:  # only answer client requests
            return None
        if version < 1 or version > 4:
            version = 4
        poll = struct.unpack('!b', request[2:3])[0]
        originate = request[40:48]  # client's transmit timestamp, echoed back verbatim

        ref_time, dispersion, _, _ = self.clock.snapshot()
        tx_time = self.clock.now()
        if recv_time is None or tx_time is None or ref_time is None:
            # Unsynchronized: LI=3 (alarm), stratum 16. Clients will reject the time.
            li, stratum, refid = 3, 16, REFID_INIT
            recv_time = tx_time = ref_time = time.time()
            dispersion = 16.0
        else:
            li, stratum, refid = 0, 1, REFID_GPS

        return struct.pack(
            '!BBbbII4sQ8sQQ',
            (li << 6) | (version << 3) | 4,  # mode 4 = server
            stratum,
            poll,
            NTP_PRECISION,
            0,                     # root delay: we are the reference
            to_short(dispersion),  # root dispersion
            refid,
            to_ntp(ref_time),
            originate,
            to_ntp(recv_time),
            to_ntp(tx_time),
        )

    def serve(self) -> None:
        cp.log(f'NTP server listening on UDP port {self.port}')
        while running:
            try:
                data, addr = self.sock.recvfrom(1024)
            except socket.timeout:
                continue
            except Exception as e:
                cp.log(f'NTP receive error: {e}')
                time.sleep(1)
                continue
            recv_time = self.clock.now()
            if len(data) < NTP_PACKET_LEN:
                continue
            try:
                reply = self.build_reply(data, recv_time)
                if reply:
                    self.sock.sendto(reply, addr)
                    self.requests += 1
            except Exception as e:
                cp.log(f'NTP reply error to {addr[0]}: {e}')
        try:
            self.sock.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------------------------

def format_times(gps_unix: Optional[float]) -> Tuple[Optional[str], Optional[str]]:
    """Format the GPS epoch as (utc_time, local_time) human-readable strings.

    Local time uses the router's timezone: on-router, the SDK process inherits TZ from
    config/system/timezone, so time.localtime() is already router-local and tracks DST. The
    offset is taken from %z (e.g. '-0700'); %Z is NOT used because it wrongly returns 'UTC'
    on this router regardless of the actual offset (see gotchas.md). Off-router these reflect
    the host machine's timezone, which only matters during local test runs.
    """
    if gps_unix is None:
        return None, None
    utc = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(gps_unix))
    local = time.strftime('%Y-%m-%d %H:%M:%S %z', time.localtime(gps_unix))
    return utc, local


def read_ntp_client() -> Tuple[Optional[str], Optional[int]]:
    """Read the router's own NTP client status: (last_server, sync_age_s).

    status/system/ntp reports where the router last got its time and how long ago. When this app
    is the router's NTP source, last_server points back at 127.0.0.1:<ntp_port>. Both may be
    absent before the router's first sync. Verified fields: last_server (str), sync_age (int s).
    """
    try:
        ntp = cp.get('status/system/ntp')
        if isinstance(ntp, dict):
            age = ntp.get('sync_age')
            return ntp.get('last_server'), int(age) if age is not None else None
    except Exception as e:
        cp.log(f'Unable to read status/system/ntp: {e}')
    return None, None


def build_status(clock: GpsClock, ntp_port: Optional[int], ntp_requests: int,
                 serving: bool) -> dict:
    """Assemble the full status/ntp_gps object.

    Always a complete object (a status-tree PUT REPLACES, see gotchas.md). Published from the
    first second so the 'waiting for GPS' phase is visible, not just the synced phase.
    """
    gps_now = clock.now()
    _, dispersion, age, count = clock.snapshot()
    synced = gps_now is not None
    if synced:
        state = 'synced'
    elif not serving:
        state = 'waiting'   # GPS never acquired; NTP port not yet open
    else:
        state = 'holdover' if age is not None else 'unsynced'
    utc_time, local_time = format_times(gps_now)
    # Router's own clock, for the web UI to compare against (it starts at 1970 with no RTC).
    router_now = None
    try:
        router_now = time.time()
    except Exception:
        pass
    # Format the router clock itself in both UTC and router-local time, using the same %z
    # numeric-offset convention as the GPS times (%Z lies on this router, see gotchas.md).
    router_utc, router_local = format_times(router_now)
    # Router timezone offset (e.g. '-0700'), informative context for the local time shown.
    tz_offset = time.strftime('%z', time.localtime(router_now)) if router_now is not None else None
    # Where the router last synced its own clock, and how long ago.
    ntp_last_server, ntp_sync_age = read_ntp_client()
    return {
        'state': state,
        'synced': synced,
        'serving': serving,
        'source': clock.source,
        'sentence': clock.sentence,
        'samples': count,
        'sample_age_s': round(age, 1) if age is not None else None,
        'dispersion_ms': round(dispersion * 1000, 1),
        'holdover_s': round(clock.holdover, 0),
        'ntp_requests': ntp_requests,
        'ntp_port': ntp_port,
        'tz_offset': tz_offset,
        'gps_unix': round(gps_now, 3) if gps_now is not None else None,
        'utc_time': utc_time,
        'local_time': local_time,
        'router_unix': round(router_now, 3) if router_now is not None else None,
        'router_utc': router_utc,
        'router_local': router_local,
        'system_offset_s': round(router_now - gps_now, 3)
            if (gps_now is not None and router_now is not None) else None,
        'ntp_last_server': ntp_last_server,
        'ntp_sync_age_s': ntp_sync_age,
        'updated': round(time.time(), 3),
    }


def publish_status(status: dict) -> None:
    try:
        cp.put(STATUS_PATH, status)
    except Exception as e:
        cp.log(f'Unable to publish {STATUS_PATH}: {e}')


# ---------------------------------------------------------------------------------------------
# Shared runtime state (read by the web server and the status loop)
# ---------------------------------------------------------------------------------------------

class AppState:
    """Live handles the web server and status loop read from."""

    def __init__(self, clock: GpsClock):
        self.clock = clock
        self.ntp_server = None   # type: Optional[NtpServer]
        self.web_port = None     # type: Optional[int]
        self.serving = False     # True once the NTP port is open

    def status(self) -> dict:
        ntp_port = self.ntp_server.port if self.ntp_server else None
        ntp_requests = self.ntp_server.requests if self.ntp_server else 0
        return build_status(self.clock, ntp_port, ntp_requests, self.serving)


# ---------------------------------------------------------------------------------------------
# Web server
# ---------------------------------------------------------------------------------------------

class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """Threaded HTTP server that skips the FQDN lookup in server_bind.

    http.server.HTTPServer.server_bind() calls socket.getfqdn(), which runs the router hostname
    through the IDNA codec and raises UnicodeError on non-conforming hostnames (see
    web-standards.md). No web client needs the FQDN, so bypass it.
    """
    daemon_threads = True
    allow_reuse_address = True

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)  # skips socket.getfqdn()
        host, port = self.socket.getsockname()[:2]
        self.server_name = host
        self.server_port = port


def make_web_handler(state: AppState):
    class WebHandler(http.server.BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def _send(self, code, body, ctype):
            if isinstance(body, str):
                body = body.encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _send_json(self, obj, code=200):
            self._send(code, json.dumps(obj), 'application/json; charset=utf-8')

        def do_GET(self):
            path = self.path.split('?')[0]
            if path in ('/', '/index.html'):
                self._serve_static('index.html')
            elif path == '/api/status':
                self._send_json(state.status())
            elif path.startswith('/static/'):
                self._serve_static(path.lstrip('/'))
            else:
                self._send(404, 'Not found', 'text/plain; charset=utf-8')

        def do_POST(self):
            path = self.path.split('?')[0]
            if path == '/api/set_time':
                self._handle_set_time()
            else:
                self._send(404, 'Not found', 'text/plain; charset=utf-8')

        def _handle_set_time(self):
            try:
                length = int(self.headers.get('Content-Length', 0))
                raw = self.rfile.read(length) if length else b''
                payload = json.loads(raw.decode('utf-8')) if raw else {}
            except Exception as e:
                self._send_json({'ok': False, 'message': f'bad request: {e}'}, 400)
                return
            epoch = payload.get('epoch')
            if epoch is None:
                self._send_json({'ok': False, 'message': 'missing epoch'}, 400)
                return
            ok, message = set_router_clock(epoch)
            self._send_json({'ok': ok, 'message': message,
                             'router_unix': round(time.time(), 3)},
                            200 if ok else 400)

        def _serve_static(self, rel):
            rel = rel.replace('..', '')
            if rel == 'index.html':
                full = os.path.join(_SCRIPT_DIR, 'index.html')
            elif rel.startswith('static/'):
                full = os.path.join(_SCRIPT_DIR, rel)
            else:
                full = os.path.join(_SCRIPT_DIR, rel)
            if not os.path.isfile(full):
                self._send(404, 'Not found', 'text/plain; charset=utf-8')
                return
            _, ext = os.path.splitext(full)
            ctype = _MIME_TYPES.get(ext.lower(), 'application/octet-stream')
            try:
                with open(full, 'rb') as f:
                    body = f.read()
                self._send(200, body, ctype)
            except (IOError, OSError):
                self._send(404, 'Not found', 'text/plain; charset=utf-8')

        def log_message(self, fmt, *args):
            pass  # quiet; NTP/status activity is logged elsewhere

    return WebHandler


def start_web_server(state: AppState) -> None:
    """Bind the web UI, stepping the port if the preferred one is in use."""
    handler = make_web_handler(state)
    port = WEB_PORT_BASE
    httpd = None
    while running and httpd is None and port <= WEB_PORT_MAX:
        try:
            httpd = ThreadingHTTPServer(('0.0.0.0', port), handler)
        except OSError as e:
            cp.log(f'Web port {port} unavailable ({e}), trying {port + WEB_PORT_STEP}')
            port += WEB_PORT_STEP
    if httpd is None:
        cp.log(f'Could not bind a web port in {WEB_PORT_BASE}-{WEB_PORT_MAX}, web UI disabled')
        return
    state.web_port = port
    cp.log(f'Web UI started on http://<router_ip>:{port}')
    threading.Thread(target=httpd.serve_forever, daemon=True).start()


# ---------------------------------------------------------------------------------------------
# Status loop and main
# ---------------------------------------------------------------------------------------------

def status_loop(state: AppState) -> None:
    """Publish status every second; log ONLY when the sync state changes."""
    last_state = None  # type: Optional[str]
    while running:
        status = state.status()
        if status['state'] != last_state:
            if status['state'] == 'synced':
                cp.log(f"GPS time sync acquired via {status['source']} "
                       f"({status['sentence']}): dispersion {status['dispersion_ms']:.0f}ms")
            elif last_state == 'synced':
                cp.log(f"GPS time sync LOST (state now {status['state']})")
            elif status['state'] == 'waiting':
                cp.log('Waiting for first GPS fix...')
            else:
                cp.log(f"NTP state: {status['state']}")
            last_state = status['state']
        publish_status(status)
        time.sleep(1)


def handle_signal(signum, frame):
    global running
    cp.log(f'Received signal {signum}, shutting down')
    running = False


def main():
    cp.log(f'Starting {APP_NAME}...')
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    port = get_appdata_number('ntp_gps_port', DEFAULT_PORT, int)
    holdover = get_appdata_number('ntp_gps_holdover', DEFAULT_HOLDOVER, float)
    cp.log(f'Config: ntp_port={port}, holdover={holdover:.0f}s')

    clock = GpsClock(holdover)
    state = AppState(clock)

    # Publish status and serve the web UI from the start, so the waiting-for-GPS phase is
    # visible and a user can set the clock manually even before GPS lock.
    threading.Thread(target=run_status_tree, args=(clock,), daemon=True).start()
    threading.Thread(target=status_loop, args=(state,), daemon=True).start()
    start_web_server(state)

    # Do NOT bind the NTP port until GPS is locked (see module docstring): a pre-fix reply is
    # stratum 16, gets discarded, and the router may not poll again for up to 24h.
    cp.log('Waiting for first GPS fix before opening the NTP port...')
    waited = 0.0
    while running and clock.now() is None:
        time.sleep(1)
        waited += 1
        if waited % 30 == 0:
            cp.log(f'Still waiting for GPS time ({waited:.0f}s), NTP port not yet open')
    if not running:
        return
    cp.log('GPS time acquired, opening NTP port')

    server = None
    while running and server is None:
        try:
            server = NtpServer(clock, port)
        except Exception as e:
            cp.log(f'Unable to bind UDP port {port}: {e}, retrying in 10s')
            time.sleep(10)
    if server is None:
        return
    state.ntp_server = server
    state.serving = True

    threading.Thread(target=server.serve, daemon=True).start()

    # Main thread parks here until shutdown; worker threads already run on their own.
    while running:
        time.sleep(1)

    # The status value outlives the app, so overwrite it with a stopped/unsynced object on the
    # way out rather than leaving a stale "synced" snapshot frozen in the tree.
    state.serving = False
    final = state.status()
    final['state'] = 'stopped'
    final['synced'] = False
    publish_status(final)
    cp.log(f'{APP_NAME} stopped')


if __name__ == '__main__':
    main()
