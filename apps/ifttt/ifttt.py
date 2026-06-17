"""IFTTT - If This Then That Rule Engine for NCOS Router.

Web dashboard on port 8000 with drag-and-drop interface for creating
simple if/then rules that interact with the router config tree via cp.py.
Each rule is stored as its own appdata entry and evaluated on its own interval.
"""

import cp
import datetime
import json
import math
import os
import socket
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from threading import Thread
from urllib.parse import urlparse, parse_qs

APP_NAME = 'ifttt'
RULE_PREFIX = 'ifttt_rule_'
DEFAULT_INTERVAL = 10
PORT = 8000
APP_DIR = os.path.dirname(__file__) or '.'
UPTIME_WAIT_SECONDS = 120

# --- Per-rule appdata storage (no index, discovery by prefix scan) ---

def _rule_key(rule_id):
    """Appdata key for a single rule."""
    return RULE_PREFIX + rule_id


def load_rule(rule_id):
    """Load a single rule from appdata."""
    try:
        val = cp.get_appdata(_rule_key(rule_id))
        if val:
            return json.loads(val)
    except Exception as e:
        cp.log('Error loading rule %s: %s' % (rule_id, e))
    return None


def save_rule(rule):
    """Save a single rule to appdata."""
    try:
        cp.put_appdata(_rule_key(rule['id']), json.dumps(rule))
    except Exception as e:
        cp.log('Error saving rule %s: %s' % (rule.get('id', '?'), e))


def delete_rule(rule_id):
    """Delete a single rule from appdata."""
    try:
        cp.delete_appdata(_rule_key(rule_id))
    except Exception as e:
        cp.log('Error deleting rule %s: %s' % (rule_id, e))


def load_all_rules():
    """Load all rules by scanning appdata for entries with the rule prefix."""
    rules = []
    try:
        all_data = cp.get_appdata()
        if all_data and isinstance(all_data, list):
            for item in all_data:
                name = item.get('name', '')
                if name.startswith(RULE_PREFIX):
                    try:
                        rule = json.loads(item.get('value', '{}'))
                        if rule and rule.get('id'):
                            rules.append(rule)
                    except (json.JSONDecodeError, ValueError):
                        cp.log('Skipping malformed rule entry: %s' % name)
    except Exception as e:
        cp.log('Error scanning appdata for rules: %s' % e)
    return rules


def save_all_rules(rules):
    """Save all rules individually."""
    for rule in rules:
        rid = rule.get('id', '')
        if rid:
            save_rule(rule)


# --- Rule evaluation ---

# --- Time condition tracking: {(rule_id, cond_index): {fired, date, count, last_fire}} ---
_time_fire_state = {}
_when_fire_state = {}

# Day name mappings for WHEN conditions
_DAY_MAP = {
    'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6
}
_UNIT_SECONDS = {
    'seconds': 1, 'minutes': 60, 'hours': 3600,
    'days': 86400, 'weeks': 604800, 'months': 2592000
}


def evaluate_time_condition(condition, rule_id='', cond_index=0):
    """Evaluate a time-based WHEN condition.

    Supports three repeat modes:
    - once: fire once at the scheduled time, suppress until next day/match
    - every: fire at interval after initial time match (with optional FOR duration limit)
    - times: fire X times then suppress until next day/match
    Returns True/False.
    """
    now = datetime.datetime.now()
    day_cfg = condition.get('day', 'any')
    time_cfg = condition.get('time', '00:00')
    repeat_mode = condition.get('repeat_mode', 'once')

    # Check day of week
    today = now.weekday()  # 0=Monday, 6=Sunday
    if day_cfg == 'weekday' and today > 4:
        return False
    if day_cfg == 'weekend' and today < 5:
        return False
    if day_cfg in _DAY_MAP and today != _DAY_MAP[day_cfg]:
        return False

    # Parse configured time
    try:
        parts = time_cfg.split(':')
        cfg_hour = int(parts[0])
        cfg_min = int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        cfg_hour, cfg_min = 0, 0

    cfg_time = datetime.datetime(now.year, now.month, now.day, cfg_hour, cfg_min)
    diff = (now - cfg_time).total_seconds()

    # Not yet reached the scheduled time
    if diff < 0:
        _when_fire_state.pop((rule_id, cond_index), None)
        return False

    key = (rule_id, cond_index)
    state = _when_fire_state.get(key, {})

    # Check if state is from a previous day and reset
    today_str = now.strftime('%Y-%m-%d')
    if state.get('date', '') != today_str:
        state = {}
        _when_fire_state.pop(key, None)

    if repeat_mode == 'once':
        if state.get('fired'):
            return False
        if diff < 60:
            _when_fire_state[key] = {'fired': True, 'date': today_str, 'count': 1, 'last_fire': time.time()}
            return True
        return False

    elif repeat_mode == 'every':
        repeat_value = int(condition.get('repeat_value', 1))
        repeat_unit = condition.get('repeat_unit', 'hours')
        interval_secs = repeat_value * _UNIT_SECONDS.get(repeat_unit, 3600)

        # FOR duration limit (0 = unlimited)
        for_value = int(condition.get('for_value', 0))
        for_unit = condition.get('for_unit', 'hours')
        for_secs = for_value * _UNIT_SECONDS.get(for_unit, 3600) if for_value > 0 else 0

        last_fire = state.get('last_fire', 0)
        since_last = time.time() - last_fire if last_fire else interval_secs + 1

        # First fire: must be within 60s of scheduled time
        if not state.get('fired'):
            if diff < 60:
                _when_fire_state[key] = {'fired': True, 'date': today_str, 'count': 1,
                                         'last_fire': time.time(), 'first_fire': time.time()}
                return True
            return False

        # Check FOR duration limit
        if for_secs > 0:
            first_fire = state.get('first_fire', state.get('last_fire', time.time()))
            if time.time() - first_fire >= for_secs:
                return False

        if since_last >= interval_secs:
            state['count'] = state.get('count', 0) + 1
            state['last_fire'] = time.time()
            if 'first_fire' not in state:
                state['first_fire'] = time.time()
            _when_fire_state[key] = state
            return True

        return False

    elif repeat_mode == 'times':
        max_times = int(condition.get('repeat_times', 1))
        fired_count = state.get('count', 0)

        if fired_count >= max_times:
            return False

        last_fire = state.get('last_fire', 0)
        # First fire: check 60s window
        if not state.get('fired'):
            if diff < 60:
                _when_fire_state[key] = {'fired': True, 'date': today_str, 'count': 1, 'last_fire': time.time()}
                return True
            return False

        # Subsequent fires — minimum 2s gap to avoid multi-fire in same poll
        since_last = time.time() - last_fire if last_fire else 999
        if since_last >= 2:
            state['count'] = fired_count + 1
            state['last_fire'] = time.time()
            _when_fire_state[key] = state
            return True

        return False

    return False


def _day_matches(day_cfg, weekday):
    """Check if a day config matches the given weekday (0=Mon, 6=Sun)."""
    if day_cfg == 'any':
        return True
    if day_cfg == 'weekday':
        return weekday <= 4
    if day_cfg == 'weekend':
        return weekday >= 5
    return _DAY_MAP.get(day_cfg, -1) == weekday


def evaluate_time_window(condition):
    """Evaluate a WHILE time window condition.

    Returns True if the current day/time falls within the start-end window.
    """
    now = datetime.datetime.now()
    today = now.weekday()

    start_day = condition.get('start_day', 'any')
    end_day = condition.get('end_day', 'any')
    start_time = condition.get('start_time', '09:00')
    end_time = condition.get('end_time', '17:00')

    try:
        sp = start_time.split(':')
        start_h, start_m = int(sp[0]), int(sp[1]) if len(sp) > 1 else 0
    except (ValueError, IndexError):
        start_h, start_m = 0, 0

    try:
        ep = end_time.split(':')
        end_h, end_m = int(ep[0]), int(ep[1]) if len(ep) > 1 else 0
    except (ValueError, IndexError):
        end_h, end_m = 23, 59

    # Check day constraints
    start_day_ok = _day_matches(start_day, today)
    end_day_ok = _day_matches(end_day, today)

    if not start_day_ok and not end_day_ok:
        return False

    now_minutes = now.hour * 60 + now.minute
    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m

    # Same day window
    if start_day == end_day or (start_day == 'any' and end_day == 'any'):
        if start_minutes <= end_minutes:
            return start_minutes <= now_minutes <= end_minutes
        else:
            # Wraps midnight
            return now_minutes >= start_minutes or now_minutes <= end_minutes

    # Different day configs — check if we're in the start day after start time,
    # or in the end day before end time
    if start_day_ok and now_minutes >= start_minutes:
        return True
    if end_day_ok and now_minutes <= end_minutes:
        return True

    return False


def dms_to_decimal(dms_str):
    """Convert DMS (degree, minute, second) GPS string or object to decimal degrees.

    Handles formats like:
    - {'degree': 43, 'minute': 9, 'second': 36.86} (DMS object from GPS fix)
    - '38 53.6440N' (degrees decimal-minutes)
    - '38 53 38.64 N' (degrees minutes seconds)
    - '38.894' (already decimal)
    - '-77.0365' (already decimal with sign)
    """
    if not dms_str:
        return None

    # Handle DMS object: {"degree": 43, "minute": 9, "second": 36.86}
    if isinstance(dms_str, dict):
        try:
            deg = float(dms_str.get('degree', 0))
            mins = float(dms_str.get('minute', 0))
            secs = float(dms_str.get('second', 0))
            sign = -1 if deg < 0 else 1
            return (abs(deg) + mins / 60.0 + secs / 3600.0) * sign
        except (ValueError, TypeError):
            return None

    dms_str = str(dms_str).strip()

    # Already a plain decimal number
    try:
        val = float(dms_str)
        return val
    except ValueError:
        pass

    # Determine sign from direction letter
    direction = 1
    for ch in 'SsWw':
        if ch in dms_str:
            direction = -1
    # Strip direction letters
    cleaned = dms_str.strip('NSEWnsew ').strip()

    parts = cleaned.split()
    try:
        if len(parts) == 1:
            # Could be "38d53'38.64\"N" or degrees with decimal minutes like "3853.6440"
            return float(parts[0]) * direction
        elif len(parts) == 2:
            # Degrees + decimal minutes: "38 53.6440"
            deg = float(parts[0])
            mins = float(parts[1])
            return (deg + mins / 60.0) * direction
        elif len(parts) >= 3:
            # Degrees + minutes + seconds: "38 53 38.64"
            deg = float(parts[0])
            mins = float(parts[1])
            secs = float(parts[2])
            return (deg + mins / 60.0 + secs / 3600.0) * direction
    except (ValueError, TypeError):
        pass
    return None


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two lat/lon points in kilometers using haversine."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def evaluate_location_condition(condition):
    """Evaluate a WHERE (GPS location) condition.

    Reads device GPS from status/gps/fix, converts DMS to decimal,
    calculates distance to target, and checks within/not_within radius.
    """
    target_lat = condition.get('lat', '')
    target_lon = condition.get('lon', '')
    radius = float(condition.get('radius', 1))
    radius_unit = condition.get('radius_unit', 'km')
    operator = condition.get('operator', 'within')

    # Parse target coordinates
    t_lat = dms_to_decimal(target_lat)
    t_lon = dms_to_decimal(target_lon)
    if t_lat is None or t_lon is None:
        cp.log('WHERE condition: invalid target coordinates')
        return False

    # Read device GPS
    try:
        gps_fix = cp.get('status/gps/fix')
    except Exception as e:
        cp.log('WHERE condition: error reading GPS: %s' % e)
        return False

    if not gps_fix or not isinstance(gps_fix, dict):
        cp.log('WHERE condition: no GPS fix available')
        return False

    # Extract lat/lon from GPS fix
    dev_lat_raw = gps_fix.get('latitude') or gps_fix.get('lat', '')
    dev_lon_raw = gps_fix.get('longitude') or gps_fix.get('lon', '')

    dev_lat = dms_to_decimal(dev_lat_raw)
    dev_lon = dms_to_decimal(dev_lon_raw)
    if dev_lat is None or dev_lon is None:
        cp.log('WHERE condition: could not parse device GPS coordinates')
        return False

    # Calculate distance
    dist_km = haversine_distance(dev_lat, dev_lon, t_lat, t_lon)

    # Convert radius to km if needed
    radius_km = radius
    if radius_unit == 'mi':
        radius_km = radius * 1.60934

    if operator == 'within':
        return dist_km <= radius_km
    elif operator == 'not_within':
        return dist_km > radius_km

    return False


def evaluate_condition(condition, rule_id='', cond_index=0):
    """Evaluate a single condition against the router config/status tree.

    Supports two condition types:
    - 'if' (default): path-based condition checking router config tree
    - 'when': time-based condition checking day/time and repeat interval

    Returns True/False.
    """
    cond_type = condition.get('condType', 'if')

    if cond_type == 'when':
        return evaluate_time_condition(condition, rule_id, cond_index)

    if cond_type == 'while_time':
        return evaluate_time_window(condition)

    if cond_type == 'where':
        return evaluate_location_condition(condition)

    path = condition.get('path', '')
    operator = condition.get('operator', 'equals')
    expected = condition.get('value', '')

    try:
        actual = cp.get(path)
    except Exception as e:
        cp.log('Error reading path %s: %s' % (path, e))
        return False

    if operator == 'exists':
        return actual is not None
    if operator == 'not_exists':
        return actual is None
    if actual is None:
        return False

    actual_str = str(actual)
    expected_str = str(expected)

    if operator == 'equals':
        return actual_str == expected_str
    elif operator == 'not_equals':
        return actual_str != expected_str
    elif operator == 'contains':
        return expected_str in actual_str
    elif operator == 'not_contains':
        return expected_str not in actual_str
    elif operator == 'greater_than':
        try:
            return float(actual_str) > float(expected_str)
        except (ValueError, TypeError):
            return False
    elif operator == 'less_than':
        try:
            return float(actual_str) < float(expected_str)
        except (ValueError, TypeError):
            return False
    elif operator == 'greater_equal':
        try:
            return float(actual_str) >= float(expected_str)
        except (ValueError, TypeError):
            return False
    elif operator == 'less_equal':
        try:
            return float(actual_str) <= float(expected_str)
        except (ValueError, TypeError):
            return False
    return False


def execute_action(action):
    """Execute a single action on the router config tree."""
    action_type = action.get('type', 'log')
    value = action.get('value', '')

    try:
        if action_type == 'set':
            path = action.get('path', '')
            if path:
                cp.put(path, value)
                cp.log('IFTTT action: SET %s = %s' % (path, value))
        elif action_type == 'alert':
            cp.alert(value)
            cp.log('IFTTT action: ALERT %s' % value)
        elif action_type == 'log':
            cp.log('IFTTT action: LOG %s' % value)
    except Exception as e:
        cp.log('Error executing action %s: %s' % (action_type, e))


def evaluate_single_rule(rule):
    """Evaluate one rule and execute its actions if conditions match.

    Supports per-condition sustain modes:
    - none: fire immediately when condition is true
    - duration: condition must stay true for N seconds (checked every 1s)
    - intervals: condition must be true for N consecutive polling intervals
    """
    if not rule.get('enabled', True):
        return
    conditions = rule.get('conditions', [])
    actions = rule.get('actions', [])
    logic = rule.get('logic', 'all')

    if not conditions or not actions:
        return

    rule_id = rule.get('id', '')
    results = [evaluate_condition(c, rule_id, i) for i, c in enumerate(conditions)]

    # Check sustain requirements for each condition
    sustained = []
    for i, cond in enumerate(conditions):
        sustain = cond.get('sustain', 'none')
        if not results[i]:
            # Condition failed, reset its sustain counter
            _sustain_state.pop((rule_id, i), None)
            sustained.append(False)
            continue

        if sustain == 'none':
            sustained.append(True)
        elif sustain == 'duration':
            duration_val = int(cond.get('sustain_value', 5))
            duration_unit = cond.get('sustain_unit', 'seconds')
            unit_multiplier = {'seconds': 1, 'minutes': 60, 'hours': 3600}
            duration = duration_val * unit_multiplier.get(duration_unit, 1)
            key = (rule_id, i)
            if key not in _sustain_state:
                # First time true, start tracking
                _sustain_state[key] = {'start': time.time(), 'count': 0}
                sustained.append(False)
            else:
                elapsed = time.time() - _sustain_state[key]['start']
                if elapsed >= duration:
                    sustained.append(True)
                    _sustain_state.pop(key, None)
                else:
                    sustained.append(False)
        elif sustain == 'intervals':
            count_needed = int(cond.get('sustain_value', 3))
            key = (rule_id, i)
            if key not in _sustain_state:
                _sustain_state[key] = {'start': 0, 'count': 1}
            else:
                _sustain_state[key]['count'] += 1
            if _sustain_state[key]['count'] >= count_needed:
                sustained.append(True)
                _sustain_state.pop(key, None)
            else:
                sustained.append(False)
        else:
            sustained.append(True)

    matched = all(sustained) if logic == 'all' else any(sustained)

    if matched:
        cp.log('IFTTT rule matched: %s' % rule.get('name', 'Unnamed'))
        for action in actions:
            execute_action(action)


# --- HTTP Request Handler ---

class IFTTTHandler(SimpleHTTPRequestHandler):
    """Handle API routes and serve static files from the app directory."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=APP_DIR, **kwargs)

    def log_message(self, format, *args):
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(length) if length else b''

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/':
            self.path = '/index.html'
            return super().do_GET()

        if path == '/api/rules':
            return self._send_json(load_all_rules())

        if path == '/api/browse':
            params = parse_qs(parsed.query)
            browse_path = params.get('path', ['status'])[0]
            try:
                result = cp.get(browse_path)
                return self._send_json({'path': browse_path, 'data': result})
            except Exception as e:
                return self._send_json({'path': browse_path, 'error': str(e)})

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/rules':
            try:
                rules = json.loads(self._read_body())
                save_all_rules(rules)
                return self._send_json({'success': True})
            except Exception as e:
                cp.log('Error saving rules: %s' % e)
                return self._send_json({'success': False, 'error': str(e)})

        if path == '/api/test':
            try:
                condition = json.loads(self._read_body())
                cond_type = condition.get('condType', 'if')
                result = evaluate_condition(condition)
                actual_value = None

                if cond_type in ('if', 'while'):
                    cond_path = condition.get('path', '')
                    if cond_path:
                        raw = cp.get(cond_path)
                        actual_value = str(raw) if raw is not None else None
                elif cond_type == 'when':
                    now = datetime.datetime.now()
                    actual_value = now.strftime('%A %H:%M:%S')
                elif cond_type == 'while_time':
                    now = datetime.datetime.now()
                    actual_value = now.strftime('%A %H:%M')
                elif cond_type == 'where':
                    try:
                        gps = cp.get('status/gps/fix')
                        if gps and isinstance(gps, dict):
                            lat_raw = gps.get('latitude') or gps.get('lat', '')
                            lon_raw = gps.get('longitude') or gps.get('lon', '')
                            lat = dms_to_decimal(lat_raw)
                            lon = dms_to_decimal(lon_raw)
                            if lat is not None and lon is not None:
                                t_lat = dms_to_decimal(condition.get('lat', ''))
                                t_lon = dms_to_decimal(condition.get('lon', ''))
                                if t_lat is not None and t_lon is not None:
                                    dist = haversine_distance(lat, lon, t_lat, t_lon)
                                    unit = condition.get('radius_unit', 'km')
                                    if unit == 'mi':
                                        dist_display = '%.2f mi' % (dist / 1.60934)
                                    else:
                                        dist_display = '%.2f km' % dist
                                    actual_value = '%.6f, %.6f (%s away)' % (lat, lon, dist_display)
                                else:
                                    actual_value = '%.6f, %.6f' % (lat, lon)
                            else:
                                actual_value = 'GPS parse error'
                        else:
                            actual_value = 'No GPS fix'
                    except Exception:
                        actual_value = 'GPS read error'

                return self._send_json({
                    'result': result,
                    'actual_value': actual_value
                })
            except Exception as e:
                return self._send_json({'result': False, 'error': str(e)})

        self.send_error(404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # DELETE /api/rules/<rule_id>
        if path.startswith('/api/rules/'):
            rule_id = path[len('/api/rules/'):]
            try:
                delete_rule(rule_id)
                return self._send_json({'success': True})
            except Exception as e:
                return self._send_json({'success': False, 'error': str(e)})

        self.send_error(404)


# --- Per-rule evaluation: interval threads and callback registrations ---

# Track active polling threads: {rule_id: Thread}
_active_threads = {}
# Track callback registrations: {rule_id: [eid, eid, ...]}
_active_callbacks = {}
# Track sustain state: {(rule_id, condition_index): {'start': timestamp, 'count': int}}
_sustain_state = {}


def _on_path_change(path, value, args):
    """Callback fired by cp.on when a watched path changes.

    args is a tuple containing (rule_id,).
    Re-loads the rule from appdata and evaluates it.
    """
    rule_id = args[0] if args else None
    if not rule_id:
        return
    try:
        rule = load_rule(rule_id)
        if rule:
            cp.log('Callback triggered for rule %s on path %s' % (
                rule.get('name', rule_id), path))
            evaluate_single_rule(rule)
    except Exception as e:
        cp.log('Callback error for rule %s: %s' % (rule_id, e))


def register_callbacks(rule):
    """Register cp.on callbacks for all condition paths in a rule."""
    rule_id = rule['id']
    eids = []
    for cond in rule.get('conditions', []):
        cond_path = cond.get('path', '')
        if not cond_path:
            continue
        try:
            result = cp.register('set', cond_path, _on_path_change, rule_id)
            if result:
                eids.append(result)
                cp.log('Registered callback on %s for rule %s' % (cond_path, rule_id))
        except Exception as e:
            cp.log('Error registering callback on %s: %s' % (cond_path, e))
    return eids


def unregister_callbacks(rule_id):
    """Unregister all cp.on callbacks for a rule."""
    eids = _active_callbacks.pop(rule_id, [])
    for eid in eids:
        try:
            cp.unregister(eid)
        except Exception as e:
            cp.log('Error unregistering eid %s: %s' % (eid, e))
    if eids:
        cp.log('Unregistered %d callbacks for rule %s' % (len(eids), rule_id))


def rule_thread(rule_id):
    """Background thread that evaluates a single rule on its own interval.

    If any condition uses duration sustain, the thread checks every 1 second
    while sustain is being tracked, otherwise uses the configured interval.
    """
    while True:
        try:
            rule = load_rule(rule_id)
            if not rule:
                cp.log('Rule %s no longer exists, stopping thread' % rule_id)
                return
            interval = rule.get('interval', DEFAULT_INTERVAL)
            interval_unit = rule.get('interval_unit', 'seconds')
            unit_mult = {'seconds': 1, 'minutes': 60, 'hours': 3600}
            interval_secs = interval * unit_mult.get(interval_unit, 1)
            evaluate_single_rule(rule)
            # Check if any sustain timers are active for this rule
            has_active_sustain = any(
                k[0] == rule_id for k in _sustain_state
            )
            time.sleep(1 if has_active_sustain else interval_secs)
        except Exception as e:
            cp.log('Rule engine error for %s: %s' % (rule_id, e))
            time.sleep(DEFAULT_INTERVAL)


def sync_rules():
    """Sync interval threads and callback registrations to match saved rules."""
    all_rules = load_all_rules()
    current_ids = set()
    for rule in all_rules:
        rid = rule.get('id', '')
        if not rid or not rule.get('enabled', True):
            continue
        current_ids.add(rid)
        trigger = rule.get('trigger', 'interval')

        if trigger == 'callback':
            # Should be using callbacks, not a thread
            if rid in _active_threads:
                del _active_threads[rid]
            if rid not in _active_callbacks:
                eids = register_callbacks(rule)
                _active_callbacks[rid] = eids
        else:
            # Should be using interval thread, not callbacks
            if rid in _active_callbacks:
                unregister_callbacks(rid)
            if rid not in _active_threads:
                t = Thread(target=rule_thread, args=(rid,), daemon=True)
                t.start()
                _active_threads[rid] = t
                cp.log('Started interval thread for rule %s' % rid)

    running_thread_ids = set(_active_threads.keys())
    running_cb_ids = set(_active_callbacks.keys())

    # Clean up removed or disabled rules
    for rid in running_thread_ids - current_ids:
        del _active_threads[rid]
        cp.log('Removed thread for rule %s' % rid)

    for rid in running_cb_ids - current_ids:
        unregister_callbacks(rid)


# --- Main ---

if __name__ == '__main__':
    cp.log('Starting IFTTT Rule Engine...')

    # Wait for system readiness
    cp.log('Waiting for system uptime (%ds)...' % UPTIME_WAIT_SECONDS)
    cp.wait_for_uptime(UPTIME_WAIT_SECONDS)
    cp.log('System ready.')

    server = HTTPServer(('0.0.0.0', PORT), IFTTTHandler)
    server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    cp.log('Web dashboard running on port %d' % PORT)

    Thread(target=server.serve_forever, daemon=True).start()

    # Auto-start enabled rules on startup
    cp.log('Loading saved rules...')
    try:
        sync_rules()
        cp.log('Rules synced: %d threads, %d callbacks' % (
            len(_active_threads), len(_active_callbacks)))
    except Exception as e:
        cp.log('Initial rule sync error: %s' % e)

    # Main loop: periodically re-sync rule evaluation threads and callbacks
    while True:
        try:
            sync_rules()
        except Exception as e:
            cp.log('Rule sync error: %s' % e)
        time.sleep(5)
