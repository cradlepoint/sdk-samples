# pylint: disable=invalid-name, missing-docstring, line-too-long, bad-continuation
"""
    Boot2 v2.0 - csclient.py version

    Copyright © 2020 Cradlepoint, Inc. <www.cradlepoint.com>.  All rights reserved.

    This file contains confidential information of Cradlepoint, Inc. and your use of this file is subject to the
    Cradlepoint Software License Agreement distributed with this file. Unauthorized reproduction or distribution of
    this file is subject to civil and criminal penalties.

    Desc:
        Run speedtest on all SIMs
        Prioritize SIMs based on throughput.
        Log results to custom fields in NCM.
        
"""

from csclient import EventingCSClient
import time
import requests
import datetime


class Boot2Exception(Exception):
    pass


class Timeout(Boot2Exception):
    pass


class SocketLost(Boot2Exception):
    pass


class OneModem(Boot2Exception):
    pass


class RunBefore(Boot2Exception):
    pass


default_speedtest = {
    "input": {
        "options": {
            "limit": {
                "size": 0,
                "time": 15
            },
            "port": None,
            "fwport": None,
            "host": "",
            "ifc_wan": None,
            "tcp": True,
            "udp": False,
            "send": True,
            "recv": True,
            "rr": False
        },
        "tests": None
    },
    "run": 1
}


apikeys = {'X-ECM-API-ID': 'YOUR',
           'X-ECM-API-KEY': 'KEYS',
           'X-CP-API-ID': 'GO',
           'X-CP-API-KEY': 'HERE',
           'Content-Type': 'application/json'}


class SIMSpeedTest(object):
    MIN_DOWNLOAD_SPD = 0.0  # Mbps
    MIN_UPLOAD_SPD = 0.0  # Mbps
    SCHEDULE = 0  # Run Boot2 every {SCHEDULE} minutes. 0 = Only run on boot.
    NUM_ACTIVE_SIMS = 0  # Number of fastest (download) SIMs to keep active.  0 = all; do not disable SIMs
    ONLY_RUN_ONCE = False  # True means do not run if Boot2 has been run on this device before.

    STATUS_DEVS_PATH = '/status/wan/devices'
    CFG_RULES2_PATH = '/config/wan/rules2'
    CTRL_WAN_DEVS_PATH = '/control/wan/devices'
    API_URL = 'https://www.cradlepointecm.com/api/v2'
    CONNECTION_STATE_TIMEOUT = 7 * 60  # 7 Min
    NETPERF_TIMEOUT = 5 * 60  # 5 Min
    sims = {}

    def __init__(self):
        self.client = EventingCSClient('Boot2')

    def check_if_run_before(self):
        if self.ONLY_RUN_ONCE:
            if self.client.get('/config/wan/rules2/0/_id_') == '00000000-1234-1234-1234-1234567890ab':
                self.client.log('ERROR - Boot2 has been run before! /config/wan/rules2/0/_id = 00000000-1234-1234-1234-1234567890ab')
                raise RunBefore('ERROR - Boot2 has been run before! /config/wan/rules2/0/_id = 00000000-1234-1234-1234-1234567890ab')
        return False

    def wait_for_ncm_sync(self):
        # WAN connection_state
        if self.client.get('status/wan/connection_state') != 'connected':
            self.client.log('Waiting until WAN is connected...')
        timeout_count = 500
        while self.client.get('/status/wan/connection_state')!= 'connected':
            timeout_count -= 1
            if not timeout_count:
                raise Timeout('WAN not connecting')
            time.sleep(2)

        # ECM State
        if self.client.get('status/ecm/state') != 'connected':
            self.client.log('Waiting until NCM is connected...')
            self.client.put('/control/ecm', {'start': True})
        timeout_count = 500
        while self.client.get('/status/ecm/state') != 'connected':
            timeout_count -= 1
            if not timeout_count:
                raise Timeout('NCM not connecting')
            time.sleep(2)

        # ECM Sync
        if self.client.get('status/ecm/sync') != 'ready':
            self.client.log('Waiting until NCM is synced...')
            self.client.put('/control/ecm', {'start': True})
        timeout_count = 500
        while self.client.get('/status/ecm/sync') != 'ready':
            self.client.put('/control/ecm', {'start': True})
            timeout_count -= 1
            if not timeout_count:
                raise Timeout('NCM not connecting')
            time.sleep(2)

        return

    def NCM_suspend(self):
        self.client.log('Stopping NCM')
        timeout_count = 500
        while not 'ready' == self.client.get('/status/ecm/sync'):
            timeout_count -= 1
            if not timeout_count:
                raise Timeout('NCM sync not ready')
            time.sleep(2)
        self.client.put('/control/ecm', {'stop': True})
        timeout_count = 500
        while not 'stopped' == self.client.get('/status/ecm/state'):
            timeout_count -= 1
            if not timeout_count:
                raise Timeout('NCM not stopping')
            time.sleep(2)

    def find_sims(self):
        while True:
            sims = {}
            wan_devs = self.client.get(self.STATUS_DEVS_PATH) or {}
            for uid, status in wan_devs.items():
                if uid.startswith('mdm-'):
                    error_text = status.get('status', {}).get('error_text', '')
                    if error_text:
                        if 'NOSIM' in error_text:
                            continue
                    sims[uid] = status
            num_sims = len(sims)
            if not num_sims:
                self.client.log('No SIMs found at all yet')
                time.sleep(10)
                continue
            if num_sims < 2:
                self.client.log('Only 1 SIM found!')
                raise OneModem('Only 1 SIM found!')
            else:
                break
        self.client.log(f'Found SIMs: {sims.keys()}')
        self.sims = sims
        return True

    def modem_state(self, sim, state):
        # Blocking call that will wait until a given state is shown as the modem's status
        timeout_counter = 0
        sleep_seconds = 0
        conn_path = '%s/%s/status/connection_state' % (self.STATUS_DEVS_PATH, sim)
        self.client.log(f'Connecting {self.port_sim(sim)}')
        while True:
            sleep_seconds += 5
            conn_state = self.client.get(conn_path)
            self.client.log(f'Waiting for {self.port_sim(sim)} to connect.  Current State={conn_state}')
            if conn_state == state:
                break
            if timeout_counter > self.CONNECTION_STATE_TIMEOUT:
                self.client.log(f'Timeout waiting on {self.port_sim(sim)}')
                raise Timeout(conn_path)
            time.sleep(min(sleep_seconds, 45))
            timeout_counter += sleep_seconds
        self.client.log(f'{self.port_sim(sim)} connected.')
        return True

    def iface(self, sim):
        iface = self.client.get('%s/%s/info/iface' % (self.STATUS_DEVS_PATH, sim))
        return iface

    def port_sim(self, sim):
        return f'{self.sims[sim]["info"]["port"]} {self.sims[sim]["info"]["sim"]}'

    def run_speedtest(self, speedtest):
        self.client.put('/state/system/netperf', {"run_count": 0})
        res = self.client.put("/control/netperf", speedtest)
        self.client.log(f'Starting Speedtest... {res}')

        timeout_counter = 0
        # wait for results
        delay = speedtest['input']['options']['limit']['time'] + 8
        status_path = "/control/netperf/output/status"
        while True:
            time.sleep(delay)
            status = self.client.get(status_path)
            if status == 'complete':
                break
            if timeout_counter > self.NETPERF_TIMEOUT:
                self.client.log(f"Timeout waiting on speedtest for {speedtest['input']['options']['ifc_wan']}")
                raise Timeout(status_path)
            timeout_counter += delay

        if status != 'complete':
            self.client.log(f"ERROR: status=%s expected 'complete' {status}")
            return None

        # now get the result
        results_path = self.client.get("/control/netperf/output/results_path")

        results = None
        while not results:
            results = self.client.get(results_path)
            time.sleep(2)
        self.client.log('Speedtest Complete.')
        return results

    def do_speedtest(self, sim):
        default_speedtest['input']['options']['ifc_wan'] = self.iface(sim)
        default_speedtest['input']['options']['send'] = False
        default_speedtest['input']['options']['recv'] = True
        tcp_down = self.run_speedtest(default_speedtest).get('tcp_down')
        default_speedtest['input']['options']['send'] = True
        default_speedtest['input']['options']['recv'] = False
        tcp_up = self.run_speedtest(default_speedtest).get('tcp_up')

        if not tcp_up:
            self.client.log('do_speedtest tcp_up results missing!')
            default_speedtest['input']['options']['send'] = True
            default_speedtest['input']['options']['recv'] = False
            results = self.run_speedtest(default_speedtest)
            tcp_up = results.get('tcp_up') or None

        if not tcp_down:
            self.client.log('do_speedtest tcp_down results missing!')
            default_speedtest['input']['options']['send'] = False
            default_speedtest['input']['options']['recv'] = True
            results = self.run_speedtest(default_speedtest)
            tcp_down = results.get('tcp_down') or None

        down = float(tcp_down.get('THROUGHPUT', 0.0)) if tcp_down else 0.0
        up = float(tcp_up.get('THROUGHPUT', 0.0)) if tcp_up else 0.0
        return down, up

    def test_sim(self, device):
        try:
            if self.modem_state(device, 'connected'):

                # Get diagnostics and log it
                diagnostics = self.client.get(f'{self.STATUS_DEVS_PATH}/{device}/diagnostics')
                self.sims[device]['diagnostics'] = diagnostics
                self.client.log(
                    f'Modem Diagnostics: {self.port_sim(device)} RSRP:{diagnostics.get("RSRP")}')

                # Do speedtest and log results
                self.sims[device]['download'], self.sims[device]['upload'] = self.do_speedtest(
                    self.sims[device])
                self.client.log(
                    f'Speedtest Results: {self.port_sim(device)} TCP Download: '
                    f'{self.sims[device]["download"]}Mbps TCP Upload: {self.sims[device]["upload"]}Mbps')

                # Verify minimum speeds
                if self.sims[device].get('download', 0.0) > self.MIN_DOWNLOAD_SPD and self.sims[device].get('upload', 0.0) > self.MIN_UPLOAD_SPD:
                    return True
                else:  # Did not meet minimums
                    self.client.log(f'{self.port_sim(device)} Failed to meet minimums! MIN_DOWNLOAD_SPD: {self.MIN_DOWNLOAD_SPD} MIN_UPLOAD_SPD: {self.MIN_UPLOAD_SPD}')
                    return False

        except Timeout:
            message = f'Timed out running speedtest on {self.port_sim(device)}'
            self.client.log(message)
            self.client.alert(message)
            self.sims[device]['download'] = self.sims[device]['upload'] = 0.0
            return False

    def create_message(self, uid, *args):
        message = ''
        for arg in args:
            if arg == 'download':
                message = "DL:{:.2f}Mbps".format(self.sims[uid]['download']) if not message else ' '.join(
                    [message, "DL:{:.2f}Mbps".format(self.sims[uid]['download'])])
            elif arg == 'upload':
                message = "UL:{:.2f}Mbps".format(self.sims[uid]['upload']) if not message else ' '.join(
                    [message, "UL:{:.2f}Mbps".format(self.sims[uid]['upload'])])
            elif arg in ['PRD', 'HOMECARRID', 'RFBAND']:  # Do not include labels for these fields
                message = "{}".format(self.sims[uid]['diagnostics'][arg]) if not message else ' '.join(
                    [message, "{}".format(self.sims[uid]['diagnostics'][arg])])
            else:  # Include field labels (e.g. "RSRP:-82")
                message = "{}:{}".format(arg, self.sims[uid]['diagnostics'][arg]) if not message else ' '.join(
                    [message, "{}:{}".format(arg, self.sims[uid]['diagnostics'][arg])])
        return message

    def lock_sim(self, sim):
        rules = [{
            "_id_": "00000000-1234-1234-1234-123456789000",
            "priority": 0,
            "trigger_name": f"{self.sims[sim]['info']['port']} {self.sims[sim]['info']['sim']}",
            "trigger_string": f"type|is|mdm%sim|is|{self.sims[sim]['info']['sim']}%port|is|{self.sims[sim]['info']['port']}"
        }]
        for i, uid in enumerate(self.sims):
            if uid != sim:
                rule = {
                    "_id_": f"0000000{i+1}-1234-1234-1234-123456789000",
                    "priority": -9 + i,
                    "trigger_name": f"{self.sims[sim]['info']['port']} {self.sims[sim]['info']['sim']}",
                    "trigger_string": f"type|is|mdm%sim|is|{self.sims[sim]['info']['sim']}%port|is|{self.sims[sim]['info']['port']}",
                    "disabled": True
                }
                rules.append(rule)
        self.client.put('config/wan/rules2', rules)
        time.sleep(2)

    def create_rules(self, sim_list):
        wan_rules = [{"_id_": "00000000-1234-1234-1234-1234567890ab", "priority": -10, "trigger_name": "Ethernet",
                      "trigger_string": "type|is|ethernet"}]
        for i in range(0, len(sim_list)):
            rule = {
                "_id_": f"0000000{i+1}-1234-1234-1234-123456789000",
                "priority": -9 + i,
                "trigger_name": f"{self.sims[sim_list[i]]['info']['port']} {self.sims[sim_list[i]]['info']['sim']}",
                "trigger_string": f"type|is|mdm%sim|is|{self.sims[sim_list[i]]['info']['sim']}%port|is|{self.sims[sim_list[i]]['info']['port']}"
            }
            if self.NUM_ACTIVE_SIMS and i >= self.NUM_ACTIVE_SIMS:
                rule['disabled'] = True
            wan_rules.append(rule)
        req = self.client.put('config/wan/rules2/', wan_rules)
        time.sleep(2)
        if self.client.get('config/wan/rules2/0/_id_') == '00000000-1234-1234-1234-1234567890ab':
            self.client.log(f'Updated WAN rules')
        else:
            self.client.log(f'WAN Rules not updated! : {req}')
        return

    def run(self):  # *** Main Application Starts Here ***
        self.client.log(f'Boot2 Starting... MIN_DOWNLOAD_SPD:{self.MIN_DOWNLOAD_SPD} MIN_UPLOAD_SPD:{self.MIN_UPLOAD_SPD} '
                 f'SCHEDULE:{self.SCHEDULE} NUM_ACTIVE_SIMS:{self.NUM_ACTIVE_SIMS} ONLY_RUN_ONCE:{self.ONLY_RUN_ONCE}')

        self.check_if_run_before()

        self.wait_for_ncm_sync()

        # Get info from router
        product_name = self.client.get("/status/product_info/product_name")
        system_id = self.client.get("/config/system/system_id")
        router_id = self.client.get('status/ecm/client_id')

        self.find_sims()  # Find active SIM slots

        # Send startup alert
        message = f'Boot2 Starting! {system_id} - {product_name} - Router ID: {router_id}'
        self.client.log(f'Sending alert to NCM: {message}')
        self.client.alert(message)

        # Pause for 3 seconds to allow NCM Alert to be sent before suspending NCM
        time.sleep(3)
        self.NCM_suspend()

        success = False  # Boot2 Success Status - Becomes True when a SIM meets minimum speeds

        # Test the connected SIM first
        primary_device = self.client.get('status/wan/primary_device')
        if 'mdm-' in primary_device:  # make sure its a modem
            if self.test_sim(primary_device):
                success = True

        # test remaining SIMs
        for sim in self.sims:
            if not self.sims[sim].get('download'):
                self.lock_sim(sim)
                if self.test_sim(sim):
                    success = True

        # Prioritizes SIMs based on download speed
        sorted_results = sorted(self.sims, key=lambda x: self.sims[x]['download'], reverse=True)

        # Create WAN rules
        self.create_rules(sorted_results)
        time.sleep(3)

        # Build text for custom1 field
        results_text = datetime.datetime.now().strftime('%m/%d/%y %H:%M:%S')  # Start with a timestamp
        if not success:
            results_text += f' FAILED TO MEET MINIMUMS! MIN_DOWNLOAD_SPD:{self.MIN_DOWNLOAD_SPD} MIN_UPLOAD_SPD:{self.MIN_UPLOAD_SPD}'
        for uid in sorted_results:  # Add the results of each SIM with the fields specified:
            results_text = ' | '.join(
                [results_text, self.create_message(uid, 'PRD', 'HOMECARRID', 'RFBAND', 'RSRP', 'download', 'upload')])

        # put messages to NCM custom fields
        self.wait_for_ncm_sync()
        if apikeys.get('X-ECM-API-ID') != 'YOUR':
            self.client.log(f'X-ECM-API-ID: {apikeys["X-ECM-API-ID"]} X-CP-API-ID: {apikeys["X-CP-API-ID"]}')
            req = requests.put(f'{self.API_URL}/routers/{router_id}/', headers=apikeys, json={'custom1': results_text[:255]})
            self.client.log(f'NCM PUT Custom1 Result: {req.status_code}')
        else:
            self.client.log('No NCM API Keys configured, skipping PUT to custom1')

        # Complete!  Send results.
        message = f"Boot2 Complete! {system_id} Results: {results_text}"
        self.client.log(message)
        self.client.alert(message)


if __name__ == '__main__':
    Boot2 = SIMSpeedTest()
    last_run = datetime.datetime.now()
    try:
        Boot2.run()
        # Run on schedule if it is not zero (0)
        if Boot2.SCHEDULE:
            while True:
                now = datetime.datetime.now()
                if last_run < now - datetime.timedelta(minutes=Boot2.SCHEDULE):
                    last_run = now
                    Boot2.run()
                time.sleep(1)

    except Exception as err:
        Boot2.client.log(f"Failed with exception={type(err)} err={str(err)}")
    finally:
        if Boot2.client.get('/status/ecm/state') != 'connected':
            Boot2.client.put('/control/ecm', {'start': 'true'})
