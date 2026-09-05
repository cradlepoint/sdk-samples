"""Device-scoped provider credential storage for GeoView (v1.1.3).

This module is the ONLY place permitted to interact with
``config/certmgmt/certs`` or to call :func:`cp.decrypt`. It owns the entire
lifecycle of the provider credential material used by GeoView.

v1.1.3 splits the geo secrets across TWO independent certmgmt records so that
the server-side keys and the browser key have separate lifecycles and the
browser key can be handed out without ever touching a server key:

    * ``speedtest_analyzer_geo_server`` -- server-side keys only:
        - ``api_key``        : private Google SERVER key (Geocoding only).
        - ``opencellid_key`` : OpenCellID cell-database key (cell lookup).
      NEITHER value is ever returned to the browser, logged, or exported.
    * ``speedtest_analyzer_geo_mapjs``  -- browser key only:
        - ``maps_js_api_key``: Google BROWSER Maps JavaScript key. This is the
          ONLY credential field permitted to leave the router (via the
          narrowly scoped /api/geo/mapjs endpoint).

Legacy migration: the earlier single record ``speedtest_analyzer_geo_google``
carried both ``api_key`` and ``maps_js_api_key``. On read it is transparently
split into the two new records; the legacy record is deleted ONLY after both
new records are written AND read-back/decrypt verified, so a crash mid-migrate
never loses a key.

Public surface (unchanged for existing callers):
    * ``resolve_device('google')`` -> CredentialStatus whose transient
      ``bundle`` MERGES both records ({api_key, opencellid_key,
      maps_js_api_key}); ``is_configured`` requires the server record complete.
    * ``maps_js_api_key('google')`` -> browser Maps JS key string or None.
    * ``update_device`` / ``clear_device`` / ``status_all`` -> logical google
      provider metadata (compat shims over the record model).
    * ``record_status_all`` / ``update_record`` / ``clear_record`` -> per-record
      metadata + write-only mutation for the split-key GeoView config UX.
    * ``scrub`` -> log/exception secret redaction.

Security posture (non-negotiable): secret values never appear in logs,
exceptions, API payloads, or any returned status object. Status objects expose
metadata only. The write path is write-only from the UI: reads never return
secrets. The credential field is stored in the NCOS ``certmgmt`` ``key`` field
(``encrypt:true``); on-router ``cp.decrypt()`` recovers it. No custom crypto.
"""

import json
import threading

import cp


# ---------------------------------------------------------------------------
# Stable record identity (application-owned).
#
# Reusing a stable ``name`` ensures a credential replacement UPDATES the
# existing cert object rather than creating a duplicate.
# ---------------------------------------------------------------------------
GEO_CERT_SERVER_DEVICE = 'speedtest_analyzer_geo_server'
GEO_CERT_MAPJS_DEVICE = 'speedtest_analyzer_geo_mapjs'
# Legacy single record migrated (then removed) by this module.
GEO_CERT_LEGACY_GOOGLE_DEVICE = 'speedtest_analyzer_geo_google'

# Record identifiers (the split-key model). These are the credential-bearing
# certmgmt records the app owns and manages.
RECORD_SERVER = 'server'
RECORD_MAPJS = 'mapjs'

_CERT_NAME_BY_RECORD = {
    RECORD_SERVER: GEO_CERT_SERVER_DEVICE,
    RECORD_MAPJS: GEO_CERT_MAPJS_DEVICE,
}

# Managed fields per record. The three geo services are INDEPENDENT, so no
# single server field is mandatory: the server record is valid when it carries
# AT LEAST ONE of its managed fields (``_RECORD_MIN_ONE`` records). The mapjs
# record's single field is effectively that one-of requirement too.
_RECORD_FIELDS = {
    # api_key       -> Google server geocoding key (Site Address only)
    # opencellid_key-> OpenCellID cell-database key (cellular resolver)
    RECORD_SERVER: ('api_key', 'opencellid_key'),
    RECORD_MAPJS: ('maps_js_api_key',),
}
# Records considered valid when at least one managed field is present.
_RECORD_MIN_ONE = (RECORD_SERVER, RECORD_MAPJS)

# Legacy fields possibly present in a very old server-style bundle. Silently
# dropped during normalization.
_RECORD_LEGACY_FIELDS = {
    RECORD_SERVER: ('url_signing_secret',),
    RECORD_MAPJS: (),
}

_CERTS_PATH = 'config/certmgmt/certs'

_SCHEMA_VERSION = 1

# Credential state values surfaced to callers (metadata only).
STATE_CONFIGURED = 'configured'
STATE_MISSING = 'missing'
STATE_INVALID = 'invalid'

_lock = threading.RLock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def supported_record(record):
    """Return the normalized record key if managed, else None."""
    key = str(record or '').strip().lower()
    return key if key in _CERT_NAME_BY_RECORD else None


def supported_provider(provider):
    """Return a normalized service key for credential resolution, else None.

    The three geo services are INDEPENDENT (no single logical Google
    provider):
        * ``opencellid`` -> cellular serving-location resolver (server record
          ``opencellid_key``).
        * ``google``     -> Site Address forward-geocoding ONLY (server record
          ``api_key``). This is NOT a cellular-location provider.
    The browser Maps JS key is a third independent service accessed via
    :func:`maps_js_api_key_value`.
    """
    key = str(provider or '').strip().lower()
    return key if key in ('opencellid', 'google') else None


def _non_empty_str(value):
    return isinstance(value, str) and value.strip() != ''


def validate_record_bundle(record, bundle):
    """Validate a decoded bundle for a certmgmt ``record``.

    Never inspects or returns secret values; only reports validity. Unknown
    extra fields cause rejection (conservative Device-write policy).
    """
    key = supported_record(record)
    if key is None or not isinstance(bundle, dict):
        return False
    if bundle.get('schema_version') != _SCHEMA_VERSION:
        return False

    managed = _RECORD_FIELDS[key]

    # Each present managed field must be a non-empty string.
    present = 0
    for field in managed:
        if field in bundle:
            if not _non_empty_str(bundle.get(field)):
                return False
            present += 1

    # A one-of record must carry at least one managed field.
    if key in _RECORD_MIN_ONE and present == 0:
        return False

    allowed = set(managed) | {'schema_version'}
    if set(bundle.keys()) - allowed:
        return False
    return True


def normalize_record_bundle(record, bundle):
    """Return a canonical-shaped copy of ``bundle`` for ``record``.

    Strips legacy/unknown fields, preserving only current managed fields plus
    ``schema_version``. Values are copied verbatim (never logged). Returns
    ``None`` when ``bundle`` is not a usable dict.
    """
    key = supported_record(record)
    if key is None or not isinstance(bundle, dict):
        return None
    canonical = {'schema_version': _SCHEMA_VERSION}
    for field in _RECORD_FIELDS[key]:
        if field in bundle and _non_empty_str(bundle.get(field)):
            canonical[field] = bundle.get(field)
    return canonical


def _has_legacy_record_fields(record, bundle):
    key = supported_record(record)
    if key is None or not isinstance(bundle, dict):
        return False
    return any(f in bundle for f in _RECORD_LEGACY_FIELDS.get(key, ()))


# ---------------------------------------------------------------------------
# certmgmt lookup
# ---------------------------------------------------------------------------
def _find_cert_entry_by_name(name):
    """Return ``(_id_, entry)`` for the app-owned cert named ``name``.

    Returns ``(None, None)`` when no matching cert exists. Never returns or
    logs the encrypted key bytes.
    """
    try:
        certs = cp.get(_CERTS_PATH)
    except Exception as exc:
        cp.log('GeoView creds: certmgmt read error: %s' % _scrub(exc))
        return None, None

    if not isinstance(certs, list):
        return None, None

    for entry in certs:
        if not isinstance(entry, dict):
            continue
        if entry.get('name') == name:
            return entry.get('_id_'), entry
    return None, None


def _updated_ts(entry):
    """Best-effort non-secret 'updated' marker for a cert entry."""
    if not isinstance(entry, dict):
        return None
    for field in ('updated', 'modified', 'created'):
        value = entry.get(field)
        if value:
            return value
    return None


# ---------------------------------------------------------------------------
# Decrypt (transient, in-memory only)
# ---------------------------------------------------------------------------
def _decrypt_bundle(entry):
    """Decrypt and JSON-parse a cert's protected key field.

    Returns the decoded bundle dict, or ``None`` if unavailable/undecodable.
    The decrypted value is used transiently and is NEVER logged or returned in
    any status/API payload.
    """
    if not isinstance(entry, dict):
        return None
    cert_id = entry.get('_id_')
    if not cert_id:
        return None

    try:
        plaintext = cp.decrypt('%s/%s/key' % (_CERTS_PATH, cert_id))
    except Exception as exc:
        cp.log('GeoView creds: decrypt error: %s' % _scrub(exc))
        return None

    if plaintext in (None, ''):
        return None

    try:
        if isinstance(plaintext, (bytes, bytearray)):
            plaintext = plaintext.decode('utf-8')
        if isinstance(plaintext, str):
            return json.loads(plaintext)
        if isinstance(plaintext, dict):
            return plaintext
    except (ValueError, TypeError, UnicodeDecodeError):
        return None
    return None


# ---------------------------------------------------------------------------
# Low-level write / delete of a single record (Device scope)
# ---------------------------------------------------------------------------
def _cert_post_body(name, bundle):
    """Build the certmgmt POST/PUT body storing the bundle in the key field."""
    return {
        'name': name,
        # The protected, encrypt:true field. NCOS encrypts at rest.
        'key': json.dumps(bundle, separators=(',', ':')),
    }


def _write_record_bundle(record, bundle):
    """Create or replace a record's stored bundle. Returns True on success.

    Reuses the stable cert name so an existing cert is UPDATED, not duplicated.
    Never logs the value.
    """
    name = _CERT_NAME_BY_RECORD[record]
    body = _cert_post_body(name, bundle)
    cert_id, _ = _find_cert_entry_by_name(name)
    try:
        if cert_id is None:
            result = cp.post(_CERTS_PATH, body)
        else:
            result = cp.put('%s/%s/key' % (_CERTS_PATH, cert_id), body['key'])
    except Exception as exc:
        cp.log('GeoView creds: write error: %s' % _scrub(exc))
        return False
    if result is None or (
        isinstance(result, dict) and result.get('status') == 'error'
    ):
        return False
    return True


def _delete_cert_by_name(name):
    """Delete an app-owned cert by name. Idempotent. Returns True on success."""
    cert_id, _ = _find_cert_entry_by_name(name)
    if cert_id is None:
        return True
    try:
        cp.delete('%s/%s' % (_CERTS_PATH, cert_id))
    except Exception as exc:
        cp.log('GeoView creds: delete error: %s' % _scrub(exc))
        return False
    return True


def _read_record_bundle(record):
    """Return a normalized+valid stored bundle for ``record``, or None.

    Transient plaintext; never logged/returned as-is to any API surface.
    """
    name = _CERT_NAME_BY_RECORD[record]
    cert_id, entry = _find_cert_entry_by_name(name)
    if cert_id is None:
        return None
    bundle = _decrypt_bundle(entry)
    if bundle is None:
        return None
    canonical = normalize_record_bundle(record, bundle)
    if canonical is None:
        return None
    # In-place canonicalization when a legacy/unknown field was stripped.
    if _has_legacy_record_fields(record, bundle) and validate_record_bundle(
            record, canonical):
        try:
            cp.put('%s/%s/key' % (_CERTS_PATH, cert_id),
                   json.dumps(canonical, separators=(',', ':')))
            cp.log('GeoView creds: normalized %s record' % record)
        except Exception as exc:
            cp.log('GeoView creds: normalize write skipped: %s' % _scrub(exc))
    return canonical if validate_record_bundle(record, canonical) else None


# ---------------------------------------------------------------------------
# Legacy migration (split speedtest_analyzer_geo_google into two records)
# ---------------------------------------------------------------------------
def _migrate_legacy_if_present():
    """Split the legacy combined record into the server + mapjs records.

    Idempotent and crash-safe: the legacy record is deleted ONLY after both
    derived records are written AND read-back/decrypt verified. Never logs any
    key value. No-op when the legacy record is absent.
    """
    cert_id, entry = _find_cert_entry_by_name(GEO_CERT_LEGACY_GOOGLE_DEVICE)
    if cert_id is None:
        return

    legacy = _decrypt_bundle(entry)
    if not isinstance(legacy, dict):
        # Present but undecodable off-router (cp.decrypt is router-only): leave
        # it untouched so we never destroy an unread key.
        return

    api_key = legacy.get('api_key')
    maps_js = legacy.get('maps_js_api_key')

    # Build the derived records (server carries the old Google server key;
    # mapjs carries the browser key). opencellid_key did not exist in legacy.
    wrote_server = True
    if _non_empty_str(api_key):
        server_bundle = {'schema_version': _SCHEMA_VERSION,
                         'api_key': api_key.strip()}
        # Preserve any opencellid_key already written to the new server record.
        existing_server = _read_record_bundle(RECORD_SERVER) or {}
        if _non_empty_str(existing_server.get('opencellid_key')):
            server_bundle['opencellid_key'] = existing_server['opencellid_key']
        wrote_server = _write_record_bundle(RECORD_SERVER, server_bundle)

    wrote_mapjs = True
    if _non_empty_str(maps_js):
        mapjs_bundle = {'schema_version': _SCHEMA_VERSION,
                        'maps_js_api_key': maps_js.strip()}
        wrote_mapjs = _write_record_bundle(RECORD_MAPJS, mapjs_bundle)

    # Read-back verify before removing the legacy record.
    server_ok = (not _non_empty_str(api_key)) or (
        (_read_record_bundle(RECORD_SERVER) or {}).get('api_key')
        == (api_key.strip() if _non_empty_str(api_key) else None))
    mapjs_ok = (not _non_empty_str(maps_js)) or (
        maps_js_api_key_value() == (maps_js.strip()
                                    if _non_empty_str(maps_js) else None))

    if wrote_server and wrote_mapjs and server_ok and mapjs_ok:
        if _delete_cert_by_name(GEO_CERT_LEGACY_GOOGLE_DEVICE):
            cp.log('GeoView creds: migrated legacy geo record into '
                   'server + mapjs records')
    else:
        cp.log('GeoView creds: legacy migration deferred (read-back '
               'incomplete); legacy record preserved')


# ---------------------------------------------------------------------------
# Credential status (metadata only)
# ---------------------------------------------------------------------------
class CredentialStatus(object):
    """Immutable-ish metadata container. Holds the transient MERGED bundle
    only when CONFIGURED, for direct hand-off to a provider adapter within one
    call. The bundle is never serialized into status/API output.
    """

    __slots__ = ('provider', 'state', 'schema_version', 'updated', '_bundle')

    def __init__(self, provider, state, schema_version=None, updated=None,
                 bundle=None):
        self.provider = provider
        self.state = state
        self.schema_version = schema_version
        self.updated = updated
        self._bundle = bundle

    @property
    def bundle(self):
        """Transient plaintext bundle (CONFIGURED only). Never log/export."""
        return self._bundle

    @property
    def is_configured(self):
        return self.state == STATE_CONFIGURED

    def to_metadata(self):
        """Return metadata-only dict safe for any API/log surface."""
        return {
            'provider': self.provider,
            'state': self.state,
            'schema_version': self.schema_version,
            'updated': self.updated,
        }


def _record_state(record):
    """Return (state, updated) metadata for a single record. No secrets."""
    name = _CERT_NAME_BY_RECORD[record]
    cert_id, entry = _find_cert_entry_by_name(name)
    if cert_id is None:
        return STATE_MISSING, None
    updated = _updated_ts(entry)
    bundle = _decrypt_bundle(entry)
    if bundle is None:
        # Off-router decrypt returns None (reads as MISSING); on-router an
        # undecodable bundle is INVALID.
        if getattr(cp, '_is_ncos', False):
            return STATE_INVALID, updated
        return STATE_MISSING, updated
    canonical = normalize_record_bundle(record, bundle)
    if canonical is not None and validate_record_bundle(record, canonical):
        return STATE_CONFIGURED, updated
    return STATE_INVALID, updated


def record_status_all():
    """Return metadata-only status for each managed record.

    Shape: ``{record: {'state': ..., 'updated': ..., 'fields': {field: bool}}}``
    where ``fields`` reports per-field presence (never the value) so the UX can
    show Configured / Not Configured per key. Never returns secret values.
    """
    with _lock:
        _migrate_legacy_if_present()
        out = {}
        for record in _CERT_NAME_BY_RECORD:
            state, updated = _record_state(record)
            bundle = _read_record_bundle(record) or {}
            fields = {}
            for field in _RECORD_FIELDS[record]:
                fields[field] = _non_empty_str(bundle.get(field))
            out[record] = {
                'record': record,
                'name': _CERT_NAME_BY_RECORD[record],
                'state': state,
                'updated': updated,
                'schema_version': _SCHEMA_VERSION,
                'fields': fields,
            }
        return out


# ---------------------------------------------------------------------------
# Logical-provider resolution (merged view over both records)
# ---------------------------------------------------------------------------
# Which server-record field backs each independent service.
_SERVICE_SERVER_FIELD = {
    'opencellid': 'opencellid_key',
    'google': 'api_key',
}


def resolve_device(provider):
    """Resolve Device credential status for ONE independent service.

        * ``opencellid`` -> CONFIGURED when the server record carries a
          non-empty ``opencellid_key``; bundle = {opencellid_key}.
        * ``google``     -> CONFIGURED when the server record carries a
          non-empty ``api_key`` (Site Address geocoding only);
          bundle = {api_key}.

    Returns MISSING when the backing field is absent, INVALID when the server
    record exists on-router but cannot be decoded. Each service is independent:
    a missing OpenCellID key never blocks geocoding and vice versa. The bundle
    carries ONLY that service's key -- never the other server key, never the
    browser Maps JS key.
    """
    key = supported_provider(provider)
    if key is None:
        return CredentialStatus(provider, STATE_MISSING)

    with _lock:
        _migrate_legacy_if_present()

        server_state, server_updated = _record_state(RECORD_SERVER)
        server_bundle = _read_record_bundle(RECORD_SERVER) or {}
        field = _SERVICE_SERVER_FIELD[key]
        value = server_bundle.get(field)

        if _non_empty_str(value):
            return CredentialStatus(
                key, STATE_CONFIGURED, schema_version=_SCHEMA_VERSION,
                updated=server_updated,
                bundle={'schema_version': _SCHEMA_VERSION, field: value})

        # On-router server record present but this field is absent -> MISSING
        # for THIS service (the other service may still be configured).
        if server_state == STATE_INVALID:
            return CredentialStatus(key, STATE_INVALID, updated=server_updated)
        return CredentialStatus(key, STATE_MISSING, updated=server_updated)


def status_all():
    """Return metadata-only status for each independent credential service.

    Keys: ``opencellid`` (cellular resolver), ``google`` (Site Address
    geocoding). The browser Maps JS service is reported under
    :func:`record_status_all` (``mapjs`` record). Compat surface for existing
    callers; never returns secret values.
    """
    return {
        'opencellid': resolve_device('opencellid').to_metadata(),
        'google': resolve_device('google').to_metadata(),
    }


def maps_js_api_key_value():
    """Return ONLY the browser Maps JavaScript API key, or None. No provider
    argument (the mapjs record is provider-agnostic)."""
    bundle = _read_record_bundle(RECORD_MAPJS)
    if not isinstance(bundle, dict):
        return None
    value = bundle.get('maps_js_api_key')
    return value if _non_empty_str(value) else None


def maps_js_api_key(provider=None):
    """Return ONLY the browser Maps JavaScript API key (independent service).

    The single narrowly scoped exception to the write-only model: this
    browser-restricted Google Maps JS key is returned when the mapjs record
    carries it. It is INDEPENDENT of the OpenCellID / Google-geocoding server
    keys and never exposes them. ``provider`` is accepted for call-site compat
    but ignored (the Maps JS service is not tied to a cellular provider).
    """
    with _lock:
        _migrate_legacy_if_present()
        return maps_js_api_key_value()


# ---------------------------------------------------------------------------
# Write-only record mutation (Device scope) -- split-key config UX
# ---------------------------------------------------------------------------
def update_record(record, fields):
    """Create or replace a single credential ``record`` (partial-merge).

    Seeds from the existing canonical bundle so a submission carrying only some
    fields preserves the others; overlays only non-empty submitted fields.
    Returns metadata-only status. Raises ``ValueError`` for a malformed bundle
    (message carries no secret material).
    """
    key = supported_record(record)
    if key is None:
        raise ValueError('Unsupported credential record')
    if not isinstance(fields, dict):
        raise ValueError('Credential fields must be an object')

    with _lock:
        merged = {}
        existing = _read_record_bundle(key)
        if isinstance(existing, dict):
            for field in _RECORD_FIELDS[key]:
                if _non_empty_str(existing.get(field)):
                    merged[field] = existing[field]

        for field in _RECORD_FIELDS[key]:
            raw = fields.get(field)
            if isinstance(raw, str) and raw.strip() != '':
                merged[field] = raw.strip()

        merged['schema_version'] = _SCHEMA_VERSION

        if not validate_record_bundle(key, merged):
            raise ValueError('Credential bundle is incomplete or malformed')

        if not _write_record_bundle(key, merged):
            raise ValueError('Credential write failed')

    return {'record': key, 'state': _record_state(key)[0]}


def clear_record(record):
    """Delete a single credential ``record`` (idempotent). Metadata only."""
    key = supported_record(record)
    if key is None:
        raise ValueError('Unsupported credential record')
    with _lock:
        if not _delete_cert_by_name(_CERT_NAME_BY_RECORD[key]):
            raise ValueError('Credential clear failed')
    return {'record': key, 'state': STATE_MISSING}


def clear_single_field(record, field):
    """Remove ONE field from a record (Remove per-key), keeping the others.

    Deletes the record entirely when no required field remains. Metadata only.
    """
    key = supported_record(record)
    if key is None:
        raise ValueError('Unsupported credential record')
    with _lock:
        existing = _read_record_bundle(key)
        if not isinstance(existing, dict) or field not in existing:
            return {'record': key, 'state': _record_state(key)[0]}
        remaining = {f: v for f, v in existing.items()
                     if f != field and f != 'schema_version'}
        remaining['schema_version'] = _SCHEMA_VERSION
        if validate_record_bundle(key, remaining):
            if not _write_record_bundle(key, remaining):
                raise ValueError('Credential write failed')
            return {'record': key, 'state': _record_state(key)[0]}
        # No complete bundle remains -> delete the record.
        if not _delete_cert_by_name(_CERT_NAME_BY_RECORD[key]):
            raise ValueError('Credential clear failed')
    return {'record': key, 'state': STATE_MISSING}


# ---------------------------------------------------------------------------
# Legacy compat shims (logical provider write/clear) -- kept for callers that
# still speak the single-provider API. Fields are routed to the right record.
# ---------------------------------------------------------------------------
def server_geocoding_key():
    """Return ONLY the Google server geocoding key (independent service).

    Never exposed to the browser or logged. Used solely by the Site Address
    forward-geocode path.
    """
    bundle = _read_record_bundle(RECORD_SERVER)
    if not isinstance(bundle, dict):
        return None
    value = bundle.get('api_key')
    return value if _non_empty_str(value) else None


def opencellid_key():
    """Return ONLY the OpenCellID cell-database key (independent service)."""
    bundle = _read_record_bundle(RECORD_SERVER)
    if not isinstance(bundle, dict):
        return None
    value = bundle.get('opencellid_key')
    return value if _non_empty_str(value) else None


# ---------------------------------------------------------------------------
# TEMPORARY migration plumbing (accepted only as internal compatibility).
#
# These route a combined write/clear to the correct record(s). They do NOT
# model a logical "google" cellular provider and must not be relied on to
# preserve one; new callers should use update_record / clear_record and the
# per-service resolvers above.
# ---------------------------------------------------------------------------
def update_device(provider, fields):
    """Route a combined credential write to the correct record(s).

    ``fields`` may contain any of ``api_key`` / ``opencellid_key`` (server
    record) and ``maps_js_api_key`` (mapjs record). Returns per-service
    metadata (no logical google provider).
    """
    if not isinstance(fields, dict):
        raise ValueError('Credential fields must be an object')

    server_fields = {k: fields[k] for k in ('api_key', 'opencellid_key')
                     if isinstance(fields.get(k), str) and fields[k].strip()}
    mapjs_fields = {k: fields[k] for k in ('maps_js_api_key',)
                    if isinstance(fields.get(k), str) and fields[k].strip()}

    if server_fields:
        update_record(RECORD_SERVER, server_fields)
    if mapjs_fields:
        update_record(RECORD_MAPJS, mapjs_fields)
    return status_all()


def clear_device(provider=None):
    """Clear all geo credential records (both records + legacy)."""
    with _lock:
        ok = (_delete_cert_by_name(GEO_CERT_SERVER_DEVICE)
              and _delete_cert_by_name(GEO_CERT_MAPJS_DEVICE)
              and _delete_cert_by_name(GEO_CERT_LEGACY_GOOGLE_DEVICE))
    if not ok:
        raise ValueError('Credential clear failed')
    return status_all()


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------
_SECRET_HINTS = (
    'api_key', 'apikey', 'opencellid_key', 'url_signing_secret',
    'signing_secret', 'signature', 'token', 'secret', 'key=', 'password',
    'passwd', 'authorization',
)


def _scrub(value):
    """Return a redacted string form of ``value`` safe for logs/exceptions."""
    try:
        text = value if isinstance(value, str) else str(value)
    except Exception:
        return '<unprintable>'
    lowered = text.lower()
    for hint in _SECRET_HINTS:
        if hint in lowered:
            return '<redacted>'
    return text


def scrub(value):
    """Public secret-redaction guard for log lines / exception bodies."""
    return _scrub(value)
