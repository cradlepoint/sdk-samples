# throttle_cellular_datacap

![Python](https://img.shields.io/badge/Python-3.8-yellow)

Works in conjunction with Connection Manager Data Usage thresholds configured on Modem profiles (does not pertain to Ethernet or WWAN profiles).

## Behavior

Upon *any* Modem interface reaching 100% of the monthly data capacity limit, manual QoS will be enabled globally and bandwidth throttling will be enforced on ALL Modem profiles to the configured limit (`minbwup` and `minbwdown` variables). The default throttling rate is 512Kbps (up/down).

Upon the start of the next monthly cycle, NCOS will automatically clear the monthly usage alert. Once this happens, rate shaping limits will be cleared and manual QoS will be disabled.

## Requirements

- Data Usage must be globally enabled
- Data cap alerts must be configured (i.e. "Alert on Cap") on the desired Modem profile

If "Alert on Cap" is not configured on the desired Modem profile, the SDK will not enforce rate shaping.

## Notes

This SDK only monitors 100% monthly usage alerts of Modem profiles. It is agnostic to other data cap alerts that may also be configured (e.g. setting weekly/daily alerts, monthly alerts at various percentages below 100%, or data usage alerts on non-Modem interfaces).
