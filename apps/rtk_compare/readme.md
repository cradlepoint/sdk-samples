# rtk_compare

<img width="1634" height="848" alt="image" src="https://github.com/user-attachments/assets/774a5e7b-56f6-41a6-8edd-eb2e3a6a7665" />

Records the **pre-correction** and **RTK-corrected** GNSS positions side by
side once per second, writes every sample to a CSV file, and serves a web UI
that plots both tracks on a map colour-coded by fix quality.

Built for routers with NTRIP RTK support (R2400 and similar).

## What "pre" and "post" correction mean here

The router runs two GNSS solutions at the same time, and both are visible in
the status tree:

| | API path | Typical GGA quality |
|---|---|---|
| **Pre-correction** | `status/gps/devices/{mdm_uid}/nmea` | `1` (GPS autonomous) |
| **Corrected** | `status/rtk/gnss/fix_sentence` | `2` / `4` / `5` (RTK) |

`status/gps/devices/{mdm_uid}` is the modem's own GNSS receiver output with no
RTCM corrections applied. `status/rtk/gnss` is the RTK engine solution after
the NTRIP RTCM stream has been applied; the same corrected position also
appears at `status/gps/fix` and in `status/gps/nmea`.

On a bench R2400 the two solutions sat about 5 m apart horizontally and 14 m
apart in altitude, which is the correction the NTRIP stream is applying.

The modem UID is discovered at runtime — the app picks the entry under
`status/gps/devices` that actually publishes a parseable GGA, and rechecks
every 30 seconds.

## Sample rate

Both solutions update at exactly **1 Hz** (measured: corrected 1.05 Hz, raw
1.00 Hz, with GGA UTC stamps advancing one per second), so the default
1-second interval already captures every fix. Each recorded row is keyed on
the GGA UTC stamps, so if the poll timer drifts onto a GNSS epoch that was
already written the repeat is skipped instead of duplicating a row. The count
of skipped repeats is shown on the Analytics page.

## Web UI

Reachable at `http://{router_lan_ip}:8000`.

> LAN clients need a firewall rule forwarding Primary LAN Zone → Router Zone
> for port 8000 (Security > Zone Firewall). Without it the page times out even
> though the app is running.

The header shows the app title with version, the router name
(`config/system/system_id`) and the NCOS version (`status/fw_info`).

**Live Map** — canvas-rendered Web Mercator map with an optional
OpenStreetMap basemap.

* Pre-correction points and their connecting track use one flat grey colour.
* Corrected points use the fix-quality colour, and each corrected track
  segment is drawn in the colour of the newer of its two endpoints, so the
  track changes colour wherever the fix quality changed.
* A dashed line links the newest pre/post pair to show the current offset.
* Scroll to zoom, drag to pan, click a point to inspect it, `Fit` to frame all
  points, `Follow` to keep the newest fix centred.

The basemap is the only thing fetched from the internet (by the *browser*, not
the router) and can be switched off; everything else is served from the app.

Colours run worst-to-best, and the legend shows the typical accuracy for each
level:

| GGA quality (field 6) | Label | Typical accuracy | Colour |
|---|---|---|---|
| 6 | Dead Reckoning | varies | blue |
| 1 | GPS (SPS) | 2–5 m | red |
| 2 | DGPS | 0.5–2 m | orange |
| 5 | RTK Float | 10–30 cm | yellow |
| 4 | RTK Fixed | 1–3 cm | green |

The legend runs worst fix to best, left to right, so it reads
**GPS → DGPS → RTK Float → RTK Fixed** with the best fix at the right-hand
end. Note that RTK Float is the lower quality despite having the higher code.
Dead reckoning is an estimated position rather than a point on that ladder, so
it leads the row instead of displacing RTK Fixed from the end.

Omitted levels:

* **0 (Invalid)** — no fix, so the GGA carries no latitude or longitude. The
  parser drops the sample before it could ever be plotted.
* **3 (PPS)** — military/authorised users only.
* **7 (Manual)** and **8 (Simulation)** — hand-entered or synthetic positions.

None of these occur on these routers. An unlisted code still records normally,
falling back to a neutral "Unknown" label and colour, and the legend grows an
"Unknown" swatch if one is ever actually plotted so no colour on the map is
left unexplained.

Badge text switches between black and white based on the background's relative
luminance, since the palette spans yellow and orange where fixed white text
falls below the 4.5:1 contrast threshold.

**RTK Fixed (4) is the goal.** RTK Float (5) means the carrier-phase
ambiguities are not fully resolved and the solution is still converging; that
normally takes 10–60 s depending on satellite visibility and baseline length.
The app records how long the corrected fix has held its current quality
(`post_quality_held_s`) and shows `converging` in the fix tile while the fix is
Float, with the full explanation on hover, so you know not to treat those
points as survey grade yet. Time held is also on the RTK Status page.

Fix quality and fix mode are deliberately **not** reported as a page banner.
They can change every second, so a banner for them appears and disappears
constantly and reflows the page. The tiles have reserved height and never
wrap, so they stay the same size as their contents change. The banner is
reserved for conditions that persist, and it debounces over several polls so a
single dropped NMEA checksum or a brief reconnect cannot flash it on and off.

The router's own `status/rtk/gnss/fix_quality` string is reported separately on
the RTK Status page rather than used as the label, so the pre and post columns
stay directly comparable. Note the router calls quality 2 `RTK_DIFFERENTIAL`
where the NMEA standard name is DGPS.

### Fix mode (2D vs 3D)

GGA carries only HDOP, so the app also parses the GSA sentence from both
streams for the fix mode and the full DOP set:

| GSA fix mode (field 2) | Meaning |
|---|---|
| 1 | No fix |
| 2 | 2D — latitude and longitude only, altitude unreliable |
| 3 | 3D — latitude, longitude and altitude |

HDOP, VDOP and PDOP are recorded for both solutions. The fix tile shows
`altitude unreliable` if the corrected solution drops to a 2D fix, since the
altitude column cannot be trusted in that state. Receivers emit one GSA per
constellation with identical DOP values, so the first usable sentence is used.

**RTK Status** — correction source state, caster host/port/mountpoint,
connection uptime, GGA uplink rate and failures, RTCM frame/byte counters,
dropped frames, CRC failures, correction age, MQTT state, RTCM message types
seen, the configured NTRIP profile, and the raw GGA sentences from both
solutions.

**Analytics** — offset min/mean/max/last (horizontal and vertical), fix
quality distribution for both solutions, and scatter statistics about the mean
position (sigma east/north, DRMS, 2DRMS, CEP50, max radial error) for the
corrected and pre-correction point sets. The scatter figures are a precision
measure; the offset figures show what the corrections changed.

**Recent Samples** — the 200 newest in-memory samples in a table. This table
stays in metres so the numeric columns remain scannable; units are in the
column headers.

Distances below 1 m are displayed in centimetres everywhere else, since RTK
offsets, accuracies and scatter figures routinely land in the 1–30 cm range
where `0.17 m` reads worse than `17 cm`. The conversion keeps the precision the
server sent rather than padding or truncating digits, so `0.17 m` becomes
`17 cm` and `0.004 m` becomes `0.4 cm`. The map scale bar switches between
centimetres, metres and kilometres the same way. CSV output is always in metres.

Buttons for **Download CSV** and **Clear History** appear on both the Live Map
and Recent Samples pages. Clearing empties the in-memory history and resets
today's recording file, then starts recording again into it.

## CSV output

Recordings are written to the `data/` subdirectory of the app, named:

```
RTK Compare - HOSTNAME - MM-DD-YYYY.csv
```

`HOSTNAME` is the router name from `config/system/system_id`, and the date is
the day the recording **started**.

**File selection happens when a recording starts, not while it runs:**

* A recording starts when the app starts and again when you clear the history.
* If no file exists for today, a new one is created with a header row.
* If a file for today already exists, it is continued — the app appends rather
  than creating a second file for the same day.
* The active file is never re-evaluated mid-run, so a recording that crosses
  midnight keeps writing to the file it started in. Nothing is interrupted and
  no file is rolled over at 00:00. A multi-day continuous run therefore lands
  in one file named for the day it began.

There is **no size cap** — the file grows for as long as the recording runs.
At 1 Hz that is roughly 20 MB per day, so keep an eye on router storage for
long unattended runs.

One row per GNSS epoch, with these columns:

```
seq, timestamp_local, timestamp_epoch, utc_offset,
pre_lat, pre_lon, pre_alt_m, pre_quality, pre_quality_label,
pre_satellites, pre_fix_mode, pre_fix_mode_label,
pre_hdop, pre_vdop, pre_pdop,
post_lat, post_lon, post_alt_m, post_quality, post_quality_label,
post_satellites, post_fix_mode, post_fix_mode_label,
post_hdop, post_vdop, post_pdop,
delta_horizontal_m, delta_vertical_m, delta_east_m, delta_north_m,
delta_bearing_deg, delta_3d_m,
rtk_fix_quality, rtk_diff_age_s, rtk_ref_station_id,
rtk_correction_state, rtk_correction_uptime_s, rtk_correction_age_s,
rtk_frames_total, rtk_frames_dropped, rtk_frames_queued,
rtk_bytes_received, rtk_crc_failures, rtk_gga_send_failures,
rtk_mqtt_connected,
horizontal_accuracy_m, vertical_accuracy_m, speed_accuracy_m_s,
reported_accuracy_m, speed_kph, heading_deg, post_quality_held_s
```

Coordinates are written with 8 decimal places. Offsets are computed in a local
east/north frame using a latitude-corrected metres-per-degree conversion.
Accuracy estimates come from the `$PCPTMINR` sentence in `status/gps/nmea`.

The active filename is shown on the Live Map page and on the Analytics page,
and the Download CSV button serves the active file under that same name.

`data/` is excluded from the app package via `buildignore`. It has to be,
because the router deletes an app whose packaged files have been modified, and
the app appends to these files at runtime.

## Appdata fields

All optional. None are written back to appdata, so NCM group configs are never
overridden.

| Field | Default | Description |
|---|---|---|
| `rtk_compare_port` | `8000` | Web UI TCP port |
| `rtk_compare_interval` | `1.0` | Sample interval in seconds (0.5–60) |
| `rtk_compare_max_points` | `7200` | In-memory samples kept for the map and analytics (60–100000) |

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/status` | Latest sample, RTK status and derived statistics |
| GET | `/api/points?since=N` | Compact history tuples newer than sequence `N` |
| GET | `/api/info` | Router name, model, NCOS version, app version, NTRIP profile, colour legend |
| GET | `/api/legend` | Fix-quality colour legend only |
| GET | `/api/history.csv` | Download the active recording under its on-disk name |
| GET | `/api/help` | This readme |
| POST | `/api/clear` | Reset today's recording file and the in-memory history |

## Requirements

* NCOS 7.26 or later with RTK support. `status/rtk` and `config/system/rtk`
  are `null` on models without it — the app logs a warning and keeps recording
  pre-correction positions only.
* RTK configured and enabled (`config/system/rtk`). Configure the NTRIP caster
  in the NCOS UI; this app only reads RTK settings, it never writes them.
* GPS enabled (`config/system/gps/enabled`).

## Notes

* Memory guard: available RAM is checked every 60 s. Below 20 % the in-memory
  history cap is halved; below 10 % the app sends an NCM alert and exits so the
  router restarts it cleanly.
* The NTRIP password is never read or returned by any endpoint.
