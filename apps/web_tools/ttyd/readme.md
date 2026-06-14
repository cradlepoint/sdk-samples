Application Name
================
ttyd

[Download the built app from our releases page!](https://github.com/cradlepoint/sdk-samples/releases/tag/built_apps)


Application Purpose
===================
ttyd runs a Linux bash shell in a web browser on port 8022. Think of it as web-SSH for your router — access a full bash terminal from any browser on the LAN without needing an SSH client.


How It Works
============
The app bundles the [ttyd](https://github.com/tsl0922/ttyd) binary, which serves a terminal emulator over HTTP using WebSockets. When the app starts, it launches ttyd on port 8022 with bash as the default shell.


Steps to Use
============
1. Install and start the app on the router.
2. Open a browser and navigate to `http://<router_ip>:8022`
3. A bash terminal session will open in the browser.


Notes
=====
- Port: 8022
- The app auto-starts and restarts on failure (configured in package.ini).
- Requires firmware 7.26 or newer.
