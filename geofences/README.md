# Geofences

A Python application that monitors GPS location and automatically switches between SIM cards based on geofence boundaries. This application is designed to work with Cradlepoint devices.

## Features

- Monitors device location using GPS
- Supports multiple geofences with custom names, coordinates, and radii
- Automatically switches between SIM1 and SIM2 based on location
- Requires 3 consecutive readings (3 seconds) before switching to prevent rapid changes
- Configurable geofence definitions through application data
- Default geofences included for Cradlepoint HQ and Boise Airport

## Configuration

The application uses a default set of geofences that can be modified through the application data. The default geofences are:

```json
[
    {
        "name": "Cradlepoint HQ",
        "lat": 43.618547,
        "lon": -116.206389,
        "radius": 200
    },
    {
        "name": "Boise Airport",
        "lat": 43.569282,
        "lon": -116.222676,
        "radius": 200
    }
]
```

Each geofence is defined by:
- `name`: A descriptive name for the geofence
- `lat`: Latitude in decimal degrees
- `lon`: Longitude in decimal degrees
- `radius`: Radius in meters

## Behavior

- When outside any geofence: Uses SIM1
- When inside a geofence: Uses SIM2
- Changes require 3 consecutive readings (3 seconds) to prevent rapid switching
- Automatically logs location changes and SIM switching events

## Usage

1. Install the required dependencies
2. Configure your geofences through the application data
3. Run the application
4. The application will automatically monitor location and switch SIM cards as needed

## Logging

The application logs important events including:
- Initial location and SIM card selection
- Entry into geofences
- Exit from geofences
- SIM card switching events
- Configuration changes

## Error Handling

- Automatically falls back to default geofences if configuration is invalid
- Handles GPS fix errors gracefully
- Logs configuration parsing errors 
