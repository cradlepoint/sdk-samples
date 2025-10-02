# WAN Rate Tracker

Tracks WAN bandwidth rates over time and stores rolling averages in a configurable field.

> [Download the built app here!](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/wan_rate.v1.0.0.tar.gz)

## What it does

- Samples WAN inbound (ibps) and outbound (obps) rates at regular intervals
- Maintains a rolling buffer of recent samples
- Calculates averages from collected samples
- Stores average rates in JSON format to a configurable system field

## Appdata Configuration

- `wan_rate_poll_interval` (default: 10) - Seconds between samples
- `wan_rate_buffer_size` (default: 30) - Number of samples to keep
- `wan_rate_report_interval` (default: 300) - Seconds between field updates
- `wan_rate_output_path` (default: `/config/system/asset_id`) - Where to store results

## Output Format

Human-readable format with Unicode arrows:
```
↓ 1250.8 Kbps, ↑ 890.3 Kbps
```
