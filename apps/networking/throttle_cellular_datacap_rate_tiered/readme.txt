App Name:
throttle_cellular_datacap_rate_tiered

Requirements, Assumptions & Behavior:
This SDK works in conjunction with Connection Manager Data Usage threshold(s)
specifically configured on Modem profiles (does not pertain to Ethernet or
WWAN profiles).  Upon *any* Modem interface reaching 70, 80, 90 or 100% of the
monthly data capacity limit, manual QoS will be enabled globally and bandwidth
throttling will be enforced on ALL Modem profiles to the configured limit as
set by the rate tier (minbwup and minbwdown variables).

Each of the rate tiers have a default throttling limit set below:
70% - 6000Kbps Tx/Rx
80% - 3000Kbps Tx/Rx
90% - 1500Kbps Tx/Rx
100% - 600Kbps Tx/Rx

If no alerts are configured for the above mentioned data capacity limits, the
SDK will not enforce rate shaping:
- Data Usage must be globally enabled
- Data cap alerts must be configured ('Alert on Cap' for 100% & 'Custom Alerts'
  with 70, 80 and 90% 'Alert Percentage' levels)

Upon the start of the next monthly cycle, NCOS will automatically clear the
monthly usage alert.  Once this happens, and if bandwidth throttling had been
enforced, rate shaping limits will be cleared and manual QoS will be disabled.

Note:
This SDK only monitors 70, 80, 90 and 100% monthly usage alerts of Modem
profiles.  It is agnostic to other data cap alerts that may also be configured
(e.g. setting weekly/daily alerts, monthly alerts at percentages not listed or
data usage alerts on non-Modem interfaces).