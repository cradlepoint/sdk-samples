import subprocess
import time
from csclient import CSClient
import shlex
import threading
from ipaddress import ip_address


cs = CSClient('rproxy')

LOGGER = cs.logger


def get_binary():
    arch = subprocess.check_output(["uname", "-m"], text=True).strip()
    if arch == "armv7l":
        return "./rproxy_arm"
    elif arch == "x86_64":
        return "./rproxy_amd64"
    elif arch == "aarch64":
        return "./rproxy_arm64"
    else:
        raise Exception(f"unsupported architecture {arch}")


def run_cmd(local_host, local_port, remote_host, remote_port, protocol):
    binary = get_binary()
    return shlex.split(f"{binary} -b {local_host}:{local_port} -r {remote_host}:{remote_port} -p {protocol}")


def populate_auto_rproxy_config():

    def ranges(s):
        for r in s.split(','):
            r = r.split('-')
            first = int(r[0])
            last = int(r[-1])
            yield from range(first, last+1)
        while True:
            last += 1
            if last > 65535:
                break
            yield last
        
    appdata = cs.get("/config/system/sdk/appdata")
    cmd_strings = set()

    for r in (j['value'] for j in appdata if j['name'].startswith('rproxy.auto')):
        # e.g. local_host:local_port_ranges:remote_port:protocol
        parts = r.split(':')
        if "." not in parts[0]:
            parts.insert(0, "127.0.0.1")
        if len(parts) < 4:
            parts.append("TCP")
        local_host = parts[0]
        local_port_ranges = ranges(parts[1])
        remote_port = parts[2]
        protocol = "UDP" if parts[3].upper() == "UDP" else "TCP"

        current_clients = cs.get("/status/lan/clients")
        for client in current_clients:
            if ip_address(client['ip_address']).version == 4:
                cmd = f"{local_host}:{next(local_port_ranges)}:{client['ip_address']}:{remote_port}:{protocol}"
                cmd_strings.add(cmd)

    return cmd_strings


def get_rproxy_config():
    appdata = cs.get("/config/system/sdk/appdata")
    return set(j['value'] for j in appdata if (j['name'].startswith('rproxy') and not j['name'].startswith('rproxy.auto')))


def main():
    LOGGER.info("starting rproxy")
    rproxy = populate_auto_rproxy_config()
    rproxy.update(get_rproxy_config())

    def output_thread(proc):
        for line in proc.stdout:
            LOGGER.info(line)
    
    ps = []
    ts = []
    for r in rproxy:
        # e.g. 0.0.0.0:80:192.168.0.5:80:tcp
        cmd = r.split(':')
        if "." not in cmd[0]:
            cmd.insert(0, "127.0.0.1")
        if len(cmd) < 5:
            cmd.append("TCP")
        local_host = cmd[0]
        local_port = cmd[1]
        remote_host = cmd[2]
        remote_port = cmd[3]
        protocol =  "UDP" if cmd[4].upper() == "UDP" else "TCP"
        cmd = run_cmd(local_host, local_port, remote_host, remote_port, protocol)
        LOGGER.info(f"starting rproxy: {cmd}")
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        t = threading.Thread(target=output_thread, args=(p,))
        t.daemon = True
        t.start()
        ps.append(p)
        ts.append(t)
    
    # periodically check for changes in rproxy config
    LOGGER.info("checking for rproxy config changes every 10 seconds")
    while True:
        time.sleep(10)
        new_rproxy = populate_auto_rproxy_config()
        new_rproxy.update(get_rproxy_config())
        if rproxy != new_rproxy:
            LOGGER.info(f"rproxy config changed from {rproxy} to {new_rproxy}")
            for p in ps:
                p.kill()
            break


if __name__ == "__main__":
    # cleanup any instances
    subprocess.run(["killall", "rproxy"])
    main()