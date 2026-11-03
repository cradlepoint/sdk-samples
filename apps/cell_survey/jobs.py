"""Scheduling, history storage, and the post-survey carrier action.

This module wraps the manual SurveyRunner (survey.py) with three extra
behaviours the web UI exposes:

  * History: every finished survey that produced cells is written as a CSV to
    tmp/history/ with a '<YYYYMMDD_HHMMSS> - <router name>.csv' filename, and an
    index (tmp/history/index.json) tracks the files so the UI can list and
    download them. This covers scheduled/startup runs, which have no browser to
    do the in-page CSV export.
  * Carrier action: after a startup or scheduled survey, the app can optionally
    act on the strongest carrier - lock its PLMN, or activate a matching
    operational eSIM profile. A manual survey never triggers an action; the
    user drives those from the results UI.
  * Schedule: "run on startup" and a cron "run on schedule", persisted in
    appdata so NCM can push them and they survive reboots.

Everything here runs on the router under cppython (Python 3.8). State is kept
on disk (relative paths only) so it survives an app restart.
"""

import json
import os
import re
import threading
import time
from datetime import datetime

import cp
import modems
import survey

# Where finished-survey CSVs and their index live. Relative path per the SDK
# rules (never /tmp). Created on demand.
_HISTORY_DIR = os.path.join('tmp', 'history')
_INDEX_PATH = os.path.join(_HISTORY_DIR, 'index.json')
# Cap stored CSVs so an app left scheduled for months doesn't fill the router.
_MAX_HISTORY = 100

# Appdata key holding the schedule/action config (JSON).
_SCHEDULE_APPDATA = 'cell_survey_schedule'

# Valid carrier-action values. 'none' never changes the modem.
_ACTIONS = ('none', 'lock', 'esim')

_io_lock = threading.Lock()
_schedule_lock = threading.Lock()

# In-memory schedule config, loaded from appdata at startup. Shape:
#   {
#     'startup_enabled': bool,
#     'startup_action': 'none'|'lock'|'esim',
#     'schedule_enabled': bool,
#     'schedule_cron': '*/30 * * * *',
#     'schedule_action': 'none'|'lock'|'esim',
#   }
_schedule = {
    'startup_enabled': False,
    'startup_action': 'none',
    'startup_port': '',       # '' = auto-select the default modem
    'schedule_enabled': False,
    'schedule_cron': '',
    'schedule_action': 'none',
    'schedule_port': '',      # '' = auto-select the default modem
}


# --- router identity --------------------------------------------------------

def router_name():
    """Return the router's system name for CSV filenames, sanitized.

    Uses config/system/system_id (the admin-set router name). Falls back to the
    product name, then 'router'. Characters not safe in a filename are replaced
    with '_' so the name slots cleanly into '<stamp> - <name>.csv'.
    """
    name = None
    try:
        name = cp.get('config/system/system_id')
    except Exception:
        name = None
    if not name:
        try:
            name = cp.get('status/product_info/product_name')
        except Exception:
            name = None
    name = str(name or 'router').strip() or 'router'
    # Keep letters, digits, space, dash, underscore, dot; collapse the rest.
    name = re.sub(r'[^A-Za-z0-9 _.\-]', '_', name)
    return name


# --- history storage --------------------------------------------------------

def _load_index():
    """Return the history index list (newest last). Empty on any error."""
    try:
        with open(_INDEX_PATH, 'r') as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except (IOError, OSError, ValueError):
        pass
    return []


def _save_index(entries):
    """Persist the history index list."""
    try:
        os.makedirs(_HISTORY_DIR, exist_ok=True)
        with open(_INDEX_PATH, 'w') as f:
            json.dump(entries, f)
    except (IOError, OSError) as e:
        cp.log('cell_survey: could not write history index: {}'.format(e))


def _safe_name(filename):
    """Reject path traversal; return a bare filename or None."""
    if not filename:
        return None
    base = os.path.basename(filename)
    if base != filename or base in ('', '.', '..'):
        return None
    if not base.lower().endswith('.csv'):
        return None
    return base


def list_history():
    """Return history entries (newest first) for the UI.

    Each entry: {filename, display_name, timestamp, trigger, cell_count,
    carrier_count, size}.
    """
    with _io_lock:
        entries = _load_index()
    out = list(reversed(entries))
    return out


def read_history_csv(filename):
    """Return (csv_text, download_name) for a stored history CSV, or None.

    Guards against path traversal and missing files.
    """
    base = _safe_name(filename)
    if not base:
        return None
    path = os.path.join(_HISTORY_DIR, base)
    try:
        with open(path, 'r') as f:
            return f.read(), base
    except (IOError, OSError):
        return None


def clear_history():
    """Delete every stored CSV and reset the index."""
    with _io_lock:
        entries = _load_index()
        for e in entries:
            base = _safe_name(e.get('filename', ''))
            if not base:
                continue
            try:
                os.remove(os.path.join(_HISTORY_DIR, base))
            except OSError:
                pass
        _save_index([])
    cp.log('cell_survey: history cleared')


def save_survey_csv(groups, trigger='manual'):
    """Write a finished survey's grouped results to a history CSV.

    Filename is '<YYYYMMDD_HHMMSS> - <router name>.csv'. Prunes to the newest
    _MAX_HISTORY files. No-op when there are no cells.

    Returns:
        str: the filename written, or None.
    """
    cells = sum(len(g.get('cells', [])) for g in (groups or []))
    if not cells:
        return None
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    name = router_name()
    filename = '{} - {}.csv'.format(stamp, name)
    csv_text = survey.groups_to_csv(groups)
    with _io_lock:
        try:
            os.makedirs(_HISTORY_DIR, exist_ok=True)
            with open(os.path.join(_HISTORY_DIR, filename), 'w') as f:
                f.write(csv_text)
        except (IOError, OSError) as e:
            cp.log('cell_survey: could not save history CSV: {}'.format(e))
            return None
        entries = _load_index()
        entries.append({
            'filename': filename,
            'display_name': filename[:-4],  # drop .csv for display
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'trigger': trigger,
            'cell_count': cells,
            'carrier_count': len([g for g in groups if g.get('plmn')]),
            'size': len(csv_text),
        })
        # Prune oldest beyond the cap.
        if len(entries) > _MAX_HISTORY:
            for old in entries[:-_MAX_HISTORY]:
                base = _safe_name(old.get('filename', ''))
                if base:
                    try:
                        os.remove(os.path.join(_HISTORY_DIR, base))
                    except OSError:
                        pass
            entries = entries[-_MAX_HISTORY:]
        _save_index(entries)
    cp.log('cell_survey: saved survey history {} ({} cells)'.format(
        filename, cells))
    return filename


# --- carrier action ---------------------------------------------------------

def _ranked_carriers(groups):
    """Carriers with a decodable PLMN, strongest signal first.

    group_by_carrier() already sorts strongest-first; this just drops the
    'Unknown' (no-PLMN) bucket, which can't be locked or matched to an eSIM.
    """
    return [g for g in (groups or []) if g.get('plmn')]


def _run_carrier_action(runner, action):
    """Act on the surveyed carriers after a scheduled/startup survey.

    action 'lock' locks the modem to the strongest carrier's PLMN. action
    'esim' activates the eUICC profile of the *highest-ranking* carrier that
    has an operational, matching profile installed - so if the strongest
    carrier has no profile, it falls through to the next strongest that does,
    rather than giving up. 'none' does nothing. All failures are logged, never
    raised.
    """
    if action not in ('lock', 'esim'):
        return
    groups = runner.snapshot().get('groups') or []
    ranked = _ranked_carriers(groups)
    if not ranked:
        cp.log('cell_survey: carrier action skipped - no carrier with a PLMN')
        return

    # Re-read the modem so config_id / eUICC data are current.
    status = modems.modem_status(runner.port) if runner.port else {}
    if status.get('error'):
        cp.log('cell_survey: carrier action skipped - {}'.format(
            status['error']))
        return

    if action == 'lock':
        best = ranked[0]
        config_id = status.get('config_id')
        res = modems.lock_plmn(config_id, best.get('plmn'))
        cp.log('cell_survey: auto-lock to {} (PLMN {}): {}'.format(
            best.get('network'), best.get('plmn'), res.get('message')))
        return

    # action == 'esim': activate the highest-ranking carrier that actually has
    # an operational eUICC profile on this modem.
    esim = status.get('esim') or {}
    if not esim.get('supported'):
        cp.log('cell_survey: auto-eSIM skipped - modem has no operational '
               'eUICC')
        return
    profiles = esim.get('profiles') or []
    for carrier in ranked:
        profile = modems.find_profile_for_carrier(
            profiles, network=carrier.get('network'))
        if not profile:
            continue
        if profile.get('active'):
            cp.log('cell_survey: auto-eSIM - best carrier with a profile ({}) '
                   'is already active'.format(carrier.get('network')))
            return
        res = modems.activate_esim_profile(
            status.get('uid'), esim.get('eid'), profile.get('iccid'))
        cp.log('cell_survey: auto-activate eSIM {} for {} (rank {} of {} '
               'carriers): {}'.format(
                   profile.get('iccid'), carrier.get('network'),
                   ranked.index(carrier) + 1, len(ranked),
                   res.get('message')))
        return
    cp.log('cell_survey: auto-eSIM skipped - no surveyed carrier has an '
           'operational eUICC profile installed')


def on_survey_complete(runner):
    """SurveyRunner completion hook: save CSV, then run the carrier action.

    Always saves the CSV to history. The carrier action only runs for a
    startup or scheduled survey (trigger != 'manual'); a manual survey leaves
    the modem alone so the user drives lock/eSIM from the UI.
    """
    snap = runner.snapshot()
    groups = snap.get('groups') or []
    trigger = snap.get('trigger') or 'manual'
    save_survey_csv(groups, trigger=trigger)
    if trigger == 'manual':
        return
    action = None
    with _schedule_lock:
        if trigger == 'startup':
            action = _schedule.get('startup_action', 'none')
        elif trigger == 'schedule':
            action = _schedule.get('schedule_action', 'none')
    _run_carrier_action(runner, action or 'none')


# --- schedule config --------------------------------------------------------

def get_schedule():
    """Return a copy of the current schedule config."""
    with _schedule_lock:
        return dict(_schedule)


def set_schedule(data):
    """Validate, store (appdata), and apply a new schedule config.

    Returns the stored config dict.
    """
    cfg = {
        'startup_enabled': bool(data.get('startup_enabled', False)),
        'startup_action': _clean_action(data.get('startup_action')),
        'startup_port': str(data.get('startup_port', '') or '').strip(),
        'schedule_enabled': bool(data.get('schedule_enabled', False)),
        'schedule_cron': str(data.get('schedule_cron', '') or '').strip(),
        'schedule_action': _clean_action(data.get('schedule_action')),
        'schedule_port': str(data.get('schedule_port', '') or '').strip(),
    }
    with _schedule_lock:
        _schedule.update(cfg)
    try:
        cp.put_appdata(_SCHEDULE_APPDATA, json.dumps(cfg))
    except Exception as e:
        cp.log('cell_survey: could not save schedule appdata: {}'.format(e))
    cp.log('cell_survey: schedule saved - startup={}/{}/{} schedule={}/{}/{} '
           'cron={}'.format(
               cfg['startup_enabled'], cfg['startup_action'],
               cfg['startup_port'] or 'auto', cfg['schedule_enabled'],
               cfg['schedule_action'], cfg['schedule_port'] or 'auto',
               cfg['schedule_cron'] or '-'))
    return cfg


def _clean_action(value):
    """Return a valid carrier action, defaulting to 'none'."""
    v = str(value or 'none')
    return v if v in _ACTIONS else 'none'


def load_schedule():
    """Load the schedule config from appdata into memory at startup."""
    try:
        raw = cp.get_appdata(_SCHEDULE_APPDATA)
        if raw:
            data = json.loads(raw)
            if isinstance(data, dict):
                with _schedule_lock:
                    _schedule.update({
                        'startup_enabled': bool(data.get('startup_enabled',
                                                          False)),
                        'startup_action': _clean_action(
                            data.get('startup_action')),
                        'startup_port': str(data.get('startup_port', '')
                                            or '').strip(),
                        'schedule_enabled': bool(data.get('schedule_enabled',
                                                          False)),
                        'schedule_cron': str(data.get('schedule_cron', '')
                                             or '').strip(),
                        'schedule_action': _clean_action(
                            data.get('schedule_action')),
                        'schedule_port': str(data.get('schedule_port', '')
                                             or '').strip(),
                    })
    except Exception as e:
        cp.log('cell_survey: could not load schedule appdata: {}'.format(e))


# --- cron matching -----------------------------------------------------------

def cron_matches(cron_expr, dt):
    """True when datetime dt matches a 5-field cron expression.

    Fields: minute hour day-of-month month day-of-week. Supports '*', lists
    (1,2,3), ranges (1-5), and step values (*/5, 0-20/4). Day-of-week uses
    cron's 0=Sunday (also accepting 7=Sunday).
    """
    try:
        fields = cron_expr.strip().split()
        if len(fields) != 5:
            return False

        def match_field(field, value):
            for part in field.split(','):
                part = part.strip()
                if part == '*':
                    return True
                if '/' in part:
                    base, step = part.split('/', 1)
                    try:
                        step = int(step)
                    except ValueError:
                        continue
                    if step <= 0:
                        continue
                    if base == '*':
                        start = 0
                    elif '-' in base:
                        start = int(base.split('-')[0])
                    else:
                        start = int(base)
                    if value >= start and (value - start) % step == 0:
                        return True
                elif '-' in part:
                    a, b = part.split('-', 1)
                    if int(a) <= value <= int(b):
                        return True
                else:
                    if int(part) == value:
                        return True
            return False

        cron_dow = (dt.weekday() + 1) % 7  # Python Mon=0 -> cron Sun=0
        dow_field = fields[4]
        dow_ok = match_field(dow_field, cron_dow) or (
            cron_dow == 0 and match_field(dow_field, 7))
        return (match_field(fields[0], dt.minute) and
                match_field(fields[1], dt.hour) and
                match_field(fields[2], dt.day) and
                match_field(fields[3], dt.month) and
                dow_ok)
    except Exception:
        return False


# --- survey triggering -------------------------------------------------------

def _start_survey(runner, trigger, port=''):
    """Start a survey via the shared SurveyRunner for a non-manual trigger.

    Selects the modem to scan on, validates it supports the AT survey and is
    connected, and starts the runner. Returns True when a survey was started.

    Args:
        runner: the shared SurveyRunner.
        trigger: 'startup' or 'schedule'.
        port: the configured modem port to use, or '' to auto-select the
            default modem. A configured port that is no longer present falls
            back to the default so a removed/renamed modem doesn't silently
            stop the schedule.
    """
    if runner.is_running():
        cp.log('cell_survey: {} survey skipped - a survey is already running'
               .format(trigger))
        return False
    modem_list = modems.list_modems()
    if not modem_list:
        cp.log('cell_survey: {} survey skipped - no modem found'.format(
            trigger))
        return False
    modem = None
    if port:
        modem = next((m for m in modem_list if m.get('port') == port), None)
        if not modem:
            cp.log('cell_survey: {} survey - configured modem {} not found, '
                   'using default'.format(trigger, port))
    if not modem:
        modem = next((m for m in modem_list if m.get('is_default')), None)
    if not modem:
        modem = modem_list[0]
    if not modem:
        cp.log('cell_survey: {} survey skipped - no modem found'.format(
            trigger))
        return False
    if not modem.get('iface'):
        cp.log('cell_survey: {} survey skipped - modem {} has no AT interface'
               .format(trigger, modem.get('port')))
        return False
    if not modems.is_supported(modem.get('mfg_model')):
        cp.log('cell_survey: {} survey skipped - modem {} does not support the '
               'AT survey'.format(trigger, modem.get('mfg_model') or 'unknown'))
        return False
    if not modem.get('connected'):
        cp.log('cell_survey: {} survey skipped - modem {} is not connected'
               .format(trigger, modem.get('port')))
        return False
    started = runner.start(modem['iface'], modem.get('uid'),
                           modem.get('mfg_model', ''), port=modem.get('port'),
                           trigger=trigger)
    if started:
        cp.log('cell_survey: {} survey started on modem {}'.format(
            trigger, modem.get('port')))
    return started


def run_startup_survey(runner):
    """Run the on-startup survey if enabled, after waiting for a WAN link.

    Called once from a daemon thread at boot. The AT survey needs a connected
    modem, so this waits for WAN connectivity first (bounded), then starts the
    survey with trigger 'startup'.
    """
    with _schedule_lock:
        enabled = _schedule.get('startup_enabled', False)
        port = _schedule.get('startup_port', '')
    if not enabled:
        return
    cp.log('cell_survey: startup survey enabled - waiting for WAN connection')
    try:
        cp.wait_for_wan_connection(timeout=180)
    except Exception:
        pass
    # Give the modem a moment to populate diagnostics after connecting.
    time.sleep(5)
    _start_survey(runner, 'startup', port=port)


def scheduler_loop(runner):
    """Daemon loop: fire a survey when the cron schedule matches.

    Checks once per ~15s and fires at most once per matching minute. A survey
    already in progress is skipped for that minute.
    """
    last_fired_minute = None
    while True:
        try:
            with _schedule_lock:
                enabled = _schedule.get('schedule_enabled', False)
                cron = _schedule.get('schedule_cron', '')
                port = _schedule.get('schedule_port', '')
            if enabled and cron:
                now = datetime.now()
                minute_key = (now.year, now.month, now.day, now.hour,
                              now.minute)
                if minute_key != last_fired_minute and cron_matches(cron, now):
                    last_fired_minute = minute_key
                    _start_survey(runner, 'schedule', port=port)
        except Exception as e:
            cp.log('cell_survey: scheduler error: {}'.format(e))
        time.sleep(15)
