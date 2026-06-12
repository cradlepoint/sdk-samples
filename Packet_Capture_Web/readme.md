# Packet Capture Web

Web interface for running and managing packet captures on Ericsson routers.  With streaming!

<img width="1596" height="846" alt="image" src="https://github.com/user-attachments/assets/84833d50-9d05-4d23-99e6-5209b52b5839" />
<img width="1596" height="846" alt="image" src="https://github.com/user-attachments/assets/92f2bee0-7c9e-49f9-971f-ad187f71d6d8" />



## Features

- **Two capture modes**: Stream (continuous) and Download (time/count limited)
- **Stream mode**: Captures continuously to a single growing pcap file until stopped or disk threshold is reached. Uses `requests` with chunked streaming via the tcpdump REST API
- **Download mode**: Captures with a timeout and/or packet count, saves the completed pcap file
- **Interface selection**: WAN devices, WAN profiles, LAN networks (by UUID), WLAN (with SSID and frequency), and VLAN interfaces
- **BPF filter arguments**: Specify tcpdump-style filter expressions (e.g. `dst port 80`)
- **Disk utilization monitoring**: Live meter showing % used with tooltip for raw bytes. Configurable threshold to auto-stop capture
- **NCM Alert**: Optional alert sent to NCM when disk threshold is reached (one-shot, resets when below threshold)
- **File management**: List, rename (inline edit), download, and delete saved .pcap files
- **Options recall**: View saved capture options for any file and re-apply them
- **Dark mode**: Toggle between light and dark themes
- **Filenames**: Auto-generated as `{router_name}_{YYYYMMDD_HHMMSS}.pcap`

## Capture Modes

| Mode | Description |
|------|-------------|
| Stream | Streams packets continuously to one file. Stops on user click or disk threshold. Uses `requests.get(stream=True)` with chunked transfer |
| Download | Captures for a set timeout (seconds) or packet count, then saves the complete file |

## Interface Types

| Type | Source | Value sent to tcpdump |
|------|--------|----------------------|
| WAN devices | `status/wan/devices/*/info/iface` | Linux iface name (e.g. `rmnet501`) |
| WAN profiles | `config/wan/rules2` | Rule `_id_` |
| LAN networks | `config/lan` | Network UUID (e.g. `00000000-0d93-319d-8220-4a1fb0372b51`) |
| WLAN | `status/lan/devices/wlan-*` | Linux iface name (e.g. `ath00`) |
| Ethernet LAN | `status/lan/devices/ethernet-*` | Linux iface name |

## Usage

1. Access the web UI at `http://<router-ip>:8000`
2. Select mode (Stream or Download)
3. Choose interface and optional BPF filter
4. For Stream: set disk threshold % and optionally enable Alert
5. For Download: set timeout and/or packet count
6. Click **Start** to begin capturing
7. Click **Stop** to end (Stream mode) or wait for timeout/count (Download mode)
8. Navigate to **Saved Files** to manage captures

## Technical Details

- Packet capture uses the router's tcpdump REST API (`GET /api/tcpdump/{filename}.pcap?params`)
- A temporary user (SDKTCPDUMP) is created for HTTP Basic Auth, then deleted after capture
- Auth propagation delay is handled with retry logic (up to 5 attempts)
- Stream mode uses `requests.get(stream=True)` with `iter_content()` for real-time chunked writes
- Download mode uses `urllib.request.urlopen()` with a timeout guard

## Web Port

Default port: **8000**

## Appdata Fields

None required. The app runs with no configuration needed.

## Requirements

- Firmware 7.24+
- Zone forwarding from Primary LAN Zone to Router Zone for LAN client access
- `requests` library (pre-installed on cppython)
