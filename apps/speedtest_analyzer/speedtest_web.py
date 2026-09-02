# Speedtest Analyzer - WAN performance testing, analysis, history, and reporting
# Supports: Ookla (BYOB - bring your own binary), Netperf (built-in), iPerf3

import cp
import os
import re
import sys
import json
import time
import socket
import socketserver
import subprocess
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime
from threading import Thread
from urllib.parse import parse_qs, urlparse

from cellular_analysis import (
    build_cellular_analysis,
    build_site_cell_inventory,
)
from cellular_geo import (
    apply_geo_settings,
    gps_fix_is_usable,
    load_geo_settings,
)

import configuration_manager as config_mgr

# Constants
PORT = 8000
HISTORY_FILE = 'tmp/speedtest_history.json'
HISTORY_BACKUP_FILE = HISTORY_FILE + '.bak'
HISTORY_TEMP_FILE = HISTORY_FILE + '.tmp'
HISTORY_CORRUPT_FILE = HISTORY_FILE + '.corrupt'
MAX_HISTORY = 100

# Read app version from package.ini
APP_VERSION = 'unknown'
try:
    import configparser as _cp
    _ini = _cp.ConfigParser()
    _ini.read('package.ini')
    _sec = list(_ini.sections())
    if _sec:
        _s = _ini[_sec[0]]
        APP_VERSION = (f"{_s.get('version_major', '0')}."
                       f"{_s.get('version_minor', '0')}."
                       f"{_s.get('version_patch', '0')}")
except Exception:
    pass

# Global state
current_test = {
    'running': False,
    'engine': None,
    'progress': {},
    'error': None
}
test_lock = threading.Lock()
history_lock = threading.RLock()

# Active local iPerf3 subprocess used for immediate Stop handling.
_iperf3_process_lock = threading.Lock()
_active_iperf3_process = None

# WAN/path snapshot for the currently running iPerf3 test.
# Used only to distinguish a remote endpoint timeout from a local WAN failure.
_active_iperf3_wan_guard = None

# Dedicated execution slot. Unlike current_test['running'], this remains
# reserved until the worker thread has completely exited its finally block.
# This prevents manual and scheduled tests from overlapping during startup,
# cancellation, TCP_RR, telemetry cleanup, or result processing.
test_slot_lock = threading.Lock()


def _reserve_test_slot(engine):
    """Atomically reserve the single speed-test execution slot."""
    if not test_slot_lock.acquire(blocking=False):
        return False

    with test_lock:
        current_test['running'] = True
        current_test['engine'] = engine
        current_test['progress'] = {'stage': 'starting', 'percent': 0}
        current_test['error'] = None

    return True


def _release_test_slot():
    """Release the speed-test execution slot after worker cleanup."""
    with test_lock:
        current_test['running'] = False

    try:
        test_slot_lock.release()
    except RuntimeError:
        pass


# Active carrier telemetry collector (set during cellular tests)
_active_carrier_collector = None

# Schedule state
schedule_config = {
    'enabled': False,       # PERSISTED intent
    'autostart': False,     # PERSISTED intent (independent of enabled)
    'cron': '',
    'engine': 'netperf',
    'params': {},
    'running': False,       # RUNTIME-ONLY: does the scheduler actually fire?
}
schedule_lock = threading.Lock()

# iPerf3 endpoint reliability statistics.
# Loaded lazily and checkpointed as one compact SDK appdata object.
_IPERF3_STATS_KEY = 'iperf_server_stats'
_IPERF3_STATS_SCHEMA_VERSION = 1
_IPERF3_STATS_CHECKPOINT_SECONDS = 1800

_iperf3_stats = None
_iperf3_stats_dirty = False
_iperf3_stats_generation = 0
_iperf3_stats_last_checkpoint = 0.0
_iperf3_stats_lock = threading.Lock()


OOKLA_BINARIES = ('ookla', 'speedtest', 'speedtest-cli')
IPERF3_BINARIES = ('iperf3', 'iperf3-arm64v8', 'iperf3-aarch64')


def has_ookla():
    """Check if ookla binary is present in the app directory."""
    for binary in OOKLA_BINARIES:
        if os.path.exists(binary):
            if not os.access(binary, os.X_OK):
                try:
                    os.chmod(binary, 0o755)
                except Exception:
                    pass
            return True
    return False


def get_ookla_binary():
    """Return the path to the ookla binary, or None if not found."""
    for binary in OOKLA_BINARIES:
        if os.path.exists(binary):
            if not os.access(binary, os.X_OK):
                try:
                    os.chmod(binary, 0o755)
                except Exception:
                    pass
            return './' + binary
    return None


def has_iperf3():
    """Check if iperf3 binary is present in the app directory."""
    for binary in IPERF3_BINARIES:
        if os.path.exists(binary):
            if not os.access(binary, os.X_OK):
                try:
                    os.chmod(binary, 0o755)
                except Exception:
                    pass
            return True
    return False


def get_iperf3_binary():
    """Return the path to the iperf3 binary, or None if not found."""
    for binary in IPERF3_BINARIES:
        if os.path.exists(binary):
            if not os.access(binary, os.X_OK):
                try:
                    os.chmod(binary, 0o755)
                except Exception:
                    pass
            return './' + binary
    return None


def _carrier_abbreviation(carrier):
    """Return a supported user-facing carrier abbreviation."""
    normalized = re.sub(
        r'[^a-z0-9]+',
        '',
        str(carrier or '').strip().lower()
    )

    if not normalized:
        return ''

    if normalized in ('att', 'attwireless') or 'firstnet' in normalized:
        return 'ATT'

    if normalized == 'vzw' or 'verizon' in normalized:
        return 'VZW'

    if normalized == 'tmo' or 'tmobile' in normalized:
        return 'TMO'

    # Unknown global carriers and MVNOs intentionally receive no carrier
    # prefix. The SIM slot remains the stable user-facing identifier.
    return ''


def _sim_slot_label(value):
    """Normalize an NCOS SIM value to SIM1 or SIM2."""
    text = str(value or '').strip().upper()

    if not text:
        return ''

    match = re.search(r'(?:SIM)?[\s_-]*([12])\b', text)

    if not match:
        return ''

    return 'SIM' + match.group(1)


def _satellite_wan_label(uid, iface):
    """Build a stable display label for a satellite WAN."""
    identity = str(uid or iface or '').strip()
    match = re.search(r'([a-zA-Z0-9]{4})$', identity)

    if match:
        return 'Satellite WAN-' + match.group(1).upper()

    return 'Satellite WAN'


def _wan_is_cellular_device(uid, device):
    """Return True only when an NCOS WAN has cellular evidence."""
    device = device if isinstance(device, dict) else {}
    info = device.get('info', {})
    info = info if isinstance(info, dict) else {}
    diagnostics = device.get('diagnostics', {})
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}

    uid = str(uid or '')
    iface = str(info.get('iface', '') or '')
    wan_type = str(info.get('type', '') or '')
    product = str(info.get('product', '') or '')

    diagnostic_identity = ' '.join(
        f'{key} {value}'
        for key, value in diagnostics.items()
        if value is not None
    )

    identity = ' '.join(
        (
            uid,
            iface,
            wan_type,
            product,
            diagnostic_identity,
        )
    ).strip().lower()

    # Satellite WANs may use mdm-* identities in NCOS, but they use the
    # same non-cellular reporting path as Ethernet WAN.
    if 'starlink' in identity or 'satellite' in identity:
        return False

    modem_identity = (
        wan_type.lower() == 'mdm' or
        uid.lower().startswith('mdm-')
    )

    if not modem_identity:
        return False

    carrier_value = str(
        diagnostics.get('CARRID', '') or ''
    ).strip().lower()

    carrier_present = carrier_value not in (
        '',
        '--',
        'unknown',
        'none',
        'n/a',
        'not available',
    )

    sim_present = bool(
        _sim_slot_label(info.get('sim', ''))
    )

    cellular_service = re.search(
        r'(^|[^a-z0-9])'
        r'(lte|4g|5g|nr5g|nr|cellular|wwan)'
        r'([^a-z0-9]|$)',
        identity,
    ) is not None

    return (
        carrier_present or
        sim_present or
        cellular_service
    )


def _friendly_wan_name(uid, device):
    """Build a display-only WAN name without changing its routing identity."""
    device = device if isinstance(device, dict) else {}
    info = device.get('info', {})
    info = info if isinstance(info, dict) else {}
    diagnostics = device.get('diagnostics', {})
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}

    iface = str(info.get('iface', '') or '')
    wan_type = str(info.get('type', '') or '')
    product = str(info.get('product', '') or '')
    uid = str(uid or '')

    identity = ' '.join(
        (wan_type, product, iface, uid)
    ).strip().lower()

    diagnostic_identity = ' '.join(
        str(value)
        for value in diagnostics.values()
        if value is not None
    ).strip().lower()

    classification_identity = (
        identity + ' ' + diagnostic_identity
    ).strip()

    # Starlink WANs can use an mdm-* UID even though they are satellite
    # connections. Satellite evidence must be evaluated before cellular
    # modem classification.
    if (
        'starlink' in classification_identity or
        'satellite' in classification_identity
    ):
        return _satellite_wan_label(uid, iface)

    carrier_value = str(
        diagnostics.get('CARRID', '') or ''
    ).strip()
    carrier = _carrier_abbreviation(carrier_value)
    sim = _sim_slot_label(info.get('sim', ''))

    carrier_present = carrier_value.lower() not in (
        '',
        '--',
        'unknown',
        'none',
        'n/a',
        'not available',
    )

    cellular_service = re.search(
        r'(^|[^a-z0-9])'
        r'(lte|5g|nr5g|nr|cellular|wwan)'
        r'([^a-z0-9]|$)',
        classification_identity,
    ) is not None

    modem_identity = (
        wan_type.lower() == 'mdm' or
        uid.lower().startswith('mdm-')
    )

    # An mdm-* UID alone is not proof of a cellular WAN. Require carrier,
    # SIM, LTE, 5G, NR, cellular, or WWAN evidence before applying cellular
    # carrier and SIM labels.
    if modem_identity and (
        carrier_present or
        bool(sim) or
        cellular_service
    ):
        if carrier and sim:
            connection = carrier + '-' + sim
        elif sim:
            connection = sim
        else:
            connection = 'Cellular WAN'

        try:
            catalog = _load_device_validation_catalog() or {}
        except Exception:
            catalog = {}

        remote = info.get('remote', {})
        remote = remote if isinstance(remote, dict) else {}
        internal_captive = (
            remote.get('internal_captive') is True
        )

        if remote and not internal_captive:
            remote_product = str(
                remote.get('product_name', '') or ''
            ).strip().upper()
            owner = _validation_match_model(
                remote_product,
                _validation_captive_models(catalog)
            ) or remote_product or 'Captive Modem'
            owner += ' Captive'
        else:
            try:
                owner = str(
                    _get_model_family() or _get_product_model() or ''
                ).strip().upper()
            except Exception:
                owner = ''

            if owner in catalog.get('single_captive_combinations', {}):
                owner += ' Internal'

        if owner:
            return owner + ' - ' + connection

        return connection

    if (
        wan_type.lower() in ('wifi', 'wi-fi', 'wlan') or
        'wifi' in identity or
        'wi-fi' in identity
    ):
        return 'Wi-Fi as WAN'

    if (
        wan_type.lower() in ('ethernet', 'eth') or
        iface.lower() in ('wan', 'ethernet-wan') or
        uid.lower() == 'ethernet-wan' or
        'ethernet wan' in identity
    ):
        return 'Ethernet WAN'

    # Preserve unknown interfaces such as future satellite, wbond, or
    # Secure Connect interfaces until their NCOS identities are validated.
    return product or iface or uid or 'Unknown WAN'


def get_wan_interfaces():
    """Get connected WAN interfaces with display and routing identities."""
    try:
        devices = cp.get('status/wan/devices')
        interfaces = []
        # Interface types to exclude from speed testing — these are overlay
        # or tunnel interfaces that don't represent a physical WAN link.
        _exclude_types = ('sdwan', 'vpn', 'gre', 'ipsec')
        if devices and isinstance(devices, dict):
            for uid, info in devices.items():
                if isinstance(info, dict):
                    iface = info.get('info', {}).get('iface', '')
                    wan_type = info.get('info', {}).get('type', '')
                    # Skip overlay/tunnel interfaces
                    if wan_type in _exclude_types:
                        continue
                    status = info.get('status', {})
                    conn_state = status.get('connection_state', 'unknown')
                    if conn_state != 'connected':
                        continue
                    ipinfo = status.get('ipinfo', {})
                    ip = ipinfo.get('ip_address', '')
                    # Get priority from config
                    config = info.get('config', {})
                    priority = config.get('priority', 999)
                    # Build a display-only name. iface remains the raw
                    # NCOS value used for routing and test-engine selection.
                    product = _friendly_wan_name(uid, info)
                    if iface:
                        interfaces.append({
                            'uid': uid,
                            'iface': iface,
                            'ip': ip,
                            'state': conn_state,
                            'priority': priority,
                            'name': product
                        })
        # Sort by priority (lowest value = highest priority)
        interfaces.sort(key=lambda x: x.get('priority', 999))
        return interfaces
    except Exception as e:
        cp.log(f'Error getting WAN interfaces: {e}')
        return []


def _get_wan_interface_label(interface):
    """Resolve an interface or device UID to its friendly display name."""
    requested = str(interface or '').strip()

    try:
        devices = cp.get('status/wan/devices') or {}

        if not isinstance(devices, dict):
            return requested or 'auto'

        if not requested or requested == 'auto':
            primary = cp.get_wan_primary_device() or ''

            if primary:
                device = devices.get(primary, {})
                return _friendly_wan_name(primary, device)

            return 'Active Primary WAN'

        for uid, device in devices.items():
            if not isinstance(device, dict):
                continue

            iface = device.get('info', {}).get('iface', '')

            if requested == uid or requested == iface:
                return _friendly_wan_name(uid, device)

    except Exception as e:
        cp.log(f'Friendly WAN label lookup failed (non-fatal): {e}')

    return requested or 'auto'


def _interface_is_cellular_wan(interface):
    """Return True only when the selected WAN has cellular evidence.

    The raw interface or WAN UID remains unchanged for test selection and
    source routing. This helper only controls optional cellular telemetry.
    """
    requested = str(interface or '').strip()

    try:
        devices = cp.get('status/wan/devices') or {}

        if not isinstance(devices, dict):
            return False

        if not requested or requested == 'auto':
            requested = cp.get_wan_primary_device() or ''

        for uid, device in devices.items():
            if not isinstance(device, dict):
                continue

            iface = device.get('info', {}).get('iface', '')

            if requested == uid or requested == iface:
                return _wan_is_cellular_device(uid, device)

    except Exception as e:
        cp.log(
            f'Cellular WAN classification failed '
            f'(telemetry disabled, test unaffected): {e}'
        )

    return False


# =============================================================================
# CELLULAR DIAGNOSTICS HELPERS
# =============================================================================

# Metric names recognized on an aggregation cell, mapped to output keys.
_CA_METRIC_KEYS = {
    'BAND': 'band',
    'RFBAND': 'band',
    'BANDWIDTH': 'bandwidth',
    'CHANNEL': 'channel',
    'RFCHANNEL': 'channel',
    'RXCHANNEL': 'channel',
    'RSSI': 'rssi',
    'DBM': 'rssi',
    'RSRP': 'rsrp',
    'RSRQ': 'rsrq',
    'SINR': 'sinr',
    'PCI': 'phy_cell_id',
    'ACTIVE': 'state',
    'STATE': 'state',
    'STATUS': 'state',
}

# Confirmed on E400 / W2255: metric first, then band generation, then cell
# index. e.g. BAND_5G_SCELL0, BANDWIDTH_5G_SCELL0, SINR_5G_SCELL0,
# ACTIVE_5G_SCELL0. P/SCELL distinguishes primary from secondary.
_CA_KEY_RE = re.compile(
    r'^(?P<metric>[A-Z]+)_(?P<gen>5G|LTE|4G)_(?P<role>[SP])CELL(?P<idx>\d*)$')

# Legacy/alternate shape kept as a fallback: CA_PCC_RFBAND, CA_SCC1_SINR.
_CA_LEGACY_RE = re.compile(
    r'^CA_(?P<role>PCC|SCC)(?P<idx>\d*)_(?P<metric>[A-Z_]+)$')

# Normalized field -> candidate diagnostics keys, in priority order.
# Verified keys come first; alternates cover vendor/firmware naming drift.
_DIAG_FIELD_CANDIDATES = {
    # Carrier and service
    'carrier': ('CARRID',),
    'home_carrier': ('HOMECARRID',),
    'roaming_raw': ('ROAM',),
    'roaming_status': ('ROAMING_STATUS', 'ROAMSTATUS'),
    'carrier_status': ('CARRIER_STATUS', 'CARRIERSTATUS'),
    'service_type': ('SRVC_TYPE',),
    'service_details': ('SRVC_TYPE_DETAILS',),
    'service_display': ('SERDIS', 'SERVICE_DISPLAY'),
    # Signal (LTE / primary)
    'signal_percent': ('SS',),
    'signal_dbm': ('DBM', 'RSSI'),
    'rsrp': ('RSRP',),
    'rsrq': ('RSRQ',),
    'sinr': ('SINR',),
    'ecio': ('ECIO',),
    # LTE radio
    'rf_band': ('RFBAND',),
    'lte_bandwidth': ('LTEBANDWIDTH', 'BANDWIDTH'),
    'rf_channel': ('RFCHANNEL',),
    'rx_frequency': ('RX_FREQUENCY', 'RXFREQUENCY'),
    'tx_channel': ('TX_CHANNEL', 'TXCHANNEL'),
    'tx_frequency': ('TX_FREQUENCY', 'TXFREQUENCY'),
    # 5G NR radio. Secondary cells confirmed as BAND_5G_SCELL0 etc, so the
    # serving-cell equivalents most likely drop the _SCELLn suffix.
    'rsrp_5g': ('RSRP_5G',),
    'rsrq_5g': ('RSRQ_5G',),
    'sinr_5g': ('SINR_5G',),
    'rf_band_5g': ('BAND_5G', 'RFBAND_5G'),
    'bandwidth_5g': (
        'RFBANDWIDTH_5G',
        'BANDWIDTH_5G',
        'NR_BANDWIDTH',
        'NRBANDWIDTH',
    ),
    'rf_channel_5g': ('CHANNEL_5G', 'RFCHANNEL_5G', 'NR_RFCHANNEL'),
    'phy_cell_id_5g': ('PHY_CELL_ID_5G', 'PCI_5G'),
    # Tower / network
    'nr_cell_id': ('NR_CELL_ID',),
    'cell_id': ('CELL_ID',),
    'phy_cell_id': ('PHY_CELL_ID',),
    'tac': ('TAC', 'TRACKING_AREA_CODE'),
    'plmn': ('CUR_PLMN', 'CURRENT_PLMN'),
    'home_plmn': ('HOME_PLMN', 'HOMEPLMN'),
    'active_apn': ('ACTIVEAPN',),
    # Registration / radio state
    'emm_state': ('EMMSTATE',),
    'rrc_state': ('EMM_CONNECTION_STATE', 'RRC_STATE', 'RRCSTATE'),
    'lte_ca_state': ('LTE_CA_STATE', 'LTECA', 'LTE_CARRIER_AGGREGATION'),
    # Modem condition
    'modem_temp': ('MODEMTEMP',),
    'modem_mode': ('MODEMOPMODE',),
    'iccid': ('ICCID',),
}


def _first_present(diagnostics, candidates, is_present):
    """Return the first present value among candidate diagnostics keys."""
    try:
        for key in candidates:
            val = diagnostics.get(key)
            if is_present(val):
                return val
    except Exception:
        pass
    return None


def _scale_sinr(value):
    """Normalize a SINR reading to dB.

    Aggregation cells report SINR in tenths of a dB (187 meaning 18.7 dB)
    while the top-level SINR fields are already scaled. Cellular SINR above
    ~40 dB is not physically plausible, so treat large values as tenths.
    """
    try:
        if value is None or value == '':
            return value
        num = float(str(value).strip())
        if abs(num) > 50:
            num = num / 10.0
        # Render whole numbers without a trailing .0
        return int(num) if num == int(num) else round(num, 1)
    except (TypeError, ValueError):
        return value


def _parse_aggregation_cells(diagnostics):
    """Parse carrier-aggregation component carriers from modem diagnostics.

    Matches the confirmed NCOS key shape <METRIC>_<GEN>_<S|P>CELL<N>
    (e.g. BAND_5G_SCELL0) plus a legacy CA_PCC_*/CA_SCC1_* fallback.

    Matching is strict regex rather than substring: a loose test wrongly
    swept in unrelated keys such as ICCID, which contains "CC".

    Args:
        diagnostics: Flat diagnostics dict from status/wan/devices/{uid}.

    Returns:
        Tuple of (cells, unmatched). cells is a list of dicts each with
        'label', 'role', 'gen' and any discovered metrics, ordered primary
        first then by cell index. unmatched holds keys that matched the CA
        shape but carried an unrecognized metric name.
    """
    cells = {}
    unmatched = {}
    try:
        for raw_key, value in diagnostics.items():
            if value is None or value == '':
                continue
            key = str(raw_key).upper()
            match = _CA_KEY_RE.match(key)
            if match:
                metric = match.group('metric')
                role = 'P' if match.group('role') == 'P' else 'S'
                gen = match.group('gen')
                idx_raw = match.group('idx')

                # NCOS PCell keys are unnumbered. SCells keep their native
                # zero-based indexes: SCell0, SCell1, SCell2, ...
                if role == 'S' and not idx_raw:
                    continue

                idx = int(idx_raw or 0)
            else:
                match = _CA_LEGACY_RE.match(key)
                if not match:
                    continue
                metric = match.group('metric')
                role = 'P' if match.group('role') == 'PCC' else 'S'
                gen = '5G'
                idx = int(match.group('idx') or 0)

            out_key = _CA_METRIC_KEYS.get(metric)
            if not out_key:
                unmatched[str(raw_key)] = value
                continue
            cell = cells.setdefault((role, gen, idx), {'role': role, 'gen': gen})
            cell[out_key] = value

        service_mode = _determine_service_mode(diagnostics)

        ordered = []
        # Primary first, then secondary cells in index order.
        for cell_key in sorted(cells, key=lambda k: (k[0] != 'P', k[2])):
            role, gen, idx = cell_key
            entry = dict(cells[cell_key])

            # Determine radio type from the actual reported band.
            # The "_5G_" field family may contain an LTE PCell on NSA.
            band_rat, _ = _parse_band_name(entry.get('band'))

            if band_rat == 'NR':
                entry['gen'] = '5G'
            elif band_rat == 'LTE':
                entry['gen'] = 'LTE'
            else:
                entry['gen'] = gen

            display_radio = (
                '5G NR'
                if entry.get('gen') == '5G'
                else entry.get('gen')
            )

            if role == 'P':
                if (
                    service_mode == '5G NSA'
                    and entry.get('gen') == 'LTE'
                ):
                    entry['label'] = 'PCell (LTE Anchor)'
                else:
                    entry['label'] = 'PCell (Primary)'
            else:
                entry['label'] = f'SCell{idx} ({display_radio})'

            # Aggregation SINR arrives in tenths of a dB
            if 'sinr' in entry:
                entry['sinr'] = _scale_sinr(entry['sinr'])
            ordered.append(entry)
        return ordered, unmatched
    except Exception as e:
        cp.log(f'Aggregation parse error: {e}')
        return [], {}


def _bandwidth_mhz(value):
    """Extract a numeric MHz value from a bandwidth string, or None.

    Handles forms like '20', '20 MHz', 'LTE BW 20MHz', '100 MHz'.
    """
    try:
        if value is None:
            return None
        text = str(value).upper().replace('MHZ', ' ')
        number = ''
        seen_digit = False
        for ch in text:
            if ch.isdigit() or (ch == '.' and seen_digit):
                number += ch
                seen_digit = True
            elif seen_digit:
                break
        if not number:
            return None
        return float(number)
    except Exception:
        return None


def _collect_cellular_snapshot(interface, include_active_carriers=False):
    """Collect normalized modem diagnostics for a cellular interface.

    Args:
        interface: Interface name or cellular device UID.
        include_active_carriers: When True, include the normalized v2.5
            current active-carrier snapshot using the same diagnostics read.

    Returns:
        Dict of normalized cellular diagnostics, or None if the interface
        is not cellular or collection fails.
    """
    try:
        if not interface or interface == 'auto':
            return None

        devices = cp.get('status/wan/devices')
        if not devices or not isinstance(devices, dict):
            return None

        # Find the device matching this interface (match on uid or info.iface)
        matched_uid = None
        matched_dev = None
        for uid, dev in devices.items():
            if isinstance(dev, dict):
                iface = dev.get('info', {}).get('iface', '')
                if uid == interface or iface == interface:
                    matched_uid = uid
                    matched_dev = dev
                    break

        if not matched_dev:
            return None

        # An mdm-* identity alone is not proof of cellular service.
        # Satellite WANs use the non-cellular reporting path.
        if not _wan_is_cellular_device(matched_uid, matched_dev):
            return None

        # Read diagnostics from the matched device
        diagnostics = matched_dev.get('diagnostics', {})
        if not diagnostics or not isinstance(diagnostics, dict):
            return None

        # Values to treat as absent (case-insensitive, whitespace-trimmed)
        _empty_strings = {'', 'none', 'n/a', 'unknown', '--'}

        def _is_present(val):
            """Return True if val should be included in the snapshot."""
            if val is None:
                return False
            if isinstance(val, str):
                return val.strip().lower() not in _empty_strings
            return True  # Numeric 0 and other types are retained

        snapshot = {
            'device_uid': matched_uid,
        }

        # Status fields (signal strength score, health, registration)
        status = matched_dev.get('status', {})
        for key in ('signal_strength', 'cellular_health_score',
                    'cellular_health_category', 'connection_state'):
            val = status.get(key)
            if _is_present(val):
                snapshot[key] = val

        # Map normalized output keys to candidate NCOS diagnostics keys.
        # Several logical fields are exposed under different key names
        # depending on modem vendor and firmware, so each entry lists the
        # candidates in priority order and the first present value wins.
        for out_key, candidates in _DIAG_FIELD_CANDIDATES.items():
            val = _first_present(diagnostics, candidates, _is_present)
            if val is not None:
                snapshot[out_key] = val

        service_mode = _determine_service_mode(diagnostics)

        if service_mode:
            snapshot['service_mode'] = service_mode

        # Tower identity follows the serving primary radio.
        #
        # LTE / NSA:
        #   CELL_ID + PHY_CELL_ID identify the LTE serving/anchor cell.
        #
        # 5G SA:
        #   Prefer NR_CELL_ID + PHY_CELL_ID_5G because there is no LTE
        #   anchor. Fall back to the generic fields for modem/firmware
        #   variants that do not expose the NR-specific keys.
        if service_mode == '5G SA':
            if _is_present(snapshot.get('nr_cell_id')):
                snapshot['cell_id'] = snapshot['nr_cell_id']

            if _is_present(snapshot.get('phy_cell_id_5g')):
                snapshot['phy_cell_id'] = snapshot['phy_cell_id_5g']

        # Carrier aggregation
        cells, unmatched = _parse_aggregation_cells(diagnostics)

        service_mode = (
            snapshot.get('service_mode')
            or _determine_service_mode(diagnostics)
        )

        # Explicit NCOS PCell telemetry is preferred. Some platforms/states
        # expose only SCells, so synthesize a primary only when needed.
        if cells and not any(c.get('role') == 'P' for c in cells):
            primary = None

            if service_mode == '5G SA':
                # Standalone has no LTE anchor. Generic RFBAND may itself
                # contain the NR serving band.
                primary_band = (
                    snapshot.get('rf_band_5g')
                    or snapshot.get('rf_band')
                )

                primary_rat, _ = _parse_band_name(primary_band)

                if primary_rat == 'NR':
                    primary_bandwidth = snapshot.get('bandwidth_5g')

                    if not _is_present(primary_bandwidth):
                        primary_bandwidth = _first_present(
                            diagnostics,
                            ('RFBANDWIDTH',),
                            _is_present
                        )

                    primary = {
                        'label': 'PCell (Primary)',
                        'role': 'P',
                        'gen': '5G',
                        'band': primary_band,
                        'bandwidth': primary_bandwidth,
                        'channel': (
                            snapshot.get('rf_channel_5g')
                            or snapshot.get('rf_channel')
                        ),
                        'rssi': snapshot.get('rssi_5g'),
                        'rsrp': snapshot.get('rsrp_5g'),
                        'rsrq': snapshot.get('rsrq_5g'),
                        'sinr': snapshot.get('sinr_5g'),
                        'phy_cell_id': snapshot.get(
                            'phy_cell_id_5g'
                        ),
                    }

            else:
                primary_band = snapshot.get('rf_band')
                primary_rat, _ = _parse_band_name(primary_band)

                # Never create an LTE anchor from an NR n-band merely
                # because that n-band appeared in generic RFBAND.
                if primary_rat == 'LTE':
                    primary = {
                        'label': (
                            'PCell (LTE Anchor)'
                            if service_mode == '5G NSA'
                            else 'PCell (Primary)'
                        ),
                        'role': 'P',
                        'gen': 'LTE',
                        'band': primary_band,
                        'bandwidth': snapshot.get('lte_bandwidth'),
                        'channel': snapshot.get('rf_channel'),
                        'rssi': snapshot.get('signal_dbm'),
                        'rsrp': snapshot.get('rsrp'),
                        'rsrq': snapshot.get('rsrq'),
                        'sinr': snapshot.get('sinr'),
                        'phy_cell_id': snapshot.get(
                            'phy_cell_id'
                        ),
                    }

            if primary:
                primary = {
                    key: value
                    for key, value in primary.items()
                    if _is_present(value)
                }

                if primary.get('band'):
                    cells.insert(0, primary)

        if cells:
            snapshot['aggregation'] = cells
        if unmatched:
            # Surfaced in the UI so unrecognized CA keys are never silently lost
            snapshot['aggregation_unmatched'] = unmatched

        # Total aggregated bandwidth is the strongest single predictor of the
        # throughput ceiling, so derive it from whatever carriers we found.
        widths = []
        for cell in cells:
            mhz = _bandwidth_mhz(cell.get('bandwidth'))
            if mhz is not None:
                widths.append(mhz)

        if not widths:
            for key in ('lte_bandwidth', 'bandwidth_5g'):
                mhz = _bandwidth_mhz(snapshot.get(key))
                if mhz is not None:
                    widths.append(mhz)

        if widths:
            total = sum(widths)
            snapshot['aggregate_bandwidth_mhz'] = round(total, 1)
            snapshot['carrier_count'] = len(widths)

        # Reuse the v2.5 Active Carrier parser against the SAME diagnostics
        # object when current carrier state is requested. This avoids a
        # second status/wan/devices read and keeps page-load telemetry
        # consistent with the test-time collector.
        if include_active_carriers:
            snapshot['active_carriers'] = _carrier_snapshot(diagnostics)

        return snapshot if snapshot else None
    except Exception as e:
        cp.log(f'Cellular snapshot error: {e}')
        return None


# =============================================================================
# ACTIVE CARRIER TELEMETRY (v2.5.0)
# =============================================================================

def _parse_band_name(band_str):
    """Extract band number and determine RAT from a band string.

    RAT classification is based on band naming convention:
    - "Band nXX" or "nXX" = NR
    - "Band XX" or "BXX" = LTE

    Returns:
        Tuple of (rat, band_str_cleaned). rat is 'NR' or 'LTE'.
    """
    if not band_str:
        return None, None
    s = str(band_str).strip()
    # Check for NR band (n prefix)
    if re.match(r'(?i)^(band\s+)?n\d+', s):
        return 'NR', s
    # LTE band
    if re.match(r'(?i)^(band\s+)?\d+|^B\d+', s):
        return 'LTE', s
    return None, s


def _parse_bandwidth_value(bw_str):
    """Parse bandwidth string to numeric MHz value.

    Returns float MHz or 0 if unparseable. Preserves 0 MHz explicitly.
    """
    if bw_str is None:
        return None
    s = str(bw_str).strip()
    if not s:
        return None
    # Extract numeric value
    m = re.search(r'(\d+(?:\.\d+)?)', s)
    if m:
        return float(m.group(1))
    return None


def _normalize_carrier(role, rat, band, bandwidth_mhz, channel, active,
                       rsrp, rsrq, sinr, pci):
    """Build a normalized carrier dict."""
    carrier = {
        'role': role,
        'rat': rat,
        'band': band,
        'bandwidth_mhz': bandwidth_mhz,
        'channel': channel,
        'active': active,
        'rsrp': rsrp,
        'rsrq': rsrq,
        'sinr': sinr,
        'pci': pci,
    }
    return carrier


def _carrier_identity(carrier):
    """Return normalized carrier identity fields for deduplication."""
    rat = str(carrier.get('rat') or '').strip().upper()

    band = str(carrier.get('band') or '').strip().upper()
    band = re.sub(
        r'^BAND\s+',
        '',
        band,
        flags=re.IGNORECASE
    ).strip()

    channel = carrier.get('channel')
    if channel is not None:
        channel = str(channel).strip()
        if not channel:
            channel = None

    bandwidth = carrier.get('bandwidth_mhz')

    return rat, band, channel, bandwidth


def _carrier_role_rank(carrier):
    """Rank how explicitly NCOS identifies a serving-cell role.

    Higher-ranked roles are preferred when multiple NCOS diagnostics
    representations describe the same physical carrier.
    """
    role = str(carrier.get('role') or '').strip().lower()

    # Explicit primary serving cell.
    if role == 'pcell':
        return 40

    # Explicit indexed secondary serving cells from either known schema.
    if role.startswith('scell') or role.startswith('lte_scell'):
        return 30

    # Direct NR diagnostics identify a real NR carrier but do not provide
    # the same explicit serving-cell relationship as PCELL/SCELL fields.
    if role == 'nr_primary':
        return 20

    return 10


def _merge_carrier_records(existing, incoming):
    """Merge duplicate records while preserving richer diagnostics.

    Prefer the record with the strongest explicit NCOS serving-cell role,
    then fill any missing diagnostics from the alternate representation.
    This keeps deduplication order-independent while preserving PCell/SCell
    information when the same carrier is also exposed through direct fields.
    """
    if _carrier_role_rank(incoming) > _carrier_role_rank(existing):
        merged = dict(incoming)
        alternate = existing
    else:
        merged = dict(existing)
        alternate = incoming

    for key, value in alternate.items():
        current = merged.get(key)

        if (current is None or current == '') and value is not None:
            merged[key] = value

    return merged


def _dedupe_active_carriers(carriers):
    """Deduplicate carriers exposed through multiple NCOS schemas.

    Deduplication is order-independent.

    Carriers are first grouped by RAT + band + bandwidth. Within each group:

    - Records with the same explicit channel are duplicates and are merged.
    - Records with different explicit channels are always preserved.
    - A channel-less record may merge with an explicit-channel record only
      when exactly one explicit channel exists in that group.
    - If multiple explicit channels exist, channel-less records are preserved
      because their physical carrier identity is ambiguous.
    """
    active_carriers = [
        carrier for carrier in carriers
        if carrier.get('active')
    ]

    groups = {}

    for carrier in active_carriers:
        rat, band, channel, bandwidth = _carrier_identity(carrier)
        base_key = (rat, band, bandwidth)

        if base_key not in groups:
            groups[base_key] = []

        groups[base_key].append(carrier)

    deduped = []

    for group in groups.values():
        explicit_by_channel = {}
        channel_less = []

        # First resolve all records that explicitly report a channel.
        for carrier in group:
            rat, band, channel, bandwidth = _carrier_identity(carrier)

            if channel is None:
                channel_less.append(carrier)
                continue

            if channel in explicit_by_channel:
                explicit_by_channel[channel] = _merge_carrier_records(
                    explicit_by_channel[channel],
                    carrier
                )
            else:
                explicit_by_channel[channel] = carrier

        explicit_records = list(explicit_by_channel.values())

        if len(explicit_records) == 1:
            # Only one explicit physical carrier exists for this
            # RAT/band/bandwidth combination. Channel-less representations
            # can therefore be safely merged into it.
            merged = explicit_records[0]

            for carrier in channel_less:
                merged = _merge_carrier_records(
                    merged,
                    carrier
                )

            deduped.append(merged)

        elif len(explicit_records) > 1:
            # Multiple physical carriers share the same RAT/band/bandwidth.
            # Preserve every explicit channel. A channel-less PCell record
            # can still be safely merged when exactly one explicit PCell
            # exists in the group; its role identifies the serving primary.
            # Other channel-less records remain separate because their
            # physical carrier identity is ambiguous.
            explicit_pcells = [
                carrier for carrier in explicit_records
                if carrier.get('role') == 'pcell'
            ]

            remaining_channel_less = []

            for carrier in channel_less:
                if (
                    carrier.get('role') == 'pcell'
                    and len(explicit_pcells) == 1
                ):
                    target = explicit_pcells[0]
                    merged = _merge_carrier_records(
                        target,
                        carrier
                    )

                    target_index = explicit_records.index(target)
                    explicit_records[target_index] = merged
                    explicit_pcells[0] = merged
                else:
                    remaining_channel_less.append(carrier)

            deduped.extend(explicit_records)

            if remaining_channel_less:
                merged_missing = remaining_channel_less[0]

                for carrier in remaining_channel_less[1:]:
                    merged_missing = _merge_carrier_records(
                        merged_missing,
                        carrier
                    )

                deduped.append(merged_missing)

        else:
            # No explicit channel is available. Multiple representations with
            # the same RAT/band/bandwidth cannot be distinguished, so treat
            # them as duplicate views of one carrier.
            if channel_less:
                merged = channel_less[0]

                for carrier in channel_less[1:]:
                    merged = _merge_carrier_records(
                        merged,
                        carrier
                    )

                deduped.append(merged)

    return deduped


def _parse_active_carriers(diagnostics):
    """Parse all active serving carriers from modem diagnostics.

    Discovers carriers from all known field families without
    model/carrier-specific branching. Deduplicates carriers that appear
    in multiple field families simultaneously.

    Args:
        diagnostics: Flat dict of modem diagnostic fields.

    Returns:
        List of normalized carrier dicts, deduplicated.
    """
    if not diagnostics or not isinstance(diagnostics, dict):
        return []

    carriers = []
    service_mode = _determine_service_mode(diagnostics)

    def _get(key):
        v = diagnostics.get(key)
        if v is None or str(v).strip().lower() in ('', 'none', 'n/a', 'unknown', '--'):
            return None
        return v

    def _is_active(val):
        """Check if an ACTIVE field indicates the carrier is active."""
        if val is None:
            return True  # No active field means assume active
        s = str(val).strip().lower()
        return s in ('active', '1', 'true', 'yes')

    # --- Family A: Generic serving-radio fields ---

    rfband = _get('RFBAND')

    if rfband:
        rat, band = _parse_band_name(rfband)

        if rat:
            if rat == 'NR':
                bw = _parse_bandwidth_value(
                    _get('RFBANDWIDTH')
                    or _get('RFBANDWIDTH_5G')
                )

                role = (
                    'pcell'
                    if service_mode == '5G SA'
                    else 'nr_primary'
                )

                rsrp = _get('RSRP_5G')
                rsrq = _get('RSRQ_5G')
                sinr = _get('SINR_5G')
                pci = _get('PHY_CELL_ID_5G')

            else:
                bw = _parse_bandwidth_value(
                    _get('LTEBANDWIDTH')
                )

                role = 'pcell'
                rsrp = _get('RSRP')
                rsrq = _get('RSRQ')
                sinr = _get('SINR')
                pci = _get('PHY_CELL_ID')

            carriers.append(_normalize_carrier(
                role=role,
                rat=rat,
                band=rfband,
                bandwidth_mhz=bw,
                channel=_get('RFCHANNEL'),
                active=True,
                rsrp=rsrp,
                rsrq=rsrq,
                sinr=sinr,
                pci=pci
            ))

    # --- Family B: Direct NR fields ---
    rfband_5g = _get('RFBAND_5G')
    if rfband_5g:
        rat, band = _parse_band_name(rfband_5g)
        if rat:
            bw = _parse_bandwidth_value(_get('RFBANDWIDTH_5G'))
            carriers.append(_normalize_carrier(
                role=(
                    'pcell'
                    if service_mode == '5G SA' and rat == 'NR'
                    else 'nr_primary'
                ), rat=rat, band=rfband_5g,
                bandwidth_mhz=bw,
                channel=_get('RFCHANNEL_5G'),
                active=True,
                rsrp=_get('RSRP_5G'), rsrq=_get('RSRQ_5G'),
                sinr=_get('SINR_5G'), pci=_get('PHY_CELL_ID_5G')
            ))

    # --- Family C: Indexed PCELL/SCELL ---
    # BAND_5G_PCELL, BANDWIDTH_5G_PCELL, etc.
    pcell_band = _get('BAND_5G_PCELL')
    if pcell_band:
        rat, band = _parse_band_name(pcell_band)
        if rat:
            bw = _parse_bandwidth_value(_get('BANDWIDTH_5G_PCELL'))
            active_val = _get('ACTIVE_5G_PCELL')
            carriers.append(_normalize_carrier(
                role='pcell', rat=rat, band=pcell_band,
                bandwidth_mhz=bw,
                channel=_get('CHANNEL_5G_PCELL'),
                active=_is_active(active_val),
                rsrp=_get('RSRP_5G_PCELL'), rsrq=_get('RSRQ_5G_PCELL'),
                sinr=_get('SINR_5G_PCELL'), pci=None
            ))

    # Discover indexed _5G_ secondary cells from keys actually returned
    # by NCOS. Do not assume contiguous indexes or a maximum SCELL number.
    scell_indexes = set()
    for raw_key in diagnostics:
        match = re.match(r'^BAND_5G_SCELL(\d+)$', str(raw_key).upper())
        if match:
            scell_indexes.add(int(match.group(1)))

    for scell_idx in sorted(scell_indexes):
        band_val = _get(f'BAND_5G_SCELL{scell_idx}')
        if band_val is None:
            continue

        rat, band = _parse_band_name(band_val)
        if not rat:
            continue

        bw = _parse_bandwidth_value(
            _get(f'BANDWIDTH_5G_SCELL{scell_idx}'))
        active_val = _get(f'ACTIVE_5G_SCELL{scell_idx}')

        carriers.append(_normalize_carrier(
            role=f'scell{scell_idx}',
            rat=rat,
            band=band_val,
            bandwidth_mhz=bw,
            channel=_get(f'CHANNEL_5G_SCELL{scell_idx}'),
            active=_is_active(active_val),
            rsrp=_get(f'RSRP_5G_SCELL{scell_idx}'),
            rsrq=_get(f'RSRQ_5G_SCELL{scell_idx}'),
            sinr=_get(f'SINR_5G_SCELL{scell_idx}'),
            pci=None
        ))

    # --- Family D: Generic LTE secondary-cell family ---
    # Discover BAND_SCELL<n> keys directly so sparse indexes are supported
    # and no arbitrary maximum carrier number is imposed.
    lte_scell_indexes = set()
    for raw_key in diagnostics:
        match = re.match(r'^BAND_SCELL(\d+)$', str(raw_key).upper())
        if match:
            lte_scell_indexes.add(int(match.group(1)))

    for lte_scell_idx in sorted(lte_scell_indexes):
        band_val = _get(f'BAND_SCELL{lte_scell_idx}')
        if band_val is None:
            continue

        rat, band = _parse_band_name(band_val)
        if not rat:
            continue

        active_val = _get(f'ACTIVE_SCELL{lte_scell_idx}')
        if not _is_active(active_val):
            continue

        bw = _parse_bandwidth_value(
            _get(f'BANDWIDTH_SCELL{lte_scell_idx}'))

        carriers.append(_normalize_carrier(
            role=f'lte_scell{lte_scell_idx}',
            rat=rat,
            band=band_val,
            bandwidth_mhz=bw,
            channel=_get(f'CHANNEL_SCELL{lte_scell_idx}'),
            active=True,
            rsrp=None,
            rsrq=None,
            sinr=None,
            pci=None
        ))

    # --- Deduplication ---
    # Multiple NCOS schemas may expose the same physical serving carrier.
    return _dedupe_active_carriers(carriers)


def _determine_service_mode(diagnostics):
    """Determine user-friendly connection mode from diagnostics.

    Uses SRVC_TYPE / SRVC_TYPE_DETAILS to distinguish LTE, 5G NSA, 5G SA.
    Does not rely solely on MODEMSYSMODE because some NSA devices report
    MODEMSYSMODE=LTE even when on 5G NSA.

    Returns:
        String like 'LTE', '5G NSA', '5G SA', or '' if unknown.
    """
    if not diagnostics:
        return ''
    try:
        srvc = str(diagnostics.get('SRVC_TYPE', '') or '').upper()
        details = str(diagnostics.get('SRVC_TYPE_DETAILS', '') or '').upper()
        sysmode = str(diagnostics.get('MODEMSYSMODE', '') or '').upper()
        serdis = str(diagnostics.get('SERDIS', '') or '').upper()

        # Check for 5G SA first
        if 'SA' in details and 'NSA' not in details:
            return '5G SA'
        if '5G-SA' in srvc or '5G SA' in srvc:
            return '5G SA'
        if 'NR5G-SA' in serdis:
            return '5G SA'

        # Check for 5G NSA
        if 'NSA' in details or 'NR' in details:
            return '5G NSA'
        if '5G' in srvc or 'NR' in srvc:
            return '5G NSA'
        if 'ENDC' in details or 'EN-DC' in details:
            return '5G NSA'
        if 'NR5G' in serdis or '5G' in serdis:
            return '5G NSA'
        if sysmode == 'NR5G-NSA' or 'NR' in sysmode:
            return '5G NSA'

        # LTE
        if 'LTE' in srvc or 'LTE' in sysmode or 'LTE' in serdis:
            return 'LTE'

        return ''
    except Exception:
        return ''


def _build_carrier_summary(carriers):
    """Build a summary of active carriers.

    Returns dict with:
        carrier_count: int
        bands: str (e.g. 'B66 + n41 + n41')
        bandwidth_mhz: float (sum of >0 MHz carriers)
        zero_mhz_count: int (carriers reporting 0 MHz)
    """
    if not carriers:
        return {
            'carrier_count': 0,
            'bands': '',
            'bandwidth_mhz': 0,
            'zero_mhz_count': 0
        }

    bands = []
    total_bw = 0.0
    zero_count = 0

    for c in carriers:
        # Format band name compactly.
        # Examples:
        #   "Band 66"  -> "B66"
        #   "B66"      -> "B66"
        #   "Band n41" -> "n41"
        #   "n41"      -> "n41"
        band_str = str(c.get('band') or '').strip()
        band_short = re.sub(
            r'^Band\s+',
            '',
            band_str,
            flags=re.IGNORECASE
        ).strip()

        if re.match(r'(?i)^n\d+', band_short):
            band_short = 'n' + band_short[1:]
        elif re.match(r'(?i)^b\d+', band_short):
            band_short = 'B' + band_short[1:]
        elif re.match(r'^\d+', band_short):
            band_short = 'B' + band_short

        bands.append(band_short or '?')

        bw = c.get('bandwidth_mhz')
        if bw is not None and bw > 0:
            total_bw += bw
        elif bw is not None and bw == 0:
            zero_count += 1
        # None bandwidth: carrier exists but BW unknown
        elif bw is None:
            pass

    return {
        'carrier_count': len(carriers),
        'bands': ' + '.join(bands),
        'bandwidth_mhz': round(total_bw, 1),
        'zero_mhz_count': zero_count
    }


def _serving_cell_snapshot(diagnostics):
    """Normalize primary serving-cell identity for one diagnostics poll."""
    if not diagnostics or not isinstance(diagnostics, dict):
        return {}

    empty = {'', 'none', 'n/a', 'unknown', '--'}

    def present(value):
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip().lower() not in empty
        return True

    def first(*keys):
        return _first_present(diagnostics, keys, present)

    service_mode = _determine_service_mode(diagnostics)

    if service_mode == '5G SA':
        cell_id = first('NR_CELL_ID', 'CELL_ID')
        pci = first('PHY_CELL_ID_5G', 'PCI_5G', 'PHY_CELL_ID')
        band = first('BAND_5G', 'RFBAND_5G', 'RFBAND')
        channel = first(
            'CHANNEL_5G',
            'RFCHANNEL_5G',
            'NR_RFCHANNEL',
            'RFCHANNEL'
        )
        source = 'NR'
    else:
        cell_id = first('CELL_ID')
        pci = first('PHY_CELL_ID')
        band = first('RFBAND')
        channel = first('RFCHANNEL')
        source = 'LTE'

    serving = {
        'service_mode': service_mode,
        'cell_id_source': source
    }

    values = {
        'cell_id': cell_id,
        'plmn': first('CUR_PLMN', 'CURRENT_PLMN'),
        'tac': first('TAC', 'TRACKING_AREA_CODE'),
        'pci': pci,
        'band': band,
        'channel': channel,
        'carrier': first('CARRID'),
    }

    for key, value in values.items():
        if present(value):
            serving[key] = value

    return serving


def _serving_cell_snapshot_signature(snapshot):
    """Return fields that identify meaningful serving-cell changes."""
    if not snapshot or not isinstance(snapshot, dict):
        return ()

    serving = snapshot.get('serving_cell')

    if not isinstance(serving, dict):
        return ()

    return (
        str(serving.get('cell_id_source') or '').strip().upper(),
        str(serving.get('cell_id') or '').strip(),
        str(serving.get('plmn') or '').strip(),
        str(serving.get('tac') or '').strip(),
        str(serving.get('pci') or '').strip(),
    )


def _carrier_snapshot(diagnostics):
    """Take a complete carrier and serving-cell snapshot."""
    carriers = _parse_active_carriers(diagnostics)
    service_mode = _determine_service_mode(diagnostics)
    summary = _build_carrier_summary(carriers)

    return {
        'service_mode': service_mode,
        'serving_cell': _serving_cell_snapshot(diagnostics),
        'carriers': carriers,
        'carrier_count': summary['carrier_count'],
        'bands': summary['bands'],
        'bandwidth_mhz': summary['bandwidth_mhz'],
        'zero_mhz_count': summary['zero_mhz_count'],
    }


def _carrier_snapshot_signature(snapshot):
    """Return stable serving-carrier identities for change detection.

    RF measurements such as RSRP/RSRQ/SINR are intentionally excluded so
    normal signal fluctuations do not create Carrier Activity transitions.
    """
    if not snapshot:
        return ()

    identities = []

    for carrier in snapshot.get('carriers', []):
        rat, band, channel, bandwidth = _carrier_identity(carrier)

        identities.append((
            rat,
            band,
            channel or '',
            bandwidth,
        ))

    return tuple(sorted(
        identities,
        key=lambda item: (
            item[0],
            item[1],
            item[2],
            -1 if item[3] is None else item[3],
        )
    ))


def _snapshots_differ(a, b):
    """Determine whether serving-carrier configuration meaningfully changed.

    Meaningful changes include service mode, carrier identity/channel,
    carrier count, band, reported bandwidth, or explicit 0 MHz state.

    Routine RF measurement changes are intentionally ignored.
    """
    if not a or not b:
        return True

    if a.get('service_mode') != b.get('service_mode'):
        return True

    if (
        _serving_cell_snapshot_signature(a)
        != _serving_cell_snapshot_signature(b)
    ):
        return True

    if a.get('carrier_count') != b.get('carrier_count'):
        return True

    if a.get('bands') != b.get('bands'):
        return True

    if a.get('bandwidth_mhz') != b.get('bandwidth_mhz'):
        return True

    if a.get('zero_mhz_count') != b.get('zero_mhz_count'):
        return True

    if _carrier_snapshot_signature(a) != _carrier_snapshot_signature(b):
        return True

    return False


def _get_modem_diagnostics_for_interface(interface):
    """Get raw modem diagnostics dict for a cellular interface.

    Args:
        interface: Interface name or device UID.

    Returns:
        Tuple of (diagnostics_dict, device_uid) or (None, None).
    """
    try:
        if not interface or interface == 'auto':
            return None, None

        devices = cp.get('status/wan/devices')
        if not devices or not isinstance(devices, dict):
            return None, None

        for uid, dev in devices.items():
            if not isinstance(dev, dict):
                continue
            iface = dev.get('info', {}).get('iface', '')
            if uid == interface or iface == interface:
                # Confirm cellular
                info_type = dev.get('info', {}).get('type', '')
                if not (uid.startswith('mdm-') or info_type == 'mdm'):
                    return None, None
                diag = dev.get('diagnostics', {})
                if diag and isinstance(diag, dict):
                    return diag, uid
                return None, None
        return None, None
    except Exception as e:
        cp.log(f'Error getting modem diagnostics: {e}')
        return None, None


def _canonical_serving_cell_id(value):
    """Normalize NCOS decimal + hex serving-cell formatting."""
    if value is None:
        return ''

    value = str(value).strip()

    if not value:
        return ''

    match = re.match(
        r'^(\d+)\s*\(0x[0-9a-f]+\)$',
        value,
        flags=re.IGNORECASE
    )

    return match.group(1) if match else value


def _serving_cell_identity_key(cell):
    """Return stable primary-cell identity or None when unidentified."""
    if not isinstance(cell, dict):
        return None

    cell_id = _canonical_serving_cell_id(
        cell.get('cell_id')
    )

    if not cell_id:
        return None

    return (
        str(
            cell.get('cell_id_source')
            or ''
        ).strip().upper(),
        str(
            cell.get('plmn')
            or ''
        ).strip(),
        cell_id,
    )


def _traffic_serving_cell_handoff_summary(
    download_activity,
    upload_activity,
):
    """Summarize proven serving-cell transitions during active traffic.

    Unknown/missing identity never bridges two known cells into an invented
    handoff. A Download -> Upload boundary change is preserved separately
    because its exact transition second is not known.
    """
    result = {
        'start_cell': None,
        'end_cell': None,
        'handoffs': [],
    }

    previous_phase_last = None

    for phase_name, activity in (
        ('download', download_activity),
        ('upload', upload_activity),
    ):
        if not isinstance(activity, dict):
            continue

        timeline = activity.get('timeline')

        if not isinstance(timeline, list) or not timeline:
            continue

        observations = []

        for state in timeline:
            if not isinstance(state, dict):
                continue

            cell = state.get('serving_cell')

            if not isinstance(cell, dict):
                cell = {}

            observations.append({
                'elapsed_s': state.get('elapsed_s', 0),
                'cell': dict(cell),
                'key': _serving_cell_identity_key(cell),
            })

        if not observations:
            continue

        first_known = next(
            (
                item
                for item in observations
                if item['key'] is not None
            ),
            None
        )

        last_known = next(
            (
                item
                for item in reversed(observations)
                if item['key'] is not None
            ),
            None
        )

        if (
            result['start_cell'] is None
            and first_known is not None
        ):
            result['start_cell'] = dict(
                first_known['cell']
            )

        # Only the actual first phase observation can prove a phase-boundary
        # transition. Do not skip an Unknown state and infer a change.
        phase_first = observations[0]

        if (
            previous_phase_last is not None
            and phase_first['key'] is not None
            and previous_phase_last['key']
                != phase_first['key']
        ):
            result['handoffs'].append({
                'phase': phase_name,
                'elapsed_s': None,
                'phase_boundary': True,
                'from': dict(
                    previous_phase_last['cell']
                ),
                'to': dict(
                    phase_first['cell']
                ),
            })

        for index in range(
            1,
            len(observations)
        ):
            previous = observations[index - 1]
            current = observations[index]

            if (
                previous['key'] is None
                or current['key'] is None
            ):
                continue

            if previous['key'] == current['key']:
                continue

            result['handoffs'].append({
                'phase': phase_name,
                'elapsed_s': current.get(
                    'elapsed_s',
                    0
                ),
                'phase_boundary': False,
                'from': dict(previous['cell']),
                'to': dict(current['cell']),
            })

        if last_known is not None:
            result['end_cell'] = dict(
                last_known['cell']
            )

            previous_phase_last = last_known

    return result


def _classify_post_test_stability(
    start_cell,
    end_cell,
    checks,
):
    """Classify three post-test serving-cell observations conservatively."""
    start_key = _serving_cell_identity_key(
        start_cell
    )

    end_key = _serving_cell_identity_key(
        end_cell
    )

    identified = []

    for check in checks:
        if not isinstance(check, dict):
            continue

        key = _serving_cell_identity_key(
            check.get('serving_cell')
        )

        if key is None:
            continue

        identified.append({
            'elapsed_s': check.get(
                'elapsed_s'
            ),
            'key': key,
        })

    result = {
        'status': 'inconclusive',
        'checks_requested': len(checks),
        'checks_identifiable': len(identified),
        'reverted_at_s': None,
    }

    # We deliberately require all three +2/+4/+6 checks for a firm
    # persistence/reversion/continued-handoff conclusion.
    if (
        len(checks) != 3
        or len(identified) != 3
    ):
        return result

    keys = [
        item['key']
        for item in identified
    ]

    unique_keys = set(keys)

    if (
        end_key is not None
        and all(
            key == end_key
            for key in keys
        )
    ):
        result['status'] = 'persisted'
        return result

    if (
        start_key is not None
        and end_key is not None
        and start_key != end_key
        and all(
            key == start_key
            for key in keys
        )
    ):
        result['status'] = 'reverted'
        result['reverted_at_s'] = (
            identified[0]['elapsed_s']
        )
        return result

    if len(unique_keys) == 1:
        only_key = keys[0]

        if (
            only_key != start_key
            and only_key != end_key
        ):
            result['status'] = (
                'continued_handoff'
            )
            return result

    if len(unique_keys) > 1:
        result['status'] = 'unstable'

    return result


class CarrierTelemetryCollector:
    """Background collector for active carrier telemetry during speed tests.

    Runs in a daemon thread, polling modem diagnostics every 2 seconds.
    Stores baseline, meaningful changes, and peak configuration.
    Thread-safe and never causes the speed test to fail.
    """

    def __init__(self, interface):
        self.interface = interface
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

        # Telemetry data
        self.baseline = None
        self.changes = []  # List of (elapsed_seconds, snapshot, description)
        self.peak = None
        self.final = None

        # Populated only when active-traffic telemetry proves a serving-cell
        # handoff. These samples are deliberately separate from _samples so
        # they cannot influence Peak Observed or traffic-phase RF/config data.
        self.post_test = None

        self._last_snapshot = None
        self._start_time = None

        # Timestamped normalized carrier samples are retained throughout the
        # test so successful Download/Upload activity can be reconstructed
        # independently from setup delays, failed server ports, and retries.
        self._samples = []

        # Successful traffic windows are registered by the test engines.
        # A phase is intentionally absent until the engine confirms that
        # traffic actually ran successfully.
        self._phase_windows = {
            'download': {'start': None, 'end': None},
            'upload': {'start': None, 'end': None},
        }

    def start(self):
        """Start the telemetry collector. Call before speed test begins."""
        try:
            # Capture baseline immediately
            diag, uid = _get_modem_diagnostics_for_interface(self.interface)
            if not diag:
                cp.log('Carrier telemetry: not a cellular interface, skipping')
                return

            self.baseline = _carrier_snapshot(diag)
            self._last_snapshot = self.baseline
            self.peak = dict(self.baseline)
            self._start_time = time.monotonic()
            self._samples = [
                (
                    self._start_time,
                    self._copy_snapshot(self.baseline)
                )
            ]
            self._running = True

            self._thread = Thread(target=self._poll_loop, daemon=True)
            self._thread.start()
            cp.log(f'Carrier telemetry started: {self.baseline.get("bands", "none")} '
                   f'({self.baseline.get("carrier_count", 0)} carriers)')
        except Exception as e:
            cp.log(f'Carrier telemetry start error (non-fatal): {e}')

    def stop(self):
        """Stop polling and capture the final carrier snapshot safely."""
        try:
            self._running = False

            # Wait briefly for the polling thread to leave its sleep/poll
            # cycle so it cannot race with the final snapshot below.
            thread = self._thread
            if (
                thread
                and thread.is_alive()
                and thread is not threading.current_thread()
            ):
                thread.join(timeout=3)

            diag, uid = _get_modem_diagnostics_for_interface(
                self.interface
            )
            if diag:
                final_snapshot = _carrier_snapshot(diag)

                with self._lock:
                    self.final = final_snapshot
                    self._samples.append(
                        (
                            time.monotonic(),
                            self._copy_snapshot(final_snapshot)
                        )
                    )
                    self._update_peak(final_snapshot)

        except Exception as e:
            cp.log(
                f'Carrier telemetry final capture error (non-fatal): {e}'
            )

    def _traffic_handoff_summary(self):
        """Build traffic-only serving-cell handoff state from captured data."""
        with self._lock:
            samples = [
                (
                    sample_time,
                    self._copy_snapshot(snapshot)
                )
                for sample_time, snapshot
                in self._samples
            ]

            phase_windows = {
                phase: dict(window)
                for phase, window
                in self._phase_windows.items()
            }

        download_activity = self._build_phase_activity(
            'download',
            samples,
            phase_windows.get('download')
        )

        upload_activity = self._build_phase_activity(
            'upload',
            samples,
            phase_windows.get('upload')
        )

        return _traffic_serving_cell_handoff_summary(
            download_activity,
            upload_activity,
        )

    def collect_post_test_stability(self):
        """Conditionally sample the modem at +2/+4/+6 seconds after a handoff.

        Stable tests return immediately with no additional polling. Post-test
        observations are diagnostic only and never feed Peak Observed,
        traffic RF, carrier configuration, or throughput calculations.
        """
        try:
            summary = self._traffic_handoff_summary()

            if not summary.get('handoffs'):
                return False

            cp.log(
                'Carrier telemetry: in-test serving-cell handoff detected; '
                'checking post-test state at +2/+4/+6 seconds'
            )

            with self._lock:
                immediate_snapshot = (
                    self._copy_snapshot(self.final)
                    if self.final
                    else None
                )

            immediate = None

            if immediate_snapshot:
                immediate = {
                    'elapsed_s': 0,
                    'available': True,
                    'service_mode': immediate_snapshot.get(
                        'service_mode',
                        ''
                    ),
                    'serving_cell': dict(
                        immediate_snapshot.get(
                            'serving_cell',
                            {}
                        )
                    ),
                }

            checks = []
            started_at = time.monotonic()

            for elapsed_s in (2, 4, 6):
                target = (
                    started_at
                    + elapsed_s
                )

                remaining = (
                    target
                    - time.monotonic()
                )

                if remaining > 0:
                    time.sleep(remaining)

                diag, uid = (
                    _get_modem_diagnostics_for_interface(
                        self.interface
                    )
                )

                if not diag:
                    checks.append({
                        'elapsed_s': elapsed_s,
                        'available': False,
                        'service_mode': '',
                        'serving_cell': {},
                    })
                    continue

                snapshot = _carrier_snapshot(
                    diag
                )

                checks.append({
                    'elapsed_s': elapsed_s,
                    'available': True,
                    'service_mode': snapshot.get(
                        'service_mode',
                        ''
                    ),
                    'serving_cell': dict(
                        snapshot.get(
                            'serving_cell',
                            {}
                        )
                    ),
                })

            classification = (
                _classify_post_test_stability(
                    summary.get(
                        'start_cell'
                    ),
                    summary.get(
                        'end_cell'
                    ),
                    checks,
                )
            )

            post_test = {
                'triggered': True,
                'reason': (
                    'in_test_serving_cell_handoff'
                ),
                'window_s': 6,
                'start_cell': dict(
                    summary.get(
                        'start_cell'
                    )
                    or {}
                ),
                'end_cell': dict(
                    summary.get(
                        'end_cell'
                    )
                    or {}
                ),
                'immediate': immediate,
                'checks': checks,
                'status': classification.get(
                    'status',
                    'inconclusive'
                ),
                'checks_requested': (
                    classification.get(
                        'checks_requested',
                        3
                    )
                ),
                'checks_identifiable': (
                    classification.get(
                        'checks_identifiable',
                        0
                    )
                ),
                'reverted_at_s': (
                    classification.get(
                        'reverted_at_s'
                    )
                ),
            }

            with self._lock:
                self.post_test = post_test

            cp.log(
                'Carrier telemetry: post-test serving-cell state '
                f'{post_test["status"]} '
                f'({post_test["checks_identifiable"]}/'
                f'{post_test["checks_requested"]} identifiable checks)'
            )

            return True

        except Exception as e:
            cp.log(
                'Carrier telemetry post-test stability error '
                f'(non-fatal): {e}'
            )
            return False

    def _poll_loop(self):
        """Background polling loop — every 2 seconds."""
        while self._running:
            try:
                time.sleep(2)
                if not self._running:
                    break
                diag, uid = _get_modem_diagnostics_for_interface(
                    self.interface)
                if not diag:
                    continue

                snapshot = _carrier_snapshot(diag)
                sample_time = time.monotonic()

                with self._lock:
                    self._samples.append(
                        (
                            sample_time,
                            self._copy_snapshot(snapshot)
                        )
                    )

                    # Check for meaningful change
                    if _snapshots_differ(snapshot, self._last_snapshot):
                        elapsed = round(sample_time - self._start_time)
                        desc = self._describe_change(
                            self._last_snapshot, snapshot)
                        self.changes.append((elapsed, snapshot, desc))
                        self._last_snapshot = snapshot

                    self._update_peak(snapshot)
            except Exception as e:
                cp.log(f'Carrier telemetry poll error (non-fatal): {e}')

    def _copy_snapshot(self, snapshot):
        """Copy a normalized carrier snapshot including carrier records."""
        if not snapshot:
            return {}

        copied = dict(snapshot)
        copied['carriers'] = [
            dict(carrier)
            for carrier in snapshot.get('carriers', [])
        ]

        serving_cell = snapshot.get('serving_cell')

        if isinstance(serving_cell, dict):
            copied['serving_cell'] = dict(serving_cell)

        return copied

    def record_phase_window(self, phase, started_at, ended_at):
        """Register one successful traffic phase.

        The engine calls this only after it knows the Download or Upload
        operation actually ran successfully. Monotonic timestamps allow the
        carrier collector to reconstruct the phase retroactively, which keeps
        failed iPerf server-port attempts and Netperf startup delays out of the
        user-facing carrier timeline.

        Args:
            phase: 'download' or 'upload'.
            started_at: Monotonic time.monotonic() when successful traffic began.
            ended_at: Monotonic time.monotonic() when that traffic phase ended.

        Returns:
            True when the phase window was accepted, otherwise False.
        """
        phase = str(phase or '').strip().lower()

        if phase not in ('download', 'upload'):
            cp.log(
                f'Carrier telemetry: invalid phase window {phase!r}'
            )
            return False

        try:
            started_at = float(started_at)
            ended_at = float(ended_at)
        except (TypeError, ValueError):
            cp.log(
                f'Carrier telemetry: invalid {phase} phase timestamps'
            )
            return False

        if ended_at < started_at:
            cp.log(
                f'Carrier telemetry: rejected {phase} phase window '
                f'(end before start)'
            )
            return False

        with self._lock:
            self._phase_windows[phase] = {
                'start': started_at,
                'end': ended_at,
            }

        cp.log(
            f'Carrier telemetry: {phase} traffic window recorded '
            f'({ended_at - started_at:.1f}s)'
        )
        return True

    def _carrier_state_record(self, snapshot, elapsed_s=None):
        """Build one history-safe carrier-state record."""
        if not snapshot:
            return None

        record = {
            'service_mode': snapshot.get('service_mode', ''),
            'serving_cell': dict(
                snapshot.get('serving_cell', {})
            ),
            'carrier_count': snapshot.get('carrier_count', 0),
            'bands': snapshot.get('bands', ''),
            'bandwidth_mhz': snapshot.get('bandwidth_mhz', 0),
            'zero_mhz_count': snapshot.get('zero_mhz_count', 0),
            'carriers': [
                dict(carrier)
                for carrier in snapshot.get('carriers', [])
            ],
        }

        if elapsed_s is not None:
            record['elapsed_s'] = elapsed_s

        return record

    def _better_peak_snapshot(self, current, candidate):
        """Return the stronger peak using count, then bandwidth."""
        if not candidate:
            return current

        if not current:
            return self._copy_snapshot(candidate)

        current_count = current.get('carrier_count', 0)
        candidate_count = candidate.get('carrier_count', 0)

        current_bw = current.get('bandwidth_mhz', 0)
        candidate_bw = candidate.get('bandwidth_mhz', 0)

        if (
            candidate_count > current_count
            or (
                candidate_count == current_count
                and candidate_bw > current_bw
            )
        ):
            return self._copy_snapshot(candidate)

        return current

    def _build_phase_activity(self, phase, samples, window):
        """Reconstruct one successful Download/Upload carrier timeline.

        The phase clock begins at the successful traffic start timestamp.
        Samples collected during setup, failed ports, or retries remain
        available internally but are excluded from this user-facing timeline.

        The state at 0s is the most recent carrier snapshot at or before the
        successful traffic start. Subsequent entries are added only when the
        serving-carrier configuration meaningfully changes.
        """
        if not window:
            return None

        started_at = window.get('start')
        ended_at = window.get('end')

        if started_at is None or ended_at is None:
            return None

        try:
            started_at = float(started_at)
            ended_at = float(ended_at)
        except (TypeError, ValueError):
            return None

        if ended_at < started_at:
            return None

        ordered = sorted(samples, key=lambda item: item[0])
        if not ordered:
            return None

        # Baseline is the last known carrier state immediately before or at
        # successful traffic start. If collection began fractionally after
        # the phase start, use the first available sample instead.
        baseline_snapshot = None

        for sample_time, snapshot in ordered:
            if sample_time <= started_at:
                baseline_snapshot = snapshot
            else:
                break

        if baseline_snapshot is None:
            for sample_time, snapshot in ordered:
                if sample_time >= started_at:
                    baseline_snapshot = snapshot
                    break

        if not baseline_snapshot:
            return None

        baseline_snapshot = self._copy_snapshot(baseline_snapshot)
        timeline = [
            self._carrier_state_record(
                baseline_snapshot,
                elapsed_s=0
            )
        ]

        last_snapshot = baseline_snapshot
        phase_peak = self._copy_snapshot(baseline_snapshot)

        for sample_time, snapshot in ordered:
            if sample_time <= started_at:
                continue

            if sample_time > ended_at:
                break

            phase_peak = self._better_peak_snapshot(
                phase_peak,
                snapshot
            )

            if _snapshots_differ(snapshot, last_snapshot):
                elapsed = max(
                    0,
                    int(round(sample_time - started_at))
                )

                # Avoid duplicate timeline entries at the same displayed
                # second. If two states land in the same rounded second,
                # retain the newest state for that point in time.
                state_record = self._carrier_state_record(
                    snapshot,
                    elapsed_s=elapsed
                )

                if (
                    timeline
                    and timeline[-1].get('elapsed_s') == elapsed
                ):
                    timeline[-1] = state_record
                else:
                    timeline.append(state_record)

                last_snapshot = self._copy_snapshot(snapshot)

        return {
            'phase': phase,
            'duration_s': round(ended_at - started_at, 1),
            'baseline': self._carrier_state_record(
                baseline_snapshot
            ),
            'timeline': timeline,
            'peak': self._carrier_state_record(
                phase_peak
            ),
        }

    def _update_peak(self, snapshot):
        """Update peak if this snapshot has more/better carriers."""
        if not snapshot or not self.peak:
            return
        # Peak = greatest carrier count; tie-break on bandwidth
        snap_count = snapshot.get('carrier_count', 0)
        peak_count = self.peak.get('carrier_count', 0)
        snap_bw = snapshot.get('bandwidth_mhz', 0)
        peak_bw = self.peak.get('bandwidth_mhz', 0)

        if (snap_count > peak_count or
                (snap_count == peak_count and snap_bw > peak_bw)):
            self.peak = dict(snapshot)

    def _describe_change(self, prev, curr):
        """Generate a human-readable description of what changed."""
        parts = []
        if prev.get('service_mode') != curr.get('service_mode'):
            parts.append(curr.get('service_mode', ''))

        if (
            _serving_cell_snapshot_signature(prev)
            != _serving_cell_snapshot_signature(curr)
        ):
            previous_cell = (
                prev.get('serving_cell') or {}
            ).get('cell_id')

            current_cell = (
                curr.get('serving_cell') or {}
            ).get('cell_id')

            if previous_cell != current_cell:
                parts.append('serving cell changed')
            else:
                parts.append('serving-cell details changed')
        if prev.get('carrier_count', 0) < curr.get('carrier_count', 0):
            diff = curr['carrier_count'] - prev.get('carrier_count', 0)
            parts.append(f'+{diff} carrier' + ('s' if diff > 1 else ''))
        elif prev.get('carrier_count', 0) > curr.get('carrier_count', 0):
            diff = prev['carrier_count'] - curr.get('carrier_count', 0)
            parts.append(f'-{diff} carrier' + ('s' if diff > 1 else ''))
        if prev.get('bands') != curr.get('bands'):
            parts.append(curr.get('bands', ''))
        if prev.get('bandwidth_mhz') != curr.get('bandwidth_mhz'):
            parts.append(f'{curr.get("bandwidth_mhz", 0)} MHz')
        if curr.get('zero_mhz_count', 0) > prev.get('zero_mhz_count', 0):
            parts.append('0 MHz reported')
        return ', '.join(parts) if parts else 'configuration changed'

    def get_results(self):
        """Get collected telemetry data for storage.

        Reads collector state under the lock so the returned history data
        represents one consistent snapshot of baseline, changes, peak,
        and final state.
        """
        with self._lock:
            if not self.baseline:
                return None

            baseline = dict(self.baseline)
            peak = dict(self.peak) if self.peak else {}
            final = dict(self.final) if self.final else None
            changes = [
                (elapsed, dict(snapshot), description)
                for elapsed, snapshot, description in self.changes
            ]
            samples = [
                (
                    sample_time,
                    self._copy_snapshot(snapshot)
                )
                for sample_time, snapshot in self._samples
            ]
            phase_windows = {
                phase: dict(window)
                for phase, window in self._phase_windows.items()
            }

            post_test = None

            if isinstance(self.post_test, dict):
                post_test = {
                    'triggered': bool(
                        self.post_test.get(
                            'triggered'
                        )
                    ),
                    'reason': self.post_test.get(
                        'reason',
                        ''
                    ),
                    'window_s': self.post_test.get(
                        'window_s',
                        0
                    ),
                    'start_cell': dict(
                        self.post_test.get(
                            'start_cell',
                            {}
                        )
                    ),
                    'end_cell': dict(
                        self.post_test.get(
                            'end_cell',
                            {}
                        )
                    ),
                    'immediate': (
                        {
                            'elapsed_s': (
                                self.post_test[
                                    'immediate'
                                ].get(
                                    'elapsed_s',
                                    0
                                )
                            ),
                            'available': bool(
                                self.post_test[
                                    'immediate'
                                ].get(
                                    'available'
                                )
                            ),
                            'service_mode': (
                                self.post_test[
                                    'immediate'
                                ].get(
                                    'service_mode',
                                    ''
                                )
                            ),
                            'serving_cell': dict(
                                self.post_test[
                                    'immediate'
                                ].get(
                                    'serving_cell',
                                    {}
                                )
                            ),
                        }
                        if isinstance(
                            self.post_test.get(
                                'immediate'
                            ),
                            dict
                        )
                        else None
                    ),
                    'checks': [
                        {
                            'elapsed_s': check.get(
                                'elapsed_s'
                            ),
                            'available': bool(
                                check.get(
                                    'available'
                                )
                            ),
                            'service_mode': check.get(
                                'service_mode',
                                ''
                            ),
                            'serving_cell': dict(
                                check.get(
                                    'serving_cell',
                                    {}
                                )
                            ),
                        }
                        for check in self.post_test.get(
                            'checks',
                            []
                        )
                        if isinstance(
                            check,
                            dict
                        )
                    ],
                    'status': self.post_test.get(
                        'status',
                        'inconclusive'
                    ),
                    'checks_requested': (
                        self.post_test.get(
                            'checks_requested',
                            0
                        )
                    ),
                    'checks_identifiable': (
                        self.post_test.get(
                            'checks_identifiable',
                            0
                        )
                    ),
                    'reverted_at_s': (
                        self.post_test.get(
                            'reverted_at_s'
                        )
                    ),
                }

        download_activity = self._build_phase_activity(
            'download',
            samples,
            phase_windows.get('download')
        )

        upload_activity = self._build_phase_activity(
            'upload',
            samples,
            phase_windows.get('upload')
        )

        # Once successful traffic phases exist, the displayed Baseline should
        # describe the radio immediately before successful traffic rather than
        # the state captured when the user originally clicked Start.
        first_activity = download_activity or upload_activity

        if first_activity and first_activity.get('baseline'):
            baseline = self._copy_snapshot(
                first_activity['baseline']
            )

        # Overall Peak is the strongest carrier state observed during the
        # successful Download or Upload traffic windows. Setup/retry activity
        # does not influence the user-facing Peak.
        successful_peak = None

        for activity in (download_activity, upload_activity):
            if activity and activity.get('peak'):
                successful_peak = self._better_peak_snapshot(
                    successful_peak,
                    activity['peak']
                )

        if successful_peak:
            peak = successful_peak

        result = {
            'baseline': {
                'service_mode': baseline.get('service_mode', ''),
                'serving_cell': dict(
                    baseline.get('serving_cell', {})
                ),
                'carrier_count': baseline.get('carrier_count', 0),
                'bands': baseline.get('bands', ''),
                'bandwidth_mhz': baseline.get('bandwidth_mhz', 0),
                'zero_mhz_count': baseline.get('zero_mhz_count', 0),
                'carriers': [
                    dict(c) for c in baseline.get('carriers', [])
                ],
            },
            'peak': {
                'service_mode': peak.get('service_mode', ''),
                'serving_cell': dict(
                    peak.get('serving_cell', {})
                ),
                'carrier_count': peak.get('carrier_count', 0),
                'bands': peak.get('bands', ''),
                'bandwidth_mhz': peak.get('bandwidth_mhz', 0),
                'zero_mhz_count': peak.get('zero_mhz_count', 0),
                'carriers': [
                    dict(c) for c in peak.get('carriers', [])
                ],
            },
            'changes': [],
            'zero_mhz_reported': False,

            # Successful traffic-phase carrier activity. Each phase owns an
            # independent 0s clock and contains only meaningful carrier-state
            # transitions observed during actual successful traffic.
            'download': download_activity,
            'upload': upload_activity,

            # Captured internally for coherent post-test front-page display.
            # This is intentionally not shown as a CA End column or exported
            # as a CA End CSV field.
            'final': {
                'service_mode': final.get('service_mode', ''),
                'serving_cell': dict(
                    final.get('serving_cell', {})
                ),
                'carrier_count': final.get('carrier_count', 0),
                'bands': final.get('bands', ''),
                'bandwidth_mhz': final.get('bandwidth_mhz', 0),
                'zero_mhz_count': final.get('zero_mhz_count', 0),
            } if final else None,
        }

        if post_test:
            result['post_test'] = post_test

        # Record meaningful transitions only, not every two-second poll.
        for elapsed, snap, desc in changes:
            result['changes'].append({
                'elapsed_s': elapsed,
                'service_mode': snap.get('service_mode', ''),
                'serving_cell': dict(
                    snap.get('serving_cell', {})
                ),
                'carrier_count': snap.get('carrier_count', 0),
                'bands': snap.get('bands', ''),
                'bandwidth_mhz': snap.get('bandwidth_mhz', 0),
                'zero_mhz_count': snap.get('zero_mhz_count', 0),
                'carriers': [
                    dict(c) for c in snap.get('carriers', [])
                ],
                'description': desc,
            })

        # Preserve visibility of explicit 0 MHz serving carriers using the
        # same successful-traffic boundary as Baseline and Peak. A 0 MHz
        # state seen only during setup, a failed iPerf port, or a failed
        # Netperf attempt must not contaminate the completed test result.
        successful_activities = [
            activity
            for activity in (download_activity, upload_activity)
            if activity
        ]

        if successful_activities:
            zero_snapshots = []

            if result.get('baseline'):
                zero_snapshots.append(result['baseline'])

            for activity in successful_activities:
                zero_snapshots.extend(
                    activity.get('timeline', [])
                )

                if activity.get('peak'):
                    zero_snapshots.append(activity['peak'])
        else:
            # Compatibility fallback for older/non-phase-aware results.
            zero_snapshots = [baseline]
            zero_snapshots.extend(
                snap for _, snap, _ in changes
            )

            if final:
                zero_snapshots.append(final)

        for snap in zero_snapshots:
            if snap.get('zero_mhz_count', 0) > 0:
                result['zero_mhz_reported'] = True
                break

        return result


def _record_carrier_phase_window(phase, started_at, ended_at):
    """Safely register a successful traffic window with carrier telemetry.

    Test engines call this only after they know a Download or Upload phase
    actually transferred data successfully. Carrier telemetry is optional
    and must never cause the speed test itself to fail.
    """
    global _active_carrier_collector

    collector = _active_carrier_collector
    if not collector:
        return False

    try:
        return collector.record_phase_window(
            phase,
            started_at,
            ended_at
        )
    except Exception as e:
        cp.log(
            f'Carrier telemetry {phase} phase record error '
            f'(non-fatal): {e}'
        )
        return False


def _read_history_file(path):
    """Read and validate a history JSON file."""
    with open(path, 'r') as f:
        history = json.load(f)
    if not isinstance(history, list):
        raise ValueError('history root must be a JSON array')
    return history


def _remove_history_file(path):
    """Best-effort removal of a history working file."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        cp.log(f'Unable to remove history file {path}: {e}')


def _fsync_history_directory():
    """Best-effort sync of history directory metadata after rename."""
    try:
        directory_fd = os.open('tmp', os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        pass


def _write_history_temp(history):
    """Write a complete, validated temporary history file."""
    os.makedirs('tmp', exist_ok=True)
    records = history[-MAX_HISTORY:]

    with open(HISTORY_TEMP_FILE, 'w') as f:
        json.dump(records, f)
        f.flush()
        os.fsync(f.fileno())

    check = _read_history_file(HISTORY_TEMP_FILE)
    if check != records:
        raise IOError('temporary history validation failed')

    return records


def _quarantine_corrupt_primary():
    """Move an invalid primary aside without replacing a good backup."""
    if not os.path.exists(HISTORY_FILE):
        return

    os.replace(HISTORY_FILE, HISTORY_CORRUPT_FILE)
    _fsync_history_directory()


def _restore_history(history, source_name):
    """Restore validated history data to the primary file."""
    records = _write_history_temp(history)

    if os.path.exists(HISTORY_FILE):
        _quarantine_corrupt_primary()

    os.replace(HISTORY_TEMP_FILE, HISTORY_FILE)
    _fsync_history_directory()

    cp.log(f'History recovered from {source_name}')
    return records


def _load_history_locked():
    """Load primary history or recover from a valid local copy."""
    candidates_exist = any(
        os.path.exists(path)
        for path in (
            HISTORY_FILE,
            HISTORY_TEMP_FILE,
            HISTORY_BACKUP_FILE,
        )
    )

    if os.path.exists(HISTORY_FILE):
        try:
            history = _read_history_file(HISTORY_FILE)

            # A valid primary is authoritative. Any remaining temp file
            # belongs to an uncommitted write and can be discarded.
            _remove_history_file(HISTORY_TEMP_FILE)

            return history

        except Exception as e:
            cp.log(f'Primary history is invalid: {e}')

    for path, source_name in (
        (HISTORY_TEMP_FILE, 'temporary history'),
        (HISTORY_BACKUP_FILE, 'history backup'),
    ):
        if not os.path.exists(path):
            continue

        try:
            history = _read_history_file(path)
            return _restore_history(history, source_name)

        except Exception as e:
            cp.log(f'Unable to recover from {source_name}: {e}')

    if not candidates_exist:
        return []

    raise RuntimeError('no valid history copy is available')


def load_history():
    """Load test history, recovering local history when possible."""
    with history_lock:
        try:
            return _load_history_locked()

        except Exception as e:
            cp.log(f'History unavailable: {e}')
            return []


def _load_history_for_update():
    """Load history for mutation; never turn corruption into [] silently."""
    try:
        return _load_history_locked()

    except Exception as e:
        cp.log(f'History update blocked: {e}')
        return None


def save_history(history):
    """Atomically save history while retaining one last-known-good copy."""
    with history_lock:
        try:
            _write_history_temp(history)

            if os.path.exists(HISTORY_FILE):
                # Validate the live history before rotating it into backup.
                # A corrupt primary must never replace a known-good backup.
                _read_history_file(HISTORY_FILE)

                os.replace(
                    HISTORY_FILE,
                    HISTORY_BACKUP_FILE
                )
                _fsync_history_directory()

            try:
                os.replace(
                    HISTORY_TEMP_FILE,
                    HISTORY_FILE
                )
                _fsync_history_directory()

            except Exception:
                # If the primary was already rotated but promotion of the
                # new temp file failed, immediately restore the old primary.
                if (
                    not os.path.exists(HISTORY_FILE)
                    and os.path.exists(HISTORY_BACKUP_FILE)
                ):
                    os.replace(
                        HISTORY_BACKUP_FILE,
                        HISTORY_FILE
                    )
                    _fsync_history_directory()

                raise

            return True

        except Exception as e:
            cp.log(f'Error saving history atomically: {e}')

            # Preserve a completed temp file when the primary disappeared;
            # it may be usable by recovery on the next load.
            if os.path.exists(HISTORY_FILE):
                _remove_history_file(HISTORY_TEMP_FILE)

            return False


def clear_history_storage():
    """Intentionally clear primary history and all recovery copies."""
    with history_lock:
        try:
            os.makedirs('tmp', exist_ok=True)

            for path in (
                HISTORY_FILE,
                HISTORY_BACKUP_FILE,
                HISTORY_TEMP_FILE,
                HISTORY_CORRUPT_FILE,
            ):
                _remove_history_file(path)

            _write_history_temp([])

            os.replace(
                HISTORY_TEMP_FILE,
                HISTORY_FILE
            )
            _fsync_history_directory()

            return True

        except Exception as e:
            cp.log(f'Error clearing history: {e}')
            return False


def add_result(result):
    """Add a test result to history as one serialized transaction."""
    with history_lock:
        history = _load_history_for_update()

        if history is None:
            cp.log(
                'New test result not saved because history is unrecoverable'
            )
            return False

        history.append(result)
        return save_history(history)


# =============================================================================
# PLATFORM DETECTION & MODEL CAPABILITIES
# =============================================================================

# Cache platform info so it's fetched once per app lifecycle, not per test.
_platform_cache = {'product': None, 'fw_major': None, 'fw_minor': None,
                   'fw_patch': None, 'loaded': False}


def _load_platform_cache():
    """Populate the platform cache from router status APIs."""
    if _platform_cache['loaded']:
        return
    try:
        product = cp.get('status/product_info')
        if product:
            _platform_cache['product'] = product.get('product_name', '')
    except Exception:
        pass
    try:
        fw = cp.get('status/fw_info')
        if fw:
            _platform_cache['fw_major'] = fw.get('major_version', 0)
            _platform_cache['fw_minor'] = fw.get('minor_version', 0)
            _platform_cache['fw_patch'] = fw.get('patch_version', 0)
    except Exception:
        pass
    _platform_cache['loaded'] = True


def _get_product_model():
    """Return the upper-cased product name string."""
    _load_platform_cache()
    return (_platform_cache.get('product') or '').upper()



# =============================================================================
# DEVICE AND CAPTIVE MODEM VALIDATION CATALOG
# =============================================================================

_DEVICE_VALIDATION_CATALOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'device_validation_catalog.json'
)
_device_validation_catalog = None
_device_validation_catalog_loaded = False
_device_validation_catalog_lock = threading.Lock()
_VALIDATION_STATUSES = {'pending', 'validated'}


def _validate_validation_entry(label, entry):
    """Validate one standalone or captive-combination status entry."""
    if not isinstance(entry, dict):
        raise ValueError(f'{label} entry must be an object')

    if entry.get('status') not in _VALIDATION_STATUSES:
        raise ValueError(
            f'{label} status must be pending or validated'
        )

    validated_date = entry.get('validated_date')
    if (
        validated_date is not None
        and not isinstance(validated_date, str)
    ):
        raise ValueError(
            f'{label} validated_date must be a string or null'
        )

    if (
        entry.get('status') == 'pending'
        and validated_date is not None
    ):
        raise ValueError(
            f'{label} pending entry must use a null validated_date'
        )


_BASIC_FIRMWARE_RE = re.compile(r'^\d+\.\d+\.\d+$')
_KNOWN_DEFECT_ENGINES = {'iperf3', 'netperf', 'ookla'}


def _validate_known_defect_entry(label, entry):
    """Validate one catalog-driven engine defect entry."""
    if not isinstance(entry, dict):
        raise ValueError(f'{label} entry must be an object')

    defect_id = entry.get('id')
    if not isinstance(defect_id, str) or not defect_id.strip():
        raise ValueError(f'{label} id must be a non-empty string')

    if entry.get('status') != 'confirmed':
        raise ValueError(f'{label} status must be confirmed')

    device = entry.get('device')
    if not isinstance(device, str) or not device.strip():
        raise ValueError(f'{label} device must be a non-empty string')

    captive = entry.get('captive_modem')
    if captive is not None and (
        not isinstance(captive, str) or not captive.strip()
    ):
        raise ValueError(
            f'{label} captive_modem must be a non-empty string or null'
        )

    engine = entry.get('engine')
    if engine not in _KNOWN_DEFECT_ENGINES:
        raise ValueError(
            f'{label} engine must be one of '
            + ', '.join(sorted(_KNOWN_DEFECT_ENGINES))
        )

    confirmed_firmware = entry.get('confirmed_firmware')
    if (
        not isinstance(confirmed_firmware, str)
        or not _BASIC_FIRMWARE_RE.fullmatch(confirmed_firmware)
    ):
        raise ValueError(
            f'{label} confirmed_firmware must use X.Y.Z format'
        )

    fixed_in = entry.get('fixed_in')
    if fixed_in is not None and (
        not isinstance(fixed_in, str)
        or not _BASIC_FIRMWARE_RE.fullmatch(fixed_in)
    ):
        raise ValueError(
            f'{label} fixed_in must use X.Y.Z format or null'
        )

    for field in ('reason', 'workaround'):
        value = entry.get(field)
        if value is not None and not isinstance(value, str):
            raise ValueError(
                f'{label} {field} must be a string when present'
            )


def _load_device_validation_catalog():
    """Load and validate the device-combination catalog once."""
    global _device_validation_catalog
    global _device_validation_catalog_loaded

    if _device_validation_catalog_loaded:
        return _device_validation_catalog

    with _device_validation_catalog_lock:
        if _device_validation_catalog_loaded:
            return _device_validation_catalog

        try:
            with open(
                _DEVICE_VALIDATION_CATALOG_PATH,
                'r',
                encoding='utf-8'
            ) as handle:
                catalog = json.load(handle)

            if not isinstance(catalog, dict):
                raise ValueError('catalog root must be an object')

            if catalog.get('schema_version') != 1:
                raise ValueError('unsupported schema_version')

            standalone = catalog.get('standalone_devices')
            single = catalog.get('single_captive_combinations')
            multiple = catalog.get('multi_captive_combinations')
            known_defects = catalog.get('known_defects', [])

            if not isinstance(standalone, dict) or not standalone:
                raise ValueError(
                    'standalone_devices must be a non-empty object'
                )

            if not isinstance(single, dict) or not single:
                raise ValueError(
                    'single_captive_combinations must be '
                    'a non-empty object'
                )

            if not isinstance(multiple, list):
                raise ValueError(
                    'multi_captive_combinations must be a list'
                )

            if not isinstance(known_defects, list):
                raise ValueError('known_defects must be a list')

            for model, entry in standalone.items():
                _validate_validation_entry(
                    f'standalone device {model}',
                    entry
                )

            for controller, modem_entries in single.items():
                if (
                    not isinstance(modem_entries, dict)
                    or not modem_entries
                ):
                    raise ValueError(
                        f'{controller} captive combinations must be '
                        'a non-empty object'
                    )

                for modem, entry in modem_entries.items():
                    _validate_validation_entry(
                        f'{controller} + {modem}',
                        entry
                    )

            signatures = set()

            for index, combination in enumerate(multiple):
                if not isinstance(combination, dict):
                    raise ValueError(
                        'multi_captive_combinations[{}] must be '
                        'an object'.format(index)
                    )

                controller = combination.get('controller')
                modems = combination.get('captive_modems')

                if (
                    not isinstance(controller, str)
                    or not controller.strip()
                ):
                    raise ValueError(
                        'multi_captive_combinations[{}] needs '
                        'a controller'.format(index)
                    )

                if not isinstance(modems, list) or len(modems) < 2:
                    raise ValueError(
                        f'{controller} multi-captive entry needs '
                        'at least two captive_modems'
                    )

                if not all(
                    isinstance(item, str) and item.strip()
                    for item in modems
                ):
                    raise ValueError(
                        f'{controller} captive_modems must be '
                        'non-empty strings'
                    )

                signature = (
                    controller.upper(),
                    tuple(sorted(
                        item.upper()
                        for item in modems
                    ))
                )

                if signature in signatures:
                    raise ValueError(
                        'duplicate multi-captive combination for '
                        + controller
                    )

                signatures.add(signature)

                _validate_validation_entry(
                    '{} + {}'.format(
                        controller,
                        ' + '.join(modems)
                    ),
                    combination
                )


            defect_ids = set()
            for index, defect in enumerate(known_defects):
                _validate_known_defect_entry(
                    f'known_defects[{index}]',
                    defect
                )
                defect_id = defect['id'].strip().upper()
                if defect_id in defect_ids:
                    raise ValueError(
                        f'duplicate known defect id: {defect["id"]}'
                    )
                defect_ids.add(defect_id)

            _device_validation_catalog = catalog
            cp.log(
                'Loaded device validation catalog '
                f'v{catalog.get("catalog_version", "unknown")}'
            )

        except Exception as error:
            _device_validation_catalog = None
            cp.log(
                'Device validation catalog unavailable (non-fatal): '
                f'{error}'
            )

        finally:
            _device_validation_catalog_loaded = True

    return _device_validation_catalog


def _validation_contains_token(text, token):
    """Match a model token without partial alpha-numeric matches."""
    text = str(text or '').upper()
    token = str(token or '').strip().upper()

    if not text or not token:
        return False

    return re.search(
        r'(?<![A-Z0-9])'
        + re.escape(token)
        + r'(?![A-Z0-9])',
        text
    ) is not None


def _validation_match_model(text, candidates):
    """Return the longest canonical model name found in text."""
    matches = [
        str(candidate).upper()
        for candidate in candidates
        if _validation_contains_token(text, candidate)
    ]

    if not matches:
        return ''

    return max(
        matches,
        key=lambda item: (len(item), item)
    )


def _validation_captive_models(catalog):
    """Return every captive model name used by the catalog."""
    models = set()

    for modem_entries in catalog.get(
        'single_captive_combinations',
        {}
    ).values():
        models.update(
            str(model).upper()
            for model in modem_entries
        )

    for combination in catalog.get(
        'multi_captive_combinations',
        []
    ):
        models.update(
            str(model).upper()
            for model in combination.get(
                'captive_modems',
                []
            )
        )

    for defect in catalog.get('known_defects', []):
        captive = defect.get('captive_modem')
        if isinstance(captive, str) and captive.strip():
            models.add(captive.strip().upper())

    return models


def _validation_scalar_strings(value, depth=0):
    """Collect remote-identity strings used for model matching."""
    if depth > 3:
        return []

    if isinstance(value, dict):
        values = []
        for item in value.values():
            values.extend(
                _validation_scalar_strings(
                    item,
                    depth + 1
                )
            )
        return values

    if isinstance(value, (list, tuple)):
        values = []
        for item in value:
            values.extend(
                _validation_scalar_strings(
                    item,
                    depth + 1
                )
            )
        return values

    if isinstance(value, str) and value.strip():
        return [value.strip()]

    return []


def _validation_remote_identity(remote, info, uid):
    """Build a physical-adapter key shared by both SIM records."""
    for key in (
        'mac0',
        'mac',
        'serial_number',
        'serial',
        'uuid'
    ):
        value = remote.get(key)
        if value:
            return '{}:{}'.format(
                key,
                str(value).strip().upper()
            )

    port = info.get('port')
    if port:
        return 'port:' + str(port).strip().upper()

    return 'uid:' + str(uid).strip().upper()


def _get_captive_modem_models(catalog):
    """Detect physical captive adapters from status/wan/devices."""
    try:
        devices = cp.get('status/wan/devices') or {}

    except Exception as error:
        cp.log(
            f'Captive modem validation detection failed: {error}'
        )
        return []

    if not isinstance(devices, dict):
        return []

    candidates = _validation_captive_models(catalog)
    physical_adapters = {}

    for uid, device in devices.items():
        if not isinstance(device, dict):
            continue

        info = device.get('info')
        if not isinstance(info, dict):
            continue

        remote = info.get('remote')
        if not isinstance(remote, dict) or not remote:
            continue

        remote_text = ' | '.join(
            _validation_scalar_strings(remote)
        )
        model = _validation_match_model(
            remote_text,
            candidates
        )

        # Some NCOS platforms expose the host's internal modem
        # through the remote/captive data model. Do not count that
        # internal representation as a physical captive adapter.
        if (
            not model
            and remote.get('internal_captive') is True
        ):
            continue

        if not model:
            product_name = remote.get('product_name')
            if product_name:
                model = str(
                    product_name
                ).strip().upper()

        if not model:
            model = 'UNKNOWN CAPTIVE MODEM'

        identity = _validation_remote_identity(
            remote,
            info,
            uid
        )
        physical_adapters.setdefault(
            identity,
            model
        )

    return sorted(physical_adapters.values())


def _get_model_family():
    """Normalize the host using model names maintained in JSON."""
    catalog = _load_device_validation_catalog()

    if not catalog:
        return ''

    candidates = set(
        catalog.get('standalone_devices', {})
    )
    candidates.update(
        catalog.get(
            'single_captive_combinations',
            {}
        )
    )

    return _validation_match_model(
        _get_product_model(),
        candidates
    )


def _validation_display_label(
    controller,
    captive_modems
):
    """Build a count-aware label for the detected hardware."""
    labels = []

    for modem in sorted(set(captive_modems)):
        count = captive_modems.count(modem)

        if count > 1:
            labels.append(
                f'{count}x {modem}'
            )
        else:
            labels.append(modem)

    if labels:
        return ' + '.join(
            [controller] + labels
        )

    return controller


def _evaluate_device_validation():
    """Return validation for the live host/captive combination."""
    catalog = _load_device_validation_catalog()
    raw_product = (
        _platform_cache.get('product') or ''
    ).strip()
    fallback_controller = (
        raw_product.upper()
        or 'THIS DEVICE MODEL'
    )

    if not catalog:
        return {
            'status': 'catalog_unavailable',
            'label': fallback_controller,
            'controller': '',
            'captive_modems': [],
            'catalog_version': '',
            'entry': None,
        }

    controller = _get_model_family()
    captive_modems = _get_captive_modem_models(
        catalog
    )
    label = _validation_display_label(
        controller or fallback_controller,
        captive_modems
    )
    entry = None

    if controller and not captive_modems:
        entry = catalog.get(
            'standalone_devices',
            {}
        ).get(controller)

    elif controller and len(captive_modems) == 1:
        entry = catalog.get(
            'single_captive_combinations',
            {}
        ).get(
            controller,
            {}
        ).get(captive_modems[0])

    elif controller and len(captive_modems) > 1:
        signature = tuple(
            sorted(captive_modems)
        )

        for combination in catalog.get(
            'multi_captive_combinations',
            []
        ):
            candidate_controller = str(
                combination.get(
                    'controller',
                    ''
                )
            ).upper()

            candidate_modems = tuple(
                sorted(
                    str(model).upper()
                    for model in combination.get(
                        'captive_modems',
                        []
                    )
                )
            )

            if (
                candidate_controller == controller
                and candidate_modems == signature
            ):
                entry = combination
                break

    if isinstance(entry, dict):
        status = entry.get('status')
    else:
        status = 'unlisted'

    return {
        'status': status,
        'label': label,
        'controller': controller,
        'captive_modems': captive_modems,
        'catalog_version': catalog.get(
            'catalog_version',
            ''
        ),
        'entry': entry,
    }



def _get_basic_firmware():
    """Return the running NCOS version as major.minor.patch."""
    _load_platform_cache()
    values = (
        _platform_cache.get('fw_major'),
        _platform_cache.get('fw_minor'),
        _platform_cache.get('fw_patch'),
    )

    if any(value is None for value in values):
        return ''

    try:
        return '{}.{}.{}'.format(
            *(int(value) for value in values)
        )
    except (TypeError, ValueError):
        return ''


def _firmware_tuple(value):
    """Convert an X.Y.Z firmware string to a numeric comparison tuple."""
    text = str(value or '').strip()

    if not _BASIC_FIRMWARE_RE.fullmatch(text):
        return None

    return tuple(
        int(part)
        for part in text.split('.')
    )


def _selected_captive_model(interface, catalog):
    """Return the captive model represented by one selected WAN, if any."""
    requested = str(interface or '').strip()

    if requested == '__active_wan__':
        requested = _resolve_requested_interface(
            requested
        )
    elif not requested or requested == 'auto':
        try:
            requested = cp.get_wan_primary_device() or ''
        except Exception:
            requested = ''

    if not requested:
        return ''

    try:
        devices = cp.get(
            'status/wan/devices'
        ) or {}

        if not isinstance(devices, dict):
            return ''

        matched = None

        for uid, device in devices.items():
            if not isinstance(device, dict):
                continue

            iface = device.get(
                'info',
                {}
            ).get(
                'iface',
                ''
            )

            if requested == uid or requested == iface:
                matched = device
                break

        if not matched:
            return ''

        info = matched.get(
            'info',
            {}
        )
        remote = info.get(
            'remote'
        )

        if not isinstance(remote, dict) or not remote:
            return ''

        # NCOS may expose the controller's internal modem through the same
        # remote/captive data model. That is not a physical captive modem.
        if remote.get('internal_captive') is True:
            return ''

        remote_text = ' | '.join(
            _validation_scalar_strings(
                remote
            )
        )

        model = _validation_match_model(
            remote_text,
            _validation_captive_models(
                catalog
            )
        )

        if model:
            return model

        return str(
            remote.get(
                'product_name'
            ) or ''
        ).strip().upper()

    except Exception as error:
        cp.log(
            'Known defect WAN identity lookup failed '
            f'(non-fatal): {error}'
        )
        return ''


def _engine_display_name(engine):
    """Return a UI-friendly engine name for catalog messages."""
    return {
        'iperf3': 'iPerf3',
        'netperf': 'Netperf',
        'ookla': 'Ookla',
    }.get(
        str(engine or '').lower(),
        str(engine or 'Test engine')
    )


def _evaluate_known_defect(engine, interface=''):
    """Return a matching confirmed engine defect for the selected WAN."""
    engine = str(
        engine or ''
    ).strip().lower()

    catalog = _load_device_validation_catalog()
    current_firmware = _get_basic_firmware()

    result = {
        'blocked': False,
        'engine': engine,
        'firmware': current_firmware,
    }

    if not catalog or not engine:
        return result

    controller = _get_model_family()

    if not controller:
        return result

    live_captives = _get_captive_modem_models(
        catalog
    )

    selected_captive = _selected_captive_model(
        interface,
        catalog
    )

    for defect in catalog.get(
        'known_defects',
        []
    ):
        if defect.get('status') != 'confirmed':
            continue

        if str(
            defect.get(
                'engine'
            ) or ''
        ).lower() != engine:
            continue

        if str(
            defect.get(
                'device'
            ) or ''
        ).upper() != controller:
            continue

        target_captive = defect.get(
            'captive_modem'
        )

        if target_captive is None:
            # null means the standalone controller only.
            if live_captives:
                continue

        else:
            target_captive = str(
                target_captive
            ).strip().upper()

            if selected_captive != target_captive:
                continue

        fixed_in = defect.get(
            'fixed_in'
        )

        if fixed_in:
            running_key = _firmware_tuple(
                current_firmware
            )
            fixed_key = _firmware_tuple(
                fixed_in
            )

            if (
                running_key
                and fixed_key
                and running_key >= fixed_key
            ):
                continue

        engine_name = _engine_display_name(
            engine
        )

        label_parts = [
            controller
        ]

        if target_captive:
            label_parts.append(
                target_captive
            )

        label_parts.append(
            engine_name
        )

        label = ' + '.join(
            label_parts
        )

        firmware_label = (
            current_firmware
            or 'unknown'
        )

        message = (
            f'{label} is disabled on NCOS '
            f'{firmware_label} due to a '
            'confirmed known defect.'
        )

        reason = str(
            defect.get(
                'reason'
            ) or ''
        ).strip()

        workaround = str(
            defect.get(
                'workaround'
            ) or ''
        ).strip()

        if reason:
            message += ' ' + reason

        if fixed_in:
            message += (
                f' Fixed in NCOS {fixed_in} '
                'and newer.'
            )

        if workaround:
            message += ' ' + workaround

        return {
            'blocked': True,
            'id': defect.get(
                'id',
                ''
            ),
            'status': 'confirmed',
            'device': controller,
            'captive_modem': (
                target_captive
                or None
            ),
            'engine': engine,
            'label': label,
            'message': message,
            'firmware': current_firmware,
            'confirmed_firmware': defect.get(
                'confirmed_firmware'
            ),
            'fixed_in': fixed_in,
        }

    return result


def _is_validated_model():
    """Return True only for the exact live catalog signature."""
    return (
        _evaluate_device_validation().get('status')
        == 'validated'
    )


# =============================================================================
# IPERF3 SERVER SOURCE SETTINGS AND SINGLE ACTIVE CACHE
# =============================================================================

_IPERF3_PUBLIC_CATALOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'iperf3_public_servers.json'
)
_IPERF3_SERVER_SETTINGS_KEY = 'iperf_server_settings'

_iperf3_server_settings = None
_iperf3_server_settings_lock = threading.Lock()

# Only the currently selected iPerf3 server source is retained in RAM.
# The inactive source is not read or parsed.
_active_iperf3_server_cache = None
_active_iperf3_server_cache_lock = threading.Lock()


def _normalize_iperf3_host(value):
    """Normalize a server hostname/IP for deterministic matching."""
    return str(value or '').strip().lower().rstrip('.')


def _public_iperf3_server_ref(
    region,
    host,
    port_start,
    port_end
):
    """Create the hidden stable reference for a Public iPerf3 endpoint."""
    return 'public|{}|{}|{}|{}'.format(
        str(region or '').strip().lower(),
        _normalize_iperf3_host(host),
        int(port_start),
        int(port_end),
    )


def _default_iperf3_server_settings():
    """Return first-migration 2.7.0 server settings."""
    return {
        'server_mode': 'public',
        'last_public_region': '',
    }


def _load_iperf3_server_settings():
    """Load the small server-mode settings object once."""
    global _iperf3_server_settings

    with _iperf3_server_settings_lock:
        if _iperf3_server_settings is not None:
            return dict(_iperf3_server_settings)

        settings = None

        try:
            value = cp.get_appdata(
                _IPERF3_SERVER_SETTINGS_KEY
            )

            if value:
                candidate = json.loads(value)

                if not isinstance(candidate, dict):
                    raise ValueError(
                        'settings must be a JSON object'
                    )

                mode = candidate.get('server_mode')
                region = candidate.get(
                    'last_public_region',
                    ''
                )

                if mode not in ('public', 'user'):
                    raise ValueError(
                        'server_mode must be public or user'
                    )

                if not isinstance(region, str):
                    raise ValueError(
                        'last_public_region must be a string'
                    )

                settings = {
                    'server_mode': mode,
                    'last_public_region': region.strip(),
                }

        except Exception as e:
            cp.log(
                'Invalid iPerf3 server settings; '
                f'using 2.7.0 defaults: {e}'
            )

        if settings is None:
            # First 2.7.0 migration intentionally defaults to Public.
            # Existing iperf3_servers SDK appdata is preserved untouched.
            settings = _default_iperf3_server_settings()

        _iperf3_server_settings = settings

        return dict(_iperf3_server_settings)


def _load_public_iperf3_server_source():
    """Read and validate the bundled Public catalog."""
    with open(
        _IPERF3_PUBLIC_CATALOG_PATH,
        'r',
        encoding='utf-8'
    ) as handle:
        raw = json.load(handle)

    if (
        not isinstance(raw, dict)
        or raw.get('schema_version') != 1
    ):
        raise ValueError(
            'invalid Public iPerf3 catalog schema'
        )

    raw_regions = raw.get('regions')

    if (
        not isinstance(raw_regions, list)
        or not raw_regions
    ):
        raise ValueError(
            'Public iPerf3 regions must be a non-empty list'
        )

    region_names = []
    servers = []
    seen_regions = set()
    seen_refs = set()

    for region in raw_regions:
        if not isinstance(region, dict):
            raise ValueError(
                'Public iPerf3 region must be an object'
            )

        region_name = str(
            region.get('name') or ''
        ).strip()

        region_key = region_name.lower()
        raw_servers = region.get('servers')

        if (
            not region_name
            or region_key in seen_regions
        ):
            raise ValueError(
                'Public iPerf3 region names must be unique'
            )

        if (
            not isinstance(raw_servers, list)
            or not raw_servers
        ):
            raise ValueError(
                f'{region_name} must contain at least one server'
            )

        seen_regions.add(region_key)
        region_names.append(region_name)

        for server in raw_servers:
            if not isinstance(server, dict):
                raise ValueError(
                    f'{region_name} server must be an object'
                )

            server_name = str(
                server.get('server_name') or ''
            ).strip()

            host = _normalize_iperf3_host(
                server.get('host')
            )

            city = str(
                server.get('city') or ''
            ).strip()

            country = str(
                server.get('country') or ''
            ).strip()

            port_start = server.get('port_start')
            port_end = server.get('port_end')

            if (
                not server_name
                or not city
                or not country
            ):
                raise ValueError(
                    f'{region_name} server metadata incomplete'
                )

            if (
                not host
                or len(host) > 253
                or any(
                    char.isspace()
                    for char in host
                )
            ):
                raise ValueError(
                    f'{region_name} server host is invalid'
                )

            if (
                not isinstance(port_start, int)
                or isinstance(port_start, bool)
                or not isinstance(port_end, int)
                or isinstance(port_end, bool)
                or not 1 <= port_start <= port_end <= 65535
            ):
                raise ValueError(
                    f'{region_name} server port range invalid'
                )

            server_ref = _public_iperf3_server_ref(
                region_name,
                host,
                port_start,
                port_end
            )

            if server_ref in seen_refs:
                raise ValueError(
                    f'duplicate Public iPerf3 endpoint: {host}'
                )

            seen_refs.add(server_ref)

            # One flat normalized list is retained.
            # Region filtering does not duplicate server dictionaries.
            servers.append({
                'region': region_name,
                'server_name': server_name,
                'host': host,
                'port_start': port_start,
                'port_end': port_end,
                'city': city,
                'country': country,
                'server_ref': server_ref,
            })

    return {
        'mode': 'public',
        'available': True,
        'regions': region_names,
        'servers': servers,
    }


def _load_user_iperf3_server_source():
    """Read the User Server List from canonical RAM (or legacy on Day-1)."""
    # Effective (Device>Group>Default) User Server list from the two-layer
    # manager. Legacy App Data is NEVER a fallback here: once either canonical
    # key exists it is outside the source-of-truth chain, and the manager's
    # upgrade-required compatibility view already surfaces legacy through the
    # effective config (§16).
    effective_users = config_mgr.active_section('iperf3_user_servers')
    servers = effective_users if isinstance(effective_users, list) else []

    # Preserve existing 2.6.5 User Server entries exactly as stored.
    # Schema modernization belongs to the later User Server feature patch.
    return {
        'mode': 'user',
        'available': True,
        'regions': [],
        'servers': servers,
    }


def _load_active_iperf3_server_cache(force=False):
    """Load only the configured iPerf3 source into one RAM cache."""
    global _active_iperf3_server_cache
    global _iperf3_server_settings

    settings = _load_iperf3_server_settings()
    mode = settings['server_mode']

    with _active_iperf3_server_cache_lock:
        if (
            not force
            and _active_iperf3_server_cache is not None
            and _active_iperf3_server_cache.get('mode') == mode
        ):
            return _active_iperf3_server_cache

        try:
            if mode == 'public':
                new_cache = (
                    _load_public_iperf3_server_source()
                )

                valid_regions = new_cache['regions']

                if (
                    valid_regions
                    and settings.get(
                        'last_public_region'
                    ) not in valid_regions
                ):
                    settings['last_public_region'] = (
                        valid_regions[0]
                    )

                    # last_public_region is RAM-only runtime state. Correcting
                    # an invalid remembered region updates RAM only and never
                    # persists to canonical or legacy App Data.
                    with _iperf3_server_settings_lock:
                        _iperf3_server_settings = dict(
                            settings
                        )

                    cp.log(
                        'Initialized iPerf3 server settings (RAM): '
                        f'{settings["server_mode"]}, '
                        f'{settings.get("last_public_region", "")}'
                    )

            else:
                new_cache = (
                    _load_user_iperf3_server_source()
                )

            # The old cache remains active until the replacement source
            # has loaded successfully.
            _active_iperf3_server_cache = new_cache

            cp.log(
                f'Loaded active iPerf3 {mode} server source: '
                f'{len(new_cache["servers"])} servers'
            )

        except Exception as e:
            cp.log(
                f'Unable to load active iPerf3 '
                f'{mode} server source: {e}'
            )

            _active_iperf3_server_cache = {
                'mode': mode,
                'available': False,
                'regions': [],
                'servers': [],
                'error': str(e),
            }

        return _active_iperf3_server_cache


def _get_active_iperf3_server_state():
    """Return the current server settings and active RAM cache."""
    settings = _load_iperf3_server_settings()
    cache = _load_active_iperf3_server_cache()

    return {
        'server_mode': settings['server_mode'],
        'last_public_region': settings.get(
            'last_public_region',
            ''
        ),
        'available': bool(
            cache.get('available')
        ),
        'regions': cache.get(
            'regions',
            []
        ),
        'servers': cache.get(
            'servers',
            []
        ),
    }


def _empty_iperf3_stats():
    """Return a new compact reliability statistics object."""
    return {
        'schema_version':
            _IPERF3_STATS_SCHEMA_VERSION,
        'servers':
            {}
    }


def _load_iperf3_stats():
    """Load iPerf3 reliability statistics once, on demand."""
    global _iperf3_stats
    global _iperf3_stats_last_checkpoint

    with _iperf3_stats_lock:
        if _iperf3_stats is not None:
            return _iperf3_stats

        loaded = None

        try:
            raw = cp.get_appdata(
                _IPERF3_STATS_KEY
            )

            if raw:
                parsed = json.loads(
                    raw
                )

                if (
                    not isinstance(
                        parsed,
                        dict
                    )
                    or parsed.get(
                        'schema_version'
                    )
                    != _IPERF3_STATS_SCHEMA_VERSION
                    or not isinstance(
                        parsed.get(
                            'servers'
                        ),
                        dict
                    )
                ):
                    raise ValueError(
                        'invalid reliability statistics schema'
                    )

                loaded = parsed

        except Exception as exc:
            cp.log(
                'Unable to load iPerf3 reliability statistics: '
                '{}'.format(
                    exc
                )
            )

        if loaded is None:
            loaded = _empty_iperf3_stats()

        _iperf3_stats = loaded
        _iperf3_stats_last_checkpoint = (
            time.monotonic()
        )

        return _iperf3_stats


def _mark_iperf3_stats_dirty():
    """Mark the in-memory statistics object as changed."""
    global _iperf3_stats_dirty
    global _iperf3_stats_generation

    _iperf3_stats_dirty = True
    _iperf3_stats_generation += 1


def _record_iperf3_endpoint_failures(
    server_ref,
    ports
):
    """Record listener-attributable failures for one endpoint."""
    server_ref = str(
        server_ref or ''
    ).strip()

    if not server_ref:
        return

    normalized_ports = []

    for port in ports or []:
        try:
            normalized_ports.append(
                str(
                    int(port)
                )
            )
        except Exception:
            continue

    if not normalized_ports:
        return

    _load_iperf3_stats()

    with _iperf3_stats_lock:
        servers = _iperf3_stats[
            'servers'
        ]

        stats = servers.setdefault(
            server_ref,
            {
                'successful_tests':
                    0,
                'endpoint_failures':
                    0,
                'ports':
                    {}
            }
        )

        stats[
            'endpoint_failures'
        ] = (
            int(
                stats.get(
                    'endpoint_failures',
                    0
                )
            )
            + len(
                normalized_ports
            )
        )

        port_stats = stats.setdefault(
            'ports',
            {}
        )

        for port in normalized_ports:
            port_stats[
                port
            ] = (
                int(
                    port_stats.get(
                        port,
                        0
                    )
                )
                + 1
            )

        _mark_iperf3_stats_dirty()


def _record_iperf3_success(
    server_ref
):
    """Record one fully successful iPerf3 test."""
    server_ref = str(
        server_ref or ''
    ).strip()

    if not server_ref:
        return

    _load_iperf3_stats()

    with _iperf3_stats_lock:
        servers = _iperf3_stats[
            'servers'
        ]

        stats = servers.setdefault(
            server_ref,
            {
                'successful_tests':
                    0,
                'endpoint_failures':
                    0,
                'ports':
                    {}
            }
        )

        stats[
            'successful_tests'
        ] = (
            int(
                stats.get(
                    'successful_tests',
                    0
                )
            )
            + 1
        )

        _mark_iperf3_stats_dirty()


def _download_listener_failure_ports(
    result
):
    """Derive retryable listener failures from a Downlink search."""
    if not isinstance(
        result,
        dict
    ):
        return []

    # New timeout-aware retry results explicitly identify only failures
    # attributable to an iPerf3 listener. Healthy-WAN timeouts may be
    # retryable operationally but must not redefine the existing
    # Reliability -> Endpoint Failures metric.
    explicit = result.get(
        'listener_failure_ports'
    )

    if explicit is not None:
        return sorted(
            set(
                explicit
                or []
            )
        )

    # Compatibility fallback for older retry results.
    attempted = set(
        result.get(
            'attempted',
            set()
        )
        or set()
    )

    terminal_port = result.get(
        'port'
    )

    if result.get(
        'success'
    ):
        attempted.discard(
            terminal_port
        )

        return sorted(
            attempted
        )

    if result.get(
        'hard_failure'
    ):
        # The terminal failure was specifically classified as
        # WAN/routing/system/non-listener. Earlier attempts were
        # retryable listener failures.
        attempted.discard(
            terminal_port
        )

        return sorted(
            attempted
        )

    # Exhaustion with hard_failure=False means every attempted
    # port failed for a retryable listener reason.
    return sorted(
        attempted
    )


def _upload_listener_failure_ports(
    download_port,
    attempted_before,
    attempted_after,
    upload_result
):
    """Derive listener failures from the Uplink retry sequence."""
    if not isinstance(
        upload_result,
        dict
    ):
        return []

    # Timeout-aware Uplink retries explicitly identify only failures
    # attributable to an iPerf3 listener. A timeout on a verified healthy
    # WAN may be retryable operationally but remains excluded from the
    # existing Reliability -> Endpoint Failures metric.
    explicit = upload_result.get(
        'listener_failure_ports'
    )

    if explicit is not None:
        return sorted(
            set(
                explicit
                or []
            )
        )

    # Compatibility fallback for older retry-result shapes.
    before = set(
        attempted_before
        or set()
    )

    after = set(
        attempted_after
        or set()
    )

    new_ports = (
        after
        - before
    )

    final_port = upload_result.get(
        'port'
    )

    if upload_result.get(
        'success'
    ):
        if final_port == download_port:
            return []

        failures = {
            download_port
        }

        failures.update(
            new_ports
        )

        failures.discard(
            final_port
        )

        return sorted(
            failures
        )

    final_reason = (
        _iperf3_retryable_endpoint_reason(
            upload_result.get(
                'error'
            )
        )
    )

    if final_reason:
        # Every attempted Uplink listener, including the final one,
        # failed for a retryable listener-specific reason.
        failures = {
            download_port
        }

        failures.update(
            new_ports
        )

        return sorted(
            failures
        )

    # The final attempt was a hard failure. If retries occurred,
    # the original Downlink port and any intermediate retry ports
    # were listener failures, but the terminal hard-failure port
    # must not be counted.
    if not new_ports:
        return []

    failures = {
        download_port
    }

    failures.update(
        new_ports
    )

    failures.discard(
        final_port
    )

    return sorted(
        failures
    )


def _checkpoint_iperf3_stats_if_due(
    force=False
):
    """Persist one batched statistics object at most hourly."""
    global _iperf3_stats_dirty
    global _iperf3_stats_last_checkpoint

    with _iperf3_stats_lock:
        if (
            _iperf3_stats is None
            or not _iperf3_stats_dirty
        ):
            return True

        now = time.monotonic()

        if (
            not force
            and (
                now
                - _iperf3_stats_last_checkpoint
            )
            < _IPERF3_STATS_CHECKPOINT_SECONDS
        ):
            return True

        snapshot = json.dumps(
            _iperf3_stats,
            separators=(',', ':')
        )

        generation = (
            _iperf3_stats_generation
        )

    try:
        cp.put_appdata(
            _IPERF3_STATS_KEY,
            snapshot
        )

    except Exception as exc:
        cp.log(
            'Unable to checkpoint iPerf3 reliability statistics: '
            '{}'.format(
                exc
            )
        )

        return False

    with _iperf3_stats_lock:
        _iperf3_stats_last_checkpoint = (
            time.monotonic()
        )

        if (
            _iperf3_stats_generation
            == generation
        ):
            _iperf3_stats_dirty = False

    return True


def _active_iperf3_reliability_descriptors():
    """Return active-mode endpoints in configured display order."""
    state = (
        _get_active_iperf3_server_state()
    )

    mode = state.get(
        'server_mode',
        'public'
    )

    descriptors = []

    for server in state.get(
        'servers',
        []
    ):
        if not isinstance(
            server,
            dict
        ):
            continue

        if mode == 'public':
            server_ref = str(
                server.get(
                    'server_ref'
                )
                or ''
            )

            host = str(
                server.get(
                    'host'
                )
                or ''
            )

        else:
            host = str(
                server.get(
                    'server'
                )
                or ''
            )

            try:
                server_ref = (
                    _user_iperf3_server_ref(
                        host,
                        server.get(
                            'port',
                            '5201'
                        )
                    )
                )

            except Exception:
                continue

        if not server_ref:
            continue

        descriptors.append({
            'server_ref':
                server_ref,
            'server_name':
                (
                    server.get(
                        'server_name'
                    )
                    or host
                ),
            'host':
                host
        })

    return (
        mode,
        descriptors
    )


def _most_failed_iperf3_port(
    port_stats
):
    """Return the highest-failure port using port number as tie-break."""
    if not isinstance(
        port_stats,
        dict
    ):
        return None

    candidates = []

    for port, count in port_stats.items():
        try:
            candidates.append(
                (
                    int(count),
                    int(port)
                )
            )
        except Exception:
            continue

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            -item[0],
            item[1]
        )
    )

    return candidates[0][1]


def _iperf3_failure_rate(
    successes,
    failures
):
    """Return the operational endpoint-failure percentage."""
    total = (
        int(successes)
        + int(failures)
    )

    if total <= 0:
        return 0.0

    return round(
        (
            int(failures)
            / total
        )
        * 100,
        1
    )


def _get_iperf3_reliability_state():
    """Return active-mode reliability statistics for the Servers page."""
    mode, descriptors = (
        _active_iperf3_reliability_descriptors()
    )

    stats = _load_iperf3_stats()

    rows = []
    total_successes = 0
    total_failures = 0
    aggregate_ports = {}

    with _iperf3_stats_lock:
        stored = stats.get(
            'servers',
            {}
        )

        for descriptor in descriptors:
            values = stored.get(
                descriptor[
                    'server_ref'
                ],
                {}
            )

            successes = int(
                values.get(
                    'successful_tests',
                    0
                )
            )

            failures = int(
                values.get(
                    'endpoint_failures',
                    0
                )
            )

            ports = values.get(
                'ports',
                {}
            )

            total_successes += (
                successes
            )

            total_failures += (
                failures
            )

            for port, count in ports.items():
                try:
                    aggregate_ports[
                        str(
                            int(port)
                        )
                    ] = (
                        aggregate_ports.get(
                            str(
                                int(port)
                            ),
                            0
                        )
                        + int(count)
                    )
                except Exception:
                    continue

            if (
                successes <= 0
                and failures <= 0
            ):
                continue

            rows.append({
                'server_name':
                    descriptor[
                        'server_name'
                    ],
                'host':
                    descriptor[
                        'host'
                    ],
                'successful_tests':
                    successes,
                'endpoint_failures':
                    failures,
                'failure_rate':
                    _iperf3_failure_rate(
                        successes,
                        failures
                    ),
                'most_failed_port':
                    _most_failed_iperf3_port(
                        ports
                    )
            })

    return {
        'server_mode':
            mode,
        'successful_tests':
            total_successes,
        'endpoint_failures':
            total_failures,
        'failure_rate':
            _iperf3_failure_rate(
                total_successes,
                total_failures
            ),
        'most_failed_port':
            _most_failed_iperf3_port(
                aggregate_ports
            ),
        'servers':
            rows
    }


def _reset_active_iperf3_reliability():
    """Clear statistics for the currently active server mode only."""
    global _iperf3_stats_dirty

    mode = _load_iperf3_server_settings().get(
        'server_mode',
        'public'
    )

    prefix = (
        mode
        + '|'
    )

    _load_iperf3_stats()

    with _iperf3_stats_lock:
        stored = _iperf3_stats.get(
            'servers',
            {}
        )

        remove = [
            ref
            for ref in stored
            if str(ref).startswith(
                prefix
            )
        ]

        for ref in remove:
            stored.pop(
                ref,
                None
            )

        if remove:
            _mark_iperf3_stats_dirty()

    if not remove:
        return True

    return _checkpoint_iperf3_stats_if_due(
        force=True
    )


def _prune_loaded_user_iperf3_stats(
    servers
):
    """Remove deleted User endpoint stats from RAM when already loaded."""
    if _iperf3_stats is None:
        return

    valid = set()

    for server in servers or []:
        if not isinstance(
            server,
            dict
        ):
            continue

        try:
            valid.add(
                _user_iperf3_server_ref(
                    server.get(
                        'server',
                        ''
                    ),
                    server.get(
                        'port',
                        '5201'
                    )
                )
            )
        except Exception:
            continue

    with _iperf3_stats_lock:
        stored = _iperf3_stats.get(
            'servers',
            {}
        )

        remove = [
            ref
            for ref in stored
            if (
                str(ref).startswith(
                    'user|'
                )
                and ref not in valid
            )
        ]

        for ref in remove:
            stored.pop(
                ref,
                None
            )

        if remove:
            _mark_iperf3_stats_dirty()


def _parse_iperf3_port_range(value):
    """Normalize one port or a contiguous port range."""
    if isinstance(value, bool):
        raise ValueError('port must be numeric')

    if isinstance(value, int):
        start = value
        end = value

    else:
        raw = str(
            value or ''
        ).strip()

        raw = (
            raw.replace('–', '-')
               .replace('—', '-')
        )

        if not raw:
            raise ValueError(
                'port or port range is required'
            )

        if '-' in raw:
            parts = raw.split('-', 1)

            if (
                not parts[0].strip().isdigit()
                or not parts[1].strip().isdigit()
            ):
                raise ValueError(
                    'port range must use start-end'
                )

            start = int(
                parts[0].strip()
            )

            end = int(
                parts[1].strip()
            )

        else:
            if not raw.isdigit():
                raise ValueError(
                    'port must be numeric'
                )

            start = int(raw)
            end = start

    if not 1 <= start <= end <= 65535:
        raise ValueError(
            'port range must be between 1 and 65535'
        )

    return start, end


def _format_iperf3_port_range(start, end):
    """Return the existing compact SDK port representation."""
    if start == end:
        return str(start)

    return '{}-{}'.format(
        start,
        end
    )


def _normalize_user_iperf3_port(value):
    """Return a canonical compact User server port/range."""
    start, end = _parse_iperf3_port_range(
        value
    )

    return _format_iperf3_port_range(
        start,
        end
    )


def _valid_iperf3_server_host(value):
    """Validate an IPv4, IPv6, or basic DNS hostname."""
    host = _normalize_iperf3_host(
        value
    )

    if (
        not host
        or len(host) > 253
        or any(
            char.isspace()
            for char in host
        )
    ):
        return False

    try:
        socket.inet_pton(
            socket.AF_INET,
            host
        )
        return True
    except OSError:
        pass

    try:
        socket.inet_pton(
            socket.AF_INET6,
            host
        )
        return True
    except OSError:
        pass

    labels = host.split('.')

    for label in labels:
        if (
            not label
            or len(label) > 63
            or not re.fullmatch(
                r'[A-Za-z0-9]'
                r'(?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?',
                label
            )
        ):
            return False

    return True


def _user_iperf3_server_ref(host, port):
    """Create a hidden deterministic User endpoint reference."""
    return 'user|{}|{}'.format(
        _normalize_iperf3_host(host),
        _normalize_user_iperf3_port(
            port
        ),
    )


def _normalize_user_iperf3_server(
    server_name,
    host,
    port_start,
    port_end,
    city,
    country
):
    """Validate fields and return the compact SDK server record."""
    server_name = str(
        server_name or ''
    ).strip()

    host = _normalize_iperf3_host(
        host
    )

    city = str(
        city or ''
    ).strip()

    country = str(
        country or ''
    ).strip()

    if not server_name:
        raise ValueError(
            'server_name is required'
        )

    if len(server_name) > 120:
        raise ValueError(
            'server_name must be 120 characters or fewer'
        )

    if not _valid_iperf3_server_host(
        host
    ):
        raise ValueError(
            'host must be a valid DNS name or IP address'
        )

    if not city:
        raise ValueError(
            'city is required'
        )

    if len(city) > 100:
        raise ValueError(
            'city must be 100 characters or fewer'
        )

    if not country:
        raise ValueError(
            'country is required'
        )

    if len(country) > 100:
        raise ValueError(
            'country must be 100 characters or fewer'
        )

    start, end = (
        _parse_iperf3_port_range(
            '{}-{}'.format(
                port_start,
                port_end
            )
            if port_start != port_end
            else port_start
        )
    )

    return {
        'server_name':
            server_name,
        'server':
            host,
        'port':
            _format_iperf3_port_range(
                start,
                end
            ),
        'city':
            city,
        'country':
            country,
    }


def _validate_user_iperf3_external_entry(entry):
    """Validate one canonical User Server JSON entry."""
    if not isinstance(entry, dict):
        raise ValueError(
            'server entry must be a JSON object'
        )

    expected = {
        'server_name',
        'host',
        'port_start',
        'port_end',
        'city',
        'country',
    }

    missing = expected - set(entry)
    extra = set(entry) - expected

    if missing:
        raise ValueError(
            'missing field(s): '
            + ', '.join(
                sorted(missing)
            )
        )

    if extra:
        raise ValueError(
            'unsupported field(s): '
            + ', '.join(
                sorted(extra)
            )
        )

    if (
        not isinstance(
            entry.get('port_start'),
            int
        )
        or isinstance(
            entry.get('port_start'),
            bool
        )
        or not isinstance(
            entry.get('port_end'),
            int
        )
        or isinstance(
            entry.get('port_end'),
            bool
        )
    ):
        raise ValueError(
            'port_start and port_end must be integers'
        )

    return _normalize_user_iperf3_server(
        entry.get('server_name'),
        entry.get('host'),
        entry.get('port_start'),
        entry.get('port_end'),
        entry.get('city'),
        entry.get('country')
    )




def _find_public_iperf3_server(server_ref, cache=None):
    """Find one cached Public server by hidden reference."""
    if cache is None:
        cache = _load_active_iperf3_server_cache()

    if not cache or cache.get('mode') != 'public':
        return None

    for server in cache.get('servers', []):
        if server.get('server_ref') == server_ref:
            return server

    return None


def _active_user_iperf3_server_refs(cache=None):
    """Return hidden refs for servers in the active User cache."""
    if cache is None:
        cache = _load_active_iperf3_server_cache()

    refs = set()

    if not cache or cache.get('mode') != 'user':
        return refs

    for server in cache.get('servers', []):
        if not isinstance(server, dict):
            continue

        host = server.get('server', '')

        if not host:
            continue

        refs.add(
            _user_iperf3_server_ref(
                host,
                server.get('port', '5201')
            )
        )

    return refs


def _iperf3_schedule_is_configured(config=None):
    """Return True when an iPerf3 schedule contains saved configuration."""
    if config is None:
        with schedule_lock:
            config = dict(schedule_config)

    if config.get('engine') != 'iperf3':
        return False

    return bool(
        config.get('enabled')
        or config.get('autostart')
        or config.get('cron')
        or config.get('params')
    )


def _safe_empty_schedule():
    """Return the known-safe disabled schedule section value."""
    return {
        'enabled': False,
        'autostart': False,
        'cron': '',
        'engine': 'netperf',
        'params': {}
    }


def _apply_safe_schedule_to_ram():
    """Apply the known-safe disabled schedule to RAM only (no persistence).

    Used by the startup validator so an unsafe saved iPerf3 schedule cannot
    run, without writing canonical or legacy App Data merely because the app
    started (and never creating a Device override).
    """
    global schedule_config
    with schedule_lock:
        schedule_config.update(_safe_empty_schedule())


def _disable_unsafe_schedule_at_startup(reason):
    """Startup safety: prevent an unsafe saved iPerf3 schedule from running.

    Applies the safe disabled schedule to RAM and logs the reason. Does NOT
    write canonical or legacy App Data (the app must not persist merely
    because it started, and must not create a Device override).
    """
    _apply_safe_schedule_to_ram()
    cp.log(f'iPerf3 schedule disabled at startup: {reason}')


def _validate_loaded_iperf3_schedule():
    """Validate a saved iPerf3 schedule before scheduler startup."""
    with schedule_lock:
        config = dict(schedule_config)

    if not _iperf3_schedule_is_configured(config):
        return

    settings = _load_iperf3_server_settings()

    active_mode = settings.get(
        'server_mode',
        'public'
    )

    params = config.get('params') or {}

    saved_source = params.get(
        'server_source'
    )

    # Pre-2.7 schedules have no server-source metadata. Because 2.7.0
    # intentionally defaults to Public mode, an old User-server schedule
    # must never silently resume after upgrade.
    if saved_source not in ('public', 'user'):
        _disable_unsafe_schedule_at_startup(
            'legacy schedule has no 2.7 server-source metadata'
        )
        return

    if saved_source != active_mode:
        _disable_unsafe_schedule_at_startup(
            f'saved source {saved_source} does not match '
            f'active mode {active_mode}'
        )
        return

    cache = _load_active_iperf3_server_cache()

    server_ref = params.get(
        'server_ref',
        ''
    )

    if saved_source == 'public':
        if (
            not server_ref
            or not _find_public_iperf3_server(
                server_ref,
                cache
            )
        ):
            _disable_unsafe_schedule_at_startup(
                'saved Public server no longer exists '
                'in the active catalog'
            )

    else:
        if (
            not server_ref
            or server_ref
            not in _active_user_iperf3_server_refs(
                cache
            )
        ):
            _disable_unsafe_schedule_at_startup(
                'saved User server no longer exists '
                'in the User Server List'
            )


def _switch_iperf3_server_mode(
    mode,
    confirm_schedule_reset=False
):
    """Safely replace the single active iPerf3 server source.

    Persistence is routed through the canonical Configuration Manager as an
    ordinary Device-only Save. There is no management-scope prompt.
    """
    global _iperf3_server_settings
    global _active_iperf3_server_cache

    mode = str(
        mode or ''
    ).strip().lower()

    if mode not in ('public', 'user'):
        return {
            'error':
                'server_mode must be public or user'
        }, 400

    # Never introduce an SDK/configuration operation while a throughput
    # test is actively running.
    with test_lock:
        if current_test.get('running'):
            return {
                'error':
                    'Cannot change iPerf3 server mode '
                    'while a test is running.'
            }, 409

    settings = _load_iperf3_server_settings()

    if settings.get('server_mode') == mode:
        return (
            _get_active_iperf3_server_state(),
            200
        )

    # Load and validate the target source BEFORE changing persistent
    # configuration or discarding the current active cache.
    try:
        if mode == 'public':
            candidate = (
                _load_public_iperf3_server_source()
            )
        else:
            candidate = (
                _load_user_iperf3_server_source()
            )

    except Exception as e:
        return {
            'error':
                f'Unable to load {mode} iPerf3 server source: {e}'
        }, 400

    with schedule_lock:
        schedule_snapshot = dict(
            schedule_config
        )

    schedule_reset_needed = False

    if _iperf3_schedule_is_configured(
        schedule_snapshot
    ):
        if not confirm_schedule_reset:
            return {
                'error':
                    'Changing iPerf3 server mode will reset '
                    'the existing iPerf3 scheduled job.',
                'schedule_reset_required': True
            }, 409

        # The schedule reset is folded into the SAME canonical transaction as
        # the server-mode change (one revision / one Group JSON). It is not
        # persisted separately.
        schedule_reset_needed = True

    # Canonical value carries ONLY server_mode. last_public_region is RAM-only
    # runtime state and is corrected in RAM below, never persisted.
    section_updates = {
        'iperf3_server_settings': {'server_mode': mode},
    }
    if schedule_reset_needed:
        section_updates['schedule'] = _safe_empty_schedule()

    # Compute the corrected remembered region for RAM only.
    remembered_region = settings.get('last_public_region', '')
    if mode == 'public':
        valid_regions = candidate.get('regions', [])
        if valid_regions and remembered_region not in valid_regions:
            remembered_region = valid_regions[0]

    # Persist the change(s) as ONE Device-only transaction. The manager handles
    # mutation gating, revision-pair reconciliation, sparse Device section
    # update, and read-back verified writes. Runtime RAM/cache is updated by the
    # hot-reload callback ONLY after a successful write.
    apply = persist_config_section(None, None, updates=section_updates)

    if apply.action == 'reconciled':
        return {'status': 'reconciled', 'error': apply.message}, 409

    if apply.action == 'blocked':
        return {'status': 'upgrade_required', 'error': apply.message,
                'block_reason': apply.block_reason}, 409

    if apply.action != 'saved':
        return {
            'error': apply.message or 'Unable to persist iPerf3 server mode.'
        }, 500

    # Local write succeeded; hot-reload refreshed server_mode in RAM. Set the
    # RAM-only last_public_region to the corrected remembered value (runtime
    # state, never persisted).
    with _iperf3_server_settings_lock:
        if isinstance(_iperf3_server_settings, dict):
            _iperf3_server_settings['last_public_region'] = remembered_region

    # Replace the active server-source cache with the validated candidate.
    with _active_iperf3_server_cache_lock:
        _active_iperf3_server_cache = (
            candidate
        )

    cp.log(
        f'iPerf3 server mode changed to {mode}; '
        f'active cache contains '
        f'{len(candidate.get("servers", []))} servers'
    )

    return (
        _get_active_iperf3_server_state(),
        200
    )




def _find_user_iperf3_server(server_ref, cache=None):
    """Find one cached User server by hidden reference."""
    if cache is None:
        cache = _load_active_iperf3_server_cache()

    if not cache or cache.get('mode') != 'user':
        return None

    for server in cache.get('servers', []):
        if not isinstance(server, dict):
            continue

        current_ref = _user_iperf3_server_ref(
            server.get('server', ''),
            server.get('port', '5201')
        )

        if current_ref == server_ref:
            return server

    return None


def _read_user_iperf3_servers_for_edit():
    """Use active User RAM when available; otherwise read SDK appdata."""
    settings = _load_iperf3_server_settings()

    if settings.get('server_mode') == 'user':
        cache = _load_active_iperf3_server_cache()

        if (
            cache
            and cache.get('mode') == 'user'
            and cache.get('available')
        ):
            return [
                dict(server)
                for server in cache.get('servers', [])
                if isinstance(server, dict)
            ]

    # Effective User Server list from the two-layer manager; legacy is never a
    # fallback once a canonical key exists (§16).
    effective_users = config_mgr.active_section('iperf3_user_servers')
    servers = effective_users if isinstance(effective_users, list) else []

    return [
        dict(server)
        for server in servers
        if isinstance(server, dict)
    ]


def _sync_active_user_iperf3_cache(servers):
    """Replace active User cache after a successful SDK write."""
    global _active_iperf3_server_cache

    settings = _load_iperf3_server_settings()

    if settings.get('server_mode') != 'user':
        return

    normalized = [
        dict(server)
        for server in servers
        if isinstance(server, dict)
    ]

    with _active_iperf3_server_cache_lock:
        _active_iperf3_server_cache = {
            'mode': 'user',
            'available': True,
            'regions': [],
            'servers': normalized,
        }

    _prune_loaded_user_iperf3_stats(
        normalized
    )


def _user_schedule_server_ref():
    """Return the User server ref used by the saved iPerf3 schedule."""
    with schedule_lock:
        config = dict(schedule_config)

    if not _iperf3_schedule_is_configured(config):
        return ''

    params = config.get('params') or {}

    if params.get('server_source') != 'user':
        return ''

    return str(
        params.get('server_ref') or ''
    )


def _user_server_refs(servers):
    """Build hidden references for a User Server List."""
    refs = set()

    for server in servers:
        if not isinstance(server, dict):
            continue

        host = server.get('server', '')

        if not host:
            continue

        refs.add(
            _user_iperf3_server_ref(
                host,
                server.get('port', '5201')
            )
        )

    return refs


# Sentinel returned by _guard_user_server_list_change when the caller must
# fold a schedule reset into the same canonical persistence transaction.
SCHEDULE_RESET_REQUIRED = 'schedule_reset_required'


def _guard_user_server_list_change(
    final_servers,
    confirm_schedule_reset=False
):
    """Protect a scheduled User endpoint from destructive changes.

    Returns:
      - None: no scheduled dependency affected; persist the list normally.
      - dict (409 body): confirmation required before the change.
      - SCHEDULE_RESET_REQUIRED: confirmed; the caller MUST persist the safe
        empty schedule together with the server-list change as ONE canonical
        transaction (do not persist the schedule separately here).
    """
    scheduled_ref = _user_schedule_server_ref()

    if not scheduled_ref:
        return None

    if scheduled_ref in _user_server_refs(
        final_servers
    ):
        return None

    if not confirm_schedule_reset:
        return {
            'error': (
                'This change removes the User iPerf3 server '
                'used by the current scheduled job.'
            ),
            'schedule_reset_required': True
        }

    return SCHEDULE_RESET_REQUIRED


def _persist_last_public_region_after_test(region):
    """Persist last actually-used Public Region after test cleanup."""
    global _iperf3_server_settings

    region = str(
        region or ''
    ).strip()

    if not region:
        return

    settings = _load_iperf3_server_settings()

    if settings.get('server_mode') != 'public':
        return

    if settings.get(
        'last_public_region'
    ) == region:
        return

    cache = _load_active_iperf3_server_cache()

    if region not in cache.get(
        'regions',
        []
    ):
        return

    updated = dict(settings)
    updated['last_public_region'] = region

    try:
        # last_public_region is last-used RUNTIME state: update RAM only.
        # Never persist to canonical (no config_revision bump) or legacy.
        with _iperf3_server_settings_lock:
            _iperf3_server_settings = dict(
                updated
            )

        cp.log(
            f'Updated last Public iPerf3 region after test (RAM): {region}'
        )

    except Exception as e:
        cp.log(
            'Unable to persist last Public iPerf3 region: '
            f'{e}'
        )




# =============================================================================
# IPERF3 USER SERVER LIST SCHEMA / MANAGEMENT
# =============================================================================

def _parse_user_iperf3_port_value(value):
    """Return canonical integer start/end ports from one port or range."""
    if isinstance(value, bool):
        raise ValueError('port cannot be boolean')

    if isinstance(value, int):
        start = value
        end = value
    else:
        raw = str(value or '').strip()
        raw = raw.replace('–', '-').replace('—', '-')

        if not raw:
            raise ValueError('port is required')

        if '-' in raw:
            parts = raw.split('-', 1)

            if (
                not parts[0].strip().isdigit()
                or not parts[1].strip().isdigit()
            ):
                raise ValueError('port range must use start-end')

            start = int(parts[0].strip())
            end = int(parts[1].strip())
        else:
            if not raw.isdigit():
                raise ValueError('port must be numeric')

            start = int(raw)
            end = start

    if not (1 <= start <= end <= 65535):
        raise ValueError(
            'port_start and port_end must be between 1 and 65535'
        )

    return start, end


def _format_user_iperf3_port(start, end):
    """Return compact SDK representation."""
    if start == end:
        return str(start)

    return '{}-{}'.format(start, end)


def _valid_user_iperf3_host(value):
    """Basic syntactic validation for DNS names and IP addresses."""
    host = str(value or '').strip().lower().rstrip('.')

    if (
        not host
        or len(host) > 253
        or any(char.isspace() for char in host)
    ):
        return False

    # Accept IPv4/IPv6 using the Python standard library.
    try:
        import ipaddress
        ipaddress.ip_address(host.strip('[]'))
        return True
    except ValueError:
        pass

    labels = host.split('.')

    for label in labels:
        if not label or len(label) > 63:
            return False

        if label[0] == '-' or label[-1] == '-':
            return False

        for char in label:
            if not (
                char.isalnum()
                or char == '-'
            ):
                return False

    return True


def _normalize_user_iperf3_record(
    server_name,
    host,
    port_start,
    port_end,
    city,
    country
):
    """Validate canonical fields and create compact SDK record."""
    server_name = str(server_name or '').strip()
    host = str(host or '').strip().lower().rstrip('.')
    city = str(city or '').strip()
    country = str(country or '').strip()

    if not server_name:
        raise ValueError('Server Name is required')

    if len(server_name) > 120:
        raise ValueError('Server Name is too long')

    if not _valid_user_iperf3_host(host):
        raise ValueError(
            'DNS Name or IP Address is invalid'
        )

    if not city:
        raise ValueError('City is required')

    if len(city) > 100:
        raise ValueError('City is too long')

    if not country:
        raise ValueError('Country is required')

    if len(country) > 100:
        raise ValueError('Country is too long')

    start, end = _parse_user_iperf3_port_value(
        '{}-{}'.format(port_start, port_end)
        if port_start != port_end
        else port_start
    )

    return {
        'server_name': server_name,
        'server': host,
        'port': _format_user_iperf3_port(start, end),
        'city': city,
        'country': country,
    }


def _external_user_iperf3_entry(record):
    """Convert compact SDK record to canonical external JSON schema."""
    if not isinstance(record, dict):
        raise ValueError('server record is invalid')

    host = str(record.get('server', '')).strip()
    port = record.get('port', '5201')
    start, end = _parse_user_iperf3_port_value(port)

    server_name = str(
        record.get('server_name')
        or host
    ).strip()

    city = str(record.get('city', '')).strip()
    country = str(record.get('country', '')).strip()

    normalized = _normalize_user_iperf3_record(
        server_name,
        host,
        start,
        end,
        city,
        country
    )

    return {
        'server_name': normalized['server_name'],
        'host': normalized['server'],
        'port_start': start,
        'port_end': end,
        'city': normalized['city'],
        'country': normalized['country'],
    }


def _validate_external_user_iperf3_entry(entry):
    """Validate exactly one schema-version-1 external server entry."""
    if not isinstance(entry, dict):
        raise ValueError('server entry must be a JSON object')

    allowed = {
        'server_name',
        'host',
        'port_start',
        'port_end',
        'city',
        'country',
    }

    missing = allowed - set(entry)
    extra = set(entry) - allowed

    if missing:
        raise ValueError(
            'missing field(s): ' + ', '.join(sorted(missing))
        )

    if extra:
        raise ValueError(
            'unsupported field(s): ' + ', '.join(sorted(extra))
        )

    if (
        not isinstance(entry['port_start'], int)
        or isinstance(entry['port_start'], bool)
        or not isinstance(entry['port_end'], int)
        or isinstance(entry['port_end'], bool)
    ):
        raise ValueError(
            'port_start and port_end must be integers'
        )

    return _normalize_user_iperf3_record(
        entry['server_name'],
        entry['host'],
        entry['port_start'],
        entry['port_end'],
        entry['city'],
        entry['country']
    )


def _require_user_iperf3_mode():
    """Return error payload when User Server List is not active."""
    settings = _load_iperf3_server_settings()

    if settings.get('server_mode') != 'user':
        return {
            'error':
                'Switch to User Server List mode before modifying '
                'User iPerf3 servers.'
        }

    return None



# =============================================================================
# MODEM CA CAPABILITY REFERENCE CATALOG
# =============================================================================

_CA_CAPABILITY_CATALOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'modem_ca_capabilities.json'
)
_ca_capability_catalog = None
_ca_capability_catalog_loaded = False
_ca_capability_catalog_lock = threading.Lock()


def _load_ca_capability_catalog():
    """Load and minimally validate the reference-only CA catalog once."""
    global _ca_capability_catalog, _ca_capability_catalog_loaded

    if _ca_capability_catalog_loaded:
        return _ca_capability_catalog

    with _ca_capability_catalog_lock:
        if _ca_capability_catalog_loaded:
            return _ca_capability_catalog

        try:
            with open(_CA_CAPABILITY_CATALOG_PATH, 'r', encoding='utf-8') as f:
                catalog = json.load(f)

            if not isinstance(catalog, dict):
                raise ValueError('catalog root must be an object')
            if catalog.get('schema_version') != 1:
                raise ValueError('unsupported schema_version')
            if catalog.get('reference_only') is not True:
                raise ValueError('catalog must be reference_only')

            families = catalog.get('modem_families')
            devices = catalog.get('devices')
            if not isinstance(families, dict) or not families:
                raise ValueError('modem_families must be a non-empty object')
            if not isinstance(devices, dict) or not devices:
                raise ValueError('devices must be a non-empty object')

            for family, capability in families.items():
                if not isinstance(capability, dict):
                    raise ValueError(f'{family} capability must be an object')
                if not isinstance(capability.get('configurations'), list):
                    raise ValueError(f'{family} configurations must be a list')

            for model, device in devices.items():
                if not isinstance(device, dict):
                    raise ValueError(f'{model} device must be an object')
                variants = device.get('variants')
                if not isinstance(variants, list) or not variants:
                    raise ValueError(f'{model} variants must be a non-empty list')
                for variant in variants:
                    if not isinstance(variant, dict):
                        raise ValueError(f'{model} variant must be an object')
                    family = variant.get('family')
                    if family not in families:
                        raise ValueError(
                            f'{model} variant references unknown family {family}'
                        )

            _ca_capability_catalog = catalog
            cp.log(
                'Loaded modem CA capability catalog '
                f'v{catalog.get("catalog_version", "unknown")}'
            )
        except Exception as e:
            _ca_capability_catalog = None
            cp.log(f'CA capability catalog disabled (non-fatal): {e}')
        finally:
            _ca_capability_catalog_loaded = True

    return _ca_capability_catalog


def _ca_scalar_strings(value, depth=0):
    """Collect interface-local scalar strings used for model matching."""
    if depth > 4:
        return []

    if isinstance(value, dict):
        values = []
        for item in value.values():
            values.extend(_ca_scalar_strings(item, depth + 1))
        return values

    if isinstance(value, (list, tuple)):
        values = []
        for item in value:
            values.extend(_ca_scalar_strings(item, depth + 1))
        return values

    if isinstance(value, str) and value.strip():
        return [value.strip().upper()]

    return []


def _ca_contains_token(text, token):
    """Match a catalog token without partial alpha-numeric matches."""
    text = str(text or '').upper()
    token = str(token or '').strip().upper()
    if not text or not token:
        return False
    return re.search(
        r'(?<![A-Z0-9])' + re.escape(token) + r'(?![A-Z0-9])',
        text
    ) is not None


def _ca_match_device(catalog, text):
    """Match a device using JSON-defined tokens, most specific first."""
    matches = []
    for model, device in catalog.get('devices', {}).items():
        for token in device.get('match_tokens', []):
            if _ca_contains_token(text, token):
                matches.append((len(str(token)), str(token), model))

    if not matches:
        return ''

    return max(matches, key=lambda item: (item[0], item[1]))[2]


def _ca_match_variant(device, text):
    """Match one device variant using JSON-defined tokens."""
    matches = []
    for variant in device.get('variants', []):
        for token in variant.get('match_tokens', []):
            if _ca_contains_token(text, token):
                matches.append((len(str(token)), str(token), variant))

    if not matches:
        return None, ''

    match = max(matches, key=lambda item: (item[0], item[1]))
    return match[2], match[1]


def _ca_match_family(catalog, text):
    """Match an interface-reported modem family across all devices."""
    matches = []
    for device in catalog.get('devices', {}).values():
        for variant in device.get('variants', []):
            family = variant.get('family', '')
            for token in variant.get('match_tokens', []):
                if _ca_contains_token(text, token):
                    matches.append(
                        (len(str(token)), str(token), family, variant)
                    )

    if not matches:
        return '', '', None

    match = max(matches, key=lambda item: (item[0], item[1], item[2]))
    return match[2], match[1], match[3]


def _ca_device_supports_family(catalog, device_model, family):
    """Return True when a device exposes the given family in the catalog."""
    device = catalog.get('devices', {}).get(device_model, {})
    return any(
        variant.get('family') == family
        for variant in device.get('variants', [])
    )


def _ca_variant_reference(
    catalog,
    device_model,
    variant,
    exact_variant=False,
    matched_token=''
):
    """Build one JSON-safe capability row for the UI."""
    if not isinstance(variant, dict):
        return None

    family = variant.get('family', '')
    capability = catalog.get('modem_families', {}).get(family)
    if not isinstance(capability, dict):
        return None

    label = str(variant.get('label') or family)
    generic_tokens = {
        str(token).upper()
        for token in variant.get('generic_match_tokens', [])
    }

    if exact_variant and matched_token:
        token = str(matched_token).upper()
        if token not in generic_tokens:
            label = token

    if exact_variant and device_model:
        prefix = str(device_model).upper() + '-'
        if not label.upper().startswith(prefix):
            label = str(device_model).upper() + '-' + label

    return {
        'label': label,
        'family': family,
        'release': capability.get('release', ''),
        'max_download_ca': capability.get('max_download_ca'),
        'max_upload_ca': capability.get('max_upload_ca'),
        'configurations': [
            dict(item)
            for item in capability.get('configurations', [])
            if isinstance(item, dict)
        ],
        'source_documents': list(capability.get('source_documents', [])),
    }


def _resolve_ca_capability_reference(catalog, modem_text, host_text=''):
    """Resolve interface evidence before considering the host chassis."""
    interface_device = _ca_match_device(catalog, modem_text)
    host_device = _ca_match_device(catalog, host_text)

    if interface_device:
        device = catalog['devices'][interface_device]
        variant, token = _ca_match_variant(device, modem_text)
        if variant:
            reference = _ca_variant_reference(
                catalog,
                interface_device,
                variant,
                exact_variant=True,
                matched_token=token
            )
            if reference:
                return {
                    'catalog_version': catalog.get('catalog_version', ''),
                    'reference_only': True,
                    'device_model': interface_device,
                    'exact_variant': True,
                    'variants': [reference],
                }

    # A captive modem may expose only its modem family, such as 5GC, while
    # the host product identifies an E3000. Interface evidence wins so the
    # captive modem never inherits the host's internal-modem capability.
    family, token, variant = _ca_match_family(catalog, modem_text)
    if family and variant:
        associated_device = ''
        if interface_device and _ca_device_supports_family(
            catalog, interface_device, family
        ):
            associated_device = interface_device
        elif (
            not interface_device and
            host_device and
            _ca_device_supports_family(catalog, host_device, family)
        ):
            associated_device = host_device

        reference = _ca_variant_reference(
            catalog,
            associated_device,
            variant,
            exact_variant=True,
            matched_token=token
        )
        if reference:
            return {
                'catalog_version': catalog.get('catalog_version', ''),
                'reference_only': True,
                'device_model': associated_device,
                'exact_variant': True,
                'variants': [reference],
            }

    if interface_device:
        device = catalog['devices'][interface_device]
        variants = []
        for variant in device.get('variants', []):
            reference = _ca_variant_reference(
                catalog, interface_device, variant
            )
            if reference:
                variants.append(reference)

        if variants:
            return {
                'catalog_version': catalog.get('catalog_version', ''),
                'reference_only': True,
                'device_model': interface_device,
                'exact_variant': False,
                'variants': variants,
            }

    if host_device:
        device = catalog['devices'][host_device]
        variant, token = _ca_match_variant(device, host_text)
        if variant:
            reference = _ca_variant_reference(
                catalog,
                host_device,
                variant,
                exact_variant=True,
                matched_token=token
            )
            if reference:
                return {
                    'catalog_version': catalog.get('catalog_version', ''),
                    'reference_only': True,
                    'device_model': host_device,
                    'exact_variant': True,
                    'variants': [reference],
                }

        variants = []
        for variant in device.get('variants', []):
            reference = _ca_variant_reference(
                catalog, host_device, variant
            )
            if reference:
                variants.append(reference)

        if variants:
            return {
                'catalog_version': catalog.get('catalog_version', ''),
                'reference_only': True,
                'device_model': host_device,
                'exact_variant': False,
                'variants': variants,
            }

    return None


def _get_ca_capability_reference(interface):
    """Return view-only CA capability data for the selected interface."""
    try:
        if not interface or interface == 'auto':
            return None

        catalog = _load_ca_capability_catalog()
        if not catalog:
            return None

        devices = cp.get('status/wan/devices')
        if not isinstance(devices, dict):
            return None

        matched_uid = ''
        matched_dev = None
        for uid, device in devices.items():
            if not isinstance(device, dict):
                continue

            info = device.get('info')
            if not isinstance(info, dict):
                info = {}

            iface = info.get('iface', '')
            if str(uid) == interface or iface == interface:
                info_type = str(info.get('type', '')).lower()
                if str(uid).startswith('mdm-') or info_type == 'mdm':
                    matched_uid = str(uid)
                    matched_dev = device
                break

        if not matched_dev:
            return None

        modem_values = [matched_uid]
        modem_values.extend(_ca_scalar_strings(matched_dev))
        modem_text = ' | '.join(modem_values).upper()
        host_text = _get_product_model()

        return _resolve_ca_capability_reference(
            catalog, modem_text, host_text
        )
    except Exception as e:
        cp.log(f'CA capability reference error (non-fatal): {e}')
        return None


def _add_ca_capabilities_to_history(history):
    """Enrich history responses without modifying saved history or CSV."""
    if not isinstance(history, list):
        return history

    interface_cache = {}
    for entry in history:
        if not isinstance(entry, dict):
            continue

        carrier_activity = entry.get('carrier_activity')
        if not isinstance(carrier_activity, dict):
            continue

        # New results retain the capability reference captured from the
        # tested interface. Only older rows require current-interface fallback.
        if carrier_activity.get('capability'):
            continue

        interface = entry.get('interface', '')
        if interface not in interface_cache:
            interface_cache[interface] = _get_ca_capability_reference(
                interface
            )

        capability = interface_cache.get(interface)
        if capability:
            carrier_activity['capability'] = capability

    return history


def _is_w2255():
    """Return True if the platform is a W2255."""
    return 'W2255' in _get_product_model()


def _is_r980():
    """Return True if the platform is an R980."""
    return 'R980' in _get_product_model()


def _is_e3000():
    """Return True if the platform is an E3000."""
    return 'E3000' in _get_product_model()


def _needs_enhanced_netperf():
    """Return True if this model requires enhanced Netperf lifecycle handling.

    R980 and E3000 need pre-run state inspection, cancellation verification,
    baseline capture, fresh-run transition detection, and bounded retry.
    """
    model = _get_product_model()
    return 'R980' in model or 'E3000' in model


def _is_w2255_726x():
    """Return True if the platform is a W2255 running NCOS 7.26.x.

    This is used to gate W2255-specific workarounds for known speed-test
    limitations on this firmware version.
    """
    _load_platform_cache()
    product = _platform_cache.get('product') or ''
    fw_major = _platform_cache.get('fw_major')
    fw_minor = _platform_cache.get('fw_minor')
    is_w2255 = 'W2255' in product.upper()
    is_726x = (fw_major == 7 and fw_minor == 26)
    return is_w2255 and is_726x


def get_model_capabilities(interface=''):
    """Return capabilities, validation status, and catalog restrictions.

    Validation status and known engine defects come from the JSON catalog.
    Runtime lifecycle safeguards remain code-defined.
    """
    _load_platform_cache()
    validation = _evaluate_device_validation()
    family = validation.get('controller', '')
    validated = (
        validation.get('status')
        == 'validated'
    )

    caps = {
        'model': _platform_cache.get('product') or '',
        'model_family': family,
        'validated': validated,
        'validation_status': validation.get(
            'status',
            'unlisted'
        ),
        'validation_label': validation.get(
            'label',
            ''
        ),
        'validation_catalog_version': validation.get(
            'catalog_version',
            ''
        ),
        'captive_modems': validation.get(
            'captive_modems',
            []
        ),
        'iperf3': True,
        'netperf': True,
        'netperf_enhanced': False,
        'netperf_alert': '',
        'engine_restrictions': {},
        'info_alert': '',
        'ookla': has_ookla(),
    }

    # Catalog-driven engine defects are independent of validation status.
    catalog = _load_device_validation_catalog() or {}

    defect_engines = {
        str(
            entry.get(
                'engine'
            ) or ''
        ).lower()
        for entry in catalog.get(
            'known_defects',
            []
        )
        if isinstance(
            entry,
            dict
        )
    }

    for engine_id in sorted(
        defect_engines
    ):
        defect = _evaluate_known_defect(
            engine_id,
            interface
        )

        if defect.get('blocked'):
            caps[
                'engine_restrictions'
            ][engine_id] = defect

    netperf_defect = caps[
        'engine_restrictions'
    ].get(
        'netperf'
    )

    if netperf_defect:
        caps['netperf'] = False
        caps['netperf_alert'] = (
            netperf_defect.get(
                'message',
                ''
            )
        )

    elif _needs_enhanced_netperf():
        caps['netperf_enhanced'] = True

    if not validated:
        label = (
            validation.get('label')
            or 'This device model'
        )
        caps['info_alert'] = (
            f'Not yet validated — {label} has not been fully '
            'tested with this app. Core functions may work, '
            'but results and feature behavior may vary.'
        )

    return caps


# Generic Netperf lifecycle policy.
#
# Netperf is a router-wide NCOS service. A native test can occasionally
# remain active after its intended duration, including tests started from
# NCM or the local NCOS Diagnostics UI. Application-owned tests use their
# requested duration plus a bounded grace period. Unknown pre-existing
# jobs are respected unless NCOS progress shows they have exceeded a
# conservative stale threshold.
_NETPERF_WATCHDOG_GRACE = 30
_NETPERF_WATCHDOG_MAX = 600
_NETPERF_FOREIGN_STALE_FALLBACK = 120

# NCOS can leave the previous run's terminal output visible briefly after
# run=1 is submitted. Give the new native process a small bounded window to
# expose running/progress before an ambiguous terminal error is accepted.
_NETPERF_FRESH_RUN_GRACE = 5

_NETPERF_ACTIVE_STATUSES = {
    'running',
    'connecting',
    'started',
}


def _netperf_watchdog_budget(duration):
    """Return the bounded wall-clock watchdog for an app-owned test."""
    try:
        seconds = int(duration)
    except (TypeError, ValueError):
        seconds = 10

    seconds = max(seconds, 1)

    return min(
        seconds + _NETPERF_WATCHDOG_GRACE,
        _NETPERF_WATCHDOG_MAX
    )


def _netperf_is_active(output):
    """Return True when NCOS reports an active native Netperf job."""
    if not isinstance(output, dict):
        return False

    return str(
        output.get('status', '') or ''
    ).strip().lower() in _NETPERF_ACTIVE_STATUSES


def _netperf_progress_seconds(output):
    """Return numeric NCOS Netperf progress when available."""
    if not isinstance(output, dict):
        return None

    value = output.get('progress')

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _netperf_command_duration(output):
    """Extract the native netperf -l duration from NCOS output."""
    if not isinstance(output, dict):
        return None

    command = str(
        output.get('command', '') or ''
    )

    match = re.search(
        r'(?:^|\s)-l\s+(\d+)(?:\s|$)',
        command
    )

    if not match:
        return None

    try:
        duration = int(match.group(1))
    except (TypeError, ValueError):
        return None

    return duration if duration > 0 else None


def _netperf_cancel_and_verify(reason='cleanup'):
    """Kill the shared native Netperf job and verify it stopped.

    The first kill gets a five-second verification window. If NCOS still
    reports an active process, one final kill is sent followed by a
    three-second verification window.

    Returns:
        True when Netperf is confirmed inactive, False otherwise.
    """
    try:
        output = cp.get('control/netperf/output')
    except Exception as error:
        cp.log(
            f'Netperf {reason}: unable to inspect service before '
            f'cleanup: {error}'
        )
        output = None

    if not _netperf_is_active(output):
        return True

    for attempt, verify_seconds in (
        (1, 5),
        (2, 3),
    ):
        cp.log(
            f'Netperf {reason}: sending kill '
            f'(attempt {attempt}/2)'
        )

        _netperf_put(
            'control/netperf/run',
            -1
        )

        for _ in range(verify_seconds):
            time.sleep(1)

            try:
                output = cp.get(
                    'control/netperf/output'
                )
            except Exception as error:
                cp.log(
                    f'Netperf {reason}: status read failed '
                    f'during cleanup: {error}'
                )
                continue

            if not _netperf_is_active(output):
                status = ''
                if isinstance(output, dict):
                    status = str(
                        output.get('status', '') or ''
                    )

                cp.log(
                    f'Netperf {reason}: service confirmed '
                    f'stopped (status={status or "cleared"})'
                )
                return True

    cp.log(
        f'Netperf {reason}: WARNING - native service '
        f'remains active after cleanup attempts'
    )

    return False


def _netperf_prepare_shared_service():
    """Ensure the router-wide Netperf service is safe for a new run.

    A legitimate pre-existing job is left alone. A job becomes reclaimable
    when its numeric NCOS progress exceeds either:

      * its native command duration plus the normal watchdog grace; or
      * 120 seconds when NCOS does not expose the original duration.

    Returns:
        Tuple of (ready, message).
    """
    try:
        output = cp.get(
            'control/netperf/output'
        )
    except Exception as error:
        cp.log(
            f'Netperf shared-service preflight read failed: {error}'
        )
        return True, ''

    if not _netperf_is_active(output):
        return True, ''

    progress = _netperf_progress_seconds(
        output
    )

    command_duration = _netperf_command_duration(
        output
    )

    if command_duration is not None:
        stale_after = _netperf_watchdog_budget(
            command_duration
        )
        duration_source = (
            f'native duration={command_duration}s'
        )
    else:
        stale_after = _NETPERF_FOREIGN_STALE_FALLBACK
        duration_source = 'native duration unavailable'

    if (
        progress is not None
        and progress >= stale_after
    ):
        cp.log(
            f'Netperf stale shared job detected: '
            f'progress={progress}s stale_after={stale_after}s '
            f'({duration_source}). Reclaiming service.'
        )

        stopped = _netperf_cancel_and_verify(
            'stale shared-job cleanup'
        )

        if stopped:
            # Give NCOS a short settle window before rewriting
            # the shared input/options state for our new test.
            time.sleep(1)
            return True, ''

        return (
            False,
            'A stale Netperf job was detected but the native '
            'service could not be stopped.'
        )

    progress_text = (
        f'{progress}s'
        if progress is not None
        else 'unknown'
    )

    message = (
        'Netperf service is already active '
        f'(progress={progress_text}, '
        f'stale threshold={stale_after}s).'
    )

    cp.log(
        message
        + ' Existing job will not be interrupted.'
    )

    return False, message


def _w2255_cancel_netperf():
    """Cancel the active netperf process and verify it stopped.

    Used on W2255 when a netperf test times out, to ensure the NCOS
    netperf process is not left running before starting another direction.

    Returns:
        True if netperf is confirmed stopped, False otherwise.
    """
    cp.log('[W2255] Cancelling netperf process (run=-1)')
    _netperf_put('control/netperf/run', -1)
    # Wait briefly and verify
    for _ in range(5):
        time.sleep(1)
        out = cp.get('control/netperf/output')
        if not out:
            return True
        status = out.get('status', '')
        if status != 'running':
            cp.log('[W2255] Netperf process confirmed stopped')
            return True
    cp.log('[W2255] WARNING: Could not verify netperf cancellation')
    return False


def _enhanced_cancel_netperf(tag=''):
    """Cancel the active netperf process and verify it stopped.

    Enhanced lifecycle handler for R980/E3000. Inspects current state,
    cancels if running/connecting, and verifies stopped before returning.

    Args:
        tag: Log tag for traceability (e.g. '[R980]' or '[E3000]').

    Returns:
        True if netperf is confirmed stopped, False otherwise.
    """
    if not tag:
        tag = '[Enhanced]'
    # Inspect current netperf state
    out = cp.get('control/netperf/output')
    if not out:
        return True
    status = out.get('status', '')
    if status not in ('running', 'connecting', 'started'):
        cp.log(f'{tag} Netperf not running (status={status}), no cancel needed')
        return True

    cp.log(f'{tag} Netperf still active (status={status}), cancelling...')
    _netperf_put('control/netperf/run', -1)

    # Verify stopped with bounded wait (max 8 seconds)
    for i in range(8):
        time.sleep(1)
        out = cp.get('control/netperf/output')
        if not out:
            cp.log(f'{tag} Netperf confirmed stopped (output cleared)')
            return True
        status = out.get('status', '')
        if status not in ('running', 'connecting', 'started'):
            cp.log(f'{tag} Netperf confirmed stopped (status={status})')
            return True

    cp.log(f'{tag} WARNING: Could not verify netperf cancellation after 8s')
    return False


def _w2255_validate_netperf_direction(out, recv, send):
    """On W2255, validate that netperf output matches the requested direction.

    W2255 sometimes leaves terminal/error output from the previous netperf
    test. If the output belongs to the opposite direction, treat it as stale.

    Args:
        out: The control/netperf/output dict.
        recv: True if this is a download test.
        send: True if this is an upload test.

    Returns:
        True if the output is valid for this direction, False if stale.
    """
    if not out or not isinstance(out, dict):
        return True
    # Check the options or command echoed in the output
    opts = out.get('options') or out.get('input', {}).get('options') or {}
    if not opts:
        return True
    # If output carries direction info, verify it matches
    out_recv = opts.get('recv', None)
    out_send = opts.get('send', None)
    if out_recv is None and out_send is None:
        return True
    if recv and out_send and not out_recv:
        cp.log('[W2255] Stale output detected: expected recv but output '
               'shows send direction')
        return False
    if send and out_recv and not out_send:
        cp.log('[W2255] Stale output detected: expected send but output '
               'shows recv direction')
        return False
    return True


# =============================================================================
# NETPERF ENGINE
# =============================================================================

# netperf reports where it wrote results as a path like
# /status/wan/devices/mdm-1757f941/status/perf_results. The device UID in that
# path names the WAN device the test actually ran on, which lets us confirm a
# 'complete' status belongs to the run we just started.
_NETPERF_RESULTS_DEV_RE = re.compile(r'/wan/devices/(?P<uid>[^/]+)/')


def _safe_test_bytes(value):
    """Normalize an engine-reported byte count.

    Returns None when the test engine did not provide a usable value.
    Failed or unavailable result paths must not look like measured zero-byte
    transfers and must never fall back to WAN-interface counters.
    """
    if value is None or isinstance(value, bool):
        return None

    try:
        parsed = int(float(value))
    except (TypeError, ValueError, OverflowError):
        return None

    return parsed if parsed >= 0 else None


def _netperf_device_uid(ifc):
    """Resolve an ifc_wan value to the WAN device UID netperf will report.

    The UI sends info.iface values (wan, rmnet501) but netperf writes results
    under the device UID (ethernet-wan, mdm-xxx). Mapping between the two lets
    us verify a result came from the interface we requested.

    Args:
        ifc: An ifc_wan value - either a device UID or an info.iface value.

    Returns:
        The device UID as a string, or '' when it cannot be resolved.
    """
    try:
        devices = cp.get('status/wan/devices') or {}
        if ifc in devices:
            return ifc
        for uid, dev in devices.items():
            if isinstance(dev, dict):
                if dev.get('info', {}).get('iface') == ifc:
                    return uid
    except Exception as e:
        cp.log(f'Error resolving netperf device UID for {ifc}: {e}')
    return ''


def _netperf_result_time(uid, result_key):
    """Read the TIME stamp of a device's stored netperf result.

    Each perf_results entry carries a TIME field that netperf rewrites on
    every run. Comparing it before and after a test detects a stale read even
    when the throughput numbers happen to repeat.

    Args:
        uid: WAN device UID, e.g. mdm-1757f941.
        result_key: One of tcp_down, tcp_up, tcp_rr.

    Returns:
        The TIME string, or '' when unavailable.
    """
    if not uid:
        return ''
    try:
        results = cp.get(
            f'status/wan/devices/{uid}/status/perf_results') or {}
        entry = results.get(result_key) or {}
        return str(entry.get('TIME', '') or '')
    except Exception:
        return ''


def _netperf_time_epoch(time_str):
    """Parse a netperf result TIME stamp into a epoch seconds value.

    Args:
        time_str: TIME field from perf_results, e.g. '2026-08-06 18:00:16'.
            Device local time, the same clock time.time() reads.

    Returns:
        Epoch seconds as a float, or 0.0 when the value cannot be parsed.
    """
    if not time_str:
        return 0.0
    try:
        return time.mktime(time.strptime(str(time_str).strip(),
                                         '%Y-%m-%d %H:%M:%S'))
    except (ValueError, OverflowError):
        return 0.0


def _netperf_limit(duration):
    """Build the netperf limit options for a time-limited test.

    Args:
        duration: Time limit in seconds.

    Returns:
        Mapping with only the time field. Size is intentionally omitted —
        the router's validator rejects writes when both size and time are
        touched independently, and all tests are time-based only.
    """
    return {"time": duration}


def _netperf_put(path, value):
    """PUT one netperf control-tree node and report a rejection.

    Args:
        path: Control-tree path relative to the API root.
        value: Value to write.

    Returns:
        True when the config store accepted the write.
    """
    resp = cp.put(path, value)
    ok = isinstance(resp, dict) and resp.get('status') == 'ok'
    if not ok:
        try:
            detail = json.dumps(resp)
        except (TypeError, ValueError):
            detail = repr(resp)
        cp.log(f'Netperf PUT rejected: {path} <- {value!r} resp={detail}')
    return ok


def _netperf_write_options(options):
    """Write netperf input options one leaf at a time.

    A whole-node PUT to control/netperf silently fails to land on some builds,
    leaving the previous run's options in place. Individual leaf writes are
    accepted reliably, so each option is written on its own path.

    For the `limit` subtree, only `time` is written. Size is never sent —
    leaving it untouched avoids the router's cross-field validator that
    rejects writes when both size and time are modified independently.

    Args:
        options: Mapping of option name to value.

    Returns:
        True when every write was accepted.
    """
    base = 'control/netperf/input/options'
    ok = True
    for name, value in options.items():
        if name == 'limit' and isinstance(value, dict):
            # Write the entire limit subtree as one object. Individual leaf
            # writes to limit/time or limit/size trigger the router's
            # cross-field validator ("Cannot have a data and time limited
            # test") whenever the other field holds a conflicting value from
            # a previous run. A single PUT to the limit node lands atomically
            # and bypasses this issue. Force size=0 so it's always time-only.
            limit_obj = {"time": value.get('time', 10), "size": 0}
            if not _netperf_put(f'{base}/limit', limit_obj):
                ok = False
        else:
            if not _netperf_put(f'{base}/{name}', value):
                ok = False
    return ok


# NCOS default values for control/netperf/input/options. Writing this full
# object before each test clears any residue from previous runs, old app
# versions, or NCM-triggered tests that may have left conflicting values
# (especially limit/size > 0 which blocks subsequent time-only writes).
_NETPERF_DEFAULT_OPTIONS = {
    "limit": {"size": 0, "time": 10},
    "port": None,
    "fwport": None,
    "host": "",
    "ifc_wan": "",
    "tcp": True,
    "udp": False,
    "send": False,
    "recv": True,
    "rr": False
}


def _netperf_reset_options():
    """Reset control/netperf/input/options to NCOS defaults.

    Writes the entire options subtree as a single object so all fields —
    including limit/size and limit/time — land atomically without triggering
    cross-field validation errors.
    """
    cp.put('control/netperf/input/options', _NETPERF_DEFAULT_OPTIONS)


def _netperf_results_device(results_path):
    """Extract the WAN device UID from a netperf results_path.

    Args:
        results_path: The results_path value from control/netperf/output.

    Returns:
        The device UID as a string, or '' when the path has no device segment.
    """
    match = _NETPERF_RESULTS_DEV_RE.search(results_path or '')
    return match.group('uid') if match else ''


def _netperf_ifc_candidates(interface):
    """Build an ordered list of ifc_wan values to try for a speed test.

    Netperf takes info.iface values and rejects device UIDs, so the request is
    resolved against the live device list and info.iface is always tried
    first. The UID is kept as a second candidate because some models accept
    their device dict key instead.

    Args:
        interface: The requested interface, either an info.iface value or a
            device UID. Empty string selects the primary WAN.

    Returns:
        Tuple of (candidates, note). candidates is a list of ifc_wan values
        to try in order, empty when the request matches no WAN device. note
        describes any issue found.
    """
    candidates = []
    note = ''
    try:
        if not interface:
            # Auto mode: use primary WAN device's iface
            primary = cp.get_wan_primary_device()
            if primary:
                primary_iface = cp.get(
                    f'status/wan/devices/{primary}/info/iface') or ''
                if primary_iface:
                    candidates.append(primary_iface)
                else:
                    candidates.append(primary)
            candidates.append('any')
        else:
            # Resolve the request against the live device list, accepting
            # either the info.iface value the UI sends or a device UID.
            devices = cp.get('status/wan/devices') or {}
            matched_uid = ''
            matched_iface = ''
            for uid, dev in devices.items():
                dev_iface = ''
                if isinstance(dev, dict):
                    dev_iface = dev.get('info', {}).get('iface') or ''
                if uid == interface or dev_iface == interface:
                    matched_uid = uid
                    matched_iface = dev_iface
                    break

            if devices and not matched_uid:
                # A selection that matches no current WAN device would only
                # earn a rejection, so report it instead of running.
                return [], f'{interface} is not a current WAN device'

            # netperf wants the info.iface value, so try it first and fall
            # back to the device UID (the W2255 accepts its dict key).
            for value in (matched_iface, matched_uid, interface):
                if value:
                    candidates.append(value)
    except Exception as e:
        cp.log(f'Error building netperf interface candidates: {e}')
        if interface:
            candidates.append(interface)
        else:
            candidates.append('any')

    # Deduplicate, preserving order
    seen = set()
    ordered = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            ordered.append(c)
    return ordered, note


def run_netperf(interface='', duration=10, direction='both', include_latency=False, host=''):
    """Run a speed test using the router's built-in netperf service."""
    global current_test
    try:
        ifc_candidates, ifc_note = _netperf_ifc_candidates(interface)
        if ifc_note:
            cp.log(f'Netperf interface warning: {ifc_note}')
        if not ifc_candidates:
            cp.log(f'Netperf aborted: cannot resolve interface '
                   f'{interface or "auto"} to a WAN device')
            return None
        cp.log(f'Netperf interface requested={interface or "auto"} '
               f'resolved ifc_wan candidates={ifc_candidates}')
        if not interface:
            interface = ifc_candidates[0] if ifc_candidates else 'any'

        results = {
            'download_bps': 0,
            'upload_bps': 0,
            'download_bytes': None,
            'upload_bytes': None,
            'test_duration': duration,
            'interface': interface,
            'protocol': 'tcp'
        }

        # Successful traffic windows are populated only by the attempt that
        # ultimately produces valid throughput. Failed interface candidates,
        # startup failures, timeouts, and retries do not survive here.
        _netperf_phase_windows = {
            'download': None,
            'upload': None,
        }

        # Netperf is a router-wide service shared with NCM and the local
        # NCOS Diagnostics UI. Respect a legitimate existing test, but
        # reclaim one that has clearly exceeded its stale threshold.
        netperf_ready, netperf_busy_message = (
            _netperf_prepare_shared_service()
        )

        if not netperf_ready:
            results['error'] = netperf_busy_message
            return results

        def _run_netperf_direction(recv, send):
            """Run one netperf direction, trying each ifc_wan candidate.

            Only an immediate rejection advances to the next candidate. A
            timeout gives up, so a stuck netperf cannot multiply into several
            40-second waits.

            Returns:
                Tuple of (result, winning_ifc). winning_ifc is the ifc_wan
                value that was accepted (even if the test timed out), so
                subsequent tests can skip the rejection cycle.
            """
            for attempt, ifc in enumerate(ifc_candidates):
                result, rejected = _netperf_attempt(recv, send, ifc)
                if not rejected:
                    if attempt > 0 and result is not None:
                        cp.log(f'Netperf succeeded with ifc_wan={ifc} '
                               f'(candidate {attempt + 1})')
                    elif attempt > 0 and result is None:
                        cp.log(f'Netperf accepted ifc_wan={ifc} but test '
                               f'failed/timed out (candidate {attempt + 1})')
                    return result, ifc
                if attempt + 1 < len(ifc_candidates):
                    cp.log(f'Netperf rejected ifc_wan={ifc}, trying '
                           f'{ifc_candidates[attempt + 1]}')
            return None, ifc_candidates[0] if ifc_candidates else 'any'

        def _netperf_attempt(recv, send, ifc):
            """Run netperf for one ifc_wan value.

            Returns:
                Tuple of (result, rejected). rejected is True only when
                netperf refused the request outright, meaning another
                interface value is worth trying.
            """
            options = {
                "limit": _netperf_limit(duration),
                "port": None,
                "fwport": None,
                "host": host,
                "ifc_wan": ifc,
                "tcp": True,
                "udp": False,
                "send": send,
                "recv": recv,
                "rr": False
            }

            phase_name = 'download' if recv else 'upload'

            # Every new attempt starts with no accepted traffic window.
            # Only a successfully completed attempt may populate it.
            _netperf_phase_windows[phase_name] = None

            # W2255/7.26.x mode flag — gates additional polling safeguards
            _w2255_mode = _is_w2255_726x()
            if _w2255_mode and not hasattr(_netperf_attempt, '_w2255_logged'):
                cp.log('[W2255] NCOS 7.26.x detected — enabling enhanced '
                       'netperf stale-result validation')
                _netperf_attempt._w2255_logged = True

            # R980/E3000 enhanced lifecycle mode
            _enhanced = _needs_enhanced_netperf()
            _enh_tag = '[R980/E3000]'
            _enh_new_run_seen = False

            # Reset state. Clear before AND after (after is in the completion
            # handler) to ensure we never read stale data regardless of how
            # quickly tests are run back-to-back.
            cp.put('/state/system/netperf', {"run_count": 0})
            time.sleep(2)

            # Reset the entire netperf input options tree to NCOS defaults
            # before writing our test params. This prevents residue from
            # previous tests, old app versions, or NCM-triggered runs from
            # polluting the current test configuration.
            _netperf_reset_options()

            # The device UID netperf should report for this interface. Used to
            # reject a leftover 'complete' from a run on a different device.
            expected_uid = _netperf_device_uid(ifc)

            # Snapshot the existing result timestamp so a repeat of the same
            # throughput numbers can still be recognized as stale.
            result_key = 'tcp_down' if recv else 'tcp_up'
            prior_time = _netperf_result_time(expected_uid, result_key)

            # Write the options as individual leaves, then trigger the run.
            # Each PUT response is checked so a refused write is visible in
            # the log instead of surfacing later as another run's numbers.
            _netperf_write_options(options)
            _netperf_put('control/netperf/input/tests', None)

            # Confirm netperf stored the interface we asked for. A mismatch
            # means the request did not take, so nothing it reports later
            # can be attributed to this interface.
            applied = cp.get('control/netperf/input/options/ifc_wan')
            if applied is not None and applied != ifc:
                cp.log(f'Netperf ifc_wan readback mismatch: sent {ifc} but '
                       f'control/netperf holds {applied!r}')
                return None, False

            # Trigger the run. Netperf accepts 1 to start and -1 to cancel;
            # 0 is not a valid value, and writing 1 starts a fresh run even
            # when the node already holds 1.
            started_at = time.time()
            traffic_started_at = None

            # Snapshot the shared native output immediately before run=1.
            # NCOS can retain the previous phase's complete/error state while
            # the new native process is still obtaining credentials.
            _pre_run_output = cp.get('control/netperf/output')
            _fresh_run_seen = False
            _stale_terminal_logged = False

            # W2255 keeps its additional platform-specific validation, but
            # shares the same pre-run snapshot used by the generic guard.
            _w2255_pre_run_snapshot = None
            _w2255_new_run_seen = False
            if _w2255_mode:
                _w2255_pre_run_snapshot = _pre_run_output
                cp.log('[W2255] Waiting for fresh Netperf run state')

            # Enhanced (R980/E3000): capture baseline result state before run
            _enh_baseline_time = ''
            _enh_baseline_guid = ''
            if _enhanced:
                _enh_baseline_time = _netperf_result_time(
                    expected_uid, result_key)
                # Use the TIME as a pseudo-GUID for baseline comparison
                _enh_baseline_guid = _enh_baseline_time
                cp.log(f'{_enh_tag} Baseline: {result_key} TIME='
                       f'{_enh_baseline_time or "empty"} on '
                       f'{expected_uid or "unknown"}')

            phase_attempt_started_at = time.monotonic()
            _netperf_put('control/netperf/run', 1)

            cp.log(f'Netperf started: recv={recv} send={send} '
                   f'ifc_wan={ifc} device={expected_uid or "unknown"} '
                   f'host={host or "auto"} '
                   f'duration={duration}')

            # Poll for completion. The rejection of a bad ifc_wan candidate
            # clears the stale "complete" from the output, so the next
            # "complete" we see is fresh from this run.
            last_out = None
            stale_logged = False
            budget = _netperf_watchdog_budget(
                duration
            )
            deadline = time.monotonic() + budget
            while time.monotonic() < deadline:
                if not current_test['running']:
                    _netperf_cancel_and_verify(
                        'user-cancel cleanup'
                    )
                    return None, False
                out = cp.get('control/netperf/output')
                if out is not None:
                    last_out = out
                if out:
                    status = out.get('status', '')
                    # progress is a 'done' string on some platforms and a
                    # climbing integer on others, so compare it as text.
                    progress = str(out.get('progress', '') or '').lower()

                    # Generic fresh-run evidence. This prevents a terminal
                    # state inherited from the prior phase from being treated
                    # as the result of the run we just requested.
                    if not _fresh_run_seen:
                        if status == 'running':
                            _fresh_run_seen = True
                            cp.log(
                                f'Netperf fresh {phase_name} run transition '
                                f'detected (status=running)'
                            )
                        elif progress and progress not in ('done', ''):
                            try:
                                if int(progress) > 0:
                                    _fresh_run_seen = True
                                    cp.log(
                                        f'Netperf fresh {phase_name} run '
                                        f'transition detected '
                                        f'(progress={progress})'
                                    )
                            except (ValueError, TypeError):
                                pass

                    # W2255: do not accept any terminal output until we have
                    # evidence the NEW run has actually started. Evidence is
                    # seeing status=='running' or a progress value that
                    # differs from the pre-run snapshot.
                    if _w2255_mode and not _w2255_new_run_seen:
                        if status == 'running':
                            _w2255_new_run_seen = True
                            cp.log('[W2255] Fresh Netperf run detected')
                        else:
                            # Check if progress changed from snapshot
                            snap_progress = ''
                            if _w2255_pre_run_snapshot:
                                snap_progress = str(
                                    _w2255_pre_run_snapshot.get(
                                        'progress', '') or '').lower()
                            if (progress and progress != snap_progress
                                    and progress not in ('done', '')):
                                _w2255_new_run_seen = True
                                cp.log('[W2255] Fresh Netperf run detected')
                            else:
                                # Terminal output without evidence of new run
                                # — this is inherited from the previous run.
                                if (status in ('complete', 'error')
                                        or progress == 'done'
                                        or out.get('error')):
                                    cp.log('[W2255] Ignoring pre-run/stale '
                                           'terminal output')
                                    time.sleep(1)
                                    continue

                    # Enhanced (R980/E3000): require fresh-run transition
                    # before accepting any terminal status. Evidence is
                    # status=='running' or numeric progress > 0.
                    if _enhanced and not _enh_new_run_seen:
                        if status == 'running':
                            _enh_new_run_seen = True
                            cp.log(f'{_enh_tag} Fresh run transition '
                                   f'detected (status=running)')
                        elif progress and progress not in ('done', ''):
                            try:
                                if int(progress) > 0:
                                    _enh_new_run_seen = True
                                    cp.log(f'{_enh_tag} Fresh run transition '
                                           f'detected (progress={progress})')
                            except (ValueError, TypeError):
                                pass
                        if not _enh_new_run_seen:
                            if status in ('complete', 'error') or progress == 'done':
                                cp.log(f'{_enh_tag} Ignoring pre-run '
                                       f'terminal output (status={status})')
                                time.sleep(1)
                                continue

                    # Record when NCOS proves this throughput operation is
                    # actually running. This becomes phase 0s instead of the
                    # earlier run=1 request/setup timestamp.
                    if traffic_started_at is None:
                        if status == 'running':
                            traffic_started_at = time.monotonic()
                            cp.log(
                                f'Carrier telemetry: Netperf {phase_name} '
                                f'traffic start detected (status=running)'
                            )
                        elif progress and progress not in ('done', ''):
                            try:
                                if int(progress) > 0:
                                    traffic_started_at = time.monotonic()
                                    cp.log(
                                        f'Carrier telemetry: Netperf '
                                        f'{phase_name} traffic start '
                                        f'detected (progress={progress})'
                                    )
                            except (ValueError, TypeError):
                                pass

                    # W2255: validate output direction matches our request.
                    # The W2255 sometimes retains output from the previous
                    # direction's test.
                    if _w2255_mode and (status == 'complete'
                                        or progress == 'done'):
                        if not _w2255_validate_netperf_direction(
                                out, recv, send):
                            time.sleep(1)
                            continue

                    if status == 'error' or out.get('error'):
                        # Error output needs the same freshness protection as
                        # completed results. NCOS can retain the previous
                        # direction's terminal error after run=1 while the new
                        # native test is still starting.
                        if not _fresh_run_seen:
                            stale_reason = ''

                            if out == _pre_run_output:
                                stale_reason = 'matches pre-run snapshot'

                            command = str(
                                out.get('command', '') or ''
                            )
                            pre_command = ''
                            if isinstance(_pre_run_output, dict):
                                pre_command = str(
                                    _pre_run_output.get(
                                        'command', ''
                                    ) or ''
                                )

                            if (
                                not stale_reason
                                and command
                                and pre_command
                                and command == pre_command
                            ):
                                stale_reason = (
                                    'command unchanged from previous run'
                                )

                            command_direction = ''
                            if command:
                                direction_match = re.search(
                                    r'(?:^|\s)-d\s+'
                                    r'(recv|send)(?:\s|$)',
                                    command
                                )
                                if direction_match:
                                    command_direction = (
                                        direction_match.group(1)
                                    )

                            expected_direction = (
                                'recv' if recv else 'send'
                            )

                            if (
                                not stale_reason
                                and command_direction
                                and command_direction
                                    != expected_direction
                            ):
                                stale_reason = (
                                    f'command direction='
                                    f'{command_direction}, expected='
                                    f'{expected_direction}'
                                )

                            terminal_results_path = str(
                                out.get('results_path', '') or ''
                            )
                            terminal_uid = (
                                _netperf_results_device(
                                    terminal_results_path
                                )
                            )

                            if (
                                not stale_reason
                                and expected_uid
                                and terminal_uid
                                and terminal_uid != expected_uid
                            ):
                                stale_reason = (
                                    f'results device={terminal_uid}, '
                                    f'expected={expected_uid}'
                                )

                            startup_elapsed = (
                                time.monotonic()
                                - phase_attempt_started_at
                            )

                            # If the terminal output is positively identified
                            # as stale, keep waiting regardless of age. If it
                            # is ambiguous, allow a short startup grace for
                            # NCOS to expose the new running state. After the
                            # grace expires, a changed/matching terminal error
                            # is treated as a legitimate immediate rejection.
                            if (
                                stale_reason
                                or startup_elapsed
                                    < _NETPERF_FRESH_RUN_GRACE
                            ):
                                if not _stale_terminal_logged:
                                    reason = (
                                        stale_reason
                                        or 'waiting for fresh run transition'
                                    )
                                    cp.log(
                                        f'Netperf ignoring stale/pre-run '
                                        f'{phase_name} terminal error: '
                                        f'{reason}'
                                    )
                                    _stale_terminal_logged = True

                                time.sleep(1)
                                continue

                        err = str(out.get('error', status) or '')
                        cp.log(f'Netperf error (ifc_wan={ifc}): {err} '
                               f'full_output={json.dumps(out)}')
                        rejected = 'no wan connection' in err.lower()
                        return None, rejected
                    if status == 'complete' or progress == 'done':
                        results_path = out.get('results_path', '')
                        actual_uid = _netperf_results_device(results_path)
                        # A 'complete' naming a different device is a leftover
                        # from an earlier run, not our result. Keep waiting
                        # rather than reporting another interface's throughput.
                        if (expected_uid and actual_uid
                                and actual_uid != expected_uid):
                            if not stale_logged:
                                cp.log(f'Netperf ignoring stale result: '
                                       f'requested ifc_wan={ifc} '
                                       f'(device={expected_uid}) but '
                                       f'results_path names {actual_uid}')
                                stale_logged = True
                            time.sleep(1)
                            continue
                        if results_path:
                            result = cp.get(results_path.lstrip('/'))
                            if result:
                                # A terminal Netperf status is not enough
                                # to prove the requested direction completed.
                                # NCOS can briefly expose the previous
                                # direction's terminal output while the new
                                # native test is still starting. Require the
                                # expected result key and its TIME field on
                                # every platform before applying freshness
                                # checks or accepting the result.
                                if result_key not in result:
                                    if not stale_logged:
                                        cp.log(
                                            f'Netperf complete but '
                                            f'{result_key} missing from '
                                            f'results, continuing poll')
                                        stale_logged = True
                                    time.sleep(1)
                                    continue

                                entry = result.get(result_key) or {}
                                new_time = str(entry.get('TIME', '') or '')

                                if not new_time:
                                    if not stale_logged:
                                        cp.log(
                                            f'Netperf complete but '
                                            f'{result_key} has no TIME, '
                                            f'continuing poll')
                                        stale_logged = True
                                    time.sleep(1)
                                    continue
                                # The result must be newer than this run, not
                                # merely different from the snapshot. A device
                                # holding several old results can otherwise
                                # flip between two of them and look fresh.
                                # Allow a small skew for clock granularity.
                                result_epoch = _netperf_time_epoch(new_time)
                                too_old = (result_epoch > 0
                                           and result_epoch < started_at - 5)
                                unchanged = (prior_time and new_time
                                             and new_time == prior_time)
                                if too_old or unchanged:
                                    if not stale_logged:
                                        age = int(started_at - result_epoch)
                                        detail = (f'{age}s older than this run'
                                                  if too_old else 'unchanged')
                                        cp.log(f'Netperf waiting: '
                                               f'{result_key} TIME '
                                               f'{new_time} on '
                                               f'{expected_uid} is {detail}')
                                        stale_logged = True
                                    time.sleep(1)
                                    continue
                                cp.log(f'Netperf complete on '
                                       f'device={actual_uid or "unknown"} '
                                       f'{result_key} TIME={new_time or "n/a"}')

                                # Capture the traffic window now, before the
                                # R980/E3000 result-settle delay. If this
                                # platform never exposed running/progress,
                                # fall back to the run=1 trigger timestamp for
                                # this successfully completed attempt.
                                traffic_ended_at = time.monotonic()

                                if traffic_started_at is None:
                                    traffic_started_at = phase_attempt_started_at
                                    cp.log(
                                        f'Carrier telemetry: Netperf '
                                        f'{phase_name} start transition not '
                                        f'exposed; using run trigger time'
                                    )

                                _netperf_phase_windows[phase_name] = (
                                    traffic_started_at,
                                    traffic_ended_at
                                )

                                # Enhanced (R980/E3000): bounded settle window
                                # Allow 2-5 sec for fresh results to stabilize
                                if _enhanced:
                                    cp.log(f'{_enh_tag} Settle window: '
                                           f're-reading results after 3s')
                                    time.sleep(3)
                                    settled = cp.get(
                                        results_path.lstrip('/'))
                                    if settled:
                                        s_entry = settled.get(
                                            result_key) or {}
                                        s_time = str(
                                            s_entry.get('TIME', '') or '')
                                        # Use the settled read if it has a
                                        # newer or equal timestamp
                                        s_epoch = _netperf_time_epoch(s_time)
                                        if s_epoch >= result_epoch:
                                            result = settled
                                            cp.log(f'{_enh_tag} Using '
                                                   f'settled result '
                                                   f'TIME={s_time}')
                                # Clear the output so next test starts clean
                                cp.put('/state/system/netperf',
                                       {"run_count": 0})
                                return result, False
                time.sleep(1)
            # Hard watchdog expired. Always reclaim the app-owned
            # native Netperf process before returning the timeout.
            last_txt = (
                json.dumps(last_out)
                if last_out is not None
                else 'None'
            )

            cp.log(
                f'Netperf poll timed out after {budget}s '
                f'(ifc_wan={ifc}). last_output={last_txt}'
            )

            cleanup_ok = _netperf_cancel_and_verify(
                'watchdog-timeout cleanup'
            )

            if not cleanup_ok:
                cp.log(
                    'Netperf timeout cleanup could not confirm '
                    'the native service stopped'
                )

            return None, False

        # Download test
        winning_ifc = None
        _enhanced_mode = _needs_enhanced_netperf()
        _enhanced_tag = '[R980/E3000]' if _enhanced_mode else ''
        _dl_retry_used = False

        if direction in ('recv', 'both'):
            # Enhanced lifecycle: verify netperf is idle before starting
            if _enhanced_mode:
                _enhanced_cancel_netperf(_enhanced_tag)
                time.sleep(1)

            with test_lock:
                current_test['progress'] = {
                    'stage': 'download',
                    'percent': 0
                }
            dl, winning_ifc = _run_netperf_direction(recv=True, send=False)

            # Enhanced lifecycle: on timeout (dl is None), retry once
            if _enhanced_mode and dl is None and not _dl_retry_used:
                _dl_retry_used = True
                cp.log(f'{_enhanced_tag} Download returned None, '
                       f'cancelling and retrying once')
                cancelled = _enhanced_cancel_netperf(_enhanced_tag)
                if cancelled:
                    time.sleep(3)
                    dl, winning_ifc = _run_netperf_direction(
                        recv=True, send=False)
                else:
                    cp.log(f'{_enhanced_tag} Cannot confirm netperf stopped, '
                           f'skipping download retry')

            if dl and 'tcp_down' in dl:
                tp = dl['tcp_down']
                if tp and 'THROUGHPUT' in tp:
                    results['download_bps'] = cp._convert_throughput(
                        float(tp['THROUGHPUT']),
                        tp.get('THROUGHPUT_UNITS', ''))

                    download_bytes = _safe_test_bytes(
                        tp.get('LOCAL_BYTES_RECVD')
                    )

                    if download_bytes is None:
                        download_bytes = _safe_test_bytes(
                            tp.get('REMOTE_BYTES_SENT')
                        )

                    if results['download_bps'] > 0:
                        results['download_bytes'] = download_bytes

                    download_window = _netperf_phase_windows.get(
                        'download'
                    )

                    if results['download_bps'] > 0 and download_window:
                        _record_carrier_phase_window(
                            'download',
                            download_window[0],
                            download_window[1]
                        )

                    cp.log(f'Download: {tp["THROUGHPUT"]} {tp.get("THROUGHPUT_UNITS", "")}')
                    cp.log(
                        'Netperf download engine data: '
                        f'{results.get("download_bytes")} bytes'
                    )

            # Once we know which ifc_wan works, promote it to the front
            # so upload and TCP_RR don't waste time on rejected candidates.
            if winning_ifc and winning_ifc != ifc_candidates[0]:
                ifc_candidates = [winning_ifc] + [c for c in ifc_candidates
                                                   if c != winning_ifc]

            if direction == 'both':
                # Enhanced lifecycle: verify download process is completely
                # stopped before starting upload
                if _enhanced_mode:
                    cp.log(f'{_enhanced_tag} Verifying download process '
                           f'stopped before upload')
                    stopped = _enhanced_cancel_netperf(_enhanced_tag)
                    if not stopped:
                        cp.log(f'{_enhanced_tag} Cannot confirm download '
                               f'stopped — aborting upload')
                        results['error'] = (
                            'Download process could not be confirmed stopped. '
                            'Upload skipped to prevent conflicts.')
                        return results
                    time.sleep(2)
                # W2255: if download returned None (timed out), verify
                # cleanup before allowing upload to proceed.
                elif _is_w2255_726x() and dl is None:
                    cp.log('[W2255] Download timed out in bidirectional test, '
                           'verifying netperf cleanup before upload')
                    cleanup_ok = _w2255_cancel_netperf()
                    if not cleanup_ok:
                        cp.log('[W2255] Cannot verify netperf cleanup after '
                               'download timeout — aborting upload')
                        results['error'] = (
                            'W2255: download timed out and netperf process '
                            'could not be confirmed stopped. Upload skipped.')
                        return results
                    time.sleep(2)
                else:
                    time.sleep(3)

        # Upload test
        _ul_retry_used = False
        if direction in ('send', 'both'):
            # Enhanced lifecycle: verify netperf is idle before upload
            if _enhanced_mode:
                _enhanced_cancel_netperf(_enhanced_tag)
                time.sleep(1)

            with test_lock:
                current_test['progress'] = {
                    'stage': 'upload',
                    'percent': 0
                }
            ul, ul_ifc = _run_netperf_direction(recv=False, send=True)

            # Enhanced lifecycle: on timeout, retry once
            if _enhanced_mode and ul is None and not _ul_retry_used:
                _ul_retry_used = True
                cp.log(f'{_enhanced_tag} Upload returned None, '
                       f'cancelling and retrying once')
                cancelled = _enhanced_cancel_netperf(_enhanced_tag)
                if cancelled:
                    time.sleep(3)
                    ul, ul_ifc = _run_netperf_direction(
                        recv=False, send=True)
                else:
                    cp.log(f'{_enhanced_tag} Cannot confirm netperf stopped, '
                           f'skipping upload retry')

            if ul_ifc and not winning_ifc:
                winning_ifc = ul_ifc
            if ul and 'tcp_up' in ul:
                tp = ul['tcp_up']
                if tp and 'THROUGHPUT' in tp:
                    results['upload_bps'] = cp._convert_throughput(
                        float(tp['THROUGHPUT']),
                        tp.get('THROUGHPUT_UNITS', ''))

                    upload_bytes = _safe_test_bytes(
                        tp.get('LOCAL_BYTES_SENT')
                    )

                    if upload_bytes is None:
                        upload_bytes = _safe_test_bytes(
                            tp.get('REMOTE_BYTES_RECVD')
                        )

                    if results['upload_bps'] > 0:
                        results['upload_bytes'] = upload_bytes

                    upload_window = _netperf_phase_windows.get(
                        'upload'
                    )

                    if results['upload_bps'] > 0 and upload_window:
                        _record_carrier_phase_window(
                            'upload',
                            upload_window[0],
                            upload_window[1]
                        )

                    cp.log(f'Upload: {tp["THROUGHPUT"]} {tp.get("THROUGHPUT_UNITS", "")}')
                    cp.log(
                        'Netperf upload engine data: '
                        f'{results.get("upload_bytes")} bytes'
                    )
            elif ul:
                cp.log(f'Upload result missing tcp_up key. Got: {list(ul.keys())}')

        # TCP RR Latency/Jitter test (optional)
        if include_latency:
            if direction == 'both':
                time.sleep(3)
            with test_lock:
                current_test['progress'] = {
                    'stage': 'latency',
                    'percent': 0
                }
            # Use the winning interface from download/upload
            rr_ifc = winning_ifc or ifc_candidates[0] if ifc_candidates else 'any'
            rr_options = {
                # Latency is always measured over a fixed interval, so the
                # request-response test stays time-limited even when the
                # throughput tests were data-limited.
                "limit": _netperf_limit(duration),
                "port": None,
                "fwport": None,
                "host": host,
                "ifc_wan": rr_ifc,
                "tcp": True,
                "udp": False,
                "send": False,
                "recv": False,
                "rr": True
            }
            # Reset state and clean options to defaults
            cp.put('control/netperf/stop', '')
            time.sleep(1)
            cp.put('/state/system/netperf', {"run_count": 0})
            time.sleep(1)
            _netperf_reset_options()
            rr_expected_uid = _netperf_device_uid(rr_ifc)
            # Same granular write path as the throughput tests.
            _netperf_write_options(rr_options)
            _netperf_put('control/netperf/input/tests', None)
            rr_applied = cp.get('control/netperf/input/options/ifc_wan')
            if rr_applied is not None and rr_applied != rr_ifc:
                cp.log(f'Netperf RR ifc_wan readback mismatch: sent {rr_ifc} '
                       f'but control/netperf holds {rr_applied!r}')
            _netperf_put('control/netperf/run', 1)
            cp.log(f'Netperf TCP_RR started: ifc_wan={rr_ifc} '
                   f'device={rr_expected_uid or "unknown"}')

            # TCP_RR freshness tracking. NCOS can briefly expose terminal
            # output from the preceding throughput test after TCP_RR starts.
            _rr_w2255_mode = _is_w2255_726x()
            _rr_enhanced_mode = _enhanced_mode
            _rr_enh_new_run_seen = False
            _rr_prior_time = ''
            if _rr_w2255_mode:
                _rr_prior_time = _netperf_result_time(
                    rr_expected_uid, 'tcp_rr')
            _rr_started_at = time.time()
            _rr_stale_logged = False
            _rr_missing_result_logged = False

            rr_budget = _netperf_watchdog_budget(
                duration
            )
            rr_deadline = (
                time.monotonic()
                + rr_budget
            )
            rr_terminal_seen = False
            rr_user_cancelled = False

            while time.monotonic() < rr_deadline:
                if not current_test['running']:
                    rr_user_cancelled = True
                    _netperf_cancel_and_verify(
                        'TCP_RR user-cancel cleanup'
                    )
                    break
                out = cp.get('control/netperf/output')
                if out:
                    status = out.get('status', '')
                    # See the throughput loop: progress may be numeric.
                    progress = str(out.get('progress', '') or '').lower()

                    # R980/E3000: do not accept terminal output until NCOS
                    # proves that this TCP_RR run actually started.
                    if _rr_enhanced_mode and not _rr_enh_new_run_seen:
                        if status == 'running':
                            _rr_enh_new_run_seen = True
                            cp.log(
                                f'{_enhanced_tag} TCP_RR fresh run transition '
                                f'detected (status=running)'
                            )
                        elif progress and progress not in ('done', ''):
                            try:
                                if int(progress) > 0:
                                    _rr_enh_new_run_seen = True
                                    cp.log(
                                        f'{_enhanced_tag} TCP_RR fresh run '
                                        f'transition detected '
                                        f'(progress={progress})'
                                    )
                            except (ValueError, TypeError):
                                pass

                        if not _rr_enh_new_run_seen:
                            if (status in ('complete', 'error')
                                    or progress == 'done'
                                    or out.get('error')):
                                if not _rr_stale_logged:
                                    cp.log(
                                        f'{_enhanced_tag} Ignoring pre-run '
                                        f'TCP_RR terminal output '
                                        f'(status={status})'
                                    )
                                    _rr_stale_logged = True
                                time.sleep(1)
                                continue

                    if status == 'error' or out.get('error'):
                        rr_terminal_seen = True
                        cp.log(
                            f'Netperf RR error: '
                            f'{out.get("error", status)}'
                        )
                        break
                    if status == 'complete' or progress == 'done':
                        results_path = out.get('results_path', '')
                        rr_actual_uid = _netperf_results_device(results_path)
                        # Skip a leftover result from a different device
                        if (rr_expected_uid and rr_actual_uid
                                and rr_actual_uid != rr_expected_uid):
                            time.sleep(1)
                            continue
                        if results_path:
                            rr_data = cp.get(results_path.lstrip('/'))

                            # A completed TCP_RR operation must contain a
                            # tcp_rr result. NCOS may temporarily leave the
                            # previous throughput result exposed while the
                            # new request-response test is starting.
                            if not rr_data or 'tcp_rr' not in rr_data:
                                if not _rr_missing_result_logged:
                                    cp.log(
                                        'TCP_RR terminal output missing '
                                        'tcp_rr result, continuing poll'
                                    )
                                    _rr_missing_result_logged = True
                                time.sleep(1)
                                continue

                            # W2255: require tcp_rr key with fresh TIME
                            if _rr_w2255_mode and rr_data:
                                rr_entry = rr_data.get('tcp_rr') or {}
                                rr_time = str(
                                    rr_entry.get('TIME', '') or '')
                                if 'tcp_rr' not in rr_data or not rr_time:
                                    if not _rr_stale_logged:
                                        cp.log(
                                            '[W2255] TCP_RR complete but '
                                            'tcp_rr key/TIME missing, '
                                            'continuing poll')
                                        _rr_stale_logged = True
                                    time.sleep(1)
                                    continue
                                rr_epoch = _netperf_time_epoch(rr_time)
                                rr_too_old = (rr_epoch > 0
                                              and rr_epoch
                                              < _rr_started_at - 5)
                                rr_unchanged = (_rr_prior_time and rr_time
                                                and rr_time
                                                == _rr_prior_time)
                                if rr_too_old or rr_unchanged:
                                    if not _rr_stale_logged:
                                        cp.log(
                                            f'[W2255] TCP_RR TIME '
                                            f'{rr_time} is stale, '
                                            f'continuing poll')
                                        _rr_stale_logged = True
                                    time.sleep(1)
                                    continue

                            cp.log(f'TCP_RR result: {json.dumps(rr_data)}')
                            if rr_data and 'tcp_rr' in rr_data:
                                rr = rr_data['tcp_rr']
                                # Latency is in microseconds, convert to ms
                                if 'MEAN_LATENCY' in rr:
                                    results['latency_ms'] = float(
                                        rr['MEAN_LATENCY']) / 1000.0
                                elif 'RT_LATENCY' in rr:
                                    results['latency_ms'] = float(
                                        rr['RT_LATENCY']) / 1000.0
                                if 'P50_LATENCY' in rr:
                                    results['p50_latency_ms'] = float(
                                        rr['P50_LATENCY']) / 1000.0
                                if 'P99_LATENCY' in rr:
                                    results['p99_latency_ms'] = float(
                                        rr['P99_LATENCY']) / 1000.0
                                if 'STDDEV_LATENCY' in rr:
                                    results['jitter_ms'] = float(
                                        rr['STDDEV_LATENCY']) / 1000.0
                                elif 'MIN_LATENCY' in rr and 'MAX_LATENCY' in rr:
                                    # Approximate jitter as (max - min) / 2
                                    min_lat = float(rr['MIN_LATENCY'])
                                    max_lat = float(rr['MAX_LATENCY'])
                                    results['jitter_ms'] = (
                                        max_lat - min_lat) / 2000.0
                                cp.log(f'Latency: {results.get("latency_ms", 0):.2f}ms '
                                       f'Jitter: {results.get("jitter_ms", 0):.2f}ms')
                        rr_terminal_seen = True
                        break

                time.sleep(1)

            if (
                not rr_terminal_seen
                and not rr_user_cancelled
            ):
                cp.log(
                    f'Netperf TCP_RR poll timed out after '
                    f'{rr_budget}s'
                )

                cleanup_ok = _netperf_cancel_and_verify(
                    'TCP_RR watchdog-timeout cleanup'
                )

                if not cleanup_ok:
                    cp.log(
                        'Netperf TCP_RR timeout cleanup could not '
                        'confirm the native service stopped'
                    )

        return results
    except Exception as e:
        cp.log(f'Netperf error: {e}')
        return None


# =============================================================================
# IPERF3 ENGINE
# =============================================================================

# Source routing table/policy name prefix for iPerf3 WAN steering.
_IPERF3_ROUTE_PREFIX = 'STWEB'


def _iperf3_setup_source_route(device_uid, source_ip):
    """Create a temporary source-routing policy so iPerf3 traffic from
    source_ip egresses through the specified WAN device.

    Uses config/routing API to create a routing table + source-IP policy.
    NCOS routing policies are indexed by numeric position, not _id_.

    Args:
        device_uid: WAN device UID (e.g. 'ethernet-lan', 'mdm-bfa1a8e').
        source_ip: Source IPv4 address on that WAN.

    Returns:
        Tuple of (table_id, policy_index) on success for later cleanup,
        or (None, None) on failure. table_id is the table's _id_ string;
        policy_index is the numeric list index returned by POST.
    """
    table_name = f'{_IPERF3_ROUTE_PREFIX}-{device_uid}'
    table_id = None
    policy_index = None
    try:
        # Define the route table: default route via device_uid
        route_table = {
            "name": table_name,
            "routes": [
                {
                    "netallow": False,
                    "ip_network": "0.0.0.0/0",
                    "dev": device_uid,
                    "auto_gateway": True
                }
            ]
        }

        # Check if the table already exists (from a previous interrupted run)
        existing_tables = _normalize_routing_list(
            cp.get('config/routing/tables'))
        for t in existing_tables:
            if isinstance(t, dict) and t.get('name') == table_name:
                table_id = t.get('_id_')
                break

        if not table_id:
            resp = cp.post('config/routing/tables/', route_table)
            if not resp:
                cp.log(f'iPerf3 source route: failed to create table '
                       f'{table_name}')
                return None, None
            table_index = resp.get('data')
            if table_index is None:
                cp.log(f'iPerf3 source route: no index returned for table')
                return None, None
            table_obj = cp.get(f'config/routing/tables/{table_index}')
            if not table_obj or not isinstance(table_obj, dict):
                cp.log(f'iPerf3 source route: cannot read created table')
                return None, None
            table_id = table_obj.get('_id_')
            if not table_id:
                cp.log(f'iPerf3 source route: created table has no _id_')
                return None, None
            cp.log(f'iPerf3 source route: table created '
                   f'index={table_index} id={table_id}')
            time.sleep(1)
        else:
            cp.log(f'iPerf3 source route: reusing existing table '
                   f'id={table_id}')

        # Create the policy: source IP → table
        route_policy = {
            "ip_version": "ip4",
            "priority": 1,
            "table": table_id,
            "src_ip_network": source_ip
        }

        resp = cp.post('config/routing/policies/', route_policy)
        if not resp:
            cp.log(f'iPerf3 source route: POST policy returned None')
            _iperf3_cleanup_table(table_id)
            return None, None

        policy_index = resp.get('data')
        if policy_index is None:
            cp.log(f'iPerf3 source route: no index in policy POST response')
            _iperf3_cleanup_table(table_id)
            return None, None

        cp.log(f'iPerf3 source route: policy created index={policy_index}')

        # Verify the policy was written correctly
        pol_obj = cp.get(f'config/routing/policies/{policy_index}')
        if not pol_obj or not isinstance(pol_obj, dict):
            cp.log(f'iPerf3 source route: cannot read policy at '
                   f'index={policy_index}')
            # Attempt cleanup of what we created
            try:
                cp.delete(f'config/routing/policies/{policy_index}')
            except Exception:
                pass
            _iperf3_cleanup_table(table_id)
            return None, None

        # Verify fields match
        verified = (
            pol_obj.get('table') == table_id
            and pol_obj.get('src_ip_network') == source_ip
            and pol_obj.get('ip_version') == 'ip4'
            and pol_obj.get('priority') == 1
        )
        if not verified:
            cp.log(f'iPerf3 source route: policy verification failed. '
                   f'Expected table={table_id} src={source_ip} '
                   f'Got: {json.dumps(pol_obj)}')
            try:
                cp.delete(f'config/routing/policies/{policy_index}')
            except Exception:
                pass
            _iperf3_cleanup_table(table_id)
            return None, None

        cp.log(f'iPerf3 source route: policy verified')
        time.sleep(1)
        return table_id, policy_index

    except Exception as e:
        cp.log(f'iPerf3 source route setup error: {e}')
        # Best-effort cleanup
        if policy_index is not None:
            try:
                cp.delete(f'config/routing/policies/{policy_index}')
            except Exception:
                pass
        if table_id:
            _iperf3_cleanup_table(table_id)
        return None, None


def _iperf3_cleanup_table(table_id):
    """Delete a routing table by its _id_. Helper for error paths."""
    if not table_id:
        return
    try:
        # Tables are accessed by _id_ — find numeric index
        tables = _normalize_routing_list(cp.get('config/routing/tables'))
        for idx, t in enumerate(tables):
            if isinstance(t, dict) and t.get('_id_') == table_id:
                cp.delete(f'config/routing/tables/{idx}')
                return
        # Fallback: try deleting by _id_ directly (some NCOS versions)
        cp.delete(f'config/routing/tables/{table_id}')
    except Exception as e:
        cp.log(f'iPerf3 source route: failed to delete table {table_id}: {e}')


def _iperf3_cleanup_source_route(table_id, policy_index):
    """Remove the temporary source-routing policy and table.

    Args:
        table_id: The table's _id_ string, or None.
        policy_index: The numeric policy list index, or None.
    """
    try:
        if policy_index is not None:
            cp.delete(f'config/routing/policies/{policy_index}')
            cp.log(f'iPerf3 source route cleanup: deleted policy '
                   f'index={policy_index}')
            time.sleep(0.3)
            # Verify it's gone
            pol = cp.get(f'config/routing/policies/{policy_index}')
            if pol and isinstance(pol, dict) and pol.get('table') == table_id:
                cp.log(f'iPerf3 source route cleanup: WARNING policy '
                       f'index={policy_index} may still exist')
        if table_id:
            _iperf3_cleanup_table(table_id)
            cp.log(f'iPerf3 source route cleanup: deleted table '
                   f'id={table_id}')
    except Exception as e:
        cp.log(f'iPerf3 source route cleanup error: {e}')


def _iperf3_cleanup_stale_routes():
    """Remove any leftover STWEB-* routing tables/policies from interrupted
    runs. Policies must be deleted before their referenced tables.

    Policies are identified by numeric list index (no _id_ field).
    Deleting by index shifts subsequent entries, so we delete from
    highest index to lowest.
    """
    try:
        tables = _normalize_routing_list(cp.get('config/routing/tables'))
        policies = _normalize_routing_list(cp.get('config/routing/policies'))

        # Find STWEB table _id_ values
        stale_table_ids = set()
        for t in tables:
            if isinstance(t, dict):
                name = t.get('name', '')
                if name.startswith(_IPERF3_ROUTE_PREFIX):
                    tid = t.get('_id_')
                    if tid:
                        stale_table_ids.add(tid)

        if not stale_table_ids:
            return

        # Find policy indexes referencing stale tables (highest first)
        stale_policy_indexes = []
        for idx, p in enumerate(policies):
            if isinstance(p, dict) and p.get('table') in stale_table_ids:
                stale_policy_indexes.append(idx)

        # Delete policies highest-index-first to avoid index shifting
        stale_policy_indexes.sort(reverse=True)
        policies_deleted = 0
        for idx in stale_policy_indexes:
            try:
                cp.delete(f'config/routing/policies/{idx}')
                policies_deleted += 1
                time.sleep(0.1)
            except Exception:
                pass

        # Now delete the tables (by numeric index, highest first)
        table_indexes = []
        for idx, t in enumerate(tables):
            if isinstance(t, dict) and t.get('_id_') in stale_table_ids:
                table_indexes.append(idx)
        table_indexes.sort(reverse=True)

        tables_deleted = 0
        for idx in table_indexes:
            try:
                cp.delete(f'config/routing/tables/{idx}')
                tables_deleted += 1
                time.sleep(0.1)
            except Exception:
                pass

        cp.log(f'iPerf3: cleaned {tables_deleted} stale STWEB table(s), '
               f'{policies_deleted} stale policy/policies')
    except Exception as e:
        cp.log(f'iPerf3 stale route cleanup error: {e}')


def _normalize_routing_list(obj):
    """Normalize config/routing API response to a list for iteration."""
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        return list(obj.values()) if obj else []
    return []


def _iperf3_retryable_endpoint_reason(error):
    """Return a retry reason only for listener-specific failures."""
    message = str(
        error or ''
    ).strip().lower()

    if not message:
        return ''

    if (
        'server is busy' in message
        or 'busy running a test' in message
    ):
        return 'busy'

    if 'connection refused' in message:
        return 'connection refused'

    if (
        'server is not running' in message
        or 'listener unavailable' in message
    ):
        return 'listener unavailable'

    return ''


def _iperf3_timeout_error(error):
    """Return True only for an iPerf3 timeout-style error."""
    message = str(error or '').strip().lower()

    return (
        'timed out' in message
        or 'timeout' in message
    )


def _iperf3_validate_active_wan_path():
    """Verify the selected WAN still owns the path after an iPerf3 timeout.

    Returns:
        Tuple of (healthy, detail).
    """
    guard = _active_iperf3_wan_guard

    if not isinstance(guard, dict):
        return False, 'WAN validation context unavailable'

    device_uid = str(
        guard.get('device_uid') or ''
    ).strip()

    source_ip = str(
        guard.get('source_ip') or ''
    ).strip()

    expected_gateway = str(
        guard.get('gateway') or ''
    ).strip()

    is_primary_wan = bool(
        guard.get('is_primary_wan')
    )

    table_id = guard.get(
        'source_route_table_id'
    )

    policy_index = guard.get(
        'source_route_policy_index'
    )

    if not device_uid:
        return False, 'selected WAN identity unavailable'

    if not source_ip:
        return False, 'selected WAN source IP unavailable'

    # Gateway is supplemental validation data. Some NCOS WAN status
    # responses may omit it even while the selected IPv4 WAN is healthy.
    # When a baseline gateway is available, verify that it remains stable.
    try:
        devices = cp.get(
            'status/wan/devices'
        ) or {}

        if not isinstance(devices, dict):
            return False, 'WAN device state unavailable'

        device = devices.get(
            device_uid
        )

        if not isinstance(device, dict):
            return False, 'selected WAN device disappeared'

        status = device.get(
            'status',
            {}
        )

        if not isinstance(status, dict):
            return False, 'selected WAN status unavailable'

        connection_state = str(
            status.get(
                'connection_state',
                ''
            ) or ''
        ).strip().lower()

        if connection_state != 'connected':
            return (
                False,
                'selected WAN is {}'.format(
                    connection_state or 'not connected'
                )
            )

        ipinfo = status.get(
            'ipinfo',
            {}
        )

        if not isinstance(ipinfo, dict):
            return False, 'selected WAN IP state unavailable'

        current_ip = str(
            ipinfo.get(
                'ip_address',
                ''
            ) or ''
        ).strip()

        if current_ip != source_ip:
            return (
                False,
                'selected WAN source IP changed from {} to {}'.format(
                    source_ip,
                    current_ip or 'none'
                )
            )

        current_gateway = str(
            ipinfo.get(
                'gateway',
                ''
            ) or ''
        ).strip()

        if (
            expected_gateway
            and current_gateway
            and current_gateway != expected_gateway
        ):
            return (
                False,
                'selected WAN gateway changed from {} to {}'.format(
                    expected_gateway,
                    current_gateway or 'none'
                )
            )

        if is_primary_wan:
            current_primary = str(
                cp.get_wan_primary_device() or ''
            ).strip()

            if current_primary != device_uid:
                return (
                    False,
                    'primary WAN changed from {} to {}'.format(
                        device_uid,
                        current_primary or 'none'
                    )
                )

            return True, 'selected primary WAN path healthy'

        if not table_id or policy_index is None:
            return (
                False,
                'non-primary source-routing context unavailable'
            )

        tables = _normalize_routing_list(
            cp.get('config/routing/tables')
        )

        route_table = None

        for table in tables:
            if (
                isinstance(table, dict)
                and table.get('_id_') == table_id
            ):
                route_table = table
                break

        if route_table is None:
            return (
                False,
                'temporary source-routing table disappeared'
            )

        routes = route_table.get(
            'routes',
            []
        )

        if not isinstance(routes, list):
            return (
                False,
                'temporary source-routing table invalid'
            )

        route_valid = any(
            isinstance(route, dict)
            and route.get('ip_network') == '0.0.0.0/0'
            and route.get('dev') == device_uid
            and bool(route.get('auto_gateway'))
            for route in routes
        )

        if not route_valid:
            return (
                False,
                'temporary source route no longer targets selected WAN'
            )

        policy = cp.get(
            'config/routing/policies/{}'.format(
                policy_index
            )
        )

        if not isinstance(policy, dict):
            return (
                False,
                'temporary source-routing policy disappeared'
            )

        policy_valid = (
            policy.get('table') == table_id
            and policy.get('src_ip_network') == source_ip
            and policy.get('ip_version') == 'ip4'
            and policy.get('priority') == 1
        )

        if not policy_valid:
            return (
                False,
                'temporary source-routing policy changed'
            )

        return True, 'selected non-primary WAN path healthy'

    except Exception as exc:
        return (
            False,
            'WAN path validation failed: {}'.format(
                exc
            )
        )


def _iperf3_runtime_retry_reason(error):
    """Classify runtime retry eligibility without changing Reliability meaning.

    Returns:
        Tuple of (reason, listener_failure).

        reason:
            Non-empty when another listener port may be attempted.

        listener_failure:
            True only for the existing listener-specific failure classes
            that are eligible for Reliability Endpoint Failure accounting.
    """
    listener_reason = (
        _iperf3_retryable_endpoint_reason(
            error
        )
    )

    if listener_reason:
        return (
            listener_reason,
            True
        )

    if not _iperf3_timeout_error(
        error
    ):
        return (
            '',
            False
        )

    healthy, detail = (
        _iperf3_validate_active_wan_path()
    )

    if healthy:
        cp.log(
            'iPerf3 timeout classified as retryable endpoint/path condition; '
            '{}'.format(
                detail
            )
        )

        return (
            'timed out',
            False
        )

    cp.log(
        'iPerf3 timeout classified as hard WAN/routing failure; '
        '{}'.format(
            detail
        )
    )

    return (
        '',
        False
    )


def _choose_iperf3_unused_port(
    port_start,
    port_end,
    attempted
):
    """Choose a random unused port without allocating the full range."""
    import random

    port_start = int(
        port_start
    )
    port_end = int(
        port_end
    )

    span = (
        port_end
        - port_start
        + 1
    )

    if span <= 0:
        return None

    if len(
        attempted
    ) >= span:
        return None

    # With a maximum attempted set of three ports, random collision
    # probability is tiny for normal public-server ranges.
    for _ in range(
        16
    ):
        candidate = random.randint(
            port_start,
            port_end
        )

        if candidate not in attempted:
            return candidate

    # Deterministic fallback uses a range iterator and does not
    # allocate the port range in RAM.
    for candidate in range(
        port_start,
        port_end + 1
    ):
        if candidate not in attempted:
            return candidate

    return None


def _get_public_iperf3_backup_server(
    server_ref,
    region
):
    """Return the next Public server in configured Region order."""
    cache = (
        _load_active_iperf3_server_cache()
    )

    if (
        not cache
        or cache.get('mode') != 'public'
        or not cache.get('available')
    ):
        return None

    server_ref = str(
        server_ref or ''
    ).strip()

    region = str(
        region or ''
    ).strip()

    if (
        not server_ref
        or not region
    ):
        return None

    first = None
    found_current = False
    region_count = 0

    for server in cache.get(
        'servers',
        []
    ):
        if (
            not isinstance(
                server,
                dict
            )
            or server.get(
                'region'
            ) != region
        ):
            continue

        region_count += 1

        if first is None:
            first = server

        if found_current:
            return server

        if server.get(
            'server_ref'
        ) == server_ref:
            found_current = True

    if (
        found_current
        and region_count > 1
        and first is not None
        and first.get(
            'server_ref'
        ) != server_ref
    ):
        return first

    return None


def _run_iperf3_phase(
    iperf3_bin,
    server,
    port,
    duration,
    bind_ip,
    bind_dev='',
    is_primary_wan=False,
    direction='download'
):
    """Run one iPerf3 direction against one server listener."""
    global current_test

    is_download = (
        direction == 'download'
    )

    stage = (
        'download'
        if is_download
        else 'upload'
    )

    with test_lock:
        current_test['progress'] = {
            'stage':
                stage,
            'percent':
                0,
            'message':
                (
                    'Trying port {} for download...'.format(
                        port
                    )
                    if is_download
                    else 'Uploading on port {}...'.format(
                        port
                    )
                )
        }

    if not current_test.get(
        'running'
    ):
        return {
            'bps': 0,
            'bytes': None,
            'port': port,
            'error': 'Test cancelled'
        }

    cmd = [
        iperf3_bin,
        '-c',
        server,
        '-p',
        str(port),
        '-t',
        str(duration),
    ]

    if is_download:
        cmd.append(
            '-R'
        )

    cmd.extend([
        '-J',
        '-4',
    ])

    if bind_ip:
        cmd.extend([
            '-B',
            bind_ip,
        ])

    if bind_dev:
        cmd.extend([
            '--bind-dev',
            bind_dev,
        ])

    def execute(command):
        started_at = (
            time.monotonic()
        )

        cp.log(
            'iPerf3 {} cmd: {}'.format(
                stage,
                ' '.join(
                    command
                )
            )
        )

        global _active_iperf3_process

        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        with _iperf3_process_lock:
            _active_iperf3_process = proc

        # Close the race where Stop was requested immediately before
        # this subprocess became the registered active iPerf3 process.
        with test_lock:
            cancel_requested = not current_test.get(
                'running'
            )

        if cancel_requested:
            try:
                proc.terminate()
            except Exception:
                pass

        try:
            stdout, stderr = (
                proc.communicate(
                    timeout=duration + 30
                )
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.communicate()
            except Exception:
                pass
            return {
                'returncode': None,
                'stdout': b'',
                'stderr': b'',
                'started_at':
                    started_at,
                'error':
                    '{} timed out'.format(
                        stage.capitalize()
                    )
            }
        finally:
            with _iperf3_process_lock:
                if _active_iperf3_process is proc:
                    _active_iperf3_process = None

        with test_lock:
            cancel_requested = not current_test.get(
                'running'
            )

        if cancel_requested:
            return {
                'returncode':
                    proc.returncode,
                'stdout':
                    stdout,
                'stderr':
                    stderr,
                'started_at':
                    started_at,
                'error':
                    'Test cancelled'
            }

        return {
            'returncode':
                proc.returncode,
            'stdout':
                stdout,
            'stderr':
                stderr,
            'started_at':
                started_at,
            'error':
                ''
        }

    execution = execute(
        cmd
    )

    cp.log(
        'iPerf3 {} returncode: {}'.format(
            stage,
            execution.get(
                'returncode'
            )
        )
    )

    if execution.get(
        'error'
    ) == 'Test cancelled':
        return {
            'bps':
                0,
            'bytes':
                None,
            'port':
                port,
            'started_at':
                execution.get(
                    'started_at'
                ),
            'error':
                'Test cancelled'
        }

    # Preserve the validated primary-WAN SO_BINDTODEVICE fallback.
    if (
        execution.get(
            'returncode'
        )
        not in (
            0,
            None
        )
    ):
        error = _parse_iperf3_error(
            execution.get(
                'stdout'
            ),
            execution.get(
                'stderr'
            )
        )

        if (
            bind_dev
            and 'Operation not permitted'
            in str(
                error or ''
            )
        ):
            if not is_primary_wan:
                message = (
                    'iPerf3 can only test the primary active WAN '
                    'connection on this device. Use Netperf to '
                    'test additional links, or set the interface '
                    'you need to test as the primary WAN '
                    'connection.'
                )

                cp.log(
                    'iPerf3 {} failed on port {}: {}'.format(
                        stage,
                        port,
                        message
                    )
                )

                return {
                    'bps': 0,
                    'bytes': None,
                    'port': port,
                    'error':
                        message
                }

            cp.log(
                '--bind-dev unsupported on this platform; '
                'retrying {} on the same port without it '
                '(primary WAN)'.format(
                    stage
                )
            )

            retry_cmd = list(
                cmd
            )

            try:
                bind_index = retry_cmd.index(
                    '--bind-dev'
                )

                del retry_cmd[
                    bind_index:
                    bind_index + 2
                ]

            except ValueError:
                pass

            execution = execute(
                retry_cmd
            )

            cp.log(
                'iPerf3 {} retry returncode: {}'.format(
                    stage,
                    execution.get(
                        'returncode'
                    )
                )
            )

    if execution.get(
        'returncode'
    ) is None:
        error = (
            execution.get(
                'error'
            )
            or '{} timed out'.format(
                stage.capitalize()
            )
        )

        cp.log(
            'iPerf3 {} timed out on port {}'.format(
                stage,
                port
            )
        )

        return {
            'bps': 0,
            'bytes': None,
            'port': port,
            'error':
                error
        }

    if execution.get(
        'returncode'
    ) != 0:
        error = _parse_iperf3_error(
            execution.get(
                'stdout'
            ),
            execution.get(
                'stderr'
            )
        )

        cp.log(
            'iPerf3 {} failed on port {}: {}'.format(
                stage,
                port,
                error
            )
        )

        return {
            'bps': 0,
            'bytes': None,
            'port': port,
            'error':
                error
        }

    try:
        data = json.loads(
            execution.get(
                'stdout',
                b''
            ).decode(
                'utf-8'
            )
        )

    except Exception as exc:
        cp.log(
            'iPerf3 {} JSON error on port {}: {}'.format(
                stage,
                port,
                exc
            )
        )

        return {
            'bps': 0,
            'bytes': None,
            'port': port,
            'error':
                'Invalid iPerf3 JSON result: {}'.format(
                    exc
                )
        }

    summary_key = (
        'sum_received'
        if is_download
        else 'sum_sent'
    )

    summary = data.get(
        'end',
        {}
    ).get(
        summary_key,
        {}
    )

    bps = (
        summary.get(
            'bits_per_second',
            0
        )
        or 0
    )

    byte_count = None

    if bps > 0:
        byte_count = (
            _safe_test_bytes(
                summary.get(
                    'bytes'
                )
            )
        )

        _record_carrier_phase_window(
            stage,
            execution[
                'started_at'
            ],
            time.monotonic()
        )

    cp.log(
        'iPerf3 {} engine data: {} bytes'.format(
            stage,
            byte_count
        )
    )

    cp.log(
        'iPerf3 {}: {:.2f} Mbps (port {})'.format(
            stage,
            bps / 1e6,
            port
        )
    )

    if bps <= 0:
        return {
            'bps': 0,
            'bytes':
                byte_count,
            'port':
                port,
            'error':
                'No data transferred'
        }

    return {
        'bps':
            bps,
        'bytes':
            byte_count,
        'port':
            port,
        'error':
            ''
    }


def _iperf3_search_download_ports(
    iperf3_bin,
    server,
    server_name,
    port_start,
    port_end,
    duration,
    bind_ip,
    bind_dev,
    is_primary_wan
):
    """Search at most three unique listener ports for Downlink."""
    attempted = set()
    listener_failures = set()

    budget = min(
        3,
        (
            int(
                port_end
            )
            - int(
                port_start
            )
            + 1
        )
    )

    last_phase = None

    for attempt_number in range(
        budget
    ):
        if not current_test.get(
            'running'
        ):
            return {
                'success': False,
                'hard_failure': True,
                'attempted':
                    attempted,
                'listener_failure_ports':
                    listener_failures,
                'port':
                    None,
                'error':
                    'Test cancelled'
            }

        attempt_port = (
            _choose_iperf3_unused_port(
                port_start,
                port_end,
                attempted
            )
        )

        if attempt_port is None:
            break

        attempted.add(
            attempt_port
        )

        phase = _run_iperf3_phase(
            iperf3_bin,
            server,
            attempt_port,
            duration,
            bind_ip,
            bind_dev,
            is_primary_wan,
            'download'
        )

        last_phase = phase

        if phase.get(
            'bps',
            0
        ) > 0:
            return {
                'success': True,
                'hard_failure': False,
                'attempted':
                    attempted,
                'listener_failure_ports':
                    listener_failures,
                'port':
                    attempt_port,
                'bps':
                    phase.get(
                        'bps',
                        0
                    ),
                'bytes':
                    phase.get(
                        'bytes'
                    ),
                'error':
                    ''
            }

        (
            reason,
            listener_failure
        ) = _iperf3_runtime_retry_reason(
            phase.get(
                'error'
            )
        )

        if listener_failure:
            listener_failures.add(
                attempt_port
            )

        if not reason:
            return {
                'success': False,
                'hard_failure': True,
                'attempted':
                    attempted,
                'listener_failure_ports':
                    listener_failures,
                'port':
                    attempt_port,
                'error':
                    phase.get(
                        'error',
                        'iPerf3 download failed'
                    )
            }

        cp.log(
            'iPerf3 {} port {} {} ({}/{})'.format(
                server_name,
                attempt_port,
                reason,
                attempt_number + 1,
                budget
            )
        )

        if (
            attempt_number + 1
            < budget
        ):
            with test_lock:
                current_test[
                    'progress'
                ] = {
                    'stage':
                        'download',
                    'percent':
                        0,
                    'message':
                        (
                            'Port {} {} - trying another '
                            'available port...'
                        ).format(
                            attempt_port,
                            reason
                        )
                }

            time.sleep(
                1
            )

    return {
        'success':
            False,
        'hard_failure':
            False,
        'attempted':
            attempted,
        'listener_failure_ports':
            listener_failures,
        'port':
            (
                last_phase.get(
                    'port'
                )
                if last_phase
                else None
            ),
        'error':
            (
                last_phase.get(
                    'error'
                )
                if last_phase
                else (
                    'No available '
                    'iPerf3 listener ports'
                )
            )
    }


def _iperf3_run_upload_with_retries(
    iperf3_bin,
    server,
    port_start,
    port_end,
    successful_download_port,
    attempted,
    duration,
    bind_ip,
    bind_dev,
    is_primary_wan
):
    """Run Uplink on the locked server with the shared port budget."""
    listener_failures = set()

    phase = _run_iperf3_phase(
        iperf3_bin,
        server,
        successful_download_port,
        duration,
        bind_ip,
        bind_dev,
        is_primary_wan,
        'upload'
    )

    if phase.get(
        'bps',
        0
    ) > 0:
        return {
            'success':
                True,
            'listener_failure_ports':
                listener_failures,
            'port':
                successful_download_port,
            'bps':
                phase.get(
                    'bps',
                    0
                ),
            'bytes':
                phase.get(
                    'bytes'
                ),
            'error':
                ''
        }

    (
        reason,
        listener_failure
    ) = _iperf3_runtime_retry_reason(
        phase.get(
            'error'
        )
    )

    if listener_failure:
        listener_failures.add(
            successful_download_port
        )

    if not reason:
        return {
            'success':
                False,
            'listener_failure_ports':
                listener_failures,
            'port':
                successful_download_port,
            'bps':
                0,
            'bytes':
                None,
            'error':
                phase.get(
                    'error',
                    'iPerf3 upload failed'
                )
        }

    budget = min(
        3,
        (
            int(
                port_end
            )
            - int(
                port_start
            )
            + 1
        )
    )

    last_phase = phase

    while len(
        attempted
    ) < budget:
        if not current_test.get(
            'running'
        ):
            return {
                'success':
                    False,
                'listener_failure_ports':
                    listener_failures,
                'port':
                    last_phase.get(
                        'port'
                    ),
                'bps':
                    0,
                'bytes':
                    None,
                'error':
                    'Test cancelled'
            }

        attempt_port = (
            _choose_iperf3_unused_port(
                port_start,
                port_end,
                attempted
            )
        )

        if attempt_port is None:
            break

        attempted.add(
            attempt_port
        )

        with test_lock:
            current_test[
                'progress'
            ] = {
                'stage':
                    'upload',
                'percent':
                    0,
                'message':
                    (
                        'Upload port {} {} - '
                        'trying port {}...'
                    ).format(
                        last_phase.get(
                            'port'
                        ),
                        reason,
                        attempt_port
                    )
            }

        cp.log(
            'iPerf3 upload port {} {}; '
            'retrying same server on port {}'.format(
                last_phase.get(
                    'port'
                ),
                reason,
                attempt_port
            )
        )

        time.sleep(
            1
        )

        phase = _run_iperf3_phase(
            iperf3_bin,
            server,
            attempt_port,
            duration,
            bind_ip,
            bind_dev,
            is_primary_wan,
            'upload'
        )

        last_phase = phase

        if phase.get(
            'bps',
            0
        ) > 0:
            return {
                'success':
                    True,
                'listener_failure_ports':
                    listener_failures,
                'port':
                    attempt_port,
                'bps':
                    phase.get(
                        'bps',
                        0
                    ),
                'bytes':
                    phase.get(
                        'bytes'
                    ),
                'error':
                    ''
            }

        (
            reason,
            listener_failure
        ) = _iperf3_runtime_retry_reason(
            phase.get(
                'error'
            )
        )

        if listener_failure:
            listener_failures.add(
                attempt_port
            )

        if not reason:
            break

    return {
        'success':
            False,
        'listener_failure_ports':
            listener_failures,
        'port':
            last_phase.get(
                'port'
            ),
        'bps':
            0,
        'bytes':
            None,
        'error':
            last_phase.get(
                'error',
                'iPerf3 upload failed'
            )
    }


def run_iperf3(
    server,
    duration=10,
    interface='',
    port=5201,
    context=None
):
    """Run bounded iPerf3 retries with optional Public backup."""
    global current_test, _active_iperf3_wan_guard

    _active_iperf3_wan_guard = None

    context = (
        context
        if isinstance(
            context,
            dict
        )
        else {}
    )

    try:
        (
            primary_port_start,
            primary_port_end
        ) = _parse_iperf3_port_range(
            port
        )

    except Exception as exc:
        return {
            'download_bps':
                0,
            'upload_bps':
                0,
            'download_bytes':
                None,
            'upload_bytes':
                None,
            'test_duration':
                duration,
            'server':
                server,
            'server_name':
                (
                    context.get(
                        'server_name'
                    )
                    or server
                ),
            'download_port':
                None,
            'upload_port':
                None,
            'error':
                (
                    'Invalid iPerf3 port '
                    'configuration: {}'
                ).format(
                    exc
                )
        }

    if not has_iperf3():
        try:
            cp.log(
                'Downloading iperf3 binary...'
            )

            import requests

            url = (
                'https://github.com/userdocs/iperf3-static/'
                'releases/download/3.17.1%2B/'
                'iperf3-arm64v8'
            )

            response = requests.get(
                url
            )

            if (
                response.status_code
                == 200
            ):
                with open(
                    'iperf3-arm64v8',
                    'wb'
                ) as handle:
                    handle.write(
                        response.content
                    )

                os.chmod(
                    'iperf3-arm64v8',
                    0o755
                )

                cp.log(
                    'iperf3 downloaded successfully'
                )

            else:
                cp.log(
                    'Failed to download iperf3: {}'.format(
                        response.status_code
                    )
                )

                return None

        except Exception as exc:
            cp.log(
                'Error downloading iperf3: {}'.format(
                    exc
                )
            )

            return None

    bind_ip = ''
    bind_dev = ''
    selected_gateway = ''
    is_primary_wan = False
    matched_uid = ''

    primary_uid = (
        cp.get_wan_primary_device()
        or ''
    )

    if interface:
        try:
            devices = cp.get(
                'status/wan/devices'
            )

            if devices:
                for uid, dev in devices.items():
                    if not isinstance(
                        dev,
                        dict
                    ):
                        continue

                    iface = dev.get(
                        'info',
                        {}
                    ).get(
                        'iface',
                        ''
                    )

                    if (
                        uid == interface
                        or iface == interface
                    ):
                        bind_ip = dev.get(
                            'status',
                            {}
                        ).get(
                            'ipinfo',
                            {}
                        ).get(
                            'ip_address',
                            ''
                        )

                        selected_gateway = dev.get(
                            'status',
                            {}
                        ).get(
                            'ipinfo',
                            {}
                        ).get(
                            'gateway',
                            ''
                        )

                        bind_dev = (
                            iface
                            or uid
                        )

                        matched_uid = uid
                        break

            if not bind_ip:
                cp.log(
                    (
                        'Could not resolve IP for interface {}, '
                        'running without bind'
                    ).format(
                        interface
                    )
                )

            else:
                cp.log(
                    'Binding to {} on device {}'.format(
                        bind_ip,
                        bind_dev
                    )
                )

            if matched_uid:
                is_primary_wan = (
                    matched_uid
                    == primary_uid
                )

        except Exception as exc:
            cp.log(
                'Error resolving interface IP: {}'.format(
                    exc
                )
            )

    cp.log(
        (
            'iPerf3 WAN selection: requested={} '
            'device_uid={} source_ip={} '
            'primary_uid={} is_primary={}'
        ).format(
            interface or 'auto',
            matched_uid or 'n/a',
            bind_ip or 'n/a',
            primary_uid or 'n/a',
            is_primary_wan
        )
    )

    source_route_table_id = None
    source_route_policy_index = None
    use_source_routing = False

    if (
        bind_ip
        and matched_uid
        and not is_primary_wan
    ):
        _iperf3_cleanup_stale_routes()

        (
            source_route_table_id,
            source_route_policy_index
        ) = _iperf3_setup_source_route(
            matched_uid,
            bind_ip
        )

        if (
            source_route_table_id
            and source_route_policy_index
            is not None
        ):
            use_source_routing = True

            cp.log(
                (
                    'iPerf3 WAN steering: active for '
                    'non-primary WAN ({}), '
                    '--bind-dev suppressed'
                ).format(
                    matched_uid
                )
            )

        else:
            message = (
                'iPerf3 WAN steering unavailable for selected '
                'non-primary WAN; test not started. Source '
                'routing policy could not be established.'
            )

            cp.log(
                message
            )

            return {
                'download_bps':
                    0,
                'upload_bps':
                    0,
                'download_bytes':
                    None,
                'upload_bytes':
                    None,
                'test_duration':
                    duration,
                'server':
                    server,
                'server_name':
                    (
                        context.get(
                            'server_name'
                        )
                        or server
                    ),
                'download_port':
                    None,
                'upload_port':
                    None,
                'error':
                    message
            }

    iperf3_bin = (
        get_iperf3_binary()
    )

    effective_bind_dev = (
        ''
        if use_source_routing
        else bind_dev
    )

    guard_uid = matched_uid

    # Auto mode follows the current primary WAN. Do not change the
    # existing bind behavior; this lookup is validation-only.
    if not interface:
        guard_uid = primary_uid

    guard_source_ip = bind_ip
    guard_gateway = selected_gateway

    if guard_uid and (
        not guard_source_ip
        or not guard_gateway
    ):
        try:
            guard_devices = cp.get(
                'status/wan/devices'
            ) or {}

            if isinstance(
                guard_devices,
                dict
            ):
                guard_device = guard_devices.get(
                    guard_uid,
                    {}
                )

                if isinstance(
                    guard_device,
                    dict
                ):
                    guard_ipinfo = guard_device.get(
                        'status',
                        {}
                    ).get(
                        'ipinfo',
                        {}
                    )

                    if not guard_source_ip:
                        guard_source_ip = guard_ipinfo.get(
                            'ip_address',
                            ''
                        )

                    if not guard_gateway:
                        guard_gateway = guard_ipinfo.get(
                            'gateway',
                            ''
                        )

        except Exception as exc:
            cp.log(
                'iPerf3 WAN validation snapshot warning: {}'.format(
                    exc
                )
            )

    _active_iperf3_wan_guard = {
        'device_uid':
            guard_uid,
        'source_ip':
            guard_source_ip,
        'gateway':
            guard_gateway,
        'is_primary_wan':
            bool(
                guard_uid
                and guard_uid == primary_uid
            ),
        'source_route_table_id':
            source_route_table_id,
        'source_route_policy_index':
            source_route_policy_index,
    }

    try:
        locked_server = server

        locked_server_name = (
            context.get(
                'server_name'
            )
            or server
        )

        locked_server_ref = str(
            context.get(
                'server_ref'
            )
            or ''
        )

        locked_port_start = (
            primary_port_start
        )

        locked_port_end = (
            primary_port_end
        )

        download = (
            _iperf3_search_download_ports(
                iperf3_bin,
                locked_server,
                locked_server_name,
                locked_port_start,
                locked_port_end,
                duration,
                bind_ip,
                effective_bind_dev,
                is_primary_wan
            )
        )

        _record_iperf3_endpoint_failures(
            locked_server_ref,
            _download_listener_failure_ports(
                download
            )
        )

        # Hard WAN/routing/system failures never trigger another
        # listener port or backup server.
        if (
            not download.get(
                'success'
            )
            and download.get(
                'hard_failure'
            )
        ):
            return {
                'download_bps':
                    0,
                'upload_bps':
                    0,
                'download_bytes':
                    None,
                'upload_bytes':
                    None,
                'test_duration':
                    duration,
                'server':
                    locked_server,
                'server_name':
                    locked_server_name,
                'download_port':
                    download.get(
                        'port'
                    ),
                'upload_port':
                    None,
                'error':
                    download.get(
                        'error',
                        'iPerf3 download failed'
                    )
            }

        # Only Public mode can use the next configured server in
        # the same Region, and only after retryable listener
        # failures exhaust the primary server's port budget.
        if not download.get(
            'success'
        ):
            backup = None

            if (
                context.get(
                    'server_source'
                )
                == 'public'
            ):
                backup = (
                    _get_public_iperf3_backup_server(
                        context.get(
                            'server_ref'
                        ),
                        context.get(
                            'region'
                        )
                    )
                )

            if backup is None:
                return {
                    'download_bps':
                        0,
                    'upload_bps':
                        0,
                    'download_bytes':
                        None,
                    'upload_bytes':
                        None,
                    'test_duration':
                        duration,
                    'server':
                        locked_server,
                    'server_name':
                        locked_server_name,
                    'download_port':
                        download.get(
                            'port'
                        ),
                    'upload_port':
                        None,
                    'error':
                        download.get(
                            'error',
                            (
                                'No available '
                                'iPerf3 listener ports'
                            )
                        )
                }

            locked_server = str(
                backup.get(
                    'host',
                    ''
                )
            )

            locked_server_name = (
                backup.get(
                    'server_name'
                )
                or locked_server
            )

            locked_server_ref = str(
                backup.get(
                    'server_ref'
                )
                or ''
            )

            locked_port_start = int(
                backup.get(
                    'port_start'
                )
            )

            locked_port_end = int(
                backup.get(
                    'port_end'
                )
            )

            cp.log(
                (
                    'iPerf3 Public primary listener ports '
                    'exhausted; trying next server in {}: {}'
                ).format(
                    context.get(
                        'region'
                    )
                    or 'Region',
                    locked_server_name
                )
            )

            with test_lock:
                current_test[
                    'progress'
                ] = {
                    'stage':
                        'download',
                    'percent':
                        0,
                    'message':
                        (
                            'Primary server listener ports '
                            'unavailable - trying {}...'
                        ).format(
                            locked_server_name
                        )
                }

            download = (
                _iperf3_search_download_ports(
                    iperf3_bin,
                    locked_server,
                    locked_server_name,
                    locked_port_start,
                    locked_port_end,
                    duration,
                    bind_ip,
                    effective_bind_dev,
                    is_primary_wan
                )
            )

            _record_iperf3_endpoint_failures(
                locked_server_ref,
                _download_listener_failure_ports(
                    download
                )
            )

            if not download.get(
                'success'
            ):
                return {
                    'download_bps':
                        0,
                    'upload_bps':
                        0,
                    'download_bytes':
                        None,
                    'upload_bytes':
                        None,
                    'test_duration':
                        duration,
                    'server':
                        locked_server,
                    'server_name':
                        locked_server_name,
                    'download_port':
                        download.get(
                            'port'
                        ),
                    'upload_port':
                        None,
                    'error':
                        download.get(
                            'error',
                            'Backup iPerf3 server failed'
                        )
                }

        if not current_test.get(
            'running'
        ):
            return {
                'download_bps':
                    download.get(
                        'bps',
                        0
                    ),
                'upload_bps':
                    0,
                'download_bytes':
                    download.get(
                        'bytes'
                    ),
                'upload_bytes':
                    None,
                'test_duration':
                    duration,
                'server':
                    locked_server,
                'server_name':
                    locked_server_name,
                'download_port':
                    download.get(
                        'port'
                    ),
                'upload_port':
                    None,
                'error':
                    'Test cancelled'
            }

        # Preserve the existing directional pause.
        time.sleep(
            2
        )

        upload_attempted_before = set(
            download.get(
                'attempted',
                set()
            )
        )

        upload = (
            _iperf3_run_upload_with_retries(
                iperf3_bin,
                locked_server,
                locked_port_start,
                locked_port_end,
                download.get(
                    'port'
                ),
                download.get(
                    'attempted',
                    set()
                ),
                duration,
                bind_ip,
                effective_bind_dev,
                is_primary_wan
            )
        )

        upload_attempted_after = set(
            download.get(
                'attempted',
                set()
            )
        )

        _record_iperf3_endpoint_failures(
            locked_server_ref,
            _upload_listener_failure_ports(
                download.get(
                    'port'
                ),
                upload_attempted_before,
                upload_attempted_after,
                upload
            )
        )

        if upload.get(
            'success'
        ):
            _record_iperf3_success(
                locked_server_ref
            )

        result = {
            'download_bps':
                download.get(
                    'bps',
                    0
                ),
            'upload_bps':
                upload.get(
                    'bps',
                    0
                ),
            'download_bytes':
                download.get(
                    'bytes'
                ),
            'upload_bytes':
                upload.get(
                    'bytes'
                ),
            'test_duration':
                duration,
            'server':
                locked_server,
            'server_name':
                locked_server_name,
            'download_port':
                download.get(
                    'port'
                ),
            'upload_port':
                upload.get(
                    'port'
                )
        }

        if not upload.get(
            'success'
        ):
            result['error'] = (
                'Upload failed: '
                + str(
                    upload.get(
                        'error',
                        'iPerf3 upload failed'
                    )
                )
            )

        cp.log(
            (
                'iPerf3 complete: server={} '
                'DL={:.2f}Mbps port={} '
                'UL={:.2f}Mbps port={}'
            ).format(
                locked_server,
                (
                    result[
                        'download_bps'
                    ]
                    / 1e6
                ),
                result[
                    'download_port'
                ],
                (
                    result[
                        'upload_bps'
                    ]
                    / 1e6
                ),
                result[
                    'upload_port'
                ]
            )
        )

        return result

    finally:
        if (
            source_route_table_id
            or source_route_policy_index
            is not None
        ):
            _iperf3_cleanup_source_route(
                source_route_table_id,
                source_route_policy_index
            )

        _active_iperf3_wan_guard = None



def _parse_iperf3_error(stdout, stderr):
    """Extract error message from iperf3 output."""
    err = stderr.decode('utf-8').strip() if stderr else ''
    out = stdout.decode('utf-8').strip() if stdout else ''
    if out:
        try:
            err_data = json.loads(out)
            if err_data.get('error'):
                return err_data['error']
        except Exception:
            pass
    return err or 'Unknown error'


# =============================================================================
# OOKLA ENGINE (streaming)
# =============================================================================

def run_ookla(interface=''):
    """Run a speed test using the Ookla binary with streaming progress."""
    global current_test
    if not has_ookla():
        return None

    try:
        ookla_bin = get_ookla_binary()
        cmd = [ookla_bin, '-f', 'jsonl',
               '-c', 'https://www.speedtest.net/api/embed/trial/config']
        if interface:
            cmd.extend(['-I', interface])

        cp.log(f'Ookla command: {" ".join(cmd)}')
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, bufsize=1)

        result_data = None

        # Ookla emits streaming Download/Upload messages while real traffic
        # is active. Use the first message for each direction as that phase's
        # independent 0s boundary rather than the earlier process launch.
        ookla_download_started_at = None
        ookla_download_ended_at = None
        ookla_upload_started_at = None
        ookla_upload_ended_at = None
        ookla_result_received_at = None

        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get('type')
            if msg_type == 'download':
                dl = msg.get('download', {})

                if ookla_download_started_at is None:
                    ookla_download_started_at = time.monotonic()
                    cp.log(
                        'Carrier telemetry: Ookla download traffic '
                        'start detected'
                    )

                with test_lock:
                    current_test['progress'] = {
                        'stage': 'download',
                        'percent': int(dl.get('progress', 0) * 100),
                        'bandwidth_bps': dl.get('bandwidth', 0) * 8
                    }
            elif msg_type == 'upload':
                ul = msg.get('upload', {})
                upload_event_time = time.monotonic()

                if (
                    ookla_download_started_at is not None
                    and ookla_download_ended_at is None
                ):
                    ookla_download_ended_at = upload_event_time

                if ookla_upload_started_at is None:
                    ookla_upload_started_at = upload_event_time
                    cp.log(
                        'Carrier telemetry: Ookla upload traffic '
                        'start detected'
                    )

                with test_lock:
                    current_test['progress'] = {
                        'stage': 'upload',
                        'percent': int(ul.get('progress', 0) * 100),
                        'bandwidth_bps': ul.get('bandwidth', 0) * 8
                    }
            elif msg_type == 'ping':
                ping = msg.get('ping', {})
                with test_lock:
                    current_test['progress'] = {
                        'stage': 'ping',
                        'latency': ping.get('latency', 0)
                    }
            elif msg_type == 'result':
                ookla_result_received_at = time.monotonic()

                if (
                    ookla_upload_started_at is not None
                    and ookla_upload_ended_at is None
                ):
                    ookla_upload_ended_at = ookla_result_received_at
                elif (
                    ookla_download_started_at is not None
                    and ookla_download_ended_at is None
                ):
                    ookla_download_ended_at = ookla_result_received_at

                result_data = msg
                break
            elif msg_type == 'log':
                level = msg.get('level', 'info')
                message = msg.get('message', '')
                if level in ('error', 'warning'):
                    cp.log(f'Ookla {level}: {message}')

        proc.wait()

        if result_data:
            dl_bw = result_data.get('download', {}).get('bandwidth', 0)
            ul_bw = result_data.get('upload', {}).get('bandwidth', 0)
            ping_ms = result_data.get('ping', {}).get('latency', 0)
            server = result_data.get('server', {})

            if dl_bw > 0 and ookla_download_started_at is not None:
                download_end = (
                    ookla_download_ended_at
                    or ookla_result_received_at
                    or time.monotonic()
                )

                _record_carrier_phase_window(
                    'download',
                    ookla_download_started_at,
                    download_end
                )

            if ul_bw > 0 and ookla_upload_started_at is not None:
                upload_end = (
                    ookla_upload_ended_at
                    or ookla_result_received_at
                    or time.monotonic()
                )

                _record_carrier_phase_window(
                    'upload',
                    ookla_upload_started_at,
                    upload_end
                )

            download_bytes = _safe_test_bytes(
                result_data.get('download', {}).get('bytes')
            )
            upload_bytes = _safe_test_bytes(
                result_data.get('upload', {}).get('bytes')
            )

            cp.log(
                'Ookla engine data: '
                f'download={download_bytes} bytes, '
                f'upload={upload_bytes} bytes'
            )

            return {
                'download_bps': dl_bw * 8,
                'upload_bps': ul_bw * 8,
                'download_bytes': download_bytes if dl_bw > 0 else None,
                'upload_bytes': upload_bytes if ul_bw > 0 else None,
                'ping_ms': ping_ms,
                'server': server.get('name', ''),
                'server_location': server.get('location', ''),
                'isp': result_data.get('isp', '')
            }
        return None
    except Exception as e:
        cp.log(f'Ookla error: {e}')
        return None


# =============================================================================
# TEST RUNNER (background thread)
# =============================================================================

def write_outputs(entry):
    """Write test results to configured output paths."""
    try:
        # Configured output targets: EFFECTIVE (Device>Group>Default) from the
        # two-layer manager. Legacy App Data is never a fallback (§16).
        outputs = config_mgr.active_section('outputs')
        if not isinstance(outputs, list) or not outputs:
            return

        # Format result text with datetime and interface/carrier
        dl = entry.get('download_mbps', 0)
        ul = entry.get('upload_mbps', 0)
        timestamp = entry.get('timestamp', '')
        iface = entry.get('interface', '')
        engine = entry.get('engine', '')

        # Get carrier name if interface is a modem
        carrier = ''
        try:
            devices = cp.get('status/wan/devices')
            if devices:
                for uid, dev in devices.items():
                    if isinstance(dev, dict):
                        if dev.get('info', {}).get('iface') == iface:
                            diag = dev.get('diagnostics', {})
                            carrier = diag.get('CARRID', '')
                            break
        except Exception:
            pass

        text = f'DL:{dl}Mbps UL:{ul}Mbps'
        if entry.get('latency_ms'):
            text += f' Lat:{entry["latency_ms"]}ms'
        if entry.get('jitter_ms'):
            text += f' Jit:{entry["jitter_ms"]}ms'

        # Add interface/carrier info
        iface_info = carrier if carrier else iface
        if iface_info:
            text += f' Iface:{iface_info}'

        text += f' Engine:{engine} {timestamp}'

        for output in outputs:
            try:
                if output == 'appdata:speedtest_results':
                    cp.put_appdata('speedtest_results', text)
                elif output.startswith('config/') or output.startswith('status/'):
                    cp.put(output, text)
                else:
                    cp.put(output, text)
            except Exception as e:
                cp.log(f'Error writing to output {output}: {e}')
    except Exception as e:
        cp.log(f'Error in write_outputs: {e}')


def _resolve_requested_interface(interface):
    """Resolve a UI interface request to one concrete NCOS interface.

    ``__active_wan__`` is a selection alias only. It is resolved from the
    current NCOS primary WAN immediately before test execution. Explicit
    interface names are returned unchanged.

    No fallback interface is attempted when Active Primary WAN cannot be
    resolved.
    """
    requested = str(interface or '').strip()

    if requested != '__active_wan__':
        return requested

    try:
        primary_uid = cp.get_wan_primary_device() or ''
    except Exception as error:
        cp.log(
            f'Active Primary WAN resolution failed reading primary device: '
            f'{error}'
        )
        return ''

    primary_uid = str(primary_uid or '').strip()

    if not primary_uid:
        cp.log(
            'Active Primary WAN resolution failed: '
            'NCOS reported no primary WAN device'
        )
        return ''

    try:
        primary_iface = cp.get(
            f'status/wan/devices/{primary_uid}/info/iface'
        )
    except Exception as error:
        cp.log(
            f'Active Primary WAN resolution failed for '
            f'{primary_uid}: {error}'
        )
        return ''

    primary_iface = str(primary_iface or '').strip()

    if not primary_iface:
        cp.log(
            f'Active Primary WAN resolution failed: '
            f'{primary_uid} has no concrete interface'
        )
        return ''

    return primary_iface


def run_test_thread(engine, params):
    """Run a speed test in a background thread."""
    global current_test, _active_carrier_collector

    # Define before entering the main try block so every exception and
    # early-return path can safely clean up telemetry.
    carrier_collector = None

    try:
        # The launch path reserves the execution slot before this thread
        # starts. If Stop was requested before the worker began executing,
        # honor it rather than re-asserting running=True.
        with test_lock:
            if not current_test['running']:
                cp.log(f'{engine} test cancelled before worker start')
                return

        result = None

        requested_interface = params.get('interface', '')
        interface = _resolve_requested_interface(
            requested_interface
        )

        if requested_interface == '__active_wan__':
            if not interface:
                error = (
                    'Active Primary WAN could not be resolved to a '
                    'connected NCOS interface. Test was not started.'
                )

                cp.log(error)

                with test_lock:
                    current_test['error'] = error
                    current_test['progress'] = {
                        'stage': 'error',
                        'percent': 0,
                    }

                return

            cp.log(
                f'Active Primary WAN resolved to concrete interface: '
                f'{interface}'
            )

        # From this point forward the alias no longer exists. All existing
        # execution, telemetry, history, CSV, and reporting code receives
        # only the concrete interface identity.
        params['interface'] = interface

        # Re-evaluate catalog restrictions against the concrete runtime WAN.
        # This protects scheduled Active Primary WAN jobs and closes the small
        # race where the primary WAN could change after manual preflight.
        defect = _evaluate_known_defect(
            engine,
            interface
        )

        if defect.get('blocked'):
            error = defect.get(
                'message',
                'This test engine is disabled for the selected interface.'
            )

            cp.log(
                f'Known defect blocked test: '
                f'{error}'
            )

            with test_lock:
                current_test['error'] = error
                current_test['progress'] = {
                    'stage': 'error',
                    'percent': 0,
                }

            return

        duration = params.get('duration', 10)

        # Carrier telemetry is optional and only applies to a WAN that has
        # positive cellular evidence. Satellite WANs may use an mdm-* UID,
        # but follow the Ethernet/non-cellular statistics path.
        if _interface_is_cellular_wan(interface):
            try:
                carrier_collector = CarrierTelemetryCollector(interface)
                carrier_collector.start()
                _active_carrier_collector = carrier_collector
            except Exception as e:
                cp.log(f'Carrier telemetry init error (non-fatal): {e}')
                carrier_collector = None
        else:
            _active_carrier_collector = None
            cp.log(
                'Carrier telemetry skipped: selected WAN is non-cellular'
            )

        if engine == 'ookla':
            result = run_ookla(interface)
        elif engine == 'netperf':
            include_latency = params.get('include_latency', False)
            host = params.get('host', '')
            result = run_netperf(interface, duration,
                                include_latency=include_latency, host=host)
        elif engine == 'iperf3':
            server = params.get('server', '')
            if not server:
                with test_lock:
                    current_test['error'] = 'No iPerf3 server specified'
                    current_test['running'] = False
                return
            port = params.get('port', 5201)
            result = run_iperf3(
                         server,
                         duration,
                         interface,
                         port,
                         context=params
                     )

        if result:
            # Stop carrier telemetry collector
            if carrier_collector:
                try:
                    carrier_collector.stop()
                except Exception as e:
                    cp.log(f'Carrier telemetry stop error (non-fatal): {e}')

            # Data volume comes only from the completed test-engine
            # result. WAN interface counters include unrelated production
            # traffic and are intentionally not used here.
            download_bytes = _safe_test_bytes(
                result.get('download_bytes')
            )
            upload_bytes = _safe_test_bytes(
                result.get('upload_bytes')
            )

            data_in_mb = (
                round(download_bytes / (1024 * 1024), 2)
                if download_bytes is not None
                else None
            )

            data_out_mb = (
                round(upload_bytes / (1024 * 1024), 2)
                if upload_bytes is not None
                else None
            )

            if (
                download_bytes is not None
                or upload_bytes is not None
            ):
                data_total_bytes = (
                    (download_bytes or 0)
                    + (upload_bytes or 0)
                )

                data_total_mb = round(
                    data_total_bytes / (1024 * 1024),
                    2
                )
            else:
                data_total_mb = None

            cp.log(
                'Engine-reported test data: '
                f'engine={engine}, '
                f'download={download_bytes} bytes, '
                f'upload={upload_bytes} bytes'
            )

            # Determine test status: complete, partial, or failed
            dl = result.get('download_bps', 0)
            ul = result.get('upload_bps', 0)
            if dl > 0 and ul > 0:
                status_val = 'complete'
            elif dl > 0 or ul > 0:
                status_val = 'partial'
            else:
                status_val = 'failed'

            # Build history entry
            entry = {
                'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
                'engine': engine,
                'download_mbps': round(dl / 1000000, 2),
                'upload_mbps': round(ul / 1000000, 2),
                'ping_ms': round(result.get('ping_ms', 0), 1) if result.get('ping_ms') else None,
                'latency_ms': round(result.get('latency_ms', 0), 2) if result.get('latency_ms') else None,
                'jitter_ms': round(result.get('jitter_ms', 0), 2) if result.get('jitter_ms') else None,
                'interface': interface or 'auto',
                'interface_label': _get_wan_interface_label(interface),
                'duration': duration,
                'data_transferred_mb': (
                    data_total_mb
                    if data_total_mb is not None and data_total_mb > 0
                    else None
                ),
                'data_download_mb': (
                    data_in_mb
                    if data_in_mb is not None and data_in_mb > 0
                    else None
                ),
                'data_upload_mb': (
                    data_out_mb
                    if data_out_mb is not None and data_out_mb > 0
                    else None
                ),
                'host': params.get('host', ''),
                'server': result.get('server', ''),
                'port': params.get('port', ''),
                'isp': result.get('isp', ''),
                'include_latency': params.get('include_latency', False),
                'status': status_val,
                'trigger': params.get('_trigger', 'manual')
            }
            if engine == 'iperf3':
                # Persist only the actual endpoint used by the completed
                # execution. Do not persist source mode, Region, backup
                # metadata, or the originally configured port range.
                entry.pop(
                    'port',
                    None
                )

                entry[
                    'server_name'
                ] = (
                    result.get(
                        'server_name'
                    )
                    or params.get(
                        'server_name'
                    )
                    or result.get(
                        'server'
                    )
                    or params.get(
                        'server',
                        ''
                    )
                )

                entry[
                    'server'
                ] = (
                    result.get(
                        'server'
                    )
                    or params.get(
                        'server',
                        ''
                    )
                )

                entry[
                    'download_port'
                ] = result.get(
                    'download_port'
                )

                entry[
                    'upload_port'
                ] = result.get(
                    'upload_port'
                )
            if status_val == 'failed':
                entry['error'] = result.get('error', 'Test returned zero results')
                entry['status_message'] = (
                    f'Test failed: {entry["error"]}. '
                    f'Neither download nor upload completed successfully.')
                cp.log(f'Test FAILED: {entry["error"]}')
            elif status_val == 'partial':
                err = result.get('error', '')
                if err:
                    entry['error'] = err
                # Build an explanation of what succeeded and what failed
                dl_mbps = entry['download_mbps']
                ul_mbps = entry['upload_mbps']
                if dl > 0 and ul == 0:
                    msg = (f'Download completed ({dl_mbps} Mbps) but upload '
                           f'failed.')
                elif ul > 0 and dl == 0:
                    msg = (f'Upload completed ({ul_mbps} Mbps) but download '
                           f'failed.')
                else:
                    msg = 'Test partially completed.'
                if err:
                    msg += f' Reason: {err}'
                entry['status_message'] = msg
                cp.log(f'Test PARTIAL: DL={dl_mbps} UL={ul_mbps}')
            # Add status_message for complete tests
            if status_val == 'complete':
                entry['status_message'] = (
                    f'Test completed successfully. '
                    f'Download: {entry["download_mbps"]} Mbps, '
                    f'Upload: {entry["upload_mbps"]} Mbps.')
            # Collect cellular telemetry
            cellular = _collect_cellular_snapshot(interface)
            if cellular:
                entry['cellular'] = cellular

            # Only tests with a proven traffic-active serving-cell handoff
            # incur the short +2/+4/+6 second stabilization window. The
            # immediate top-level cellular snapshot above is intentionally
            # captured first so its semantics do not change.
            if carrier_collector:
                try:
                    carrier_collector.collect_post_test_stability()
                except Exception as e:
                    cp.log(
                        'Carrier telemetry post-test check error '
                        f'(non-fatal): {e}'
                    )

            # Add carrier activity telemetry from collector
            if carrier_collector:
                try:
                    ca_results = carrier_collector.get_results()
                    if ca_results:
                        capability = _get_ca_capability_reference(interface)
                        if capability:
                            ca_results['capability'] = capability
                        entry['carrier_activity'] = ca_results
                except Exception as e:
                    cp.log(f'Carrier telemetry results error (non-fatal): {e}')
            add_result(entry)
            # Write to configured outputs (only for successful tests)
            if status_val == 'complete':
                write_outputs(entry)
            with test_lock:
                current_test['progress'] = {
                    'stage': 'complete',
                    'result': entry
                }
                if status_val == 'failed':
                    current_test['error'] = entry.get('error', 'Test failed')
        else:
            # Stop carrier telemetry collector on failure path
            if carrier_collector:
                try:
                    carrier_collector.stop()
                except Exception:
                    pass

            with test_lock:
                err_msg = current_test.get('error') or 'Test failed'
                current_test['error'] = err_msg
            # Save failed entry to history
            entry = {
                'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
                'engine': engine,
                'download_mbps': 0,
                'upload_mbps': 0,
                'ping_ms': None,
                'latency_ms': None,
                'jitter_ms': None,
                'interface': interface or 'auto',
                'interface_label': _get_wan_interface_label(interface),
                'duration': duration,
                'server': params.get('server', ''),
                'status': 'failed',
                'error': current_test.get('error') or 'No results',
                'status_message': (
                    f'Test failed: '
                    f'{current_test.get("error") or "No results returned"}. '
                    f'The test engine did not produce any speed measurements.')
            }
            if engine == 'iperf3':
                entry[
                    'server_name'
                ] = (
                    params.get(
                        'server_name'
                    )
                    or params.get(
                        'server',
                        ''
                    )
                )

                entry[
                    'download_port'
                ] = None

                entry[
                    'upload_port'
                ] = None

            # Collect cellular telemetry
            cellular = _collect_cellular_snapshot(interface)
            if cellular:
                entry['cellular'] = cellular

            # Only tests with a proven traffic-active serving-cell handoff
            # incur the short +2/+4/+6 second stabilization window. The
            # immediate top-level cellular snapshot above is intentionally
            # captured first so its semantics do not change.
            if carrier_collector:
                try:
                    carrier_collector.collect_post_test_stability()
                except Exception as e:
                    cp.log(
                        'Carrier telemetry post-test check error '
                        f'(non-fatal): {e}'
                    )

            # Add carrier activity telemetry from collector
            if carrier_collector:
                try:
                    ca_results = carrier_collector.get_results()
                    if ca_results:
                        capability = _get_ca_capability_reference(interface)
                        if capability:
                            ca_results['capability'] = capability
                        entry['carrier_activity'] = ca_results
                except Exception:
                    pass
            add_result(entry)
    except Exception as e:
        cp.log(f'Test thread error: {e}')
        with test_lock:
            current_test['error'] = str(e)
        # Clean up carrier collector on exception
        if carrier_collector:
            try:
                carrier_collector.stop()
            except Exception:
                pass
    finally:
        # Guarantee collector cleanup for every path, including validation
        # failures, early returns, and unexpected test-engine exceptions.
        if carrier_collector and carrier_collector._running:
            try:
                carrier_collector.stop()
            except Exception as e:
                cp.log(
                    f'Carrier telemetry cleanup error (non-fatal): {e}'
                )

        _active_carrier_collector = None

        if (
            engine == 'iperf3'
            and params.get('_trigger', 'manual') == 'manual'
            and params.get('_persist_public_region')
        ):
            _persist_last_public_region_after_test(
                params.get('_persist_public_region')
            )

        _release_test_slot()


# =============================================================================
# HTTP SERVER
# =============================================================================


def _normalize_legacy_user_iperf3_import_catalog(catalog):
    """Convert supported pre-2.7 User Server exports to schema v1."""
    if (
        isinstance(catalog, dict)
        and 'schema_version' in catalog
    ):
        return catalog

    if isinstance(catalog, list):
        entries = catalog

    elif isinstance(catalog, dict):
        if isinstance(
            catalog.get('servers'),
            list
        ):
            entries = catalog.get(
                'servers'
            )

        elif isinstance(
            catalog.get('iperf3_servers'),
            list
        ):
            entries = catalog.get(
                'iperf3_servers'
            )

        else:
            return catalog

    else:
        return catalog

    canonical = []

    for number, entry in enumerate(
        entries,
        start=1
    ):
        if not isinstance(
            entry,
            dict
        ):
            raise ValueError(
                'Legacy server entry {} must be '
                'a JSON object'.format(
                    number
                )
            )

        host = str(
            entry.get('host')
            or entry.get('server')
            or ''
        ).strip()

        if not host:
            raise ValueError(
                'Legacy server entry {} is missing '
                'a server/host value'.format(
                    number
                )
            )

        server_name = str(
            entry.get('server_name')
            or entry.get('label')
            or host
        ).strip()

        if (
            'port' in entry
            and str(
                entry.get('port') or ''
            ).strip()
        ):
            (
                port_start,
                port_end
            ) = _parse_user_iperf3_port_value(
                entry.get('port')
            )

        elif (
            entry.get('port_start') is not None
            and entry.get('port_end') is not None
        ):
            try:
                port_start = int(
                    entry.get('port_start')
                )

                port_end = int(
                    entry.get('port_end')
                )

            except Exception:
                raise ValueError(
                    'Legacy server entry {} has invalid '
                    'port_start/port_end values'.format(
                        number
                    )
                )

        else:
            raise ValueError(
                'Legacy server entry {} is missing '
                'port information'.format(
                    number
                )
            )

        canonical.append({
            'server_name':
                server_name,
            'host':
                host,
            'port_start':
                port_start,
            'port_end':
                port_end,
            'city':
                str(
                    entry.get('city')
                    or ''
                ).strip(),
            'country':
                str(
                    entry.get('country')
                    or ''
                ).strip(),
        })

    return {
        'schema_version': 1,
        'servers': canonical
    }


class SpeedtestHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for the speedtest web interface."""

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass

    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/' or self.path == '/index.html':
            self.serve_file('index.html', 'text/html')
        elif self.path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
        elif self.path == '/api/status':
            self.send_json(self.get_status())
        elif self.path == '/api/history':
            history = load_history()
            self.send_json(_add_ca_capabilities_to_history(history))
        elif self.path == '/api/interfaces':
            self.send_json(get_wan_interfaces())
        elif self.path == '/api/engines':
            self.send_json(self.get_engines())
        elif self.path == '/api/router_info':
            self.send_json(self.get_router_info())
        elif self.path == '/api/cellular_status' or self.path.startswith('/api/cellular_status?'):
            iface = ''
            if '?' in self.path:
                qs = self.path.split('?', 1)[1]
                for part in qs.split('&'):
                    if part.startswith('iface='):
                        iface = part[6:]
            self.send_json(self.get_cellular_status(iface))
        elif self.path == '/api/geo_gps':
            self.send_json(
                self.get_geo_gps()
            )

        elif self.path == '/api/geo_settings':
            self.send_json(
                _effective_geo_settings()
            )

        elif (
            self.path == '/api/cellular_analysis'
            or self.path.startswith('/api/cellular_analysis?')
        ):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            history = load_history()

            # Normal Cellular Analysis remains scoped by the lower-page
            # Interface and History controls.
            analysis = build_cellular_analysis(
                history,
                interface=params.get(
                    'iface',
                    ['']
                )[0],
                scope=params.get(
                    'history',
                    ['all']
                )[0],
                selected_cell_key=params.get(
                    'cell',
                    ['']
                )[0],
            )

            # GeoView is deliberately site-wide. It uses every retained
            # cellular result across all cellular interfaces, independent
            # of the lower-page filters.
            site_inventory = (
                build_site_cell_inventory(
                    history
                )
            )

            geo = dict(
                analysis.get('geo')
                or {}
            )

            geo.update({
                'cells':
                    site_inventory.get(
                        'cells',
                        []
                    ),

                'interfaces':
                    site_inventory.get(
                        'interfaces',
                        []
                    ),

                'tests':
                    site_inventory.get(
                        'tests',
                        0
                    ),

                # External cell-location providers are intentionally not
                # implemented in the v1.1.1 foundation.
                'estimated_locations': 0,
            })

            analysis['geo'] = (
                apply_geo_settings(
                    geo,
                    _effective_geo_settings(),
                )
            )

            self.send_json(
                analysis
            )

        elif self.path == '/api/version':
            self.send_json({'version': APP_VERSION})
        elif self.path == '/api/capabilities' or self.path.startswith('/api/capabilities?'):
            iface = ''
            if '?' in self.path:
                qs = self.path.split('?', 1)[1]
                for part in qs.split('&'):
                    if part.startswith('iface='):
                        iface = part[6:]
            self.send_json(
                get_model_capabilities(
                    iface
                )
            )
        elif self.path == '/api/schedule':
            with schedule_lock:
                data = dict(schedule_config)
            # 'enabled'/'autostart' are the persisted intent; 'running' is the
            # runtime state (may be false after a restart when autostart is off
            # even though enabled=true). Countdown reflects the RUNTIME state.
            if data.get('running') and data.get('cron'):
                data['next_run_seconds'] = self._seconds_to_next_cron(data['cron'])
            self.send_json(data)
        elif self.path == '/api/outputs':
            self.send_json(self.get_outputs())
        elif self.path == '/api/config/state':
            self.handle_config_state()
        elif self.path == '/api/iperf3/server_state':
            self.send_json(
                _get_active_iperf3_server_state()
            )
        elif self.path == '/api/iperf3/reliability':
            self.send_json(
                _get_iperf3_reliability_state()
            )
        elif self.path == '/api/netperf_servers':
            self.send_json(self.get_netperf_servers())
        elif self.path == '/api/iperf3_servers':
            self.send_json(self.get_iperf3_servers())
        elif self.path == '/api/servers':
            self.send_json(self.get_all_servers())
        elif self.path == '/api/reports':
            self.send_json(self.get_saved_reports())
        elif self.path == '/api/cell_diagnostics':
            self.send_json(self.get_cell_diagnostics())
        elif self.path == '/api/carrier_telemetry':
            self.send_json(self.get_live_carrier_telemetry())
        elif self.path.startswith('/static/'):
            self.serve_static()
        else:
            self.send_error(404)

    def do_POST(self):
        """Handle POST requests."""
        if self.path == '/api/start':
            self.handle_start()
        elif self.path == '/api/stop':
            self.handle_stop()
        elif self.path == '/api/clear_history':
            self.handle_clear_history()
        elif self.path == '/api/history/delete':
            self.handle_delete_history_entry()
        elif self.path == '/api/iperf3/server_mode':
            self.handle_set_iperf3_server_mode()
        elif self.path == '/api/iperf3/user/save':
            self.handle_user_iperf3_save()
        elif self.path == '/api/iperf3/user/edit':
            self.handle_user_iperf3_edit()
        elif self.path == '/api/iperf3/user/delete':
            self.handle_user_iperf3_delete()
        elif self.path == '/api/iperf3/user/delete_all':
            self.handle_user_iperf3_delete_all()
        elif self.path == '/api/iperf3/user/import':
            self.handle_user_iperf3_import()
        elif self.path == '/api/iperf3/reliability/reset':
            self.handle_reset_iperf3_reliability()
        elif self.path == '/api/servers/save':
            self.handle_save_server()
        elif self.path == '/api/servers/delete':
            self.handle_delete_server()
        elif self.path == '/api/servers/delete_all':
            self.handle_delete_all_servers()
        elif self.path == '/api/servers/import':
            self.handle_import_servers()
        elif self.path == '/api/reports/save':
            self.handle_save_report()
        elif self.path == '/api/reports/delete':
            self.handle_delete_report()
        elif self.path == '/api/schedule':
            self.handle_save_schedule()
        elif self.path == '/api/outputs':
            self.handle_save_outputs()
        elif self.path == '/api/geo_settings':
            self.handle_save_geo_settings()
        # --- Two-layer Configuration Management endpoints (v1.1.2) ----------
        elif self.path == '/api/config/state':
            self.handle_config_state()
        elif self.path == '/api/config/convert':
            self.handle_config_convert()
        elif self.path == '/api/config/group_upgrade_candidate':
            self.handle_config_group_upgrade_candidate()
        elif self.path == '/api/config/migrate/sections':
            self.handle_config_migrate_sections()
        elif self.path == '/api/config/migrate/candidate':
            self.handle_config_migrate_candidate()
        elif self.path == '/api/config/migrate/validate':
            self.handle_config_migrate_validate()
        elif self.path == '/api/config/migrate/cleanup':
            self.handle_config_migrate_cleanup()
        elif self.path == '/api/config/update_group/sections':
            self.handle_config_update_group_sections()
        elif self.path == '/api/config/update_group/candidate':
            self.handle_config_update_group_candidate()
        elif self.path == '/api/config/update_group/validate':
            self.handle_config_update_group_validate()
        elif self.path == '/api/config/update_group/cleanup':
            self.handle_config_update_group_cleanup()
        elif self.path == '/api/config/reset_section':
            self.handle_config_reset_section()
        elif self.path == '/api/config/reset':
            self.handle_config_reset()
        elif self.path == '/api/config/factory_reset':
            self.handle_config_factory_reset()
        else:
            self.send_error(404)

    def do_DELETE(self):
        """Handle DELETE requests."""
        if self.path.startswith('/api/servers/delete'):
            self.handle_delete_server()
        else:
            self.send_error(404)

    # =====================================================================
    # CANONICAL CONFIGURATION MANAGEMENT ENDPOINTS (v1.1.2)
    # =====================================================================

    def handle_config_state(self):
        """Return the two-layer configuration state (§53).

        Exposes the LOCKED new model: derived state, per-layer presence /
        revision / schema_version, override sections, and mutation-block info.
        Old origin/mode is NEVER exposed as the source of truth.
        """
        try:
            report = config_mgr.state_report()

            try:
                report['history_count'] = len(load_history())
            except Exception:
                report['history_count'] = None
            report['history_capacity'] = MAX_HISTORY
            report['app_version'] = APP_VERSION

            self.send_json(report)
        except Exception as exc:
            cp.log(f'Config state error: {exc}')
            self.send_json({'error': 'Unable to read configuration state.'},
                           500)

    def handle_config_convert(self):
        """Convert legacy/experimental OR older-schema Device config (§17-§21,
        §49). This is the ONLY action that migrates data to
        speedtest_analyzer_device."""
        block = config_mgr.mutation_blocked()
        device_load = config_mgr._load_layer('device')
        if device_load.status == 'older':
            result = config_mgr.convert_older_device_schema()
        else:
            result = config_mgr.convert_legacy_to_device()
        if result.status == 'saved':
            self.send_json({'status': 'converted', 'message': result.message})
        else:
            self.send_json({'status': 'error',
                            'error': result.error or 'Conversion failed.'},
                           409)

    def handle_config_group_upgrade_candidate(self):
        """Return an upgraded Group JSON candidate for an older Group schema
        (§50). Never written locally."""
        cand = config_mgr.build_group_upgrade_candidate()
        if cand is None:
            self.send_json({'error': 'No older-schema Group configuration to '
                                     'upgrade.'}, 409)
            return
        self.send_json({
            'status': 'candidate',
            'sdk_data_name': config_mgr.GROUP_KEY,
            'config_json': cand.to_json(),
            'group_revision': cand.group_revision,
        })

    # --- Group Migration wizard (selection-only, group-first) ---------------

    def handle_config_migrate_sections(self):
        """Return the configured Device sections eligible for Group promotion
        (§25). Selection only; no configuration values are editable here."""
        try:
            sections = config_mgr.migration_available_sections()
            self.send_json({'status': 'ok', 'sections': sections})
        except Exception as exc:
            cp.log(f'Migration sections error: {exc}')
            self.send_json({'error': 'Unable to read migration sections.'},
                           500)

    def handle_config_migrate_candidate(self):
        """Validate the selection and build the Group candidate JSON (§27-§29).

        Nothing is written locally. Returns the SDK Data NAME and the complete
        Group JSON VALUE for the user to paste into the NCM Group.
        """
        try:
            data = self._read_json_request()
        except Exception:
            data = {}
        selected = data.get('sections')
        if not isinstance(selected, list):
            self.send_json({'error': 'sections list required.'}, 400)
            return
        cand, reason = config_mgr.build_group_migration_candidate(selected)
        if cand is None:
            self.send_json({'status': 'invalid', 'reason': reason}, 409)
            return
        self.send_json({
            'status': 'candidate',
            'sdk_data_name': config_mgr.GROUP_KEY,
            'config_json': cand.to_json(),
            'group_revision': cand.group_revision,
            'promoted_sections': selected,
        })

    def handle_config_migrate_validate(self):
        """Validate the expected Group payload is visible on device (§30).

        Does NOT claim NCM provenance. Does NOT mutate the Device document.
        """
        try:
            data = self._read_json_request()
        except Exception:
            data = {}
        try:
            revision = int(data.get('group_revision', 1))
        except Exception:
            revision = 1
        result = config_mgr.validate_group_present(revision)
        if result.ok:
            self.send_json({'status': 'validated', 'message': result.reason})
        else:
            self.send_json({'status': 'not_yet', 'reason': result.reason})

    def handle_config_migrate_cleanup(self):
        """Trim promoted sections from the Device document AFTER Group
        validation (§31, §32, §34). Supports cleanup retry on failure."""
        try:
            data = self._read_json_request()
        except Exception:
            data = {}
        promoted = data.get('promoted_sections')
        if not isinstance(promoted, list):
            self.send_json({'error': 'promoted_sections list required.'}, 400)
            return
        result = config_mgr.trim_promoted_device_sections(promoted)
        if result.status == 'saved':
            self.send_json({'status': 'complete', 'message': result.message})
        else:
            # Group stays intact; Device cleanup incomplete -> allow retry.
            self.send_json({'status': 'cleanup_incomplete',
                            'error': result.error}, 409)

    # --- Update NCM Group Configuration (promote into an EXISTING Group) -----

    def handle_config_update_group_sections(self):
        """Return the current Device overrides eligible for Group update.

        Same shape as the migrate wizard: {section, label, default_selected,
        promotable, reason}. Shows ONLY current Device overrides.
        """
        try:
            sections = config_mgr.update_group_available_sections()
            self.send_json({'status': 'ok', 'sections': sections})
        except Exception as exc:
            cp.log(f'Update-group sections error: {exc}')
            self.send_json({'error': 'Unable to read Device overrides.'}, 500)

    def handle_config_update_group_candidate(self):
        """Validate the selection and build the REVISED Group candidate JSON.

        Starts from a deep copy of the current Group and promotes ONLY the
        selected Device sections. group_revision = current + 1. Nothing is
        written locally. Returns the SDK Data NAME, the complete revised Group
        VALUE, the current + new group_revision, the promoted sections, and the
        reconciliation token (group_revision, device_revision).
        """
        try:
            data = self._read_json_request()
        except Exception:
            data = {}
        selected = data.get('sections')
        if not isinstance(selected, list):
            self.send_json({'error': 'sections list required.'}, 400)
            return
        cand, reason, token = config_mgr.build_group_update_candidate(selected)
        if cand is None:
            self.send_json({'status': 'invalid', 'reason': reason}, 409)
            return
        self.send_json({
            'status': 'candidate',
            'sdk_data_name': config_mgr.GROUP_KEY,
            'config_json': cand.to_json(),
            'new_group_revision': cand.group_revision,
            'current_group_revision': cand.group_revision - 1,
            'promoted_sections': selected,
            'token': token,
        })

    def handle_config_update_group_validate(self):
        """Validate the revised Group payload is visible at the new revision.

        Honors the reconciliation token: if the Device changed during the
        staged workflow the update is aborted and the user must restart. Does
        NOT mutate the Device document; does NOT claim NCM provenance.
        """
        try:
            data = self._read_json_request()
        except Exception:
            data = {}
        try:
            revision = int(data.get('new_group_revision'))
        except Exception:
            self.send_json({'error': 'new_group_revision required.'}, 400)
            return
        token = data.get('token')
        if token is not None and not isinstance(token, dict):
            self.send_json({'error': 'token must be an object.'}, 400)
            return
        result = config_mgr.validate_group_update(revision, token=token)
        if result.ok:
            self.send_json({'status': 'validated', 'message': result.reason})
        elif getattr(result, 'reconcile_aborted', False):
            # Device changed during the staged workflow: this is NOT a
            # "retry validate" case -- the whole workflow must be restarted.
            self.send_json({'status': 'reconcile_aborted',
                            'reason': result.reason}, 409)
        else:
            self.send_json({'status': 'not_yet', 'reason': result.reason})

    def handle_config_update_group_cleanup(self):
        """Remove promoted Device sections AFTER the revised Group validated.

        Honors the reconciliation token. On failure the Group is left intact
        and cleanup_incomplete is returned (Device still wins); Retry allowed.
        """
        try:
            data = self._read_json_request()
        except Exception:
            data = {}
        promoted = data.get('promoted_sections')
        if not isinstance(promoted, list):
            self.send_json({'error': 'promoted_sections list required.'}, 400)
            return
        token = data.get('token')
        if token is not None and not isinstance(token, dict):
            self.send_json({'error': 'token must be an object.'}, 400)
            return
        result = config_mgr.cleanup_promoted_after_group_update(
            promoted, token=token)
        if result.status == 'saved':
            self.send_json({'status': 'complete', 'message': result.message})
        elif getattr(result, 'reconcile_aborted', False):
            # Device changed during the staged workflow: restart required, NOT
            # a cleanup retry (retrying with a stale token keeps failing).
            self.send_json({'status': 'reconcile_aborted',
                            'error': result.error}, 409)
        else:
            self.send_json({'status': 'cleanup_incomplete',
                            'error': result.error}, 409)

    # --- Device override reset (§36, §37) -----------------------------------

    def handle_config_reset_section(self):
        """Reset ONE Device override section (§36).

        The manager validates the PROPOSED effective config first. When the
        requested reset alone would create a dependency conflict (the confirmed
        iPerf3 schedule <-> server-mode defect) it returns
        dependency_reset_required with the coupled sections and NOTHING is
        written; the frontend confirms a coupled reset by re-POSTing with
        confirm_sections. On success reset_target says whether the section
        inherited the NCM Group value or the Built-in Default (§ wording fix).
        """
        try:
            data = self._read_json_request()
        except Exception:
            data = {}
        section = data.get('section')
        if not section:
            self.send_json({'error': 'section required.'}, 400)
            return
        confirm_sections = data.get('confirm_sections')
        if confirm_sections is not None and \
                not isinstance(confirm_sections, list):
            self.send_json({'error': 'confirm_sections must be a list.'}, 400)
            return
        result = config_mgr.reset_section_to_group(
            section, confirm_sections=confirm_sections)
        if result.status == 'saved':
            self.send_json({'status': 'reset', 'message': result.message,
                            'reset_target': result.reset_target})
        elif result.status == 'dependency_reset_required':
            dep = result.dependency or {}
            self.send_json({
                'status': 'dependency_reset_required',
                'requested_section': dep.get('requested_section'),
                'requested_label': dep.get('requested_label'),
                'required_reset_sections': dep.get('required_reset_sections',
                                                   []),
                'required_reset_labels': dep.get('required_reset_labels', []),
                'reason': dep.get('reason', ''),
                'reset_target': dep.get('reset_target'),
            }, 409)
        else:
            self.send_json({'status': 'error',
                            'error': result.error or 'Reset failed.'}, 409)

    def handle_config_reset(self):
        """Reset ALL Device overrides (§37) / Device-only reset (§38).

        Never deletes speedtest_analyzer_group.
        """
        result = config_mgr.reset_all_device_overrides()
        if result.status == 'saved':
            self.send_json({'status': 'reset', 'message': result.message})
        else:
            self.send_json({'status': 'error',
                            'error': result.error or 'Reset failed.'}, 409)

    def handle_config_factory_reset(self):
        """Factory Reset (explicit confirmation required in request body)."""
        try:
            data = self._read_json_request()
        except Exception:
            data = {}
        if not data.get('confirm'):
            self.send_json({'error': 'Explicit confirmation required.'}, 400)
            return
        outcome = config_mgr.factory_reset(clear_history_fn=clear_history_storage)
        self.send_json({
            'status': 'factory_reset',
            'removed_appdata': outcome.removed_appdata,
            'removed_files': outcome.removed_files,
            'kept_group_config': outcome.kept_group,
            'message': outcome.message,
        })

    def handle_save_geo_settings(self):
        """Persist explicit provider-independent GeoView configuration."""
        content_length = int(
            self.headers.get(
                'Content-Length',
                0
            )
        )

        body = (
            self.rfile.read(
                content_length
            ).decode('utf-8')
            if content_length
            else '{}'
        )

        try:
            data = json.loads(body)

        except json.JSONDecodeError:
            self.send_json(
                {
                    'error':
                        'Invalid JSON'
                },
                400,
            )
            return

        # Validate/normalize the incoming GeoView settings WITHOUT persisting
        # to the legacy geoview_settings key. Persistence is routed through the
        # canonical Configuration Manager so it participates in the Device/
        # NCM Group workflow like every other normal configuration section.
        try:
            normalized = config_mgr.cellular_geo.normalize_geo_settings(
                data, mark_configured=True)
            geoview_value = config_mgr.cellular_geo._persisted_settings(
                normalized)

        except ValueError as exc:
            self.send_json({'error': str(exc)}, 400)
            return

        self._respond_config_apply(
            'geoview', geoview_value,
            success_payload=normalized)


    def handle_set_iperf3_server_mode(self):
        """Switch between Public and User iPerf3 server sources."""
        content_length = int(
            self.headers.get(
                'Content-Length',
                0
            )
        )

        body = (
            self.rfile.read(
                content_length
            ).decode('utf-8')
            if content_length
            else '{}'
        )

        try:
            data = json.loads(body)

        except json.JSONDecodeError:
            self.send_json({
                'error': 'Invalid JSON'
            }, 400)
            return

        result, status_code = (
            _switch_iperf3_server_mode(
                data.get('server_mode'),
                bool(
                    data.get(
                        'confirm_schedule_reset',
                        False
                    )
                )
            )
        )

        self.send_json(
            result,
            status_code
        )


    def get_geo_gps(self):
        """Return one on-demand local GPS status sample for GeoView."""
        try:
            gps = (
                cp.get_gps_status()
                or {}
            )

        except Exception as exc:
            cp.log(
                'GeoView GPS query failed: %s'
                % exc
            )

            return {
                'available': False,
                'gps_lock': False,
                'fix_available': False,
                'latitude': None,
                'longitude': None,
                'satellites': None,
                'accuracy': None,
                'last_fix_age': None,
            }

        latitude = gps.get(
            'latitude'
        )

        longitude = gps.get(
            'longitude'
        )

        gps_lock = bool(
            gps.get(
                'gps_lock'
            )
            if gps.get(
                'gps_lock'
            ) is not None
            else gps.get(
                'lock'
            )
        )

        fix_available = gps_fix_is_usable(
            {
                'gps_lock': gps_lock,
                'latitude': latitude,
                'longitude': longitude,
            }
        )

        return {
            'available': True,

            'gps_lock':
                gps_lock,

            'fix_available':
                fix_available,

            'latitude':
                latitude,

            'longitude':
                longitude,

            'satellites':
                gps.get(
                    'satellites'
                ),

            'accuracy':
                gps.get(
                    'accuracy'
                ),

            'last_fix_age':
                gps.get(
                    'last_fix_age'
                ),
        }

    def get_status(self):
        """Get current test status."""
        with test_lock:
            return {
                'running': current_test['running'],
                'engine': current_test['engine'],
                'progress': current_test['progress'].copy(),
                'error': current_test['error']
            }

    def get_router_info(self):
        """Get router hostname, model, and firmware for filenames and display."""
        info = {'hostname': 'router', 'model': '', 'firmware': ''}
        try:
            info['hostname'] = cp.get('config/system/system_id') or 'router'
        except Exception:
            pass
        try:
            product = cp.get('status/product_info')
            if product:
                info['model'] = product.get('product_name', '')
        except Exception:
            pass
        try:
            fw = cp.get('status/fw_info')
            if fw:
                major = fw.get('major_version', 0)
                minor = fw.get('minor_version', 0)
                patch = fw.get('patch_version', 0)
                info['firmware'] = '{}.{}.{}'.format(major, minor, patch)
        except Exception:
            pass
        return info

    def get_cellular_status(self, iface=''):
        """Get current cellular health and service type for a given interface."""
        try:
            if not iface:
                # No interface specified — check all connected cellular interfaces
                interfaces = get_wan_interfaces()
                if not interfaces:
                    return {'has_cellular': False}
                # Try each interface until we find a cellular one
                for intf in interfaces:
                    snapshot = _collect_cellular_snapshot(
                        intf.get('iface', ''),
                        include_active_carriers=True
                    )
                    if snapshot:
                        carriers = snapshot.get('active_carriers', {})
                        return {
                            'has_cellular': True,
                            'cellular_health_score': snapshot.get('cellular_health_score'),
                            'cellular_health_category': snapshot.get('cellular_health_category'),
                            'service_type': snapshot.get('service_type'),
                            'service_display': snapshot.get('service_display'),
                            'signal_strength': snapshot.get('signal_strength'),
                            'carrier_state': carriers,
                        }
                return {'has_cellular': False}
            # Specific interface requested
            snapshot = _collect_cellular_snapshot(
                iface,
                include_active_carriers=True
            )
            if not snapshot:
                return {'has_cellular': False}

            carriers = snapshot.get('active_carriers', {})
            return {
                'has_cellular': True,
                'cellular_health_score': snapshot.get('cellular_health_score'),
                'cellular_health_category': snapshot.get('cellular_health_category'),
                'service_type': snapshot.get('service_type'),
                'service_display': snapshot.get('service_display'),
                'signal_strength': snapshot.get('signal_strength'),
                'carrier_state': carriers,
            }
        except Exception:
            return {'has_cellular': False}

    def _seconds_to_next_cron(self, cron_expr):
        """Estimate seconds until next cron match (max 24h lookahead)."""
        try:
            now = datetime.utcnow()
            for i in range(1, 1441):  # Check next 24 hours, minute by minute
                candidate = datetime(now.year, now.month, now.day,
                                     now.hour, now.minute)
                # Add i minutes
                import calendar
                total_minutes = now.hour * 60 + now.minute + i
                days_ahead = total_minutes // 1440
                remaining = total_minutes % 1440
                candidate = now.replace(hour=remaining // 60,
                                        minute=remaining % 60, second=0)
                if days_ahead > 0:
                    # Simple next-day approximation
                    pass
                if cron_matches(cron_expr, candidate):
                    return i * 60 - now.second
            return None
        except Exception:
            return None

    def get_engines(self):
        """Get available speedtest engines."""
        engines = []
        if has_ookla():
            engines.append({
                'id': 'ookla',
                'name': 'Ookla Speedtest',
                'description': 'Licensed Ookla binary detected',
                'needs_server': False
            })
        engines.append({
            'id': 'iperf3',
            'name': 'iPerf3',
            'description': 'Requires external iPerf3 server',
            'needs_server': True
        })
        engines.append({
            'id': 'netperf',
            'name': 'Netperf (Built-in)',
            'description': 'Uses router built-in netperf service',
            'needs_server': False
        })
        return engines

    def get_iperf3_servers(self):
        """Load iperf3 server list from appdata 'iperf3_servers' (JSON),
        falling back to bundled CSV.

        Appdata format: [{"server":"host","port":"5201-5210","country":"US","city":"Seattle"}, ...]
        Port can be a single port ("5201") or a range ("5201-5210").
        """
        # Effective (Device>Group>Default) User Server list from the two-layer
        # manager. Legacy App Data is never a fallback once a canonical key
        # exists (§16); the manager surfaces legacy through its effective
        # config only while in upgrade-required compatibility mode.
        try:
            effective_users = config_mgr.active_section('iperf3_user_servers')
            if isinstance(effective_users, list) and len(effective_users) > 0:
                return effective_users
        except Exception as e:
            cp.log(f'Error reading iperf3 user servers: {e}')

        # Fall back to bundled JSON file
        servers = []
        json_path = 'iperf3_working_servers.json'
        try:
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    servers = json.load(f)
        except Exception as e:
            cp.log(f'Error loading iperf3 servers JSON: {e}')
        return servers

    def handle_start(self):
        """Start a speed test."""
        global current_test

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else '{}'
        try:
            params = json.loads(body)
        except json.JSONDecodeError:
            self.send_json({'error': 'Invalid JSON'}, 400)
            return

        engine = params.get('engine', 'netperf')

        if engine == 'iperf3':
            source = str(
                params.get(
                    'server_source'
                ) or 'custom'
            ).strip().lower()

            settings = (
                _load_iperf3_server_settings()
            )

            cache = (
                _load_active_iperf3_server_cache()
            )

            if source == 'public':
                if settings.get(
                    'server_mode'
                ) != 'public':
                    self.send_json({
                        'error':
                            'Public iPerf3 server mode is not active.'
                    }, 409)
                    return

                selected = (
                    _find_public_iperf3_server(
                        params.get(
                            'server_ref',
                            ''
                        ),
                        cache
                    )
                )

                if not selected:
                    self.send_json({
                        'error':
                            'Selected Public iPerf3 server '
                            'is no longer available.'
                    }, 400)
                    return

                params['server'] = (
                    selected['host']
                )

                params['port'] = (
                    '{}-{}'.format(
                        selected[
                            'port_start'
                        ],
                        selected[
                            'port_end'
                        ]
                    )
                    if selected[
                        'port_start'
                    ] != selected[
                        'port_end'
                    ]
                    else str(
                        selected[
                            'port_start'
                        ]
                    )
                )

                params[
                    'server_name'
                ] = selected[
                    'server_name'
                ]

                params[
                    'server_ref'
                ] = selected[
                    'server_ref'
                ]

                params[
                    'region'
                ] = selected[
                    'region'
                ]

                # Held only in RAM during execution.
                params[
                    '_persist_public_region'
                ] = selected[
                    'region'
                ]

            elif source == 'user':
                if settings.get(
                    'server_mode'
                ) != 'user':
                    self.send_json({
                        'error':
                            'User Server List mode is not active.'
                    }, 409)
                    return

                selected = (
                    _find_user_iperf3_server(
                        params.get(
                            'server_ref',
                            ''
                        ),
                        cache
                    )
                )

                if not selected:
                    self.send_json({
                        'error':
                            'Selected User iPerf3 server '
                            'is no longer available.'
                    }, 400)
                    return

                params['server'] = (
                    selected.get(
                        'server',
                        ''
                    )
                )

                params['port'] = (
                    selected.get(
                        'port',
                        '5201'
                    )
                )

                params[
                    'server_name'
                ] = (
                    selected.get(
                        'server_name'
                    )
                    or selected.get(
                        'server',
                        ''
                    )
                )

            elif source != 'custom':
                self.send_json({
                    'error':
                        'Invalid iPerf3 server source.'
                }, 400)
                return

        if engine == 'ookla' and not has_ookla():
            self.send_json({'error': 'Ookla binary not found'}, 400)
            return
        defect = _evaluate_known_defect(
            engine,
            params.get(
                'interface',
                ''
            )
        )

        if defect.get('blocked'):
            self.send_json({
                'error': defect.get(
                    'message',
                    'This test engine is disabled for the selected interface.'
                )
            }, 400)
            return

        if not _reserve_test_slot(engine):
            self.send_json({'error': 'Test already running'}, 409)
            return

        thread = Thread(target=run_test_thread, args=(engine, params), daemon=True)
        try:
            thread.start()
        except Exception as e:
            _release_test_slot()
            cp.log(f'Failed to start manual test thread: {e}')
            self.send_json({'error': 'Failed to start test'}, 500)
            return

        self.send_json({'status': 'started', 'engine': engine})

    def handle_stop(self):

        """Stop a running test."""

        global current_test, _active_iperf3_process

        with test_lock:

            current_test['running'] = False

        # iPerf3 is a local subprocess and is not controlled by the
        # NCOS control/netperf/stop endpoint.
        with _iperf3_process_lock:

            proc = _active_iperf3_process

            if (
                proc is not None
                and proc.poll() is None
            ):
                try:
                    proc.terminate()
                    cp.log(
                        'Stop requested: terminating active iPerf3 process'
                    )
                except Exception as error:
                    cp.log(
                        'Unable to terminate active iPerf3 process: {}'.format(
                            error
                        )
                    )

        # Preserve the existing NCOS Netperf cancellation path.
        cp.stop_speed_test()

        self.send_json({'status': 'stopped'})

    def handle_clear_history(self):
        """Clear test history and all local recovery copies."""
        if not clear_history_storage():
            self.send_json(
                {'error': 'Unable to clear history'},
                500
            )
            return

        self.send_json({'status': 'cleared'})

    def handle_delete_history_entry(self):
        """Delete a single history entry by index."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else '{}'

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_json({'error': 'Invalid JSON'}, 400)
            return

        idx = data.get('index')

        if not isinstance(idx, int):
            self.send_json(
                {'error': 'index must be an integer'},
                400
            )
            return

        with history_lock:
            history = _load_history_for_update()

            if history is None:
                self.send_json(
                    {'error': 'History is unavailable'},
                    500
                )
                return

            if idx < 0 or idx >= len(history):
                self.send_json(
                    {'error': 'index out of range'},
                    400
                )
                return

            history.pop(idx)

            if not save_history(history):
                self.send_json(
                    {'error': 'Unable to save history'},
                    500
                )
                return

        self.send_json({
            'status': 'deleted',
            'history': history
        })

    def get_netperf_servers(self):
        """Return EFFECTIVE Netperf servers from the two-layer manager.

        Legacy App Data is never a fallback once a canonical key exists (§16).
        """
        effective_netperf = config_mgr.active_section('netperf_servers')
        if isinstance(effective_netperf, list):
            return effective_netperf
        return []


    def get_all_servers(self):
        """Get all saved servers (netperf and iperf3) from appdata."""
        result = {'netperf': [], 'iperf3': []}
        # Netperf servers (canonical RAM once adopted; legacy on Day-1).
        result['netperf'] = self.get_netperf_servers()
        # iPerf3 servers
        result['iperf3'] = self.get_iperf3_servers()
        return result

    def _read_json_request(self, max_bytes=1048576):
        """Read one JSON request body with a hard size limit."""
        try:
            content_length = int(
                self.headers.get('Content-Length', 0)
            )
        except Exception:
            content_length = 0

        if content_length > max_bytes:
            raise ValueError(
                'Request is too large. Maximum size is 1 MB.'
            )

        body = (
            self.rfile.read(content_length).decode('utf-8')
            if content_length
            else '{}'
        )

        try:
            return json.loads(body)
        except json.JSONDecodeError:
            raise ValueError('Invalid JSON')


    def handle_reset_iperf3_reliability(self):
        """Reset active-mode iPerf3 reliability statistics."""
        with test_lock:
            if current_test.get(
                'running'
            ):
                self.send_json({
                    'error':
                        'Reliability statistics cannot be reset '
                        'while a test is running.'
                }, 409)

                return

        try:
            data = self._read_json_request()

        except Exception as exc:
            self.send_json({
                'error':
                    str(
                        exc
                    )
            }, 400)

            return

        if not bool(
            data.get(
                'confirm_reset',
                False
            )
        ):
            self.send_json({
                'error':
                    'Reset Reliability Statistics requires '
                    'explicit confirmation.',
                'reset_confirmation_required':
                    True
            }, 409)

            return

        if not _reset_active_iperf3_reliability():
            self.send_json({
                'error':
                    'Statistics were cleared in memory but '
                    'could not be persisted. Retry the reset.'
            }, 500)

            return

        self.send_json(
            _get_iperf3_reliability_state()
        )


    def handle_user_iperf3_save(self):
        """Add one canonical User iPerf3 endpoint."""
        mode_error = _require_user_iperf3_mode()

        if mode_error:
            self.send_json(mode_error, 409)
            return

        try:
            data = self._read_json_request()
            entry = data.get('server') or {}

            normalized = _validate_external_user_iperf3_entry(
                entry
            )

            servers = _read_user_iperf3_servers_for_edit()

        except Exception as e:
            self.send_json({'error': str(e)}, 400)
            return

        new_ref = _user_iperf3_server_ref(
            normalized['server'],
            normalized['port']
        )

        # /user/save is Add-only. Endpoint identity is the normalized
        # Hostname/IP + Port/Range reference. Existing endpoints must be
        # changed through the explicit Edit workflow.
        for server in servers:
            if not isinstance(server, dict):
                continue
            try:
                existing_ref = _user_iperf3_server_ref(
                    server.get('server', ''),
                    server.get('port', '5201')
                )
            except Exception:
                continue

            if existing_ref == new_ref:
                self.send_json({
                    'error': (
                        'This User iPerf3 endpoint already exists. '
                        'Use Edit to change its Friendly Name or '
                        'other settings.'
                    ),
                    'duplicate': True,
                    'server_ref': new_ref
                }, 409)
                return

        final_servers = [
            server
            for server in servers
            if isinstance(server, dict)
        ]
        final_servers.append(normalized)

        guard = _guard_user_server_list_change(
            final_servers,
            bool(data.get('confirm_schedule_reset', False))
        )

        # Persist through the canonical Configuration Manager (no legacy
        # write). If the change also requires a schedule reset, both are
        # persisted as ONE transaction. Refresh the active User cache only
        # after a successful local save.
        result = respond_user_iperf3_list_apply(
            self, final_servers, guard,
            success_payload={
                'status': 'saved',
                'server_ref': new_ref,
                'total': len(final_servers),
            })
        if result and result.action == 'saved':
            _sync_active_user_iperf3_cache(final_servers)


    def handle_user_iperf3_edit(self):

        """Edit one User iPerf3 endpoint by its original hidden reference."""

        mode_error = _require_user_iperf3_mode()

        if mode_error:
            self.send_json(mode_error, 409)
            return

        try:
            data = self._read_json_request()

            original_ref = str(
                data.get('server_ref') or ''
            ).strip()

            if not original_ref:
                raise ValueError(
                    'server_ref is required'
                )

            entry = data.get('server') or {}

            normalized = _validate_external_user_iperf3_entry(
                entry
            )

            servers = _read_user_iperf3_servers_for_edit()

        except Exception as error:
            self.send_json({
                'error': str(error)
            }, 400)
            return

        new_ref = _user_iperf3_server_ref(
            normalized['server'],
            normalized['port']
        )

        original_index = None

        for index, server in enumerate(servers):

            if not isinstance(server, dict):
                continue

            try:
                existing_ref = _user_iperf3_server_ref(
                    server.get('server', ''),
                    server.get('port', '5201')
                )
            except Exception:
                continue

            if existing_ref == original_ref:
                original_index = index
                break

        if original_index is None:
            self.send_json({
                'error': (
                    'The User iPerf3 server being edited '
                    'no longer exists.'
                )
            }, 404)
            return

        # If endpoint identity changes, it must not collide with
        # any other saved User server.
        if new_ref != original_ref:

            for index, server in enumerate(servers):

                if index == original_index:
                    continue

                if not isinstance(server, dict):
                    continue

                try:
                    existing_ref = _user_iperf3_server_ref(
                        server.get('server', ''),
                        server.get('port', '5201')
                    )
                except Exception:
                    continue

                if existing_ref == new_ref:
                    self.send_json({
                        'error': (
                            'Another User iPerf3 server already '
                            'uses this Hostname/IP and Port/Range.'
                        ),
                        'duplicate': True,
                        'server_ref': new_ref
                    }, 409)
                    return

        final_servers = [
            dict(server)
            if isinstance(server, dict)
            else server
            for server in servers
        ]

        final_servers[original_index] = normalized

        guard = _guard_user_server_list_change(
            final_servers,
            bool(
                data.get(
                    'confirm_schedule_reset',
                    False
                )
            )
        )

        result = respond_user_iperf3_list_apply(
            self, final_servers, guard,
            success_payload={
                'status': 'edited',
                'server_ref': new_ref,
                'previous_server_ref': original_ref,
                'endpoint_changed': (new_ref != original_ref),
                'total': len(final_servers),
            })
        if result and result.action == 'saved':
            _sync_active_user_iperf3_cache(final_servers)


    def handle_user_iperf3_delete(self):
        """Delete one User endpoint by hidden deterministic reference."""
        mode_error = _require_user_iperf3_mode()

        if mode_error:
            self.send_json(mode_error, 409)
            return

        try:
            data = self._read_json_request()
            server_ref = str(
                data.get('server_ref') or ''
            ).strip()

            if not server_ref:
                raise ValueError('server_ref is required')

            servers = _read_user_iperf3_servers_for_edit()

        except Exception as e:
            self.send_json({'error': str(e)}, 400)
            return

        final_servers = []

        for server in servers:
            remove = False

            if isinstance(server, dict):
                try:
                    remove = (
                        _user_iperf3_server_ref(
                            server.get('server', ''),
                            server.get('port', '5201')
                        )
                        == server_ref
                    )
                except Exception:
                    remove = False

            if not remove:
                final_servers.append(server)

        guard = _guard_user_server_list_change(
            final_servers,
            bool(data.get('confirm_schedule_reset', False))
        )

        result = respond_user_iperf3_list_apply(
            self, final_servers, guard,
            success_payload={
                'status': 'deleted',
                'total': len(final_servers),
            })
        if result and result.action == 'saved':
            _sync_active_user_iperf3_cache(final_servers)


    def handle_user_iperf3_delete_all(self):
        """Clear the complete User Server List."""
        mode_error = _require_user_iperf3_mode()

        if mode_error:
            self.send_json(mode_error, 409)
            return

        try:
            data = self._read_json_request()
        except Exception as e:
            self.send_json({'error': str(e)}, 400)
            return

        if not bool(data.get('confirm_delete_all', False)):
            self.send_json({
                'error':
                    'Delete All requires explicit confirmation.',
                'delete_all_confirmation_required': True
            }, 409)
            return

        guard = _guard_user_server_list_change(
            [],
            bool(data.get('confirm_schedule_reset', False))
        )

        result = respond_user_iperf3_list_apply(
            self, [], guard,
            success_payload={
                'status': 'deleted_all',
                'total': 0,
            })
        if result and result.action == 'saved':
            _sync_active_user_iperf3_cache([])


    def handle_user_iperf3_import(self):
        """Transactionally import canonical schema-version-1 JSON."""
        mode_error = _require_user_iperf3_mode()

        if mode_error:
            self.send_json(mode_error, 409)
            return

        try:
            data = self._read_json_request()

            catalog = data.get('catalog')

            catalog = (
                _normalize_legacy_user_iperf3_import_catalog(
                    catalog
                )
            )

            if not isinstance(catalog, dict):
                raise ValueError(
                    'Expected a JSON object named catalog'
                )

            if set(catalog) != {'schema_version', 'servers'}:
                raise ValueError(
                    'Top level must contain only '
                    'schema_version and servers'
                )

            if catalog.get('schema_version') != 1:
                raise ValueError(
                    'schema_version must be 1'
                )

            incoming = catalog.get('servers')

            if not isinstance(incoming, list):
                raise ValueError(
                    'servers must be a JSON array'
                )

            if not incoming:
                raise ValueError(
                    'Server list is empty'
                )

            if len(incoming) > 500:
                raise ValueError(
                    'Maximum 500 server entries'
                )

            normalized = []
            incoming_refs = set()
            duplicate_count = 0

            for number, entry in enumerate(incoming, start=1):
                try:
                    server = _validate_external_user_iperf3_entry(
                        entry
                    )

                    ref = _user_iperf3_server_ref(
                        server['server'],
                        server['port']
                    )
                except Exception as e:
                    raise ValueError(
                        'Server entry {}: {}'.format(number, e)
                    )

                if ref in incoming_refs:
                    duplicate_count += 1
                    continue

                incoming_refs.add(ref)
                normalized.append(server)

            existing = _read_user_iperf3_servers_for_edit()

        except Exception as e:
            self.send_json({'error': str(e)}, 400)
            return

        mode = str(
            data.get('mode') or ''
        ).strip().lower()

        # Empty current list imports directly.
        if not existing:
            mode = 'replace'

        elif mode not in ('merge', 'replace'):
            self.send_json({
                'error':
                    'Choose Merge Lists or Replace List before importing.'
            }, 400)
            return

        if (
            existing
            and mode == 'replace'
            and not bool(data.get('confirm_replace', False))
        ):
            self.send_json({
                'error':
                    'Replacing the User Server List will delete '
                    'the existing list.',
                'replace_confirmation_required': True
            }, 409)
            return

        if mode == 'merge':
            final_servers = [
                dict(server)
                for server in existing
                if isinstance(server, dict)
            ]

            refs = set()

            for server in final_servers:
                try:
                    refs.add(
                        _user_iperf3_server_ref(
                            server.get('server', ''),
                            server.get('port', '5201')
                        )
                    )
                except Exception:
                    pass

            added = 0

            for server in normalized:
                ref = _user_iperf3_server_ref(
                    server['server'],
                    server['port']
                )

                if ref in refs:
                    duplicate_count += 1
                    continue

                final_servers.append(server)
                refs.add(ref)
                added += 1

        else:
            final_servers = normalized
            added = len(normalized)

        guard = _guard_user_server_list_change(
            final_servers,
            bool(data.get('confirm_schedule_reset', False))
        )

        result = respond_user_iperf3_list_apply(
            self, final_servers, guard,
            success_payload={
                'status': 'imported',
                'mode': mode,
                'added': added,
                'duplicates_skipped': duplicate_count,
                'total': len(final_servers),
            })
        if result and result.action == 'saved':
            _sync_active_user_iperf3_cache(final_servers)


    def handle_save_server(self):
        """Save a server and synchronize the active User cache."""
        content_length = int(
            self.headers.get(
                'Content-Length',
                0
            )
        )

        body = (
            self.rfile.read(
                content_length
            ).decode('utf-8')
            if content_length
            else '{}'
        )

        try:
            data = json.loads(body)

        except json.JSONDecodeError:
            self.send_json({
                'error': 'Invalid JSON'
            }, 400)
            return

        engine = data.get(
            'engine',
            ''
        )

        server_entry = data.get(
            'server',
            {}
        )

        confirm_schedule_reset = bool(
            data.get(
                'confirm_schedule_reset',
                False
            )
        )

        if not engine or not server_entry:
            self.send_json({
                'error':
                    'Missing engine or server'
            }, 400)
            return

        if engine == 'iperf3':
            settings = (
                _load_iperf3_server_settings()
            )

            if settings.get(
                'server_mode'
            ) != 'user':
                self.send_json({
                    'error':
                        'Switch to User Server List mode '
                        'before modifying User iPerf3 servers.'
                }, 409)
                return

            try:
                start_port, end_port = (
                    _parse_iperf3_port_range(
                        server_entry.get(
                            'port',
                            ''
                        )
                    )
                )

                normalized = (
                    _normalize_user_iperf3_server(
                        server_entry.get(
                            'server_name'
                        ),
                        server_entry.get(
                            'server'
                        ),
                        start_port,
                        end_port,
                        server_entry.get(
                            'city'
                        ),
                        server_entry.get(
                            'country'
                        )
                    )
                )

                servers = (
                    _read_user_iperf3_servers_for_edit()
                )

            except Exception as e:
                self.send_json({
                    'error': str(e)
                }, 400)
                return

            new_ref = (
                _user_iperf3_server_ref(
                    normalized['server'],
                    normalized['port']
                )
            )

            final_servers = []
            replaced = False

            for server in servers:
                if not isinstance(
                    server,
                    dict
                ):
                    continue

                try:
                    existing_ref = (
                        _user_iperf3_server_ref(
                            server.get(
                                'server',
                                ''
                            ),
                            server.get(
                                'port',
                                '5201'
                            )
                        )
                    )

                except Exception:
                    existing_ref = ''

                if existing_ref == new_ref:
                    if not replaced:
                        final_servers.append(
                            normalized
                        )
                        replaced = True

                else:
                    final_servers.append(
                        server
                    )

            if not replaced:
                final_servers.append(
                    normalized
                )

            guard = (
                _guard_user_server_list_change(
                    final_servers,
                    confirm_schedule_reset
                )
            )

            result = respond_user_iperf3_list_apply(
                self, final_servers, guard,
                success_payload={
                    'status': 'saved',
                    'servers': final_servers,
                })
            if result and result.action == 'saved':
                _sync_active_user_iperf3_cache(final_servers)
            return

        # Netperf: read current list (canonical RAM once adopted), append,
        # persist through the Configuration Manager (no legacy write).
        servers = self.get_netperf_servers()

        server_host = server_entry.get(
            'server',
            ''
        )

        servers = [
            server
            for server in servers
            if server.get(
                'server'
            ) != server_host
        ]

        servers.append(
            server_entry
        )

        respond_config_apply_on(
            self, 'netperf_servers', servers,
            success_payload={
                'status': 'saved',
                'servers': servers,
            })

    def handle_delete_server(self):
        """Delete one server and protect dependent User schedules."""
        content_length = int(
            self.headers.get(
                'Content-Length',
                0
            )
        )

        body = (
            self.rfile.read(
                content_length
            ).decode('utf-8')
            if content_length
            else '{}'
        )

        try:
            data = json.loads(body)

        except json.JSONDecodeError:
            self.send_json({
                'error': 'Invalid JSON'
            }, 400)
            return

        engine = data.get(
            'engine',
            ''
        )

        server_host = str(
            data.get(
                'server',
                ''
            )
        ).strip()

        server_ref = str(
            data.get(
                'server_ref',
                ''
            )
        ).strip()

        confirm_schedule_reset = bool(
            data.get(
                'confirm_schedule_reset',
                False
            )
        )

        if engine == 'iperf3':
            settings = (
                _load_iperf3_server_settings()
            )

            if settings.get(
                'server_mode'
            ) != 'user':
                self.send_json({
                    'error':
                        'Switch to User Server List mode '
                        'before modifying User iPerf3 servers.'
                }, 409)
                return

            if not server_ref and not server_host:
                self.send_json({
                    'error':
                        'Missing server reference'
                }, 400)
                return

            try:
                servers = (
                    _read_user_iperf3_servers_for_edit()
                )

            except Exception as e:
                self.send_json({
                    'error':
                        f'Unable to read User Server List: {e}'
                }, 500)
                return

            final_servers = []

            for server in servers:
                if not isinstance(
                    server,
                    dict
                ):
                    continue

                remove = False

                if server_ref:
                    try:
                        remove = (
                            _user_iperf3_server_ref(
                                server.get(
                                    'server',
                                    ''
                                ),
                                server.get(
                                    'port',
                                    '5201'
                                )
                            )
                            == server_ref
                        )

                    except Exception:
                        remove = False

                else:
                    # Legacy UI compatibility until the frontend
                    # moves fully to hidden references.
                    remove = (
                        server.get(
                            'server'
                        )
                        == server_host
                    )

                if not remove:
                    final_servers.append(
                        server
                    )

            guard = (
                _guard_user_server_list_change(
                    final_servers,
                    confirm_schedule_reset
                )
            )

            result = respond_user_iperf3_list_apply(
                self, final_servers, guard,
                success_payload={
                    'status': 'deleted',
                    'servers': final_servers,
                })
            if result and result.action == 'saved':
                _sync_active_user_iperf3_cache(final_servers)
            return

        if not engine or not server_host:
            self.send_json({
                'error':
                    'Missing engine or server'
            }, 400)
            return

        # Netperf: read current list (canonical RAM once adopted), remove the
        # host, persist through the Configuration Manager (no legacy write).
        servers = self.get_netperf_servers()

        servers = [
            server
            for server in servers
            if server.get(
                'server'
            ) != server_host
        ]

        respond_config_apply_on(
            self, 'netperf_servers', servers,
            success_payload={
                'status': 'deleted',
                'servers': servers,
            })

    def handle_delete_all_servers(self):
        """Clear the complete User iPerf3 Server List safely."""
        content_length = int(
            self.headers.get(
                'Content-Length',
                0
            )
        )

        body = (
            self.rfile.read(
                content_length
            ).decode('utf-8')
            if content_length
            else '{}'
        )

        try:
            data = json.loads(body)

        except json.JSONDecodeError:
            self.send_json({
                'error': 'Invalid JSON'
            }, 400)
            return

        if data.get(
            'engine'
        ) != 'iperf3':
            self.send_json({
                'error':
                    'Delete All is available only '
                    'for User iPerf3 servers.'
            }, 400)
            return

        settings = (
            _load_iperf3_server_settings()
        )

        if settings.get(
            'server_mode'
        ) != 'user':
            self.send_json({
                'error':
                    'Switch to User Server List mode '
                    'before deleting User iPerf3 servers.'
            }, 409)
            return

        if not bool(
            data.get(
                'confirm_delete_all',
                False
            )
        ):
            self.send_json({
                'error':
                    'Delete All requires explicit confirmation.',
                'delete_all_confirmation_required':
                    True
            }, 409)
            return

        guard = (
            _guard_user_server_list_change(
                [],
                bool(
                    data.get(
                        'confirm_schedule_reset',
                        False
                    )
                )
            )
        )

        # Clear the User iPerf3 list through the canonical Configuration
        # Manager (no legacy write), folding any required schedule reset into
        # the same transaction.
        result = respond_user_iperf3_list_apply(
            self, [], guard,
            success_payload={
                'status': 'deleted_all',
                'servers': [],
            })
        if result and result.action == 'saved':
            _sync_active_user_iperf3_cache([])


    def handle_import_servers(self):
        """Import Netperf or canonical User iPerf3 server data."""
        content_length = int(
            self.headers.get(
                'Content-Length',
                0
            )
        )

        if content_length > 1048576:
            self.send_json({
                'error':
                    'File too large. Maximum size is 1 MB.'
            }, 400)
            return

        body = (
            self.rfile.read(
                content_length
            ).decode('utf-8')
            if content_length
            else '{}'
        )

        try:
            data = json.loads(body)

        except json.JSONDecodeError:
            self.send_json({
                'error':
                    'Invalid JSON in request body.'
            }, 400)
            return

        engine = data.get(
            'engine',
            ''
        )

        if engine not in (
            'netperf',
            'iperf3'
        ):
            self.send_json({
                'error':
                    'Invalid engine type.'
            }, 400)
            return

        # -------------------------------------------------------------
        # User iPerf3 canonical import
        # -------------------------------------------------------------
        if engine == 'iperf3':
            settings = (
                _load_iperf3_server_settings()
            )

            if settings.get(
                'server_mode'
            ) != 'user':
                self.send_json({
                    'error':
                        'Switch to User Server List mode '
                        'before importing User iPerf3 servers.'
                }, 409)
                return

            catalog = data.get(
                'catalog'
            )

            if not isinstance(
                catalog,
                dict
            ):
                self.send_json({
                    'error':
                        'File format unrecognized. '
                        'Expected a JSON object.'
                }, 400)
                return

            if catalog.get(
                'schema_version'
            ) != 1:
                self.send_json({
                    'error':
                        'Unsupported or missing schema_version. '
                        'Expected schema_version 1.'
                }, 400)
                return

            if set(catalog) != {
                'schema_version',
                'servers'
            }:
                self.send_json({
                    'error':
                        'Top-level JSON must contain only '
                        'schema_version and servers.'
                }, 400)
                return

            incoming = catalog.get(
                'servers'
            )

            if not isinstance(
                incoming,
                list
            ):
                self.send_json({
                    'error':
                        'servers must be a JSON array.'
                }, 400)
                return

            if not incoming:
                self.send_json({
                    'error':
                        'File contains no server entries.'
                }, 400)
                return

            if len(incoming) > 500:
                self.send_json({
                    'error':
                        'Too many entries. Maximum is 500.'
                }, 400)
                return

            normalized = []
            incoming_refs = set()
            duplicate_count = 0

            # Transactional validation: one bad entry rejects
            # the entire import before SDK appdata is touched.
            for index, entry in enumerate(
                incoming,
                start=1
            ):
                try:
                    server = (
                        _validate_user_iperf3_external_entry(
                            entry
                        )
                    )

                    ref = (
                        _user_iperf3_server_ref(
                            server['server'],
                            server['port']
                        )
                    )

                except Exception as e:
                    self.send_json({
                        'error':
                            f'Server entry {index}: {e}'
                    }, 400)
                    return

                if ref in incoming_refs:
                    duplicate_count += 1
                    continue

                incoming_refs.add(ref)
                normalized.append(
                    server
                )

            try:
                existing = (
                    _read_user_iperf3_servers_for_edit()
                )

            except Exception as e:
                self.send_json({
                    'error':
                        f'Unable to read User Server List: {e}'
                }, 500)
                return

            mode = str(
                data.get(
                    'mode',
                    ''
                )
            ).strip().lower()

            # Empty list: file loads directly. No Merge/Replace choice.
            if not existing:
                mode = 'replace'

            elif mode not in (
                'merge',
                'replace'
            ):
                self.send_json({
                    'error':
                        'Choose Merge Lists or Replace List '
                        'before importing.'
                }, 400)
                return

            if (
                existing
                and mode == 'replace'
                and not bool(
                    data.get(
                        'confirm_replace',
                        False
                    )
                )
            ):
                self.send_json({
                    'error':
                        'Replacing the User Server List will '
                        'delete the existing list.',
                    'replace_confirmation_required':
                        True
                }, 409)
                return

            if mode == 'merge':
                final_servers = [
                    dict(server)
                    for server in existing
                    if isinstance(
                        server,
                        dict
                    )
                ]

                existing_refs = set()

                for server in final_servers:
                    try:
                        existing_refs.add(
                            _user_iperf3_server_ref(
                                server.get(
                                    'server',
                                    ''
                                ),
                                server.get(
                                    'port',
                                    '5201'
                                )
                            )
                        )
                    except Exception:
                        pass

                added = 0

                for server in normalized:
                    ref = (
                        _user_iperf3_server_ref(
                            server['server'],
                            server['port']
                        )
                    )

                    if ref in existing_refs:
                        duplicate_count += 1
                        continue

                    final_servers.append(
                        server
                    )

                    existing_refs.add(
                        ref
                    )

                    added += 1

            else:
                final_servers = normalized
                added = len(
                    normalized
                )

            guard = (
                _guard_user_server_list_change(
                    final_servers,
                    bool(
                        data.get(
                            'confirm_schedule_reset',
                            False
                        )
                    )
                )
            )

            result = respond_user_iperf3_list_apply(
                self, final_servers, guard,
                success_payload={
                    'status': 'imported',
                    'mode': mode,
                    'added': added,
                    'duplicates_skipped': duplicate_count,
                    'total': len(final_servers),
                })
            if result and result.action == 'saved':
                _sync_active_user_iperf3_cache(final_servers)
            return

        # -------------------------------------------------------------
        # Netperf import behavior (routed through Configuration Manager)
        # -------------------------------------------------------------
        mode = data.get(
            'mode',
            'replace'
        )

        servers_data = data.get(
            'servers'
        )

        if not isinstance(
            servers_data,
            list
        ):
            self.send_json({
                'error':
                    'File format unrecognized. '
                    'Expected a JSON array.'
            }, 400)
            return

        if len(servers_data) == 0:
            self.send_json({
                'error':
                    'File contains no server entries.'
            }, 400)
            return

        if len(servers_data) > 500:
            self.send_json({
                'error':
                    'Too many entries. Maximum is 500.'
            }, 400)
            return

        valid_entries = []
        skipped = 0

        for entry in servers_data:
            if not isinstance(
                entry,
                dict
            ):
                skipped += 1
                continue

            server_val = entry.get(
                'server',
                ''
            )

            if not isinstance(
                server_val,
                str
            ):
                skipped += 1
                continue

            server_val = (
                server_val.strip()
            )

            if (
                not server_val
                or len(server_val) > 253
            ):
                skipped += 1
                continue

            filtered = {}

            for key in (
                'server',
                'label'
            ):
                value = entry.get(
                    key
                )

                if value is not None:
                    filtered[key] = str(
                        value
                    ).strip()

            filtered[
                'server'
            ] = server_val

            valid_entries.append(
                filtered
            )

        if not valid_entries:
            self.send_json({
                'error':
                    'No valid servers found in the file.'
            }, 400)
            return

        if mode == 'merge':
            try:
                existing = self.get_netperf_servers()

            except Exception:
                existing = []

            existing_map = {
                server.get('server'):
                    server
                for server in existing
                if isinstance(
                    server,
                    dict
                )
            }

            for entry in valid_entries:
                existing_map[
                    entry['server']
                ] = entry

            final_servers = list(
                existing_map.values()
            )

        else:
            final_servers = (
                valid_entries
            )

        respond_config_apply_on(
            self, 'netperf_servers', final_servers,
            success_payload={
                'status': 'imported',
                'imported': len(valid_entries),
                'skipped': skipped,
                'total': len(final_servers),
            })

    def get_cell_diagnostics(self):
        """Return raw modem diagnostics for every cellular WAN device.

        Diagnostic aid: carrier-aggregation key names are undocumented and
        vary by modem, so this exposes exactly what this router reports.
        """
        result = {}
        try:
            devices = cp.get('status/wan/devices')
            if not devices or not isinstance(devices, dict):
                return result
            for uid, dev in devices.items():
                if not isinstance(dev, dict):
                    continue
                info = dev.get('info', {})
                if not (uid.startswith('mdm-') or info.get('type') == 'mdm'):
                    continue
                diagnostics = dev.get('diagnostics', {}) or {}
                cells, unmatched = _parse_aggregation_cells(diagnostics)
                result[uid] = {
                    'iface': info.get('iface', ''),
                    'diagnostics': diagnostics,
                    'diagnostic_keys': sorted(diagnostics.keys()),
                    'parsed_aggregation': cells,
                    'aggregation_unmatched': unmatched,
                }
        except Exception as e:
            cp.log(f'Error reading cell diagnostics: {e}')
        return result

    def get_live_carrier_telemetry(self):
        """Return the collector's latest cached carrier snapshot.

        The background collector is responsible for polling NCOS every
        two seconds. The web UI reads that cached state so browser polling
        does not create a second stream of modem diagnostic API requests.
        """
        global _active_carrier_collector

        collector = _active_carrier_collector
        if not collector or not collector.baseline:
            return {'active': False}

        try:
            with collector._lock:
                current = (
                    dict(collector._last_snapshot)
                    if collector._last_snapshot
                    else dict(collector.baseline)
                )
                peak = (
                    dict(collector.peak)
                    if collector.peak
                    else {}
                )

            return {
                'active': True,
                'service_mode': current.get('service_mode', ''),
                'carrier_count': current.get('carrier_count', 0),
                'bands': current.get('bands', ''),
                'bandwidth_mhz': current.get('bandwidth_mhz', 0),
                'zero_mhz_count': current.get('zero_mhz_count', 0),
                'peak_carrier_count': peak.get('carrier_count', 0),
                'peak_bandwidth_mhz': peak.get('bandwidth_mhz', 0),
            }

        except Exception as e:
            cp.log(
                f'Carrier telemetry live read error (non-fatal): {e}'
            )
            return {'active': False}

    def get_netperf_probe(self):
        """Probe what control/netperf accepts and whether Ookla is reachable.

        Two open questions this answers:
        1. Does control/netperf support a bind-address option (which would
           map to netperf's -L flag) in addition to ifc_wan? If so, we can
           force the source interface the way iPerf3 does with -B.
        2. Is the system Ookla binary (used by the NCM speed test) present
           and executable from an SDK app's sandbox?
        """
        probe = {}

        # 1. DTD for control/netperf — lists every accepted field and type.
        # Runs over the SDK socket, so no auth needed.
        for path in ('dtd/control/netperf',
                     'dtd/control/netperf/input',
                     'dtd/control/netperf/input/options'):
            try:
                probe[path] = cp.get(path)
            except Exception as e:
                probe[path] = f'error: {e}'

        # Current live state of the control tree for comparison
        for path in ('control/netperf', 'control/netperf/output',
                     'status/system/netperf'):
            try:
                probe[path] = cp.get(path)
            except Exception as e:
                probe[path] = f'error: {e}'

        # 2. Ookla binary probe. NCOS launches './ookla' from its own cwd,
        # so check the usual system locations. Detection only — nothing is
        # executed, and note the SDK license restriction before using it.
        ookla_paths = [
            'ookla', './ookla',
            '/usr/bin/ookla', '/usr/sbin/ookla', '/bin/ookla',
            '/sbin/ookla', '/opt/ookla', '/opt/bin/ookla',
            '/usr/local/bin/ookla',
            '/var/ookla', '/tmp/ookla',
            '/usr/bin/speedtest', '/usr/sbin/speedtest',
        ]
        found = {}
        for path in ookla_paths:
            try:
                exists = os.path.exists(path)
                entry = {'exists': exists}
                if exists:
                    entry['executable'] = os.access(path, os.X_OK)
                    entry['is_file'] = os.path.isfile(path)
                    try:
                        entry['size'] = os.path.getsize(path)
                    except Exception:
                        pass
                found[path] = entry
            except Exception as e:
                found[path] = {'error': str(e)}
        probe['ookla_paths'] = found

        # Where are we actually running from?
        try:
            probe['cwd'] = os.getcwd()
            probe['cwd_listing'] = sorted(os.listdir('.'))[:50]
        except Exception as e:
            probe['cwd'] = f'error: {e}'

        # Netperf binary location (the log showed /usr/bin/netperf)
        netperf_paths = ['/usr/bin/netperf', '/usr/sbin/netperf',
                         '/bin/netperf', 'netperf']
        np_found = {}
        for path in netperf_paths:
            try:
                np_found[path] = {
                    'exists': os.path.exists(path),
                    'executable': (os.access(path, os.X_OK)
                                   if os.path.exists(path) else False),
                }
            except Exception as e:
                np_found[path] = {'error': str(e)}
        probe['netperf_paths'] = np_found

        return probe

    def get_saved_reports(self):
        """Get saved reports from file."""
        try:
            if os.path.exists('tmp/saved_reports.json'):
                with open('tmp/saved_reports.json', 'r') as f:
                    return json.load(f)
        except Exception as e:
            cp.log(f'Error loading reports: {e}')
        return []

    def handle_save_report(self):
        """Save a named report (snapshot of current history stats)."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else '{}'
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_json({'error': 'Invalid JSON'}, 400)
            return
        name = data.get('name', '').strip()
        if not name:
            self.send_json({'error': 'Report name required'}, 400)
            return
        report = data.get('report', {})
        report['name'] = name
        report['saved_at'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

        reports = self.get_saved_reports()
        reports.append(report)
        os.makedirs('tmp', exist_ok=True)
        with open('tmp/saved_reports.json', 'w') as f:
            json.dump(reports, f)
        self.send_json({'status': 'saved'})

    def handle_delete_report(self):
        """Delete a saved report by index."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else '{}'
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_json({'error': 'Invalid JSON'}, 400)
            return
        idx = data.get('index', -1)
        reports = self.get_saved_reports()
        if 0 <= idx < len(reports):
            reports.pop(idx)
            os.makedirs('tmp', exist_ok=True)
            with open('tmp/saved_reports.json', 'w') as f:
                json.dump(reports, f)
        self.send_json({'status': 'deleted', 'reports': reports})

    def handle_save_schedule(self):
        """Save or update the test schedule."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else '{}'
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_json({'error': 'Invalid JSON'}, 400)
            return
        schedule_engine = data.get(
            'engine',
            'netperf'
        )
        schedule_params = data.get(
            'params',
            {}
        )

        if schedule_engine == 'iperf3':
            settings = (
                _load_iperf3_server_settings()
            )

            cache = (
                _load_active_iperf3_server_cache()
            )

            mode = settings.get(
                'server_mode',
                'public'
            )

            source = str(
                schedule_params.get(
                    'server_source'
                ) or mode
            ).strip().lower()

            if source != mode:
                self.send_json({
                    'error':
                        'Scheduled iPerf3 server source does not '
                        'match the active server mode.'
                }, 409)
                return

            if mode == 'public':
                selected = (
                    _find_public_iperf3_server(
                        schedule_params.get(
                            'server_ref',
                            ''
                        ),
                        cache
                    )
                )

                if not selected:
                    self.send_json({
                        'error':
                            'Select a valid Public iPerf3 server '
                            'before saving the schedule.'
                    }, 400)
                    return

                schedule_params[
                    'server_source'
                ] = 'public'

                schedule_params[
                    'server_ref'
                ] = selected[
                    'server_ref'
                ]

                schedule_params[
                    'server_name'
                ] = selected[
                    'server_name'
                ]

                schedule_params[
                    'region'
                ] = selected[
                    'region'
                ]

                schedule_params[
                    'server'
                ] = selected[
                    'host'
                ]

                schedule_params[
                    'port'
                ] = (
                    '{}-{}'.format(
                        selected[
                            'port_start'
                        ],
                        selected[
                            'port_end'
                        ]
                    )
                    if selected[
                        'port_start'
                    ] != selected[
                        'port_end'
                    ]
                    else str(
                        selected[
                            'port_start'
                        ]
                    )
                )

            else:
                selected = (
                    _find_user_iperf3_server(
                        schedule_params.get(
                            'server_ref',
                            ''
                        ),
                        cache
                    )
                )

                if not selected:
                    self.send_json({
                        'error':
                            'Select a valid User iPerf3 server '
                            'before saving the schedule.'
                    }, 400)
                    return

                schedule_params[
                    'server_source'
                ] = 'user'

                schedule_params[
                    'server_ref'
                ] = (
                    _user_iperf3_server_ref(
                        selected.get(
                            'server',
                            ''
                        ),
                        selected.get(
                            'port',
                            '5201'
                        )
                    )
                )

                schedule_params[
                    'server_name'
                ] = (
                    selected.get(
                        'server_name'
                    )
                    or selected.get(
                        'server',
                        ''
                    )
                )

                schedule_params[
                    'server'
                ] = selected.get(
                    'server',
                    ''
                )

                schedule_params[
                    'port'
                ] = selected.get(
                    'port',
                    '5201'
                )


        if bool(
            data.get(
                'enabled',
                False
            )
        ):
            defect = _evaluate_known_defect(
                schedule_engine,
                schedule_params.get(
                    'interface',
                    ''
                )
            )

            if defect.get('blocked'):
                self.send_json({
                    'error': defect.get(
                        'message',
                        'This test engine is disabled for the selected interface.'
                    )
                }, 400)
                return

        config = {
            'enabled': bool(data.get('enabled', False)),
            'autostart': bool(data.get('autostart', False)),
            'cron': data.get('cron', ''),
            'engine': schedule_engine,
            'params': schedule_params
        }

        # Persist through the canonical Configuration Manager. All schedule
        # feature validation above has already passed; the manager handles
        # mutation gating, revision reconciliation, and read-back writes.
        apply_result = self._respond_config_apply(
            'schedule', config,
            success_payload={
                'status': ('enabled' if config['enabled'] else 'disabled'),
                'schedule': config,
            })

        # Explicit Schedule Save is an APPLY/RUNTIME action: the schedule must
        # run now when enabled=true, INDEPENDENT of autostart. When the save
        # was a persistence NO-OP (e.g. after a restart the persisted schedule
        # is enabled=true/autostart=false so runtime was not running, and the
        # user re-saves the unchanged schedule), the manager does not hot-reload
        # -- so we set the runtime running flag here without forcing any write
        # or device_revision increment. Only on a successful save/no-op-save
        # (never on reconciled/blocked/error).
        if apply_result is not None and apply_result.action == 'saved':
            with schedule_lock:
                schedule_config['running'] = bool(config['enabled'])
                schedule_config['enabled'] = bool(config['enabled'])
                schedule_config['autostart'] = bool(config['autostart'])

    def _respond_config_apply(self, section, value,
                              success_payload=None):
        """Route an ordinary section save through the manager + reply.

        Thin method wrapper around the module-level respond_config_apply_on so
        every Save surface shares one contract. Returns the ConfigApplyResult.
        """
        return respond_config_apply_on(
            self, section, value,
            success_payload or {'status': 'saved'})

    def get_outputs(self):
        """Get EFFECTIVE configured output paths from the two-layer manager.

        Legacy App Data is never a fallback once a canonical key exists (§16);
        the manager's effective config already reflects the correct layer.
        """
        effective_outputs = config_mgr.active_section('outputs')
        if isinstance(effective_outputs, list):
            return {'outputs': effective_outputs}
        return {'outputs': []}

    def handle_save_outputs(self):
        """Save output configuration."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else '{}'
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_json({'error': 'Invalid JSON'}, 400)
            return
        outputs = data.get('outputs', [])
        cp.log(f'Outputs configured: {outputs}')
        self._respond_config_apply(
            'outputs', outputs,
            success_payload={'status': 'saved', 'outputs': outputs})

    def send_json(self, data, code=200):
        """Send a JSON response."""
        body = json.dumps(data).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def serve_file(self, filename, content_type):
        """Serve a file from the app directory."""
        try:
            with open(filename, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404)

    def serve_static(self):
        """Serve static files."""
        path = self.path.lstrip('/')
        if '..' in path:
            self.send_error(403)
            return

        ext_map = {
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.html': 'text/html',
            '.svg': 'image/svg+xml',
            '.png': 'image/png',
            '.ico': 'image/x-icon',
            '.woff': 'font/woff',
            '.woff2': 'font/woff2',
            '.ttf': 'font/ttf'
        }
        ext = os.path.splitext(path)[1].lower()
        content_type = ext_map.get(ext, 'application/octet-stream')

        try:
            with open(path, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404)


# =============================================================================
# MAIN
# =============================================================================

def cron_matches(cron_expr, dt):
    """Check if a datetime matches a cron expression (minute hour dom month dow)."""
    try:
        fields = cron_expr.strip().split()
        if len(fields) != 5:
            return False

        def match_field(field, value, min_val, max_val):
            for part in field.split(','):
                part = part.strip()
                if '/' in part:
                    base, step = part.split('/', 1)
                    step = int(step)
                    start = min_val if base == '*' else int(base.split('-')[0] if '-' in base else base)
                    if value >= start and (value - start) % step == 0:
                        return True
                elif part == '*':
                    return True
                elif '-' in part:
                    a, b = part.split('-', 1)
                    if int(a) <= value <= int(b):
                        return True
                else:
                    if int(part) == value:
                        return True
            return False

        # dow: 0=Sunday in cron, Python weekday: 0=Monday
        cron_dow = (dt.weekday() + 1) % 7
        return (match_field(fields[0], dt.minute, 0, 59) and
                match_field(fields[1], dt.hour, 0, 23) and
                match_field(fields[2], dt.day, 1, 31) and
                match_field(fields[3], dt.month, 1, 12) and
                match_field(fields[4], cron_dow, 0, 7))
    except Exception:
        return False


def load_schedule():
    """DEPRECATED (v1.1.2 two-layer): schedule is loaded from the EFFECTIVE
    configuration by config_mgr.initialize() -> _apply_config_to_runtime().

    This no longer reads the fragmented legacy ``speedtest_schedule`` key
    directly: once either canonical key exists, legacy is never a fallback
    (§16), and while upgrade_required the manager surfaces legacy through its
    effective compatibility view. Kept as a safe no-op so any residual caller
    does not reintroduce a legacy read.
    """
    return


# =============================================================================
# TWO-LAYER CONFIGURATION INTEGRATION (v1.1.2)
# =============================================================================
#
# Effective configuration is the section-level merge of the two canonical
# layers (speedtest_analyzer_device > speedtest_analyzer_group > built-in
# defaults). Ordinary user changes are persisted ONLY to
# speedtest_analyzer_device through the Configuration Manager. The Group key is
# never written locally. Runtime readers consult the EFFECTIVE config (via
# config_mgr.active_section); fragmented legacy App Data is NEVER a fallback
# once either canonical key exists (§16). The hot-reload callback below
# repopulates RAM globals/caches from the effective config. No legacy or Group
# App Data is written by any of this.

# Runtime-only Device GPS fix, refreshed when the effective GeoView policy is
# device_gps becomes authoritative (save/convert/validate/reset/startup) and on
# explicit Refresh GPS. This is RUNTIME STATE ONLY: it is never persisted into
# either canonical key and never triggers a revision increment (§39-§41).
_device_gps_runtime = {
    'polled': False,
    'gps_lock': False,
    'latitude': None,
    'longitude': None,
    'polled_at': None,
    'status': 'unknown',   # 'lock' | 'no_lock' | 'unavailable' | 'unknown'
}
_device_gps_runtime_lock = threading.Lock()


def _poll_device_gps_runtime(reason=''):
    """Perform ONE fresh Device GPS acquisition and store it in RUNTIME only.

    Uses the existing safe, non-blocking status read (cp.get_gps_status), the
    same call the on-demand Refresh GPS path uses. No background thread is
    started. No App Data is written; no revision changes. "No Lock" is a valid
    outcome: the app stays in Device GPS mode and does NOT fall back to
    manual/default/fake coordinates. Never raises.
    """
    global _device_gps_runtime
    try:
        gps = cp.get_gps_status() or {}
    except Exception as exc:
        cp.log('GeoView: Device GPS poll unavailable (%s): %s'
               % (reason, exc))
        with _device_gps_runtime_lock:
            _device_gps_runtime = {
                'polled': True, 'gps_lock': False, 'latitude': None,
                'longitude': None, 'polled_at': time.time(),
                'status': 'unavailable',
            }
        return

    lock_val = gps.get('gps_lock')
    if lock_val is None:
        lock_val = gps.get('lock')
    gps_lock = bool(lock_val)
    latitude = gps.get('latitude')
    longitude = gps.get('longitude')

    usable = gps_fix_is_usable({
        'gps_lock': gps_lock, 'latitude': latitude, 'longitude': longitude,
    })

    with _device_gps_runtime_lock:
        if usable:
            _device_gps_runtime = {
                'polled': True, 'gps_lock': True, 'latitude': latitude,
                'longitude': longitude, 'polled_at': time.time(),
                'status': 'lock',
            }
        else:
            # No Lock is valid. Stay in Device GPS mode; do NOT fabricate or
            # fall back to any other coordinates.
            _device_gps_runtime = {
                'polled': True, 'gps_lock': False, 'latitude': None,
                'longitude': None, 'polled_at': time.time(),
                'status': 'no_lock',
            }
    cp.log('GeoView: Device GPS poll (%s) -> %s'
           % (reason, 'lock' if usable else 'no_lock'))


def get_device_gps_runtime():
    """Return a copy of the current runtime Device GPS fix (never persisted)."""
    with _device_gps_runtime_lock:
        return dict(_device_gps_runtime)


def _apply_config_to_runtime(effective):
    """Reinitialize affected runtime subsystems from the EFFECTIVE config.

    Called by the Configuration Manager after any successful save/convert/
    reload with the EFFECTIVE (merged Device>Group>Default) config body. This
    updates ONLY in-RAM structures and caches. It NEVER writes configuration
    back into any App Data key: a group-managed configuration must not cause
    the device to create or update device-level App Data.

    Architecture:
        (group,device) layers -> effective RAM body -> runtime globals/caches.

    When the effective GeoView policy is device_gps, ONE fresh GPS acquisition
    is triggered here (runtime-only). Never raises.
    """
    global schedule_config
    global _iperf3_server_settings

    # True only while the startup initialize() apply runs. Used to suppress
    # runtime auto-start of an enabled-but-not-autostart schedule after a
    # restart, WITHOUT writing enabled=false back to App Data. Module-scope
    # default set below.
    global _config_startup_apply

    # The hot-reload callback receives the effective config body directly
    # (already section-merged). Tolerate a wrapped {'config': {...}} shape too.
    if isinstance(effective, dict) and 'config' in effective and \
            isinstance(effective.get('config'), dict):
        body = effective['config']
    else:
        body = effective if isinstance(effective, dict) else {}

    # --- Scheduled Tasks -----------------------------------------------------
    schedule = body.get('schedule')
    if isinstance(schedule, dict):
        try:
            with schedule_lock:
                # enabled and autostart are INDEPENDENT PERSISTED fields and
                # are mirrored into runtime EXACTLY as persisted -- we never
                # mutate persisted/effective 'enabled' here. The separate
                # RUNTIME flag schedule_config['running'] controls whether the
                # scheduler thread actually fires.
                schedule_config.update({
                    'enabled': bool(schedule.get('enabled', False)),
                    'autostart': bool(schedule.get('autostart', False)),
                    'cron': schedule.get('cron', ''),
                    'engine': schedule.get('engine', 'netperf'),
                    'params': dict(schedule.get('params', {})),
                })
                # Derive the runtime running state via the single shared helper
                # (config_mgr.compute_schedule_running) so the web layer and the
                # regression tests use ONE source of truth:
                #   - startup/boot apply: running = enabled AND autostart
                #   - interactive save/apply: running = enabled
                enabled = schedule_config['enabled']
                autostart = schedule_config['autostart']
                schedule_config['running'] = config_mgr.compute_schedule_running(
                    enabled, autostart, is_startup=_config_startup_apply)
                if _config_startup_apply and enabled and not autostart:
                    cp.log('Schedule: enabled but autostart=false -> not '
                           'auto-starting after restart (persisted enabled '
                           'preserved; runtime not running)')
        except Exception as e:
            cp.log(f'Config apply (schedule) error: {e}')

    # --- iPerf3 server settings ---------------------------------------------
    # Only server_mode is canonical. last_public_region is RAM-only runtime
    # state and is preserved across a canonical apply (never sourced from or
    # written to canonical).
    iperf3_settings = body.get('iperf3_server_settings')
    if isinstance(iperf3_settings, dict):
        try:
            mode = iperf3_settings.get('server_mode', 'public')
            with _iperf3_server_settings_lock:
                remembered_region = ''
                if isinstance(_iperf3_server_settings, dict):
                    remembered_region = _iperf3_server_settings.get(
                        'last_public_region', '')
                _iperf3_server_settings = {
                    'server_mode': mode,
                    'last_public_region': remembered_region,
                }
            # Rebuild the active server-source RAM cache from the new settings.
            # (Reads the bundled public catalog / canonical user list; no
            # legacy App Data write.)
            _load_active_iperf3_server_cache(force=True)
        except Exception as e:
            cp.log(f'Config apply (iperf3 settings) error: {e}')

    # --- GeoView authoritative Device-GPS poll ------------------------------
    # When the newly authoritative effective GeoView policy is device_gps,
    # trigger ONE fresh runtime GPS acquisition (§40, §41). This covers every
    # activation path because the manager calls this callback after Device
    # save, legacy/experimental conversion, Group validation, Device-override
    # removal, and startup. Runtime-only; no writes; no revision change.
    geoview = body.get('geoview')
    if isinstance(geoview, dict) and \
            geoview.get('active_location_source') == 'device_gps':
        try:
            _poll_device_gps_runtime(reason='effective device_gps authoritative')
        except Exception as e:
            cp.log(f'Config apply (geoview device_gps poll) error: {e}')


def _effective_geo_settings():
    """Return the EFFECTIVE GeoView settings (Device>Group>Default merge).

    The effective ``geoview`` section stores the GeoView persisted sub-object
    (schema 2); run it through the GeoView normalizer so callers receive the
    same fully normalized structure that load_geo_settings() returns. No
    legacy App Data is written or consulted here once the manager is loaded.
    """
    effective_geo = config_mgr.active_section('geoview')
    if effective_geo is not None:
        try:
            return config_mgr.cellular_geo.normalize_geo_settings(effective_geo)
        except Exception as exc:
            cp.log(f'Config apply (geoview normalize) error: {exc}')
    return load_geo_settings()


class ConfigApplyResult(object):
    """Result of an ordinary Device Save routed through the manager.

    action (LOCKED two-layer model -- NO scope / NO group candidate):
      'saved'       -> Device configuration written (or emptied+deleted)
      'reconciled'  -> a canonical layer changed; staged edit discarded (409)
      'blocked'     -> configuration mutation is blocked (upgrade/error) (409)
      'error'       -> failure with message

    ``removed_override_sections`` carries the sections whose redundant Device
    override was auto-removed because it matched the Group value (§14). The UI
    shows a non-blocking informational message; there is NO confirmation modal.
    """

    def __init__(self, action, message='', config=None,
                 removed_override_sections=None, block_reason=None,
                 no_change=False):
        self.action = action
        self.message = message
        self.config = config
        self.removed_override_sections = removed_override_sections or []
        self.block_reason = block_reason
        self.no_change = no_change


def persist_config_section(section, value, updates=None):
    """Persist ordinary configuration change(s) as a Device-only save.

    Always writes speedtest_analyzer_device (never Group, never the old
    experimental key, never fragmented legacy keys). The manager performs, in
    order: mutation-block gating -> revision-pair reconciliation -> sparse
    Device section update (with redundant-override removal when Group matches)
    -> read-back verified write (or delete when emptied) -> effective recompute
    -> hot apply.

    Pass a single ``section``/``value`` for one section, or an ``updates`` dict
    of {section: value} for a multi-section transaction (ONE device_revision
    increment). Callers invoke this only AFTER their own feature validation.
    """
    if updates is not None:
        kw = {'updates': updates}
    else:
        kw = {'section': section, 'value': value}

    result = config_mgr.save_device(**kw)

    if result.status == 'saved':
        return ConfigApplyResult(
            'saved', config=result.config,
            removed_override_sections=result.removed_override_sections,
            message=result.message,
            no_change=getattr(result, 'no_change', False))
    if result.status == 'reconciled':
        return ConfigApplyResult('reconciled', message=result.message,
                                 config=result.config)
    if result.status == 'blocked':
        block = config_mgr.mutation_blocked()
        return ConfigApplyResult(
            'blocked',
            message=(block.detail if block else result.message),
            block_reason=(block.reason if block else 'upgrade_required'))
    return ConfigApplyResult('error', message=(result.error or 'save failed'))


def respond_user_iperf3_list_apply(handler, final_servers, guard,
                                   success_payload):
    """Persist a User iPerf3 list change (optionally + schedule reset).

    ``guard`` is the result of _guard_user_server_list_change:
      - dict  -> confirmation required; sent as 409 (no persistence).
      - SCHEDULE_RESET_REQUIRED -> fold a safe schedule reset into the SAME
        Device transaction as the list change (one device_revision increment).
      - None -> persist the list change alone.

    Returns the ConfigApplyResult (or None when a 409 confirmation was sent).
    """
    if isinstance(guard, dict):
        handler.send_json(guard, 409)
        return None

    if guard == SCHEDULE_RESET_REQUIRED:
        updates = {
            'iperf3_user_servers': final_servers,
            'schedule': _safe_empty_schedule(),
        }
        result = persist_config_section(None, None, updates=updates)
        _emit_apply_contract(handler, result, success_payload)
        return result

    return respond_config_apply_on(
        handler, 'iperf3_user_servers', final_servers, success_payload)


def _emit_apply_contract(handler, result, success_payload):
    """Send the uniform ordinary-Save response for a ConfigApplyResult.

    Ordinary saves NEVER return scope_required or group_candidate. On success
    the caller's success_payload is augmented with any redundant-override
    removal notice so the UI can show a non-blocking informational message.
    """
    if result.action == 'reconciled':
        handler.send_json({'status': 'reconciled', 'error': result.message},
                          409)
    elif result.action == 'blocked':
        handler.send_json({
            'status': 'upgrade_required',
            'error': result.message,
            'block_reason': result.block_reason,
        }, 409)
    elif result.action == 'saved':
        payload = dict(success_payload) if isinstance(success_payload, dict) \
            else {'status': 'saved'}
        if result.removed_override_sections:
            payload['override_removed_sections'] = \
                result.removed_override_sections
            if result.message:
                payload['override_removed_message'] = result.message
        if getattr(result, 'no_change', False):
            # True normalized no-op: persistent + effective config unchanged.
            payload['no_change'] = True
        handler.send_json(payload)
    else:
        handler.send_json({'error': result.message or 'Save failed.'}, 500)


def respond_config_apply_on(handler, section, value, success_payload):
    """Route an ordinary section Save through the manager and send the reply.

    Module-level twin of SpeedtestHandler._respond_config_apply so non-method
    persistence paths (server-list handlers, iPerf3 mode switch) share one
    contract:

      reconciled        -> 409 {"status":"reconciled","error":...}
      upgrade_required  -> 409 {"status":"upgrade_required","error":...}
      saved             -> 200 success_payload (+ override_removed_* if any)
      error             -> 500 {"error":...}

    Returns the ConfigApplyResult so the caller can perform success-side RAM
    cache/runtime updates ONLY after persistence actually succeeded.
    """
    try:
        result = persist_config_section(section, value)
    except Exception as exc:
        cp.log(f'Config apply error ({section}): {exc}')
        handler.send_json({'error': 'Configuration save failed.'}, 500)
        return ConfigApplyResult('error', message=str(exc))

    _emit_apply_contract(handler, result, success_payload)
    return result


def scheduler_thread():
    """Background thread that checks cron schedule and runs tests."""
    last_fired = None
    while True:
        try:
            # No extra reliability thread is required. This existing
            # 15-second scheduler loop only performs an SDK write when
            # statistics are dirty and the one-hour checkpoint is due.
            _checkpoint_iperf3_stats_if_due()

            with schedule_lock:
                # The scheduler fires on the RUNTIME running flag, not the
                # persisted 'enabled' intent. 'running' is derived by the
                # config-apply callback (boot: enabled AND autostart; save:
                # enabled). Fall back to 'enabled' only if 'running' has not
                # been set yet (defensive; the callback always sets it).
                running = schedule_config.get(
                    'running', schedule_config.get('enabled', False))
                cron = schedule_config.get('cron', '')
                engine = schedule_config.get('engine', 'netperf')
                params = schedule_config.get('params', {})

            if running and cron:
                now = datetime.utcnow()
                current_minute = (now.year, now.month, now.day, now.hour, now.minute)
                if current_minute != last_fired and cron_matches(cron, now):
                    last_fired = current_minute
                    if _reserve_test_slot(engine):
                        cp.log(f'Scheduled test triggered: {cron}')
                        params_copy = dict(params)
                        params_copy['engine'] = engine
                        params_copy['_trigger'] = 'scheduled'
                        thread = Thread(target=run_test_thread,
                                        args=(engine, params_copy), daemon=True)
                        try:
                            thread.start()
                        except Exception:
                            _release_test_slot()
                            raise
                    else:
                        cp.log(
                            'Scheduled test skipped: another test is '
                            'already running'
                        )
        except Exception as e:
            cp.log(f'Scheduler error: {e}')
        time.sleep(15)


cp.log('Starting...')
cp.log('Speedtest Analyzer - WAN Performance Testing and Analysis')

# Check available engines
if has_ookla():
    cp.log('Ookla binary detected - will use as primary engine')
else:
    cp.log('No Ookla binary - using Netperf (built-in) as default')

# Register the runtime reinitialization callback so the Configuration Manager
# can hot-reload affected subsystems after adopt/save/validate/reload.
# _config_startup_apply is True ONLY during the startup initialize() apply so
# an enabled-but-not-autostart schedule does not auto-start after a restart
# (runtime-only suppression; persisted enabled is never changed).
_config_startup_apply = False
config_mgr.register_hot_reload(_apply_config_to_runtime)

# Load iPerf3 runtime server settings + active server-source RAM cache. These
# establish baseline RAM state; the manager's effective config corrects them
# via the hot-reload callback below.
_load_iperf3_server_settings()
_load_active_iperf3_server_cache()

# Load the two-layer configuration. The manager computes the EFFECTIVE config
# (Device>Group>Default), or the legacy compatibility view while
# upgrade_required, and hot-applies it into the runtime RAM surfaces above
# (including the schedule) WITHOUT writing any App Data on startup. The
# schedule is therefore established here, not by a direct legacy-key read.
try:
    # Startup apply: gate the boot-only no-autostart suppression for THIS apply.
    _config_startup_apply = True
    try:
        _config_state = config_mgr.initialize()
    finally:
        _config_startup_apply = False
    cp.log('Configuration: state=%s (group_present=%s device_present=%s)'
           % (_config_state.state, _config_state.group_present,
              _config_state.device_present))
    if _config_state.mutation_block is not None:
        cp.log('Configuration: mutation blocked (%s)'
               % _config_state.mutation_block.reason)
    # The effective config has been hot-applied by initialize(); re-validate
    # iPerf3 schedule metadata against the (possibly updated) runtime schedule
    # for the normal operating states.
    if _config_state.state in (config_mgr.STATE_DEVICE,
                               config_mgr.STATE_GROUP,
                               config_mgr.STATE_GROUP_WITH_DEVICE_OVERRIDES,
                               config_mgr.STATE_UPGRADE_REQUIRED):
        _validate_loaded_iperf3_schedule()
except Exception as _cfg_exc:
    cp.log('Configuration: initialize error: %s' % _cfg_exc)

# Log the RUNTIME running state (not just persisted enabled) so the boot log is
# honest: an enabled-but-not-autostart schedule is preserved as enabled but is
# NOT running after a restart.
if schedule_config.get('running'):
    cp.log(f'Schedule active (running): {schedule_config.get("cron", "")}')
elif schedule_config.get('enabled') and not schedule_config.get('autostart'):
    cp.log('Schedule enabled but NOT running after restart '
           '(Auto-start off): %s' % schedule_config.get('cron', ''))

# Start scheduler thread
sched_thread = Thread(target=scheduler_thread, daemon=True)
sched_thread.start()



class ResilientHTTPServer(HTTPServer):
    """HTTPServer with a numeric fallback for invalid router hostnames."""

    def server_bind(self):
        # Preserve TCPServer's normal wildcard bind and socket behavior.
        socketserver.TCPServer.server_bind(self)

        host, port = self.server_address[:2]

        try:
            # Preserve HTTPServer's normal server-name behavior when the
            # router hostname can be resolved and encoded successfully.
            self.server_name = socket.getfqdn(host)
        except UnicodeError as e:
            # NCOS may expose an internal hostname that cannot be encoded as
            # a valid DNS label. The numeric listener address is sufficient
            # because the app is accessed through the router's LAN IP.
            self.server_name = host or '0.0.0.0'
            cp.log(
                'Web server hostname lookup unavailable; using '
                f'{self.server_name}: {e}'
            )

        self.server_port = port


# Start web server
try:
    ResilientHTTPServer.allow_reuse_address = True
    server = ResilientHTTPServer(('', PORT), SpeedtestHandler)
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    cp.log(f'Web server started on port {PORT}')
except Exception as e:
    cp.log(f'Failed to start web server: {e}')
    sys.exit(1)

# Main loop
while True:
    time.sleep(1)
