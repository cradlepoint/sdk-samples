# status/wan/ - WAN Status API

<!-- path: status/wan -->
<!-- type: status -->

WAN (Wide Area Network) status: connection state, active device, IP config, traffic stats. Runtime-only. Config in `config/wan/` drives what appears here.

[status](../) / wan

---

## Index

| Path | Type | Document |
|------|------|----------|
| `status/wan/connection_state` | string | [connection_state.md](connection_state.md) |
| `status/wan/primary_device` | string | [primary_device.md](primary_device.md) |
| `status/wan/ipinfo` | object | [ipinfo.md](ipinfo.md) |
| `status/wan/ip6info` | object | [ip6info.md](ip6info.md) |
| `status/wan/stats` | object | [stats.md](stats.md) |
| `status/wan/devices` | object | [devices/README.md](devices/README.md) |
| `status/wan/cm` | object | [cm.md](cm.md) |
| `status/wan/swans` | object | [swans.md](swans.md) |
| `status/wan/policies` | object | [policies.md](policies.md) |
| `status/wan/steering` | object | [steering.md](steering.md) |
| `status/wan/sdwan` | object | [sdwan.md](sdwan.md) |

---

## Config → Status Relationship

Devices are created when WAN hardware matches rules in `config/wan/rules2/`. See [config/wan/rules2/](../../config-wan-rules2.md).
