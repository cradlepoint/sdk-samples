"""5GSpeed runs speedtests and puts results into configurable field.
Designed to enable NCM API support for speedtests.

Speedtest engines (in priority order):
1. Ookla - if licensed 'ookla' binary is present in app directory
2. Netperf - built-in router netperf service (default fallback)

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
import os
import time
from datetime import datetime

default_results_path = "config/system/asset_id"


def has_ookla():
    """Check if ookla binary is present."""
    if os.path.exists('ookla'):
        if not os.access('ookla', os.X_OK):
            try:
                os.chmod('ookla', 0o755)
            except Exception:
                pass
        return True
    return False


def get_config(name):
    try:
        appdata = cp.get('config/system/sdk/appdata')
        return [x["value"] for x in appdata if x["name"] == name][0]
    except Exception:
        cp.log('No config found - saving defaults.')
        cp.post('config/system/sdk/appdata',
                {"name": name, "value": default_results_path})
        return default_results_path


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
    """Run speedtest with Ookla if available, fallback to netperf."""
    text = None
    if has_ookla():
        text = speedtest_ookla()
    if not text:
        if has_ookla():
            cp.log('Ookla failed, falling back to netperf...')
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
    engine = 'Ookla' if has_ookla() else 'Netperf (built-in)'
    cp.log(f'Speedtest engine: {engine}')
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
