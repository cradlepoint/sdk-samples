"""Provider-result cache for GeoView (v1.1.3).

Caches normalized provider responses keyed by ``(provider, cell_identity)`` so
repeated resolves and ``/api/cellular_analysis`` reads do not hammer external
providers. Contains no provider calls and no job control; it only stores and
serves results and owns the retry/expiry policy contract.

Design points (LLD §3):
    * Key: ``(provider, normalized cell identity)`` where identity encodes ECI
      (LTE/NSA) or NCI (SA).
    * Hit: return cached normalized result when not expired.
    * Miss: eligible for a provider fetch (only within a resolve job).
    * Negative caching: ``not_found`` cached with a shorter TTL to avoid
      re-hammering providers.
    * Expiry: positive/negative TTLs are configurable (canonical App Data via
      configuration_manager; NEVER credentials).
    * Retry: bounded retry with backoff for transient statuses
      (``timeout``/``provider_error``); no retry for ``auth_error``/``quota``.

The cache holds only normalized results (metadata: status/location/address).
It never stores credentials or credentialed URLs.
"""

import json
import os
import tempfile
import threading
import time

import cp
import geo_providers
import geo_secrets


def _scrub(value):
    """Redact secret-looking content from a value for safe logging."""
    try:
        return geo_secrets.scrub(value)
    except Exception:
        return '<redacted>'


# Default TTLs (seconds). Overridable via configuration (non-secret App Data).
DEFAULT_POSITIVE_TTL = 30 * 24 * 3600     # 30 days for a resolved location.
DEFAULT_NEGATIVE_TTL = 6 * 3600           # 6 hours for a not_found result.

# Persistent cache file (relative to the app working dir, like tmp/history).
# Only SAFE normalized results (resolved / not_found) are persisted; never
# secrets, never credentialed URLs, never transient/auth/quota/network errors.
CACHE_FILE = 'tmp/geoview_cell_cache.json'
# Bump when the persisted key/record shape changes. A mismatch discards the
# whole file on load, so coordinates written by a DIFFERENT scheme (e.g. the
# removed Google Geolocation path) can never be reused as OpenCellID results.
CACHE_SCHEMA_VERSION = 2

# Bounded retry policy for transient provider failures within a resolve job.
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_BASE = 1.5                 # seconds; multiplied per attempt.

_NEGATIVE_STATUSES = (geo_providers.STATUS_NOT_FOUND,)
# Statuses that are outcomes of a completed fetch but are NOT cached as a
# reusable location (they are transient or credential/quota conditions).
_NON_CACHEABLE_STATUSES = (
    geo_providers.STATUS_AUTH_ERROR,
    geo_providers.STATUS_QUOTA,
    geo_providers.STATUS_TIMEOUT,
    geo_providers.STATUS_NO_INTERNET,
    geo_providers.STATUS_PROVIDER_ERROR,
)


def cache_key(provider, identity):
    """Build a stable cache key from provider + full normalized identity.

    The key encodes provider + RAT semantics + MCC + MNC + TAC(lac) +
    ECI/NCI(value) so a cached location is only ever reused for the exact same
    serving-cell identity under the exact same provider. Because the provider
    prefix is part of the key (``opencellid``), a coordinate cached by any
    other/older provider scheme can never be served as an OpenCellID result.
    Falls back to ``cell_key`` only when a structured value is unavailable.
    """
    prov = str(provider or '').strip().lower()
    if isinstance(identity, dict):
        semantics = identity.get('semantics') or ''
        value = identity.get('value')
        if value is None:
            value = identity.get('cell_key') or ''
        mcc = identity.get('mcc')
        mnc = identity.get('mnc')
        lac = identity.get('lac')
        return '%s|%s|%s|%s|%s|%s' % (
            prov, semantics,
            '' if mcc is None else mcc,
            '' if mnc is None else mnc,
            '' if lac is None else lac,
            value)
    return '%s|%s' % (prov, identity)


class GeoCache(object):
    """Thread-safe in-memory provider-result cache with TTL + retry policy."""

    def __init__(self, positive_ttl=DEFAULT_POSITIVE_TTL,
                 negative_ttl=DEFAULT_NEGATIVE_TTL,
                 max_attempts=DEFAULT_MAX_ATTEMPTS,
                 backoff_base=DEFAULT_BACKOFF_BASE, clock=time.time,
                 persist_path=CACHE_FILE):
        self.positive_ttl = positive_ttl
        self.negative_ttl = negative_ttl
        self.max_attempts = max(1, int(max_attempts))
        self.backoff_base = backoff_base
        self._clock = clock
        self._entries = {}
        self._lock = threading.RLock()
        # Persistence is best-effort and never fatal; ``persist_path=None``
        # yields a purely in-memory cache (used in tests).
        self._persist_path = persist_path
        self._load()

    # -- persistence (safe, atomic, no secrets) -----------------------------
    def _sanitize_result(self, result):
        """Return a persist-safe copy of a normalized result.

        Keeps only non-secret, browser/log-safe metadata (status, location,
        address, provider, source, fallback). Never persists credentials or
        credentialed URLs (normalized results never carry them, but this is a
        defensive whitelist).
        """
        result = result or {}
        location = result.get('location')
        safe_location = None
        if isinstance(location, dict):
            safe_location = {
                k: location.get(k) for k in (
                    'lat', 'lon', 'range_m', 'samples', 'changeable',
                    'position_is_estimated', 'accuracy_m')
                if k in location
            }
        return {
            'cell_key': result.get('cell_key'),
            'status': result.get('status'),
            'location': safe_location,
            'address': result.get('address'),
            'provider': result.get('provider'),
            'source': result.get('source'),
            'fallback': result.get('fallback'),
        }

    def _load(self):
        """Load persisted entries, discarding on any schema/format mismatch.

        A schema-version mismatch (or unreadable/corrupt file) discards the
        WHOLE file, so coordinates written by a different/older resolution
        scheme (e.g. the removed Google Geolocation path) can never be reused.
        Expired entries are dropped on load. Best-effort; never raises.
        """
        if not self._persist_path:
            return
        try:
            if not os.path.exists(self._persist_path):
                return
            with open(self._persist_path, 'r') as handle:
                doc = json.load(handle)
        except Exception as exc:
            cp.log('GeoView cache load skipped: %s' % _scrub(exc))
            return

        if (not isinstance(doc, dict)
                or doc.get('schema_version') != CACHE_SCHEMA_VERSION):
            # Foreign/old shape: ignore entirely (never reuse its coordinates).
            return

        entries = doc.get('entries')
        if not isinstance(entries, dict):
            return

        now = self._clock()
        loaded = {}
        for key, entry in entries.items():
            if not isinstance(entry, dict):
                continue
            expires = entry.get('expires')
            if expires is not None and now >= expires:
                continue  # already expired
            result = entry.get('result')
            if not isinstance(result, dict):
                continue
            loaded[key] = {
                'key': key,
                'result': self._sanitize_result(result),
                'fetched': entry.get('fetched'),
                'expires': expires,
                'negative': bool(entry.get('negative')),
            }
        with self._lock:
            self._entries = loaded

    def _save_locked(self):
        """Atomically write the current entries. Caller holds ``_lock``.

        Uses a temp file + ``os.replace`` for an atomic swap so a crash never
        leaves a partially written cache. Best-effort; never raises.
        """
        if not self._persist_path:
            return
        doc = {
            'schema_version': CACHE_SCHEMA_VERSION,
            'entries': {
                key: {
                    'result': self._sanitize_result(entry.get('result')),
                    'fetched': entry.get('fetched'),
                    'expires': entry.get('expires'),
                    'negative': entry.get('negative'),
                }
                for key, entry in self._entries.items()
            },
        }
        directory = os.path.dirname(self._persist_path) or '.'
        try:
            os.makedirs(directory, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=directory,
                                            prefix='geoview_cell_cache.',
                                            suffix='.tmp')
            try:
                with os.fdopen(fd, 'w') as handle:
                    json.dump(doc, handle, separators=(',', ':'))
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp_path, self._persist_path)
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
        except Exception as exc:
            cp.log('GeoView cache save skipped: %s' % _scrub(exc))

    def configure(self, positive_ttl=None, negative_ttl=None,
                  max_attempts=None, backoff_base=None):
        """Update non-secret policy values from configuration."""
        with self._lock:
            if positive_ttl is not None:
                self.positive_ttl = positive_ttl
            if negative_ttl is not None:
                self.negative_ttl = negative_ttl
            if max_attempts is not None:
                self.max_attempts = max(1, int(max_attempts))
            if backoff_base is not None:
                self.backoff_base = backoff_base

    # -- lookup / store -----------------------------------------------------
    def get(self, provider, identity):
        """Return a cached normalized result if present and unexpired."""
        key = cache_key(provider, identity)
        now = self._clock()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry['expires'] is not None and now >= entry['expires']:
                # Expired positive/negative entry: drop so it is re-fetched.
                self._entries.pop(key, None)
                return None
            return dict(entry['result'])

    def store(self, provider, identity, result):
        """Store a normalized result, applying positive/negative TTL policy.

        Non-cacheable statuses (auth/quota/timeout/no_internet/provider_error)
        are intentionally NOT stored, so a later resolve can retry cleanly.
        Returns True when stored, False when skipped.
        """
        status = (result or {}).get('status')
        if status in _NON_CACHEABLE_STATUSES:
            return False

        key = cache_key(provider, identity)
        now = self._clock()
        negative = status in _NEGATIVE_STATUSES
        ttl = self.negative_ttl if negative else self.positive_ttl
        expires = now + ttl if ttl is not None else None

        with self._lock:
            self._entries[key] = {
                'key': key,
                # Persist-safe projection only (no secrets/credentialed URLs).
                'result': self._sanitize_result(result),
                'fetched': now,
                'expires': expires,
                'negative': negative,
            }
            self._save_locked()
        return True

    def invalidate(self, provider=None):
        """Clear cache entries. If provider given, only that provider's keys."""
        with self._lock:
            if provider is None:
                self._entries.clear()
                self._save_locked()
                return
            prefix = '%s|' % str(provider).strip().lower()
            removed = False
            for key in [k for k in self._entries if k.startswith(prefix)]:
                self._entries.pop(key, None)
                removed = True
            if removed:
                self._save_locked()

    def snapshot(self):
        """Return metadata-only cache stats (no credentials, no URLs)."""
        with self._lock:
            total = len(self._entries)
            negative = sum(1 for e in self._entries.values()
                           if e.get('negative'))
        return {'entries': total, 'negative': negative,
                'positive': total - negative}

    # -- fetch-through with bounded retry -----------------------------------
    def resolve(self, provider, identity, fetch, sleep=time.sleep):
        """Return a cached result or fetch-through with bounded retry.

        ``fetch()`` is a zero-arg callable returning a normalized result. Cache
        is consulted first (hit short-circuits, no provider call). On miss, the
        fetch is attempted up to ``max_attempts`` times for transient statuses
        with linear backoff; ``auth_error``/``quota`` are not retried. The
        final result is stored per TTL policy and returned.
        """
        cached = self.get(provider, identity)
        if cached is not None:
            cached['cache'] = 'hit'
            return cached

        result = None
        for attempt in range(1, self.max_attempts + 1):
            result = fetch()
            status = (result or {}).get('status')

            if status not in geo_providers.TRANSIENT_STATUSES:
                break
            if attempt < self.max_attempts:
                sleep(self.backoff_base * attempt)

        if result is None:
            result = geo_providers.normalized_result(
                cache_key(provider, identity),
                geo_providers.STATUS_PROVIDER_ERROR, provider=provider)

        self.store(provider, identity, result)
        result = dict(result)
        result['cache'] = 'miss'
        return result


# Module-level shared cache used by the resolve job and cellular_analysis read.
_shared_cache = GeoCache()


def shared_cache():
    """Return the process-wide shared GeoCache instance."""
    return _shared_cache
