# cli - execute CLI command and return output

import time

import cp
from csterm import CSTerm

ct = CSTerm(cp)
cp.log('Starting...')
while True:
    # use ct.exec followed by CLI command to execute
    # Example: "sms 2081234567 'hello world' int1"
    # Example: "arpdump"
    cp.log('Output:\n' + ct.exec('arpdump'))
    time.sleep(10)
