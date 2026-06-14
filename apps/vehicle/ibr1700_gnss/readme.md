# ibr1700_gnss

![Python](https://img.shields.io/badge/Python-3.8-yellow)

Demonstrates accessing the gyroscope and accelerometer data in the IBR1700 by reading from the GNSS socket. The app sends the ALL and IMU commands and then logs what it reads from the GNSS socket.

## Requirements

- IBR1700
- GPS Antenna
- GPS enabled on the device

## Expected Output

NMEA sentences are output as logs.

## Socket Commands

Supported commands should be terminated with `\r\n` (e.g. `HISTORY\r\n`).

| Command | Description |
|---------|-------------|
| `ALL` | Send everything, all data read from the GNSS hardware (high volume) |
| `HISTORY` | Send the NMEA position history. Socket is closed at end of the message |
| `IMU` | Enable/disable the IMU (Inertial Measurement Unit) sentences |
| `LAST` | Send only the last NMEA position |
| `NMEA` | Send the NMEA position history then continue sending updates every second |

## NMEA Sentences

### PCPTMIMU

Inertial Measurement Unit (IMU) Measurement. The measurement of the accelerometer and gyroscope. Arrives at 10Hz.

| Field | Type | Unit |
|-------|------|------|
| `time` | float | seconds |
| `accel_X` | float | meters/sec² |
| `accel_Y` | float | meters/sec² |
| `accel_Z` | float | meters/sec² |
| `rotation_X` | float | degree/second |
| `rotation_Y` | float | degree/second |
| `rotation_Z` | float | degree/second |

Example:
```
$PINVMIMU,82928.100,0.04642,-0.08398,-9.67104,-2.34985,1.13220,-0.73242,*3A
```

### PCPTMINR

IPL Inertial Navigation Result. If the GNSS signals are lost, the inertial navigation system provides a prediction of position.

| Field | Type | Description |
|-------|------|-------------|
| `time` | float | seconds |
| `latitude` | float | predicted latitude |
| `longitude` | float | predicted longitude |
| `height_meters` | float | predicted height |
| `velocity_N` | float | meters/sec |
| `velocity_E` | float | meters/sec |
| `velocity_V` | float | meters/sec |
| `pos_std_N` | float | position std dev N, meters |
| `pos_std_E` | float | position std dev E, meters |
| `pos_std_V` | float | vertical position std dev, meters |
| `vel_std_N` | float | velocity std dev N, meters |
| `vel_std_E` | float | velocity std dev E, meters |
| `vel_std_V` | float | vertical velocity std dev, meters |
| `phase` | integer | |
| `librtn` | integer | |

Example:
```
$PCPTMINR,21804.700,43.6196987,-116.2057534,873.53,0.00,0.00,-0.00,17.53,17.53,17.53,14.61,14.61,14.61,0,0,*1C
```
