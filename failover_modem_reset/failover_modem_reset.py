import cp
import time
from datetime import datetime

cp.log('Starting Failover Modem Reset...')

def load_config():
    """Load reboot_hour and reboot_timer from appdata."""
    timer = cp.get_appdata('reboot_timer') or ''
    hour = cp.get_appdata('reboot_hour') or ''
    if timer:
        return int(hour or '2'), timer
    return int(hour or '2'), timer


reboot_hour, reboot_timer = load_config()
if reboot_timer:
    cp.log(f'Config: reboot_timer={reboot_timer} min')
else:
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
                        carrier = info.get('carrier', 'unknown')
                        diag = dev.get('diagnostics', {})
                        signal_str = diag.get('RSRP', diag.get('RSSI', 'N/A'))
                        alert_msg = (
                            f'FAILOVER DETECTED: sim2 connected on port {port} '
                            f'(dev={dev_id}, carrier={carrier}, signal={signal_str})'
                        )
                        cp.log(alert_msg)
                        cp.alert(alert_msg)
                        failovers[port] = time.time()
            last_summaries[dev_id] = summary

        # Reload config from appdata each cycle
        reboot_hour, reboot_timer = load_config()

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
