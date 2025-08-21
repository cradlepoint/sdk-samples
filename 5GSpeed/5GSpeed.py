"""5GSpeed runs Ookla speedtests and puts results into configurable field.  Designed to enable NCM API support for Ookla speedtests.

Steps to use:
=============
The app will create an entry in the router configuration under System > SDK Data named "5GSpeed" with the path for the results field.
Default is config/system/asset_id

Clear the results by performing any of the following:

1. Use NCM API PUT router request to clear the results field and to run the SDK speedtest. Wait for 1 min, and run NCM API Get router request to get the result.

2. Clear the results in NCM > Devices tab (if using description or asset_id)

3. Go to device console and clear results field:
put {results_path} ""

Sample result:
DL:52.54Mbps - UL:16.55Mbps - Ping:9.715ms - Server:Telstra - ISP:Vocus Communications - TimeGMT:2023-04-11T01:06:43.758382Z - URL:http://www.speedtest.net/result/14595594656.png

Retrieve Results via NCM API:
=============================
Generate NCM API v2 API Keys on the Tools page > NetCloud API tab in NCM.
Use those keys in the headers of an HTTP GET request to https://www.cradlepointecm.com/api/v2/routers/{router_id/
router_id can be found in NCM or at CLI: get status/ecm/client_id
The results are in the field defined in SDK Data (default is asset_id)

Clear results and run new test via NCM API:
===========================================
Use API keys in headers of an HTTP PUT request to https://www.cradlepointecm.com/api/v2/routers/{router_id/
Content-Type: application/json
Body contains blank field defined in SDK Data (default is asset_id):
{"asset_id": ""}

In a few minutes, new results should populate.
"""

import cp
from speedtest import Speedtest
import time

default_results_path = "config/system/asset_id"

def get_config(name):
    try:
        appdata = cp.get('config/system/sdk/appdata')
        return [x["value"] for x in appdata if x["name"] == name][0]
    except:
        cp.log('No config found - saving defaults.')
        cp.post('config/system/sdk/appdata', {"name": name, "value": default_results_path})
        return default_results_path

def results_field_check(path, results, *args):
    try:
        if not results:
            cp.log('Initiating Speedtest due to cleared results...')
            speedtest()
        else:
            cp.log(f'5GSpeed ready. To start speedtest: put {results_path} ""')
        return
    except Exception as e:
        cp.logger.exception(e)

def speedtest():
    try:
        cp.log('Starting Speedtest...')
        s = Speedtest()
        server = s.get_best_server()
        cp.log(f'Found Best Ookla Server: {server["sponsor"]}')
        cp.log("Performing Ookla Download Test...")
        d = s.download()
        cp.log("Performing Ookla Upload Test...")
        u = s.upload(pre_allocate=False)
        download = '{:.2f}'.format(d / 1000 / 1000)
        upload = '{:.2f}'.format(u / 1000 / 1000)
        cp.log('Ookla Speedtest Complete! Results:')
        cp.log(f'Client ISP: {s.results.client["isp"]}')
        cp.log(f'Ookla Server: {s.results.server["sponsor"]}')
        cp.log(f'Ping: {s.results.ping}ms')
        cp.log(f'Download Speed: {download}Mb/s')
        cp.log(f'Upload Speed: {upload} Mb/s')
        cp.log(f'Ookla Results Image: {s.results.share()}')
        text = f'DL:{download}Mbps - UL:{upload}Mbps - Ping:{s.results.ping}ms - Server:{s.results.server["sponsor"]} - ISP:{s.results.client["isp"]} - TimeGMT:{s.results.timestamp} - Img:{s.results.share()}'
        cp.put(results_path, text)
        return
    except Exception as e:
        cp.logger.exception(e)

try:
    cp.log('Starting...')
    while not cp.get('status/wan/connection_state') == 'connected':
        time.sleep(2)
    results_path = get_config('5GSpeed')
    cp.on('put', results_path, results_field_check)
    boot_results = cp.get(results_path)
    results_field_check(None, boot_results, None)
    while True:
        time.sleep(60)
except Exception as e:
    cp.logger.exception(e)
