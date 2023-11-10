# cli - execute CLI command and return output

import time

from csclient import EventingCSClient
from csterm import CSTerm

cp = EventingCSClient('cli_sample')
ct = CSTerm(cp)
cp.log('Starting...')
while True:
    # use ct.exec followed by CLI command to execute
    # Example: "sms 2081234567 'hello world' int1"
    # Example: "arpdump"
    cp.log('Output:\n' + ct.exec('arpdump'))
    time.sleep(10)
