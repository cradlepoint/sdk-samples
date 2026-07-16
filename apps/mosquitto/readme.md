# mosquitto
Starts the NCOS-native Mosquitto MQTT broker using the included `mosquitto.conf` configuration file. This is not a Python application — it runs the `mosquitto` binary directly from `start.sh`.

## How It Works

The app's `start.sh` script launches the Mosquitto MQTT broker daemon with the bundled configuration file:

```bash
mosquitto --config-file mosquitto.conf --daemon
```

The router's NCOS firmware includes the Mosquitto binary. This app simply provides a configuration file and starts the broker as an SDK-managed service.

## Configuration

The included `mosquitto.conf` contains the full default Mosquitto configuration with comments explaining each option. Key settings to customize:

| Setting | Default | Description |
|---------|---------|-------------|
| `port` | 1883 | MQTT listener port |
| `allow_anonymous` | true | Whether unauthenticated clients can connect |
| `max_connections` | -1 (unlimited) | Maximum client connections |
| `persistence` | false | Save messages to disk |

Edit `mosquitto.conf` to change the broker behavior (e.g., add TLS, set up authentication, configure persistence).

## Use Cases

- Local MQTT broker for IoT sensor data collection on the router
- Bridge between local devices and cloud MQTT services
- Internal message bus for other SDK apps running on the same router

## Requirements

- Router firmware 7.26 or later with Mosquitto binary available
- Port 1883 (or configured port) not in use by another service

## Connecting to the Broker

From other SDK apps on the same router:
```python
import paho.mqtt.client as mqtt
client = mqtt.Client()
client.connect('127.0.0.1', 1883)
```

From LAN clients (requires firewall zone forwarding from LAN to Router zone):
```
mqtt://router-ip:1883
```

## Notes

- The broker runs as a daemon process managed by the SDK framework
- `restart` is set to false — if Mosquitto crashes, it will not auto-restart
- For TLS support, configure the certificate paths in `mosquitto.conf`
