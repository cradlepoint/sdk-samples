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
    for m in modems:
        m['is_default'] = (m['port'] == DEFAULT_PORT)
    modems.sort(key=lambda m: (not m['is_default'], m['port']))
    return modems


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
    result = {
        'port': port,
        'uid': uid,
        'iface': modem['iface'],
        'config_id': modem['config_id'],
        'mfg_model': mfg_model,
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
