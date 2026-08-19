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
                        iperf3_ports='5201-5210')
    st = speedtest.Speedtest(source_address='10.0.0.1', interface='pmip3',
                             device='mdm-41949674')
    st.start()
    print(st.results.download, st.results.upload, st.results.ping,
          st.results.jitter)

PORT RANGES (iperf3 only):
    Surveys test every connected modem at the same time, so each test needs its
    own port. Ports are reserved from the configured range for the life of a
    test and a port that is busy or errors falls through to the next one.
"""

import cp
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


def configure(engine=None, iperf3_server=None, iperf3_ports=None):
    """Set the active engine and iPerf3 target.

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


def describe_engine():
    """Return a one-line description of the active engine for logging."""
    engine = resolve_engine()
    if engine == ENGINE_IPERF3:
        server, start, end = get_iperf3_target()
        ports = str(start) if start == end else f'{start}-{end}'
        target = f'{server}:{ports}' if server else 'no server configured'
        return f'iPerf3 | {target}'
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
        duration: Seconds per direction.
    """

    def __init__(self, config=None, source_address=None, interface='', device='',
                 timeout=None, duration=DEFAULT_DURATION, secure=False,
                 shutdown_event=None):
        self.config = config or {}
        self._source_address = source_address
        self._interface = interface or ''
        self._device = device or ''
        self._duration = duration or DEFAULT_DURATION
        self._timeout = timeout or (self._duration + 30)
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

        tried = set()
        last_error = 'no port was attempted'
        for _ in range(port_end - port_start + 1):
            port = _reserve_port(tried)
            if port is None:
                break
            tried.add(port)
            try:
                results, error = self._iperf3_on_port(binary, server, port)
            finally:
                _release_port(port)
            if results:
                return results
            last_error = error or 'unknown error'
            cp.log(f'iPerf3 {server}:{port} unusable ({last_error})')

        raise Exception(f'iPerf3 failed on every port in {port_start}-{port_end} '
                        f'for {server}: {last_error}')

    def _iperf3_on_port(self, binary, server, port):
        """Run download then upload on one port.

        Returns (results, error). results is None when the port produced no
        data at all, which tells the caller to try the next port.
        """
        download_bps, upload_bps = 0, 0
        bytes_received, bytes_sent = 0, 0
        latency, jitter = None, None
        error = None

        # Download first: reverse mode, the server sends to us.
        download, error = self._iperf3_direction(binary, server, port, reverse=True)
        if download:
            end = download.get('end') or {}
            received = end.get('sum_received') or {}
            download_bps = int(received.get('bits_per_second') or 0)
            bytes_received = int(received.get('bytes') or 0)
        else:
            # A dead port or unreachable server fails here - move on quickly
            # rather than paying the upload timeout as well.
            return None, error

        upload, upload_error = self._iperf3_direction(binary, server, port,
                                                     reverse=False)
        if upload:
            end = upload.get('end') or {}
            sent = end.get('sum_sent') or {}
            upload_bps = int(sent.get('bits_per_second') or 0)
            bytes_sent = int(sent.get('bytes') or 0)
            # RTT stats are only reported for the sending side, so the upload
            # run is where latency and jitter come from.
            latency, jitter = _iperf3_rtt(upload)
        else:
            error = upload_error
            cp.log(f'iPerf3 upload failed on {server}:{port}: {upload_error}')

        if not download_bps and not upload_bps:
            return None, error or 'no data transferred'

        self.results = SpeedtestResults(
            download=download_bps, upload=upload_bps, ping=latency, jitter=jitter,
            server={'host': f'{server}:{port}'}, client={},
            bytes_received=bytes_received, bytes_sent=bytes_sent,
            engine=ENGINE_IPERF3)
        return self.results, error

    def _iperf3_direction(self, binary, server, port, reverse):
        """Run one iperf3 direction. Returns (parsed_json, error_message)."""
        cmd = [binary, '-c', server, '-p', str(port),
               '-t', str(self._duration), '-J', '-4']
        if reverse:
            cmd.append('-R')
        if self._source_address:
            cmd.extend(['-B', self._source_address])
        if self._interface:
            cmd.extend(['--bind-dev', self._interface])

        data, error = self._iperf3_exec(cmd)
        if data is None and error and 'Operation not permitted' in error \
                and '--bind-dev' in cmd:
            # SO_BINDTODEVICE needs CAP_NET_RAW, which the SDK sandbox may not
            # grant. Retry with source-IP binding only; MSS's source routing
            # still steers the traffic out of the right WAN.
            cp.log('--bind-dev not permitted here - retrying with -B only')
            retry = [arg for arg in cmd
                     if arg not in ('--bind-dev', self._interface)]
            data, error = self._iperf3_exec(retry)
        return data, error

    def _iperf3_exec(self, cmd):
        """Execute one iperf3 command. Returns (parsed_json, error_message)."""
        proc = None
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            stdout, stderr = proc.communicate(timeout=self._timeout)
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
            return None, f'timed out after {self._timeout}s'
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
                                timeout=self._timeout)
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
