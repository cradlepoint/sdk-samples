"""NTP_GPS - NTP server whose time comes from GPS NMEA instead of the system clock.

Time source: poll status/gps/nmea and treat each change in the sentence array as a new GPS
second. This is consistent across all router models (R1900, R2400, ...), unlike the GNSS daemon
socket whose timing sentences differ by hardware. NCOS publishes the array with a modest,
somewhat drifting delay (a few tenths of a second), which a fixed latency constant corrects for.

Each epoch gives one sample: (GPS UTC time + latency) - monotonic clock at arrival. A polled
sample can only ever arrive late, so the largest offset in a short window is the least-delayed
one, closest to the true GPS second; NTP replies on UDP port 1123 (configurable) are built
from it.

If GPS is lost, the server keeps answering from the monotonic clock for a holdover period,
then reports itself unsynchronized (LI=3, stratum 16) so clients stop trusting it.
"""
import signal
import socket
import struct
import threading
import time
from collections import deque
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple

import cp
from pynmeagps import NMEAReader

APP_NAME = 'NTP_GPS'

STATUS_PATH = 'status/ntp_gps'  # app publishes its own sync state here (RAM only, not persisted)

DEFAULT_PORT = 1123
DEFAULT_HOLDOVER = 300        # seconds to keep serving after the last GPS sample
STATUS_TREE_LATENCY = 0.8     # GPS second -> status/gps/nmea publish delay, added to each sample

TIME_SENTENCES = ('RMC', 'ZDA', 'GGA', 'GLL')
MAX_DATE_SKEW = 5.0           # seconds a time-of-day sentence may differ from the RMC/ZDA time
POLL_INTERVAL = 0.2           # seconds between status/gps/nmea reads
MAX_POLL_GAP = 0.5            # discard an edge if the polls around it were further apart

SAMPLE_WINDOW = 30            # offset samples kept (about 30 s at 1 Hz)
STEP_THRESHOLD = 1.0          # GPS time disagreeing with the estimate by more resets the window
STATUS_LOG_INTERVAL = 60      # seconds between status log lines
DRIFT_RATE = 15e-6            # assumed free-run drift of the monotonic clock (s/s)

NTP_EPOCH_OFFSET = 2208988800  # seconds from 1900-01-01 to 1970-01-01
NTP_PACKET_LEN = 48
NTP_PRECISION = -20            # ~1 microsecond clock read resolution
REFID_GPS = b'GPS\x00'
REFID_INIT = b'INIT'

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
# Status logging and main
# ---------------------------------------------------------------------------------------------

def publish_status(clock: GpsClock, server: NtpServer, synced: bool,
                   gps_now: Optional[float], dispersion: float,
                   age: Optional[float], count: int) -> None:
    """Publish the complete sync-state object to STATUS_PATH.

    A status-tree PUT REPLACES, so this must always be the whole object (see gotchas.md).
    Times are epoch seconds / numeric offsets, never a %Z abbreviation. Values live in RAM
    only and outlive the app, so shutdown overwrites this with an unsynced object.
    """
    status = {
        'synced': synced,
        'source': clock.source,
        'sentence': clock.sentence,
        'samples': count,
        'sample_age_s': round(age, 1) if age is not None else None,
        'dispersion_ms': round(dispersion * 1000, 1),
        'holdover_s': round(clock.holdover, 0),
        'ntp_requests': server.requests,
        'ntp_port': server.port,
        'gps_unix': round(gps_now, 3) if gps_now is not None else None,
        'system_offset_s': round(time.time() - gps_now, 3) if gps_now is not None else None,
        'updated': round(time.time(), 3),
    }
    try:
        cp.put(STATUS_PATH, status)
    except Exception as e:
        cp.log(f'Unable to publish {STATUS_PATH}: {e}')


def log_status(clock: GpsClock, server: NtpServer) -> bool:
    """Log sync state, publish it to STATUS_PATH; returns whether currently synced."""
    gps_now = clock.now()
    _, dispersion, age, count = clock.snapshot()
    synced = gps_now is not None
    if synced:
        cp.log(f'Synced to GPS via {clock.source} ({clock.sentence}): {count} samples, '
               f'last {age:.1f}s ago, '
               f'dispersion {dispersion * 1000:.0f}ms, '
               f'system clock offset {time.time() - gps_now:+.3f}s, '
               f'{server.requests} NTP requests served')
    elif age is not None:
        cp.log(f'NOT synced: last GPS sample {age:.0f}s ago (holdover {clock.holdover:.0f}s), '
               f'{server.requests} NTP requests served')
    else:
        cp.log(f'NOT synced: waiting for valid GPS time, {server.requests} NTP requests served')
    publish_status(clock, server, synced, gps_now, dispersion, age, count)
    return synced


def status_loop(clock: GpsClock, server: NtpServer) -> None:
    """Log every STATUS_LOG_INTERVAL seconds, and immediately when sync is gained or lost."""
    synced = log_status(clock, server)
    last_log = time.monotonic()
    while running:
        time.sleep(1)
        now_synced = clock.now() is not None
        if now_synced != synced or time.monotonic() - last_log >= STATUS_LOG_INTERVAL:
            if now_synced != synced:
                cp.log('GPS time sync acquired' if now_synced else 'GPS time sync LOST')
            synced = log_status(clock, server)
            last_log = time.monotonic()


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
    cp.log(f'Config: port={port}, holdover={holdover:.0f}s')

    clock = GpsClock(holdover)
    server = None
    while running and server is None:
        try:
            server = NtpServer(clock, port)
        except Exception as e:
            cp.log(f'Unable to bind UDP port {port}: {e}, retrying in 10s')
            time.sleep(10)
    if server is None:
        return

    threading.Thread(target=server.serve, daemon=True).start()
    threading.Thread(target=status_loop, args=(clock, server), daemon=True).start()

    run_status_tree(clock)

    # The status value outlives the app, so clear it to an unsynced object on the way out
    # rather than leaving a stale "synced" snapshot frozen in the tree.
    _, dispersion, age, count = clock.snapshot()
    publish_status(clock, server, False, None, dispersion, age, count)
    cp.log(f'{APP_NAME} stopped')


if __name__ == '__main__':
    main()
