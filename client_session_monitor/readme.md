Client Session Monitor
=======================

Monitors client connections to specific domains by tracking firewall connection table entries. Logs session start/end times, duration, and bandwidth usage.

## Features

- Multi-domain monitoring with DNS resolution to track destination IPs
- Real-time connection tracking via firewall conntrack
- Session detection based on traffic activity timeout
- Client identification with hostname, MAC, network, and SSID
- Per-session bandwidth tracking (TX/RX bytes)
- Session logging to CSV file with automatic rotation
- Web dashboard with active sessions and history
- Downloadable CSV reports with router hostname and timestamp

## SDK Appdata Fields

- **monitored_domains** (string, default: "example.com") - Comma-separated list of domains/URLs to monitor
- **session_timeout** (integer, default: 60) - Seconds of inactivity before session ends
- **log_size_limit** (integer, default: 10485760) - Maximum CSV log file size in bytes (default 10MB)

## Usage

1. Install app on router
2. Access dashboard at http://ROUTER_IP:8000
3. Click gear icon to configure:
   - Add monitored domains (e.g., "netflix.com", "youtube.com", "cnn.com")
   - Set session timeout (seconds of inactivity before session ends)
4. Download session history as CSV from dashboard

## Dashboard

- **Active Sessions**: Real-time view of clients currently accessing monitored domains
- **Session History**: Last 100 completed sessions with timestamps and bandwidth
- **Settings**: Configure monitored domains and session timeout via gear icon
- **Download**: Export session history as CSV with filename format: `client-sessions_hostname_YYYYMMDD_HHMMSS.csv`
- Auto-refreshes every 3 seconds

## Notes

- Tracks sessions by MAC address to survive DHCP IP changes
- Resolves all IPs for domains to handle CDN/load balancer scenarios
- CSV file trims oldest rows when size limit is reached (default 10MB)
- Session history kept in memory (last 100 sessions)
