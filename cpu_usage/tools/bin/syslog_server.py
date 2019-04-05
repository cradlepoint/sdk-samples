import logging
import socket
import socketserver
import sys

# Tiny Syslog Server in Python.
#
# This is a tiny syslog server that is able to receive UDP based syslog
# entries on a specified port and save them to a file.
# That's it... it does nothing else...
# There are a few configuration parameters.

LOG_FILE = 'syslog.txt'
HOST = "0.0.0.0"
PORT = 514


logging.basicConfig(level=logging.DEBUG, format='%(message)s', datefmt='',
                    filename=LOG_FILE, filemode='w')

# set True to show GPS messages, else discard
SHOW_GSP = False


class SyslogUDPHandler(socketserver.BaseRequestHandler):

    def handle(self):
        """Handle one Syslog message"""
        data = self.request[0]

        if data[4] > 0x80:
            # handle CP's weird Syslog payload
            # [39]3C31353EE65636D3A2052656D6F746520636F6465206578656400
            # 192.168.1.1 :  b'<15>\xef\xbb\xbfecm: Remote code exec tri\x00'
            data = data[:4] + b" ? " + data[7:]
        # msg = ""
        # for by in data:
        #     msg += "%02X" % by
        # print("[%02d]%s" % (len(data), msg))
        data = bytes.decode(data.strip(), 'utf-8')

        skip_phrases = [
            # <15>WAN:1f3c6020: modem sync op: get_gps - status exception: 4
            # <15>WAN:1f3c6020: status exception: 4
            "status exception:",

            # <14>cp_stack_mgr: INFO  lte_sierra.c(6107) int1: lte_sierra_...
            "cp_stack_mgr",

            # <12>dnsmasq-dhcp[410]: no address range available for DHCPv6 an1
            "address range available for DHCPv6 request",

            # <15>smsserver: SMS STATE: sms_idle -> sms_start
            "sms_idle -> sms_start",

            # wlan: Starting wireless survey on radio 0
            # wlan: Wireless survey completed (radio 0)
            "ireless survey",

            # wwan2: WifiWanService.wwan, all requested
            #                     scans have been done: nets : []
            "WifiWanService.wwan",

            # wwan2: we're calling plug_profiles for radio
            "calling plug_profiles",

            # WAN:43988388.PassiveDns: ipv6_out bytes :
            #                     152 pkts : 2 iface out : 25853
            "PassiveDns",

            # dnsmasq-dhcp[473]: DHCPINFORM(primarylan1) 192.168.35.6 ...
            "dnsmasq-dhcp",

        ]

        if not SHOW_GSP:
            skip_phrases.extend([
                # WAN:1f0e98e7: Modem:gps: {'fix': {'latitude': {'second': ...
                "Modem:gps",

                # gps.ploop: is the GPS keep-alive - the "Poll Loop"
                "gps.ploop",

                # gps.tx.inet: <tx_tcp host=192.168.1.6 port=9999
                "gps.tx.inet",

                # <services.gps.efsm_dti.DefaultTimeIntervalEFSM object
                "gps.efsm",

                # gps.src.cs: No gps sample
                "gps.src",
            ])

        skip_this = False
        for phrase in skip_phrases:
            # seek each phrase
            if data.find(phrase) >= 0:
                skip_this = True
                break

        if not skip_this:
            # only log messages we care to see
            data = data.strip('\x00')
            print("%s : " % self.client_address[0], str(data))
            logging.info(str(data))

        return

if __name__ == "__main__":

    if len(sys.argv) > 1:
        # run a simple test
        udp_server = ("192.168.1.6", PORT)
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sent = udp_sock.sendto(b"<15>?Hello", udp_server)
        print("Send data to {}".format(udp_server))
        udp_sock.close()
        sys.exit(1)

    print("Starting SYSLOG server on({0}:{1})".format(HOST, PORT))
    logging.info("Starting SYSLOG server on({0}:{1})".format(HOST, PORT))
    try:
        server = socketserver.UDPServer((HOST, PORT), SyslogUDPHandler)
        server.serve_forever(poll_interval=0.5)
    except (IOError, SystemExit):
        raise
    except KeyboardInterrupt:
        print("Crtl+C Pressed. Shutting down.")
