# status/rtk

<!-- path: status/rtk -->
<!-- type: status -->
<!-- response: object -->

[status](README.md) / rtk

---

RTK (Real Time Kinematic) correction state: the NTRIP/LPP correction link, the
RTCM stream counters, and the corrected GNSS solution.

**Feature-gated.** `status/rtk` and `config/system/rtk` are both `null` on
models without RTK support (verified: E3000 returns `null`, R2400 returns the
full struct). Gate on the parent path existing before using any field. There is
no DTD for status paths — `/api/dtd/status/rtk` returns
`{"exception": "key", "key": "status"}`.

Verified on an R2400-5GF-NA running NCOS 7.26.81 with an NTRIP caster.

### Fields (top-level)

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | boolean | RTK feature enabled |
| `correction_source` | object | Correction link state. See below |
| `corrections` | object | RTCM stream counters. See below |
| `gnss` | object | Corrected GNSS solution. See below |
| `mqtt` | object | MQTT publisher state. See below |

**correction_source**

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `ntrip` or `lpp` |
| `format` | string | Protocol revision, e.g. `v1` |
| `state` | string | e.g. `streaming` |
| `error` | string | `null` when healthy |
| `connected_at` | number | Unix epoch of connect |
| `uptime_s` | number | Seconds connected |
| `retry_interval_s` | number | `null` while connected |
| `detail` | object | Source-specific detail. See below |

**correction_source.detail** (NTRIP)

| Field | Type | Description |
|-------|------|-------------|
| `host` | string | Caster hostname |
| `port` | integer | Caster port |
| `mountpoint` | string | Mountpoint, e.g. `AUTO` |
| `gga_rate_s` | integer | How often the router sends its GGA upstream |
| `last_gga_sent` | string | Last GGA sentence sent to the caster |
| `last_gga_at` | number | Unix epoch of that send |
| `gga_send_failures` | integer | Cumulative upstream GGA failures |

**corrections**

| Field | Type | Description |
|-------|------|-------------|
| `frames_total` | integer | RTCM frames received |
| `frames_dropped` | integer | RTCM frames dropped |
| `frames_queued` | integer | RTCM frames queued |
| `bytes_received` | integer | Total RTCM bytes |
| `crc_failures` | integer | RTCM CRC failures |
| `last_frame_at` | number | Unix epoch of the last frame |
| `msg_types_seen` | array | RTCM message type numbers, e.g. `[1005, 1074, 1084, 1230]` |

**gnss**

| Field | Type | Description |
|-------|------|-------------|
| `fix_quality` | string | e.g. `RTK_FLOAT`, `RTK_DIFFERENTIAL` |
| `fix_sentence` | string | Single GGA with the **corrected** position |
| `diff_age_s` | number | Age of the differential correction |
| `ref_station_id` | integer | Base station ID |
| `satellites` | integer | Satellites in the corrected solution |
| `recent_positions` | array | Last 10 fixes: `{lat, lon, alt, quality, time}` |

**mqtt**

| Field | Type | Description |
|-------|------|-------------|
| `connected` | boolean | MQTT connected |
| `publish_failures` | integer | Cumulative publish failures |
| `last_publish_at` | number | Unix epoch of the last publish |

### Pre-correction vs corrected position

Both solutions are live in the status tree at the same time, which makes it
possible to measure exactly what the corrections are doing:

| | Path | Typical GGA quality |
|---|---|---|
| **Pre-correction** (raw modem GNSS) | `status/gps/devices/{mdm_uid}/nmea` | `1` (autonomous) |
| **Corrected** (RTK engine) | `status/rtk/gnss/fix_sentence` | `2` / `4` / `5` |

The corrected position also appears at `status/gps/fix` and in
`status/gps/nmea`; `status/gps/devices/{mdm_uid}` is the only place the
*un*corrected modem solution is exposed. On a bench R2400 the two sat about
0.8–3 m apart horizontally and ~3 m apart in altitude.

Pick the modem UID at runtime — there can be several entries under
`status/gps/devices` and the ones that are not the GNSS source are `{}`.

**Update rate: both solutions are 1 Hz** (measured 1.00–1.05 Hz, with GGA UTC
stamps advancing exactly one per second). Polling faster than that returns the
same fix repeatedly, so key recorded samples on the GGA UTC stamp if you need
one row per epoch.

### Example response
```json
{
  "enabled": true,
  "correction_source": {
    "type": "ntrip",
    "format": "v1",
    "state": "streaming",
    "error": null,
    "connected_at": 1791126771.1149845,
    "uptime_s": 701,
    "retry_interval_s": null,
    "detail": {
      "host": "truertk.example.com",
      "port": 2101,
      "mountpoint": "AUTO",
      "gga_rate_s": 10,
      "last_gga_sent": "$GNGGA,152423.000,4340.3868045,N,11617.5251602,W,2,19,0.68,808.584,M,-18.583,M,0002,1607*47\r\n",
      "last_gga_at": 1791127468.8820019,
      "gga_send_failures": 1
    }
  },
  "corrections": {
    "frames_total": 8200,
    "frames_dropped": 0,
    "frames_queued": 5,
    "bytes_received": 634585,
    "crc_failures": 0,
    "last_frame_at": 1791127471.9187977,
    "msg_types_seen": [1005, 1029, 1033, 1074, 1084, 1094, 1114, 1124, 1230]
  },
  "gnss": {
    "fix_quality": "RTK_DIFFERENTIAL",
    "fix_sentence": "$GNGGA,152426.000,4340.3868042,N,11617.5251588,W,2,19,0.68,808.596,M,-18.584,M,0002,1607*40\r\n",
    "diff_age_s": 2.0,
    "ref_station_id": 1607,
    "satellites": 19,
    "recent_positions": [
      {"lat": 43.6731134, "lon": -116.292086, "alt": 808.596, "quality": 2, "time": "152426.000"}
    ]
  },
  "mqtt": {
    "connected": true,
    "publish_failures": 0,
    "last_publish_at": 1791127489.171818
  }
}
```

### SDK Example
```python
import cp

rtk = cp.get('status/rtk')
if not isinstance(rtk, dict):
    cp.log('RTK is not supported on this router')
else:
    gnss = rtk.get('gnss') or {}
    source = rtk.get('correction_source') or {}
    cp.log('RTK {} via {} ({}) sats={}'.format(
        gnss.get('fix_quality'),
        source.get('type'),
        source.get('state'),
        gnss.get('satellites')))
```

### REST
```
GET /api/status/rtk
GET /api/status/rtk/gnss
GET /api/status/rtk/gnss/fix_sentence
GET /api/status/rtk/correction_source
GET /api/status/rtk/corrections
```

### GGA fix quality codes

The quality field (field 6) of the GGA sentence tells you which solution you
are looking at, and implies the accuracy you can expect:

| Code | Fix type | Typical accuracy | Description |
|------|----------|------------------|-------------|
| 0 | Invalid | – | No position fix available |
| 1 | GPS (SPS) | 2–5 m | Standard autonomous GPS, no corrections |
| 2 | DGPS | 0.5–2 m | Differential GPS — corrections from SBAS (WAAS, EGNOS) or a base station |
| 3 | PPS | < 0.3 m | Precise Positioning Service (military/authorised users) |
| 4 | RTK Fixed | 1–3 cm | Full carrier-phase solution resolved — highest precision |
| 5 | RTK Float | 10–30 cm | Carrier-phase ambiguities not fully resolved — converging to Fixed |
| 6 | Dead Reckoning | varies | Estimated from last known fix and motion sensors |
| 7 | Manual | – | Position entered manually |
| 8 | Simulation | – | Simulated position for testing |

**RTK Float (5) is a transient state, not a destination.** It means the
carrier-phase ambiguities are not fully resolved and the solution is still
converging toward Fixed, which normally takes 10–60 s depending on satellite
visibility and baseline length. Code anything that needs survey-grade accuracy
to wait for quality 4 rather than accepting 5.

Note the router reports quality 2 as `RTK_DIFFERENTIAL` in
`status/rtk/gnss/fix_quality`, where the NMEA standard name is DGPS.

### GSA fix mode and the full DOP set

**GGA carries only HDOP.** PDOP and VDOP are in the GSA sentence, which is
present in both `status/gps/nmea` and
`status/gps/devices/{mdm_uid}/nmea`:

```
$xxGSA,mode,fix_mode,sv1..sv12,PDOP,HDOP,VDOP,systemId*cs
  field 2  = fix mode
  field 15 = PDOP, field 16 = HDOP, field 17 = VDOP
```

| GSA fix mode (field 2) | Meaning |
|------|---------|
| 1 | No fix |
| 2 | 2D fix — latitude and longitude only, altitude unreliable |
| 3 | 3D fix — latitude, longitude and altitude |

Receivers emit **one GSA per constellation** (trailing `systemId` 1–5) with
identical DOP values, and the per-constellation ones can have empty satellite
slots — so take the first sentence that parses with a DOP value rather than
assuming a single GSA. Verified values on an R2400: corrected
`PDOP 1.23 / HDOP 0.65 / VDOP 1.05`, raw modem `PDOP 1.1 / HDOP 0.6 / VDOP 0.9`.

A 2D fix is worth checking for explicitly: the altitude field still contains a
number, it is just not trustworthy.

### Related

- [gps.md](gps.md) — GPS fix, NMEA, and per-device raw sentences
- `config/system/rtk` — RTK configuration (`source`, `ntrip`, `lpp`)
- `apps/rtk_compare/` — sample app that records both solutions to CSV
