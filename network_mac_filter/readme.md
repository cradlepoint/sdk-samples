# Network MAC Filter

Enforces MAC address limits per network using deny rules in firewall filter policies. When the MAC limit is reached on a specific network, the app automatically adds deny rules for any new reachable MACs seen on that network.

<img width="1458" height="851" alt="image" src="https://github.com/user-attachments/assets/0d590f4c-d11d-4efb-8148-b8e2bbe8e88a" />

## Features

- **Per-network configuration** - Each LAN can have its own MAC limit and allowed prefixes
- **Monitors ARP table** (`status/routing/cli/arpdump`) for REACHABLE and STALE IPv4 MAC addresses every 2 seconds
- **Grace period** - MACs must be missing for 6 seconds (3 cycles) before removal to handle ARP cache fluctuations
- **Known/Unknown MAC tracking** - MACs matching configured OUI prefixes are marked as "known" and don't count toward limits
- **Dynamic prefix re-evaluation** - Changing prefixes immediately updates known/unknown status for all tracked MACs
- **Automatic enforcement** - When unknown MAC limit is reached, new MACs are automatically blocked via firewall deny rules
- **Manual blocking** - Manually blocked MACs persist across disconnects and reboots until explicitly unblocked
- **Color-coded status** - Green (ALLOWED), Orange (OVER LIMIT), Red (BLOCKED)
- **Web interface** (default port 8000) for viewing and managing allowed/blocked MAC addresses per network
- **Settings modal** - Configure limits and prefixes per network via gear icon
- **Real-time toggle** - Manually allow/block individual MAC addresses
- **Filter policy validation** - Warns when Zone-Based Firewall filter policies are missing
- **State persistence** - Survives router reboots

## How It Works

1. **Monitoring**: Every 2 seconds, the app reads the ARP table to discover REACHABLE and STALE IPv4 devices
2. **Grace Period**: MACs must be missing for 6 seconds (3 consecutive cycles) before being removed from tracking
3. **Classification**: Each MAC is checked against its network's allowed prefixes every cycle
   - **Known MACs**: Match configured prefixes, don't count toward limits, always allowed
   - **Unknown MACs**: Don't match prefixes, count toward limits, subject to enforcement
   - Prefix changes immediately re-classify all tracked MACs
4. **Enforcement**: When a new unknown MAC appears and the network has reached its limit, a firewall deny rule is automatically created
5. **Manual Blocking**: MACs blocked via the web interface are saved to `tmp/manual_blocks.json` and remain blocked even after disconnecting
6. **Management**: The web interface allows manual override of allow/block status for any tracked MAC

## Firewall Integration

The app integrates with NCOS Zone-Based Firewall (ZFW) filter policies:

1. Gets the network name from `status/lan/networks/{interface}/info/name`
2. Finds the matching filter policy in `config/security/zfw/filter_policies/` by name
3. Adds/removes deny rules with MAC address matching in the `src.mac` field
4. Deny rules are named `Deny-{mac_address}` for easy identification

**Important**: Each LAN must have a matching Zone-Based Firewall filter policy with the same name. If a policy is missing, the app will display a warning and disable block/allow buttons for that network.

## Configuration

All configuration is done via the web interface settings modal (gear icon):

### Per-Network Settings

Each network can be configured independently:

- **Max Hosts** - Maximum number of unknown hosts allowed (0 = unlimited)
- **Allowed MAC Prefixes** - Comma-separated OUI prefixes (first 6 hex characters) that are always allowed

Configuration is saved to appdata field `network_config` as JSON.

### Global Settings

- **custom_mac_filter_port** (Optional) - TCP port for web interface (default: 8000)

## Web Interface

Access at `http://{router_ip}:{port}/` (default: `http://192.168.1.4:8000/`)

### Main View

- Networks listed in config/lan order
- Each network shows:
  - Known MAC count (matching prefixes)
  - Unknown MAC count vs limit
  - Configured prefixes
  - Warning if filter policy is missing
  - Table of all tracked MACs with:
    - MAC address
    - IP address
    - Prefix status (Known/Unknown)
    - Current status with color-coded pills:
      - 🟢 **ALLOWED** - Green (allowed MACs)
      - 🟠 **OVER LIMIT** - Orange (auto-blocked due to limit, freed when disconnected)
      - 🔴 **BLOCKED** - Red (manually blocked, persists until unblocked)
    - Block/Allow button (disabled if no filter policy)

### Settings Modal (Gear Icon)

- Configure max hosts per network
- Configure allowed MAC prefixes per network
- Changes take effect immediately after saving

### Theme Toggle (Sun/Moon Icon)

- Switch between light and dark mode
- Preference saved to browser localStorage

## Example Configuration

**Scenario**: Guest network with 5-device limit, excluding company infrastructure

1. Click gear icon to open settings
2. Find "Guest LAN" network
3. Set **Max Hosts**: `5`
4. Set **Allowed MAC Prefixes**: `00:11:22,AA:BB:CC,DD:EE:FF`
5. Click "Save Settings"

**Result**:
- Devices with MACs starting with `00:11:22`, `AA:BB:CC`, or `DD:EE:FF` are always allowed (marked as "Known")
- Up to 5 additional unknown devices are allowed
- The 6th unknown device triggers a firewall deny rule
- All activity is visible in the web interface

## Setup

1. Install the app via NetCloud Manager
2. Create Zone-Based Firewall filter policies for each LAN:
   - Policy name must match LAN name exactly (e.g., "Primary LAN", "Guest LAN")
   - Default action "allow" (app adds specific deny rules)
3. Access web interface at `http://{router_ip}:8000/`
4. Click gear icon to configure limits and prefixes per network
5. Monitor and manage MACs in real-time

## Logs

The app logs important events:
- Startup and configuration loading
- Filter policy status for each network
- New MACs discovered and blocked when limits are reached
- Firewall rule additions/removals
- Web server status

View logs in NetCloud Manager or via the router's local logs.

## Appdata Fields

- `network_config` - JSON object with per-network configuration: `{network_name: {max_hosts: int, allowed_prefixes: [str]}}`
- `custom_mac_filter_port` - Web interface port (default: 8000)

## State Files

- `tmp/state.json` - Current tracked MACs (cleared on removal after grace period)
- `tmp/manual_blocks.json` - Manually blocked MACs (persists across disconnects and reboots)

## Troubleshooting

**Block/Allow buttons are disabled**
- A Zone-Based Firewall filter policy matching the network name is missing
- Create a filter policy with the exact same name as the LAN network

**MACs not being blocked**
- Check that max_hosts is set > 0 for the network
- Verify the MAC doesn't match any configured prefixes
- Check logs for errors

**MACs flickering in/out of the list**
- This should not happen with the 6-second grace period and STALE tracking
- If it does, check for ARP table issues or network instability

**Manually blocked MAC reconnected**
- Manually blocked MACs (red BLOCKED status) stay blocked until you click Allow
- Auto-blocked MACs (orange OVER LIMIT status) free up slots when they disconnect
