"""IMEI_ICCID_asset_id - write internal modem IMEI and SIM info into asset_id.

Builds a string like:
    IMEI: 357926100739635 | SIM1: Verizon 89148000010933156465 | SIM2: T-Mobile 8901...

and writes it to config/system/asset_id, which surfaces as the Asset ID field in
NetCloud Manager. Only writes when the value actually changes.
"""

import time

import cp

APP_NAME = 'IMEI_ICCID_asset_id'

# Physical port of the internal modem. Both SIM slots of the internal modem
# appear as separate mdm-* devices sharing this port.
INTERNAL_MODEM_PORT = 'int1'

# Defaults used when the matching appdata field is missing or empty.
# Never write these back to appdata - that would override NCM group config.
DEFAULT_POLL_INTERVAL = 300
MIN_POLL_INTERVAL = 30

# Used while the modem has not reported IMEI/SIM data yet (e.g. right after boot).
RETRY_INTERVAL = 15


def get_appdata_int(field, default, minimum):
    """Read an integer appdata field, falling back to a code default."""
    try:
        value = cp.get_appdata(field)
        if value is None or str(value).strip() == '':
            return default
        parsed = int(str(value).strip())
        if parsed < minimum:
            cp.log(f'{field}={parsed} below minimum, using {minimum}')
            return minimum
        return parsed
    except Exception as e:
        cp.log(f'Error reading appdata {field}: {e}')
        return default


def slot_number(diag, info):
    """Return the SIM slot number as a string, or None if unknown."""
    slot = str(diag.get('SIM_SLOT_ID') or diag.get('SIM_NUM') or '').strip()
    if slot:
        return slot
    # info['sim'] looks like 'sim1' / 'sim2'
    sim = str(info.get('sim') or '').strip().lower()
    if sim.startswith('sim') and sim[3:].isdigit():
        return sim[3:]
    return None


def collect_modem_info():
    """Collect IMEI and per-slot SIM details from the internal modem.

    Returns:
        Tuple of (imei, slots) where imei is a string or None, and slots is a
        list of (slot_number_int, carrier, iccid) tuples for SIMs present.
    """
    imei = None
    slots = []

    try:
        devices = cp.get('status/wan/devices') or {}
    except Exception as e:
        cp.log(f'Error getting WAN devices: {e}')
        return None, []

    for dev_id in sorted(devices):
        if not dev_id.startswith('mdm-'):
            continue

        try:
            info = cp.get(f'status/wan/devices/{dev_id}/info') or {}
        except Exception as e:
            cp.log(f'Error getting info for {dev_id}: {e}')
            continue

        if info.get('port') != INTERNAL_MODEM_PORT:
            continue

        try:
            diag = cp.get(f'status/wan/devices/{dev_id}/diagnostics') or {}
        except Exception as e:
            cp.log(f'Error getting diagnostics for {dev_id}: {e}')
            diag = {}

        if imei is None:
            # DISP_IMEI is the modem IMEI; info['serial'] reports the same value.
            imei = str(diag.get('DISP_IMEI') or info.get('serial') or '').strip()
            if imei in ('', 'unset'):
                imei = None

        slot = slot_number(diag, info)
        if slot is None:
            continue

        # No SIM in this slot - nothing to report.
        if str(diag.get('NOSIM') or '').upper() == 'TRUE':
            continue

        iccid = str(diag.get('ICCID') or '').strip()
        if not iccid:
            continue

        carrier = str(diag.get('CARRID') or diag.get('HOMECARRID')
                      or info.get('carrier_id') or '').strip()

        slots.append((int(slot) if slot.isdigit() else slot, carrier, iccid))

    slots.sort(key=lambda item: str(item[0]))
    return imei, slots


def build_asset_id(imei, slots):
    """Format the asset_id string. Returns None if there is nothing to write."""
    parts = []
    if imei:
        parts.append(f'IMEI: {imei}')
    for slot, carrier, iccid in slots:
        label = f'SIM{slot}: '
        label += f'{carrier} {iccid}' if carrier else iccid
        parts.append(label)
    if not parts:
        return None
    return ' | '.join(parts)


def main():
    cp.log(f'Starting {APP_NAME}...')
    poll_interval = get_appdata_int(f'{APP_NAME}.poll_interval',
                                    DEFAULT_POLL_INTERVAL, MIN_POLL_INTERVAL)
    cp.log(f'Poll interval: {poll_interval}s')

    last_written = None

    while True:
        sleep_for = poll_interval
        try:
            imei, slots = collect_modem_info()
            asset_id = build_asset_id(imei, slots)

            if not asset_id:
                # Modem may still be initializing after boot - retry sooner.
                cp.log('No internal modem IMEI or SIM data available yet.')
                sleep_for = min(RETRY_INTERVAL, poll_interval)
            elif asset_id == last_written:
                pass  # No change - avoid needless config writes.
            else:
                current = cp.get('config/system/asset_id')
                if current == asset_id:
                    last_written = asset_id
                    cp.log(f'asset_id already correct: {asset_id}')
                else:
                    result = cp.put('config/system/asset_id', asset_id)
                    if result is None:
                        cp.log(f'Failed to write asset_id: {asset_id}')
                    else:
                        last_written = asset_id
                        cp.log(f'asset_id set to: {asset_id}')
        except Exception as e:
            cp.log(f'Error in main loop: {e}')

        time.sleep(sleep_for)


if __name__ == '__main__':
    main()
