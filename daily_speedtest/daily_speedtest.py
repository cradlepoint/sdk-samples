# daily_speedtest - run an ookla speedtest daily at configured hours and put results to user defined field (asset_id)

import time
import json
from datetime import datetime
import cp
from speedtest import Speedtest

# Hours of day to run speedtests. 24-hour format.  Default is 8am, 12pm, 4pm.
testing_hours = [8, 12, 16]
results_field = 'config/system/asset_id'
default_appdata = {"testing_hours": testing_hours, "results_field": results_field}
last_test_dates = {}

def get_appdata(name):
    """Get appdata from NCOS Configs. If not found, save default_appdata and return it."""
    try:
        appdata = cp.get('config/system/sdk/appdata')
        data = json.loads([x["value"] for x in appdata if x["name"] == name][0])
    except:
        data = default_appdata
        cp.post('config/system/sdk/appdata', {"name": name, "value": json.dumps(data)})
        cp.log(f'No appdata found - Saved default: {data}')
    return data

def run_speedtest():
    cp.log(f'Daily speedtest hours: {testing_hours} -- Running now...')
    wan = cp.get('status/wan/primary_device')
    wan_ip = cp.get(f'status/wan/devices/{wan}/status/ipinfo/ip_address')
    speedtest = Speedtest(source_address=wan_ip)
    speedtest.get_best_server()
    speedtest.download()
    speedtest.upload(pre_allocate=False)
    down = '{:.2f}'.format(speedtest.results.download / 1000 / 1000)
    up = '{:.2f}'.format(speedtest.results.upload / 1000 / 1000)
    latency = int(speedtest.results.ping)
    results_text = f'{down}Mbps Down / {up}Mbps Up / {latency}ms'
    cp.log(results_text)
    cp.put(results_field, results_text)
    # Optional Alert
    # cp.alert(results_text)


# Start App
cp.log('Starting...')

# Wait for NCM connection
while not cp.get('status/ecm/state') == 'connected':
    time.sleep(2)

# Main Loop
while True:
    config = get_appdata('daily_speedtest')
    testing_hours = config['testing_hours']
    results_field = config['results_field']
    for testing_hour in testing_hours:
        if not last_test_dates.get(testing_hour):
            last_test_dates[testing_hour] = None
        if last_test_dates[testing_hour] != datetime.today().date():
            if testing_hour == datetime.now().today().hour:
                run_speedtest()
                last_test_dates[testing_hour] = datetime.today().date()
    time.sleep(60)
