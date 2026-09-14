"""GeoView provider adapters (v1.1.3).

Adapters translate a normalized cell identity into a normalized location /
address result using an external provider. They contain NO caching and NO job
control (those live in ``geo_cache`` and the ``speedtest_web`` orchestration).

Providers (v1.1.3; the adapter interface is generic so additional providers
can be added later without changing callers):
    * Cellular serving-cell location -> OpenCellID cell database
      (``/cell/get``). NCOS is authoritative for LTE vs NR; the primary
      serving cell only is resolved (LTE/NSA anchor via ECI; SA primary via
      NCI). Google Geolocation is NOT used for cellular location.
    * Site Address geocoding + reverse geocode -> Google Geocoding API (server
      side only). The interactive map is rendered browser-side by the Google
      Maps JavaScript API; there is no server-side map composition here.

Security posture (non-negotiable):
    * Adapters receive an already-resolved plaintext credential bundle from
      ``geo_secrets`` for the duration of a single call, held transiently.
    * Only server-side keys are used here: the OpenCellID key (cell lookup)
      and the private Google SERVER key (``api_key``, Geocoding only). Neither
      is ever exposed to the browser, logged, or placed in an exception body.
      Errors are typed and carry provider-safe messages only.

Standard library only (``urllib``) so no new runtime dependency is introduced
on NCOS.
"""

import json
import socket
import urllib.error
import urllib.parse
import urllib.request

import cp


# Normalized status values (LLD §2.1).
STATUS_OK = 'ok'
STATUS_NOT_FOUND = 'not_found'
STATUS_AUTH_ERROR = 'auth_error'
STATUS_QUOTA = 'quota'
STATUS_TIMEOUT = 'timeout'
STATUS_NO_INTERNET = 'no_internet'
STATUS_PROVIDER_ERROR = 'provider_error'

# Transient statuses eligible for bounded retry (see geo_cache policy).
TRANSIENT_STATUSES = (STATUS_TIMEOUT, STATUS_PROVIDER_ERROR)

_DEFAULT_TIMEOUT = 10.0

# OpenCellID cell-database lookup (serving-cell location). Google Geolocation
# (geolocation/v1/geolocate) is intentionally NOT used for cellular location.
_OPENCELLID_GET = 'https://opencellid.org/cell/get'

# OpenCellID observation contribution endpoint. The API key is sent in the
# form-urlencoded POST body (never in the URL).
_OPENCELLID_MEASURE_ADD = 'https://opencellid.org/measure/add'

# The exact success acknowledgment OpenCellID returns for an inserted
# measurement. Success requires HTTP 200 AND this acknowledgment.
_OPENCELLID_MEASURE_ADD_OK = 'Your measurement has been inserted.'

# Google Geocoding is retained ONLY for Site Address forward-geocode + reverse
# geocode of a resolved cell, using the private server key.
_GOOGLE_GEOCODE = 'https://maps.googleapis.com/maps/api/geocode/json'

# OpenCellID provider error codes. These arrive either as an HTTP status or as
# an HTTP-200 JSON error body ({"error": "...", "code": N}); both are handled.
_OPENCELLID_ERROR_STATUS = {
    1: STATUS_NOT_FOUND,       # cell not found in the database
    2: STATUS_AUTH_ERROR,      # invalid API key
    3: STATUS_PROVIDER_ERROR,  # invalid input (bad request shaping)
    4: STATUS_AUTH_ERROR,      # access denied / not whitelisted
    5: STATUS_PROVIDER_ERROR,  # generic provider error
    6: STATUS_PROVIDER_ERROR,  # server overloaded (transient)
    7: STATUS_QUOTA,           # rate/quota limit exceeded
}


class ProviderError(Exception):
    """Typed provider error mapped to a normalized status.

    The message is provider-safe: it never contains credentials or a
    credentialed URL.
    """

    def __init__(self, status, message=''):
        super(ProviderError, self).__init__(message or status)
        self.status = status


def normalized_result(cell_key, status, location=None, address=None,
                      provider='', source='', fallback=None):
    """Build a normalized provider response (LLD §2.1).

    ``fallback``: generic descriptor for a provider that reports the location
    was derived from a fallback (e.g. an area centroid) rather than an exact
    cell fix, so a fallback-derived estimate is never silently presented as an
    exact result. ``None`` when the provider did not return one (never
    invented). Google does not use it; kept for provider-agnostic extension.
    """
    return {
        'cell_key': cell_key,
        'status': status,
        'location': location,
        'address': address,
        'provider': provider,
        'source': source,
        'fallback': fallback,
    }


# ---------------------------------------------------------------------------
# Normalized map marker contract (shared by both adapters)
# ---------------------------------------------------------------------------
# A marker is a plain dict composed backend-side by speedtest_web and returned
# by the /api/geo/mapjs endpoint for the browser Maps JavaScript map:
#   {"role": "site"|"cell", "label": "SITE"|"A"|"B"..., "lat": float,
#    "lon": float, "accuracy_m": float|None, "cell_key": str|None}
# It contains no secret material.
MARKER_ROLE_SITE = 'site'
MARKER_ROLE_CELL = 'cell'


def make_marker(role, label, lat, lon, accuracy_m=None, cell_key=None,
                carrier=None):
    """Build one normalized marker dict.

    ``carrier`` is a browser-safe display string (e.g. 'T-Mobile') used only to
    color the live-map accuracy circle per carrier. It carries no secret and is
    absent/None for the SITE marker.
    """
    return {
        'role': role,
        'label': label,
        'lat': float(lat),
        'lon': float(lon),
        'accuracy_m': accuracy_m,
        'cell_key': cell_key,
        'carrier': carrier,
    }


# ---------------------------------------------------------------------------
# HTTP helper (credential-safe)
# ---------------------------------------------------------------------------
def _http_json(url, data=None, headers=None, timeout=_DEFAULT_TIMEOUT):
    """Perform an HTTP GET/POST and parse a JSON response.

    Raises ``ProviderError`` with a normalized status on failure. Never logs
    the URL (it may contain credentials) or the raw error body.
    """
    request_headers = {'Accept': 'application/json'}
    if headers:
        request_headers.update(headers)

    body = None
    if data is not None:
        body = json.dumps(data).encode('utf-8')
        request_headers['Content-Type'] = 'application/json'

    req = urllib.request.Request(url, data=body, headers=request_headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8')
        return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise ProviderError(_status_from_http(exc.code),
                            'provider http %s' % exc.code)
    except (socket.timeout, TimeoutError):
        raise ProviderError(STATUS_TIMEOUT, 'provider timeout')
    except urllib.error.URLError as exc:
        # DNS/connect failures typically indicate no Internet path.
        if isinstance(exc.reason, (socket.timeout, TimeoutError)):
            raise ProviderError(STATUS_TIMEOUT, 'provider timeout')
        raise ProviderError(STATUS_NO_INTERNET, 'no internet path')
    except (ValueError, json.JSONDecodeError):
        raise ProviderError(STATUS_PROVIDER_ERROR, 'malformed provider body')
    except Exception:
        # Defensive: never allow a raw exception (which could embed a
        # credentialed URL) to propagate to logs.
        raise ProviderError(STATUS_PROVIDER_ERROR, 'provider error')


def _status_from_http(code):
    if code in (401, 403):
        return STATUS_AUTH_ERROR
    if code == 404:
        return STATUS_NOT_FOUND
    if code == 429:
        return STATUS_QUOTA
    return STATUS_PROVIDER_ERROR


def _http_post_form(url, fields, headers=None, timeout=_DEFAULT_TIMEOUT):
    """POST an application/x-www-form-urlencoded body; return (code, text).

    The request body (which carries the API key) is NEVER logged, and neither
    is the URL. Raises ``ProviderError`` with a normalized status on transport
    failure. On an HTTP error status the body is discarded and mapped to a
    status (the raw provider body may echo submitted values).
    """
    request_headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    if headers:
        request_headers.update(headers)

    body = urllib.parse.urlencode(fields).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers=request_headers,
                                 method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8', 'replace')
            return resp.getcode(), raw
    except urllib.error.HTTPError as exc:
        raise ProviderError(_status_from_http(exc.code),
                            'provider http %s' % exc.code)
    except (socket.timeout, TimeoutError):
        raise ProviderError(STATUS_TIMEOUT, 'provider timeout')
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (socket.timeout, TimeoutError)):
            raise ProviderError(STATUS_TIMEOUT, 'provider timeout')
        raise ProviderError(STATUS_NO_INTERNET, 'no internet path')
    except Exception:
        raise ProviderError(STATUS_PROVIDER_ERROR, 'provider error')


# ---------------------------------------------------------------------------
# Cell identity -> OpenCellID request shaping
# ---------------------------------------------------------------------------
def _opencellid_radio(identity):
    """Map the NCOS-authoritative normalized identity to an OpenCellID radio.

    LTE and 5G NSA both resolve on the LTE anchor identity (ECI) -> ``LTE``.
    5G SA resolves on the NR primary identity (NCI) -> ``NR``. Driven ENTIRELY
    by the NCOS-derived normalized identity, never by anything OpenCellID
    returns (OpenCellID's returned ``radio`` is unreliable and must not be
    trusted to identify the RAT).
    """
    semantics = str(identity.get('semantics') or '').lower()
    radio = str(identity.get('radio') or '').lower()
    if semantics == 'nci' or radio == 'nr':
        return 'NR'
    return 'LTE'


def _as_int(value):
    """Return ``int(value)`` when it is a clean integer, else None."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None


def _opencellid_error_status(data):
    """Map an OpenCellID HTTP-200 JSON error body to a normalized status.

    OpenCellID may return ``{"error": "...", "code": N}`` (or ``stat:"fail"``)
    with HTTP 200. Returns a normalized status string when the body is an
    error, else ``None`` (the body may still lack a location, handled by the
    caller). Never trusts the body to prove success.
    """
    if not isinstance(data, dict):
        return STATUS_PROVIDER_ERROR

    code = _as_int(data.get('code'))
    if code is not None and code in _OPENCELLID_ERROR_STATUS:
        return _OPENCELLID_ERROR_STATUS[code]

    stat = str(data.get('stat') or data.get('status') or '').lower()
    if stat in ('fail', 'error'):
        # Error without a recognized numeric code: treat as a provider error
        # (retryable) rather than a definitive not_found.
        return STATUS_PROVIDER_ERROR

    if data.get('error') and code is None:
        return STATUS_PROVIDER_ERROR

    return None


def _opencellid_identity_matches(data, mcc, mnc, lac, cellid):
    """Validate that the returned record matches the requested identity.

    Compares MCC/MNC/lac/cellid from the response against the request. The
    returned ``radio`` is deliberately NOT checked (OpenCellID echoes the same
    record for LTE/NR/omitted) and the returned ``tac`` is deliberately
    ignored (live responses return ``tac:0``). A field that OpenCellID does
    not echo back is not treated as a mismatch.
    """
    checks = (
        (data.get('mcc'), mcc),
        (data.get('mnc'), mnc),
        (data.get('lac'), lac),
        (data.get('cellid'), cellid),
    )
    for returned, requested in checks:
        if returned is None:
            continue
        if _as_int(returned) != requested:
            return False
    return True


# ---------------------------------------------------------------------------
# OpenCellID adapter (cellular serving-cell location)
# ---------------------------------------------------------------------------
class OpenCellIDAdapter(object):
    """Resolve the primary serving cell to a location via the OpenCellID
    cell database.

    This is an INDEPENDENT cellular-location provider. Its provider/source
    identity is ``opencellid`` (never ``google``). It has NO dependency on any
    Google key and performs NO geocoding. NCOS is authoritative for LTE vs NR;
    only the primary serving cell is resolved (LTE/NSA anchor ECI, or SA
    primary NCI). NSA NR components and SA SCells without a complete
    independent NCI identity never reach here (geo_identity gates that
    upstream).
    """

    provider = 'opencellid'

    def __init__(self, bundle, timeout=_DEFAULT_TIMEOUT):
        # Transient plaintext bundle held only for this adapter's lifetime.
        # ``opencellid_key`` -> OpenCellID cell-database key (server side
        # only). Never exposed to the browser or logged.
        self._opencellid_key = (bundle or {}).get('opencellid_key')
        self._timeout = timeout

    def resolve_cell(self, cell_key, identity):
        """Resolve the primary serving cell via OpenCellID ``/cell/get``."""
        radio = _opencellid_radio(identity)
        mcc = _as_int(identity.get('mcc'))
        mnc = _as_int(identity.get('mnc'))
        # NCOS TAC maps to OpenCellID ``lac``; ECI/NCI maps to ``cellid``.
        lac = _as_int(identity.get('lac'))
        cellid = _as_int(identity.get('cell_id'))

        # Eligible only with a full serving-cell identity. No PCI/band/channel
        # is ever fabricated into a cell id (guaranteed upstream).
        if None in (mcc, mnc, lac, cellid):
            return normalized_result(cell_key, STATUS_NOT_FOUND,
                                     provider=self.provider,
                                     source='cell_database')

        query = {
            'key': self._opencellid_key or '',
            'mcc': mcc,
            'mnc': mnc,
            'lac': lac,
            'cellid': cellid,
            'radio': radio,
            'format': 'json',
        }
        url = '%s?%s' % (_OPENCELLID_GET, urllib.parse.urlencode(query))

        try:
            # An explicit application User-Agent is required: OpenCellID is
            # fronted by Cloudflare, which returns HTTP 403 / Error 1010
            # (browser_signature_banned) for urllib's default User-Agent.
            data = _http_json(
                url,
                headers={'User-Agent': 'Speedtest-Analyzer/1.1.3'},
                timeout=self._timeout)
        except ProviderError as exc:
            return normalized_result(cell_key, exc.status,
                                     provider=self.provider,
                                     source='cell_database')

        # OpenCellID may report an error in an HTTP-200 JSON body.
        err_status = _opencellid_error_status(data)
        if err_status is not None:
            return normalized_result(cell_key, err_status,
                                     provider=self.provider,
                                     source='cell_database')

        lat, lon = data.get('lat'), data.get('lon')
        if lat is None or lon is None:
            return normalized_result(cell_key, STATUS_NOT_FOUND,
                                     provider=self.provider,
                                     source='cell_database')

        # Validate the returned identity against the request. OpenCellID's
        # returned ``radio`` is NOT trusted (it echoes the same record for
        # LTE/NR/omitted), and its returned ``tac`` is ignored (live responses
        # return tac:0); the NCOS TAC is preserved as the authoritative area.
        if not _opencellid_identity_matches(data, mcc, mnc, lac, cellid):
            return normalized_result(cell_key, STATUS_NOT_FOUND,
                                     provider=self.provider,
                                     source='cell_database')

        try:
            location = {
                'lat': float(lat),
                'lon': float(lon),
                # OpenCellID ``range`` is the cell coverage range in meters --
                # NOT a location-accuracy radius. It is surfaced as ``range_m``
                # and MUST NOT be rendered as an "Accuracy +/-" value.
                'range_m': (float(data.get('range'))
                            if data.get('range') is not None else None),
                'samples': _as_int(data.get('samples')),
                'changeable': (bool(data.get('changeable'))
                               if data.get('changeable') is not None
                               else None),
                'position_is_estimated': True,
                # OpenCellID does not provide a location-accuracy radius.
                'accuracy_m': None,
            }
        except (TypeError, ValueError):
            return normalized_result(cell_key, STATUS_NOT_FOUND,
                                     provider=self.provider,
                                     source='cell_database')

        # No reverse-geocode here: OpenCellID cell location is independent of
        # Google. An address string is not part of the OpenCellID result.
        return normalized_result(cell_key, STATUS_OK, location=location,
                                 address=None, provider=self.provider,
                                 source='cell_database')


# ---------------------------------------------------------------------------
# Google geocoder (Site Address forward-geocode ONLY)
# ---------------------------------------------------------------------------
class GoogleAdapter(object):
    """Google Geocoding adapter for the Manual Site Address feature ONLY.

    Uses the private Google SERVER key (``api_key``) to forward-geocode a Site
    Address into coordinates. It performs NO cellular geolocation (that is
    OpenCellID's job) and never exposes the key to the browser or logs. The
    Google Maps JavaScript presentation uses a SEPARATE browser key handled by
    geo_secrets, not this adapter.
    """

    provider = 'google'

    def __init__(self, bundle, timeout=_DEFAULT_TIMEOUT):
        # Transient plaintext bundle held only for this adapter's lifetime.
        self._api_key = (bundle or {}).get('api_key')
        self._timeout = timeout

    def forward_geocode(self, address):
        """Forward-geocode a site address to (lat, lon, formatted_address).

        Uses ONLY the private SERVER key (Geocoding API); the key is never
        exposed to the browser and never appears in a log or exception body.
        Raises ``ProviderError`` (typed status) on transport/quota/auth error
        and STATUS_NOT_FOUND when the address does not resolve, so the caller
        can surface a clear Save/Apply error rather than persist fake coords.
        """
        text = str(address or '').strip()
        if not text:
            raise ProviderError(STATUS_NOT_FOUND, 'empty address')

        url = '%s?address=%s&key=%s' % (
            _GOOGLE_GEOCODE,
            urllib.parse.quote(text),
            urllib.parse.quote(self._api_key or ''))

        data = _http_json(url, timeout=self._timeout)

        # Google reports semantic outcomes in a top-level 'status' string even
        # on HTTP 200. Map the ones that matter to normalized statuses.
        api_status = str(data.get('status') or '').upper()
        if api_status in ('REQUEST_DENIED', 'OVER_QUERY_LIMIT'):
            raise ProviderError(
                STATUS_AUTH_ERROR if api_status == 'REQUEST_DENIED'
                else STATUS_QUOTA, 'geocode %s' % api_status.lower())

        results = data.get('results') or []
        if not results or not isinstance(results[0], dict):
            raise ProviderError(STATUS_NOT_FOUND, 'address not found')

        geometry = results[0].get('geometry') or {}
        loc = geometry.get('location') or {}
        lat, lon = loc.get('lat'), loc.get('lng')
        if lat is None or lon is None:
            raise ProviderError(STATUS_NOT_FOUND, 'address not found')

        return (float(lat), float(lon),
                results[0].get('formatted_address') or text)


# ---------------------------------------------------------------------------
# OpenCellID contribution adapter (observation upload)
# ---------------------------------------------------------------------------
class OpenCellIDContributor(object):
    """Submit an observed serving-cell measurement to OpenCellID.

    Uses ``/measure/add`` with an application/x-www-form-urlencoded POST body
    so the API key is NEVER in the URL. The mandatory application User-Agent is
    always sent (urllib's default UA is blocked by Cloudflare). This adapter
    ONLY uploads; it never resolves locations and never trusts/returns provider
    coordinates. The submitted location is always the router's observed
    position supplied by the caller.

    A single measurement is considered successfully inserted ONLY when the
    response is HTTP 200 AND carries OpenCellID's expected success
    acknowledgment. Anything else maps to a safe normalized error status. The
    request body and any secret-bearing response are never logged.
    """

    provider = 'opencellid'

    # Mandatory application User-Agent (shared with the lookup path).
    _USER_AGENT = 'Speedtest-Analyzer/1.1.3'

    def __init__(self, bundle, timeout=_DEFAULT_TIMEOUT):
        self._opencellid_key = (bundle or {}).get('opencellid_key')
        self._timeout = timeout

    def submit_measurement(self, measurement):
        """Submit one measurement dict.

        ``measurement`` carries: lat, lon, mcc, mnc, tac, cellid, act
        (mandatory) and optionally measured_at, signal, pci. Returns a
        normalized result ({'status': ...}). Never raises.
        """
        if not self._opencellid_key:
            return normalized_result(None, STATUS_AUTH_ERROR,
                                     provider=self.provider,
                                     source='measure_add')

        fields = {'key': self._opencellid_key}
        for name in ('lat', 'lon', 'mcc', 'mnc', 'tac', 'cellid', 'act',
                     'measured_at', 'signal', 'pci'):
            value = measurement.get(name)
            if value is None:
                continue
            fields[name] = value

        try:
            code, text = _http_post_form(
                _OPENCELLID_MEASURE_ADD, fields,
                headers={'User-Agent': self._USER_AGENT},
                timeout=self._timeout)
        except ProviderError as exc:
            return normalized_result(None, exc.status, provider=self.provider,
                                     source='measure_add')

        # Success requires HTTP 200 AND the expected acknowledgment.
        if code == 200 and _OPENCELLID_MEASURE_ADD_OK in (text or ''):
            return normalized_result(None, STATUS_OK, provider=self.provider,
                                     source='measure_add')
        # Non-acknowledged 200 (or other) -> provider error (retryable). The
        # raw body is not logged (it can echo submitted values).
        return normalized_result(None, STATUS_PROVIDER_ERROR,
                                 provider=self.provider, source='measure_add')


# Adapter factories
# ---------------------------------------------------------------------------
def build_contributor(bundle, timeout=_DEFAULT_TIMEOUT):
    """Return the OpenCellID observation-contribution adapter.

    Independent of the lookup adapter and the Google geocoder. Uses only the
    OpenCellID key from the transient server-key bundle.
    """
    return OpenCellIDContributor(bundle, timeout=timeout)


def build_adapter(provider, bundle, timeout=_DEFAULT_TIMEOUT):
    """Return the CELLULAR-LOCATION provider adapter (implements resolve_cell).

    ``bundle`` is the transient server-key bundle from ``geo_secrets``. The
    cellular serving-location provider is OpenCellID. Raises ``ValueError`` for
    an unsupported provider so callers surface it as unsupported_provider.
    """
    key = str(provider or '').strip().lower()
    if key == 'opencellid':
        return OpenCellIDAdapter(bundle, timeout=timeout)
    # 'google' is NOT a cellular-location provider; it only geocodes Site
    # Addresses and renders the browser map. Reject it here so no code path can
    # accidentally resolve cells via Google.
    raise ValueError('Unsupported cellular geo provider')


def build_geocoder(bundle, timeout=_DEFAULT_TIMEOUT):
    """Return the Google Geocoding adapter for Site Address forward-geocode.

    Independent of the cellular-location provider. Uses only the private Google
    SERVER key (``api_key``) held in the server-key bundle.
    """
    return GoogleAdapter(bundle, timeout=timeout)
