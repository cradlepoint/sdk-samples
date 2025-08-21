""" AutoInstall is a Cradlepoint SDK Application used to choose the best SIM on install.
The application detects SIMs, and ensures (clones) they have unique WAN profiles for prioritization.
Then the app collects diagnostics and runs Ookla speedtests on each SIM.
Then the app prioritizes the SIMs WAN Profiles by TCP download speed.
Results are written to the log, set as the description field, and sent as a custom alert.
The app can be manually triggered again by clearing out the description field in NCM.
App settings can be configured in System > SDK Data."""

import cp
from speedtest import Speedtest
import time
import datetime
import json

defaults = {
    "MIN_DOWNLOAD_SPD": 0.0,  # Mbps
    "MIN_UPLOAD_SPD": 0.0,  # Mbps
    "SCHEDULE": 0,  # Run AutoInstall every {SCHEDULE} minutes. 0 = Only run on boot.
    "NUM_ACTIVE_SIMS": 0,  # Number of fastest (download) SIMs to keep active.  0 = all; do not disable SIMs
    "ONLY_RUN_ONCE": False  # True means do not run if AutoInstall has been run on this device before.
}

class AutoInstallException(Exception):
    """General AutoInstall Exception."""
    pass


class Timeout(AutoInstallException):
    """Timeout Exception."""
    pass


class OneModem(AutoInstallException):
    """Only One Modem Found Exception."""
    pass


class RunBefore(AutoInstallException):
    """AutoInstall has already been run before Exception."""
    pass


class AutoInstall(object):
    """Main Application."""
    MIN_DOWNLOAD_SPD = 0.0  # Mbps
    MIN_UPLOAD_SPD = 0.0  # Mbps
    SCHEDULE = 0  # Run AutoInstall every {SCHEDULE} minutes. 0 = Only run on boot.
    NUM_ACTIVE_SIMS = 0  # Number of fastest (download) SIMs to keep active.  0 = all; do not disable SIMs
    ONLY_RUN_ONCE = False  # True means do not run if AutoInstall has been run on this device before.

    STATUS_DEVS_PATH = '/status/wan/devices'
    CFG_RULES2_PATH = '/config/wan/rules2'
    CTRL_WAN_DEVS_PATH = '/control/wan/devices'
    API_URL = 'https://www.cradlepointecm.com/api/v2'
    CONNECTION_STATE_TIMEOUT = 15 * 60  # 7 Min
    NETPERF_TIMEOUT = 5 * 60  # 5 Min
    sims = {}

    def __init__(self):
        self.speedtest = Speedtest()

    def get_config(self, name):
        """Return config from /config/system/sdk/appdata."""
        appdata = cp.get('config/system/sdk/appdata')
        try:
            config = json.loads([x["value"] for x in appdata if x["name"] == name][0])
            if not config:
                config = defaults
        except:
            config = defaults
            cp.post('config/system/sdk/appdata', {"name": name, "value": json.dumps(config)})
        self.MIN_DOWNLOAD_SPD = config["MIN_DOWNLOAD_SPD"]
        self.MIN_UPLOAD_SPD = config["MIN_UPLOAD_SPD"]
        self.SCHEDULE = config["SCHEDULE"]
        self.NUM_ACTIVE_SIMS = config["NUM_ACTIVE_SIMS"]
        self.ONLY_RUN_ONCE = config["ONLY_RUN_ONCE"]
        return

    def check_if_run_before(self):
        """Check if AutoInstall has been run before and return boolean."""
        if self.ONLY_RUN_ONCE:
            if cp.get('config/system/snmp/persisted_config') == 'AutoInstall':
                cp.log(
                    'ERROR - AutoInstall has been run before!')
                raise RunBefore(
                    'ERROR - AutoInstall has been run before!')
        return False

    def wait_for_ncm_sync(self):
        """Blocking call to wait until WAN is connected, and NCM is connected and synced."""
        # WAN connection_state
        if cp.get('status/wan/connection_state') != 'connected':
            cp.log('Waiting until WAN is connected...')
        timeout_count = 500
        while cp.get('/status/wan/connection_state') != 'connected':
            timeout_count -= 1
            if not timeout_count:
                raise Timeout('WAN not connecting')
            time.sleep(2)

        # ECM State
        if cp.get('status/ecm/state') != 'connected':
            cp.log('Waiting until NCM is connected...')
            cp.put('/control/ecm', {'start': True})
        timeout_count = 500
        while cp.get('/status/ecm/state') != 'connected':
            timeout_count -= 1
            if not timeout_count:
                raise Timeout('NCM not connecting')
            time.sleep(2)

        # ECM Sync
        if cp.get('status/ecm/sync') != 'ready':
            cp.log('Waiting until NCM is synced...')
            cp.put('/control/ecm', {'start': True})
        timeout_count = 500
        while cp.get('/status/ecm/sync') != 'ready':
            cp.put('/control/ecm', {'start': True})
            timeout_count -= 1
            if not timeout_count:
                raise Timeout('NCM not syncing')
            time.sleep(2)
        return

    def NCM_suspend(self):
        """Blocking call to wait until NCM synced, then stopped."""
        cp.log('Stopping NCM')
        timeout_count = 500
        while not 'ready' == cp.get('/status/ecm/sync'):
            timeout_count -= 1
            if not timeout_count:
                raise Timeout('NCM sync not ready')
            time.sleep(2)
        cp.put('/control/ecm', {'stop': True})
        timeout_count = 500
        while not 'stopped' == cp.get('/status/ecm/state'):
            timeout_count -= 1
            if not timeout_count:
                raise Timeout('NCM not stopping')
            time.sleep(2)

    def find_sims(self):
        """Detects all available SIMs in router and stores in self.sims."""
        timeout = 0
        while True:
            sims = {}
            wan_devs = cp.get(self.STATUS_DEVS_PATH) or {}
            for uid, status in wan_devs.items():
                if uid.startswith('mdm-'):
                    error_text = status.get('status', {}).get('error_text', '')
                    if error_text:
                        if 'NOSIM' in error_text:
                            continue
                    sims[uid] = status
            num_sims = len(sims)
            if not num_sims:
                cp.log('No SIMs found at all yet')
            if num_sims < 2:
                cp.log('Only 1 SIM found!')
            if timeout >= 10:
                cp.log('Timeout: Did not find 2 or more SIMs')
                raise Timeout('Did not find 2 or more SIMs')
            if num_sims >= 2:
                break
            time.sleep(10)
            timeout += 1

        cp.log(f'Found SIMs: {sims.keys()}')
        self.sims = sims
        return True
                    
    def create_unique_WAN_profiles(self):
        """Ensures that each modem has a unique WAN profile (rule) for prioritization."""
        repeat = True
        while repeat:
            self.find_sims()
            for dev_UID, dev_status in self.sims.items():
                try:
                    self.sims[dev_UID]["rule_id"] = dev_status.get('config', {}).get('_id_')
                    self.sims[dev_UID]["priority"] = float(dev_status.get('config', {}).get('priority'))
                    self.sims[dev_UID]["port"] = dev_status.get('info', {}).get('port')
                    self.sims[dev_UID]["sim"] = dev_status.get('info', {}).get('sim')
                    i = 0.1
                    found_self = False
                    repeat = False
                    for dev, stat in self.sims.items():
                        if stat.get('config', {}).get('_id_') == self.sims[dev_UID]["rule_id"]:
                            if not found_self:
                                found_self = True
                            else:  # Two SIMs using same WAN profile
                                config = cp.get(
                                    f'config/wan/rules2/'
                                    f'{self.sims[dev_UID]["rule_id"]}')
                                config.pop('_id_')
                                config['priority'] += i
                                i += 0.1
                                config['trigger_name'] = f'{stat["diagnostics"]["HOMECARRID"]} {stat["info"]["port"]} {stat["info"]["sim"]}'
                                config['trigger_string'] = \
                                    f'type|is|mdm%sim|is|{stat["info"]["sim"]}%port|is|{stat["info"]["port"]}'
                                cp.log(f'NEW WAN RULE: {config}')
                                rule_index = cp.post('config/wan/rules2/', config)["data"]
                                new_id = cp.get(f'config/wan/rules2/{rule_index}/_id_')
                                self.sims[dev_UID]["config"]["_id_"] = new_id
                                repeat = True
                except Exception as e:
                    cp.log(f'Exception: {e}')
                    continue

    def modem_state(self, sim, state):
        """Blocking call that will wait until a given state is shown as the modem's status."""
        timeout_counter = 0
        sleep_seconds = 0
        conn_path = '%s/%s/status/connection_state' % (self.STATUS_DEVS_PATH, sim)
        cp.log(f'Connecting {self.port_sim(sim)}')
        while True:
            sleep_seconds += 5
            conn_state = cp.get(conn_path)
            cp.log(f'Waiting for {self.port_sim(sim)} to connect.  Current State={conn_state}')
            if conn_state == state:
                break
            if timeout_counter > self.CONNECTION_STATE_TIMEOUT:
                cp.log(f'Timeout waiting on {self.port_sim(sim)}')
                raise Timeout(conn_path)
            time.sleep(min(sleep_seconds, 45))
            timeout_counter += sleep_seconds
        cp.log(f'{self.port_sim(sim)} connected.')
        return True

    def iface(self, sim):
        """Return iface value for sim."""
        iface = cp.get('%s/%s/info/iface' % (self.STATUS_DEVS_PATH, sim))
        return iface

    def port_sim(self, sim):
        """Return port value for sim."""
        return f'{self.sims[sim]["info"]["port"]} {self.sims[sim]["info"]["sim"]}'

    def do_speedtest(self, sim):
        """Run Ookla speedtests and return TCP down and TCP up in Mbps."""
        servers = []
        self.speedtest.get_servers(servers)
        self.speedtest.get_best_server()
        cp.log(f'Running TCP Download test on {sim}...')
        self.speedtest.download()
        cp.log(f'Running TCP Upload test on {sim}...')
        self.speedtest.upload(pre_allocate=False)
        down = self.speedtest.results.download / 1000 / 1000
        up = self.speedtest.results.upload / 1000 / 1000
        cp.log(f'Speedtest complete for {sim}.')
        return down, up

    def test_sim(self, device):
        """Get diagnostics, run speedtests, and verify minimums."""
        try:
            if self.modem_state(device, 'connected'):

                # Get diagnostics and log it
                diagnostics = cp.get(f'{self.STATUS_DEVS_PATH}/{device}/diagnostics')
                self.sims[device]['diagnostics'] = diagnostics
                cp.log(
                    f'Modem Diagnostics: {self.port_sim(device)} RSRP:{diagnostics.get("RSRP")}')

                # Do speedtest and log results
                self.sims[device]['download'], self.sims[device]['upload'] = self.do_speedtest(device)
                cp.log(
                    f'Speedtest Results: {self.port_sim(device)} TCP Download: '
                    f'{self.sims[device]["download"]}Mbps TCP Upload: {self.sims[device]["upload"]}Mbps')

                # Verify minimum speeds
                if self.sims[device].get('download', 0.0) > self.MIN_DOWNLOAD_SPD and \
                        self.sims[device].get('upload', 0.0) > self.MIN_UPLOAD_SPD:
                    return True
                else:  # Did not meet minimums
                    cp.log(f'{self.port_sim(device)} Failed to meet minimums! MIN_DOWNLOAD_SPD: {self.MIN_DOWNLOAD_SPD} MIN_UPLOAD_SPD: {self.MIN_UPLOAD_SPD}')
                    return False
        except Timeout:
            message = f'Timed out running speedtest on {self.port_sim(device)}'
            cp.log(message)
            cp.alert(message)
            self.sims[device]['download'] = self.sims[device]['upload'] = 0.0
            return False

    def create_message(self, uid, *args):
        """Create text results message for log, alert, and description."""
        message = ''
        try:
            for arg in args:
                if arg == 'download':
                    message = "DL:{:.2f}Mbps".format(self.sims[uid]['download']) if not message else ' '.join(
                        [message, "DL:{:.2f}Mbps".format(self.sims[uid]['download'])])
                elif arg == 'upload':
                    message = "UL:{:.2f}Mbps".format(self.sims[uid]['upload']) if not message else ' '.join(
                        [message, "UL:{:.2f}Mbps".format(self.sims[uid]['upload'])])
                elif arg in ['PRD', 'HOMECARRID', 'RFBAND']:  # Do not include labels for these fields
                    message = "{}".format(self.sims[uid]['diagnostics'].get(arg)) if not message else ' '.join(
                        [message, "{}".format(self.sims[uid]['diagnostics'].get(arg))])
                else:  # Include field labels (e.g. "RSRP:-82")
                    message = "{}:{}".format(arg, self.sims[uid]['diagnostics'].get(arg)) if not message else ' '.join(
                        [message, "{}:{}".format(arg, self.sims[uid]['diagnostics'].get(arg))])
        except Exception as e:
            cp.log(e)
        return message

    def prioritize_rules(self, sim_list):
        """Re-prioritize WAN rules by TCP download speed."""
        lowest_priority = 100
        for uid in sim_list:
            priority = cp.get(f'status/wan/devices/{uid}/config/priority')
            if priority < lowest_priority:
                lowest_priority = priority
        for i, uid in enumerate(sim_list):
            rule_id = cp.get(f'status/wan/devices/{uid}/config/_id_')
            new_priority = lowest_priority + i * .1
            cp.log(f'New priority for {uid} = {new_priority}')
            cp.put(f'config/wan/rules2/{rule_id}/priority', new_priority)
        return

    def run(self):
        """Start of Main Application."""
        self.get_config('AutoInstall')
        cp.log(
            f'AutoInstall Starting... MIN_DOWNLOAD_SPD:{self.MIN_DOWNLOAD_SPD} MIN_UPLOAD_SPD:{self.MIN_UPLOAD_SPD} '
            f'SCHEDULE:{self.SCHEDULE} NUM_ACTIVE_SIMS:{self.NUM_ACTIVE_SIMS} ONLY_RUN_ONCE:{self.ONLY_RUN_ONCE}')

        self.check_if_run_before()

        self.wait_for_ncm_sync()

        # Get info from router
        product_name = cp.get("/status/product_info/product_name")
        system_id = cp.get("/config/system/system_id")
        router_id = cp.get('status/ecm/client_id')

        # Send startup alert
        message = f'AutoInstall Starting! {system_id} - {product_name} - Router ID: {router_id}'
        cp.log(f'Sending alert to NCM: {message}')
        cp.alert(message)

        self.create_unique_WAN_profiles()

        # Pause for 3 seconds to allow NCM Alert to be sent before suspending NCM
        time.sleep(3)
        self.NCM_suspend()

        success = False  # AutoInstall Success Status - Becomes True when a SIM meets minimum speeds

        # Test the connected SIM first
        primary_device = cp.get('status/wan/primary_device')
        if 'mdm-' in primary_device:  # make sure its a modem
            if self.test_sim(primary_device):
                success = True

        # Disable all wan rules
        wan_rules = cp.get('config/wan/rules2')
        for i, uid in enumerate(wan_rules):
            cp.put(f'config/wan/rules2/{i}/disabled', True)
        time.sleep(5)

        # test remaining SIMs
        for sim in self.sims:
            if not self.sims[sim].get('download'):
                rule_id = cp.get(f'status/wan/devices/{sim}/config/_id_')
                cp.put(f'config/wan/rules2/{rule_id}/disabled', False)
                if self.test_sim(sim):
                    success = True
                cp.put(f'config/wan/rules2/{rule_id}/disabled', True)

        # Prioritizes SIMs based on download speed
        sorted_results = sorted(self.sims, key=lambda x: int(self.sims[x]['download']), reverse=True)  # Sort by download speed
        # sorted_results = sorted(self.sims, key=lambda x: int(self.sims[x]['diagnostics']['RSRP']), reverse=True)  # Sort by RSRP

        # Configure WAN Profiles
        cp.log(f'Prioritizing SIMs: {sorted_results}')
        self.prioritize_rules(sorted_results)

        # Enable all wan rules
        wan_rules = cp.get('config/wan/rules2')
        for i, uid in enumerate(wan_rules):
            cp.put(f'config/wan/rules2/{i}/disabled', False)
        time.sleep(3)

        # Build results text
        results_text = datetime.datetime.now().strftime('%m/%d/%y %H:%M:%S')  # Start with a timestamp
        if not success:
            results_text += f' FAILED TO MEET MINIMUMS! MIN_DOWNLOAD_SPD:{self.MIN_DOWNLOAD_SPD} MIN_UPLOAD_SPD:{self.MIN_UPLOAD_SPD}'
        for uid in sorted_results:  # Add the results of each SIM with the fields specified:
            results_text = ' | '.join(
                [results_text, self.create_message(uid, 'PRD', 'HOMECARRID', 'RFBAND', 'RSRP', 'download', 'upload')])

        # put results to description field
        cp.put('config/system/desc', results_text[:1023])

        # Mark as RUN for ONLY_RUN_ONCE flag
        cp.put('config/system/snmp/persisted_config', 'AutoInstall')

        # Complete!  Send results.
        message = f"AutoInstall Complete! {system_id} Results: {results_text}"
        self.wait_for_ncm_sync()
        cp.log(message)
        cp.alert(message)


def manual_test(path, desc, *args):
    """Callback function for triggering manual tests."""
    if not desc:  # blank description, run app
        try:
            autoinstall.run()
        except Exception as e:
            cp.log(f"Failed with exception={type(e)} err={str(e)}")
        finally:
            cp.put('/control/ecm', {'start': 'true'})


if __name__ == '__main__':
    cp.log('Starting...')
    while not cp.get('status/wan/connection_state') == 'connected':
        time.sleep(1)
    while True:
        try:
            autoinstall = AutoInstall()
            break
        except:
            cp.log('Error getting http://www.speedtest.net/speedtest-config.php - will try again in 5 seconds.')
            time.sleep(5)
    try:
        # Setup callback for manual testing:
        cp.register('put', '/config/system/desc', manual_test)

        # RUN AUTOINSTALL:
        manual_test(None, None)

        # Sleep forever / wait for manual tests:
        while True:
            time.sleep(1)
    except Exception as err:
        cp.log(f"Failed with exception={type(err)} err={str(err)}")
