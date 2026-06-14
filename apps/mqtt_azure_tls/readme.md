# mqtt_azure_tls

![Python](https://img.shields.io/badge/Python-3.8-yellow)

Communicates with MS Azure IoT Hub using MQTT directly without the use of the IoT Hub SDK. Developed based on the [MS Azure MQTT support documentation](https://github.com/MicrosoftDocs/azure-docs/blob/master/articles/iot-hub/iot-hub-mqtt-support.md) — refer to section "Using the MQTT protocol directly".

## Requirements

- MS Azure IoT Hub and Device configured
- MS Azure Shared Access Signature Token for the device
- MS Azure Device Explorer Tool is helpful for testing

## Expected Output

NCOS logs will be output when a message is sent to IoT Hub or when a message is received from the IoT Hub. The MS Azure Device Explorer Tool can be used to send messages and monitor received messages for the device.
