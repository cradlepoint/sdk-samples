# Status Endpoints Needing Feature Enablement

These status paths return minimal or empty data because the feature is disabled or not configured. Enable them and re-scan to capture full documentation.

---

## status/wan/ - WAN Subtree

| Endpoint | Current State | Enables When |
|----------|---------------|--------------|
| **status/wan/cm** | Empty `{}` | Connection Manager enabled (multi-WAN mgmt) |
| **status/wan/swans** | ✓ Documented | [status/wan/swans.md](status/wan/swans.md) |
| **status/wan/steering** | `rules: []`, `intents: {}` | Add traffic affinity/steering rules in **config/wan/** (affinity) |
| **status/wan/sdwan** | `connected_hub: "None"`, `links: {}` | SD-WAN hub/spoke configured (NetCloud SD-WAN or equivalent) |
| **status/wan/ip6info** | Empty `{}` | IPv6 enabled and assigned on WAN (config/wan rule with ip6_mode) |

---

## status/ - Empty or Minimal

| Endpoint | Current State | Enables When |
|----------|---------------|--------------|
| **status/apdisc** | `neighbors: {}` | AP discovery configured |
| **status/certmgmt** | `view: []`, `ca_fingerprints: []` | Add certificates / CA to populate |
| **status/dnsmonitor** | Empty `{}` | DNS monitoring configured |
| **status/multicast** | `memberships: []` | Multicast routing configured |
| **status/network** | `null` | Network status (condition-dependent) |
| **status/nhrp** | `mappings: []` | DMVPN / NHRP configured |
| **status/wwan** | `devices: []` | WiFi-as-WAN (WWAN) configured |
| **status/iot** | `bluetooth: radio unplugged` (no BT on some routers), `mqtt`/`msft` disconnected | IoT + Bluetooth (requires BT hardware), MQTT, Microsoft IoT |

---

## status/ - Partial (Some Data, May Improve)

| Endpoint | Current State | Enables When |
|----------|---------------|--------------|
| **status/sdwan_adv** | `user_mode_driver: disabled`, `wan_bonding: []`, `qoe: []`, `link_mon: []` | Advanced SD-WAN, WAN bonding, QoE, link monitoring |
| **status/nemopmipv6** | `enabled: false` | NEMO PMIPv6 enabled in config |
| **status/opendns** | `status: "notcfg"` | OpenDNS/Umbrella configured |
| **status/qos** | `enabled: false`, `queues: []` | QoS rules configured |

---

## Documented (Features Enabled)

| Endpoint | Document |
|----------|----------|
| status/hotspot | [status/hotspot.md](status/hotspot.md) |
| status/gre | [status/gre.md](status/gre.md) |
| status/l2tp | [status/l2tp.md](status/l2tp.md) |
| status/openvpn | [status/openvpn.md](status/openvpn.md) |
| status/dyndns | [status/dyndns.md](status/dyndns.md) |

---

## Quick Enable Checklist

### SWANS (Smart WAN Selection)
- **Config**: `config/wan/swans`
- **Enable**: Set `enabled: true`
- **Optional**: Enable criteria (latency, signal_strength, jitter, datausage)

### SD-WAN
- **Config**: NetCloud Manager or router config for SD-WAN hub/spoke

### Traffic Steering / Affinity
- **Config**: `config/wan/` → affinity rules

### IPv6 on WAN
- **Config**: `config/wan/rules2/{rule_id}` → `ip6_mode: "auto6"`

### NHRP / DMVPN
- **Config**: config for DMVPN tunnel with NHRP

### Multicast
- **Config**: Multicast routing enabled

---

## After Enabling

Re-scan and update docs:

```bash
python3 explore_status.py status/wan/sdwan
python3 explore_status.py status/apdisc
# etc.
```
