"""
    ports_status

    Application Purpose
    ===================
    This application will set the device description to visually show
    the LAN/WAN/WWAN/Modem/IP Verify status

    Description is updated every 5 seconds, but only synced to NCM
    if there is a change from the current description

    Sample Description Output
    ===================
    WAN: 🟢 LAN: 🟢 ⚫️ ⚫️ ⚫️ ⚫️ 🟢 ⚫️ ⚫️ ⚫️ MDM: 🟡 MDM: ⚫️ IPV: 🟢
"""

import time
import cp

APP_NAME = 'PORTS_STATUS'
DEBUG = False
MODELS_WITHOUT_WAN = ['CBA', 'W18', 'W200', 'W400', 'L950', 'IBR200', '4250']

cp.log('Starting...')

if DEBUG:
    cp.log("DEBUG ENABLED")

if DEBUG:
    cp.log("Getting Model")

"""Get model number, since some models don't have ethernet WAN"""
model = ''
model = cp.get('/status/product_info/product_name')
if DEBUG:
    cp.log(model)

while True:
    try:
        ports_status = ""
        is_available_modem = 0
        is_available_wan = 0
        is_available_wwan = 0
        is_configured_wwan = 0

        wans = cp.get('/status/wan/devices')
        mdm_present = False
        for wan in wans:
            if 'mdm' in wan:
                mdm_present = True
        ports = cp.get('/status/ethernet')

        if wans and ports and mdm_present:
            """Get status of ethernet WANs"""
            for wan in (wan for wan in wans if 'ethernet' in wan):

                summary = cp.get('/status/wan/devices/{}/status/summary'.format(wan))
                if summary:
                    if 'connected' in summary:
                        is_available_wan = 1
                        ports_status += "WAN: 🟢 "

                    elif 'available' in summary or 'standby' in summary:
                        is_available_wan = 2
                        ports_status += "WAN: 🟡 "

                    elif 'error' in summary:
                        continue

            """If no active/standby WANs are found, show offline"""
            if is_available_wan == 0 and not any(x in model for x in MODELS_WITHOUT_WAN):
                ports_status += "WAN: ⚫️ "

            ports_status += "LAN:"

            """Get status of all ethernet ports"""
            for port in ports:
                """Ignore ethernet0 (treat as WAN) except for IBR200/CBA"""
                if (port['port'] == 0 and any(x in model for x in MODELS_WITHOUT_WAN)) or (port['port'] >= 1):
                    if port['link'] == "up":
                        ports_status += " 🟢 "
                    else:
                        ports_status += " ⚫️ "

            """Get status of all modems"""
            for wan in (wan for wan in wans if 'mdm' in wan):

                """Filter to only track modems. Will show green if at least one modem is active"""
                if 'mdm' in wan:

                    """Get modem status for each modem"""
                    summary = cp.get('/status/wan/devices/{}/status/summary'.format(wan))

                    if summary:
                        #cp.log("Modem {} Summary: {}".format(wan, summary))
                        if 'connected' in summary:
                            is_available_modem = 1
                            ports_status += "MDM: 🟢 "

                        elif 'available' in summary or 'standby' in summary or \
                                'suspended' in summary or 'connecting' in summary or \
                                'transitioning' in summary or 'unready' in summary or \
                                'unconfigured' in summary or 'operation failed' in summary or \
                                'switch' in summary:
                            is_available_modem = 2
                            ports_status += "MDM: 🟡 "

                        else:
                            ports_status += "MDM: ⚫️ "

            for wan in (wan for wan in wans if 'wwan' in wan):
                is_configured_wwan = 1
                summary = cp.get('/status/wan/devices/{}/status/summary'.format(wan))

                if summary:

                    if 'connected' in summary:
                        is_available_wwan = 1
                        ports_status += "WWAN: 🟢 "
                        """Stop checking if active WWAN is found"""
                        break

                    elif 'available' in summary or 'standby' in summary or \
                            'suspended' in summary or 'connecting' in summary or \
                            'transitioning' in summary or 'unready' in summary or \
                            'unconfigured' in summary or 'operation failed' in summary or \
                            'switch' in summary:
                        is_available_wwan = 2
                        ports_status += "WWAN: 🟡 "
                        """If standby WWAN found, keep checking for an active one"""
                        continue

                    elif 'error' in summary:
                        continue

            """If no active/standby WANs are found, show offline"""
            if is_available_wwan == 0 and is_configured_wwan == 1:
                ports_status += "WWAN: ⚫️ "

            ipverifys = cp.get('/status/ipverify')
            if ipverifys:
                ports_status += "IPV:"

                for ipverify in ipverifys:
                    testpass = cp.get('/status/ipverify/{}/pass'.format(ipverify))
                    if testpass:
                        ports_status += " 🟢 "
                    else:
                        ports_status += " ⚫️ "


            """Write string to description field"""
            if DEBUG:
                cp.log("WRITING DESCRIPTION")
                cp.log(ports_status)
            cp.put('config/system/desc', ports_status)

    except Exception as err:
        cp.log("Failed with exception={} err={}".format(type(err), str(err)))

    """Wait 5 seconds before checking again"""
    time.sleep(5)
