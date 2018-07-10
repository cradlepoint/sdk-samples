"""
This application will communicate with MS Azure IoT Hub using MQTT. It was developed
based on the sample from here:
    https://github.com/MicrosoftDocs/azure-docs/blob/master/articles/iot-hub/iot-hub-mqtt-support.md

Refer to section 'Using the MQTT protocol directly'.
"""

import cs
import os
import ssl
import urllib.parse

from app_logging import AppLogger
from paho.mqtt import client as mqtt


# Create an AppLogger for logging to syslog in NCOS.
log = AppLogger()

# Path to the TLS certificates file. The certificates were copied from the certs.c file
# located here: https://github.com/Azure/azure-iot-sdk-c/blob/master/certs/certs.c
path_to_root_cert = os.path.join(os.getcwd(), 'certs.cer')

# MS Azure IoT Hub name
iot_hub_name = ''

# Device name in MS Azure IoT Hub
device_id = ''

# SAS token for the device id. This can be generated using the Device Explorer Tool.
# The format of the token should be similar to:
# 'SharedAccessSignature sr={your hub name}.azure-devices.net%2Fdevices%2FMyDevice01%2Fapi-version%3D2016-11-14&sig=vSgHBMUG.....Ntg%3d&se=1456481802'
sas_token = ''

# Called when the broker responds to our connection request.
def on_connect(client, userdata, flags, rc):
    log.info('Device connected with result code: {}'.format(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    try:
        client.subscribe('devices/{}/messages/devicebound/#'.format(device_id))
    except Exception as ex:
        log.error('Client Subscribe exception. ex={}'.format(ex))


# Called when the broker responds to our disconnect request.
def on_disconnect(client, userdata, rc):
    log.info('Device disconnected with result code: {}'.format(rc))


# Called when a message that was to be sent using the publish() call has
# completed transmission to the broker.
#
# This callback is important because even if the publish() call returns success,
# it does not always mean that the message has been sent.
def on_publish(client, userdata, mid):
    log.info('Device sent message.')


# Called when the broker responds to a subscribe request. The mid variable
# matches the mid variable returned from the corresponding subscribe() call.
# The granted_qos variable is a list of integers that give the QoS level the
# broker has granted for each of the different subscription requests.
def on_subscribe(client, userdata, mid, granted_qos):
    log.debug('Subscribe response: Message ID={}, granted_qos={}'.format(mid, granted_qos))


# Called when a message has been received on a topic that the client subscribes
# to and the message does not match an existing topic filter callback. Use
# message_callback_add() to define a callback that will be called for specific
# topic filters. on_message will serve as fallback when none matched.
def on_message(client, userdata, msg):
    log.debug('Device received topic: {}, msg: {}'.format(msg.topic, msg.payload))


mqtt_client = mqtt.Client(client_id=device_id, protocol=mqtt.MQTTv311)


# Assign the appropriate callback functions
mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect
mqtt_client.on_publish = on_publish
mqtt_client.on_message = on_message
mqtt_client.on_subscribe = on_subscribe

try:
    mqtt_client.username_pw_set(username=iot_hub_name + '.azure-devices.net/' + device_id, password=sas_token)

    mqtt_client.tls_set(ca_certs=path_to_root_cert, certfile=None, keyfile=None, cert_reqs=ssl.CERT_REQUIRED,
                        tls_version=ssl.PROTOCOL_TLSv1, ciphers=None)

    mqtt_client.tls_insecure_set(False)

    mqtt_client.connect(iot_hub_name + '.azure-devices.net', port=8883)

    # Get some router data and publish to the IoT Hub
    device_data = dict()
    log.info('device_data = {}'.format(device_data))
    device_data['router_id'] = cs.CSClient().get('/config/system/system_id').get('data')
    device_data['product_name'] = cs.CSClient().get('/status/product_info/product_name').get('data')

    # Not all CP devices have a modem_temperature
    if device_data['product_name'].startswith('ibr200') is False:
        device_data['router_temperature'] = cs.CSClient().get('/status/system/modem_temperature').get('data')

    mqtt_client.publish('devices/' + device_id + '/messages/events/', urllib.parse.urlencode(device_data), qos=1)

    mqtt_client.loop_forever()

except Exception as e:
    log.error('Exception: {}'.format(e))
