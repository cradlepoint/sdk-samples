"""
Use MQTT and subscribe to the IBR1700 OBD-II PIDs
Reference: https://www.eclipse.org/paho/clients/python/docs/

This app does the following:
- Connects to the internal MQTT Broker
- Subscribes to all OBD-II PIDs.
- Outputs logs when the PID publish messages are received.

"""
import settings
import cp
import paho.mqtt.client as mqtt


mqtt_client = None

# Topics for all OBD-II PIDs with QOS
topics = [(settings.VEHICLE_SPEED, 0),
          (settings.ENGINE_SPEED, 0),
          (settings.THROTTLE_POSITION, 0),
          (settings.ODOMETER, 0),
          (settings.FUEL_LEVEL, 0),
          (settings.ENGINE_COOLANT_TEMPERATURE, 0),
          (settings.IGNITION_STATUS, 0),
          (settings.MIL_STATUS, 0),
          (settings.FUEL_RATE, 0),
          (settings.PTO_STATUS, 0),
          (settings.SEATBELT_FASTENED, 0),
          (settings.MISFIRE_MONITOR, 0),
          (settings.FUEL_SYSTEM_MONITOR, 0),
          (settings.COMPREHENSIVE_COMPONENT_MONITOR, 0),
          (settings.CATALYST_MONITOR, 0),
          (settings.HEATED_CATALYST_MONITOR, 0),
          (settings.EVAPORATIVE_SYSTEM_MONITOR, 0),
          (settings.SECONDARY_AIR_SYSTEM_MONITOR, 0),
          (settings.AC_SYSTEM_REFRIGERANT_MONITOR, 0),
          (settings.OXYGEN_SENSOR_MONITOR, 0),
          (settings.OXYGEN_SENSOR_HEATER_MONITOR, 0),
          (settings.EGR_SYSTEM_MONITOR, 0),
          (settings.BRAKE_SWITCH_STATUS, 0),
          (settings.AMBIENT_AIR_TEMPERATURE, 0),
          (settings.TRIP_ODOMETER, 0),
          (settings.TRIP_FUEL_CONSUMPTION, 0),
          (settings.DISTANCE_SINCE_DTC_CLEARED, 0),
          (settings.TRANSMISSION_FLUID_TEMPERATURE, 0),
          (settings.OIL_LIFE_REMAINING, 0),
          (settings.ENGINE_OIL_TEMPERATURE, 0),
          (settings.BAROMETRIC_PRESSURE, 0),
          (settings.ENGINE_RUN_TIME, 0),
          (settings.MILES_PER_GALLON, 0)]


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

    try:
        client.subscribe(topics)
    except Exception as ex:
        cp.log('Client Subscribe exception. ex={}'.format(ex))


# Called when a message has been received on a topic that the client subscribes
# to and the message does not match an existing topic filter callback. Use
# message_callback_add() to define a callback that will be called for specific
# topic filters. on_message will serve as fallback when none matched.
def on_message(client, userdata, message):
    cp.log('Published msg received. topic: {}, msg: {}'.format(message.topic, message.payload))
    # Add code here to take more action based on the topic and payload.


# Called when the broker responds to a subscribe request. The mid variable
# matches the mid variable returned from the corresponding subscribe() call.
# The granted_qos variable is a list of integers that give the QoS level the
# broker has granted for each of the different subscription requests.
def on_subscribe(client, userdata, mid, granted_qos):
    cp.log('Subscribe response: Message ID={}, granted_qos={}'.format(mid, granted_qos))


def start_mqtt():
    global mqtt_client
    try:
        cp.log('Start MQTT Client')

        # Create the MQTT Client
        system_id = cp.get('/config/system/system_id')
        mqtt_client = mqtt.Client(client_id=system_id)
        mqtt_client.disable_logger()

        # Assign callback functions
        mqtt_client.on_connect = on_connect
        mqtt_client.on_subscribe = on_subscribe
        mqtt_client.on_message = on_message

        # Connect to the MQTT broker using the server and port in the settings file.
        connack_code = mqtt_client.connect(settings.MQTT_SERVER, settings.MQTT_PORT)
        cp.log('MQTT connect reply to {}, {}: {}'.format(settings.MQTT_SERVER, settings.MQTT_PORT,
                                                           mqtt.connack_string(connack_code)))

        # Blocking call that processes network traffic, dispatches callbacks and
        # handles reconnecting.
        mqtt_client.loop_forever()

    except Exception as ex:
        cp.log('Exception in start_mqtt()! exception: {}'.format(ex))
        raise


if __name__ == "__main__":
    try:
        start_mqtt()
    except Exception as ex:
        cp.log('Exception occurred!: {}'.format(ex))
