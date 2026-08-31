"""Local history analytics for Speedtest Analyzer Cellular Analysis.

This module is intentionally pure-Python and does not call NCOS. It derives
all analytics from the bounded Speedtest Analyzer history already persisted
by speedtest_web.py.
"""

from datetime import datetime, timedelta
import re


_SCHEMA_VERSION = 1
_UNKNOWN_CELL_KEY = 'unknown'
_UNKNOWN_LABEL = 'Unknown Serving Cell'
_EMPTY_TEXT = {'', 'none', 'n/a', 'unknown', '--', 'not registered', 'unavailable'}


def _text(value):
    if value is None:
        return ''
    return str(value).strip()


def _present(value):
    text = _text(value)
    return bool(text) and text.lower() not in _EMPTY_TEXT


def _number(value):
    if value is None or value == '':
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        match = re.search(r'-?\d+(?:\.\d+)?', str(value))
        if not match:
            return None
        try:
            return float(match.group(0))
        except ValueError:
            return None


def _canonical_cell_id(value):
    """Return a canonical positive serving-cell identifier string or ''."""
    if not _present(value):
        return ''

    text = _text(value)

    # NCOS commonly emits forms such as "6643981 (0x65610d)". Prefer the
    # leading decimal representation so formatting differences bucket alike.
    match = re.match(r'^\s*(\d+)\b', text)
    if match:
        number = int(match.group(1))
        return str(number) if number > 0 else ''

    match = re.match(r'^\s*0x([0-9a-fA-F]+)\b', text)
    if match:
        number = int(match.group(1), 16)
        return str(number) if number > 0 else ''

    # Accept a clean positive integer string only. Do not manufacture serving
    # identities from PCI/TAC/band when CELL_ID/NCI is absent.
    if re.match(r'^\+?\d+$', text):
        number = int(text)
        return str(number) if number > 0 else ''

    return ''


def _normalize_plmn(value):
    text = _text(value)
    if not _present(text):
        return ''
    digits = ''.join(ch for ch in text if ch.isdigit())
    return digits if len(digits) in (5, 6) else text


def _parse_timestamp(value):
    text = _text(value)
    if not text:
        return None
    try:
        if text.endswith('Z'):
            return datetime.strptime(text, '%Y-%m-%dT%H:%M:%SZ')
        return datetime.fromisoformat(text.replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None


def _scope_cutoff(scope, now=None):
    scope = _text(scope).lower() or 'all'
    if scope == 'all':
        return None

    hours = {
        '12h': 12,
        '24h': 24,
        '3d': 72,
        '7d': 168,
    }.get(scope)

    if hours is None:
        return None

    return (now or datetime.utcnow()) - timedelta(hours=hours)


def _normalize_rat(value):
    text = _text(value).upper()
    if text in ('5G', 'NR', 'NR5G') or 'NR' in text or '5G' in text:
        return 'NR'
    if text in ('4G', 'LTE') or 'LTE' in text:
        return 'LTE'
    return text


def _normalize_band(value, rat=''):
    text = _text(value)
    if not text:
        return ''
    text = re.sub(r'^Band\s+', '', text, flags=re.IGNORECASE).strip()
    if re.match(r'(?i)^n\d+', text):
        return 'n' + text[1:]
    if re.match(r'(?i)^b\d+', text):
        return 'B' + text[1:]
    if re.match(r'^\d+', text):
        return ('n' if _normalize_rat(rat) == 'NR' else 'B') + text
    return text


def _normalize_bandwidth(value):
    number = _number(value)
    if number is None:
        return None
    return round(number, 1)


def _normalize_channel(value):
    if not _present(value):
        return ''
    return _text(value)


def _normalize_pci(value):
    if not _present(value):
        return ''
    text = _text(value)
    match = re.search(r'\d+', text)
    return match.group(0) if match else text


def _serving_cell_from_cellular(cellular):
    if not isinstance(cellular, dict):
        return None

    service_mode = _text(cellular.get('service_mode'))

    if service_mode not in ('LTE', '5G NSA', '5G SA'):
        for field in ('service_display', 'service_type'):
            candidate = _text(cellular.get(field))
            upper = candidate.upper()

            if 'NSA' in upper:
                service_mode = '5G NSA'
                break

            if 'SA' in upper:
                service_mode = '5G SA'
                break

            if upper == 'LTE':
                service_mode = 'LTE'
                break

    if (
        service_mode not in ('LTE', '5G NSA', '5G SA')
        and _present(cellular.get('nr_cell_id'))
        and not _present(cellular.get('cell_id'))
    ):
        service_mode = '5G SA'

    is_sa = service_mode == '5G SA'
    source = 'NR_CELL_ID' if is_sa else 'LTE'
    rat = 'NR' if is_sa else 'LTE'

    raw_id = cellular.get('cell_id')
    if is_sa and _present(cellular.get('nr_cell_id')):
        raw_id = cellular.get('nr_cell_id')

    cell_id = _canonical_cell_id(raw_id)
    plmn = _normalize_plmn(cellular.get('plmn'))

    return {
        'cell_id': cell_id,
        'raw_cell_id': _text(raw_id),
        'cell_id_source': source,
        'service_mode': service_mode,
        'plmn': plmn,
        'tac': (
            _text(cellular.get('tac'))
            if _present(cellular.get('tac'))
            else ''
        ),
        'pci': _normalize_pci(
            cellular.get('phy_cell_id_5g')
            if is_sa
            else cellular.get('phy_cell_id')
        ),
        'band': _normalize_band(
            cellular.get('rf_band_5g')
            if is_sa
            else cellular.get('rf_band'),
            rat,
        ),
        'channel': _normalize_channel(
            cellular.get('rf_channel_5g')
            if is_sa
            else cellular.get('rf_channel')
        ),
        'carrier': _text(cellular.get('carrier')),
    }


def _serving_cell_from_activity(activity):
    if not isinstance(activity, dict):
        return None

    for container in (
        (activity.get('download') or {}).get('peak') if isinstance(activity.get('download'), dict) else None,
        (activity.get('download') or {}).get('baseline') if isinstance(activity.get('download'), dict) else None,
        activity.get('peak'),
        activity.get('baseline'),
        activity.get('final'),
    ):
        if not isinstance(container, dict):
            continue
        serving = container.get('serving_cell')
        if isinstance(serving, dict):
            result = dict(serving)
            result['cell_id'] = _canonical_cell_id(result.get('cell_id'))
            result['plmn'] = _normalize_plmn(result.get('plmn'))
            result['pci'] = _normalize_pci(result.get('pci'))
            result['cell_id_source'] = _text(result.get('cell_id_source')).upper()
            return result

    return None


def _normalize_traffic_serving_cell(serving):
    """Normalize one serving-cell observation captured during test traffic."""
    if not isinstance(serving, dict):
        return None

    result = dict(serving)
    service_mode = _text(result.get('service_mode'))
    raw_source = _text(
        result.get('cell_id_source')
    ).upper()

    is_nr = (
        service_mode == '5G SA'
        or raw_source in ('NR', 'NR_CELL_ID')
    )

    rat = 'NR' if is_nr else 'LTE'
    source = 'NR_CELL_ID' if is_nr else 'LTE'

    raw_id = result.get('cell_id')

    result['cell_id'] = _canonical_cell_id(raw_id)
    result['raw_cell_id'] = _text(raw_id)
    result['cell_id_source'] = source
    result['service_mode'] = service_mode
    result['plmn'] = _normalize_plmn(
        result.get('plmn')
    )
    result['tac'] = (
        _text(result.get('tac'))
        if _present(result.get('tac'))
        else ''
    )
    result['pci'] = _normalize_pci(
        result.get('pci')
    )
    result['band'] = _normalize_band(
        result.get('band'),
        rat,
    )
    result['channel'] = _normalize_channel(
        result.get('channel')
    )
    result['carrier'] = _text(
        result.get('carrier')
    )

    return result


def _snapshot_serving_cell(snapshot):
    """Return normalized serving-cell identity from one activity snapshot."""
    if not isinstance(snapshot, dict):
        return None

    serving = snapshot.get('serving_cell')
    if not isinstance(serving, dict):
        return None

    return _normalize_traffic_serving_cell(
        serving
    )


def _phase_serving_cell_intervals(phase_name, phase):
    """Convert one traffic phase timeline into serving-cell time intervals."""
    if not isinstance(phase, dict):
        return []

    duration = _number(
        phase.get('duration_s')
    )

    if duration is None or duration <= 0:
        return []

    observations = []

    baseline = phase.get('baseline')
    baseline_cell = _snapshot_serving_cell(
        baseline
    )

    if baseline_cell is not None:
        observations.append({
            'elapsed_s': 0.0,
            'cell': baseline_cell,
        })

    timeline = phase.get('timeline')
    if isinstance(timeline, list):
        for snapshot in timeline:
            if not isinstance(snapshot, dict):
                continue

            cell = _snapshot_serving_cell(
                snapshot
            )

            if cell is None:
                continue

            elapsed = _number(
                snapshot.get('elapsed_s')
            )

            if elapsed is None:
                continue

            elapsed = max(
                0.0,
                min(float(elapsed), float(duration))
            )

            observations.append({
                'elapsed_s': elapsed,
                'cell': cell,
            })

    if not observations:
        peak_cell = _snapshot_serving_cell(
            phase.get('peak')
        )

        if peak_cell is not None:
            observations.append({
                'elapsed_s': 0.0,
                'cell': peak_cell,
            })

    if not observations:
        return []

    observations.sort(
        key=lambda item: item['elapsed_s']
    )

    collapsed = []

    for observation in observations:
        elapsed = observation['elapsed_s']
        cell = observation['cell']
        key = _cell_key(cell)

        if (
            collapsed
            and collapsed[-1]['elapsed_s'] == elapsed
        ):
            collapsed[-1] = {
                'elapsed_s': elapsed,
                'cell': cell,
                'key': key,
            }
            continue

        if (
            collapsed
            and collapsed[-1]['key'] == key
        ):
            continue

        collapsed.append({
            'elapsed_s': elapsed,
            'cell': cell,
            'key': key,
        })

    intervals = []

    for index, observation in enumerate(
        collapsed
    ):
        start_s = observation['elapsed_s']

        if index + 1 < len(collapsed):
            end_s = collapsed[
                index + 1
            ]['elapsed_s']
        else:
            end_s = float(duration)

        if end_s < start_s:
            continue

        interval = {
            'phase': phase_name,
            'start_s': round(start_s, 3),
            'end_s': round(end_s, 3),
            'duration_s': round(
                end_s - start_s,
                3,
            ),
            'cell': observation['cell'],
        }

        intervals.append(interval)

    return intervals


def _traffic_serving_cell_intervals(record):
    """Return ordered serving-cell intervals observed during active traffic.

    Download and Upload remain separate phases because each phase has its own
    elapsed clock. The result preserves proven in-test handoffs without
    inventing state between scheduled speed tests.
    """
    if not isinstance(record, dict):
        return []

    activity = record.get(
        'carrier_activity'
    )

    if not isinstance(activity, dict):
        return []

    intervals = []

    for phase_name in (
        'download',
        'upload',
    ):
        intervals.extend(
            _phase_serving_cell_intervals(
                phase_name,
                activity.get(phase_name),
            )
        )

    return intervals


def _traffic_serving_cell_summary(record):
    """Summarize serving-cell identity observed during active test traffic.

    A single speed test may use more than one serving cell. This summary
    preserves every identifiable cell and every proven transition without
    inventing transitions through missing/Unknown telemetry.
    """
    intervals = _traffic_serving_cell_intervals(
        record
    )

    if not intervals:
        fallback = _serving_cell_for_record(
            record
        )
        fallback_key = _cell_key(fallback)

        if fallback_key == _UNKNOWN_CELL_KEY:
            return {
                'start_cell': None,
                'end_cell': None,
                'cells_observed': [],
                'handoffs': [],
                'unknown_observed': True,
                'active_traffic_s': 0.0,
            }

        return {
            'start_cell': dict(fallback),
            'end_cell': dict(fallback),
            'cells_observed': [
                dict(fallback)
            ],
            'handoffs': [],
            'unknown_observed': False,
            'active_traffic_s': 0.0,
        }

    cells_observed = []
    seen_keys = set()
    unknown_observed = False
    active_traffic_s = 0.0

    start_cell = None
    end_cell = None
    handoffs = []

    previous = None

    for interval in intervals:
        duration = _number(
            interval.get('duration_s')
        )

        if duration is not None and duration > 0:
            active_traffic_s += duration

        cell = interval.get('cell')
        key = _cell_key(cell)

        if key == _UNKNOWN_CELL_KEY:
            unknown_observed = True
        else:
            if start_cell is None:
                start_cell = dict(cell)

            end_cell = dict(cell)

            if key not in seen_keys:
                seen_keys.add(key)
                cells_observed.append(
                    dict(cell)
                )

        if previous is not None:
            previous_cell = previous.get('cell')
            previous_key = _cell_key(
                previous_cell
            )

            if (
                previous_key != _UNKNOWN_CELL_KEY
                and key != _UNKNOWN_CELL_KEY
                and previous_key != key
            ):
                handoffs.append({
                    'phase': interval.get(
                        'phase',
                        ''
                    ),
                    'elapsed_s': round(
                        float(
                            interval.get(
                                'start_s',
                                0.0
                            )
                            or 0.0
                        ),
                        3,
                    ),
                    'from': dict(
                        previous_cell
                    ),
                    'to': dict(
                        cell
                    ),
                    'phase_boundary': (
                        previous.get('phase')
                        != interval.get('phase')
                    ),
                })

        previous = interval

    return {
        'start_cell': start_cell,
        'end_cell': end_cell,
        'cells_observed': cells_observed,
        'handoffs': handoffs,
        'unknown_observed': unknown_observed,
        'active_traffic_s': round(
            active_traffic_s,
            3,
        ),
    }


def _serving_cell_for_record(record):
    activity_cell = _serving_cell_from_activity(record.get('carrier_activity'))
    final_cell = _serving_cell_from_cellular(record.get('cellular'))

    # Prefer in-test identity when it is usable. Fill descriptive attributes
    # from the final snapshot because older history has richer final metadata.
    if activity_cell and activity_cell.get('cell_id'):
        result = dict(final_cell or {})
        result.update({
            key: value for key, value in activity_cell.items()
            if value not in (None, '')
        })
        return result

    return final_cell or activity_cell or {
        'cell_id': '',
        'raw_cell_id': '',
        'cell_id_source': '',
        'service_mode': '',
        'plmn': '',
        'tac': '',
        'pci': '',
        'band': '',
        'channel': '',
        'carrier': '',
    }


def _cell_key(cell):
    cell_id = _canonical_cell_id(cell.get('cell_id')) if isinstance(cell, dict) else ''
    if not cell_id:
        return _UNKNOWN_CELL_KEY
    source = _text(cell.get('cell_id_source')).upper() or 'CELL'
    plmn = _normalize_plmn(cell.get('plmn')) or '?'
    return '%s|%s|%s' % (source, plmn, cell_id)


def _supplement_peak_identity(record, snapshot):
    """Supplement missing peak carrier identity from final cellular data.

    carrier_activity peak observations remain authoritative for the observed
    radio configuration.  The final cellular aggregation is used only to fill
    missing channel/PCI identity when a RAT + band + bandwidth match is
    unambiguous.

    This allows the same physical component to be followed across tests
    without replacing or inventing peak carrier state.
    """
    if not isinstance(snapshot, dict):
        return snapshot

    cellular = record.get('cellular')
    if not isinstance(cellular, dict):
        return snapshot

    aggregation = cellular.get('aggregation')
    if not isinstance(aggregation, list):
        return snapshot

    candidates = []

    for carrier in aggregation:
        if not isinstance(carrier, dict):
            continue

        rat = _normalize_rat(
            carrier.get('rat')
            or carrier.get('gen')
        )

        band = _normalize_band(
            carrier.get('band'),
            rat
        )

        bandwidth = _normalize_bandwidth(
            carrier.get('bandwidth_mhz')
            if carrier.get('bandwidth_mhz') is not None
            else carrier.get('bandwidth')
        )

        channel = _normalize_channel(
            carrier.get('channel')
        )

        pci = _normalize_pci(
            carrier.get('pci')
            if carrier.get('pci') is not None
            else carrier.get('phy_cell_id')
        )

        if not rat and not band:
            continue

        candidates.append({
            'rat': rat,
            'band': band,
            'bandwidth_mhz': bandwidth,
            'channel': channel,
            'pci': pci,
        })

    if not candidates:
        return snapshot

    enriched = dict(snapshot)
    enriched_carriers = []

    for carrier in snapshot.get('carriers', []):
        if not isinstance(carrier, dict):
            continue

        updated = dict(carrier)

        rat = _normalize_rat(updated.get('rat'))
        band = _normalize_band(
            updated.get('band'),
            rat
        )
        bandwidth = _normalize_bandwidth(
            updated.get('bandwidth_mhz')
        )
        channel = _normalize_channel(
            updated.get('channel')
        )
        pci = _normalize_pci(
            updated.get('pci')
        )

        # Nothing to supplement when both discriminators already exist.
        # Normalizers return '' for missing channel/PCI, so use truthiness
        # rather than an is-not-None test here.
        if channel and pci:
            enriched_carriers.append(updated)
            continue

        matches = []

        for candidate in candidates:
            if candidate['rat'] != rat:
                continue

            if candidate['band'] != band:
                continue

            if candidate['bandwidth_mhz'] != bandwidth:
                continue

            if (
                channel
                and candidate['channel']
                and candidate['channel'] != channel
            ):
                continue

            if (
                pci
                and candidate['pci']
                and candidate['pci'] != pci
            ):
                continue

            matches.append(candidate)

        # Supplement only when the mapping is unambiguous.
        if len(matches) == 1:
            match = matches[0]

            if not channel and match['channel']:
                updated['channel'] = match['channel']

            if not pci and match['pci']:
                updated['pci'] = match['pci']

        enriched_carriers.append(updated)

    enriched['carriers'] = enriched_carriers

    return enriched


def _active_peak(record):
    """Return the strongest radio configuration observed during test traffic.

    carrier_activity.peak is authoritative because the collector builds it
    from successful Download/Upload traffic windows only, excluding setup,
    failed attempts, and retry activity.

    This represents radio resources reported while test traffic was active.
    It must not be interpreted as proof of uplink secondary-carrier usage.
    """
    activity = record.get('carrier_activity')
    if not isinstance(activity, dict):
        return None, ''

    overall_peak = activity.get('peak')
    if isinstance(overall_peak, dict):
        return (
            _supplement_peak_identity(
                record,
                overall_peak
            ),
            'traffic_peak'
        )

    # Compatibility fallback for records that contain phase-aware activity
    # but do not contain the consolidated successful-traffic peak.
    download = activity.get('download')
    if isinstance(download, dict) and isinstance(download.get('peak'), dict):
        return (
            _supplement_peak_identity(
                record,
                download.get('peak')
            ),
            'download_peak'
        )

    return None, ''


def _normalized_carriers(snapshot):
    if not isinstance(snapshot, dict):
        return []
    result = []
    for carrier in snapshot.get('carriers', []):
        if not isinstance(carrier, dict):
            continue
        active = carrier.get('active')
        bw = _normalize_bandwidth(carrier.get('bandwidth_mhz'))
        if active is False or bw == 0:
            continue
        rat = _normalize_rat(carrier.get('rat'))
        band = _normalize_band(carrier.get('band'), rat)
        if not rat and not band:
            continue
        result.append({
            'role': _text(carrier.get('role')),
            'rat': rat,
            'band': band,
            'bandwidth_mhz': bw,
            'channel': _normalize_channel(carrier.get('channel')),
            'pci': _normalize_pci(carrier.get('pci')),
            'rsrp': _number(carrier.get('rsrp')),
            'rsrq': _number(carrier.get('rsrq')),
            'sinr': _number(carrier.get('sinr')),
        })
    return result


def _carrier_identity(carrier):
    return (
        _normalize_rat(carrier.get('rat')),
        _normalize_band(carrier.get('band'), carrier.get('rat')),
        _normalize_channel(carrier.get('channel')),
        _normalize_pci(carrier.get('pci')),
    )


def _config_signature(snapshot):
    carriers = _normalized_carriers(snapshot)
    if not carriers:
        return ()
    parts = []
    for carrier in carriers:
        ident = _carrier_identity(carrier)
        parts.append(ident + (_normalize_bandwidth(carrier.get('bandwidth_mhz')),))
    return tuple(sorted(parts, key=lambda item: tuple('' if v is None else str(v) for v in item)))


def _format_bw(value):
    if value is None:
        return '? MHz'
    if float(value).is_integer():
        return '%d MHz' % int(value)
    return '%s MHz' % value


def _carrier_role_is_primary(role):
    role = _text(role).lower()
    return role in ('pcell', 'p', 'primary', 'lte_pcell', 'nr_pcell') or role.startswith('pcell')


def _format_configuration(snapshot):
    carriers = _normalized_carriers(snapshot)
    if not carriers:
        return ''

    def sort_key(carrier):
        primary = 0 if _carrier_role_is_primary(carrier.get('role')) else 1
        rat = 0 if carrier.get('rat') == 'LTE' else 1
        return (primary, rat, carrier.get('band', ''), carrier.get('channel', ''))

    labels = []
    for carrier in sorted(carriers, key=sort_key):
        band = carrier.get('band') or carrier.get('rat') or '?'
        label = '%s %s' % (carrier.get('rat') or '', band)
        label = label.strip()
        if carrier.get('bandwidth_mhz') is not None:
            label += ' (%s)' % _format_bw(carrier.get('bandwidth_mhz'))
        if _carrier_role_is_primary(carrier.get('role')) and carrier.get('rat') == 'NR':
            label += ' PCell'
        labels.append(label)
    return ' + '.join(labels)


def _network_mode(record, cell=None):
    cell = cell or _serving_cell_for_record(record)
    service_mode = _text(cell.get('service_mode')) if cell else ''
    peak, _ = _active_peak(record)
    carriers = _normalized_carriers(peak)
    has_nr = any(carrier.get('rat') == 'NR' for carrier in carriers)

    if (
        service_mode == '5G SA'
        or _text(cell.get('cell_id_source')).upper()
        in ('NR', 'NR_CELL_ID')
    ):
        return '5g_sa'
    if service_mode == '5G NSA' or has_nr:
        return 'lte_5g_nsa'
    if service_mode == 'LTE' or cell.get('cell_id'):
        return 'lte_only'
    return 'unknown'


def _network_mode_label(mode):
    return {
        'lte_only': 'LTE Only',
        'lte_5g_nsa': 'LTE + 5G NR (NSA)',
        '5g_sa': '5G Standalone (SA)',
        'unknown': 'Unknown',
    }.get(mode, 'Unknown')


def _record_interface(record):
    return _text(record.get('interface')) or 'auto'


def _is_cellular_history_record(record):
    if not isinstance(record, dict):
        return False
    return isinstance(record.get('cellular'), dict) or isinstance(record.get('carrier_activity'), dict)


def _history_interfaces(history):
    result = {}
    for record in history:
        if not _is_cellular_history_record(record):
            continue
        interface = _record_interface(record)
        item = result.setdefault(interface, {
            'interface': interface,
            'label': _text(record.get('interface_label')) or interface,
            'tests': 0,
            'last_timestamp': '',
        })
        item['tests'] += 1
        timestamp = _text(record.get('timestamp'))
        if timestamp > item['last_timestamp']:
            item['last_timestamp'] = timestamp
    return sorted(result.values(), key=lambda item: item.get('last_timestamp', ''), reverse=True)


def _scope_records(history, interface, scope, now=None):
    cutoff = _scope_cutoff(scope, now=now)
    scoped = []
    for record in history:
        if not _is_cellular_history_record(record):
            continue
        if interface and _record_interface(record) != interface:
            continue
        if cutoff is not None:
            timestamp = _parse_timestamp(record.get('timestamp'))
            if timestamp is None or timestamp < cutoff:
                continue
        scoped.append(record)
    scoped.sort(key=lambda record: _parse_timestamp(record.get('timestamp')) or datetime.min)
    return scoped


def _cell_distribution(records):
    """Build traffic-aware serving-cell distribution.

    A single test may contribute to more than one serving cell when an
    identifiable handoff occurs during active traffic. tests/tests_seen are
    therefore per-cell test participation counts and may overlap.

    active_traffic_pct is mutually exclusive because it is derived from the
    actual Download/Upload observation intervals.
    """
    buckets = {}

    def ensure_bucket(key, cell, timestamp):
        is_unknown = key == _UNKNOWN_CELL_KEY

        if not isinstance(cell, dict):
            cell = {}

        return buckets.setdefault(key, {
            'key': key,
            'cell_id': (
                cell.get('cell_id', '')
                if not is_unknown
                else ''
            ),
            'cell_id_source': cell.get(
                'cell_id_source',
                ''
            ),
            'carrier': cell.get(
                'carrier',
                ''
            ),
            'plmn': cell.get(
                'plmn',
                ''
            ),
            'tac': cell.get(
                'tac',
                ''
            ),
            'pci': cell.get(
                'pci',
                ''
            ),
            'band': cell.get(
                'band',
                ''
            ),
            'channel': cell.get(
                'channel',
                ''
            ),
            'tests': 0,
            'tests_seen': 0,
            'active_traffic_s': 0.0,
            'first_seen': timestamp,
            'last_seen': timestamp,
            '_mode_counts': {
                'lte_only': 0,
                'lte_5g_nsa': 0,
                '5g_sa': 0,
                'unknown': 0,
            },
        })

    for record in records:
        timestamp = _text(
            record.get('timestamp')
        )

        intervals = (
            _traffic_serving_cell_intervals(
                record
            )
        )

        per_test = {}
        active_seconds = {}

        if intervals:
            for interval in intervals:
                cell = interval.get('cell')
                key = _cell_key(cell)

                if key not in per_test:
                    per_test[key] = (
                        dict(cell)
                        if isinstance(cell, dict)
                        else {}
                    )

                duration = _number(
                    interval.get('duration_s')
                )

                if duration is not None and duration > 0:
                    active_seconds[key] = (
                        active_seconds.get(
                            key,
                            0.0
                        )
                        + float(duration)
                    )
        else:
            summary = (
                _traffic_serving_cell_summary(
                    record
                )
            )

            for cell in summary.get(
                'cells_observed',
                []
            ):
                key = _cell_key(cell)

                if key == _UNKNOWN_CELL_KEY:
                    continue

                per_test[key] = dict(cell)

            if summary.get(
                'unknown_observed'
            ):
                per_test[
                    _UNKNOWN_CELL_KEY
                ] = {}

        if not per_test:
            fallback = _serving_cell_for_record(
                record
            )
            key = _cell_key(fallback)

            per_test[key] = (
                dict(fallback)
                if isinstance(fallback, dict)
                else {}
            )

        for key, cell in per_test.items():
            bucket = ensure_bucket(
                key,
                cell,
                timestamp,
            )

            bucket['tests'] += 1
            bucket['tests_seen'] += 1

            bucket['active_traffic_s'] += (
                active_seconds.get(
                    key,
                    0.0
                )
            )

            mode = _network_mode(
                record,
                cell
            )

            bucket['_mode_counts'][mode] = (
                bucket['_mode_counts'].get(
                    mode,
                    0
                )
                + 1
            )

            if (
                timestamp
                and (
                    not bucket['first_seen']
                    or timestamp
                    < bucket['first_seen']
                )
            ):
                bucket['first_seen'] = timestamp

            if (
                timestamp
                and timestamp
                > bucket['last_seen']
            ):
                bucket['last_seen'] = timestamp

            for attr in (
                'cell_id_source',
                'carrier',
                'plmn',
                'tac',
                'pci',
                'band',
                'channel',
            ):
                if (
                    not bucket.get(attr)
                    and cell.get(attr)
                ):
                    bucket[attr] = cell.get(
                        attr
                    )

    total_tests = len(records)

    total_active_traffic = sum(
        float(
            item.get(
                'active_traffic_s',
                0.0
            )
            or 0.0
        )
        for item in buckets.values()
    )

    known = [
        item
        for key, item in buckets.items()
        if key != _UNKNOWN_CELL_KEY
    ]

    known.sort(
        key=lambda item: (
            -item['tests_seen'],
            item.get('cell_id', '')
        )
    )

    unknown = buckets.get(
        _UNKNOWN_CELL_KEY
    )

    result = (
        known +
        ([unknown] if unknown else [])
    )

    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    letter_index = 0

    for item in result:
        is_unknown = (
            item['key']
            == _UNKNOWN_CELL_KEY
        )

        item['unknown'] = is_unknown

        if is_unknown:
            item['view_label'] = 'Unknown'
            item['label'] = 'Unknown'
        else:
            label = (
                letters[letter_index]
                if letter_index < len(letters)
                else str(letter_index + 1)
            )

            item['view_label'] = label
            item['label'] = label
            letter_index += 1

        # Backward-compatible field:
        # percentage of analyzed tests in which this cell was seen.
        # With in-test handoffs, percentages across cells may overlap.
        item['usage_pct'] = round(
            (
                item['tests_seen']
                / total_tests
                * 100.0
            ),
            1,
        ) if total_tests else 0.0

        item['active_traffic_s'] = round(
            float(
                item.get(
                    'active_traffic_s',
                    0.0
                )
                or 0.0
            ),
            3,
        )

        item['active_traffic_pct'] = round(
            (
                item['active_traffic_s']
                / total_active_traffic
                * 100.0
            ),
            1,
        ) if total_active_traffic else 0.0

        mode_counts = item.pop(
            '_mode_counts',
            {}
        )

        item['technology_modes'] = {
            mode: count
            for mode, count
            in mode_counts.items()
            if count
        }

        source = _text(
            item.get(
                'cell_id_source'
            )
        ).upper()

        if is_unknown:
            item['technology_role'] = ''

        elif source in (
            'NR',
            'NR_CELL_ID',
        ):
            item['technology_role'] = (
                '5G SA PCell'
            )

        else:
            saw_lte = bool(
                mode_counts.get(
                    'lte_only'
                )
            )

            saw_nsa = bool(
                mode_counts.get(
                    'lte_5g_nsa'
                )
            )

            if saw_lte and saw_nsa:
                item[
                    'technology_role'
                ] = (
                    'LTE PCell / NSA Anchor'
                )

            elif saw_nsa:
                item[
                    'technology_role'
                ] = 'LTE Anchor'

            elif saw_lte:
                item[
                    'technology_role'
                ] = 'LTE PCell'

            else:
                item[
                    'technology_role'
                ] = 'Primary Cell'

        item['display_name'] = (
            _UNKNOWN_LABEL
            if is_unknown
            else 'Serving Cell %s'
            % item['view_label']
        )

    return result


def _timeline(records, cells):
    labels = {item['key']: item.get('view_label', '') for item in cells}
    segments = []
    for record in records:
        cell = _serving_cell_for_record(record)
        key = _cell_key(cell)
        timestamp = _text(record.get('timestamp'))
        if segments and segments[-1]['key'] == key:
            segments[-1]['tests'] += 1
            segments[-1]['end'] = timestamp
            continue
        segments.append({
            'key': key,
            'label': labels.get(key, 'Unknown'),
            'start': timestamp,
            'end': timestamp,
            'tests': 1,
        })
    return segments


def _timeline_events(records, cells):
    """Return proven in-test handoffs for timeline marker rendering.

    These events intentionally do not become long timeline segments because
    the app does not continuously observe the modem between scheduled tests.
    """
    labels = {
        item['key']: item.get(
            'view_label',
            ''
        )
        for item in cells
    }

    events = []

    for record in records:
        timestamp = _text(
            record.get('timestamp')
        )

        summary = (
            _traffic_serving_cell_summary(
                record
            )
        )

        for handoff in summary.get(
            'handoffs',
            []
        ):
            from_cell = handoff.get(
                'from'
            )
            to_cell = handoff.get(
                'to'
            )

            from_key = _cell_key(
                from_cell
            )
            to_key = _cell_key(
                to_cell
            )

            event = {
                'timestamp': timestamp,
                'phase': handoff.get(
                    'phase',
                    ''
                ),
                'elapsed_s': handoff.get(
                    'elapsed_s',
                    0.0
                ),
                'phase_boundary': bool(
                    handoff.get(
                        'phase_boundary'
                    )
                ),
                'from': dict(
                    from_cell
                ),
                'to': dict(
                    to_cell
                ),
                'from_key': from_key,
                'to_key': to_key,
                'from_label': labels.get(
                    from_key,
                    ''
                ),
                'to_label': labels.get(
                    to_key,
                    ''
                ),
            }

            events.append(event)

    return events


def _technology_usage(records):
    counts = {'lte_only': 0, 'lte_5g_nsa': 0, '5g_sa': 0, 'unknown': 0}
    for record in records:
        counts[_network_mode(record)] += 1
    total = len(records)
    result = []
    for mode in ('lte_only', 'lte_5g_nsa', '5g_sa', 'unknown'):
        count = counts[mode]
        if not count:
            continue
        result.append({
            'mode': mode,
            'label': _network_mode_label(mode),
            'tests': count,
            'usage_pct': round(count / total * 100.0, 1) if total else 0.0,
        })
    return result


def _components_match(previous, current):
    """Return True when two observations identify the same radio component.

    Component identity is RAT + band plus an explicit channel and/or PCI.

    Channel and PCI are supplemental identifiers:
    - when both sides report a field, conflicting values reject the match;
    - when only one side reports PCI, a stable explicit channel can still
      identify the component;
    - at least one explicit shared discriminator must match.

    Role and bandwidth are intentionally excluded because SCell roles may move
    and bandwidth is component state rather than component identity.
    """
    previous_identity = _carrier_identity(previous)
    current_identity = _carrier_identity(current)

    previous_rat, previous_band, previous_channel, previous_pci = (
        previous_identity
    )

    current_rat, current_band, current_channel, current_pci = (
        current_identity
    )

    if (
        previous_rat != current_rat
        or previous_band != current_band
    ):
        return False

    channel_match = bool(
        previous_channel
        and current_channel
        and previous_channel == current_channel
    )

    pci_match = bool(
        previous_pci
        and current_pci
        and previous_pci == current_pci
    )

    if (
        previous_channel
        and current_channel
        and previous_channel != current_channel
    ):
        return False

    if (
        previous_pci
        and current_pci
        and previous_pci != current_pci
    ):
        return False

    return channel_match or pci_match


def _component_bandwidth_changed(previous_snapshot, current_snapshot):
    """Detect changed MHz allocation on the same identifiable component.

    Matching is one-to-one and intentionally ignores SCell role movement.
    """
    previous = _normalized_carriers(previous_snapshot)
    current = _normalized_carriers(current_snapshot)

    for previous_carrier in previous:
        matches = [
            current_carrier
            for current_carrier in current
            if _components_match(
                previous_carrier,
                current_carrier
            )
        ]

        # Ambiguous identity is not enough evidence for a bandwidth change.
        if len(matches) != 1:
            continue

        current_carrier = matches[0]

        reverse_matches = [
            candidate
            for candidate in previous
            if _components_match(
                candidate,
                current_carrier
            )
        ]

        if len(reverse_matches) != 1:
            continue

        previous_bandwidth = _normalize_bandwidth(
            previous_carrier.get('bandwidth_mhz')
        )

        current_bandwidth = _normalize_bandwidth(
            current_carrier.get('bandwidth_mhz')
        )

        if (
            previous_bandwidth is not None
            and current_bandwidth is not None
            and previous_bandwidth != current_bandwidth
        ):
            return True

    return False



def _total_observed_bandwidth(snapshot):
    """Return summed active component-carrier bandwidth in MHz.

    This intentionally uses the same normalized carrier data represented by
    Peak Observed Radio Configurations. Missing/unusable bandwidth does not
    become zero and therefore cannot manufacture a false transition.
    """
    carriers = _normalized_carriers(snapshot)

    if not carriers:
        return None

    total = 0.0
    observed = False

    for carrier in carriers:
        bandwidth = _normalize_bandwidth(
            carrier.get('bandwidth_mhz')
        )

        if bandwidth is None:
            continue

        observed = True

        if bandwidth > 0:
            total += bandwidth

    if not observed:
        return None

    return round(total, 3)


def _bandwidth_changed(previous_snapshot, current_snapshot):
    """Return True when total Peak Observed bandwidth changed.

    The Cellular Change Activity tile intentionally measures total available
    radio bandwidth between consecutive tests rather than requiring the same
    physical component carrier to change its individual channel width.
    """
    previous_total = _total_observed_bandwidth(
        previous_snapshot
    )

    current_total = _total_observed_bandwidth(
        current_snapshot
    )

    if previous_total is None or current_total is None:
        return False

    return previous_total != current_total


def _change_activity(records):
    counters = {
        'serving_cell_changes': 0,
        'in_test_serving_cell_changes': 0,
        'between_test_serving_cell_changes': 0,
        'peak_config_changes': 0,
        'bandwidth_changes': 0,
        'network_mode_changes': 0,
    }

    summaries = [
        _traffic_serving_cell_summary(
            record
        )
        for record in records
    ]

    for summary in summaries:
        count = len(
            summary.get(
                'handoffs',
                []
            )
        )

        counters[
            'in_test_serving_cell_changes'
        ] += count

    for index, record in enumerate(records):
        if index > 0:
            previous = records[index - 1]

            previous_summary = summaries[
                index - 1
            ]

            current_summary = summaries[
                index
            ]

            previous_cell = (
                previous_summary.get(
                    'end_cell'
                )
            )

            current_cell = (
                current_summary.get(
                    'start_cell'
                )
            )

            previous_key = _cell_key(
                previous_cell
            )

            current_key = _cell_key(
                current_cell
            )

            if (
                previous_key
                != _UNKNOWN_CELL_KEY
                and current_key
                != _UNKNOWN_CELL_KEY
                and previous_key
                != current_key
            ):
                counters[
                    'between_test_serving_cell_changes'
                ] += 1

            previous_peak, _ = _active_peak(
                previous
            )

            current_peak, _ = _active_peak(
                record
            )

            previous_sig = _config_signature(
                previous_peak
            )

            current_sig = _config_signature(
                current_peak
            )

            if (
                previous_sig
                and current_sig
                and previous_sig
                != current_sig
            ):
                counters[
                    'peak_config_changes'
                ] += 1

                if _bandwidth_changed(
                    previous_peak,
                    current_peak
                ):
                    counters[
                        'bandwidth_changes'
                    ] += 1

            previous_mode = _network_mode(
                previous,
                previous_summary.get(
                    'end_cell'
                )
            )

            current_mode = _network_mode(
                record,
                current_summary.get(
                    'start_cell'
                )
            )

            if (
                previous_mode != 'unknown'
                and current_mode != 'unknown'
                and previous_mode
                != current_mode
            ):
                counters[
                    'network_mode_changes'
                ] += 1

    counters['serving_cell_changes'] = (
        counters[
            'in_test_serving_cell_changes'
        ]
        + counters[
            'between_test_serving_cell_changes'
        ]
    )

    return counters


def _rf_stats(records, selected_source):
    metrics = {
        'rsrp': [],
        'rsrq': [],
        'sinr': [],
    }
    health = {}

    for record in records:
        cellular = record.get('cellular')
        if not isinstance(cellular, dict):
            continue
        # SA serving-cell identity is reported as NR_CELL_ID.
        # Treat both normalized NR and NR_CELL_ID sources as NR RF scope.
        is_nr_serving_cell = selected_source in (
            'NR',
            'NR_CELL_ID',
        )

        suffix = '_5g' if is_nr_serving_cell else ''
        for metric in ('rsrp', 'rsrq', 'sinr'):
            value = _number(cellular.get(metric + suffix))
            if value is not None:
                metrics[metric].append(value)
        category = _text(cellular.get('cellular_health_category'))
        if category:
            health[category] = health.get(category, 0) + 1

    result = {}
    for metric, values in metrics.items():
        if not values:
            result[metric] = {'count': 0, 'avg': None, 'best': None, 'worst': None}
            continue
        # Higher is better for RSRP/RSRQ/SINR (less negative or more positive).
        result[metric] = {
            'count': len(values),
            'avg': round(sum(values) / len(values), 1),
            'best': round(max(values), 1),
            'worst': round(min(values), 1),
        }

    health_total = sum(health.values())
    result['health'] = [
        {
            'category': category,
            'tests': count,
            'usage_pct': round(count / health_total * 100.0, 1) if health_total else 0.0,
        }
        for category, count in sorted(health.items(), key=lambda item: (-item[1], item[0]))
    ]
    return result


def _radio_configurations(records):
    buckets = {}
    eligible = 0
    for record in records:
        peak, source = _active_peak(record)
        signature = _config_signature(peak)
        if not signature:
            continue
        eligible += 1
        key = repr(signature)
        bucket = buckets.setdefault(key, {
            'signature': signature,
            'label': _format_configuration(peak),
            'tests': 0,
            'source': source,
            'carriers': _normalized_carriers(peak),
        })
        bucket['tests'] += 1

    result = sorted(
        buckets.values(),
        key=lambda item: (-item['tests'], item['label'])
    )

    for item in result:
        total_bandwidth = 0.0

        for carrier in item.get('carriers', []):
            bandwidth = carrier.get('bandwidth_mhz')

            try:
                bandwidth = float(bandwidth)
            except (TypeError, ValueError):
                continue

            if bandwidth > 0:
                total_bandwidth += bandwidth

        if total_bandwidth.is_integer():
            total_bandwidth = int(total_bandwidth)
        else:
            total_bandwidth = round(total_bandwidth, 1)

        item['total_bandwidth_mhz'] = total_bandwidth
        item['usage_pct'] = round(
            item['tests'] / eligible * 100.0,
            1
        ) if eligible else 0.0

        item['signature'] = [
            list(part)
            for part in item['signature']
        ]

    return result, eligible


def _record_observes_cell(record, selected_key):
    """Return True when a record contains the selected traffic-active cell."""
    if not selected_key:
        return False

    summary = _traffic_serving_cell_summary(
        record
    )

    for cell in summary.get(
        'cells_observed',
        []
    ):
        if _cell_key(cell) == selected_key:
            return True

    return False


def _traffic_snapshot_candidates(record):
    """Return snapshots captured during successful Download/Upload traffic."""
    activity = record.get(
        'carrier_activity'
    )

    if not isinstance(activity, dict):
        return []

    snapshots = []

    for phase_name in (
        'download',
        'upload',
    ):
        phase = activity.get(
            phase_name
        )

        if not isinstance(phase, dict):
            continue

        baseline = phase.get(
            'baseline'
        )

        if isinstance(baseline, dict):
            snapshots.append(
                baseline
            )

        timeline = phase.get(
            'timeline'
        )

        if isinstance(timeline, list):
            for snapshot in timeline:
                if isinstance(snapshot, dict):
                    snapshots.append(
                        snapshot
                    )

        peak = phase.get(
            'peak'
        )

        if isinstance(peak, dict):
            snapshots.append(
                peak
            )

    return snapshots


def _selected_cell_peak_for_record(
    record,
    selected_key,
):
    """Return the strongest active-traffic snapshot for one serving cell.

    Candidate snapshots must explicitly identify the selected serving cell.
    The strongest snapshot uses the same general Peak Observed preference:
    greatest usable carrier count, then greatest total observed bandwidth.

    Legacy records without phase timing retain the existing _active_peak
    fallback, but only when their representative cell is the selected cell.
    """
    candidates = []

    for snapshot in _traffic_snapshot_candidates(
        record
    ):
        cell = _snapshot_serving_cell(
            snapshot
        )

        if _cell_key(cell) != selected_key:
            continue

        carriers = _normalized_carriers(
            snapshot
        )

        if not carriers:
            continue

        total_bw = _total_observed_bandwidth(
            snapshot
        )

        candidates.append((
            len(carriers),
            (
                float(total_bw)
                if total_bw is not None
                else -1.0
            ),
            snapshot,
        ))

    if candidates:
        candidates.sort(
            key=lambda item: (
                item[0],
                item[1],
            ),
            reverse=True,
        )

        return (
            candidates[0][2],
            'selected_cell_traffic_peak',
        )

    representative = _serving_cell_for_record(
        record
    )

    if _cell_key(representative) != selected_key:
        return None, ''

    peak, source = _active_peak(
        record
    )

    return peak, source


def _radio_configurations_from_snapshots(
    snapshots,
):
    """Build radio-configuration distribution from one snapshot per test."""
    buckets = {}
    eligible = 0

    for snapshot, source in snapshots:
        signature = _config_signature(
            snapshot
        )

        if not signature:
            continue

        eligible += 1
        key = repr(signature)

        bucket = buckets.setdefault(
            key,
            {
                'signature': signature,
                'label': _format_configuration(
                    snapshot
                ),
                'tests': 0,
                'source': source,
                'carriers': _normalized_carriers(
                    snapshot
                ),
            },
        )

        bucket['tests'] += 1

    result = sorted(
        buckets.values(),
        key=lambda item: (
            -item['tests'],
            item['label'],
        ),
    )

    for item in result:
        total_bandwidth = 0.0

        for carrier in item.get(
            'carriers',
            []
        ):
            bandwidth = _normalize_bandwidth(
                carrier.get(
                    'bandwidth_mhz'
                )
            )

            if bandwidth is None:
                continue

            if bandwidth > 0:
                total_bandwidth += bandwidth

        if total_bandwidth.is_integer():
            total_bandwidth = int(
                total_bandwidth
            )
        else:
            total_bandwidth = round(
                total_bandwidth,
                1,
            )

        item[
            'total_bandwidth_mhz'
        ] = total_bandwidth

        item['usage_pct'] = round(
            (
                item['tests']
                / eligible
                * 100.0
            ),
            1,
        ) if eligible else 0.0

        item['signature'] = [
            list(part)
            for part in item['signature']
        ]

    return result, eligible


def _primary_carrier_for_serving_cell(
    snapshot,
    cell,
):
    """Return the radio carrier corresponding to the serving primary cell."""
    if not isinstance(cell, dict):
        return None

    carriers = _normalized_carriers(
        snapshot
    )

    if not carriers:
        return None

    source = _text(
        cell.get(
            'cell_id_source'
        )
    ).upper()

    service_mode = _text(
        cell.get(
            'service_mode'
        )
    )

    expected_rat = (
        'NR'
        if (
            source in (
                'NR',
                'NR_CELL_ID',
            )
            or service_mode == '5G SA'
        )
        else 'LTE'
    )

    target_band = _normalize_band(
        cell.get('band'),
        expected_rat,
    )

    target_channel = _normalize_channel(
        cell.get('channel')
    )

    target_pci = _normalize_pci(
        cell.get('pci')
    )

    compatible = []

    for carrier in carriers:
        if carrier.get('rat') != expected_rat:
            continue

        carrier_band = _normalize_band(
            carrier.get('band'),
            expected_rat,
        )

        carrier_channel = _normalize_channel(
            carrier.get('channel')
        )

        carrier_pci = _normalize_pci(
            carrier.get('pci')
        )

        if (
            target_band
            and carrier_band
            and target_band != carrier_band
        ):
            continue

        if (
            target_channel
            and carrier_channel
            and target_channel != carrier_channel
        ):
            continue

        if (
            target_pci
            and carrier_pci
            and target_pci != carrier_pci
        ):
            continue

        score = 0

        if (
            target_channel
            and carrier_channel
            and target_channel == carrier_channel
        ):
            score += 4

        if (
            target_pci
            and carrier_pci
            and target_pci == carrier_pci
        ):
            score += 4

        if (
            target_band
            and carrier_band
            and target_band == carrier_band
        ):
            score += 2

        if _carrier_role_is_primary(
            carrier.get('role')
        ):
            score += 1

        compatible.append(
            (
                score,
                carrier,
            )
        )

    if compatible:
        compatible.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        return compatible[0][1]

    # Last-resort fallback when NCOS omitted primary-cell identity fields.
    primary = [
        carrier
        for carrier in carriers
        if (
            carrier.get('rat')
            == expected_rat
            and _carrier_role_is_primary(
                carrier.get('role')
            )
        )
    ]

    if len(primary) == 1:
        return primary[0]

    return None


def _selected_cell_rf(
    records,
    selected_key,
):
    """Build RF statistics from traffic telemetry belonging to one cell."""
    metrics = {
        'rsrp': [],
        'rsrq': [],
        'sinr': [],
    }

    health = {}

    for record in records:
        peak, _ = _selected_cell_peak_for_record(
            record,
            selected_key,
        )

        peak_cell = _snapshot_serving_cell(
            peak
        )

        primary = (
            _primary_carrier_for_serving_cell(
                peak,
                peak_cell,
            )
            if peak_cell is not None
            else None
        )

        used_traffic_rf = False

        if isinstance(primary, dict):
            for metric in (
                'rsrp',
                'rsrq',
                'sinr',
            ):
                value = _number(
                    primary.get(metric)
                )

                if value is not None:
                    metrics[metric].append(
                        value
                    )
                    used_traffic_rf = True

        cellular = record.get(
            'cellular'
        )

        if not isinstance(cellular, dict):
            continue

        final_cell = _serving_cell_from_cellular(
            cellular
        )

        final_matches = (
            _cell_key(final_cell)
            == selected_key
        )

        # Older retained records may have useful top-level RF telemetry
        # without enough PLMN/TAC metadata to reproduce the complete
        # serving-cell key. Only relax the match when the test observed
        # exactly one identifiable traffic-active serving cell. A record
        # with multiple observed cells must retain the strict final-cell
        # match so RF cannot be attributed to the wrong side of a handoff.
        summary = _traffic_serving_cell_summary(
            record
        )

        known_observed = [
            observed
            for observed in summary.get(
                'cells_observed',
                []
            )
            if _cell_key(observed)
            != _UNKNOWN_CELL_KEY
        ]

        legacy_stable_match = (
            len(known_observed) == 1
            and _cell_key(
                known_observed[0]
            ) == selected_key
        )

        final_or_legacy_matches = (
            final_matches
            or legacy_stable_match
        )

        # Backward compatibility for older retained history that did not
        # preserve per-carrier RF values during the traffic phases.
        if (
            not used_traffic_rf
            and final_or_legacy_matches
        ):
            source = _text(
                final_cell.get(
                    'cell_id_source'
                )
            ).upper()

            is_nr = source in (
                'NR',
                'NR_CELL_ID',
            )

            suffix = (
                '_5g'
                if is_nr
                else ''
            )

            for metric in (
                'rsrp',
                'rsrq',
                'sinr',
            ):
                value = _number(
                    cellular.get(
                        metric + suffix
                    )
                )

                if value is not None:
                    metrics[metric].append(
                        value
                    )

        # Health is a final modem-state observation, so only attribute it
        # to the serving cell that owns that final snapshot.
        if final_or_legacy_matches:
            category = _text(
                cellular.get(
                    'cellular_health_category'
                )
            )

            if category:
                health[category] = (
                    health.get(
                        category,
                        0
                    )
                    + 1
                )

    result = {}

    for metric, values in metrics.items():
        if not values:
            result[metric] = {
                'count': 0,
                'avg': None,
                'best': None,
                'worst': None,
            }
            continue

        result[metric] = {
            'count': len(values),
            'avg': round(
                sum(values) / len(values),
                1,
            ),
            'best': round(
                max(values),
                1,
            ),
            'worst': round(
                min(values),
                1,
            ),
        }

    health_total = sum(
        health.values()
    )

    result['health'] = [
        {
            'category': category,
            'tests': count,
            'usage_pct': round(
                count
                / health_total
                * 100.0,
                1,
            ) if health_total else 0.0,
        }
        for category, count
        in sorted(
            health.items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        )
    ]

    return result


def _selected_cell(records, cells, selected_key=''):
    known = [
        cell
        for cell in cells
        if cell.get('key') != _UNKNOWN_CELL_KEY
    ]

    if not known:
        return None

    cell = None

    if selected_key:
        cell = next(
            (
                item
                for item in known
                if item.get('key')
                == selected_key
            ),
            None,
        )

    if cell is None:
        cell = known[0]

    cell_records = [
        record
        for record in records
        if _record_observes_cell(
            record,
            cell['key'],
        )
    ]

    selected_snapshots = []

    for record in cell_records:
        peak, source = (
            _selected_cell_peak_for_record(
                record,
                cell['key'],
            )
        )

        if isinstance(peak, dict):
            selected_snapshots.append(
                (
                    peak,
                    source,
                )
            )

    configs, config_eligible = (
        _radio_configurations_from_snapshots(
            selected_snapshots
        )
    )

    detail = dict(cell)

    detail['technology_usage'] = (
        _technology_usage(
            cell_records
        )
    )

    detail['rf'] = _selected_cell_rf(
        cell_records,
        cell['key'],
    )

    detail[
        'radio_configurations'
    ] = configs

    detail[
        'radio_configuration_tests'
    ] = config_eligible

    return detail




def build_site_cell_inventory(history):
    """Build site-wide serving-cell inventory across all retained history.

    GeoView intentionally ignores the lower-page interface and date filters.
    It represents every identifiable serving cell observed by every cellular
    interface in the retained local history. The existing traffic-aware cell
    engine remains authoritative, so cells seen only during an in-test handoff
    are preserved here as well.
    """
    history = history if isinstance(history, list) else []

    records = [
        record
        for record in history
        if _is_cellular_history_record(record)
    ]

    records.sort(
        key=lambda record: (
            _parse_timestamp(record.get('timestamp'))
            or datetime.min
        )
    )

    cells = [
        dict(cell)
        for cell in _cell_distribution(records)
        if cell.get('key') != _UNKNOWN_CELL_KEY
    ]

    cells_by_key = {
        cell.get('key'): cell
        for cell in cells
        if cell.get('key')
    }

    observed_by_interface = {
        key: {}
        for key in cells_by_key
    }

    for record in records:
        interface = _record_interface(record)
        interface_label = (
            _text(record.get('interface_label'))
            or interface
        )

        summary = _traffic_serving_cell_summary(record)
        observed_cells = summary.get('cells_observed', [])

        if not observed_cells:
            fallback = _serving_cell_for_record(record)
            if _cell_key(fallback) != _UNKNOWN_CELL_KEY:
                observed_cells = [fallback]

        final_cell = _serving_cell_for_record(record)
        final_key = _cell_key(final_cell)

        per_test_keys = set()

        for observed in observed_cells:
            key = _cell_key(observed)

            if (
                key == _UNKNOWN_CELL_KEY
                or key not in cells_by_key
                or key in per_test_keys
            ):
                continue

            per_test_keys.add(key)
            inventory_cell = cells_by_key[key]

            # Traffic snapshots are authoritative for identity. The final
            # snapshot may carry richer descriptive metadata for the same
            # cell, so use it only to fill missing display attributes.
            candidates = [observed]

            if final_key == key:
                candidates.append(final_cell)

            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue

                for attr in (
                    'carrier',
                    'plmn',
                    'tac',
                    'pci',
                    'band',
                    'channel',
                    'cell_id_source',
                ):
                    if (
                        not inventory_cell.get(attr)
                        and candidate.get(attr)
                    ):
                        inventory_cell[attr] = candidate.get(attr)

            interface_bucket = observed_by_interface[key].setdefault(
                interface,
                {
                    'interface': interface,
                    'label': interface_label,
                    'tests': 0,
                },
            )

            interface_bucket['tests'] += 1

            # Prefer a human-friendly label whenever a later record supplies
            # one for the same NCOS interface identifier.
            if (
                interface_label
                and (
                    not interface_bucket.get('label')
                    or interface_bucket.get('label') == interface
                )
            ):
                interface_bucket['label'] = interface_label

    for cell in cells:
        interface_rows = list(
            observed_by_interface.get(
                cell.get('key'),
                {},
            ).values()
        )

        interface_rows.sort(
            key=lambda item: (
                -int(item.get('tests', 0) or 0),
                _text(item.get('label')).lower(),
            )
        )

        cell['interfaces'] = interface_rows
        cell['interface_count'] = len(interface_rows)

    return {
        'tests': len(records),
        'cells': cells,
        'interfaces': _history_interfaces(records),
    }

def build_cellular_analysis(history, interface='', scope='all', selected_cell_key='', now=None):
    """Build the complete local Cellular Analysis response from history."""
    history = history if isinstance(history, list) else []
    interfaces = _history_interfaces(history)

    selected_interface = _text(interface)
    available = {item['interface'] for item in interfaces}
    if selected_interface not in available:
        selected_interface = interfaces[0]['interface'] if interfaces else ''

    records = _scope_records(history, selected_interface, scope, now=now) if selected_interface else []
    cells = _cell_distribution(records)
    technology = _technology_usage(records)
    changes = _change_activity(records)
    selected_cell = _selected_cell(records, cells, selected_cell_key)

    dominant = next((cell for cell in cells if cell.get('key') != _UNKNOWN_CELL_KEY), None)

    return {
        'schema_version': _SCHEMA_VERSION,
        'geo': {
            'provider': 'none',
            'configured': False,
            'status': 'not_configured',
        },
        'interfaces': interfaces,
        'scope': {
            'interface': selected_interface,
            'interface_label': next((item['label'] for item in interfaces if item['interface'] == selected_interface), selected_interface),
            'history': _text(scope).lower() or 'all',
            'tests_analyzed': len(records),
        },
        'overview': {
            'tests_analyzed': len(records),
            'serving_cells_observed': len([cell for cell in cells if cell.get('key') != _UNKNOWN_CELL_KEY]),
            'dominant_cell': {
                'key': dominant.get('key'),
                'label': dominant.get('view_label'),
                'tests': dominant.get('tests'),
                'usage_pct': dominant.get('usage_pct'),
            } if dominant else None,
            'network_modes': technology,
        },
        'serving_cells': cells,
        'timeline': _timeline(records, cells),
        'timeline_events': _timeline_events(
            records,
            cells,
        ),
        'change_activity': changes,
        'selected_cell': selected_cell,
    }
