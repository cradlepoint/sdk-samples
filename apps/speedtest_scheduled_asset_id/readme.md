# speedtest_scheduled_asset_id
Runs a netperf speedtest on a configurable cron schedule and writes results to the router's asset_id field. Can also be triggered manually by setting asset_id to "start".

## Result Format

```
DL: 26.8Mbps, UL: 12.5Mbps, Latency: 56ms, Carrier: Verizon, DBM: -74, SINR: 5.6, RSRP: -95, RSRQ: -11, 2024-03-15T14:30:00Z
```

Download speed, upload speed, latency, modem diagnostics, and ISO timestamp. Modem diagnostics (Carrier, DBM, SINR, RSRP, RSRQ) are only included if the primary WAN device is a modem. Timestamp is at the end so results can be sorted by download speed.

## Manual Trigger

Set the router's asset_id to "start" (case-insensitive) via NCM API or router UI to trigger an immediate speedtest. Results overwrite the "start" value when complete.

```
PUT https://www.cradlepointecm.com/api/v2/routers/{router_id}/
{"asset_id": "start"}
```

## Appdata Fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `cron_schedule` | No | `0 2 * * 1` | Cron expression (minute hour day month weekday). Changes are picked up within 15 seconds |

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
2. Reads `cron_schedule` from appdata every 15 seconds (uses default if not set)
3. Checks if the current time matches the cron schedule
4. Also checks if asset_id is set to "start" for manual triggering
5. When triggered, runs a netperf speedtest
6. Reads modem diagnostics (Carrier, DBM, SINR, RSRP, RSRQ) from the primary WAN device if it's a modem
7. Writes formatted results to `config/system/asset_id`

## Retrieving Results via NCM

The asset_id field is visible in NCM under Devices. It can also be read via the NCM API:

```
GET https://www.cradlepointecm.com/api/v2/routers/{router_id}/
```

The result is in the `asset_id` field of the response.
