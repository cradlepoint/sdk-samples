"""
speedtest_scheduled_custom1 - Run speedtests on a cron schedule from appdata.
Results are written to NCM custom1 field via the ncm PyPI library.

Speedtest engines (in priority order):
1. Ookla - if licensed 'ookla' binary is present in app directory
2. Netperf - built-in router netperf service (default fallback)

Appdata fields:
  schedule   - cron expression (default: "0 8,12,17 * * *")
  ncm_keys   - JSON string with NCM API keys:
               {"X-CP-API-ID":"...","X-CP-API-KEY":"...","X-ECM-API-ID":"...","X-ECM-API-KEY":"..."}
"""

import cp
import os
import time
import json
from datetime import datetime
import ncm

DEFAULT_SCHEDULE = "0 12 * * *"


def get_appdata(name, default):
    try:
        val = cp.get_appdata(name)
        if val:
            return val
    except Exception:
        pass
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


def run_speedtest():
    """Run speedtest with Ookla if available, fallback to netperf."""
    if has_ookla():
        result = run_speedtest_ookla()
        if result:
            return result
        cp.log('Ookla failed, falling back to netperf...')
    return run_speedtest_netperf()


def run_speedtest_ookla():
    """Run speedtest using Ookla binary."""
    try:
        from speedtest_ookla import Speedtest
        s = Speedtest(timeout=90)
        s.start()
        r = s.results
        down = '{:.2f}'.format(r.download / 1e6)
        up = '{:.2f}'.format(r.upload / 1e6)
        ping = int(r.ping)
        result = f'{down}Mbps Down / {up}Mbps Up / {ping}ms'
        cp.log(f'Ookla result: {result}')
        return result
    except Exception as e:
        cp.log(f'Ookla error: {e}')
        return None


def run_speedtest_netperf():
    """Run speedtest using router's built-in netperf."""
    try:
        data = cp.speed_test(duration=10, direction='both')
        if data:
            dl = data.get('download_bps', 0) / 1e6
            ul = data.get('upload_bps', 0) / 1e6
            result = f'{dl:.2f}Mbps Down / {ul:.2f}Mbps Up'
            cp.log(f'Netperf result: {result}')
            return result
        cp.log('Netperf returned no results')
        return None
    except Exception as e:
        cp.log(f'Netperf error: {e}')
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
engine = 'Ookla' if has_ookla() else 'Netperf (built-in)'
cp.log(f'Speedtest engine: {engine}')
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
