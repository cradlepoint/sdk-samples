# system_monitor will get various system diagnostics, alert on thresholds, and put current status in asset_id field.

from csclient import EventingCSClient
import time
import json

interval = 60  # Seconds between monitoring polls
cpu_threshold = 80  # Send alert when CPU utilization reaches threshold
mem_threshold = 80  # Send alert when memory utilization reaches threshold

cp = EventingCSClient('system_monitor')
cp.log('Starting...')
previous_ethernet = None

while True:
    status = {}

    # CPU Utilization
    try:
        cpu = cp.get('status/system/cpu')
        status["cpu"] = round(sum(list(cpu.values())) * 100)
        if status["cpu"] > cpu_threshold:
            cp.alert(f'CPU at {status["cpu"]}%')
    except Exception as e:
        cp.logger.exception(e)

    # Memory Utilization
    try:
        mem = cp.get('status/system/memory')
        status["memory"] = round((mem["memtotal"] - mem["memavailable"]) / mem["memtotal"] * 100)
        if status["memory"] > mem_threshold:
            cp.alert(f'Memory at {status["memory"]}%')
    except Exception as e:
        cp.logger.exception(e)

    # Uptime
    status["uptime"] = round(cp.get('status/system/uptime'))

    # Get Ethernet port states and alert on change
    try:
        ethernet = {}
        ports = {}
        while not ports:
            ports = cp.get('status/ethernet')
        for port in ports:
            ethernet[f'{port["port"]}'] = port["link"]
        status["ethernet"] = ethernet
        if previous_ethernet:
            diff = dict(set(ethernet.items()) ^ set(previous_ethernet.items()))
            if diff:
                msg = {"type": "ethernet port state change", "ports": {}}
                for port in diff:
                    msg["ports"][port] = ethernet[port]
                cp.alert(msg)
        previous_ethernet = dict(ethernet)
    except Exception as e:
        cp.logger.exception(e)

    # Put status string to asset_id field
    cp.put('config/system/asset_id', json.dumps(status))

    # Pause for defined interval
    time.sleep(interval)

    '''
    Use these blocks of code to monitor various parameters:

    # CPU Utilization
    try:
        cpu = cp.get('status/system/cpu')
        status["cpu"] = round(sum(list(cpu.values())) * 100)
        if status["cpu"] > cpu_threshold:
            cp.alert(f'CPU at {status["cpu"]}%')
    except Exception as e:
        cp.logger.exception(e)

    # Memory Utilization
    try:
        mem = cp.get('status/system/memory')
        status["memory"] = round((mem["memtotal"] - mem["memavailable"]) / mem["memtotal"] * 100)
        if status["memory"] > mem_threshold:
            cp.alert(f'Memory at {status["memory"]}%')
    except Exception as e:
        cp.logger.exception(e)

    # Uptime
    status["uptime"] = round(cp.get('status/system/uptime'))

    # Get Ethernet port states and alert on change
    try:
        ethernet = {}
        ports = {}
        while not ports:
            ports = cp.get('status/ethernet')
        for port in ports:
            ethernet[f'{port["port"]}'] = port["link"]
        status["ethernet"] = ethernet
        if previous_ethernet:
            diff = dict(set(ethernet.items()) ^ set(previous_ethernet.items()))
            if diff:
                msg = {"type": "ethernet port state change", "ports": {}}
                for port in diff:
                    msg["ports"][port] = ethernet[port]
                cp.alert(msg)
        previous_ethernet = dict(ethernet)
    except Exception as e:
        cp.logger.exception(e)

'''
