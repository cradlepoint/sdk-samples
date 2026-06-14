"""signal_alert - Monitor modem signal metrics and send NetCloud alert with GPS when below thresholds.

Appdata (SDK app settings):
  signal_metrics - Comma-separated metric names, default "RSRP,RSRQ". Only these are monitored.
  For each metric, appdata field of the same name (e.g. RSRP) is the threshold. If missing, that metric is not monitored.

Checks all connected modems. Sends one below alert per metric when it crosses below; sends one recovery alert per metric when it recovers (above threshold for 60s).
"""

import cp
import time

stable_threshold = 60.0  # seconds before considering "recovered"
modems = {}  # uid -> {'below': set of metric names, 'stabletime': {metric: timestamp}}
DEFAULT_SIGNAL_METRICS = 'RSRP,RSRQ'
DEFAULT_THRESHOLDS = {'RSRP': -111, 'RSRQ': -12}


def get_monitored_metrics():
    """Build dict of metric_name -> threshold from appdata. RSRP/RSRQ use defaults -111/-12 if not set."""
    raw = (cp.get_appdata('signal_metrics') or DEFAULT_SIGNAL_METRICS).strip()
    names = [s.strip() for s in raw.split(',') if s.strip()]
    monitored = {}
    for name in names:
        thr_val = cp.get_appdata(name)
        if thr_val is None or str(thr_val).strip() == '':
            if name in DEFAULT_THRESHOLDS:
                monitored[name] = DEFAULT_THRESHOLDS[name]
            else:
                cp.log('No threshold for %s, skipping' % name)
            continue
        try:
            monitored[name] = int(thr_val)
        except (TypeError, ValueError):
            cp.log('Invalid threshold for %s (%s), skipping' % (name, thr_val))
    return monitored


def find_modems(metric_names):
    """Update modems dict with connected modem UIDs that have any of the given diagnostics."""
    global modems
    if not metric_names:
        return
    wan_devs = cp.get('status/wan/devices')
    if not wan_devs:
        return
    new_modems = {}
    for dev_uid, dev_status in wan_devs.items():
        if 'mdm-' not in dev_uid:
            continue
        diag = dev_status.get('diagnostics') or {}
        if any(m in diag for m in metric_names):
            if dev_uid in modems:
                new_modems[dev_uid] = modems[dev_uid]
            else:
                new_modems[dev_uid] = {'below': set(), 'stabletime': {}}
    if set(new_modems.keys()) != set(modems.keys()):
        cp.log('Found modems: %s' % list(new_modems.keys()))
    modems.clear()
    modems.update(new_modems)


def main_loop(monitored_metrics):
    """monitored_metrics: dict of metric_name -> threshold (int)."""
    if not monitored_metrics:
        return
    lat, long_val = cp.get_lat_long()
    loc = ''
    if lat is not None and long_val is not None:
        loc = ' Lat/long: %.5f, %.5f' % (lat, long_val)

    for uid, state in list(modems.items()):
        diag = cp.get('status/wan/devices/%s/diagnostics' % uid)
        if not diag:
            continue
        carrier = diag.get('CARRID') or 'Modem'
        now = time.time()

        for metric, thr in monitored_metrics.items():
            val = diag.get(metric)
            if val is None:
                continue
            try:
                v = int(val)
            except (TypeError, ValueError):
                continue
            is_below = v < thr

            if metric in state['below']:
                if is_below:
                    modems[uid]['stabletime'].pop(metric, None)
                else:
                    if metric not in state['stabletime']:
                        modems[uid]['stabletime'][metric] = now
                        cp.log('%s %s %s recovered above threshold; monitoring for %.0fs' % (uid, carrier, metric, stable_threshold))
                    elif now - state['stabletime'][metric] > stable_threshold:
                        msg = '%s %s recovered: %s (above threshold of %s).%s' % (carrier, metric, v, thr, loc)
                        cp.log(msg)
                        cp.alert(msg)
                        modems[uid]['below'].discard(metric)
                        modems[uid]['stabletime'].pop(metric, None)
            else:
                if is_below:
                    modems[uid]['below'].add(metric)
                    msg = '%s %s %s is below threshold of %s.%s' % (carrier, metric, v, thr, loc)
                    cp.log(msg)
                    cp.alert(msg)


if __name__ == '__main__':
    cp.log('Starting...')
    cp.wait_for_wan_connection()
    prev_monitored = None
    while True:
        monitored = get_monitored_metrics()
        if prev_monitored is not None and monitored != prev_monitored:
            cp.log('Metrics/thresholds changed: %s' % monitored)
        prev_monitored = monitored
        find_modems(monitored.keys() if monitored else [])
        main_loop(monitored)
        time.sleep(1)
