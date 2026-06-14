
"""
SDK Application: throttle_cellular_datacap_rate_tiered

This SDK will enforce tiered rate shaping based on monthly data
capacity usage thresholds set within Connection Manager.  Usage
thresholds can be 70, 80, 90 and 100% per how the SDK is currently
written, and will only act upon those thresholds configured in
Connection Manager.  For instance, if only 80 and 100% limits are set
in Connection Manager, the SDK will only enforce throttling changes
when those 2 x percentages are reached.  At the start of the next
billing cycle, data usage alerts will be automatically cleared, and the
SDK will disable rate shaping.

Prerequisites:
- Enable Global Data Usage in Connection manager
- Establish data cap alert thresholds on the appropriate cellular
  interface profile(s)
"""

import cp
import time

class DataUsageCheck(object):
    """
    Establish global variables.

    Set rate shaping values (in Kbps) for 70, 80, 90 & 100% rate tiers.
    e.g. minbwup_70 & minbwdown_70 refers to upload & download at 70%
    
    Each of the rate tiers have a default throttling limit set below:
    70% - 6000Kbps Tx/Rx
    80% - 3000Kbps Tx/Rx
    90% - 1500Kbps Tx/Rx
    100% - 600Kbps Tx/Rx
    """
    
    minbwup_70 = 6000
    minbwdown_70 = 6000
    minbwup_80 = 3000
    minbwdown_80 = 3000
    minbwup_90 = 1500
    minbwdown_90 = 1500
    minbwup_100 = 600
    minbwdown_100 = 600
    STATUS_DEVS_PATH = '/status/wan/devices'
    STATUS_DATACAP_PATH = '/status/wan/datacap'
    CFG_RULES2_PATH = '/config/wan/rules2'

    def find_modems(self):
        while True:
            devs = cp.get(self.STATUS_DEVS_PATH)
            modems_list = [x for x in devs if x.startswith('mdm-')]
            cp.log(f'modems_list: {modems_list}')
            num_modems = len(modems_list)
            if not num_modems:
                cp.log('No Modems found at all yet')
                time.sleep(10)
                continue
            else:
                return modems_list

    def find_modem_profiles(self):
        wan_ifcs = cp.get(self.CFG_RULES2_PATH)
        modem_profiles_list = [x['_id_'] for x in wan_ifcs
            if x['trigger_string'].startswith('type|is|mdm')]
        cp.log(f'modem_profiles_list: {modem_profiles_list}')
        return modem_profiles_list

    def reset_throttle(self, modem_profiles_list, monthlyreset):
        for mdm in modem_profiles_list:
            if monthlyreset:
                cp.delete(self.CFG_RULES2_PATH + '/' + mdm
                               + '/bandwidth_egress')
                cp.delete(self.CFG_RULES2_PATH + '/' + mdm
                               + '/bandwidth_ingress')
            else:
                if 'bandwidth_egress' in cp.get(self.CFG_RULES2_PATH + '/' + mdm):
                    cp.delete(self.CFG_RULES2_PATH + '/' + mdm
                                   + '/bandwidth_egress')
                if 'bandwidth_ingress' in cp.get(self.CFG_RULES2_PATH + '/' + mdm):
                    cp.delete(self.CFG_RULES2_PATH + '/' + mdm
                                   + '/bandwidth_ingress')
        cp.put('config/qos/enabled', False)
        if monthlyreset:
            cp.log(
                'Monthly data usage reset - disabling reduced LTE data rate'
            )
            message = (
                f'Monthly data usage reset - disabling reduced LTE data rate '
                f'for {self.system_id} - {self.product_name} - Router ID: '
                f'{self.router_id}'
            )
            cp.alert(message)

    def set_throttle(self, modem_profiles_list, minbwup, minbwdown, tierset):
        for mdm in modem_profiles_list:
            cp.put(self.CFG_RULES2_PATH + '/' + mdm
                        + '/bandwidth_egress', minbwup)
            cp.put(self.CFG_RULES2_PATH + '/' + mdm
                        + '/bandwidth_ingress', minbwdown)
        cp.put('config/qos/enabled', True)
        cp.log('Exceeded monthly data usage threshold - ' + str(tierset)
                    + '% tier - reducing LTE data rate')
        message = (
            f'Exceeded monthly data usage threshold - reducing LTE data rate '
            f'for {self.system_id} - {self.product_name} - Router ID: '
            f'{self.router_id}'
        )
        cp.alert(message)

    def run(self):
        # Get info from router to populate description field in NCM
        # alert message
        self.product_name = cp.get('/status/product_info/product_name')
        self.system_id = cp.get('/config/system/system_id')
        self.router_id = cp.get('status/ecm/client_id')
        # Retrieve list of modems and their profiles
        modems_list = [str(x.split('-')[1]) for x in self.find_modems()]
        modem_profiles_list = self.find_modem_profiles()
        # Reset any throttling to account for router reboots.  If a
        # data cap alert is still active during the monthly cycle, the
        # appropriate rate shaping will be re-applied
        monthlyreset = False
        self.reset_throttle(modem_profiles_list, monthlyreset)
        time.sleep(5)

        currtierset = 0

        while True:
            if cp.get(self.STATUS_DATACAP_PATH + '/completed_alerts/'):
                alerts = cp.get(self.STATUS_DATACAP_PATH
                                     + '/completed_alerts/')
                limitreached = 0
                tierset = 0
                for indalert in alerts:
                    for modem in modems_list:
                        if (indalert['alerts'] and
                                indalert['rule_id'] == modem + '-monthly'):
                            if 'email_alert' in indalert['alerts']:
                                limitreached += 1
                                tierset = 100
                                minbwup = self.minbwup_100
                                minbwdown = self.minbwdown_100
                                continue
                            elif 'early_email-90.0' in indalert['alerts']:
                                limitreached += 1
                                tierset = 90
                                minbwup = self.minbwup_90
                                minbwdown = self.minbwdown_90
                                continue
                            elif 'early_email-80.0' in indalert['alerts']:
                                limitreached += 1
                                tierset = 80
                                minbwup = self.minbwup_80
                                minbwdown = self.minbwdown_80
                                continue
                            elif 'early_email-70.0' in indalert['alerts']:
                                limitreached += 1
                                tierset = 70
                                minbwup = self.minbwup_70
                                minbwdown = self.minbwdown_70
                                continue
                if limitreached > 0 and currtierset != tierset:
                    currtierset = tierset
                    self.set_throttle(modem_profiles_list, minbwup, minbwdown,
                        currtierset)
                elif limitreached == 0 and currtierset > 0:
                    currtierset = 0
                    monthlyreset = True
                    self.reset_throttle(modem_profiles_list, monthlyreset)
            elif currtierset > 0:
                currtierset = 0
                monthlyreset = True
                self.reset_throttle(modem_profiles_list, monthlyreset)
            time.sleep(10)

if __name__ == '__main__':
    throttle_cellular_datacap_rate_tiered = DataUsageCheck()
    throttle_cellular_datacap_rate_tiered.run()
    