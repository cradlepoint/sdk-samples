"""
An MQTT App example
Reference: https://www.eclipse.org/paho/clients/python/docs/

This app does the following:
- Connects to MQTT test server ‘test.mosquitto.org’
- Subscribes to topics as defined in settings.py.
- Runs a background thread which publishes data to the topics defined in settings.py every 10 secs.
- Generates a log when the MQTT server sends the published information for topics subscribed.
"""

# A try/except is wrapped around the imports to catch an
# attempt to import a file or library that does not exist
# in NCOS. Very useful during app development if one is
# adding python libraries.
try:
    import cs
    import os
    import sys
    import traceback
    import settings
    import json
    import time
    import ssl
    import paho.mqtt.client as mqtt
    import paho.mqtt.publish as publish

    from app_logging import AppLogger
    from threading import Thread

except Exception as e:
    # Output logs indicating what import failed.
    cs.CSClient().log('mqtt_app.py', 'Import failure: {}'.format(e))
    cs.CSClient().log('mqtt_app.py', 'Traceback: {}'.format(traceback.format_exc()))
    sys.exit(-1)


# Create an AppLogger for logging to syslog in NCOS.
log = AppLogger()

# The mqtt_client for publishing to the broker
mqtt_client = None


# Called when the broker responds to our connection request.
def on_connect(client, userdata, flags, rc):
    log.debug('MQTT Client connection results: {}'.format(mqtt.connack_string(rc)))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    # QOS 0: The broker will deliver the message once, with no confirmation.
    # QOS 1: The broker will deliver the message at least once, with confirmation required.
    # QOS 2: The broker will deliver the message exactly once by using a four step handshake.
    #
    # A list of tuples (i.e. topic, qos). Both topic and qos must be present in the tuple.
    topics = [(settings.GPS_TOPIC, 2),
              (settings.MODEM_TEMP_TOPIC, 1),
              (settings.WAN_CONNECTION_STATE_TOPIC, 0)]
    try:
        client.subscribe(topics)
    except Exception as ex:
        log.error('Client Subscribe exception. ex={}'.format(ex))


# Called when a message has been received on a topic that the client subscribes
# to and the message does not match an existing topic filter callback. Use
# message_callback_add() to define a callback that will be called for specific
# topic filters. on_message will serve as fallback when none matched.
def on_message(client, userdata, msg):
    log.debug('Published msg received. topic: {}, msg: {}'.format(msg.topic, msg.payload))


# Called when a message that was to be sent using the publish() call has
# completed transmission to the broker. For messages with QoS levels 1
# and 2, this means that the appropriate handshakes have completed. For
# QoS 0, this simply means that the message has left the client. The mid
# variable matches the mid variable returned from the corresponding publish()
# call, to allow outgoing messages to be tracked.
#
# This callback is important because even if the publish() call returns success,
# it does not always mean that the message has been sent.
def on_publish(client, userdata, mid):
    log.debug('Publish response: Message ID={}'.format(mid))


# Called when the broker responds to a subscribe request. The mid variable
# matches the mid variable returned from the corresponding subscribe() call.
# The granted_qos variable is a list of integers that give the QoS level the
# broker has granted for each of the different subscription requests.
def on_subscribe(client, userdata, mid, granted_qos):
    log.debug('Subscribe response: Message ID={}, granted_qos={}'.format(mid, granted_qos))


# This function will publish a file to the MQTT broker
def publish_file(file_name, file_path):
    global mqtt_client
    log.debug('publish_file({})'.format(file_path))
    try:
        with open(file_path) as fh:
            file_contents = fh.read()
        ret_obj = mqtt_client.publish(topic=file_name, payload=file_contents, qos=0)

        if ret_obj.rc == mqtt.MQTT_ERR_SUCCESS:
            log.debug('MQTT published file: {}'.format(file_path))
        else:
            log.warning('MQTT failed to publish file: {}'.format(file_path))
            log.warning('MQTT failed to publish file. error: {}'.format(mqtt.error_string(ret_obj.rc)))

    except Exception as ex:
        log.error('Exception in publish_file(). ex: {}'.format(ex))


# This function will periodically publish device data to the MQTT Broker
def publish_thread():
    log.debug('Start publish_thread()')
    while True:
        try:
            gps_lastpos = cs.CSClient().get(settings.GPS_TOPIC).get('data')
            gps_pos = {'longitude': gps_lastpos.get('longitude'),
                       'latitude': gps_lastpos.get('latitude')}

            # Single Topic Publish example
            # QOS 0: The client will deliver the message once, with no confirmation.
            publish.single(topic=settings.GPS_TOPIC, payload=json.dumps(gps_pos), qos=0,
                           hostname=settings.MQTT_SERVER, port=settings.MQTT_PORT)

            time.sleep(1)

            # Multiple Topics Publish example
            modem_temp = cs.CSClient().get(settings.MODEM_TEMP_TOPIC).get('data', '')
            wan_connection_state = cs.CSClient().get(settings.WAN_CONNECTION_STATE_TOPIC).get('data')

            # Using tuples to define multiple messages,
            # the form must be: ("<topic>", "<payload>", qos, retain)
            # QOS 1: The client will deliver the message at least once, with confirmation required.
            # QOS 2: The client will deliver the message exactly once by using a four step handshake.
            msgs = [(settings.MODEM_TEMP_TOPIC, modem_temp, 1, False),
                    (settings.WAN_CONNECTION_STATE_TOPIC, wan_connection_state, 2, False)]

            publish.multiple(msgs=msgs, hostname=settings.MQTT_SERVER, port=settings.MQTT_PORT)

            time.sleep(1)

            # Publish the package.ini file as an example
            file_name = 'package.ini'
            publish_file(file_name, os.path.join(os.getcwd(), file_name))

            time.sleep(10)
        except Exception as ex:
            log.error('Exception in publish_thread(). ex: {}'.format(ex))


def start_mqtt():
    global mqtt_client
    try:
        log.debug('Start MQTT Client')

        mqtt_client = mqtt.Client(client_id=settings.MQTT_CLIENT_ID)

        if settings.MQTT_LOGGING:
            # Add MQTT logging to the app logs
            mqtt_client.enable_logger(AppLogger.logger)
        else:
            mqtt_client.disable_logger()

        # Assign callback functions
        mqtt_client.on_connect = on_connect
        mqtt_client.on_message = on_message
        mqtt_client.on_publish = on_publish
        mqtt_client.on_subscribe = on_subscribe

        # Set a Will to be sent by the broker in case the client disconnects unexpectedly.
        # QOS 2: The broker will deliver the message exactly once by using a four step handshake.
        mqtt_client.will_set('/will/oops', payload='{} has vanished!'.format(settings.MQTT_CLIENT_ID), qos=2)

        connack_code = mqtt_client.connect(settings.MQTT_SERVER, settings.MQTT_PORT)
        log.info('MQTT connect reply to {}, {}: {}'.format(settings.MQTT_SERVER, settings.MQTT_PORT,
                                                           mqtt.connack_string(connack_code)))
        # Blocking call that processes network traffic, dispatches callbacks and
        # handles reconnecting.
        mqtt_client.loop_forever()

    except Exception as ex:
        log.error('Exception in start_mqtt()! exception: {}'.format(ex))
        raise


def start_app():
    try:
        log.debug('start_app()')

        # Start the MQTT client thread.
        mqtt_thread = Thread(target=start_mqtt, args=())
        mqtt_thread.start()

        publish_thread()

    except Exception as ex:
        log.error('Exception during start_app()! exception: {}'.format(ex))
        raise


if __name__ == "__main__":
    start_app()
