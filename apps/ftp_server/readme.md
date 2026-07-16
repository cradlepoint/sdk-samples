# ftp_server
Starts an FTP server on port 2121 using the `pyftpdlib` library. Serves files from USB storage mounted at `/var/media` on the router, allowing file transfers to and from a USB drive connected to the router.

## How It Works

The app uses `pyftpdlib` to run a full-featured FTP server on the router. It listens on port 2121 (SDK apps cannot use ports below 1024) and serves files from the router's USB storage mount point.

When running outside the router (e.g., for local testing), it serves files from the current working directory.

## Configuration

| Setting | Value |
|---------|-------|
| Listen address | `0.0.0.0:2121` |
| Serve directory | `/var/media` (USB storage) |
| Max connections | 256 |
| Max connections per IP | 5 |

## Credentials

| Username | Password | Permissions |
|----------|----------|-------------|
| `user` | `12345` | Full read/write (`elradfmwM`) |
| `anonymous` | (none) | Read-only |

For production use, change the default credentials in the source code.

## USB Storage Requirement

A USB-compatible storage device must be plugged into the router. It mounts at `/var/media`. If no USB device is present, the FTP server will fail to start or serve an empty directory.

## Firewall Configuration

Port 2121 must be allowed through the router's zone firewall for external clients to connect. Add an inbound allow rule for TCP port 2121 on the appropriate zone (typically the LAN zone, or WAN if remote access is needed).

## Connecting to the Server

```
ftp router-ip 2121
```

Or from an FTP client application, specify port 2121 when connecting.

## Requirements

- Router firmware 7.26 or later
- USB storage device connected to the router
- `pyftpdlib`, `asynchat.py`, and `asyncore.py` (included in app directory)
- Firewall rule allowing TCP port 2121

## Notes

- The server runs continuously until the app is stopped
- SDK apps can only bind to ports above 1024
- The `restart` flag is set to false — if the server crashes, it will not auto-restart
