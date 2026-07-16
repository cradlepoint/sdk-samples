# mqtt_azure_tls
Communicates directly with Microsoft Azure IoT Hub using MQTT over TLS (port 8883), without the Azure IoT SDK. Publishes router data (system ID, product name, modem temperature) to IoT Hub and subscribes to cloud-to-device messages.

Based on the [MS Azure MQTT support documentation](https://github.com/MicrosoftDocs/azure-docs/blob/master/articles/iot-hub/iot-hub-mqtt-support.md) — refer to section "Using the MQTT protocol directly".

## How It Works

1. Connects to Azure IoT Hub via MQTT over TLS (port 8883)
2. Authenticates using a SAS token and IoT Hub root CA certificates
3. Subscribes to the device's cloud-to-device message topic
4. Reads router data (system ID, product name, temperature) via `cp.get()`
5. Publishes the data to the device's events topic
6. Runs the MQTT loop to receive incoming messages

## Configuration

Edit these variables at the top of `mqtt_azure_tls.py`:

| Variable | Description |
|----------|-------------|
| `iot_hub_name` | Your Azure IoT Hub name (without `.azure-devices.net`) |
| `device_id` | The device identity registered in your IoT Hub |
| `sas_token` | A Shared Access Signature token for the device |

### SAS Token Format

```
SharedAccessSignature sr={hub_name}.azure-devices.net%2Fdevices%2F{device_id}%2Fapi-version%3D2016-11-14&sig=...&se=...
```

Generate a SAS token using the Azure Device Explorer Tool or Azure CLI.

## Certificate Setup

The app includes a `certs.cer` file containing the Azure IoT Hub root CA certificates. These were sourced from the [Azure IoT SDK C certs](https://github.com/Azure/azure-iot-sdk-c/blob/master/certs/certs.c).

## Published Data

The app publishes a URL-encoded payload containing:
- `router_id` — Router system ID
- `product_name` — Router model name
- `router_temperature` — Modem temperature (if available)

## Requirements

- Router firmware 7.26 or later
- Microsoft Azure IoT Hub with a registered device
- SAS token for the device (generated via Device Explorer or Azure CLI)
- Network connectivity to `{iot_hub_name}.azure-devices.net` on port 8883
- `paho-mqtt` library (included in app directory)

## Testing with Azure Device Explorer

Use the [Azure IoT Device Explorer Tool](https://github.com/Azure/azure-iot-sdk-csharp/tree/main/tools/DeviceExplorer) to:
- Generate SAS tokens for your device
- Monitor messages received from the device
- Send cloud-to-device messages to the device

## Sample Log Output

```
Device connected with result code: 0
Device sent message.
Device received topic: devices/MyDevice/messages/devicebound/..., msg: b'Hello from cloud'
```
