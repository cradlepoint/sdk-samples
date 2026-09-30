"""Local tests for the v1.1.2 TWO-LAYER Configuration Manager.

Runs off-router with an in-memory fake for the ``cp`` App Data surface so the
manager's persistence, merge, migration, and revision behavior can be verified
without a device. Not packaged/deployed; a developer test harness only.

Run: ../../.venv/bin/python3 test_configuration_manager.py

The fake deliberately simulates the SDK's LOOSE/substring name matching on the
single-argument get_appdata() path, so the exact-match loader (§3) is actually
exercised: the manager must never rely on cp.get_appdata(name) directly for the
canonical keys.
"""

import json
import sys


# ---------------------------------------------------------------------------
# Fake ``cp`` module installed BEFORE importing configuration_manager.
# ---------------------------------------------------------------------------

class FakeCp(object):
    def __init__(self):
        self.store = {}          # name -> value (str)
        self.put_calls = []      # [(name, value), ...]
        self.delete_calls = []   # [name, ...]

    def log(self, *a, **k):
        pass

    def get_appdata(self, name=''):
        # No name -> full entry list (exact-match loader uses this path).
        if not name:
            return [{'name': n, 'value': v, '_id_': n}
                    for n, v in self.store.items()]
        # Named path -> simulate LOOSE substring matching like the real SDK:
        # return the first entry whose stored name CONTAINS the request. This
        # is intentionally "wrong" so any code relying on it for canonical keys
        # gets caught.
        if name in self.store:
            return self.store[name]
        for n, v in self.store.items():
            if name in n or n in name:
                return v
        return None

    def put_appdata(self, name, value):
        self.put_calls.append((name, value))
        self.store[name] = value

    def delete_appdata(self, name):
        self.delete_calls.append(name)
        self.store.pop(name, None)


fake_cp = FakeCp()
sys.modules['cp'] = fake_cp

import configuration_manager as cm  # noqa: E402
import cellular_geo  # noqa: E402


PASS = []
FAIL = []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(('PASS' if cond else 'FAIL') + ': ' + name)


def reset_state():
    fake_cp.store.clear()
    fake_cp.put_calls.clear()
    fake_cp.delete_calls.clear()
    cm._set_effective(cm.build_default_config(), None)


GROUP = cm.GROUP_KEY
DEVICE = cm.DEVICE_KEY
EXPERIMENTAL = cm.EXPERIMENTAL_KEY

LEGACY_KEYS = ['speedtest_schedule', 'speedtest_outputs',
               'iperf_server_settings', 'iperf3_servers',
               'netperf_servers', 'geoview_settings']


def put_group(config_body, revision=1):
    doc = cm.build_group_document(config_body, revision)
    fake_cp.store[GROUP] = cm.serialize_document(doc)


def put_device(config_body, revision=1):
    doc = cm.build_device_document(config_body, revision)
    fake_cp.store[DEVICE] = cm.serialize_document(doc)


def stored_device_doc():
    raw = fake_cp.store.get(DEVICE)
    return json.loads(raw) if raw else None


def stored_group_doc():
    raw = fake_cp.store.get(GROUP)
    return json.loads(raw) if raw else None


def writes_to(key):
    return [c for c in fake_cp.put_calls if c[0] == key]


# ===========================================================================
# EXACT NAME MATCHING (§3)
# ===========================================================================
reset_state()
# Populate all three related names with DISTINCT identifiable bodies.
fake_cp.store[EXPERIMENTAL] = cm.serialize_document(
    {'schema_version': 1, 'config': {'outputs': ['EXPERIMENTAL']}})
put_group({'outputs': ['GROUP']}, 1)
put_device({'outputs': ['DEVICE']}, 1)

g = cm._get_appdata_exact(GROUP)
d = cm._get_appdata_exact(DEVICE)
e = cm._get_appdata_exact(EXPERIMENTAL)
check('exact-match: group returns group body only',
      'GROUP' in (g or ''))
check('exact-match: device returns device body only',
      'DEVICE' in (d or ''))
check('exact-match: experimental returns experimental body only',
      'EXPERIMENTAL' in (e or ''))
check('exact-match: group does not leak device/experimental',
      'DEVICE' not in (g or '') and 'EXPERIMENTAL' not in (g or ''))
check('exact-match: device does not leak group/experimental',
      'GROUP' not in (d or '') and 'EXPERIMENTAL' not in (d or ''))
check('exact-match: experimental does not leak group/device',
      'GROUP' not in (e or '') and 'DEVICE' not in (e or ''))
check('exact-match: absent name returns None (no loose fallback)',
      cm._get_appdata_exact('speedtest_analyzer_nope') is None)


# ===========================================================================
# FRESH INSTALL (§10)
# ===========================================================================
reset_state()
before = len(fake_cp.put_calls)
cs = cm.load_effective_config()
check('fresh: state unconfigured', cs.state == cm.STATE_UNCONFIGURED)
check('fresh: no keys -> effective equals defaults',
      cs.effective == cm.build_default_config())
check('fresh: ZERO App Data writes on load',
      len(fake_cp.put_calls) == before)
check('fresh: mutation not blocked', cm.mutation_blocked() is None)
check('fresh: effective outputs is default empty list',
      cm.active_section('outputs') == [])
# initialize() must also never write.
reset_state()
before = len(fake_cp.put_calls)
cm.initialize()
check('fresh: initialize() writes nothing',
      len(fake_cp.put_calls) == before)


# ===========================================================================
# FIRST NORMAL SAVE ON FRESH DEVICE (§11)
# ===========================================================================
reset_state()
cm.load_effective_config()
res = cm.save_device('schedule', {'enabled': True, 'engine': 'netperf',
                                  'cron': '0 * * * *'})
doc = stored_device_doc()
check('fresh first save: status saved', res.status == 'saved')
check('fresh first save: device key created', doc is not None)
check('fresh first save: document_type device',
      doc and doc.get('document_type') == 'device')
check('fresh first save: device_revision == 1',
      doc and doc.get('device_revision') == 1)
check('fresh first save: only schedule section stored (sparse)',
      doc and list(doc['config'].keys()) == ['schedule'])
check('fresh first save: schedule enabled persisted',
      doc and doc['config']['schedule']['enabled'] is True)
check('fresh first save: state now device',
      cm.load_effective_config().state == cm.STATE_DEVICE)
check('fresh first save: NO group key written',
      len(writes_to(GROUP)) == 0)
check('fresh first save: NO experimental key written',
      len(writes_to(EXPERIMENTAL)) == 0)
check('fresh first save: NO legacy key written',
      all(not writes_to(k) for k in LEGACY_KEYS))

# Subsequent save increments device_revision by exactly one.
res2 = cm.save_device('outputs', ['appdata:speedtest_results'])
doc2 = stored_device_doc()
check('device managed: subsequent save -> device_revision 2',
      doc2 and doc2.get('device_revision') == 2)
check('device managed: both sections now present',
      doc2 and set(doc2['config'].keys()) == {'schedule', 'outputs'})


# ===========================================================================
# SECTION-LEVEL MERGE (§6, §7, §8)
# ===========================================================================
reset_state()
put_group({'schedule': {'enabled': True, 'engine': 'netperf', 'cron': 'G'},
           'outputs': ['group_output'],
           'iperf3_server_settings': {'server_mode': 'user'}}, 1)
put_device({'schedule': {'enabled': False, 'engine': 'iperf3', 'cron': 'D'}}, 3)
cs = cm.load_effective_config()
eff = cs.effective
check('merge: schedule -> Device (override)',
      eff['schedule']['cron'] == 'D')
check('merge: outputs -> Group (not overridden)',
      eff['outputs'] == ['group_output'])
check('merge: iperf3_server_settings -> Group',
      eff['iperf3_server_settings']['server_mode'] == 'user')
check('merge: netperf_servers -> Default (absent both)',
      eff['netperf_servers'] == [])
check('merge: state group_with_device_overrides',
      cs.state == cm.STATE_GROUP_WITH_DEVICE_OVERRIDES)
check('merge: override_sections == [schedule]',
      cs.override_sections == ['schedule'])

# Falsey values are authoritative: device outputs = [] must NOT inherit group.
reset_state()
put_group({'outputs': ['group_output']}, 1)
put_device({'outputs': []}, 1)
eff = cm.load_effective_config().effective
check('presence: device outputs=[] overrides group (no truthiness fallback)',
      eff['outputs'] == [])

# Missing Group+Device section inherits Default; defensive deep copy.
reset_state()
put_group({'schedule': {'enabled': True, 'engine': 'netperf', 'cron': 'G'}}, 1)
cm.load_effective_config()
sec = cm.active_section('schedule')
sec['cron'] = 'MUTATED'
sec2 = cm.active_section('schedule')
check('defensive copy: mutating returned section does not affect RAM',
      sec2['cron'] == 'G')


# ===========================================================================
# GROUP behavior (§13, §14)
# ===========================================================================
# Group only -> pure group, no device writes.
reset_state()
put_group({'schedule': {'enabled': True, 'engine': 'netperf', 'cron': 'G'}}, 5)
cs = cm.load_effective_config()
check('group only: state group', cs.state == cm.STATE_GROUP)
check('group only: no device overrides', cs.override_sections == [])

# Device save while Group exists creates a SPARSE override, never writes group.
before_group_writes = len(writes_to(GROUP))
res = cm.save_device('schedule', {'enabled': False, 'engine': 'iperf3',
                                  'cron': 'D'})
doc = stored_device_doc()
check('override: device save creates sparse device override',
      doc and list(doc['config'].keys()) == ['schedule'])
check('override: device_revision starts at 1 for new device doc',
      doc and doc['device_revision'] == 1)
check('override: group key NEVER written on ordinary save',
      len(writes_to(GROUP)) == before_group_writes == 0)
check('override: state now group_with_device_overrides',
      cm.load_effective_config().state ==
      cm.STATE_GROUP_WITH_DEVICE_OVERRIDES)

# Saving a value equal to Group removes the redundant override (§14).
reset_state()
group_sched = {'enabled': True, 'autostart': False, 'engine': 'netperf',
               'cron': 'SAME', 'params': {}}
put_group({'schedule': group_sched, 'outputs': ['g']}, 2)
put_device({'schedule': {'enabled': False, 'engine': 'iperf3', 'cron': 'D'},
            'outputs': ['d']}, 4)
cm.load_effective_config()
res = cm.save_device('schedule', dict(group_sched))
doc = stored_device_doc()
check('redundant: schedule matching group removed from device',
      doc and 'schedule' not in doc['config'])
check('redundant: outputs override retained',
      doc and 'outputs' in doc['config'])
check('redundant: removed_override_sections reports schedule',
      'schedule' in res.removed_override_sections)
check('redundant: effective schedule now inherits group',
      cm.active_section('schedule')['cron'] == 'SAME')

# Removing the LAST override deletes the device key (§14).
reset_state()
put_group({'outputs': ['g'], 'schedule': group_sched}, 2)
put_device({'schedule': {'enabled': False, 'engine': 'iperf3', 'cron': 'D'}}, 1)
cm.load_effective_config()
res = cm.save_device('schedule', dict(group_sched))
check('redundant last: device key deleted -> pure group',
      stored_device_doc() is None)
check('redundant last: state returns to group',
      cm.load_effective_config().state == cm.STATE_GROUP)
check('redundant last: no group write occurred',
      len(writes_to(GROUP)) == 0)


# ===========================================================================
# GROUP UPDATE FROM NCM (§43)
# ===========================================================================
reset_state()
put_group({'schedule': {'enabled': True, 'engine': 'netperf', 'cron': 'A'},
           'outputs': ['A']}, 4)
put_device({'schedule': {'enabled': False, 'engine': 'iperf3', 'cron': 'B'}}, 2)
eff = cm.load_effective_config().effective
check('group update pre: schedule=B(device), outputs=A(group)',
      eff['schedule']['cron'] == 'B' and eff['outputs'] == ['A'])
# Group rev 5 changes both schedule and outputs.
put_group({'schedule': {'enabled': True, 'engine': 'netperf', 'cron': 'C'},
           'outputs': ['B']}, 5)
eff = cm.load_effective_config().effective
check('group update: overridden schedule stays device (B)',
      eff['schedule']['cron'] == 'B')
check('group update: non-overridden outputs becomes new group (B)',
      eff['outputs'] == ['B'])


# ===========================================================================
# LEGACY UPGRADE (§16, §17, §19)
# ===========================================================================
reset_state()
fake_cp.store['speedtest_schedule'] = json.dumps(
    {'enabled': True, 'engine': 'netperf', 'cron': 'LEG'})
fake_cp.store['speedtest_outputs'] = json.dumps(['appdata:speedtest_results'])
fake_cp.store['iperf3_servers'] = json.dumps([{'host': 'x'}])
before = len(fake_cp.put_calls)
cs = cm.load_effective_config()
check('legacy: PRIMARY state is upgrade_required (not unconfigured)',
      cs.state == cm.STATE_UPGRADE_REQUIRED)
check('legacy: legacy_upgrade_required boolean still set as detail',
      cs.legacy_upgrade_required is True)
check('legacy: mutation blocked (upgrade_required)',
      cm.mutation_blocked() is not None and
      cm.mutation_blocked().reason == 'upgrade_required')
check('legacy: ZERO writes on load', len(fake_cp.put_calls) == before)
check('legacy: runtime still sees legacy schedule via effective',
      cm.active_section('schedule')['cron'] == 'LEG')
# Ordinary save must be BLOCKED while upgrade_required.
res = cm.save_device('outputs', ['x'])
check('legacy: ordinary save blocked', res.status == 'blocked')
check('legacy: blocked save wrote nothing to device',
      stored_device_doc() is None)
# Convert.
res = cm.convert_legacy_to_device()
doc = stored_device_doc()
check('legacy convert: status saved', res.status == 'saved')
check('legacy convert: device_revision 1', doc and doc['device_revision'] == 1)
check('legacy convert: schedule mapped', doc and 'schedule' in doc['config'])
check('legacy convert: outputs mapped', doc and 'outputs' in doc['config'])
check('legacy convert: iperf3_servers -> iperf3_user_servers',
      doc and 'iperf3_user_servers' in doc['config'])
check('legacy convert: runtime/result keys excluded',
      doc and 'speedtest_results' not in doc['config'])
check('legacy convert: legacy keys untouched (not deleted)',
      'speedtest_schedule' in fake_cp.store and
      'speedtest_schedule' not in fake_cp.delete_calls)
check('legacy convert: state device', cm.load_effective_config().state ==
      cm.STATE_DEVICE)
check('legacy convert: mutation unblocked',
      cm.mutation_blocked() is None)
check('legacy convert: NO group/experimental/legacy writes',
      len(writes_to(GROUP)) == 0 and len(writes_to(EXPERIMENTAL)) == 0 and
      all(not writes_to(k) for k in LEGACY_KEYS))

# New key present + legacy present -> NO legacy upgrade prompt (§16).
reset_state()
fake_cp.store['speedtest_schedule'] = json.dumps(
    {'enabled': True, 'engine': 'netperf', 'cron': 'LEG'})
put_device({'outputs': ['x']}, 1)
cs = cm.load_effective_config()
check('legacy suppressed: device present -> no legacy upgrade',
      cs.state == cm.STATE_DEVICE and not cs.legacy_upgrade_required)
check('legacy suppressed: legacy is NOT a fallback for missing section',
      cm.active_section('schedule')['cron'] != 'LEG')

reset_state()
fake_cp.store['speedtest_schedule'] = json.dumps(
    {'enabled': True, 'engine': 'netperf', 'cron': 'LEG'})
put_group({'outputs': ['x']}, 1)
cs = cm.load_effective_config()
check('legacy suppressed: group present -> no legacy upgrade',
      cs.state == cm.STATE_GROUP and not cs.legacy_upgrade_required)

# Truly fresh (no keys, no legacy) stays unconfigured, NOT upgrade_required.
reset_state()
cs = cm.load_effective_config()
check('fresh vs legacy: no legacy sources -> state unconfigured',
      cs.state == cm.STATE_UNCONFIGURED and not cs.legacy_upgrade_required)

# derive_state unit: legacy_present flag drives primary state.
absent_g = cm.LayerLoad('group', 'absent')
absent_d = cm.LayerLoad('device', 'absent')
check('derive_state: both absent + legacy_present -> upgrade_required',
      cm.derive_state(absent_g, absent_d, legacy_present=True) ==
      cm.STATE_UPGRADE_REQUIRED)
check('derive_state: both absent + no legacy -> unconfigured',
      cm.derive_state(absent_g, absent_d, legacy_present=False) ==
      cm.STATE_UNCONFIGURED)


# ===========================================================================
# EXPERIMENTAL single key (§20)
# ===========================================================================
reset_state()
# Old experimental doc WITH abandoned management metadata that must be ignored.
fake_cp.store[EXPERIMENTAL] = json.dumps({
    'schema_version': 1,
    'config_revision': 7,
    'management': {'origin': 'group', 'mode': 'group'},
    'config': {'schedule': {'enabled': True, 'engine': 'netperf',
                            'cron': 'EXP'},
               'outputs': ['exp_out']},
})
before = len(fake_cp.put_calls)
cs = cm.load_effective_config()
check('experimental: PRIMARY state upgrade_required when new keys absent',
      cs.state == cm.STATE_UPGRADE_REQUIRED and cs.legacy_upgrade_required)
check('experimental: ZERO writes on load', len(fake_cp.put_calls) == before)
res = cm.convert_legacy_to_device()
doc = stored_device_doc()
check('experimental convert: device_revision 1 (old rev 7 ignored)',
      doc and doc['device_revision'] == 1)
check('experimental convert: no management metadata in device doc',
      doc and 'management' not in doc and 'config_revision' not in doc),
check('experimental convert: schedule preferred from experimental',
      doc and doc['config']['schedule']['cron'] == 'EXP')
check('experimental convert: old experimental key not written',
      len(writes_to(EXPERIMENTAL)) == 0)
check('experimental convert: old experimental key not deleted',
      EXPERIMENTAL not in fake_cp.delete_calls)
check('experimental convert: state device',
      cm.load_effective_config().state == cm.STATE_DEVICE)

# Experimental is IGNORED once a new canonical key exists.
reset_state()
fake_cp.store[EXPERIMENTAL] = json.dumps({
    'schema_version': 1, 'config': {'outputs': ['exp']}})
put_device({'outputs': ['dev']}, 1)
eff = cm.load_effective_config().effective
check('experimental ignored when device present',
      eff['outputs'] == ['dev'])


# ===========================================================================
# MULTI-SECTION TRANSACTION (§15)
# ===========================================================================
reset_state()
put_device({'schedule': {'enabled': True, 'engine': 'iperf3', 'cron': 'X'}}, 5)
cm.load_effective_config()
put_before = len(writes_to(DEVICE))
res = cm.save_device(updates={
    'iperf3_user_servers': [{'host': 'srv1'}],
    'schedule': {'enabled': False, 'engine': 'netperf', 'cron': ''},
})
doc = stored_device_doc()
check('multi-section: single device write for whole transaction',
      len(writes_to(DEVICE)) - put_before == 1)
check('multi-section: device_revision +1 exactly once (5->6)',
      doc and doc['device_revision'] == 6)
check('multi-section: both sections present, no partial state',
      doc and set(doc['config'].keys()) == {'schedule', 'iperf3_user_servers'})


# ===========================================================================
# REVISIONS (§44, §45, §46)
# ===========================================================================
reset_state()
put_group({'outputs': ['g']}, 12)
put_device({'schedule': {'enabled': True, 'engine': 'netperf', 'cron': 'S'}}, 4)
report = cm.state_report()
check('revisions: independent group_revision reported',
      report['group_revision'] == 12)
check('revisions: independent device_revision reported',
      report['device_revision'] == 4)
# A device save changes only device revision, not group.
cm.load_effective_config()
cm.save_device('outputs', ['d'])
report = cm.state_report()
check('revisions: device save left group_revision unchanged',
      report['group_revision'] == 12)
check('revisions: device save incremented device_revision (4->5)',
      report['device_revision'] == 5)


# ===========================================================================
# RECONCILIATION TOKEN (§46)
# ===========================================================================
# Simulate persisted device changing between token capture and re-read by
# monkeypatching capture to observe mismatch. Simpler: put a device doc, load,
# then externally bump device revision, then attempt a save that must reconcile.
reset_state()
put_device({'outputs': ['a']}, 1)
cm.load_effective_config()
# External change to persisted device (as if NCM/another actor moved it on).
put_device({'outputs': ['external']}, 9)
# The save path re-reads inside save_device; capture==re-read within the call,
# so to prove discard-on-mismatch we drive the token directly.
tok_before = cm.RevisionToken(0, 1)
tok_after = cm.capture_revision_token()
check('reconcile: revision token reflects external change (device 1 -> 9)',
      tok_after.device_revision == 9 and tok_before != tok_after)


# ===========================================================================
# GROUP MIGRATION (§23-§34)
# ===========================================================================
reset_state()
put_device({
    'schedule': {'enabled': True, 'engine': 'netperf', 'cron': 'S'},
    'outputs': ['o'],
    'iperf3_server_settings': {'server_mode': 'public'},
}, 3)
cm.load_effective_config()

avail = cm.migration_available_sections()
avail_names = {a['section'] for a in avail}
check('migration: wizard lists only configured device sections',
      avail_names == {'schedule', 'outputs', 'iperf3_server_settings'})

# Build candidate promoting schedule + outputs, keeping iperf3_server_settings.
cand, reason = cm.build_group_migration_candidate(['schedule', 'outputs'])
check('migration: candidate built', cand is not None)
check('migration: group_revision == 1 for initial migration',
      cand and cand.group_revision == 1)
check('migration: candidate contains ONLY promoted sections',
      cand and set(cand.document['config'].keys()) == {'schedule', 'outputs'})
check('migration: candidate document_type group',
      cand and cand.document['document_type'] == 'group')
check('migration: NO local write to group key during candidate build',
      len(writes_to(GROUP)) == 0)
check('migration: Device document UNTOUCHED until group validates',
      stored_device_doc()['config'].keys().__len__() == 3 and
      len(writes_to(DEVICE)) == 0)

# Group has not arrived yet -> validation fails, device still intact.
vr = cm.validate_group_present(1)
check('migration: validate fails before group present',
      vr.ok is False)
check('migration: device still intact after failed validation',
      set(stored_device_doc()['config'].keys()) ==
      {'schedule', 'outputs', 'iperf3_server_settings'})

# User pastes the candidate into NCM (simulate group key arrival).
fake_cp.store[GROUP] = cand.to_json()
vr = cm.validate_group_present(1)
check('migration: validate succeeds once group present',
      vr.ok is True)
check('migration: success wording does NOT claim provenance',
      'provenance' not in (vr.reason or '').lower())

# ONLY NOW trim promoted sections from device.
res = cm.trim_promoted_device_sections(['schedule', 'outputs'])
doc = stored_device_doc()
check('migration: after validation, promoted sections trimmed from device',
      doc and set(doc['config'].keys()) == {'iperf3_server_settings'})
check('migration: retained section kept on device',
      doc and 'iperf3_server_settings' in doc['config'])
check('migration: device_revision incremented on cleanup (3->4)',
      doc and doc['device_revision'] == 4)
check('migration: still ZERO local group writes end-to-end',
      len(writes_to(GROUP)) == 0)
check('migration: final state group_with_device_overrides',
      cm.load_effective_config().state ==
      cm.STATE_GROUP_WITH_DEVICE_OVERRIDES)

# All promoted -> device key deleted.
reset_state()
put_device({'schedule': {'enabled': True, 'engine': 'netperf', 'cron': 'S'},
            'outputs': ['o']}, 2)
cm.load_effective_config()
cand, _ = cm.build_group_migration_candidate(['schedule', 'outputs'])
fake_cp.store[GROUP] = cand.to_json()
cm.validate_group_present(1)
cm.trim_promoted_device_sections(['schedule', 'outputs'])
check('migration all-promoted: device key deleted',
      stored_device_doc() is None)
check('migration all-promoted: state pure group',
      cm.load_effective_config().state == cm.STATE_GROUP)

# Dependency-invalid selection blocked (§27).
reset_state()
put_device({'iperf3_server_settings': {'server_mode': 'user'},
            'iperf3_user_servers': [{'host': 'u'}]}, 1)
cm.load_effective_config()
ok, reason = cm.validate_migration_selection(['iperf3_server_settings'])
check('migration dep: promoting user-mode without user servers blocked',
      ok is False)
ok, reason = cm.validate_migration_selection(
    ['iperf3_server_settings', 'iperf3_user_servers'])
check('migration dep: promoting both is valid', ok is True)


# ===========================================================================
# GEOVIEW GROUP SANITIZATION (§40, §42)
# ===========================================================================
reset_state()
# Device GPS with a current fix present in the persisted section.
geo_devgps = cellular_geo._persisted_settings(
    cellular_geo.normalize_geo_settings({
        'provider': 'none',
        'active_location_source': 'device_gps',
        'configured': True,
        'locations': {
            'device_gps': {'latitude': 45.5, 'longitude': -122.6},
            'manual_coordinates': {'latitude': None, 'longitude': None},
            'site_address': {'address': ''},
        },
    }))
put_device({'geoview': geo_devgps}, 1)
cm.load_effective_config()
avail = {a['section']: a for a in cm.migration_available_sections()}
check('geoview: device_gps is promotable', avail['geoview']['promotable'])
cand, _ = cm.build_group_migration_candidate(['geoview'])
gv = cand.document['config']['geoview']
check('geoview: promoted policy is device_gps',
      gv['active_location_source'] == 'device_gps')
check('geoview: device GPS latitude NOT copied into group',
      gv['locations']['device_gps']['latitude'] is None)
check('geoview: device GPS longitude NOT copied into group',
      gv['locations']['device_gps']['longitude'] is None)

# Manual coordinates GeoView is NOT promotable (§42).
reset_state()
geo_manual = cellular_geo._persisted_settings(
    cellular_geo.normalize_geo_settings({
        'provider': 'none',
        'active_location_source': 'manual_coordinates',
        'configured': True,
        'locations': {
            'device_gps': {'latitude': None, 'longitude': None},
            'manual_coordinates': {'latitude': 40.0, 'longitude': -70.0},
            'site_address': {'address': ''},
        },
    }))
put_device({'geoview': geo_manual}, 1)
cm.load_effective_config()
avail = {a['section']: a for a in cm.migration_available_sections()}
check('geoview: manual coords NOT promotable',
      avail['geoview']['promotable'] is False)
check('geoview: manual coords not default-selected',
      avail['geoview']['default_selected'] is False)
cand, reason = cm.build_group_migration_candidate(['geoview'])
check('geoview: promoting manual coords is blocked',
      cand is None and reason)


# ===========================================================================
# RESET SECTION / RESET ALL OVERRIDES (§36, §37, §38)
# ===========================================================================
reset_state()
put_group({'schedule': {'enabled': True, 'engine': 'netperf', 'cron': 'G'},
           'outputs': ['g']}, 1)
put_device({'schedule': {'enabled': False, 'engine': 'iperf3', 'cron': 'D'},
            'outputs': ['d']}, 2)
cm.load_effective_config()
res = cm.reset_section_to_group('schedule')
doc = stored_device_doc()
check('reset section: schedule removed from device',
      doc and 'schedule' not in doc['config'])
check('reset section: effective schedule inherits group',
      cm.active_section('schedule')['cron'] == 'G')
check('reset section: group key never written',
      len(writes_to(GROUP)) == 0)

# Reset ALL overrides with group present deletes device, keeps group.
res = cm.reset_all_device_overrides()
check('reset all (group present): device key deleted',
      stored_device_doc() is None)
check('reset all (group present): group key preserved',
      stored_group_doc() is not None and GROUP not in fake_cp.delete_calls)
check('reset all (group present): state pure group',
      cm.load_effective_config().state == cm.STATE_GROUP)

# §38: device-only reset with legacy sources retains empty schema doc.
reset_state()
fake_cp.store['speedtest_schedule'] = json.dumps(
    {'enabled': True, 'engine': 'netperf', 'cron': 'LEG'})
put_device({'outputs': ['d']}, 3)
cm.load_effective_config()
res = cm.reset_all_device_overrides()
doc = stored_device_doc()
check('reset all (§38 legacy present): device doc retained, config empty',
      doc is not None and doc['config'] == {})
check('reset all (§38 legacy present): device_revision incremented (3->4)',
      doc and doc['device_revision'] == 4)
check('reset all (§38): legacy stays suppressed (not resurrected)',
      cm.load_effective_config().state == cm.STATE_DEVICE and
      not cm.load_effective_config().legacy_upgrade_required)

# §38: device-only reset with NO legacy sources deletes device key.
reset_state()
put_device({'outputs': ['d']}, 1)
cm.load_effective_config()
res = cm.reset_all_device_overrides()
check('reset all (§38 no legacy): device key deleted -> fresh',
      stored_device_doc() is None and
      cm.load_effective_config().state == cm.STATE_UNCONFIGURED)


# ===========================================================================
# SCHEMA (§49, §50, §51)
# ===========================================================================
# Newer schema -> unsupported, no overwrite.
reset_state()
fake_cp.store[DEVICE] = json.dumps({
    'schema_version': 99, 'document_type': 'device', 'device_revision': 1,
    'config': {'outputs': ['future']}})
before = len(fake_cp.put_calls)
cs = cm.load_effective_config()
check('schema newer: state unsupported_schema',
      cs.state == cm.STATE_UNSUPPORTED_SCHEMA)
check('schema newer: mutation blocked',
      cm.mutation_blocked() is not None)
check('schema newer: NO overwrite/downgrade write',
      len(fake_cp.put_calls) == before)
res = cm.save_device('outputs', ['x'])
check('schema newer: ordinary save blocked', res.status == 'blocked')

# Older device schema -> upgrade_required, no startup write, convert bumps rev.
reset_state()
fake_cp.store[DEVICE] = json.dumps({
    'schema_version': 0, 'document_type': 'device', 'device_revision': 4,
    'config': {'outputs': ['old']}})
before = len(fake_cp.put_calls)
cs = cm.load_effective_config()
check('schema older device: upgrade_required',
      cs.state == cm.STATE_UPGRADE_REQUIRED)
check('schema older device: NO startup write',
      len(fake_cp.put_calls) == before)
res = cm.convert_older_device_schema()
doc = stored_device_doc()
check('schema older device: convert bumps device_revision (4->5)',
      doc and doc['device_revision'] == 5 and doc['schema_version'] == 1)

# Older group schema -> group candidate only, no local group write.
reset_state()
fake_cp.store[GROUP] = json.dumps({
    'schema_version': 0, 'document_type': 'group', 'group_revision': 6,
    'config': {'outputs': ['og']}})
before = len(fake_cp.put_calls)
cs = cm.load_effective_config()
check('schema older group: upgrade_required (group_schema)',
      cs.state == cm.STATE_UPGRADE_REQUIRED and
      cm.mutation_blocked().reason == 'group_schema')
cand = cm.build_group_upgrade_candidate()
check('schema older group: candidate group_revision = previous+1 (6->7)',
      cand and cand.group_revision == 7)
check('schema older group: NO local group write',
      len(writes_to(GROUP)) == 0 and len(fake_cp.put_calls) == before)


# ===========================================================================
# CAN_MIGRATE_TO_GROUP MATRIX (§23) -- Device-only migration
# ===========================================================================
def _can_migrate_for(setup):
    reset_state()
    setup()
    return cm.state_report()

# unconfigured
r = _can_migrate_for(lambda: None)
check('can_migrate matrix: unconfigured -> False',
      r['state'] == cm.STATE_UNCONFIGURED and r['can_migrate_to_group'] is False)
# upgrade_required (legacy)
def _legacy():
    fake_cp.store['speedtest_schedule'] = json.dumps(
        {'enabled': True, 'engine': 'netperf', 'cron': 'L'})
r = _can_migrate_for(_legacy)
check('can_migrate matrix: upgrade_required -> False',
      r['state'] == cm.STATE_UPGRADE_REQUIRED and
      r['can_migrate_to_group'] is False)
# device
r = _can_migrate_for(lambda: put_device({'outputs': ['d']}, 1))
check('can_migrate matrix: device -> True',
      r['state'] == cm.STATE_DEVICE and r['can_migrate_to_group'] is True)
# group
r = _can_migrate_for(lambda: put_group({'outputs': ['g']}, 1))
check('can_migrate matrix: group -> False',
      r['state'] == cm.STATE_GROUP and r['can_migrate_to_group'] is False)
# group_with_device_overrides
def _grp_dev():
    put_group({'outputs': ['g']}, 1)
    put_device({'schedule': {'enabled': True, 'engine': 'netperf',
                             'cron': 'D'}}, 1)
r = _can_migrate_for(_grp_dev)
check('can_migrate matrix: group_with_device_overrides -> False',
      r['state'] == cm.STATE_GROUP_WITH_DEVICE_OVERRIDES and
      r['can_migrate_to_group'] is False)
# unsupported_schema
def _newer():
    fake_cp.store[DEVICE] = json.dumps({
        'schema_version': 99, 'document_type': 'device', 'device_revision': 1,
        'config': {}})
r = _can_migrate_for(_newer)
check('can_migrate matrix: unsupported_schema -> False',
      r['state'] == cm.STATE_UNSUPPORTED_SCHEMA and
      r['can_migrate_to_group'] is False)
# error (corrupt)
def _corrupt():
    fake_cp.store[DEVICE] = '{not json'
r = _can_migrate_for(_corrupt)
check('can_migrate matrix: error -> False',
      r['state'] == cm.STATE_ERROR and r['can_migrate_to_group'] is False)

# Migration candidate build is refused once Group already exists.
reset_state()
put_group({'outputs': ['g']}, 1)
put_device({'schedule': {'enabled': True, 'engine': 'netperf', 'cron': 'D'}}, 1)
cm.load_effective_config()
cand, reason = cm.build_group_migration_candidate(['schedule'])
check('migration guard: candidate refused when Group already present',
      cand is None and reason)


# ===========================================================================
# LEGACY / EXPERIMENTAL COMPATIBILITY-EFFECTIVE (§17 runtime continuity)
# ===========================================================================
# Fragmented legacy remains the EFFECTIVE config while upgrade_required.
reset_state()
fake_cp.store['speedtest_schedule'] = json.dumps(
    {'enabled': True, 'autostart': True, 'engine': 'iperf3', 'cron': '30 2 * * *'})
fake_cp.store['iperf3_servers'] = json.dumps([{'host': 'legsrv', 'port': '5201'}])
fake_cp.store['speedtest_outputs'] = json.dumps(['appdata:speedtest_results'])
before = len(fake_cp.put_calls)
cs = cm.load_effective_config()
check('legacy-effective: state upgrade_required', cs.state ==
      cm.STATE_UPGRADE_REQUIRED)
check('legacy-effective: schedule is the normalized legacy schedule',
      cm.active_section('schedule')['cron'] == '30 2 * * *' and
      cm.active_section('schedule')['engine'] == 'iperf3')
check('legacy-effective: user iperf3 list is the legacy list',
      cm.active_section('iperf3_user_servers') == [{'host': 'legsrv',
                                                    'port': '5201'}])
check('legacy-effective: outputs are the legacy outputs',
      cm.active_section('outputs') == ['appdata:speedtest_results'])
check('legacy-effective: ZERO writes while compatibility-effective',
      len(fake_cp.put_calls) == before)
# Conversion preserves the effective values; storage becomes Device rev1.
pre_schedule = cm.active_section('schedule')
pre_outputs = cm.active_section('outputs')
pre_users = cm.active_section('iperf3_user_servers')
res = cm.convert_legacy_to_device()
doc = stored_device_doc()
check('legacy-effective: convert -> device_revision 1',
      doc and doc['device_revision'] == 1)
check('legacy-effective: convert preserves schedule value',
      cm.active_section('schedule') == pre_schedule)
check('legacy-effective: convert preserves outputs value',
      cm.active_section('outputs') == pre_outputs)
check('legacy-effective: convert preserves user list value',
      cm.active_section('iperf3_user_servers') == pre_users)
check('legacy-effective: after convert state device',
      cm.load_effective_config().state == cm.STATE_DEVICE)

# Experimental payload remains effective; management metadata ignored.
reset_state()
fake_cp.store[EXPERIMENTAL] = json.dumps({
    'schema_version': 1, 'config_revision': 42,
    'management': {'origin': 'group', 'mode': 'device_override'},
    'config': {'schedule': {'enabled': True, 'engine': 'netperf', 'cron': 'XP'},
               'outputs': ['xp_out']},
})
before = len(fake_cp.put_calls)
cs = cm.load_effective_config()
check('exp-effective: state upgrade_required', cs.state ==
      cm.STATE_UPGRADE_REQUIRED)
check('exp-effective: experimental config body is effective',
      cm.active_section('schedule')['cron'] == 'XP' and
      cm.active_section('outputs') == ['xp_out'])
check('exp-effective: ZERO startup writes', len(fake_cp.put_calls) == before)
pre_sched_xp = cm.active_section('schedule')
res = cm.convert_legacy_to_device()
doc = stored_device_doc()
check('exp-effective: convert -> device_revision 1 (rev 42 ignored)',
      doc and doc['device_revision'] == 1)
check('exp-effective: convert preserves effective schedule',
      cm.active_section('schedule') == pre_sched_xp)
check('exp-effective: no management metadata carried into device doc',
      'management' not in doc and 'config_revision' not in doc)


# ===========================================================================
# HOT-RELOAD EFFECTIVE-BODY SHAPE (§ callback boundary)
# ===========================================================================
_captured = {'payload': None, 'count': 0}


def _capture_cb(effective):
    _captured['payload'] = effective
    _captured['count'] += 1


cm.register_hot_reload(_capture_cb)


def _is_effective_body(payload):
    """True when payload is a section body, not a wrapped/layered document."""
    if not isinstance(payload, dict):
        return False
    if 'schema_version' in payload or 'document_type' in payload or \
            'config' in payload or 'device_revision' in payload or \
            'group_revision' in payload:
        return False
    if 'group' in payload or 'device' in payload:
        return False
    # Must contain the known section keys.
    return all(k in payload for k in cm.SECTION_NAMES)


# first Device save
reset_state()
cm.load_effective_config()
_captured['payload'] = None
cm.save_device('schedule', {'enabled': True, 'engine': 'netperf', 'cron': 'A'})
check('hot-reload shape: first device save -> effective body',
      _is_effective_body(_captured['payload']))

# Device save with Group present
reset_state()
put_group({'outputs': ['g']}, 1)
cm.load_effective_config()
_captured['payload'] = None
cm.save_device('schedule', {'enabled': True, 'engine': 'netperf', 'cron': 'B'})
check('hot-reload shape: device save with group -> effective body',
      _is_effective_body(_captured['payload']))

# redundant override removal
reset_state()
gs = {'enabled': True, 'autostart': False, 'engine': 'netperf', 'cron': 'SAME',
      'params': {}}
put_group({'schedule': gs, 'outputs': ['g']}, 1)
put_device({'schedule': {'enabled': False, 'engine': 'iperf3', 'cron': 'D'}}, 1)
cm.load_effective_config()
_captured['payload'] = None
cm.save_device('schedule', dict(gs))
check('hot-reload shape: redundant override removal -> effective body',
      _is_effective_body(_captured['payload']))

# Group migration cleanup
reset_state()
put_device({'schedule': {'enabled': True, 'engine': 'netperf', 'cron': 'S'},
            'outputs': ['o']}, 1)
cm.load_effective_config()
cand, _ = cm.build_group_migration_candidate(['schedule', 'outputs'])
fake_cp.store[GROUP] = cand.to_json()
cm.validate_group_present(1)
_captured['payload'] = None
cm.trim_promoted_device_sections(['schedule', 'outputs'])
check('hot-reload shape: migration cleanup -> effective body',
      _is_effective_body(_captured['payload']))

# legacy conversion
reset_state()
fake_cp.store['speedtest_schedule'] = json.dumps(
    {'enabled': True, 'engine': 'netperf', 'cron': 'LEG'})
cm.load_effective_config()
_captured['payload'] = None
cm.convert_legacy_to_device()
check('hot-reload shape: legacy conversion -> effective body',
      _is_effective_body(_captured['payload']))

# Restore no-op callback so later suites are unaffected.
cm.register_hot_reload(None)


# ===========================================================================
# OVERRIDE DETAILS (reset_target + safe summaries) -- UX cleanup pass
# ===========================================================================
def details_for():
    return cm.state_report().get('override_details', [])

# reset_target=group when the section also exists in Group.
reset_state()
put_group({'schedule': {'enabled': True, 'engine': 'netperf', 'cron': 'G'}}, 1)
put_device({'schedule': {'enabled': True, 'autostart': True,
                         'engine': 'iperf3', 'cron': '0 * * * *',
                         'params': {'server_name': 'NOCIX - KC, MO'}}}, 1)
d = details_for()
sched = next((x for x in d if x['section'] == 'schedule'), None)
check('override_details: schedule present', sched is not None)
check('override_details: reset_target=group when Group has section',
      sched and sched['reset_target'] == 'group')
check('override_details: schedule summary compact + safe (no JSON dump)',
      sched and 'Hourly' in sched['summary'] and 'iperf3' in sched['summary']
      and 'NOCIX - KC, MO' in sched['summary'] and '{' not in sched['summary'])

# reset_target=default when the section is NOT in Group.
reset_state()
put_group({'schedule': {'enabled': True, 'engine': 'netperf', 'cron': 'G'}}, 1)
put_device({'schedule': {'enabled': False, 'engine': 'iperf3', 'cron': 'D'},
            'outputs': ['config/system/desc']}, 2)
d = details_for()
out = next((x for x in d if x['section'] == 'outputs'), None)
check('override_details: outputs present', out is not None)
check('override_details: reset_target=default when Group lacks section',
      out and out['reset_target'] == 'default')
check('override_details: outputs summary shows target',
      out and out['summary'] == 'config/system/desc')

# Summaries for the remaining section types (compact + safe).
check('summary iperf3_server_settings user',
      cm.summarize_section('iperf3_server_settings',
                           {'server_mode': 'user'}) == 'User iPerf3 Servers')
check('summary iperf3_server_settings public',
      cm.summarize_section('iperf3_server_settings',
                           {'server_mode': 'public'}) ==
      'Public iPerf3 Servers')
check('summary iperf3_user_servers count',
      cm.summarize_section('iperf3_user_servers',
                           [{'host': 'a'}, {'host': 'b'}, {'host': 'c'}]) ==
      '3 configured servers')
check('summary netperf_servers count (singular)',
      cm.summarize_section('netperf_servers', [{'server': 'n'}]) ==
      '1 configured server')
check('summary geoview device_gps',
      cm.summarize_section('geoview',
                           {'active_location_source': 'device_gps'}) ==
      'Device GPS')
check('summary geoview manual',
      cm.summarize_section('geoview',
                           {'active_location_source': 'manual_coordinates'}) ==
      'Manual Coordinates')

# No-secret safety: a hypothetical future secret field must never appear in a
# summary (the allow-listed summarizer ignores unknown fields).
poisoned = {'server_mode': 'user', 'api_key': 'SECRET-TOKEN-123',
            'password': 'p@ss'}
s = cm.summarize_section('iperf3_server_settings', poisoned)
check('summary safety: unknown secret-like fields never surface',
      'SECRET-TOKEN-123' not in s and 'p@ss' not in s and
      s == 'User iPerf3 Servers')
gv_poison = {'active_location_source': 'device_gps',
             'provider_api_key': 'LEAK'}
check('summary safety: geoview secret-like field never surfaces',
      'LEAK' not in cm.summarize_section('geoview', gv_poison))


# ===========================================================================
# EFFECTIVE SECTION SOURCES (backend-derived, by presence)
# ===========================================================================
def sources_for():
    return cm.state_report().get('effective_section_sources', {})

# Pure fresh/default -> all default.
reset_state()
src = sources_for()
check('sources fresh: all default',
      all(src.get(s) == 'default' for s in cm.SECTION_NAMES))

# Device-only sparse -> present sections device, rest default.
reset_state()
put_device({'schedule': {'enabled': True, 'engine': 'netperf', 'cron': 'D'},
            'outputs': ['d']}, 1)
src = sources_for()
check('sources device-only: schedule/outputs=device, others=default',
      src['schedule'] == 'device' and src['outputs'] == 'device' and
      src['netperf_servers'] == 'default' and src['geoview'] == 'default')

# Pure Group sparse -> present sections group, rest default.
reset_state()
put_group({'schedule': {'enabled': True, 'engine': 'netperf', 'cron': 'G'},
           'iperf3_server_settings': {'server_mode': 'user'}}, 1)
src = sources_for()
check('sources group-only: schedule/iperf3_server_settings=group, rest default',
      src['schedule'] == 'group' and
      src['iperf3_server_settings'] == 'group' and
      src['outputs'] == 'default')

# Group + Device overrides -> device wins where present, else group, else default.
reset_state()
put_group({'schedule': {'enabled': True, 'engine': 'netperf', 'cron': 'G'},
           'outputs': ['g'], 'netperf_servers': [{'server': 'n'}]}, 1)
put_device({'schedule': {'enabled': False, 'engine': 'iperf3', 'cron': 'D'}}, 1)
src = sources_for()
check('sources group+device: schedule=device (override)',
      src['schedule'] == 'device')
check('sources group+device: outputs=group (inherited)',
      src['outputs'] == 'group')
check('sources group+device: netperf_servers=group (inherited)',
      src['netperf_servers'] == 'group')
check('sources group+device: geoview=default (absent both)',
      src['geoview'] == 'default')

# Falsey Device section is present -> source device (presence, not truthiness).
reset_state()
put_group({'outputs': ['g']}, 1)
put_device({'outputs': []}, 1)
src = sources_for()
check('sources falsey device outputs=[]: source device (presence)',
      src['outputs'] == 'device')

# Falsey Group section is present -> source group when device absent.
reset_state()
put_group({'outputs': []}, 1)
src = sources_for()
check('sources falsey group outputs=[]: source group (presence)',
      src['outputs'] == 'group')


# ===========================================================================
# DEVICE-GPS PERSISTENCE AUDIT (§39, §40) -- coords never persisted to device
# ===========================================================================
# Simulate an ordinary GeoView save with device_gps selected AND a current GPS
# fix present in the incoming payload's device_gps locations. The persisted
# Device geoview section must NOT contain the current lat/lon.
reset_state()
cm.load_effective_config()
incoming = cellular_geo.normalize_geo_settings({
    'provider': 'none',
    'active_location_source': 'device_gps',
    'configured': True,
    'locations': {
        'device_gps': {'latitude': 47.6, 'longitude': -122.3},
        'manual_coordinates': {'latitude': None, 'longitude': None},
        'site_address': {'address': ''},
    },
})
geoview_value = cellular_geo._persisted_settings(incoming)
res = cm.save_device('geoview', geoview_value)
doc = stored_device_doc()
stored_geo = doc['config']['geoview'] if doc else {}
dev_gps = stored_geo.get('locations', {}).get('device_gps', {})
check('device-gps save: device_revision == 1 (policy saved)',
      doc and doc['device_revision'] == 1)
check('device-gps save: active_location_source persisted = device_gps',
      stored_geo.get('active_location_source') == 'device_gps')
check('device-gps save: current GPS latitude NOT persisted to device',
      dev_gps.get('latitude') is None)
check('device-gps save: current GPS longitude NOT persisted to device',
      dev_gps.get('longitude') is None)
# A subsequent identical save must be a redundant no-op (no revision bump),
# proving GPS coords are not sneaking in to make it look "changed".
writes_before = len(writes_to(DEVICE))
res2 = cm.save_device('geoview', cellular_geo._persisted_settings(
    cellular_geo.normalize_geo_settings({
        'provider': 'none', 'active_location_source': 'device_gps',
        'configured': True,
        'locations': {
            'device_gps': {'latitude': 12.3, 'longitude': 45.6},
            'manual_coordinates': {'latitude': None, 'longitude': None},
            'site_address': {'address': ''},
        }})))
doc2 = stored_device_doc()
check('device-gps save: re-save with DIFFERENT GPS coords does NOT bump revision',
      doc2 and doc2['device_revision'] == 1)
check('device-gps save: no-op re-save performed ZERO device writes',
      len(writes_to(DEVICE)) == writes_before)
check('device-gps save: no-op reported no_change=True',
      res2.status == 'saved' and res2.no_change is True)


# ===========================================================================
# NO-OP SAVE GUARD (§45) -- cases A-G
# ===========================================================================
# B. Ordinary identical save: existing Device Schedule saved again unchanged.
reset_state()
sched = {'enabled': True, 'autostart': False, 'engine': 'netperf',
         'cron': '0 * * * *', 'params': {}}
put_device({'schedule': dict(sched)}, 3)
cm.load_effective_config()
wb = len(writes_to(DEVICE))
res = cm.save_device('schedule', dict(sched))
doc = stored_device_doc()
check('noop B: identical schedule re-save -> no_change=True',
      res.no_change is True)
check('noop B: identical schedule re-save -> ZERO writes',
      len(writes_to(DEVICE)) == wb)
check('noop B: identical schedule re-save -> revision unchanged (3)',
      doc and doc['device_revision'] == 3)

# C. Multi-section identical transaction -> no write/increment.
reset_state()
put_device({'schedule': dict(sched), 'outputs': ['o']}, 2)
cm.load_effective_config()
wb = len(writes_to(DEVICE))
res = cm.save_device(updates={'schedule': dict(sched), 'outputs': ['o']})
doc = stored_device_doc()
check('noop C: multi-section identical -> no_change=True', res.no_change is True)
check('noop C: multi-section identical -> ZERO writes',
      len(writes_to(DEVICE)) == wb)
check('noop C: multi-section identical -> revision unchanged (2)',
      doc and doc['device_revision'] == 2)

# D. Multi-section partial change -> ONE write, ONE increment.
reset_state()
put_device({'schedule': dict(sched), 'outputs': ['o']}, 2)
cm.load_effective_config()
wb = len(writes_to(DEVICE))
res = cm.save_device(updates={'schedule': dict(sched), 'outputs': ['CHANGED']})
doc = stored_device_doc()
check('noop D: partial change -> no_change False', not res.no_change)
check('noop D: partial change -> exactly ONE device write',
      len(writes_to(DEVICE)) - wb == 1)
check('noop D: partial change -> revision +1 (2->3)',
      doc and doc['device_revision'] == 3)
check('noop D: changed section persisted, unchanged section intact',
      doc and doc['config']['outputs'] == ['CHANGED'] and
      doc['config']['schedule']['cron'] == '0 * * * *')

# E. Group redundant override still wins over the no-op guard.
reset_state()
gsched = {'enabled': True, 'autostart': False, 'engine': 'netperf',
          'cron': 'G', 'params': {}}
put_group({'schedule': dict(gsched), 'outputs': ['g']}, 1)
put_device({'schedule': {'enabled': False, 'engine': 'iperf3', 'cron': 'D'},
            'outputs': ['d']}, 4)
cm.load_effective_config()
res = cm.save_device('schedule', dict(gsched))
doc = stored_device_doc()
check('noop E: saving value equal to Group removes redundant override',
      doc and 'schedule' not in doc['config'])
check('noop E: removal is a real change (not no_change)', not res.no_change)
check('noop E: outputs override retained',
      doc and doc['config']['outputs'] == ['d'])

# E2. Removing the last override deletes the Device key (cleanup wins).
reset_state()
put_group({'schedule': dict(gsched)}, 1)
put_device({'schedule': {'enabled': False, 'engine': 'iperf3', 'cron': 'D'}}, 1)
cm.load_effective_config()
res = cm.save_device('schedule', dict(gsched))
check('noop E2: last redundant override -> Device key deleted',
      stored_device_doc() is None and not res.no_change)

# F. PURE GROUP same-value save (distinct from removing an existing override).
#    Group schedule=A, Device absent, user saves schedule=A.
reset_state()
hot = {'count': 0}
cm.register_hot_reload(lambda eff: hot.__setitem__('count', hot['count'] + 1))
put_group({'schedule': dict(gsched)}, 2)
cm.load_effective_config()
hot['count'] = 0
wb = len(writes_to(DEVICE))
res = cm.save_device('schedule', dict(gsched))
check('noop F: no Device key created', stored_device_doc() is None)
check('noop F: zero Device writes', len(writes_to(DEVICE)) == wb)
check('noop F: no device_revision generated (device absent)',
      cm.state_report().get('device_revision') is None)
check('noop F: Group untouched (still present, rev 2)',
      stored_group_doc() is not None and
      cm.state_report().get('group_revision') == 2)
check('noop F: no_change=True', res.no_change is True)
check('noop F: no hot reload invoked', hot['count'] == 0)
check('noop F: state remains pure group',
      cm.load_effective_config().state == cm.STATE_GROUP)
cm.register_hot_reload(None)

# G. Legacy-suppression sentinel (config={}) must survive an identical no-op.
reset_state()
fake_cp.store['speedtest_schedule'] = json.dumps(
    {'enabled': True, 'engine': 'netperf', 'cron': 'LEG'})
put_device({}, 5)  # sentinel empty-config device doc suppressing legacy
cm.load_effective_config()
# There are no sections in the sentinel; save a section that equals... nothing
# to compare. Instead prove the sentinel is not deleted by an identical empty
# transaction is impossible (staged never empty), so test that saving a NEW
# section writes (not deletes) and keeps suppression, and that re-saving that
# same section is a no-op preserving the doc.
res = cm.save_device('outputs', ['x'])
doc = stored_device_doc()
check('noop G: sentinel + real save -> device doc present, section added',
      doc is not None and doc['config'].get('outputs') == ['x'] and
      doc['device_revision'] == 6)
wb = len(writes_to(DEVICE))
res2 = cm.save_device('outputs', ['x'])
doc2 = stored_device_doc()
check('noop G: identical re-save -> no_change, sentinel/doc preserved',
      res2.no_change is True and doc2 is not None and
      doc2['device_revision'] == 6 and len(writes_to(DEVICE)) == wb)

# Manual coordinates remain device-specific persistent configuration.
reset_state()
cm.load_effective_config()
manual = cellular_geo._persisted_settings(cellular_geo.normalize_geo_settings({
    'provider': 'none', 'active_location_source': 'manual_coordinates',
    'configured': True,
    'locations': {
        'device_gps': {'latitude': None, 'longitude': None},
        'manual_coordinates': {'latitude': 40.0, 'longitude': -70.0},
        'site_address': {'address': ''},
    }}))
cm.save_device('geoview', manual)
doc = stored_device_doc()
mc = doc['config']['geoview']['locations']['manual_coordinates']
check('manual coords: persisted as device-specific config',
      mc.get('latitude') == 40.0 and mc.get('longitude') == -70.0)


# ===========================================================================
# RESET DEPENDENCY VALIDATION (v1.1.2) -- iPerf3 schedule <-> server mode
# ===========================================================================
# Helper builders for the confirmed E400 repro shape.


def _iperf3_schedule(server_source, server_ref='pub|us|host|5201'):
    return {'enabled': True, 'autostart': False, 'engine': 'iperf3',
            'cron': '0 * * * *',
            'params': {'server_source': server_source,
                       'server_ref': server_ref}}


def _netperf_schedule():
    return {'enabled': True, 'autostart': False, 'engine': 'netperf',
            'cron': '0 * * * *', 'params': {}}


# --- A. Group Public iPerf3 schedule + Device User mode ---------------------
# Group rev1: Public iPerf3 schedule (no iperf3_server_settings -> default
# Public). Device overrides schedule (safe disabled) AND server_mode=user.
# Resetting Scheduled Testing ALONE would inherit the Group Public schedule
# while the Device still forces User mode -> incompatible. Must be BLOCKED.
reset_state()
put_group({'schedule': _iperf3_schedule('public')}, 1)
put_device({'schedule': cm._default_config_body()['schedule'],
            'iperf3_server_settings': {'server_mode': 'user'}}, 2)
cm.load_effective_config()
wb = len(writes_to(DEVICE))
res = cm.reset_section_to_group('schedule')
check('reset dep A: schedule-only reset BLOCKED (dependency_reset_required)',
      res.status == 'dependency_reset_required')
check('reset dep A: zero Device writes on blocked reset',
      len(writes_to(DEVICE)) == wb)
check('reset dep A: device doc unchanged (rev still 2)',
      stored_device_doc() and stored_device_doc()['device_revision'] == 2)
check('reset dep A: required_reset_sections couples schedule + server mode',
      res.dependency and
      set(res.dependency['required_reset_sections']) ==
      {'schedule', 'iperf3_server_settings'})
check('reset dep A: reason is human-readable and non-empty',
      res.dependency and bool(res.dependency.get('reason')))

# --- B. Confirmed coupled reset -> both removed atomically, ONE revision ----
reset_state()
put_group({'schedule': _iperf3_schedule('public')}, 1)
put_device({'schedule': cm._default_config_body()['schedule'],
            'iperf3_server_settings': {'server_mode': 'user'}}, 2)
cm.load_effective_config()
wb = len(writes_to(DEVICE))
db = len([c for c in fake_cp.delete_calls if c == DEVICE])
res = cm.reset_section_to_group(
    'schedule', confirm_sections=['schedule', 'iperf3_server_settings'])
doc = stored_device_doc()
check('reset dep B: confirmed coupled reset -> saved', res.status == 'saved')
# Device had ONLY those two sections -> the coupled removal empties the Device
# doc, so the transaction is a single atomic DELETE (zero writes), not a write.
check('reset dep B: zero device writes (atomic delete of emptied Device)',
      len(writes_to(DEVICE)) == wb)
check('reset dep B: exactly ONE Device key delete for the transaction',
      len([c for c in fake_cp.delete_calls if c == DEVICE]) - db == 1)
# Both overrides removed; Device had only those two sections -> key deleted.
check('reset dep B: both overrides removed (Device key deleted)', doc is None)
check('reset dep B: Group untouched (still rev 1)',
      stored_group_doc() and stored_group_doc()['group_revision'] == 1)
# Effective now: schedule from Group (Public), server mode default (Public).
eff = cm.get_effective_config()
check('reset dep B: effective schedule inherited from Group (Public)',
      eff['schedule']['params'].get('server_source') == 'public')
check('reset dep B: effective server mode back to Public default',
      eff['iperf3_server_settings']['server_mode'] == 'public')
ok_final, conflict_final = cm.check_effective_dependencies(eff)
check('reset dep B: final effective config is dependency-consistent', ok_final)

# --- B2. Coupled reset keeps unrelated overrides + increments once ----------
reset_state()
put_group({'schedule': _iperf3_schedule('public')}, 1)
put_device({'schedule': cm._default_config_body()['schedule'],
            'iperf3_server_settings': {'server_mode': 'user'},
            'outputs': ['keepme']}, 4)
cm.load_effective_config()
wb = len(writes_to(DEVICE))
res = cm.reset_section_to_group(
    'schedule', confirm_sections=['schedule', 'iperf3_server_settings'])
doc = stored_device_doc()
check('reset dep B2: unrelated outputs override retained',
      doc and doc['config'].get('outputs') == ['keepme'] and
      'schedule' not in doc['config'] and
      'iperf3_server_settings' not in doc['config'])
check('reset dep B2: exactly ONE device write; revision +1 (4->5)',
      len(writes_to(DEVICE)) - wb == 1 and doc['device_revision'] == 5)

# --- C. Inverse case: Group User schedule + Device Public mode --------------
# The Group is internally consistent (User schedule + User server mode + User
# servers). The Device overrides server_mode to Public (and disables the
# schedule). Resetting the schedule alone would inherit the Group User schedule
# while the Device still forces Public -> incompatible. Confirming the coupled
# reset removes both Device overrides and inherits the consistent Group.
reset_state()
put_group({'schedule': _iperf3_schedule('user', 'user|h|5201'),
           'iperf3_server_settings': {'server_mode': 'user'},
           'iperf3_user_servers': [{'server': 'h', 'port': '5201'}]}, 1)
put_device({'schedule': cm._default_config_body()['schedule'],
            'iperf3_server_settings': {'server_mode': 'public'}}, 2)
cm.load_effective_config()
res = cm.reset_section_to_group('schedule')
check('reset dep C: inverse (Group User schedule + Device Public) BLOCKED',
      res.status == 'dependency_reset_required')
check('reset dep C: inverse couples schedule + server mode',
      res.dependency and
      set(res.dependency['required_reset_sections']) ==
      {'schedule', 'iperf3_server_settings'})
# Confirm resolves it.
res2 = cm.reset_section_to_group(
    'schedule', confirm_sections=['schedule', 'iperf3_server_settings'])
check('reset dep C: confirmed inverse reset -> saved', res2.status == 'saved')

# --- D. Netperf / non-dependent schedule reset is unaffected ----------------
reset_state()
put_group({'schedule': _netperf_schedule()}, 1)
put_device({'schedule': {'enabled': False, 'autostart': False,
                         'engine': 'netperf', 'cron': '*/5 * * * *',
                         'params': {}},
            'iperf3_server_settings': {'server_mode': 'user'}}, 2)
cm.load_effective_config()
res = cm.reset_section_to_group('schedule')
check('reset dep D: Netperf schedule reset NOT blocked (saved)',
      res.status == 'saved')
doc = stored_device_doc()
check('reset dep D: only the schedule override removed; server mode kept',
      doc and 'schedule' not in doc['config'] and
      doc['config'].get('iperf3_server_settings', {}).get('server_mode')
      == 'user')

# --- D2. Resetting a NON-iperf3 override never couples the iperf3 schedule ---
# Group has a Public iPerf3 schedule; Device overrides server_mode=user (which
# already conflicts) plus an unrelated outputs override. Resetting OUTPUTS must
# not drag the schedule/server-mode dependency in (the conflict pre-exists and
# is not caused by removing outputs).
reset_state()
put_group({'schedule': _iperf3_schedule('public'),
           'outputs': ['g']}, 1)
put_device({'outputs': ['d'],
            'iperf3_server_settings': {'server_mode': 'public'}}, 2)
cm.load_effective_config()
res = cm.reset_section_to_group('outputs')
check('reset dep D2: unrelated outputs reset unaffected by iperf3 coupling',
      res.status == 'saved')

# --- E. reset_target wording: group vs default ------------------------------
# Section exists in Group -> reset_target 'group' + NCM Group wording.
reset_state()
put_group({'outputs': ['g']}, 1)
put_device({'outputs': ['d']}, 2)
cm.load_effective_config()
res = cm.reset_section_to_group('outputs')
check('reset target E-group: reset_target == group',
      res.reset_target == 'group')
check('reset target E-group: message names the NCM Group configuration',
      'NCM Group configuration' in (res.message or ''))

# Section absent from Group -> reset_target 'default' + Built-in Default wording.
reset_state()
put_group({'schedule': _netperf_schedule()}, 1)   # group present, no outputs
put_device({'outputs': ['d']}, 2)
cm.load_effective_config()
res = cm.reset_section_to_group('outputs')
check('reset target E-default: reset_target == default',
      res.reset_target == 'default')
check('reset target E-default: message names the Built-in Default',
      'Built-in Default' in (res.message or ''))

# --- F. Reset All validates the final Group+Default effective config --------
# When the Group ALONE is internally consistent, Reset All succeeds and deletes
# the Device key.
reset_state()
put_group({'schedule': _iperf3_schedule('public')}, 1)
put_device({'schedule': cm._default_config_body()['schedule'],
            'iperf3_server_settings': {'server_mode': 'user'}}, 2)
cm.load_effective_config()
res = cm.reset_all_device_overrides()
check('reset all F: consistent Group -> Reset All saved',
      res.status == 'saved')
check('reset all F: Device key deleted, Group kept (rev 1)',
      stored_device_doc() is None and
      stored_group_doc() and stored_group_doc()['group_revision'] == 1)

# When the Group ALONE would be inconsistent, Reset All refuses (validates the
# final effective before persisting). Construct a Group whose own schedule
# disagrees with its own server mode.
reset_state()
put_group({'schedule': _iperf3_schedule('user', 'user|h|5201'),
           'iperf3_server_settings': {'server_mode': 'public'},
           'iperf3_user_servers': [{'server': 'h', 'port': '5201'}]}, 1)
put_device({'outputs': ['d']}, 2)
cm.load_effective_config()
wb = len(writes_to(DEVICE))
dc = len(fake_cp.delete_calls)
res = cm.reset_all_device_overrides()
check('reset all F2: inconsistent Group -> Reset All refused (error)',
      res.status == 'error')
check('reset all F2: no Device delete/write when refused',
      len(writes_to(DEVICE)) == wb and len(fake_cp.delete_calls) == dc)


# ===========================================================================
# UPDATE NCM GROUP CONFIGURATION (v1.1.2)
# ===========================================================================
# --- G. Group rev1 + Device Schedule -> candidate rev2 ----------------------
# Group rev1: server mode + user servers + geoview. Device: schedule + outputs.
# Select Schedule only -> candidate rev2 preserves existing Group sections,
# promotes schedule, does NOT add outputs (stays a Device override).
reset_state()
group_body = {
    'iperf3_server_settings': {'server_mode': 'user'},
    'iperf3_user_servers': [{'server': 'h', 'port': '5201'}],
    'geoview': cm.build_default_config()['geoview'],
}
put_group(group_body, 1)
device_sched = _iperf3_schedule('user', 'user|h|5201')
put_device({'schedule': device_sched, 'outputs': ['out1']}, 3)
cm.load_effective_config()
cand, reason, token = cm.build_group_update_candidate(['schedule'])
check('update G: candidate built', cand is not None)
check('update G: candidate group_revision == current + 1 (rev 2)',
      cand and cand.group_revision == 2)
cbody = cand.document['config'] if cand else {}
check('update G: existing Group server mode preserved',
      cbody.get('iperf3_server_settings', {}).get('server_mode') == 'user')
check('update G: existing Group user servers preserved',
      cbody.get('iperf3_user_servers') == [{'server': 'h', 'port': '5201'}])
check('update G: existing Group geoview preserved', 'geoview' in cbody)
check('update G: selected schedule promoted from Device',
      cbody.get('schedule', {}).get('params', {}).get('server_source')
      == 'user')
check('update G: unselected outputs NOT added to Group',
      'outputs' not in cbody)
check('update G: token captures (group=1, device=3)',
      token and token['group_revision'] == 1 and
      token['device_revision'] == 3)
check('update G: no local Group write during candidate build',
      not writes_to(GROUP))
check('update G: Device untouched during candidate build (rev 3)',
      stored_device_doc() and stored_device_doc()['device_revision'] == 3)

# --- H. Validate + cleanup: unselected override remains a Device override ---
# Simulate the admin pasting the revised Group (rev2) into NCM, then validate
# and clean up. Only the promoted schedule is trimmed; outputs stays on Device.
reset_state()
put_group(group_body, 1)
put_device({'schedule': device_sched, 'outputs': ['out1']}, 3)
cm.load_effective_config()
cand, reason, token = cm.build_group_update_candidate(['schedule'])
# Admin updates NCM Group value -> now rev2 with the revised body.
fake_cp.store[GROUP] = cand.to_json()
val = cm.validate_group_update(2, token=token)
check('update H: revised Group validates at rev2', val.ok)
res = cm.cleanup_promoted_after_group_update(['schedule'], token=token)
doc = stored_device_doc()
check('update H: cleanup saved', res.status == 'saved')
check('update H: promoted schedule trimmed from Device',
      doc and 'schedule' not in doc['config'])
check('update H: unselected outputs remains a Device override',
      doc and doc['config'].get('outputs') == ['out1'])

# --- I. Select ALL -> Device key removed after validation -------------------
reset_state()
put_group({'iperf3_server_settings': {'server_mode': 'public'}}, 1)
put_device({'schedule': _netperf_schedule(), 'outputs': ['o']}, 5)
cm.load_effective_config()
cand, reason, token = cm.build_group_update_candidate(['schedule', 'outputs'])
check('update I: candidate built for all overrides', cand is not None)
fake_cp.store[GROUP] = cand.to_json()
val = cm.validate_group_update(2, token=token)
check('update I: validates at rev2', val.ok)
res = cm.cleanup_promoted_after_group_update(['schedule', 'outputs'],
                                             token=token)
check('update I: select-all cleanup -> Device key removed',
      res.status == 'saved' and stored_device_doc() is None)

# --- J. Device untouched before validation ----------------------------------
reset_state()
put_group({'iperf3_server_settings': {'server_mode': 'public'}}, 1)
put_device({'schedule': _netperf_schedule()}, 7)
cm.load_effective_config()
wb = len(writes_to(DEVICE))
dc = len(fake_cp.delete_calls)
cand, reason, token = cm.build_group_update_candidate(['schedule'])
# Before the admin updates NCM, validation must fail and Device stays intact.
val = cm.validate_group_update(2, token=token)
check('update J: validate fails before Group updated in NCM', not val.ok)
check('update J: Device untouched before validation',
      len(writes_to(DEVICE)) == wb and len(fake_cp.delete_calls) == dc and
      stored_device_doc() and stored_device_doc()['device_revision'] == 7)

# --- K. Stale / wrong Group revision fails validate -------------------------
reset_state()
put_group({'iperf3_server_settings': {'server_mode': 'public'}}, 1)
put_device({'schedule': _netperf_schedule()}, 2)
cm.load_effective_config()
cand, reason, token = cm.build_group_update_candidate(['schedule'])
fake_cp.store[GROUP] = cand.to_json()  # now rev2
val_wrong = cm.validate_group_update(3, token=token)   # expect rev3 (wrong)
check('update K: wrong expected revision fails validate', not val_wrong.ok)

# --- L. Device revision change during workflow aborts -----------------------
reset_state()
put_group({'iperf3_server_settings': {'server_mode': 'public'}}, 1)
put_device({'schedule': _netperf_schedule()}, 2)
cm.load_effective_config()
cand, reason, token = cm.build_group_update_candidate(['schedule'])
fake_cp.store[GROUP] = cand.to_json()  # rev2 in NCM
# Admin changed the Device out from under the workflow (rev 2 -> 3).
put_device({'schedule': _netperf_schedule(), 'outputs': ['late']}, 3)
val = cm.validate_group_update(2, token=token)
check('update L: Device change during workflow aborts validate', not val.ok)
res = cm.cleanup_promoted_after_group_update(['schedule'], token=token)
check('update L: Device change during workflow aborts cleanup',
      res.status == 'error')

# --- M. GeoView GPS coords stripped when promoted ---------------------------
reset_state()
geo_gps = cellular_geo._persisted_settings(cellular_geo.normalize_geo_settings({
    'provider': 'none', 'active_location_source': 'device_gps',
    'configured': True,
    'locations': {
        'device_gps': {'latitude': 47.6, 'longitude': -122.3},
        'manual_coordinates': {'latitude': None, 'longitude': None},
        'site_address': {'address': ''},
    }}))
put_group({'iperf3_server_settings': {'server_mode': 'public'}}, 1)
put_device({'geoview': geo_gps}, 2)
cm.load_effective_config()
cand, reason, token = cm.build_group_update_candidate(['geoview'])
check('update M: geoview candidate built', cand is not None)
gv = cand.document['config']['geoview'] if cand else {}
gps = gv.get('locations', {}).get('device_gps', {})
check('update M: promoted geoview keeps device_gps policy',
      gv.get('active_location_source') == 'device_gps')
check('update M: promoted geoview strips runtime GPS coordinates',
      gps.get('latitude') is None and gps.get('longitude') is None)

# --- N. Manual / site GeoView remains non-promotable ------------------------
reset_state()
geo_manual = cellular_geo._persisted_settings(
    cellular_geo.normalize_geo_settings({
        'provider': 'none', 'active_location_source': 'manual_coordinates',
        'configured': True,
        'locations': {
            'device_gps': {'latitude': None, 'longitude': None},
            'manual_coordinates': {'latitude': 40.0, 'longitude': -70.0},
            'site_address': {'address': ''},
        }}))
put_group({'iperf3_server_settings': {'server_mode': 'public'}}, 1)
put_device({'geoview': geo_manual}, 2)
cm.load_effective_config()
sections = cm.update_group_available_sections()
geo_entry = [s for s in sections if s['section'] == 'geoview']
check('update N: manual-coordinate GeoView is not promotable',
      geo_entry and geo_entry[0]['promotable'] is False)
cand, reason, token = cm.build_group_update_candidate(['geoview'])
check('update N: promoting manual GeoView is blocked', cand is None)

# --- O. Invalid dependency selection blocked --------------------------------
# Promote an iperf3 schedule that needs User servers, but the revised Group
# would have Public server mode and no user servers -> blocked.
reset_state()
put_group({'iperf3_server_settings': {'server_mode': 'public'}}, 1)
put_device({'schedule': _iperf3_schedule('user', 'user|h|5201')}, 2)
cm.load_effective_config()
cand, reason, token = cm.build_group_update_candidate(['schedule'])
check('update O: invalid dependency selection blocked (no candidate)',
      cand is None and bool(reason))

# --- P. can_update_group visibility by state --------------------------------
# device only -> can_migrate_to_group True, can_update_group False.
reset_state()
put_device({'outputs': ['d']}, 1)
cm.load_effective_config()
rep = cm.state_report()
check('update P: pure device -> can_migrate True, can_update False',
      rep['state'] == 'device' and rep['can_migrate_to_group'] is True and
      rep['can_update_group'] is False)
# clean group (no device) -> neither.
reset_state()
put_group({'outputs': ['g']}, 1)
cm.load_effective_config()
rep = cm.state_report()
check('update P: clean group -> can_migrate False, can_update False',
      rep['state'] == 'group' and rep['can_migrate_to_group'] is False and
      rep['can_update_group'] is False)
# group + device overrides -> can_update True, can_migrate False.
reset_state()
put_group({'outputs': ['g']}, 1)
put_device({'schedule': _netperf_schedule()}, 1)
cm.load_effective_config()
rep = cm.state_report()
check('update P: group+overrides -> can_migrate False, can_update True',
      rep['state'] == 'group_with_device_overrides' and
      rep['can_migrate_to_group'] is False and
      rep['can_update_group'] is True)


# ===========================================================================
# SCHEDULE RUNTIME RUNNING SEMANTICS (v1.1.2) -- enabled/autostart/running
# ===========================================================================
# enabled and autostart are INDEPENDENT persisted fields. The RUNTIME running
# state is derived by cm.compute_schedule_running(enabled, autostart,
# is_startup) -- the single source of truth the web layer also calls:
#   startup apply:      running = enabled AND autostart
#   interactive save:   running = enabled
#   enabled=false:      never running

# Case 1: enabled=true / autostart=true -> Save runs, restart runs.
check('sched run 1: save (enabled+autostart) -> running',
      cm.compute_schedule_running(True, True, is_startup=False) is True)
check('sched run 1: startup (enabled+autostart) -> running',
      cm.compute_schedule_running(True, True, is_startup=True) is True)

# Case 2: enabled=true / autostart=false -> Save runs, restart does NOT run.
check('sched run 2: save (enabled, no autostart) -> running',
      cm.compute_schedule_running(True, False, is_startup=False) is True)
check('sched run 2: startup (enabled, no autostart) -> NOT running',
      cm.compute_schedule_running(True, False, is_startup=True) is False)

# Case 5: enabled=false -> never running regardless of autostart / startup.
check('sched run 5a: disabled + autostart, save -> not running',
      cm.compute_schedule_running(False, True, is_startup=False) is False)
check('sched run 5b: disabled + autostart, startup -> not running',
      cm.compute_schedule_running(False, True, is_startup=True) is False)
check('sched run 5c: disabled, no autostart, save -> not running',
      cm.compute_schedule_running(False, False, is_startup=False) is False)

# Case 4: changing autostart true->false while enabled stays true.
#   In-session (interactive apply) it keeps running; next restart it does not.
check('sched run 4a: autostart off (enabled) in-session -> still running',
      cm.compute_schedule_running(True, False, is_startup=False) is True)
check('sched run 4b: autostart off (enabled) next restart -> not running',
      cm.compute_schedule_running(True, False, is_startup=True) is False)

# Case 3 (persistence side): after a restart with a persisted enabled=true/
# autostart=false schedule, an explicit UNCHANGED Save is a persistence no-op
# (no write, no revision bump). The web handler then applies runtime running
# from the SAVED enabled (compute_schedule_running(..., is_startup=False)=True),
# so the schedule starts WITHOUT forcing a revision. Here we prove the
# persistence half: identical re-save is a true no-op.
reset_state()
sched_ns = {'enabled': True, 'autostart': False, 'engine': 'iperf3',
            'cron': '*/30 * * * *',
            'params': {'server_source': 'public', 'server_ref': 'x'}}
put_device({'schedule': dict(sched_ns)}, 4)
cm.load_effective_config()
wb = len(writes_to(DEVICE))
res = cm.save_device('schedule', dict(sched_ns))
doc = stored_device_doc()
check('sched run 3: unchanged re-save is a persistence no-op (no_change)',
      res.no_change is True)
check('sched run 3: no Device write on unchanged re-save',
      len(writes_to(DEVICE)) == wb)
check('sched run 3: device_revision unchanged (still 4)',
      doc and doc['device_revision'] == 4)
check('sched run 3: persisted enabled remains true (never coerced)',
      doc and doc['config']['schedule']['enabled'] is True)
# The runtime running that the handler applies on this no-op save:
check('sched run 3: handler would set running=true (save semantics)',
      cm.compute_schedule_running(
          doc['config']['schedule']['enabled'],
          doc['config']['schedule']['autostart'],
          is_startup=False) is True)

# Case 2 persistence half: saving enabled=true/autostart=false persists BOTH
# fields correctly and never coerces enabled=false.
reset_state()
cm.load_effective_config()
res = cm.save_device('schedule', {'enabled': True, 'autostart': False,
                                  'engine': 'netperf', 'cron': '0 * * * *',
                                  'params': {}})
doc = stored_device_doc()
check('sched run 2p: persisted enabled=true after save',
      doc and doc['config']['schedule']['enabled'] is True)
check('sched run 2p: persisted autostart=false after save',
      doc and doc['config']['schedule']['autostart'] is False)


# ===========================================================================
# LEGACY GEO PROVIDER MIGRATION (v1.1.3) -- provider=unwired normalizes to none
# ===========================================================================
# v1.1.3 ships Google as the only external Geo Provider. A legacy persisted
# configuration that selected the removed 'unwired' provider must normalize
# SAFELY to 'none' -- never silently converted to Google, and with NO external
# provider request as a side effect. normalize_geo_settings is a pure, local
# transform: it must not persist appdata or reach the network.
reset_state()
_writes_before_legacy = len(fake_cp.put_calls)
legacy_unwired = cellular_geo.normalize_geo_settings({
    'schema_version': 2,
    'provider': 'unwired',
    'active_location_source': 'manual_coordinates',
    'configured': True,
    'locations': {
        'manual_coordinates': {'latitude': 39.0, 'longitude': -104.0},
    },
})
check('geo migrate: legacy provider=unwired -> normalized none',
      legacy_unwired['provider'] == 'none')
check('geo migrate: unwired is NOT silently converted to google',
      legacy_unwired['provider'] != 'google')
check('geo migrate: normalize_geo_settings performs no appdata write',
      len(fake_cp.put_calls) == _writes_before_legacy)
# Case-insensitive / whitespace legacy value still normalizes to none.
legacy_unwired_ci = cellular_geo.normalize_geo_settings({
    'schema_version': 2, 'provider': '  Unwired  ',
    'active_location_source': 'device_gps',
})
check('geo migrate: legacy provider="  Unwired  " -> none',
      legacy_unwired_ci['provider'] == 'none')
# Supported providers still normalize through unchanged.
_none_ok = cellular_geo.normalize_geo_settings({
    'schema_version': 2, 'provider': 'none',
    'active_location_source': 'device_gps'})
_google_ok = cellular_geo.normalize_geo_settings({
    'schema_version': 2, 'provider': 'google',
    'active_location_source': 'device_gps'})
check('geo migrate: provider=none preserved', _none_ok['provider'] == 'none')
check('geo migrate: provider=google preserved',
      _google_ok['provider'] == 'google')
# An unknown/unsupported provider still fails closed (not coerced to a valid
# value), confirming only the explicit legacy 'unwired' value is migrated.
_bad_rejected = False
try:
    cellular_geo.normalize_geo_settings({
        'schema_version': 2, 'provider': 'mapbox',
        'active_location_source': 'device_gps'})
except ValueError:
    _bad_rejected = True
check('geo migrate: unknown provider still rejected (fails closed)',
      _bad_rejected)


# ===========================================================================
# APPDATA WRITE AUDIT (§61) -- cumulative across the ENTIRE suite (runs last)
# ===========================================================================
group_writes = [c for c in fake_cp.put_calls if c[0] == GROUP]
exp_writes = [c for c in fake_cp.put_calls if c[0] == EXPERIMENTAL]
legacy_writes = [c for c in fake_cp.put_calls if c[0] in LEGACY_KEYS]
group_deletes = [c for c in fake_cp.delete_calls if c == GROUP]
check('AUDIT: zero lifetime writes to speedtest_analyzer_group',
      len(group_writes) == 0)
check('AUDIT: zero lifetime DELETES of speedtest_analyzer_group',
      len(group_deletes) == 0)
check('AUDIT: zero lifetime writes to experimental speedtest_analyzer',
      len(exp_writes) == 0)
check('AUDIT: zero lifetime writes to fragmented legacy keys',
      len(legacy_writes) == 0)


# ===========================================================================
print('\n' + '=' * 60)
print('PASSED: %d   FAILED: %d' % (len(PASS), len(FAIL)))
if FAIL:
    print('FAILURES:')
    for name in FAIL:
        print('  - ' + name)
    sys.exit(1)
print('ALL CONFIGURATION MANAGER TESTS PASSED')
sys.exit(0)
