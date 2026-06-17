# mqtt_app
An MQTT App example using the paho library.

Reference: https://www.eclipse.org/paho/clients/python/docs/

## Requirements

MQTT test server `test.mosquitto.org` is used for demonstrations. A real MQTT server will be required for a production application.

## What It Does

- Connects to MQTT test server `test.mosquitto.org`
- Subscribes to topics as defined in `settings.py`
- Runs a background thread which publishes data to the topics defined in `settings.py` every 10 seconds
- Generates a log when the MQTT server sends the published information for topics subscribed

## Expected Output

Logs will be output for MQTT messages sent and received.
