# Packet Capture (tcpdump) API

## Overview

The router exposes a tcpdump-based packet capture API. Captures are started via a blocking
HTTP GET that streams pcap data in chunked encoding. Captures are stopped via the control API.

## Start Capture

```
GET /api/tcpdump/{filename}.pcap?iface={iface}&args={filter}&timeout={sec}&count={pkts}&wifichannel=&wifichannelwidth=&wifiextrachannel=&url=
```

**Parameters:**
- `iface` — interface device name (`any`, `primarylan1`, `rmnet501`, `wan`, etc.)
- `args` — BPF filter string (empty = all traffic)
- `timeout` — seconds until capture ends (0 = unlimited)
- `count` — packet limit (0 = unlimited)
- `wifichannel` — Wi-Fi channel number (for monitor mode captures)
- `wifichannelwidth` — channel width (for monitor mode captures)
- `wifiextrachannel` — extra channel (for monitor mode captures)
- `url` — purpose unclear, does NOT trigger callbacks to external URLs

**Behavior:**
- Returns HTTP 200 with `Content-Type: application/vnd.tcpdump.pcap`
- `Transfer-Encoding: chunked` — pcap data streams in real-time as packets arrive
- Blocks until capture completes (timeout/count) or is stopped
- Filename MUST end in `.pcap` — other extensions return `{"success": true, "data": null}`
- Standard libpcap format: magic `0xa1b2c3d4`, version 2.4, snaplen 262144, linktype 1 (Ethernet)

**SDK usage:**
```python
import http.client
import ssl
import struct

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

conn = http.client.HTTPSConnection("192.168.3.10", context=ctx)
conn.request("GET", "/api/tcpdump/cap.pcap?iface=primarylan1&args=&timeout=30&count=0&wifichannel=&wifichannelwidth=&wifiextrachannel=&url=",
             headers={"Authorization": "Basic ..."})
resp = conn.getresponse()

# Read 24-byte pcap global header
pcap_hdr = resp.read(24)

# Read packets (16-byte header + data each)
while True:
    pkt_hdr = resp.read(16)
    if len(pkt_hdr) < 16:
        break  # stream ended
    ts_sec, ts_usec, incl_len, orig_len = struct.unpack('<IIII', pkt_hdr)
    pkt_data = resp.read(incl_len)
    # Parse Ethernet/IP/TCP/UDP headers from pkt_data...
```

## Check Status

```
GET /api/status/tcpdump
```

**When running:**
```json
{
  "running": {"pid": 14397, "args": ["tcpdump", "-nUi", "primarylan1", "", "-w", "-"], "returncode": null},
  "interface": "primarylan1",
  "args": "",
  "count": 0,
  "timeout": 1781114939.17,
  "kwargs": {"wifichannel": "", "wifichannelwidth": "", "wifiextrachannel": "", "iface_uid": "primarylan1", "timeout_duration": 60}
}
```

**When fully stopped:**
```json
{"running": {}, "interface": null, "args": null}
```

**Key indicator:** `interface: null` = fully stopped. `interface` set to a value = capture active or draining.

**Note:** The `running` dict may be `{}` even while a capture is active — use `interface` field as the reliable indicator.

## Stop Capture

```
PUT /api/control/system/tcpdump
Body (form-encoded): data={"stop":true}
```

Returns: `{"success": true, "data": {"stop": true}}`

**Critical behaviors:**
- Stop takes a few seconds to fully take effect in `status/tcpdump`
- The HTTP chunked stream may continue delivering buffered packets after stop
- The app MUST close its own HTTP connection after confirming stop
- Client disconnect (closing the GET connection) does NOT stop the capture — explicit stop is required

## Interface Discovery

Use these APIs to populate the capture interface dropdown:

- `GET /api/status/wan/devices` — WAN interfaces (cellular, ethernet-wan, sdwan)
  - Interface name: `device['info']['iface']` (e.g. `rmnet501`, `wan`)
  - Description: `device['info']['model']` or `device['info']['product']`
  - Active check: `device['status']['connection_state'] == 'connected'`
- `GET /api/status/lan/devices` — LAN interfaces
  - Interface name: `device['info']['iface']` (e.g. `primarylan1`)
  - Active check: `device['status']['link_state'] == 'up'`
- `GET /api/status/wlan` — Wi-Fi radios (for monitor mode captures)
  - Radio band: `radio['band']` (e.g. `"2.4 GHz"`, `"5 GHz"`)
  - Available channels: `radio['channel_list']` (array of integers)
  - Monitor interfaces: `mon0` (2.4 GHz), `mon1` (5 GHz)

## Wi-Fi Monitor Mode

For Wi-Fi captures, use `mon0` or `mon1` as the interface and set `wifichannel` to the desired channel.
After capture, disable monitor mode: `PUT /api/control/wlan/monitor_mode` with body `data=false`.

**Monitor mode state:**
- **The tcpdump API automatically enables monitor mode** when a capture is started on a `mon` interface — no separate enable step is needed. Just start the capture on `mon0` or `mon1` and the router handles the transition internally
- **Enable (manual):** `PUT /api/control/wlan/monitor_mode` with body `data=true` — but this is NOT needed for captures; the tcpdump endpoint does it automatically
- **Disable:** `PUT /api/control/wlan/monitor_mode` with body `data=false` — this works reliably and immediately restores AP mode
- **Check state:** `GET /api/control/wlan/monitor_mode` — `true` = monitor mode active, `false` = AP mode
- **Check operational state:** `GET /api/status/wlan/state` — returns `"Monitor"` when active, `"On"` when in AP mode
- **KNOWN ISSUE:** Standalone REST `PUT control/wlan/monitor_mode = true` may not reliably enable monitor mode outside of a capture context. The tcpdump endpoint is the reliable way to trigger it
- **`wifichannel` and `wifichannelwidth` can be empty** — the router auto-selects channel if not specified
- **`config/wlan/radio/{i}/mode`** — does NOT reflect monitor mode during captures. Stays `"ap"` during active monitor captures. For persistent mode configuration only
- **`control/wlan/monitor`** — a separate field; do NOT use for enabling/disabling monitor mode
- Radios MUST be enabled (`config/wlan/radio/{i}/enabled = true`) before monitor mode can activate
- **NCOS built-in UI also leaves monitor mode active after capture** — the router's own packet capture UI enables monitor mode for Wi-Fi captures and does NOT automatically restore AP mode when the capture ends
