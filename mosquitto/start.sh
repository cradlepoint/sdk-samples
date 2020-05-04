#!/bin/bash
logger "Starting Mosquitto: mosquitto --config-file mosquitto.conf --daemon"
mosquitto --config-file mosquitto.conf --daemon &
wait %1
