Failover Modem Reset
===========================

Monitors all modem SIM slots and detects failover from sim1 to sim2. Logs all SIM status changes and resets the sim2 device after failover.

## SDK Appdata Fields

| Field | Default | Description |
|-------|---------|-------------|
| reboot_hour | 2 | Hour (0-23) when modem reset should occur after failover is detected |
| reboot_timer | (not set) | Minutes after sim2 connects to wait before resetting modem. Overrides reboot_hour if set |

## How It Works

1. On startup, logs the status of all modem devices with SIMs (skips NOSIM slots)
2. If sim2 is already connected on startup, immediately starts the reset timer
3. Polls WAN device status every 3 seconds
4. Logs all `status.summary` changes on SIM devices (e.g., connected, available, disconnected)
5. Detects when sim2 connects on the same port (physical modem) as sim1
6. If `reboot_timer` is set, resets the sim2 device after that many minutes
7. Otherwise, resets the sim2 device at `reboot_hour` (default 2am)
