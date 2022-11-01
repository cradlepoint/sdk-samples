"""epilog - SDK Application that writes logs to files on flash available for download via HTTP/Remote Connect.

Never lose another log!  Remote Syslog!
No more logs rolling over, no more physical USB flash drives,
and you can recover logs after a reboot.  Via Remote Connect!

A "Full Log {MAC ADDRESS}.txt" file will be created containing all logs.
Individual "Log {MAC ADDRESS} {TIMESTAMP}.txt" files will be created at each boot for isolating logs.

Use Remote Connect LAN Manager to connect to 127.0.0.1 port 8000 HTTP.
Or forward the LAN zone to the ROUTER zone for local access on http://{ROUTER IP}:8000.

"""

from csclient import EventingCSClient
from subprocess import Popen, PIPE
import datetime
import time

cp = EventingCSClient('epilog')
cp.log(f'Download log via NCM LAN Manager - HTTP 127.0.0.1 port 8000')

try:
    mac = cp.get('status/product_info/mac0').replace(':', '').upper()
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    logfile = f'Log - {mac} {timestamp}.txt'
    full_log = f'Full Log - {mac}.txt'

    cmd = ['/usr/bin/tail', '/var/log/messages', '-n1000', '-F']
    tail = Popen(cmd, stdout=PIPE, stderr=PIPE)
    with open(f'logs/{logfile}', 'a+') as f:
        with open(f'logs/{full_log}', 'a+') as g:
            for line in iter(tail.stdout.readline, ''):
                if tail.returncode:
                    break
                line = line.decode('utf-8').split(' ')
                try:
                    line[0] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(float(line[0])))
                except:
                    pass
                line = ' '.join(line)
                f.write(line)
                g.write(line)
except Exception as e:
    cp.log(f'Exception! {e}')
