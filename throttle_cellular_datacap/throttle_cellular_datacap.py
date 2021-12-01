
"""
SDK Application: throttle_cellular_datacap

This SDK will enforce rate shaping based on reaching 100% of a monthly
data capacity threshold set within Connection Manager.  The SDK will
only act where the "Alert on Cap" is set.  At the start of the next
billing cycle, data usage alerts will be automatically cleared, and the
SDK will disable rate shaping.

Prerequisites:
- Enable Global Data Usage in Connection manager
- Enable "Alert on Cap" on the appropriate cellular interface profile(s)
"""

app_name = 'throttle_cellular_datacap'

try:
    from csclient import EventingCSClient
    import sys
    import time
    import json
    import traceback
    import logging.handlers
except Exception as ex:
    EventingCSClient().log(f'Import failure: {ex}')
    EventingCSClient().log(f'Traceback: {traceback.format_exc()}')
    sys.exit(-1)


class DataUsageCheck(object):
    """
    Establish global variables.
    
    Set rate shaping values (in Kbps) 
    """

    # Modem Defaults (as of 7.0.40) - Not used when QoS is Disabled
    maxbwup = 25000
    maxbwdown = 25000
    
    minbwup = 512
    minbwdown = 512
    capreached = 0
    STATUS_DEVS_PATH = '/status/wan/devices'
    STATUS_DATACAP_PATH = '/status/wan/datacap'
    CFG_RULES2_PATH = '/config/wan/rules2'

    def __init__(self):
        self.cp = EventingCSClient(app_name)

    def find_modems(self):
        while True:
            devs = self.cp.get(self.STATUS_DEVS_PATH)
            modems_list = [x for x in devs if x.startswith('mdm-')]
            self.cp.log(f'modems_list: {modems_list}')
            num_modems = len(modems_list)
            if not num_modems:
                self.cp.log('No Modems found at all yet')
                time.sleep(10)
                continue
            else:
                return modems_list

    def find_modem_profiles(self):
        wan_ifcs = self.cp.get(self.CFG_RULES2_PATH)
        modem_profiles_list = [x['_id_'] for x in wan_ifcs
            if x['trigger_string'].startswith('type|is|mdm')]
        self.cp.log(f'modem_profiles_list: {modem_profiles_list}')
        return modem_profiles_list

    def reset_throttle(self, modem_profiles_list, monthlyreset):
        for mdm in modem_profiles_list:
            if monthlyreset:
                self.cp.delete(self.CFG_RULES2_PATH + '/' + mdm
                               + '/bandwidth_egress')
                self.cp.delete(self.CFG_RULES2_PATH + '/' + mdm
                               + '/bandwidth_ingress')
            else:
                if 'bandwidth_egress' in self.cp.get(self.CFG_RULES2_PATH + '/' + mdm):
                    self.cp.delete(self.CFG_RULES2_PATH + '/' + mdm
                                   + '/bandwidth_egress')
                if 'bandwidth_ingress' in self.cp.get(self.CFG_RULES2_PATH + '/' + mdm):
                    self.cp.delete(self.CFG_RULES2_PATH + '/' + mdm
                                   + '/bandwidth_ingress')
        self.cp.put('config/qos/enabled', False)
        if monthlyreset:
            self.cp.log(
                'Monthly data usage reset - disabling reduced LTE data rate'
            )
            message = (
                f'Monthly data usage reset - disabling reduced LTE data rate '
                f'for {self.system_id} - {self.product_name} - Router ID: '
                f'{self.router_id}'
            )
            self.cp.alert(message)
            self.capreached = 0

    def set_throttle(self, modem_profiles_list):
        for mdm in modem_profiles_list:
            self.cp.put(self.CFG_RULES2_PATH + '/' + mdm
                        + '/bandwidth_egress', self.minbwup)
            self.cp.put(self.CFG_RULES2_PATH + '/' + mdm
                        + '/bandwidth_ingress', self.minbwdown)
        self.cp.put('config/qos/enabled', True)
        self.cp.log(
            'Exceeded monthly data usage threshold - reducing LTE data rate'
        )
        message = (
            f'Exceeded monthly data usage threshold - reducing LTE data rate '
            f'for {self.system_id} - {self.product_name} - Router ID: '
            f'{self.router_id}'
        )
        self.cp.alert(message)
        self.capreached = 1

    def run(self):
        # Get info from router to populate description field in NCM
        # alert message
        self.product_name = self.cp.get('/status/product_info/product_name')
        self.system_id = self.cp.get('/config/system/system_id')
        self.router_id = self.cp.get('status/ecm/client_id')
        # Retrieve list of modems and their profiles
        modems_list = [str(x.split('-')[1]) for x in self.find_modems()]
        modem_profiles_list = self.find_modem_profiles()
        # Reset any throttling to account for router reboots.  If a
        # data cap alert is still active during the monthly cycle, the
        # appropriate rate shaping will be re-applied
        monthlyreset = False
        self.reset_throttle(modem_profiles_list, monthlyreset)
        time.sleep(5)

        while True:
            if self.cp.get(self.STATUS_DATACAP_PATH + '/completed_alerts/'):
                alerts = self.cp.get(self.STATUS_DATACAP_PATH
                    + '/completed_alerts/')
                limitreached = 0
                for modem in modems_list:
                    if [x['rule_id'] for x in alerts if x['rule_id'] == modem
                            + '-monthly' if 'email_alert' in x['alerts']]:
                        limitreached += 1
                if limitreached > 0 and self.capreached == 0:
                    self.set_throttle(modem_profiles_list)
                elif limitreached == 0 and self.capreached == 1:
                    monthlyreset = True
                    self.reset_throttle(modem_profiles_list, monthlyreset)
            elif self.capreached == 1:
                monthlyreset = True
                self.reset_throttle(modem_profiles_list, monthlyreset)
            time.sleep(10)

if __name__ == '__main__':
    throttle_cellular_datacap = DataUsageCheck()
    throttle_cellular_datacap.run()
