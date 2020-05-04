# ping_sample - sample using "ping" SDK Code Snippet

from csclient import EventingCSClient
import json


def ping(host, **kwargs):
    """
    :param host: string
        destination IP address to ping
    :param kwargs:
        "num": number of pings to send. Default is 4
        "srcaddr": source IP address.  If blank NCOS uses primary WAN.
    :return:
        dict {
            "tx": int - number of pings transmitted
            "rx": int - number of pings received
            "loss": float - percentage of lost pings (e.g. "25.0")
            "min": float - minimum round trip time in milliseconds
            "max": float - maximum round trip time in milliseconds
            "avg": float - average round trip time in milliseconds
            "error" string - error message if not successful
    requirements:
    cp = SDK CS Client.  (e.g. CSClient() or EventingCSClient())
    """
    import time
    start = {"host": host}
    for k, v in kwargs:
        start[k] = v
    cp.put('control/ping/start', start)
    result = {}
    pingstats = {'host': host}
    for k, v in kwargs:
        pingstats[k] = v
    try_count = 0
    while try_count < 15:
        result = cp.get('control/ping')
        if result and result.get('data', {}).get('status') in ["error", "done"]:
            break
        time.sleep(2)
        try_count += 1
    if try_count == 15:
        pingstats['error'] = "No Results - Execution Timed Out"
    else:
        # Parse results text
        parsedresults = result.get('data', {}).get('result').split('\n')
        i = 0
        index = 1
        for item in parsedresults:
            if item[0:3] == "---": index = i + 1
            i += 1
        pingstats['tx'] = int(parsedresults[index].split(' ')[0])
        pingstats['rx'] = int(parsedresults[index].split(' ')[3])
        pingstats['loss'] = float(parsedresults[index].split(' ')[6].split('%')[0])
        pingstats['min'] = float(parsedresults[index + 1].split(' ')[5].split('/')[0])
        pingstats['avg'] = float(parsedresults[index + 1].split(' ')[5].split('/')[1])
        pingstats['max'] = float(parsedresults[index + 1].split(' ')[5].split('/')[2])
    return pingstats


cp = EventingCSClient('ping_sample')
cp.log('Starting...')
cp.log('Output:\n' + json.dumps(ping('8.8.8.8')))
