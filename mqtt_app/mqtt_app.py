"""
An MQTT App example
Reference: https://www.eclipse.org/paho/clients/python/docs/

This app does the following:
- Connects to MQTT test server ‘test.mosquitto.org’
- Subscribes to topics as defined in settings.py.
- Runs a background thread which publishes data to the topics defined in settings.py every 10 secs.
- Generates a log when the MQTT server sends the published information for topics subscribed.
"""
import os
import json
import time
import settings
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish

from threading import Thread
from csclient import EventingCSClient

cp = EventingCSClient("mqtt_app")
mqtt_client = None


# Called when the broker responds to our connection request.
def on_connect(client, userdata, flags, rc):
    cp.log("MQTT Client connection results: {}".format(mqtt.connack_string(rc)))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    # QOS 0: The broker will deliver the message once, with no confirmation.
    # QOS 1: The broker will deliver the message at least once, with confirmation required.
    # QOS 2: The broker will deliver the message exactly once by using a four step handshake.
    #
    # A list of tuples (i.e. topic, qos). Both topic and qos must be present in the tuple.
    topics = [
        (settings.GPS_TOPIC, 2),
        (settings.MODEM_TEMP_TOPIC, 1),
        (settings.WAN_CONNECTION_STATE_TOPIC, 0),
    ]
    try:
        client.subscribe(topics)
    except Exception as ex:
        cp.log("Client Subscribe exception. ex={}".format(ex))


# Called when a message has been received on a topic that the client subscribes
# to and the message does not match an existing topic filter callback. Use
# message_callback_add() to define a callback that will be called for specific
# topic filters. on_message will serve as fallback when none matched.
def on_message(client, userdata, msg):
    cp.log("Published msg received. topic: {}, msg: {}".format(msg.topic, msg.payload))


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
    cp.log("Publish response: Message ID={}".format(mid))


# Called when the broker responds to a subscribe request. The mid variable
# matches the mid variable returned from the corresponding subscribe() call.
# The granted_qos variable is a list of integers that give the QoS level the
# broker has granted for each of the different subscription requests.
def on_subscribe(client, userdata, mid, granted_qos):
    cp.log("Subscribe response: Message ID={}, granted_qos={}".format(mid, granted_qos))


# This function will publish a file to the MQTT broker
def publish_file(file_name, file_path):
    global mqtt_client
    cp.log("publish_file({})".format(file_path))
    try:
        with open(file_path) as fh:
            file_contents = fh.read()
        ret_obj = mqtt_client.publish(topic=file_name, payload=file_contents, qos=0)

        if ret_obj.rc == mqtt.MQTT_ERR_SUCCESS:
            cp.log("MQTT published file: {}".format(file_path))
        else:
            cp.log("MQTT failed to publish file: {}".format(file_path))
            cp.log(
                "MQTT failed to publish file. error: {}".format(
                    mqtt.error_string(ret_obj.rc)
                )
            )

    except Exception as ex:
        cp.log("Exception in publish_file(). ex: {}".format(ex))


# This function will periodically publish device data to the MQTT Broker
def publish_thread():
    cp.log("Start publish_thread()")
    while True:
        try:
            gps_lastpos = cp.get(settings.GPS_TOPIC)
            gps_pos = {
                "longitude": gps_lastpos.get("longitude"),
                "latitude": gps_lastpos.get("latitude"),
            }

            # Single Topic Publish example
            # QOS 0: The client will deliver the message once, with no confirmation.
            publish.single(
                topic=settings.GPS_TOPIC,
                payload=json.dumps(gps_pos),
                qos=0,
                hostname=settings.MQTT_SERVER,
                port=settings.MQTT_PORT,
            )

            time.sleep(1)

            # Multiple Topics Publish example
            modem_temp = cp.get(settings.MODEM_TEMP_TOPIC)
            wan_connection_state = cp.get(settings.WAN_CONNECTION_STATE_TOPIC)

            # Using tuples to define multiple messages,
            # the form must be: ("<topic>", "<payload>", qos, retain)
            # QOS 1: The client will deliver the message at least once, with confirmation required.
            # QOS 2: The client will deliver the message exactly once by using a four step handshake.
            msgs = [
                (settings.MODEM_TEMP_TOPIC, modem_temp, 1, False),
                (settings.WAN_CONNECTION_STATE_TOPIC, wan_connection_state, 2, False),
            ]

            publish.multiple(
                msgs=msgs, hostname=settings.MQTT_SERVER, port=settings.MQTT_PORT
            )

            time.sleep(1)

            # Publish the package.ini file as an example
            file_name = "package.ini"
            publish_file(file_name, os.path.join(os.getcwd(), file_name))

            time.sleep(10)
        except Exception as ex:
            cp.log("Exception in publish_thread(). ex: {}".format(ex))


def start_mqtt():
    global mqtt_client
    try:
        cp.log("Start MQTT Client")
        system_id = cp.get("/config/system/system_id")
        mqtt_client = mqtt.Client(client_id=system_id)
        mqtt_client.disable_logger()

        # Assign callback functions
        mqtt_client.on_connect = on_connect
        mqtt_client.on_message = on_message
        mqtt_client.on_publish = on_publish
        mqtt_client.on_subscribe = on_subscribe

        # Set a Will to be sent by the broker in case the client disconnects unexpectedly.
        # QOS 2: The broker will deliver the message exactly once by using a four step handshake.
        mqtt_client.will_set(
            "/will/oops",
            payload="{} has vanished!".format(settings.MQTT_CLIENT_ID),
            qos=2,
        )

        connack_code = mqtt_client.connect(settings.MQTT_SERVER, settings.MQTT_PORT)
        cp.log(
            "MQTT connect reply to {}, {}: {}".format(
                settings.MQTT_SERVER,
                settings.MQTT_PORT,
                mqtt.connack_string(connack_code),
            )
        )
        # Blocking call that processes network traffic, dispatches callbacks and
        # handles reconnecting.
        mqtt_client.loop_forever()

    except Exception as ex:
        cp.log("Exception in start_mqtt()! exception: {}".format(ex))
        raise


cp.log("Starting...")
mqtt_thread = Thread(target=start_mqtt, args=())
mqtt_thread.start()
publish_thread()
