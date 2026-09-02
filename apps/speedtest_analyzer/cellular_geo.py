"""Provider-independent GeoView configuration and site context helpers.

GeoView user configuration is persisted in NCOS SDK appdata so it survives
SDK application package upgrades. This module intentionally contains no
external Geo Provider integrations.

Google/Unwired-style network calls belong in later provider adapters after
those APIs are researched and their current contracts are confirmed.
"""

import json
import threading

import cp


GEO_APPDATA_KEY = 'geoview_settings'
_GEO_SCHEMA_VERSION = 2
_geo_lock = threading.RLock()


def _empty_locations():
    """Return independent storage for every supported Site Location method."""
    return {
        'device_gps': {
            'latitude': None,
            'longitude': None,
        },
        'manual_coordinates': {
            'latitude': None,
            'longitude': None,
        },
        'site_address': {
            'address': '',
        },
    }


def _active_location(
    source,
    locations,
):
    """Build the compatibility/public location object for the active source."""
    if source == 'device_gps':
        value = locations['device_gps']

        return {
            'source': source,
            'latitude': value['latitude'],
            'longitude': value['longitude'],
            'address': '',
        }

    if source == 'manual_coordinates':
        value = locations[
            'manual_coordinates'
        ]

        return {
            'source': source,
            'latitude': value['latitude'],
            'longitude': value['longitude'],
            'address': '',
        }

    value = locations['site_address']

    return {
        'source': 'site_address',
        'latitude': None,
        'longitude': None,
        'address': value['address'],
    }


def default_geo_settings():
    """Return fresh code defaults without writing anything to appdata."""
    locations = _empty_locations()
    source = 'device_gps'

    return {
        'schema_version': _GEO_SCHEMA_VERSION,
        'configured': False,
        'provider': 'none',
        'active_location_source': source,
        'locations': locations,
        'location': _active_location(
            source,
            locations,
        ),
    }


def _number(value):
    if value in (None, ''):
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def _validate_coordinates(
    latitude,
    longitude,
    label,
    required=False,
    reject_zero_pair=False,
):
    """Normalize one optional coordinate pair."""
    latitude_value = _number(
        latitude
    )

    longitude_value = _number(
        longitude
    )

    supplied = (
        latitude not in (None, '')
        or longitude not in (None, '')
    )

    if not supplied and not required:
        return (
            None,
            None,
        )

    if (
        latitude_value is None
        or longitude_value is None
    ):
        raise ValueError(
            '%s require latitude and longitude'
            % label
        )

    if not (
        -90.0 <= latitude_value <= 90.0
    ):
        raise ValueError(
            '%s latitude must be between -90 and 90'
            % label
        )

    if not (
        -180.0 <= longitude_value <= 180.0
    ):
        raise ValueError(
            '%s longitude must be between -180 and 180'
            % label
        )

    if (
        reject_zero_pair
        and latitude_value == 0.0
        and longitude_value == 0.0
    ):
        raise ValueError(
            '%s cannot use 0.0, 0.0 without a valid GPS fix'
            % label
        )

    return (
        latitude_value,
        longitude_value,
    )


def gps_fix_is_usable(gps):
    """Return True only for a currently locked, usable Device GPS fix."""
    if not isinstance(
        gps,
        dict,
    ):
        return False

    gps_lock = gps.get(
        'gps_lock'
    )

    if gps_lock is None:
        gps_lock = gps.get(
            'lock'
        )

    if not bool(
        gps_lock
    ):
        return False

    try:
        latitude, longitude = (
            _validate_coordinates(
                gps.get(
                    'latitude'
                ),
                gps.get(
                    'longitude'
                ),
                'Device GPS',
                required=True,
                reject_zero_pair=True,
            )
        )

    except ValueError:
        return False

    return (
        latitude is not None
        and longitude is not None
    )


def _legacy_locations(
    value,
    source,
):
    """Migrate the v1 single-location model into independent v2 locations."""
    locations = _empty_locations()

    legacy = value.get(
        'location'
    )

    if not isinstance(
        legacy,
        dict,
    ):
        legacy = {}

    if source == 'device_gps':
        locations['device_gps'] = {
            'latitude':
                legacy.get(
                    'latitude'
                ),
            'longitude':
                legacy.get(
                    'longitude'
                ),
        }

    elif source == 'manual_coordinates':
        locations[
            'manual_coordinates'
        ] = {
            'latitude':
                legacy.get(
                    'latitude'
                ),
            'longitude':
                legacy.get(
                    'longitude'
                ),
        }

    elif source == 'site_address':
        locations['site_address'] = {
            'address':
                legacy.get(
                    'address'
                )
                or '',
        }

    return locations


def normalize_geo_settings(
    value,
    mark_configured=None,
):
    """Validate and normalize persisted/public GeoView settings."""
    if not isinstance(
        value,
        dict,
    ):
        value = {}

    provider = str(
        value.get(
            'provider'
        )
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

    legacy_location = value.get(
        'location'
    )

    if not isinstance(
        legacy_location,
        dict,
    ):
        legacy_location = {}

    source = str(
        value.get(
            'active_location_source'
        )
        or legacy_location.get(
            'source'
        )
        or value.get(
            'location_source'
        )
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

    raw_locations = value.get(
        'locations'
    )

    if isinstance(
        raw_locations,
        dict,
    ):
        locations = {
            'device_gps':
                raw_locations.get(
                    'device_gps'
                )
                if isinstance(
                    raw_locations.get(
                        'device_gps'
                    ),
                    dict,
                )
                else {},
            'manual_coordinates':
                raw_locations.get(
                    'manual_coordinates'
                )
                if isinstance(
                    raw_locations.get(
                        'manual_coordinates'
                    ),
                    dict,
                )
                else {},
            'site_address':
                raw_locations.get(
                    'site_address'
                )
                if isinstance(
                    raw_locations.get(
                        'site_address'
                    ),
                    dict,
                )
                else {},
        }

    else:
        locations = _legacy_locations(
            value,
            source,
        )

    device = locations[
        'device_gps'
    ]

    device_latitude, device_longitude = (
        _validate_coordinates(
            device.get(
                'latitude'
            ),
            device.get(
                'longitude'
            ),
            'Device GPS coordinates',
            required=False,
            reject_zero_pair=True,
        )
    )

    manual = locations[
        'manual_coordinates'
    ]

    manual_required = (
        source ==
        'manual_coordinates'
    )

    manual_latitude, manual_longitude = (
        _validate_coordinates(
            manual.get(
                'latitude'
            ),
            manual.get(
                'longitude'
            ),
            'Manual coordinates',
            required=manual_required,
            reject_zero_pair=False,
        )
    )

    address = str(
        locations[
            'site_address'
        ].get(
            'address'
        )
        or ''
    ).strip()

    if len(address) > 300:
        raise ValueError(
            'Site address is too long'
        )

    if (
        source == 'site_address'
        and not address
    ):
        raise ValueError(
            'Site Address cannot be empty'
        )

    normalized_locations = {
        'device_gps': {
            'latitude':
                device_latitude,
            'longitude':
                device_longitude,
        },
        'manual_coordinates': {
            'latitude':
                manual_latitude,
            'longitude':
                manual_longitude,
        },
        'site_address': {
            'address':
                address,
        },
    }

    configured = bool(
        value.get(
            'configured'
        )
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
        'active_location_source':
            source,
        'locations':
            normalized_locations,
        # Compatibility/public active location used by existing UI paths.
        'location':
            _active_location(
                source,
                normalized_locations,
            ),
    }


def is_group_safe_source(source):
    """True when a GeoView active location source is a Group-safe POLICY.

    Group-safe means the policy does not carry device-specific physical
    location data. Only ``device_gps`` qualifies for v1.1.2 (§40/§42):
    ``manual_coordinates`` and ``site_address`` are device-specific.
    """
    return source == 'device_gps'


def strip_runtime_gps_for_persistence(persisted):
    """Return a persisted GeoView section with RUNTIME device GPS coordinates
    cleared, regardless of the active source (§39, §40).

    Current device GPS latitude/longitude are RUNTIME state and must never be
    written into canonical configuration (device or group). This clears the
    ``locations.device_gps`` coordinates before persistence. Manual coordinates
    and site address are device-specific PERSISTENT configuration and are kept.
    The active_location_source policy and provider/configured flags are kept.
    """
    if not isinstance(
        persisted,
        dict,
    ):
        return persisted

    result = json.loads(
        json.dumps(
            persisted
        )
    )

    locations = result.get(
        'locations'
    )

    if isinstance(
        locations,
        dict,
    ) and isinstance(
        locations.get(
            'device_gps'
        ),
        dict,
    ):
        # Clear runtime fix; keep the key so the section stays well-formed.
        locations['device_gps'] = {
            'latitude': None,
            'longitude': None,
        }

    return result


def group_sanitized_geoview(persisted):
    """Return a Group-safe copy of a persisted GeoView section (§40, §42).

    Strips device-specific physical location data so a Group standard never
    carries one router's coordinates/address:

    - device_gps: the POLICY is promoted, but current lat/lon are cleared.
      Authoritative Group Device-GPS triggers a fresh runtime poll later.
    - manual_coordinates / site_address: these are device-specific and are
      never promoted; the sanitized section falls back to the device_gps
      policy with empty coordinates. Callers must block promotion of a
      non-Group-safe source before reaching here (this is a defensive floor).

    The returned object stays schema_version 2 and remains a valid persisted
    GeoView section.
    """
    if not isinstance(
        persisted,
        dict,
    ):
        base = default_geo_settings()

        return _persisted_settings(
            base
        )

    source = persisted.get(
        'active_location_source'
    )

    # Non-Group-safe sources collapse to the Device GPS policy with no coords.
    if not is_group_safe_source(
        source
    ):
        source = 'device_gps'

    empty = _empty_locations()

    sanitized = {
        'schema_version':
            _GEO_SCHEMA_VERSION,
        'configured':
            bool(
                persisted.get(
                    'configured'
                )
            ),
        'provider':
            str(
                persisted.get(
                    'provider'
                )
                or 'none'
            ),
        'active_location_source':
            source,
        # Device-specific physical location data is intentionally cleared.
        'locations':
            empty,
    }

    return sanitized


def _persisted_settings(
    normalized,
):
    """Return only canonical v2 values written to SDK appdata."""
    return {
        'schema_version':
            _GEO_SCHEMA_VERSION,
        'configured':
            bool(
                normalized[
                    'configured'
                ]
            ),
        'provider':
            normalized[
                'provider'
            ],
        'active_location_source':
            normalized[
                'active_location_source'
            ],
        'locations':
            normalized[
                'locations'
            ],
    }


def load_geo_settings():
    """Load GeoView configuration from NCOS SDK appdata."""
    with _geo_lock:
        try:
            raw = cp.get_appdata(
                GEO_APPDATA_KEY
            )

        except Exception:
            return default_geo_settings()

        # Code defaults are intentionally not written to appdata.
        if raw in (
            None,
            '',
        ):
            return default_geo_settings()

        try:
            if isinstance(
                raw,
                dict,
            ):
                value = raw

            else:
                value = json.loads(
                    raw
                )

            return normalize_geo_settings(
                value
            )

        except (
            ValueError,
            TypeError,
            json.JSONDecodeError,
        ):
            return default_geo_settings()


# NOTE (v1.1.2): the former save_geo_settings() writer was removed. GeoView
# configuration is persisted exclusively through the canonical Configuration
# Manager (speedtest_analyzer) via the Device/NCM Group workflow. This module
# now only NORMALIZES and LOADS GeoView settings (for legacy reads and
# canonical operation) and never writes the legacy geoview_settings key.


def apply_geo_settings(
    geo,
    settings,
):
    """Overlay provider-independent settings onto the GeoView response."""
    result = (
        dict(
            geo
        )
        if isinstance(
            geo,
            dict,
        )
        else {}
    )

    normalized = normalize_geo_settings(
        settings
    )

    result[
        'schema_version'
    ] = normalized[
        'schema_version'
    ]

    result[
        'provider'
    ] = normalized[
        'provider'
    ]

    result[
        'configured'
    ] = normalized[
        'configured'
    ]

    result[
        'status'
    ] = (
        'configured'
        if normalized[
            'configured'
        ]
        else 'not_configured'
    )

    result[
        'active_location_source'
    ] = normalized[
        'active_location_source'
    ]

    result[
        'locations'
    ] = {
        'device_gps':
            dict(
                normalized[
                    'locations'
                ][
                    'device_gps'
                ]
            ),
        'manual_coordinates':
            dict(
                normalized[
                    'locations'
                ][
                    'manual_coordinates'
                ]
            ),
        'site_address':
            dict(
                normalized[
                    'locations'
                ][
                    'site_address'
                ]
            ),
    }

    # Keep the active-location compatibility object for existing consumers.
    result[
        'location'
    ] = dict(
        normalized[
            'location'
        ]
    )

    # No provider adapter is active in this foundation phase.
    result.setdefault(
        'estimated_locations',
        0,
    )

    return result
