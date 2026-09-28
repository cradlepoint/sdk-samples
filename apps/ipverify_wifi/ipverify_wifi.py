# ipverify_wifi - WiFi enabled when IPVerify Test "Wifi" passes, otherwise disabled.
from csclient import EventingCSClient
import time

test_name = 'wifi'  # Uses IPVerify test with this in its name.  Not case sensitive.

# Main App
cp = EventingCSClient('ipverify_wifi')
cp.log('Starting...')

cp.log('Initializing WiFi to disabled!')
cp.put('control/wlan/enable', False)

passing = False
while True:
    try:
        tests = cp.get('config/identities/ipverify')
        if tests is None:
            cp.log('CS unavailable, retrying in 5s')
            time.sleep(5)
            continue
        test_id = next(x for x in tests if test_name in x["name"].lower())["_id_"]
        if not test_id:
            cp.log('Test not found! Please configure IPVerify test with "wifi" in name.  Disabling WiFi!')
            cp.put('control/wlan/enable', False)
        else:
            test_pass = cp.get(f'status/ipverify/{test_id}/pass')
            if not passing and test_pass:
                cp.log('IPVerify test passed.  Enabling WiFi!')
                cp.put('control/wlan/enable', True)
                passing = True
            elif passing and not test_pass:
                cp.log('IPVerify test failed.  Disabling WiFi!')
                cp.put('control/wlan/enable', False)
                passing = False
        time.sleep(1)
    except Exception as e:
        cp.logger.exception(f'Error: {e}')
        cp.log('Error getting IPVerify test.  Disabling WiFi!')
        cp.put('control/wlan/enable', False)
        time.sleep(30)
