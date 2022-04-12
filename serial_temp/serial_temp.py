import time
import serial
import paho.mqtt.client as mqtt
import json
from csclient import EventingCSClient

cp = EventingCSClient("serial_temp")
broker_address = "127.0.0.01"
port = "/dev/ttyUSB0"
speed = 9600
my_sim = "mdm-e152d8b2"  # Change to your SIM slot UID


class Timeout(Exception):
    pass


def has_t1t2(chunks):
    return len(chunks) > 2 and "1." in chunks[0] and "2." in chunks[1]


def parse_temp(temp_str):
    dotpos = temp_str.find(".")
    if dotpos:
        return float(temp_str[dotpos + 1 : -1])
    else:
        return None


def modem_state(cp, state, sim):
    # Blocking call that will wait until a given state is shown as the modem's status
    timeout_counter = 0
    sleep_seconds = 0
    conn_path = "%s/%s/status/connection_state" % ("status/wan/devices", sim)
    cp.log(f"modem_state waiting sim={sim} state={state}")
    while True:
        sleep_seconds += 5
        conn_state = cp.get(conn_path).get("data", "")
        # TODO add checking for error states
        cp.log(f"waiting for state={state} on sim={sim} curr state={conn_state}")
        if conn_state == state:
            break
        if timeout_counter > 600:
            cp.log(f"timeout waiting on sim={sim}")
            raise Timeout(conn_path)
        time.sleep(min(sleep_seconds, 45))
        timeout_counter += min(sleep_seconds, 45)
    cp.log(f"sim={sim} connected")
    return True


def data_logger_to_mqtt_reader():
    client = mqtt.Client(
        "Datalogger2Mqtt", protocol=mqtt.MQTTv311
    )  # create new instance
    try:
        client.connect(broker_address, port=9898)  # connect to broker
    except ConnectionRefusedError:
        return
    try:
        with serial.Serial("/dev/ttyUSB0", 9600, timeout=1) as ser:
            while True:
                line = ser.readline()
                chunks = line.decode("utf-8").split(",")
                if chunks and has_t1t2(chunks):
                    d1temp = parse_temp(chunks[0])
                    d2temp = parse_temp(chunks[1])
                    data = {"d1temp": d1temp, "d2temp": d2temp}
                    client.publish("measurement/", json.dumps(data))
    except Exception as e:
        cp.log(f"Exception is {e}")
    finally:
        client.disconnect()


if modem_state(cp, "connected", my_sim):
    data_logger_to_mqtt_reader()
