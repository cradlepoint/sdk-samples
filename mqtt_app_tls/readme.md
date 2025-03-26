# mqtt_app_tls  

## Overview
This application demonstrates secure MQTT communication using TLS certificates. It connects to an MQTT broker, subscribes to configured topics, and publishes device data at regular intervals.  

[**Download Built App**](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/mqtt_app_tls.tar.gz) 

## Features
- Secure MQTT connection using TLS certificates
- Automatic subscription to configured topics
- Periodic publishing of device data
- Automatic reconnection handling
- Last Will and Testament (LWT) message support

## Configuration
The application uses settings defined in `settings.py` (not shown), which should include:

- `MQTT_SERVER`: MQTT broker hostname
- `MQTT_PORT`: MQTT broker port
- `MQTT_CA_CERT`: CA certificate path
- `MQTT_CLIENT_CERT`: Client certificate path
- `MQTT_CLIENT_KEY`: Client private key path
- `PUBLISH_INTERVAL`: Time interval between publications
- `topics`: Dictionary of topics to subscribe to and publish

## Topic Configuration
Topics are configured as a dictionary where:
- Keys are the topic names
- Values are dictionaries containing data paths to publish

Example configuration:
```python
topics = {
    "device/data": {
        "temperature": "/sensors/temperature",
        "humidity": "/sensors/humidity"
    }
}
```

## Quality of Service (QoS) Levels
The application supports different QoS levels:
- QoS 0: At most once delivery
- QoS 1: At least once delivery (used for subscriptions)
- QoS 2: Exactly once delivery (used for Last Will messages)

## Security
The application implements TLS 1.2 security with:
- CA certificate verification
- Client certificate authentication
- Client private key encryption

## Logging
The application logs important events such as:
- Connection status
- Message publications
- Subscription confirmations
- Errors and exceptions

## Error Handling
The application includes comprehensive error handling for:
- Connection failures
- Publication errors
- Subscription issues
- File operations
- Certificate handling

## Background Operation
The application runs two main threads:
1. MQTT client thread for handling connections and subscriptions
2. Publishing thread for periodic data transmission
