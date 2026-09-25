"""
Speedtest module - Multi-engine speed testing with concurrent multi-modem support.

Presents the small subset of the original Ookla Speedtest interface that
Mobile_Site_Survey uses, so the survey code stays engine-agnostic.

ENGINES - which binaries are bundled is fixed when the app is packaged, so
detect_binaries() runs once at startup and available_engines() then reports only
the engines this build can run. The default is the first available, following the
documented priority of Ookla (bring-your-own binary) then Netperf. iPerf3 is
never the default because only the user can supply its server address:

  ookla    Default when a licensed Ookla binary ('ookla', 'speedtest' or
           'speedtest-cli') has been put in the app directory. There is no Ookla
           license for SDK apps, so no binary is ever bundled or distributed -
           it is used if present and never required. The only engine that
           produces a results image URL. Pinned to a WAN with "-i <source_ip>".

  netperf  Default when no Ookla binary is present, and always selectable. The
           netperf service built into NCOS, driven through cp.speed_test(),
           which needs no server and no binary and pins the test to one WAN
           through its ifc_wan option - so no source routing is required.
           Latency and jitter come from a netperf TCP_RR run. netperf is a
           single shared router resource and cannot run concurrent tests, so
           modems are measured one at a time.

  iperf3   Bundled iperf3-arm64v8 binary against the user's own iperf3 server.
           Pinned to a WAN with "-B <source_ip>" plus "--bind-dev <iface>" (the
           pattern used by the speedtest_web app), falling back to "-B" alone
           where --bind-dev is not permitted. Note -B needs an IP address, not
           an interface name. Latency and jitter are derived from the TCP
           round-trip stats iperf3 reports for the sending side.

Every engine measures its own latency and jitter. They are left as None only
when the engine could not measure them.

USAGE:
    import speedtest
    speedtest.configure(engine='iperf3', iperf3_server='iperf.example.com',
                        iperf3_ports='5201-5210',
                        iperf3_options={'protocol': 'udp', 'bandwidth': '50M'})
    st = speedtest.Speedtest(source_address='10.0.0.1', interface='pmip3',
                             device='mdm-41949674')
    st.start()
    print(st.results.download, st.results.upload, st.results.ping,
          st.results.jitter)

PORT RANGES (iperf3 only):
    Surveys test every connected modem at the same time, so each test needs its
    own port. Ports are reserved from the configured range for the life of a
    test and a port that is busy or errors falls through to the next one.

IPERF3 TEST OPTIONS:
    iperf3 is the one engine whose test parameters are worth exposing, because
    the user owns the server on the other end. Every option below is passed
    straight through to the bundled binary, and every value is range checked
    here so a bad appdata entry cannot produce an unparseable command line:

      protocol       'tcp' or 'udp'          -u when udp
      duration       seconds per direction   -t
      parallel       simultaneous streams    -P
      bandwidth      target rate, e.g. 50M   -b
      bytes          volume instead of time  -n  (overrides duration)
      buffer_length  read/write buffer size  -l
      omit           seconds to discard      -O
      window         socket buffer size      -w
      no_delay       disable Nagle (TCP)     -N
      zero_copy      sendfile() (TCP)        -Z

    UDP changes what can be measured. There are no TCP round-trip stats, so
    latency comes back None, but iperf3 reports jitter and datagram loss
    directly and those are used instead. iperf3 also caps an unrestricted UDP
    test at 1 Mbit/s, so a bandwidth target is effectively required for UDP -
    configure() logs a warning when one is missing.
"""

import cp
import re
import subprocess
import json
import os
import threading
import time
from datetime import datetime

ENGINE_NETPERF = 'netperf'
ENGINE_IPERF3 = 'iperf3'
ENGINE_OOKLA = 'ookla'
ENGINES = (ENGINE_OOKLA, ENGINE_NETPERF, ENGINE_IPERF3)

OOKLA_BINARIES = ('ookla', 'speedtest', 'speedtest-cli')
IPERF3_BINARIES = ('iperf3', 'iperf3-arm64v8', 'iperf3-aarch64')

DEFAULT_DURATION = 10
DEFAULT_PORT = 5201

PROTOCOL_TCP = 'tcp'
PROTOCOL_UDP = 'udp'
IPERF3_PROTOCOLS = (PROTOCOL_TCP, PROTOCOL_UDP)

# Bounds for the numeric iperf3 options. 128 is iperf3's own compile-time limit
# on parallel streams; the duration and omit ceilings just keep a typo from
# turning one survey point into an hour-long test.
MAX_PARALLEL_STREAMS = 128
MAX_DURATION = 300
MAX_OMIT = 60

# A size-limited run (-n) has no time bound at all, so it gets a hard ceiling
# instead of "duration + grace". Without it, one stalled transfer would hang a
# survey indefinitely.
IPERF3_SIZE_TIMEOUT = 300

# iperf3 accepts a byte count with an optional K/M/G suffix for -b, -n, -l and
# -w. Anything else is rejected here rather than handed to the binary.
_SIZE_VALUE = re.compile(r'^\d+(\.\d+)?[kmgKMG]?$')

# The iperf3 test parameters, with the values used when nothing is configured.
DEFAULT_IPERF3_OPTIONS = {
    'protocol': PROTOCOL_TCP,
    'duration': DEFAULT_DURATION,
    'parallel': 1,
    'bandwidth': '',
    'bytes': '',
    'buffer_length': '',
    'omit': 0,
    'window': '',
    'no_delay': False,
    'zero_copy': False,
}

# TCP_RR is a request/response test, so it needs round trips rather than volume.
# Five seconds is plenty and keeps the extra leg from lengthening a survey.
NETPERF_RR_DURATION = 5

# Bundled binaries are detected once by detect_binaries(). An app's files are
# fixed when it is packaged and signed, so a binary cannot appear or disappear
# while the app is running - there is no reason to stat the filesystem per test.
_detect_lock = threading.Lock()
_binaries_detected = False
_ookla_binary = None
_iperf3_binary = None

# Module configuration, set by configure()
_config_lock = threading.Lock()
_engine = ENGINE_NETPERF
_iperf3_server = ''
_iperf3_port_start = DEFAULT_PORT
_iperf3_port_end = DEFAULT_PORT
_iperf3_options = dict(DEFAULT_IPERF3_OPTIONS)

# iperf3 port reservation, shared across concurrent modem tests
_port_condition = threading.Condition()
_ports_in_use = set()

# netperf is a single shared resource on the router - one test at a time
_netperf_lock = threading.Lock()


# =============================================================================
# CONFIGURATION
# =============================================================================

def parse_port_range(ports):
    """Parse "5201" or "5201-5210" into a (start, end) tuple.

    Returns (None, None) when the value cannot be understood.
    """
    try:
        text = str(ports).strip()
        if not text:
            return None, None
        if '-' in text:
            start_text, _, end_text = text.partition('-')
            start = int(start_text.strip())
            end = int(end_text.strip())
        else:
            start = int(text)
            end = start
        if not (0 < start < 65536) or not (0 < end < 65536):
            return None, None
        if end < start:
            start, end = end, start
        return start, end
    except Exception:
        return None, None


def _clean_choice(value, choices, current, field):
    """Return value if it is one of choices, else current."""
    candidate = str(value).strip().lower()
    if candidate in choices:
        return candidate
    cp.log(f'Invalid iPerf3 {field} "{value}" - keeping {current}')
    return current


def _clean_int(value, minimum, maximum, current, field):
    """Return value clamped into [minimum, maximum], else current."""
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        cp.log(f'Invalid iPerf3 {field} "{value}" - keeping {current}')
        return current
    if number < minimum or number > maximum:
        clamped = min(max(number, minimum), maximum)
        cp.log(f'iPerf3 {field} {number} out of range - using {clamped}')
        return clamped
    return number


def _clean_size(value, current, field):
    """Return a byte count with an optional K/M/G suffix, blank to disable."""
    text = str(value).strip()
    if not text:
        return ''
    if _SIZE_VALUE.match(text):
        return text
    cp.log(f'Invalid iPerf3 {field} "{value}" - expected a number with an '
           f'optional K, M or G suffix, keeping {current or "default"}')
    return current


def _clean_bool(value):
    """Coerce a checkbox value, which may arrive as "1"/"0"/True, to a bool."""
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in ('1', 'true', 'yes', 'on')


def _apply_iperf3_options(options):
    """Validate and store the iperf3 test options. Assumes _config_lock held."""
    global _iperf3_options
    if not isinstance(options, dict):
        cp.log(f'Ignoring iPerf3 options of type {type(options).__name__}')
        return

    current = _iperf3_options
    updated = dict(current)
    if 'protocol' in options:
        updated['protocol'] = _clean_choice(
            options['protocol'], IPERF3_PROTOCOLS, current['protocol'],
            'protocol')
    if 'duration' in options:
        updated['duration'] = _clean_int(
            options['duration'], 1, MAX_DURATION, current['duration'],
            'duration')
    if 'parallel' in options:
        updated['parallel'] = _clean_int(
            options['parallel'], 1, MAX_PARALLEL_STREAMS, current['parallel'],
            'parallel streams')
    if 'omit' in options:
        updated['omit'] = _clean_int(
            options['omit'], 0, MAX_OMIT, current['omit'], 'omit')
    for key, label in (('bandwidth', 'bandwidth'), ('bytes', 'size'),
                       ('buffer_length', 'buffer length'),
                       ('window', 'window size')):
        if key in options:
            updated[key] = _clean_size(options[key], current[key], label)
    for key in ('no_delay', 'zero_copy'):
        if key in options:
            updated[key] = _clean_bool(options[key])

    _iperf3_options = updated

    # iperf3 caps an unrestricted UDP test at 1 Mbit/s, which looks like a
    # terrible link rather than a missing setting, so say so out loud.
    if updated['protocol'] == PROTOCOL_UDP and not updated['bandwidth']:
        cp.log('iPerf3 UDP has no bandwidth target - iperf3 will cap the test '
               'at 1 Mbit/s. Set a target rate to measure the link.')


def configure(engine=None, iperf3_server=None, iperf3_ports=None,
              iperf3_options=None):
    """Set the active engine, iPerf3 target and iPerf3 test options.

    Safe to call at any time - the web UI calls it again whenever settings are
    saved so an engine change takes effect without restarting the app.
    """
    global _engine, _iperf3_server, _iperf3_port_start, _iperf3_port_end
    with _config_lock:
        if engine:
            candidate = str(engine).strip().lower()
            if candidate in ENGINES:
                _engine = candidate
            else:
                cp.log(f'Unknown speedtest engine "{engine}" - keeping {_engine}')
        if iperf3_server is not None:
            server = str(iperf3_server).strip()
            # Accept "host:5201-5210" as well as a bare hostname, so a legacy
            # combined value keeps working.
            if ':' in server:
                host, _, embedded_ports = server.partition(':')
                server = host.strip()
                if embedded_ports.strip() and iperf3_ports is None:
                    iperf3_ports = embedded_ports
            _iperf3_server = server
        if iperf3_ports is not None:
            start, end = parse_port_range(iperf3_ports)
            if start:
                _iperf3_port_start, _iperf3_port_end = start, end
            elif str(iperf3_ports).strip():
                cp.log(f'Invalid iPerf3 port range "{iperf3_ports}" - keeping '
                       f'{_iperf3_port_start}-{_iperf3_port_end}')
        if iperf3_options is not None:
            _apply_iperf3_options(iperf3_options)


def get_engine():
    """Return the configured engine setting."""
    with _config_lock:
        return _engine


def resolve_engine():
    """Return the engine that will actually run.

    Falls back to the default if the configured engine is not available in this
    build, which keeps a stale appdata value from disabling speedtests.
    """
    configured = get_engine()
    available = available_engines()
    if configured in available:
        return configured
    return available[0]


def get_iperf3_target():
    """Return the configured iPerf3 target as (server, port_start, port_end)."""
    with _config_lock:
        return _iperf3_server, _iperf3_port_start, _iperf3_port_end


def get_iperf3_options():
    """Return a copy of the iPerf3 test options.

    A copy, so a test that reads the options at its start keeps a consistent
    set even if the user saves new settings while it is running.
    """
    with _config_lock:
        return dict(_iperf3_options)


def _find_binary(names):
    """Return './name' for the first present binary, or None.

    Tar extraction on the router does not preserve the execute bit, so the
    binary is chmod'ed rather than tested with os.access().
    """
    for name in names:
        if os.path.exists(name):
            try:
                os.chmod(name, 0o755)
            except Exception as e:
                cp.log(f'Could not set execute permission on {name}: {e}')
            return './' + name
    return None


def detect_binaries():
    """Detect the bundled binaries once. Called at startup.

    Which binaries exist is fixed when the app is packaged, so this runs a
    single time and the result is reused for the life of the process.
    """
    global _binaries_detected, _ookla_binary, _iperf3_binary
    with _detect_lock:
        if _binaries_detected:
            return
        _ookla_binary = _find_binary(OOKLA_BINARIES)
        _iperf3_binary = _find_binary(IPERF3_BINARIES)
        _binaries_detected = True


def has_ookla():
    """Return True when an Ookla binary was found in the app directory."""
    detect_binaries()
    return _ookla_binary is not None


def has_iperf3():
    """Return True when an iperf3 binary was found in the app directory."""
    detect_binaries()
    return _iperf3_binary is not None


def available_engines():
    """Return the engines this build can actually run, in priority order.

    netperf is always present because it is built into NCOS. Ookla and iPerf3
    depend on a binary being bundled, so they are only offered when one is.
    The first entry is the default.
    """
    detect_binaries()
    engines = []
    if _ookla_binary:
        engines.append(ENGINE_OOKLA)
    engines.append(ENGINE_NETPERF)
    if _iperf3_binary:
        engines.append(ENGINE_IPERF3)
    return engines


def default_engine():
    """Return the default engine: Ookla if a binary is bundled, else netperf.

    iPerf3 is never the default because it needs a server address that only the
    user can supply.
    """
    return available_engines()[0]


def engine_error():
    """Return a message explaining why the active engine cannot run, else None.

    Only iPerf3 can be misconfigured - the engine list already excludes anything
    whose binary is missing.
    """
    if resolve_engine() == ENGINE_IPERF3:
        server, _, _ = get_iperf3_target()
        if not server:
            return 'No iPerf3 server configured'
    return None


def engine_label(engine):
    """Return a display name for an engine."""
    return {
        ENGINE_OOKLA: 'Ookla',
        ENGINE_NETPERF: 'Netperf (built into NCOS)',
        ENGINE_IPERF3: 'iPerf3'
    }.get(engine, engine)


def describe_iperf3_options():
    """Return a short summary of the iPerf3 test options for logging."""
    options = get_iperf3_options()
    parts = [options['protocol'].upper()]
    # -n replaces -t, so only one of the two is ever in effect.
    if options['bytes']:
        parts.append(f"{options['bytes']}B")
    else:
        parts.append(f"{options['duration']}s")
    if options['parallel'] > 1:
        parts.append(f"{options['parallel']} streams")
    if options['bandwidth']:
        parts.append(f"{options['bandwidth']}bps")
    if options['buffer_length']:
        parts.append(f"buf {options['buffer_length']}")
    if options['window']:
        parts.append(f"win {options['window']}")
    if options['omit']:
        parts.append(f"omit {options['omit']}s")
    if options['protocol'] == PROTOCOL_TCP:
        if options['no_delay']:
            parts.append('no-delay')
        if options['zero_copy']:
            parts.append('zero-copy')
    return ' '.join(parts)


def describe_engine():
    """Return a one-line description of the active engine for logging."""
    engine = resolve_engine()
    if engine == ENGINE_IPERF3:
        server, start, end = get_iperf3_target()
        ports = str(start) if start == end else f'{start}-{end}'
        target = f'{server}:{ports}' if server else 'no server configured'
        return f'iPerf3 | {target} | {describe_iperf3_options()}'
    return engine_label(engine)


def needs_source_routing():
    """Return True when the active engine needs source routing to pin a WAN.

    netperf pins the WAN itself through cp.speed_test()'s ifc_wan option, so it
    needs no config/routing entries at all.
    """
    return resolve_engine() != ENGINE_NETPERF


# =============================================================================
# IPERF3 PORT RESERVATION
# =============================================================================

def _reserve_port(already_tried, wait_timeout=300):
    """Reserve a port from the configured range for exclusive use by this test.

    Skips ports this test has already tried and waits while every remaining
    candidate is held by another modem's test. Returns None when there are no
    untried candidates left, or when none came free within wait_timeout.
    """
    _, start, end = get_iperf3_target()
    deadline = time.time() + wait_timeout
    with _port_condition:
        while True:
            candidates = [p for p in range(start, end + 1)
                          if p not in already_tried]
            if not candidates:
                return None
            for port in candidates:
                if port not in _ports_in_use:
                    _ports_in_use.add(port)
                    return port
            # Every untried port is busy with another modem - wait for one back.
            if time.time() >= deadline:
                cp.log(f'Timed out waiting for a free iPerf3 port in '
                       f'{start}-{end}')
                return None
            _port_condition.wait(0.5)


def _release_port(port):
    """Return a port to the pool and wake any test waiting for one."""
    with _port_condition:
        _ports_in_use.discard(port)
        _port_condition.notify_all()


# =============================================================================
# RESULTS
# =============================================================================

class SpeedtestResults:
    """Holds the results of a speedtest (compatible with the Ookla interface)."""

    def __init__(self, download=0, upload=0, ping=None, jitter=None, server=None,
                 client=None, bytes_received=0, bytes_sent=0, engine='',
                 opener=None, secure=False):
        self.download = download        # bits per second
        self.upload = upload            # bits per second
        self.ping = ping                # milliseconds, None when unavailable
        self.jitter = jitter            # milliseconds, None when unavailable
        self.server = server or {}
        self.client = client or {}
        self.engine = engine
        self.timestamp = f'{datetime.utcnow().isoformat()}Z'
        self.bytes_received = bytes_received
        self.bytes_sent = bytes_sent
        self._share = None
        self._opener = opener

    def share(self):
        """Return the results image URL (Ookla only, empty for other engines)."""
        return self._share or ''


# =============================================================================
# NETPERF HELPERS
# =============================================================================

def _to_int(value):
    """Coerce a netperf counter, which arrives as a string, to an int."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _us_to_ms(value):
    """Convert a netperf latency field from microseconds to milliseconds."""
    try:
        return float(value) / 1000.0
    except (TypeError, ValueError):
        return None


# =============================================================================
# IPERF3 HELPERS
# =============================================================================

def _iperf3_error(stdout, stderr):
    """Extract the most useful error message from an iperf3 failure."""
    out = stdout.decode('utf-8', 'replace').strip() if stdout else ''
    err = stderr.decode('utf-8', 'replace').strip() if stderr else ''
    if out:
        try:
            data = json.loads(out)
            if data.get('error'):
                return data['error']
        except Exception:
            pass
    return err or out or 'unknown error'


def _iperf3_binary_missing(error):
    """True when an iperf3 failure means the binary itself is gone.

    Popen raises FileNotFoundError, whose str() is the errno 2 message. That is
    not a per-port failure, so the caller stops instead of retrying every port.
    """
    return 'No such file or directory' in str(error or '')


def _iperf3_summary(data, *keys):
    """Return the first populated summary block from an iperf3 result.

    TCP runs report "sum_sent" and "sum_received" separately. UDP runs report a
    single "sum", so callers pass the TCP key first and "sum" as the fallback
    and get the right block for either protocol.
    """
    end = (data or {}).get('end') or {}
    for key in keys:
        block = end.get(key)
        if isinstance(block, dict) and block.get('bits_per_second'):
            return block
    return {}


def _to_float(value):
    """Coerce an iperf3 numeric field to a float, or None when absent."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _iperf3_rtt(data):
    """Derive (latency_ms, jitter_ms) from an iperf3 TCP result.

    iperf3 only reports TCP round-trip times for the sending side, so this is
    populated by the upload run and is absent on platforms where iperf3 cannot
    read tcp_info. Jitter is approximated as (max_rtt - min_rtt) / 2, matching
    how the netperf engine in the speedtest_web app approximates it.
    """
    streams = ((data or {}).get('end') or {}).get('streams') or []
    means, mins, maxes = [], [], []
    for stream in streams:
        if not isinstance(stream, dict):
            continue
        sender = stream.get('sender') or {}
        for key, bucket in (('mean_rtt', means), ('min_rtt', mins),
                            ('max_rtt', maxes)):
            try:
                value = float(sender.get(key))
            except (TypeError, ValueError):
                continue
            if value > 0:
                bucket.append(value)
    latency = sum(means) / len(means) / 1000.0 if means else None
    jitter = None
    if mins and maxes:
        jitter = (max(maxes) - min(mins)) / 2 / 1000.0
    return latency, jitter


# =============================================================================
# SPEEDTEST
# =============================================================================

class Speedtest:
    """Multi-engine speedtest pinned to a single WAN device.

    Args:
        source_address: WAN IP to source packets from (iperf3 and Ookla).
        interface: WAN iface name, e.g. 'pmip3'. Used as netperf's ifc_wan and
            as iperf3's --bind-dev.
        device: WAN device uid, e.g. 'mdm-41949674'. Used to locate netperf
            results when the control tree does not report a results path.
        duration: Seconds per direction. Leave unset to let iPerf3 use its
            configured duration; the other engines always use DEFAULT_DURATION.
    """

    def __init__(self, config=None, source_address=None, interface='', device='',
                 timeout=None, duration=None, secure=False,
                 shutdown_event=None):
        self.config = config or {}
        self._source_address = source_address
        self._interface = interface or ''
        self._device = device or ''
        # An explicit duration wins over the configured iPerf3 duration, so a
        # caller that asks for a specific length still gets it.
        self._duration_override = duration
        self._duration = duration or DEFAULT_DURATION
        self._timeout = timeout
        self._secure = secure
        self._shutdown_event = shutdown_event
        self.results = None
        self.closest = []
        self.engine = get_engine()

    # -- compatibility shims for the original Ookla interface ----------------

    def get_best_server(self, servers=None):
        """No-op. Every engine handles server selection itself."""
        pass

    def download(self, callback=None, threads=None):
        """Run the full test. Kept for interface compatibility."""
        return self.start()

    def upload(self, callback=None, pre_allocate=True, threads=None):
        """No-op. Upload is measured as part of start()."""
        pass

    def download_and_upload(self, callback=None, threads=None):
        """Run the full test."""
        return self.start()

    def _default_timeout(self):
        """Subprocess timeout for a run of self._duration seconds."""
        return self._timeout or (self._duration + 30)

    # -- entry point ---------------------------------------------------------

    def start(self):
        """Run download, upload and latency measurement with the active engine."""
        if self.engine == ENGINE_OOKLA:
            return self._run_ookla()
        if self.engine == ENGINE_IPERF3:
            return self._run_iperf3()
        return self._run_netperf()

    # =====================================================================
    # NETPERF ENGINE
    # =====================================================================

    def _run_netperf(self):
        """Run a speed test with the netperf service built into NCOS.

        The work is done by cp.speed_test(), which drives control/netperf and
        pins the test to one WAN through its ifc_wan option, so no source
        routing is needed. netperf cannot run concurrent tests - it is a single
        shared router resource - so modems are serialised here.
        """
        if not self._interface:
            raise Exception('netperf needs a WAN interface name (ifc_wan)')

        with _netperf_lock:
            result = cp.speed_test(interface=self._interface,
                                   duration=self._duration, direction='both')
            if not result:
                raise Exception('netperf returned no results')
            # Read the counters while they still belong to the test just run.
            bytes_received, bytes_sent = self._netperf_byte_counters()
            # cp.speed_test() measures throughput only, so latency and jitter
            # come from netperf's own TCP_RR test.
            latency, jitter = self._netperf_latency()

        download_bps = result.get('download_bps') or 0
        upload_bps = result.get('upload_bps') or 0
        if not download_bps and not upload_bps:
            raise Exception('netperf measured no throughput')

        self.results = SpeedtestResults(
            download=download_bps, upload=upload_bps,
            ping=latency, jitter=jitter,
            # netperf picks its own server from Cradlepoint's pool, so there is
            # no user-facing server to report.
            server={}, client={},
            bytes_received=bytes_received, bytes_sent=bytes_sent,
            engine=ENGINE_NETPERF)
        return self.results

    def _netperf_latency(self):
        """Measure latency and jitter with a netperf TCP_RR test.

        cp.speed_test() has no latency measurement, so this drives
        control/netperf directly with "rr": True, which is the documented way to
        get latency and jitter out of netperf. TCP_RR is a request/response test
        and moves almost no data.

        Returns (latency_ms, jitter_ms); either may be None.
        """
        path = self._netperf_results_path()
        try:
            # perf_results accumulates every test ever run on this device and is
            # never cleared, so note the current timestamp first. Without this,
            # an RR run that fails would read back the previous survey's numbers.
            previous_stamp = None
            if path:
                previous = cp.get(f'{path}/tcp_rr')
                if isinstance(previous, dict):
                    previous_stamp = previous.get('TIME')

            cp.put('/state/system/netperf', {"run_count": 0})
            time.sleep(1)
            cp.put('control/netperf', {
                "input": {
                    "options": {
                        "limit": {"size": 0, "time": NETPERF_RR_DURATION},
                        "port": None,
                        "fwport": None,
                        "host": "",
                        "ifc_wan": self._interface,
                        "tcp": True,
                        "udp": False,
                        "send": False,
                        "recv": False,
                        "rr": True
                    },
                    "tests": None
                },
                "run": 1
            })

            results_path = None
            deadline = time.time() + NETPERF_RR_DURATION + 30
            while time.time() < deadline:
                output = cp.get('control/netperf/output')
                if output:
                    if output.get('error') or output.get('status') == 'error':
                        cp.log(f'netperf TCP_RR error: '
                               f'{output.get("error") or "status error"}')
                        return None, None
                    if output.get('status') == 'complete' \
                            or output.get('progress') == 'done':
                        results_path = (output.get('results_path') or '').lstrip('/')
                        break
                time.sleep(1)
            else:
                cp.log('netperf TCP_RR timed out')
                cp.put('control/netperf/stop', '')
                return None, None

            data = cp.get(results_path or path)
            entry = data.get('tcp_rr') if isinstance(data, dict) else None
            if not isinstance(entry, dict):
                cp.log('netperf TCP_RR returned no tcp_rr results')
                return None, None
            if previous_stamp and entry.get('TIME') == previous_stamp:
                cp.log('netperf TCP_RR result is stale - discarding')
                return None, None

            # RT_LATENCY is the round trip time, STDDEV_LATENCY the jitter, both
            # in microseconds. NCOS 7.x does not report MEAN_LATENCY, so
            # RT_LATENCY is the field to rely on.
            latency = _us_to_ms(entry.get('RT_LATENCY'))
            if latency is None:
                latency = _us_to_ms(entry.get('MEAN_LATENCY'))
            jitter = _us_to_ms(entry.get('STDDEV_LATENCY'))
            return latency, jitter
        except Exception as e:
            cp.log(f'Exception measuring netperf latency: {e}')
            return None, None

    def _netperf_results_path(self):
        """Path to this device's netperf results in the status tree."""
        if not self._device:
            return None
        return f'status/wan/devices/{self._device}/status/perf_results'

    def _netperf_byte_counters(self):
        """Return (bytes_received, bytes_sent) recorded for this device.

        cp.speed_test() returns throughput but not volume, so the counters are
        read from the device's status tree to keep the survey's data usage total
        accurate on metered links.
        """
        received, sent = 0, 0
        path = self._netperf_results_path()
        if not path:
            return received, sent
        try:
            results = cp.get(path)
            if isinstance(results, dict):
                down = results.get('tcp_down')
                up = results.get('tcp_up')
                if isinstance(down, dict):
                    received = _to_int(down.get('LOCAL_BYTES_RECVD'))
                if isinstance(up, dict):
                    sent = _to_int(up.get('LOCAL_BYTES_SENT'))
        except Exception as e:
            cp.log(f'Could not read netperf byte counters: {e}')
        return received, sent

    # =====================================================================
    # IPERF3 ENGINE
    # =====================================================================

    def _run_iperf3(self):
        """Run an iperf3 test, walking the port range past busy or failing ports."""
        detect_binaries()
        binary = _iperf3_binary
        if not binary:
            raise Exception('No iPerf3 binary found in the app directory')
        server, port_start, port_end = get_iperf3_target()
        if not server:
            raise Exception('No iPerf3 server configured')

        # Read the options once so both directions of this test use the same
        # parameters even if the user saves new settings mid-survey.
        options = get_iperf3_options()

        tried = set()
        last_error = 'no port was attempted'
        for _ in range(port_end - port_start + 1):
            port = _reserve_port(tried)
            if port is None:
                break
            tried.add(port)
            try:
                results, error = self._iperf3_on_port(binary, server, port,
                                                      options)
            finally:
                _release_port(port)
            if results:
                return results
            last_error = error or 'unknown error'
            if _iperf3_binary_missing(last_error):
                # The binary is gone, so no port will work. This happens when
                # the app directory is removed underneath a running test - a
                # purge or uninstall during a survey - and walking the rest of
                # the range would just repeat the same error per port.
                raise Exception(f'iPerf3 binary {binary} is no longer present - '
                                f'the app directory was removed while the test '
                                f'was running')
            cp.log(f'iPerf3 {server}:{port} unusable ({last_error})')

        raise Exception(f'iPerf3 failed on every port in {port_start}-{port_end} '
                        f'for {server}: {last_error}')

    def _iperf3_on_port(self, binary, server, port, options):
        """Run download then upload on one port.

        Returns (results, error). results is None when the port produced no
        data at all, which tells the caller to try the next port.
        """
        download_bps, upload_bps = 0, 0
        bytes_received, bytes_sent = 0, 0
        latency, jitter = None, None
        error = None
        udp = options['protocol'] == PROTOCOL_UDP
        down_stats, up_stats = {}, {}

        # Download first: reverse mode, the server sends to us.
        download, error = self._iperf3_direction(binary, server, port, options,
                                                 reverse=True)
        if download:
            down_stats = _iperf3_summary(download, 'sum_received', 'sum')
            download_bps = int(down_stats.get('bits_per_second') or 0)
            bytes_received = int(down_stats.get('bytes') or 0)
        else:
            # A dead port or unreachable server fails here - move on quickly
            # rather than paying the upload timeout as well.
            return None, error

        upload, upload_error = self._iperf3_direction(binary, server, port,
                                                     options, reverse=False)
        if upload:
            # Volume sent is always taken from the sending side, so the survey's
            # data usage total reflects what the modem actually transmitted.
            sent = _iperf3_summary(upload, 'sum_sent', 'sum')
            bytes_sent = int(sent.get('bytes') or 0)
            if udp:
                # For UDP the sender's own block reports no jitter and no loss -
                # both live in the receiver's block, which iperf3 relays back
                # from the server. That block is also the honest upload rate,
                # since it counts only datagrams that arrived.
                up_stats = _iperf3_summary(upload, 'sum_received', 'sum',
                                           'sum_sent')
            else:
                up_stats = sent
                # RTT stats are only reported for the sending side, so the
                # upload run is where latency and jitter come from.
                latency, jitter = _iperf3_rtt(upload)
            upload_bps = int(up_stats.get('bits_per_second') or 0)
        else:
            error = upload_error
            cp.log(f'iPerf3 upload failed on {server}:{port}: {upload_error}')

        if udp:
            # UDP carries no TCP round-trip stats, so latency stays None, but
            # iperf3 measures jitter directly. The download figure is measured
            # locally by this client, so prefer it over the server's report.
            jitter = _to_float(down_stats.get('jitter_ms'))
            if jitter is None:
                jitter = _to_float(up_stats.get('jitter_ms'))
            self._log_udp_loss(server, port, down_stats, up_stats)

        if not download_bps and not upload_bps:
            return None, error or 'no data transferred'

        self.results = SpeedtestResults(
            download=download_bps, upload=upload_bps, ping=latency, jitter=jitter,
            server={'host': f'{server}:{port}'}, client={},
            bytes_received=bytes_received, bytes_sent=bytes_sent,
            engine=ENGINE_IPERF3)
        return self.results, error

    def _log_udp_loss(self, server, port, down_stats, up_stats):
        """Log the datagram loss iperf3 reports for a UDP test.

        Loss is not part of SpeedtestResults - the survey's packet loss column
        comes from its own continuous ping - so it is logged rather than
        recorded, which keeps the CSV and the server payload unchanged.
        """
        parts = []
        for label, block in (('down', down_stats), ('up', up_stats)):
            percent = _to_float(block.get('lost_percent'))
            if percent is None:
                continue
            lost = block.get('lost_packets')
            total = block.get('packets')
            detail = f'{label} {percent:.2f}%'
            if lost is not None and total:
                detail += f' ({lost}/{total})'
            parts.append(detail)
        if parts:
            cp.log(f'iPerf3 UDP datagram loss on {server}:{port}: '
                   f'{", ".join(parts)}')

    def _iperf3_duration(self, options):
        """Seconds per direction: an explicit duration wins over the setting."""
        return self._duration_override or options['duration']

    def _iperf3_timeout(self, options):
        """Subprocess timeout for one iperf3 direction."""
        if self._timeout:
            return self._timeout
        if options['bytes']:
            # -n transfers a volume with no time limit, so the only sane bound
            # is a fixed ceiling.
            return IPERF3_SIZE_TIMEOUT + options['omit']
        return self._iperf3_duration(options) + options['omit'] + 30

    def _iperf3_direction(self, binary, server, port, options, reverse):
        """Run one iperf3 direction. Returns (parsed_json, error_message)."""
        cmd = [binary, '-c', server, '-p', str(port), '-J', '-4']

        # -n takes precedence over -t in iperf3, so only one is ever passed.
        if options['bytes']:
            cmd.extend(['-n', options['bytes']])
        else:
            cmd.extend(['-t', str(self._iperf3_duration(options))])
        if options['protocol'] == PROTOCOL_UDP:
            cmd.append('-u')
        if options['parallel'] > 1:
            cmd.extend(['-P', str(options['parallel'])])
        if options['bandwidth']:
            cmd.extend(['-b', options['bandwidth']])
        if options['buffer_length']:
            cmd.extend(['-l', options['buffer_length']])
        if options['omit']:
            cmd.extend(['-O', str(options['omit'])])
        if options['window']:
            cmd.extend(['-w', options['window']])
        if options['protocol'] == PROTOCOL_TCP:
            # Both of these are TCP-only in iperf3 and are rejected with -u.
            if options['no_delay']:
                cmd.append('-N')
            if options['zero_copy']:
                cmd.append('-Z')
        if reverse:
            cmd.append('-R')
        if self._source_address:
            cmd.extend(['-B', self._source_address])
        if self._interface:
            cmd.extend(['--bind-dev', self._interface])

        timeout = self._iperf3_timeout(options)
        data, error = self._iperf3_exec(cmd, timeout)
        if data is None and error and 'Operation not permitted' in error \
                and '--bind-dev' in cmd:
            # SO_BINDTODEVICE needs CAP_NET_RAW, which the SDK sandbox may not
            # grant. Retry with source-IP binding only; MSS's source routing
            # still steers the traffic out of the right WAN.
            cp.log('--bind-dev not permitted here - retrying with -B only')
            retry = [arg for arg in cmd
                     if arg not in ('--bind-dev', self._interface)]
            data, error = self._iperf3_exec(retry, timeout)
        return data, error

    def _iperf3_exec(self, cmd, timeout):
        """Execute one iperf3 command. Returns (parsed_json, error_message)."""
        proc = None
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            stdout, stderr = proc.communicate(timeout=timeout)
            if proc.returncode == 0:
                return json.loads(stdout.decode('utf-8')), None
            return None, _iperf3_error(stdout, stderr)
        except subprocess.TimeoutExpired:
            if proc:
                try:
                    proc.kill()
                    proc.communicate()
                except Exception:
                    pass
            return None, f'timed out after {timeout}s'
        except json.JSONDecodeError as e:
            return None, f'could not parse iperf3 output: {e}'
        except Exception as e:
            return None, str(e)

    # =====================================================================
    # OOKLA ENGINE
    # =====================================================================

    def _run_ookla(self):
        """Run an Ookla speedtest using a licensed binary in the app directory."""
        detect_binaries()
        binary = _ookla_binary
        if not binary:
            raise Exception('No Ookla binary found in the app directory')

        if 'ookla' in binary:
            # The ookla binary streams jsonl.
            cmd = [binary, '-f', 'jsonl',
                   '-c', 'https://www.speedtest.net/api/embed/trial/config']
            if self._source_address:
                cmd.extend(['-i', self._source_address])
            return self._run_ookla_jsonl(cmd)

        cmd = [binary, '--accept-license', '-f', 'json']
        if self._source_address:
            cmd.extend(['-i', self._source_address])
        return self._run_ookla_json(cmd)

    def _run_ookla_json(self, cmd):
        """Run an Ookla binary that emits a single JSON blob."""
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=self._default_timeout())
        if result.returncode != 0:
            raise Exception(f'Ookla speedtest failed with return code '
                            f'{result.returncode}: {result.stderr}')
        data = json.loads(result.stdout)
        self.results = self._ookla_results(data)
        return self.results

    def _run_ookla_jsonl(self, cmd):
        """Run the ookla binary, which emits one JSON object per line."""
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                universal_newlines=True, bufsize=1)
        result_data = None
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if message.get('type') == 'result':
                    result_data = message
                    break
        except Exception as e:
            cp.log(f'Exception reading Ookla output: {e}')
        finally:
            try:
                proc.kill()
            except Exception:
                pass
            proc.wait()

        if not result_data:
            raise Exception('Ookla speedtest completed but returned no results')
        self.results = self._ookla_results(result_data)
        return self.results

    def _ookla_results(self, data):
        """Build a SpeedtestResults from an Ookla result object."""
        download = data.get('download') or {}
        upload = data.get('upload') or {}
        ping = data.get('ping') or {}
        client = data.get('client') or {}
        isp = data.get('isp', '')
        if isp and not client.get('isp'):
            client['isp'] = isp
        results = SpeedtestResults(
            # Ookla reports bandwidth in bytes per second.
            download=(download.get('bandwidth') or 0) * 8,
            upload=(upload.get('bandwidth') or 0) * 8,
            ping=ping.get('latency'),
            jitter=ping.get('jitter'),
            server=data.get('server') or {},
            client=client,
            bytes_received=download.get('bytes') or 0,
            bytes_sent=upload.get('bytes') or 0,
            engine=ENGINE_OOKLA)
        results._share = (data.get('result') or {}).get('url', '')
        return results
