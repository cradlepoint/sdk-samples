# speedtest_web - Web interface for running speed tests with history and reports
# Supports: Ookla (BYOB - bring your own binary), Netperf (built-in), iPerf3

import cp
import os
import sys
import json
import time
import socket
import subprocess
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime
from threading import Thread

# Constants
PORT = 8000
HISTORY_FILE = 'tmp/speedtest_history.json'
MAX_HISTORY = 100

# Global state
current_test = {
    'running': False,
    'engine': None,
    'progress': {},
    'error': None
}
test_lock = threading.Lock()

# Schedule state
schedule_config = {
    'enabled': False,
    'autostart': False,
    'cron': '',
    'engine': 'netperf',
    'params': {}
}
schedule_lock = threading.Lock()


OOKLA_BINARIES = ('ookla', 'speedtest', 'speedtest-cli')
IPERF3_BINARIES = ('iperf3', 'iperf3-arm64v8', 'iperf3-aarch64')


def has_ookla():
    """Check if ookla binary is present in the app directory."""
    for binary in OOKLA_BINARIES:
        if os.path.exists(binary):
            if not os.access(binary, os.X_OK):
                try:
                    os.chmod(binary, 0o755)
                except Exception:
                    pass
            return True
    return False


def get_ookla_binary():
    """Return the path to the ookla binary, or None if not found."""
    for binary in OOKLA_BINARIES:
        if os.path.exists(binary):
            if not os.access(binary, os.X_OK):
                try:
                    os.chmod(binary, 0o755)
                except Exception:
                    pass
            return './' + binary
    return None


def has_iperf3():
    """Check if iperf3 binary is present in the app directory."""
    for binary in IPERF3_BINARIES:
        if os.path.exists(binary):
            if not os.access(binary, os.X_OK):
                try:
                    os.chmod(binary, 0o755)
                except Exception:
                    pass
            return True
    return False


def get_iperf3_binary():
    """Return the path to the iperf3 binary, or None if not found."""
    for binary in IPERF3_BINARIES:
        if os.path.exists(binary):
            if not os.access(binary, os.X_OK):
                try:
                    os.chmod(binary, 0o755)
                except Exception:
                    pass
            return './' + binary
    return None


def get_wan_interfaces():
    """Get list of connected WAN interfaces with priority info."""
    try:
        devices = cp.get('status/wan/devices')
        interfaces = []
        if devices and isinstance(devices, dict):
            for uid, info in devices.items():
                if isinstance(info, dict):
                    iface = info.get('info', {}).get('iface', '')
                    status = info.get('status', {})
                    conn_state = status.get('connection_state', 'unknown')
                    if conn_state != 'connected':
                        continue
                    ipinfo = status.get('ipinfo', {})
                    ip = ipinfo.get('ip_address', '')
                    # Get priority from config
                    config = info.get('config', {})
                    priority = config.get('priority', 999)
                    # Get friendly name
                    wan_type = info.get('info', {}).get('type', '')
                    product = ''
                    if wan_type == 'mdm':
                        diag = info.get('diagnostics', {})
                        carrier = diag.get('CARRID', '')
                        sim = info.get('info', {}).get('sim', '')
                        product = carrier or uid
                        if sim:
                            product = product + ' ' + sim.upper()
                    else:
                        product = info.get('info', {}).get('product', '') or uid
                    if iface:
                        interfaces.append({
                            'uid': uid,
                            'iface': iface,
                            'ip': ip,
                            'state': conn_state,
                            'priority': priority,
                            'name': product
                        })
        # Sort by priority (lowest value = highest priority)
        interfaces.sort(key=lambda x: x.get('priority', 999))
        return interfaces
    except Exception as e:
        cp.log(f'Error getting WAN interfaces: {e}')
        return []


def load_history():
    """Load test history from file."""
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        cp.log(f'Error loading history: {e}')
    return []


def save_history(history):
    """Save test history to file."""
    try:
        os.makedirs('tmp', exist_ok=True)
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history[-MAX_HISTORY:], f)
    except Exception as e:
        cp.log(f'Error saving history: {e}')


def add_result(result):
    """Add a test result to history."""
    history = load_history()
    history.append(result)
    save_history(history)


# =============================================================================
# NETPERF ENGINE
# =============================================================================

def run_netperf(interface='', duration=10, direction='both', include_latency=False, host='', size=0):
    """Run a speed test using the router's built-in netperf service."""
    global current_test
    try:
        if not interface:
            primary = cp.get_wan_primary_device()
            if primary:
                interface = cp.get(
                    f'status/wan/devices/{primary}/info/iface') or ''
            else:
                interface = ''

        results = {
            'download_bps': 0,
            'upload_bps': 0,
            'test_duration': duration,
            'interface': interface,
            'protocol': 'tcp'
        }

        def _run_netperf_direction(recv, send):
            """Run a single netperf direction and poll for completion."""
            params = {
                "input": {
                    "options": {
                        "limit": {"size": size, "time": duration},
                        "port": None,
                        "fwport": None,
                        "host": host,
                        "ifc_wan": interface,
                        "tcp": True,
                        "udp": False,
                        "send": send,
                        "recv": recv,
                        "rr": False
                    },
                    "tests": None
                },
                "run": 1
            }
            # Reset state and clear previous output
            cp.put('/state/system/netperf', {"run_count": 0})
            time.sleep(1)

            # Start the test
            cp.put('control/netperf', params)
            cp.log(f'Netperf started: recv={recv} send={send} iface={interface}')

            # Poll for progress/completion
            deadline = time.time() + duration + 30
            while time.time() < deadline:
                if not current_test['running']:
                    cp.put('control/netperf/stop', '')
                    return None
                out = cp.get('control/netperf/output')
                if out:
                    progress = out.get('progress', '')
                    status = out.get('status', '')
                    if status == 'error' or out.get('error'):
                        cp.log(f'Netperf error: {out.get("error", status)}')
                        return None
                    if status == 'complete' or progress == 'done':
                        results_path = out.get('results_path', '')
                        if results_path:
                            result = cp.get(results_path.lstrip('/'))
                            cp.log(f'Netperf result keys: {list(result.keys()) if result else None}')
                            return result
                        return None
                time.sleep(1)
            cp.log('Netperf poll timed out')
            return None

        # Download test
        if direction in ('recv', 'both'):
            with test_lock:
                current_test['progress'] = {
                    'stage': 'download',
                    'percent': 0
                }
            dl = _run_netperf_direction(recv=True, send=False)
            if dl and 'tcp_down' in dl:
                tp = dl['tcp_down']
                if tp and 'THROUGHPUT' in tp:
                    results['download_bps'] = cp._convert_throughput(
                        float(tp['THROUGHPUT']),
                        tp.get('THROUGHPUT_UNITS', ''))
                    cp.log(f'Download: {tp["THROUGHPUT"]} {tp.get("THROUGHPUT_UNITS", "")}')

            if direction == 'both':
                time.sleep(3)

        # Upload test
        if direction in ('send', 'both'):
            with test_lock:
                current_test['progress'] = {
                    'stage': 'upload',
                    'percent': 0
                }
            ul = _run_netperf_direction(recv=False, send=True)
            if ul and 'tcp_up' in ul:
                tp = ul['tcp_up']
                if tp and 'THROUGHPUT' in tp:
                    results['upload_bps'] = cp._convert_throughput(
                        float(tp['THROUGHPUT']),
                        tp.get('THROUGHPUT_UNITS', ''))
                    cp.log(f'Upload: {tp["THROUGHPUT"]} {tp.get("THROUGHPUT_UNITS", "")}')
            elif ul:
                cp.log(f'Upload result missing tcp_up key. Got: {list(ul.keys())}')

        # TCP RR Latency/Jitter test (optional)
        if include_latency:
            if direction == 'both':
                time.sleep(3)
            with test_lock:
                current_test['progress'] = {
                    'stage': 'latency',
                    'percent': 0
                }
            rr_params = {
                "input": {
                    "options": {
                        "limit": {"size": size, "time": duration},
                        "port": None,
                        "fwport": None,
                        "host": host,
                        "ifc_wan": interface,
                        "tcp": True,
                        "udp": False,
                        "send": False,
                        "recv": False,
                        "rr": True
                    },
                    "tests": None
                },
                "run": 1
            }
            # Reset state
            cp.put('/state/system/netperf', {"run_count": 0})
            time.sleep(1)
            cp.put('control/netperf', rr_params)
            cp.log(f'Netperf TCP_RR started: iface={interface}')

            deadline = time.time() + duration + 30
            while time.time() < deadline:
                if not current_test['running']:
                    cp.put('control/netperf/stop', '')
                    break
                out = cp.get('control/netperf/output')
                if out:
                    status = out.get('status', '')
                    progress = out.get('progress', '')
                    if status == 'error' or out.get('error'):
                        cp.log(f'Netperf RR error: {out.get("error", status)}')
                        break
                    if status == 'complete' or progress == 'done':
                        results_path = out.get('results_path', '')
                        if results_path:
                            rr_data = cp.get(results_path.lstrip('/'))
                            cp.log(f'TCP_RR result: {json.dumps(rr_data)}')
                            if rr_data and 'tcp_rr' in rr_data:
                                rr = rr_data['tcp_rr']
                                # Latency is in microseconds, convert to ms
                                if 'MEAN_LATENCY' in rr:
                                    results['latency_ms'] = float(
                                        rr['MEAN_LATENCY']) / 1000.0
                                elif 'RT_LATENCY' in rr:
                                    results['latency_ms'] = float(
                                        rr['RT_LATENCY']) / 1000.0
                                if 'P50_LATENCY' in rr:
                                    results['p50_latency_ms'] = float(
                                        rr['P50_LATENCY']) / 1000.0
                                if 'P99_LATENCY' in rr:
                                    results['p99_latency_ms'] = float(
                                        rr['P99_LATENCY']) / 1000.0
                                if 'STDDEV_LATENCY' in rr:
                                    results['jitter_ms'] = float(
                                        rr['STDDEV_LATENCY']) / 1000.0
                                elif 'MIN_LATENCY' in rr and 'MAX_LATENCY' in rr:
                                    # Approximate jitter as (max - min) / 2
                                    min_lat = float(rr['MIN_LATENCY'])
                                    max_lat = float(rr['MAX_LATENCY'])
                                    results['jitter_ms'] = (
                                        max_lat - min_lat) / 2000.0
                                cp.log(f'Latency: {results.get("latency_ms", 0):.2f}ms '
                                       f'Jitter: {results.get("jitter_ms", 0):.2f}ms')
                        break
                time.sleep(1)

        return results
    except Exception as e:
        cp.log(f'Netperf error: {e}')
        return None


# =============================================================================
# IPERF3 ENGINE
# =============================================================================

def run_iperf3(server, duration=10, interface='', port=5201):
    """Run a speed test using iperf3 binary with port range retry support.
    
    port can be an int (single port) or string with range like "5201-5210".
    If a port fails, retries on the next port in range.
    """
    global current_test

    # Parse port range
    ports = []
    port_str = str(port)
    if '-' in port_str:
        try:
            start, end = port_str.split('-', 1)
            ports = list(range(int(start), int(end) + 1))
        except ValueError:
            ports = [int(port_str.split('-')[0])]
    else:
        ports = [int(port_str)]

    if not has_iperf3():
        try:
            cp.log('Downloading iperf3 binary...')
            import requests
            url = "https://github.com/userdocs/iperf3-static/releases/download/3.17.1%2B/iperf3-arm64v8"
            response = requests.get(url)
            if response.status_code == 200:
                with open('iperf3-arm64v8', 'wb') as f:
                    f.write(response.content)
                os.chmod('iperf3-arm64v8', 0o755)
                cp.log('iperf3 downloaded successfully')
            else:
                cp.log(f'Failed to download iperf3: {response.status_code}')
                return None
        except Exception as e:
            cp.log(f'Error downloading iperf3: {e}')
            return None

    # Resolve interface name to IP for iperf3 -B flag
    bind_ip = ''
    if interface:
        try:
            devices = cp.get('status/wan/devices')
            if devices:
                for uid, dev in devices.items():
                    if isinstance(dev, dict):
                        if dev.get('info', {}).get('iface') == interface:
                            bind_ip = dev.get('status', {}).get(
                                'ipinfo', {}).get('ip_address', '')
                            break
            if not bind_ip:
                cp.log(f'Could not resolve IP for interface {interface}, '
                       f'running without bind')
        except Exception as e:
            cp.log(f'Error resolving interface IP: {e}')

    iperf3_bin = get_iperf3_binary()

    # Try ports in order until one works
    for attempt_port in ports:
        if not current_test['running']:
            return {'download_bps': 0, 'upload_bps': 0, 'test_duration': duration,
                    'error': 'Test cancelled'}

        results = _run_iperf3_on_port(
            iperf3_bin, server, attempt_port, duration, bind_ip)

        if results and (results['download_bps'] > 0 or results['upload_bps'] > 0):
            return results

        # Failed on this port — retry on next if available
        if attempt_port != ports[-1]:
            cp.log(f'iPerf3 failed on port {attempt_port}, retrying on next port...')
            time.sleep(1)

    # All ports exhausted
    cp.log(f'iPerf3 failed on all ports: {ports[0]}-{ports[-1]}')
    return results or {'download_bps': 0, 'upload_bps': 0, 'test_duration': duration,
                       'error': f'iPerf3 failed on all ports ({ports[0]}-{ports[-1]})'}


def _run_iperf3_on_port(iperf3_bin, server, port, duration, bind_ip):
    """Run iperf3 download+upload on a specific port. Returns results dict."""
    global current_test
    results = {'download_bps': 0, 'upload_bps': 0, 'test_duration': duration}

    try:
        # Download test (reverse mode)
        with test_lock:
            current_test['progress'] = {'stage': 'download', 'percent': 0}
        cmd = [iperf3_bin, '-c', server, '-p', str(port),
               '-t', str(duration), '-R', '-J']
        if bind_ip:
            cmd.extend(['-B', bind_ip])
        cp.log(f'iPerf3 download cmd: {" ".join(cmd)}')
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = proc.communicate(timeout=duration + 30)
            cp.log(f'iPerf3 download returncode: {proc.returncode}')
            if proc.returncode == 0:
                data = json.loads(stdout.decode('utf-8'))
                bps = data.get('end', {}).get('sum_received', {}).get(
                    'bits_per_second', 0)
                results['download_bps'] = bps
                cp.log(f'iPerf3 download: {bps/1e6:.2f} Mbps (port {port})')
            else:
                err_msg = _parse_iperf3_error(stdout, stderr)
                cp.log(f'iPerf3 download failed on port {port}: {err_msg}')
                results['error'] = err_msg
                return results  # Fail fast — try next port
        except subprocess.TimeoutExpired:
            proc.kill()
            cp.log(f'iPerf3 download timed out on port {port}')
            results['error'] = 'Download timed out'
            return results
        except json.JSONDecodeError as e:
            cp.log(f'iPerf3 JSON error: {e}')
            results['error'] = str(e)
            return results

        if not current_test['running']:
            return results

        time.sleep(2)

        # Upload test
        with test_lock:
            current_test['progress'] = {'stage': 'upload', 'percent': 0}
        cmd = [iperf3_bin, '-c', server, '-p', str(port),
               '-t', str(duration), '-J']
        if bind_ip:
            cmd.extend(['-B', bind_ip])
        cp.log(f'iPerf3 upload cmd: {" ".join(cmd)}')
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = proc.communicate(timeout=duration + 30)
            cp.log(f'iPerf3 upload returncode: {proc.returncode}')
            if proc.returncode == 0:
                data = json.loads(stdout.decode('utf-8'))
                bps = data.get('end', {}).get('sum_sent', {}).get(
                    'bits_per_second', 0)
                results['upload_bps'] = bps
                cp.log(f'iPerf3 upload: {bps/1e6:.2f} Mbps (port {port})')
            else:
                err_msg = _parse_iperf3_error(stdout, stderr)
                cp.log(f'iPerf3 upload failed on port {port}: {err_msg}')
                # Download succeeded but upload failed — still return partial
                results['error'] = 'Upload failed: ' + err_msg
        except subprocess.TimeoutExpired:
            proc.kill()
            cp.log(f'iPerf3 upload timed out on port {port}')
            results['error'] = 'Upload timed out'
        except json.JSONDecodeError as e:
            cp.log(f'iPerf3 JSON error: {e}')

        cp.log(f'iPerf3 complete on port {port}: DL={results["download_bps"]/1e6:.2f}Mbps '
               f'UL={results["upload_bps"]/1e6:.2f}Mbps')
        if results['download_bps'] == 0 and results['upload_bps'] == 0:
            results['error'] = results.get('error', 'No data transferred')
        return results
    except Exception as e:
        cp.log(f'iPerf3 error on port {port}: {e}')
        results['error'] = str(e)
        return results


def _parse_iperf3_error(stdout, stderr):
    """Extract error message from iperf3 output."""
    err = stderr.decode('utf-8').strip() if stderr else ''
    out = stdout.decode('utf-8').strip() if stdout else ''
    if out:
        try:
            err_data = json.loads(out)
            if err_data.get('error'):
                return err_data['error']
        except Exception:
            pass
    return err or 'Unknown error'


# =============================================================================
# OOKLA ENGINE (streaming)
# =============================================================================

def run_ookla(interface=''):
    """Run a speed test using the Ookla binary with streaming progress."""
    global current_test
    if not has_ookla():
        return None

    try:
        ookla_bin = get_ookla_binary()
        cmd = [ookla_bin, '-f', 'jsonl',
               '-c', 'https://www.speedtest.net/api/embed/trial/config']
        if interface:
            cmd.extend(['-I', interface])

        cp.log(f'Ookla command: {" ".join(cmd)}')
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, bufsize=1)

        result_data = None
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get('type')
            if msg_type == 'download':
                dl = msg.get('download', {})
                with test_lock:
                    current_test['progress'] = {
                        'stage': 'download',
                        'percent': int(dl.get('progress', 0) * 100),
                        'bandwidth_bps': dl.get('bandwidth', 0) * 8
                    }
            elif msg_type == 'upload':
                ul = msg.get('upload', {})
                with test_lock:
                    current_test['progress'] = {
                        'stage': 'upload',
                        'percent': int(ul.get('progress', 0) * 100),
                        'bandwidth_bps': ul.get('bandwidth', 0) * 8
                    }
            elif msg_type == 'ping':
                ping = msg.get('ping', {})
                with test_lock:
                    current_test['progress'] = {
                        'stage': 'ping',
                        'latency': ping.get('latency', 0)
                    }
            elif msg_type == 'result':
                result_data = msg
                break
            elif msg_type == 'log':
                level = msg.get('level', 'info')
                message = msg.get('message', '')
                if level in ('error', 'warning'):
                    cp.log(f'Ookla {level}: {message}')

        proc.wait()

        if result_data:
            dl_bw = result_data.get('download', {}).get('bandwidth', 0)
            ul_bw = result_data.get('upload', {}).get('bandwidth', 0)
            ping_ms = result_data.get('ping', {}).get('latency', 0)
            server = result_data.get('server', {})
            return {
                'download_bps': dl_bw * 8,
                'upload_bps': ul_bw * 8,
                'ping_ms': ping_ms,
                'server': server.get('name', ''),
                'server_location': server.get('location', ''),
                'isp': result_data.get('isp', '')
            }
        return None
    except Exception as e:
        cp.log(f'Ookla error: {e}')
        return None


# =============================================================================
# TEST RUNNER (background thread)
# =============================================================================

def write_outputs(entry):
    """Write test results to configured output paths."""
    try:
        val = cp.get_appdata('speedtest_outputs')
        if not val:
            return
        outputs = json.loads(val)
        if not outputs:
            return

        # Format result text with datetime and interface/carrier
        dl = entry.get('download_mbps', 0)
        ul = entry.get('upload_mbps', 0)
        timestamp = entry.get('timestamp', '')
        iface = entry.get('interface', '')
        engine = entry.get('engine', '')

        # Get carrier name if interface is a modem
        carrier = ''
        try:
            devices = cp.get('status/wan/devices')
            if devices:
                for uid, dev in devices.items():
                    if isinstance(dev, dict):
                        if dev.get('info', {}).get('iface') == iface:
                            diag = dev.get('diagnostics', {})
                            carrier = diag.get('CARRID', '')
                            break
        except Exception:
            pass

        text = f'DL:{dl}Mbps UL:{ul}Mbps'
        if entry.get('latency_ms'):
            text += f' Lat:{entry["latency_ms"]}ms'
        if entry.get('jitter_ms'):
            text += f' Jit:{entry["jitter_ms"]}ms'

        # Add interface/carrier info
        iface_info = carrier if carrier else iface
        if iface_info:
            text += f' Iface:{iface_info}'

        text += f' Engine:{engine} {timestamp}'

        for output in outputs:
            try:
                if output == 'appdata:speedtest_results':
                    cp.put_appdata('speedtest_results', text)
                elif output.startswith('config/') or output.startswith('status/'):
                    cp.put(output, text)
                else:
                    cp.put(output, text)
            except Exception as e:
                cp.log(f'Error writing to output {output}: {e}')
    except Exception as e:
        cp.log(f'Error in write_outputs: {e}')


def run_test_thread(engine, params):
    """Run a speed test in a background thread."""
    global current_test
    try:
        with test_lock:
            current_test['running'] = True
            current_test['engine'] = engine
            current_test['progress'] = {'stage': 'starting', 'percent': 0}
            current_test['error'] = None

        result = None
        interface = params.get('interface', '')
        duration = params.get('duration', 10)

        if engine == 'ookla':
            result = run_ookla(interface)
        elif engine == 'netperf':
            include_latency = params.get('include_latency', False)
            host = params.get('host', '')
            size = params.get('size', 0)
            result = run_netperf(interface, duration,
                                include_latency=include_latency, host=host,
                                size=size)
        elif engine == 'iperf3':
            server = params.get('server', '')
            if not server:
                with test_lock:
                    current_test['error'] = 'No iPerf3 server specified'
                    current_test['running'] = False
                return
            port = params.get('port', 5201)
            result = run_iperf3(server, duration, interface, port)

        if result:
            # Detect failed test (all zeros = failed)
            dl = result.get('download_bps', 0)
            ul = result.get('upload_bps', 0)
            is_failed = (dl == 0 and ul == 0)

            # Build history entry
            entry = {
                'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
                'engine': engine,
                'download_mbps': round(dl / 1000000, 2),
                'upload_mbps': round(ul / 1000000, 2),
                'ping_ms': round(result.get('ping_ms', 0), 1) if result.get('ping_ms') else None,
                'latency_ms': round(result.get('latency_ms', 0), 2) if result.get('latency_ms') else None,
                'jitter_ms': round(result.get('jitter_ms', 0), 2) if result.get('jitter_ms') else None,
                'interface': interface or 'auto',
                'duration': duration,
                'size': params.get('size', 0),
                'host': params.get('host', ''),
                'server': result.get('server', ''),
                'port': params.get('port', ''),
                'isp': result.get('isp', ''),
                'include_latency': params.get('include_latency', False),
                'status': 'failed' if is_failed else 'complete'
            }
            if engine == 'iperf3':
                entry['server'] = params.get('server', '')
                entry['port'] = params.get('port', '5201')
            if is_failed:
                entry['error'] = result.get('error', 'Test returned zero results')
                cp.log(f'Test FAILED: {entry["error"]}')
            add_result(entry)
            # Write to configured outputs (only for successful tests)
            if not is_failed:
                write_outputs(entry)
            with test_lock:
                current_test['progress'] = {
                    'stage': 'complete',
                    'result': entry
                }
                if is_failed:
                    current_test['error'] = entry.get('error', 'Test failed')
        else:
            with test_lock:
                err_msg = current_test.get('error') or 'Test failed'
                current_test['error'] = err_msg
            # Save failed entry to history
            entry = {
                'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
                'engine': engine,
                'download_mbps': 0,
                'upload_mbps': 0,
                'ping_ms': None,
                'latency_ms': None,
                'jitter_ms': None,
                'interface': interface or 'auto',
                'duration': duration,
                'server': params.get('server', ''),
                'status': 'failed',
                'error': current_test.get('error') or 'No results'
            }
            add_result(entry)
    except Exception as e:
        cp.log(f'Test thread error: {e}')
        with test_lock:
            current_test['error'] = str(e)
    finally:
        with test_lock:
            current_test['running'] = False


# =============================================================================
# HTTP SERVER
# =============================================================================

class SpeedtestHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for the speedtest web interface."""

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass

    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/' or self.path == '/index.html':
            self.serve_file('index.html', 'text/html')
        elif self.path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
        elif self.path == '/api/status':
            self.send_json(self.get_status())
        elif self.path == '/api/history':
            self.send_json(load_history())
        elif self.path == '/api/interfaces':
            self.send_json(get_wan_interfaces())
        elif self.path == '/api/engines':
            self.send_json(self.get_engines())
        elif self.path == '/api/router_info':
            self.send_json(self.get_router_info())
        elif self.path == '/api/schedule':
            with schedule_lock:
                data = dict(schedule_config)
            # Compute seconds until next cron match
            if data.get('enabled') and data.get('cron'):
                data['next_run_seconds'] = self._seconds_to_next_cron(data['cron'])
            self.send_json(data)
        elif self.path == '/api/outputs':
            self.send_json(self.get_outputs())
        elif self.path == '/api/iperf3_servers':
            self.send_json(self.get_iperf3_servers())
        elif self.path == '/api/servers':
            self.send_json(self.get_all_servers())
        elif self.path == '/api/reports':
            self.send_json(self.get_saved_reports())
        elif self.path.startswith('/static/'):
            self.serve_static()
        else:
            self.send_error(404)

    def do_POST(self):
        """Handle POST requests."""
        if self.path == '/api/start':
            self.handle_start()
        elif self.path == '/api/stop':
            self.handle_stop()
        elif self.path == '/api/clear_history':
            self.handle_clear_history()
        elif self.path == '/api/servers/save':
            self.handle_save_server()
        elif self.path == '/api/servers/delete':
            self.handle_delete_server()
        elif self.path == '/api/reports/save':
            self.handle_save_report()
        elif self.path == '/api/reports/delete':
            self.handle_delete_report()
        elif self.path == '/api/schedule':
            self.handle_save_schedule()
        elif self.path == '/api/outputs':
            self.handle_save_outputs()
        else:
            self.send_error(404)

    def do_DELETE(self):
        """Handle DELETE requests."""
        if self.path.startswith('/api/servers/delete'):
            self.handle_delete_server()
        else:
            self.send_error(404)

    def get_status(self):
        """Get current test status."""
        with test_lock:
            return {
                'running': current_test['running'],
                'engine': current_test['engine'],
                'progress': current_test['progress'].copy(),
                'error': current_test['error']
            }

    def get_router_info(self):
        """Get router hostname for filenames."""
        try:
            hostname = cp.get('config/system/system_id') or 'router'
            return {'hostname': hostname}
        except Exception:
            return {'hostname': 'router'}

    def _seconds_to_next_cron(self, cron_expr):
        """Estimate seconds until next cron match (max 24h lookahead)."""
        try:
            now = datetime.utcnow()
            for i in range(1, 1441):  # Check next 24 hours, minute by minute
                candidate = datetime(now.year, now.month, now.day,
                                     now.hour, now.minute) 
                # Add i minutes
                import calendar
                total_minutes = now.hour * 60 + now.minute + i
                days_ahead = total_minutes // 1440
                remaining = total_minutes % 1440
                candidate = now.replace(hour=remaining // 60,
                                        minute=remaining % 60, second=0)
                if days_ahead > 0:
                    # Simple next-day approximation
                    pass
                if cron_matches(cron_expr, candidate):
                    return i * 60 - now.second
            return None
        except Exception:
            return None

    def get_engines(self):
        """Get available speedtest engines."""
        engines = []
        if has_ookla():
            engines.append({
                'id': 'ookla',
                'name': 'Ookla Speedtest',
                'description': 'Licensed Ookla binary detected',
                'needs_server': False
            })
        engines.append({
            'id': 'netperf',
            'name': 'Netperf (Built-in)',
            'description': 'Uses router built-in netperf service',
            'needs_server': False
        })
        engines.append({
            'id': 'iperf3',
            'name': 'iPerf3',
            'description': 'Requires external iPerf3 server',
            'needs_server': True
        })
        return engines

    def get_iperf3_servers(self):
        """Load iperf3 server list from appdata 'iperf3_servers' (JSON),
        falling back to bundled CSV.

        Appdata format: [{"server":"host","port":"5201-5210","country":"US","city":"Seattle"}, ...]
        Port can be a single port ("5201") or a range ("5201-5210").
        """
        # Try appdata first (allows NCM group config push)
        try:
            servers_json = cp.get_appdata('iperf3_servers')
            if servers_json:
                servers = json.loads(servers_json)
                if isinstance(servers, list) and len(servers) > 0:
                    return servers
        except Exception as e:
            cp.log(f'Error reading iperf3_servers appdata: {e}')

        # Fall back to bundled JSON file
        servers = []
        json_path = 'iperf3_working_servers.json'
        try:
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    servers = json.load(f)
        except Exception as e:
            cp.log(f'Error loading iperf3 servers JSON: {e}')
        return servers

    def handle_start(self):
        """Start a speed test."""
        global current_test
        if current_test['running']:
            self.send_json({'error': 'Test already running'}, 409)
            return

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else '{}'
        try:
            params = json.loads(body)
        except json.JSONDecodeError:
            self.send_json({'error': 'Invalid JSON'}, 400)
            return

        engine = params.get('engine', 'netperf')
        if engine == 'ookla' and not has_ookla():
            self.send_json({'error': 'Ookla binary not found'}, 400)
            return

        thread = Thread(target=run_test_thread, args=(engine, params), daemon=True)
        thread.start()
        self.send_json({'status': 'started', 'engine': engine})

    def handle_stop(self):
        """Stop a running test."""
        global current_test
        with test_lock:
            current_test['running'] = False
        cp.stop_speed_test()
        self.send_json({'status': 'stopped'})

    def handle_clear_history(self):
        """Clear test history."""
        save_history([])
        self.send_json({'status': 'cleared'})

    def get_all_servers(self):
        """Get all saved servers (netperf and iperf3) from appdata."""
        result = {'netperf': [], 'iperf3': []}
        # Netperf servers
        try:
            val = cp.get_appdata('netperf_servers')
            if val:
                result['netperf'] = json.loads(val)
        except Exception:
            pass
        # iPerf3 servers
        result['iperf3'] = self.get_iperf3_servers()
        return result

    def handle_save_server(self):
        """Save a server to appdata."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else '{}'
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_json({'error': 'Invalid JSON'}, 400)
            return

        engine = data.get('engine', '')
        server_entry = data.get('server', {})
        if not engine or not server_entry:
            self.send_json({'error': 'Missing engine or server'}, 400)
            return

        appdata_key = 'netperf_servers' if engine == 'netperf' else 'iperf3_servers'

        try:
            existing = cp.get_appdata(appdata_key)
            if existing:
                servers = json.loads(existing)
            else:
                servers = []
        except Exception:
            servers = []

        # Avoid duplicates by server hostname
        server_host = server_entry.get('server', '')
        servers = [s for s in servers if s.get('server') != server_host]
        servers.append(server_entry)

        cp.put_appdata(appdata_key, json.dumps(servers))
        self.send_json({'status': 'saved', 'servers': servers})

    def handle_delete_server(self):
        """Delete a server from appdata."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else '{}'
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_json({'error': 'Invalid JSON'}, 400)
            return

        engine = data.get('engine', '')
        server_host = data.get('server', '')
        if not engine or not server_host:
            self.send_json({'error': 'Missing engine or server'}, 400)
            return

        appdata_key = 'netperf_servers' if engine == 'netperf' else 'iperf3_servers'

        try:
            existing = cp.get_appdata(appdata_key)
            if existing:
                servers = json.loads(existing)
            else:
                servers = []
        except Exception:
            servers = []

        servers = [s for s in servers if s.get('server') != server_host]
        cp.put_appdata(appdata_key, json.dumps(servers))
        self.send_json({'status': 'deleted', 'servers': servers})

    def get_saved_reports(self):
        """Get saved reports from file."""
        try:
            if os.path.exists('tmp/saved_reports.json'):
                with open('tmp/saved_reports.json', 'r') as f:
                    return json.load(f)
        except Exception as e:
            cp.log(f'Error loading reports: {e}')
        return []

    def handle_save_report(self):
        """Save a named report (snapshot of current history stats)."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else '{}'
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_json({'error': 'Invalid JSON'}, 400)
            return
        name = data.get('name', '').strip()
        if not name:
            self.send_json({'error': 'Report name required'}, 400)
            return
        report = data.get('report', {})
        report['name'] = name
        report['saved_at'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

        reports = self.get_saved_reports()
        reports.append(report)
        os.makedirs('tmp', exist_ok=True)
        with open('tmp/saved_reports.json', 'w') as f:
            json.dump(reports, f)
        self.send_json({'status': 'saved'})

    def handle_delete_report(self):
        """Delete a saved report by index."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else '{}'
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_json({'error': 'Invalid JSON'}, 400)
            return
        idx = data.get('index', -1)
        reports = self.get_saved_reports()
        if 0 <= idx < len(reports):
            reports.pop(idx)
            os.makedirs('tmp', exist_ok=True)
            with open('tmp/saved_reports.json', 'w') as f:
                json.dump(reports, f)
        self.send_json({'status': 'deleted', 'reports': reports})

    def handle_save_schedule(self):
        """Save or update the test schedule."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else '{}'
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_json({'error': 'Invalid JSON'}, 400)
            return
        config = {
            'enabled': bool(data.get('enabled', False)),
            'autostart': bool(data.get('autostart', False)),
            'cron': data.get('cron', ''),
            'engine': data.get('engine', 'netperf'),
            'params': data.get('params', {})
        }
        save_schedule(config)
        status = 'enabled' if config['enabled'] else 'disabled'
        cp.log(f'Schedule {status}: {config["cron"]}')
        self.send_json({'status': status, 'schedule': config})

    def get_outputs(self):
        """Get configured output paths."""
        try:
            val = cp.get_appdata('speedtest_outputs')
            if val:
                return {'outputs': json.loads(val)}
        except Exception:
            pass
        return {'outputs': []}

    def handle_save_outputs(self):
        """Save output configuration."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else '{}'
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_json({'error': 'Invalid JSON'}, 400)
            return
        outputs = data.get('outputs', [])
        cp.put_appdata('speedtest_outputs', json.dumps(outputs))
        cp.log(f'Outputs configured: {outputs}')
        self.send_json({'status': 'saved', 'outputs': outputs})

    def send_json(self, data, code=200):
        """Send a JSON response."""
        body = json.dumps(data).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def serve_file(self, filename, content_type):
        """Serve a file from the app directory."""
        try:
            with open(filename, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404)

    def serve_static(self):
        """Serve static files."""
        path = self.path.lstrip('/')
        if '..' in path:
            self.send_error(403)
            return

        ext_map = {
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.html': 'text/html',
            '.svg': 'image/svg+xml',
            '.png': 'image/png',
            '.ico': 'image/x-icon',
            '.woff': 'font/woff',
            '.woff2': 'font/woff2',
            '.ttf': 'font/ttf'
        }
        ext = os.path.splitext(path)[1].lower()
        content_type = ext_map.get(ext, 'application/octet-stream')

        try:
            with open(path, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404)


# =============================================================================
# MAIN
# =============================================================================

def cron_matches(cron_expr, dt):
    """Check if a datetime matches a cron expression (minute hour dom month dow)."""
    try:
        fields = cron_expr.strip().split()
        if len(fields) != 5:
            return False

        def match_field(field, value, min_val, max_val):
            for part in field.split(','):
                part = part.strip()
                if '/' in part:
                    base, step = part.split('/', 1)
                    step = int(step)
                    start = min_val if base == '*' else int(base.split('-')[0] if '-' in base else base)
                    if value >= start and (value - start) % step == 0:
                        return True
                elif part == '*':
                    return True
                elif '-' in part:
                    a, b = part.split('-', 1)
                    if int(a) <= value <= int(b):
                        return True
                else:
                    if int(part) == value:
                        return True
            return False

        # dow: 0=Sunday in cron, Python weekday: 0=Monday
        cron_dow = (dt.weekday() + 1) % 7
        return (match_field(fields[0], dt.minute, 0, 59) and
                match_field(fields[1], dt.hour, 0, 23) and
                match_field(fields[2], dt.day, 1, 31) and
                match_field(fields[3], dt.month, 1, 12) and
                match_field(fields[4], cron_dow, 0, 7))
    except Exception:
        return False


def load_schedule():
    """Load schedule from appdata. If autostart is set, enable on boot."""
    global schedule_config
    try:
        val = cp.get_appdata('speedtest_schedule')
        if val:
            data = json.loads(val)
            with schedule_lock:
                schedule_config.update(data)
                # Auto-enable on boot if autostart is checked
                if schedule_config.get('autostart', False):
                    schedule_config['enabled'] = True
    except Exception:
        pass


def save_schedule(config):
    """Save schedule to appdata."""
    global schedule_config
    with schedule_lock:
        schedule_config.update(config)
    cp.put_appdata('speedtest_schedule', json.dumps(config))


def scheduler_thread():
    """Background thread that checks cron schedule and runs tests."""
    last_fired = None
    while True:
        try:
            with schedule_lock:
                enabled = schedule_config.get('enabled', False)
                cron = schedule_config.get('cron', '')
                engine = schedule_config.get('engine', 'netperf')
                params = schedule_config.get('params', {})

            if enabled and cron:
                now = datetime.utcnow()
                current_minute = (now.year, now.month, now.day, now.hour, now.minute)
                if current_minute != last_fired and cron_matches(cron, now):
                    last_fired = current_minute
                    if not current_test['running']:
                        cp.log(f'Scheduled test triggered: {cron}')
                        params_copy = dict(params)
                        params_copy['engine'] = engine
                        thread = Thread(target=run_test_thread,
                                        args=(engine, params_copy), daemon=True)
                        thread.start()
        except Exception as e:
            cp.log(f'Scheduler error: {e}')
        time.sleep(15)


cp.log('Starting...')
cp.log('speedtest_web - Speed Test Web Interface')

# Check available engines
if has_ookla():
    cp.log('Ookla binary detected - will use as primary engine')
else:
    cp.log('No Ookla binary - using Netperf (built-in) as default')

# Load saved schedule
load_schedule()
if schedule_config.get('enabled'):
    cp.log(f'Schedule active: {schedule_config.get("cron", "")}')

# Start scheduler thread
sched_thread = Thread(target=scheduler_thread, daemon=True)
sched_thread.start()

# Start web server
try:
    HTTPServer.allow_reuse_address = True
    server = HTTPServer(('', PORT), SpeedtestHandler)
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    cp.log(f'Web server started on port {PORT}')
except Exception as e:
    cp.log(f'Failed to start web server: {e}')
    sys.exit(1)

# Main loop
while True:
    time.sleep(1)
