# NTP_GPS

A stratum-1 NTP server whose time comes from the router's GPS instead of its system clock.
NTP requests are answered on **UDP port 1123** (all interfaces) with reference ID `GPS`.

## How it works

**Primary source: the GNSS daemon socket** (`127.0.0.1:17488`). After the `ALL` command, gnssd streams,
each GPS second:

- the `RMC` sentence, giving the true UTC second and fix validity;
- `$PCPTMDBG,UTC Time Tag <fix_uptime> system time <sys_uptime>`, the daemon's own uptime value
  for that fix and its clock reading when it emitted the line.

The daemon's uptime clock and the app's `time.monotonic()` are both `CLOCK_MONOTONIC` with a
fixed offset, measured as `monotonic_at_arrival - sys_uptime` on each line. That converts
`fix_uptime` to the app's clock and removes the socket transport delay exactly — no guessing.
`fix_uptime` still trails the true GPS-second epoch by a fixed receiver+daemon fix latency
(`ntp_gps_fix_latency_ms`, see below), which is subtracted.

**Fallback: `status/gps/nmea` polling** every 0.2 s, if the socket is unavailable. NCOS
publishes that array about 0.7 to 1.0 s after the GPS second, with a drifting delay, and its
RMC/ZDA are one second older than GGA/GLL. The app retries the socket every 60 s.

Each GPS second gives one offset sample against the monotonic clock. The socket samples cluster
tightly, so the median of the last 30 is what NTP replies are built from. (The fallback uses the
largest offset, the least-delayed poll.)

- **No GPS fix yet**: replies carry LI=3 (alarm) and stratum 16, so clients reject them.
- **GPS lost after sync**: the server keeps answering from the monotonic clock for the holdover
  period (default 300 s), with root dispersion growing over time, then reports unsynchronized.
- Time is only taken from epochs whose RMC status is `A` (valid).

Every 60 s the app logs the source in use, sample count, dispersion, the router system clock's
offset from GPS time, and the number of requests served.

## Accuracy

Measured on an R2400 (NCOS 7.26.100) from a LAN host synced to time.apple.com, the server read
within **±3 ms of true time**, consistently (several rounds of −0.6 to −2.3 ms, run-to-run
spread 2–4 ms), with reported dispersion around 10 ms. A PPS-disciplined server is still better;
the limit here is the receiver+daemon fix latency and its stability, not GPS.

On the status-tree fallback, expect a few hundred ms.

Two caveats on the absolute figure:

- The `±3 ms` is relative to a reference (time.apple.com via a Mac) that is itself only good to
  about ±90 ms absolute. The *stability* is real; the absolute zero point is only as good as
  that reference, because it is baked into `ntp_gps_fix_latency_ms`.
- `ntp_gps_fix_latency_ms` (default 141) is the one calibrated constant, measured on one R2400
  and firmware. A different model, firmware, or antenna may shift it. To recalibrate, query the
  app from a LAN host with a well-synced clock (see Testing): if the app reads ahead of that
  host, lower the value by that amount; if behind, raise it.

The "system clock offset" in the log is the router's own SNTP error, measured about 0.8 s here;
it is not the app's error.

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

## SDK Appdata

All fields are optional. Defaults are applied in code.

| Name | Required | Default | Description |
|---|---|---|---|
| `ntp_gps_port` | No | `1123` | UDP port the NTP server listens on |
| `ntp_gps_holdover` | No | `300` | Seconds to keep serving time after GPS samples stop |
| `ntp_gps_fix_latency_ms` | No | `141` | Receiver+daemon fix latency: how far the GNSS daemon's fix timestamp trails the true GPS second. Subtracted from the served time. Calibrate per hardware (see Accuracy) |

## Security

NTP is unauthenticated. Any host that can reach the port can query it. Replies are the same size
as requests (48 bytes) and only client-mode packets are answered, so the server cannot be used
for traffic amplification. The GNSS socket is local-only (`127.0.0.1`).

## Dependencies

Bundles `pynmeagps` 1.0.42, the newest release that supports Python 3.8 (cppython).
