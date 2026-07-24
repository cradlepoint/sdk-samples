# iPerf3 Web UI

A web-based interface for running iPerf3 bandwidth tests from a Cradlepoint router. Supports both client and server modes with full option control, live results display, persistent test history, and CSV/HTML export.

<img width="1559" height="844" alt="image" src="https://github.com/user-attachments/assets/3271184f-deac-43ae-ad7e-834d697b354f" />
<img width="1559" height="844" alt="image" src="https://github.com/user-attachments/assets/94de844d-af7c-4bd6-b8a3-c36deebf24b1" />
<img width="1559" height="844" alt="image" src="https://github.com/user-attachments/assets/b368c072-3da6-4b3c-90ca-cf3bdab90022" />


## How It Works

1. On startup, the app launches a web server on port 8000
2. Browse to `http://<router_ip>:8000` to access the UI
3. Select Client or Server mode and configure options
4. Click "Run Test" (client) or "Start Server" (server) to begin
5. Results display in real-time with summary cards (client mode)
6. All completed client tests are saved to history on disk

## Web Interface

### Run Test Tab

**Mode Selection** — Client or Server

**Client Mode Options:**
- Host and port of the remote iPerf3 server
- Protocol: TCP, UDP, or SCTP
- Direction: Upload, Download (-R), or Bidirectional (--bidir)
- Duration, parallel streams, report interval
- Target bandwidth, window size, buffer length
- MSS, ToS/DSCP, TCP no-delay, zero-copy, omit first second

**Server Mode:**
- Listen port and bind address
- Runs continuously until manually stopped (accepts multiple client connections)

**Results Panel:**
- Summary cards showing download, upload, jitter, and packet loss
- Raw output console with auto-scroll

### History Tab
- Table of all completed tests with timestamp, mode, server, protocol, direction, transfer, bandwidth, and duration
- **Export CSV** — download all history as a CSV file
- **Export HTML Report** — download a styled HTML report with bandwidth statistics (average, min, max)
- **Clear History** — remove all saved history

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve the web UI |
| `/api/start` | POST | Start an iPerf3 test (JSON body with options) |
| `/api/stop` | POST | Stop a running test or server |
| `/api/status` | GET | Get current test status and output |
| `/api/history` | GET | Get all test history |
| `/api/history/clear` | POST | Clear all history |
| `/api/export/csv` | GET | Download history as CSV |
| `/api/export/html` | GET | Download history as HTML report |

## Requirements

- Router firmware 7.26 or later
- An iPerf3 server reachable from the router (for client mode)
- Network connectivity on port 5201 (default) to the iPerf3 server
- LAN zone forwarding to Router zone for port 8000 (for LAN client access to the web UI)

## Notes

- The bundled binary (`iperf3-arm64v8`) is for ARM64 routers — compatible with all current Cradlepoint models
- History is stored in `tmp/iperf3_history.json` (up to 500 entries)
- Only one test/server instance can run at a time
- Web server binds to all interfaces on port 8000
- Client tests use JSON output mode (`-J`) internally for result parsing
- Server mode streams raw text output (no JSON) for readability
- Server output buffer is capped at 50KB to prevent memory issues on long-running servers
- Dark mode toggle persists via localStorage
