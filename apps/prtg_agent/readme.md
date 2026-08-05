# PRTG Agent

Collects system monitoring data and modem signal diagnostics from a Cradlepoint router and pushes it to a PRTG Network Monitor server using the HTTP Push Data Advanced sensor.

## Features

- Collects CPU, memory, uptime, temperature, and modem signal data (including 5G metrics)
- Pushes data as XML to PRTG HTTP Push Data Advanced sensor via POST
- Configurable collection paths with wildcard support
- Web UI for managing settings, viewing collected data, and triggering manual pushes
- All configuration persisted in SDK appdata (survives reboots, manageable from NCM)

## PRTG Setup

1. In PRTG, add an **HTTP Push Data Advanced** sensor to the desired device
2. Note the **Identification Token** and **Port** from the sensor settings
3. Configure the sensor to accept POST requests
4. Set "No Incoming Data" behavior as desired (e.g. switch to down after X minutes)

## Router Setup

1. Install the app on the router
2. Open the web UI at `http://<router-ip>:8000`
3. Navigate to **PRTG Server** and enter:
   - Protocol (http or https)
   - Server address (IP or hostname of your PRTG probe)
   - Port (default 5050)
   - Identification Token
   - Push interval in seconds
4. Save settings

## Web UI

Access at `http://<router-ip>:8000`

- **Status** — View agent state, push count, last push time. Trigger manual push
- **PRTG Server** — Configure server connection details and interval
- **Data Paths** — Add/remove/reset the NCOS API paths to collect. Supports `*` wildcard for one path segment
- **Preview** — View collected channels and the raw XML payload before sending

## Appdata Fields

| Field | Description | Default |
|-------|-------------|---------|
| `server` | PRTG probe IP or hostname | *(empty — required)* |
| `port` | PRTG sensor port | `5050` |
| `token` | Sensor identification token | *(empty — required)* |
| `interval` | Push interval in seconds | `60` |
| `protocol` | `http` or `https` | `http` |
| `paths` | JSON array of NCOS API paths to collect | See defaults below |

## Default Collection Paths

```
status/system/cpu
status/system/load_avg
status/system/memory/memtotal
status/system/memory/memfree
status/system/memory/memavailable
status/system/uptime
status/system/temperature
status/wan/devices/*/diagnostics/CARRID
status/wan/devices/*/diagnostics/DBM
status/wan/devices/*/diagnostics/RSRP
status/wan/devices/*/diagnostics/RSRQ
status/wan/devices/*/diagnostics/SINR
status/wan/devices/*/diagnostics/RSRP_5G
status/wan/devices/*/diagnostics/RSRQ_5G
status/wan/devices/*/diagnostics/SINR_5G
status/wan/devices/*/diagnostics/SS
status/wan/devices/*/diagnostics/RFBAND
status/wan/devices/*/diagnostics/SRVC_TYPE
status/wan/devices/*/diagnostics/MODEMTEMP
status/wan/devices/*/status/connection_state
status/wan/devices/*/status/signal_strength
status/speedtest
```

## Special Value Parsing

Some paths return values that aren't plain numbers. These are parsed into numeric channels automatically:

- `status/system/cpu` — `{user, nice, system}` fields are summed into a single `cpu` channel (e.g. `0.23`)
- `status/wan/devices/*/diagnostics/RFBAND` — the band number is extracted from strings like `"Band 66"` -> `66`
- `status/speedtest` — parsed into separate `speedtest dl`, `speedtest ul`, `speedtest latency`, and `speedtest jitter` channels (Mbps / ms) from a status string like `"DL:74.91Mbps UL:46.4Mbps Lat:81.39ms Jit:7.84ms Iface:T-Mobile Engine:netperf ..."`
- `status/wan/devices/*/status/connection_state` — mapped to `1` if `"connected"`, `0` if `"connecting"` or `"disconnected"`. Any other state is skipped rather than guessed at

Any path that resolves but still can't produce a numeric value (e.g. `CARRID`, `SRVC_TYPE`) is shown in the Preview tab under "Skipped Paths" so it's clear why it isn't sent to PRTG.

## Wildcard Paths

Use `*` to match any single path segment. For example:

- `status/wan/devices/*/diagnostics/RSRP_5G` — collects RSRP_5G from all modem devices
- `status/wan/devices/*/status/signal_strength` — collects signal strength from all WAN devices

The wildcard resolves against the actual device IDs present on the router (e.g. `mdm-abcd1234`).

## PRTG Channel Mapping

Each collected numeric value becomes a PRTG channel. Units are auto-detected:

| Pattern | PRTG Unit |
|---------|-----------|
| CPU / load | CPU (%) |
| Memory fields | BytesFile |
| Temperature | Temperature |
| Uptime | TimeSeconds |
| Signal strength / SS | Percent |
| RSRP, DBM | Custom (dBm) |
| RSRQ, SINR | Custom (dB) |

Non-numeric values (e.g. carrier name, service type, connection state) are skipped since PRTG channels require numeric data.

## Notes

- The app does NOT push data until both `server` and `token` are configured
- Maximum 50 channels per PRTG sensor — keep your path list within this limit
- Float values (e.g. SINR "23.4") are sent with `<float>1</float>` so PRTG handles them correctly
- The push uses HTTP POST with `Content-Type: application/xml`
