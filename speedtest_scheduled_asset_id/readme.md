# speedtest_scheduled_asset_id

Runs an Ookla speedtest on a configurable cron schedule and writes results to the router's asset_id field.

## Result Format

```
2024-03-15T14:30:00Z DL: 26.8Mbps, UL: 12.5Mbps, Latency: 56ms, DBM: -74, SINR: 5.6
```

ISO timestamp followed by download speed, upload speed, latency, and modem diagnostics. Modem diagnostics (DBM, SINR) are only included if the primary WAN device is a modem.

## Appdata Fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `cron_schedule` | No | `0 2 * * 1` | Cron expression (minute hour day month weekday) |

## Cron Expression Examples

| Expression | Description |
|-----------|-------------|
| `0 2 * * 1` | Weekly on Monday at 2:00 AM UTC (default) |
| `0 */4 * * *` | Every 4 hours |
| `*/30 * * * *` | Every 30 minutes |
| `0 8 * * *` | Daily at 8:00 AM UTC |
| `0 0 * * 1` | Weekly on Monday at midnight UTC |
| `0 */1 * * *` | Every hour |

## How It Works

1. App starts and waits for WAN connectivity
2. Reads `cron_schedule` from appdata (uses default if not set)
3. Checks every 15 seconds if the current time matches the cron schedule
4. When triggered, runs an Ookla speedtest
5. Reads modem diagnostics (DBM, SINR) from the primary WAN device if it's a modem
6. Writes formatted results to `config/system/asset_id`

## Retrieving Results via NCM

The asset_id field is visible in NCM under Devices. It can also be read via the NCM API:

```
GET https://www.cradlepointecm.com/api/v2/routers/{router_id}/
```

The result is in the `asset_id` field of the response.
