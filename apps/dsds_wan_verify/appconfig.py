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

Most defaults are flat values in SLOT_DEFAULTS. Two are derived from the
slot's SIM number instead, by default_priority() and
default_signal_failback(), so SIM 1 outranks SIM 2 and is the slot the
app returns to without either being configured. Always use
slot_defaults(slot_key) rather than copying SLOT_DEFAULTS directly - it
also deep-copies the mutable defaults, which a shallow dict() would
share between every slot.

Ping and signal are **on** by default, because the out-of-the-box
defaults are meant to be a working DSDS failover setup rather than an
inert one: both slots ping 8.8.8.8, both carry a signal threshold, and
SIM 1 returns to service when its signal recovers. HTTP stays off, since
it has no sensible default URL. Turn a test off per slot to disable it;
a slot with no test enabled can never produce a verdict, so the app will
not move off it.

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
    'settle_seconds': 20,

    # How the ping verdict and the HTTP verdict combine.
    #   'all' - every enabled test type must pass (default). An HTTP test
    #           exists to catch what ping cannot, so its failure has to
    #           count even while ping succeeds.
    #   'any' - one passing test type is enough to call the slot healthy.
    'test_combine': 'all',

    # --- Ping test (run by the router's IP Verify subsystem) ---
    # On by default against a public resolver, so a fresh install
    # actually verifies the link instead of sitting inert. Only the
    # connected slot's test is ever armed.
    'ping_enabled': True,
    'ping_targets': ['8.8.8.8'],
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
    #   2. Destination gate - the app will not switch to this slot on
    #      signal alone unless the slot DEMONSTRATES it clears this
    #      threshold. A slot reporting none of these metrics fails the
    #      gate, because an unverifiable threshold is not a satisfied
    #      one. When neither slot clears its own threshold there is no
    #      better place to be, so `priority` decides where traffic sits -
    #      which is what stops the app bouncing between two weak slots.
    #   3. Failback gate - see signal_failback_enabled below.
    #
    # Job 2 is why leaving this set EMPTY on the secondary slot is a bad
    # idea: with no threshold there is nothing for the destination to
    # demonstrate, so a signal failure on the primary moves traffic to
    # the secondary unconditionally - even with no coverage there at all.
    #
    # The defaults are EQUAL on both slots, and that is deliberate. Both
    # slots are then held to the same "is this usable" bar, so a signal
    # failover only fires when the destination is genuinely usable. The
    # case a lower secondary bar is meant to cover - a weak area that
    # breaches both slots, where job 2 pins traffic to the primary and
    # the secondary never gets used - is already covered by the ping
    # test, which is on by default: a connectivity failure moves traffic
    # without consulting the destination's signal at all.
    #
    # Lower the secondary's bar only if ping and HTTP are both off, so
    # signal is the only test, and accept that the app may then move to a
    # measurably weaker slot - each slot is compared against its own bar,
    # never against the other slot's reading. Do not set it so low that
    # it cannot be breached: RSRP below roughly -140 dBm is past what
    # modems report, which makes the threshold equivalent to having none
    # and brings back the problem in the paragraph above.
    #
    # The values are conventional "cell edge" numbers rather than ones
    # tuned for any deployment: RSRP -100 dBm is the usual poor/very-poor
    # boundary on LTE, and RSRP_5G -120 dBm is much lower because 5G NR
    # stays usable well past where LTE RSRP would be written off. Both
    # families are set because a slot reports only the ones its current
    # radio technology uses, and a metric that is not reported is ignored
    # for job 1 rather than failed.
    'signal_enabled': True,
    'signal_thresholds': {'RSRP': -100.0, 'RSRP_5G': -120.0},
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
    #
    # The value here is only the fallback. The real default is derived
    # per slot by default_signal_failback(), which turns it on for SIM 1
    # alone - the slot that is preferred by default, and so the only one
    # the app would ever proactively return to.
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
    #
    # Overridden outright once the slot carrying traffic fails its own
    # connectivity tests. The wait is an argument about uncertainty, and
    # it only stands while the current slot still works; with both slots
    # failing, honouring it would park traffic on a link known to be
    # broken to avoid one that is merely unverified.
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


def _sim_number(slot_key):
    """SIM number from a slot key, or None if it cannot be read.

    Slot keys look like '<port>|<sim>' ('int1|sim1'), so the number comes
    off the trailing digits of the sim half.
    """
    if not isinstance(slot_key, str) or '|' not in slot_key:
        return None
    digits = ''.join(c for c in slot_key.rsplit('|', 1)[1] if c.isdigit())
    if not digits:
        return None
    try:
        return int(digits)
    except (TypeError, ValueError):
        return None


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

    Anything unparseable falls back to SLOT_DEFAULTS['priority'].
    """
    number = _sim_number(slot_key)
    if number is None:
        return SLOT_DEFAULTS['priority']
    low, high = _SLOT_BOUNDS['priority']
    return max(low, min(high, number))


def default_signal_failback(slot_key):
    """Whether signal failback is on by default for this slot.

    True for SIM 1 only. Failback is read exclusively on the slot that
    outranks its sibling, and SIM 1 is the slot default_priority() makes
    preferred, so turning it on anywhere else would be a setting with no
    effect. An unparseable key gets the flat default.
    """
    number = _sim_number(slot_key)
    if number is None:
        return SLOT_DEFAULTS['signal_failback_enabled']
    return number == 1


def slot_defaults(slot_key=None):
    """A fresh defaults dict, with the SIM-derived defaults applied.

    The list and dict defaults are copied, not referenced. A plain
    dict(SLOT_DEFAULTS) is shallow, so every slot would share one
    ping_targets list and one signal_thresholds dict - and
    slot_config() hands this straight to the monitor and the web UI for
    a slot that has never been configured.
    """
    cfg = dict(SLOT_DEFAULTS)
    cfg['ping_targets'] = list(SLOT_DEFAULTS['ping_targets'])
    cfg['signal_thresholds'] = dict(SLOT_DEFAULTS['signal_thresholds'])
    cfg['http_expect_status'] = list(SLOT_DEFAULTS['http_expect_status'])
    if slot_key is not None:
        cfg['priority'] = default_priority(slot_key)
        cfg['signal_failback_enabled'] = default_signal_failback(slot_key)
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

    `slot_key` only selects the SIM-derived defaults for a slot that has
    never had them stored; an explicit stored value always wins.
    """
    cfg = slot_defaults(slot_key)
    if not isinstance(raw, dict):
        return cfg

    for key in SLOT_DEFAULTS:
        if key not in raw:
            continue
        value = raw[key]
        if key in _SLOT_BOOL_KEYS:
            # cfg[key], not `default`: signal_failback_enabled's default
            # is derived from the SIM number, so the flat value would
            # discard that for an unparseable stored value.
            cfg[key] = _as_bool(value, cfg[key])
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
    #
    # Keyed on *presence* in `raw`, not on the cleaned set being empty.
    # The default set is non-empty, so "cfg is empty" no longer means
    # "nothing is stored" - testing that way would let the default mask
    # a legacy config and skip the migration entirely. An explicitly
    # stored empty set is also honoured, which is how clearing every
    # metric in the UI turns the threshold off.
    if 'signal_thresholds' in raw:
        cfg['signal_thresholds'] = _clean_thresholds(raw['signal_thresholds'])
    else:
        migrated = None
        for legacy in _LEGACY_THRESHOLD_KEYS:
            if legacy in raw:
                migrated = _clean_thresholds(raw[legacy])
                if migrated:
                    break
        if migrated is not None:
            cfg['signal_thresholds'] = migrated

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


def read_raw():
    """The stored appdata string, or '' when there is nothing stored.

    Separate from load() so a caller can cheaply tell whether the config
    *changed* without reparsing it. The monitor polls this so an edit
    made outside the app - the appdata entry deleted from the router UI,
    an NCM group push, a REST call - is picked up without a restart.

    Returns None on a read error, which is NOT the same as '': deleting
    the entry on the strength of a failed read, or reporting the config
    as wiped because the socket hiccuped, would both be wrong.
    """
    try:
        value = cp.get_appdata(APPDATA_FIELD)
    except Exception as e:
        cp.log('Could not read %s appdata: %s' % (APPDATA_FIELD, e))
        return None
    if value is None:
        # The field does not exist. Normal on a fresh install, and what
        # is seen after the entry is deleted from the router.
        return ''
    return value if isinstance(value, str) else ''


def load_from(raw_text):
    """Parse a stored appdata string into config, applying defaults.

    Returns {'slots': {slot_key: {...}}}. A slot missing from the result
    is not unconfigured - slot_config() falls back to slot_defaults() for
    anything not listed here.
    """
    raw = {}
    if raw_text and raw_text.strip():
        try:
            raw = json.loads(raw_text)
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


def load():
    """Read config from appdata, applying defaults for anything missing.

    Returns {'slots': {slot_key: {...}}}.
    """
    return load_from(read_raw() or '')


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
