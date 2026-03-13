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
failover_time = None
failover_port = None
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
                    cp.log(f'Primary already on sim2 ({dev_id}) - starting reboot timer')
                    failover_time = time.time()
                    failover_port = port
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
                # Detect sim2 connecting after sim1 was connected
                if sim == 'sim2' and summary == 'connected' and not failover_time:
                    port = info.get('port', '')
                    # Check if sim1 on same port was previously connected
                    for other_id, other_dev in mdms.items():
                        other_info = other_dev.get('info', {})
                        if other_info.get('sim') == 'sim1' and other_info.get('port') == port:
                            cp.log(f'FAILOVER DETECTED: sim2 connected on port {port} ({dev_id}). Starting reboot timer.')
                            failover_time = time.time()
                            failover_port = port
                            break
            last_summaries[dev_id] = summary

        # Reboot logic
        if failover_time:
            now = datetime.now()
            if reboot_timer:
                if (time.time() - failover_time) >= int(reboot_timer) * 60:
                    cp.log(f'Reboot timer expired ({reboot_timer} min). Resetting modem on port {failover_port}.')
                    for dev_id, dev in mdms.items():
                        if dev.get('info', {}).get('port') == failover_port and dev.get('info', {}).get('sim') == 'sim2':
                            cp.put(f'control/wan/devices/{dev_id}/reset', None)
                            cp.log(f'Reset {dev_id}')
                    failover_time = None
                    failover_port = None
            elif now.hour == reboot_hour and now.minute < 5:
                cp.log(f'Scheduled modem reboot at {now.strftime("%H:%M")}')
                for dev_id, dev in mdms.items():
                    if dev.get('info', {}).get('port') == failover_port and dev.get('info', {}).get('sim') == 'sim2':
                        cp.put(f'control/wan/devices/{dev_id}/reset', None)
                        cp.log(f'Reset {dev_id}')
                failover_time = None
                failover_port = None

        time.sleep(3)

    except Exception as e:
        cp.log(f'Error: {e}')
        time.sleep(3)
