<img width="1454" height="845" alt="image" src="https://github.com/user-attachments/assets/dfe1c7e2-3b3b-476d-9b3d-58b8cb5b73d1" />

Gives your router accurate time from GPS, even with no internet. The app runs a stratum-1 NTP
server sourced from the router's GPS fix, so the router (and any LAN client) can keep its clock
set from GPS. It also provides a web dashboard where you can watch sync status and set the
router's clock by hand.

Cradlepoint routers have no battery-backed clock, so they boot thinking it is 1970 and rely on
NTP to learn the real time. This app is that time source when the only thing available is GPS.

## Features

- Stratum-1 NTP server sourced from GPS, answering on **UDP port 1123**.
- Web dashboard at **http://router_ip:8123** showing full sync status and the router's current
  clock. A **Local / UTC switch** at the top (defaults to Local) sets the timezone for every
  timestamp on the page, so you never have to reconcile mixed zones. "Local" is the router's own
  configured timezone.
- A **Set Router Clock** panel with three sources in one place — set from **GPS**, from your
  **browser time**, or from a **manually** picked date/time — for correcting the clock before GPS
  has locked or whenever you want to set it by hand.
- Light/dark mode.

## Steps to Use

1. Make sure GPS is enabled on the router and the antenna has a clear view of the sky.
2. Install and start the app. It starts serving the dashboard immediately and opens the NTP port
   as soon as GPS locks.
3. Point the router's NTP client at the app: NTP server `127.0.0.1`, port `1123`
   (Administration > System > Time, or `config/system/ntp`). The router's clock is then
   disciplined to GPS.
4. Open **http://router_ip:8123** to watch status and, if needed, set the clock manually.

### Setting the clock from the web UI

The dashboard's **Set Router Clock** panel is useful when the router clock is still at 1970 and
you want it correct right away, or when there is no GPS and no NTP at all. Pick one of three
sources:

- **Set from GPS** sends the app's current GPS-derived UTC time to the router. Available only
  once GPS has locked (the button shows the GPS time and is disabled until then).
- **Set from browser time** sends your computer's current time (as UTC) to the router. The
  router applies its own configured timezone for local display, so this is correct regardless of
  where you are.
- **Set manually** sends whatever you pick in the calendar/clock field, interpreted in your
  browser's local timezone.

All three use the router's `control/system/clock/set_time` endpoint. When GPS is synced you
normally do not need them — the router gets its time over NTP automatically.

## Status

The app publishes its current state to `status/ntp_gps`, continuously, starting from the moment
it launches (so you can see it progress through `waiting` before GPS locks). Read it with
`GET /api/status/ntp_gps/` or `cp.get('status/ntp_gps')`.

| Field | Description |
|---|---|
| `state` | `waiting` (no fix yet), `synced`, `holdover`, `unsynced`, or `stopped` |
| `synced` | `true` when serving GPS-derived time |
| `serving` | `true` once the NTP port is open |
| `source` | Active time source path, or `none` before the first sample |
| `sentence` | NMEA sentence the latest time came from, e.g. `GPGGA`, `GNRMC` |
| `samples` | Offset samples in the current window (up to 30) |
| `sample_age_s` | Seconds since the last GPS sample, or `null` |
| `dispersion_ms` | Reported root dispersion, milliseconds |
| `holdover_s` | Configured holdover window |
| `ntp_requests` | NTP requests served since startup |
| `ntp_port` | UDP port the NTP server is listening on |
| `tz_offset` | Router timezone as a numeric UTC offset (e.g. `-0700`) |
| `gps_unix` | Current GPS-derived time as Unix epoch seconds, or `null` when unsynced |
| `utc_time` | GPS time formatted as a UTC string, or `null` |
| `local_time` | GPS time in the router's timezone, with numeric offset (e.g. `-0700`) |
| `router_unix` | The router's own system clock, Unix epoch seconds |
| `router_utc` | The router's clock formatted as a UTC string |
| `router_local` | The router's clock in its own timezone, with numeric offset |
| `system_offset_s` | Router system clock minus GPS time, seconds (`null` when unsynced) |
| `ntp_last_server` | Where the router last synced its own clock (from `status/system/ntp`) |
| `ntp_sync_age_s` | Seconds since the router last synced its clock, or `null` |
| `updated` | Unix epoch seconds when this object was published |

## Settings (SDK Appdata)

All fields are optional. Defaults are applied in code.

| Field | Required | Default | Description |
|---|---|---|---|
| `ntp_gps_port` | No | `1123` | UDP port the NTP server listens on |
| `ntp_gps_holdover` | No | `300` | Seconds to keep serving time after GPS samples stop |

The web UI picks port `8123`; if that is in use it tries `8133`, `8143`, ... up to `8223`. The
chosen port is logged at startup.

## How it works

The app reads the router's GPS time from `status/gps/nmea` and serves it as NTP. This source
behaves the same on every router model (R1900, R2400, and others).

- **No GPS fix yet**: the NTP port stays closed and the status shows `waiting`. The port is held
  closed on purpose — a router without a clock may poll NTP only once at boot, and an early
  "unsynchronized" reply would be discarded and not retried for a long time. Keeping the port
  closed until GPS locks means that poll simply goes unanswered and the client retries normally.
- **GPS lost after sync**: the server keeps serving time for a holdover period (default 300 s),
  then reports itself unsynchronized so clients stop trusting it.

Accuracy is roughly a few hundred milliseconds — coarser than a PPS-disciplined server, but it
works on every model with no per-hardware setup, and is far better than a clock with no time
source at all.

## Technical details

- NTP replies are RFC 5905 server-mode packets (stratum 1, refid `GPS`).
- Setting the router clock uses `control/system/clock/set_time` (a Unix epoch).
- Status lives in RAM at `status/ntp_gps` and is cleared to a `stopped` object on shutdown.
- Bundles `pynmeagps` 1.0.42, the newest release that supports Python 3.8 (cppython).
- The web server overrides `server_bind` to skip the router's FQDN lookup, avoiding the IDNA
  error that otherwise prevents `http.server` from starting on some router hostnames.
