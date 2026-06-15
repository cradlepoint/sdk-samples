# OBDII_monitor
Monitors OBD-II values, puts latest values in asset_id, and alerts on conditions defined in SDK AppData.

## Requirements

- OBD-II Streamer

## Configuration

The app will create an entry in SDK AppData for "OBDII_monitor". Set the polling interval in seconds from 1-50 (higher than 50 can miss historical values).

Define the PID names you want to monitor and any conditions for alerting (optional):

**Monitor odometer with no alert conditions:**

```json
"ODOMETER": {"condition": "", "value": ""}
```

This will put the ODOMETER value in the asset_id field but not send alerts.

**Monitor speed with alerting:**

```json
"VEHICLE_SPEED": {"condition": ">", "value": 80}
```

**Alert if fuel system monitor not complete:**

```json
"FUEL_SYSTEM_MONITOR": {"condition": "!=", "value": "COMPLETE"}
```

## Alert Conditions

- `>` — greater than
- `<` — less than
- `=` — equal to
- `!=` — not equal to
