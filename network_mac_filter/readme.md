# Network MAC Filter

Enforces MAC address limits per network using Zone-Based Firewall deny rules. Automatically blocks new devices when limits are reached, with support for whitelisted MAC prefixes and manual blocking.

<img width="1458" height="851" alt="image" src="https://github.com/user-attachments/assets/05aee15f-524e-4fdd-a74e-1a838f7d344a" />

## Features

- **Per-network limits** - Configure max unknown hosts per LAN (0 = unlimited)
- **MAC prefix whitelist** - Known OUI prefixes don't count toward limits
- **Auto-blocking** - New MACs blocked when limit reached (🟠 OVER LIMIT)
- **Manual blocking** - Persist blocks across disconnects/reboots (🔴 BLOCKED)
- **Dynamic tracking** - Monitors REACHABLE and STALE ARP entries every 2 seconds
- **Grace period** - 6-second delay before removing disconnected MACs
- **Web interface** - Real-time view and control at port 8000
- **Color-coded status** - 🟢 ALLOWED, 🟠 OVER LIMIT, 🔴 BLOCKED

## Quick Start

1. **Install app** via NetCloud Manager
2. **Create Zone-Based Firewall filter policies** - Policy name must match LAN name exactly (e.g., "Primary LAN")
3. **Access web UI** at `http://{router_ip}:8000/`
4. **Configure** via gear icon:
   - Set max unknown per network
   - Add allowed MAC prefixes (e.g., `00:11:22,AA:BB:CC`)
5. **Monitor and manage** MACs in real-time

## How It Works

**Monitoring**: Checks ARP table every 2 seconds for REACHABLE/STALE IPv4 devices

**Classification**: 
- **Known MACs** - Match configured prefixes, always allowed, don't count toward limits
- **Unknown MACs** - Don't match prefixes, count toward limits
- Prefix changes immediately re-classify all MACs

**Enforcement**:
- **Auto-block** (🟠 OVER LIMIT) - When limit reached, new MACs get firewall deny rules. Freed when disconnected.
- **Manual block** (🔴 BLOCKED) - Click Block button. Saved to appdata, persists until unblocked.

**Grace Period**: MACs must be missing for 6 seconds (3 cycles) before removal

## Configuration

### Via Web Interface (Gear Icon)

**Per-Network Settings:**
- **Max Unknown** - Maximum unknown MACs allowed (0 = unlimited)
- **Allowed MAC Prefixes** - Comma-separated OUI prefixes: `00:11:22,AA:BB:CC,DD:EE:FF`

### Via Appdata (Optional)

- `network_config` - JSON: `{"Network Name": {"max_unknown": 5, "allowed_prefixes": ["001122", "AABBCC"]}}`
- `manual_blocks` - JSON: `{"Network Name": {"AA:BB:CC:DD:EE:FF": true}}`
- `disable_ui` - Set to any value to disable the web interface
- `custom_mac_filter_port` - Web port (default: 8000)

## Example

**Scenario**: Guest network with 5-device limit, excluding company devices

1. Gear icon → Find "Guest LAN"
2. Max Unknown: `5`
3. Allowed MAC Prefixes: `00:11:22,AA:BB:CC`
4. Save

**Result**: Company devices (00:11:22*, AA:BB:CC*) always allowed. Up to 5 other devices allowed. 6th device auto-blocked.

## Firewall Integration

Requires Zone-Based Firewall filter policy per LAN:
- Policy name must match LAN name exactly
- Default action "allow" (app adds specific deny rules)
- Deny rules named `Deny-{mac_address}`
- **Apply filter policy when forwarding the network/zone to another zone** (e.g., LAN → WAN, LAN → Tunnel)

If policy missing, web UI shows warning and disables Block/Allow buttons.

## Headless Mode (No Web UI)

Set `disable_ui` appdata to any value to run without the web interface. All configuration and blocking is done via appdata and the CLI/API.

### Status

The app publishes per-network status every cycle to:
```
status/network_mac_filter/{network_name}
```
Network names have spaces and slashes replaced with underscores (e.g., "Guest LAN" → `Guest_LAN`).

Example response:

```json
{
  "total_macs": 4,
  "known_macs": 1,
  "unknown_allowed": 2,
  "unknown_blocked": 1,
  "manual_blocks": 1,
  "max_unknown": 5,
  "has_policy": true,
  "macs": [
    {
      "mac": "00:11:22:33:44:55",
      "ip": "192.168.0.10",
      "known": true,
      "blocked": false,
      "manual": false
    },
    {
      "mac": "AA:BB:CC:DD:EE:FF",
      "ip": "192.168.0.100",
      "known": false,
      "blocked": true,
      "manual": true
    }
  ]
}
```

- `known` — matches an allowed prefix
- `blocked` — currently has a firewall deny rule
- `manual` — manually blocked, persists until explicitly unblocked

### Block / Unblock via Control Tree

```
PUT control/network_mac_filter/{network_name}/block    → "AA:BB:CC:DD:EE:FF"
PUT control/network_mac_filter/{network_name}/unblock  → "AA:BB:CC:DD:EE:FF"
```

MAC addresses accept any format (colons, dashes, no separators, mixed case).

curl examples:
```
# Block a MAC on Guest_LAN
curl -s -k -u admin:pass -X PUT \
  https://ROUTER_IP/api/control/network_mac_filter/Guest_LAN/block \
  -d "data=AA:BB:CC:DD:EE:FF"

# Unblock
curl -s -k -u admin:pass -X PUT \
  https://ROUTER_IP/api/control/network_mac_filter/Guest_LAN/unblock \
  -d "data=AA:BB:CC:DD:EE:FF"

# Read status
curl -s -k -u admin:pass \
  https://ROUTER_IP/api/status/network_mac_filter/Guest_LAN
```

### Configure networks via Appdata

Set `network_config` appdata:
```json
{"Guest LAN": {"max_unknown": 5, "allowed_prefixes": ["001122", "AABBCC"]}}
```

### Appdata curl examples

Appdata is an array of `{"name": "...", "value": "...", "_id_": "..."}` objects. You need to find the entry's `_id_` to update or delete it.

```
# List all appdata (find _id_ values)
curl -s -k -u admin:pass https://ROUTER_IP/api/config/system/sdk/appdata/

# Create network_config (first time)
curl -s -k -u admin:pass -X POST https://ROUTER_IP/api/config/system/sdk/appdata/ \
  -d 'data={"name":"network_config","value":"{\"Guest LAN\":{\"max_unknown\":5,\"allowed_prefixes\":[\"001122\"]}}"}'

# Update network_config (use _id_ from GET response)
curl -s -k -u admin:pass -X PUT https://ROUTER_IP/api/config/system/sdk/appdata/ID/value \
  -d 'data={"Guest LAN":{"max_unknown":5,"allowed_prefixes":["001122"]}}'
```

Replace `ID` with the `_id_` value returned from the GET request for the `network_config` entry.

## State Files

- `tmp/state.json` - Current tracked MACs

## Troubleshooting

**Block/Allow buttons disabled** - Create Zone-Based Firewall filter policy matching LAN name

**MACs not being blocked** - Check:
- max_unknown > 0
- MAC doesn't match prefixes
- Filter policy is applied to correct zone forwarding (e.g., LAN → WAN)

**Manual vs Auto-blocking**:
- 🟠 OVER LIMIT - Auto-blocked, frees slot when disconnected
- 🔴 BLOCKED - Manually blocked, stays blocked until you click Allow
