#!/usr/bin/env python3
"""rtk_compare - compare pre-correction and RTK-corrected GNSS positions.

Every sample interval (default 1 second) the app records two positions:

  * PRE-CORRECTION  - the raw modem GNSS solution from
                      status/gps/devices/{mdm_uid}/nmea (GGA quality 1,
                      no RTCM corrections applied).
  * POST-CORRECTION - the RTK engine solution from
                      status/rtk/gnss/fix_sentence (GGA quality 2/4/5,
                      NTRIP RTCM corrections applied).

Both positions, the offset between them, accuracy estimates and NTRIP /
RTCM link health are appended to a CSV file and exposed through a small
web UI that plots the two tracks on a map.

Requires a router with RTK support (R2400 and similar). status/rtk and
config/system/rtk are null on models without it.
"""

import http.server
import json
import math
import os
import socket
import socketserver
import sys
import threading
import time
from collections import deque

try:
    import configparser
except ImportError:  # pragma: no cover - cppython always has configparser
    import ConfigParser as configparser

import cp

ON_ROUTER = os.path.exists('/var/tmp/cs.sock')

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_STATIC_DIR = os.path.join(_SCRIPT_DIR, 'static')

APP_NAME = 'rtk_compare'

# --- defaults (overridable via appdata, never written back to appdata) ---
DEFAULT_PORT = 8000
DEFAULT_INTERVAL = 1.0
DEFAULT_MAX_POINTS = 7200

MIN_INTERVAL = 0.5
MAX_INTERVAL = 60.0

# Recordings live in a subdirectory so that buildignore can exclude them by
# directory name: the filenames vary by hostname and date, and make.py's
# buildignore matches exact basenames only (no globs). Packaging a file the
# app appends to would make the router delete the app on a signature check.
DATA_DIR = 'data'
CSV_PREFIX = 'RTK Compare'
CSV_DATE_FORMAT = '%m-%d-%Y'

ERROR_LOG_REPEAT_SECONDS = 60

DEVICE_RESCAN_SECONDS = 30
MEMORY_CHECK_SECONDS = 60
MEM_SHED_PERCENT = 20.0
MEM_EXIT_PERCENT = 10.0

# NMEA GGA fix quality (field 6) -> (label, colour, typical accuracy).
# Colours run worst-to-best: red (1) -> orange (2) -> yellow (5) -> green (4).
# The router's own fix_quality string is reported separately rather than used
# as the label, so the pre and post columns stay directly comparable.
# Qualities 3 (PPS), 7 (Manual) and 8 (Simulation) are intentionally absent:
# PPS is for military/authorised users, and Manual and Simulation are only
# produced by hand-entered or synthetic positions. None occur on these
# routers. An unlisted code still records fine, it just falls back to the
# neutral "Unknown" label and colour.
# Quality 0 (Invalid) is also absent: it means there is no fix, so the GGA
# carries no latitude or longitude and the sample is dropped before it could
# ever be plotted.
QUALITY_INFO = {
    1: ('GPS (SPS)', '#dc2626', '2-5 m'),
    2: ('DGPS', '#f97316', '0.5-2 m'),
    4: ('RTK Fixed', '#22c55e', '1-3 cm'),
    5: ('RTK Float', '#eab308', '10-30 cm'),
    6: ('Dead Reckoning', '#2563eb', 'varies'),
}
UNKNOWN_QUALITY = ('Unknown', '#64748b', 'unknown')

# Legend display order: worst fix on the left, best on the right, so the
# progression reads GPS -> DGPS -> RTK Float -> RTK Fixed with RTK Fixed at
# the right-hand end. Note 5 precedes 4: RTK Float is the LOWER quality
# despite the higher code. Dead reckoning is an estimated position rather than
# a point on that ladder, so it leads rather than displacing RTK Fixed.
QUALITY_DISPLAY_ORDER = (6, 1, 2, 5, 4)

# RTK Float means the carrier-phase ambiguities are not fully resolved yet and
# the solution is still converging toward Fixed.
CONVERGING_QUALITY = 5
BEST_QUALITY = 4

# GSA fix mode (field 2).
FIX_MODE_INFO = {
    1: 'No fix',
    2: '2D',
    3: '3D',
}

# Single colour used for every pre-correction point and its track.
PRE_COLOR = '#94a3b8'

MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.ttf': 'font/ttf',
    '.json': 'application/json',
}

CSV_HEADER = [
    'seq',
    'timestamp_local',
    'timestamp_epoch',
    'utc_offset',
    'pre_lat',
    'pre_lon',
    'pre_alt_m',
    'pre_quality',
    'pre_quality_label',
    'pre_satellites',
    'pre_fix_mode',
    'pre_fix_mode_label',
    'pre_hdop',
    'pre_vdop',
    'pre_pdop',
    'post_lat',
    'post_lon',
    'post_alt_m',
    'post_quality',
    'post_quality_label',
    'post_satellites',
    'post_fix_mode',
    'post_fix_mode_label',
    'post_hdop',
    'post_vdop',
    'post_pdop',
    'delta_horizontal_m',
    'delta_vertical_m',
    'delta_east_m',
    'delta_north_m',
    'delta_bearing_deg',
    'delta_3d_m',
    'rtk_fix_quality',
    'rtk_diff_age_s',
    'rtk_ref_station_id',
    'rtk_correction_state',
    'rtk_correction_uptime_s',
    'rtk_correction_age_s',
    'rtk_frames_total',
    'rtk_frames_dropped',
    'rtk_frames_queued',
    'rtk_bytes_received',
    'rtk_crc_failures',
    'rtk_gga_send_failures',
    'rtk_mqtt_connected',
    'horizontal_accuracy_m',
    'vertical_accuracy_m',
    'speed_accuracy_m_s',
    'reported_accuracy_m',
    'speed_kph',
    'heading_deg',
    'post_quality_held_s',
]

# Compact history tuple layout shared with the web UI.
H_SEQ = 0
H_TS = 1
H_PRE_LAT = 2
H_PRE_LON = 3
H_PRE_ALT = 4
H_PRE_Q = 5
H_POST_LAT = 6
H_POST_LON = 7
H_POST_ALT = 8
H_POST_Q = 9
H_DH = 10
H_DV = 11
H_HACC = 12


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def quality_label(quality, router_label=None):
    """Return a human label for a GGA fix quality code.

    The local table wins over the router's fix_quality string so that labels
    stay consistent between the pre and post columns; the router string is
    only used for codes this app does not know about.
    """
    info = QUALITY_INFO.get(quality)
    if info:
        return info[0]
    if router_label:
        return str(router_label).replace('_', ' ')
    return UNKNOWN_QUALITY[0]


def quality_color(quality):
    """Return the plot colour for a GGA fix quality code."""
    info = QUALITY_INFO.get(quality)
    if info:
        return info[1]
    return UNKNOWN_QUALITY[1]


def quality_accuracy(quality):
    """Return the typical accuracy for a GGA fix quality code."""
    info = QUALITY_INFO.get(quality)
    if info:
        return info[2]
    return UNKNOWN_QUALITY[2]


def fix_mode_label(mode):
    """Return a label for a GSA fix mode (1=no fix, 2=2D, 3=3D)."""
    if mode is None:
        return None
    return FIX_MODE_INFO.get(mode, 'Mode {}'.format(mode))


def nmea_checksum_ok(sentence):
    """Validate the trailing *HH XOR checksum of an NMEA sentence."""
    try:
        text = sentence.strip()
        if not text.startswith('$'):
            return False
        star = text.rfind('*')
        if star < 1 or star + 3 > len(text):
            return False
        expected = int(text[star + 1:star + 3], 16)
        actual = 0
        for char in text[1:star]:
            actual ^= ord(char)
        return actual == expected
    except Exception:
        return False


def _to_float(text):
    try:
        if text is None or text == '':
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _to_int(text):
    try:
        if text is None or text == '':
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


def dm_to_degrees(value, hemisphere):
    """Convert NMEA ddmm.mmmm / dddmm.mmmm plus hemisphere to signed degrees."""
    try:
        if not value:
            return None
        dot = value.find('.')
        deg_digits = (dot if dot >= 0 else len(value)) - 2
        if deg_digits < 1:
            return None
        degrees = float(value[:deg_digits])
        minutes = float(value[deg_digits:])
        result = degrees + minutes / 60.0
        if hemisphere in ('S', 'W'):
            result = -result
        return result
    except (TypeError, ValueError):
        return None


def parse_gga(sentence):
    """Parse a GGA sentence into a dict, or return None if unusable."""
    try:
        if not sentence:
            return None
        text = sentence.strip()
        if 'GGA' not in text or not text.startswith('$'):
            return None
        if not nmea_checksum_ok(text):
            return None
        fields = text[1:text.rfind('*')].split(',')
        if len(fields) < 10:
            return None
        lat = dm_to_degrees(fields[2], fields[3])
        lon = dm_to_degrees(fields[4], fields[5])
        if lat is None or lon is None:
            return None
        quality = _to_int(fields[6])
        return {
            'talker': fields[0],
            'utc': fields[1],
            'lat': lat,
            'lon': lon,
            'quality': 0 if quality is None else quality,
            'satellites': _to_int(fields[7]),
            'hdop': _to_float(fields[8]),
            'alt_m': _to_float(fields[9]),
            'geoid_sep_m': _to_float(fields[11]) if len(fields) > 11 else None,
            'diff_age_s': _to_float(fields[13]) if len(fields) > 13 else None,
            'ref_station_id': fields[14] if len(fields) > 14 and fields[14] else None,
            'sentence': text,
        }
    except Exception:
        return None


def parse_gsa(sentence):
    """Parse a GSA sentence for the fix mode and the full DOP set.

    Format: $xxGSA,mode,fix_mode,sv1..sv12,PDOP,HDOP,VDOP,systemId*cs
    GGA only carries HDOP, so GSA is the only source of PDOP and VDOP.
    Receivers emit one GSA per constellation with identical DOP values, so
    the first usable sentence is enough.
    """
    try:
        if not sentence or 'GSA' not in sentence:
            return None
        text = sentence.strip()
        if not text.startswith('$') or not nmea_checksum_ok(text):
            return None
        fields = text[1:text.rfind('*')].split(',')
        if len(fields) < 18:
            return None
        mode = _to_int(fields[2])
        if mode is None:
            return None
        return {
            'fix_mode': mode,
            'fix_mode_label': fix_mode_label(mode),
            'pdop': _to_float(fields[15]),
            'hdop': _to_float(fields[16]),
            'vdop': _to_float(fields[17]),
        }
    except Exception:
        return None


def parse_pcptminr(sentence):
    """Parse the Cradlepoint proprietary $PCPTMINR accuracy sentence.

    Format: $PCPTMINR,uptime,lat,lon,alt,vel_n,vel_e,vel_d,hacc,vacc,sacc,
            hdop,vdop,pdop,fix_type,num_sv*checksum
    Only the accuracy estimates are used; the trailing fix_type / num_sv
    fields are not reliably populated on tested firmware.
    """
    try:
        if not sentence or 'PCPTMINR' not in sentence:
            return None
        text = sentence.strip()
        star = text.rfind('*')
        body = text[1:star] if star > 0 else text[1:]
        fields = body.split(',')
        if len(fields) < 11:
            return None
        return {
            'hacc_m': _to_float(fields[8]),
            'vacc_m': _to_float(fields[9]),
            'sacc_m_s': _to_float(fields[10]),
        }
    except Exception:
        return None


def find_gga(sentences):
    """Return the first parseable GGA from a list of NMEA sentences."""
    if not sentences:
        return None
    if isinstance(sentences, str):
        sentences = [sentences]
    for sentence in sentences:
        parsed = parse_gga(sentence)
        if parsed:
            return parsed
    return None


def find_gsa(sentences):
    """Return fix mode and DOPs from the first usable GSA in a list."""
    if not sentences:
        return None
    if isinstance(sentences, str):
        sentences = [sentences]
    fallback = None
    for sentence in sentences:
        parsed = parse_gsa(sentence)
        if not parsed:
            continue
        if parsed.get('pdop') is not None:
            return parsed
        if fallback is None:
            fallback = parsed
    return fallback


def find_pcptminr(sentences):
    """Return accuracy estimates from the first $PCPTMINR in a list."""
    if not sentences:
        return None
    if isinstance(sentences, str):
        sentences = [sentences]
    for sentence in sentences:
        parsed = parse_pcptminr(sentence)
        if parsed:
            return parsed
    return None


def meters_per_degree(lat_deg):
    """Return (metres per degree latitude, metres per degree longitude)."""
    phi = math.radians(lat_deg)
    m_lat = (111132.92
             - 559.82 * math.cos(2 * phi)
             + 1.175 * math.cos(4 * phi)
             - 0.0023 * math.cos(6 * phi))
    m_lon = (111412.84 * math.cos(phi)
             - 93.5 * math.cos(3 * phi)
             + 0.118 * math.cos(5 * phi))
    return m_lat, m_lon


def enu_offset(lat_ref, lon_ref, lat, lon):
    """Local east/north offset in metres of (lat, lon) from the reference."""
    m_lat, m_lon = meters_per_degree((lat_ref + lat) / 2.0)
    return (lon - lon_ref) * m_lon, (lat - lat_ref) * m_lat


def _round(value, digits):
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def csv_value(value, digits=None):
    """Format one CSV field, escaping only when necessary."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if digits is not None and isinstance(value, (int, float)):
        value = '{:.{p}f}'.format(float(value), p=digits)
    text = str(value)
    if any(ch in text for ch in (',', '"', '\n', '\r')):
        text = '"' + text.replace('"', '""') + '"'
    return text


def sanitize_for_filename(value):
    """Strip characters that are illegal or awkward in a filename."""
    text = str(value or 'router').strip()
    cleaned = []
    for char in text:
        if char.isalnum() or char in ' -_.':
            cleaned.append(char)
        else:
            cleaned.append('_')
    result = ''.join(cleaned).strip(' .')
    return result or 'router'


def csv_filename(router_name, when=None):
    """Build the recording filename: 'RTK Compare - HOST - MM-DD-YYYY.csv'."""
    stamp = time.strftime(CSV_DATE_FORMAT,
                          time.localtime(time.time() if when is None else when))
    return '{} - {} - {}.csv'.format(CSV_PREFIX,
                                     sanitize_for_filename(router_name),
                                     stamp)


def utc_offset_string(timestamp):
    """Return the router-local UTC offset (e.g. -0600) for a timestamp.

    status/system/tz reports both DST variants as "UTC", so the numeric
    offset from %z is the only trustworthy indicator.
    """
    try:
        return time.strftime('%z', time.localtime(timestamp))
    except Exception:
        return ''


# ---------------------------------------------------------------------------
# sampler
# ---------------------------------------------------------------------------

class Sampler(object):
    """Polls GNSS/RTK status, writes CSV rows and keeps a bounded history."""

    def __init__(self, interval, max_points, router_name):
        self.interval = interval
        self.max_points = max_points
        self.router_name = router_name

        self.lock = threading.RLock()
        self.history = deque(maxlen=max_points)
        self.latest = None
        self.rtk_snapshot = {}
        self.generation = 1
        self.seq = 0

        self.data_dir = os.path.join(_SCRIPT_DIR, DATA_DIR)
        self.csv_name = ''
        self.csv_path = ''
        self.csv_bytes = 0
        self.csv_writable = False
        self.rows_written = 0

        self.started_at = time.time()
        self.cleared_at = None
        self.errors = 0
        self.last_error = ''
        self.rtk_supported = None
        self._error_log_times = {}

        self._gps_uid = None
        self._gps_uid_checked = 0.0
        self._last_epoch = None
        self.duplicates_skipped = 0
        self._quality_value = None
        self._quality_since = None
        self._last_memory_check = 0.0
        self._shed = False

        self.open_recording()

    # -- CSV ---------------------------------------------------------------

    def open_recording(self, truncate=False):
        """Select the recording file for today and make it the active one.

        Called when a recording starts (app start, and again on clear) and
        never from the sample loop, so a run that crosses midnight keeps
        writing to the file it started in instead of being interrupted.
        A day that already has a file is continued rather than replaced.
        """
        name = csv_filename(self.router_name)
        path = os.path.join(self.data_dir, name)
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            existed = os.path.isfile(path)
            if existed and not truncate:
                cp.log('Continuing recording {}'.format(name))
            else:
                with open(path, 'w') as handle:
                    handle.write(','.join(CSV_HEADER) + '\n')
                cp.log('{} recording {}'.format(
                    'Reset' if existed else 'Started', name))
            self.csv_name = name
            self.csv_path = path
            self.csv_bytes = os.path.getsize(path)
            self.csv_writable = True
            return True
        except Exception as error:
            self.csv_name = name
            self.csv_path = path
            self.csv_writable = False
            self._record_error('Unable to open recording {}: {}'.format(
                name, error))
            return False

    def _append_csv(self, row):
        """Append one row. There is no size cap; the file grows until cleared."""
        try:
            line = ','.join(row) + '\n'
            with open(self.csv_path, 'a') as handle:
                handle.write(line)
            self.csv_bytes += len(line)
            self.rows_written += 1
            self.csv_writable = True
        except Exception as error:
            self.csv_writable = False
            self._record_error('CSV append failed: {}'.format(error))

    def clear_history(self):
        """Empty the in-memory history and reset today's recording file."""
        with self.lock:
            if not self.open_recording(truncate=True):
                return False
            self.history.clear()
            self.latest = None
            self.rows_written = 0
            self.duplicates_skipped = 0
            self._last_epoch = None
            self.generation += 1
            self.cleared_at = time.time()
            cp.log('Location history cleared')
            return True

    def _record_error(self, message):
        """Count an error and log it, rate-limiting identical repeats.

        The sample loop runs once a second, so an error that persists (a full
        filesystem, say) would otherwise flood the router log.
        """
        self.errors += 1
        self.last_error = message
        now = time.time()
        key = message.split(':')[0]
        last = self._error_log_times.get(key, 0)
        if (now - last) >= ERROR_LOG_REPEAT_SECONDS:
            if len(self._error_log_times) > 32:
                self._error_log_times.clear()
            self._error_log_times[key] = now
            cp.log(message)

    # -- polling -----------------------------------------------------------

    def _gps_device_uid(self):
        """Return the modem UID that publishes raw GNSS NMEA sentences."""
        now = time.time()
        if self._gps_uid and (now - self._gps_uid_checked) < DEVICE_RESCAN_SECONDS:
            return self._gps_uid
        try:
            devices = cp.get('status/gps/devices') or {}
            fallback = None
            chosen = None
            for uid in sorted(devices.keys()):
                entry = devices.get(uid)
                if not isinstance(entry, dict) or not entry:
                    continue
                sentences = entry.get('nmea') or entry.get('current_nmea') or []
                if fallback is None and sentences:
                    fallback = uid
                if find_gga(sentences):
                    chosen = uid
                    break
            self._gps_uid = chosen or fallback
            self._gps_uid_checked = now
        except Exception as error:
            self._record_error('GPS device discovery failed: {}'.format(error))
        return self._gps_uid

    def _raw_device_sentences(self, uid):
        if not uid:
            return []
        try:
            sentences = cp.get('status/gps/devices/{}/nmea'.format(uid))
            if not sentences:
                sentences = cp.get('status/gps/devices/{}/current_nmea'.format(uid))
            return sentences or []
        except Exception as error:
            self._record_error('Raw GNSS read failed: {}'.format(error))
            return []

    def sample(self):
        """Take one sample, append it to the CSV and the history."""
        now = time.time()
        try:
            rtk = cp.get('status/rtk')
        except Exception as error:
            self._record_error('status/rtk read failed: {}'.format(error))
            rtk = None

        if self.rtk_supported is None:
            self.rtk_supported = isinstance(rtk, dict)
            if not self.rtk_supported:
                cp.log('WARNING: status/rtk is not available on this router - '
                       'only pre-correction positions will be recorded')

        rtk = rtk if isinstance(rtk, dict) else {}
        gnss = rtk.get('gnss') or {}
        source = rtk.get('correction_source') or {}
        detail = source.get('detail') or {}
        corrections = rtk.get('corrections') or {}
        mqtt = rtk.get('mqtt') or {}

        try:
            corrected_nmea = cp.get('status/gps/nmea') or []
        except Exception as error:
            self._record_error('status/gps/nmea read failed: {}'.format(error))
            corrected_nmea = []

        try:
            corrected_fix = cp.get('status/gps/fix') or {}
        except Exception as error:
            self._record_error('status/gps/fix read failed: {}'.format(error))
            corrected_fix = {}

        uid = self._gps_device_uid()
        raw_nmea = self._raw_device_sentences(uid)

        pre = find_gga(raw_nmea)
        post = parse_gga(gnss.get('fix_sentence')) or find_gga(corrected_nmea)
        accuracy = find_pcptminr(corrected_nmea) or {}
        pre_gsa = find_gsa(raw_nmea) or {}
        post_gsa = find_gsa(corrected_nmea) or {}

        # Track how long the corrected fix has held its current quality. RTK
        # Float converges to Fixed over roughly 10-60 s, so the dwell time is
        # what tells you whether a Float fix is still settling or stuck.
        post_quality = post.get('quality') if post else None
        if post_quality != self._quality_value:
            self._quality_value = post_quality
            self._quality_since = now
        quality_held = None
        if self._quality_since is not None:
            quality_held = max(0.0, now - self._quality_since)

        delta = self._compute_delta(pre, post)
        sample = self._build_sample(now, uid, pre, post, delta, accuracy,
                                    corrected_fix, rtk, gnss, source, detail,
                                    corrections, mqtt, pre_gsa, post_gsa,
                                    quality_held)

        # Both GNSS solutions update at 1 Hz. Polling on a 1 s timer can drift
        # onto the same GNSS epoch twice, so key each recorded row on the GGA
        # UTC stamps and skip a repeat of the epoch already written.
        epoch = (post.get('utc') if post else None,
                 pre.get('utc') if pre else None)
        fresh = epoch != (None, None) and epoch != self._last_epoch

        with self.lock:
            self.seq += 1
            sample['seq'] = self.seq
            sample['epoch_repeat'] = not fresh
            self.latest = sample
            self.rtk_snapshot = sample['rtk']
            if not fresh:
                self.duplicates_skipped += 1
            if (pre or post) and fresh:
                self._last_epoch = epoch
                self.history.append((
                    self.seq,
                    round(now, 3),
                    _round(pre.get('lat') if pre else None, 8),
                    _round(pre.get('lon') if pre else None, 8),
                    _round(pre.get('alt_m') if pre else None, 3),
                    pre.get('quality') if pre else None,
                    _round(post.get('lat') if post else None, 8),
                    _round(post.get('lon') if post else None, 8),
                    _round(post.get('alt_m') if post else None, 3),
                    post.get('quality') if post else None,
                    _round(delta.get('horizontal_m'), 3),
                    _round(delta.get('vertical_m'), 3),
                    _round(accuracy.get('hacc_m'), 2),
                ))
                self._append_csv(self._csv_row(sample))

        self._check_memory()
        return sample

    def _compute_delta(self, pre, post):
        if not pre or not post:
            return {}
        try:
            east, north = enu_offset(pre['lat'], pre['lon'], post['lat'], post['lon'])
            horizontal = math.hypot(east, north)
            vertical = None
            if pre.get('alt_m') is not None and post.get('alt_m') is not None:
                vertical = post['alt_m'] - pre['alt_m']
            bearing = None
            if horizontal > 0:
                bearing = math.degrees(math.atan2(east, north)) % 360.0
            three_d = horizontal
            if vertical is not None:
                three_d = math.sqrt(horizontal * horizontal + vertical * vertical)
            return {
                'east_m': east,
                'north_m': north,
                'horizontal_m': horizontal,
                'vertical_m': vertical,
                'bearing_deg': bearing,
                'three_d_m': three_d,
            }
        except Exception as error:
            self._record_error('Delta computation failed: {}'.format(error))
            return {}

    def _build_sample(self, now, uid, pre, post, delta, accuracy, corrected_fix,
                      rtk, gnss, source, detail, corrections, mqtt,
                      pre_gsa, post_gsa, quality_held):
        last_frame_at = corrections.get('last_frame_at')
        correction_age = None
        if isinstance(last_frame_at, (int, float)) and last_frame_at > 0:
            correction_age = max(0.0, now - last_frame_at)

        last_gga_at = detail.get('last_gga_at')
        gga_age = None
        if isinstance(last_gga_at, (int, float)) and last_gga_at > 0:
            gga_age = max(0.0, now - last_gga_at)

        speed_knots = corrected_fix.get('ground_speed_knots')
        speed_kph = None
        if isinstance(speed_knots, (int, float)):
            speed_kph = speed_knots * 1.852

        pre_block = None
        if pre:
            pre_block = {
                'lat': _round(pre.get('lat'), 8),
                'lon': _round(pre.get('lon'), 8),
                'alt_m': _round(pre.get('alt_m'), 3),
                'quality': pre.get('quality'),
                'quality_label': quality_label(pre.get('quality')),
                'quality_accuracy': quality_accuracy(pre.get('quality')),
                'satellites': pre.get('satellites'),
                'hdop': pre.get('hdop'),
                'vdop': pre_gsa.get('vdop'),
                'pdop': pre_gsa.get('pdop'),
                'fix_mode': pre_gsa.get('fix_mode'),
                'fix_mode_label': pre_gsa.get('fix_mode_label'),
                'geoid_sep_m': pre.get('geoid_sep_m'),
                'utc': pre.get('utc'),
                'source': 'status/gps/devices/{}/nmea'.format(uid) if uid else None,
                'sentence': pre.get('sentence'),
            }

        post_block = None
        if post:
            post_block = {
                'lat': _round(post.get('lat'), 8),
                'lon': _round(post.get('lon'), 8),
                'alt_m': _round(post.get('alt_m'), 3),
                'quality': post.get('quality'),
                'quality_label': quality_label(post.get('quality'),
                                               gnss.get('fix_quality')),
                'quality_accuracy': quality_accuracy(post.get('quality')),
                'quality_held_s': _round(quality_held, 1),
                'converging': post.get('quality') == CONVERGING_QUALITY,
                'at_best_quality': post.get('quality') == BEST_QUALITY,
                'satellites': post.get('satellites') or gnss.get('satellites'),
                'hdop': post.get('hdop'),
                'vdop': post_gsa.get('vdop'),
                'pdop': post_gsa.get('pdop'),
                'fix_mode': post_gsa.get('fix_mode'),
                'fix_mode_label': post_gsa.get('fix_mode_label'),
                'geoid_sep_m': post.get('geoid_sep_m'),
                'utc': post.get('utc'),
                'diff_age_s': (post.get('diff_age_s')
                               if post.get('diff_age_s') is not None
                               else gnss.get('diff_age_s')),
                'ref_station_id': (post.get('ref_station_id')
                                   or gnss.get('ref_station_id')),
                'source': 'status/rtk/gnss/fix_sentence',
                'sentence': post.get('sentence'),
            }

        return {
            'seq': 0,
            'timestamp': round(now, 3),
            'timestamp_local': time.strftime('%Y-%m-%d %H:%M:%S',
                                             time.localtime(now)),
            'utc_offset': utc_offset_string(now),
            'gps_device': uid,
            'pre': pre_block,
            'post': post_block,
            'delta': {
                'horizontal_m': _round(delta.get('horizontal_m'), 3),
                'vertical_m': _round(delta.get('vertical_m'), 3),
                'east_m': _round(delta.get('east_m'), 3),
                'north_m': _round(delta.get('north_m'), 3),
                'bearing_deg': _round(delta.get('bearing_deg'), 1),
                'three_d_m': _round(delta.get('three_d_m'), 3),
            },
            'accuracy': {
                'horizontal_m': _round(accuracy.get('hacc_m'), 2),
                'vertical_m': _round(accuracy.get('vacc_m'), 2),
                'speed_m_s': _round(accuracy.get('sacc_m_s'), 2),
                'reported_m': _round(corrected_fix.get('accuracy'), 2),
            },
            'motion': {
                'speed_kph': _round(speed_kph, 2),
                'speed_knots': _round(speed_knots, 2),
                'heading_deg': _round(corrected_fix.get('heading'), 1),
            },
            'rtk': {
                'supported': bool(self.rtk_supported),
                'enabled': rtk.get('enabled'),
                'fix_quality': gnss.get('fix_quality'),
                'diff_age_s': _round(gnss.get('diff_age_s'), 2),
                'ref_station_id': gnss.get('ref_station_id'),
                'satellites': gnss.get('satellites'),
                'correction': {
                    'type': source.get('type'),
                    'format': source.get('format'),
                    'state': source.get('state'),
                    'error': source.get('error'),
                    'uptime_s': _round(source.get('uptime_s'), 0),
                    'retry_interval_s': source.get('retry_interval_s'),
                    'host': detail.get('host'),
                    'port': detail.get('port'),
                    'mountpoint': detail.get('mountpoint'),
                    'gga_rate_s': detail.get('gga_rate_s'),
                    'gga_send_failures': detail.get('gga_send_failures'),
                    'last_gga_age_s': _round(gga_age, 1),
                },
                'corrections': {
                    'frames_total': corrections.get('frames_total'),
                    'frames_dropped': corrections.get('frames_dropped'),
                    'frames_queued': corrections.get('frames_queued'),
                    'bytes_received': corrections.get('bytes_received'),
                    'crc_failures': corrections.get('crc_failures'),
                    'age_s': _round(correction_age, 1),
                    'msg_types_seen': corrections.get('msg_types_seen') or [],
                },
                'mqtt': {
                    'connected': mqtt.get('connected'),
                    'publish_failures': mqtt.get('publish_failures'),
                },
            },
        }

    def _csv_row(self, sample):
        pre = sample.get('pre') or {}
        post = sample.get('post') or {}
        delta = sample.get('delta') or {}
        accuracy = sample.get('accuracy') or {}
        motion = sample.get('motion') or {}
        rtk = sample.get('rtk') or {}
        correction = rtk.get('correction') or {}
        corrections = rtk.get('corrections') or {}
        mqtt = rtk.get('mqtt') or {}

        def fixed(value, digits):
            """Avoid scientific notation / lost precision on coordinates."""
            if value is None:
                return None
            return '{:.{p}f}'.format(float(value), p=digits)

        values = [
            sample.get('seq'),
            sample.get('timestamp_local'),
            fixed(sample.get('timestamp'), 3),
            sample.get('utc_offset'),
            fixed(pre.get('lat'), 8),
            fixed(pre.get('lon'), 8),
            pre.get('alt_m'),
            pre.get('quality'),
            pre.get('quality_label'),
            pre.get('satellites'),
            pre.get('fix_mode'),
            pre.get('fix_mode_label'),
            pre.get('hdop'),
            pre.get('vdop'),
            pre.get('pdop'),
            fixed(post.get('lat'), 8),
            fixed(post.get('lon'), 8),
            post.get('alt_m'),
            post.get('quality'),
            post.get('quality_label'),
            post.get('satellites'),
            post.get('fix_mode'),
            post.get('fix_mode_label'),
            post.get('hdop'),
            post.get('vdop'),
            post.get('pdop'),
            delta.get('horizontal_m'),
            delta.get('vertical_m'),
            delta.get('east_m'),
            delta.get('north_m'),
            delta.get('bearing_deg'),
            delta.get('three_d_m'),
            rtk.get('fix_quality'),
            rtk.get('diff_age_s'),
            rtk.get('ref_station_id'),
            correction.get('state'),
            correction.get('uptime_s'),
            corrections.get('age_s'),
            corrections.get('frames_total'),
            corrections.get('frames_dropped'),
            corrections.get('frames_queued'),
            corrections.get('bytes_received'),
            corrections.get('crc_failures'),
            correction.get('gga_send_failures'),
            mqtt.get('connected'),
            accuracy.get('horizontal_m'),
            accuracy.get('vertical_m'),
            accuracy.get('speed_m_s'),
            accuracy.get('reported_m'),
            motion.get('speed_kph'),
            motion.get('heading_deg'),
            post.get('quality_held_s'),
        ]
        if len(values) != len(CSV_HEADER):
            cp.log('WARNING: CSV row width {} != header width {}'.format(
                len(values), len(CSV_HEADER)))
        return [csv_value(value) for value in values]

    # -- memory guard ------------------------------------------------------

    def _check_memory(self):
        """Shed history or restart the app if the router runs low on RAM."""
        now = time.time()
        if (now - self._last_memory_check) < MEMORY_CHECK_SECONDS:
            return
        self._last_memory_check = now
        try:
            memory = cp.get('status/system/memory') or {}
            total = memory.get('memtotal') or 0
            available = memory.get('memavailable') or 0
            if not total:
                return
            percent = available * 100.0 / total
        except Exception:
            return

        if percent <= MEM_EXIT_PERCENT:
            cp.alert('{}: only {:.1f}% memory available - restarting'.format(
                APP_NAME, percent))
            cp.log('Memory critically low ({:.1f}%) - exiting for restart'.format(
                percent))
            sys.exit(0)

        if percent <= MEM_SHED_PERCENT and not self._shed:
            with self.lock:
                reduced = max(600, self.max_points // 2)
                trimmed = deque(self.history, maxlen=reduced)
                self.history = trimmed
                self.max_points = reduced
                self._shed = True
            cp.log('Memory low ({:.1f}%) - history capped at {} samples'.format(
                percent, reduced))
        elif percent > MEM_SHED_PERCENT + 10:
            self._shed = False

    # -- views for the web UI ---------------------------------------------

    def points_since(self, since):
        """Return compact history tuples newer than the given sequence."""
        with self.lock:
            points = [list(row) for row in self.history if row[H_SEQ] > since]
            return {
                'generation': self.generation,
                'since': since,
                'next': self.seq,
                'total': len(self.history),
                'points': points,
            }

    def statistics(self):
        """Derive summary analytics from the in-memory history."""
        with self.lock:
            rows = list(self.history)
            rows_written = self.rows_written
            csv_bytes = self.csv_bytes
            csv_name = self.csv_name
            csv_writable = self.csv_writable
            generation = self.generation
            cleared_at = self.cleared_at
            errors = self.errors
            last_error = self.last_error
            duplicates = self.duplicates_skipped

        stats = {
            'samples': len(rows),
            'rows_written': rows_written,
            'duplicates_skipped': duplicates,
            'csv_bytes': csv_bytes,
            'csv_name': csv_name,
            'csv_writable': csv_writable,
            'generation': generation,
            'cleared_at': cleared_at,
            'uptime_s': int(time.time() - self.started_at),
            'errors': errors,
            'last_error': last_error,
            'interval_s': self.interval,
            'max_points': self.max_points,
            'duration_s': 0,
            'delta': {},
            'post_quality_counts': {},
            'pre_quality_counts': {},
            'post_spread': {},
            'pre_spread': {},
            'fix_percent': {},
        }
        if not rows:
            return stats

        stats['duration_s'] = int(rows[-1][H_TS] - rows[0][H_TS])

        deltas = [row[H_DH] for row in rows if row[H_DH] is not None]
        verticals = [row[H_DV] for row in rows if row[H_DV] is not None]
        if deltas:
            stats['delta'] = {
                'count': len(deltas),
                'min_m': _round(min(deltas), 3),
                'max_m': _round(max(deltas), 3),
                'mean_m': _round(sum(deltas) / len(deltas), 3),
                'last_m': _round(deltas[-1], 3),
            }
        if verticals:
            stats['delta']['vertical_mean_m'] = _round(
                sum(verticals) / len(verticals), 3)
            stats['delta']['vertical_last_m'] = _round(verticals[-1], 3)

        post_counts = {}
        pre_counts = {}
        for row in rows:
            if row[H_POST_Q] is not None:
                key = str(row[H_POST_Q])
                post_counts[key] = post_counts.get(key, 0) + 1
            if row[H_PRE_Q] is not None:
                key = str(row[H_PRE_Q])
                pre_counts[key] = pre_counts.get(key, 0) + 1
        stats['post_quality_counts'] = post_counts
        stats['pre_quality_counts'] = pre_counts

        post_total = sum(post_counts.values())
        if post_total:
            stats['fix_percent'] = {
                'rtk_fixed': _round(post_counts.get('4', 0) * 100.0 / post_total, 1),
                'rtk_float': _round(post_counts.get('5', 0) * 100.0 / post_total, 1),
                'differential': _round(post_counts.get('2', 0) * 100.0 / post_total, 1),
                'autonomous': _round(post_counts.get('1', 0) * 100.0 / post_total, 1),
            }

        stats['post_spread'] = self._spread(
            [(row[H_POST_LAT], row[H_POST_LON], row[H_POST_ALT]) for row in rows])
        stats['pre_spread'] = self._spread(
            [(row[H_PRE_LAT], row[H_PRE_LON], row[H_PRE_ALT]) for row in rows])
        return stats

    @staticmethod
    def _spread(samples):
        """Scatter statistics (precision) about the mean of a position set."""
        points = [(lat, lon, alt) for lat, lon, alt in samples
                  if lat is not None and lon is not None]
        if len(points) < 2:
            return {}
        mean_lat = sum(point[0] for point in points) / len(points)
        mean_lon = sum(point[1] for point in points) / len(points)
        easts = []
        norths = []
        for lat, lon, _alt in points:
            east, north = enu_offset(mean_lat, mean_lon, lat, lon)
            easts.append(east)
            norths.append(north)
        var_e = sum(value * value for value in easts) / len(easts)
        var_n = sum(value * value for value in norths) / len(norths)
        sigma_e = math.sqrt(var_e)
        sigma_n = math.sqrt(var_n)
        radial = [math.hypot(e, n) for e, n in zip(easts, norths)]
        altitudes = [alt for _lat, _lon, alt in points if alt is not None]
        result = {
            'count': len(points),
            'mean_lat': _round(mean_lat, 8),
            'mean_lon': _round(mean_lon, 8),
            'sigma_east_m': _round(sigma_e, 3),
            'sigma_north_m': _round(sigma_n, 3),
            'drms_m': _round(math.sqrt(var_e + var_n), 3),
            'twodrms_m': _round(2 * math.sqrt(var_e + var_n), 3),
            'cep50_m': _round(0.59 * (sigma_e + sigma_n), 3),
            'max_radial_m': _round(max(radial), 3),
        }
        if len(altitudes) >= 2:
            mean_alt = sum(altitudes) / len(altitudes)
            var_alt = sum((alt - mean_alt) ** 2 for alt in altitudes) / len(altitudes)
            result['mean_alt_m'] = _round(mean_alt, 3)
            result['sigma_alt_m'] = _round(math.sqrt(var_alt), 3)
        return result


# ---------------------------------------------------------------------------
# static router / app info
# ---------------------------------------------------------------------------

def read_package_ini():
    """Return (app_name, version) from package.ini."""
    name = APP_NAME
    version = '0.0.0'
    try:
        parser = configparser.ConfigParser()
        parser.read(os.path.join(_SCRIPT_DIR, 'package.ini'))
        for section in parser.sections():
            name = section
            version = '{}.{}.{}'.format(
                parser.get(section, 'version_major', fallback='0'),
                parser.get(section, 'version_minor', fallback='0'),
                parser.get(section, 'version_patch', fallback='0'))
            break
    except Exception:
        pass
    return name, version


def read_help_text():
    for candidate in (os.path.join(_SCRIPT_DIR, 'readme.md'),
                      os.path.join(_SCRIPT_DIR, 'README.md'),
                      '/app/readme.md'):
        try:
            with open(candidate, 'r') as handle:
                return handle.read()
        except (IOError, OSError):
            continue
    return 'Help documentation not available.'


def _safe_get(path):
    try:
        return cp.get(path)
    except Exception:
        return None


def collect_device_info(app_version):
    """Router identity, NCOS version and the configured RTK source."""
    info = {
        'app_name': APP_NAME,
        'app_version': app_version,
        'router_name': 'N/A',
        'router_model': 'N/A',
        'serial_number': 'N/A',
        'mac_address': 'N/A',
        'firmware_version': 'N/A',
        'rtk_config': {},
    }

    name = _safe_get('config/system/system_id')
    if name:
        info['router_name'] = str(name)

    model = _safe_get('status/product_info/product_name')
    if model:
        info['router_model'] = str(model)

    serial = _safe_get('status/product_info/manufacturing/serial_num')
    if serial:
        info['serial_number'] = str(serial)

    mac = _safe_get('status/product_info/mac0')
    if mac:
        info['mac_address'] = str(mac)

    firmware = _safe_get('status/fw_info') or {}
    if firmware:
        parts = [firmware.get('major_version'),
                 firmware.get('minor_version'),
                 firmware.get('patch_version')]
        parts = [str(part) for part in parts if part is not None]
        if parts:
            info['firmware_version'] = '.'.join(parts)

    rtk_config = _safe_get('config/system/rtk') or {}
    if isinstance(rtk_config, dict):
        ntrip = rtk_config.get('ntrip') or {}
        info['rtk_config'] = {
            'enabled': rtk_config.get('enabled'),
            'source': rtk_config.get('source'),
            'host': ntrip.get('host'),
            'port': ntrip.get('port'),
            'mountpoint': ntrip.get('mountpoint'),
            'format': ntrip.get('format'),
            'gga_rate': ntrip.get('gga_rate'),
            'username': ntrip.get('username'),
        }
    return info


def quality_legend():
    """Colour/label legend for the web UI."""
    return {
        'pre_color': PRE_COLOR,
        'qualities': [
            {'code': code,
             'label': QUALITY_INFO[code][0],
             'color': QUALITY_INFO[code][1],
             'accuracy': QUALITY_INFO[code][2]}
            for code in QUALITY_DISPLAY_ORDER if code in QUALITY_INFO
        ],
        'unknown': {'label': UNKNOWN_QUALITY[0], 'color': UNKNOWN_QUALITY[1],
                    'accuracy': UNKNOWN_QUALITY[2]},
        'fix_modes': [{'code': code, 'label': FIX_MODE_INFO[code]}
                      for code in sorted(FIX_MODE_INFO.keys())],
        'best_quality': BEST_QUALITY,
        'converging_quality': CONVERGING_QUALITY,
    }


# ---------------------------------------------------------------------------
# web server
# ---------------------------------------------------------------------------

class RequestHandler(http.server.BaseHTTPRequestHandler):
    """Serves the UI plus the JSON/CSV API."""

    protocol_version = 'HTTP/1.1'
    server_version = 'rtk_compare'

    sampler = None
    device_info = {}
    app_version = '0.0.0'

    def do_GET(self):
        path = self.path.split('?')[0]
        try:
            if path in ('/', '/index.html'):
                self._serve_file('index.html', 'text/html; charset=utf-8')
            elif path == '/api/status':
                self._send_json(self._status_payload())
            elif path == '/api/points':
                self._send_json(self.sampler.points_since(self._query_int('since', 0)))
            elif path == '/api/info':
                self._send_json(self._info_payload())
            elif path == '/api/legend':
                self._send_json(quality_legend())
            elif path == '/api/help':
                self._send_bytes(read_help_text().encode('utf-8'),
                                 'text/plain; charset=utf-8')
            elif path in ('/api/history.csv', '/api/download'):
                self._serve_csv()
            elif path.startswith('/static/'):
                self._serve_static(path)
            else:
                self.send_error(404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as error:
            cp.log('GET {} failed: {}'.format(path, error))
            try:
                self.send_error(500)
            except Exception:
                pass

    def do_POST(self):
        path = self.path.split('?')[0]
        try:
            length = int(self.headers.get('Content-Length') or 0)
            if length:
                self.rfile.read(length)
            if path == '/api/clear':
                ok = self.sampler.clear_history()
                self._send_json({'success': bool(ok),
                                 'generation': self.sampler.generation})
            else:
                self.send_error(404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as error:
            cp.log('POST {} failed: {}'.format(path, error))
            try:
                self.send_error(500)
            except Exception:
                pass

    # -- payloads ----------------------------------------------------------

    def _status_payload(self):
        sampler = self.sampler
        with sampler.lock:
            latest = sampler.latest
        return {
            'latest': latest,
            'stats': sampler.statistics(),
            'server_time': round(time.time(), 3),
            'rtk_supported': bool(sampler.rtk_supported),
        }

    def _info_payload(self):
        payload = dict(self.device_info)
        payload['legend'] = quality_legend()
        payload['interval_s'] = self.sampler.interval
        payload['max_points'] = self.sampler.max_points
        payload['csv_name'] = self.sampler.csv_name
        payload['data_dir'] = DATA_DIR
        return payload

    # -- transport helpers -------------------------------------------------

    def _query_int(self, key, default):
        try:
            query = self.path.split('?', 1)[1] if '?' in self.path else ''
            for part in query.split('&'):
                if not part:
                    continue
                name, _, value = part.partition('=')
                if name == key:
                    return int(value)
        except (ValueError, IndexError):
            pass
        return default

    def _send_bytes(self, body, content_type, extra_headers=None):
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload):
        body = json.dumps(payload).encode('utf-8')
        self._send_bytes(body, 'application/json; charset=utf-8')

    def _serve_file(self, relative, content_type):
        full = os.path.join(_SCRIPT_DIR, relative)
        try:
            with open(full, 'rb') as handle:
                body = handle.read()
        except (IOError, OSError):
            self.send_error(404)
            return
        self._send_bytes(body, content_type)

    def _serve_static(self, path):
        relative = path[len('/static/'):].replace('..', '')
        full = os.path.join(_STATIC_DIR, relative)
        if not os.path.isfile(full):
            self.send_error(404)
            return
        _, extension = os.path.splitext(full)
        content_type = MIME_TYPES.get(extension.lower(), 'application/octet-stream')
        try:
            with open(full, 'rb') as handle:
                body = handle.read()
        except (IOError, OSError):
            self.send_error(404)
            return
        self._send_bytes(body, content_type)

    def _serve_csv(self):
        """Download the active recording under its real on-disk name."""
        sampler = self.sampler
        filename = sampler.csv_name or csv_filename(sampler.router_name)
        try:
            with open(sampler.csv_path, 'rb') as handle:
                body = handle.read()
        except (IOError, OSError):
            body = (','.join(CSV_HEADER) + '\n').encode('utf-8')
        self._send_bytes(body, 'text/csv; charset=utf-8',
                         {'Content-Disposition':
                          'attachment; filename="{}"'.format(filename)})

    def log_message(self, fmt, *args):
        # Suppress per-request logging; the UI polls once per second.
        return


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def start_web_server(port, sampler, device_info, app_version):
    """Start the HTTP server in a daemon thread. Returns the server or None."""
    RequestHandler.sampler = sampler
    RequestHandler.device_info = device_info
    RequestHandler.app_version = app_version
    try:
        server = ThreadedHTTPServer(('', port), RequestHandler)
        server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except OSError as error:
        cp.log('ERROR: could not bind port {}: {}'.format(port, error))
        return None
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cp.log('Web server started on port {}'.format(port))
    return server


# ---------------------------------------------------------------------------
# configuration
# ---------------------------------------------------------------------------

def _appdata_value(name, default, caster, minimum=None, maximum=None):
    """Read an appdata field, falling back to the code default."""
    try:
        raw = cp.get_appdata(name)
    except Exception:
        raw = None
    if raw is None or str(raw).strip() == '':
        return default
    try:
        value = caster(str(raw).strip())
    except (TypeError, ValueError):
        cp.log('WARNING: appdata {}="{}" is not valid - using {}'.format(
            name, raw, default))
        return default
    if minimum is not None and value < minimum:
        value = minimum
    if maximum is not None and value > maximum:
        value = maximum
    return value


def load_settings():
    port = _appdata_value('rtk_compare_port', DEFAULT_PORT, int, 1, 65535)
    interval = _appdata_value('rtk_compare_interval', DEFAULT_INTERVAL,
                              float, MIN_INTERVAL, MAX_INTERVAL)
    max_points = _appdata_value('rtk_compare_max_points', DEFAULT_MAX_POINTS,
                                int, 60, 100000)
    return port, interval, max_points


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    app_name, app_version = read_package_ini()
    cp.log('Starting {} v{}...'.format(app_name, app_version))

    try:
        port, interval, max_points = load_settings()
    except Exception as error:
        cp.log('Settings load failed ({}) - using defaults'.format(error))
        port = DEFAULT_PORT
        interval = DEFAULT_INTERVAL
        max_points = DEFAULT_MAX_POINTS

    cp.log('Sampling every {}s, history {} samples'.format(
        interval, max_points))

    try:
        device_info = collect_device_info(app_version)
        cp.log('Router {} ({}) NCOS {}'.format(
            device_info.get('router_name'),
            device_info.get('router_model'),
            device_info.get('firmware_version')))
    except Exception as error:
        cp.log('Device info lookup failed: {}'.format(error))
        device_info = {'app_version': app_version}

    router_name = device_info.get('router_name') or 'router'
    if router_name == 'N/A':
        router_name = 'router'

    try:
        sampler = Sampler(interval, max_points, router_name)
    except Exception as error:
        cp.log('ERROR: sampler init failed: {}'.format(error))
        _park('sampler could not be initialised')
        return

    start_web_server(port, sampler, device_info, app_version)

    next_run = time.time()
    while True:
        try:
            sampler.sample()
        except SystemExit:
            raise
        except Exception as error:
            cp.log('Sample failed: {}'.format(error))
        next_run += interval
        delay = next_run - time.time()
        if delay <= 0:
            # Fell behind; resynchronise rather than busy-looping.
            next_run = time.time() + interval
            delay = interval
        time.sleep(delay)


def _park(reason):
    """Idle instead of exiting, so restart=true does not hot-loop the app."""
    cp.log('{} is idle: {}'.format(APP_NAME, reason))
    while True:
        time.sleep(300)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as unexpected:
        try:
            cp.log('FATAL: {}'.format(unexpected))
        except Exception:
            pass
        _park('unrecoverable error: {}'.format(unexpected))
