# ibr1700_obdII
Demonstrates how to subscribe to OBD-II vehicle diagnostic PIDs via the IBR1700's internal MQTT broker. The app receives real-time vehicle data (speed, RPM, fuel level, etc.) and logs it.

## How It Works

The IBR1700 router with an OBD-II adapter publishes vehicle diagnostic data to an internal MQTT broker. This app connects to that broker and subscribes to all available OBD-II PID topics. When PID values are published, the app's callback logs the topic and payload.

## Supported PIDs

The app subscribes to 33 OBD-II PIDs including:

- Vehicle speed, engine speed (RPM), throttle position
- Odometer, trip odometer, fuel level, fuel rate, miles per gallon
- Engine coolant temperature, oil temperature, oil life remaining
- Ignition status, MIL (check engine) status, seatbelt status
- Brake switch status, PTO status, transmission fluid temperature
- Ambient air temperature, barometric pressure
- Various emission monitor statuses (catalyst, O2 sensor, EGR, etc.)

See `settings.py` for the full list of MQTT topic paths.

## Requirements

- IBR1700 router
- OBD-II Adapter Kit (Part #170758-000)
- Vehicle with OBD-II port, or an OBD-II simulator
- OBD-II and desired PIDs enabled in the IBR1700: System > Administration > OBD-II
- Router firmware 7.26 or later

## Configuration

The MQTT broker connection settings are defined in `settings.py`:
- `MQTT_SERVER` — Internal broker address (typically `127.0.0.1`)
- `MQTT_PORT` — Broker port (typically `1883`)

PID topics are also defined in `settings.py` and follow the format `OBDII/PIDS/<PID_NAME>`.

## Sample Output

```
Start MQTT Client
MQTT connect reply to 127.0.0.1, 1883: Connection Accepted.
Subscribe response: Message ID=1, granted_qos=(0, 0, 0, ...)
Published msg received. topic: OBDII/PIDS/ENGINE_SPEED, msg: b'8464'
Published msg received. topic: OBDII/PIDS/VEHICLE_SPEED, msg: b'80.78'
Published msg received. topic: OBDII/PIDS/FUEL_LEVEL, msg: b'72.5'
```

## Extending the App

The `on_message` callback is where you add custom logic. For example:
- Forward PID data to a cloud service
- Trigger alerts based on thresholds (e.g., high engine temp)
- Log data to a file for later analysis
