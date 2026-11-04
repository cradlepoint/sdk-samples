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
.venv/bin/pip3 install -t path/to/app_folder --python-version 3.8 --only-binary=:all: \
    --no-deps "pynmeagps==1.0.42"
rm -rf path/to/app_folder/pynmeagps/__pycache__ path/to/app_folder/pynmeagps-*.dist-info
```

Pin 1.0.42: later releases need Python 3.9+/3.10+, and every 3.8-compatible release is yanked
on PyPI, so an unpinned install fails on cppython.

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

If RTK/NTRIP is configured, the higher-accuracy corrected GGA is available at:

```
GET /api/status/rtk/gnss/fix_sentence
```

Returns a single GNGGA string (not an array):
```
"$GNGGA,152426.000,4340.3868042,N,11617.5251588,W,2,19,0.68,808.596,M,-18.584,M,0002,1607*40"
```

**The old flat `status/rtk/ntrip/*` and `status/rtk/rtcm_*` paths do not
exist.** The tree is grouped into `correction_source`, `corrections`, `gnss`
and `mqtt` — see **[rtk.md](rtk.md)** for every field, verified on an R2400
running NCOS 7.26.81.

Quick map from the old names to the current ones:

| Old (does not exist) | Current |
|---|---|
| `status/rtk/ntrip/rtk_sentence` | `status/rtk/gnss/fix_sentence` |
| `status/rtk/ntrip/rtk_quality` | `status/rtk/gnss/fix_quality` |
| `status/rtk/ntrip/connected` | `status/rtk/correction_source/state` |
| `status/rtk/ntrip/last_gga_reminder` | `status/rtk/correction_source/detail/last_gga_sent` |
| `status/rtk/ntrip/error_detail` | `status/rtk/correction_source/error` |
| `status/rtk/rtcm_total` | `status/rtk/corrections/frames_total` |
| `status/rtk/rtcm_dropped` | `status/rtk/corrections/frames_dropped` |
| `status/rtk/rtcm_queued` | `status/rtk/corrections/frames_queued` |
| `status/rtk/mqtt_connected` | `status/rtk/mqtt/connected` |

#### Pre-correction vs corrected position

`status/gps/fix`, `status/gps/nmea` and `status/rtk/gnss` all carry the
**RTK-corrected** position. The only place the **uncorrected** modem GNSS
solution is exposed is the per-device subtree:

```
status/gps/devices/{mdm_uid}/nmea   -> $GPGGA with quality 1 (autonomous)
status/rtk/gnss/fix_sentence        -> $GNGGA with quality 2 / 4 / 5 (RTK)
```

Both update at 1 Hz. Discover `{mdm_uid}` at runtime: several entries can exist
under `status/gps/devices` and the non-GNSS ones are `{}`. See
`apps/rtk_compare/` for a working comparison app.

### NMEA timing: status tree vs GNSS socket

Verified on R2400, NCOS 7.26.100, against a LAN host synced to time.apple.com.

**`status/gps/nmea`** is replaced once per second as a whole array:
- Published **0.7–1.0 s after** the GPS second of its GGA, and the delay drifts between runs.
- **RMC and ZDA are one epoch older than GGA/GLL** in the same snapshot
  (e.g. `$GNRMC,140910.000,...` alongside `$GNGGA,140911.000,...`). Take the date from RMC and
  the freshest time of day from GGA, handling midnight rollover.
- `status/gps/fix/time` lags even further (~1.2 s).

**GNSS daemon socket, `127.0.0.1:17488`** (TCP, local only). Exists on R2400 as well as IBR1700:
- `NMEA\r\n` sends the position history as one burst, then live sentences each second.
- `ALL\r\n` sends everything, including 10 Hz `$PCPTMIMU` and `$PCPTMINR` (~140 lines/s).
- Each epoch arrives in the order GGA, GLL, GSA..., RMC, VTG, ZDA, then `$PCPTMDBG` and
  `$PCPTMGPSTIME`, within a few ms. The whole burst lands ~0.95 s into the following second.

**Recovering the exact GPS-second instant (for NTP / precise timestamping):**

- `$PCPTMDBG,UTC Time Tag <fix_uptime> system time <sys_uptime>` — `fix_uptime` is the daemon's
  uptime value for this epoch's fix (already corrected for receiver latency); `sys_uptime` is the
  daemon's uptime-clock reading when it emitted the line. Record `time.monotonic()` on arrival.
- The daemon uptime clock and the app's `time.monotonic()` are both `CLOCK_MONOTONIC` but with
  **different origins**, so `C = monotonic_at_arrival - sys_uptime` is a constant (~95 ms on an
  R2400, the socket+scheduler transport delay) — NOT zero. `fix_uptime + C` places the fix on the
  app clock with the transport delay removed. Re-measure `C` every line to absorb slow skew.
- `fix_uptime` still trails the true GPS-second epoch by a fixed receiver+daemon fix latency,
  ~141 ms on an R2400 (measured against time.apple.com, stable to ±1 ms). Subtract it as a
  tunable constant; it is not exposed in any sentence.
- `$PCPTMGPSTIME,<fix_uptime>,<field3>,<gps_week>` — field 3 is **NOT hhmmss UTC**; its seconds
  run past 60 (a GPS time-of-week count). Take the UTC second from RMC, not from this line.
- Net result: ±3 ms vs true UTC. Skip the history burst by only accepting epochs ~1 s apart.
  `apps/NTP_GPS/` is a working example.

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
