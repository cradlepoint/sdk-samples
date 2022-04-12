import paho.mqtt.client as mqtt
import random
import json
import time
import sys
import logging.handlers

handlers = [logging.StreamHandler()]
if sys.platform == "linux2":
    # on router also use the syslog
    handlers.append(logging.handlers.SysLogHandler(address="/dev/log"))

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(name)s: %(message)s",
    datefmt="%b %d %H:%M:%S",
    handlers=handlers,
)
logger = logging.getLogger("mqtt_azure_client")

BROKER_IP = "192.168.0.1"  # Broker IP Address
BROKER_PORT = 9898  # Port at which the Broker is running


class IoTClient:
    def __init__(self, broker_ip=BROKER_IP, broker_port=BROKER_PORT):
        self.client = mqtt.Client(
            "FakeTempSensor", protocol=mqtt.MQTTv311
        )  # create new instance
        self.broker_ip = broker_ip
        self.broker_port = broker_port

    def twin_cb(self, client, userdata, msg):
        twin = json.loads(msg.payload.decode("utf-8"))
        logger.info("Twin: \n %s", str(twin))

    def setting_cb(self, client, userdata, msg):
        settings = msg.payload.decode("utf-8")
        json_data = json.loads(settings)
        for attr, value in json_data.items():
            if attr != "$version":
                logger.info("attr being processed %s", attr)
                reported_payload = {attr: {}}
                reported_payload[attr]["value"] = value["value"]
                reported_payload[attr]["statusCode"] = 200
                reported_payload[attr]["status"] = "completed"
                reported_payload[attr]["desiredVersion"] = json_data["$version"]
                self.client.publish(
                    "property/?rid={}".format(int(time.time())),
                    json.dumps(reported_payload),
                    qos=1,
                )

    def command_cb(self, client, userdata, data):
        msg = data.payload.decode("utf-8")
        logger.info(msg)
        if data.topic:
            try:
                topic = data.topic.decode("utf-8")
            except:
                topic = str(data.topic)
        index = topic.find("$rid=")
        method_id = topic[index + 5 :]
        logger.info("Method ID : \n %s", str(method_id))
        len_temp = len("command_sub/")
        method_name = topic[len_temp : topic.find("/", len_temp + 1)]
        ret_message = "{}"
        next_topic = "".join(["command_pub/", "{}/?$rid={}".format(200, method_id)])
        logger.info(
            "C2D: => %s with data %s and name => %s",
            next_topic,
            ret_message,
            method_name,
        )
        self.client.publish(next_topic, ret_message, qos=0)

    def get_twin(self):
        self.client.publish("twin/?$rid=1", None, qos=1)

    def setup_subscriptions(self):
        # initialize twin support
        self.client.subscribe("twin_resp/#")
        self.client.message_callback_add("twin_resp/#", self.twin_cb)

        # desired properties subscribe
        self.client.subscribe("setting/#")
        self.client.message_callback_add("setting/#", self.setting_cb)

        # Direct method subscribe
        self.client.subscribe("command_sub/#")
        self.client.message_callback_add("command_sub/#", self.command_cb)

    def start(self):
        last_measurement_sent = int(time.time())
        last_reported_property_sent = int(time.time())
        self.client.connect(self.broker_ip, port=self.broker_port)  # connect to broker
        self.setup_subscriptions()

        self.get_twin()

        while True:
            if int(time.time()) - last_measurement_sent >= 15:
                measurements = {
                    "temp_sensor_val": random.randint(20, 50),
                    "temp_state": "Off" if random.randint(0, 1) == 0 else "On",
                    "temp_alert": "Temp High Alert",
                }
                self.client.publish(
                    "measurement/", json.dumps(measurements)
                )  # publish measurement data
                last_measurement_sent = time.time()

            if int(time.time()) - last_reported_property_sent >= 30:
                properties = {"fw_version": "1.0.0"}
                self.client.publish(
                    "property/?rid={}".format(int(time.time())), json.dumps(properties)
                )  # publish property data
                last_reported_property_sent = time.time()

            # yield to handle MQTT messaging
            self.client.loop()


if __name__ == "__main__":
    iot_client = IoTClient(broker_ip=BROKER_IP, broker_port=BROKER_PORT)
    iot_client.start()
