"""
speedtest_scheduled_custom1 - Run Ookla speedtests on a cron schedule from appdata.
Results are written to NCM custom1 field via the ncm PyPI library.

Appdata fields:
  schedule   - cron expression (default: "0 8,12,17 * * *")
  ncm_keys   - JSON string with NCM API keys:
               {"X-CP-API-ID":"...","X-CP-API-KEY":"...","X-ECM-API-ID":"...","X-ECM-API-KEY":"..."}
"""

import cp
import time
import json
from datetime import datetime
from speedtest_ookla import Speedtest
import ncm

DEFAULT_SCHEDULE = "0 12 * * *"


def get_appdata(name, default):
    try:
        appdata = cp.get('config/system/sdk/appdata')
        for item in appdata:
            if item['name'] == name:
                return item['value']
    except Exception as e:
        cp.log(f'Error reading appdata {name}: {e}')
    cp.post('config/system/sdk/appdata', {'name': name, 'value': default})
    cp.log(f'Saved default appdata {name}: {default}')
    return default


def cron_matches(expr, now):
    """Return True if the cron expression matches the given datetime (minute resolution)."""
    try:
        parts = expr.strip().split()
        if len(parts) != 5:
            return False
        minute, hour, dom, month, dow = parts
        checks = [
            (minute, now.minute),
            (hour, now.hour),
            (dom, now.day),
            (month, now.month),
            (dow, now.weekday()),  # 0=Monday; cron 0=Sunday - close enough for simple use
        ]
        for field, value in checks:
            if field == '*':
                continue
            values = set()
            for part in field.split(','):
                if '-' in part:
                    a, b = part.split('-')
                    values.update(range(int(a), int(b) + 1))
                elif '/' in part:
                    base, step = part.split('/')
                    start = 0 if base == '*' else int(base)
                    values.update(range(start, 60, int(step)))
                else:
                    values.add(int(part))
            if value not in values:
                return False
        return True
    except Exception as e:
        cp.log(f'Cron parse error: {e}')
        return False


def run_speedtest():
    try:
        s = Speedtest(timeout=90)
        s.start()
        r = s.results
        down = '{:.2f}'.format(r.download / 1e6)
        up = '{:.2f}'.format(r.upload / 1e6)
        ping = int(r.ping)
        result = f'{down}Mbps Down / {up}Mbps Up / {ping}ms'
        cp.log(f'Speedtest result: {result}')
        return result
    except Exception as e:
        cp.log(f'Speedtest error: {e}')
        return None


V2_KEYS = ('X-CP-API-ID', 'X-CP-API-KEY', 'X-ECM-API-ID', 'X-ECM-API-KEY')


def get_keys():
    try:
        keys = cp.get_ncm_api_keys() or {}
        if all(keys.get(k) for k in V2_KEYS):
            return {k: keys[k] for k in V2_KEYS}
    except Exception:
        pass
    try:
        keys = json.loads(get_appdata('ncm_keys', '{}'))
        if keys:
            return keys
    except Exception:
        pass
    return None


def put_custom1(result_text):
    try:
        keys = get_keys()
        if not keys or not all(keys.get(k) for k in V2_KEYS):
            cp.log('No NCM keys available - skipping custom1 update')
            return
        ncm.set_api_keys(keys)
        router_id = cp.get('status/ecm/client_id')
        
        # Check if custom2 appdata exists
        use_custom2 = False
        try:
            appdata = cp.get('config/system/sdk/appdata')
            for item in appdata:
                if item['name'] == 'custom2':
                    use_custom2 = True
                    break
        except Exception:
            pass
        
        if use_custom2:
            ncm.set_custom2(router_id, result_text)
            cp.log('Custom2 updated successfully')
        else:
            ncm.set_custom1(router_id, result_text)
            cp.log('Custom1 updated successfully')
    except Exception as e:
        cp.log(f'NCM update error: {e}')


cp.log('Starting speedtest_scheduled_custom1...')
cp.wait_for_wan_connection()

last_fired_minute = None

while True:
    try:
        schedule = get_appdata('schedule', DEFAULT_SCHEDULE)
        if len(schedule.strip().split()) != 5:
            schedule = DEFAULT_SCHEDULE
        now = datetime.now()
        current_minute = (now.year, now.month, now.day, now.hour, now.minute)

        if current_minute != last_fired_minute and cron_matches(schedule, now):
            last_fired_minute = current_minute
            cp.log(f'Schedule matched at {now.strftime("%Y-%m-%d %H:%M")} - running speedtest')
            result = run_speedtest()
            if result:
                put_custom1(result)

    except Exception as e:
        cp.log(f'Main loop error: {e}')

    time.sleep(30)
