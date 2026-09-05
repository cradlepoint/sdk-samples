"""OpenCellID observation contribution (v1.1.3).

Isolated contribution logic so the narrow "share where a serving cell was
observed" feature never leaks into the OpenCellID *lookup* path, the resolve
job, the cache, or Cellular Analysis RF/timeline logic.

Contribution posts the geographic position where the ROUTER observed a serving
cell (Device GPS lock, or the validated Manual Site coordinates) to
OpenCellID's ``/measure/add``. It NEVER submits the OpenCellID estimated tower
coordinates.

Hard rules (from the feature spec):
    * Only Internal / Captive cellular modem observations are eligible. Never
      Ethernet, Wi-Fi, Satellite, external/generic modems, or anything without
      a complete authoritative serving identity.
    * Primary identity only: LTE -> LTE primary ECI; NSA -> LTE anchor ECI;
      SA -> NR primary NCI. Never fabricate an SCell identity.
    * Dedupe via a persistent ledger keyed by complete serving identity
      (RAT semantics + MCC + MNC + TAC + ECI/NCI). Same cell within 20 m of the
      last successfully contributed position is SKIPPED; >= 20 m is eligible
      again. A different cell is eligible immediately, even at the same coords.
    * The ledger is updated ONLY after OpenCellID acknowledges success.

Security posture: this module never logs the OpenCellID key, request body,
credentialed URL, or a plaintext provider response that could contain secrets.
The ledger stores NO credentials.
"""

import json
import os
import tempfile
import threading
import time

import cp
import geo_identity
import geo_providers
import geo_secrets


# Persistent, credential-free contribution ledger (relative to app working dir,
# like tmp/history and the geo cell cache).
LEDGER_FILE = 'tmp/geoview_contribution_ledger.json'
LEDGER_SCHEMA_VERSION = 1

# Same-cell dedupe distance. < 20 m from the last successful contributed
# position for the SAME identity -> skip; >= 20 m -> eligible again.
DEDUPE_MIN_METERS = 20.0

_lock = threading.RLock()


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def _distance_sq_m(lat1, lon1, lat2, lon2):
    """Approximate short-distance squared meters without the NCOS math module."""
    lat1 = float(lat1)
    lon1 = float(lon1)
    lat2 = float(lat2)
    lon2 = float(lon2)

    # Equirectangular distance is appropriate for the 20 m same-cell dedupe
    # threshold. Approximate cos(mid-latitude) with a Taylor polynomial so the
    # NCOS reduced Python runtime does not require the math module.
    mid_lat_rad = ((lat1 + lat2) / 2.0) * 0.017453292519943295
    x2 = mid_lat_rad * mid_lat_rad
    cos_lat = (1.0 - (x2 / 2.0)
               + ((x2 * x2) / 24.0)
               - ((x2 * x2 * x2) / 720.0)
               + ((x2 * x2 * x2 * x2) / 40320.0))

    dlon = lon2 - lon1
    if dlon > 180.0:
        dlon -= 360.0
    elif dlon < -180.0:
        dlon += 360.0

    north_m = (lat2 - lat1) * 111132.0
    east_m = dlon * 111320.0 * cos_lat
    return (north_m * north_m) + (east_m * east_m)


def _valid_coords(lat, lon):
    """Return (lat, lon) floats when a usable, nonzero pair, else None."""
    try:
        flat = float(lat)
        flon = float(lon)
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= flat <= 90.0) or not (-180.0 <= flon <= 180.0):
        return None
    if flat == 0.0 and flon == 0.0:
        return None
    return (flat, flon)


# ---------------------------------------------------------------------------
# Ledger (atomic, schema-guarded, no credentials)
# ---------------------------------------------------------------------------
def _ledger_identity_key(identity):
    """Stable dedupe key: RAT semantics + MCC + MNC + TAC + ECI/NCI."""
    semantics = str(identity.get('semantics') or '').lower()
    mcc = identity.get('mcc')
    mnc = identity.get('mnc')
    lac = identity.get('lac')
    value = identity.get('value')
    return '%s|%s|%s|%s|%s' % (
        semantics,
        '' if mcc is None else mcc,
        '' if mnc is None else mnc,
        '' if lac is None else lac,
        '' if value is None else value)


def _load_ledger(path):
    """Load the ledger dict {key: {lat, lon, timestamp}}. Never raises."""
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, 'r') as handle:
            doc = json.load(handle)
    except Exception as exc:
        cp.log('GeoView contribution ledger load skipped: %s'
               % geo_secrets.scrub(exc))
        return {}
    if (not isinstance(doc, dict)
            or doc.get('schema_version') != LEDGER_SCHEMA_VERSION):
        return {}
    entries = doc.get('entries')
    if not isinstance(entries, dict):
        return {}
    clean = {}
    for key, entry in entries.items():
        if not isinstance(entry, dict):
            continue
        pair = _valid_coords(entry.get('lat'), entry.get('lon'))
        if pair is None:
            continue
        clean[key] = {'lat': pair[0], 'lon': pair[1],
                      'timestamp': entry.get('timestamp')}
    return clean


def _save_ledger(path, entries):
    """Atomically write the ledger. Best-effort; never raises."""
    if not path:
        return
    doc = {'schema_version': LEDGER_SCHEMA_VERSION, 'entries': entries}
    directory = os.path.dirname(path) or '.'
    try:
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=directory,
                                        prefix='geoview_contribution_ledger.',
                                        suffix='.tmp')
        try:
            with os.fdopen(fd, 'w') as handle:
                json.dump(doc, handle, separators=(',', ':'))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
    except Exception as exc:
        cp.log('GeoView contribution ledger save skipped: %s'
               % geo_secrets.scrub(exc))


def _should_skip(ledger, ident_key, lat, lon):
    """True when the same identity was contributed < 20 m from (lat, lon)."""
    prev = ledger.get(ident_key)
    if not isinstance(prev, dict):
        return False
    prev_pair = _valid_coords(prev.get('lat'), prev.get('lon'))
    if prev_pair is None:
        return False
    return (_distance_sq_m(prev_pair[0], prev_pair[1], lat, lon)
            < (DEDUPE_MIN_METERS * DEDUPE_MIN_METERS))


def _record_success(path, ledger, ident_key, lat, lon):
    """Persist a successful contribution for dedupe. Caller holds ``_lock``."""
    ledger[ident_key] = {'lat': lat, 'lon': lon,
                         'timestamp': int(time.time())}
    _save_ledger(path, ledger)


# ---------------------------------------------------------------------------
# Observation shaping (primary serving identity only)
# ---------------------------------------------------------------------------
def _rsrp_for_identity(cell, identity):
    """Primary LTE/NR RSRP for the observation, else None.

    ``signal`` is optional and LTE/NR RSRP only. When unavailable/invalid it is
    omitted upstream. The inventory cell carries the last observed primary
    ``rsrp`` when present.
    """
    if not isinstance(cell, dict):
        return None
    raw = cell.get('rsrp')
    if raw in (None, ''):
        return None
    try:
        val = int(round(float(raw)))
    except (TypeError, ValueError):
        return None
    # RSRP is a negative dBm value; guard obviously invalid ranges.
    if val < -157 or val > -20:
        return None
    return val


def _pci_for_identity(cell, identity):
    """LTE-only PCI in 0..503, else None (omitted upstream)."""
    if identity.get('semantics') != geo_identity.SEMANTICS_ECI:
        return None
    if not isinstance(cell, dict):
        return None
    raw = cell.get('pci')
    if raw in (None, ''):
        return None
    try:
        pci = int(raw)
    except (TypeError, ValueError):
        return None
    return pci if 0 <= pci <= 503 else None


def build_measurement(identity, cell, lat, lon, measured_at_ms=None):
    """Build the normalized measurement payload for one eligible cell.

    ``identity`` is a ``geo_identity.NormalizedIdentity``. ``cell`` is the
    matching site-inventory cell (for optional signal/pci). Returns a dict of
    the mandatory fields plus any valid optional fields. Contribution location
    is ALWAYS (lat, lon) -- where the router observed the cell.
    """
    act = 'NR' if identity.semantics == geo_identity.SEMANTICS_NCI else 'LTE'
    measurement = {
        'lat': lat,
        'lon': lon,
        'mcc': identity.mcc,
        'mnc': identity.mnc,
        'tac': identity.lac,
        'cellid': identity.value,
        'act': act,
    }
    if measured_at_ms is not None:
        try:
            measurement['measured_at'] = int(measured_at_ms)
        except (TypeError, ValueError):
            pass
    signal = _rsrp_for_identity(cell, identity.to_request())
    if signal is not None:
        measurement['signal'] = signal
    pci = _pci_for_identity(cell, identity.to_request())
    if pci is not None:
        measurement['pci'] = pci
    return measurement


# ---------------------------------------------------------------------------
# Submission (single measurement)
# ---------------------------------------------------------------------------
def _submit_one(adapter, ledger, path, identity, measurement):
    """Submit one measurement, updating the ledger on acknowledged success.

    Returns one of: 'submitted', 'skipped', 'failed'. Applies the 20 m
    same-cell dedupe BEFORE the network call.
    """
    ident_key = _ledger_identity_key(identity.to_request())
    lat = measurement['lat']
    lon = measurement['lon']

    with _lock:
        if _should_skip(ledger, ident_key, lat, lon):
            return 'skipped'

    result = adapter.submit_measurement(measurement)
    if result.get('status') == geo_providers.STATUS_OK:
        with _lock:
            _record_success(path, ledger, ident_key, lat, lon)
        return 'submitted'
    return 'failed'


# ---------------------------------------------------------------------------
# Automatic (Device GPS) contribution -- single completed test result
# ---------------------------------------------------------------------------
def contribute_from_completed_test(bundle, cells, lat, lon,
                                   interface_eligible, measured_at_ms=None,
                                   ledger_path=LEDGER_FILE, timeout=10.0):
    """Silently contribute eligible cells from ONE completed cellular test.

    ``bundle`` is the transient OpenCellID credential bundle. ``cells`` is the
    serving-cell set for the completed test (already scoped to that test's
    interface). ``lat``/``lon`` is the router's observed position (a valid GPS
    lock). ``interface_eligible`` gates on Internal/Captive classification.

    Silent: returns a small counts dict for diagnostics only; the caller must
    not surface a toast/popup. Never raises.
    """
    counts = {'submitted': 0, 'skipped': 0, 'failed': 0, 'eligible': 0}
    if not interface_eligible:
        return counts
    pair = _valid_coords(lat, lon)
    if pair is None:
        return counts

    try:
        eligible, _ineligible = geo_identity.normalize_inventory(cells)
        if not eligible:
            return counts
        adapter = geo_providers.build_contributor(bundle, timeout=timeout)
    except Exception as exc:
        cp.log('GeoView auto-contribution setup skipped: %s'
               % geo_secrets.scrub(exc))
        return counts

    cells_by_key = {}
    for cell in (cells or []):
        if isinstance(cell, dict) and cell.get('key'):
            cells_by_key.setdefault(cell.get('key'), cell)

    with _lock:
        ledger = _load_ledger(ledger_path)

    for identity in eligible:
        counts['eligible'] += 1
        cell = cells_by_key.get(identity.cell_key) or {}
        measurement = build_measurement(identity, cell, pair[0], pair[1],
                                        measured_at_ms=measured_at_ms)
        try:
            outcome = _submit_one(adapter, ledger, ledger_path, identity,
                                  measurement)
        except Exception as exc:
            cp.log('GeoView auto-contribution error: %s'
                   % geo_secrets.scrub(exc))
            outcome = 'failed'
        counts[outcome] = counts.get(outcome, 0) + 1

    return counts


# ---------------------------------------------------------------------------
# Manual (Site coordinates) contribution -- scan retained history
# ---------------------------------------------------------------------------
def _most_recent_eligible_observations(cells):
    """Return one (identity, cell) per unique primary serving identity.

    ``cells`` is the site inventory already hard-filtered to Internal/Captive
    cellular observations by the caller. De-duplication to a unique identity is
    handled by ``normalize_inventory``; the inventory cell carries the most
    recent observed descriptive metadata for that cell.
    """
    eligible, _ineligible = geo_identity.normalize_inventory(cells)
    cells_by_key = {}
    for cell in (cells or []):
        if isinstance(cell, dict) and cell.get('key'):
            cells_by_key.setdefault(cell.get('key'), cell)
    out = []
    for identity in eligible:
        out.append((identity, cells_by_key.get(identity.cell_key) or {}))
    return out


def contribute_manual(bundle, cells, lat, lon, ledger_path=LEDGER_FILE,
                      timeout=10.0):
    """Contribute eligible history observations using the manual Site coords.

    ``cells`` MUST already be hard-filtered by the caller to Internal/Captive
    cellular observations. ``lat``/``lon`` are the CURRENT validated manual
    Site coordinates. Returns a counts dict {submitted, duplicates, failed,
    eligible}. Uses provider acknowledgment (never optimistic). Never raises.
    """
    counts = {'submitted': 0, 'duplicates': 0, 'failed': 0, 'eligible': 0}
    pair = _valid_coords(lat, lon)
    if pair is None:
        return counts

    try:
        observations = _most_recent_eligible_observations(cells)
        if not observations:
            return counts
        adapter = geo_providers.build_contributor(bundle, timeout=timeout)
    except Exception as exc:
        cp.log('GeoView manual-contribution setup skipped: %s'
               % geo_secrets.scrub(exc))
        return counts

    with _lock:
        ledger = _load_ledger(ledger_path)

    for identity, cell in observations:
        counts['eligible'] += 1
        # Timestamp/signal/PCI correspond to the most recent real observation
        # of this cell; contribution location is the manual Site coordinates.
        measurement = build_measurement(identity, cell, pair[0], pair[1])
        try:
            outcome = _submit_one(adapter, ledger, ledger_path, identity,
                                  measurement)
        except Exception as exc:
            cp.log('GeoView manual-contribution error: %s'
                   % geo_secrets.scrub(exc))
            outcome = 'failed'
        if outcome == 'submitted':
            counts['submitted'] += 1
        elif outcome == 'skipped':
            counts['duplicates'] += 1
        else:
            counts['failed'] += 1

    return counts
