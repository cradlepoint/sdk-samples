# -*- coding: utf-8 -*-
"""
This program allows the user interact with the local API by using the
description field as the input command and posting the output of the command
back into the description field. If a status command is passed the Cradlepoint
will re-run the command every 5 seconds until a new command is entered. Thanks
to @nathanwiens for the port status contribution, which will post unicode
symbols representing each port's status to the description field. Due to field
character length limitations only the first 256 characters of the result will
be put into the description.

 Example description field good input and expected output:
     input:
         .put('/config/system/gps/enabled', False)
     expected output:
         {'success': True, 'data': False}
 Example description field bad input and expected output:
     input:
         .put('/config/system/enabled', False)
     expected output:
         {'success': False, 'data': {'exception': 'key', 'key': 'enabled'}}
"""

import csclient as cs
import time
import sys
from csclient import EventingCSClient
cp = EventingCSClient('hello_world')
APP_NAME = 'DESC_Interactive'
last_status = ''

while 1:
    desc = cs.CSClient().get('/config/system/desc')
    if desc['success'] is True and desc['data'] is not None:
        desc = desc.get('data')
        print("Desc data is: ", desc)
        if (desc.startswith('.get(\'/status') or last_status != '' or
                desc.startswith('.get(\'status')):
            if (desc.startswith('.get(\'/status') or
                    desc.startswith('.get(\'status')):
                last_status = desc
            elif last_status == '':
                print("Invalid state!")
                sys.exit(1)
            if last_status == '.get(\'/status/ethernet\')':
                # pretty format for status/ethernet info
                ports_status = "Ports: "
                for port in cs.CSClient().get('/status/ethernet').get('data'):
                    if port['port'] == 0:
                        ports_status += " WAN: "
                    elif port['port'] == 1:
                        ports_status += " LAN: "
                    if port['link'] == "up":
                        ports_status += " 🟢 "
                    elif port['link'] == "down":
                        ports_status += " 🔴 "
                cs.CSClient().put('/config/system/desc', ports_status)
            else:
                try:
                    print("trying: ", 'cs.CSClient()' + last_status)
                    data = eval('cs.CSClient()'+last_status)
                    print(data)
                    cs.CSClient().put('/config/system/desc',
                                      str(data.get('data'))[0:255])
                except Exception as e:
                    print(e)
                    cs.CSClient().put('/config/system/desc', str(e))
        elif desc.startswith("."):
            # All other calls to status are unformatted and return a raw string
            last_status = ''
            try:
                data = eval('cs.CSClient()'+desc)
                cs.CSClient().put('/config/system/desc',
                                  str(data.get('data'))[0:255])
            except Exception as e:
                print(e)
                cs.CSClient().put('/config/system/desc', str(e))

    time.sleep(5)
