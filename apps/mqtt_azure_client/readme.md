# mqtt_azure_client
Sample application that uses the SDK to bridge sensor data to Microsoft Azure IoT Central. Connects to a local MQTT broker (acting as an Azure IoT Central bridge) and publishes telemetry, properties, and handles cloud-to-device commands.

## How It Works

The app connects to a local MQTT broker that bridges to Azure IoT Central. It:

1. Connects to the broker at the configured IP and port
2. Subscribes to device twin, desired property, and direct method topics
3. Publishes simulated temperature sensor measurements every 15 seconds
4. Reports device properties (firmware version) every 30 seconds
5. Responds to cloud-to-device commands and desired property changes

## Architecture

```
[Sensor Data] → [This App] → [Local MQTT Broker] → [Azure IoT Central]
                                    ↕
                            [Commands/Settings]
```

The local broker handles the Azure IoT Central protocol translation, allowing this app to use simple MQTT topics instead of the full Azure IoT SDK.

## Configuration

Edit the constants at the top of `mqtt_azure_client.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `BROKER_IP` | `192.168.0.1` | IP address of the MQTT-to-Azure bridge broker |
| `BROKER_PORT` | `9898` | Port of the bridge broker |

## MQTT Topics

| Topic | Direction | Purpose |
|-------|-----------|---------|
| `measurement/` | Publish | Send telemetry data |
| `property/?rid=<id>` | Publish | Report device properties |
| `twin_resp/#` | Subscribe | Receive device twin responses |
| `setting/#` | Subscribe | Receive desired property changes |
| `command_sub/#` | Subscribe | Receive direct method invocations |
| `command_pub/<status>/?$rid=<id>` | Publish | Respond to direct methods |

## Sample Telemetry Payload

```json
{"temp_sensor_val": 35, "temp_state": "On", "temp_alert": "Temp High Alert"}
```

## Requirements

- Router firmware 7.26 or later
- An MQTT-to-Azure IoT Central bridge running at the configured IP/port
- Azure IoT Central application configured with a matching device template
- `paho-mqtt` library (included in app directory)

## Notes

- The sample uses simulated temperature data — replace with real sensor readings for production
- The bridge broker must be set up separately (not included in this app)
- Device twin, settings, and command callbacks demonstrate the full Azure IoT Central feature set
