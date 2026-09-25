# Mobile Site Survey v3
Professional cellular network drive testing application with modern web interface and high-performance speed testing.

Light Side:
![image](https://github.com/user-attachments/assets/712a198b-4930-49f9-9e6a-0c6acb1ae96b)

Dark Side:
![image](https://github.com/user-attachments/assets/117ce0fd-7389-48cd-a995-3dfc0e619d40)

## Key Features

### 🚀 **Speedtest Engines**
Choose in the web UI under **Test Options → Speedtest Engine**. Which binaries
are bundled is fixed when the app is packaged, so the app detects them once at
startup and **the dropdown only lists engines it can actually run** — Ookla does
not appear unless a binary is present. As shipped that means **Netperf** and
**iPerf3**, with Netperf the default.

| Engine | Needs | Notes |
|---|---|---|
| **Ookla** | your own licensed binary | There is **no Ookla license for SDK apps**, so no binary is bundled or distributed with this app and it is never required. If you have your own license, add `ookla`, `speedtest` or `speedtest-cli` to the app directory before packaging; it then appears in the dropdown and becomes the default. The only engine that produces a results image URL. Pinned to each WAN with `-i <wan_ip>`. |
| **Netperf** | nothing | Built into NCOS and driven through `cp.speed_test()`, with latency and jitter from netperf's own TCP_RR test. No server, no binary, no configuration. Pinned to each WAN through its `ifc_wan` option, so **no source routing is added to the router config**. netperf cannot run concurrent tests — it is a single shared router resource — so modems are measured one at a time and a multi-modem survey takes proportionally longer. |
| **iPerf3** | your own iperf3 server | Uses the bundled `iperf3-arm64v8` binary. Pinned to each WAN with `-B <wan_ip>` plus `--bind-dev <iface>`, falling back to `-B` alone where `--bind-dev` is not permitted. The only engine whose test parameters are configurable — see **iPerf3 test options** below. Latency and jitter are derived from the TCP round-trip stats iperf3 reports for the sending side. |

**iPerf3 test options** — selecting the iPerf3 engine reveals a **Test Options**
group. Each field maps to one iperf3 flag and is passed straight through to the
binary, so anything the flag does, it does here. Blank or zero means "leave it to
iperf3". Values are range checked before the command is built, so a bad entry is
logged and ignored rather than breaking the test.

| Option | Flag | Default | Notes |
|---|---|---|---|
| Protocol | `-u` when UDP | TCP | See the UDP note below |
| Duration | `-t` | `10` | Seconds **per direction**, so a test takes roughly twice this. Ignored when Size is set |
| Streams | `-P` | `1` | Parallel connections. More streams fill a high-latency link that a single TCP flow cannot |
| Bandwidth | `-b` | blank | Target rate **per stream**, e.g. `50M`. Blank is unlimited for TCP. Caps data use on a metered SIM |
| Size | `-n` | blank | Transfer a fixed volume, e.g. `100M`, instead of testing for a fixed time. Overrides Duration. A size-limited run has no time bound, so it gets a 300-second safety timeout per direction |
| Buffer | `-l` | blank | Read/write block size, e.g. `128K`. For UDP this is the datagram size — keep it under the path MTU to avoid fragmentation |
| Window | `-w` | blank | Socket buffer / TCP window, e.g. `512K`. Blank lets the kernel autotune |
| Omit | `-O` | `0` | Seconds discarded from the start of each direction, so TCP slow start does not drag the average down |
| No Delay | `-N` | off | Disables Nagle. TCP only |
| Zero Copy | `-Z` | off | `sendfile()` instead of copying through userspace, which lowers router CPU on fast links. TCP only |

Sizes accept a plain byte count or a `K`, `M` or `G` suffix, matching iperf3.

**iPerf3 and UDP** — UDP changes what can be measured. There are no TCP
round-trip stats, so **Latency is left empty**, but iperf3 reports jitter and
datagram loss directly and those are used instead: jitter lands in the `Jitter`
column and loss is written to the router log per test. Throughput is taken from
the receiving side in both directions, so it reflects datagrams that actually
arrived. One thing to watch: **iperf3 caps an unrestricted UDP test at
1 Mbit/s**, which reads as a terrible link rather than a missing setting, so set
a Bandwidth target whenever you select UDP. The app logs a warning if you do not.
`-N` and `-Z` are TCP-only and are dropped automatically for UDP.

**iPerf3 servers** — the dropdown is pre-populated with LeaseWeb's public
iperf3 servers ([list and terms](https://kb.leaseweb.com/kb/network/network-link-speeds/)),
grouped by region, and **Custom server…** lets you enter your own hostname or IP.
These are third-party servers offered as a convenience; for repeatable survey
numbers, run your own iperf3 server close to the area being tested.

**The LeaseWeb presets are TCP only.** Selecting UDP against one fails with
`unable to read from stream socket: Resource temporarily unavailable`, which is
the server declining UDP rather than a fault on the router. UDP needs an iperf3
server you control, started plainly as `iperf3 -s` so it accepts both.

**Use your own server for UDP.** A survey measures download then upload
back-to-back on the same reserved port, which most public servers cannot serve.
`iperf.he.net` accepts UDP but runs one test at a time on a single port, so the
download succeeds and the upload comes back `the server is busy running a test`
with nothing to fall through to. A plain `iperf3 -s` of your own handles the
pattern fine, and a port range lets concurrent modems through as well.

**iPerf3 port ranges** — surveys test every connected modem at the same time, so
each test needs its own port. With a range such as `5201-5210` each modem
reserves a free port, and a port that is busy or errors falls through to the next
one in the range. A single port still works; concurrent modem tests just queue.
LeaseWeb's servers accept `5201-5210` and allow only one connection per port,
which is exactly the case the fall-through handles.

- Real-time download/upload measurements
- Optimized for cellular network testing scenarios

### 🎨 **Professional Web UI**
- Modern, responsive interface with real-time updates
- Live survey status indicators and GPS lock monitoring
- Tabbed configuration interface for easy setup
- Real-time results display with 24-hour timestamp format

### 📊 **Comprehensive Testing**
- **Distance-based testing** - Automatic tests when moving specified distances
- **Time-based testing** - Scheduled tests at regular intervals
- **GPS location tracking** - Precise coordinate logging with accuracy metrics
- **Cellular diagnostics** - Signal strength, carrier info, and network details
- **Packet loss monitoring** - Continuous connectivity testing between surveys

### 🔧 **Advanced Configuration**
- **Multi-interface testing** - Cellular, Ethernet, and WiFi-as-WAN support
- **CSV data export** - Results saved to router flash storage
- **Server integration** - Powered by 5g-ready.io for cloud data collection
- **Multi-router coordination** - Synchronized testing across multiple devices

## Quick Start

1. **Access Web Interface** - Navigate to the router's IP on the port the app logged (8000 by default)
2. **Configure Settings** - Set distance/time intervals and testing options
3. **Run Survey** - Click "Run Survey Now" for manual testing or enable automatic testing
4. **View Results** - Real-time results display with professional formatting

### Web Interface Port

The web interface starts on **port 8000**. If 8000 is already in use, the app
walks up through **8001-8100** and binds the first free port. If every port in
that range is taken, the app logs an error and exits.

The chosen port is always written to the router log at startup:

```text
Web interface available on port 8000
```

Check the log (or `make.py deploy` output) to see which port was used before
browsing to the router. LAN clients also need a firewall zone forward from the
Primary LAN Zone to the Router Zone to reach the app's port.

Note: surveyor coordination (`enable_surveyors`) contacts peer routers on port
**8000** only, so peers that fell back to another port will not be triggered.

## Requirements

- Cellular modem with GPS antenna
- GPS lock for location-based testing
- An iperf3 server, only if you select the iPerf3 engine
- No speedtest binary or license is required

## Default Configuration

- **Distance testing**: Every 50 meters
- **Speed testing**: Enabled, using the netperf engine built into NCOS
- **Data export**: CSV files saved to router flash
- **Server integration**: Ready for 5g-ready.io cloud platform

## Configuration (appdata `Mobile_Site_Survey`)

All settings live in a single JSON value under `config/system/sdk/appdata` with
the name `Mobile_Site_Survey`, and every one of them is editable from the web UI.
None are required — anything missing falls back to the code default.

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `true` | Run distance-based tests |
| `min_distance` | int | `50` | Meters between distance-based tests |
| `enable_timer` | bool | `false` | Run time-based tests |
| `min_time` | int | `0` | Seconds between timed tests |
| `all_wans` | bool | `false` | Also test Ethernet and WiFi-as-WAN, not just modems |
| `speedtests` | bool | `true` | Run speedtests |
| `speedtest_engine` | str | best available | `netperf`, `iperf3`, or `ookla` if a binary is bundled. An engine whose binary is absent falls back to `netperf` |
| `iperf3_server` | str | `""` | iPerf3 server hostname or IP. Required when `speedtest_engine` is `iperf3`. The UI offers the LeaseWeb public servers or a custom entry |
| `iperf3_ports` | str | `5201-5210` | iPerf3 port or port range, e.g. `5201` or `5201-5210` |
| `iperf3_protocol` | str | `tcp` | `tcp` or `udp` (`-u`) |
| `iperf3_duration` | int | `10` | Seconds per direction (`-t`), 1-300. Ignored when `iperf3_bytes` is set |
| `iperf3_parallel` | int | `1` | Parallel streams (`-P`), 1-128 |
| `iperf3_bandwidth` | str | `""` | Target rate per stream (`-b`), e.g. `50M`. Blank is unlimited for TCP |
| `iperf3_bytes` | str | `""` | Transfer a fixed volume (`-n`) instead of a timed test, e.g. `100M` |
| `iperf3_buffer_length` | str | `""` | Read/write buffer length (`-l`), e.g. `128K` |
| `iperf3_omit` | int | `0` | Seconds discarded from the start of each direction (`-O`), 0-60 |
| `iperf3_window` | str | `""` | Socket buffer / TCP window size (`-w`), e.g. `512K` |
| `iperf3_no_delay` | bool | `false` | Disable Nagle (`-N`). TCP only |
| `iperf3_zero_copy` | bool | `false` | Use `sendfile()` (`-Z`). TCP only |
| `packet_loss` | bool | `true` | Continuous ping monitoring between surveys |
| `write_csv` | bool | `true` | Write results to CSV in `results/` |
| `full_diagnostics` | bool | `false` | Write every diagnostics field to CSV |
| `dead_reckoning` | bool | `false` | Use dead-reckoning position |
| `debug` | bool | `false` | Verbose logging |
| `send_to_server` | bool | `false` | POST results to `server_url` |
| `server_url` | str | `https://5g-ready.io/injector` | Results collection endpoint |
| `server_token` | str | `""` | Bearer token for `server_url` |
| `include_logs` | bool | `false` | Attach app logs to the POST payload |
| `enable_surveyors` | bool | `false` | Trigger surveys on peer routers |
| `surveyors` | list | `[]` | Peer router IP addresses |

Every `iperf3_*` field is ignored unless `speedtest_engine` is `iperf3`.

The older combined `speedtest_url` field (`host:start-end`) is migrated
automatically into `iperf3_server` and `iperf3_ports` on first run and removed.

## Results

CSV files are written to `results/` and downloadable from the web UI. Columns:

```text
Timestamp, Lat, Long, Accuracy, Carrier, Download, Upload, Latency, Jitter,
Packet Loss Percent, bytes_sent, bytes_received, Results Image, Engine, Server,
<diagnostics...>
```

`Engine` records which engine measured the row, so a CSV that spans an engine
change stays interpretable. `Server` is the target that was measured against —
`host:port` for iPerf3, the selected server for Ookla, and **blank for netperf**,
which picks its own server internally. Neither field is sent to `server_url`.

`Latency` and `Jitter` are both in milliseconds, and every engine measures them
itself: netperf from a TCP_RR test (`RT_LATENCY` and `STDDEV_LATENCY`), Ookla
from its ping stage, iPerf3 from the TCP round-trip times it reports for the
sending side. A cell is left empty if the engine could not measure it — most
often with **iPerf3 over UDP**, which has no round-trip stats, so `Latency` is
blank while `Jitter` is still filled in from UDP's own measurement.
`Results Image` is only populated by the Ookla engine.

The payload sent to `server_url` is unchanged from v3.2 — jitter is a
CSV-and-UI-only field.

---

*Professional cellular network testing made simple with modern web interface and high-performance binary speed testing.*
