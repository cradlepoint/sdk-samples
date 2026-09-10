"""GeoView resolution orchestration (v1.1.3).

Owns the single bounded resolve-job model and the credential-safe map
mediation. This is the orchestration boundary where ALL GeoView failures are
contained so Speedtest execution, retained history, and local Cellular
Analysis are never affected (HLD §11, LLD §9).

Constraints (LLD §4.1):
    * One active job maximum. A second ``resolve()`` while ``running`` returns
      the current job status instead of starting a new one.
    * No permanent daemon: the worker thread starts on demand and exits when
      the job completes.
    * No additional NCOS telemetry polling.

Job lifecycle (LLD §4.2):
    idle -> running -> { complete | partial | failed }
    plus non-fatal ``credentials_required`` (no job started) when the selected
    provider's Device credential is missing/invalid (S2/S4/J6b).

Credential handling:
    * The selected provider's plaintext bundle is resolved from ``geo_secrets``
      transiently, held only for the duration of the worker, and never logged
      or exported.
    * ``/api/cellular_analysis`` reads cached enrichment only; it never calls
      into this module to start resolution.
"""

import threading
import time

import cp
import geo_cache
import geo_identity
import geo_providers
import geo_secrets


STATE_IDLE = 'idle'
STATE_RUNNING = 'running'
STATE_COMPLETE = 'complete'
STATE_PARTIAL = 'partial'
STATE_FAILED = 'failed'
STATE_CREDENTIALS_REQUIRED = 'credentials_required'


def _now_iso():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


class ResolveJob(object):
    """Single bounded GeoView resolution job with metadata-only status."""

    def __init__(self):
        self._lock = threading.RLock()
        self._thread = None
        # The provider of the CURRENTLY running job (None when idle) — enforces
        # the single-active-job constraint across all providers.
        self._running_provider = None
        # Per-provider status snapshots, PARTITIONED BY PROVIDER so the resolve
        # status/counts are provider-specific just like enrichment. Switching
        # providers surfaces the selected provider's own last-run status;
        # switching back restores it. Shape:
        #   {provider: {state, started, finished, counts, reason}}
        self._status_by_provider = {}
        # Metadata-only per-cell results, PARTITIONED BY PROVIDER so a result
        # from one provider is never visible under a different effective
        # provider. Shape: {provider: {cell_key: record}}.
        self._results_by_provider = {}
        # The provider whose results/counts the CURRENT job produces.
        self._results_provider = None

    # -- status -------------------------------------------------------------
    @staticmethod
    def _empty_counts():
        return {'eligible': 0, 'ineligible': 0, 'resolved': 0,
                'not_found': 0, 'failed': 0}

    def _idle_status(self):
        return {'state': STATE_IDLE, 'started': None, 'finished': None,
                'counts': self._empty_counts(), 'reason': None}

    def status(self, provider=None):
        """Return a metadata-only status snapshot for the EFFECTIVE provider.

        Provider-specific: returns that provider's own last-run state/counts,
        so Google 1/1 then switching to a different unresolved provider shows
        that provider 0/1 (idle), and switching back to Google restores
        Google's 1/1. When no provider is given, reports the currently running
        job or idle.
        """
        with self._lock:
            snap = geo_cache.shared_cache().snapshot()
            key = str(provider).strip().lower() if provider else None
            if key is None:
                # No provider context: reflect a running job if any, else idle.
                key = self._running_provider
            if key is None:
                base = self._idle_status()
                base['provider'] = provider or 'none'
                base['cache'] = snap
                return base
            st = self._status_by_provider.get(key)
            if st is None:
                base = self._idle_status()
            else:
                base = {
                    'state': st['state'],
                    'started': st['started'],
                    'finished': st['finished'],
                    'counts': dict(st['counts']),
                    'reason': st['reason'],
                }
            base['provider'] = key
            base['cache'] = snap
            return base

    def _provider_status(self, provider):
        """Get (creating if needed) the mutable status dict for a provider."""
        st = self._status_by_provider.get(provider)
        if st is None:
            st = self._idle_status()
            self._status_by_provider[provider] = st
        return st

    def enrichment(self, provider):
        """Return cached per-cell enrichment for the given EFFECTIVE provider.

        Metadata only: cell_key -> {status, location, address, provider,
        eligible/reason}. Only records produced under ``provider`` are returned,
        so a result from one provider never appears while a different provider
        is effective. Never initiates a provider request.
        """
        key = str(provider or '').strip().lower()
        with self._lock:
            bucket = self._results_by_provider.get(key) or {}
            return {ck: dict(v) for ck, v in bucket.items()}

    @property
    def is_running(self):
        with self._lock:
            return self._running_provider is not None

    # -- start --------------------------------------------------------------
    def resolve(self, provider, cells, timeout=10.0):
        """Start (or reuse) the single bounded job.

        ``provider`` is the effective selected cellular-location provider
        ('none'|'opencellid'). ``cells`` is the site-inventory cell list.
        Returns the current job
        status. If a job is already running, returns its status without
        starting a second one (J3). Provider handling is generic (keyed by
        provider), so the provider-scoped status/enrichment architecture is
        retained for future providers.
        """
        with self._lock:
            # Single active job across all providers.
            if self._running_provider is not None:
                return self.status(self._running_provider)

            provider = str(provider or 'none').strip().lower()

            # Provider = None disables GeoView entirely (P0).
            if provider == 'none':
                return self.status('none')

            # Credential gate (Device-scoped). Missing/invalid => non-fatal
            # credentials_required; NO provider request, NO job started (J6b).
            cred = geo_secrets.resolve_device(provider)
            if not cred.is_configured:
                st = self._provider_status(provider)
                st['state'] = STATE_CREDENTIALS_REQUIRED
                st['reason'] = 'credentials_%s' % cred.state
                st['finished'] = _now_iso()
                return self.status(provider)

            # Reset THIS provider's status/counts for a fresh run and spin up
            # the worker. Other providers' status/results are left intact.
            self._running_provider = provider
            self._results_provider = provider
            st = self._provider_status(provider)
            st['state'] = STATE_RUNNING
            st['reason'] = None
            st['started'] = _now_iso()
            st['finished'] = None
            st['counts'] = self._empty_counts()
            self._results_by_provider[provider] = {}

            # Hand the transient bundle to the worker; it stays in memory only.
            bundle = cred.bundle
            self._thread = threading.Thread(
                target=self._run,
                args=(provider, bundle, list(cells or []), timeout),
                daemon=True,
            )
            self._thread.start()
            return self.status(provider)

    # -- worker -------------------------------------------------------------
    def _run(self, provider, bundle, cells, timeout):
        """Worker body. Bounded: exits when all eligible cells are processed."""
        try:
            eligible, ineligible = geo_identity.normalize_inventory(cells)

            with self._lock:
                st = self._provider_status(provider)
                st['counts']['eligible'] = len(eligible)
                st['counts']['ineligible'] = len(ineligible)
                bucket = self._results_by_provider.setdefault(provider, {})
                for item in ineligible:
                    bucket[item.cell_key] = item.to_metadata()

            try:
                adapter = geo_providers.build_adapter(
                    provider, bundle, timeout=timeout)
            except ValueError:
                self._finish(STATE_FAILED, reason='unsupported_provider')
                return

            cache = geo_cache.shared_cache()
            fatal_no_internet = False

            for identity in eligible:
                request = identity.to_request()

                def _fetch():
                    return adapter.resolve_cell(identity.cell_key, request)

                result = cache.resolve(provider, request, _fetch)
                self._record_result(identity.cell_key, result)

                if result.get('status') == geo_providers.STATUS_NO_INTERNET:
                    fatal_no_internet = True
                    break

            if fatal_no_internet:
                self._finish(STATE_FAILED, reason='no_internet')
                return

            self._finish_aggregate()
        except Exception as exc:
            # Absolute containment: no GeoView failure escapes the boundary.
            cp.log('GeoView resolve worker error: %s'
                   % geo_secrets.scrub(exc))
            self._finish(STATE_FAILED, reason='worker_error')

    def _record_result(self, cell_key, result):
        status = result.get('status')
        with self._lock:
            provider = self._results_provider or result.get('provider')
            bucket = self._results_by_provider.setdefault(provider, {})
            bucket[cell_key] = {
                'cell_key': cell_key,
                'eligible': True,
                'status': status,
                'location': result.get('location'),
                'address': result.get('address'),
                'provider': result.get('provider'),
                'fallback': result.get('fallback'),
            }
            counts = self._provider_status(provider)['counts']
            if status == geo_providers.STATUS_OK:
                counts['resolved'] += 1
            elif status == geo_providers.STATUS_NOT_FOUND:
                counts['not_found'] += 1
            else:
                counts['failed'] += 1

    def _finish_aggregate(self):
        with self._lock:
            provider = self._results_provider
            counts = self._provider_status(provider)['counts']
            resolved = counts['resolved']
            eligible = counts['eligible']
            problems = counts['not_found'] + counts['failed']

            if eligible == 0:
                state = STATE_COMPLETE
            elif resolved == eligible:
                state = STATE_COMPLETE
            else:
                state = STATE_PARTIAL
        self._finish(state)

    def _finish(self, state, reason=None):
        with self._lock:
            provider = self._results_provider
            if provider is not None:
                st = self._provider_status(provider)
                st['state'] = state
                st['reason'] = reason
                st['finished'] = _now_iso()
            # Release the single-job slot.
            self._running_provider = None

    # -- reset --------------------------------------------------------------
    def reset(self):
        """Reset job model to idle (used on reload/reboot). Cache untouched."""
        with self._lock:
            if self._running_provider is not None:
                return
            self._status_by_provider = {}
            self._results_provider = None


# Module-level single job instance (one active job maximum).
_job = ResolveJob()


def job():
    """Return the process-wide single ResolveJob instance."""
    return _job
