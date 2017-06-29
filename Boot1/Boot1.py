#pylint: disable=invalid-name, missing-docstring, line-too-long, bad-continuation
"""
    Router SDK Boot1 Application.

    Copyright © 2016 Cradlepoint, Inc. <www.cradlepoint.com>.  All rights reserved.

    This file contains confidential information of Cradlepoint, Inc. and your
    use of this file is subject to the Cradlepoint Software License Agreement
    distributed with this file. Unauthorized reproduction or distribution of
    this file is subject to civil and criminal penalties.

    Desc:
        Determine "fastest" wireless wan connection by loading both SIMs,
        running speedtest. Disable the not-fastest SIM.

"""

import sys
import json
import socket
import time
#import Email

app_name = "Boot1"

#_STDERR=False
_STDERR = True

#tmplog = "/tmp/log.txt"
tmplog = None


def rawlog(fmt, *args):
    if _STDERR:
        msg = fmt % args
        print(msg, file=sys.stderr)

    if tmplog:
        with open(tmplog, "a") as outfile:
            msg = fmt % args
            print(time.ctime(), file=outfile)
            print(msg, file=outfile)

class Boot1Exception(Exception):
    pass

class Timeout(Boot1Exception):
    pass

class SocketLost(Boot1Exception):
    pass

class OneModem(Boot1Exception):
    pass

class ReadLine(object):
    """State machine to read CR/LF style line. Input controlled from outside. """

    # Keeping the read or recv or whatever outside the class allows me to handle
    # weird conditions around sockets, serial ports, etc.
    STATE_RECV_LINE = 1
    STATE_WAIT_LF = 2
    STATE_WAIT_SOL = 3

    CR = b'\x0d'
    LF = b'\x0a'

    def __init__(self, maxlen=256):
        self.maxlen = maxlen
        self.state = self.STATE_RECV_LINE
        self.s = bytes()
        self.len_s = 0

    def recv(self, c):
        return_s = None

        if self.state == self.STATE_RECV_LINE:
            if c == self.CR:
                # CR; could be a bare CR or a CRLF
                return_s = self.s
                # restart capture
                self.s = bytes()
                self.len_s = 0
                self.state = self.STATE_WAIT_LF
            elif c == self.LF:
                # bare LF (unusual)
                return_s = self.s

                # restart capture
                self.s = bytes()
                self.len_s = 0
            else:
                #rawlog("c={} s={}".format(c,self.s))
                self.s += c
                self.len_s += 1

                # protection from evil input; if we don't see a CRLF before
                # maxlen, throw away our current input and start over
                if self.len_s >= self.maxlen:
                    # throw away current input; start over
                    self.s = bytes()
                    self.len_s = 0

        elif self.state == self.STATE_WAIT_LF:
            if c == self.LF:
                # saw CRLF; capture was restarted in the previous state
                assert self.len_s == 0, self.len_s
            else:
                # raw CR! save what we've seen and start parsing again
                # (note: this won't handle weird cases like CRCRCR)
                self.s = c
                self.len_s = 1

            # start capturing line again
            self.state = self.STATE_RECV_LINE

        else:
            # WTF?
            assert 0, self.state

        return return_s

class CSClient(object):
    """Wrapper for the TCP interface to the router config store."""

    def __init__(self):
        self.getline = ReadLine()

    def _read_line(self, sock):
        while True:
            try:
                c = sock.recv(1)
            except socket.timeout:
                break

            if not c:
                raise SocketLost("connection lost sock={}".format(sock))

            buf = self.getline.recv(c)
            if buf is not None:
                s = buf.decode("utf-8")
                rawlog("read_line line=%s"%s)
                return s

#        logger.info("socket timeout {}".format(sock))
        return None

    def get(self, base, query='', tree=0):
        """Send a get request."""
        cmd = "get\n{}\n{}\n{}\n".format(base, query, tree)
        return self._dispatch(cmd)

    def put(self, base, value='', query='', tree=0):
        """Send a put request."""
        value = json.dumps(value).replace(' ', '')
        cmd = "put\n{}\n{}\n{}\n{}\n".format(base, query, tree, value)
        return self._dispatch(cmd)

    def append(self, base, value='', query=''):
        """Send an append request."""
        value = json.dumps(value).replace(' ', '')
        cmd = "post\n{}\n{}\n{}\n".format(base, query, value)
        return self._dispatch(cmd)

    def delete(self, base, query=''):
        """Send a delete request."""
        cmd = "delete\n{}\n{}\n".format(base, query)
        return self._dispatch(cmd)

    def alert(self, value=''):
        """Send a request to create an alert."""
        cmd = "alert\n{}\n{}\n".format(app_name, value)
        return self._dispatch(cmd)

    def log(self, value=''):
        """Send a request to create a log entry."""
        cmd = "log\n{}\n{}\n".format(app_name, value)
        return self._dispatch(cmd)

    def paranoid_sendall(self, cmd, sock):
        message_list = cmd.split("\n")
        for msg in message_list:
            rawlog("send >>>%s<<<",msg)
            sock.sendall(bytes(msg+"\n", 'ascii'))
            time.sleep(0.1)

    def safe_dispatch(self, cmd):
        """Send the command and return the response."""
        resl = ''
        rawlog("_dispatch %s", cmd)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            # davep 20160706 ; disable Nagle because we're talking localhost
            # and other side is using sock.readline()
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

            sock.connect(('localhost', 1337))
            sock.sendall(bytes(cmd, 'ascii'))
#            self.paranoid_sendall(cmd, sock)

            line = self._read_line(sock)
            resl = ""
            if line and line.strip() == 'status: ok':
                line = self._read_line(sock)
                if line and line.startswith("content-length"):
                    mlen = int(line.strip().split(' ')[1])
                    # eat \r\n\r\n
                    sock.recv(1)
                    sock.recv(1)
                    sock.recv(1)
                    sock.recv(1)
                    # read message, pray that sender has accurate content-length field
                    while mlen > 0:
                        c = sock.recv(1)
                        if not c:
                            raise SocketLost("connection lost sock={}".format(sock))
                        resl += c.decode('utf8')
                        mlen -= 1

        rawlog("_dispatch resl=\"%s\"", resl)
        return resl

    def _dispatch(self, cmd):
        errmsg = None
        resl = ""
        try:
            resl = self.safe_dispatch(cmd)
        except Boot1Exception as err:
            # ignore the command error, continue on to next command
            errmsg = "dispatch failed with exception={} err={}".format(type(err), str(err))

        if errmsg is not None:
            rawlog(errmsg)

        return resl

default_speedtest = {
    "input": {
        "options": {
            "limit": {
                "size":0,
                "time":15
            },
            "port":None,
            "host":"",
            "ifc_wan":None,
            "tcp":True,
            "udp":False,
            "send":True,
            "recv":True,
            "rr":False
        },
        "tests":None
    },
    "run":1
}

class SIMSpeedTest(object):
    STATUS_DEVS_PATH = '/status/wan/devices'
    CFG_RULES2_PATH = '/config/wan/rules2'
    CTRL_WAN_DEVS_PATH = '/control/wan/devices'
    MIN_UPLOAD_SPD = 1.0        # Mbps
    MIN_DOWNLOAD_SPD = 10.0
    CONNECTION_STATE_TIMEOUT = 7 * 60 # 7 Min
    NETPERF_TIMEOUT = 4 * 60 # 4 Min

    def __init__(self):
        self.client = CSClient()

    def log(self, fmt, *args):
        rawlog(fmt, *args)
        msg = fmt % args
        self.client.log(msg)

    def find_modems(self, verbose):
        dsdm = self.client.get('/config/wan/dual_sim_disable_mask')
        self.log("dsdm: %s" % dsdm)
        while True:
            devs = json.loads(self.client.get(self.STATUS_DEVS_PATH))
            modems_list = [x for x in devs if x.startswith("mdm-")]
            self.log('modems_list: %s', modems_list)
            num_modems = len(modems_list)
            if not num_modems:
                rawlog('No Modems found at all yet')
                time.sleep(10)
                continue

            if num_modems < 2:
                status = devs[modems_list[0]].get('status') or None
                ready = None if not status else status.get('ready')
                if -1 != ready.find('unconfigured'):
                    rawlog('Modems not yet finished configuring')
                    time.sleep(10)
                    continue

                if verbose:
                    self.log("Looks like we have been run before!")
                raise OneModem("Only one Modem found")
            else:
                break

        modems = {}
        for mdm in modems_list:
            err_txt = devs[mdm]['status']['error_text']
            if err_txt and -1 != err_txt.find('NOSIM'):
                continue
            self.log('mdm: %s', mdm)
            key = devs[mdm]['info'].get('sim')
            self.log('key: %s %s', key, type(key))
            modems[key] = mdm
        self.log('modems dict: %s', modems)
        return modems

    def find_sims(self):
        modems = self.find_modems(True)
        sim1 = modems.get('sim1') or None
        sim2 = modems.get('sim2') or None
        self.log('Sim1: %s Sim2: %s', sim1, sim2)
        return (sim1, sim2)

    def find_device(self, devs, devname):
        return [idx for (idx, dev) in enumerate(devs) if dev['trigger_string'].startswith(devname)]

    def enable_dev_mode(self, dev, mode, state):
        devices = json.loads(self.client.get(self.CFG_RULES2_PATH))
        mdms = self.find_device(devices, dev)
        if state != None:
            [self.client.put(self.CFG_RULES2_PATH + '/%d' % mdm, {mode:state}) for mdm in mdms]
        else:
            for mdm in mdms:
                key = '%s/%d/%s' % (self.CFG_RULES2_PATH,mdm,mode)
                if self.client.get(key) != None:
                    self.client.delete(key)

    def enable_mdm_mode(self, mode, state):
        self.enable_dev_mode('type|is|mdm', mode, state)

    def enable_eth_mode(self, mode, state):
        self.enable_dev_mode('type|is|ethernet', mode, state)

    def set_wan_dev_disabled(self, dev, state):
        s = self.client.put(self.CFG_RULES2_PATH + '/%d' % dev, {"disabled":state})
        self.log("set_wan_dev_disabled - put s=%s", s)

    def modem_state(self, sim, state):
        ''' Blocking call that will wait until a given state is shown as the modem's status '''
        timeout_counter = 0
        sleep_seconds = 0
        conn_path = '%s/%s/status/connection_state' % (self.STATUS_DEVS_PATH, sim)
        self.log("modem_state waiting sim=%s state=%s", sim, state)
        while True:
            sleep_seconds += 5
            conn_state = self.client.get(conn_path)
            # TODO add checking for mdm error states
            self.log('waiting for state=%s on sim=%s curr state=%s', state, sim, conn_state)
            if conn_state.replace('"', '') == state:
                break
            if timeout_counter > self.CONNECTION_STATE_TIMEOUT:
                self.log("timeout waiting on sim=%s", sim)
                raise Timeout(conn_path)
            time.sleep(min(sleep_seconds,45))
            timeout_counter += sleep_seconds
        self.log("sim=%s connected", sim)
        return True

    def connect_sim(self, sim, state):
        self.client.put('%s/%s/testmode' % (self.CTRL_WAN_DEVS_PATH, sim), {"ready":state})

    def reset_sim(self, sim, state):
        self.log("Reset SIM called")
        self.client.put('%s/%s' % (self.CTRL_WAN_DEVS_PATH, sim), {"reset":state})
        while True:
            devs = json.loads(self.client.get(self.STATUS_DEVS_PATH))
            modems_list = [x for x in devs if x.startswith("mdm-")]
            self.log('Modems_list: %s', modems_list)
            if len(modems_list):
                time.sleep(10)
                continue
            else:
                break
        self.log("Modem is offline")
        try:
            modems = self.find_modems(False)
        except OneModem:
            pass
        self.log("Modem is back online")

    def reset_spdtest_cnt(self):
        self.client.put('/state/system/netperf', {"run_count":0})

    def iface(self, sim):
        iface = self.client.get('%s/%s/info/iface' % (self.STATUS_DEVS_PATH, sim))
        return iface

    def run_speedtest(self, speedtest):
        # TODO verify the put was successful
        res = self.client.put("/control/netperf", speedtest)
        self.log("put netperf res=%s", res)

        timeout_counter = 0

        # wait for results
        delay = speedtest['input']['options']['limit']['time'] + 2
        status = None
        status_path = "/control/netperf/output/status"
        while True:
            self.log("waiting for netperf results...")
            status = self.client.get(status_path).replace('"', '')
            self.log("status=%s", status)
            if status == 'complete':
                break
            # add timeout
            if timeout_counter > self.NETPERF_TIMEOUT:
                self.log("timeout waiting on netperf")
                raise Timeout(status_path)
            time.sleep(delay)
            timeout_counter += delay

        if status != 'complete':
            self.log("error: status=%s expected 'complete'", status)
            return None

        # now get the result
        res = self.client.get("/control/netperf/output/results_path")
        self.log("results_path=%s", res)

        # TODO verify retrieved the string successfully
        # strip and remove the leading/trailing quotes
        results = self.client.get("%s" % res.strip()[1:-1]) or {}
        #client.log("results=%s (%s)" % (results, type(results)))
        return results

    def do_speedtest(self, sim):
        mdm_ifc = self.iface(sim).replace('"', '')
        self.log('Sim iface: %s', mdm_ifc)
        default_speedtest['input']['options']['ifc_wan'] = mdm_ifc

        # run speedtest w/send & recv and attempt to parse as JSON
        results = json.loads(self.run_speedtest(default_speedtest))

        tcp_up = results.get('tcp_up') or None
        tcp_down = results.get('tcp_down') or None

        if not tcp_up:
            self.log('do_speedtest tcp_up results missing!')
            default_speedtest['input']['options']['send'] = True
            default_speedtest['input']['options']['recv'] = False
            results = json.loads(self.run_speedtest(default_speedtest))
            tcp_up = results.get('tcp_up') or None
        if not tcp_down:
            self.log('do_speedtest tcp_down results missing!')
            default_speedtest['input']['options']['send'] = False
            default_speedtest['input']['options']['recv'] = True
            results = json.loads(self.run_speedtest(default_speedtest))
            tcp_down = results.get('tcp_down') or None

        up = float(tcp_up.get('THROUGHPUT') or 0) if tcp_up else 0
        down = float(tcp_down.get('THROUGHPUT') or 0) if tcp_down else 0
        self.log('do_speedtest returning: %s down, %s up', down, up)

        self.reset_spdtest_cnt()

        return (up, down)

    def send_email(self, message):
        rawlog("send_email:%s",message)
        return
        # Example of how to send email
        server = "mail.<mailprovider>.com"
        port = 587
        username = "<username>.com"
        password = '<password>'
        from_addr = '%s@<something>.com' % username
        to_addr = '<someone>@<somewhere>.com'

        email = Email.Email(server, port, username, password)
        email.message('Information Message', from_addr, to_addr, message)
        email.send()


    def meets_minimums(self, up, down):
        return up >= self.MIN_UPLOAD_SPD and down >= self.MIN_DOWNLOAD_SPD

    def percent_diff(self, a, b):
        if a == 0 or b == 0: return 100.0
        return (abs(a-b)/min(a,b))*100.0

    def gt_percent_diff(self, a, b, percent):
        return self.percent_diff(a, b) >= percent

    def ten_prcnt_diff(self, a,b):
        return self.gt_percent_diff(a, b, 10.0)

    def select_sim(self, sim1, s1_up, s1_down, sim2, s2_up, s2_down):
        rawlog('select_sim')
        s1 = {'slot':sim1, 'slot_name':'sim1', 'slot_num':1, 'up':s1_up, 'down':s1_down}
        s2 = {'slot':sim2, 'slot_name':'sim2', 'slot_num':2, 'up':s2_up, 'down':s2_down}

        if self.meets_minimums(s1_up, s1_down):
            return (s1,s2)

        if self.meets_minimums(s2_up, s2_down):
            return (s2,s1)

        # Neither meet minimums, but > 10% diff on each, defer to DL speed
        if self.ten_prcnt_diff(s1_up, s2_up) and self.ten_prcnt_diff(s1_down, s2_down):
            return (s1,s2) if s1_down > s2_down else (s2,s1)

        # Neither meet minimums, but > 10% diff on upload, defer to UL speed
        if self.ten_prcnt_diff(s1_up, s2_up) and not self.ten_prcnt_diff(s1_down, s2_down):
            return (s1,s2) if s1_up > s2_up else (s2,s1)

        # Neither meet minimums, but > 10% diff on download, defer to DL speed
        if not self.ten_prcnt_diff(s1_up, s2_up) and self.ten_prcnt_diff(s1_down, s2_down):
            return (s1,s2) if s1_down > s2_down else (s2,s1)

        # Neither meet minimums and < 10% diff on both, defer to biggest delta
        if not self.ten_prcnt_diff(s1_up, s2_up) and not self.ten_prcnt_diff(s1_down, s2_down):
            d_up = self.percent_diff(s1_up, s2_up)
            d_down = self.percent_diff(s1_down, s2_down)

            if d_up > d_down:
                return (s1,s2) if s1_up > s2_up else (s2,s1)
            else:
                return (s1,s2) if s1_down > s2_down else (s2,s1)

    def log_results(self, product_name, system_id, selected_sim, rejected_sim):
        rawlog("log_results")
        sdiag= json.loads(self.client.get('%s/%s/diagnostics' % (self.STATUS_DEVS_PATH, selected_sim['slot'])))
        rdiag= json.loads(self.client.get('%s/%s/diagnostics' % (self.STATUS_DEVS_PATH, rejected_sim['slot'])))

        msg1 = 'The results of the SIM test on product={} id={} are as follows:'.format(product_name, system_id)
        msg2 = 'Selected Sim: slot={} carrier={} ICCID={} down={:.4f} up={:.4f}'.format( \
                selected_sim['slot_name'], sdiag['HOMECARRID'], sdiag['ICCID'], selected_sim['down'], selected_sim['up'])
        msg3 = 'Rejected Sim: slot={} carrier={} ICCID={} down={:.4f} up={:.4f}'.format( \
                rejected_sim['slot_name'], rdiag['HOMECARRID'], rdiag['ICCID'], rejected_sim['down'], rejected_sim['up'])

        msg = msg1 + ' ' + msg2 + ', ' + msg3

        self.log(msg1); self.log(msg2); self.log(msg3)
        self.client.alert(msg)
        self.send_email(msg)

    def lock_sim(self,sim):
        port = self.client.get('/%s/%s/info/port' % (self.STATUS_DEVS_PATH, sim['slot'])).replace('"', '')
        sim_disable_mask = '%s,%s' % (port, sim['slot_num'])
        self.log("Writing dual_sim_disable_mask to: %s", sim_disable_mask)
        self.client.put('/config/wan', {'dual_sim_disable_mask':sim_disable_mask})

    def NTP_time_updated(self):
        return time.time() > 1467416418

    def ECM_resume(self):
        self.log('Resuming ECM')
        self.client.put('/control/ecm', {'restart': 'true'})
        timeout_count = 500
        while not 'connected' == self.client.get('/status/ecm/state').replace('"', ''):
            timeout_count -= 1
            if not timeout_count:
                raise Timeout('ECM not connecting')
            time.sleep(2)

    def ECM_suspend(self):
        self.log('Suspending ECM')
        timeout_count = 500
        while not 'ready' == self.client.get('/status/ecm/sync').replace('"', ''):
            timeout_count -= 1
            if not timeout_count:
                raise Timeout('ECM sync ready')
            time.sleep(2)
        self.client.put('/control/ecm', {'stop':'stop'})
        timeout_count = 500
        while not 'stopped' == self.client.get('/status/ecm/state').replace('"', ''):
            timeout_count -= 1
            if not timeout_count:
                raise Timeout('ECM not stopping')
            time.sleep(2)

    def ECM_config_ver(self):
        return self.client.get('/config/ecm/config_version').replace('"', '')

    def ECM_updated(self):
        return self.ECM_config_ver > 0

    def ECM_connected(self):
        ecm_state = self.client.get("/status/ecm/state")
        #TODO Remove unmanaged test below after dev done.
        return '"connected"' == ecm_state or '"unmanaged"' == ecm_state

    def min_fw_version_check(self, major, minor, patch=0):
        fw_major = int(self.client.get("/status/fw_info/major_version").replace('"', ''))
        fw_minor = int(self.client.get("/status/fw_info/minor_version").replace('"', ''))
        fw_patch = int(self.client.get("/status/fw_info/patch_version").replace('"', ''))
        self.log("Current FW Version - major: %s, minor: %s, patch: %s",
            fw_major, fw_minor, fw_patch)
        return fw_major >= major and fw_minor >= minor and fw_patch >= patch

    def wait_to_start(self):
        while not self.NTP_time_updated():
            self.log("waiting for NTP time set now=%s", time.ctime())
            time.sleep(5)

        while not self.ECM_connected():
            self.log("waiting for ECM update now=%s", time.ctime())
            time.sleep(5)

    def run(self):
        if not self.min_fw_version_check(6, 2):
            self.log("Boot1 FW version check failed!")
            return
        else:
            self.log("Boot1 FW version check passed")

        if 'running' == self.client.get('/status/sdk/Boot1').replace('"', ''):
            self.log("Boot1 SIM test already running!")
            return
        else:
            self.client.put('/status/sdk', {'Boot1':'running'})

        self.log("Boot1 SIM test starting")
        self.wait_to_start()

        product_name = self.client.get("/status/product_info/product_name")
        system_id = self.client.get("/config/system/system_id")

        sim1, sim2 = self.find_sims()

        self.client.log('Sending alert to ECM.')
        message = "Hello from BOOT1 SIM Speedtest product={} id={}".format(product_name, system_id)
        self.client.alert('Transmitting message: %s' % message)
        self.send_email(message)

        self.ECM_suspend()

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
                self.log("timeout on sim=%s", sim1)
                self.client.alert("netperf failed on sim1=%s" % sim1)
                # continue, try sim2

        sim2_upload_speed = sim2_download_speed = 0.0
        if sim2 and not (sim1_upload_speed >= self.MIN_UPLOAD_SPD and sim1_download_speed >= self.MIN_DOWNLOAD_SPD):
            self.connect_sim(sim2, True)
            self.connect_sim(sim1, False)
            try:
                if self.modem_state(sim2, 'connected'):
                    sim2_upload_speed, sim2_download_speed = self.do_speedtest(sim2)
            except Timeout:
                self.log("timeout on sim=%s", sim2)
                self.client.alert("netperf failed on sim2=%s" % sim2)
            self.connect_sim(sim1, True)
        elif not sim2:
            rawlog("Error with Sim2:%s", sim2)
            self.log("Error with Sim2:%s", sim2)

        self.enable_mdm_mode('loadbalance', False)
        self.enable_eth_mode('loadbalance', False)

        rawlog('\n\nSpeeds - Sim1: %f down, %f up    Sim2: %f down, %f up' % \
                                                        (sim1_download_speed, sim1_upload_speed, \
                                                         sim2_download_speed, sim2_upload_speed))

        # Check for abject failure
        if sim1_download_speed == 0.0 and sim1_upload_speed == 0.0 and \
           sim2_download_speed == 0.0 and sim2_upload_speed == 0.0:
            self.client.alert('Was not able to get any modem speed results.  Aborting!')
            self.log('Was not able to get any modem speed results.  Aborting!')
            self.client.put('/status/sdk', {'Boot1':'failed'})
            self.ECM_resume()
            return

        # Run the selection algorithm
        selected_sim, rejected_sim = self.select_sim(sim1, sim1_upload_speed, sim1_download_speed, sim2, sim2_upload_speed, sim2_download_speed)

        self.log_results(product_name, system_id, selected_sim, rejected_sim)

        self.enable_mdm_mode('loadbalance', None)
        self.enable_eth_mode('loadbalance', None)

        self.lock_sim(selected_sim)
        self.reset_sim(selected_sim['slot'], True)

        self.ECM_resume()

        self.client.put('/status/sdk', {'Boot1':'completed'})
        self.log("Boot1 SIM test completed")

if __name__ == '__main__':
    errmsg = None
    try:
        boot1 = SIMSpeedTest()
        boot1.run()
    except OneModem:
        # non-local goto :-(
        boot1.ECM_resume()
    except Exception as err:
        boot1.ECM_resume()
        errmsg = "failed with exception={} err={}".format(type(err), str(err))

    # not doing this inside the exception above in case we can't write to the
    # filesystem; don't want to throw inside a except
    if errmsg is not None:
        rawlog("failed with exception={}".format(errmsg))
        try:
            with open("/tmp/boot1.fatal.log","w") as outfile:
                outfile.write(errmsg)
        except IOError as err:
            # unable to open the log file
            if _STDERR:
                print("failed with exception={}".format(err), file=sys.stderr)
            pass

    while True:
        # as of this writing (20160707) we cannot exit the SDK app without
        # being restarted by the firmware SDK service. So we suspend.
        time.sleep(2147483647)
