# settings.py
# MQTT Server settings
MQTT_SERVER = 'test.mosquitto.org'
MQTT_PORT = 1883
MQTT_USER_NAME = 'anonymous'
MQTT_PASSWORD = 'anonymous'

# Seconds between publishing
PUBLISH_INTERVAL = 10

# Each topic is a dictionary, containing the {name: path} of each value to publish

topics = {
    'gps': {
        'latitude': '/status/gps/lastpos/latitude',
        'longitude': '/status/gps/lastpos/longitude',
        'age': '/status/gps/lastpos/age',
        'timestamp': '/status/gps/lastpos/timestamp',
        'accuracy': '/status/gps/fix/accuracy',
        'altitude_meters': '/status/gps/fix/altitude_meters',
        'ground_speed_knots': '/status/gps/fix/ground_speed_knots',
        'heading': '/status/gps/fix/heading',
        'satellites': '/status/gps/fix/satellites',

    },
    'status': {
        'system_id': 'config/system/system_id',
        'active_wan': 'status/wan/primary_device',
        'connection_state': '/status/wan/connection_state',
        'wan_in_bps': 'status/wan/stats/ibps',
        'wan_out_bps': 'status/wan/stats/obps',
        'lan_clients': 'status/lan/clients',
        'wlan_clients': 'status/wlan/clients',
        'temperature': '/status/system/temperature',
        'usb_state': 'status/usb/connection/state'
    }
}
