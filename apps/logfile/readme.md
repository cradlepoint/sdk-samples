# logfile
Writes router syslog messages to persistent files on flash storage, available for download via HTTP on port 8000. Access logs through NCM Remote Connect (LAN Manager) or by forwarding the LAN zone to the Router zone for direct local access.

![image](https://github.com/cradlepoint/sdk-samples/assets/7169690/962df5a3-8793-4386-8cf0-1cf7fd3b3b5a)

## How It Works

The app tails `/var/log/messages` and writes each line to a timestamped log file stored in a `logs/` directory within the app. Log filenames include the router's MAC address and creation timestamp:

```
Log - 0030443B3877.2022-11-11 09:52:25.txt
```

When a log file reaches the maximum size, a new file is started. When the number of backup files exceeds the limit, the oldest file is deleted.

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `max_file_size` | 100 MB | Maximum size per log file before rotation |
| `backup_count` | 10 | Maximum number of log files to keep |

To change these values, edit the variables at the top of `logfile.py`.

## Accessing Log Files

### Via NCM Remote Connect (recommended)
1. Open NCM and navigate to the device
2. Use LAN Manager to connect to `127.0.0.1` port `8000` over HTTP
3. Browse and download log files

### Via Local LAN Access
1. Add a firewall zone forwarding rule from Primary LAN Zone to Router Zone
2. Browse to `http://<router_ip>:8000`
3. Download log files directly

## Log Format

Timestamps in the original syslog are converted to human-readable format:
```
2022-11-11 09:52:25 daemon.info ...
```

## Features

- Persistent storage — logs survive reboots (stored on flash)
- Automatic rotation — old logs are deleted when backup count is exceeded
- Timestamped filenames — easy to identify when logs were captured
- HTTP access — download via browser, no SSH needed
- MAC-identified — filenames include router MAC for easy identification

## Requirements

- Router firmware 7.26 or later
- Port 8000 accessible (via Remote Connect or zone forwarding)
