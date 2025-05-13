from cpsdk import CPSDK
import requests
import time
from typing import Union, Dict

cp = CPSDK('timezone_via_gnss')


def get_timezone_offset(lat: float, lon: float, api_key: str) -> Dict[str, Union[bool, str]]:
    """
    Get the UTC offset as a string (e.g., '5' or '5:30') for given coordinates using TimeZoneDB API.
    Returns standard time offset (ignores DST).
    
    Args:
        lat (float): The latitude coordinate
        lon (float): The longitude coordinate
        api_key (str): Your TimeZoneDB API key
        
    Returns:
        Dict[str, Union[bool, str]]: Dictionary containing 'valid' status and 'data' (offset if valid)
    """
    valid_offsets = [
        '-11', '-10', '-9', '-8', '-7', '-6', '-5', '-4', 
        '-3:30', '-3', '-2', '-1', '0', '1', '2', '3', 
        '4', '4:30', '5', '5:30', '5:45', '6', '6:30', 
        '7', '8', '9', '9:30', '10', '11', '12', '13'
    ]

    try:
        url = "http://api.timezonedb.com/v2.1/get-time-zone"
        params = {
            'key': api_key,
            'format': 'json',
            'by': 'position',
            'lat': lat,
            'lng': lon
        }
        response = requests.get(url, params=params)
        
        if response.status_code == 429:
            cp.log("Rate limited by TimeZoneDB")
            return {'valid': False, 'data': None}
            
        response.raise_for_status()
        data = response.json()
        
        if data['status'] == 'OK':
            # Get current offset and DST status
            current_offset = int(data['gmtOffset'])
            is_dst = bool(data.get('dst', 0))
            
            # If DST is active, subtract 1 hour (3600 seconds) to get standard time
            if is_dst:
                total_offset = current_offset - 3600
            else:
                total_offset = current_offset
            
            # Round to nearest minute (60 seconds)
            total_offset = round(total_offset / 60) * 60
            
            total_minutes = int(total_offset / 60)
            hours = total_minutes // 60
            minutes = abs(total_minutes % 60)
            
            # Create the offset string
            if minutes == 0:
                offset_str = f"{hours}" if hours >= 0 else f"{hours}"
            else:
                offset_str = f"{hours}:{minutes:02d}" if hours >= 0 else f"{hours}:{minutes:02d}"
            
            # Check if the offset is in our valid list
            if offset_str not in valid_offsets:
                cp.log(f"Warning: Invalid offset {offset_str} for coordinates {lat}, {lon}")
                return {'valid': False, 'data': None}
            
            cp.log(f"Timezone offset: {offset_str}")
            return {'valid': True, 'data': offset_str}
        
        else:
            cp.log(f"Error: {data.get('message', 'Unknown error')}")
            return {'valid': False, 'data': None}
            
    except requests.exceptions.RequestException as e:
        cp.log(f"Error making request: {e}")
        return {'valid': False, 'data': None}
    
    except Exception as e:
        cp.log(f"Error getting timezone: {e}")
        return {'valid': False, 'data': None}


def get_timezonedb_api_key() -> Dict[str, Union[bool, str]]:
    """
    Get the TimeZoneDB API key from appdata.
    
    Returns:
        Dict[str, Union[bool, str]]: Dictionary containing 'valid' status and 'data' (API key if valid)
    """
    cp.log("Getting TimeZoneDB API key...")
    api_key = cp.get_appdata('timezonedb_api_key')
    if not api_key:
        cp.log("timezonedb_api_key not found in appdata")
        cp.log("Please create timezonedb_api_key under System -> SDK Data at the group level in NCM")
        return {'valid': False, 'data': None}
    
    cp.log("timezonedb_api_key found in appdata")
    return {'valid': True, 'data': api_key}


def get_gnss_data() -> Dict[str, Union[bool, Dict[str, float]]]:
    """
    Get and parse GPS coordinates from the device if lock is valid.
    
    Returns:
        Dict[str, Union[bool, Dict[str, float]]]: Dictionary containing 'valid' status and 'data' (coordinates if valid)
    """
    cp.log("Getting GNSS data...")
    gnss_data = cp.get('status/gps/fix')
    if not gnss_data['lock']:
        return {'valid': False, 'data': None}
    
    # Convert latitude from DMS to decimal degrees
    lat = abs(gnss_data['latitude']['degree']) + gnss_data['latitude']['minute'] / 60 + gnss_data['latitude']['second'] / 3600
    if gnss_data['latitude']['degree'] < 0:
        lat = -lat
        
    # Convert longitude from DMS to decimal degrees
    lon = abs(gnss_data['longitude']['degree']) + gnss_data['longitude']['minute'] / 60 + gnss_data['longitude']['second'] / 3600
    if gnss_data['longitude']['degree'] < 0:
        lon = -lon
    
    cp.log(f"GNSS data: latitude: {lat}, longitude: {lon}")
    return {'valid': True, 'data': {'latitude': lat, 'longitude': lon}}


# Example usage
if __name__ == "__main__":
    cp.wait_for_uptime(120)
    retry_delay = 60

    # Check to see if the device has already completed the timezone setup
    timezone_offset = cp.get_appdata('timezone_offset')
    if timezone_offset:
        cp.log(f"Timezone offset already set to: {timezone_offset}")
        cp.log("Exiting...")
        exit()
    else:
        cp.log("Timezone offset not set. Continuing...")

    # Check for API key indefinitely
    api_key = get_timezonedb_api_key()
    while not api_key['valid']:
        cp.log(f"Waiting {retry_delay} seconds to re-check timezonedb_api_key...")
        time.sleep(retry_delay)
        api_key = get_timezonedb_api_key()

    # Check for GPS lock indefinitely
    gnss_data = get_gnss_data()
    while not gnss_data['valid']:
        cp.log(f"Waiting {retry_delay} seconds to re-check GNSS data...")
        time.sleep(retry_delay)
        gnss_data = get_gnss_data()
    
    # Get timezone offset with retry logic
    max_retries = 5
    retries = 0
    
    while retries <= max_retries:
        timezone = get_timezone_offset(gnss_data['data']['latitude'], gnss_data['data']['longitude'], api_key['data'])
        
        if timezone['valid']:
            break
            
        if retries < max_retries:
            cp.log(f"Failed to get timezone offset. Retrying in {retry_delay} seconds... (Attempt {retries + 1}/{max_retries})")
            time.sleep(retry_delay)
            retries += 1
        else:
            cp.log(f"Failed to get timezone offset after {max_retries} attempts")
            break
    
    # Set notification messages based on timezone validity
    if timezone['valid']:
        cp.post_appdata('timezone_offset', timezone['data'])
        # Invert the timezone value for system config
        inverted_timezone = timezone['data'].replace('-', '+') if timezone['data'].startswith('-') else f"-{timezone['data']}"
        cp.put('config/system/timezone', inverted_timezone)
        cp.log(f"Timezone offset set applied and saved to SDK Data")
        notify_message = f"Timezone automatically set to {timezone['data']}"
    else:
        cp.post_appdata('timezone_offset', '+0')
        cp.put('config/system/timezone', '+0')
        cp.log("Timezone offset defaulted to UTC. Timezone needs to be set manually.")
        notify_message = "Timezone offset needs to be set manually"

    # Handle notifications with appropriate message
    timezone_notify = cp.get_appdata('timezone_notify')
    if not timezone_notify or not any(method in timezone_notify for method in ['desc', 'asset_id', 'alert']):
        cp.log('No notify method found in SDK Data for timezone_notify')
    else:
        timezone_notify = timezone_notify.lower()
        if 'desc' in timezone_notify:
            cp.log("desc found in timezone_notify. Updating system description.")
            cp.put('config/system/desc', notify_message)
        if 'asset_id' in timezone_notify:
            cp.log("asset_id found in timezone_notify. Updating asset_id.")
            cp.put('config/system/asset_id', notify_message)
        if 'alert' in timezone_notify:
            cp.log("alert found in timezone_notify. Sending alert.")
            cp.alert(notify_message)