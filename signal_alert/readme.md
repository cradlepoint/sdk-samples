# signal_alert

Monitors modem signal metrics on all connected modems and sends NetCloud alerts with GPS when any metric goes below its threshold. Sends one alert when signal crosses below and one when it recovers (after 60 seconds above threshold).

## Requirements

- **GPS antenna** optional; lat/long is included in alerts when available. App works without GPS.

## Appdata (SDK app settings)

Configure in the router UI under the SDK app settings or in NetCloud Manager.

| Field | Description | Default |
|-------|-------------|---------|
| `signal_metrics` | Comma-separated list of metric names to monitor (e.g. `RSRP`, `RSRQ`, `SINR`). Only modems that report these diagnostics are checked. | `RSRP,RSRQ` |
| `RSRP` | Threshold (dBm). Alert when modem RSRP is below this. | `-111` |
| `RSRQ` | Threshold (dB). Alert when modem RSRQ is below this. | `-12` |

For any other metric listed in `signal_metrics`, add an appdata field with the same name as the threshold. If that field is missing, that metric is not monitored (and a log message is written). RSRP and RSRQ use the defaults above when their appdata fields are not set.

## Behavior

- Discovers connected modems that report at least one of the configured metrics.
- Each loop: reads thresholds from appdata; for each modem, compares each configured metric to its threshold.
- **Below:** When a monitored metric goes below its threshold, sends one alert for that metric (e.g. *"AT&T RSRP -68 is below threshold of -60."*). One alert per metric per crossing.
- **Recovery:** When a metric that was below goes above its threshold and stays above for 60 seconds, sends one recovery alert for that metric (e.g. *"AT&T RSRP recovered: -95 (above threshold of -111)."*). One recovery alert per metric that recovers.
- Alerts include lat/long when GPS is available.
- Logs when thresholds or monitored metrics change.

## Example output

```
Starting...
Found modems: ['mdm-b194c176']
AT&T RSRP -115 is below threshold of -111. Lat/long: 34.05, -118.25
AT&T RSRQ -14 is below threshold of -12. Lat/long: 34.05, -118.25
AT&T RSRP recovered: -95 (above threshold of -111). Lat/long: 34.05, -118.25
AT&T RSRQ recovered: -8 (above threshold of -12). Lat/long: 34.05, -118.25
```
