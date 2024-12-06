# usb_alerts - send alerts when USB devices are connected or disconnected

from csclient import EventingCSClient
from subprocess import Popen, PIPE

cp = EventingCSClient('usb_alerts')
cp.log('Starting...')

cmd = ['/usr/bin/tail', '/var/log/messages', '-F']
tail = Popen(cmd, stdout=PIPE, stderr=PIPE)
for line in iter(tail.stdout.readline, ''):
    if tail.returncode:
        break
    try:
        line = line.decode()
        if 'speed USB' in line:
            msg = f'USB Connected: {line.split("USB")[1].strip()}'
            cp.alert(msg)
        if 'USB disconnect' in line:
            msg = line.split(":")[2].strip().replace("disconnect", "Disconnected")
            cp.alert(msg)
    except:
        pass
