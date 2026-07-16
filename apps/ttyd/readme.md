# ttyd
Runs a Linux bash shell in a web browser on port 8022. Think of it as web-SSH for your router — access a full bash terminal from any browser on the LAN without needing an SSH client.

## How It Works

The app bundles the [ttyd](https://github.com/tsl0922/ttyd) binary, which serves a terminal emulator over HTTP using WebSockets. When the app starts, it launches ttyd on port 8022 with bash as the default shell.

The start.sh script launches:
```bash
ttyd -p 8022 bash
```

## Steps to Use

1. Install and start the app on the router
2. Ensure a firewall zone forwarding rule exists from LAN zone to Router zone
3. Open a browser and navigate to `http://<router_ip>:8022`
4. A bash terminal session opens in the browser

## Use Cases

- Remote troubleshooting without an SSH client
- Quick access to router shell from any device with a browser
- Running diagnostic commands (tcpdump, ifconfig, route, etc.)
- Inspecting SDK app files and logs on the router filesystem

## Security Considerations

- Anyone with LAN access can open a shell — consider limiting access via firewall rules
- The terminal runs as the app user (`cpshell`) with restricted permissions
- Do not expose port 8022 to the WAN without additional authentication

## Port

| Port | Protocol | Service |
|------|----------|---------|
| 8022 | HTTP/WebSocket | ttyd terminal |

## Requirements

- Router firmware 7.26 or later
- Router model with ARM64 (aarch64) architecture (the bundled binary is platform-specific)
- Firewall zone forwarding from LAN to Router zone for browser access
- Modern web browser with WebSocket support
