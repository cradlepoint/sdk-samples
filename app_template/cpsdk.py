from csclient import EventingCSClient
import time
import re

class CPSDK(EventingCSClient):
    def __init__(self, appname):
        super().__init__(appname)

    def get_uptime(self):
        """Return the router uptime in seconds."""
        return int(self.get('status/system/uptime'))
        return uptime

    def wait_for_uptime(self, min_uptime_seconds):
        """Wait for the device uptime to be greater than the specified uptime and sleep if it is less than the specified uptime."""
        try:
            current_uptime = self.get_uptime()
            if current_uptime < min_uptime_seconds:
                sleep_duration = min_uptime_seconds - current_uptime
                self.log(f"Router uptime is less than {min_uptime_seconds} seconds. Sleeping for {sleep_duration} seconds.")
                time.sleep(sleep_duration)
            else:
                self.log(f"Router uptime is sufficient: {current_uptime} seconds.")
        except Exception as e:
            self.logger.exception(f"Error validating uptime: {e}")
    
    def wait_for_wan_connection(self):
        """Wait for a WAN connection to be established."""
        while True:
            if self.get('status/wan/connection_state') == 'connected':
                return
            time.sleep(1)

    def get_router_id(self):
        """Return the router ID."""
        return self.get('status/ecm/client_id')

    def get_appdata(self, name):
        """Get value of appdata from NCOS Config by name."""
        appdata = self.get('config/system/sdk/appdata')
        return next(iter(x["value"] for x in appdata if x["name"] == name), None)
    
    def post_appdata(self, name, value):
        """Create appdata in NCOS Config by name."""
        self.post('config/system/sdk/appdata', {"name": name, "value": value})
    
    def put_appdata(self, name, value):
        """Set value of appdata in NCOS Config by name."""
        appdata = self.get('config/system/sdk/appdata')
        for item in appdata:
            if item["name"] == name:
                self.put(f'config/system/sdk/appdata/{item["_id_"]}/value', value)
    
    def delete_appdata(self, name):
        """Delete appdata in NCOS Config by name."""
        appdata = self.get('config/system/sdk/appdata')
        for item in appdata:
            if item["name"] == name:
                self.delete(f'config/system/sdk/appdata/{item["_id_"]}')

    def get_ncm_api_keys(self):
        """Get NCM API keys from the router's certificate management configuration.
        Returns:
            dict: Dictionary containing all API keys, with None for any missing keys
        """
        try:
            certs = self.get('config/certmgmt/certs')
            
            api_keys = {
                'X-ECM-API-ID': None,
                'X-ECM-API-KEY': None,
                'X-CP-API-ID': None,
                'X-CP-API-KEY': None,
                'Bearer Token': None
            }

            for cert in certs:
                cert_name = cert.get('name', '')
                for key in api_keys:
                    if key in cert_name:
                        api_keys[key] = self.decrypt(f'config/certmgmt/certs/{cert["_id_"]}/key')

            # Log warning for any missing keys
            missing = [k for k, v in api_keys.items() if v is None]
            if missing:
                self.logger.warning(f"Missing API keys: {', '.join(missing)}")

            return api_keys
            
        except Exception as e:
            self.logger.exception(f"Error retrieving NCM API keys: {e}")
            raise

    def extract_cert_and_key(self, cert_name_or_uuid):
        """Extract and save the certificate and key to the local filesystem. Returns the filenames of the certificate and key files."""
        cert_x509 = None
        cert_key = None
        ca_uuid = None
        cert_name = None

        # Check if cert_name_or_uuid is in UUID format
        uuid_regex = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
        is_uuid = bool(uuid_regex.match(cert_name_or_uuid))
        match_field = '_id_' if is_uuid else 'name'

        # Get the list of certificates
        certs = self.get('config/certmgmt/certs')

        # if cert_name is a uuid, find the cert by uuid, otherwise, find the cert by name
        for cert in certs:
            if cert[match_field] == cert_name_or_uuid:
                cert_name = cert.get('name')
                cert_x509 = cert.get('x509')
                cert_key = self.decrypt(f'config/certmgmt/certs/{cert["_id_"]}/key')
                ca_uuid = cert.get('ca_uuid')
                break
        else:
            self.log(f'No certificate "{cert_name_or_uuid}" found')
            return None, None

        # Extract the CA certificate(s) if it exists
        while ca_uuid not in ["", "None", None]:
            for cert in certs:
                if cert.get('_id_') == ca_uuid:
                    cert_x509 += "\n" + cert.get('x509')
                    ca_uuid = cert.get('ca_uuid')

        # Write the fullchain and privatekey .pem files
        if cert_x509 and cert_key:
            with open(f"{cert_name}.pem", "w") as fullchain_file:
                fullchain_file.write(cert_x509)
            with open(f"{cert_name}_key.pem", "w") as privatekey_file:
                privatekey_file.write(cert_key)
            return f"{cert_name}.pem", f"{cert_name}_key.pem"
        elif cert_x509:
            with open(f"{cert_name}.pem", "w") as fullchain_file:
                fullchain_file.write(cert_x509)
            return f"{cert_name}.pem", None
        else:
            self.log(f'Missing x509 certificate for "{cert_name_or_uuid}"')
            return None, None

    def get_ipv4_wired_clients(self):
        """Return a list of IPv4 wired clients and their details."""
        wired_clients = []
        lan_clients = self.get('status/lan/clients') or []
        leases = self.get('status/dhcpd/leases') or []

        # Filter out IPv6 clients
        lan_clients = [client for client in lan_clients if ":" not in client.get("ip_address", "")]

        for lan_client in lan_clients:
            mac_upper = lan_client.get("mac", "").upper()
            lease = next((x for x in leases if x.get("mac", "").upper() == mac_upper), None)
            hostname = lease.get("hostname") if lease else None
            network = lease.get("network") if lease else None

            # Set hostname to None if it matches the MAC address with hyphens or is "*"
            if hostname and (hostname.upper() == mac_upper.replace(":", "-") or hostname == "*"):
                hostname = None

            wired_clients.append({
                "mac": lan_client.get("mac"),
                "hostname": hostname,
                "ip_address": lan_client.get("ip_address"),
                "network": network
            })
        return wired_clients

    def get_ipv4_wifi_clients(self):
        """Return a list of IPv4 Wi-Fi clients and their details."""
        wifi_clients = []
        wlan_clients = self.get('status/wlan/clients') or []
        leases = self.get('status/dhcpd/leases') or []
        bw_modes = {0: "20 MHz", 1: "40 MHz", 2: "80 MHz", 3: "80+80 MHz", 4: "160 MHz"}
        wlan_modes = {0: "802.11b", 1: "802.11g", 2: "802.11n", 3: "802.11n-only", 4: "802.11ac", 5: "802.11ax"}
        wlan_band = {0: "2.4", 1: "5"}

        for wlan_client in wlan_clients:
            radio = wlan_client.get("radio")
            bss = wlan_client.get("bss")
            ssid = self.get(f'config/wlan/radio/{radio}/bss/{bss}/ssid')

            mac_upper = wlan_client.get("mac", "").upper()
            
            # Get DHCP lease information
            lease = next((x for x in leases if x.get("mac", "").upper() == mac_upper), None)
            hostname = lease.get("hostname") if lease else wlan_client.get("hostname")
            network = lease.get("network") if lease else None

            # Set hostname to None if it matches the MAC address with hyphens or is "*"
            if hostname and (hostname.upper() == mac_upper.replace(":", "-") or hostname == "*"):
                hostname = None

            wifi_clients.append({
                "mac": wlan_client.get("mac"),
                "hostname": hostname,
                "ip_address": lease.get("ip_address"),
                "radio": radio,
                "bss": bss,
                "ssid": ssid,
                "network": network,
                "band": wlan_band.get(radio, "Unknown"),
                "mode": wlan_modes.get(wlan_client.get("mode"), "Unknown"),
                "bw": bw_modes.get(wlan_client.get("bw"), "Unknown"),
                "txrate": wlan_client.get("txrate"),
                "rssi": wlan_client.get("rssi0"),
                "time": wlan_client.get("time", 0)
            })
        return wifi_clients

    def get_ipv4_lan_clients(self):
        """Return a dictionary containing all IPv4 clients, both wired and Wi-Fi."""
        try:
            wired_clients = self.get_ipv4_wired_clients()
            wifi_clients = self.get_ipv4_wifi_clients()

            # Ensure both keys are present in the final dictionary
            lan_clients = {
                "wired_clients": wired_clients,
                "wifi_clients": wifi_clients
            }

            return lan_clients
        except Exception as e:
            self.logger.exception(f"Error retrieving clients: {e}")

    def get_lat_long(self):
        """Return latitude and longitude as floats"""
        fix = self.get('status/gps/fix')
        retries = 0
        while not fix and retries < 5:
            time.sleep(0.1)
            fix = self.get('status/gps/fix')
            retries += 1

        if not fix:
            return None, None

        try:
            lat_deg = fix['latitude']['degree']
            lat_min = fix['latitude']['minute']
            lat_sec = fix['latitude']['second']
            long_deg = fix['longitude']['degree']
            long_min = fix['longitude']['minute']
            long_sec = fix['longitude']['second']
            lat = self.dec(lat_deg, lat_min, lat_sec)
            long = self.dec(long_deg, long_min, long_sec)
            lat = float(f"{float(lat):.6f}")
            long = float(f"{float(long):.6f}")
            return lat, long
        except:
            return None, None
            
    def dec(self, deg, min, sec):
        """Return decimal version of lat or long from deg, min, sec"""
        if str(deg)[0] == '-':
            dec = deg - (min / 60) - (sec / 3600)
        else:
            dec = deg + (min / 60) + (sec / 3600)
        return round(dec, 6)
    
    def get_connected_wans(self):
        """Return list of connected WAN UIDs"""
        wans = []
        while not wans:
            wans = self.get('status/wan/devices')
        # get the wans that are connected
        wans = [k for k, v in wans.items() if v['status']['connection_state'] == 'connected']
        if not wans:
            self.log('No WANs connected!')
        return wans

    def get_sims(self):
        """Return list of modem UIDs with SIMs"""
        SIMs = []
        devices = None
        while not devices:
            devices = self.get('status/wan/devices')
        for uid, status in devices.items():
            if uid.startswith('mdm-'):
                error_text = status.get('status', {}).get('error_text', '')
                if error_text:
                    if 'NOSIM' in error_text:
                        continue
                SIMs.append(uid)
        return SIMs

    def get_wan_connection_state(self):
        """Return the connection state of the WAN."""
        return self.get('status/wan/connection_state')
    
    def get_wan_devices(self):
        """Return the list of WAN devices."""
        return self.get('status/wan/devices')
    
    def get_wan_device_status(self, device_id):
        """Return the status of a WAN device."""
        return self.get(f'status/wan/devices/{device_id}/status')
    
    def get_wan_device_connection_state(self, device_id):
        """Return the connection state of a WAN device."""
        return self.get(f'status/wan/devices/{device_id}/status/connection_state')
    
    def get_wan_device_profile_id(self, device_id):
        """Return the profile ID of a WAN device."""
        return self.get(f'status/wan/devices/{device_id}/config/_id_')
    
    def get_ipverify_id_by_name(self, name):
        """Return the IPVerify ID of a WAN device by name."""
        ipverifies = self.get('config/identities/ipverify')
        return next(iter(x['_id_'] for x in ipverifies if x['name'] == name), None)
    
    def register_ipverify_function(self, ipverify_id, function):
        """Register a function to be called when the IPVerify test state changes."""
        self.register('put', f'status/ipverify/{ipverify_id}/pass', function)

    def get_wan_profiles(self):
        """Return the list of WAN profiles."""
        return self.get('config/wan/rules2')
    
    def get_wan_profile_by_id(self, id):
        """Return the WAN profile by ID."""
        return next(iter(x for x in self.get('config/wan/rules2') if x['_id_'] == id), None)
    
    def get_wan_profile_by_name(self, name):
        """Return the WAN profile by name."""
        return next(iter(x for x in self.get('config/wan/rules2') if x['name'] == name), None)
    
    def get_custom_apns(self):
        """Return the list of custom APNs."""
        return self.get('config/wan/custom_apns')
    
    def add_custom_apn(self, carrier, apn):
        """Add a custom APN to the config"""
        self.post('config/wan/custom_apns', {'carrier': carrier, 'apn': apn})

    def delete_custom_apn(self, apn):
        """Delete a custom APN from the config"""
        self.delete(f'config/wan/custom_apns/{apn}')
