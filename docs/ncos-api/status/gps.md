# status/gps

<!-- path: status/gps -->
<!-- type: status -->
<!-- response: object -->

[status](README.md) / gps

---

GPS fix, position, and device NMEA data.

### Fields (top-level)

| Field | Type | Description |
|-------|------|-------------|
| `fix` | object | See [gps/fix.md](gps/fix.md) |
| `state` | integer | GPS state |
| `nmea` | array | NMEA sentences |
| `lastpos` | object | See sub-table |
| `connections` | object | Connection state (varies) |
| `schedule` | object | Schedule config (varies) |
| `ploop` | object | Poll loop state (varies) |
| `devices` | object | See sub-table |

**lastpos**

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | number | Timestamp |
| `latitude` | number | Latitude |
| `longitude` | number | Longitude |
| `age` | number | Age |

**devices.{mdm_uid}**

| Field | Type | Description |
|-------|------|-------------|
| `current_nmea` | array | NMEA sentences (array of strings) |

### SDK Example
```python
import cp
gps = cp.get('status/gps')
if gps:
    fix = gps.get('fix', {})
    cp.log(f'GPS lock={fix.get("lock")} sats={fix.get("satellites")}')
```

### REST
```
GET /api/status/gps
```

### Parsing NMEA Sentences

Use the `pynmeagps` library for parsing NMEA sentences. Install to your app folder:

```bash
.venv/bin/pip install -t path/to/app_folder pynmeagps
```

Cradlepoint routers may emit `GPRMC` (GPS-only) or `GNRMC` (multi-constellation) depending on modem config. pynmeagps handles both — `msg.msgID` returns `RMC` regardless of talker prefix.

```python
from pynmeagps import NMEAReader
import cp

nmea_sentences = cp.get('status/gps/nmea')
if nmea_sentences:
    for sentence in nmea_sentences:
        try:
            msg = NMEAReader.parse(sentence)
            if msg.msgID == 'GGA':
                cp.log(f'GGA: lat={msg.lat} lon={msg.lon} '
                       f'alt={msg.alt}m sats={msg.numSV}')
            elif msg.msgID == 'RMC':
                if msg.status == 'A':  # 'A'=active, 'V'=void
                    speed_kmh = msg.spd * 1.852
                    cp.log(f'RMC: lat={msg.lat} lon={msg.lon} '
                           f'speed={speed_kmh:.1f}km/h '
                           f'course={msg.cog}°')
        except Exception as e:
            cp.log(f'NMEA parse error: {e}')
```

Key pynmeagps fields by sentence type:
- **GGA**: `lat`, `lon`, `alt` (meters), `numSV`, `quality`, `HDOP`, `sep` (geoid separation)
- **RMC**: `lat`, `lon`, `spd` (knots), `cog` (course°), `date`, `time`, `status`
- **VTG**: `cogt` (true course°), `sogk` (speed km/h), `sogn` (speed knots)

See `dead_reckoning/` for a working usage example.

### Breakout docs (in gps/)
- [gps/fix.md](gps/fix.md) – fix object (10 fields, latitude/longitude depth 3)


### RTK NMEA Source

If RTK/NTRIP is configured, higher-accuracy NMEA data is available at:

```
GET /api/status/rtk/ntrip/rtk_sentence
```

Returns a single GNGGA string (not an array):
```
"$GNGGA,144817.000,3236.9529285,N,09653.9311163,W,2,6,1.82,207.161,M,-23.749,M,0003,0174*7E"
```

Other useful fields in `status/rtk/ntrip/`:
| Field | Type | Description |
|-------|------|-------------|
| `rtk_sentence` | string | Single GNGGA with RTK-corrected position |
| `rtk_quality` | string | e.g. "RTK_DIFFERENTIAL" |
| `connected` | boolean | NTRIP connection status |
| `last_gga_reminder` | string | Last GGA sent to NTRIP caster |
| `error_detail` | string | Connection error details if any |

Parent `status/rtk/` also has:
| Field | Type | Description |
|-------|------|-------------|
| `enabled` | boolean | RTK feature enabled |
| `mqtt_connected` | boolean | MQTT connection status |
| `rtcm_dropped` | integer | Dropped RTCM messages |
| `rtcm_queued` | integer | Queued RTCM messages |
| `rtcm_total` | integer | Total RTCM messages received |

### Proprietary NMEA Sentences

Cradlepoint routers may include proprietary NMEA sentences in `status/gps/nmea`:
- `$PCPTMINR` — Cradlepoint internal sentence. Not parseable by pynmeagps. Catch and skip the parse error.
