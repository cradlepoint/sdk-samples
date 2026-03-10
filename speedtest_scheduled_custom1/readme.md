# speedtest_scheduled_custom1

Runs Ookla speedtests on a cron schedule and writes results to the NCM `custom1` field.

## Appdata Fields

| Name | Default | Description |
|------|---------|-------------|
| `schedule` | `0 12 * * *` | Cron expression (see examples below). Defaults to daily at 12:00 if missing or invalid. |
| `ncm_keys` | `{}` | NCM API v2 keys as JSON (see below). |
| `custom2` | (none) | If this field exists (any value), results are written to `custom2` instead of `custom1`. |

## Schedule Examples

Cron format: `minute hour day month weekday`

| Schedule | Expression | Description |
|----------|------------|-------------|
| Daily at noon | `0 12 * * *` | Once per day at 12:00 PM |
| Twice daily | `0 9,16 * * *` | 9:00 AM and 4:00 PM every day |
| Business hours | `0 8,12,17 * * *` | 8 AM, noon, and 5 PM every day |
| Every 6 hours | `0 */6 * * *` | 12 AM, 6 AM, 12 PM, 6 PM |
| Hourly | `0 * * * *` | Top of every hour |
| Weekly Monday | `0 12 * * 1` | Mondays at noon |
| Weekdays only | `0 12 * * 1-5` | Noon on Monday-Friday |
| First of month | `0 9 1 * *` | 9 AM on the 1st of each month |

## NCM API Keys

The app checks for encrypted keys stored in router certmgmt first (via the [NCM API Key Encryptor](https://github.com/cradlepoint/api-samples/tree/master/scripts/ncm_api_key_encryptor)), then falls back to the `ncm_keys` appdata field.

To use appdata, set `ncm_keys` to:

```json
{"X-CP-API-ID":"...","X-CP-API-KEY":"...","X-ECM-API-ID":"...","X-ECM-API-KEY":"..."}
```

## Result Format

```
12.34Mbps Down / 5.67Mbps Up / 23ms
```
