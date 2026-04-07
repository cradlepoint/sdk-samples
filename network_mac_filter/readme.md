# Network MAC Filter

Enforces MAC address limits per network using Zone-Based Firewall deny rules. Automatically blocks new devices when limits are reached, with support for whitelisted MAC prefixes and manual blocking.

<img width="1458" height="851" alt="image" src="https://github.com/user-attachments/assets/05aee15f-524e-4fdd-a74e-1a838f7d344a" />

## Features

- **Per-network limits** - Configure max unknown hosts per LAN (0 = unlimited)
- **Sticky MACs** - Learned unknown MACs hold their slot permanently while running (like Cisco port-security sticky). Reboot clears them
- **MAC prefix whitelist** - Known OUI prefixes don't count toward limits, manageable via control tree
- **Auto-blocking** - New MACs blocked when limit reached (🟠 OVER LIMIT)
- **Manual blocking** - Persist blocks across disconnects/reboots (🔴 BLOCKED)
- **Dynamic tracking** - Monitors REACHABLE and STALE ARP entries every 2 seconds
- **Grace period** - 6-second delay before removing disconnected known-prefix MACs
- **Web interface** - Real-time view and control at port 8000, can be disabled/enabled at runtime
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
- **Sticky learning** - When an unknown MAC is first seen and a slot is available, it's allowed and becomes "sticky". Sticky MACs hold their slot permanently while the app is running, even if the device disconnects. This prevents slot recycling — once learned, only a reboot or `clear_sticky` frees the slot.
- **Auto-block** (🟠 OVER LIMIT) - When all sticky slots are filled, new MACs get firewall deny rules.
- **Manual block** (🔴 BLOCKED) - Click Block button. Saved to appdata, persists until unblocked.

**Grace Period**: Known-prefix MACs must be missing for 6 seconds (3 cycles) before removal. Sticky and blocked MACs are never removed automatically.

## Configuration

### Via Web Interface (Gear Icon)

**Per-Network Settings:**
- **Max Unknown** - Maximum unknown MACs allowed (0 = unlimited)
- **Allowed MAC Prefixes** - Comma-separated OUI prefixes: `00:11:22,AA:BB:CC,DD:EE:FF`

## Example

**Scenario**: Guest network with 5-device limit, excluding company devices

1. Gear icon → Find "Guest LAN"
2. Max Unknown: `5`
3. Allowed MAC Prefixes: `00:11:22,AA:BB:CC`
4. Save

**Result**: Company devices (00:11:22*, AA:BB:CC*) always allowed. Up to 5 other devices allowed and learned as sticky. 6th unknown device auto-blocked. Sticky MACs hold their slots even when disconnected — reboot or `clear_sticky` to reset.

## Firewall Integration

Requires Zone-Based Firewall filter policy per LAN:
- Policy name must match LAN name exactly
- Default action "allow" (app adds specific deny rules)
- Deny rules named `Deny-{mac_address}`
- **Apply filter policy when forwarding the network/zone to another zone** (e.g., LAN → WAN, LAN → Tunnel)

If policy missing, web UI shows warning and disables Block/Allow buttons.

## Headless Mode (No Web UI)

Set `disable_ui` appdata to any value to run without the web interface. All configuration and blocking is done via appdata and the CLI/API. The app checks this setting every 2 seconds — setting or clearing `disable_ui` while running will stop or start the web server dynamically without an app restart.

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
  "manual_blocked_macs": ["AA:BB:CC:DD:EE:FF"],
  "max_unknown": 5,
  "has_policy": true,
  "known_prefixes": ["001122", "AABBCC"],
  "macs": [
    {
      "mac": "00:11:22:33:44:55",
      "ip": "192.168.0.10",
      "known": true,
      "blocked": false,
      "manual": false,
      "sticky": false
    },
    {
      "mac": "AA:BB:CC:DD:EE:FF",
      "ip": "192.168.0.100",
      "known": false,
      "blocked": true,
      "manual": true,
      "sticky": false
    }
  ]
}
```

- `known` — matches an allowed prefix
- `known_prefixes` — OUI prefixes configured for this network
- `blocked` — currently has a firewall deny rule
- `manual` — manually blocked, persists until explicitly unblocked
- `sticky` — learned unknown MAC that holds its slot permanently while running

### Block / Unblock via Control Tree

```
PUT control/network_mac_filter/{network_name}/block    → "AA:BB:CC:DD:EE:FF"
PUT control/network_mac_filter/{network_name}/unblock  → "AA:BB:CC:DD:EE:FF"
```

### Add / Remove Known Prefixes via Control Tree

Add or remove OUI prefixes (first 6 hex chars of MAC) to a network's allowed list:

```
PUT control/network_mac_filter/{network_name}/add_known_prefix    → "00:11:22"
PUT control/network_mac_filter/{network_name}/remove_known_prefix → "00:11:22"
```

Accepts any format: `00:11:22`, `001122`, `00-11-22`. Comma-separated for multiple: `00:11:22,AA:BB:CC`. All MACs matching the prefix are treated as known (always allowed, don't count toward limits). Changes are saved to appdata and take effect on the next monitoring cycle.

### Clear Sticky MACs via Control Tree

Reset all learned sticky MACs for a network, freeing their slots:

```
PUT control/network_mac_filter/{network_name}/clear_sticky → "1"
```

This removes all sticky MACs from tracking (unless manually blocked) and allows new devices to fill the slots. Equivalent to a reboot for that network only.

MAC addresses accept any format (colons, dashes, no separators, mixed case).

## State Files

- `tmp/state.json` - Current tracked MACs

## Troubleshooting

**Block/Allow buttons disabled** - Create Zone-Based Firewall filter policy matching LAN name

**MACs not being blocked** - Check:
- max_unknown > 0
- MAC doesn't match prefixes
- Filter policy is applied to correct zone forwarding (e.g., LAN → WAN)

**Manual vs Auto-blocking**:
- 🟠 OVER LIMIT - Auto-blocked, denied until `clear_sticky` frees a slot or reboot
- 🔴 BLOCKED - Manually blocked, stays blocked until you click Allow

**Sticky MACs not clearing** - Use `clear_sticky` control tree action or reboot the router
