# mqtt_app
A full MQTT example using the Paho library. Connects to an MQTT broker, subscribes to topics, and periodically publishes router data (GPS, system info) to those topics.

Reference: https://www.eclipse.org/paho/clients/python/docs/

## How It Works

1. Connects to the MQTT broker defined in `settings.py`
2. Subscribes to configured topics with QoS 1
3. Runs a background publish thread that sends router data at a configurable interval
4. Logs all messages received on subscribed topics

The app uses the router's `system_id` as the MQTT client ID and sets a Last Will message so the broker can notify subscribers if the client disconnects unexpectedly.

## Configuration

All settings are defined in `settings.py`:

| Setting | Description |
|---------|-------------|
| `MQTT_SERVER` | Broker hostname or IP (default: `test.mosquitto.org`) |
| `MQTT_PORT` | Broker port (default: `1883`) |
| `PUBLISH_INTERVAL` | Seconds between publish cycles (default: `10`) |
| `topics` | Dictionary mapping topic names to router data paths |

### Topics Format

Topics are defined as a nested dictionary where keys are topic names, values are dictionaries mapping field labels to NCOS API paths:

```python
topics = {
    'my/topic': {
        'System ID': 'config/system/system_id',
        'WAN IP': 'status/wan/ipinfo/ip_address',
    }
}
```

## Features

- Automatic reconnection and subscription renewal on disconnect
- QoS 1 for reliable message delivery
- Last Will and Testament (LWT) for disconnect notification
- Threaded architecture — MQTT loop and publishing run independently
- Logs all connection, subscription, publish, and message events

## Sample Output

```
Start MQTT Client
MQTT connect reply to test.mosquitto.org, 1883: Connection Accepted.
Subscribe response: Message ID=1, granted_qos=(1, 1)
Publish response: Message ID=2
Published msg received. topic: my/topic, msg: b'System ID: MyRouter'
```

## Requirements

- Router firmware 7.26 or later
- Network connectivity to the MQTT broker
- `paho-mqtt` library (included in app directory)
- For production: a private MQTT broker (the test server is public and unreliable)

## Notes

- The test server `test.mosquitto.org` is for demonstration only — do not use for production
- Modify `settings.py` to point to your own broker and customize topics/data paths
