from csclient import EventingCSClient
import time
import os

cp = EventingCSClient('cpu_usage')

def get_usage():

    while True:
        memory = cp.get('/status/system/memory')
        load_avg = cp.get('/status/system/load_avg')
        cpu = cp.get('/status/system/cpu')

        log_data = ('CPU Usage: ' +
                	str(round(float(cpu['nice']) +
                			  float(cpu['system']) +
                			  float(cpu['user']) *
                			  float(100))) + '%, ' +
        	        ' Mem Available: ' +
                    str(('{:,.0f}'.format(memory['memavailable'] /
                    float(1 << 20))+" MB,")) +
        	        ' Mem Total: ' + str(('{:,.0f}'.format(memory['memtotal'] /
                    float(1 << 20))+" MB" + "\n")))

        cp.log(log_data)
        time.sleep(15)

if __name__ == '__main__':

    cp.log('Started App')
    get_usage()
    cp.log('Exited App')
