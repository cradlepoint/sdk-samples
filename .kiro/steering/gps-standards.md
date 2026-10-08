---
inclusion: fileMatch
fileMatchPattern: "**/*gps*,**/*nmea*,**/*gnss*,**/*rtk*"
description: "GPS, GNSS, NMEA sentence parsing and RTK/NTRIP corrections: pynmeagps usage, status/gps and status/rtk trees, fix quality, DOP, and GPS injection"
---
# GPS and NMEA Sentence Parsing

- **Use `pynmeagps` for NMEA parsing** - never write custom NMEA parsers. Install to app folder: `.venv/bin/pip3 install -t path/to/app_folder pynmeagps` (Mac/Linux) or `.venv\Scripts\pip install -t path/to/app_folder pynmeagps` (Windows)
- **NEVER copy pynmeagps from another app** - always use pip to install a fresh copy into the target app folder. This ensures you get the latest compatible version
- **NMEA data sources on the router**:
  - `status/gps/nmea` — array of current NMEA sentences
  - `status/gps/devices/{mdm_uid}/current_nmea` — per-modem NMEA sentences
  - IBR1700 GNSS daemon — TCP socket on `127.0.0.1:17488` (see `ibr1700_gnss` app)
- **NEVER manually split NMEA sentences by comma** - use pynmeagps for proper checksum validation and typed field access
- **`PCPTMINR` is a proprietary Cradlepoint NMEA sentence** - it appears in `status/gps/nmea` and pynmeagps will raise "Unknown msgID". This is expected — catch the exception and skip it silently
- **`status/rtk/ntrip/rtk_sentence` and `status/rtk/rtcm_total` DO NOT EXIST** — older notes in this repo claimed otherwise. The real `status/rtk` tree is **grouped** (verified R2400, NCOS 7.26.81): `{enabled, correction_source{type, format, state, error, connected_at, uptime_s, retry_interval_s, detail{host, port, mountpoint, gga_rate_s, last_gga_sent, last_gga_at, gga_send_failures}}, corrections{frames_total, frames_dropped, frames_queued, bytes_received, crc_failures, last_frame_at, msg_types_seen[]}, gnss{fix_quality, fix_sentence, diff_age_s, ref_station_id, satellites, recent_positions[10]}, mqtt{connected, publish_failures, last_publish_at}}`. See `docs/ncos-api/status/rtk.md`
- **Talker IDs**: `GP` = GPS only, `GN` = multi-constellation (GPS+GLONASS+etc.), `GL` = GLONASS. Cradlepoint routers may emit either `GPRMC` or `GNRMC` depending on modem/config. pynmeagps handles both transparently — `msg.msgID` returns `RMC` regardless of talker prefix
- **Common sentence types and their pynmeagps fields**:
  - **GGA** (fix quality, position, altitude): `msg.lat`, `msg.lon`, `msg.alt` (meters above sea level), `msg.altUnit` (`'M'`), `msg.numSV` (satellite count), `msg.quality` (0=no fix, 1=GPS, 2=DGPS), `msg.HDOP`, `msg.sep` (geoid separation)
  - **RMC** (position, speed, course, date/time): `msg.lat`, `msg.lon`, `msg.spd` (speed over ground in knots), `msg.cog` (course over ground in degrees true), `msg.date`, `msg.time`, `msg.status` (`'A'`=active/valid, `'V'`=void)
  - **VTG** (track/speed detail): `msg.cogt` (true course°), `msg.cogm` (magnetic course°), `msg.sogn` (speed knots), `msg.sogk` (speed km/h)
  - **GSA** (DOP and active satellites): `msg.PDOP`, `msg.HDOP`, `msg.VDOP`, `msg.navMode` (1=no fix, 2=2D, 3=3D)
  - **GSV** (satellites in view): `msg.numSV`, repeating group with `svid`, `elv`, `az`, `cno`
- **Speed conversion from knots**: `speed_kmh = msg.spd * 1.852` or `speed_mph = msg.spd * 1.15078`
- **Parsing example with position, altitude, speed, and heading**:
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
                if msg.status == 'A':
                    cp.log(f'RMC: lat={msg.lat} lon={msg.lon} '
                           f'speed={msg.spd}kn course={msg.cog}°')
        except Exception as e:
            cp.log(f'NMEA parse error: {e}')
```

## Corrected vs uncorrected position

- **The UNcorrected GNSS fix is only in `status/gps/devices/{mdm_uid}`** — `status/gps/fix`,
  `status/gps/nmea` and `status/rtk/gnss` all carry the RTK-**corrected** position (GGA quality
  2/4/5). The per-device subtree is the raw modem solution (GGA quality 1), which is what makes a
  pre/post correction comparison possible. Discover `{mdm_uid}` at runtime: several entries can
  exist under `status/gps/devices` and the non-GNSS ones are `{}`.
- **Both solutions update at exactly 1 Hz** — polling faster just returns the same fix. Key
  recorded samples on the GGA UTC stamp if you need one row per epoch.

## Fix quality and DOP

- **GGA carries only HDOP. PDOP and VDOP are in GSA, and GSA is also the only source of the
  2D/3D fix mode.** `$xxGSA,mode,fix_mode,sv1..sv12,PDOP,HDOP,VDOP,systemId`: field 2 is the fix
  mode (1=no fix, 2=2D with unreliable altitude, 3=3D), fields 15/16/17 are PDOP/HDOP/VDOP.
- **Receivers emit one GSA per constellation** (trailing `systemId` 1–5) with identical DOPs, and
  some have empty satellite slots. Take the first sentence that parses with a DOP value instead of
  assuming a single GSA.
- **GGA quality 5 (RTK Float) is a transient converging state, not a destination** — it resolves
  to quality 4 (RTK Fixed) in 10–60 s. Accuracy is 10–30 cm as Float versus 1–3 cm as Fixed, so
  anything survey-grade must wait for 4. Full quality/accuracy table in
  `docs/ncos-api/status/rtk.md`.

## RTK feature gating

- **`config/system/rtk` and `status/rtk` are `null` on models without RTK support** (e.g. E3000);
  an RTK-capable model (R2400) has a populated `config/system/rtk/ntrip` struct (`format`,
  `gga_rate`, `host`, `mountpoint`, `port`, `username`, `password`). Gate on the parent path
  existing before writing. A PUT to an unsupported path can return `ok` over the on-router socket
  and write nothing — read it back. See `docs/ncos-api/gotchas.md`.

## GPS injection

Write scalar sub-paths (`fix/lock`, `fix/latitude` as dict, `lastpos/latitude`, etc.) plus
`status/gps/devices/None/current_nmea`, with a 0.5 s keepalive loop. GPS must be enabled with
keepalive, and `control/gps/stop` each cycle. **May only work reliably from NCM-installed apps**
(production SDK mode) — dev-mode SCP installs appear to have lower privilege for status-tree
writes that reach WPC. Confirmed working pattern: `connected_ems_vehicle/ncm_client.py`; see
also `docs/ncos-api/status/gps.md`.
