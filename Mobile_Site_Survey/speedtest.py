"""
Speedtest module - Multi-engine speed testing with concurrent multi-modem support.
Provides compatibility with the original Ookla Speedtest interface used by Mobile_Site_Survey.

Engine priority:
1. Ookla - if licensed 'ookla' or 'speedtest' binary is present (BYOB)
2. iPerf3 - uses bundled iperf3-arm64v8 binary with port range for concurrent tests

Concurrent testing is supported by both engines:
- Ookla: each subprocess uses -i source_address binding
- iPerf3: each subprocess uses -B source_address binding + separate port from range

USAGE:
    from speedtest import Speedtest
    st = Speedtest(source_address="10.0.0.1")
    st.download()         # Runs download + upload test
    print(f"Download: {st.results.download} bps")
    print(f"Upload: {st.results.upload} bps")

CONFIGURATION (via appdata 'Mobile_Site_Survey' JSON):
    speedtest_url: "server:port" or "server:start_port-end_port"
                   e.g. "iperf.example.com:5201" or "iperf.example.com:5201-5210"
                   Only used for iperf3 mode.

PORT RANGES (iperf3 only):
    When running simultaneous tests on multiple modems, each test needs its own port.
    Configure a port range (e.g. 5201-5210) and the module assigns ports round-robin.
"""

import subprocess
import json
import os
import threading
import select
import time
from datetime import datetime

# Port allocation for concurrent iperf3 tests
_port_lock = threading.Lock()
_ports_in_use = set()
_server = ''
_port_start = 5201
_port_end = 5201

# Engine detection
_engine = None  # 'ookla' or 'iperf3', detected on first use


def _detect_engine():
    """Detect which speedtest engine to use."""
    global _engine
    if _engine is not None:
        return _engine

    # Check for Ookla binary (either 'ookla' or 'speedtest' name)
    for binary in ('ookla', 'speedtest'):
        if os.path.exists(binary):
            if not os.access(binary, os.X_OK):
                try:
                    os.chmod(binary, 0o755)
                except Exception:
                    pass
            _engine = 'ookla'
            return _engine

    # Fall back to iperf3
    if os.path.exists('iperf3-arm64v8'):
        if not os.access('iperf3-arm64v8', os.X_OK):
            try:
                os.chmod('iperf3-arm64v8', 0o755)
            except Exception:
                pass
        _engine = 'iperf3'
        return _engine

    _engine = 'none'
    return _engine


def get_engine():
    """Return the current engine name."""
    return _detect_engine()


def configure(server_str):
    """Configure the iperf3 server and port range.

    Args:
        server_str: "host:port" or "host:start-end" (e.g. "iperf.example.com:5201-5210")
    """
    global _server, _port_start, _port_end
    if not server_str:
        return
    parts = server_str.strip().split(':')
    _server = parts[0]
    if len(parts) > 1:
        port_part = parts[1]
        if '-' in port_part:
            start, end = port_part.split('-', 1)
            _port_start = int(start)
            _port_end = int(end)
        else:
            _port_start = int(port_part)
            _port_end = _port_start


def _allocate_port():
    """Allocate a port from the range. Blocks until one is available."""
    while True:
        with _port_lock:
            for port in range(_port_start, _port_end + 1):
                if port not in _ports_in_use:
                    _ports_in_use.add(port)
                    return port
        time.sleep(0.5)


def _release_port(port):
    """Release a port back to the pool."""
    with _port_lock:
        _ports_in_use.discard(port)


class SpeedtestResults:
    """Class for holding the results of a speedtest (compatible with Ookla interface)."""

    def __init__(self, download=0, upload=0, ping=0, server=None, client=None,
                 bytes_received=0, bytes_sent=0, opener=None, secure=False):
        self.download = download  # bits per second
        self.upload = upload      # bits per second
        self.ping = ping          # milliseconds
        self.server = server or {}
        self.client = client or {}
        self.timestamp = f'{datetime.utcnow().isoformat()}Z'
        self.bytes_received = bytes_received
        self.bytes_sent = bytes_sent
        self._share = None
        self._opener = opener

    def share(self):
        """Return share URL (Ookla only, empty for iperf3)."""
        return self._share or ''


class Speedtest:
    """Multi-engine speedtest with source address binding for per-modem testing.

    Drop-in replacement for the original Ookla Speedtest class interface.
    Automatically uses Ookla if binary present, otherwise iperf3.
    """

    def __init__(self, config=None, source_address=None, timeout=60,
                 secure=False, shutdown_event=None):
        self.config = config or {}
        self._source_address = source_address
        self._timeout = timeout
        self._secure = secure
        self._shutdown_event = shutdown_event
        self.results = None
        self.closest = []
        self._engine = _detect_engine()

    def get_best_server(self, servers=None):
        """Compatibility method - both engines handle server selection internally."""
        pass

    def download(self, callback=None, threads=None):
        """Run download test (actually runs both download and upload)."""
        return self.start()

    def upload(self, callback=None, pre_allocate=True, threads=None):
        """Compatibility method - upload is included in download() call."""
        pass

    def download_and_upload(self, callback=None, threads=None):
        """Run both download and upload tests."""
        return self.start()

    def start(self):
        """Run the speed test using the detected engine."""
        if self._engine == 'ookla':
            return self._run_ookla()
        elif self._engine == 'iperf3':
            return self._run_iperf3()
        else:
            raise Exception("No speedtest binary found (need 'ookla', 'speedtest', or 'iperf3-arm64v8')")

    # =========================================================================
    # OOKLA ENGINE
    # =========================================================================

    def _run_ookla(self):
        """Run Ookla speedtest using the binary."""
        # Determine binary name
        binary = './ookla' if os.path.exists('ookla') else './speedtest'

        # Build command
        if 'ookla' in binary:
            # New ookla binary uses jsonl format
            cmd = [binary, '-f', 'jsonl',
                   '-c', 'https://www.speedtest.net/api/embed/trial/config']
            if self._source_address:
                cmd.extend(['-i', self._source_address])
            return self._run_ookla_jsonl(cmd)
        else:
            # Old speedtest binary uses json format
            cmd = [binary, '--accept-license', '-f', 'json']
            if self._source_address:
                cmd.extend(['-i', self._source_address])
            return self._run_ookla_json(cmd)

    def _run_ookla_json(self, cmd):
        """Run old-style Ookla binary that outputs single JSON blob."""
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=self._timeout)
        if result.returncode != 0:
            raise Exception(f"Speedtest failed with return code {result.returncode}: {result.stderr}")

        data = json.loads(result.stdout)
        download_bps = data.get('download', {}).get('bandwidth', 0) * 8
        upload_bps = data.get('upload', {}).get('bandwidth', 0) * 8
        bytes_received = data.get('download', {}).get('bytes', 0)
        bytes_sent = data.get('upload', {}).get('bytes', 0)
        ping = data.get('ping', {}).get('latency', 0)
        server = data.get('server', {})
        client = data.get('client', {})
        share_url = data.get('result', {}).get('url', '')

        self.results = SpeedtestResults(
            download=download_bps, upload=upload_bps, ping=ping,
            server=server, client=client,
            bytes_received=bytes_received, bytes_sent=bytes_sent
        )
        self.results._share = share_url
        return self.results

    def _run_ookla_jsonl(self, cmd):
        """Run new ookla binary that outputs JSONL (line-by-line JSON)."""
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, bufsize=1)

        result_data = None
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if msg.get('type') == 'result':
                    result_data = msg
                    break
                elif msg.get('type') == 'log':
                    level = msg.get('level', '')
                    if level in ('error', 'warning'):
                        pass  # Errors handled below if no result
        except Exception:
            pass
        finally:
            try:
                proc.kill()
            except Exception:
                pass
            proc.wait()

        if result_data:
            dl_bw = result_data.get('download', {}).get('bandwidth', 0)
            ul_bw = result_data.get('upload', {}).get('bandwidth', 0)
            ping_ms = result_data.get('ping', {}).get('latency', 0)
            server = result_data.get('server', {})
            client = result_data.get('client', {})
            bytes_received = result_data.get('download', {}).get('bytes', 0)
            bytes_sent = result_data.get('upload', {}).get('bytes', 0)
            share_url = result_data.get('result', {}).get('url', '')
            isp = result_data.get('isp', '')
            if isp and not client.get('isp'):
                client['isp'] = isp

            self.results = SpeedtestResults(
                download=dl_bw * 8, upload=ul_bw * 8, ping=ping_ms,
                server=server, client=client,
                bytes_received=bytes_received, bytes_sent=bytes_sent
            )
            self.results._share = share_url
            return self.results

        raise Exception("Ookla speedtest completed but no results received")

    # =========================================================================
    # IPERF3 ENGINE
    # =========================================================================

    def _run_iperf3(self):
        """Run iperf3 speed test (download + upload)."""
        if not _server:
            raise Exception("No iperf3 server configured. Set speedtest_url in appdata.")

        port = _allocate_port()
        try:
            download_bps = 0
            upload_bps = 0
            bytes_received = 0
            bytes_sent = 0

            # Download test (reverse mode: server sends to client)
            dl_result = self._iperf3_run(port, reverse=True)
            if dl_result:
                download_bps = int(dl_result.get('end', {}).get(
                    'sum_received', {}).get('bits_per_second', 0))
                bytes_received = int(dl_result.get('end', {}).get(
                    'sum_received', {}).get('bytes', 0))

            # Upload test (normal mode: client sends to server)
            ul_result = self._iperf3_run(port, reverse=False)
            if ul_result:
                upload_bps = int(ul_result.get('end', {}).get(
                    'sum_sent', {}).get('bits_per_second', 0))
                bytes_sent = int(ul_result.get('end', {}).get(
                    'sum_sent', {}).get('bytes', 0))

            self.results = SpeedtestResults(
                download=download_bps,
                upload=upload_bps,
                ping=0,
                server={'host': f'{_server}:{port}'},
                client={},
                bytes_received=bytes_received,
                bytes_sent=bytes_sent
            )
            return self.results

        except Exception as e:
            raise Exception(f"iperf3 speedtest failed: {e}")
        finally:
            _release_port(port)

    def _iperf3_run(self, port, reverse=False):
        """Run a single iperf3 test direction."""
        cmd = ['./iperf3-arm64v8', '-c', _server, '-p', str(port),
               '-t', '10', '-J']
        if reverse:
            cmd.append('-R')
        if self._source_address:
            cmd.extend(['-B', self._source_address])

        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = proc.communicate(timeout=self._timeout)
            if proc.returncode == 0:
                return json.loads(stdout.decode('utf-8'))
            else:
                err_text = stderr.decode('utf-8').strip() if stderr else ''
                try:
                    err_data = json.loads(stdout.decode('utf-8'))
                    err_text = err_data.get('error', err_text)
                except Exception:
                    pass
                raise Exception(
                    f"iperf3 returned {proc.returncode}: {err_text}")
        except subprocess.TimeoutExpired:
            proc.kill()
            raise Exception("iperf3 test timed out")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse iperf3 output: {e}")
