"""Cellular network survey via modem AT commands.

Runs an AT network survey (AT#CSURV) over the router's AT passthrough channel,
reached through the NCOS CLI 'atterm' command driven over the csterm control
tree. Parses the labeled survey output into a list of detected cells and groups
them by carrier (PLMN = MCC + MNC) using a bundled worldwide PLMN table.

The survey is long-running (often 10-30s). It is driven incrementally: a line
is written to control/csterm/<id> and the accumulated output is read back on
each poll, exactly like csterm.CSTerm but tailored so a background thread can
report progress and detect completion.
"""

import json
import os
import re
import threading
import time

import cp

# Strip ANSI / terminal escape sequences from CLI output.
_ANSI_RE = re.compile(
    r'(?:\x1B[@-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[@-~])'
)

# Absolute cap on how long we will drive a single survey (seconds). The
# compact survey output arrives as one burst whose timing is not predictable
# from the modem's RAT/camp -- the same modem on 5G SA has been observed
# finishing in ~8s and in ~185s on different runs. So we use one generous cap
# for every case rather than trying to guess a shorter one.
_SURVEY_TIMEOUT = 300
# Poll interval between reads of the csterm buffer (seconds).
_POLL_INTERVAL = 0.4

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PLMN_PATH = os.path.join(_SCRIPT_DIR, 'plmn_table.json')

_plmn_table = None

# Downlink EARFCN -> E-UTRA band, from 3GPP TS 36.101 Table 5.7.3-1. The
# AT#CSURVC LTE row carries only the EARFCN (no band number), so the band is
# derived from which range the EARFCN falls in. Each entry is
# (band, dl_earfcn_low, dl_earfcn_high) inclusive. Covers the FDD and TDD
# bands in common use; an EARFCN outside every range yields no band.
_LTE_DL_EARFCN_RANGES = (
    (1, 0, 599),
    (2, 600, 1199),
    (3, 1200, 1949),
    (4, 1950, 2399),
    (5, 2400, 2649),
    (7, 2750, 3449),
    (8, 3450, 3799),
    (12, 5010, 5179),
    (13, 5180, 5279),
    (14, 5280, 5379),
    (17, 5730, 5849),
    (18, 5850, 5999),
    (19, 6000, 6149),
    (20, 6150, 6449),
    (21, 6450, 6599),
    (25, 8040, 8689),
    (26, 8690, 9039),
    (28, 9210, 9659),
    (29, 9660, 9769),   # DL-only
    (30, 9770, 9869),
    (32, 9920, 10359),  # DL-only
    (34, 36200, 36349),
    (38, 37750, 38249),
    (39, 38250, 38649),
    (40, 38650, 39649),
    (41, 39650, 41589),
    (42, 41590, 43589),
    (43, 43590, 45589),
    (46, 46790, 54539),
    (48, 55240, 56739),
    (66, 66436, 67335),
    (71, 68586, 68935),
)


def lte_band_from_earfcn(earfcn):
    """Derive the E-UTRA band number from a downlink EARFCN.

    The LTE survey row has no band field, only the EARFCN, so the band is
    looked up from the 3GPP downlink EARFCN ranges.

    Args:
        earfcn: EARFCN as a string or int.

    Returns:
        str: The band number as a string (e.g. '66'), or '' if the EARFCN is
            empty or does not fall in a known range.
    """
    try:
        ch = int(earfcn)
    except (TypeError, ValueError):
        return ''
    for band, low, high in _LTE_DL_EARFCN_RANGES:
        if low <= ch <= high:
            return str(band)
    return ''


def _clean(text):
    """Remove ANSI escape sequences from CLI output."""
    if not text:
        return ''
    return _ANSI_RE.sub('', text)


def load_plmn_table():
    """Load the bundled worldwide PLMN table (cached).

    Returns:
        dict: Maps 'MCCMNC' -> {network, country, mcc, mnc}. Empty on failure.
    """
    global _plmn_table
    if _plmn_table is not None:
        return _plmn_table
    try:
        with open(_PLMN_PATH, 'r') as f:
            _plmn_table = json.load(f)
    except Exception as e:
        cp.log('Could not load plmn_table.json: {}'.format(e))
        _plmn_table = {}
    return _plmn_table


def lookup_plmn(mcc, mnc):
    """Resolve an MCC/MNC pair to carrier and country.

    The modem may report the MNC with or without a leading zero, so we try the
    reported form first then common zero-padded variants.

    Args:
        mcc: Mobile Country Code as a string.
        mnc: Mobile Network Code as a string.

    Returns:
        dict: {network, country, plmn, mcc, mnc}. network/country may be
            'Unknown' when the pair is not in the table.
    """
    table = load_plmn_table()
    mcc = str(mcc).strip()
    mnc = str(mnc).strip()
    candidates = [mnc]
    # Try 2- and 3-digit zero-padded forms, and a stripped form.
    if len(mnc) < 3:
        candidates.append(mnc.zfill(2))
        candidates.append(mnc.zfill(3))
    candidates.append(mnc.lstrip('0') or '0')
    seen = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        entry = table.get(mcc + cand)
        if entry:
            return {
                'network': entry.get('network', 'Unknown'),
                'country': entry.get('country', 'Unknown'),
                'plmn': mcc + mnc,
                'mcc': mcc,
                'mnc': mnc,
            }
    return {
        'network': 'Unknown',
        'country': 'Unknown',
        'plmn': mcc + mnc,
        'mcc': mcc,
        'mnc': mnc,
    }


def _cell(rat, channel, mcc, mnc, cell_id, tac, pci, band, bandwidth,
          rsrp, rsrq):
    """Build a normalized cell dict with PLMN resolved.

    band and bandwidth are distinct: 'band' is the NR band number (5G only;
    AT#CSURVC does not report a band number for LTE rows, only the EARFCN), and
    'bandwidth' is the LTE E-UTRA channel bandwidth in MHz (LTE only). Each is
    '' when the RAT does not provide it.
    """
    info = lookup_plmn(mcc, mnc) if mcc and mnc else {
        'network': 'Unknown', 'country': 'Unknown',
        'plmn': '', 'mcc': mcc, 'mnc': mnc,
    }
    try:
        signal = int(rsrp)
    except (TypeError, ValueError):
        signal = None
    return {
        'rat': rat,
        'channel': str(channel),
        'mcc': mcc,
        'mnc': mnc,
        'plmn': info['plmn'],
        'network': info['network'],
        'country': info['country'],
        'cell_id': str(cell_id),
        'tac': str(tac),
        'pci': str(pci),
        'band': str(band),
        'bandwidth': str(bandwidth),
        'rsrp': str(rsrp),
        'rsrq': str(rsrq),
        'signal': signal,
    }


def parse_survey(raw):
    """Parse AT#CSURVC (compact) survey output into a list of cell dicts.

    Field layout is from the Telit FE990/FN990 AT reference (#CSURVC). The
    survey emits one comma-separated row per cell. We care about two
    serving-cell shapes, distinguished by the sign of the second field:

      5G NR (11 fields; second field is a non-negative band index):
        nr_arfcn, nr_band, nr_scs, nr_mcc, nr_mnc, cell_id, tac, pci,
        cell_status, rsrp, rsrq
      LTE serving cell (11 fields; second field is a negative rxLev in dBm):
        earfcn, rxLev, mcc, mnc, cell_id, tac, pci, cell_status, rsrp, rsrq,
        bandwidth

    Notes on the fields the UI shows:
      - 5G rows carry an NR band number (nr_band) but no channel bandwidth.
      - LTE rows carry the E-UTRA channel bandwidth in MHz (5/10/15/20) but no
        band NUMBER -- only the EARFCN. So an LTE row's 'band' is left blank
        and its 'bandwidth' is populated; a 5G row is the reverse.
      - The 6-field LTE neighbor shape (earfcn, rxLev, pci, cell_status, rsrp,
        rsrq) carries no MCC/MNC, so its PLMN cannot be decoded; those are
        dropped rather than grouped under 'Unknown'.

    Args:
        raw: Full captured survey text (banner + rows + 'ended'/'OK').

    Returns:
        list: Normalized cell dicts. Cells whose PLMN could not be decoded are
            dropped entirely (not grouped under 'Unknown').
    """
    text = _clean(raw)
    cells = []
    for line in text.splitlines():
        s = line.strip()
        if not s or ',' not in s:
            continue
        parts = [p.strip() for p in s.split(',')]
        # Every data row is all-numeric (allowing a leading '-'); skip banner,
        # prompt, and 'OK' lines.
        if not all(re.fullmatch(r'-?\d+', p) for p in parts):
            continue

        n = len(parts)
        try:
            second = int(parts[1])
        except (ValueError, IndexError):
            continue

        if n >= 11 and second >= 0:
            # 5G NR serving cell: band=nr_band (parts[1]), no bandwidth field.
            cells.append(_cell(
                '5G NR', parts[0], parts[3], parts[4], parts[5],
                parts[6], parts[7], band=parts[1], bandwidth='',
                rsrp=parts[9], rsrq=parts[10]))
        elif n >= 11 and second < 0:
            # LTE serving cell: the output has no band NUMBER, only the EARFCN
            # (parts[0]), so derive the band from it. bandwidth (MHz) is the
            # trailing field (parts[10]).
            cells.append(_cell(
                'LTE', parts[0], parts[2], parts[3], parts[4],
                parts[5], parts[6], band=lte_band_from_earfcn(parts[0]),
                bandwidth=parts[10] if n > 10 else '',
                rsrp=parts[8], rsrq=parts[9]))

    # Drop any cell whose PLMN could not be decoded (empty mcc/mnc).
    return [c for c in cells if c['plmn']]


def group_by_carrier(cells):
    """Group parsed cells by PLMN/carrier, sorted by best signal.

    Returns:
        list: Each item is {plmn, network, country, mcc, mnc, best_signal,
            cell_count, cells}. Groups are sorted strongest signal first;
            unknown-PLMN cells are collected under a single 'Unknown' group.
    """
    groups = {}
    for c in cells:
        key = c['plmn'] or 'unknown'
        if key not in groups:
            groups[key] = {
                'plmn': c['plmn'],
                'network': c['network'],
                'country': c['country'],
                'mcc': c['mcc'],
                'mnc': c['mnc'],
                'cells': [],
            }
        groups[key]['cells'].append(c)

    result = []
    for g in groups.values():
        signals = [c['signal'] for c in g['cells'] if c['signal'] is not None]
        g['best_signal'] = max(signals) if signals else None
        g['cell_count'] = len(g['cells'])
        g['cells'].sort(
            key=lambda c: (c['signal'] is None, -(c['signal'] or -999)))
        result.append(g)

    result.sort(key=lambda g: (g['best_signal'] is None,
                               -(g['best_signal'] or -999)))
    return result


class SurveyRunner:
    """Drives an AT survey on a modem in a background thread.

    State is exposed through snapshot() for the web UI to poll.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._thread = None
        self.state = 'idle'          # idle | running | done | error
        self.message = ''
        self.subiface = None
        self.uid = None
        self.mfg_model = ''
        self.started_at = None
        self.finished_at = None
        self.raw = ''
        self.groups = []
        self.cell_count = 0

    def is_running(self):
        with self._lock:
            return self.state == 'running'

    def snapshot(self):
        with self._lock:
            return {
                'state': self.state,
                'message': self.message,
                'subiface': self.subiface,
                'started_at': self.started_at,
                'finished_at': self.finished_at,
                'cell_count': self.cell_count,
                'groups': self.groups,
            }

    def start(self, subiface, uid=None, mfg_model=''):
        """Begin a survey on the given modem SubIface (e.g. 'rmnet501').

        Args:
            subiface: Modem AT interface (e.g. 'rmnet501').
            uid: Modem WAN device uid (e.g. 'mdm-5a3e6e08').
            mfg_model: Modem manufacturer model (e.g. 'FE990B40-NAD'), recorded
                for diagnostics.
        """
        with self._lock:
            if self.state == 'running':
                return False
            self.state = 'running'
            self.message = 'Starting survey...'
            self.subiface = subiface
            self.uid = uid
            self.mfg_model = mfg_model or ''
            self.started_at = time.time()
            self.finished_at = None
            self.raw = ''
            self.groups = []
            self.cell_count = 0
        cp.log('cell_survey: starting survey on modem {}'.format(subiface))
        self._thread = threading.Thread(
            target=self._run, args=(subiface,), daemon=True)
        self._thread.start()
        return True

    def _set(self, **kwargs):
        with self._lock:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def _run(self, subiface):
        sid = 'cellsurvey-%d' % int(time.time())
        path = 'control/csterm/%s' % sid
        try:
            # Open the CLI session.
            cp.put(path, {'k': '\n', 'u': 'admin'})
            time.sleep(0.5)
            cp.get(path)

            # Enter the modem's AT passthrough channel.
            cp.put(path, {'k': 'atterm %s\n' % subiface, 'u': 'admin'})
            connected = False
            buf = ''
            deadline = time.time() + 10
            while time.time() < deadline:
                time.sleep(_POLL_INTERVAL)
                resp = cp.get(path)
                buf += _clean(_chunk(resp))
                if 'ctrl-d to exit' in buf:
                    connected = True
                    break
                if 'No Modem Interface Found' in buf:
                    self._fail('No modem found at {}'.format(subiface))
                    return
                cp.put(path, {'k': '', 'u': 'admin'})

            if not connected:
                self._fail('Could not open AT channel on {}'.format(subiface))
                self._exit_term(path)
                return

            # Scan time is not predictable from the camp, so use a neutral
            # message and a count-up timer rather than an estimate.
            self._set(message='This may take a while...')
            cp.log('cell_survey: running AT#CSURVC on {}'.format(subiface))

            # Fire the compact survey and pump output until it ends or times
            # out. AT#CSURVC streams one comma-separated row per cell.
            cp.put(path, {'k': 'AT#CSURVC\n', 'u': 'admin'})
            survey = ''
            start = time.time()
            started = False
            while True:
                time.sleep(_POLL_INTERVAL)
                chunk = _clean(_chunk(cp.get(path)))
                if chunk:
                    survey += chunk
                low = survey.lower()
                if 'survey started' in low:
                    started = True
                rows = _count_rows(survey)
                now = time.time()
                # Count-up timer runs from the moment the command was fired,
                # not from when 'survey started' is parsed. On 5G SA the whole
                # response (banner included) can arrive in one burst at the
                # end, so gating the timer on `started` froze it for the entire
                # scan. `started` only gates completion detection below.
                elapsed_5s = int((now - start) // 5 * 5)
                self._set(message='This may take a while... '
                                  '{}s'.format(elapsed_5s))

                # Only treat 'ended'/'OK' as done once the survey has actually
                # started, so a stray prompt/OK from opening the channel can't
                # end capture before any rows arrive.
                done = started and ('survey ended' in low
                                    or re.search(r'(?m)^\s*OK\s*$', survey))
                if done:
                    # One more pump to flush any trailing rows + OK.
                    cp.put(path, {'k': '', 'u': 'admin'})
                    time.sleep(_POLL_INTERVAL)
                    survey += _clean(_chunk(cp.get(path)))
                    break

                if now - start > _SURVEY_TIMEOUT:
                    self._set(message='Survey timed out; parsing partial data.')
                    cp.log('cell_survey: survey timed out after {}s (rows '
                           'seen: {})'.format(_SURVEY_TIMEOUT, rows))
                    break
                cp.put(path, {'k': '', 'u': 'admin'})

            self._exit_term(path)

            cells = parse_survey(survey)
            groups = group_by_carrier(cells)
            elapsed = time.time() - start
            with self._lock:
                self.raw = survey
                self.groups = groups
                self.cell_count = len(cells)
                self.state = 'done'
                self.finished_at = time.time()
                if cells:
                    self.message = ('Survey complete in {:.0f} seconds: {} '
                                    'cells across {} carriers.'.format(
                                        elapsed, len(cells), len(groups)))
                else:
                    self.message = ('Survey complete in {:.0f} seconds but no '
                                    'cells were parsed.'.format(elapsed))
            if cells:
                carriers = ', '.join(
                    '{} ({})'.format(g['network'], g['cell_count'])
                    for g in groups)
                cp.log('cell_survey: survey complete in {:.0f}s - {} cells '
                       'across {} carriers: {}'.format(
                           elapsed, len(cells), len(groups), carriers))
            else:
                # Log a short raw snippet so a parse miss can be diagnosed.
                snippet = survey.strip().replace('\r', '')[-300:]
                cp.log('cell_survey: no cells parsed in {:.0f}s. Tail: {}'
                       .format(elapsed, snippet))
        except Exception as e:
            cp.log('cell_survey: survey error: {}'.format(e))
            self._fail('Survey error: {}'.format(e))

    def _exit_term(self, path):
        """Leave the AT channel and CLI session cleanly."""
        try:
            cp.put(path, {'k': '\x04', 'u': 'admin'})  # ctrl-d exits atterm
            time.sleep(0.3)
            cp.get(path)
            cp.put(path, {'k': 'exit\n', 'u': 'admin'})
            time.sleep(0.2)
            cp.get(path)
        except Exception:
            pass

    def _fail(self, msg):
        with self._lock:
            self.state = 'error'
            self.message = msg
            self.finished_at = time.time()
        cp.log(msg)


def _chunk(resp):
    """Extract the 'k' text field from a csterm get() response.

    On-router cp.get() returns the dict directly; be defensive about shape.
    """
    if isinstance(resp, dict):
        return resp.get('k', '') or ''
    return ''


def _count_rows(text):
    """Count comma-separated survey data rows seen so far (for live progress)."""
    n = 0
    for line in text.splitlines():
        s = line.strip()
        if ',' in s and re.fullmatch(r'(-?\d+)(,-?\d+)+', s):
            n += 1
    return n
