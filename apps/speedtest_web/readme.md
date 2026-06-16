# speedtest_web
Web-based speed test interface with scheduling, history tracking, and report generation.

<img width="1519" height="841" alt="image" src="https://github.com/user-attachments/assets/ddbd71b3-e9d6-442d-94c1-5a1309be2be1" />
<img width="1519" height="841" alt="image" src="https://github.com/user-attachments/assets/8ebf23d5-4215-4f09-9d25-67759c148cb0" />
<img width="1519" height="841" alt="image" src="https://github.com/user-attachments/assets/54051101-c97a-43f8-bed0-f0637be0acba" />
<img width="1519" height="841" alt="image" src="https://github.com/user-attachments/assets/4edfcc2e-69e9-4e4a-ad60-1ff0d1663122" />


## Features

- **Multi-engine support**: Ookla (BYOB), Netperf (built-in), iPerf3
- **Live progress streaming**: Real-time bandwidth display in header bar during tests
- **Scheduled tests**: Cron-based scheduling with visual builder, presets, and custom expressions
- **Auto-start on boot**: Schedule resumes automatically after reboot
- **Header status bar**: Shows live test progress or countdown to next scheduled test
- **Test history**: Stores up to 100 test results with full test parameters
- **Per-engine stats**: Separate statistics and graphs for each engine type
- **Bar graphs**: Visual DL/UL bars for chronological test comparison
- **Failed test tracking**: Errors logged, zeros detected as failures
- **CSV/HTML reports**: Download reports with per-engine breakdowns and colored cards
- **Server management**: Save netperf and iPerf3 servers to SDK appdata (NCM pushable)
- **Port range retry**: iPerf3 tries next port in range if current one fails
- **Result outputs**: Write results to multiple NCOS fields simultaneously
- **Interface selection**: Auto-detects connected WANs sorted by priority with carrier names
- **Size limit**: Netperf supports data size limit in addition to time
- **TCP Latency/Jitter**: Optional TCP_RR measurement
- **Dark mode**: Toggle light/dark theme
- **Tab persistence**: Active tab survives page refresh

## Speed Test Engines

### Ookla (Bring Your Own Binary)
If an `ookla`, `speedtest`, or `speedtest-cli` binary is present in the app directory, it will
be detected and offered as the primary testing engine. You must have a valid Ookla license.
The app streams JSONL output in real-time for live progress updates.

### Netperf (Default)
Uses the router's built-in netperf service via `control/netperf`. No additional
software or server needed. Supports custom server host or auto-detect.
- TCP Download and Upload
- Optional TCP Latency/Jitter (TCP_RR)
- Size limit (MB) or time-based duration
- Per-interface testing via `ifc_wan`

### iPerf3
Requires a user-provided iPerf3 server address. Supports port ranges (e.g. 5201-5210)
for automatic retry on busy ports. Bundled `iperf3-arm64v8` binary included.
Also detects `iperf3` or `iperf3-aarch64` binary names.
- Source IP binding (`-B`) for per-interface testing
- Port range retry on connection failure

## Web Interface

Access at `http://<router_ip>:8000` from a device on the LAN.

**Note**: LAN access requires a firewall zone forwarding rule from the Primary LAN Zone
to the Router Zone.

## Tabs

### Run Tests
- Manual test execution with engine, interface, duration, size limit, latency options
- Schedule configuration with visual cron builder
- Schedule status showing all active test parameters

### History & Reports
- All Tests summary: avg/max/min stats + bar graph
- Per-engine breakdown: stats + graph for each engine type
- Test Log table with all parameters (time, engine, status, DL, UL, latency, jitter, interface, server, duration, size)
- CSV Report download (full history with all fields)
- HTML Report download (colored cards with per-engine sections)

### Servers
- Save/delete netperf servers (IP + label)
- Save/delete iPerf3 servers (host, port/range, city, country)
- All saved to SDK appdata (persists across reboots, pushable via NCM groups)

### Outputs
- Configure where results are written after each successful test
- Multiple outputs can be active simultaneously:
  - Description (`config/system/desc`)
  - Asset ID (`config/system/asset_id`)
  - SDK Data (`speedtest_results`)
  - Custom path

## Appdata Fields

All optional. Configuration is done through the web interface.

| Field | Description |
|-------|-------------|
| `speedtest_schedule` | JSON: `{enabled, autostart, cron, engine, params}` |
| `speedtest_outputs` | JSON array of output paths |
| `netperf_servers` | JSON array of `{server, label}` objects |
| `iperf3_servers` | JSON array of `{server, port, city, country}` objects |

## Output Format

Results written to configured outputs include datetime, speeds, interface/carrier:
```
DL:96.82Mbps UL:46.74Mbps Lat:12.5ms Jit:2.1ms Iface:T-Mobile Engine:netperf 2026-06-13T11:30:00Z
```

## Schedule Configuration

Three ways to set a schedule:
1. **Quick Presets**: Every 5/15/30 min, hourly, daily, weekly, weekdays
2. **Visual Builder**: Select repeat interval, hour, minute, day of week
3. **Custom Cron**: Enter raw cron expression (min hour dom month dow)

Options:
- **Enable Schedule**: Activate/deactivate without losing config
- **Auto-start on boot**: Schedule auto-enables on app startup

## History Entry Fields

Each test result stores: timestamp, engine, download_mbps, upload_mbps, latency_ms,
jitter_ms, interface, server, port, host, duration, size, include_latency, status, error

## Requirements

- Firmware 7.25+
- For Ookla: Place licensed `ookla` or `speedtest` binary (ARM64) in app directory
- For iPerf3: Bundled binary included, or place your own `iperf3` or `iperf3-arm64v8`
