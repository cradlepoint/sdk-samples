App Name:
throttle_cellular_datacap

Requirements, Assumptions & Behavior:
This SDK works in conjunction with Connection Manager Data Usage threshold(s)
specifically configured on Modem profiles (does not pertain to Ethernet or
WWAN profiles).  Upon *any* Modem interface reaching 100% of the monthly data
capacity limit, manual QoS will be enabled globally and bandwidth throttling
will be enforced on ALL Modem profiles to the configured limit (minbwup and
minbwdown variables).  The default throttling rate if reaching the data
capacity limit is 512Kbps (up/down).

If 'Alert on Cap' is not configured on the desired Modem profile, the SDK will
not enforce rate shaping.  The following are required:
- Data Usage must be globally enabled
- Data cap alerts must be configured (i.e. 'Alert on Cap')

Upon the start of the next monthly cycle, NCOS will automatically clear the
monthly usage alert.  Once this happens, and if bandwidth throttling had been
enforced, rate shaping limits will be cleared and manual QoS will be disabled.

Note:
This SDK only monitors 100% monthly usage alerts of Modem profiles.  It is
agnostic to other data cap alerts that may also be configured (e.g. setting
weekly/daily alerts, monthly alerts at various percentages below 100% or data
usage alerts on non-Modem interfaces).

