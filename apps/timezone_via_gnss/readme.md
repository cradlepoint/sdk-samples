# timezone_via_gnss
Automatically set device timezone using GNSS and TimezoneDB.

## Requirements

- TimezoneDB account and API key
- GNSS antenna
- `timezone_api_key` configured at group or device level under System > SDK Data

## Optional Configuration

- `timezone_notify` — Set under System > SDK Data with values `desc`, `asset_id`, and/or `alert`

## How It Works

Uses GNSS data to query TimezoneDB and request a UTC offset value which will be applied to the device config under System > Administration > System Clock.
