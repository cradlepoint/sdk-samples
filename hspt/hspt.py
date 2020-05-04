"""
Copyright (c) 2016 CradlePoint, Inc. <www.cradlepoint.com>.  All rights
reserved.

This file contains confidential information of CradlePoint, Inc. and your use
of this file is subject to the CradlePoint Software License Agreement
distributed with this file. Unauthorized reproduction or distribution of this
file is subject to civil and criminal penalties.
"""
import os
import sys
from csclient import EventingCSClient


def mkroutes(route, directory):
    location = "%s/%s" % (os.getcwd(), directory)
    route_map.append((route, location))


cp = EventingCSClient('hspt')

# Build route maps for / and /resources
route_map = []
sys.path.append('.')
mkroutes('/(.*)', '')
mkroutes('/resources/(.*)', 'resources/')

value = {
    'action': 'start',
    'routes': route_map,
    'server': 'hotspotServer'
}
cp.put('/control/system/httpserver', value)
