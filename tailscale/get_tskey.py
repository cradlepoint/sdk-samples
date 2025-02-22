from cs_get import cs_get, get_appdata
import ipaddress
import sys


if __name__ == "__main__":
    command = sys.argv[1]

    if command in ["tskey", "tsversion", "tsadvertise_tags", "tshostname"]:
        try:
            value = get_appdata(command)
            if value:
                print(value)
        except Exception as e:
            print(f"An error occurred: {e}", file=sys.stderr)
            exit(1)

    elif command == "tsroutes":
        lans = cs_get("/config/lan")
        networks = []
        for lan in lans:
            network = str(ipaddress.ip_network(f"{lan['ip_address']}/{lan['netmask']}", strict=False))
            networks.append(network)
        tsroutes = get_appdata('tsroutes')
        if tsroutes:
            networks.extend(list(map(str.strip, tsroutes.split(','))))
        print(",".join(networks))