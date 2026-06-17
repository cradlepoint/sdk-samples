# daily_speedtest - run speedtests daily at configured hours and put results to user defined field
#
# Speedtest engines (in priority order):
# 1. Ookla - if licensed 'ookla' binary is present in app directory
# 2. Netperf - built-in router netperf service (default fallback)

import os
import time
import json
from datetime import datetime
import cp

# Hours of day to run speedtests. 24-hour format.  Default is 8am, 12pm, 4pm.
testing_hours = [8, 12, 16]
results_field = 'config/system/asset_id'
default_appdata = {"testing_hours": testing_hours, "results_field": results_field}
last_test_dates = {}


OOKLA_BINARIES = ('ookla', 'speedtest', 'speedtest-cli')


def has_ookla():
    """Check if ookla binary is present (BYOB)."""
    for binary in OOKLA_BINARIES:
        if os.path.exists(binary):
            if not os.access(binary, os.X_OK):
                try:
                    os.chmod(binary, 0o755)
                except Exception:
                    pass
            return True
    return False


def get_appdata(name):
    """Get appdata from NCOS Configs. If not found, save default_appdata and return it."""
    try:
        appdata = cp.get('config/system/sdk/appdata')
        data = json.loads([x["value"] for x in appdata if x["name"] == name][0])
    except Exception:
        data = default_appdata
        cp.post('config/system/sdk/appdata',
                {"name": name, "value": json.dumps(data)})
        cp.log(f'No appdata found - Saved default: {data}')
    return data


def run_speedtest_ookla():
    """Run speedtest using Ookla binary. Returns formatted text or None."""
    try:
        from speedtest_ookla import Speedtest
        wan = cp.get('status/wan/primary_device')
        wan_ip = cp.get(f'status/wan/devices/{wan}/status/ipinfo/ip_address')
        speedtest = Speedtest(source_address=wan_ip, timeout=90)
        speedtest.start()
        r = speedtest.results
        down = '{:.2f}'.format(r.download / 1000 / 1000)
        up = '{:.2f}'.format(r.upload / 1000 / 1000)
        latency = int(r.ping)
        return f'{down}Mbps Down / {up}Mbps Up / {latency}ms'
    except Exception as e:
        cp.log(f'Ookla error: {e}')
        return None


def run_speedtest_netperf():
    """Run speedtest using router's built-in netperf. Returns formatted text or None."""
    try:
        result = cp.speed_test(duration=10, direction='both')
        if result:
            dl = result.get('download_bps', 0) / 1000000
            ul = result.get('upload_bps', 0) / 1000000
            return f'{dl:.2f}Mbps Down / {ul:.2f}Mbps Up'
        cp.log('Netperf returned no results')
        return None
    except Exception as e:
        cp.log(f'Netperf error: {e}')
        return None


def run_speedtest():
    """Run speedtest with Ookla if available, fallback to netperf."""
    cp.log(f'Daily speedtest hours: {testing_hours} -- Running now...')
    result = None
    if has_ookla():
        result = run_speedtest_ookla()
    if not result:
        if has_ookla():
            cp.log('Ookla failed, falling back to netperf...')
        result = run_speedtest_netperf()
    if result:
        cp.log(result)
        cp.put(results_field, result)
    else:
        cp.log('All speedtest engines failed.')


# Start App
cp.log('Starting...')
engine = 'Ookla' if has_ookla() else 'Netperf (built-in)'
cp.log(f'Speedtest engine: {engine}')

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
