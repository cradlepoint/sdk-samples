"""Speedtest Analyzer two-layer Configuration Management (v1.1.2).

This module implements the LOCKED two-key configuration architecture. There
are TWO canonical SDK App Data documents with DIFFERENT responsibilities:

- ``speedtest_analyzer_group``  -- the NCM Group standard. READ/validated
  only. The application NEVER writes this key locally during normal
  operation. It normally arrives via NCM Group SDK/Application Data delivery.

- ``speedtest_analyzer_device`` -- locally managed Device configuration and
  Device overrides. This is the ONLY canonical normal-configuration key the
  application itself writes/deletes locally. All ordinary Saves modify it.

Effective configuration is a strict SECTION-LEVEL merge:

    BUILT-IN DEFAULTS -> GROUP CONFIG -> DEVICE CONFIG -> EFFECTIVE RAM

Precedence is DEVICE > GROUP > DEFAULT, section-atomic. A section is
"overridden" purely because its section KEY EXISTS in the higher layer, never
because of truthiness (``[]``/``{}``/``false``/``""`` are authoritative).

Management state is DERIVED from which canonical keys exist; it is NEVER
stored in JSON. There is no ``management.origin`` / ``management.mode`` and no
single ``config_revision``. Group and Device carry INDEPENDENT revisions
(``group_revision`` / ``device_revision``).

The experimental single key ``speedtest_analyzer`` and the fragmented legacy
keys are MIGRATION INPUTS ONLY. Once either new canonical key exists, legacy
data is permanently outside the source-of-truth chain (never a fallback).

Secrets/encryption and Geo-provider API credentials are OUT OF SCOPE and must
never be stored in either canonical document. The public iPerf3 catalog stays
packaged/read-only and is never copied here. Runtime/results/statistics/
history are NOT configuration and never live in a canonical document.

NOTE ON PROVENANCE: The presence of ``speedtest_analyzer_group`` structurally
identifies the Group configuration LAYER. It does NOT prove the key physically
arrived through NCM Group scope (a user could manually create it at Device
scope). Validation proves exact key / document_type / schema / revision only.
It never claims "NCM Group provenance verified."
"""

import json
import os
import threading

import cp

# GeoView owns its own schema-2 validation. The canonical documents embed the
# GeoView persisted sub-object and delegate all GeoView validation to the
# existing reference implementation rather than duplicating it here.
import cellular_geo


# ---------------------------------------------------------------------------
# Canonical keys
# ---------------------------------------------------------------------------

# The two canonical configuration keys.
GROUP_KEY = 'speedtest_analyzer_group'
DEVICE_KEY = 'speedtest_analyzer_device'

# The abandoned experimental single key. MIGRATION INPUT ONLY. The application
# performs ZERO writes/deletes to this key.
EXPERIMENTAL_KEY = 'speedtest_analyzer'

CURRENT_SCHEMA_VERSION = 1

DOCUMENT_TYPE_GROUP = 'group'
DOCUMENT_TYPE_DEVICE = 'device'


# ---------------------------------------------------------------------------
# Derived management states
# ---------------------------------------------------------------------------

STATE_UNCONFIGURED = 'unconfigured'
STATE_UPGRADE_REQUIRED = 'upgrade_required'
STATE_DEVICE = 'device'
STATE_GROUP = 'group'
STATE_GROUP_WITH_DEVICE_OVERRIDES = 'group_with_device_overrides'
STATE_UNSUPPORTED_SCHEMA = 'unsupported_schema'
STATE_ERROR = 'error'


# ---------------------------------------------------------------------------
# Legacy / migration source keys
# ---------------------------------------------------------------------------

# Fragmented legacy App Data names that historically held NORMAL user
# configuration. MIGRATION INPUT ONLY; never written by this application.
LEGACY_SCHEDULE_KEY = 'speedtest_schedule'
LEGACY_IPERF3_SETTINGS_KEY = 'iperf_server_settings'
LEGACY_IPERF3_SERVERS_KEY = 'iperf3_servers'
LEGACY_NETPERF_SERVERS_KEY = 'netperf_servers'
LEGACY_OUTPUTS_KEY = 'speedtest_outputs'
LEGACY_GEOVIEW_KEY = 'geoview_settings'

LEGACY_CONFIG_KEYS = (
    LEGACY_SCHEDULE_KEY,
    LEGACY_IPERF3_SETTINGS_KEY,
    LEGACY_IPERF3_SERVERS_KEY,
    LEGACY_NETPERF_SERVERS_KEY,
    LEGACY_OUTPUTS_KEY,
    LEGACY_GEOVIEW_KEY,
)

# Runtime/results/statistics keys explicitly EXCLUDED from any canonical
# configuration document. Recorded for the Factory Reset inventory only.
RUNTIME_RESULTS_KEY = 'speedtest_results'
RUNTIME_IPERF3_STATS_KEY = 'iperf_server_stats'

TMP_DIR = 'tmp'


# ---------------------------------------------------------------------------
# Section registry
# ---------------------------------------------------------------------------

# The supported section-level configuration keys. Order is significant only
# for deterministic iteration; merge/override is section-atomic.
SECTION_NAMES = (
    'schedule',
    'outputs',
    'iperf3_server_settings',
    'iperf3_user_servers',
    'netperf_servers',
    'geoview',
)


_config_lock = threading.RLock()

# The effective normalized configuration held in application runtime. ``None``
# until the first authoritative load. When no canonical key exists this holds
# the built-in defaults (Day-1) WITHOUT ever being persisted.
_effective_config = None

# When a canonical layer requires an interactive upgrade/conversion or is in an
# error state, ordinary configuration mutation is blocked. This is a derived,
# non-persisted flag recomputed on every authoritative load.
_mutation_block = None  # None or a MutationBlock instance

_hot_reload_callback = None


def register_hot_reload(callback):
    """Register the runtime reinitialization callback.

    ``callback(effective_config)`` receives the full effective config body and
    must reinitialize only the affected subsystems in place (no app restart).
    """
    global _hot_reload_callback
    _hot_reload_callback = callback


def _run_hot_reload(config):
    """Invoke the registered hot-reload callback, if any. Never raises."""
    callback = _hot_reload_callback
    if callback is None:
        return
    try:
        callback(config)
    except Exception as exc:
        cp.log('Config: hot-reload callback error: %s' % exc)


# ---------------------------------------------------------------------------
# Structured result helpers (no dataclasses; Python 3.8 friendly)
# ---------------------------------------------------------------------------

class LayerLoad(object):
    """Outcome of loading ONE canonical layer (group or device).

    status:
        'absent'    -> the key does not exist
        'ok'        -> present, parsed, valid, normalized
        'older'     -> present, parseable, schema_version < CURRENT (needs
                       interactive upgrade; NOT authoritative yet)
        'newer'     -> present, schema_version > CURRENT (unsupported)
        'corrupt'   -> present but not parseable/valid JSON
    """

    def __init__(self, layer, status, document=None, schema_version=None,
                 revision=None, error=None):
        self.layer = layer  # 'group' | 'device'
        self.status = status
        self.document = document
        self.schema_version = schema_version
        self.revision = revision
        self.error = error

    @property
    def present(self):
        return self.status != 'absent'

    @property
    def usable(self):
        return self.status == 'ok'


class WriteResult(object):
    """Outcome of a read-back verified Device-key write/delete."""

    def __init__(self, ok, document=None, error=None):
        self.ok = ok
        self.document = document
        self.error = error


class GroupCandidate(object):
    """A complete Group JSON the user pastes into NCM. Never written locally."""

    def __init__(self, document):
        self.document = document

    @property
    def group_revision(self):
        return self.document.get('group_revision')

    def to_json(self):
        return serialize_document(self.document)


class ValidationResult(object):
    """Outcome of validating an expected persisted document.

    ``reconcile_aborted`` (Group-update workflow only) is True when validation
    failed specifically because the Device configuration changed during the
    staged workflow (§46). The caller must invalidate the staged workflow and
    require a fresh restart rather than offering a plain "Retry Validate".
    """

    def __init__(self, ok, reason='', document=None, reconcile_aborted=False):
        self.ok = ok
        self.reason = reason
        self.document = document
        self.reconcile_aborted = reconcile_aborted


class ReconcileResult(object):
    """Outcome of revision-pair reconciliation before a persistent Device op.

    changed=True means a canonical layer differed from the captured token; the
    staged edit was discarded and effective RAM was reloaded. The caller must
    tell the user to review/reapply.
    """

    def __init__(self, changed, config, message=''):
        self.changed = changed
        self.config = config
        self.message = message


class MutationBlock(object):
    """Describes why ordinary configuration mutation is currently blocked.

    reason is one of:
        'upgrade_required'    -> legacy/experimental or older-schema device
        'group_schema'        -> older group schema needs NCM update
        'unsupported_schema'  -> a canonical doc is a newer schema
        'error'               -> a canonical doc is corrupt / unusable
    """

    def __init__(self, reason, detail=''):
        self.reason = reason
        self.detail = detail


class SaveResult(object):
    """Outcome of an ordinary Device save.

    status:
        'saved'       -> Device document written (or deleted when emptied)
        'reconciled'  -> a canonical layer changed; staged edit discarded
        'blocked'     -> configuration mutation is blocked (see message)
        'dependency_reset_required' -> the requested section reset alone would
                         produce an inconsistent effective config; the caller
                         must confirm a coupled multi-section reset (dependency)
        'error'       -> feature/persistence error
    removed_override_sections lists sections whose Device override was removed
    because it normalized to the exact Group value (§14). informational only.
    """

    def __init__(self, status, config=None, message='', error=None,
                 removed_override_sections=None, no_change=False,
                 reset_target=None, dependency=None):
        self.status = status
        self.config = config
        self.message = message
        self.error = error
        self.removed_override_sections = removed_override_sections or []
        # no_change=True means the proposed persistent Device body was
        # identical to what is already persisted: ZERO writes, no revision
        # increment, no key create/delete, no hot reload.
        self.no_change = no_change
        # reset_target ('group' | 'default') is the backend-derived destination
        # of a section reset, so the UI toast says the correct thing (§ reset
        # wording bug). None for non-reset saves.
        self.reset_target = reset_target
        # dependency (on status='dependency_reset_required') carries the
        # conflict metadata: requested_section, required_reset_sections, reason,
        # reset_target. The frontend renders a themed confirmation modal.
        self.dependency = dependency


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def serialize_document(document):
    """Deterministically serialize a canonical document.

    Deterministic key ordering keeps read-back comparison stable and matches
    the GeoView persistence convention.
    """
    return json.dumps(document, separators=(',', ':'), sort_keys=True)


# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------

def _default_config_body():
    """Return the complete built-in default ``config`` body.

    This is the DEFAULT layer. It is never persisted merely because the app
    started; it only backstops effective section resolution.
    """
    return {
        'schedule': {
            'enabled': False,
            'autostart': False,
            'cron': '',
            'engine': 'netperf',
            'params': {},
        },
        'iperf3_server_settings': {
            # Only server_mode is canonical persistent configuration.
            # last_public_region is last-used RUNTIME state and is never
            # persisted here.
            'server_mode': 'public',
        },
        'iperf3_user_servers': [],
        'netperf_servers': [],
        'geoview': cellular_geo._persisted_settings(
            cellular_geo.default_geo_settings()
        ),
        'outputs': [],
    }


def build_default_config():
    """Return a deep copy of the complete built-in default config body."""
    return json.loads(json.dumps(_default_config_body()))


# ---------------------------------------------------------------------------
# Section validators / normalizers
#
# Each returns (normalized_value, ok). ``ok`` is False when the incoming
# section was structurally invalid and had to be reset to a default.
# ---------------------------------------------------------------------------

def _normalize_schedule(value):
    default = _default_config_body()['schedule']
    if not isinstance(value, dict):
        return default, False

    ok = True
    engine = value.get('engine', 'netperf')
    if engine not in ('netperf', 'iperf3', 'ookla'):
        engine = 'netperf'
        ok = False

    params = value.get('params', {})
    if not isinstance(params, dict):
        params = {}
        ok = False

    cron = value.get('cron', '')
    if not isinstance(cron, str):
        cron = ''
        ok = False

    return {
        'enabled': bool(value.get('enabled', False)),
        'autostart': bool(value.get('autostart', False)),
        'cron': cron,
        'engine': engine,
        'params': params,
    }, ok


def _normalize_iperf3_settings(value):
    """Normalize the canonical iPerf3 server settings section.

    Only ``server_mode`` is canonical configuration. ``last_public_region`` is
    last-used runtime state and is dropped here even if a legacy document
    supplies it, so a test run / cache init can never mutate canonical config.
    """
    if not isinstance(value, dict):
        return {'server_mode': 'public'}, False

    ok = True
    mode = value.get('server_mode', 'public')
    if mode not in ('public', 'user'):
        mode = 'public'
        ok = False

    return {'server_mode': mode}, ok


def _normalize_server_list(value):
    """Normalize a saved server list (iPerf3 user list or Netperf list).

    Entries must be JSON objects. Per-field validation stays with the feature
    handlers; here we only guarantee a list of dicts so a malformed blob cannot
    poison a whole document.
    """
    if not isinstance(value, list):
        return [], False

    ok = True
    cleaned = []
    for entry in value:
        if isinstance(entry, dict):
            cleaned.append(entry)
        else:
            ok = False
    return cleaned, ok


def _normalize_outputs(value):
    """Normalize the configured output-target list (strings only)."""
    if not isinstance(value, list):
        return [], False

    ok = True
    cleaned = []
    for entry in value:
        if isinstance(entry, str) and entry.strip():
            cleaned.append(entry)
        else:
            ok = False
    return cleaned, ok


def _normalize_geoview(value):
    """Normalize the persisted GeoView section for CANONICAL storage.

    Delegates validation to the GeoView reference implementation, then strips
    runtime device GPS coordinates (§39, §40): current device_gps lat/lon are
    runtime state and must never be written into the canonical Device (or
    Group) document. Manual coordinates / site address are device-specific
    persistent configuration and are preserved.
    """
    try:
        normalized = cellular_geo.normalize_geo_settings(value)
        persisted = cellular_geo._persisted_settings(normalized)
        return cellular_geo.strip_runtime_gps_for_persistence(persisted), True
    except Exception:
        return cellular_geo._persisted_settings(
            cellular_geo.default_geo_settings()
        ), False


_SECTION_NORMALIZERS = {
    'schedule': _normalize_schedule,
    'iperf3_server_settings': _normalize_iperf3_settings,
    'iperf3_user_servers': _normalize_server_list,
    'netperf_servers': _normalize_server_list,
    'outputs': _normalize_outputs,
    'geoview': _normalize_geoview,
}


def normalize_section(section, value):
    """Normalize one section value. Returns (normalized_value, ok)."""
    normalizer = _SECTION_NORMALIZERS.get(section)
    if normalizer is None:
        raise KeyError('unknown configuration section: %s' % section)
    return normalizer(value)


def _normalize_config_body(raw_config):
    """Normalize a SPARSE config body: only present sections are kept.

    Unlike the abandoned architecture, canonical documents are section-sparse.
    A section is present only when its key exists in ``raw_config``; absent
    sections are simply not in the returned body (they inherit downward).

    Returns (body, repaired_sections).
    """
    body = {}
    repaired = []
    if not isinstance(raw_config, dict):
        return body, ['config']
    for section in SECTION_NAMES:
        if section not in raw_config:
            continue
        normalized, ok = normalize_section(section, raw_config[section])
        body[section] = normalized
        if not ok:
            repaired.append(section)
    return body, repaired


# ---------------------------------------------------------------------------
# Document construction / validation
# ---------------------------------------------------------------------------

def build_device_document(config_body, device_revision):
    """Build a complete schema-1 Device document from a sparse config body."""
    return {
        'schema_version': CURRENT_SCHEMA_VERSION,
        'document_type': DOCUMENT_TYPE_DEVICE,
        'device_revision': int(device_revision),
        'config': json.loads(json.dumps(config_body)),
    }


def build_group_document(config_body, group_revision):
    """Build a complete schema-1 Group document from a sparse config body."""
    return {
        'schema_version': CURRENT_SCHEMA_VERSION,
        'document_type': DOCUMENT_TYPE_GROUP,
        'group_revision': int(group_revision),
        'config': json.loads(json.dumps(config_body)),
    }


def _validate_document(document, expected_type):
    """Validate a canonical document's envelope.

    Returns (ok, schema_version, revision, reason). Does NOT claim provenance.
    """
    if not isinstance(document, dict):
        return False, None, None, 'document is not an object'

    schema_version = document.get('schema_version')
    if not isinstance(schema_version, int) or isinstance(schema_version, bool):
        return False, None, None, 'invalid schema_version'

    if document.get('document_type') != expected_type:
        return False, schema_version, None, 'unexpected document_type'

    rev_key = ('group_revision' if expected_type == DOCUMENT_TYPE_GROUP
               else 'device_revision')
    revision = document.get(rev_key)
    if not isinstance(revision, int) or isinstance(revision, bool) or \
            revision < 0:
        return False, schema_version, None, 'invalid %s' % rev_key

    if not isinstance(document.get('config'), dict):
        return False, schema_version, revision, 'missing config body'

    return True, schema_version, revision, ''


# ---------------------------------------------------------------------------
# Exact-match App Data loader (§3)
# ---------------------------------------------------------------------------

def _get_appdata_exact(name):
    """Return the raw value for App Data ``name`` using EXACT name matching.

    The SDK's ``cp.get_appdata`` may perform loose/substring matching between
    the related names (speedtest_analyzer / _group / _device). This loader
    inspects the full entry list and accepts an entry ONLY when
    ``entry['name'] == name`` exactly. Returns the raw value (str/dict/list) or
    None when no exactly-named entry exists.
    """
    try:
        entries = cp.get_appdata()
    except Exception as exc:
        cp.log('Config: error listing App Data: %s' % exc)
        return None

    if not isinstance(entries, list):
        # Defensive: some environments may already return a scalar for a name.
        return None

    for entry in entries:
        if isinstance(entry, dict) and entry.get('name') == name:
            return entry.get('value')
    return None


def _parse_json_value(raw):
    """Parse a raw App Data value into a Python object, or None on failure."""
    if raw in (None, ''):
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Canonical layer loading
# ---------------------------------------------------------------------------

def _load_layer(layer):
    """Load ONE canonical layer exactly. Returns a LayerLoad."""
    key = GROUP_KEY if layer == 'group' else DEVICE_KEY
    expected_type = (DOCUMENT_TYPE_GROUP if layer == 'group'
                     else DOCUMENT_TYPE_DEVICE)

    raw = _get_appdata_exact(key)
    if raw in (None, ''):
        return LayerLoad(layer, 'absent')

    parsed = _parse_json_value(raw)
    if parsed is None:
        return LayerLoad(layer, 'corrupt', error='unparseable JSON')

    schema_version = parsed.get('schema_version') if isinstance(parsed, dict) \
        else None
    if not isinstance(schema_version, int) or isinstance(schema_version, bool):
        return LayerLoad(layer, 'corrupt', error='invalid schema_version')

    if schema_version > CURRENT_SCHEMA_VERSION:
        return LayerLoad(layer, 'newer', document=parsed,
                         schema_version=schema_version,
                         error='newer unsupported schema')

    if schema_version < CURRENT_SCHEMA_VERSION:
        # Older schema: attempt in-RAM migration to prove it can upgrade, but
        # do NOT persist here. Report 'older' for interactive handling.
        migrated, _ = migrate_schema(parsed, expected_type)
        ok, _, revision, reason = _validate_document(migrated, expected_type)
        if not ok:
            return LayerLoad(layer, 'corrupt',
                             error='older schema not migratable: %s' % reason)
        return LayerLoad(layer, 'older', document=migrated,
                         schema_version=schema_version, revision=revision)

    ok, sv, revision, reason = _validate_document(parsed, expected_type)
    if not ok:
        return LayerLoad(layer, 'corrupt', error=reason)

    # Normalize the config body (sparse). Normalization never adds sections.
    body, _repaired = _normalize_config_body(parsed.get('config'))
    document = {
        'schema_version': CURRENT_SCHEMA_VERSION,
        'document_type': expected_type,
        ('group_revision' if layer == 'group' else 'device_revision'):
            revision,
        'config': body,
    }
    return LayerLoad(layer, 'ok', document=document,
                     schema_version=sv, revision=revision)


def load_layers():
    """Load both canonical layers exactly. Returns (group_load, device_load)."""
    return _load_layer('group'), _load_layer('device')


# ---------------------------------------------------------------------------
# Effective section-level merge (§6, §7, §8)
# ---------------------------------------------------------------------------

def compute_effective(group_body, device_body):
    """Section-level merge: DEVICE > GROUP > DEFAULT.

    A section comes from Device when its KEY EXISTS in ``device_body``, else
    from Group when its KEY EXISTS in ``group_body``, else from built-in
    defaults. Presence is by key existence, never truthiness. Returns a deep
    copy so callers cannot mutate authoritative layers.
    """
    defaults = _default_config_body()
    group_body = group_body if isinstance(group_body, dict) else {}
    device_body = device_body if isinstance(device_body, dict) else {}

    effective = {}
    for section in SECTION_NAMES:
        if section in device_body:
            effective[section] = device_body[section]
        elif section in group_body:
            effective[section] = group_body[section]
        else:
            effective[section] = defaults[section]
    return json.loads(json.dumps(effective))


def override_sections(group_body, device_body):
    """Return the list of Device sections that override an existing layer.

    A Device section is an "override" when it is present in the Device
    document. (When Group is absent these are simply Device-managed sections;
    callers interpret the label based on management state.)
    """
    device_body = device_body if isinstance(device_body, dict) else {}
    return [s for s in SECTION_NAMES if s in device_body]


def effective_section_sources(group_body, device_body):
    """Return {section: 'device'|'group'|'default'} by SECTION PRESENCE.

    Presence is by key existence, never truthiness (a falsey ``[]``/``{}`` in a
    layer still counts as present). This is the authoritative per-section
    source the UI needs; the frontend cannot derive it from bare
    group_present/device_present/override_sections because a section may be
    absent from BOTH layers and therefore come from built-in defaults.
    """
    group_body = group_body if isinstance(group_body, dict) else {}
    device_body = device_body if isinstance(device_body, dict) else {}
    sources = {}
    for section in SECTION_NAMES:
        if section in device_body:
            sources[section] = 'device'
        elif section in group_body:
            sources[section] = 'group'
        else:
            sources[section] = 'default'
    return sources


# ---------------------------------------------------------------------------
# Effective-config dependency validation (§ reset dependency, v1.1.2)
#
# A proposed EFFECTIVE configuration must be internally consistent before it is
# persisted. The ONE dependency that matters for v1.1.2 is the iPerf3 scheduled
# test's coupling to the active iPerf3 server mode:
#
#   A configured iPerf3 schedule records params.server_source ('public'|'user')
#   -- the server family the scheduled job was built against. The EFFECTIVE
#   iperf3_server_settings.server_mode controls which server list is active.
#   When they disagree, the scheduled test points at a server family the device
#   is not serving (empty dropdown / stale status card), i.e. the confirmed
#   E400 defect. Netperf/Ookla schedules and non-iperf3 schedules have no such
#   coupling and are never touched.
#
# This validator operates purely on an EFFECTIVE (already section-merged) body
# so it works identically for section reset, Reset All, and Group-update paths.
# ---------------------------------------------------------------------------


def compute_schedule_running(enabled, autostart, is_startup):
    """Return the RUNTIME running state for a schedule.

    ``enabled`` and ``autostart`` are INDEPENDENT PERSISTED fields; this never
    mutates them. It only derives whether the scheduler should actually fire:

    - Startup / boot apply (``is_startup=True``):
        running = enabled AND autostart
        (an enabled-but-not-autostart schedule does NOT auto-start after an
        app/router restart)
    - Interactive save / apply (``is_startup=False``):
        running = enabled
        (an explicit user Save runs the schedule now, regardless of autostart)

    ``enabled=false`` never runs, regardless of autostart or startup.
    """
    enabled = bool(enabled)
    autostart = bool(autostart)
    if not enabled:
        return False
    if is_startup:
        return autostart
    return True


def _schedule_is_active_iperf3(schedule):
    """True when a schedule section is a CONFIGURED iPerf3 scheduled test.

    Mirrors the runtime _iperf3_schedule_is_configured contract: a schedule
    counts as configured when it is enabled/autostart or carries a cron/params
    payload. A bare disabled/empty schedule (the safe-reset value) never
    triggers a dependency.
    """
    if not isinstance(schedule, dict):
        return False
    if schedule.get('engine') != 'iperf3':
        return False
    return bool(schedule.get('enabled') or schedule.get('autostart')
                or schedule.get('cron') or schedule.get('params'))


def check_effective_dependencies(effective_body):
    """Validate an EFFECTIVE config body's internal dependencies.

    Returns (ok, conflict) where conflict (on failure) is a dict:
        { 'requested_dependency': 'schedule_server_mode',
          'sections': [<section>, ...],   # sections whose disagreement causes
                                          # the conflict, in a stable order
          'reason': <human-readable> }

    Only the iPerf3 schedule <-> server-mode coupling is enforced (v1.1.2).
    """
    body = effective_body if isinstance(effective_body, dict) else {}
    schedule = body.get('schedule')
    if not _schedule_is_active_iperf3(schedule):
        return True, None

    params = schedule.get('params') if isinstance(schedule.get('params'),
                                                  dict) else {}
    scheduled_source = params.get('server_source')

    settings = body.get('iperf3_server_settings')
    server_mode = settings.get('server_mode') if isinstance(settings, dict) \
        else 'public'

    # A scheduled iPerf3 job with no recorded server family cannot be validated
    # for consistency; treat it as depending on the active mode (no false
    # coupling -- only flag when it plainly disagrees).
    if scheduled_source in ('public', 'user') and \
            scheduled_source != server_mode:
        friendly_sched = ('Public' if scheduled_source == 'public'
                          else 'User')
        friendly_mode = 'Public' if server_mode == 'public' else 'User'
        reason = (
            'The Scheduled Test uses a %s iPerf3 server, but the effective '
            'iPerf3 Server Mode would be %s. The scheduled test and the '
            'server mode must use the same server family.'
            % (friendly_sched, friendly_mode))
        return False, {
            'requested_dependency': 'schedule_server_mode',
            'sections': ['schedule', 'iperf3_server_settings'],
            'reason': reason,
        }

    return True, None


# ---------------------------------------------------------------------------
# Compact, safe section summaries for the Device Overrides UI
# ---------------------------------------------------------------------------

# Human-friendly cron descriptions (mirrors the frontend map; safe subset).
_CRON_DESCRIPTIONS = {
    '*/5 * * * *': 'Every 5 minutes',
    '*/10 * * * *': 'Every 10 minutes',
    '*/15 * * * *': 'Every 15 minutes',
    '*/30 * * * *': 'Every 30 minutes',
    '0 * * * *': 'Hourly',
    '0 */2 * * *': 'Every 2 hours',
    '0 */3 * * *': 'Every 3 hours',
    '0 */4 * * *': 'Every 4 hours',
    '0 */6 * * *': 'Every 6 hours',
    '0 */12 * * *': 'Every 12 hours',
    '0 0 * * *': 'Daily at midnight',
    '0 6 * * *': 'Daily at 6am',
    '0 12 * * *': 'Daily at noon',
}


def summarize_section(section, value):
    """Return a short, SAFE human summary of a section value for the UI.

    Never dumps full JSON and never exposes secrets/credentials (v1.1.2 has
    none, but the summary is deliberately allow-listed so future secret fields
    can never leak). Returns '' when there is nothing meaningful to show.
    """
    try:
        if section == 'schedule':
            if not isinstance(value, dict):
                return ''
            parts = []
            parts.append('Enabled' if value.get('enabled') else 'Disabled')
            cron = value.get('cron') or ''
            desc = _CRON_DESCRIPTIONS.get(cron, cron)
            if desc:
                parts.append(desc)
            engine = value.get('engine')
            if engine:
                parts.append(str(engine))
            # server_name lives in params for iperf3-style schedules.
            params = value.get('params')
            if isinstance(params, dict):
                sname = params.get('server_name')
                if sname:
                    parts.append(str(sname))
            return ' \u00b7 '.join(parts)

        if section == 'outputs':
            if not isinstance(value, list):
                return ''
            if not value:
                return 'No output targets'
            # Output targets are config PATHS/labels, not secrets.
            return ', '.join(str(v) for v in value)

        if section == 'iperf3_server_settings':
            if not isinstance(value, dict):
                return ''
            mode = value.get('server_mode')
            if mode == 'user':
                return 'User iPerf3 Servers'
            return 'Public iPerf3 Servers'

        if section == 'iperf3_user_servers':
            if not isinstance(value, list):
                return ''
            n = len(value)
            return '%d configured server%s' % (n, '' if n == 1 else 's')

        if section == 'netperf_servers':
            if not isinstance(value, list):
                return ''
            n = len(value)
            return '%d configured server%s' % (n, '' if n == 1 else 's')

        if section == 'geoview':
            if not isinstance(value, dict):
                return ''
            src = value.get('active_location_source')
            return {
                'device_gps': 'Device GPS',
                'manual_coordinates': 'Manual Coordinates',
                'site_address': 'Site Address',
            }.get(src, 'GeoView policy')
    except Exception:
        return ''
    return ''


def override_details(group_body, device_body):
    """Return per-override detail objects for the Device Overrides UI.

    For each Device-present section:
      { section, label, summary, reset_target }
    where reset_target is 'group' when the section ALSO exists in the Group
    layer (removing the Device override inherits Group), else 'default'
    (removing it falls to built-in defaults). Derived by SECTION PRESENCE;
    this does NOT change merge behavior.
    """
    group_body = group_body if isinstance(group_body, dict) else {}
    device_body = device_body if isinstance(device_body, dict) else {}
    details = []
    for section in SECTION_NAMES:
        if section not in device_body:
            continue
        details.append({
            'section': section,
            'label': SECTION_LABELS.get(section, section),
            'summary': summarize_section(section, device_body[section]),
            'reset_target': 'group' if section in group_body else 'default',
        })
    return details


# ---------------------------------------------------------------------------
# Derived management state (§9)
# ---------------------------------------------------------------------------

def derive_state(group_load, device_load, legacy_present=False):
    """Derive the primary management state from the two layer loads.

    ``legacy_present`` is True when NO new canonical key exists but a valid
    migration source (experimental single key or fragmented legacy config)
    does. In that case the PRIMARY derived state is ``upgrade_required`` per
    the locked LLD (§17/§53), not merely ``unconfigured`` with a boolean.

    Precedence for problem states: a canonical doc that is 'newer' ->
    unsupported_schema; 'corrupt' -> error; 'older' -> upgrade_required.
    Otherwise the normal four presence-derived states, with legacy sources
    (when both new keys are absent) promoting the state to upgrade_required.
    """
    # Problem states take priority so mutation stays blocked.
    if group_load.status == 'newer' or device_load.status == 'newer':
        return STATE_UNSUPPORTED_SCHEMA
    if group_load.status == 'corrupt' or device_load.status == 'corrupt':
        return STATE_ERROR
    if device_load.status == 'older' or group_load.status == 'older':
        return STATE_UPGRADE_REQUIRED

    group_present = group_load.present
    device_present = device_load.present

    if not group_present and not device_present:
        # No new canonical keys. A valid legacy/experimental migration source
        # makes the PRIMARY state upgrade_required; otherwise truly fresh.
        if legacy_present:
            return STATE_UPGRADE_REQUIRED
        return STATE_UNCONFIGURED
    if not group_present and device_present:
        return STATE_DEVICE
    if group_present and not device_present:
        return STATE_GROUP
    return STATE_GROUP_WITH_DEVICE_OVERRIDES


# ---------------------------------------------------------------------------
# Legacy / experimental discovery (§17, §19, §20)
# ---------------------------------------------------------------------------

def _read_legacy_json(key, expect_list=False):
    """Read one legacy App Data key (exact match) and JSON-parse it."""
    raw = _get_appdata_exact(key)
    parsed = _parse_json_value(raw)
    if parsed is None:
        return None
    if expect_list and not isinstance(parsed, list):
        return None
    return parsed


def legacy_config_discovery():
    """Discover normal configuration living in fragmented legacy keys.

    Returns a dict of canonical section name -> parsed legacy value (only for
    sections that actually exist). Runtime/results/history keys are never read.
    Mapping is the LLD §19 classification.
    """
    discovered = {}

    schedule = _read_legacy_json(LEGACY_SCHEDULE_KEY)
    if isinstance(schedule, dict):
        discovered['schedule'] = schedule

    iperf3_settings = _read_legacy_json(LEGACY_IPERF3_SETTINGS_KEY)
    if isinstance(iperf3_settings, dict):
        # server_mode ONLY (§19).
        discovered['iperf3_server_settings'] = iperf3_settings

    iperf3_servers = _read_legacy_json(LEGACY_IPERF3_SERVERS_KEY,
                                       expect_list=True)
    if isinstance(iperf3_servers, list):
        discovered['iperf3_user_servers'] = iperf3_servers

    netperf_servers = _read_legacy_json(LEGACY_NETPERF_SERVERS_KEY,
                                        expect_list=True)
    if isinstance(netperf_servers, list):
        discovered['netperf_servers'] = netperf_servers

    outputs = _read_legacy_json(LEGACY_OUTPUTS_KEY, expect_list=True)
    if isinstance(outputs, list):
        discovered['outputs'] = outputs

    geoview = _read_legacy_json(LEGACY_GEOVIEW_KEY)
    if geoview is not None:
        discovered['geoview'] = geoview

    return discovered


def experimental_config_discovery():
    """Discover a config body inside the experimental single key, if present.

    Returns the normalized SPARSE config body (only sections that exist) or
    None when the experimental key is absent/invalid. Old management metadata
    (management.origin/mode/config_revision) is IGNORED entirely (§20).
    """
    raw = _get_appdata_exact(EXPERIMENTAL_KEY)
    parsed = _parse_json_value(raw)
    if not isinstance(parsed, dict):
        return None
    raw_config = parsed.get('config')
    if not isinstance(raw_config, dict):
        return None
    body, _ = _normalize_config_body(raw_config)
    return body


def has_legacy_migration_sources():
    """True when experimental OR any fragmented legacy config key exists."""
    if _get_appdata_exact(EXPERIMENTAL_KEY) not in (None, ''):
        return True
    for key in LEGACY_CONFIG_KEYS:
        if _get_appdata_exact(key) not in (None, ''):
            return True
    return False


def _build_migration_source_body():
    """Build the SPARSE config body used to convert legacy/experimental data.

    The experimental single key is the PREFERRED migration source when present
    and valid (§20). Otherwise fragmented legacy keys are used. Returns a
    normalized sparse body.
    """
    experimental = experimental_config_discovery()
    if experimental is not None:
        return experimental

    discovered = legacy_config_discovery()
    body, _ = _normalize_config_body(discovered)
    return body


# ---------------------------------------------------------------------------
# Schema migration framework (§47)
# ---------------------------------------------------------------------------

def migrate_legacy_to_v1(discovered):
    """Build a SPARSE schema-1 config body from discovered legacy data.

    Only sections that exist are included; nothing is padded with defaults, so
    the resulting Device document stays section-sparse per the LLD.
    """
    body, _ = _normalize_config_body(discovered)
    return body


# Ordered chains of schema upgrades per document type. schema N -> N+1. Each
# entry converts a full document in memory. v1 is current; future steps append.
_GROUP_SCHEMA_MIGRATIONS = {
    # 1: migrate_group_v1_to_v2,
}
_DEVICE_SCHEMA_MIGRATIONS = {
    # 1: migrate_device_v1_to_v2,
}


def migrate_schema(document, document_type):
    """Sequentially upgrade a parsed document toward CURRENT_SCHEMA_VERSION.

    Returns (document, migrated_bool). In-memory only; persistence decisions
    follow the normal Device/Group workflow and are never done here.
    """
    if not isinstance(document, dict):
        return document, False

    chain = (_GROUP_SCHEMA_MIGRATIONS if document_type == DOCUMENT_TYPE_GROUP
             else _DEVICE_SCHEMA_MIGRATIONS)

    version = document.get('schema_version')
    if not isinstance(version, int) or isinstance(version, bool):
        return document, False

    migrated = False
    while version < CURRENT_SCHEMA_VERSION and version in chain:
        document = chain[version](document)
        version = document.get('schema_version')
        migrated = True

    return document, migrated


# ---------------------------------------------------------------------------
# Authoritative load + effective state
# ---------------------------------------------------------------------------

class ConfigState(object):
    """Snapshot of the full derived configuration state."""

    def __init__(self, state, group_load, device_load, effective,
                 mutation_block, override_sections, legacy_upgrade_required):
        self.state = state
        self.group_load = group_load
        self.device_load = device_load
        self.effective = effective
        self.mutation_block = mutation_block
        self.override_sections = override_sections
        self.legacy_upgrade_required = legacy_upgrade_required

    @property
    def group_present(self):
        return self.group_load.status in ('ok', 'older', 'newer')

    @property
    def device_present(self):
        return self.device_load.status in ('ok', 'older', 'newer')


def _group_body(group_load):
    if group_load.usable and group_load.document:
        return group_load.document.get('config', {})
    return {}


def _device_body(device_load):
    if device_load.usable and device_load.document:
        return device_load.document.get('config', {})
    return {}


def compute_state():
    """Load both layers, derive state, compute effective config + block.

    This is the single authoritative read path. It NEVER writes App Data.
    The PRIMARY derived state is authoritative per the LLD: legacy/experimental
    migration sources (with both new keys absent) report state=upgrade_required,
    not merely unconfigured with a boolean.
    """
    group_load, device_load = load_layers()

    # Legacy/experimental migration sources only matter when NO new canonical
    # key exists and neither is in a problem state.
    both_absent = (not group_load.present) and (not device_load.present)
    legacy_present = both_absent and has_legacy_migration_sources()

    state = derive_state(group_load, device_load, legacy_present=legacy_present)
    legacy_upgrade_required = (state == STATE_UPGRADE_REQUIRED
                               and legacy_present)

    block = None
    if state == STATE_UNSUPPORTED_SCHEMA:
        block = MutationBlock('unsupported_schema',
                              'A configuration document uses a newer, '
                              'unsupported schema version.')
    elif state == STATE_ERROR:
        block = MutationBlock('error',
                              'A configuration document is corrupt and must '
                              'be repaired or replaced.')
    elif state == STATE_UPGRADE_REQUIRED:
        if legacy_upgrade_required:
            # Legacy/experimental config from an earlier version (§17/§18).
            block = MutationBlock('upgrade_required',
                                  'Speedtest Analyzer found configuration '
                                  'created by an earlier version. Your '
                                  'existing settings must be converted before '
                                  'configuration changes can be made. You can '
                                  'still run tests and view history and '
                                  'reports; only configuration changes are '
                                  'blocked until conversion completes.')
        elif group_load.status == 'older':
            block = MutationBlock('group_schema',
                                  'The NCM Group configuration uses an older '
                                  'schema and must be updated in NCM.')
        else:
            block = MutationBlock('upgrade_required',
                                  'The Device configuration uses an older '
                                  'schema and must be converted. You can still '
                                  'run tests and view history and reports; '
                                  'only configuration changes are blocked.')

    # Effective config: only usable layers contribute; problem layers do not.
    if state in (STATE_UNSUPPORTED_SCHEMA, STATE_ERROR):
        # Present something safe to read without pretending compatibility.
        effective = build_default_config()
    elif legacy_upgrade_required:
        # Compatibility mode: legacy participates ONLY here (both new keys
        # absent). Build a read-only effective view from migration sources so
        # runtime keeps working; mutation stays blocked until conversion.
        effective = compute_effective({}, _build_migration_source_body())
    elif state == STATE_UPGRADE_REQUIRED:
        # Older-schema canonical layer(s): use the in-RAM migrated documents
        # for read-only runtime so the app stays operational while blocked.
        effective = compute_effective(
            group_load.document.get('config', {}) if group_load.document
            else {},
            device_load.document.get('config', {}) if device_load.document
            else {},
        )
    else:
        effective = compute_effective(_group_body(group_load),
                                      _device_body(device_load))

    overrides = override_sections(_group_body(group_load),
                                  _device_body(device_load))

    return ConfigState(state, group_load, device_load, effective, block,
                       overrides, legacy_upgrade_required)


def load_effective_config():
    """Compute state, cache effective config + block. Returns the ConfigState.

    Never persists anything.
    """
    global _effective_config, _mutation_block
    with _config_lock:
        cs = compute_state()
        _effective_config = cs.effective
        _mutation_block = cs.mutation_block
        return cs


def _reload_and_apply():
    """Recompute effective config AND hot-apply it to runtime subsystems.

    Used by every MUTATION path (save/convert/cleanup/reset) so the runtime is
    reinitialized from the new EFFECTIVE body immediately after a successful
    persistent change. The hot-reload callback always receives the effective
    section body (never a wrapped/layered document). Returns the ConfigState.
    """
    cs = load_effective_config()
    if cs.state not in (STATE_ERROR, STATE_UNSUPPORTED_SCHEMA):
        _run_hot_reload(cs.effective)
    return cs


def get_effective_config():
    """Return a deep copy of the effective RAM configuration body."""
    with _config_lock:
        if _effective_config is None:
            return build_default_config()
        return json.loads(json.dumps(_effective_config))


def _set_effective(effective, block):
    global _effective_config, _mutation_block
    with _config_lock:
        _effective_config = json.loads(json.dumps(effective))
        _mutation_block = block


def mutation_blocked():
    """Return the current MutationBlock, or None when mutation is allowed."""
    with _config_lock:
        return _mutation_block


def active_section(section):
    """Return a defensive copy of an effective section, or None if unknown.

    Runtime readers use this to source effective configuration once loaded.
    Under the two-key model the effective config is ALWAYS complete (defaults
    backstop every section), so this returns the merged value. Legacy App Data
    is NEVER consulted here once either canonical key exists; that fallback is
    the caller's Day-1/compatibility concern and is expressed through the
    effective config computed in compute_state().
    """
    with _config_lock:
        if section not in _SECTION_NORMALIZERS:
            return None
        if _effective_config is None:
            return None
        body = _effective_config
        if section not in body:
            return None
        return json.loads(json.dumps(body[section]))


# ---------------------------------------------------------------------------
# Read-back verified Device write / delete (§12)
# ---------------------------------------------------------------------------

def _write_device_document(document):
    """Serialize + write + exact read-back verify the Device document.

    Returns a WriteResult. On any verification failure, fails closed and does
    NOT update effective RAM state. Only the Device key is ever written.
    """
    ok, _, expected_rev, reason = _validate_document(
        document, DOCUMENT_TYPE_DEVICE)
    if not ok:
        return WriteResult(False, error='refusing invalid device doc: %s'
                           % reason)

    serialized = serialize_document(document)
    try:
        cp.put_appdata(DEVICE_KEY, serialized)
    except Exception as exc:
        return WriteResult(False, error='put_appdata failed: %s' % exc)

    verify = _load_layer('device')
    if verify.status != 'ok' or verify.document is None:
        return WriteResult(False, error='read-back did not validate (%s)'
                           % verify.status)
    if verify.revision != expected_rev:
        return WriteResult(False, error='read-back revision mismatch')
    return WriteResult(True, document=verify.document)


def _delete_device_document():
    """Delete the Device key and verify absence via exact match."""
    try:
        cp.delete_appdata(DEVICE_KEY)
    except Exception as exc:
        cp.log('Config: delete device failed: %s' % exc)
        return False
    return _get_appdata_exact(DEVICE_KEY) in (None, '')


# ---------------------------------------------------------------------------
# Reconciliation token (§46)
# ---------------------------------------------------------------------------

class RevisionToken(object):
    """The authoritative (group_revision, device_revision) pair, 0 when absent."""

    def __init__(self, group_revision, device_revision):
        self.group_revision = group_revision
        self.device_revision = device_revision

    def __eq__(self, other):
        return (isinstance(other, RevisionToken)
                and self.group_revision == other.group_revision
                and self.device_revision == other.device_revision)

    def __repr__(self):
        return 'RevisionToken(group=%r, device=%r)' % (
            self.group_revision, self.device_revision)


def capture_revision_token(group_load=None, device_load=None):
    """Capture the current authoritative revision pair (group|0, device|0)."""
    if group_load is None or device_load is None:
        group_load, device_load = load_layers()
    g = group_load.revision if (group_load.usable and
                                group_load.revision is not None) else 0
    d = device_load.revision if (device_load.usable and
                                 device_load.revision is not None) else 0
    return RevisionToken(g, d)


# ---------------------------------------------------------------------------
# Ordinary Device save (§11, §12, §13, §14, §15)
# ---------------------------------------------------------------------------

def _as_updates(section, value, updates):
    """Normalize the (section, value) vs updates-dict calling convention."""
    if updates is not None:
        return dict(updates)
    if section is None:
        return {}
    return {section: value}


def save_device(section=None, value=None, updates=None):
    """Ordinary configuration Save. Always Device-only. No prompt.

    Behavior:
    - Blocks when configuration mutation is blocked (upgrade/error/unsupported).
    - Captures the revision token, re-reads both layers, and discards the whole
      staged operation if either revision changed (§46).
    - Builds the proposed Device config by overlaying the staged section(s) on
      the CURRENT Device body (sparse; only configured sections are stored).
    - When Group exists and a saved section normalizes to the exact Group
      value, the redundant Device override is removed (§14). If that empties
      the Device document, the Device key is deleted, returning to pure Group.
    - Otherwise writes the Device document with read-back verify and increments
      device_revision exactly once for the whole transaction (§15, §45).
    - Recomputes + hot-applies effective config.
    """
    with _config_lock:
        block = mutation_blocked()
        if block is not None:
            return SaveResult('blocked', message=block.detail,
                              config=get_effective_config())

        staged = _as_updates(section, value, updates)
        for name in staged:
            if name not in _SECTION_NORMALIZERS:
                return SaveResult('error',
                                  error='unknown configuration section: %s'
                                  % name)
        if not staged:
            return SaveResult('error', error='no sections to save')

        # Reconcile: capture token, re-read, discard on any change.
        token = capture_revision_token()
        group_load, device_load = load_layers()
        current_token = capture_revision_token(group_load, device_load)
        if current_token != token:
            # Token captured and immediately re-read; a difference means the
            # persisted layers changed under us in the same operation window.
            cs = _reload_and_apply()
            return SaveResult(
                'reconciled', config=cs.effective,
                message='Saved configuration changed. Your edit was not '
                        'applied. Review the current settings and reapply.')

        # Additional guard: if the loaded state now blocks mutation, stop.
        cs_state = derive_state(group_load, device_load)
        if cs_state in (STATE_UNSUPPORTED_SCHEMA, STATE_ERROR,
                        STATE_UPGRADE_REQUIRED):
            load_effective_config()
            return SaveResult('blocked',
                              message='Configuration must be resolved before '
                                      'saving.',
                              config=get_effective_config())

        group_body = _group_body(group_load)
        device_body = dict(_device_body(device_load))
        group_present = group_load.usable and group_load.present

        removed = []
        for name, raw_value in staged.items():
            normalized, _ok = normalize_section(name, raw_value)
            if group_present and name in group_body and \
                    _sections_equal(normalized, group_body[name]):
                # Redundant override: remove rather than store an identical copy.
                if name in device_body:
                    del device_body[name]
                removed.append(name)
            else:
                device_body[name] = normalized

        # Determine current device revision (0 when Device absent).
        current_dev_rev = device_load.revision if (
            device_load.usable and device_load.revision is not None) else 0

        # No-op guard (§45: no change -> no increment). This runs AFTER
        # Group-equality pruning above, and compares the PROPOSED PERSISTENT
        # device.config body to the CURRENTLY PERSISTED device.config body
        # (normalized). If they are identical:
        #   - ZERO App Data writes
        #   - no device_revision increment
        #   - no Device key create/delete
        #   - no hot reload (persistent + effective config are unchanged)
        # This deliberately ignores the raw incoming request, so runtime-only
        # values (e.g. a fresh device_gps fix, already stripped before
        # persistence) never count as a configuration change. When the guard
        # fires, no Group-equality removal occurred (a removal would make the
        # bodies differ), so ``removed`` is empty and effective is unchanged.
        # The legacy-suppression sentinel (config={}) is preserved because an
        # identical empty body matches and returns WITHOUT deleting the key.
        existing_device_body = _device_body(device_load)
        if device_load.present and \
                _sections_equal(device_body, existing_device_body):
            return SaveResult('saved', config=get_effective_config(),
                              no_change=True,
                              message='No configuration change.')

        if not device_body:
            # No device sections remain.
            if device_load.present:
                # A real change: an existing Device override (or the last one)
                # was pruned. Delete the Device key -> pure Group / defaults,
                # recompute + hot-apply (effective changed).
                if not _delete_device_document():
                    return SaveResult('error',
                                      error='unable to remove Device '
                                            'configuration')
                cs = _reload_and_apply()
                return SaveResult('saved', config=cs.effective,
                                  removed_override_sections=removed,
                                  message=_redundant_message(removed))
            # Device was ALREADY absent and the proposed value normalized to a
            # Group value (or defaults): nothing to persist. This is a true
            # no-op -> NO Device key creation, NO write, NO revision, NO hot
            # reload. (Pure-Group same-value save.)
            return SaveResult('saved', config=get_effective_config(),
                              no_change=True,
                              message='No configuration change.')

        new_document = build_device_document(device_body, current_dev_rev + 1)
        write = _write_device_document(new_document)
        if not write.ok:
            return SaveResult('error', error=write.error)

        cs = _reload_and_apply()
        return SaveResult('saved', config=cs.effective,
                          removed_override_sections=removed,
                          message=_redundant_message(removed))


def _sections_equal(a, b):
    """Deterministic deep equality for two normalized section values."""
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _redundant_message(removed):
    if not removed:
        return ''
    labels = {
        'schedule': 'Schedule',
        'outputs': 'Outputs',
        'iperf3_server_settings': 'iPerf3 Server Mode',
        'iperf3_user_servers': 'User iPerf3 Servers',
        'netperf_servers': 'Netperf Servers',
        'geoview': 'GeoView',
    }
    names = ', '.join(labels.get(s, s) for s in removed)
    if len(removed) == 1:
        return ('%s now matches the NCM Group configuration. The local %s '
                'override was removed.' % (names, names))
    return ('%s now match the NCM Group configuration. Those local overrides '
            'were removed.' % names)


# ---------------------------------------------------------------------------
# Legacy / experimental conversion (§17-§22)
# ---------------------------------------------------------------------------

def convert_legacy_to_device():
    """Convert legacy/experimental configuration into a Device document (§21).

    Preconditions (caller-enforced by state): both new canonical keys absent
    and a migration source exists. Sequence: read source -> normalize ->
    build schema-1 Device doc, device_revision=1 -> write -> read-back verify
    -> validate -> load effective -> unlock editing. Migration sources are
    never modified/deleted. Returns a SaveResult.
    """
    with _config_lock:
        group_load, device_load = load_layers()
        if group_load.present or device_load.present:
            # A new canonical key already exists; conversion is not applicable.
            return SaveResult('error',
                              error='canonical configuration already exists')

        if not has_legacy_migration_sources():
            return SaveResult('error', error='no migration source found')

        body = _build_migration_source_body()
        document = build_device_document(body, 1)
        write = _write_device_document(document)
        if not write.ok:
            # Old configuration remains active; editing stays blocked.
            return SaveResult('error',
                              error='conversion write failed: %s' % write.error)

        cs = _reload_and_apply()
        return SaveResult('saved', config=cs.effective,
                          message='Configuration converted to the current '
                                  'format. Device Managed.')


# ---------------------------------------------------------------------------
# Older-schema Device conversion (§49)
# ---------------------------------------------------------------------------

def convert_older_device_schema():
    """Confirmed migration of an older-schema Device document (§49).

    migrate in RAM -> normalize -> write Device -> read-back verify ->
    device_revision +1 -> hot reload. Only valid when the Device layer is in
    'older' status.
    """
    with _config_lock:
        group_load, device_load = load_layers()
        if device_load.status != 'older' or device_load.document is None:
            return SaveResult('error',
                              error='no older-schema Device document to '
                                    'convert')
        body, _ = _normalize_config_body(device_load.document.get('config'))
        prev_rev = device_load.revision if device_load.revision is not None \
            else 0
        document = build_device_document(body, prev_rev + 1)
        write = _write_device_document(document)
        if not write.ok:
            return SaveResult('error', error=write.error)
        cs = _reload_and_apply()
        return SaveResult('saved', config=cs.effective,
                          message='Device configuration upgraded.')


# ---------------------------------------------------------------------------
# Older-schema Group upgrade candidate (§50)
# ---------------------------------------------------------------------------

def build_group_upgrade_candidate():
    """Generate an upgraded Group JSON candidate (§50). Never written locally.

    group_revision = previous + 1. The user updates the Group key in NCM;
    validation then confirms the new schema/revision.
    """
    with _config_lock:
        group_load = _load_layer('group')
        if group_load.status != 'older' or group_load.document is None:
            return None
        body, _ = _normalize_config_body(group_load.document.get('config'))
        prev_rev = group_load.revision if group_load.revision is not None \
            else 0
        document = build_group_document(body, prev_rev + 1)
        return GroupCandidate(document)


# ---------------------------------------------------------------------------
# Group Migration (§23-§34) -- selection-only, group-first, non-destructive
# ---------------------------------------------------------------------------

# Section labels for wizard presentation.
SECTION_LABELS = {
    'schedule': 'Scheduled Testing',
    'outputs': 'Outputs',
    'iperf3_server_settings': 'iPerf3 Server Mode',
    'iperf3_user_servers': 'User iPerf3 Servers',
    'netperf_servers': 'Netperf Servers',
    'geoview': 'GeoView Policy',
}


def migration_available_sections():
    """Return the configured Device sections eligible for Group promotion.

    Only sections present in the Device document are eligible. GeoView is
    special (§42): when its active source is manual/site-specific it is NOT
    promotable and defaults to Keep-on-Device.

    Returns a list of dicts: {section, label, default_selected, promotable,
    reason}.
    """
    with _config_lock:
        device_load = _load_layer('device')
        device_body = _device_body(device_load)
        result = []
        for section in SECTION_NAMES:
            if section not in device_body:
                continue
            promotable = True
            reason = ''
            default_selected = True
            if section == 'geoview':
                if not _geoview_group_safe(device_body[section]):
                    promotable = False
                    default_selected = False
                    reason = ('GeoView uses device-specific location data '
                              '(manual coordinates or site address) and cannot '
                              'be promoted to a Group standard. Change GeoView '
                              'to Device GPS and save before migrating.')
            result.append({
                'section': section,
                'label': SECTION_LABELS.get(section, section),
                'default_selected': default_selected,
                'promotable': promotable,
                'reason': reason,
            })
        return result


def _geoview_group_safe(geoview_section):
    """True when a GeoView section is safe to promote to a Group standard.

    Group-safe means the active location source is a POLICY (device_gps), not
    device-specific coordinates/address (§40, §42).
    """
    try:
        source = geoview_section.get('active_location_source')
    except AttributeError:
        return False
    return source == 'device_gps'


def _sanitize_geoview_for_group(geoview_section):
    """Return a Group-safe GeoView section with device-specific data stripped.

    For device_gps policy, current coordinates are NOT copied into Group (§40).
    """
    return cellular_geo.group_sanitized_geoview(geoview_section)


def validate_migration_selection(selected_sections):
    """Validate a proposed Group selection without editing values (§27).

    Returns (ok, reason). Prevents creation of an internally invalid Group
    standard by reusing dependency rules: if iperf3_server_settings is promoted
    with server_mode=user, iperf3_user_servers must also be promoted and
    non-empty; if a promoted schedule references user iPerf3, the user server
    list must be promoted too.
    """
    with _config_lock:
        device_load = _load_layer('device')
        device_body = _device_body(device_load)

        selected = set(selected_sections)
        for s in selected:
            if s not in device_body:
                return (False, 'Selected section "%s" is not configured on '
                        'this Device.' % s)
            if s == 'geoview' and not _geoview_group_safe(device_body[s]):
                return (False, 'GeoView cannot be promoted while it uses '
                        'device-specific location data.')

        settings = device_body.get('iperf3_server_settings')
        if 'iperf3_server_settings' in selected and isinstance(settings, dict) \
                and settings.get('server_mode') == 'user':
            user_servers = device_body.get('iperf3_user_servers')
            if 'iperf3_user_servers' not in selected:
                return (False, 'iPerf3 Server Mode is set to User servers, so '
                        'User iPerf3 Servers must also be promoted to the '
                        'Group.')
            if not isinstance(user_servers, list) or not user_servers:
                return (False, 'iPerf3 Server Mode is set to User servers but '
                        'no User iPerf3 Servers are configured. Cancel, '
                        'configure servers, and restart migration.')

        schedule = device_body.get('schedule')
        if 'schedule' in selected and isinstance(schedule, dict) \
                and schedule.get('engine') == 'iperf3':
            # A promoted iperf3 schedule needs a promoted user server list when
            # the promoted/effective server mode is user.
            effective_mode = None
            if 'iperf3_server_settings' in selected and \
                    isinstance(settings, dict):
                effective_mode = settings.get('server_mode')
            if effective_mode == 'user' and \
                    'iperf3_user_servers' not in selected:
                return (False, 'The scheduled iPerf3 test depends on User '
                        'iPerf3 Servers, which must also be promoted.')

        return (True, '')


def build_group_migration_candidate(selected_sections):
    """Build the Group candidate document from selected Device sections (§28).

    Validates the selection first. Copies ONLY the selected sections into the
    Group candidate (section-sparse). GeoView is sanitized (§40). group_revision
    = 1 for an initial Device->Group migration. Nothing is written locally.

    Returns (GroupCandidate, reason). candidate is None on validation failure.
    """
    with _config_lock:
        # "Migrate to NCM Group" is the pure Device -> Group administrative
        # migration only (§23). If a Group key already exists, the router is
        # already Group-managed and this workflow is not applicable.
        group_load, device_load = load_layers()
        if group_load.present:
            return (None, 'This router already has an NCM Group configuration; '
                    'the Device-to-Group migration does not apply.')
        if not device_load.present:
            return (None, 'There is no Device configuration to migrate.')

        ok, reason = validate_migration_selection(selected_sections)
        if not ok:
            return None, reason

        device_body = _device_body(device_load)

        group_body = {}
        for section in SECTION_NAMES:
            if section not in selected_sections:
                continue
            if section not in device_body:
                continue
            if section == 'geoview':
                group_body[section] = _sanitize_geoview_for_group(
                    device_body[section])
            else:
                group_body[section] = json.loads(
                    json.dumps(device_body[section]))

        document = build_group_document(group_body, 1)
        return GroupCandidate(document), ''


def validate_group_present(expected_revision=1):
    """Validate that the expected Group payload is visible on device (§30).

    Checks: exact key exists, JSON parses, document_type=group, expected
    schema_version, expected group_revision. Does NOT claim NCM provenance.
    Does NOT mutate the Device document. Returns a ValidationResult.
    """
    with _config_lock:
        group_load = _load_layer('group')
        if group_load.status == 'absent':
            return ValidationResult(
                False, 'Group configuration is not visible yet. The NCM '
                       'change may still be synchronizing.')
        if group_load.status != 'ok' or group_load.document is None:
            return ValidationResult(
                False, 'Group configuration payload did not validate (%s).'
                       % group_load.status)
        if group_load.revision != expected_revision:
            return ValidationResult(False, 'Group revision mismatch.')
        # Payload validated on device (NOT provenance-verified).
        return ValidationResult(True, 'Group configuration payload validated '
                                'on device.', document=group_load.document)


def trim_promoted_device_sections(promoted_sections):
    """Remove promoted sections from the Device document AFTER Group validates.

    Sequence (§31, §32): only call this once ``validate_group_present`` has
    succeeded. Removes ONLY the promoted sections; keeps deselected sections.
    If the Device config still has sections, rewrite once with device_revision
    +1. If empty, delete the Device key. Recompute + hot-apply effective config.

    Returns a SaveResult. On partial failure (§34) the Group document is left
    intact and the condition is reported.
    """
    with _config_lock:
        group_load, device_load = load_layers()
        if not (group_load.usable and group_load.present):
            return SaveResult('error',
                              error='Group configuration is not validated; '
                                    'refusing to trim Device sections.')
        if not device_load.present:
            # Nothing to trim; already pure Group.
            cs = _reload_and_apply()
            return SaveResult('saved', config=cs.effective)

        device_body = dict(_device_body(device_load))
        for section in promoted_sections:
            if section in device_body:
                del device_body[section]

        current_dev_rev = device_load.revision if (
            device_load.revision is not None) else 0

        if not device_body:
            # Only reached AFTER the Group validated present (guard at top).
            cp.log('Config[trim]: Device emptied by cleanup -> DELETING '
                   'device key (group validated present, prev device_rev=%s)'
                   % current_dev_rev)
            if not _delete_device_document():
                return SaveResult(
                    'error',
                    error='Group configuration validated. Device override '
                          'cleanup incomplete: unable to delete Device key. '
                          'Retry cleanup.')
        else:
            cp.log('Config[trim]: rewriting Device with remaining sections=%s '
                   'device_rev=%s->%s (group validated present)'
                   % (sorted(device_body.keys()), current_dev_rev,
                      current_dev_rev + 1))
            document = build_device_document(device_body, current_dev_rev + 1)
            write = _write_device_document(document)
            if not write.ok:
                return SaveResult(
                    'error',
                    error='Group configuration validated. Device override '
                          'cleanup incomplete: %s. Retry cleanup.'
                          % write.error)

        cs = _reload_and_apply()
        return SaveResult('saved', config=cs.effective,
                          message='Migration complete.')


# ---------------------------------------------------------------------------
# Update NCM Group Configuration (v1.1.2) -- promote selected Device overrides
# into an EXISTING Group standard.
#
# Distinct from "Migrate to NCM Group" (which is the pure Device -> Group first
# migration and is offered ONLY in the pure Device state). Update starts from a
# DEEP COPY of the CURRENT speedtest_analyzer_group document and replaces/adds
# ONLY the selected Device override sections. It NEVER rebuilds the Group from
# Device, never copies Built-in Defaults into the Group, and never removes
# unrelated Group sections. group_revision = current + 1. The app performs ZERO
# local writes/deletes to the Group key -- the administrator updates the value
# in NCM and validates it.
# ---------------------------------------------------------------------------


def _revision_pair(group_load=None, device_load=None):
    """Return the (group_revision|None, device_revision|None) pair for tokens.

    None when a layer is absent (distinct from revision 0). Used to detect any
    change to either layer during the staged Update workflow (§46).
    """
    if group_load is None or device_load is None:
        group_load, device_load = load_layers()
    g = group_load.revision if (group_load.usable and group_load.present) \
        else None
    d = device_load.revision if (device_load.usable and device_load.present) \
        else None
    return {'group_revision': g, 'device_revision': d}


def update_group_available_sections():
    """Return the current Device override sections eligible for Group update.

    Only sections present in the Device document are shown (§ "show ONLY current
    Device overrides"). GeoView follows the existing safety rules: manual/site
    coordinates are NOT promotable; a device_gps policy is promotable with
    runtime coordinates stripped. Reuses migration_available_sections, which is
    already exactly "current Device overrides + GeoView promotability".
    """
    return migration_available_sections()


def validate_group_update_selection(selected_sections):
    """Validate a proposed Group-UPDATE selection (§ dependency validation).

    Unlike the initial migration (which validates the selection in isolation),
    an Update merges promoted sections onto the EXISTING Group. Dependency
    validation therefore runs against the PROPOSED REVISED GROUP body: e.g. a
    promoted Schedule that references a User iPerf server is valid when the
    revised Group's effective server mode is User (already in Group, or also
    promoted) with a non-empty User server list present in the revised Group.

    Returns (ok, reason).
    """
    with _config_lock:
        group_load, device_load = load_layers()
        if not (group_load.usable and group_load.present):
            return (False, 'There is no NCM Group configuration to update.')
        if not device_load.present:
            return (False, 'There are no Device overrides to promote.')

        device_body = _device_body(device_load)
        group_body = _group_body(group_load)

        selected = list(selected_sections)
        for s in selected:
            if s not in device_body:
                return (False, 'Selected section "%s" is not a Device '
                        'override.' % s)
            if s == 'geoview' and not _geoview_group_safe(device_body[s]):
                return (False, 'GeoView cannot be promoted while it uses '
                        'device-specific location data.')

        # Build the proposed revised Group body: existing Group sections, with
        # selected Device sections replacing/adding (GeoView sanitized).
        revised = _build_group_update_body(group_body, device_body, selected)

        # iPerf3 server-mode / user-server-list dependency in the REVISED Group.
        settings = revised.get('iperf3_server_settings')
        if isinstance(settings, dict) and settings.get('server_mode') == \
                'user':
            servers = revised.get('iperf3_user_servers')
            if not isinstance(servers, list) or not servers:
                return (False, 'The revised Group sets iPerf3 Server Mode to '
                        'User servers but has no User iPerf3 Servers. Promote '
                        'User iPerf3 Servers as well, or configure them in the '
                        'Group first.')

        # A scheduled iPerf3 test in the revised Group must agree with the
        # revised Group server mode (reuse the effective dependency validator).
        ok, conflict = check_effective_dependencies(revised)
        if not ok:
            return (False, conflict.get('reason', 'The revised Group '
                    'configuration would be internally inconsistent.'))

        return (True, '')


def _build_group_update_body(group_body, device_body, selected_sections):
    """Return the proposed revised Group body (deep copy + selected sections).

    Starts from a DEEP COPY of the current Group body. For each selected
    section that is a Device override, the Device value replaces/adds the Group
    section (GeoView sanitized for Group). Unselected sections and unrelated
    Group sections are left exactly as-is. Never adds Built-in Defaults.
    """
    revised = json.loads(json.dumps(group_body if isinstance(group_body, dict)
                                    else {}))
    device_body = device_body if isinstance(device_body, dict) else {}
    for section in SECTION_NAMES:
        if section not in selected_sections:
            continue
        if section not in device_body:
            continue
        if section == 'geoview':
            revised[section] = _sanitize_geoview_for_group(
                device_body[section])
        else:
            revised[section] = json.loads(json.dumps(device_body[section]))
    return revised


def build_group_update_candidate(selected_sections):
    """Build the revised Group candidate for an EXISTING Group (§ Update).

    Validates the selection against the proposed revised Group, deep-copies the
    current Group, promotes ONLY the selected Device sections, and sets
    group_revision = current + 1. Nothing is written locally.

    Returns (GroupCandidate, reason, token). candidate is None on failure.
    ``token`` is the reconciliation pair captured at build time.
    """
    with _config_lock:
        group_load, device_load = load_layers()
        if not (group_load.usable and group_load.present):
            return (None, 'There is no NCM Group configuration to update.',
                    None)
        if not device_load.present:
            return (None, 'There are no Device overrides to promote.', None)

        ok, reason = validate_group_update_selection(selected_sections)
        if not ok:
            return None, reason, None

        group_body = _group_body(group_load)
        device_body = _device_body(device_load)
        revised = _build_group_update_body(group_body, device_body,
                                           selected_sections)

        current_rev = group_load.revision if group_load.revision is not None \
            else 0
        document = build_group_document(revised, current_rev + 1)
        token = _revision_pair(group_load, device_load)
        # Diagnostic: this path is READ-ONLY (no Device write/delete). Log the
        # revision pair + override list so an intermittent "no overrides" report
        # can be traced against what the backend actually saw.
        cp.log('Config[update_group]: candidate built group_rev=%s->%s '
               'device_rev=%s overrides=%s selected=%s (no Device write)'
               % (token.get('group_revision'), document.get('group_revision'),
                  token.get('device_revision'),
                  override_sections(group_body, device_body),
                  list(selected_sections)))
        return GroupCandidate(document), '', token


def validate_group_update(expected_revision, token=None):
    """Validate the revised Group payload is visible at expected_revision.

    Reuses validate_group_present (exact key / document_type=group / schema /
    expected revision). When a reconciliation ``token`` is provided, the DEVICE
    revision is also checked: if the Device changed since the candidate was
    built, the staged workflow is aborted (§46). Never mutates the Device doc.

    Returns a ValidationResult; on a token mismatch reason explains the abort.
    """
    with _config_lock:
        if token is not None:
            device_load = _load_layer('device')
            current_device_rev = (device_load.revision
                                  if (device_load.usable and
                                      device_load.present) else None)
            if current_device_rev != token.get('device_revision'):
                cp.log('Config[update_group]: validate ABORTED (reconcile) '
                       'token_device_rev=%s current_device_rev=%s '
                       'device_present=%s (no Device write)'
                       % (token.get('device_revision'), current_device_rev,
                          device_load.present))
                return ValidationResult(
                    False, 'The Device configuration changed during this '
                           'workflow. Restart the Group update so stale '
                           'changes are not merged.',
                    reconcile_aborted=True)
        result = validate_group_present(expected_revision)
        cp.log('Config[update_group]: validate expected_group_rev=%s ok=%s '
               '(read-only, no Device write)'
               % (expected_revision, result.ok))
        return result


def cleanup_promoted_after_group_update(promoted_sections, token=None):
    """Remove promoted Device sections AFTER the revised Group validated.

    Reuses trim_promoted_device_sections. When a reconciliation ``token`` is
    provided, the Device revision is re-checked first so a Device change during
    the staged workflow aborts cleanup instead of trimming stale sections. On a
    trim failure the Group is left intact and cleanup_incomplete is returned so
    Device continues to win (§34); the caller may Retry Cleanup.

    Returns a SaveResult.
    """
    with _config_lock:
        if token is not None:
            device_load = _load_layer('device')
            current_device_rev = (device_load.revision
                                  if (device_load.usable and
                                      device_load.present) else None)
            if current_device_rev != token.get('device_revision'):
                cp.log('Config[update_group]: cleanup ABORTED (reconcile) '
                       'token_device_rev=%s current_device_rev=%s '
                       '(no Device delete/write)'
                       % (token.get('device_revision'), current_device_rev))
                aborted = SaveResult(
                    'error',
                    error='The Device configuration changed during this '
                          'workflow. Restart the Group update.')
                aborted.reconcile_aborted = True
                return aborted
        cp.log('Config[update_group]: cleanup trimming promoted=%s '
               '(Group already validated present)' % list(promoted_sections))
        return trim_promoted_device_sections(promoted_sections)


# ---------------------------------------------------------------------------
# Reset section to Group / Reset all Device overrides (§36, §37, §38)
# ---------------------------------------------------------------------------

def _reset_target_for(section, group_body):
    """Return the reset destination for a section: 'group' or 'default'.

    A section resets to Group when the section KEY EXISTS in the Group layer
    (by presence, never truthiness), else to built-in Default.
    """
    return 'group' if section in group_body else 'default'


def _reset_message(section, reset_target):
    """Backend-derived reset success wording (§ reset wording bug).

    Says exactly where the section reset TO -- the NCM Group configuration or
    the Built-in Default -- instead of always claiming "NCM Group".
    """
    label = SECTION_LABELS.get(section, section)
    if reset_target == 'group':
        return '%s reset to the NCM Group configuration.' % label
    return '%s reset to the Built-in Default.' % label


def _validate_proposed_effective(group_body, proposed_device_body):
    """Validate the effective config that a proposed Device body would produce.

    Returns (ok, conflict). conflict is the dict from
    check_effective_dependencies (or None).
    """
    proposed_effective = compute_effective(group_body, proposed_device_body)
    return check_effective_dependencies(proposed_effective)


def reset_section_to_group(section, confirm_sections=None):
    """Remove a Device override section so the inherited value is used (§36).

    Requires Group present (a reset always inherits Group or Built-in Default).
    Before persisting, the PROPOSED effective config (Device>Group>Default) is
    validated. If removing the requested section alone would create a dependency
    conflict (the confirmed iPerf3 schedule <-> server-mode defect), returns
    status='dependency_reset_required' with the coupled sections; NOTHING is
    written. The caller re-invokes with ``confirm_sections`` covering all
    required sections to perform ONE atomic coupled reset (one revision, one
    hot reload). The final effective config is validated again before write.
    """
    with _config_lock:
        group_load, device_load = load_layers()
        if not (group_load.usable and group_load.present):
            return SaveResult('error',
                              error='No Group configuration to reset to.')
        if not device_load.present:
            return SaveResult('error', error='No Device overrides to reset.')

        group_body = _group_body(group_load)
        device_body = dict(_device_body(device_load))
        if section not in device_body:
            return SaveResult('error',
                              error='Section "%s" is not a Device override.'
                                    % section)

        reset_target = _reset_target_for(section, group_body)

        # Determine the set of sections to remove.
        if confirm_sections:
            remove_set = [s for s in SECTION_NAMES if s in confirm_sections]
            # Guard: only sections that are actually Device overrides.
            for s in remove_set:
                if s not in device_body:
                    return SaveResult(
                        'error',
                        error='Section "%s" is not a Device override.' % s)
            if section not in remove_set:
                remove_set.append(section)
        else:
            remove_set = [section]

        # Build the proposed Device body after removing the requested set.
        proposed = dict(device_body)
        for s in remove_set:
            proposed.pop(s, None)

        # Validate the proposed effective configuration.
        ok, conflict = _validate_proposed_effective(group_body, proposed)
        if not ok:
            if not confirm_sections:
                # First (unconfirmed) attempt: surface the coupled reset that
                # would make the effective config valid. Removing BOTH the
                # requested section and the conflicting overriding section(s)
                # resolves the dependency; only include sections that are
                # actually Device overrides (so we never claim to reset an
                # inherited section).
                required = []
                for s in conflict.get('sections', []):
                    if s in device_body and s not in required:
                        required.append(s)
                if section not in required:
                    required.insert(0, section)
                return SaveResult(
                    'dependency_reset_required',
                    config=get_effective_config(),
                    dependency={
                        'requested_section': section,
                        'requested_label': SECTION_LABELS.get(section, section),
                        'required_reset_sections': required,
                        'required_reset_labels': [
                            SECTION_LABELS.get(s, s) for s in required],
                        'reason': conflict.get('reason', ''),
                        'reset_target': reset_target,
                    })
            # A confirmed reset that STILL leaves an inconsistent config is a
            # bad request; refuse rather than persist an invalid effective.
            return SaveResult(
                'error',
                error=('The selected reset would still leave an incompatible '
                       'configuration: %s' % conflict.get('reason', '')))

        current_dev_rev = device_load.revision if (
            device_load.revision is not None) else 0

        if not proposed:
            if not _delete_device_document():
                return SaveResult('error',
                                  error='Unable to remove Device configuration.')
        else:
            document = build_device_document(proposed, current_dev_rev + 1)
            write = _write_device_document(document)
            if not write.ok:
                return SaveResult('error', error=write.error)

        cs = _reload_and_apply()
        if len(remove_set) > 1:
            labels = ', '.join(SECTION_LABELS.get(s, s) for s in remove_set)
            message = ('%s reset. The dependent sections were reset together '
                       'to keep the configuration consistent.' % labels)
        else:
            message = _reset_message(section, reset_target)
        return SaveResult('saved', config=cs.effective, message=message,
                          reset_target=reset_target)


def reset_all_device_overrides():
    """Delete the Device key when Group exists (§37), or perform a Device-only
    reset with legacy suppression when Group is absent (§38).

    §37: Group present -> delete speedtest_analyzer_device. Never delete Group.
    §38: Group absent, Device present -> if legacy migration sources still
    exist, KEEP a valid current-schema Device document with config={} and an
    incremented device_revision so legacy stays suppressed. If no legacy
    sources exist, delete the Device key and return to true Fresh/Defaults.
    """
    with _config_lock:
        group_load, device_load = load_layers()

        if group_load.usable and group_load.present:
            # Validate the FINAL effective config (Group + Default only, since
            # every Device override is removed) before persisting. Group is
            # authored in NCM; if the Group alone is internally inconsistent we
            # refuse rather than persist a Device delete that produces a broken
            # effective config. (Removing all Device overrides cannot create a
            # NEW dependency the Group did not already carry, but this keeps the
            # write gated on a valid final effective, matching the reset rule.)
            final_effective = compute_effective(_group_body(group_load), {})
            ok, conflict = check_effective_dependencies(final_effective)
            if not ok:
                return SaveResult(
                    'error',
                    config=get_effective_config(),
                    error=('Resetting all Device overrides would leave an '
                           'incompatible NCM Group configuration: %s'
                           % conflict.get('reason', '')))
            if device_load.present:
                if not _delete_device_document():
                    return SaveResult('error',
                                      error='Unable to remove Device '
                                            'configuration.')
            cs = _reload_and_apply()
            return SaveResult('saved', config=cs.effective,
                              message='All Device overrides removed. NCM Group '
                                      'configuration is now effective.')

        # Group absent.
        if not device_load.present:
            cs = _reload_and_apply()
            return SaveResult('saved', config=cs.effective,
                              message='No Device configuration to reset.')

        current_dev_rev = device_load.revision if (
            device_load.revision is not None) else 0

        if has_legacy_migration_sources():
            # §38: keep an empty current-schema Device doc to suppress legacy.
            document = build_device_document({}, current_dev_rev + 1)
            write = _write_device_document(document)
            if not write.ok:
                return SaveResult('error', error=write.error)
            cs = _reload_and_apply()
            return SaveResult('saved', config=cs.effective,
                              message='Device configuration reset to built-in '
                                      'defaults.')

        # No legacy sources: safe to return to true Fresh/Defaults.
        if not _delete_device_document():
            return SaveResult('error',
                              error='Unable to remove Device configuration.')
        cs = _reload_and_apply()
        return SaveResult('saved', config=cs.effective,
                          message='Device configuration removed. Built-in '
                                  'defaults active.')


# ---------------------------------------------------------------------------
# Factory Reset inventory (§58)
# ---------------------------------------------------------------------------

class FactoryResetOutcome(object):
    def __init__(self, removed_appdata, removed_files, kept_group, message=''):
        self.removed_appdata = removed_appdata
        self.removed_files = removed_files
        self.kept_group = kept_group
        self.message = message


def factory_reset_inventory():
    """Return the exact Speedtest Analyzer-owned persistent state to remove.

    NEVER includes speedtest_analyzer_group (externally/Group owned, §58) and
    never includes unrelated NCOS/device configuration.
    """
    return {
        'appdata': [
            DEVICE_KEY,
            EXPERIMENTAL_KEY,
            LEGACY_SCHEDULE_KEY,
            LEGACY_IPERF3_SETTINGS_KEY,
            LEGACY_IPERF3_SERVERS_KEY,
            LEGACY_NETPERF_SERVERS_KEY,
            LEGACY_OUTPUTS_KEY,
            LEGACY_GEOVIEW_KEY,
            RUNTIME_RESULTS_KEY,
            RUNTIME_IPERF3_STATS_KEY,
        ],
        'tmp_files': [
            'tmp/speedtest_history.json',
            'tmp/speedtest_history.json.bak',
            'tmp/speedtest_history.json.tmp',
            'tmp/speedtest_history.json.corrupt',
            'tmp/saved_reports.json',
        ],
    }


def factory_reset(clear_history_fn=None):
    """Remove Speedtest Analyzer-owned persistent local state (§58).

    NEVER writes/deletes speedtest_analyzer_group. When Group is present, the
    Group configuration is kept and becomes effective again after local data is
    cleared. ``clear_history_fn`` is the existing history-clear implementation
    (reused, not reimplemented).
    """
    with _config_lock:
        group_load = _load_layer('group')
        group_present = group_load.usable and group_load.present

        inventory = factory_reset_inventory()
        removed_appdata = []
        removed_files = []

        for key in inventory['appdata']:
            # Never touch the Group key (defensive; it is not in the inventory).
            if key == GROUP_KEY:
                continue
            try:
                cp.delete_appdata(key)
                removed_appdata.append(key)
            except Exception as exc:
                cp.log('Config: factory reset could not remove %s: %s'
                       % (key, exc))

        if clear_history_fn is not None:
            try:
                clear_history_fn()
            except Exception as exc:
                cp.log('Config: factory reset history clear error: %s' % exc)

        for path in inventory['tmp_files']:
            try:
                if os.path.exists(path):
                    os.remove(path)
                    removed_files.append(path)
            except Exception as exc:
                cp.log('Config: factory reset could not remove %s: %s'
                       % (path, exc))

        cs = _reload_and_apply()
        _run_hot_reload(cs.effective)
        if group_present:
            message = ('Local data and history cleared. NCM Group '
                       'configuration is now effective.')
        else:
            message = ('Speedtest Analyzer local data cleared. Built-in '
                       'defaults active.')
        return FactoryResetOutcome(removed_appdata, removed_files,
                                   group_present, message)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

def initialize():
    """Startup entry point: load effective config and hot-reload subsystems.

    NEVER persists anything. When no canonical key exists, built-in defaults
    (Day-1) or the legacy compatibility view (upgrade_required) become the
    effective RAM configuration WITHOUT any write. Configuration mutation stays
    blocked when the derived state requires it.
    """
    # Recompute effective config and hot-apply runtime subsystems (except in
    # hard error/unsupported states, where we do not pretend compatibility).
    return _reload_and_apply()


# ---------------------------------------------------------------------------
# State reporting for the API (§53)
# ---------------------------------------------------------------------------

def state_report():
    """Return the full configuration state dict for /api/config/state (§53).

    This is a pure read: it recomputes/caches effective state but does NOT
    hot-apply to runtime (a status poll must not restart subsystems).
    """
    with _config_lock:
        cs = load_effective_config()
        group_load = cs.group_load
        device_load = cs.device_load

        block = cs.mutation_block
        report = {
            'current_schema_version': CURRENT_SCHEMA_VERSION,
            'state': cs.state,
            'group_present': cs.group_present,
            'group_revision': (group_load.revision
                               if group_load.revision is not None else None),
            'group_schema_version': group_load.schema_version,
            'device_present': cs.device_present,
            'device_revision': (device_load.revision
                                if device_load.revision is not None else None),
            'device_schema_version': device_load.schema_version,
            'override_sections': cs.override_sections,
            'override_section_labels': [
                SECTION_LABELS.get(s, s) for s in cs.override_sections],
            # Backend-derived per-section source (device|group|default) by
            # SECTION PRESENCE. The UI maps these to friendly labels.
            'effective_section_sources': effective_section_sources(
                _group_body(group_load), _device_body(device_load)),
            # Per-override detail cards: label, safe compact summary, and the
            # reset destination (group when the section exists in Group, else
            # default). Derived by presence; does not change merge behavior.
            'override_details': override_details(
                _group_body(group_load), _device_body(device_load)),
            'legacy_upgrade_required': cs.legacy_upgrade_required,
            'mutation_blocked': block is not None,
            'mutation_block_reason': block.reason if block else None,
            'mutation_block_detail': block.detail if block else None,
            # "Migrate to NCM Group" is the Device-managed -> Group-standard
            # administrative migration ONLY (§23). It is offered exclusively in
            # the pure Device state with mutation unblocked. A router that
            # already has speedtest_analyzer_group is already Group-managed, so
            # group / group_with_device_overrides do NOT offer migration;
            # promoting existing Device overrides into an existing Group is a
            # separate future workflow, not part of v1.1.2.
            'can_migrate_to_group': (cs.state == STATE_DEVICE and
                                     block is None),
            # "Update NCM Group Configuration" promotes selected Device
            # overrides into an EXISTING Group. Offered ONLY when a Group
            # already exists AND Device overrides exist (state
            # group_with_device_overrides) with mutation unblocked. It never
            # reappears as "Migrate to NCM Group".
            'can_update_group': (
                cs.state == STATE_GROUP_WITH_DEVICE_OVERRIDES and
                block is None),
        }
        return report
