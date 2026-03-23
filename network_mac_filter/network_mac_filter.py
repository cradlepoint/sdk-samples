import cp
import time
import re
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import socket

# Global state
tracked_macs = {}  # {network: {mac: {'ip': str, 'blocked': bool, 'known': bool, 'missing_count': int}}}
manual_blocks = {}  # {network: {mac: True}} - Manually blocked MACs that persist
network_config = {}  # {network: {'max_unknown': int, 'allowed_prefixes': [str]}}
network_policy_status = {}  # {network: bool} - True if policy exists
web_port = 8000
GRACE_PERIOD_CYCLES = 3  # Remove MAC after missing for this many cycles


def parse_mac_prefixes(prefix_str):
    """Parse comma-separated MAC prefixes, handling various formats."""
    if not prefix_str:
        return []
    
    prefixes = []
    for prefix in prefix_str.split(','):
        # Remove all non-hex characters
        clean = re.sub(r'[^0-9A-Fa-f]', '', prefix.strip())
        if len(clean) >= 6:
            prefixes.append(clean[:6].upper())
    return prefixes


def normalize_mac(mac_str):
    """Normalize a MAC address string to XX:XX:XX:XX:XX:XX format.
    Handles formats like AABBCCDDEEFF, AA-BB-CC-DD-EE-FF, aa:bb:cc:dd:ee:ff, etc."""
    clean = re.sub(r'[^0-9A-Fa-f]', '', mac_str.strip())
    if len(clean) != 12:
        return None
    clean = clean.upper()
    return ':'.join(clean[i:i+2] for i in range(0, 12, 2))


def is_allowed_prefix(mac, network):
    """Check if MAC has an allowed OUI prefix for this network."""
    prefixes = network_config.get(network, {}).get('allowed_prefixes', [])
    if not prefixes:
        return False
    clean_mac = re.sub(r'[^0-9A-Fa-f]', '', mac).upper()
    return any(clean_mac.startswith(prefix) for prefix in prefixes)


def parse_arpdump(arpdump_str):
    """Parse ARP dump and return list of {interface, mac, ip, state}."""
    entries = []
    for line in arpdump_str.split('\n'):
        parts = line.split()
        if len(parts) >= 5 and parts[0] == 'ethernet' and parts[2] in ['REACHABLE', 'STALE']:
            mac = parts[3]
            ip = parts[4]
            interface = parts[1]
            # Check if IPv4 (no colons in IP)
            if ':' not in ip and mac != '0/0/0':
                # Remove trailing digit from interface
                interface = re.sub(r'\d+$', '', interface)
                entries.append({'interface': interface, 'mac': mac, 'ip': ip})
    return entries


def get_network_name(interface):
    """Get network name from interface."""
    try:
        info = cp.get(f'status/lan/networks/{interface}/info')
        if info:
            return info.get('name', '')
    except Exception as e:
        cp.log(f"Error getting network name for {interface}: {e}")
    return ''


def check_filter_policies():
    """Check which networks have matching filter policies."""
    global network_policy_status
    try:
        policies = cp.get('config/security/zfw/filter_policies')
        policy_names = [p.get('name') for p in policies] if policies else []
        
        lans = cp.get('config/lan')
        if lans:
            for lan in lans:
                name = lan.get('name')
                if name:
                    network_policy_status[name] = name in policy_names
        
        cp.log(f"Filter policy status: {network_policy_status}")
    except Exception as e:
        cp.log(f"Error checking filter policies: {e}")


def cleanup_orphaned_deny_rules():
    """Remove deny rules for non-known MACs from filter policies on startup.
    Keep deny rules for known-prefix MACs and manually blocked MACs."""
    global tracked_macs
    try:
        policies = cp.get('config/security/zfw/filter_policies')
        if not policies:
            return
        
        # Build set of MACs to keep (known-prefix + manually blocked)
        keep_macs = set()
        for network_name, macs in tracked_macs.items():
            for mac, info in macs.items():
                if info.get('known', False) or is_manually_blocked(network_name, mac):
                    keep_macs.add(mac)
        
        total_removed = 0
        for policy in policies:
            policy_id = policy.get('_id_')
            policy_name = policy.get('name')
            if not policy_id:
                continue
            
            rules = cp.get(f'config/security/zfw/filter_policies/{policy_id}/rules') or []
            
            new_rules = []
            removed_count = 0
            for rule in rules:
                rule_name = rule.get('name', '')
                if rule_name.startswith('Deny-'):
                    # Extract MAC from rule name
                    rule_mac = rule_name[5:]  # Strip 'Deny-' prefix
                    if rule_mac in keep_macs:
                        new_rules.append(rule)
                    else:
                        removed_count += 1
                else:
                    new_rules.append(rule)
            
            if removed_count > 0:
                cp.put(f'config/security/zfw/filter_policies/{policy_id}/rules', new_rules)
                cp.log(f"Removed {removed_count} deny rules from {policy_name} (kept {len(keep_macs)} known/manual)")
                total_removed += removed_count
        
        # Flush tracked_macs of non-known, non-manual entries
        for network_name in list(tracked_macs.keys()):
            for mac in list(tracked_macs[network_name].keys()):
                if not tracked_macs[network_name][mac].get('known', False) and not is_manually_blocked(network_name, mac):
                    del tracked_macs[network_name][mac]
        save_state()
        
        if total_removed > 0:
            cp.log(f"Startup cleanup: Removed {total_removed} total deny rules")
    except Exception as e:
        cp.log(f"Error cleaning up orphaned deny rules: {e}")


def get_filter_policy_id(network_name):
    """Get filter policy _id_ for network name."""
    try:
        policies = cp.get('config/security/zfw/filter_policies')
        if policies:
            for policy in policies:
                if policy.get('name') == network_name:
                    return policy.get('_id_')
    except Exception as e:
        cp.log(f"Error getting filter policy: {e}")
    return None


def add_deny_rule(policy_id, mac):
    """Add deny rule for MAC address to filter policy."""
    try:
        rules = cp.get(f'config/security/zfw/filter_policies/{policy_id}/rules') or []
        
        # Check if rule already exists
        for rule in rules:
            src_macs = rule.get('src', {}).get('mac', [])
            for mac_entry in src_macs:
                if mac_entry.get('identity') == mac:
                    return True
        
        # Add new deny rule
        new_rule = {
            'action': 'deny',
            'app_sets': [],
            'dst': {'ip': [], 'port': []},
            'ip_version': 'ip4',
            'name': f'Deny-{mac}',
            'priority': 10,
            'protocols': [],
            'src': {
                'ip': [],
                'mac': [{'identity': mac}],
                'port': []
            }
        }
        rules.append(new_rule)
        
        cp.put(f'config/security/zfw/filter_policies/{policy_id}/rules', rules)
        cp.log(f"Added deny rule for MAC {mac} in policy {policy_id}")
        return True
    except Exception as e:
        cp.log(f"Error adding deny rule: {e}")
        return False


def remove_deny_rule(policy_id, mac):
    """Remove deny rule for MAC address from filter policy."""
    try:
        rules = cp.get(f'config/security/zfw/filter_policies/{policy_id}/rules') or []
        
        # Filter out the rule for this MAC
        new_rules = []
        for rule in rules:
            src_macs = rule.get('src', {}).get('mac', [])
            has_mac = any(mac_entry.get('identity') == mac for mac_entry in src_macs)
            if not has_mac:
                new_rules.append(rule)
        
        if len(new_rules) != len(rules):
            cp.put(f'config/security/zfw/filter_policies/{policy_id}/rules', new_rules)
            cp.log(f"Removed deny rule for MAC {mac} from policy {policy_id}")
            return True
    except Exception as e:
        cp.log(f"Error removing deny rule: {e}")
    return False


def load_state():
    """Load tracked MACs from state file."""
    global tracked_macs
    try:
        if os.path.exists('tmp/state.json'):
            with open('tmp/state.json', 'r') as f:
                tracked_macs = json.load(f)
            cp.log(f"Loaded state: {len(tracked_macs)} networks")
    except Exception as e:
        cp.log(f"Error loading state: {e}")


def save_state():
    """Save tracked MACs to state file."""
    try:
        os.makedirs('tmp', exist_ok=True)
        with open('tmp/state.json', 'w') as f:
            json.dump(tracked_macs, f)
    except Exception as e:
        cp.log(f"Error saving state: {e}")


def load_manual_blocks():
    """Load manually blocked MACs from appdata."""
    global manual_blocks
    try:
        data = cp.get_appdata('manual_blocks')
        if data:
            manual_blocks = json.loads(data)
            cp.log(f"Loaded manual blocks: {sum(len(macs) for macs in manual_blocks.values())} MACs")
    except Exception as e:
        cp.log(f"Error loading manual blocks: {e}")


def save_manual_blocks():
    """Save manually blocked MACs to appdata."""
    try:
        cp.put_appdata('manual_blocks', json.dumps(manual_blocks))
    except Exception as e:
        cp.log(f"Error saving manual blocks: {e}")


def is_manually_blocked(network, mac):
    """Check if MAC is manually blocked."""
    return manual_blocks.get(network, {}).get(mac, False)


def set_manual_block(network, mac, blocked):
    """Set or clear manual block for MAC."""
    global manual_blocks
    if network not in manual_blocks:
        manual_blocks[network] = {}
    
    if blocked:
        manual_blocks[network][mac] = True
        cp.log(f"Manually blocked MAC {mac} on {network}")
    else:
        if mac in manual_blocks[network]:
            del manual_blocks[network][mac]
            cp.log(f"Manually unblocked MAC {mac} on {network}")
    
    save_manual_blocks()

def publish_status():
    """Publish per-network status to status tree for CLI access."""
    for network_name, macs in tracked_macs.items():
        known = 0
        unknown_allowed = 0
        unknown_blocked = 0
        manual = 0
        total = len(macs)
        mac_list = []

        for mac, info in macs.items():
            if info.get('known', False):
                known += 1
            elif info.get('blocked', False):
                unknown_blocked += 1
                if is_manually_blocked(network_name, mac):
                    manual += 1
            else:
                unknown_allowed += 1

            mac_list.append({
                'mac': mac,
                'ip': info.get('ip', ''),
                'known': info.get('known', False),
                'blocked': info.get('blocked', False),
                'manual': is_manually_blocked(network_name, mac)
            })

        config = network_config.get(network_name, {})
        max_unknown = config.get('max_unknown', 0)
        has_policy = network_policy_status.get(network_name, False)

        status = {
            'total_macs': total,
            'known_macs': known,
            'unknown_allowed': unknown_allowed,
            'unknown_blocked': unknown_blocked,
            'manual_blocks': manual,
            'max_unknown': max_unknown,
            'has_policy': has_policy,
            'macs': mac_list
        }

        try:
            safe_name = network_name.replace(' ', '_').replace('/', '_')
            cp.put(f'status/network_mac_filter/{safe_name}', status)
        except Exception as e:
            cp.log(f"Error publishing status for {network_name}: {e}")


def _resolve_network_name(safe_name):
    """Resolve a safe (underscored) network name back to the real LAN name."""
    try:
        lans = cp.get('config/lan')
        if lans:
            for lan in lans:
                name = lan.get('name', '')
                if name.replace(' ', '_').replace('/', '_') == safe_name:
                    return name
    except Exception as e:
        cp.log(f"Error resolving network name: {e}")
    return None


def on_block(path, value, args):
    """Callback for control/network_mac_filter/{network}/block."""
    try:
        parts = path.split('/')
        safe_name = parts[2] if len(parts) >= 4 else ''
        network_name = _resolve_network_name(safe_name)
        if not network_name:
            cp.log(f"Block: unknown network '{safe_name}'")
            return

        mac = normalize_mac(str(value))
        if not mac:
            cp.log(f"Block: invalid MAC '{value}'")
            return

        policy_id = get_filter_policy_id(network_name)
        if not policy_id:
            cp.log(f"Block: no filter policy for {network_name}")
            return

        set_manual_block(network_name, mac, True)
        if network_name in tracked_macs and mac in tracked_macs[network_name]:
            tracked_macs[network_name][mac]['blocked'] = True
        add_deny_rule(policy_id, mac)
        cp.log(f"CLI block: {mac} on {network_name}")
    except Exception as e:
        cp.log(f"Error in on_block: {e}")


def on_unblock(path, value, args):
    """Callback for control/network_mac_filter/{network}/unblock."""
    try:
        parts = path.split('/')
        safe_name = parts[2] if len(parts) >= 4 else ''
        network_name = _resolve_network_name(safe_name)
        if not network_name:
            cp.log(f"Unblock: unknown network '{safe_name}'")
            return

        mac = normalize_mac(str(value))
        if not mac:
            cp.log(f"Unblock: invalid MAC '{value}'")
            return

        policy_id = get_filter_policy_id(network_name)
        if not policy_id:
            cp.log(f"Unblock: no filter policy for {network_name}")
            return

        set_manual_block(network_name, mac, False)
        if network_name in tracked_macs and mac in tracked_macs[network_name]:
            tracked_macs[network_name][mac]['blocked'] = False
        remove_deny_rule(policy_id, mac)
        cp.log(f"CLI unblock: {mac} on {network_name}")
    except Exception as e:
        cp.log(f"Error in on_unblock: {e}")


def register_control_callbacks():
    """Register block/unblock callbacks for each LAN network."""
    try:
        lans = cp.get('config/lan')
        if not lans:
            return
        for lan in lans:
            name = lan.get('name', '')
            if not name:
                continue
            safe_name = name.replace(' ', '_').replace('/', '_')
            cp.register('set', f'control/network_mac_filter/{safe_name}/block', on_block)
            cp.register('set', f'control/network_mac_filter/{safe_name}/unblock', on_unblock)
            cp.log(f"Registered control callbacks for {name}")
    except Exception as e:
        cp.log(f"Error registering control callbacks: {e}")




def monitor_macs():
    """Monitor ARP table and enforce MAC limits."""
    global tracked_macs
    
    while True:
        try:
            # Load all LAN names each cycle to keep tracked_macs updated
            lans = cp.get('config/lan')
            if lans:
                for lan in lans:
                    name = lan.get('name')
                    if name and name not in tracked_macs:
                        tracked_macs[name] = {}
            
            arpdump = cp.get('status/routing/cli/arpdump')
            if not arpdump:
                time.sleep(2)
                continue
            
            entries = parse_arpdump(arpdump)
            
            current_macs = {}  # {network: {mac: ip}}
            current_known = {}  # {network: {mac: ip}} for known prefixes
            
            for entry in entries:
                interface = entry['interface']
                mac = entry['mac']
                ip = entry['ip']
                
                # Get network name
                network_name = get_network_name(interface)
                if not network_name:
                    continue
                
                # Check if allowed prefix for this network
                if is_allowed_prefix(mac, network_name):
                    if network_name not in current_known:
                        current_known[network_name] = {}
                    current_known[network_name][mac] = ip
                    continue
                
                if network_name not in current_macs:
                    current_macs[network_name] = {}
                current_macs[network_name][mac] = ip
            
            # Update tracked_macs in place with grace period
            for network_name in list(tracked_macs.keys()):
                # Mark all MACs as potentially missing
                for mac in tracked_macs[network_name]:
                    tracked_macs[network_name][mac]['missing_count'] = tracked_macs[network_name][mac].get('missing_count', 0) + 1
            
            # Process known MACs (don't enforce limits)
            for network_name, macs in current_known.items():
                if network_name not in tracked_macs:
                    tracked_macs[network_name] = {}
                for mac, ip in macs.items():
                    if mac in tracked_macs[network_name]:
                        # Update existing
                        tracked_macs[network_name][mac]['ip'] = ip
                        tracked_macs[network_name][mac]['missing_count'] = 0
                        tracked_macs[network_name][mac]['known'] = True
                    else:
                        # Add new known MAC
                        tracked_macs[network_name][mac] = {'ip': ip, 'blocked': False, 'known': True, 'missing_count': 0}
            
            # Re-evaluate all tracked MACs against current config to handle prefix changes
            for network_name in tracked_macs:
                for mac in list(tracked_macs[network_name].keys()):
                    # Check if this MAC should be known based on current config
                    should_be_known = is_allowed_prefix(mac, network_name)
                    tracked_macs[network_name][mac]['known'] = should_be_known
            
            # Process unknown MACs and enforce limits
            for network_name, macs in current_macs.items():
                if network_name not in tracked_macs:
                    tracked_macs[network_name] = {}
                
                for mac, ip in macs.items():
                    if mac in tracked_macs[network_name]:
                        # Update existing MAC
                        tracked_macs[network_name][mac]['ip'] = ip
                        tracked_macs[network_name][mac]['missing_count'] = 0
                        # Check if manually blocked
                        if is_manually_blocked(network_name, mac):
                            tracked_macs[network_name][mac]['blocked'] = True
                    else:
                        # New MAC - check if manually blocked or if limit reached
                        if is_manually_blocked(network_name, mac):
                            # Manually blocked - always block
                            tracked_macs[network_name][mac] = {'ip': ip, 'blocked': True, 'known': False, 'missing_count': 0}
                            policy_id = get_filter_policy_id(network_name)
                            if policy_id:
                                add_deny_rule(policy_id, mac)
                                cp.log(f"Blocked manually blocked MAC {mac} on {network_name}")
                        else:
                            # Check if limit reached
                            allowed_count = sum(1 for m in tracked_macs[network_name].values() 
                                              if not m.get('blocked', False) and not m.get('known', False) and m.get('missing_count', 0) < GRACE_PERIOD_CYCLES)
                            
                            max_unknown = network_config.get(network_name, {}).get('max_unknown', 0)
                            should_block = max_unknown > 0 and allowed_count >= max_unknown
                            
                            if should_block:
                                # Block new MAC
                                tracked_macs[network_name][mac] = {'ip': ip, 'blocked': True, 'known': False, 'missing_count': 0}
                                policy_id = get_filter_policy_id(network_name)
                                if policy_id:
                                    add_deny_rule(policy_id, mac)
                                    cp.log(f"Blocked MAC {mac} on {network_name} (limit: {max_unknown})")
                            else:
                                # Allow new MAC
                                tracked_macs[network_name][mac] = {'ip': ip, 'blocked': False, 'known': False, 'missing_count': 0}
            
            # Handle MACs that have been missing for grace period
            for network_name in list(tracked_macs.keys()):
                for mac in list(tracked_macs[network_name].keys()):
                    if tracked_macs[network_name][mac].get('missing_count', 0) >= GRACE_PERIOD_CYCLES:
                        # Keep blocked MACs (manual or auto) - deny rules stay active
                        if tracked_macs[network_name][mac].get('blocked', False):
                            continue
                        
                        # Remove unblocked MACs that disappeared
                        del tracked_macs[network_name][mac]
                        cp.log(f"Stopped tracking MAC {mac} on {network_name} (missing for {GRACE_PERIOD_CYCLES} cycles)")
            
            # Save state every cycle
            save_state()
            
            # Publish status for CLI access
            publish_status()
            
        except Exception as e:
            cp.log(f"Error in monitor_macs: {e}")
        
        time.sleep(2)


class WebHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging
    
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(self.get_html().encode())
        elif self.path == '/api/data':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            data = {'networks': tracked_macs, 'network_config': network_config, 'policy_status': network_policy_status, 'manual_blocks': manual_blocks}
            self.wfile.write(json.dumps(data).encode())
        elif self.path == '/api/config':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            # Get all LAN names in order from config/lan
            all_networks = []
            lans = cp.get('config/lan')
            if lans:
                for lan in lans:
                    name = lan.get('name')
                    if name:
                        all_networks.append(name)
            data = {'networks': all_networks, 'config': network_config}
            self.wfile.write(json.dumps(data).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == '/api/toggle':
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length).decode()
            data = json.loads(body) if body else {}
            
            network = data.get('network')
            mac = data.get('mac')
            
            if network and mac and network in tracked_macs and mac in tracked_macs[network]:
                current_blocked = tracked_macs[network][mac]['blocked']
                new_blocked = not current_blocked
                
                policy_id = get_filter_policy_id(network)
                if policy_id:
                    if new_blocked:
                        add_deny_rule(policy_id, mac)
                        set_manual_block(network, mac, True)
                    else:
                        remove_deny_rule(policy_id, mac)
                        set_manual_block(network, mac, False)
                    
                    tracked_macs[network][mac]['blocked'] = new_blocked
                    
                    # Recheck policy status
                    check_filter_policies()
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': True, 'blocked': new_blocked}).encode())
                    return
                else:
                    # Recheck policy status
                    check_filter_policies()
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': f'Filter policy not found for network: {network}'}).encode())
                    return
            
            self.send_response(400)
            self.end_headers()
        elif self.path == '/api/save_config':
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length).decode()
            data = json.loads(body) if body else {}
            
            global network_config
            network_config = data.get('config', {})
            
            # Check filter policies after config change
            check_filter_policies()
            
            # Save to appdata
            try:
                cp.put_appdata('network_config', json.dumps(network_config))
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True}).encode())
            except Exception as e:
                cp.log(f"Error saving config: {e}")
                self.send_response(500)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    
    def get_html(self):
        return '''<!DOCTYPE html>
<html data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Network MAC Filter</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
:root {
  --bg: #f5f5f5; --surface: #fff; --text: #333; --border: #ddd;
  --primary: #0066cc; --success: #28a745; --danger: #dc3545;
}
[data-theme="dark"] {
  --bg: #1a1a1a; --surface: #2d2d2d; --text: #e0e0e0; --border: #444;
}
body { font-family: system-ui, -apple-system, sans-serif; background: var(--bg); color: var(--text); padding: 20px; }
.container { max-width: 1200px; margin: 0 auto; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
h1 { font-size: 24px; }
.network { background: var(--surface); padding: 15px; border-radius: 4px; margin-bottom: 15px; border: 1px solid var(--border); }
.network h2 { font-size: 18px; margin-bottom: 10px; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 10px; text-align: left; border-bottom: 1px solid var(--border); }
th { font-weight: 600; }
.status { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
.status.allowed { background: var(--success); color: white; }
.status.blocked { background: var(--danger); color: white; }
.status.overlimit { background: #ff8c00; color: white; }
button { background: var(--primary); color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 14px; }
button:hover { opacity: 0.9; }
button:disabled { opacity: 0.5; cursor: not-allowed; }
.icon-btn { background: none; border: none; font-size: 20px; cursor: pointer; padding: 8px; }
.modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; }
.modal.show { display: flex; align-items: center; justify-content: center; }
.modal-content { background: var(--surface); padding: 20px; border-radius: 8px; max-width: 600px; width: 90%; max-height: 80vh; overflow-y: auto; }
.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.modal-header h2 { font-size: 20px; }
.close-btn { background: none; border: none; font-size: 24px; cursor: pointer; padding: 0; color: var(--text); }
.network-config { background: var(--bg); padding: 15px; border-radius: 4px; margin-bottom: 15px; }
.network-config h3 { font-size: 16px; margin-bottom: 10px; }
.form-group { margin-bottom: 10px; }
.form-group label { display: block; margin-bottom: 5px; font-weight: 600; }
.form-group input { width: 100%; padding: 8px; border: 1px solid var(--border); border-radius: 4px; background: var(--surface); color: var(--text); }
.save-btn { width: 100%; padding: 10px; font-size: 16px; }
.alert { position: fixed; top: 20px; right: 20px; background: var(--danger); color: white; padding: 15px 20px; border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); z-index: 2000; animation: slideIn 0.3s; }
@keyframes slideIn { from { transform: translateX(400px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
.policy-warning { background: #fff3cd; color: #856404; padding: 10px; border-radius: 4px; margin-bottom: 10px; border: 1px solid #ffeaa7; }
[data-theme="dark"] .policy-warning { background: #664d03; color: #ffecb5; border-color: #997404; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>Network MAC Filter</h1>
    <div>
      <button class="icon-btn" onclick="openSettings()">⚙️</button>
      <button class="icon-btn" onclick="toggleTheme()" id="themeBtn">🌙</button>
    </div>
  </div>
  <div id="networks"></div>
</div>
<div class="modal" id="settingsModal">
  <div class="modal-content">
    <div class="modal-header">
      <h2>Network Settings</h2>
      <button class="close-btn" onclick="closeSettings()">&times;</button>
    </div>
    <div id="networkSettings"></div>
    <button class="save-btn" onclick="saveSettings()">Save Settings</button>
  </div>
</div>
<script>
var theme = localStorage.getItem('theme') || 'light';
document.documentElement.setAttribute('data-theme', theme);

function toggleTheme() {
  theme = theme === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
  document.getElementById('themeBtn').textContent = theme === 'light' ? '🌙' : '☀️';
}

document.getElementById('themeBtn').textContent = theme === 'light' ? '🌙' : '☀️';

var networkConfig = {};

function openSettings() {
  fetch('/api/config').then(function(r) { return r.json(); }).then(function(data) {
    networkConfig = data.config || {};
    var html = '';
    for (var i = 0; i < data.networks.length; i++) {
      var network = data.networks[i];
      var config = networkConfig[network] || {max_unknown: 0, allowed_prefixes: []};
      var prefixes = config.allowed_prefixes ? config.allowed_prefixes.join(', ') : '';
      html += '<div class="network-config"><h3>' + network + '</h3>';
      html += '<div class="form-group"><label>Max Unknown (0 = no limit)</label><input type="number" id="max_' + i + '" value="' + config.max_unknown + '" min="0"></div>';
      html += '<div class="form-group"><label>Allowed MAC Prefixes (comma-separated)</label><input type="text" id="prefix_' + i + '" value="' + prefixes + '" placeholder="00:11:22, AA:BB:CC"></div>';
      html += '</div>';
    }
    document.getElementById('networkSettings').innerHTML = html;
    document.getElementById('settingsModal').className = 'modal show';
  });
}

function closeSettings() {
  document.getElementById('settingsModal').className = 'modal';
}

function saveSettings() {
  fetch('/api/config').then(function(r) { return r.json(); }).then(function(data) {
    var newConfig = {};
    for (var i = 0; i < data.networks.length; i++) {
      var network = data.networks[i];
      var maxHosts = parseInt(document.getElementById('max_' + i).value) || 0;
      var prefixStr = document.getElementById('prefix_' + i).value;
      var prefixes = [];
      if (prefixStr) {
        var parts = prefixStr.split(',');
        for (var j = 0; j < parts.length; j++) {
          var clean = parts[j].replace(/[^0-9A-Fa-f]/g, '').toUpperCase();
          if (clean.length >= 6) {
            prefixes.push(clean.substring(0, 6));
          }
        }
      }
      newConfig[network] = {max_unknown: maxHosts, allowed_prefixes: prefixes};
    }
    fetch('/api/save_config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({config: newConfig})
    }).then(function() {
      closeSettings();
      loadData();
    });
  });
}

function toggleMAC(network, mac) {
  fetch('/api/toggle', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({network: network, mac: mac})
  }).then(function(r) { return r.json(); }).then(function(result) {
    if (result.success === false) {
      showAlert(result.error);
    } else {
      loadData();
    }
  });
}

function showAlert(message) {
  var alert = document.createElement('div');
  alert.className = 'alert';
  alert.textContent = message;
  document.body.appendChild(alert);
  setTimeout(function() {
    document.body.removeChild(alert);
  }, 4000);
}

function loadData() {
  fetch('/api/data').then(function(r) { return r.json(); }).then(function(data) {
    fetch('/api/config').then(function(r) { return r.json(); }).then(function(configData) {
      var html = '';
      var networks = configData.networks;
      
      for (var n = 0; n < networks.length; n++) {
        var network = networks[n];
        var macs = data.networks[network] || {};
        var macList = Object.keys(macs);
        var config = data.network_config[network] || {max_unknown: 0, allowed_prefixes: []};
        var hasPolicy = data.policy_status[network];
        
        var knownCount = 0;
        var unknownCount = 0;
        for (var i = 0; i < macList.length; i++) {
          if (macs[macList[i]].known) {
            knownCount++;
          } else {
            unknownCount++;
          }
        }
        
        var limit = config.max_unknown > 0 ? config.max_unknown : 'unlimited';
        var prefixes = config.allowed_prefixes.length ? config.allowed_prefixes.join(', ') : 'None';
        
        html += '<div class="network"><h2>' + network + ' (' + knownCount + ' known MACs - ' + unknownCount + ' of ' + limit + ' unknown MACs)</h2>';
        
        if (!hasPolicy) {
          html += '<div class="policy-warning"><strong>⚠️ Warning:</strong> Filter policy not found for this network. Create a Zone-Based Firewall filter policy named "' + network + '" to enable MAC filtering.</div>';
        }
        
        html += '<div style="margin-bottom:10px"><strong>Prefixes:</strong> ' + prefixes + '</div>';
        
        if (macList.length === 0) {
          html += '<div>No MAC addresses tracked</div></div>';
          continue;
        }
        
        html += '<table><thead><tr><th>MAC Address</th><th>IP Address</th><th>Prefix</th><th>Status</th><th>Action</th></tr></thead><tbody>';
        
        for (var i = 0; i < macList.length; i++) {
          var mac = macList[i];
          var info = macs[mac];
          var isManualBlock = data.manual_blocks[network] && data.manual_blocks[network][mac];
          var status = '';
          var statusClass = '';
          var action = '';
          
          if (info.blocked) {
            if (isManualBlock) {
              status = 'BLOCKED';
              statusClass = 'blocked';
              action = 'Allow';
            } else {
              status = 'OVER LIMIT';
              statusClass = 'overlimit';
              action = 'Allow';
            }
          } else {
            status = 'ALLOWED';
            statusClass = 'allowed';
            action = 'Block';
          }
          
          var prefix = info.known ? 'Known' : 'Unknown';
          var disabled = hasPolicy ? '' : ' disabled';
          html += '<tr><td>' + mac + '</td><td>' + info.ip + '</td><td>' + prefix + '</td><td><span class="status ' + statusClass + '">' + status + '</span></td><td><button' + disabled + ' onclick="toggleMAC(&quot;' + network + '&quot;,&quot;' + mac + '&quot;)">' + action + '</button></td></tr>';
        }
        
        html += '</tbody></table></div>';
      }
      
      document.getElementById('networks').innerHTML = html || '<div class="network">No networks configured</div>';
    });
  });
}

loadData();
setInterval(loadData, 2000);
</script>
</body>
</html>'''


def start_web_server():
    """Start web server in background thread."""
    global web_port
    
    try:
        os.makedirs('tmp', exist_ok=True)
        server = HTTPServer(('', web_port), WebHandler)
        server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        cp.log(f"Web server started on port {web_port}")
        server.serve_forever()
    except Exception as e:
        cp.log(f"Error starting web server: {e}")


def main():
    global network_config, web_port
    
    cp.log("Starting network_mac_filter")
    
    # Load saved state first (needed for cleanup decisions)
    load_state()
    load_manual_blocks()
    
    # Load configuration from appdata (needed for known-prefix detection during cleanup)
    try:
        config_str = cp.get_appdata('network_config')
        if config_str:
            network_config = json.loads(config_str)
            cp.log(f"Loaded network config: {len(network_config)} networks")
    except Exception as e:
        cp.log(f"Error loading network_config: {e}")
    
    # Clean up deny rules for non-known MACs and flush tracking
    cleanup_orphaned_deny_rules()
    
    # Check filter policies on startup
    check_filter_policies()
    
    try:
        port_str = cp.get_appdata('custom_mac_filter_port')
        if port_str:
            web_port = int(port_str)
    except Exception as e:
        cp.log(f"Error loading custom_mac_filter_port: {e}")
    
    # Start web server in background (unless disabled via appdata)
    disable_ui = cp.get_appdata('disable_ui')
    if disable_ui:
        cp.log("Web UI disabled via appdata")
    else:
        web_thread = threading.Thread(target=start_web_server, daemon=True)
        web_thread.start()
    
    # Register control callbacks for CLI block/unblock
    register_control_callbacks()
    
    # Start monitoring
    monitor_macs()


if __name__ == '__main__':
    main()
