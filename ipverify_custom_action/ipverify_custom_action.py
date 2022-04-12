# ipverify_custom_action - register function for callback on ipverify status change
# Log examples:
# 11:58:41 AM INFO ipverify_custom_action VPN Monitor Failed - Resetting Tunnel.
# 11:58:54 AM INFO ipverify_custom_action VPN Recovered.
# ipverify_uid is default uid for first ipverify test - modify as needed to match your test

from csclient import EventingCSClient
import time

ipverify_uid = "00000000-91a5-3a5b-ac9b-5ae6367d2d59"


def custom_action(path, value, *args):
    if not value:  # Test has failed
        cp.log("VPN Monitor Failed - Restarting Tunnel.")
        cp.put("config/vpn/enabled", False)
        time.sleep(1)
        cp.put("config/vpn/enabled", True)


cp = EventingCSClient("ipverify_custom_action")
cp.log("Starting...")
cp.on("put", f"status/ipverify/{ipverify_uid}/pass", custom_action)
time.sleep(999999)
