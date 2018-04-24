Application Name
================
mqtt_app


Application Version
===================
1.0


NCOS Devices Supported
======================
ALL


External Requirements
=====================
MQTT test server test.mosquitto.org is used for
demonstrations. A real MQTT server will be required
for a productions application.


Application Purpose
===================
An MQTT App example using the paho library.
Reference: https://www.eclipse.org/paho/clients/python/docs/

This app does the following:
- Connects to MQTT test server ‘test.mosquitto.org’
- Subscribes to topics as defined in settings.py.
- Runs a background thread which publishes data to the topics defined in settings.py every 10 secs.
- Generates a log when the MQTT server sends the published information for topics subscribed.


Expected Output
===============
Logs will be output for MQTT messages sent and received.

