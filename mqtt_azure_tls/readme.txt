Application Name
================
mqtt_azure_tls


Application Version
===================
1.0


NCOS Devices Supported
======================
ALL


External Requirements
=====================
- MS Azure IoT Hub and Device configured.
- MS Azure Shared Access Signature Token for the device.
- MS Azure Device Explorer Tool is helpful for testing.


Application Purpose
===================
This application will communicate with MS Azure IoT Hub using MQTT directly without the use of the IoT Hub SDK.
It was developed based on MS Azure document from here:
    https://github.com/MicrosoftDocs/azure-docs/blob/master/articles/iot-hub/iot-hub-mqtt-support.md

Refer to section 'Using the MQTT protocol directly'.


Expected Output
===============
NCOS logs will be output when a message is sent to IoT Hub or when a message is received from the IoT Hub.
The MS Azure Device Explorer Tool can be used to send messages and monitor received messages for the device.

