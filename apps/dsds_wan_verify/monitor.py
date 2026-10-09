"""Monitoring loop and failover decision logic.

Responsibilities, in order of each tick:

1. Discover DSDS slots.
2. Suppress everything while a switch is in flight or settling.
3. Keep the router's IP Verify config in sync, with only the connected
   slot's test enabled.
4. Run HTTP tests for the connected slot, off the main thread.
5. Evaluate the connected slot's health and switch if it has failed.

Every discovered slot is monitored; there is no per-slot opt-out,
because excluding a slot would leave the app nowhere to move to.

Failover is always armed. Each slot carries its own tests, and the app
moves off whichever slot is connected when that slot's own tests fail.

Each slot has **one** signal threshold, meaning "the level at which this
slot is no longer worth using", and it does three jobs:

1. **Failover** - while the slot is connected, drop below it for
   `signal_fail_threshold` consecutive readings and the app moves away.
2. **Destination gate** - the app will not switch to a slot on signal
   alone unless that slot *demonstrates* it clears its own threshold.
   A slot reporting none of the metrics its threshold is set on fails
   the gate: an unverifiable threshold is not a satisfied threshold, and
   without that rule a slot with no coverage at all would look like an
   improvement over a merely weak one. When neither slot clears its own
   threshold there is no better place to be, so `priority` decides where
   traffic sits. That is what stops the app bouncing between two weak
   slots.
3. **Failback gate** - with `signal_failback_enabled`, the app returns to
   a strictly higher priority slot once that slot comes back above its
   own threshold.

Jobs 2 and 3 both read "no reading" as a reason *not* to move, while job
1 reads it as a reason not to leave. That asymmetry is deliberate: the
app acts on evidence in whichever direction keeps traffic where it is.

The deliberate asymmetry is in what *can* be tested. Connectivity (ping
and HTTP) is only measurable on the slot that is connected, while signal
is measurable on both, because a DSDS modem keeps reporting live
diagnostics for the standby slot. That is what lets the app check the
destination before committing to a ~30 second switch.

That asymmetry is also the one flap the signal threshold cannot close.
A slot with excellent signal and a broken link looks permanently ready
to return to, and its connectivity tests cannot run while it is on
standby to say otherwise. So a failover caused by **connectivity**
starts a `failback_holdoff_seconds` timer on the slot being left, and no
proactive failback to it happens until that expires. A failover caused
by signal or a lost connection sets no timer: in those cases the
threshold is a live measurement that already gates the return properly.

That timer only exists on the slot the app would fail back *to*, which
with two slots is the preferred one. Leaving the secondary moves traffic
to the preferred slot, and nothing pulls it back off a higher-priority
slot on its own, so the secondary has no return to hold off.

The timer is also **overridden** the moment the slot carrying traffic
fails its own connectivity tests. The holdoff is an argument about
*uncertainty* - do not return to a slot whose link cannot be checked
from standby - and that argument only stands while the current slot
works. Once both slots have failed, waiting means parking traffic on a
link known to be broken in order to avoid one merely unverified, so the
app moves anyway. With neither SIM in service it will alternate roughly
every settle + ~30s; that is the intended behavior, because it means
whichever slot regains service first is picked up within a couple of
minutes instead of after the full holdoff.
"""

import threading
import time

import appconfig
import cp
import dsds
import verify

HISTORY_LIMIT = 100
MEMORY_CHECK_INTERVAL = 60

# Fixed monitoring cadence. Each test confirms its own failures through
# its own retries, so this is just how often results are read, and 2s
# keeps reaction tight relative to the ~30s a switch itself costs.
POLL_INTERVAL = 2

# How long no slot may report 'connected' before it counts as a real
# outage rather than the brief gap in the middle of a SIM switch.
NO_ACTIVE_GRACE = 20

# How often to check whether the stored config changed underneath the
# app. Config is normally reloaded on the spot when the web UI saves it,
# but appdata can also be edited from the router UI, pushed by an NCM
# group, deleted outright, or written over REST - none of which call back
# into the app. Without this poll the app would keep running the config
# it read at startup and the web UI would keep showing it, which looks
# exactly like the save silently failing.
#
# Only the raw appdata string is fetched for the comparison, and the
# config is reparsed only when it actually differs, so this costs one
# small read every interval.
CONFIG_CHECK_INTERVAL = 10


def _describe_failing(failing):
    """Render (metric, value_or_None, threshold) triples for a message.

    A value of None means the slot is not reporting that metric at all,
    which reads very differently from a measured shortfall.
    """
    return ', '.join(
        '%s %s < %g' % (metric, 'not reported' if value is None else '%g' % value,
                        threshold)
        for metric, value, threshold in failing)


class Monitor(object):
    def __init__(self, stop_event=None):
        self.lock = threading.RLock()
        # Lets a worker thread abandon its retry sleep on shutdown.
        self.stop_event = stop_event or threading.Event()
        # The raw appdata text the current config was parsed from, kept
        # so an external change can be spotted by comparison rather than
        # by reparsing and diffing the whole structure.
        self._conf_raw = appconfig.read_raw() or ''
        self.conf = appconfig.load_from(self._conf_raw)
        self._last_conf_check = time.time()
        self.slots = {}
        # (slot_key, target) -> identity _id_ for the IP Verify tests
        # confirmed enabled on the router. NOT every test the app owns -
        # a disabled test's stale verdict lingers in status/ipverify, so
        # results are only ever read for what is actually armed.
        self.armed_tests = {}
        self.ping_results = {}
        self.http_results = {}
        self._http_running = set()
        self._http_next_run = {}
        self.signal_fail_counts = {}
        # Consecutive readings a higher-priority slot has been above its
        # failback minimum, keyed by that slot.
        self.failback_ok_counts = {}
        self.last_switch_ts = 0.0
        self.switch_count = 0
        self.settle_until = 0.0
        # Flap guard for the one case signal cannot judge: the app left a
        # slot because its connectivity tests failed, and that slot's
        # signal still looks fine, so nothing would stop it going
        # straight back. Holds one slot key and a deadline.
        self.failback_hold_slot = None
        self.failback_hold_until = 0.0
        # When the currently connected slot became the active one. Test
        # results older than this belong to a different slot.
        self.active_since = 0.0
        self.history = []
        self.status_text = 'starting'
        self.switch_lock = threading.Lock()
        self.switching = False
        self._last_active = None
        self._last_memory_check = 0.0
        self._warned_metrics = set()
        self._reconcile_signature = None
        self._no_active_since = None
        self._no_active_logged = False

    # -- helpers ---------------------------------------------------------

    def event(self, text, level='info'):
        entry = {'ts': time.time(), 'text': text, 'level': level}
        with self.lock:
            self.history.append(entry)
            if len(self.history) > HISTORY_LIMIT:
                del self.history[:len(self.history) - HISTORY_LIMIT]
        cp.log(text)

    def _label(self, slot_key):
        """Friendly label for a slot key, usable after the slot is gone.

        dsds.slot_label() renders '? / ?' for an unknown slot, which is
        worse than the key itself in a message about a slot that has been
        removed, so fall back to the key when it is not discovered.
        """
        slot = self.slots.get(slot_key)
        return dsds.slot_label(slot) if slot else str(slot_key)

    def _priority(self, slot_key):
        """Configured priority for a slot. Lower number = higher priority."""
        try:
            return int(appconfig.slot_config(self.conf, slot_key)['priority'])
        except (TypeError, ValueError, KeyError):
            return 1

    def _is_higher_priority(self, candidate_key, than_key):
        """True when moving candidate -> than counts as a *failback*.

        Only a move to a strictly higher priority (lower number) slot is a
        failback. Equal priority means no preference, so neither direction
        is gated on the failback minimum.
        """
        return self._priority(candidate_key) < self._priority(than_key)

    def _is_preferred(self, slot_key):
        """True when this slot outranks its own sibling outright.

        Compared against the sibling rather than against every slot on
        the router, because a router can host more than one DSDS modem
        (`int1`, `int2`) and each pair is decided independently - a
        global ranking would let one modem's slot suppress another's.

        A slot with no sibling has nothing to be preferred over, and
        equal numbers mean no preference, which is what leaves the
        failback minimum unread on both slots.
        """
        sibling = (self.slots.get(slot_key) or {}).get('sibling')
        if not sibling or sibling not in self.slots:
            return False
        return self._is_higher_priority(slot_key, sibling)

    def reload_config(self):
        """Re-read config from appdata right now.

        Called after the web UI saves. The raw text is kept alongside the
        parsed config so _maybe_reload_config() does not then see its own
        write as an external change and reload a second time.
        """
        raw = appconfig.read_raw()
        with self.lock:
            if raw is not None:
                self._conf_raw = raw
            self.conf = appconfig.load_from(self._conf_raw)
            self._last_conf_check = time.time()
            # Force the next tick to re-push IP Verify config.
            self._reconcile_signature = None
        return self.conf

    def _maybe_reload_config(self):
        """Pick up a config change made outside the app.

        Appdata can be edited from the router UI, pushed by an NCM group,
        written over REST, or deleted - none of which tell the app. Only
        the stored string is read here; the config is reparsed solely
        when it differs, because reparsing also clears the IP Verify
        signature and that forces a rewrite of the router's test config.
        """
        now = time.time()
        if now - self._last_conf_check < CONFIG_CHECK_INTERVAL:
            return
        self._last_conf_check = now
        raw = appconfig.read_raw()
        # None means the read failed, which is not the same as "nothing
        # is stored" - treating it as empty would drop every slot back to
        # defaults over a transient error.
        if raw is None or raw == self._conf_raw:
            return
        with self.lock:
            self._conf_raw = raw
            self.conf = appconfig.load_from(raw)
            self._reconcile_signature = None
        if raw.strip():
            self.event('Configuration changed outside the web UI; reloaded '
                       'from appdata')
        else:
            self.event('The %s appdata entry is gone, so every SIM slot is '
                       'back on the app\'s built-in defaults'
                       % appconfig.APPDATA_FIELD, 'warn')

    # -- evaluation ------------------------------------------------------

    def _ping_verdict(self, key, cfg):
        """Aggregate a slot's ping targets into True/False/None.

        None means no usable result: either the test is disabled because
        the slot is not connected, or the router has not produced a
        verdict yet. Unknown is never counted as a failure.
        """
        if not cfg.get('ping_enabled') or not cfg.get('ping_targets'):
            return None
        results = self.ping_results.get(key) or {}
        values = [results.get(t) for t in cfg['ping_targets']]
        known = [v for v in values if v is not None]
        if not known:
            return None
        if cfg.get('ping_fail_mode') == 'any':
            return all(known)
        return any(known)

    def _http_verdict(self, key, cfg):
        if not cfg.get('http_enabled') or not cfg.get('http_url'):
            return None
        entry = self.http_results.get(key)
        if not entry or entry.get('ok') is None:
            return None
        # A result captured before this slot became the active one says
        # nothing about the slot that is connected now. Compare against
        # when the slot went active, NOT against settle_until - a result
        # taken during the settle window was still sourced from this
        # slot's own IP, so it is valid evidence about this slot.
        if entry.get('ts', 0) < self.active_since:
            return None
        # Ignore a result old enough that the link could have changed
        # under it, so a dead worker thread cannot pin a stale verdict.
        max_age = max(3 * int(cfg.get('http_interval') or 30), 120)
        if time.time() - entry.get('ts', 0) > max_age:
            return None
        return bool(entry['ok'])

    def _compare_signal(self, slot, thresholds):
        """Compare a slot's live metrics against a threshold set.

        Returns (breaches, unknown) where breaches is a list of
        (metric, value, threshold) and unknown lists metrics the slot is
        not currently reporting. A metric that is not reported cannot be
        judged, so it is never counted as a breach.
        """
        breaches, unknown = [], []
        signal = slot.get('signal') or {}
        for metric, threshold in (thresholds or {}).items():
            if metric not in signal:
                unknown.append(metric)
                continue
            if signal[metric] < threshold:
                breaches.append((metric, signal[metric], threshold))
        return breaches, unknown

    def _signal_breaches(self, slot, cfg):
        """Is this slot below its signal threshold right now?

        The same comparison whichever job it is doing - deciding to leave
        the connected slot, or deciding whether the sibling is any better.
        One threshold per slot means these can never disagree.
        """
        if not cfg.get('signal_enabled'):
            return [], []
        return self._compare_signal(slot, cfg.get('signal_thresholds'))

    def _has_signal_test(self, cfg):
        return bool(cfg.get('signal_enabled') and cfg.get('signal_thresholds'))

    def _meets_threshold(self, slot, thresholds):
        """Is this slot at or above its threshold, on what it reports?

        Judged on the metrics the slot actually reports: every reported
        one must clear the threshold, and at least one must be reported.
        Requiring *all* configured metrics would make this unsatisfiable
        in normal use, because a slot only reports one metric family at a
        time - setting both LTE and 5G values (which is the documented
        advice, since the radio can switch between them) would otherwise
        guarantee failure.

        Returns (ok, failing) where failing entries are
        (metric, value_or_None, threshold).
        """
        breaches, unknown = self._compare_signal(slot, thresholds)
        if len(unknown) == len(thresholds):
            # None of the configured metrics are reported, so there is no
            # evidence either way. An unverifiable threshold is not a
            # satisfied threshold.
            return False, [(m, None, thresholds[m]) for m in unknown]
        return (not breaches), breaches

    def _signal_allows_failback(self, slot, cfg):
        """Is this slot back above its threshold, enough to return to?

        The same threshold that would push the app off this slot, read
        from the other side. One number, so "strong enough to come back
        to" and "not so weak that I would leave" cannot contradict each
        other, which is what made the old three-way split so easy to
        misconfigure.

        Only consulted when this slot is a strictly higher priority than
        the one connected, because that is the only direction "fail back"
        means anything.
        """
        if not cfg.get('signal_failback_enabled'):
            return True, []
        thresholds = cfg.get('signal_thresholds') or {}
        if not thresholds or not cfg.get('signal_enabled'):
            return True, []
        return self._meets_threshold(slot, thresholds)

    # -- failback holdoff ------------------------------------------------

    def _hold_failback(self, slot_key):
        """Start the post-connectivity-failure wait on `slot_key`.

        Called only for a failover the connectivity tests caused. A
        failover on signal or a lost connection deliberately sets no
        timer, because the threshold is then a live measurement that
        already decides whether returning makes sense.

        Only ever armed on a slot the app would proactively fail back
        to - with two slots, the preferred one. Leaving the *secondary*
        puts traffic on the preferred slot, and nothing moves it back off
        a higher-priority slot on its own, so a timer there would count
        down against a return that cannot happen and would read on the
        dashboard as though it were holding something back.
        """
        if not self._is_preferred(slot_key):
            return
        seconds = 0
        try:
            seconds = int(appconfig.slot_config(
                self.conf, slot_key)['failback_holdoff_seconds'])
        except (TypeError, ValueError, KeyError):
            seconds = 0
        if seconds <= 0:
            return
        with self.lock:
            self.failback_hold_slot = slot_key
            self.failback_hold_until = time.time() + seconds
        # An event, not just a log line: this is the one piece of state
        # that can keep traffic on the secondary SIM for an hour, so it
        # needs to be visible in the UI's Event Log, not only in the
        # router's system log.
        self.event('Holding off failback to %s for %ds: the app left it '
                   'because its connectivity tests failed, and signal alone '
                   'cannot tell whether that is fixed'
                   % (self._label(slot_key), seconds))

    def _clear_failback_hold(self, why=None):
        with self.lock:
            held = self.failback_hold_slot
            self.failback_hold_slot = None
            self.failback_hold_until = 0.0
        if held and why:
            self.event('Cleared the failback holdoff on %s: %s'
                       % (self._label(held), why))

    def _failback_hold_remaining(self, slot_key):
        """Seconds left before `slot_key` may be failed back to."""
        if self.failback_hold_slot != slot_key:
            return 0
        return max(0, int(self.failback_hold_until - time.time()))

    # What an unreported metric means, per context. The two directions
    # are not symmetric: the app will not leave a slot on a metric it
    # cannot read, and will not move to one either, so the same missing
    # reading is ignored in one context and decisive in the other.
    _UNKNOWN_EFFECT = {
        'failover': 'not counted as a breach, so it will not move the app '
                    'off this slot',
        'destination': 'so this slot cannot show it is any better, and the '
                       'app will not switch to it on signal alone',
        'failback': 'so this slot cannot show it has recovered, and the app '
                    'will not fail back to it on signal alone',
    }

    def _warn_unknown_metrics(self, key, metrics, context='failover'):
        for metric in metrics:
            token = (key, metric, context)
            if token in self._warned_metrics:
                continue
            self._warned_metrics.add(token)
            slot = self.slots.get(key) or {}
            cp.log('%s: %s %s threshold configured but the slot is not '
                   'reporting that metric (radio is %s) - %s'
                   % (key, metric, context,
                      slot.get('service_detail') or slot.get('service_type')
                      or 'unknown',
                      self._UNKNOWN_EFFECT.get(context, 'ignoring it')))

    # -- switching -------------------------------------------------------

    def do_switch(self, reason, manual=False, hold_failback=False):
        """Trigger a DSDS SIM switch. Returns (ok, message).

        Serialized by switch_lock so a manual switch from the UI cannot
        race the monitor loop.

        `hold_failback` starts the failback holdoff on the slot being
        left. Set it only when the connectivity tests are what caused the
        move, since that is the case signal cannot judge from standby.
        """
        if not self.switch_lock.acquire(blocking=False):
            return False, 'a switch is already in progress'
        try:
            slots = dsds.discover_slots()
            with self.lock:
                self.slots = slots
            if dsds.switch_in_progress(slots):
                return False, 'the modem is already switching slots'
            current = dsds.active_slot(slots)
            if not current:
                return False, 'no slot is currently connected, so there is ' \
                              'no connected device to request the switch on'
            target_key = current.get('sibling')
            target = slots.get(target_key) if target_key else None
            if not target:
                return False, 'no sibling slot found on port %s' % current.get('port')
            if target.get('nosim'):
                return False, 'sibling slot %s has no SIM' % dsds.slot_label(target)

            self.switching = True
            self.status_text = 'switching to %s' % dsds.slot_label(target)
            self.event('%s switching from %s to %s: %s'
                       % ('Manual' if manual else 'Automatic',
                          dsds.slot_label(current), dsds.slot_label(target),
                          reason), 'warn')

            ok, message = dsds.request_switch(current)
            if not ok:
                self.switching = False
                self.event('Switch request failed: %s' % message, 'error')
                return False, message

            now = time.time()
            with self.lock:
                self.last_switch_ts = now
                self.switch_count += 1
                self.signal_fail_counts = {}
                self.failback_ok_counts = {}
                self.http_results = {}
                self._http_next_run = {}

            ok, elapsed, slots = dsds.wait_for_switch(current['key'])
            new_active = dsds.active_slot(slots)
            settle = appconfig.slot_config(
                self.conf, new_active['key'])['settle_seconds'] \
                if new_active else 0
            with self.lock:
                self.slots = slots
                self.settle_until = time.time() + settle
                self.switching = False
            if ok and new_active:
                # Record the new slot here so the next tick does not also
                # report it as an externally-driven slot change. Because
                # that suppresses the tick's bookkeeping, active_since has
                # to be stamped here too, or HTTP results on the new slot
                # would be measured against the previous slot's start.
                self._last_active = new_active['key']
                with self.lock:
                    self.active_since = time.time()
                # Any hold on the slot just arrived at is moot - the app
                # is on it, so there is nothing to fail back to. Set a
                # fresh hold on the one being left if connectivity is
                # what drove the move. A manual switch clears instead:
                # the operator has overridden the guard explicitly.
                if self.failback_hold_slot == new_active['key'] or manual:
                    self._clear_failback_hold(
                        'switched to it manually' if manual
                        else 'the app is now on it')
                if hold_failback and not manual:
                    self._hold_failback(current['key'])
                self.event('Switch completed in %.0fs: now on %s'
                           % (elapsed, dsds.slot_label(new_active)))
                self.status_text = 'settling on %s' % dsds.slot_label(new_active)
                return True, 'switched to %s in %.0fs' % (
                    dsds.slot_label(new_active), elapsed)

            self.event('Switch did not complete within %.0fs; no slot is '
                       'connected' % elapsed, 'error')
            self.status_text = 'switch timed out'
            return False, 'switch did not complete within %.0fs' % elapsed
        finally:
            self.switching = False
            self.switch_lock.release()

    # -- HTTP tests ------------------------------------------------------

    def _run_http(self, key, cfg, source_ip):
        """Run one HTTP check in a worker thread.

        Off the main loop because an HTTP timeout (2s by default) would
        otherwise stall discovery and the failover decision for as long
        as the request hangs.
        """
        def work():
            ok, detail = verify.http_check_with_retries(
                url=cfg['http_url'],
                method=cfg['http_method'],
                timeout=cfg['http_timeout'],
                source_ip=source_ip,
                expect_status=cfg['http_expect_status'],
                verify_tls=cfg['http_verify_tls'],
                retry_count=cfg['http_retry_count'],
                retry_interval=cfg['http_retry_interval'],
                stop_event=self.stop_event,
            )
            with self.lock:
                detail['ok'] = ok
                detail['ts'] = time.time()
                self.http_results[key] = detail
                self._http_running.discard(key)
                self._http_next_run[key] = time.time() + cfg['http_interval']
        try:
            thread = threading.Thread(target=work, name='http-%s' % key)
            thread.daemon = True
            thread.start()
        except Exception as e:
            with self.lock:
                self._http_running.discard(key)
            cp.log('Could not start HTTP test thread for %s: %s' % (key, e))

    def _maybe_run_http(self, slot, cfg):
        key = slot['key']
        if not cfg.get('http_enabled') or not cfg.get('http_url'):
            return
        # Only the connected slot: a standby slot has no IP to source
        # from and no route, so the test could only fail misleadingly.
        if not slot.get('connected'):
            return
        source_ip = slot.get('ip_address')
        if not source_ip:
            return
        with self.lock:
            if key in self._http_running:
                return
            if time.time() < self._http_next_run.get(key, 0):
                return
            self._http_running.add(key)
        self._run_http(key, cfg, source_ip)

    # -- IP Verify sync --------------------------------------------------

    def _sync_ipverify(self, active_key):
        """Push the desired IP Verify config, but only when it changed.

        Every write restarts the router's IP Verify poller and blanks all
        results, so this is gated on a signature of the desired state to
        avoid rewriting identical config on every tick.
        """
        desired = {}
        for key, slot in self.slots.items():
            cfg = appconfig.slot_config(self.conf, key)
            if not cfg.get('ping_enabled'):
                continue
            if not cfg.get('ping_targets') or not slot.get('uid'):
                continue
            desired[key] = {
                'slot': slot,
                'targets': cfg['ping_targets'],
                'cfg': {
                    'interval': cfg['ping_interval'],
                    'retry_count': cfg['ping_retry_count'],
                    'retry_interval': cfg['ping_retry_interval'],
                    'pkt_size': cfg['ping_pkt_size'],
                    'pkt_per_try': cfg['ping_pkt_per_try'],
                    'pkt_timeout': cfg['ping_pkt_timeout'],
                },
            }

        signature = (active_key, tuple(sorted(
            (key, entry['slot'].get('uid'), tuple(entry['targets']),
             tuple(sorted(entry['cfg'].items())))
            for key, entry in desired.items())))

        if signature != self._reconcile_signature:
            armed, verified = verify.reconcile_ping_tests(desired, active_key)
            if armed is not None:
                with self.lock:
                    self.armed_tests = armed
                # Only cache the signature once the router confirms the
                # writes landed. Caching an unapplied state would leave
                # the standby slot's test armed forever, since nothing
                # would ever retry.
                if verified:
                    self._reconcile_signature = signature
                    # A config write blanks every result; give the poller
                    # time to produce real verdicts before trusting them.
                    worst = max(
                        [e['cfg']['interval'] +
                         e['cfg']['retry_count'] * e['cfg']['retry_interval']
                         for e in desired.values()] or [0])
                    self.settle_until = max(
                        self.settle_until, time.time() + worst + 2)
        elif not desired:
            with self.lock:
                self.armed_tests = {}

        # armed_tests holds only the identities confirmed enabled on the
        # router, which with DSDS is at most the connected slot's. The
        # standby slot therefore gets no entry and reads as "no result" -
        # necessary because the router leaves a disabled test's last
        # verdict sitting in status/ipverify, so reading it would report
        # a disconnected slot's ping as passing.
        results = verify.read_ping_results(self.armed_tests)
        with self.lock:
            self.ping_results = results

    # -- memory guard ----------------------------------------------------

    def _check_memory(self):
        now = time.time()
        if now - self._last_memory_check < MEMORY_CHECK_INTERVAL:
            return
        self._last_memory_check = now
        try:
            mem = cp.get('status/system/memory') or {}
            total = mem.get('memtotal')
            avail = mem.get('memavailable')
            if not total or not avail:
                return
            pct = 100.0 * avail / total
            if pct < 10:
                # The router restarts the app (auto_start=true), which
                # reclaims everything. Logged rather than alerted - this
                # app does not send NCM alerts.
                cp.log('Available memory %.0f%% - exiting so the router '
                       'restarts this app and reclaims it' % pct)
                raise SystemExit(0)
            if pct < 20:
                cp.log('Low memory (%.0f%% available) - trimming history' % pct)
                with self.lock:
                    del self.history[:max(0, len(self.history) - 20)]
                    self._warned_metrics.clear()
        except SystemExit:
            raise
        except Exception as e:
            cp.log('Memory check error: %s' % e)

    # -- main tick -------------------------------------------------------

    def tick(self):
        # First, so an external config change is in effect for the rest
        # of this tick rather than one poll later.
        self._maybe_reload_config()

        slots = dsds.discover_slots()
        with self.lock:
            self.slots = slots

        if not slots:
            self.status_text = 'no DSDS modem found'
            return

        # Drop state for slots that no longer exist, so the dicts cannot
        # grow without bound across SIM swaps and reboots.
        live = set(slots)
        with self.lock:
            for store in (self.signal_fail_counts, self.failback_ok_counts,
                          self.http_results, self._http_next_run):
                for key in [k for k in store if k not in live]:
                    del store[key]

        if self.failback_hold_slot:
            if self.failback_hold_slot not in live:
                self._clear_failback_hold('the slot is no longer present')
            elif not self._is_preferred(self.failback_hold_slot):
                # The preference changed under an active hold. The app
                # does not fail back to a slot that no longer outranks
                # its sibling, so the countdown now guards nothing.
                self._clear_failback_hold(
                    'it is no longer the preferred slot, so there is no '
                    'proactive failback to it to hold off')
            elif time.time() >= self.failback_hold_until:
                self._clear_failback_hold('the wait expired')

        if dsds.switch_in_progress(slots):
            self.status_text = 'SIM switch in progress'
            return
        if self.switching:
            return

        active = dsds.active_slot(slots)
        active_key = active['key'] if active else None

        if active_key is None:
            # Mid-switch there is a ~1s window where the outgoing slot has
            # already gone to 'standby' and the incoming one has not yet
            # reached 'connecting', so neither reports a switching
            # summary. Treating that blink as a slot change logs a
            # misleading event and needlessly resets per-slot state, so
            # require it to persist before believing it.
            if self._no_active_since is None:
                self._no_active_since = time.time()
            if time.time() - self._no_active_since < NO_ACTIVE_GRACE:
                self.status_text = 'slot transition in progress'
                return
            if not self._no_active_logged:
                self._no_active_logged = True
                self.event('No SIM slot is connected; waiting for NCOS to '
                           'bring one up', 'error')
        else:
            self._no_active_since = None
            self._no_active_logged = False

            if active_key != self._last_active:
                # A slot change the app did not initiate (NCOS, a reboot,
                # or a manual switch elsewhere) still needs a settle
                # window, taken from the incoming slot's own config.
                if self._last_active is not None:
                    self.event('Active slot changed to %s'
                               % dsds.slot_label(active))
                    with self.lock:
                        self.settle_until = max(
                            self.settle_until,
                            time.time() + appconfig.slot_config(
                                self.conf, active_key)['settle_seconds'])
                # Something outside the app put traffic back on the held
                # slot (NCOS, a reboot, an admin elsewhere). There is
                # nothing left to fail back to, so the guard is spent.
                if self.failback_hold_slot == active_key:
                    self._clear_failback_hold('it is the connected slot again')
                self._last_active = active_key
                with self.lock:
                    self.active_since = time.time()
                    self.signal_fail_counts = {}
                    self.failback_ok_counts = {}
                    # Results captured on the previous slot are
                    # meaningless now, and the new slot should be probed
                    # promptly rather than waiting out the old interval.
                    self.http_results = {}
                    self._http_next_run = {}

        self._sync_ipverify(active_key)

        for slot in slots.values():
            self._maybe_run_http(slot, appconfig.slot_config(self.conf, slot['key']))

        self._check_memory()

        if not active:
            self.status_text = 'no slot connected'
            # dsds_switch has to be sent to a connected device, so with
            # nothing connected there is no way to act. NCOS drives
            # recovery here.
            return

        if time.time() < self.settle_until:
            self.status_text = 'settling on %s (%ds left)' % (
                dsds.slot_label(active), int(self.settle_until - time.time()))
            return

        self._evaluate(active, slots)

    def _evaluate(self, active, slots):
        key = active['key']
        cfg = appconfig.slot_config(self.conf, key)

        ping_ok = self._ping_verdict(key, cfg)
        http_ok = self._http_verdict(key, cfg)

        verdicts = [v for v in (ping_ok, http_ok) if v is not None]
        if not verdicts:
            conn_failed = False
        elif cfg.get('test_combine') == 'any':
            # Only call the slot down when nothing can get through.
            conn_failed = not any(verdicts)
        else:
            # Default: every enabled test type has to pass. An HTTP test
            # is usually added precisely to catch what ping cannot - a
            # captive portal, broken DNS, or a path that drops anything
            # other than ICMP - so a failing HTTP test must count even
            # while ping still succeeds.
            conn_failed = not all(verdicts)

        breaches, unknown = self._signal_breaches(active, cfg)
        self._warn_unknown_metrics(key, unknown)

        # Ping and HTTP each retry internally before reporting a failure
        # (IP Verify's retry_count for ping, http_retry_count for HTTP),
        # so a failing verdict here is already a confirmed failure and is
        # acted on immediately. Signal has no equivalent, so it keeps its
        # own consecutive-reading counter.
        with self.lock:
            if breaches:
                self.signal_fail_counts[key] = self.signal_fail_counts.get(key, 0) + 1
            else:
                self.signal_fail_counts[key] = 0
            signal_strikes = self.signal_fail_counts[key]

        parts = []
        if ping_ok is not None:
            parts.append('ping %s' % ('ok' if ping_ok else 'FAIL'))
        if http_ok is not None:
            parts.append('http %s' % ('ok' if http_ok else 'FAIL'))
        if breaches:
            parts.append('signal low (%s)' % ', '.join(
                '%s %g < %g' % (m, v, t) for m, v, t in breaches))
        elif self._has_signal_test(cfg):
            parts.append('signal ok')
        self.status_text = 'on %s%s' % (
            dsds.slot_label(active), ' - ' + ', '.join(parts) if parts else ' - no tests enabled')

        reason = None
        if conn_failed:
            detail = []
            if ping_ok is False:
                detail.append('ping to %s failed after %d retries'
                              % (', '.join(cfg['ping_targets']),
                                 cfg['ping_retry_count']))
            if http_ok is False:
                entry = self.http_results.get(key) or {}
                detail.append('HTTP %s %s failed on %s attempt(s) (%s)' % (
                    cfg['http_method'], cfg['http_url'],
                    entry.get('attempts', '?'),
                    entry.get('error') or 'status %s' % entry.get('status')))
            reason = '; '.join(detail)
        elif breaches and signal_strikes >= cfg['signal_fail_threshold']:
            reason = 'signal below threshold after %d consecutive checks: %s' % (
                signal_strikes, ', '.join(
                    '%s %g < %g' % (m, v, t) for m, v, t in breaches))

        if reason:
            self._try_failover(active, slots, reason, conn_failed)
        else:
            # Healthy where we are, but a higher-priority slot may have
            # recovered enough to move back to.
            self._maybe_failback(active, slots)

    def _try_failover(self, active, slots, reason, conn_failed=False):
        target_key = active.get('sibling')
        target = slots.get(target_key) if target_key else None
        if not target:
            self.status_text = 'on %s - %s, but there is no sibling slot to ' \
                               'move to' % (dsds.slot_label(active), reason)
            return
        if target.get('nosim'):
            self.status_text = 'on %s - %s, but %s has no SIM' % (
                dsds.slot_label(active), reason, dsds.slot_label(target))
            return

        target_cfg = appconfig.slot_config(self.conf, target_key)

        # When the app has no choice there is nothing to weigh up: the
        # connected slot failed its connectivity tests, or lost its
        # connection outright. A link that cannot be verified still beats
        # one that is known dead, so the destination's signal is not
        # consulted at all and the move always happens.
        must_move = conn_failed or not active.get('connected')

        # A forced move overrides a failback holdoff on the destination.
        # The holdoff exists to stop the app returning to a slot whose
        # *connectivity* it cannot judge from standby - but that argument
        # only holds while the slot it is standing on still works. Once
        # this slot has failed too, waiting buys nothing: the app would
        # be sitting on a link it knows is broken to avoid one it merely
        # cannot verify.
        #
        # Cleared here rather than relying on do_switch() clearing it on
        # arrival, so the dashboard stops counting down the moment the
        # decision is made instead of ~30 seconds later, and so the
        # reason appears in the event log.
        #
        # This is what makes the app keep hunting when neither SIM has
        # service. It will alternate roughly every settle + ~30s, which
        # is deliberate: whichever slot regains service first is picked
        # up within a couple of minutes, where honouring the holdoff
        # could leave traffic parked on a dead slot for the full hour.
        if must_move and self.failback_hold_slot == target_key:
            self._clear_failback_hold(
                'the app is now on %s and that slot has failed too, so '
                'returning to a link it cannot verify beats staying on one '
                'it knows is broken' % dsds.slot_label(active))

        if not must_move and self._has_signal_test(target_cfg):
            # Signal-only degradation: the link still works, so a switch
            # has to be an improvement to be worth ~30s of downtime.
            #
            # The destination has to *demonstrate* it clears its own
            # threshold, which is what lets the secondary slot be held to
            # a different bar. Judged with _meets_threshold() rather than
            # by looking for breaches, because a slot reporting NONE of
            # the metrics its threshold is set on produces no breaches at
            # all - so a breach test alone would read "no evidence" as
            # "no problem" and switch to a slot with no signal whatsoever.
            # An unverifiable threshold is not a satisfied threshold.
            thresholds = target_cfg.get('signal_thresholds') or {}
            ok, failing = self._meets_threshold(target, thresholds)
            _, unknown = self._compare_signal(target, thresholds)
            self._warn_unknown_metrics(target_key, unknown, 'destination')
            if not ok:
                # The destination is no better than where we are, so
                # there is no better place to be. Priority decides where
                # traffic sits, which is what stops the app bouncing
                # between two weak slots - every switch would otherwise
                # look like an improvement from whichever slot it was
                # standing on.
                measured = [f for f in failing if f[1] is not None]
                if measured:
                    detail = 'is below its own threshold too (%s)' \
                        % _describe_failing(failing)
                else:
                    detail = 'is not reporting %s at all, so it cannot show ' \
                        'it is any better' \
                        % ', '.join(sorted(f[0] for f in failing))
                if not self._is_higher_priority(target_key, active['key']):
                    self.status_text = \
                        'on %s - %s, but %s %s; priority keeps traffic here' \
                        % (dsds.slot_label(active), reason,
                           dsds.slot_label(target), detail)
                    return
                self.event('Neither slot clears its signal threshold - %s %s '
                           '- so neither is worth having; moving from %s to '
                           'the preferred %s'
                           % (dsds.slot_label(target), detail,
                              dsds.slot_label(active),
                              dsds.slot_label(target)), 'warn')

        # Only a connectivity failure arms the holdoff: signal is
        # readable on a standby slot, so it gates its own return.
        self.do_switch(reason, hold_failback=conn_failed)

    def _maybe_failback(self, active, slots):
        """Return to a higher-priority slot once its signal recovers.

        This is the proactive half of failback: the connected slot is
        passing all its own tests, but a slot the operator ranked higher
        has come back above its threshold, so move back to it.

        Only possible because a DSDS modem keeps reporting live
        diagnostics for the standby slot - there is no way to ping it.
        And that is exactly why the holdoff below exists: signal is the
        only evidence available here, so a slot whose *link* is broken
        while its signal is fine looks permanently ready to return to.
        """
        target_key = active.get('sibling')
        target = slots.get(target_key) if target_key else None
        if not target or target.get('nosim'):
            self.failback_ok_counts.pop(target_key, None)
            return
        if not self._is_higher_priority(target_key, active['key']):
            return

        cfg = appconfig.slot_config(self.conf, target_key)
        if not cfg.get('signal_failback_enabled'):
            return
        thresholds = cfg.get('signal_thresholds') or {}
        if not thresholds or not cfg.get('signal_enabled'):
            # Signal is the only thing measurable on a standby slot, so
            # with no threshold set there is nothing to recover above and
            # failback stays manual.
            return

        # The app left this slot because its connectivity tests failed,
        # and those tests cannot run while it is on standby. Its signal
        # will keep saying "come back" regardless, so without this wait
        # the app would return, fail connectivity, leave, and repeat
        # every settle + ~30s. Not applied to a signal or disconnect
        # failover, where the threshold below is live evidence.
        waiting = self._failback_hold_remaining(target_key)
        if waiting:
            self.failback_ok_counts.pop(target_key, None)
            self.status_text = \
                'on %s - holding off failback to higher-priority %s for ' \
                'another %dm %ds after its connectivity failure' % (
                    dsds.slot_label(active), dsds.slot_label(target),
                    waiting // 60, waiting % 60)
            return

        ok, failing = self._signal_allows_failback(target, cfg)
        _, unknown = self._compare_signal(target, thresholds)
        self._warn_unknown_metrics(target_key, unknown, 'failback')

        if not ok:
            if self.failback_ok_counts.pop(target_key, 0):
                cp.log('Higher-priority %s dropped back below its signal '
                       'threshold: %s' % (dsds.slot_label(target),
                                          _describe_failing(failing)))
            return

        with self.lock:
            count = self.failback_ok_counts.get(target_key, 0) + 1
            self.failback_ok_counts[target_key] = count

        need = cfg['signal_fail_threshold']
        if count < need:
            self.status_text = 'on %s - higher-priority %s is back above its ' \
                               'threshold, failing back in %d reading(s)' % (
                dsds.slot_label(active), dsds.slot_label(target), need - count)
            return

        signal = ', '.join('%s %g' % (m, (target.get('signal') or {})[m])
                           for m in thresholds
                           if m in (target.get('signal') or {}))
        with self.lock:
            self.failback_ok_counts.pop(target_key, None)
        self.do_switch('higher-priority %s recovered (%s) over %d reading(s)'
                       % (dsds.slot_label(target), signal, count))

    # -- snapshot for the web UI ----------------------------------------

    def snapshot(self):
        now = time.time()
        with self.lock:
            conf = self.conf
            slots_out = []
            for key in sorted(self.slots):
                slot = self.slots[key]
                cfg = appconfig.slot_config(conf, key)
                ping = dict(self.ping_results.get(key) or {})
                http = dict(self.http_results.get(key) or {})
                if http.get('ts'):
                    http['age'] = int(now - http['ts'])
                preferred = self._is_preferred(key)
                metrics = []
                for metric, label, unit in dsds.SIGNAL_METRICS:
                    if metric not in (slot.get('signal') or {}):
                        continue
                    metrics.append({
                        'key': metric, 'label': label, 'unit': unit,
                        'value': slot['signal'][metric],
                        'threshold': cfg['signal_thresholds'].get(metric)
                        if cfg.get('signal_enabled') else None,
                    })
                breaches, unknown = self._signal_breaches(slot, cfg)
                failback_ok, _ = self._signal_allows_failback(slot, cfg)
                # Whether any configured metric is actually being
                # reported right now. The two signal checks treat "no
                # reading" in opposite directions on purpose - the app
                # will not *leave* a slot without evidence, and will not
                # *move to* one without evidence either - so without this
                # the UI shows a slot as both above and below its
                # threshold at once and looks broken.
                reported = None
                if self._has_signal_test(cfg):
                    reported = len(unknown) < len(cfg['signal_thresholds'])
                slots_out.append({
                    'signal_reported': reported,
                    'preferred': preferred,
                    # Seconds left before the app may fail back to this
                    # slot, after leaving it on a connectivity failure.
                    'failback_hold': self._failback_hold_remaining(key),
                    'key': key,
                    'label': dsds.slot_label(slot),
                    'port': slot.get('port'),
                    'sim': slot.get('sim'),
                    'carrier': slot.get('carrier'),
                    'home_carrier': slot.get('home_carrier'),
                    'serving_carrier': slot.get('serving_carrier'),
                    'dsds_instance': slot.get('dsds_instance'),
                    'connection_state': slot.get('connection_state'),
                    'summary': slot.get('summary'),
                    'reason': slot.get('reason'),
                    'connected': slot.get('connected'),
                    'active_sib': slot.get('active_sib'),
                    'switching': slot.get('switching'),
                    'ip_address': slot.get('ip_address'),
                    'service_type': slot.get('service_type'),
                    'service_detail': slot.get('service_detail'),
                    'rf_band': slot.get('rf_band'),
                    'health_score': slot.get('health_score'),
                    'health_category': slot.get('health_category'),
                    'nosim': slot.get('nosim'),
                    'uptime': slot.get('uptime'),
                    'sibling': slot.get('sibling'),
                    'metrics': metrics,
                    'signal_verdict': (None if not self._has_signal_test(cfg)
                                       else not breaches),
                    # Only the preferred slot is ever a failback target,
                    # so on any other slot this reports no verdict rather
                    # than one nothing acts on.
                    'signal_failback_ok': (
                        None if not (preferred
                                     and cfg.get('signal_failback_enabled')
                                     and self._has_signal_test(cfg))
                        else failback_ok),
                    'ping': ping,
                    'ping_verdict': self._ping_verdict(key, cfg),
                    'http': http,
                    'http_verdict': self._http_verdict(key, cfg),
                    'signal_fail_count': self.signal_fail_counts.get(key, 0),
                    'failback_ok_count': self.failback_ok_counts.get(key, 0),
                    'priority': self._priority(key),
                    'config': cfg,
                })
            return {
                'slots': slots_out,
                'status': self.status_text,
                'switching': self.switching,
                'poll_interval': POLL_INTERVAL,
                'settle_remaining': max(0, int(self.settle_until - now)),
                'last_switch_ago': int(now - self.last_switch_ts)
                if self.last_switch_ts else None,
                'switch_count': self.switch_count,
                'failback_hold_slot': self.failback_hold_slot,
                'failback_hold_remaining': max(
                    0, int(self.failback_hold_until - now))
                if self.failback_hold_slot else 0,
                'history': [
                    {'ago': int(now - h['ts']), 'text': h['text'],
                     'level': h['level']}
                    for h in reversed(self.history[-40:])
                ],
            }
