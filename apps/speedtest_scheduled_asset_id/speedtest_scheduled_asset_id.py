"""
speedtest_scheduled_asset_id - Runs speedtest on a configurable cron schedule
and writes results to the router's asset_id field.

Speedtest engines (in priority order):
1. Ookla - if licensed 'ookla' binary is present in app directory
2. Netperf - built-in router netperf service (default fallback)

Results format: ISO timestamp followed by speedtest results and modem diagnostics.
Example: "DL: 26.8Mbps, UL: 12.5Mbps, Latency: 56ms, Carrier: Verizon, DBM: -74, SINR: 5.6, RSRP: -95, RSRQ: -11, 2024-03-15T14:30:00Z"

Modem diagnostics (Carrier, DBM, SINR, RSRP, RSRQ) are included only if the primary WAN device
is a modem.

Appdata fields:
- cron_schedule: Cron expression (minute hour day month weekday).
  Default: "0 2 * * 1" (Monday at 2:00 AM UTC)
"""

import cp
import os
import time
from datetime import datetime

DEFAULT_CRON = '0 2 * * 1'  # Monday at 2:00 AM UTC


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


def get_cron_schedule():
    """Read cron schedule from appdata, use default if not configured."""
    value = cp.get_appdata('cron_schedule')
    if value:
        return value
    return DEFAULT_CRON


def parse_cron_field(field, min_val, max_val):
    """Parse a single cron field and return set of matching values."""
    values = set()
    for part in field.split(','):
        part = part.strip()
        if '/' in part:
            range_part, step = part.split('/', 1)
            step = int(step)
            if range_part == '*':
                start = min_val
                end = max_val
            elif '-' in range_part:
                start, end = range_part.split('-', 1)
                start = int(start)
                end = int(end)
            else:
                start = int(range_part)
                end = max_val
            for i in range(start, end + 1, step):
                values.add(i)
        elif part == '*':
            for i in range(min_val, max_val + 1):
                values.add(i)
        elif '-' in part:
            start, end = part.split('-', 1)
            for i in range(int(start), int(end) + 1):
                values.add(i)
        else:
            values.add(int(part))
    return values


def cron_matches(cron_expr, dt):
    """Check if a datetime matches a cron expression."""
    try:
        fields = cron_expr.strip().split()
        if len(fields) != 5:
            cp.log(f'Invalid cron expression: {cron_expr}')
            return False

        minutes = parse_cron_field(fields[0], 0, 59)
        hours = parse_cron_field(fields[1], 0, 23)
        days = parse_cron_field(fields[2], 1, 31)
        months = parse_cron_field(fields[3], 1, 12)
        weekdays = parse_cron_field(fields[4], 0, 7)

        # Convert Python weekday (0=Monday) to cron weekday (0=Sunday)
        cron_dow = (dt.weekday() + 1) % 7

        if dt.minute not in minutes:
            return False
        if dt.hour not in hours:
            return False
        if dt.day not in days:
            return False
        if dt.month not in months:
            return False
        if cron_dow not in weekdays and (cron_dow == 0 and 7 not in weekdays):
            return False
        return True
    except Exception as e:
        cp.log(f'Error parsing cron expression: {e}')
        return False


def get_modem_diagnostics():
    """Get carrier, DBM, SINR, RSRP, and RSRQ from primary WAN device if modem."""
    try:
        primary = cp.get('status/wan/primary_device')
        if not primary:
            return None, None, None, None, None
        if not primary.startswith('mdm-'):
            return None, None, None, None, None
        device = cp.get(f'status/wan/devices/{primary}')
        if not device:
            return None, None, None, None, None
        diag = device.get('diagnostics', {})
        if not diag:
            return None, None, None, None, None
        carrier = diag.get('CARRID')
        dbm = diag.get('DBM')
        sinr = diag.get('SINR')
        rsrp = diag.get('RSRP')
        rsrq = diag.get('RSRQ')
        return carrier, dbm, sinr, rsrp, rsrq
    except Exception as e:
        cp.log(f'Error getting modem diagnostics: {e}')
        return None, None, None, None, None


def run_speedtest_ookla():
    """Run Ookla speedtest. Returns (dl_mbps, ul_mbps, latency_ms) or None."""
    try:
        from speedtest_ookla import Speedtest
        cp.log('Running Ookla speedtest...')
        s = Speedtest(timeout=90)
        s.start()
        r = s.results
        dl_mbps = r.download / 1_000_000
        ul_mbps = r.upload / 1_000_000
        latency = r.ping
        return dl_mbps, ul_mbps, latency
    except Exception as e:
        cp.log(f'Ookla speedtest error: {e}')
        return None


def run_speedtest_netperf():
    """Run netperf speedtest. Returns (dl_mbps, ul_mbps, latency_ms) or None."""
    try:
        cp.log('Running netperf speedtest...')
        result = cp.speed_test(duration=10, direction='both')
        if result:
            dl_mbps = result.get('download_bps', 0) / 1_000_000
            ul_mbps = result.get('upload_bps', 0) / 1_000_000
            return dl_mbps, ul_mbps, 0
        return None
    except Exception as e:
        cp.log(f'Netperf speedtest error: {e}')
        return None


def run_speedtest():
    """Run speedtest with Ookla if available, fallback to netperf.
    Write results to asset_id."""
    try:
        # Try Ookla first if binary present
        result = None
        engine = 'netperf'
        if has_ookla():
            result = run_speedtest_ookla()
            if result:
                engine = 'ookla'

        # Fallback to netperf
        if not result:
            if has_ookla():
                cp.log('Ookla failed, falling back to netperf...')
            result = run_speedtest_netperf()

        if not result:
            cp.log('All speedtest engines failed.')
            return

        dl_mbps, ul_mbps, latency = result
        timestamp = f'{datetime.utcnow().isoformat()}Z'

        # Build result string
        text = f'DL: {dl_mbps:.1f}Mbps, UL: {ul_mbps:.1f}Mbps'
        if latency:
            text += f', Latency: {latency:.0f}ms'

        # Add modem diagnostics if primary device is a modem
        carrier, dbm, sinr, rsrp, rsrq = get_modem_diagnostics()
        if carrier:
            text += f', Carrier: {carrier}'
        if dbm is not None:
            text += f', DBM: {dbm}'
        if sinr is not None:
            text += f', SINR: {sinr}'
        if rsrp is not None:
            text += f', RSRP: {rsrp}'
        if rsrq is not None:
            text += f', RSRQ: {rsrq}'
        text += f', {timestamp}'

        cp.log(f'Speedtest result ({engine}): {text}')
        cp.put('config/system/asset_id', text)
        cp.log('Results written to asset_id.')
    except Exception as e:
        cp.log(f'Speedtest error: {e}')


try:
    cp.log('Starting...')
    engine = 'Ookla' if has_ookla() else 'Netperf (built-in)'
    cp.log(f'Speedtest engine: {engine}')
    cp.wait_for_wan_connection()

    cron_schedule = get_cron_schedule()
    cp.log(f'Cron schedule: {cron_schedule}')

    last_run_minute = None

    while True:
        # Re-read schedule every cycle to pick up appdata changes
        cron_schedule = get_cron_schedule()

        # Manual trigger: run speedtest if asset_id is set to "start"
        asset_id = cp.get('config/system/asset_id')
        if asset_id and asset_id.lower() == 'start':
            cp.log('asset_id is "start" - running manual speedtest...')
            run_speedtest()
            time.sleep(15)
            continue

        now = datetime.utcnow()
        current_minute = (now.year, now.month, now.day, now.hour, now.minute)

        # Only run once per matching minute
        if current_minute != last_run_minute and cron_matches(cron_schedule, now):
            last_run_minute = current_minute
            run_speedtest()

        time.sleep(15)
except Exception as e:
    cp.log(f'Fatal error: {e}')
