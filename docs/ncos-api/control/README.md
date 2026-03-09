# control/ - NCOS Control API

<!-- path: control -->
<!-- type: control -->

Actions and commands. **PUT values to trigger actions.** GET returns current structure/state. Most leaf values are `null` until written.

[NCOS API Documentation](../) / control

---

## Overview

| Operation | REST | SDK |
|-----------|------|-----|
| Read (structure) | `GET /api/control/{path}` | `cp.get('control/{path}')` |
| Trigger action | `PUT /api/control/{path}` | `cp.put('control/{path}', value)` |

**Note:** Many control paths accept `PUT` with a value to trigger an action (e.g. `cp.put('control/system/reboot', 1)`). The exact value varies by endpoint.

## Top-Level Branches

| Path | Description |
|------|-------------|
| [control/system](system.md) | Reboot, factory reset, clock, tcpdump, apps, SDK |
| [control/wan](wan.md) | reset_stats, devices, steering |
| [control/gpio](gpio.md) | GPIO pin read/write (0/1) |
| [control/wlan](wlan.md) | enable, kick_mac, block_macs, radio inhibit |
| [control/ping](ping.md) | Start/stop ping, results |
| [control/routing](routing.md) | static route/table add/del, suppression |
| [control/ecm](ecm.md) | register, start, stop, restart |
| control/lan | reset_stats, wired_8021x authorize |
| control/firewall | conntrack flush, hitcounter reset |
| control/log | clear, message |
| control/recover | clear |
| control/gre | start/stop GRE tunnels |
| control/vpn | start/stop VPN tunnels |
| control/hotspot | clearList, revoke |
| control/gps | start, stop |
| control/container | app start/stop/restart |
| control/ob_upgrade | OTA firmware check/update |
| control/dns | cache clear |
| control/flowstats | ipdst enable, sample_period |
| control/license | keys enable/disable, update |
| control/remote_modem | force upgrades, clear metrics |
| control/security | IPS action, update |
| control/stats | client_usage clear |
| control/traceroute | start/stop traceroute |
| control/sdwan_adv | user_mode_driver, wan_bonding |
| control/testmode | AT modem test |
| control/dnsmonitor | DNS monitoring controls |
| control/ethernet | mirror |
| control/certmgmt | CA, CSR |
| control/gre_netmanager | reset_stats, devices |
| control/vti_netmanager | reset_stats |
| control/openvpn_netmanager | reset_stats, devices |
| control/qos | override |
| control/iot | bluetooth, mqtt, msft |
| control/webfilter | debug |
| control/netperf | run tests |
| control/vti | tunnel controls |
| control/app | per-app action |
| control/csterm | console |
| control/opennhrp | flush, vpn_connect/disconnect |
| control/discovery | process_msg |
| control/net_health | force_report |
| control/cdp | collection |
| control/netflow | ulog, data |
| control/vpn | IPSec start/stop |

## Common Patterns

### Trigger reboot
```python
cp.put('control/system/reboot', 1)
```

### Enable/disable WLAN
```python
cp.put('control/wlan/enable', True)
```

### Set GPIO output
```python
cp.put('control/gpio/LED_SS_0', 1)  # on
cp.put('control/gpio/LED_SS_0', 0)  # off
```

### Start ping
```python
cp.put('control/ping/start', {'host': '8.8.8.8', 'num': 4})
```

## Access

```bash
GET /api/control/
GET /api/control/system
PUT /api/control/system/reboot  # body: 1
```

```python
import cp
struct = cp.get('control/system')
cp.put('control/system/reboot', 1)
```

## Related

- [status/](../status/README.md) - Read-only status
- [config/](../config/README.md) - Persistent configuration
