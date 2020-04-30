from csclient import EventingCSClient
cp = EventingCSClient('mqtt_app')

MQTT_CLIENT_ID = cp.get('config/system/system_id')

# MQTT Server settings
MQTT_SERVER = 'test.mosquitto.org'
MQTT_PORT = 1883
MQTT_USER_NAME = 'anonymous'
MQTT_PASSWORD = 'anonymous'

# MQTT Topics
# Topics are named the same as the path to get the data from the
# NCOS device. This was done for simplicity.
GPS_TOPIC = '/status/gps/lastpos'
MODEM_TEMP_TOPIC = '/status/system/modem_temperature'
WAN_CONNECTION_STATE_TOPIC = '/status/wan/connection_state'