"""Connectivity tests bound to a single DSDS SIM slot.

Two kinds of test, for two different reasons:

* **Ping** uses the router's own IP Verify subsystem
  (`config/ipverify/ping` + `config/identities/ipverify`), bound to one
  WAN device so the probe is sourced from that slot. The router does the
  work, which is cheaper and more accurate than pinging from Python.

* **HTTP** has no IP Verify equivalent, so the app performs it itself,
  binding the socket's source address to the slot's WAN IP.

Both only ever run against the slot that is currently connected. For
ping that is enforced by enabling only the active slot's identity: a test
bound to a *disconnected* device does not sit idle, it reports a hard
`pass: false` that is indistinguishable from a real outage. For HTTP the
app simply skips slots that are not connected.
"""

import http.client
import socket
import ssl
import time
import urllib.parse

import cp

# Every IP Verify object this app owns is named with this prefix, so it
# can find its own objects again after a restart and leave anything the
# user or another app created alone.
NAME_PREFIX = 'DSDSWV-'

# IP Verify identity names only accept [a-zA-Z0-9_-], so dots and pipes
# from slot keys and IP targets have to be translated.
_NAME_SAFE = '-_'


def identity_name(slot_key, target):
    """Build a router-legal IP Verify identity name for a slot + target."""
    raw = '%s%s-%s' % (NAME_PREFIX, slot_key, target)
    return ''.join(c if (c.isalnum() or c in _NAME_SAFE) else '_'
                   for c in raw)[:30]


def is_managed(name):
    return isinstance(name, str) and name.startswith(NAME_PREFIX)


# ---------------------------------------------------------------------------
# IP Verify ping tests
# ---------------------------------------------------------------------------

def _read_list(path):
    try:
        val = cp.get(path)
    except Exception as e:
        cp.log('Error reading %s: %s' % (path, e))
        return None
    if val is None:
        return None
    return val if isinstance(val, list) else []


def read_ipverify_state():
    """Return (identities, ping_tests) as lists, or (None, None) on failure.

    None means "could not read", which callers must not confuse with
    "nothing configured" - deleting on the strength of a failed read
    would wipe the user's tests.
    """
    identities = _read_list('config/identities/ipverify')
    tests = _read_list('config/ipverify/ping')
    if identities is None or tests is None:
        return None, None
    return identities, tests


def _ping_test_payload(slot, target, cfg):
    """Build a config/ipverify/ping entry bound to one WAN device.

    Binding uses `wan_trigger_field = uid`. The option list for that field
    is type/port/pdn/manufacturer/model/serial/mac/uid/config_id - note
    there is no `sim` option, and both DSDS slots share `port` *and*
    `config_id`, so neither of those can single out a slot. `uid` is the
    only field that reliably can, which is why the app resolves the
    port/sim pair the user configured down to a UID here.

    UIDs survive a DSDS switch (verified), but they are still runtime
    values, so reconcile_ping_tests() rewrites this field whenever the
    resolved UID for a slot changes.
    """
    return {
        'ping_target': target,
        'wan_trigger_field': 'uid',
        'wan_trigger_predicate': 'is',
        # info/uid is the bare hex ('5a3e6e08'), not the 'mdm-' prefixed
        # device key used in status paths.
        'wan_trigger_value': (slot.get('uid') or '').replace('mdm-', ''),
        'pkt_per_try': int(cfg.get('pkt_per_try', 1)),
        'pkt_size': int(cfg.get('pkt_size', 36)),
        'pkt_timeout': int(cfg.get('pkt_timeout', 10)),
        'pkt_interval': int(cfg.get('pkt_interval', 10)),
    }


def _identity_payload(name, test_id, cfg, enabled):
    return {
        'name': name,
        'type': 'ping',
        'test_id': test_id,
        'enabled': bool(enabled),
        'interval': int(cfg.get('interval', 10)),
        'retry_count': int(cfg.get('retry_count', 2)),
        'retry_interval': int(cfg.get('retry_interval', 5)),
        # The router's own log/alert flags fire on every run, not just on
        # change, which floods the log. This app watches status/ipverify
        # and reports transitions itself.
        'log_on_pass': False,
        'log_on_fail': False,
        'alert_on_pass': False,
        'alert_on_fail': False,
    }


def reconcile_ping_tests(desired, active_key):
    """Make the router's IP Verify config match `desired`.

    `desired` maps slot_key -> {'slot': slot, 'targets': [...], 'cfg': {}}
    for slots whose ping test is enabled in app config.

    Only the identity for `active_key` is left enabled. Every other
    managed identity is disabled, which removes its key from
    status/ipverify entirely - that is what makes "the test only runs
    while that SIM is connected" literally true, instead of the test
    running and reporting a misleading failure.

    Returns (owned, verified):
      owned    - dict of (slot_key, target) -> identity _id_ for the
                 tests this app owns, or None if the router config could
                 not be read at all.
      verified - False when a write could not be confirmed, telling the
                 caller to try again rather than cache this state as
                 applied.

    Any write here restarts the router's IP Verify poller, so *every*
    test briefly reverts to '' (no result). Callers must treat that as
    "unknown" and re-arm their settle window; see check_results().
    """
    identities, tests = read_ipverify_state()
    if identities is None:
        return None, False

    tests_by_id = {}
    for idx, test in enumerate(tests):
        if isinstance(test, dict) and test.get('_id_'):
            tests_by_id[test['_id_']] = (idx, test)

    wanted = {}
    for key, entry in desired.items():
        for target in entry['targets']:
            wanted[identity_name(key, target)] = (key, target, entry)

    owned = {}
    stale_identities = []
    stale_tests = []
    seen = set()
    # Cleared when a write could not be confirmed, so the caller retries
    # instead of caching a signature that does not match the router.
    verified = True

    for idx, identity in enumerate(identities):
        if not isinstance(identity, dict):
            continue
        name = identity.get('name', '')
        if not is_managed(name):
            continue
        test_entry = tests_by_id.get(identity.get('test_id'))

        if name not in wanted or name in seen:
            # No longer configured, or a duplicate of one already kept.
            stale_identities.append(idx)
            if test_entry:
                stale_tests.append(test_entry[0])
            continue

        seen.add(name)
        key, target, entry = wanted[name]
        if not test_entry:
            # Identity with no surviving test - rebuild it from scratch.
            stale_identities.append(idx)
            continue

        test_idx, test = test_entry
        want_test = _ping_test_payload(entry['slot'], target, entry['cfg'])
        drift = {k: v for k, v in want_test.items() if test.get(k) != v}
        if drift:
            cp.put('config/ipverify/ping/%d' % test_idx, drift)
            cp.log('Updated IP Verify ping test %s: %s' % (name, drift))

        want_enabled = (key == active_key)
        want_identity = _identity_payload(
            name, identity.get('test_id'), entry['cfg'], want_enabled)
        idrift = {k: v for k, v in want_identity.items()
                  if k != 'enabled' and identity.get(k) != v}
        if idrift:
            cp.put('config/identities/ipverify/%d' % idx, idrift)

        # `enabled` is the field that decides whether this slot's test
        # runs at all, so it is written as a scalar leaf rather than
        # folded into a dict merge, and then read back. A config PUT can
        # report success while applying nothing, and silently trusting it
        # here would leave the standby slot's test armed - which reads as
        # a hard failure and is indistinguishable from a real outage.
        if identity.get('enabled') is not want_enabled:
            cp.put('config/identities/ipverify/%d/enabled' % idx, want_enabled)
            readback = cp.get('config/identities/ipverify/%d/enabled' % idx)
            if bool(readback) is not want_enabled:
                cp.log('Could not set %s enabled=%s (reads back as %r) - '
                       'will retry' % (name, want_enabled, readback))
                verified = False
            else:
                cp.log('IP Verify test %s %s' % (
                    name, 'armed' if want_enabled else 'disarmed'))

        owned[(key, target)] = identity.get('_id_')

    # Arrays shift on delete, so remove highest index first. Identities go
    # before the tests they point at.
    for idx in sorted(set(stale_identities), reverse=True):
        cp.delete('config/identities/ipverify/%d' % idx)
    for idx in sorted(set(stale_tests), reverse=True):
        cp.delete('config/ipverify/ping/%d' % idx)
    if stale_identities:
        cp.log('Removed %d stale IP Verify test(s)' % len(stale_identities))

    for name, (key, target, entry) in wanted.items():
        if name in seen:
            continue
        identity_id = _create_ping_test(
            name, entry['slot'], target, entry['cfg'], key == active_key)
        if identity_id:
            owned[(key, target)] = identity_id
        else:
            verified = False

    return owned, verified


def _create_ping_test(name, slot, target, cfg, enabled):
    """Create one IP Verify ping test plus its identity.

    POST returns the new entry's array *index*, not its UUID, so the
    _id_ has to be read back before it can be referenced.
    """
    try:
        resp = cp.post('config/ipverify/ping', _ping_test_payload(slot, target, cfg))
        if not isinstance(resp, dict) or resp.get('data') is None:
            cp.log('Failed to create ping test for %s: %s' % (target, resp))
            return None
        test_id = cp.get('config/ipverify/ping/%s/_id_' % resp['data'])
        if not test_id:
            cp.log('Could not read _id_ for new ping test %s' % target)
            return None

        resp = cp.post('config/identities/ipverify',
                       _identity_payload(name, test_id, cfg, enabled))
        if not isinstance(resp, dict) or resp.get('data') is None:
            cp.log('Failed to create IP Verify identity %s: %s' % (name, resp))
            return None
        identity_id = cp.get('config/identities/ipverify/%s/_id_' % resp['data'])
        if not identity_id:
            cp.log('Could not read _id_ for new identity %s' % name)
            return None
        cp.log('Created IP Verify ping test %s -> %s (enabled=%s)'
               % (name, target, enabled))
        return identity_id
    except Exception as e:
        cp.log('Error creating IP Verify test for %s: %s' % (target, e))
        return None


def remove_all_managed():
    """Delete every IP Verify object this app created."""
    identities, tests = read_ipverify_state()
    if identities is None:
        return
    tests_by_id = {}
    for idx, test in enumerate(tests):
        if isinstance(test, dict) and test.get('_id_'):
            tests_by_id[test['_id_']] = idx

    drop_identities, drop_tests = [], []
    for idx, identity in enumerate(identities):
        if isinstance(identity, dict) and is_managed(identity.get('name', '')):
            drop_identities.append(idx)
            if identity.get('test_id') in tests_by_id:
                drop_tests.append(tests_by_id[identity['test_id']])
    for idx in sorted(drop_identities, reverse=True):
        cp.delete('config/identities/ipverify/%d' % idx)
    for idx in sorted(drop_tests, reverse=True):
        cp.delete('config/ipverify/ping/%d' % idx)
    if drop_identities:
        cp.log('Removed %d managed IP Verify test(s)' % len(drop_identities))


def read_ping_results(owned):
    """Read status/ipverify for this app's tests.

    Returns slot_key -> {target: True|False|None}, where None means "no
    result": either the identity is disabled (the key is absent from
    status/ipverify entirely) or the router's poller has not produced a
    verdict yet (`pass` is the empty string). Those two cases are both
    "don't know", and neither may be counted as a failure.
    """
    out = {}
    try:
        statuses = cp.get('status/ipverify') or {}
    except Exception as e:
        cp.log('Error reading status/ipverify: %s' % e)
        return out
    if not isinstance(statuses, dict):
        return out

    for (key, target), identity_id in owned.items():
        entry = statuses.get(identity_id)
        value = entry.get('pass') if isinstance(entry, dict) else None
        out.setdefault(key, {})[target] = value if isinstance(value, bool) else None
    return out


# ---------------------------------------------------------------------------
# HTTP tests (performed by the app)
# ---------------------------------------------------------------------------

def http_check_with_retries(url, method='GET', timeout=2.0, source_ip=None,
                            expect_status=None, verify_tls=False,
                            retry_count=0, retry_interval=2.0,
                            stop_event=None):
    """Run http_check, retrying a failure before reporting it.

    Mirrors what IP Verify does for ping: a single lost request or a
    momentary DNS hiccup should not be reported as a failure. Only when
    every attempt has failed does this return False, which is what makes
    one failing verdict enough to act on.

    Returns (ok, detail) with `attempts` added to detail. Never raises.
    """
    attempts = max(1, int(retry_count) + 1)
    detail = {}
    for attempt in range(attempts):
        ok, detail = http_check(url, method, timeout, source_ip,
                                expect_status, verify_tls)
        detail['attempts'] = attempt + 1
        if ok:
            return True, detail
        if attempt < attempts - 1:
            # Honour a shutdown request rather than sleeping through it.
            if stop_event is not None:
                if stop_event.wait(retry_interval):
                    detail['error'] = 'cancelled during retry'
                    return False, detail
            else:
                time.sleep(retry_interval)
    detail['attempts'] = attempts
    return False, detail


def http_check(url, method='GET', timeout=2.0, source_ip=None,
               expect_status=None, verify_tls=False):
    """Fetch `url` with GET or HEAD and report whether it succeeded.

    `source_ip` binds the socket's source address so the request leaves
    through one specific WAN device. On a DSDS modem only one slot is
    connected at a time, so the active slot normally owns the default
    route anyway; binding still matters on a router with more than one
    physical modem, and it makes the result unambiguous either way.

    `expect_status` is a collection of acceptable HTTP status codes. When
    empty, any 2xx or 3xx counts as reachable - the point is proving the
    path works, not validating the response body.

    TLS certificates are not verified by default: this is a reachability
    probe, and a stale CA bundle or a captive portal would otherwise show
    up as a connectivity failure. Set verify_tls when the identity of the
    endpoint actually matters.

    Returns (ok, detail_dict). Never raises.
    """
    started = time.time()
    detail = {'url': url, 'method': method, 'source_ip': source_ip,
              'status': None, 'ms': None, 'error': None}
    try:
        parts = urllib.parse.urlsplit(url if '://' in url else 'http://' + url)
        scheme = (parts.scheme or 'http').lower()
        if scheme not in ('http', 'https'):
            detail['error'] = 'unsupported scheme %r' % scheme
            return False, detail
        host = parts.hostname
        if not host:
            detail['error'] = 'no host in URL'
            return False, detail
        port = parts.port or (443 if scheme == 'https' else 80)
        path = parts.path or '/'
        if parts.query:
            path = '%s?%s' % (path, parts.query)

        method = (method or 'GET').upper()
        if method not in ('GET', 'HEAD'):
            detail['error'] = 'unsupported method %r' % method
            return False, detail

        # (ip, 0) lets the kernel pick the source port.
        source = (source_ip, 0) if source_ip else None
        timeout = float(timeout)

        if scheme == 'https':
            if verify_tls:
                context = ssl.create_default_context()
            else:
                context = ssl._create_unverified_context()
            conn = http.client.HTTPSConnection(
                host, port, timeout=timeout, source_address=source,
                context=context)
        else:
            conn = http.client.HTTPConnection(
                host, port, timeout=timeout, source_address=source)

        try:
            conn.request(method, path, headers={
                'User-Agent': 'dsds_wan_verify',
                'Accept': '*/*',
                # Never reuse a socket: a pooled connection could predate
                # the current SIM slot and would not prove anything.
                'Connection': 'close',
            })
            resp = conn.getresponse()
            detail['status'] = resp.status
            # Drain HEAD-less bodies so the socket closes cleanly, but cap
            # the read - this runs on a router with limited RAM and the
            # body is not inspected.
            if method == 'GET':
                resp.read(2048)
        finally:
            try:
                conn.close()
            except Exception:
                pass

        detail['ms'] = int((time.time() - started) * 1000)
        if expect_status:
            ok = detail['status'] in set(int(s) for s in expect_status)
            if not ok:
                detail['error'] = 'status %s not in %s' % (
                    detail['status'], sorted(set(int(s) for s in expect_status)))
        else:
            ok = 200 <= (detail['status'] or 0) < 400
            if not ok:
                detail['error'] = 'status %s' % detail['status']
        return ok, detail

    except socket.timeout:
        detail['ms'] = int((time.time() - started) * 1000)
        detail['error'] = 'timeout after %ss' % timeout
        return False, detail
    except Exception as e:
        detail['ms'] = int((time.time() - started) * 1000)
        detail['error'] = '%s: %s' % (type(e).__name__, e)
        return False, detail
