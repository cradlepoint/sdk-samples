# Ericsson Router SDK Application
# speed_limit - Monitors vehicle speed via GPS and alerts on speed limit violations
import cp
import time

cp.log('Starting speed_limit...')

# Conversion factor: knots to MPH
KNOTS_TO_MPH = 1.15078

# Default speed limit if not configured in appdata
DEFAULT_SPEED_LIMIT_MPH = 100

# Polling interval in seconds
POLL_INTERVAL = 2


def get_speed_limit():
    """Read the speed limit from appdata. Returns default if not set."""
    try:
        value = cp.get_appdata('speed_limit_mph')
        if value:
            return float(value)
    except Exception as e:
        cp.log(f'Error reading speed_limit_mph appdata: {e}')
    return DEFAULT_SPEED_LIMIT_MPH


def get_gps_data():
    """Get current GPS fix data. Returns dict with speed_mph, lat, lon or None."""
    try:
        gps = cp.get('status/gps/fix')
        if not gps:
            return None

        if not gps.get('lock'):
            return None

        speed_knots = gps.get('ground_speed_knots')
        if speed_knots is None:
            return None

        speed_mph = speed_knots * KNOTS_TO_MPH

        lat = None
        lon = None
        if gps.get('latitude') and gps.get('longitude'):
            lat = cp.dec(
                gps['latitude']['degree'],
                gps['latitude']['minute'],
                gps['latitude']['second']
            )
            lon = cp.dec(
                gps['longitude']['degree'],
                gps['longitude']['minute'],
                gps['longitude']['second']
            )

        return {
            'speed_mph': speed_mph,
            'lat': lat,
            'lon': lon
        }
    except Exception as e:
        cp.log(f'Error reading GPS data: {e}')
        return None


def format_location(lat, lon):
    """Format lat/lon for display."""
    if lat is not None and lon is not None:
        return f'{lat:.6f},{lon:.6f}'
    return 'unknown'


def main():
    """Main loop - monitor speed and alert on violations."""
    cp.log('Speed limit monitor running')

    # Violation tracking state
    in_violation = False
    violation_start_time = None
    violation_start_lat = None
    violation_start_lon = None
    max_speed_mph = 0.0

    while True:
        try:
            speed_limit = get_speed_limit()
            gps_data = get_gps_data()

            if gps_data is None:
                time.sleep(POLL_INTERVAL)
                continue

            current_speed = gps_data['speed_mph']
            current_lat = gps_data['lat']
            current_lon = gps_data['lon']

            if not in_violation and current_speed > speed_limit:
                # Violation started
                in_violation = True
                violation_start_time = time.strftime('%Y-%m-%d %H:%M:%S')
                violation_start_lat = current_lat
                violation_start_lon = current_lon
                max_speed_mph = current_speed
                cp.log(f'Speed violation started: {current_speed:.1f} MPH '
                       f'(limit {speed_limit:.0f} MPH) at '
                       f'{format_location(current_lat, current_lon)}')

            elif in_violation and current_speed > speed_limit:
                # Still in violation, track max speed
                if current_speed > max_speed_mph:
                    max_speed_mph = current_speed

            elif in_violation and current_speed <= speed_limit:
                # Violation ended
                violation_end_time = time.strftime('%Y-%m-%d %H:%M:%S')
                violation_end_lat = current_lat
                violation_end_lon = current_lon

                alert_msg = (
                    f'Speed violation: max {max_speed_mph:.1f} MPH '
                    f'(limit {speed_limit:.0f} MPH). '
                    f'Start: {violation_start_time} at '
                    f'{format_location(violation_start_lat, violation_start_lon)}. '
                    f'End: {violation_end_time} at '
                    f'{format_location(violation_end_lat, violation_end_lon)}.'
                )
                cp.log(alert_msg)
                cp.alert(alert_msg)

                # Reset state
                in_violation = False
                violation_start_time = None
                violation_start_lat = None
                violation_start_lon = None
                max_speed_mph = 0.0

        except Exception as e:
            cp.log(f'Error in main loop: {e}')

        time.sleep(POLL_INTERVAL)


main()
