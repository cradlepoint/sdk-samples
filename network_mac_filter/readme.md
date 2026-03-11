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
   - Set max hosts per network
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
- **Manual block** (🔴 BLOCKED) - Click Block button. Saved to `tmp/manual_blocks.json`, persists until unblocked.

**Grace Period**: MACs must be missing for 6 seconds (3 cycles) before removal

## Configuration

### Via Web Interface (Gear Icon)

**Per-Network Settings:**
- **Max Hosts** - Maximum unknown hosts (0 = unlimited)
- **Allowed MAC Prefixes** - Comma-separated OUI prefixes: `00:11:22,AA:BB:CC,DD:EE:FF`

### Via Appdata (Optional)

- `network_config` - JSON: `{"Network Name": {"max_hosts": 5, "allowed_prefixes": ["001122", "AABBCC"]}}`
- `custom_mac_filter_port` - Web port (default: 8000)

## Example

**Scenario**: Guest network with 5-device limit, excluding company devices

1. Gear icon → Find "Guest LAN"
2. Max Hosts: `5`
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

## State Files

- `tmp/state.json` - Current tracked MACs
- `tmp/manual_blocks.json` - Manually blocked MACs (persists across reboots)

## Troubleshooting

**Block/Allow buttons disabled** - Create Zone-Based Firewall filter policy matching LAN name

**MACs not being blocked** - Check max_hosts > 0 and MAC doesn't match prefixes

**MACs flickering** - Shouldn't happen with 6-second grace period and STALE tracking. Check ARP stability.

**Manual vs Auto-blocking**:
- 🟠 OVER LIMIT - Auto-blocked, frees slot when disconnected
- 🔴 BLOCKED - Manually blocked, stays blocked until you click Allow
