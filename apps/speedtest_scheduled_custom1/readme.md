# speedtest_scheduled_custom1
Runs a speedtest on a cron schedule and writes the result to the NCM `custom1` field. It uses the licensed Ookla binary if one is in the app folder, and the router's built-in netperf service otherwise. If an Ookla test fails, it falls back to netperf.

## Appdata Fields

| Name | Default | Description |
|------|---------|-------------|
| `schedule` | `0 12 * * *` | Cron expression (see examples below). Defaults to daily at 12:00 if the field is missing or does not have exactly five parts. A five-part expression with a bad value inside (for example `0 noon * * *`) logs a parse error and never runs. The field is read again every 30 seconds, so changes apply without a restart. |
| `ncm_keys` | `{}` | NCM API v2 keys as JSON (see below). |
| `custom2` | (none) | If this field exists (any value), results are written to `custom2` instead of `custom1`. |

## Schedule Examples

Cron format: `minute hour day month weekday`, evaluated in the router's local time.

Weekdays use standard cron numbering: `0` = Sunday, `1` = Monday, `2` = Tuesday, `3` = Wednesday, `4` = Thursday, `5` = Friday, `6` = Saturday. `7` is also accepted as Sunday.

Supported in each part: `*`, a single number, a comma list (`9,16`), a range (`1-5`), and a step on `*` (`*/6`). A step on a range (`1-5/2`) is not supported.


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

With the Ookla binary, the result includes ping:

```
12.34Mbps Down / 5.67Mbps Up / 23ms
```

With the built-in netperf service (a 10-second test in both directions), there is no ping value:

```
12.34Mbps Down / 5.67Mbps Up
```

If no NCM API keys are available, the test still runs and is logged, but the app skips the `custom1` update and logs that it did.
