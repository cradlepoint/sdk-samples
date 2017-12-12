import cs

# Used for logging or anytime the app name is needed
APP_NAME = 'mqtt_app'

# MQTT Server settings
MQTT_SERVER = 'test.mosquitto.org'
MQTT_PORT = 1883
MQTT_PORT_TLS = 8883
MQTT_QOS = 0
MQTT_USER_NAME = 'anonymous'
MQTT_PASSWORD = 'anonymous'

# MQTT Topics
GPS_TOPIC = '/status/gps'
MODEM_TEMP_TOPIC = '/status/system/modem_temperature'
WAN_CONNECTION_STATE_TOPIC = '/status/wan/connection_state'

# MQTT Client
MQTT_CLIENT_ID = cs.CSClient().get('/config/system/system_id').get('data', '')
