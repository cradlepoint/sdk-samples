# throttle_cellular_datacap_rate_tiered

![Python](https://img.shields.io/badge/Python-3.8-yellow)

Works in conjunction with Connection Manager Data Usage thresholds configured on Modem profiles (does not pertain to Ethernet or WWAN profiles).

## Behavior

Upon *any* Modem interface reaching 70, 80, 90, or 100% of the monthly data capacity limit, manual QoS will be enabled globally and bandwidth throttling will be enforced on ALL Modem profiles to the configured limit as set by the rate tier (`minbwup` and `minbwdown` variables).

### Rate Tiers

| Threshold | Default Throttle |
|-----------|-----------------|
| 70% | 6000 Kbps Tx/Rx |
| 80% | 3000 Kbps Tx/Rx |
| 90% | 1500 Kbps Tx/Rx |
| 100% | 600 Kbps Tx/Rx |

Upon the start of the next monthly cycle, NCOS will automatically clear the monthly usage alert. Once this happens, rate shaping limits will be cleared and manual QoS will be disabled.

## Requirements

- Data Usage must be globally enabled
- Data cap alerts must be configured:
  - "Alert on Cap" for 100%
  - "Custom Alerts" with 70, 80, and 90% "Alert Percentage" levels

If no alerts are configured for the above mentioned data capacity limits, the SDK will not enforce rate shaping.

## Notes

This SDK only monitors 70, 80, 90, and 100% monthly usage alerts of Modem profiles. It is agnostic to other data cap alerts that may also be configured (e.g. setting weekly/daily alerts, monthly alerts at percentages not listed, or data usage alerts on non-Modem interfaces).
