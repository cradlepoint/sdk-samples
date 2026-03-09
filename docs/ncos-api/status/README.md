# status/ - NCOS Status API

Runtime status information. **Not persisted** to NVRAM; created at runtime by router processes.

## Index

| Path | Document |
|------|----------|
| status/wan/* | [wan/README.md](wan/README.md) |
| status/system | [system.md](system.md) |
| status/lan | [lan.md](lan.md) |
| status/vpn | [vpn.md](vpn.md) |
| status/hotspot | [hotspot.md](hotspot.md) |
| status/firewall | [firewall.md](firewall.md) |
| status/gps | [gps.md](gps.md) |
| status/container | [container.md](container.md) |
| status/ecm | [ecm.md](ecm.md) |
| status/apdisc | [apdisc.md](apdisc.md) ⚠ |
| status/certmgmt | [certmgmt.md](certmgmt.md) ⚠ |
| status/client_usage | [client_usage.md](client_usage.md) |
| status/dhcp | [dhcp.md](dhcp.md) |
| status/dhcpd | [dhcpd.md](dhcpd.md) |
| status/dns | [dns.md](dns.md) |
| status/dnsmonitor | [dnsmonitor.md](dnsmonitor.md) ⚠ |
| status/dyndns | [dyndns.md](dyndns.md) |
| status/ethernet | [ethernet.md](ethernet.md) |
| status/feature | [feature.md](feature.md) |
| status/flowstats | [flowstats.md](flowstats.md) |
| status/fw_info | [fw_info.md](fw_info.md) |
| status/gpio | [gpio.md](gpio.md) |
| status/gre | [gre.md](gre.md) |
| status/gre_netmanager | [gre_netmanager.md](gre_netmanager.md) |
| status/l2tp | [l2tp.md](l2tp.md) |
| status/lldp | [lldp.md](lldp.md) |
| status/log | [log.md](log.md) |
| status/mdns | [mdns.md](mdns.md) |
| status/modem | [modem.md](modem.md) |
| status/mount | [mount.md](mount.md) |
| status/multicast | [multicast.md](multicast.md) ⚠ |
| status/neighborcache | [neighborcache.md](neighborcache.md) |
| status/nemopmipv6 | [nemopmipv6.md](nemopmipv6.md) |
| status/network | [network.md](network.md) ⚠ |
| status/nhrp | [nhrp.md](nhrp.md) ⚠ |
| status/opendns | [opendns.md](opendns.md) |
| status/openvpn | [openvpn.md](openvpn.md) |
| status/openvpn_netmanager | [openvpn_netmanager.md](openvpn_netmanager.md) |
| status/power_usage | [power_usage.md](power_usage.md) |
| status/product_info | [product_info.md](product_info.md) |
| status/qos | [qos.md](qos.md) |
| status/recover | [recover.md](recover.md) |
| status/remote_modem | [remote_modem.md](remote_modem.md) |
| status/routing | [routing.md](routing.md) |
| status/scepclient | [scepclient.md](scepclient.md) |
| status/sdwan_adv | [sdwan_adv.md](sdwan_adv.md) |
| status/security | [security.md](security.md) |
| status/sfp | [sfp.md](sfp.md) |
| status/signal_strength_leds | [signal_strength_leds.md](signal_strength_leds.md) |
| status/stats | [stats.md](stats.md) |
| status/stp | [stp.md](stp.md) |
| status/tcpdump | [tcpdump.md](tcpdump.md) |
| status/usb | [usb.md](usb.md) |
| status/vsi | [vsi.md](vsi.md) |
| status/vti_netmanager | [vti_netmanager.md](vti_netmanager.md) |
| status/vxlan | [vxlan.md](vxlan.md) |
| status/wired_8021x | [wired_8021x.md](wired_8021x.md) |
| status/wlan | [wlan.md](wlan.md) |
| status/wwan | [wwan.md](wwan.md) ⚠ |

⚠ = Minimal/empty until feature enabled. See [FEATURES_TO_ENABLE.md](../FEATURES_TO_ENABLE.md)

## Access

```python
import cp
data = cp.get('status/wan/connection_state')
```

```bash
GET /api/status/{path}
```
