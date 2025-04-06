# tailscale

## NCOS Devices Supported
ALL

## Application Purpose
[Tailscale](https://tailscale.com) is a mesh VPN that makes it easy to connect your devices, wherever they are. This application provides a way to proxy traffic from the LAN to the Tailscale network.

## Notes
Tailscale can function as a fully L3 routed VPN, but as a Cradlepoint app, it can only run as a proxy. In other words. This app uses the `userspace-networking`. It also exposes a SOCKS5 proxy on port 1055, which can be used to proxy traffic directed to it to another device on the tailscale network.  Also incoming traffic from tailscale to the LAN is possible. This sdk app automatically adds the lan networks as routes to the tailscale network.

## Security Notice
Depending on the tailscale network configuration. This app can expose the router to any device on the tailscale network. It is recommended to use the Access Controls feature in tailscale to limit access to the router.

## Usage
It is assumed that a tailscale account is already created. Log into the account and navitage to the admin console. Create a new key under Settings->Keys and then "Generate auth key". Generate a 90 day reusable key, and confgiure the tags as desired. Click "Generate key" and be sure to copy the tskey-auth code as shown.

![generate_auth_key](https://github.com/cradlepoint/sdk-samples/assets/59579399/67c243b4-78da-482c-a5e5-ee01d33c2228)

Next, add the tailscale app as an SDK app in your Cradlepoint ncm account. Add the SDK to a new group (see https://docs.cradlepoint.com/r/NetCloudOS-SDK-Sample-Apps-Quick-Start-Guide for more details)

Configure the group, navigate to System->SDK Appdata, and add a new key value pair with tskey as the key and the tskey-auth code as the value.

![app data](https://github.com/cradlepoint/sdk-samples/assets/59579399/4d785b56-ede7-43bf-9462-f76a7ba4d6ac)

The router will automatically download tailscale and use the key to authenticate. The router's hostname should show up in the list of tailscale machines.

![machines](https://github.com/cradlepoint/sdk-samples/assets/59579399/d47d8bcb-e8ab-45ce-858d-9f32c6011a18)

## Other Settings
You can configure the tailscale version, add additional routes if you would like.
For example:

| Name | Value | Notes |
| ---- | ----- | ----- |
| tsroutes | 172.16.0.0/12 | Manually add a tailscale routes, comma separated
| tsversion | 1.60.1 | Use this version of tailscale explicitly
| tshostname | myhostname | use this hostname instead of the router's system id
| tstags | example | request these tags to use for this device
| tsserver | https://headscale.example.com | Enable use of self-hosted login server such as [Headscale](https://headscale.net/)

## Overlapping subnets
You can use tailscales 4via6 feature if you would like to get to devices behind a Cradlepoint routers that might share the same subnet.  First come up with a site id you would like to use (0-65535). Then from a computer with tailscale installed execute: `tailscale debug via [site-id] [subnet]`. For example: `tailscale debug via 1 172.16.0.0/12` should generate a 4via6 subnet of `fd7a:115c:a1e0:b1a:0:1:ac10:0/108`. Add this as a tsroute above and you can access the network via ipv6 or by the domain name following the format `Q-R-S-T-via-X` where Q-R-S-T is the ipv4 address and X is the site id, e.g.: `172-16-0-1-via-1`.
