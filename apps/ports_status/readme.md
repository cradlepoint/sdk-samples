# ports_status
Sets the device description field to a visual summary of port and connection status using color-coded emoji indicators. Provides a quick at-a-glance view of WAN, LAN, Modem, WWAN, and IP Verify status in NCM.

## How It Works

The app polls router status every 5 seconds and builds a string showing the state of each interface:
- Checks ethernet WAN connections
- Checks all LAN port link states
- Checks modem connection status
- Checks WWAN (WiFi as WAN) status
- Checks IP Verify test results

The resulting string is written to `config/system/desc` (the device description field visible in NCM).

## Status Indicators

| Indicator | Meaning |
|-----------|---------|
| 🟢 | Connected / Active / Up / Pass |
| 🟡 | Available / Standby / Connecting |
| ⚫️ | Down / Offline / Fail |

## Sample Output

```
WAN: 🟢 LAN: 🟢 ⚫️ ⚫️ ⚫️ ⚫️ 🟢 ⚫️ ⚫️ ⚫️ MDM: 🟡 MDM: ⚫️ IPV: 🟢
```

This shows:
- WAN ethernet is connected
- 2 of 8 LAN ports have devices connected
- First modem is in standby, second is offline
- IP Verify test is passing

## Behavior Notes

- Polls every 5 seconds
- Only writes to description when a change is detected (avoids unnecessary NCM syncs)
- Models without ethernet WAN (CBA, W18, W200, W400, L950, IBR200, 4250) skip the WAN indicator
- Each modem gets its own indicator (supports multi-modem routers)
- Each IP Verify test gets its own indicator

## Viewing in NCM

The description field is visible in the NCM Devices list, providing quick visual status without opening individual device pages.

## Requirements

- Router firmware 7.26 or later
- Works on all Cradlepoint router models (adapts to available interfaces)
