"""Configuration loading, defaults, and validation.

Config lives in a single appdata field (`dsds_wan_verify`) holding JSON,
shaped as `{"slots": {"<port>|<sim>": {...}}}`. There is no global
section: everything is per SIM slot, and the handful of app-wide values
that used to be configurable are now fixed constants.

Every discovered slot is monitored. There is no per-slot opt-out,
because DSDS is only meaningful with both slots in play - a slot
excluded from failover is a slot the app can never move to, which
reduces the modem to a single SIM. Control the app's behavior by
choosing which *tests* are enabled, not which slots exist.

Defaults are applied in code and never written back to appdata, because
writing defaults would override a group config pushed from NCM.

Most defaults are flat values in SLOT_DEFAULTS. `priority` is the one
exception: it is derived from the slot's SIM number by
default_priority(), so SIM 1 outranks SIM 2 without being configured.
Use slot_defaults(slot_key) rather than copying SLOT_DEFAULTS directly.

All three tests (ping, HTTP, signal) are **off** by default. A slot with
no test enabled can never produce a verdict, so the app will not move it.

Signal used to carry three threshold sets per slot and now carries one,
`signal_thresholds`. A config written against any of the older layouts
is migrated on read - see _LEGACY_THRESHOLD_KEYS.
"""

import json

import cp

APPDATA_FIELD = 'dsds_wan_verify'

# Per-slot defaults.
SLOT_DEFAULTS = {
    # Which slot the app prefers. **Lower number = higher priority**,
    # matching the WAN profile convention (Ethernet 1, 5G/LTE 1.5,
    # 3G-only 5).
    #
    # This has to live here rather than being read from
    # `config/wan/rules2`, because both DSDS slots match the *same* WAN
    # rule and therefore share one priority value - the WAN profile
    # cannot express a preference between them.
    #
    # Priority settles two things: which slot the app returns to, and
    # which slot wins when *neither* meets its signal threshold - without
    # that tiebreak the app would bounce between two equally weak slots.
    #
    # The web UI writes 1 and 2 from a single "Preferred SIM" choice on
    # the dashboard, so the two slots can never end up equal through the
    # UI. Equal numbers set directly in appdata or by an NCM group mean
    # no preference at all: no proactive failback, and no tiebreak, since
    # the comparison is strict.
    #
    # The value here is only the fallback. The real default is derived
    # per slot from its SIM number by default_priority(), so SIM 1 is
    # preferred out of the box.
    'priority': 1,

    # Seconds to ignore this slot's test results after it becomes the
    # active slot, so it has time to finish registering and get a stable
    # route. A DSDS switch itself takes ~30s; this is the quiet period
    # *after* that.
    'settle_seconds': 45,

    # How the ping verdict and the HTTP verdict combine.
    #   'all' - every enabled test type must pass (default). An HTTP test
    #           exists to catch what ping cannot, so its failure has to
    #           count even while ping succeeds.
    #   'any' - one passing test type is enough to call the slot healthy.
    'test_combine': 'all',

    # --- Ping test (run by the router's IP Verify subsystem) ---
    'ping_enabled': False,
    'ping_targets': [],
    # 'all' = failed only when every target fails; 'any' = one is enough.
    'ping_fail_mode': 'all',
    'ping_interval': 10,
    'ping_retry_count': 2,
    'ping_retry_interval': 5,
    'ping_pkt_size': 36,
    'ping_pkt_per_try': 1,
    'ping_pkt_timeout': 10,

    # --- Signal test ---
    # ONE threshold set per slot, used for every signal decision about
    # that slot. Earlier builds split it three ways (leave / arrive /
    # prefer); the numbers only made sense in relation to each other, so
    # most of the ways to fill them in were wrong, and the failure mode
    # of a wrong answer was a modem that flapped or never moved.
    #
    # The single set reads as "the level at which this slot is no longer
    # worth using", and it does three jobs from that one meaning:
    #
    #   1. Failover - while this slot is connected, drop below it for
    #      signal_fail_threshold consecutive readings and the app moves
    #      away.
    #   2. Tiebreak - when the connected slot has breached and this one
    #      has too, neither slot is worth having, so the app does not
    #      switch on signal alone; `priority` decides where traffic sits.
    #      That is what stops it bouncing between two weak slots.
    #   3. Failback gate - see signal_failback_enabled below.
    #
    # Set the SECONDARY slot's threshold LOWER than the primary's.
    # Equal numbers mean a weak-signal area breaches both at once, and
    # rule 2 then pins traffic to the primary, so the secondary never
    # gets used. A lower bar keeps it available exactly when the primary
    # has become marginal.
    'signal_enabled': False,
    'signal_thresholds': {},
    'signal_fail_threshold': 3,

    # Proactively return to this slot once its signal comes back above
    # its own threshold, even though the slot carrying traffic is passing
    # all of its tests.
    #
    # Only consulted when this slot is a strictly higher priority than
    # the one connected, because that is the only direction "fail back"
    # describes - with two slots, that means the preferred slot.
    #
    # Possible at all only because a DSDS modem keeps reporting live
    # diagnostics for the standby slot; there is no way to ping it.
    'signal_failback_enabled': False,

    # Seconds to wait before failing back to this slot after the app left
    # it because its CONNECTIVITY tests failed. 0 disables the wait.
    #
    # Read only on a slot that outranks its sibling - with two slots, the
    # preferred one - because that is the only slot the app proactively
    # returns to. On the secondary it is ignored: leaving the secondary
    # puts traffic on the preferred slot, and nothing moves it back off
    # on its own, so there is no return to delay.
    #
    # This is the flap guard for the one case signal cannot cover: a slot
    # with excellent signal whose link is broken. Signal says "come back"
    # the instant the app leaves, the connectivity tests cannot be run on
    # a standby slot to contradict it, so without a holdoff the app
    # returns, fails connectivity again, and leaves again - roughly every
    # settle_seconds + 30s, indefinitely.
    #
    # Deliberately NOT applied when the app left on low signal or a lost
    # connection. In those cases the signal threshold is a live, readable
    # measure of whether coming back is sensible, so a timer would only
    # delay a return that is already properly gated.
    'failback_holdoff_seconds': 3600,

    # --- HTTP test (run by the app) ---
    'http_enabled': False,
    'http_url': '',
    'http_method': 'GET',
    'http_timeout': 2,
    'http_interval': 30,
    # Extra attempts after the first failure, mirroring what IP Verify
    # does for ping. The test only reports FAIL once every attempt has
    # failed, which is what makes a single failing verdict actionable
    # without a separate slot-level failure counter.
    'http_retry_count': 1,
    'http_retry_interval': 2,
    'http_expect_status': [],
    'http_verify_tls': False,
}

_SLOT_BOOL_KEYS = ('ping_enabled', 'signal_enabled',
                   'signal_failback_enabled',
                   'http_enabled', 'http_verify_tls')

# Sane bounds. Values outside these are clamped rather than rejected, so
# a bad config degrades instead of stopping the app. The ping retry
# bounds are the router's own IP Verify limits.
_SLOT_BOUNDS = {
    'priority': (1, 99),
    'settle_seconds': (0, 900),
    'ping_interval': (1, 3600),
    'ping_retry_count': (0, 5),
    'ping_retry_interval': (5, 30),
    'ping_pkt_size': (36, 1500),
    'ping_pkt_per_try': (1, 255),
    'ping_pkt_timeout': (1, 255),
    'signal_fail_threshold': (1, 100),
    # Up to 24 hours. 0 is a legal value meaning "no wait", so this is
    # clamped from 0 rather than from a minimum delay.
    'failback_holdoff_seconds': (0, 86400),
    'http_timeout': (1, 120),
    'http_interval': (5, 3600),
    'http_retry_count': (0, 10),
    'http_retry_interval': (1, 60),
}

# Threshold keys from superseded layouts, in the order to try, so an
# existing config is carried over rather than silently dropped. Earlier
# builds split the thresholds up to three ways; the failover set is tried
# first because it is the one that carries the same meaning as the single
# set that replaced it.
_LEGACY_THRESHOLD_KEYS = ('signal_failover_thresholds',
                          'signal_failover_below',
                          'signal_failback_thresholds',
                          'signal_failback_above',
                          'signal_select_thresholds',
                          'signal_min_to_select')

# Likewise for the flag that turned the signal test on.
_LEGACY_SIGNAL_ENABLED_KEYS = ('signal_failover_enabled',)


def default_priority(slot_key):
    """Default priority for a slot, derived from its SIM number.

    SIM 1 gets priority 1, SIM 2 gets 2, and so on, so the lower SIM
    number is preferred out of the box.

    A flat default would tie the two slots, and because
    _is_higher_priority() compares strictly, a tie means no slot is
    preferred: no proactive failback, and no tiebreak when both slots are
    below their thresholds. Preferring SIM 1 is both the conventional
    expectation and the only default under which failback works without
    being configured first.

    Slot keys look like '<port>|<sim>' ('int1|sim1'), so the number comes
    off the trailing digits of the sim half. Anything unparseable falls
    back to SLOT_DEFAULTS['priority'].
    """
    fallback = SLOT_DEFAULTS['priority']
    if not isinstance(slot_key, str) or '|' not in slot_key:
        return fallback
    digits = ''.join(c for c in slot_key.rsplit('|', 1)[1] if c.isdigit())
    if not digits:
        return fallback
    try:
        low, high = _SLOT_BOUNDS['priority']
        return max(low, min(high, int(digits)))
    except (TypeError, ValueError):
        return fallback


def slot_defaults(slot_key=None):
    """A fresh defaults dict, with the per-slot priority applied."""
    cfg = dict(SLOT_DEFAULTS)
    if slot_key is not None:
        cfg['priority'] = default_priority(slot_key)
    return cfg


def _clamp(value, bounds, default):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    low, high = bounds
    return max(low, min(high, value))


def _as_bool(value, default):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ('1', 'true', 'yes', 'on')
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _clean_thresholds(raw):
    """Keep only numeric threshold entries for known metric keys."""
    from dsds import METRIC_LABELS
    out = {}
    if not isinstance(raw, dict):
        return out
    for key, value in raw.items():
        if key not in METRIC_LABELS:
            continue
        if value is None or value == '':
            continue
        try:
            out[key] = float(value)
        except (TypeError, ValueError):
            continue
    return out


def _clean_slot(raw, slot_key=None):
    """Apply defaults and validation to one slot's config.

    `slot_key` only selects the default priority for a slot that has
    never had one stored; an explicit stored value always wins.
    """
    cfg = slot_defaults(slot_key)
    if not isinstance(raw, dict):
        return cfg

    for key, default in SLOT_DEFAULTS.items():
        if key not in raw:
            continue
        value = raw[key]
        if key in _SLOT_BOOL_KEYS:
            cfg[key] = _as_bool(value, default)
        elif key in _SLOT_BOUNDS:
            # Falls back to cfg[key], not `default`, so an unparseable
            # stored priority lands on this slot's own default rather
            # than the flat one.
            cfg[key] = _clamp(value, _SLOT_BOUNDS[key], cfg[key])
        else:
            cfg[key] = value

    targets = cfg.get('ping_targets')
    if isinstance(targets, str):
        targets = [t.strip() for t in targets.replace(',', '\n').split('\n')]
    if not isinstance(targets, list):
        targets = []
    # Dedupe while preserving order; IP Verify identity names are derived
    # from the target, so a duplicate would collide.
    seen = set()
    clean_targets = []
    for target in targets:
        target = str(target).strip()
        if target and target not in seen:
            seen.add(target)
            clean_targets.append(target)
    cfg['ping_targets'] = clean_targets[:8]

    cfg['http_method'] = 'HEAD' \
        if str(cfg.get('http_method')).upper() == 'HEAD' else 'GET'
    cfg['http_url'] = str(cfg.get('http_url') or '').strip()

    codes = cfg.get('http_expect_status')
    if isinstance(codes, str):
        codes = [c.strip() for c in codes.replace(' ', ',').split(',')]
    clean_codes = []
    if isinstance(codes, list):
        for code in codes:
            try:
                code = int(code)
            except (TypeError, ValueError):
                continue
            if 100 <= code <= 599:
                clean_codes.append(code)
    cfg['http_expect_status'] = clean_codes

    cfg['ping_fail_mode'] = 'any' \
        if str(cfg.get('ping_fail_mode')) == 'any' else 'all'
    cfg['test_combine'] = 'any' \
        if str(cfg.get('test_combine')) == 'any' else 'all'

    # One threshold set now, carried over from whichever of the older
    # split fields a stored config happens to use.
    thresholds = _clean_thresholds(cfg.get('signal_thresholds'))
    if not thresholds:
        for legacy in _LEGACY_THRESHOLD_KEYS:
            thresholds = _clean_thresholds(raw.get(legacy))
            if thresholds:
                break
    cfg['signal_thresholds'] = thresholds

    # The enable flag is only migrated when the new one is absent
    # entirely, so an explicit `false` from a current client is not
    # overridden by a stale `true`.
    if 'signal_enabled' not in raw:
        for legacy in _LEGACY_SIGNAL_ENABLED_KEYS:
            if legacy in raw:
                cfg['signal_enabled'] = _as_bool(
                    raw[legacy], cfg['signal_enabled'])
                break

    return cfg


def load():
    """Read config from appdata, applying defaults for anything missing.

    Returns {'slots': {slot_key: {...}}}.
    """
    raw = {}
    try:
        value = cp.get_appdata(APPDATA_FIELD)
        if value and isinstance(value, str) and value.strip():
            raw = json.loads(value)
    except Exception as e:
        cp.log('Could not parse %s appdata, using defaults: %s'
               % (APPDATA_FIELD, e))
        raw = {}
    if not isinstance(raw, dict):
        raw = {}

    slots = {}
    raw_slots = raw.get('slots') if isinstance(raw.get('slots'), dict) else {}
    for key, value in raw_slots.items():
        slots[key] = _clean_slot(value, key)

    return {'slots': slots}


def save(conf):
    """Persist config to appdata, merging over what is already stored.

    Incoming slot fields are layered on top of the stored values rather
    than replacing the whole slot. Without that, a client written against
    an older field set - a browser tab left open across an app upgrade,
    or a script posting a partial slot - silently blanks every field it
    does not know about, because the slot would otherwise be rebuilt from
    defaults.

    Returns True on success.
    """
    try:
        stored = load().get('slots') or {}
        slots = {}
        for key, incoming in (conf.get('slots') or {}).items():
            merged = dict(stored.get(key) or slot_defaults(key))
            if isinstance(incoming, dict):
                merged.update(incoming)
            slots[key] = _clean_slot(merged, key)
        # Keep slots the caller did not mention at all.
        for key, value in stored.items():
            slots.setdefault(key, value)
        cp.put_appdata(APPDATA_FIELD, json.dumps({'slots': slots}))
        return True
    except Exception as e:
        cp.log('Error saving config: %s' % e)
        return False


def slot_config(conf, slot_key):
    """Config for one slot, defaults applied even if never configured."""
    return conf.get('slots', {}).get(slot_key) or slot_defaults(slot_key)
