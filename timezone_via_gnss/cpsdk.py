from csclient import EventingCSClient
import time

class CPSDK(EventingCSClient):
    def __init__(self, appname):
        super().__init__(appname)


    def get_uptime(self):
        """Return the router uptime in seconds."""
        uptime = int(self.get('status/system/uptime'))
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

    
    def extract_and_save_cert(self, cert_name):
        """Extract and save the certificate and key to the local filesystem."""
        cert_x509 = None
        cert_key = None
        ca_uuid = None

        # Get the list of certificates
        certs = self.get('config/certmgmt/certs')

        # Extract the x509 and key for the matching certificate and its CA
        for cert in certs:
            if cert['name'] == cert_name:
                cert_x509 = cert.get('x509')
                cert_key = self.decrypt(f'config/certmgmt/certs/{cert["_id_"]}/key')
                ca_uuid = cert.get('ca_uuid')
                self.log(f'Found certificate "{cert_name}" with CA UUID: {ca_uuid}')
                break
        else:
            self.log(f'No certificate "{cert_name}" found')
            return

        # Extract the CA certificate(s) if it exists
        while ca_uuid not in ["", "None", None]:
            for cert in certs:
                if cert.get('_id_') == ca_uuid:
                    cert_x509 += "\n" + cert.get('x509')
                    ca_uuid = cert.get('ca_uuid')
                    msg = f'Found CA certificate "{cert.get("name")}"'
                    if ca_uuid not in ["", "None", None]:
                        msg += f' with CA UUID: {ca_uuid}'
                    self.log(msg)

        # Write the fullchain and privatekey .pem files
        if cert_x509 and cert_key:
            with open(f"{cert_name}.pem", "w") as fullchain_file:
                fullchain_file.write(cert_x509)
            with open(f"{cert_name}_key.pem", "w") as privatekey_file:
                privatekey_file.write(cert_key)
            self.log(f'Certificate "{cert_name}" extracted and saved')
        else:
            self.log(f'Missing certificate or key for "{cert_name}"')


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
                "ip": lan_client.get("ip_address"),
                "network": network
            })
        return wired_clients


    def get_ipv4_wifi_clients(self):
        """Return a list of IPv4 Wi-Fi clients and their details."""
        wifi_clients = []
        wlan_clients = self.get('status/wlan/clients') or []
        bw_modes = {0: "20 MHz", 1: "40 MHz", 2: "80 MHz", 3: "80+80 MHz", 4: "160 MHz"}
        wlan_modes = {0: "802.11b", 1: "802.11g", 2: "802.11n", 3: "802.11n-only", 4: "802.11ac", 5: "802.11ax"}
        wlan_band = {0: "2.4", 1: "5"}

        for wlan_client in wlan_clients:
            radio = wlan_client.get("radio")
            bss = wlan_client.get("bss")
            ssid = self.get(f'config/wlan/radio/{radio}/bss/{bss}/ssid')

            mac_upper = wlan_client.get("mac", "").upper()
            hostname = wlan_client.get("hostname")

            # Set hostname to None if it matches the MAC address with hyphens or is "*"
            if hostname and (hostname.upper() == mac_upper.replace(":", "-") or hostname == "*"):
                hostname = None

            wifi_clients.append({
                "mac": wlan_client.get("mac"),
                "hostname": hostname,
                "ip": wlan_client.get("ip_address"),
                "radio": radio,
                "bss": bss,
                "ssid": ssid,
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
            