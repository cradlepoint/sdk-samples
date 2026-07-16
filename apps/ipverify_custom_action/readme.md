# ipverify_custom_action
Registers a callback function that triggers when an IP Verify test status changes. The included example monitors an ICMP ping test over an IPsec VPN tunnel and restarts the VPN service when the test fails.

## How It Works

1. The app waits for an IP Verify identity to be configured on the router
2. It registers a callback on `status/ipverify/{uid}/pass` using `cp.register()`
3. When the IP Verify test fails (value becomes `False`), the callback fires
4. The callback disables and re-enables VPN to restart the tunnel

## Use Case

IP Verify runs periodic connectivity tests (ICMP ping, HTTP, DNS). When a test fails, it typically means the network path is broken. This app extends that by taking a custom remediation action — in this case, restarting the VPN tunnel to force re-establishment.

## Customizing the Action

Edit the `custom_action()` function to perform any action on IP Verify failure:

```python
def custom_action(path, value, *args):
    if not value:  # Test has failed
        cp.log('IP Verify test failed - taking action')
        # Your custom logic here
```

Examples of custom actions:
- Restart a VPN tunnel (included example)
- Reset a modem
- Send an alert via `cp.alert()`
- Toggle a GPIO pin
- Switch WAN priority

## Requirements

- At least one IP Verify identity configured on the router
- Router firmware 7.26 or later
- For the VPN example: an IPsec tunnel configured that the IP Verify test monitors

## Configuration

No SDK appdata required. The app automatically monitors the first IP Verify identity found at `config/identities/ipverify/0/_id_`.

## Sample Log Output

```
Starting...
Watching ipverify test abc12345-def6-7890-ghij-klmnopqrstuv
VPN Monitor Failed - Restarting Tunnel.
```
