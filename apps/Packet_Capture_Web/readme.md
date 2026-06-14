# Packet Capture Web

![Python](https://img.shields.io/badge/Python-3.8-yellow) ![Web App](https://img.shields.io/badge/Interface-Web_App-blue)

Web interface for running and managing packet captures on Cradlepoint routers. Designed for **automated, unattended packet capture** — configure once, enable Auto Start, and the router captures traffic on every boot until disk is full, with NCM alerts when it stops.

![image](https://github.com/user-attachments/assets/b641c856-4dea-45a4-87ad-cd4a36d62e22)
![image](https://github.com/user-attachments/assets/0b254edb-463e-4249-a34d-c6c46eabe57c)

## Automated Capture

The primary use case: deploy to a router, save your capture settings, enable Auto Start, and walk away. The app will:

1. **Start capturing automatically on every boot** using saved defaults
2. **Stream continuously** to a single pcap file, growing until the disk threshold is reached
3. **Send an NCM alert** when the disk threshold stops the capture
4. **Survive reboots** — settings persist in appdata (config), captures persist on flash

Push settings to a fleet via NCM group appdata to enable automated capture across hundreds of routers simultaneously.

## Features

- **Two capture modes**: Stream (continuous) and Download (time/count limited)
- **Stream mode**: Captures continuously to a single growing pcap file until stopped or disk threshold is reached
- **Download mode**: Captures with a timeout and/or packet count, saves the completed file
- **Auto Start**: Begin capturing on boot using saved defaults — no user interaction required
- **Save/Load Defaults**: Persist capture settings in appdata. Push via NCM to configure remotely
- **Disk utilization monitoring**: Live meter with configurable threshold to auto-stop capture
- **NCM Alert**: Notification when disk threshold stops a capture (one-shot, auto-resets)
- **Interface selection**: WAN devices, WAN profiles, LAN networks, WLAN (with SSID/frequency), VLANs
- **BPF filter arguments**: tcpdump-style filter expressions (e.g. `dst port 80`)
- **Packet count**: Each file shows packet count in the file list (with K/M abbreviations)
- **Stop reason tracking**: Every capture records why it stopped (disk full, user, interrupted)
- **File management**: Rename, download, delete, view options/stop reason from the browser
- **Dark mode**: Light/dark theme toggle

## Capture Modes

| Mode | Description |
|------|-------------|
| Stream | Streams packets continuously to one file via `requests.get(stream=True)`. Stops on user click or disk threshold |
| Download | Captures for a set timeout (seconds) or packet count. Blocks until complete, then saves |

## Interface Types

| Type | Source | Value sent to tcpdump |
|------|--------|----------------------|
| WAN devices | `status/wan/devices/*/info/iface` | Linux iface name |
| WAN profiles | `config/wan/rules2` | Rule `_id_` |
| LAN networks | `config/lan` | Network UUID |
| WLAN | `status/lan/devices/wlan-*` | Linux iface name |
| Ethernet LAN | `status/lan/devices/ethernet-*` | Linux iface name |

## Usage

### Manual Capture

1. Access `http://<router-ip>:8000`
2. Select mode, interface, and filter
3. Click **Start** → **Stop** when done
4. Download from **Saved Files**

### Automated Capture (recommended)

1. Access `http://<router-ip>:8000`
2. Select **Stream** mode, choose interface
3. Set disk threshold (e.g. 80%) and check **Send Alert**
4. Click **Save Defaults** then **Auto Start** (turns green)
5. Reboot router — capture starts automatically on every boot

### NCM Fleet Deployment

Push the `pcap_defaults` appdata field via NCM group config to enable automated capture across all routers in a group without touching each one.

## Buttons

| Button | Function |
|--------|----------|
| Start | Begin capture with current settings |
| Stop | Stop a running capture |
| Auto Start | Toggle auto-start on boot (green = ON) |
| Save Defaults | Save current form settings to appdata |
| Load Defaults | Restore saved settings into the form |

## Technical Details

- Uses the router's tcpdump REST API with chunked `Transfer-Encoding` streaming
- Temporary user (SDKTCPDUMP) created for HTTP Basic Auth per capture session
- Stale capture flush before each stream to prevent empty-response issues
- Disk check before any capture setup (won't start if already over threshold)
- Disk checked every ~100KB during streaming
- Packet count computed after capture and cached in metadata
- Existing files without packet count are backfilled on app startup

## Appdata Fields

| Field | Description |
|-------|-------------|
| `pcap_defaults` | JSON string with capture settings, auto_start flag, and interface config |

## Web Port

Default port: **8000**

## Requirements

- Firmware 7.24+
- Zone forwarding from Primary LAN Zone to Router Zone for LAN client access
- `requests` library (pre-installed on cppython)
