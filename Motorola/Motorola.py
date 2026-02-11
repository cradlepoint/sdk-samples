"""Motorola - Broadcast Beacons with WAN and VPN State.

At the configured interval a UDP packet with JSON body containing
status of WAN interfaces and VPNs is sent to the broadcast IP Address
of the configured LANs.
A Web UI runs on port 8000 for configuration.
Default Configuration:
    interval = 5
    udp_port = 21010
    networks = first LAN enabled
"""

import cp
from threading import Thread
import tornado.web
import json
import os
import ipaddress
import socket
import time
from datetime import datetime

APP_DATA_KEY = 'Motorola'
DEFAULT_INTERVAL = 5
DEFAULT_UDP_PORT = 21010


def get_default_networks():
    """Build default networks from current LAN config. Enable first LAN."""
    try:
        cp_lans = cp.get('config/lan') or []
        networks = []
        for i, lan in enumerate(cp_lans):
            networks.append({
                "_id_": lan["_id_"],
                "name": lan["name"],
                "enabled": (i == 0)
            })
        return networks if networks else []
    except Exception as e:
        cp.get_logger().exception("Error getting default networks: %s", e)
        return []


def load_config():
    """Load config from appdata. Returns merged config with current LANs."""
    try:
        val = cp.get_appdata(APP_DATA_KEY)
        if val:
            saved = json.loads(val)
            if saved:
                return saved
    except Exception as e:
        cp.log("No config found or parse error - using defaults: %s" % e)
    return {
        "interval": DEFAULT_INTERVAL,
        "udp_port": DEFAULT_UDP_PORT,
        "networks": get_default_networks()
    }


def save_config(config):
    """Save config to appdata."""
    try:
        cp.put_appdata(APP_DATA_KEY, json.dumps(config))
    except Exception as e:
        cp.get_logger().exception("Error saving config: %s", e)


class ConfigHandler(tornado.web.RequestHandler):
    """Handles config/ endpoint requests."""
    def get(self):
        """Return app config in JSON for web UI."""
        config = get_config()
        self.write(json.dumps(config))


class SubmitHandler(tornado.web.RequestHandler):
    """Handles submit/ endpoint requests."""
    def get(self):
        """Parse args and update and save config."""
        try:
            broadcaster.interval = int(self.get_argument('interval', DEFAULT_INTERVAL))
            broadcaster.udp_port = int(self.get_argument('udp_port', DEFAULT_UDP_PORT))
            networks = self.get_arguments('networks')
            lans = []
            cp_lans = cp.get('config/lan') or []
            for lan in cp_lans:
                enabled = lan["_id_"] in networks
                lans.append({
                    "_id_": lan["_id_"],
                    "name": lan["name"],
                    "enabled": enabled
                })
            broadcaster.networks = lans
            config = {
                "interval": broadcaster.interval,
                "udp_port": broadcaster.udp_port,
                "networks": lans
            }
            save_config(config)
            cp.log("Saved new config: %s" % config)
            self.redirect('/')
        except Exception as e:
            cp.get_logger().exception("Error saving config: %s", e)


def get_message():
    """Collect WAN and VPN States and send UDP Broadcast."""
    try:
        datestamp = datetime.utcnow().strftime("%Y%m%d")
        timestamp = datetime.utcnow().strftime("%H%M%S")
        model = cp.get('status/product_info/product_name')
        fw = cp.get('status/fw_info')
        if fw:
            NCOS_version = '%s.%s.%s' % (
                fw.get("major_version", 0),
                fw.get("minor_version", 0),
                fw.get("patch_version", 0)
            )
        else:
            NCOS_version = "0.0.0"

        payload = {
            "TimeStamp": {"Date": datestamp, "Time": timestamp},
            "ModemInfo": {
                "ModelNum": model,
                "SwVer": NCOS_version,
                "SchemaVer": "01.00.00.00"
            }
        }

        wan_conn_status = []
        wan_devices = None
        for _ in range(10):
            wan_devices = cp.get('status/wan/devices')
            if wan_devices:
                break
            time.sleep(0.5)
        if not wan_devices:
            wan_devices = {}

        wan_devs = {
            uid: status for uid, status in wan_devices.items()
            if 'NOSIM' not in (status.get('status', {}).get('error_text') or '')
        }

        for dev, status in wan_devs.items():
            try:
                wan_conn = get_wan_connection_info(dev, status)
                wan_conn_status.append(wan_conn)
            except Exception as e:
                cp.get_logger().exception("Exception getting WAN State for %s: %s", dev, e)
        payload["WANConnStatus"] = wan_conn_status

        vpn_status = []
        vpns = cp.get('config/vpn/tunnels') or []
        for vpn in vpns:
            try:
                state = cp.get('status/vpn/tunnels/%s/state' % vpn["_id_"])
                connected = bool(state == 'up')
                vpn_status.append({
                    "Name": vpn["name"],
                    "Status": connected
                })
            except Exception as e:
                cp.get_logger().exception("Exception getting VPN state for %s: %s", vpn["_id_"], e)
        if vpn_status:
            payload["VPNStatus"] = vpn_status

        fix = cp.get('status/gps/fix')
        for _ in range(3):
            if fix:
                break
            fix = cp.get('status/gps/fix')
        if fix:
            try:
                lat_deg = fix['latitude']['degree']
                lat_min = fix['latitude']['minute']
                lat_sec = fix['latitude']['second']
                lon_deg = fix['longitude']['degree']
                lon_min = fix['longitude']['minute']
                lon_sec = fix['longitude']['second']
                lat = dec(lat_deg, lat_min, lat_sec)
                lon = dec(lon_deg, lon_min, lon_sec)
                payload["GNSSStatus"] = {
                    "Lat": lat,
                    "Lon": lon,
                    "Accuracy": fix.get('accuracy'),
                    "Fix": fix.get('lock'),
                    "NumSatellites": fix.get('satellites')
                }
            except Exception as e:
                cp.get_logger().exception("Exception getting GPS: %s", e)

        return json.dumps(payload).encode('utf-8')
    except Exception as e:
        cp.get_logger().exception("Exception getting message: %s", e)
        return None


class Broadcaster:
    """UDP Beacon Broadcaster."""
    interval = DEFAULT_INTERVAL
    udp_port = DEFAULT_UDP_PORT
    networks = []
    debug = False

    def loop(self):
        """Main loop to manage broadcasts."""
        get_config()
        primary_device = cp.get('status/wan/primary_device')
        vpn_state = self.get_vpn_states()
        message = get_message()
        if message:
            self.send_broadcast(message)
        last_broadcast = time.time()

        while True:
            get_config()
            try:
                self.debug = bool(cp.get('config/system/admin/reboot_count/enabled'))
            except Exception:
                self.debug = False
            temp_vpn_state = self.get_vpn_states()
            temp_primary_device = cp.get('status/wan/primary_device')
            if (temp_vpn_state != vpn_state or
                    temp_primary_device != primary_device or
                    time.time() - last_broadcast > self.interval):
                message = get_message()
                if message:
                    self.send_broadcast(message)
                vpn_state = temp_vpn_state
                primary_device = temp_primary_device
                last_broadcast = time.time()
            time.sleep(1)

    def get_vpn_states(self):
        """Get VPN states."""
        vpn_state = {}
        vpns = cp.get('config/vpn/tunnels') or []
        for vpn in vpns:
            try:
                state = cp.get('status/vpn/tunnels/%s/state' % vpn["_id_"])
                vpn_state[vpn["_id_"]] = state
            except Exception as e:
                cp.get_logger().exception("Error getting VPN state for %s: %s", vpn["_id_"], e)
        return vpn_state

    def send_broadcast(self, message):
        """Send UDP Broadcasts to configured LANs."""
        for network in self.networks:
            if network.get("enabled"):
                try:
                    lan_ip = cp.get('config/lan/%s/ip_address' % network["_id_"])
                    dec_mask = cp.get('config/lan/%s/netmask' % network["_id_"])
                    if not lan_ip or not dec_mask:
                        continue
                    cidr_mask = cidr(dec_mask)
                    interface = '%s/%s' % (lan_ip, cidr_mask)
                    addr = ipaddress.ip_interface(interface)
                    broadcast = str(addr.network.broadcast_address)
                    udp_socket.sendto(message, (broadcast, self.udp_port))
                    if self.debug:
                        cp.log("Broadcast to %s on %s on UDP Port %s" % (
                            broadcast, network["name"], self.udp_port))
                except Exception as e:
                    cp.get_logger().exception("Exception sending broadcast on %s: %s",
                                             network["name"], e)


def get_config():
    """Return app config, merging saved config with current LANs."""
    cp_lans = cp.get('config/lan') or []
    networks = []
    for lan in cp_lans:
        networks.append({
            "_id_": lan["_id_"],
            "name": lan["name"],
            "enabled": False
        })

    config = load_config()
    try:
        broadcaster.interval = int(config.get("interval", DEFAULT_INTERVAL))
        broadcaster.udp_port = int(config.get("udp_port", DEFAULT_UDP_PORT))
        saved_networks = config.get("networks") or []
        enabled_ids = {n["_id_"] for n in saved_networks if n.get("enabled")}
        for net in networks:
            net["enabled"] = net["_id_"] in enabled_ids
        broadcaster.networks = networks
        config["networks"] = networks
    except Exception as e:
        cp.get_logger().exception("Error loading config: %s", e)
    return config


def cidr(netmask):
    """Return CIDR netmask."""
    octets = str(netmask).split('.')
    binary_str = ''
    for octet in octets:
        binary_str += bin(int(octet))[2:].zfill(8)
    return str(len(binary_str.rstrip('0')))


def dec(deg, min_val, sec):
    """Return decimal version of lat or long from deg, min, sec."""
    if str(deg)[0] == '-':
        return round(deg - (min_val / 60) - (sec / 3600), 6)
    return round(deg + (min_val / 60) + (sec / 3600), 6)


def get_wan_connection_info(dev, status):
    """Get WAN connection information."""
    wan_type = status.get("info", {}).get("type", "")
    nwktype = get_network_type(wan_type, status)
    state = bool(status.get("status", {}).get("connection_state") == "connected")
    primary_device = cp.get('status/wan/primary_device')
    default_route = bool(dev == primary_device)

    wan_conn = {
        "Name": status.get('config', {}).get('trigger_name'),
        "NwkType": nwktype,
        "State": state,
        "DefaultRoute": default_route,
    }

    if wan_type == 'mdm':
        add_cellular_info(wan_conn, status)
    elif nwktype == 'wifi':
        add_wifi_info(wan_conn, status)

    return wan_conn


def get_network_type(wan_type, status):
    """Get network type based on WAN type and status."""
    if wan_type == 'mdm':
        diagnostics = status.get("diagnostics") or {}
        serdis = diagnostics.get("SERDIS", "Unknown")
        return {'LTE': 'cellular-4G', '5G': 'cellular-5G'}.get(serdis, 'cellular-%s' % serdis)
    if wan_type == 'wwan':
        return 'wifi'
    if wan_type == 'ethernet':
        return 'ethernet'
    return 'Unknown'


def add_cellular_info(wan_conn, status):
    """Add cellular-specific information to WAN connection."""
    diagnostics = status.get("diagnostics", {})
    if diagnostics.get("DBM"):
        wan_conn["RSSI"] = float(diagnostics["DBM"])
    if diagnostics.get("ACTIVEAPN"):
        wan_conn["APN"] = diagnostics["ACTIVEAPN"]
    if diagnostics.get("RSRP"):
        wan_conn["RSRP"] = int(diagnostics["RSRP"])
    if diagnostics.get("RSRQ"):
        wan_conn["RSRQ"] = int(diagnostics["RSRQ"])
    if diagnostics.get("SINR"):
        wan_conn["SINR"] = float(diagnostics["SINR"])


def add_wifi_info(wan_conn, status):
    """Add WiFi-specific information to WAN connection."""
    diagnostics = status.get("diagnostics", {})
    if diagnostics.get("RSSI"):
        wan_conn["RSSI"] = float(diagnostics["RSSI"])


if __name__ == "__main__":
    cp.log('Starting...')

    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.settimeout(0.2)

    broadcaster = Broadcaster()
    Thread(target=broadcaster.loop, daemon=True).start()

    web_port = int(cp.get_appdata('Motorola_port') or 8000)
    cp.log('Web UI on port %s' % web_port)
    application = tornado.web.Application([
        (r"/config", ConfigHandler),
        (r"/submit", SubmitHandler),
        (r"/(.*)", tornado.web.StaticFileHandler,
         {"path": os.path.dirname(__file__), "default_filename": "index.html"}),
    ])
    application.listen(web_port)
    tornado.ioloop.IOLoop.instance().start()
