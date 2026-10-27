"""DSDS slot discovery, signal metrics, and SIM switch control.

A Dual SIM Dual Standby (DSDS) modem presents each SIM slot as its own
`mdm-*` WAN device, but only one slot is connected at a time. Both slots
share the same `info/port` (e.g. `int1`) and the same WAN rule
(`info/config_id`), so the port alone cannot tell them apart.

Slots are identified by port + sim (+ carrier for display), never by UID
or device id, because those are opaque. UIDs are resolved from the
port/sim pair at runtime only where the router API demands one.

Verified on an R2400-5GF-NA (NCOS 7.26.81) with a T-Mobile SIM in slot 1
and a Verizon SIM in slot 2. See readme.md for the full field reference.
"""

import time

import cp

# Signal metrics this app understands, in the order they should be shown.
# Every one of these is "higher is better" (values are negative dBm/dB for
# the power/quality metrics, so -80 is better than -100).
#
# Which keys are actually present depends on the radio technology the slot
# is using right now, not on the modem's capabilities:
#   5G SA  -> RSRP_5G / RSRQ_5G / SINR_5G only (no DBM/RSRP/RSRQ/SINR)
#   LTE    -> DBM / RSRP / RSRQ / SINR only (no *_5G)
# so the set has to be detected per slot on every poll.
SIGNAL_METRICS = (
    ('DBM', 'RSSI', 'dBm'),
    ('RSRP', 'RSRP', 'dBm'),
    ('RSRQ', 'RSRQ', 'dB'),
    ('SINR', 'SINR', 'dB'),
    ('RSRP_5G', 'RSRP 5G', 'dBm'),
    ('RSRQ_5G', 'RSRQ 5G', 'dB'),
    ('SINR_5G', 'SINR 5G', 'dB'),
)

METRIC_LABELS = {key: label for key, label, _ in SIGNAL_METRICS}
METRIC_UNITS = {key: unit for key, _, unit in SIGNAL_METRICS}

# status/wan/devices/{uid}/status/summary values that mean a DSDS switch is
# in flight. The incoming slot reports 'Dual SIM switch' and the outgoing
# slot reports 'sibling transitioning'. Measured window: ~7s to ~31s after
# the dsds_switch PUT. While either appears, no test result is meaningful.
SWITCHING_SUMMARIES = ('dual sim switch', 'sibling transitioning')

# A switch took 31s end to end on the test unit. Allow generous headroom
# before calling it stuck, since a cold registration on a new carrier can
# take considerably longer than a warm one.
SWITCH_TIMEOUT = 150

# After the dsds_switch PUT, one of the slots enters a switching summary
# (SWITCHING_SUMMARIES) within ~1-2s on the test unit. If nothing is
# switching by this deadline, the request did not take - most often
# because the target slot was suspended on a backoff timer and could not
# be brought up - so the switch is declared failed here rather than after
# the full SWITCH_TIMEOUT. Measured onset was under 2s; the headroom
# covers a busier modem.
SWITCH_START_TIMEOUT = 12


def slot_key(port, sim):
    """Stable identifier for a SIM slot: 'int1|sim1'.

    Port + sim is the identity used everywhere in config and the UI.
    Carrier is deliberately not part of the key because it changes when a
    SIM is replaced or roams, which would silently orphan the config.
    """
    return '%s|%s' % (port or '?', sim or '?')


def slot_label(slot):
    """Human-readable slot name: 'Verizon (int1 / sim1)'.

    Carrier leads, with the port/sim in parentheses, so the most
    recognizable part reads first. A slot with no known carrier falls
    back to just the 'int1 / sim1' identifier.
    """
    carrier = slot.get('carrier')
    base = '%s / %s' % (slot.get('port') or '?', slot.get('sim') or '?')
    if carrier:
        return '%s (%s)' % (carrier, base)
    return base


def _clean_str(value):
    """Normalize a diagnostics string, treating placeholders as absent.

    Diagnostics values are always strings, and some fields carry the
    literal text 'None' or 'Unknown' instead of being omitted when the
    modem has nothing to report.
    """
    if value is None:
        return None
    text = str(value).strip()
    if text == '' or text.lower() in ('none', 'unknown', 'n/a'):
        return None
    return text


def _to_float(value):
    """Parse a diagnostics value to float. Diagnostics are all strings."""
    if value is None or value == '':
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def read_signal(diag):
    """Extract the signal metrics that this slot is currently reporting.

    Returns a dict of metric key -> float, containing only metrics the
    modem actually reported. Absent and unparseable metrics are omitted
    rather than defaulted, so a threshold is never evaluated against a
    made-up number.
    """
    out = {}
    if not isinstance(diag, dict):
        return out
    for key, _, _ in SIGNAL_METRICS:
        val = _to_float(diag.get(key))
        if val is not None:
            out[key] = val
    return out


def discover_slots():
    """Find every DSDS SIM slot on the router.

    Reads the whole `status/wan/devices` tree once per call and pulls
    info/status/diagnostics out of it, rather than issuing three GETs per
    device.

    Returns a dict of slot_key -> slot dict. Slots on the same physical
    modem share `port`; `sibling` points at the other slot's key.
    """
    slots = {}
    try:
        devices = cp.get('status/wan/devices')
    except Exception as e:
        cp.log('Error reading status/wan/devices: %s' % e)
        return slots
    if not isinstance(devices, dict):
        return slots

    for uid, dev in devices.items():
        if not uid.startswith('mdm-') or not isinstance(dev, dict):
            continue
        info = dev.get('info') or {}
        status = dev.get('status') or {}
        diag = dev.get('diagnostics') or {}

        # Two independent indicators of DSDS. info/dsds is the clean
        # boolean; DSDS_ENABLED is the modem's own report. Accept either so
        # the app still works if one is missing on another model.
        is_dsds = bool(info.get('dsds')) or \
            str(diag.get('DSDS_ENABLED', '')).upper() == 'TRUE'
        if not is_dsds:
            continue

        port = info.get('port')
        sim = info.get('sim')
        key = slot_key(port, sim)
        summary = status.get('summary') or ''
        ipinfo = status.get('ipinfo') or {}

        slots[key] = {
            'key': key,
            'port': port,
            'sim': sim,
            # CARRID is the serving carrier and is absent on a slot that is
            # not registered, so fall back to the SIM's home carrier.
            'carrier': _clean_str(diag.get('CARRID')) or
                       _clean_str(diag.get('HOMECARRID')),
            'home_carrier': _clean_str(diag.get('HOMECARRID')),
            'serving_carrier': _clean_str(diag.get('CARRID')),
            'iccid': _clean_str(diag.get('ICCID')),
            'uid': uid,
            'dsds_instance': diag.get('DSDS_INSTANCE'),
            'connection_state': status.get('connection_state'),
            'summary': summary,
            'reason': status.get('reason'),
            # Why the modem rejected or dropped this slot, e.g.
            # "CPPM failed: carrier reject". Populated by NCOS, so it is
            # the one place to see why a SIM failed outside the app (a bad
            # APN, a carrier reject). Cleaned so the literal 'None' string
            # a healthy slot reports is dropped rather than displayed.
            'error_text': _clean_str(status.get('error_text')),
            # isActiveSib is the router's own "this is the slot that owns
            # the radio" flag. It flips ~14s into a switch, roughly halfway
            # through, so it is not a substitute for connection_state.
            'active_sib': bool(status.get('isActiveSib')),
            'connected': status.get('connection_state') == 'connected',
            'switching': summary.lower() in SWITCHING_SUMMARIES,
            # A SIM that failed to register - e.g. a bad APN - is parked
            # on a backoff timer and reports suspended=True with a
            # 'suspended (N secs)' summary until the timer expires and it
            # returns to 'standby'. The modem cannot switch to a
            # suspended slot: a dsds_switch aimed at one is accepted but
            # never completes, so it must be gated out as a target.
            'suspended': bool(status.get('suspended')),
            'ip_address': ipinfo.get('ip_address'),
            'signal': read_signal(diag),
            'service_type': _clean_str(diag.get('SRVC_TYPE')),
            # A standby slot reports the literal string 'None' here rather
            # than omitting the key, which would otherwise be displayed.
            'service_detail': _clean_str(diag.get('SRVC_TYPE_DETAILS')),
            'rf_band': _clean_str(diag.get('RFBAND')),
            'health_score': status.get('cellular_health_score'),
            'health_category': status.get('cellular_health_category'),
            'nosim': str(diag.get('NOSIM', '')).upper() == 'TRUE',
            'uptime': status.get('uptime'),
        }

    # Pair each slot with the other slot on the same physical modem.
    by_port = {}
    for key, slot in slots.items():
        by_port.setdefault(slot['port'], []).append(key)
    for key, slot in slots.items():
        peers = [k for k in by_port.get(slot['port'], []) if k != key]
        slot['sibling'] = peers[0] if len(peers) == 1 else None

    return slots


def active_slot(slots):
    """Return the connected slot, or None.

    Prefers connection_state over isActiveSib: during a switch the
    incoming slot sets isActiveSib well before it can carry traffic.
    """
    for slot in slots.values():
        if slot.get('connected'):
            return slot
    return None


def switch_in_progress(slots):
    """True if any slot reports a DSDS switch in flight."""
    return any(slot.get('switching') for slot in slots.values())


def switch_target_blocked(target):
    """Why a switch to `target` cannot be attempted now, or None if it can.

    A dsds_switch is accepted by the modem even when the destination
    cannot come up, and then simply never completes - which is what made
    the app sit through the full SWITCH_TIMEOUT. The two cases worth
    catching before asking are a missing SIM and a slot suspended on a
    registration backoff (bad APN, no service). A suspended slot returns
    to 'standby' when its timer expires, so this is transient, not fatal.

    Returns a short human-readable reason string, or None when the target
    looks ready to switch to.
    """
    if not target:
        return 'there is no sibling slot to switch to'
    if target.get('nosim'):
        return '%s has no SIM' % slot_label(target)
    if target.get('suspended'):
        summary = target.get('summary') or 'suspended'
        return '%s is %s' % (slot_label(target), summary)
    return None


def request_switch(slot):
    """Ask a DSDS modem to swap to its other SIM slot.

    The PUT goes to the *connected* slot's device. It returns immediately
    (~0.1s) and the swap then runs asynchronously; the new slot reached
    'connected' 31s later on the test unit.

    Note the `dsds_switch` key is not always present in a device's
    testmode struct beforehand, so its absence must not be treated as
    "unsupported" - the PUT creates it. Conversely, once written the key
    persists in the control tree for both slots, so its presence proves
    nothing either.

    Returns (ok, message).
    """
    uid = slot.get('uid')
    if not uid:
        return False, 'slot has no resolved device'
    if not slot.get('connected'):
        return False, 'slot %s is not connected; switch must be requested ' \
                      'on the connected slot' % slot_label(slot)
    path = 'control/wan/devices/%s/testmode/dsds_switch' % uid
    try:
        resp = cp.put(path, True)
    except Exception as e:
        return False, 'dsds_switch PUT failed: %s' % e

    # The on-router socket returns {'status': 'ok'|'error'} while local
    # REST returns {'success': True|False}. Check both so an on-router
    # failure is not silently read as success.
    if isinstance(resp, dict):
        if resp.get('status') == 'error' or resp.get('success') is False:
            return False, 'dsds_switch rejected: %s' % resp
    elif resp is None:
        return False, 'dsds_switch PUT got no response'
    return True, 'switch requested on %s' % slot_label(slot)


def wait_for_switch(from_key, to_key=None, timeout=SWITCH_TIMEOUT, poll=2.0,
                    start_timeout=SWITCH_START_TIMEOUT):
    """Block until the sibling slot connects, or the switch is called off.

    Returns (ok, elapsed_seconds, slots, reason). Observed progression
    after the PUT on the test unit:
        2.6s  old slot -> 'disconnecting'
        6.0s  old slot -> 'disconnected' / 'standby'
        7.2s  new slot -> 'connecting' / 'Dual SIM switch'
       14.1s  isActiveSib flips to the new slot
       28.3s  new slot gets an IP
       30.7s  new slot -> 'connected'

    Failure is returned in three ways, distinguished by `reason`:

    * `'did not start'` - no slot entered a switching summary within
      `start_timeout`. The PUT was accepted but nothing moved, which on
      the test unit means the target could not be brought up (a suspended
      backoff being the usual cause). Returned in a couple of seconds
      instead of after the full `timeout`.
    * `'target failed'` - the switch started but the target slot
      (`to_key`) went **suspended** instead of connecting, i.e. it tried
      to register and could not - a bad APN or no service. Seen in the
      field within ~30s, where the modem then abandons the switch and
      NCOS restores the original slot. This is the definitive "the target
      cannot come up" signal, far faster than the full timeout, and it
      means the target's link is broken even though its signal looks fine
      from standby - exactly the case the failback holdoff is for.
    * `'timed out'` - a switch did start but no slot had connected by
      `timeout`, and the target never reported suspended either.
    """
    start = time.time()
    slots = {}
    switch_seen = False
    while time.time() - start < timeout:
        slots = discover_slots()
        current = active_slot(slots)
        if current and current['key'] != from_key:
            return True, time.time() - start, slots, None
        if switch_in_progress(slots):
            switch_seen = True
        elif not switch_seen and time.time() - start >= start_timeout:
            # Nothing ever entered a switching state, so the request did
            # not take. No point waiting out the remaining timeout.
            return False, time.time() - start, slots, 'did not start'
        # Once the switch has started, a target that goes suspended has
        # failed to register. Don't wait for it: the modem will keep it
        # on a backoff timer and eventually restore the original slot, so
        # the whole window would otherwise be dead air.
        if switch_seen and to_key:
            target = slots.get(to_key) or {}
            if target.get('suspended'):
                return False, time.time() - start, slots, 'target failed'
        time.sleep(poll)
    return False, time.time() - start, slots, 'timed out'
