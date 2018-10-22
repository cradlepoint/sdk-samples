# pylint: disable=invalid-name, missing-docstring, line-too-long, bad-continuation
"""
    Router SDK Boot1 Application.

    Copyright © 2017 Cradlepoint, Inc. <www.cradlepoint.com>.  All rights reserved.

    This file contains confidential information of Cradlepoint, Inc. and your
    use of this file is subject to the Cradlepoint Software License Agreement
    distributed with this file. Unauthorized reproduction or distribution of
    this file is subject to civil and criminal penalties.

    Desc:
        Determine "fastest" wireless wan connection by loading both SIMs,
        running speedtest. Disable the not-fastest SIM.
"""

import cs
import time
import settings
from app_logging import AppLogger

# Create an AppLogger for logging to NCOS syslog.
log = AppLogger()


class Boot1Exception(Exception):
    pass


class Timeout(Boot1Exception):
    pass


class SocketLost(Boot1Exception):
    pass


class OneModem(Boot1Exception):
    pass


default_speedtest = {
    "input": {
        "options": {
            "limit": {
                "size": 0,
                "time": 15
            },
            "port": None,
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


class SIMSpeedTest(object):
    STATUS_DEVS_PATH = '/status/wan/devices'
    CFG_RULES2_PATH = '/config/wan/rules2'
    CTRL_WAN_DEVS_PATH = '/control/wan/devices'
    MIN_UPLOAD_SPD = 1.0  # Mbps
    MIN_DOWNLOAD_SPD = 10.0
    CONNECTION_STATE_TIMEOUT = 7 * 60  # 7 Min
    NETPERF_TIMEOUT = 4 * 60  # 4 Min

    def __init__(self):
        self.client = cs.CSClient()

    def find_modems(self, verbose):
        dsdm = self.client.get('/config/wan/dual_sim_disable_mask').get('data', '')
        log.info("dsdm: %s" % dsdm)
        while True:
            devs = self.client.get(self.STATUS_DEVS_PATH).get('data', {})
            modems_list = [x for x in devs if x.startswith("mdm-")]
            log.info('modems_list: %s', modems_list)
            num_modems = len(modems_list)
            if not num_modems:
                log.info('No Modems found at all yet')
                time.sleep(10)
                continue

            if num_modems < 2:
                status = devs[modems_list[0]].get('status') or None
                ready = None if not status else status.get('ready')
                if -1 != ready.find('unconfigured'):
                    log.info('Modems not yet finished configuring')
                    time.sleep(10)
                    continue

                if verbose:
                    log.info("Looks like we have been run before!")
                raise OneModem("Only one Modem found")
            else:
                break

        modems = {}
        for mdm in modems_list:
            err_txt = devs[mdm]['status']['error_text']
            if err_txt and -1 != err_txt.find('NOSIM'):
                continue
            log.info('mdm: %s', mdm)
            key = devs[mdm]['info'].get('sim')
            log.info('key: {}'.format(key))
            modems[key] = mdm
        log.info('modems dict: %s', modems)
        return modems

    def find_sims(self):
        modems = self.find_modems(True)
        sim1 = modems.get('sim1') or None
        sim2 = modems.get('sim2') or None
        log.info('sim1: %s sim2: %s', sim1, sim2)
        return sim1, sim2

    def find_device(self, devs, devname):
        return [idx for (idx, dev) in enumerate(devs) if dev['trigger_string'].startswith(devname)]

    def enable_dev_mode(self, dev, mode, state):
        devices = self.client.get(self.CFG_RULES2_PATH).get('data', [])
        mdms = self.find_device(devices, dev)
        if state is not None:
            for mdm in mdms:
                reply = self.client.put(self.CFG_RULES2_PATH + '/%d' % mdm, {mode: state})
        else:
            for mdm in mdms:
                key = '%s/%d/%s' % (self.CFG_RULES2_PATH, mdm, mode)
                if self.client.get(key).get('data', '') is not None:
                    log.info('delete - {}'.format(key))
                    self.client.delete(key)

    def enable_mdm_mode(self, mode, state):
        self.enable_dev_mode('type|is|mdm', mode, state)

    def enable_eth_mode(self, mode, state):
        self.enable_dev_mode('type|is|ethernet', mode, state)

    def set_wan_dev_disabled(self, dev, state):
        s = self.client.put(self.CFG_RULES2_PATH + '/%d' % dev, {"disabled": state})
        log.info("set_wan_dev_disabled - put s=%s", s)

    def modem_state(self, sim, state):
        # Blocking call that will wait until a given state is shown as the modem's status
        timeout_counter = 0
        sleep_seconds = 0
        conn_path = '%s/%s/status/connection_state' % (self.STATUS_DEVS_PATH, sim)
        log.info("modem_state waiting sim=%s state=%s", sim, state)
        while True:
            sleep_seconds += 5
            conn_state = self.client.get(conn_path).get('data', '')
            # TODO add checking for mdm error states
            log.info('waiting for state=%s on sim=%s curr state=%s', state, sim, conn_state)
            if conn_state == state:
                break
            if timeout_counter > self.CONNECTION_STATE_TIMEOUT:
                log.info("timeout waiting on sim=%s", sim)
                raise Timeout(conn_path)
            time.sleep(min(sleep_seconds, 45))
            timeout_counter += sleep_seconds
        log.info("sim=%s connected", sim)
        return True

    def connect_sim(self, sim, state):
        self.client.put('%s/%s/testmode' % (self.CTRL_WAN_DEVS_PATH, sim), {"ready": state})

    def reset_sim(self, sim, state):
        log.info("Reset SIM called")
        self.client.put('%s/%s' % (self.CTRL_WAN_DEVS_PATH, sim), {"reset": state})
        while True:
            devs = self.client.get(self.STATUS_DEVS_PATH).get('data', {})
            modems_list = [x for x in devs if x.startswith("mdm-")]
            log.info('Modems_list: %s', modems_list)
            if len(modems_list):
                time.sleep(10)
                continue
            else:
                break
        log.info("Modem is offline")
        try:
            modems = self.find_modems(False)
        except OneModem:
            pass
        log.info("Modem is back online")

    def reset_spdtest_cnt(self):
        self.client.put('/state/system/netperf', {"run_count": 0})

    def iface(self, sim):
        iface = self.client.get('%s/%s/info/iface' % (self.STATUS_DEVS_PATH, sim)).get('data', '')
        return iface

    def run_speedtest(self, speedtest):
        # TODO verify the put was successful
        res = self.client.put("/control/netperf", speedtest)
        log.info("put netperf res=%s", res)

        timeout_counter = 0

        # wait for results
        delay = speedtest['input']['options']['limit']['time'] + 2
        status = None
        status_path = "/control/netperf/output/status"
        while True:
            log.info("waiting for netperf results...")
            status = self.client.get(status_path).get('data', '')
            log.info("status=%s", status)
            if status == 'complete':
                break
            # add timeout
            if timeout_counter > self.NETPERF_TIMEOUT:
                log.info("timeout waiting on netperf")
                raise Timeout(status_path)
            time.sleep(delay)
            timeout_counter += delay

        if status != 'complete':
            log.error("ERROR: status=%s expected 'complete'", status)
            return None

        # now get the result
        results_path = self.client.get("/control/netperf/output/results_path").get('data', '')
        log.info("results_path=%s", results_path)

        # TODO verify retrieved the string successfully
        # strip and remove the leading/trailing quotes
        results = self.client.get(results_path).get('data', {})
        # log.info("results=%s (%s)" % (results, type(results)))
        return results

    def do_speedtest(self, sim):
        mdm_ifc = self.iface(sim)
        log.info('Sim iface: %s', mdm_ifc)
        default_speedtest['input']['options']['ifc_wan'] = mdm_ifc

        # run speedtest w/send & recv and attempt to parse as JSON
        results = self.run_speedtest(default_speedtest)

        tcp_up = results.get('tcp_up') or None
        tcp_down = results.get('tcp_down') or None

        if not tcp_up:
            log.info('do_speedtest tcp_up results missing!')
            default_speedtest['input']['options']['send'] = True
            default_speedtest['input']['options']['recv'] = False
            results = self.run_speedtest(default_speedtest)
            tcp_up = results.get('tcp_up') or None

        if not tcp_down:
            log.info('do_speedtest tcp_down results missing!')
            default_speedtest['input']['options']['send'] = False
            default_speedtest['input']['options']['recv'] = True
            results = self.run_speedtest(default_speedtest)
            tcp_down = results.get('tcp_down') or None

        up = float(tcp_up.get('THROUGHPUT') or 0) if tcp_up else 0
        down = float(tcp_down.get('THROUGHPUT') or 0) if tcp_down else 0
        log.info('do_speedtest returning: %s down, %s up', down, up)

        self.reset_spdtest_cnt()

        return up, down

    def meets_minimums(self, up, down):
        return up >= self.MIN_UPLOAD_SPD and down >= self.MIN_DOWNLOAD_SPD

    def percent_diff(self, a, b):
        if a == 0 or b == 0:
            return 100.0
        return (abs(a - b) / min(a, b)) * 100.0

    def gt_percent_diff(self, a, b, percent):
        return self.percent_diff(a, b) >= percent

    def ten_prcnt_diff(self, a, b):
        return self.gt_percent_diff(a, b, 10.0)

    def select_sim(self, sim1, s1_up, s1_down, sim2, s2_up, s2_down):
        log.info('select_sim')
        s1 = {'slot': sim1, 'slot_name': 'sim1', 'slot_num': 1, 'up': s1_up, 'down': s1_down}
        s2 = {'slot': sim2, 'slot_name': 'sim2', 'slot_num': 2, 'up': s2_up, 'down': s2_down}

        log.info('s1: {}'.format(s1))
        log.info('s2: {}'.format(s2))

        if self.meets_minimums(s1_up, s1_down):
            return s1, s2

        if self.meets_minimums(s2_up, s2_down):
            return s2, s1

        # Neither meet minimums, but > 10% diff on each, defer to DL speed
        if self.ten_prcnt_diff(s1_up, s2_up) and self.ten_prcnt_diff(s1_down, s2_down):
            return (s1, s2) if s1_down > s2_down else (s2, s1)

        # Neither meet minimums, but > 10% diff on upload, defer to UL speed
        if self.ten_prcnt_diff(s1_up, s2_up) and not self.ten_prcnt_diff(s1_down, s2_down):
            return (s1, s2) if s1_up > s2_up else (s2, s1)

        # Neither meet minimums, but > 10% diff on download, defer to DL speed
        if not self.ten_prcnt_diff(s1_up, s2_up) and self.ten_prcnt_diff(s1_down, s2_down):
            return (s1, s2) if s1_down > s2_down else (s2, s1)

        # Neither meet minimums and < 10% diff on both, defer to biggest delta
        if not self.ten_prcnt_diff(s1_up, s2_up) and not self.ten_prcnt_diff(s1_down, s2_down):
            d_up = self.percent_diff(s1_up, s2_up)
            d_down = self.percent_diff(s1_down, s2_down)

            if d_up > d_down:
                return (s1, s2) if s1_up > s2_up else (s2, s1)
            else:
                return (s1, s2) if s1_down > s2_down else (s2, s1)

        log.error('ERROR: select_sim did not return any data!')

    def log_results(self, product_name, system_id, selected_sim, rejected_sim):
        log.info("log_results")
        log.info('selected_sim: {}'.format(selected_sim))
        log.info('rejected_sim: {}'.format(rejected_sim))
        try:
            log.info('{} - {}'.format(self.STATUS_DEVS_PATH, self.client.get(self.STATUS_DEVS_PATH)))
            log.info('sdiag get path: {}'.format('{}/{}/diagnostics'.format(self.STATUS_DEVS_PATH, selected_sim.get('slot'))))
            log.info('rdiag get path: {}'.format('{}/{}/diagnostics'.format(self.STATUS_DEVS_PATH, rejected_sim.get('slot'))))

            sdiag = self.client.get('{}/{}/diagnostics'.format(self.STATUS_DEVS_PATH, selected_sim.get('slot'))).get('data', {})
            rdiag = self.client.get('{}/{}/diagnostics'.format(self.STATUS_DEVS_PATH, rejected_sim.get('slot'))).get('data', {})

            log.info('sdiag: {}'.format(sdiag))
            log.info('rdiag: {}'.format(rdiag))

            msg1 = 'The results of the SIM test on product={} id={} are as follows:'.format(product_name, system_id)
            log.info(msg1)

            msg2 = 'Selected Sim: slot={} carrier={} ICCID={} down={:.4f} up={:.4f}'.format(selected_sim.get('slot_name'),
                                                                                            sdiag.get('HOMECARRID'),
                                                                                            sdiag.get('ICCID'),
                                                                                            selected_sim.get('down'),
                                                                                            selected_sim.get('up'))
            log.info(msg2)

            msg3 = 'Rejected Sim: slot={} carrier={} ICCID={} down={:.4f} up={:.4f}'.format(rejected_sim.get('slot_name'),
                                                                                            rdiag.get('HOMECARRID'),
                                                                                            rdiag.get('ICCID'),
                                                                                            rejected_sim.get('down'),
                                                                                            rejected_sim.get('up'))
            log.info(msg3)

            self.client.alert(settings.APP_NAME, '{}, {}, {}'.format(msg1, msg2, msg3))

        except Exception as e:
            log.error('Exception in log_results. ex: {}'.format(e))

    def lock_sim(self, sim):
        port = self.client.get('/%s/%s/info/port' % (self.STATUS_DEVS_PATH, sim['slot'])).get('data', '')
        sim_disable_mask = '%s,%s' % (port, sim['slot_num'])
        log.info("Writing dual_sim_disable_mask to: %s", sim_disable_mask)
        self.client.put('/config/wan', {'dual_sim_disable_mask': sim_disable_mask})

    def NTP_time_updated(self):
        return time.time() > 1467416418

    def ECM_resume(self):
        log.info('Resuming ECM')
        self.client.put('/control/ecm', {'restart': 'true'})
        timeout_count = 500
        while not 'connected' == self.client.get('/status/ecm/state').get('data', ''):
            timeout_count -= 1
            if not timeout_count:
                raise Timeout('ECM not connecting')
            time.sleep(2)

    def ECM_suspend(self):
        log.info('Suspending ECM')
        timeout_count = 500

        while not 'ready' == self.client.get('/status/ecm/sync').get('data', ''):
            timeout_count -= 1
            if not timeout_count:
                raise Timeout('ECM sync ready')
            time.sleep(2)

        self.client.put('/control/ecm', {'stop': 'stop'})
        timeout_count = 500

        while not 'stopped' == self.client.get('/status/ecm/state').get('data', ''):
            timeout_count -= 1
            if not timeout_count:
                raise Timeout('ECM not stopping')
            time.sleep(2)

    def ECM_config_ver(self):
        return self.client.get('/config/ecm/config_version').get('data', '')

    def ECM_updated(self):
        return self.ECM_config_ver > 0

    def ECM_connected(self):
        ecm_state = self.client.get("/status/ecm/state").get('data', '')
        # TODO Remove unmanaged test below after dev done.
        return "connected" == ecm_state or "unmanaged" == ecm_state

    def min_fw_version_check(self, major, minor, patch=0):
        fw_major = int(self.client.get("/status/fw_info/major_version").get('data', ''))
        fw_minor = int(self.client.get("/status/fw_info/minor_version").get('data', ''))
        fw_patch = int(self.client.get("/status/fw_info/patch_version").get('data', ''))
        log.info("Current FW Version - major: %s, minor: %s, patch: %s",
                 fw_major, fw_minor, fw_patch)
        return (fw_major, fw_minor, fw_patch) >= (major, minor, patch)

    def wait_to_start(self):
        while not self.NTP_time_updated():
            log.info("waiting for NTP time set now=%s", time.ctime())
            time.sleep(5)

        while not self.ECM_connected():
            log.info("waiting for ECM update now=%s", time.ctime())
            time.sleep(5)

    def run(self):
        if not self.min_fw_version_check(6, 2):
            log.info("{} FW version check failed!".format(settings.APP_NAME))
            return
        else:
            log.info("{} FW version check passed".format(settings.APP_NAME))

        if 'running' == self.client.get('/status/sdk/{}'.format(settings.APP_NAME)).get('data', ''):
            log.info("{} SIM test already running!".format(settings.APP_NAME))
            return
        else:
            self.client.put('/status/sdk', {settings.APP_NAME: 'running'})

        log.info("{} SIM test starting".format(settings.APP_NAME))
        self.wait_to_start()

        product_name = self.client.get("/status/product_info/product_name").get('data', '')
        system_id = self.client.get("/config/system/system_id").get('data', '')

        sim1, sim2 = self.find_sims()

        message = "Hello from BOOT1 SIM Speedtest product={} id={}".format(product_name, system_id)
        log.info('Sending alert to ECM: {}'.format(message))
        self.client.alert(settings.APP_NAME, 'Transmitting message: {}'.format(message))

        self.ECM_suspend()

        if self.min_fw_version_check(6, 4):
            self.enable_eth_mode('connectionset', 1)
            self.enable_mdm_mode('connectionset', 1)
        else:
            self.enable_eth_mode('loadbalance', True)
            self.enable_mdm_mode('loadbalance', True)

        self.connect_sim(sim1, True)
        self.connect_sim(sim2, False)

        sim1_upload_speed = sim1_download_speed = 0.0
        if sim1:
            try:
                if self.modem_state(sim1, 'connected'):
                    sim1_upload_speed, sim1_download_speed = self.do_speedtest(sim1)
            except Timeout:
                log.warning("Timeout on sim=%s", sim1)
                self.client.alert(settings.APP_NAME, "netperf failed due to Timeout on sim1={}".format(sim1))
                # continue, try sim2

        sim2_upload_speed = sim2_download_speed = 0.0
        if sim2 and not (sim1_upload_speed >= self.MIN_UPLOAD_SPD and sim1_download_speed >= self.MIN_DOWNLOAD_SPD):
            self.connect_sim(sim2, True)
            self.connect_sim(sim1, False)
            try:
                if self.modem_state(sim2, 'connected'):
                    sim2_upload_speed, sim2_download_speed = self.do_speedtest(sim2)
            except Timeout:
                log.warning("Timeout on sim=%s", sim2)
                self.client.alert(settings.APP_NAME, "netperf failed due to Timeout on sim2={}".format(sim2))
            self.connect_sim(sim1, True)

        elif not sim2:
            log.error("Error with Sim2:%s", sim2)

        if self.min_fw_version_check(6, 4):
            self.enable_eth_mode('connectionset', 0)
            self.enable_mdm_mode('connectionset', 0)
        else:
            self.enable_mdm_mode('loadbalance', False)
            self.enable_eth_mode('loadbalance', False)

        log.info('Speeds - Sim1: %f down, %f up    Sim2: %f down, %f up' % \
                 (sim1_download_speed, sim1_upload_speed, \
                  sim2_download_speed, sim2_upload_speed))

        # Check for abject failure
        if sim1_download_speed == 0.0 and sim1_upload_speed == 0.0 and \
           sim2_download_speed == 0.0 and sim2_upload_speed == 0.0:
            fail_msg = 'Was not able to get any modem speed results.  Aborting!'
            self.client.alert(settings.APP_NAME, fail_msg)
            log.warning(fail_msg)
            self.client.put('/status/sdk', {settings.APP_NAME: 'failed'})
            self.ECM_resume()
            return

        # Run the selection algorithm
        selected_sim, rejected_sim = self.select_sim(sim1, sim1_upload_speed, sim1_download_speed, sim2,
                                                     sim2_upload_speed, sim2_download_speed)

        self.log_results(product_name, system_id, selected_sim, rejected_sim)

        if self.min_fw_version_check(6, 4):
            self.enable_mdm_mode('connectionset', None)
            self.enable_eth_mode('connectionset', None)
        else:
            self.enable_mdm_mode('loadbalance', None)
            self.enable_eth_mode('loadbalance', None)

        self.lock_sim(selected_sim)
        self.reset_sim(selected_sim['slot'], True)

        self.ECM_resume()

        self.client.put('/status/sdk', {settings.APP_NAME: 'completed'})
        log.info("{} SIM test completed".format(settings.APP_NAME))


if __name__ == '__main__':
    try:
        boot1 = SIMSpeedTest()
        boot1.run()
    except Exception as err:
        log.error("Failed with exception={} err={}".format(type(err), str(err)))
    finally:
        if cs.CSClient().get('/status/ecm/state').get('data', '') != 'connected':
            boot1.ECM_resume()
        log.info('{} is done'.format(settings.APP_NAME))

    while True:
        # as of this writing (20160707) we cannot exit the SDK app without
        # being restarted by the firmware SDK service. So we suspend.
        time.sleep(2147483647)
