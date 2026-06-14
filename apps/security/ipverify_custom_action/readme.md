# ipverify_custom_action

![Python](https://img.shields.io/badge/Python-3.8-yellow)

Creates a custom action in a function to be called when an IPverify test status changes. The provided example is for use with IPVerify ICMP ping test over IPSec tunnel — when it fails, the app will restart IPsec.

## Expected Output

```
VPN Monitor Failed - Restarting Tunnel.
```

(when test fails)
