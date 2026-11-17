# serial_to_UDP

Reads data from the router's serial interface and forwards every chunk to one or more
remote hosts over UDP.

<img width="1686" height="845" alt="image" src="https://github.com/user-attachments/assets/2077fcd2-a94b-4f66-a780-6cfabf96edc0" />
<img width="1686" height="845" alt="image" src="https://github.com/user-attachments/assets/b66ded08-0a9a-4b07-97da-baa297d5f205" />

A web UI at `http://<router_ip>:<port>` configures both sides. The port is shown in the app
log and saved in the `serial_to_UDP_web_port` SDK Data field (usually 8000, or the next free
port if 8000 is taken).

- **UDP settings** (destinations and source address) are stored in SDK Data (appdata).
- **Serial port settings** are read from and written back to the **router config** at
  `config/system/serial`, not SDK Data.

Saving either page applies immediately. The app rebinds the UDP socket or reopens the
serial port on its own; no restart needed.

## UDP destinations

Add as many destinations as you need (up to 32). Each chunk read from the serial port is
sent as a separate datagram to every destination. A destination that is unreachable is
logged and skipped, and does not stop delivery to the others.

## UDP source

The source address defaults to the router's primary LAN address
(`config/lan/0/ip_address`) on port **5000**. Leave the source fields blank in the web UI
to use those defaults.

Defaults are resolved in code and are never written to appdata, so a blank source cannot
override values pushed from an NCM group config. The only value the app writes to appdata on
its own is the discovered web port (see below).

## Serial port settings

The Serial Port page pulls the current values from the router and writes changes back to
`config/system/serial`:

| Field | Config path |
| --- | --- |
| Serial Device | `serial_port` (`ttyUSB0` or `ttyACM0`) |
| Baud Rate | `baud_rate` (50 – 4000000) |
| Data Bits | `byte_size` (5 – 8) |
| Parity | `byte_parity` (0 None, 1 Even, 2 Odd, 3 Mark, 4 Space) |
| Stop Bits | `stop_bits` (0 = 1, 1 = 1.5, 2 = 2) |
| Hardware Flow Control | `flow_control/hardware` |
| Software Flow Control | `flow_control/software` |

Notes:

- The router rejects hardware and software flow control being enabled together. The UI
  clears one when you select the other, and the app also blocks the combination before
  writing.
- All fields are written in a single PUT so the router validates the change as a whole. A
  rejected change leaves the existing config untouched rather than half-applied.
- `config/system/serial/enabled` (the router's own telnet-style serial redirector service)
  is intentionally not exposed here. It is a separate service from this app's forwarding
  and running both against the same device can cause contention; leave it configured
  through the router's own UI/API if you need it.

## SDK Data (appdata)

Field name: `serial_to_UDP`, value is a single JSON object.

```json
{
  "destinations": [
    {"ip": "192.168.13.101", "port": 5000},
    {"ip": "192.168.13.102", "port": 5001}
  ],
  "udp_src_ip": "192.168.13.31",
  "udp_src_port": 12345
}
```

| Field | Required | Default |
| --- | --- | --- |
| `destinations` | yes | none — no data is forwarded until at least one is set |
| `udp_src_ip` | no | `config/lan/0/ip_address` |
| `udp_src_port` | no | `5000` |

The older single-destination format (`udp_dest_ip` / `udp_dest_port`) is still read and
treated as one destination, so existing installs keep working.

The web UI port is a separate SDK Data field:

| Field | Required | Description |
| --- | --- | --- |
| `serial_to_UDP_web_port` | no | Web UI port (1-65535). If set, the app uses exactly this port. If not set, it uses the first free port from 8000 and saves it here. Delete it to pick a port automatically again. |

The startup log shows the port, e.g. `Bound port 8001 (discovered, saved to
serial_to_UDP_web_port)` then `Web server started on port 8001`. To change it for one router
or a group, set `serial_to_UDP_web_port` in NCM SDK Data (device or group) and restart the
app. Delete the field and restart to go back to automatic selection. A configured port that
is busy is retried for about 10 seconds. If it is not a number from 1 to 65535, or stays
busy, the web UI does not start and the log says why, but serial to UDP forwarding keeps
running.

## Security note

The web UI and its JSON API on the app's web port have **no authentication**. Anyone who can reach
that port can change the UDP destinations and write to the router's serial configuration.
Only expose it on trusted networks, and keep the zone firewall rule scoped to the LAN
zones that need it.

## Requirements

- A serial device connected to the router (e.g. `/dev/ttyUSB0`)
- Network connectivity between the source and each destination
- LAN client access to the web UI requires a firewall zone forwarding rule from the
  Primary LAN Zone to the Router Zone (Security > Zone Firewall)

## Behavior

- Starts the web UI on its web port, then reads UDP settings from SDK Data and serial
  settings from the router config
- Opens the serial port and binds a UDP socket to the source address
- Reads up to 1024 bytes at a time and fans each read out to all destinations
- Reconnects automatically on serial errors and rebinds the socket on socket errors
- Keeps draining the serial port when no destinations are configured, logging a reminder
  at most once a minute, so the input buffer does not back up
- `GET /api/status` reports whether the port is open, bytes read, datagrams sent, send
  errors, and how long ago data last arrived. The Serial Port page shows this.
