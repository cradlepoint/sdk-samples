"""
speedtest_scheduled_asset_id - Runs Ookla speedtest on a configurable cron schedule
and writes results to the router's asset_id field.

Results format: ISO timestamp followed by speedtest results and modem diagnostics.
Example: "DL: 26.8Mbps, UL: 12.5Mbps, Latency: 56ms, Carrier: Verizon, DBM: -74, SINR: 5.6, RSRP: -95, RSRQ: -11, 2024-03-15T14:30:00Z"

Modem diagnostics (Carrier, DBM, SINR, RSRP, RSRQ) are included only if the primary WAN device is a modem.

Appdata fields:
- cron_schedule: Cron expression (minute hour day month weekday). Default: "0 2 * * 1" (Monday at 2:00 AM UTC)
"""

import cp
import time
from datetime import datetime
from speedtest_ookla import Speedtest

DEFAULT_CRON = '0 2 * * 1'  # Monday at 2:00 AM UTC


def get_cron_schedule():
    """Read cron schedule from appdata, use default if not configured."""
    value = cp.get_appdata('cron_schedule')
    if value:
        return value
    return DEFAULT_CRON


def parse_cron_field(field, min_val, max_val):
    """Parse a single cron field and return set of matching values.

    Supports: *, */N, N, N-M, N-M/S, and comma-separated combinations.
    """
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
    """Check if a datetime matches a cron expression.

    Cron format: minute hour day_of_month month day_of_week
    day_of_week: 0=Sunday, 1=Monday, ..., 6=Saturday (or 7=Sunday)
    """
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
    """Get carrier, DBM, SINR, RSRP, and RSRQ from primary WAN device if it is a modem.

    Returns tuple (carrier, dbm, sinr, rsrp, rsrq) or (None, None, None, None, None) if not a modem.
    """
    try:
        primary = cp.get('status/wan/primary_device')
        if not primary:
            return None, None, None, None, None

        # Check if primary device is a modem (starts with 'mdm-')
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


def run_speedtest():
    """Run an Ookla speedtest and write results to asset_id."""
    try:
        cp.log('Starting scheduled speedtest...')
        s = Speedtest(timeout=90)
        s.start()
        r = s.results

        dl_mbps = r.download / 1_000_000
        ul_mbps = r.upload / 1_000_000
        latency = r.ping

        timestamp = f'{datetime.utcnow().isoformat()}Z'

        # Build result string
        result = f'DL: {dl_mbps:.1f}Mbps, UL: {ul_mbps:.1f}Mbps, Latency: {latency:.0f}ms'

        # Add modem diagnostics if primary device is a modem
        carrier, dbm, sinr, rsrp, rsrq = get_modem_diagnostics()
        if carrier:
            result += f', Carrier: {carrier}'
        if dbm is not None:
            result += f', DBM: {dbm}'
        if sinr is not None:
            result += f', SINR: {sinr}'
        if rsrp is not None:
            result += f', RSRP: {rsrp}'
        if rsrq is not None:
            result += f', RSRQ: {rsrq}'
        result += f', {timestamp}'

        cp.log(f'Speedtest result: {result}')
        cp.put('config/system/asset_id', result)
        cp.log('Results written to asset_id.')
    except Exception as e:
        cp.log(f'Speedtest error: {e}')


try:
    cp.log('Starting...')
    cp.wait_for_wan_connection()

    cron_schedule = get_cron_schedule()
    cp.log(f'Cron schedule: {cron_schedule}')

    last_run_minute = None

    while True:
        now = datetime.utcnow()
        current_minute = (now.year, now.month, now.day, now.hour, now.minute)

        # Only run once per matching minute
        if current_minute != last_run_minute and cron_matches(cron_schedule, now):
            last_run_minute = current_minute
            run_speedtest()
            # Re-read schedule in case it changed
            cron_schedule = get_cron_schedule()

        time.sleep(15)
except Exception as e:
    cp.log(f'Fatal error: {e}')
