import cp
import time
from datetime import datetime

cp.log('Starting Failover Modem Reset...')

reboot_hour = cp.get_appdata('reboot_hour') or ''
reboot_timer = cp.get_appdata('reboot_timer') or ''
if reboot_timer:
    cp.log(f'Config: reboot_timer={reboot_timer} min')
else:
    reboot_hour = int(reboot_hour or '2')
    cp.log(f'Config: reboot_hour={reboot_hour}')


def get_mdm_devices(devices):
    """Return dict of {dev_id: dev} for modem devices that have SIMs."""
    mdms = {}
    for dev_id, dev in devices.items():
        info = dev.get('info', {})
        if info.get('type') != 'mdm':
            continue
        error = dev.get('status', {}).get('error_text', '') or ''
        if 'NOSIM' in error:
            continue
        mdms[dev_id] = dev
    return mdms


last_summaries = {}
failovers = {}  # {port: failover_time}
first_run = True

while True:
    try:
        devices = cp.get('status/wan/devices') or {}
        mdms = get_mdm_devices(devices)

        if first_run:
            for dev_id, dev in mdms.items():
                sim = dev.get('info', {}).get('sim', '?')
                summary = dev.get('status', {}).get('summary', '')
                cp.log(f'{dev_id} ({sim}): {summary}')
                last_summaries[dev_id] = summary
                if sim == 'sim2' and summary == 'connected':
                    port = dev.get('info', {}).get('port', '')
                    cp.log(f'Already on sim2 ({dev_id}) port {port} - starting reboot timer')
                    failovers[port] = time.time()
            first_run = False
            time.sleep(3)
            continue

        # Track summary changes on all mdm devices with SIMs
        for dev_id, dev in mdms.items():
            info = dev.get('info', {})
            sim = info.get('sim', '?')
            summary = dev.get('status', {}).get('summary', '')
            if dev_id in last_summaries and last_summaries[dev_id] != summary:
                cp.log(f'{dev_id} ({sim}): {last_summaries[dev_id]} -> {summary}')
                if sim == 'sim2' and summary == 'connected':
                    port = info.get('port', '')
                    if port not in failovers:
                        cp.log(f'FAILOVER DETECTED: sim2 connected on port {port} ({dev_id}). Starting reboot timer.')
                        failovers[port] = time.time()
            last_summaries[dev_id] = summary

        # Reboot logic
        for port in list(failovers):
            now = datetime.now()
            if reboot_timer:
                if (time.time() - failovers[port]) >= int(reboot_timer) * 60:
                    cp.log(f'Reboot timer expired ({reboot_timer} min). Resetting sim2 on port {port}.')
                    for dev_id, dev in mdms.items():
                        if dev.get('info', {}).get('port') == port and dev.get('info', {}).get('sim') == 'sim2':
                            cp.put(f'control/wan/devices/{dev_id}/reset', None)
                            cp.log(f'Reset {dev_id}')
                    del failovers[port]
            elif now.hour == reboot_hour and now.minute < 5:
                cp.log(f'Scheduled modem reset at {now.strftime("%H:%M")} for port {port}')
                for dev_id, dev in mdms.items():
                    if dev.get('info', {}).get('port') == port and dev.get('info', {}).get('sim') == 'sim2':
                        cp.put(f'control/wan/devices/{dev_id}/reset', None)
                        cp.log(f'Reset {dev_id}')
                del failovers[port]

        time.sleep(3)

    except Exception as e:
        cp.log(f'Error: {e}')
        time.sleep(3)
