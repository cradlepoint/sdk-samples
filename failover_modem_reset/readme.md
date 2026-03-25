Failover Modem Reset
===========================

Monitors all modem SIM slots and detects failover from sim1 to sim2. Logs all SIM status changes, sends an NCM alert on failover detection, and resets the sim2 device after failover. Supports multiple modems with independent failover tracking per port. Configuration changes via appdata are picked up automatically without restarting the app.

## SDK Appdata Fields

| Field | Default | Description |
|-------|---------|-------------|
| reboot_hour | 2 | Hour (0-23) when modem reset should occur after failover is detected |
| reboot_timer | (not set) | Minutes after sim2 connects to wait before resetting modem. Overrides reboot_hour if set |

## How It Works

1. On startup, logs the status of all modem devices with SIMs (skips NOSIM slots)
2. If any sim2 is already connected on startup, immediately starts the reset timer for that port
3. Polls WAN device status every 3 seconds
4. Logs all `status.summary` changes on SIM devices (e.g., connected, available, disconnected)
5. Detects when sim2 connects on any modem port and sends an NCM alert with device ID, port, carrier, and signal strength
6. Appdata fields (`reboot_timer`, `reboot_hour`) are re-read every cycle, so config changes take effect immediately
7. If `reboot_timer` is set, resets the sim2 device after that many minutes
8. Otherwise, resets the sim2 device at `reboot_hour` (default 2am)
9. Each modem port is tracked independently — multiple modems can fail over and reset on their own timers
