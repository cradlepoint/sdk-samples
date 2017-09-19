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
import argparse
import subprocess
sys.path.append('.')

import cs

path = '/control/system/httpserver'

route_map = []


def log(msg):
    subprocess.run(['logger', msg])


def mkroutes(route, directory):
    location = "%s/%s" % (os.getcwd(), directory)
    route_map.append((route, location))


def action(command):
    client = cs.CSClient()

    value = {
        'action': command,
        'routes': route_map,
        'server': 'hotspotServer'
    }
    client.put(path, value)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('opt')
    args = parser.parse_args()

    # Build route maps for / and /resources
    mkroutes('/(.*)', '')
    mkroutes('/resources/(.*)', 'resources/')

    opt = args.opt.strip()
    if opt not in ['start', 'stop']:
        log('failed to run command')
        exit()

    action(opt)
