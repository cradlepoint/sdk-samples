# NTP_GPS

A stratum-1 NTP server whose time comes from the router's GPS instead of its system clock.
NTP requests are answered on **UDP port 1123** (all interfaces) with reference ID `GPS`.

## How it works

**Time source: `status/gps/nmea` polling** every 0.2 s. This is the one source used on all
router models (R1900, R2400, ...). The per-model GNSS daemon socket is deliberately not used:
its timing sentences differ by hardware (`$PCPTMDBG` on some, `$PCPTMINR` on others), so polling
the status tree is the only consistent source.

Each GPS second the app reads the NMEA array and takes the freshest UTC time from it — the date
from `RMC` (or `ZDA`), the time of day from the newest of `RMC`/`ZDA`/fix-valid `GGA`/`GLL`, since
`RMC`/`ZDA` in the status tree can lag `GGA` by one epoch. A change between two closely spaced
polls marks a new GPS second and yields one offset sample against the monotonic clock.

NCOS publishes the array a few tenths of a second after the GPS second, so a fixed
`STATUS_TREE_LATENCY` (0.8 s) is added to each sample. A polled sample can only ever arrive late,
so the largest offset in the last 30 is the least-delayed one, and that is what NTP replies are
built from.

- **No GPS fix yet**: replies carry LI=3 (alarm) and stratum 16, so clients reject them.
- **GPS lost after sync**: the server keeps answering from the monotonic clock for the holdover
  period (default 300 s), with root dispersion growing over time, then reports unsynchronized.
- Time is only taken from epochs whose RMC status is `A` (valid).

Every 60 s (and whenever sync is gained or lost) the app logs the source in use, sample count,
dispersion, the router system clock's offset from GPS time, and the number of requests served.
The same state is published to `status/ntp_gps` (see Status below).

## Accuracy

Expect roughly a few hundred milliseconds. The limit is the `status/gps/nmea` publish delay and
its drift, corrected by the fixed `STATUS_TREE_LATENCY` (0.8 s) constant and the least-delayed
sample selection. This is coarser than a PPS-disciplined server, but it is the same on every
model and needs no per-hardware calibration.

The "system clock offset" in the log is the router's own SNTP error; it is not the app's error.

**Do not point the router's own NTP client at this app** (`127.0.0.1:1123`) while
calibrating. The router clock then follows the app, and the offset line always reads near zero.

## Requirements

- GPS enabled and an antenna with a fix.
- For LAN clients to reach port 1123, the zone firewall needs a forwarding rule from the
  Primary LAN Zone to the Router Zone (`Security > Zone Firewall`).

## Testing

Most stock clients (macOS `sntp`, `ntpdate`) only query port 123. Point an NTP client that
supports a custom port (chrony: `server 192.168.0.1 port 1123 iburst`) at it, or use Python:

```bash
python3 -c "import socket,struct,time;s=socket.socket(2,2);s.settimeout(2);s.sendto(b'\x23'+b'\0'*47,('192.168.0.1',1123));d=s.recv(48);print('stratum',d[1],'time',time.ctime(struct.unpack('!I',d[40:44])[0]-2208988800))"
```

## Status

The app publishes its sync state to `status/ntp_gps`, updated whenever sync is gained or lost and
at least every 60 s. Read it with `GET /api/status/ntp_gps/` or `cp.get('status/ntp_gps')`. The
value lives in RAM only (not persisted across reboot); on shutdown it is overwritten with an
unsynced object rather than left stale.

| Field | Description |
|---|---|
| `synced` | `true` when the server is currently serving GPS-derived time |
| `source` | Active time source path: `status/gps/nmea`, or `none` before the first sample |
| `sentence` | Full NMEA id of the sentence the latest time came from, e.g. `GPGGA`, `GNRMC` (`null` before the first sample) |
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

## Security

NTP is unauthenticated. Any host that can reach the port can query it. Replies are the same size
as requests (48 bytes) and only client-mode packets are answered, so the server cannot be used
for traffic amplification.

## Dependencies

Bundles `pynmeagps` 1.0.42, the newest release that supports Python 3.8 (cppython).
