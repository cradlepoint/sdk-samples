"""Modem discovery, status, and PLMN locking for cell_survey.

Discovery rule: a 5G/LTE modem exposes each SIM slot as a separate mdm-*
WAN device, but both share the same physical 'port' (e.g. int1) and the same
'config_id'. The UI should present ONE modem per physical port, so we collapse
mdm devices by port and prefer the connected / SIM1 instance for status.

The modem's info.config_id is the _id_ of the WAN rule (config/wan/rules2) that
matches that modem's technology. That rule is where lock_net / net_sel_mode are
written to force a PLMN, so config_id doubles as the lock target.

AT survey needs the modem's SubIface (e.g. rmnet501), which equals the device
info.iface for an mdm device.
"""

import time

import cp

# Preferred modem to default to in the UI.
DEFAULT_PORT = 'int1'

# The AT network survey (AT#CSURVC) is a Telit command set. Only the Telit
# modules Cradlepoint ships (FE990 / FN990) support it; on any other module the
# survey cannot run, so the UI disables it and the API refuses to start.
_SUPPORTED_MODELS = ('FE990', 'FN990')


def is_supported(mfg_model):
    """True if the modem's manufacturer model supports the AT survey.

    Matches the Telit FE990 / FN990 families (e.g. 'FN990A28-CP',
    'FE990B40-NAD'). Any other module returns False.
    """
    model = str(mfg_model or '').upper()
    return any(m in model for m in _SUPPORTED_MODELS)


# eUICC profile "Class" codes from the EUICC_PROF<n> diagnostics string. These
# match the eSIM Manager UI's Class column: 0 is a test profile, 2 is a
# provisioned operational profile. Only operational profiles are worth
# activating from this app, so the UI offers an "Activate eSIM Profile" button
# only for class == '2'.
_EUICC_CLASS_LABELS = {
    '0': 'test',
    '1': 'provisioning',
    '2': 'operational',
}


def parse_euicc_profiles(diag):
    """Parse the EUICC_PROF<n> diagnostics fields into profile dicts.

    An eSIM-capable modem (ESIM_TYPE set, EUICC_SGP22 == 'TRUE') publishes one
    EUICC_PROF<n> field per installed profile, each a comma-separated string.
    The field order matches the columns in the router's eSIM Manager UI:

        0: iccid            (e.g. '8901882014725970045F')
        1: profile_name     (e.g. 'T-Mobile')            -- "Profile Name"
        2: active           ('1' = active, '0' = not)    -- "Active"
        3: nickname         (e.g. 'W2255-SIM1-TMO')      -- "Nickname"
        4: service_provider (e.g. 'T-Mobile')            -- "Service Provider"
        5: class            ('0' test, '2' operational)  -- "Class"
        6: reserved         (trailing padding, ignored)

    Only operational profiles (class '2') can be meaningfully activated from
    this app; a test profile is flagged so the UI can hide its button.

    Args:
        diag: The modem's status/wan/devices/<uid>/diagnostics dict.

    Returns:
        list: profile dicts {iccid, profile_name, nickname, service_provider,
            active (bool), profile_class, class_label, operational (bool)},
            in profile-slot order. Empty if the modem has no eUICC profiles.
    """
    if not isinstance(diag, dict):
        return []
    profiles = []
    i = 1
    while True:
        raw = diag.get('EUICC_PROF{}'.format(i))
        if raw is None:
            break
        i += 1
        parts = [p.strip() for p in str(raw).split(',')]
        if len(parts) < 6 or not parts[0]:
            continue
        iccid = parts[0]
        profile_name = parts[1]
        active = parts[2] == '1'
        nickname = parts[3]
        service_provider = parts[4]
        profile_class = parts[5]
        profiles.append({
            'iccid': iccid,
            'profile_name': profile_name,
            'nickname': nickname,
            'service_provider': service_provider,
            'active': active,
            'profile_class': profile_class,
            'class_label': _EUICC_CLASS_LABELS.get(profile_class, profile_class),
            'operational': profile_class == '2',
        })
    return profiles


def _norm_carrier(name):
    """Normalize a carrier/profile name for loose matching.

    Lowercases and strips non-alphanumerics so 'AT&T' matches 'at&t' / 'att'
    and 'T-Mobile' matches 'tmobile'. Used to line a survey carrier up with an
    installed eUICC profile by name.
    """
    return ''.join(ch for ch in str(name or '').lower() if ch.isalnum())


def euicc_info(diag):
    """Summarize a modem's eUICC (eSIM) state for the UI.

    Args:
        diag: The modem's diagnostics dict.

    Returns:
        dict: {supported (bool), eid, profiles (list)}. supported is True when
            the modem exposes SGP.22 eUICC support; profiles is from
            parse_euicc_profiles().
    """
    if not isinstance(diag, dict):
        return {'supported': False, 'eid': None, 'profiles': []}
    profiles = parse_euicc_profiles(diag)
    supported = (str(diag.get('EUICC_SGP22', '')).upper() == 'TRUE'
                 or bool(diag.get('EID'))
                 or bool(profiles))
    return {
        'supported': supported,
        'eid': diag.get('EID'),
        'profiles': profiles,
    }


def find_profile_for_carrier(profiles, network=None, plmn_mcc=None,
                             plmn_mnc=None):
    """Find an operational eUICC profile matching a survey carrier by name.

    Matching is by profile/service-provider name against the survey carrier's
    network name (normalized), since the EUICC_PROF string carries no PLMN.
    Only operational (class '2') profiles are considered.

    Args:
        profiles: list from parse_euicc_profiles().
        network: Survey carrier network name (e.g. 'T-Mobile').

    Returns:
        dict: The matching profile, or None.
    """
    target = _norm_carrier(network)
    if not target:
        return None
    for p in profiles:
        if not p.get('operational'):
            continue
        names = {_norm_carrier(p.get('profile_name')),
                 _norm_carrier(p.get('service_provider'))}
        if target in names:
            return p
        # Allow a loose contains match (e.g. 'tmobile' in 'tmobileus').
        for n in names:
            if n and (n in target or target in n):
                return p
    return None


def activate_esim_profile(uid, eid, iccid):
    """Activate (enable) an eUICC profile by ICCID on a modem.

    Sends the SGP.22 set_state/enable action to the modem's eUICC control
    endpoint. Enabling a profile makes the modem re-register on that carrier,
    which may briefly drop the connection (and can reset the modem if it needs
    different firmware).

    Args:
        uid: Modem WAN device uid (e.g. 'mdm-84e7b418').
        eid: The eUICC EID (from diagnostics 'EID').
        iccid: The target profile's ICCID.

    Returns:
        dict: {ok: bool, message: str}.
    """
    if not uid:
        return {'ok': False, 'message': 'Missing modem id.'}
    if not eid:
        return {'ok': False, 'message': 'Missing eUICC EID for this modem.'}
    if not iccid:
        return {'ok': False, 'message': 'Missing profile ICCID.'}
    path = 'control/wan/devices/{}/euicc'.format(uid)
    value = {
        'eid': eid,
        'op_id': 0,
        'action': 'set_state',
        'payload': {'iccid': iccid, 'state': 'enable'},
    }
    resp = cp.put(path, value)
    if _put_ok(resp):
        cp.log('cell_survey: activating eUICC profile {} on {}'.format(
            iccid, uid))
        return {'ok': True,
                'message': 'Activating eSIM profile. The modem will '
                           're-register on this carrier; the connection may '
                           'drop briefly and the modem may reset.'}
    cp.log('cell_survey: failed to activate eUICC profile {} on {}: {}'.format(
        iccid, uid, resp))
    return {'ok': False,
            'message': 'Could not start eSIM profile activation.'}


def _signal_quality(rsrp):
    """Rough human label for an RSRP value (dBm)."""
    try:
        v = int(rsrp)
    except (TypeError, ValueError):
        return 'Unknown'
    if v >= -80:
        return 'Excellent'
    if v >= -90:
        return 'Good'
    if v >= -100:
        return 'Fair'
    return 'Poor'


def list_modems():
    """Return one entry per physical modem port, default modem flagged.

    The default is the first CONNECTED modem/SIM when any modem is connected,
    so the UI opens on a usable link. Among connected modems the preferred
    port (DEFAULT_PORT, int1) wins, otherwise the lowest-sorting connected
    port. When nothing is connected, fall back to the preferred port if
    present, else the lowest-sorting port.

    Returns:
        list: Each item is {port, uid, iface (SubIface), config_id, model,
            connected, sim_count, is_default}. Sorted with the default port
            first.
    """
    devices = cp.get('status/wan/devices') or {}
    by_port = {}
    for key, dev in devices.items():
        info = (dev or {}).get('info') or {}
        if info.get('type') != 'mdm':
            continue
        status = (dev or {}).get('status') or {}
        port = info.get('port') or key
        connected = status.get('connection_state') == 'connected'
        entry = by_port.get(port)
        candidate = {
            'port': port,
            'uid': key,
            'iface': info.get('iface'),
            'config_id': info.get('config_id'),
            'model': info.get('model') or 'Modem',
            'mfg_model': info.get('mfg_model') or '',
            'connected': connected,
            'sim_count': 1,
        }
        if entry is None:
            by_port[port] = candidate
        else:
            entry['sim_count'] += 1
            # Prefer a connected SIM instance for the representative device.
            if connected and not entry['connected']:
                entry.update({
                    'uid': candidate['uid'],
                    'iface': candidate['iface'],
                    'config_id': candidate['config_id'],
                    'model': candidate['model'],
                    'mfg_model': candidate['mfg_model'],
                    'connected': True,
                })

    modems = list(by_port.values())
    default_port = _choose_default_port(modems)
    for m in modems:
        m['is_default'] = (m['port'] == default_port)
    modems.sort(key=lambda m: (not m['is_default'], m['port']))
    return modems


def _choose_default_port(modems):
    """Pick the default port: first connected modem if any, else fallback.

    Preference, in order:
      1. The preferred port (DEFAULT_PORT) if it is connected.
      2. The lowest-sorting connected port.
      3. The preferred port if present (even if not connected).
      4. The lowest-sorting port.
      5. None (no modems).
    """
    if not modems:
        return None
    ports = sorted(m['port'] for m in modems)
    connected = sorted(m['port'] for m in modems if m.get('connected'))
    if connected:
        if DEFAULT_PORT in connected:
            return DEFAULT_PORT
        return connected[0]
    if DEFAULT_PORT in ports:
        return DEFAULT_PORT
    return ports[0]


def _find_modem(port):
    """Return the representative modem dict for a port, or None."""
    for m in list_modems():
        if m['port'] == port:
            return m
    return None


def modem_status(port):
    """Detailed status/signal/carrier for the modem on the given port.

    Returns:
        dict: Connection and radio details for the UI, or {'error': ...}.
    """
    modem = _find_modem(port)
    if not modem:
        return {'error': 'No modem found on port {}'.format(port)}

    uid = modem['uid']
    base = 'status/wan/devices/{}'.format(uid)
    diag = cp.get('{}/diagnostics'.format(base)) or {}
    status = cp.get('{}/status'.format(base)) or {}

    mfg_model = diag.get('MFG_MDL') or modem.get('mfg_model') or ''
    signal = _signal_metrics(diag)
    esim = euicc_info(diag)
    result = {
        'port': port,
        'uid': uid,
        'iface': modem['iface'],
        'config_id': modem['config_id'],
        'mfg_model': mfg_model,
        'esim': esim,
        'supported': is_supported(mfg_model),
        'model': diag.get('MDL') or modem['model'],
        'sim_count': modem['sim_count'],
        'connection_state': status.get('connection_state', 'unknown'),
        'summary': status.get('summary', ''),
        'error_text': status.get('error_text'),
        'carrier': diag.get('CARRID') or diag.get('HOMECARRID') or 'Unknown',
        'home_carrier': diag.get('HOMECARRID'),
        'plmn': diag.get('CUR_PLMN') or diag.get('HM_PLMN'),
        'service_type': diag.get('SRVC_TYPE') or diag.get('SERDIS'),
        'service_type_display': _service_type_display(diag),
        'rf_band': signal['rf_band'],
        'cell_id': diag.get('CELL_ID') or diag.get('NR_CELL_ID'),
        'rssi': signal['rssi'],
        'rsrp': signal['rsrp'],
        'rsrq': signal['rsrq'],
        'sinr': signal['sinr'],
        'signal_quality': _signal_quality(signal['rsrp']),
        'signal_pct': status.get('signal_strength') or diag.get('SS'),
        'roam': diag.get('ROAM'),
        'temperature': diag.get('MODEMTEMP'),
        'imei': diag.get('DISP_IMEI') or diag.get('GSN'),
        'iccid': diag.get('ICCID'),
        'apn': diag.get('ACTIVEAPN'),
        'lock': lock_status(modem['config_id']),
    }
    return result


def _service_type_display(diag):
    """Human service-type label; append SA/NSA when the modem is on 5G.

    SRVC_TYPE is coarse ('5G', 'LTE'). SRVC_TYPE_DETAILS carries the 5G camp,
    e.g. 'SA - 5G Sub-6 GHz' or 'NSA - ...'. When on 5G, show '5G SA' / '5G
    NSA' so the tile distinguishes Standalone from Non-Standalone. For non-5G
    service, show SRVC_TYPE as-is.

    Returns:
        str: e.g. '5G SA', '5G NSA', '5G', 'LTE', or '' when unknown.
    """
    srvc = str(diag.get('SRVC_TYPE') or diag.get('SERDIS') or '').strip()
    if not srvc:
        return ''
    is_5g = '5G' in srvc.upper() or 'NR' in srvc.upper()
    if not is_5g:
        return srvc
    details = str(diag.get('SRVC_TYPE_DETAILS') or '').strip().upper()
    if details.startswith('NSA'):
        return '{} NSA'.format(srvc)
    if details.startswith('SA'):
        return '{} SA'.format(srvc)
    return srvc


def _signal_metrics(diag):
    """Pick RSRP/RSRQ/SINR/RSSI/band for the modem's live radio technology.

    Which diagnostics fields carry signal depends on the serving technology:
    an LTE-serving modem populates RSRP/RSRQ/SINR/DBM, while a 5G-serving modem
    populates RSRP_5G/RSRQ_5G/SINR_5G (and omits DBM). Prefer the set that
    matches the current service type, then fall back to whichever is present so
    a modem on either RAT shows real numbers rather than blanks.

    Returns:
        dict: {rsrp, rsrq, sinr, rssi, rf_band} with None where unavailable.
    """
    serving = (diag.get('SRVC_TYPE') or diag.get('SERDIS') or '').upper()
    is_5g = '5G' in serving or 'NR' in serving

    def pick(nr_key, lte_key):
        """Return the preferred-then-fallback value for a metric."""
        nr = diag.get(nr_key)
        lte = diag.get(lte_key)
        if is_5g:
            return nr if nr not in (None, '') else lte
        return lte if lte not in (None, '') else nr

    return {
        'rsrp': pick('RSRP_5G', 'RSRP'),
        'rsrq': pick('RSRQ_5G', 'RSRQ'),
        'sinr': pick('SINR_5G', 'SINR'),
        # RSSI (DBM) is LTE-only; 5G has no equivalent, so None is expected.
        'rssi': diag.get('DBM'),
        'rf_band': pick('RFBAND_5G', 'RFBAND'),
    }


def lock_status(config_id):
    """Current net-selection lock for a modem's WAN rule.

    Returns:
        dict: {net_sel_mode, lock_net} with None when not set.
    """
    if not config_id:
        return {'net_sel_mode': None, 'lock_net': None}
    rule = cp.get('config/wan/rules2/{}/modem'.format(config_id)) or {}
    return {
        'net_sel_mode': rule.get('net_sel_mode'),
        'lock_net': rule.get('lock_net'),
    }


def lock_plmn(config_id, plmn):
    """Force the modem's WAN rule to a specific PLMN (manual net selection).

    Writes config/wan/rules2/{config_id}/modem = {lock_net, net_sel_mode}.
    The two fields are cross-validated, so they are written in one PUT. The
    write is read back and retried up to 3 times before reporting failure.

    Args:
        config_id: The modem's WAN rule _id_ (from modem info.config_id).
        plmn: Numeric PLMN string, e.g. '310260'.

    Returns:
        dict: {ok: bool, message: str}.
    """
    if not config_id:
        return {'ok': False, 'message': 'Missing modem rule id.'}
    if not plmn or not plmn.isdigit():
        return {'ok': False, 'message': 'Invalid PLMN: {}'.format(plmn)}

    value = {'lock_net': plmn, 'net_sel_mode': 'manual'}
    path = 'config/wan/rules2/{}/modem'.format(config_id)
    for attempt in range(3):
        resp = cp.put(path, value)
        ok = _put_ok(resp)
        # Read back to confirm (write-success can be reported without applying).
        current = cp.get(path) or {}
        if ok and current.get('lock_net') == plmn \
                and current.get('net_sel_mode') == 'manual':
            cp.log('Locked modem rule {} to PLMN {}'.format(config_id, plmn))
            return {'ok': True,
                    'message': 'Locked to PLMN {}. The modem will '
                               're-register; this may briefly drop the '
                               'connection.'.format(plmn)}
        time.sleep(0.5)
    cp.log('Failed to lock modem rule {} to PLMN {}'.format(config_id, plmn))
    return {'ok': False, 'message': 'Could not confirm the PLMN lock after '
                                    '3 attempts.'}


def unlock(config_id):
    """Restore automatic network selection by clearing the lock.

    Deletes the WAN rule's whole 'modem' subtree, which reverts net selection
    to its default (auto) and removes the locked PLMN. This mirrors the manual
    CLI workflow ('delete config/wan/rules2/<id>/modem/') and avoids leaving a
    half-written lock behind.

    Returns:
        dict: {ok: bool, message: str}.
    """
    if not config_id:
        return {'ok': False, 'message': 'Missing modem rule id.'}
    path = 'config/wan/rules2/{}/modem'.format(config_id)
    for attempt in range(3):
        cp.delete(path)
        current = cp.get(path) or {}
        mode = current.get('net_sel_mode')
        # Cleared: subtree gone, or mode fell back to a non-manual default.
        if mode in (None, 'auto', 'home', 'smart') \
                and not current.get('lock_net'):
            cp.log('Restored automatic net selection on rule {}'.format(
                config_id))
            return {'ok': True,
                    'message': 'Restored automatic network selection.'}
        time.sleep(0.5)
    return {'ok': False, 'message': 'Could not confirm automatic selection.'}


def _put_ok(resp):
    """True if a cp.put() response indicates success (socket or REST shape)."""
    if not isinstance(resp, dict):
        return False
    # On-router socket: {'status': 'ok', ...}; local REST: {'success': True}.
    return resp.get('status') == 'ok' or resp.get('success') is True
