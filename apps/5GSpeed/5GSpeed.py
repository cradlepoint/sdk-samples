"""5GSpeed runs speedtests and puts results into configurable field.
Designed to enable NCM API support for speedtests.

Speedtest engines (in priority order):
1. Ookla - if licensed 'ookla' binary is present in app directory
2. iPerf3 - if appdata "speedtest" is set to "iperf3" and "iperf3_server" is configured
3. Netperf - built-in router netperf service (default fallback)

SDK Appdata fields:
- "5GSpeed" - path to results field (default: config/system/asset_id)
- "speedtest" - engine selection: "netperf" (default) or "iperf3"
- "iperf3_server" - iPerf3 server in format ip_address:portx-porty
  (e.g., "10.0.0.1:5201-5210"). Uses first port for upload, second for download.
  If single port (e.g., "10.0.0.1:5201"), uses same port for both.

Steps to use:
=============
The app will create an entry in the router configuration under System > SDK Data named "5GSpeed"
with the path for the results field. Default is config/system/asset_id

Clear the results by performing any of the following:

1. Use NCM API PUT router request to clear the results field and to run the SDK speedtest.
   Wait for 1 min, and run NCM API Get router request to get the result.

2. Clear the results in NCM > Devices tab (if using description or asset_id)

3. Go to device console and clear results field:
put {results_path} ""

Sample result (Ookla):
DL:52.54Mbps UL:16.55Mbps Ping:9.7ms Server:Telstra ISP:Vocus Time:2023-04-11T01:06:43Z

Sample result (Netperf):
DL:96.82Mbps UL:46.74Mbps Engine:netperf Time:2023-04-11T01:06:43Z

Sample result (iPerf3):
DL:85.23Mbps UL:42.11Mbps Engine:iperf3 Server:10.0.0.1:5201 Time:2023-04-11T01:06:43Z

Retrieve Results via NCM API:
=============================
Generate NCM API v2 API Keys on the Tools page > NetCloud API tab in NCM.
Use those keys in the headers of an HTTP GET request to
https://www.cradlepointecm.com/api/v2/routers/{router_id}/
router_id can be found in NCM or at CLI: get status/ecm/client_id
The results are in the field defined in SDK Data (default is asset_id)

Clear results and run new test via NCM API:
===========================================
Use API keys in headers of an HTTP PUT request to
https://www.cradlepointecm.com/api/v2/routers/{router_id}/
Content-Type: application/json
Body contains blank field defined in SDK Data (default is asset_id):
{"asset_id": ""}

In a few minutes, new results should populate.
"""

import cp
import json
import os
import subprocess
import time
from datetime import datetime

default_results_path = "config/system/asset_id"

OOKLA_BINARIES = ('ookla', 'speedtest', 'speedtest-cli')
IPERF3_BINARIES = ('iperf3', 'iperf3-arm64v8', 'iperf3-aarch64')


def _find_binary(candidates):
    """Find first existing binary from candidates list, chmod if needed."""
    for name in candidates:
        if os.path.exists(name):
            if not os.access(name, os.X_OK):
                try:
                    os.chmod(name, 0o755)
                except Exception:
                    pass
            return './' + name
    return None


def has_ookla():
    """Check if ookla binary is present (BYOB)."""
    return _find_binary(OOKLA_BINARIES) is not None


def has_iperf3():
    """Check if iperf3 binary is present."""
    return _find_binary(IPERF3_BINARIES) is not None


def get_appdata_value(name):
    """Read a single appdata field value. Returns empty string if not found."""
    try:
        appdata = cp.get('config/system/sdk/appdata')
        if appdata:
            for item in appdata:
                if item.get('name') == name:
                    return item.get('value', '')
    except Exception as e:
        cp.log(f'Error reading appdata {name}: {e}')
    return ''


def get_config(name):
    try:
        appdata = cp.get('config/system/sdk/appdata')
        return [x["value"] for x in appdata if x["name"] == name][0]
    except Exception:
        cp.log('No config found - saving defaults.')
        cp.post('config/system/sdk/appdata',
                {"name": name, "value": default_results_path})
        return default_results_path


def parse_iperf3_server(server_str):
    """Parse iperf3_server appdata value.

    Format: ip_address:portx-porty  (e.g., "10.0.0.1:5201-5210")
    Or:     ip_address:port         (e.g., "10.0.0.1:5201")

    Returns (host, port_start, port_end) or None on failure.
    port_start == port_end when a single port is specified.
    """
    if not server_str:
        return None
    try:
        host, port_part = server_str.rsplit(':', 1)
        if '-' in port_part:
            ports = port_part.split('-', 1)
            port_start = int(ports[0])
            port_end = int(ports[1])
        else:
            port_start = int(port_part)
            port_end = port_start
        return (host, port_start, port_end)
    except (ValueError, IndexError) as e:
        cp.log(f'Invalid iperf3_server format "{server_str}": {e}')
        return None


def speedtest_ookla():
    """Run speedtest using Ookla binary. Returns formatted text or None."""
    try:
        from speedtest_ookla import Speedtest
        cp.log('Starting Ookla Speedtest...')
        s = Speedtest(timeout=90)
        s.start()
        r = s.results
        download = '{:.2f}'.format(r.download / 1000 / 1000)
        upload = '{:.2f}'.format(r.upload / 1000 / 1000)
        cp.log(f'Ookla Speedtest Complete!')
        cp.log(f'Download: {download}Mb/s  Upload: {upload}Mb/s  Ping: {r.ping}ms')
        text = (f'DL:{download}Mbps UL:{upload}Mbps Ping:{r.ping}ms '
                f'Server:{r.server.get("name", "Unknown")} ISP:{r.isp} '
                f'Time:{r.timestamp}')
        return text
    except Exception as e:
        cp.log(f'Ookla speedtest error: {e}')
        return None


def speedtest_iperf3():
    """Run speedtest using iPerf3 binary. Returns formatted text or None."""
    server_str = get_appdata_value('iperf3_server')
    parsed = parse_iperf3_server(server_str)
    if not parsed:
        cp.log('iPerf3 selected but no valid iperf3_server configured.')
        cp.log('Set appdata "iperf3_server" to ip_address:portx-porty')
        return None

    binary = _find_binary(IPERF3_BINARIES)
    if not binary:
        cp.log('iPerf3 binary not found')
        return None

    host, port_start, port_end = parsed
    cp.log(f'Starting iPerf3 Speedtest to {host} (ports {port_start}-{port_end})...')

    # Upload test - try ports starting from port_start
    ul_mbps, ul_port = _run_iperf3_with_port_retry(
        binary, host, port_start, port_end, reverse=False
    )

    # Download test - try ports starting from port_start
    dl_mbps, dl_port = _run_iperf3_with_port_retry(
        binary, host, port_start, port_end, reverse=True
    )

    if dl_mbps is not None and ul_mbps is not None:
        timestamp = f'{datetime.utcnow().isoformat()}Z'
        cp.log(f'iPerf3 Speedtest Complete!')
        cp.log(f'Download: {dl_mbps:.2f}Mb/s  Upload: {ul_mbps:.2f}Mb/s')
        text = (f'DL:{dl_mbps:.2f}Mbps UL:{ul_mbps:.2f}Mbps '
                f'Engine:iperf3 Server:{host}:{dl_port} Time:{timestamp}')
        return text
    else:
        cp.log('iPerf3 test failed on all ports in range')
        return None


def _run_iperf3_with_port_retry(binary, host, port_start, port_end, reverse=False):
    """Try iperf3 test starting at port_start, increment on failure until port_end.

    Returns (mbps, port_used) or (None, None).
    """
    for port in range(port_start, port_end + 1):
        result = _run_iperf3_test(binary, host, port, reverse=reverse)
        if result is not None:
            return (result, port)
        cp.log(f'  Port {port} failed/busy, trying next...')
    return (None, None)


def _run_iperf3_test(binary, host, port, reverse=False):
    """Run a single iperf3 test. Returns Mbps or None."""
    try:
        cmd = [binary, '-c', host, '-p', str(port), '-t', '10', '-J']
        if reverse:
            cmd.append('-R')
        cp.log(f'  iperf3 cmd: {" ".join(cmd)}')
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
            cp.log('iPerf3 timed out after 60s')
            return None

        stdout = proc.stdout.read().decode('utf-8')
        if proc.returncode != 0:
            stderr = proc.stderr.read().decode('utf-8')
            cp.log(f'iPerf3 error (rc={proc.returncode}): {stderr}')
            return None

        results = json.loads(stdout)
        if reverse:
            bps = results['end']['sum_received']['bits_per_second']
        else:
            bps = results['end']['sum_sent']['bits_per_second']
        return round(bps / 1000000, 2)
    except (json.JSONDecodeError, KeyError) as e:
        cp.log(f'iPerf3 parse error: {e}')
        return None
    except Exception as e:
        cp.log(f'iPerf3 error: {e}')
        return None


def speedtest_netperf():
    """Run speedtest using router's built-in netperf. Returns formatted text or None."""
    try:
        cp.log('Starting Netperf Speedtest...')
        result = cp.speed_test(duration=10, direction='both')
        if result:
            dl_mbps = result.get('download_bps', 0) / 1000000
            ul_mbps = result.get('upload_bps', 0) / 1000000
            timestamp = f'{datetime.utcnow().isoformat()}Z'
            cp.log(f'Netperf Speedtest Complete!')
            cp.log(f'Download: {dl_mbps:.2f}Mb/s  Upload: {ul_mbps:.2f}Mb/s')
            text = (f'DL:{dl_mbps:.2f}Mbps UL:{ul_mbps:.2f}Mbps '
                    f'Engine:netperf Time:{timestamp}')
            return text
        else:
            cp.log('Netperf returned no results')
            return None
    except Exception as e:
        cp.log(f'Netperf speedtest error: {e}')
        return None


def speedtest():
    """Run speedtest with engine priority: Ookla (if present) > configured engine > netperf."""
    text = None

    # Ookla always takes priority if binary is present
    if has_ookla():
        text = speedtest_ookla()
        if text:
            cp.put(results_path, text)
            return
        cp.log('Ookla failed, trying configured engine...')

    # Check configured engine from appdata
    engine = get_appdata_value('speedtest') or 'netperf'
    engine = engine.strip().lower()

    if engine == 'iperf3':
        if has_iperf3():
            text = speedtest_iperf3()
            if text:
                cp.put(results_path, text)
                return
            cp.log('iPerf3 failed, falling back to netperf...')
        else:
            cp.log('iperf3 engine selected but no binary found, '
                   'falling back to netperf...')

    # Default: netperf
    text = speedtest_netperf()
    if text:
        cp.put(results_path, text)
    else:
        cp.log('All speedtest engines failed.')
        cp.put(results_path, 'Speedtest failed')


def results_field_check(path, results, *args):
    try:
        if not results:
            cp.log('Initiating Speedtest due to cleared results...')
            speedtest()
        else:
            cp.log(f'5GSpeed ready. To start speedtest: put {results_path} ""')
    except Exception as e:
        cp.log(f'Error: {e}')


try:
    cp.log('Starting...')
    engine_label = 'Ookla' if has_ookla() else 'Netperf (built-in)'
    configured = get_appdata_value('speedtest') or 'netperf'
    if configured.strip().lower() == 'iperf3' and has_iperf3():
        engine_label = 'iPerf3'
    elif configured.strip().lower() == 'iperf3' and not has_ookla():
        engine_label = 'iPerf3 (binary found)' if has_iperf3() else 'Netperf (iperf3 binary missing)'
    cp.log(f'Speedtest engine: {engine_label}')
    while not cp.get('status/wan/connection_state') == 'connected':
        time.sleep(2)
    results_path = get_config('5GSpeed')
    cp.on('put', results_path, results_field_check)
    boot_results = cp.get(results_path)
    results_field_check(None, boot_results, None)
    while True:
        time.sleep(60)
except Exception as e:
    cp.log(f'Fatal error: {e}')
