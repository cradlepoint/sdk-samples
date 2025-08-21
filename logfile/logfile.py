"""logfile - SDK Application that writes log to files on flash available for download via HTTP/Remote Connect.

Never lose another log!  Remote Syslog!
No more logs rolling over, no more physical USB flash drives,
and you can recover logs after a reboot.  Via Remote Connect!

Log files will be created with filenames containing the router MAC address and timestamp.  Example:
Log - 0030443B3877.2022-11-11 09:52:25.txt

When the log file reaches the maximum file size (Default 100MB) it will start a new log file.
When the number of backup logs exceeds the backup count (default 10) it will delete the oldest log.

Use Remote Connect LAN Manager to connect to 127.0.0.1 port 8000 HTTP.
Or forward the LAN zone to the ROUTER zone for local access on http://{ROUTER IP}:8000.

"""

import cp
from subprocess import Popen, PIPE
import datetime
import time
import os
from os.path import isfile, join

max_file_size = 104857600
backup_count = 10

def write_logs():
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    logfile = f'logs/Log - {mac} {timestamp}'
    if os.path.exists(f'{logfile}.txt'):
        i = 1
        while True:
            suffix = f'({i})'
            if not os.path.exists(f'{logfile} {suffix}.txt'):
                logfile = f'{logfile} {suffix}.txt'
                cp.log(f'LOGFILE {logfile}')
                break
            else:
                cp.log('NOPE!')
                i += 1
    else:
        logfile += '.txt'
    f = open(logfile, 'wt')
    try:
        cmd = ['/usr/bin/tail', '/var/log/messages', '-n1', '-F']
        tail = Popen(cmd, stdout=PIPE, stderr=PIPE)
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
            f.flush()
            os.sync()
            if f.tell() > max_file_size:
                f.close()
                time.sleep(1)
                return
    except Exception as e:
        cp.log(f'Exception! {e}')

def rotate_files():
    logfiles = [f for f in os.listdir('logs') if isfile(join('logs', f))]
    logfiles = sorted(logfiles, reverse=True, key=lambda item: (int(item.partition(' ')[0])
                                                  if item[0].isdigit() else float('inf'), item))
    if len(logfiles) == backup_count:
        os.remove(f'logs/{logfiles[-1]}')

cp.log(f'Download logs via NCM LAN Manager - HTTP 127.0.0.1 port 8000')
mac = cp.get('status/product_info/mac0').replace(':', '').upper()

while True:
    write_logs()
    rotate_files()
