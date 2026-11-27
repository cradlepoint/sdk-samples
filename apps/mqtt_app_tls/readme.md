# mqtt_app_tls  
This application demonstrates secure MQTT communication using TLS certificates. It connects to an MQTT broker, subscribes to configured topics, and publishes device data at regular intervals.

## Features
- Secure MQTT connection (TLS 1.2), using certificates from NCOS Certificate Manager
- Automatic subscription to configured topics
- Periodic publishing of device data over the same TLS connection
- Automatic reconnection handling, including when the first connection fails
- Last Will and Testament (LWT) message support

## Configuration
The application does not read SDK Data. All settings are constants in `settings.py`, which ships with the app. Edit that file and rebuild the app to change them:

- `MQTT_SERVER`: MQTT broker hostname (shipped value: `test.mosquitto.org`)
- `MQTT_PORT`: MQTT broker port (shipped value: `8884`, the test broker's TLS client-certificate port)
- `MQTT_CA_CERT`: Name of the CA certificate in NCOS Certificate Manager (shipped value: `Mosquitto CA`). Required
- `MQTT_CLIENT_CERT`: Name of the client certificate in NCOS Certificate Manager (shipped value: `Mosquitto Client`)
- `MQTT_CLIENT_KEY`: Name of the client private key in NCOS Certificate Manager (shipped value: `Mosquitto Key`)
- `PUBLISH_INTERVAL`: Seconds between publications (shipped value: `10`)
- `topics`: Dictionary of topics to subscribe to and publish

Certificate names must match the names in the router's Certificate Manager. The app looks up all three names at startup. If the client certificate or key name is not found, the app logs `Certificate "<name>" not found` and connects without a client certificate, which only works if the broker does not require one. If the CA certificate is not found, the app passes no CA file to the TLS setup, which then falls back to the default system CA store and verifies the broker against that. A broker with a private CA will not be trusted, so treat the CA as required.

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
- QoS 1: At least once delivery (used for subscriptions and for the periodic publishes)
- QoS 2: Exactly once delivery (used for the Last Will message, sent by the broker to `/will/oops` if the client disappears)

## Security
The application implements TLS 1.2 security with:
- CA certificate verification
- Client certificate authentication, when the client certificate and key are found in Certificate Manager

Subscriptions and the periodic publishes share one TLS connection. The publishes are sent through the connected client, so they are never sent without TLS. If the client is not connected, the app logs `MQTT client not connected yet. Waiting to publish.` and tries again after the next interval.

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
The application runs two loops:
1. An MQTT client thread for handling the connection, subscriptions, and reconnects. If the broker cannot be reached (broker down, no route yet, certificate missing, or a TLS handshake failure), it logs the error and tries again after 10 seconds, doubling the wait up to 60 seconds. Each retry builds a new client and reads the certificates again, so a certificate uploaded after the app started is picked up on the next try. After a connection that worked, the wait starts over at 10 seconds
2. The periodic publishing loop, which runs on the main thread. It waits the full publish interval after every pass, including after an error, so a failure never turns into a rapid retry loop
