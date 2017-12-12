import cs

# Used for logging or anytime the app name is needed
APP_NAME = 'mqtt_app'

# MQTT Server settings
MQTT_SERVER = 'test.mosquitto.org'
MQTT_PORT = 1883
MQTT_PORT_TLS = 8883
MQTT_QOS_0 = 0
MQTT_QOS_1 = 1
MQTT_QOS_2 = 2
MQTT_USER_NAME = 'anonymous'
MQTT_PASSWORD = 'anonymous'

# MQTT Topics
# Topics are names the same as the path to get the data from the
# NCOS device. This was done for simplicity.
GPS_TOPIC = '/status/gps'
MODEM_TEMP_TOPIC = '/status/system/modem_temperature'
WAN_CONNECTION_STATE_TOPIC = '/status/wan/connection_state'

# MQTT Client
MQTT_CLIENT_ID = cs.CSClient().get('/config/system/system_id').get('data', '')
