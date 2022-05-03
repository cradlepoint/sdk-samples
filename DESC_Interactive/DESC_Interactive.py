# -*- coding: utf-8 -*-
"""
Created on Wed Jan 27 15:39:31 2021

@author: amickel
"""

import csclient as cs
import time

APP_NAME = 'DESC_Interactive'
while 1:
    desc = cs.CSClient().get('/config/system/desc')
    if desc.startswith("/status"):
        if desc == 'status/ethernet':
            ports_status = "Ports: "
            for port in cs.CSClient().get('/status/ethernet').get('data'):
                if port['port'] is 0:
                    ports_status += " WAN: "
                elif port['port'] is 1:
                    ports_status += " LAN: "        
                if port['link'] == "up":
                    ports_status += " 🟢 "
                elif port['link'] == "down":
                    ports_status += " 🔴 "
            cs.CSClient().put('/config/system/desc', ports_status)
        else:
            cs.CSClient().put('/config/system/desc', cs.CSClient().get(desc).get('data'))
    time.sleep(5)
