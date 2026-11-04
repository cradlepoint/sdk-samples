# NTP_GPS

Gives your router accurate time from GPS. The app runs a stratum-1 NTP server that gets its time
from the router's GPS fix, so you can point the router's own NTP client at it and keep the system
clock set from GPS, even with no internet.

NTP requests are answered on **UDP port 1123**.

## Setup

1. Make sure GPS is enabled and the antenna has a fix.
2. Install and start the app.
3. Point the router's NTP client at the app: set the NTP server to `127.0.0.1` on port `1123`.
   The router's clock will then be disciplined to GPS time.

That's it. The app logs its status and keeps the router's time synced to GPS as long as there's a
fix.

## How it works

The app reads the router's GPS time from `status/gps/nmea` and serves it as NTP. This source works
the same on every router model (R1900, R2400, and others).

- **No GPS fix yet**: the server reports itself unsynchronized, so the router keeps its previous
  time until GPS is ready.
- **GPS lost after sync**: the server keeps serving time for a holdover period (default 300 s),
  then reports itself unsynchronized.

## Accuracy

Expect roughly a few hundred milliseconds. This is coarser than a PPS-disciplined server, but it
works on every model with no per-hardware setup, and is far better than a drifting clock with no
time source at all.

## Status

The app publishes its current state to `status/ntp_gps`. Read it with `GET /api/status/ntp_gps/`
or `cp.get('status/ntp_gps')`.

| Field | Description |
|---|---|
| `synced` | `true` when the server is serving GPS-derived time |
| `source` | Active time source path, or `none` before the first sample |
| `sentence` | NMEA sentence the latest time came from, e.g. `GPGGA`, `GNRMC` |
| `samples` | Offset samples in the current window (up to 30) |
| `sample_age_s` | Seconds since the last GPS sample, or `null` |
| `dispersion_ms` | Reported root dispersion, milliseconds |
| `holdover_s` | Configured holdover window |
| `ntp_requests` | NTP requests served since startup |
| `ntp_port` | UDP port the server is listening on |
| `gps_unix` | Current GPS-derived time as Unix epoch seconds, or `null` when unsynced |
| `system_offset_s` | Router system clock minus GPS time, seconds (`null` when unsynced) |
| `updated` | Unix epoch seconds when this object was published |

## SDK Appdata

All fields are optional. Defaults are applied in code.

| Name | Required | Default | Description |
|---|---|---|---|
| `ntp_gps_port` | No | `1123` | UDP port the NTP server listens on |
| `ntp_gps_holdover` | No | `300` | Seconds to keep serving time after GPS samples stop |

## Dependencies

Bundles `pynmeagps` 1.0.42, the newest release that supports Python 3.8 (cppython).
