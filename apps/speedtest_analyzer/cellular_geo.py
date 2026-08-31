"""Local GeoView settings and provider-independent site context helpers.

This module intentionally contains no external Geo Provider integrations.
Google/Unwired-style network calls belong in later provider adapters after
those APIs are researched and their current contracts are confirmed.
"""

import json
import os
import threading


GEO_SETTINGS_FILE = 'tmp/geoview_settings.json'
GEO_SETTINGS_TEMP_FILE = GEO_SETTINGS_FILE + '.tmp'
_GEO_SCHEMA_VERSION = 1
_geo_lock = threading.RLock()


def default_geo_settings():
    """Return a fresh default GeoView settings object."""
    return {
        'schema_version': _GEO_SCHEMA_VERSION,
        'configured': False,
        'provider': 'none',
        'location': {
            'source': 'device_gps',
            'latitude': None,
            'longitude': None,
            'address': '',
        },
    }


def _number(value):
    if value in (None, ''):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_geo_settings(value, mark_configured=None):
    """Validate and normalize one persisted/public GeoView settings object."""
    if not isinstance(value, dict):
        value = {}

    provider = str(
        value.get('provider')
        or 'none'
    ).strip().lower()

    if provider not in (
        'none',
        'google',
        'unwired',
    ):
        raise ValueError(
            'Unsupported Geo Provider'
        )

    location = value.get('location')

    if not isinstance(location, dict):
        location = {}

    source = str(
        location.get('source')
        or value.get('location_source')
        or 'device_gps'
    ).strip().lower()

    if source not in (
        'device_gps',
        'manual_coordinates',
        'site_address',
    ):
        raise ValueError(
            'Unsupported site location source'
        )

    latitude = _number(
        location.get('latitude')
    )

    longitude = _number(
        location.get('longitude')
    )

    address = str(
        location.get('address')
        or ''
    ).strip()

    if len(address) > 300:
        raise ValueError(
            'Site address is too long'
        )

    if source == 'manual_coordinates':
        if latitude is None or longitude is None:
            raise ValueError(
                'Manual coordinates require latitude and longitude'
            )

    if (
        latitude is not None
        and not (-90.0 <= latitude <= 90.0)
    ):
        raise ValueError(
            'Latitude must be between -90 and 90'
        )

    if (
        longitude is not None
        and not (-180.0 <= longitude <= 180.0)
    ):
        raise ValueError(
            'Longitude must be between -180 and 180'
        )

    if (
        source == 'site_address'
        and not address
    ):
        raise ValueError(
            'Site Address cannot be empty'
        )

    configured = bool(
        value.get('configured')
    )

    if mark_configured is not None:
        configured = bool(
            mark_configured
        )

    return {
        'schema_version':
            _GEO_SCHEMA_VERSION,

        'configured':
            configured,

        'provider':
            provider,

        'location': {
            'source':
                source,

            'latitude':
                latitude,

            'longitude':
                longitude,

            'address':
                address,
        },
    }


def load_geo_settings(path=GEO_SETTINGS_FILE):
    """Load local GeoView settings; invalid/missing data falls back safely."""
    with _geo_lock:
        if not os.path.exists(path):
            return default_geo_settings()

        try:
            with open(
                path,
                'r',
                encoding='utf-8',
            ) as handle:
                value = json.load(handle)

            return normalize_geo_settings(value)

        except (
            OSError,
            ValueError,
            TypeError,
            json.JSONDecodeError,
        ):
            return default_geo_settings()


def save_geo_settings(value, path=GEO_SETTINGS_FILE):
    """Atomically persist explicit GeoView configuration changes."""
    normalized = normalize_geo_settings(
        value,
        mark_configured=True,
    )

    directory = (
        os.path.dirname(path)
        or '.'
    )

    temp_path = path + '.tmp'

    with _geo_lock:
        os.makedirs(
            directory,
            exist_ok=True,
        )

        try:
            with open(
                temp_path,
                'w',
                encoding='utf-8',
            ) as handle:
                json.dump(
                    normalized,
                    handle,
                    separators=(',', ':'),
                    sort_keys=True,
                )

                handle.flush()
                os.fsync(handle.fileno())

            os.replace(
                temp_path,
                path,
            )

            try:
                directory_fd = os.open(
                    directory,
                    os.O_RDONLY,
                )

                try:
                    os.fsync(directory_fd)

                finally:
                    os.close(directory_fd)

            except OSError:
                # Directory fsync is best-effort on constrained platforms.
                pass

        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)

                except OSError:
                    pass

    return normalized


def apply_geo_settings(geo, settings):
    """Overlay public local settings onto a site-wide GeoView response."""
    result = (
        dict(geo)
        if isinstance(geo, dict)
        else {}
    )

    normalized = normalize_geo_settings(
        settings
    )

    result['provider'] = (
        normalized['provider']
    )

    result['configured'] = (
        normalized['configured']
    )

    result['status'] = (
        'configured'
        if normalized['configured']
        else 'not_configured'
    )

    result['location'] = dict(
        normalized['location']
    )

    # No provider adapter is active in this foundation phase.
    result.setdefault(
        'estimated_locations',
        0,
    )

    return result
