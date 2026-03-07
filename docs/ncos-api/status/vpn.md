# status/vpn

<!-- path: status/vpn -->
<!-- type: status -->
<!-- response: object -->

[status](README.md) / vpn

---

IPSec/strongSwan VPN status: tunnels, connections, service state, and policy.

### Fields (top-level)

| Field | Type | Description |
|-------|------|-------------|
| `global` | object | See sub-table |
| `running` | boolean | VPN service running |
| `tunnels` | array | See sub-table |
| `service` | object | See [vpn/service.md](vpn/service.md) |
| `enabled` | array | Enabled VPN services (e.g. ["vpn"]) |
| `tunnel_action` | object | See sub-table |

**global**

| Field | Type | Description |
|-------|------|-------------|
| `policy` | string | XFRM policy |
| `state` | string | XFRM state summary |
| `config` | string | strongSwan config text |
| `strongswan_conf` | string | charon daemon config |
| `limits` | string | Tunnel limits |

**tunnels[]**

| Field | Type | Description |
|-------|------|-------------|
| `_id_` | uuid | Tunnel config ID |
| `name` | string | Tunnel name |
| `enabled` | boolean | Tunnel enabled |
| `state` | string | connecting, up, down |
| `cli` | string | CLI output (optional) |
| `dead_peer_timeout` | integer | DPD timeout |
| `connections` | array | See sub-table |

**tunnels[].connections[]**

| Field | Type | Description |
|-------|------|-------------|
| `version` | string | IKEv1, IKEv2 |
| `local` | array | Local IP(s) |
| `remote` | array | Remote IP(s) |
| `sas` | array | Security associations |

**tunnel_action**

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Tunnel name |
| `action` | string | start, stop |

### SDK Example
```python
import cp
vpn = cp.get('status/vpn')
if vpn:
    for t in vpn.get('tunnels', []):
        cp.log(f"IPSec {t.get('name')}: {t.get('state')}")
```

### REST
```
GET /api/status/vpn
```

### Breakout docs (in vpn/)
- [vpn/service.md](vpn/service.md) – service object (10+ fields, deep nesting)

### Related
- [gre](gre.md) – GRE tunnels
- [openvpn](openvpn.md) – OpenVPN tunnels
- config/vpn/ – IPSec VPN configuration
