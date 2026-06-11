# Packet Capture Web

Web interface for managing packet captures on Cradlepoint routers.

## Features

- **Capture modes**: Download, CloudShark, and Custom URL streaming
- **Interface selection**: Choose from available WAN/LAN interfaces or capture on all
- **BPF filter arguments**: Specify tcpdump-style filter expressions (e.g. `dst port 80`)
- **Timeout and count**: Set capture duration and packet limits
- **File management**: List, rename, download, and delete captured .pcap files
- **Options recall**: View and re-apply the options used for any saved capture
- **Dark mode**: Toggle between light and dark themes

## Capture Modes

| Mode | Description |
|------|-------------|
| Download | Streams the packet capture as a file download saved locally on the router |
| CloudShark | Streams the packet capture to CloudShark.org (requires API token) |
| Custom URL | Streams the capture via HTTP PUT to a custom server. Headers: `Transfer-Encoding: chunked`, `Content-Type: application/octet-stream` |

## Usage

1. Access the web UI at `http://<router-ip>:8000`
2. Select capture mode, interface, and options
3. Click **Start** to begin capturing
4. Click **Stop** to end early, or wait for timeout/count limit
5. Navigate to **Saved Files** to manage captures

## Web Port

Default port: **8000**

## Appdata Fields

None required. The app runs with no configuration needed.

## Requirements

- Firmware 7.24+
- Zone forwarding from Primary LAN Zone to Router Zone for LAN client access
