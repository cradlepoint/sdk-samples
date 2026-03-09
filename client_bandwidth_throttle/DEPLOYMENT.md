# Client Bandwidth Throttle - Deployment Summary

## ✅ Application Successfully Deployed

**App Name:** client_bandwidth_throttle  
**Version:** 1.0.0  
**Status:** Running  
**Web Interface:** http://192.168.1.4:8000

## Features

✓ Real-time client monitoring  
✓ Per-client bandwidth limits (default: 10 Mbps)  
✓ Auto-refresh dashboard (5 seconds)  
✓ QoS-based throttling  

## Quick Start

1. **Access Dashboard:** Open http://192.168.1.4:8000 in your browser
2. **View Clients:** See all connected LAN clients with hostname, IP, and MAC
3. **Set Limits:** Enter bandwidth limit (1-1000 Mbps) and click "Set"
4. **Monitor:** Dashboard auto-refreshes to show current limits

## Technical Details

- **Port:** 8000
- **QoS Queues:** Named `CBT-{MAC_ADDRESS}` for each client
- **Default Limit:** 10 Mbps (upload and download)
- **Auto-enables QoS** if not already active

## Firewall Note

If accessing from LAN clients, add firewall rule:
- Zone: LAN → Router
- Protocol: TCP
- Port: 8000
- Action: Allow

## Files Created

- `client_bandwidth_throttle/client_bandwidth_throttle.py` - Main application
- `client_bandwidth_throttle/readme.md` - Documentation
- `client_bandwidth_throttle/package.ini` - App metadata
- `client_bandwidth_throttle/start.sh` - Startup script
- `client_bandwidth_throttle/cp.py` - CP module

## Management Commands

```bash
# Check status
python3 make.py status client_bandwidth_throttle

# Stop app
python3 make.py stop client_bandwidth_throttle

# Start app
python3 make.py start client_bandwidth_throttle

# Redeploy after changes
bash deploy.sh client_bandwidth_throttle
```
