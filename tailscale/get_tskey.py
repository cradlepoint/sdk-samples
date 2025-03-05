from csappdata import AppDataCSClient
import ipaddress
import sys


if __name__ == "__main__":
    command = sys.argv[1]

    cs = AppDataCSClient('certificate_data', encrypt_cert_name='ecc')

    if command in ["tskey", "tsversion", "tstags"]:
        try:
            value = cs.get_appdata(command)
            if value:
                print(value)
        except Exception as e:
            print(f"An error occurred: {e}", file=sys.stderr)
            exit(1)

    elif command == "tsroutes":
        lans = cs.get("/config/lan")
        networks = []
        for lan in lans:
            network = str(ipaddress.ip_network(f"{lan['ip_address']}/{lan['netmask']}", strict=False))
            networks.append(network)
        tsroutes = cs.get_appdata('tsroutes')
        if tsroutes:
            networks.extend(list(map(str.strip, tsroutes.split(','))))
        print(",".join(networks))
    
    elif command == "tshostname":
        hostname = cs.get_appdata('tshostname')
        if not hostname:
            hostname = cs.get("/config/system/system_id")
        print(hostname)