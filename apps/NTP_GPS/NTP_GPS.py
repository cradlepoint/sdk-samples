"""NTP_GPS - NTP server whose time comes from GPS NMEA instead of the system clock.

Time source (in order of preference):
1. The GNSS daemon socket (127.0.0.1:17488, see the ibr1700_gnss app). After the NMEA command
   it pushes every sentence as soon as gnssd has it, so the arrival of the first sentence of
   each epoch marks the GPS second with only a few milliseconds of jitter.
2. Fallback for models without the socket: poll status/gps/nmea and treat each change in the
   array as a new second. NCOS publishes that array with a larger, drifting delay.

Each epoch gives one sample: (GPS UTC time + latency) - monotonic clock at arrival. The largest
offset in a short window is the least-delayed sample, and NTP replies on UDP port 1123
(configurable) are built from it.

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

DEFAULT_PORT = 1123
DEFAULT_HOLDOVER = 300        # seconds to keep serving after the last GPS sample
DEFAULT_FIX_LATENCY_MS = 141  # receiver+daemon fix latency: how far the daemon's fix_uptime
                              # trails the true GPS-second epoch (R2400, NCOS 7.26.100, measured
                              # against time.apple.com to +-1 ms run-to-run). Subtracted from the
                              # GPS time. Fixed per hardware/firmware; tune via appdata.
STATUS_TREE_LATENCY = 0.8     # GPS second -> status/gps/nmea publish delay (fallback source)

GNSS_ADDR = ('127.0.0.1', 17488)
GNSS_COMMAND = b'ALL\r\n'     # needed for $PCPTMGPSTIME / $PCPTMDBG timing sentences
GNSS_IDLE_TIMEOUT = 5.0       # reconnect if the socket is silent this long
MAX_LINE = 4096               # drop a partial line that grows past this (no newline seen)
MIN_EPOCH_GAP = 0.5           # epochs arriving closer together are history backlog, not live

TIME_SENTENCES = ('RMC', 'ZDA', 'GGA', 'GLL')
MAX_DATE_SKEW = 5.0           # seconds a time-of-day sentence may differ from the RMC/ZDA time
POLL_INTERVAL = 0.2           # fallback: seconds between status/gps/nmea reads
MAX_POLL_GAP = 0.5            # fallback: discard an edge if the polls around it were further apart
FALLBACK_PERIOD = 60          # fallback: seconds to poll before retrying the socket

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

    def _best_offset(self) -> Optional[float]:
        if not self.offsets:
            return None
        if self.source == 'gnss-socket':
            # Socket samples are already corrected to the true GPS second via the daemon's
            # timestamps, so they scatter symmetrically. The median rejects jitter without bias.
            return sorted(self.offsets)[len(self.offsets) // 2]
        # Polling (fallback): a sample can only arrive late, shrinking its offset. The largest
        # offset in the window is the least-delayed, hence closest to the true second.
        return max(self.offsets)

    def add_sample(self, gps_unix: float, mono: float, source: str) -> None:
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
# Primary source: GNSS daemon socket
# ---------------------------------------------------------------------------------------------

class EpochTracker:
    """Turns the GNSS daemon's timing sentences into exact (gps_unix, gps_second_mono) samples.

    Each GPS second, within a burst that arrives in a few ms, gnssd emits (verified on an
    R2400, NCOS 7.26.100):

      $G?RMC ...,status,...,date,...
          The true UTC second and whether the fix is valid.

      $PCPTMDBG,UTC Time Tag <fix_uptime> system time <sys_uptime>
          <fix_uptime>  - the daemon's uptime value for this GPS second, already corrected for
                          receiver fix latency (fractional, e.g. ...495).
          <sys_uptime>  - the daemon's uptime-clock reading when it emitted the line, tens of ms
                          later. The app records time.monotonic() = `mono` at the same instant.

    The daemon's uptime clock and the app's time.monotonic() are both CLOCK_MONOTONIC but have
    DIFFERENT ORIGINS, so they differ by a constant C = mono - sys_uptime, measured from the same
    line (re-measuring every second absorbs slow skew between the two clocks). That removes the
    socket transport delay exactly:  gps_second_mono = fix_uptime + C.

    fix_uptime itself still trails the true GPS-second epoch by the receiver+daemon fix latency
    (~141 ms on an R2400, constant to +-1 ms), which is NOT exposed in any sentence, so it is
    subtracted as a fixed, tunable offset (fix_latency). That is the one calibrated constant left.

    (The $PCPTMGPSTIME third field is NOT hhmmss UTC - its seconds run past 60, so it is a GPS
    time-of-week count. The UTC second is taken from RMC instead.)
    """

    def __init__(self, fix_latency: float):
        self.fix_latency = fix_latency  # receiver+daemon lag of fix_uptime behind true GPS second
        self.utc = None                 # type: Optional[float]   UTC unix sec from current RMC/ZDA
        self.have_fix = False           # latest RMC reported status 'A'
        self.prev_arrival = None        # type: Optional[float]

    def feed(self, line: str, mono: float) -> Optional[Tuple[float, float]]:
        talker = line[3:6]
        if talker == 'RMC':
            try:
                msg = NMEAReader.parse(line)
                self.have_fix = msg.status == 'A'
                if self.have_fix and msg.date and msg.time:
                    self.utc = datetime.combine(msg.date, msg.time, timezone.utc).timestamp()
            except Exception:
                pass
            return None

        if line.startswith('$PCPTMDBG,UTC Time Tag'):
            return self._on_tag(line, mono)
        return None

    def _on_tag(self, line: str, mono: float) -> Optional[Tuple[float, float]]:
        # "$PCPTMDBG,UTC Time Tag <fix_uptime> system time <sys_uptime>*cksum"
        #   fix_uptime  - daemon uptime of THIS epoch's GPS second (fractional, already corrected
        #                 for receiver fix latency)
        #   sys_uptime  - daemon uptime clock reading when it emitted the line, a few tens of ms
        #                 later. mono - sys_uptime is the app<->daemon monotonic clock offset.
        # This line arrives right after the epoch's RMC, so self.utc is the matching UTC second.
        try:
            tail = line.split('UTC Time Tag', 1)[1]
            fix_uptime = float(tail.split('system time', 1)[0].strip())
            sys_uptime = float(tail.split('system time', 1)[1].split('*', 1)[0].strip())
        except (IndexError, ValueError):
            return None

        # Skip the history burst: live epochs arrive ~1 s apart, backlog back-to-back.
        live = self.prev_arrival is not None and (mono - self.prev_arrival) >= MIN_EPOCH_GAP
        self.prev_arrival = mono
        if not live or not self.have_fix or self.utc is None:
            return None

        # Convert the daemon's fix_uptime to the app's monotonic clock, then step back by the
        # receiver+daemon fix latency so the sample marks the true GPS-second epoch.
        clock_offset = mono - sys_uptime    # app monotonic - daemon uptime
        gps_second_mono = fix_uptime + clock_offset - self.fix_latency
        return self.utc, gps_second_mono


def run_gnss_socket(clock: GpsClock, fix_latency: float) -> bool:
    """Stream NMEA from the GNSS socket until it fails. Returns False if it never connected."""
    try:
        sock = socket.create_connection(GNSS_ADDR, timeout=5)
    except Exception as e:
        cp.log(f'GNSS socket {GNSS_ADDR[0]}:{GNSS_ADDR[1]} unavailable: {e}')
        return False

    cp.log(f'Connected to GNSS socket {GNSS_ADDR[0]}:{GNSS_ADDR[1]}')
    tracker = EpochTracker(fix_latency)
    buf = b''
    try:
        sock.settimeout(GNSS_IDLE_TIMEOUT)
        sock.sendall(GNSS_COMMAND)
        while running:
            try:
                data = sock.recv(4096)
            except socket.timeout:
                cp.log('GNSS socket idle, reconnecting')
                break
            mono = time.monotonic()
            if not data:
                cp.log('GNSS socket closed by daemon, reconnecting')
                break
            buf += data
            while b'\n' in buf:
                raw, buf = buf.split(b'\n', 1)
                line = raw.strip().decode('ascii', errors='replace')
                sample = tracker.feed(line, mono) if line.startswith('$') else None
                if sample:
                    clock.add_sample(sample[0], sample[1], 'gnss-socket')
            if len(buf) > MAX_LINE:
                buf = b''
    except Exception as e:
        cp.log(f'GNSS socket error: {e}')
    finally:
        try:
            sock.close()
        except Exception:
            pass
    return True


# ---------------------------------------------------------------------------------------------
# Fallback source: status/gps/nmea polling
# ---------------------------------------------------------------------------------------------

def time_sentences(sentences) -> Tuple[str, ...]:
    """The time-bearing sentences (any talker: GP, GN, GL...) in a status/gps/nmea snapshot."""
    return tuple(s.strip() for s in sentences
                 if isinstance(s, str) and s[3:6] in TIME_SENTENCES)


def nmea_to_unix(sentences: Tuple[str, ...]) -> Optional[float]:
    """Freshest GPS UTC time in a status-tree snapshot as Unix time, or None without a fix.

    The date comes from RMC (or ZDA). The time of day is the newest one among RMC, ZDA and
    fix-valid GGA/GLL, because RMC/ZDA in the status tree can lag GGA by one epoch.
    """
    day = None          # type: Optional[date]
    day_time = None     # time of day of the sentence that supplied the date
    times = []          # type: List
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
        times.append(msg_time)

    if not has_fix or day is None or day_time is None:
        return None

    anchor = datetime.combine(day, day_time)
    best = None  # type: Optional[datetime]
    for msg_time in times:
        candidate = datetime.combine(day, msg_time)
        diff = (candidate - anchor).total_seconds()
        if diff < -43200:       # time of day wrapped past midnight after the dated sentence
            candidate += timedelta(days=1)
        elif diff > 43200:      # dated sentence is already past midnight
            candidate -= timedelta(days=1)
        if abs((candidate - anchor).total_seconds()) > MAX_DATE_SKEW:
            continue
        if best is None or candidate > best:
            best = candidate
    if best is None:
        return None
    return best.replace(tzinfo=timezone.utc).timestamp()


def run_status_tree(clock: GpsClock, duration: float) -> None:
    """Poll status/gps/nmea for `duration` seconds, feeding one sample per publish."""
    last_key = None             # type: Optional[Tuple[str, ...]]
    last_poll_mono = None       # type: Optional[float]
    end = time.monotonic() + duration
    while running and time.monotonic() < end:
        try:
            sentences = cp.get('status/gps/nmea')
            mono = time.monotonic()
            key = time_sentences(sentences) if isinstance(sentences, list) else None
            # A change seen between two closely spaced polls is a usable edge. The first
            # snapshot (or one after a poll gap) could be up to a second old.
            if key and key != last_key:
                if last_key is not None and last_poll_mono is not None \
                        and mono - last_poll_mono <= MAX_POLL_GAP:
                    gps_unix = nmea_to_unix(key)
                    if gps_unix is not None:
                        clock.add_sample(gps_unix + STATUS_TREE_LATENCY, mono, 'status-tree')
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

def log_status(clock: GpsClock, server: NtpServer) -> bool:
    """Log sync state; returns whether currently synced."""
    gps_now = clock.now()
    _, dispersion, age, count = clock.snapshot()
    if gps_now is not None:
        cp.log(f'Synced to GPS via {clock.source}: {count} samples, last {age:.1f}s ago, '
               f'dispersion {dispersion * 1000:.0f}ms, '
               f'system clock offset {time.time() - gps_now:+.3f}s, '
               f'{server.requests} NTP requests served')
        return True
    if age is not None:
        cp.log(f'NOT synced: last GPS sample {age:.0f}s ago (holdover {clock.holdover:.0f}s), '
               f'{server.requests} NTP requests served')
    else:
        cp.log(f'NOT synced: waiting for valid GPS time, {server.requests} NTP requests served')
    return False


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
    fix_latency = get_appdata_number('ntp_gps_fix_latency_ms', DEFAULT_FIX_LATENCY_MS, float) / 1000
    cp.log(f'Config: port={port}, holdover={holdover:.0f}s, fix_latency={fix_latency * 1000:.0f}ms')

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

    while running:
        if run_gnss_socket(clock, fix_latency):
            time.sleep(1)  # brief pause before reconnecting
        else:
            cp.log(f'Falling back to status/gps/nmea polling for {FALLBACK_PERIOD}s')
            run_status_tree(clock, FALLBACK_PERIOD)
    cp.log(f'{APP_NAME} stopped')


if __name__ == '__main__':
    main()
