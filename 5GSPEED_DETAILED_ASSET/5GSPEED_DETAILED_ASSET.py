'''

Description: The 5GSPEED_DETAILED SDK application will uses Ookla Speedtest python library and designed to perform Ookla speedtest from a Cradlepoint Endpoint which will enable comprehensive and end-to-end speedtest result.

Steps to use:
=============
perform any of the following:

1. Use NCM API PUT router request to clear the asset ID and to run the SDK speedtest. Wait for 1 min, and run NCM API Get router request to get the result.

2. Make the asset_id blank in NCM > Devices tab

3. Go to device console and enter put 5GSPEED 1


Installation:
=============
Go to NCM > Tools page and load the script. Afterwards, load the script in the desired NCM Group where the router belongs


Results:
========
All results will be displayed in asset ID column of the router.

Sample result:
DL:52.54Mbps - UL:16.55Mbps - Ping:9.715ms - Server:Telstra - ISP:Vocus Communications - TimeGMT:2023-04-11T01:06:43.758382Z - URL:http://www.speedtest.net/result/14595594656.png


For any questions, please reach out to developer jon.campo@cradlepoint.com

DISCLAIMER:
==========
Please note: This script is meant for demo purposes only. All tools/ scripts in this repo are released for use "AS IS" without any warranties of any kind, including, but not limited to their installation, use, or performance. Any use of these scripts and tools is at your own risk. There is no guarantee that they have been through thorough testing in a comparable environment and we are not responsible for any damage or data loss incurred with their use. You are responsible for reviewing and testing any scripts you run thoroughly before use in any non-testing environment.


'''

from csclient import EventingCSClient
from speedtest import Speedtest
import time

def asset_id_check(path, asset_id, *args):
    if not asset_id:
        cp.log('Initiating Speedtest due to asset id empty...')
        #cp.put('status/5GSPEED', "1")
        speedtest()
        return

#def speedtest(path, value, *args):
def speedtest():
    cp.log('Ongoing Speedtest...')
    #cp.put('config/system/asset_id', "Ongoing Speedtest. Please wait 1 minute for the result")
    #time.sleep(10)

    #servers = []
    s = Speedtest()

    #Find the best ookla speedtest server based from latency and ping
    cp.log("Finding the Best Ookla Speedtest.net Server...")
    server = s.get_best_server()
    cp.log('Found Best Ookla Speedtest.net Server: {}'.format(server['sponsor']))

    p = s.results.ping
    cp.log('Ping: {}ms'.format(p))

    #Perform Download ookla download speedtest
    cp.log("Performing Ookla Speedtest.net Download Test...")
    d = s.download()
    cp.log('Ookla Speedtest.net Download: {:.2f} Kb/s'.format(d / 1000))

    #Perform Upload ookla upload speedtest. Option pre_allocate false prevents memory error
    cp.log("Performing Ookla Speedtest.net Upload Test...")
    u = s.upload(pre_allocate=False)
    cp.log('Ookla Speedtest.net Upload: {:.2f} Kb/s'.format(u / 1000))

    #Access speedtest result dictionary
    res = s.results.dict()

    #share link for ookla test result page
    share = s.results.share()

    t = res['timestamp']

    i = res["client"]["isp"]

    s = server['sponsor']

    #return res["download"], res["upload"], res["ping"],res['timestamp'],server['sponsor'],res["client"]["isp"], share


    cp.log('')
    cp.log('Test Result')
    cp.log('Timestamp GMT: {}'.format(t))
    cp.log('Client ISP: {}'.format(i))
    cp.log('Ookla Speedtest.net Server: {}'.format(s))
    cp.log('Ping: {}ms'.format(p))
    cp.log('Download Speed: {:.2f} Mb/s'.format(d / 1000 / 1000))
    cp.log('Upload Speed: {:.2f} Mb/s'.format(u / 1000 / 1000))
    cp.log('Ookla Speedtest.net URL Result: {}'.format(share))

    download = '{:.2f}'.format(d / 1000 / 1000)
    upload = '{:.2f}'.format(u / 1000 / 1000)
    #text = 'DL:{}Mbps UL:{}Mbps - {}'.format(download, upload,share)
    text = 'DL:{}Mbps - UL:{}Mbps - Ping:{}ms - Server:{} - ISP:{} - TimeGMT:{} - URL:{}'.format(download, upload, p, s, i, t, share)
    cp.put('config/system/asset_id', text)

    cp.log(f'Speedtest Complete! {text}')
    return



try:
    cp = EventingCSClient('5GSPEEDTEST')


    cp.log('Starting... To start speedtest: put status/5GSPEED 1 or make asset id blank')
    cp.on('put', 'config/system/asset_id', asset_id_check)
    cp.on('put', 'status/5GSPEED', speedtest)
    asset_id = cp.get('/config/system/asset_id')
    #cp.log(asset_id)

    #Performed if asset ID is blank
    if asset_id is "" or asset_id is None:

        connected = False
        while not connected:
            connected = cp.get('status/ecm/state') == 'connected'
            time.sleep(1)

        #cp.log('Detected at bootup that the asset id is blank. Starting the 5GSpeedtest in 1 minute to allow device finish its bootup...')
        cp.log('Detected at bootup that the asset id is blank.')
        #time.sleep(60)
        cp.log('Starting Initial 5GSpeedtest with asset id blank...')
        #cp.put('status/5GSPEED', '1')
        speedtest()

    time.sleep(999999)
except Exception as e:
    cp.log(e)


