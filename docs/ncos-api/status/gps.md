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

### GPS Coordinate Injection (Simulated GPS)

To inject simulated GPS coordinates that NCM Location Services will report:

1. **Disable GPS to stop gnssd** from overwriting your injected data:
```python
cp.put("config/system/gps/enabled", False)
```

2. **Each cycle, write the ENTIRE `status/gps` tree in one put.** Partial writes (sub-paths or sub-dicts) don't reliably reach WPC. You must write the complete tree matching gnssd's output:
```python
cp.put("status/gps", {
    "fix": {
        "accuracy": 3.0,
        "age": 0.0,
        "altitude_meters": 50.0,
        "from_sentence": "GPGGA",
        "ground_speed_knots": speed_knots,
        "heading": heading,
        "latitude": {"degree": 40.0, "minute": 45.0, "second": 14.2},  # floats
        "lock": True,
        "longitude": {"degree": -73.0, "minute": 59.0, "second": 37.1},
        "satellites": 8,
        "time": 143248,  # HHMMSS int
    },
    "lastpos": {
        "age": 0.0,
        "latitude": 40.7539,  # decimal degrees
        "longitude": -73.9936,
        "timestamp": time.time(),
    },
    "nmea": [gga, rmc, pcptminr],  # include $PCPTMINR
    "state": 1,
    "connections": [],
    "schedule": {},
    "ploop": [],
    "devices": {
        "mdm-XXXXX": {
            "current_nmea": [gga + "\r\n", rmc + "\r\n"],
            "fix": {
                "latitude": {"degree": "40.0", "minute": "45.0", "second": "14.2"},  # strings!
                "longitude": {"degree": "-73.0", "minute": "59.0", "second": "37.1"},
                "lock": True, "age": 0, "satellites": 8, "time": 143248,
            },
            "nmea": [gga + "\r\n", rmc + "\r\n"],
        },
    },
})
```

3. **PCPTMINR sentence format** — Cradlepoint proprietary, contains decimal lat/lon:
```
$PCPTMINR,uptime,lat,lon,alt,speed_ms,heading,climb,hacc,vacc,sacc,hdop,vdop,pdop,fix_type,num_sv,*checksum
```

**CRITICAL rules:**
- **Write the FULL `status/gps` tree** — partial writes (`status/gps/fix`, `status/gps/fix/lock`) do NOT reliably reach WPC
- **The modem GPS hardware (`cpevt` via QMI/rmnet) cannot be stopped from the SDK** — `config/wan/devices/{modem}/gps/enabled = False`, `config/system/gps/enabled = False`, `control/gps/stop`, and `gps_interval = 0` all fail to stop the kernel-level QMI GPS session. The modem pushes GPS events every second regardless
- **GPS antenna must be physically disconnected** for reliable injection — when the hardware GPS has a fix, `cpevt` overwrites the status tree every second and WPC reads its data instead of yours
- **Top-level DMS = floats** (43.0), **device-level DMS = strings** ("43.0")
- **Include `$PCPTMINR`** — Cradlepoint proprietary sentence with decimal lat/lon
- **Include `connections`, `schedule`, `ploop`** — even empty, these keys must be present
- NCM reports in "breadcrumbs" mode every ~10 minutes
- See `gps_playback/` for a complete working implementation
