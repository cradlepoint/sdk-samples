/* dsds_wan_verify - dashboard and configuration UI.
 *
 * Supplements static/js/script.js, which already provides sidebar
 * navigation, dark mode, the help/info modals, and showToast().
 */
(function () {
    'use strict';

    var STATUS_POLL_MS = 3000;
    var state = {
        metrics: [],
        pollInterval: 2,
        defaults: { slot: {} },
        config: { slots: {} },
        slots: [],
        // One signature covers both configuration pages: they are built
        // together so a change made anywhere refreshes both.
        formsBuiltFor: '',
        suspendRender: false,
        // Which slot tab is showing, and which test sections are expanded.
        // Both survive a form rebuild so saving config does not collapse
        // everything the user had open. The two configuration pages share
        // one active tab so switching pages stays on the same slot.
        activeSlotTab: '',
        openSections: {}
    };

    // ---------------------------------------------------------------
    // helpers
    // ---------------------------------------------------------------

    function esc(value) {
        if (value === null || value === undefined) { return ''; }
        return String(value)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function toast(message, type) {
        if (window.webAppTemplate && window.webAppTemplate.showToast) {
            window.webAppTemplate.showToast(esc(message), type || 'info', 5000);
        }
    }

    function fmtAgo(seconds) {
        if (seconds === null || seconds === undefined) { return '—'; }
        seconds = Math.max(0, Math.round(seconds));
        if (seconds < 60) { return seconds + 's ago'; }
        if (seconds < 3600) { return Math.floor(seconds / 60) + 'm ago'; }
        return Math.floor(seconds / 3600) + 'h ago';
    }

    // A remaining duration, not an elapsed one, so it never says "ago"
    // and keeps minute resolution where the default is an hour.
    function fmtDuration(seconds) {
        if (!seconds) { return '0s'; }
        seconds = Math.max(0, Math.round(seconds));
        if (seconds < 60) { return seconds + 's'; }
        var m = Math.floor(seconds / 60);
        if (m < 60) { return m + 'm ' + (seconds % 60) + 's'; }
        return Math.floor(m / 60) + 'h ' + (m % 60) + 'm';
    }

    function fmtUptime(seconds) {
        if (!seconds) { return '—'; }
        seconds = Math.round(seconds);
        var h = Math.floor(seconds / 3600);
        var m = Math.floor((seconds % 3600) / 60);
        if (h) { return h + 'h ' + m + 'm'; }
        return m + 'm';
    }

    function num(value) {
        if (value === null || value === undefined || value === '') { return null; }
        var parsed = Number(value);
        return isNaN(parsed) ? null : parsed;
    }

    function getJSON(url) {
        return fetch(url, { cache: 'no-store' }).then(function (r) {
            if (!r.ok) { throw new Error('HTTP ' + r.status); }
            return r.json();
        });
    }

    function postJSON(url, body) {
        return fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body || {})
        }).then(function (r) {
            return r.json().then(function (data) {
                return { ok: r.ok, data: data };
            });
        });
    }

    // Signal metrics are negative dBm/dB where higher is better. These
    // ranges are only used to size the visual bar, never to decide
    // pass/fail, which always compares against the configured threshold.
    var METRIC_RANGE = {
        DBM: [-120, -50], RSRP: [-130, -70], RSRQ: [-20, -3], SINR: [-5, 30],
        RSRP_5G: [-130, -70], RSRQ_5G: [-20, -3], SINR_5G: [-5, 30]
    };

    function metricPercent(key, value) {
        var range = METRIC_RANGE[key] || [-120, 0];
        var pct = ((value - range[0]) / (range[1] - range[0])) * 100;
        return Math.max(2, Math.min(100, pct));
    }

    // ---------------------------------------------------------------
    // dashboard rendering
    // ---------------------------------------------------------------

    function verdictIcon(verdict) {
        if (verdict === true) { return '<i class="fas fa-check-circle dwv-test-icon ok"></i>'; }
        if (verdict === false) { return '<i class="fas fa-times-circle dwv-test-icon bad"></i>'; }
        return '<i class="fas fa-minus-circle dwv-test-icon unknown"></i>';
    }

    // Slots grouped by modem port, in SIM order. A router can host more
    // than one DSDS modem (int1, int2), and each pair is decided
    // independently - the preferred SIM, the priority tiebreak and the
    // failback direction are all per-modem, never global.
    function modemGroups(slots) {
        var byPort = {};
        var order = [];
        slots.forEach(function (s) {
            if (!byPort[s.port]) { byPort[s.port] = []; order.push(s.port); }
            byPort[s.port].push(s);
        });
        return order.map(function (port) {
            return {
                port: port,
                slots: byPort[port].slice().sort(function (a, b) {
                    return String(a.sim).localeCompare(String(b.sim));
                })
            };
        });
    }

    function renderSlotBadges(slot) {
        var badges = [];
        if (slot.switching) {
            badges.push('<span class="dwv-badge warn"><i class="fas fa-circle-notch"></i> Switching</span>');
        } else if (slot.connected) {
            badges.push('<span class="dwv-badge ok"><i class="fas fa-link"></i> Connected</span>');
        } else if (slot.nosim) {
            badges.push('<span class="dwv-badge bad"><i class="fas fa-ban"></i> No SIM</span>');
        } else {
            badges.push('<span class="dwv-badge"><i class="fas fa-pause"></i> ' +
                esc(slot.summary || slot.connection_state || 'standby') + '</span>');
        }
        if (slot.preferred) {
            badges.push('<span class="dwv-badge primary" title="The app returns to this slot when it can">' +
                '<i class="fas fa-star"></i> Preferred</span>');
        }
        // Counting down a wait the operator cannot otherwise see, since
        // the slot looks perfectly healthy on signal while it is held.
        if (slot.failback_hold) {
            badges.push('<span class="dwv-badge warn" title="Left on a connectivity failure; ' +
                'signal cannot tell whether that is fixed, so the app waits before returning">' +
                '<i class="fas fa-hourglass-half"></i> Hold ' + fmtDuration(slot.failback_hold) +
                '</span>');
        }
        return badges.join('');
    }

    function renderMetrics(slot) {
        if (!slot.metrics.length) {
            return '<p class="dwv-hint">This slot is not reporting any signal metrics right now.</p>';
        }
        var rows = slot.metrics.map(function (m) {
            var has = m.threshold !== null && m.threshold !== undefined;
            var breached = has && m.value < m.threshold;
            var pct = metricPercent(m.key, m.value);
            var fillClass = breached ? 'bad' : (pct < 35 ? 'warn' : '');
            // The threshold is shown on the metric's own row. As a line
            // underneath it sat between two metrics and read as though it
            // belonged to the next one down.
            return '' +
                '<div class="dwv-metric">' +
                    '<span class="dwv-metric-name">' + esc(m.label) +
                        (has ? '<span class="dwv-metric-limit" title="Threshold for this metric">' +
                            '&ge; ' + esc(m.threshold) + '</span>' : '') +
                    '</span>' +
                    '<span class="dwv-metric-track">' +
                        '<span class="dwv-metric-fill ' + fillClass + '" style="width:' + pct.toFixed(0) + '%"></span>' +
                    '</span>' +
                    '<span class="dwv-metric-value ' + (breached ? 'bad' : '') + '">' +
                        esc(m.value) + ' ' + esc(m.unit) +
                    '</span>' +
                '</div>';
        });
        return '<div class="dwv-metrics">' + rows.join('') + '</div>';
    }

    function renderTests(slot) {
        var rows = [];
        var cfg = slot.config;

        if (cfg.ping_enabled && cfg.ping_targets.length) {
            cfg.ping_targets.forEach(function (target) {
                var verdict = slot.ping.hasOwnProperty(target) ? slot.ping[target] : null;
                var note = '';
                if (verdict === null) {
                    note = slot.connected
                        ? '<span class="dwv-test-note">waiting for a result</span>'
                        : '<span class="dwv-test-note">not run (slot is not connected)</span>';
                }
                rows.push('<div class="dwv-test">' + verdictIcon(verdict) +
                    '<span class="dwv-test-target">ping ' + esc(target) + '</span>' + note + '</div>');
            });
        }

        if (cfg.http_enabled && cfg.http_url) {
            var verdict = slot.http_verdict;
            var note;
            if (!slot.connected) {
                note = '<span class="dwv-test-note">not run (slot is not connected)</span>';
            } else if (slot.http.error) {
                note = '<span class="dwv-test-note">' + esc(slot.http.error) +
                    (slot.http.attempts > 1 ? ' · ' + esc(slot.http.attempts) + ' attempts' : '') +
                    '</span>';
            } else if (slot.http.status) {
                note = '<span class="dwv-test-note">' + esc(slot.http.status) +
                    (slot.http.ms !== null && slot.http.ms !== undefined ? ' · ' + esc(slot.http.ms) + ' ms' : '') +
                    (slot.http.attempts > 1 ? ' · ' + esc(slot.http.attempts) + ' attempts' : '') +
                    (slot.http.age !== undefined ? ' · ' + fmtAgo(slot.http.age) : '') +
                    // Explain the grey icon rather than showing a good
                    // status code next to an "unknown" marker.
                    (verdict === null ? ' · too old to count' : '') + '</span>';
            } else {
                note = '<span class="dwv-test-note">waiting for a result</span>';
            }
            rows.push('<div class="dwv-test">' + verdictIcon(verdict) +
                '<span class="dwv-test-target">' + esc(cfg.http_method) + ' ' + esc(cfg.http_url) + '</span>' +
                note + '</div>');
        }

        // `signal_reported` is false when none of the slot's threshold
        // metrics exist on its current radio technology. The engine then
        // neither leaves the slot nor moves to it, so both rows below
        // report "no reading" rather than a pass on one and a fail on the
        // other, which read as a contradiction.
        var noReading = cfg.signal_enabled && slot.signal_reported === false;

        if (cfg.signal_enabled) {
            var sv = slot.signal_verdict;
            rows.push('<div class="dwv-test">' +
                (noReading ? verdictIcon(null) : verdictIcon(sv)) +
                '<span class="dwv-test-target">signal threshold</span>' +
                '<span class="dwv-test-note">' + (
                    sv === null ? 'no thresholds set'
                        : noReading
                        ? 'this radio does not report the metrics it is set on'
                        : sv === false ? 'below threshold' : 'above threshold'
                ) + '</span></div>');
        }
        // Only the preferred slot is ever a failback target, so the
        // snapshot reports no verdict for any other slot and this row is
        // skipped rather than showing something nothing acts on.
        if (slot.preferred && cfg.signal_failback_enabled) {
            var fb = slot.signal_failback_ok;
            rows.push('<div class="dwv-test">' +
                (noReading ? verdictIcon(null) : verdictIcon(fb)) +
                '<span class="dwv-test-target">failback on recovery</span>' +
                '<span class="dwv-test-note">' + (
                    slot.failback_hold
                        ? 'held for ' + fmtDuration(slot.failback_hold) +
                          ' after its connectivity failure'
                        : fb === null ? 'no thresholds set'
                        : noReading ? 'waiting for a reading to judge on'
                        : fb === false ? 'not above its threshold yet'
                        : 'above its threshold, ready to return to'
                ) + '</span></div>');
        }

        if (!rows.length) {
            // Only say what is actually true of *this* slot. On the
            // preferred slot, no tests really does mean nothing can move
            // traffic off it. On the secondary it does not: the app
            // returns to the preferred slot when that slot's failback
            // fires, whatever is or is not configured here.
            return '<p class="dwv-hint">' + (slot.preferred
                ? 'No tests are enabled for this slot, so while it is connected ' +
                  'nothing can fail and the app will not move off it.'
                : 'No tests configured.') + '</p>';
        }
        if (slot.signal_fail_count) {
            rows.push('<div class="dwv-test"><span class="dwv-test-note">' +
                esc(slot.signal_fail_count) + ' consecutive low signal reading(s), need ' +
                esc(cfg.signal_fail_threshold) + '</span></div>');
        }
        if (slot.failback_ok_count) {
            rows.push('<div class="dwv-test"><span class="dwv-test-note">' +
                esc(slot.failback_ok_count) + ' of ' + esc(cfg.signal_fail_threshold) +
                ' reading(s) above its threshold</span></div>');
        }
        return '<div class="dwv-tests">' + rows.join('') + '</div>';
    }

    function renderSlotCard(slot) {
        var cls = 'dwv-slot-card';
        if (slot.switching) { cls += ' is-switching'; }
        else if (slot.connected) { cls += ' is-active'; }
        if (slot.fail_count || slot.signal_fail_count) { cls += ' is-failing'; }

        return '' +
        '<div class="' + cls + '">' +
            '<div class="dwv-slot-head">' +
                '<div class="dwv-slot-title">' +
                    '<span class="dwv-slot-name">' + esc(slot.port) + ' / ' + esc(slot.sim) + '</span>' +
                    '<span class="dwv-slot-sub">' +
                        esc(slot.carrier || 'unknown carrier') +
                        (slot.service_detail ? ' · ' + esc(slot.service_detail) :
                            (slot.service_type ? ' · ' + esc(slot.service_type) : '')) +
                        (slot.rf_band ? ' · ' + esc(slot.rf_band) : '') +
                    '</span>' +
                '</div>' +
                '<div class="dwv-badges">' + renderSlotBadges(slot) + '</div>' +
            '</div>' +
            '<div class="dwv-slot-body">' +
                '<dl class="dwv-kv">' +
                    '<dt>State</dt><dd>' + esc(slot.connection_state || '—') +
                        (slot.reason ? ' <span class="dwv-test-note">(' + esc(slot.reason) + ')</span>' : '') + '</dd>' +
                    '<dt>WAN IP</dt><dd>' + esc(slot.ip_address || '—') + '</dd>' +
                    '<dt>Uptime</dt><dd>' + fmtUptime(slot.uptime) + '</dd>' +
                    '<dt>DSDS instance</dt><dd>' + esc(slot.dsds_instance !== null && slot.dsds_instance !== undefined ? slot.dsds_instance : '—') +
                        (slot.active_sib ? ' <span class="dwv-test-note">(owns the radio)</span>' : '') + '</dd>' +
                    (slot.health_category ? '<dt>Health</dt><dd>' + esc(slot.health_category) +
                        (slot.health_score ? ' (' + esc(slot.health_score) + ')' : '') + '</dd>' : '') +
                '</dl>' +
                '<div>' +
                    '<div class="dwv-section-label">Signal</div>' + renderMetrics(slot) +
                '</div>' +
                '<div>' +
                    '<div class="dwv-section-label">Test results</div>' + renderTests(slot) +
                '</div>' +
            '</div>' +
        '</div>';
    }

    function renderDashboard(snap) {
        var container = document.getElementById('slot-cards');
        if (!snap.slots.length) {
            container.innerHTML = '<div class="dwv-empty">' +
                '<i class="fas fa-sim-card" style="font-size:2rem"></i>' +
                '<p>No DSDS modem detected on this router.</p>' +
                '<p class="dwv-hint">This app requires a modem that reports ' +
                '<code>DSDS_ENABLED</code>, with both SIM slots visible as separate WAN devices.</p>' +
                '</div>';
        } else {
            container.innerHTML = snap.slots.map(renderSlotCard).join('');
        }

        document.getElementById('monitor-status').textContent = snap.status || '—';

        var stats = [
            ['Poll', snap.poll_interval + 's'],
            ['Settle', snap.settle_remaining ? snap.settle_remaining + 's' : '—'],
            ['Last switch', snap.last_switch_ago === null ? 'never' : fmtAgo(snap.last_switch_ago)],
            ['Switches', snap.switch_count]
        ];
        if (snap.failback_hold_remaining) {
            stats.push(['Failback hold', fmtDuration(snap.failback_hold_remaining)]);
        }
        document.getElementById('monitor-stats').innerHTML = stats.map(function (pair) {
            return '<div class="dwv-stat"><span class="dwv-stat-label">' + esc(pair[0]) +
                '</span><span class="dwv-stat-value">' + esc(pair[1]) + '</span></div>';
        }).join('');

        renderPreferred(snap);

        // A slot with no enabled test can never fail, so failover being
        // always-armed is only meaningful once something is configured.
        var armed = snap.slots.filter(function (s) {
            return s.config.ping_enabled || s.config.http_enabled ||
                s.config.signal_enabled;
        });
        var hint = document.getElementById('failover-hint');
        if (snap.slots.length && !armed.length) {
            hint.innerHTML = '<i class="fas fa-triangle-exclamation"></i> No tests are enabled, ' +
                'so no slot can fail and nothing will switch automatically. Set up ping or HTTP ' +
                'checks under <strong>Connectivity Tests</strong>, or a threshold under ' +
                '<strong>Signal Thresholds</strong>.';
        } else if (snap.failback_hold_slot) {
            var held = snap.slots.filter(function (s) {
                return s.key === snap.failback_hold_slot; })[0];
            hint.innerHTML = '<i class="fas fa-hourglass-half"></i> The app left <strong>' +
                esc(held ? held.sim : snap.failback_hold_slot) + '</strong> because its ' +
                'connectivity tests failed. Those tests cannot run while it is on standby and its ' +
                'signal looks fine either way, so failback to it is held for ' +
                fmtDuration(snap.failback_hold_remaining) + ' to stop the modem flapping. ' +
                '<strong>Switch SIM Now</strong> overrides it.';
        } else {
            hint.innerHTML = '';
        }

        var badge = document.getElementById('live-status');
        var text = document.getElementById('live-status-text');
        badge.className = 'dwv-live';
        if (snap.switching || snap.status.indexOf('switch in progress') !== -1) {
            badge.className += ' warn busy';
            text.textContent = 'switching';
        } else if (!snap.slots.length) {
            badge.className += ' bad';
            text.textContent = 'no DSDS modem';
        } else {
            var active = snap.slots.filter(function (s) { return s.connected; })[0];
            if (active) {
                badge.className += ' ok';
                text.textContent = active.port + '/' + active.sim +
                    (active.carrier ? ' · ' + active.carrier : '');
            } else {
                badge.className += ' bad';
                text.textContent = 'no slot connected';
            }
        }

        var switchBtn = document.getElementById('switch-btn');
        switchBtn.disabled = snap.switching || !snap.slots.some(function (s) { return s.connected; });

        renderHistory(snap.history || []);
    }

    // --- preferred SIM -------------------------------------------------

    // A two-way choice per modem, rather than a free priority number on
    // each slot. "Which SIM do you want to be on" is the only question
    // an operator actually has; exposing two independent numbers also
    // allowed them to be set equal, which silently disabled failback and
    // the both-slots-weak tiebreak. Stored as priority 1 and 2 so an NCM
    // group config keeps working, and applied the moment it is clicked -
    // it belongs to the live view, not to a form you have to remember to
    // save.
    function renderPreferred(snap) {
        var box = document.getElementById('preferred-sim');
        if (!box) { return; }
        var groups = modemGroups(snap.slots).filter(function (g) {
            return g.slots.length > 1;
        });
        if (!groups.length) {
            box.innerHTML = '';
            return;
        }
        box.innerHTML = groups.map(function (group) {
            var buttons = group.slots.map(function (s) {
                return '<button type="button" class="dwv-seg-btn' +
                    (s.preferred ? ' active' : '') + '" ' +
                    'data-prefer="' + esc(s.key) + '"' +
                    (s.nosim ? ' disabled title="No SIM in this slot"' : '') + '>' +
                    esc(s.sim.toUpperCase()) +
                    (s.carrier ? ' <span class="dwv-seg-sub">' + esc(s.carrier) + '</span>' : '') +
                    '</button>';
            }).join('');
            // No slot flagged preferred means the two priorities are
            // equal, which only a direct appdata or NCM edit can do.
            // Clicking either button repairs it.
            var tied = !group.slots.some(function (s) { return s.preferred; });
            return '<div class="dwv-seg-group">' +
                '<span class="dwv-seg-label">Preferred SIM' +
                    (groups.length > 1 ? ' <span class="dwv-seg-sub">' +
                        esc(group.port) + '</span>' : '') + '</span>' +
                '<span class="dwv-seg">' + buttons + '</span>' +
                (tied ? '<span class="dwv-seg-flag" title="Both slots carry the same priority ' +
                    'number, so neither is preferred: no automatic failback, and no tiebreak when ' +
                    'both are weak. Pick one to fix it.">' +
                    '<i class="fas fa-triangle-exclamation"></i></span>' : '') +
                '</div>';
        }).join('');
    }

    // Writes priority 1 to the chosen slot and 2 to its sibling, so the
    // two can never come out equal through the UI.
    function setPreferred(slotKey) {
        var slot = (state.slots || []).filter(function (s) {
            return s.key === slotKey; })[0];
        if (!slot) { return; }
        var slots = {};
        slots[slotKey] = { priority: 1 };
        if (slot.sibling) { slots[slot.sibling] = { priority: 2 }; }
        postJSON('api/config', { slots: slots }).then(function (res) {
            if (!res.ok || res.data.error) {
                toast(res.data.error || 'Could not set the preferred SIM', 'error');
                return;
            }
            // Pick up the stored priorities so the threshold page's
            // failback column follows immediately.
            state.config.slots = res.data.slots;
            state.formsBuiltFor = '';
            toast('Preferred SIM is now ' + slot.sim.toUpperCase(), 'success');
            poll();
        }).catch(function (err) {
            toast('Could not set the preferred SIM: ' + err.message, 'error');
        });
    }

    function renderHistory(events) {
        var list = document.getElementById('history-list');
        if (!events.length) {
            list.innerHTML = '<p class="text-secondary">No events yet.</p>';
            return;
        }
        list.innerHTML = events.map(function (e) {
            return '<div class="dwv-event ' + esc(e.level) + '">' +
                '<span class="dwv-event-ago">' + fmtAgo(e.ago) + '</span>' +
                '<span class="dwv-event-text">' + esc(e.text) + '</span></div>';
        }).join('');
    }

    // ---------------------------------------------------------------
    // slot configuration forms
    // ---------------------------------------------------------------
    //
    // Two configuration pages, each with one tab per SIM slot:
    //
    //   * Connectivity Tests - ping and HTTP, plus the slot settings
    //     that govern how their verdicts combine and the flap guard for
    //     a connectivity-caused failover.
    //   * Signal Thresholds  - the one threshold per slot, which is the
    //     only test that works on a disconnected slot.
    //
    // Which SIM is preferred lives on the dashboard, not here: it is a
    // single live choice about where traffic should sit, not a form
    // field.
    //
    // Both pages are always present in the DOM (the template only hides
    // the inactive section), so collectSlots() reads every field
    // whichever page is showing and either Save button writes the whole
    // config. That also means a threshold input left off-screen still
    // carries its stored value, instead of being blanked by a save.

    function thresholdTable(slot, field, valueHeader) {
        var cfg = slot.config[field] || {};
        var live = {};
        slot.metrics.forEach(function (m) { live[m.key] = m; });

        var rows = state.metrics.map(function (m) {
            var present = live.hasOwnProperty(m.key);
            var value = cfg.hasOwnProperty(m.key) ? cfg[m.key] : '';
            return '<tr class="' + (present ? 'is-present' : '') + '">' +
                '<td>' + esc(m.label) + ' <span class="dwv-test-note">' + esc(m.unit) + '</span></td>' +
                '<td class="dwv-live-val">' + (present ? esc(live[m.key].value)
                    : '<span class="dwv-test-note">not reported</span>') + '</td>' +
                '<td><input type="number" step="any" class="form-input" ' +
                    'data-slot="' + esc(slot.key) + '" data-field="' + esc(field) + '" ' +
                    'data-metric="' + esc(m.key) + '" value="' + esc(value) + '" ' +
                    'placeholder="off"></td>' +
                '</tr>';
        }).join('');

        return '<table class="dwv-threshold-table">' +
            '<thead><tr><th>Metric</th><th>Now</th><th>' + valueHeader + '</th></tr></thead>' +
            '<tbody>' + rows + '</tbody>' +
        '</table>';
    }

    function tabId(key) { return 'slottab-' + key.replace(/[^a-zA-Z0-9]/g, '_'); }

    // --- collapsible test section ----------------------------------

    function collapseSection(slotKey, name, icon, title, bodyHtml) {
        var open = state.openSections[slotKey + '|' + name] === true;
        var bodyId = tabId(slotKey) + '-' + name + '-body';
        return '' +
        '<div class="dwv-collapse' + (open ? ' is-open' : '') + '" data-collapse="' + esc(name) + '">' +
            '<button type="button" class="dwv-collapse-bar" aria-expanded="' + (open ? 'true' : 'false') + '" ' +
                    'aria-controls="' + bodyId + '" data-collapse-toggle="' + esc(name) + '">' +
                '<i class="fas fa-chevron-right dwv-collapse-caret"></i>' +
                '<span class="dwv-collapse-title"><i class="fas ' + icon + '"></i> ' + title + '</span>' +
                '<span class="dwv-collapse-summary" data-summary="' + esc(name) + '"></span>' +
            '</button>' +
            '<div class="dwv-collapse-body" id="' + bodyId + '"' + (open ? '' : ' hidden') + '>' +
                bodyHtml +
            '</div>' +
        '</div>';
    }

    // --- summaries shown on each collapsed bar ---------------------

    function truncateList(items, max) {
        if (items.length <= max) { return items.join(', '); }
        return items.slice(0, max).join(', ') + ' +' + (items.length - max) + ' more';
    }

    function summaryFor(name, cfg) {
        if (name === 'ping') {
            if (!cfg.ping_enabled) { return { state: 'off', text: 'Not running' }; }
            if (!cfg.ping_targets.length) {
                return { state: 'warn', text: 'On, but no targets set' };
            }
            return {
                state: 'on',
                text: truncateList(cfg.ping_targets, 3) +
                    ' · every ' + cfg.ping_interval + 's' +
                    ' · fail if ' + (cfg.ping_fail_mode === 'any' ? 'any' : 'all') + ' fail'
            };
        }
        if (name === 'http') {
            if (!cfg.http_enabled) { return { state: 'off', text: 'Not running' }; }
            if (!cfg.http_url) { return { state: 'warn', text: 'On, but no URL set' }; }
            var host = cfg.http_url.replace(/^https?:\/\//, '');
            return {
                state: 'on',
                text: cfg.http_method + ' ' + (host.length > 38 ? host.slice(0, 38) + '…' : host) +
                    ' · ' + cfg.http_timeout + 's timeout' +
                    ' · expect ' + (cfg.http_expect_status.length
                        ? cfg.http_expect_status.join('/') : 'any 2xx/3xx') +
                    ' · every ' + cfg.http_interval + 's' +
                    ' · ' + cfg.http_retry_count + ' retr' +
                    (cfg.http_retry_count === 1 ? 'y' : 'ies')
            };
        }
        return { state: 'off', text: '' };
    }

    function updateSummaries() {
        var collected = collectSlots();
        Object.keys(collected).forEach(function (slotKey) {
            var form = document.querySelector('[data-test-form="' + slotKey + '"]');
            if (!form) { return; }
            ['ping', 'http'].forEach(function (name) {
                var target = form.querySelector('[data-summary="' + name + '"]');
                if (!target) { return; }
                var info = summaryFor(name, collected[slotKey]);
                target.className = 'dwv-collapse-summary ' + info.state;
                target.textContent = info.text;
            });
        });
    }

    // --- shared form field builders --------------------------------

    function fieldBuilder(slot) {
        var key = slot.key;
        var cfg = slot.config;
        return {
            id: function (f) { return 's-' + key.replace(/[^a-zA-Z0-9]/g, '_') + '-' + f; },
            field: function (name, label, type, attrs) {
                var id = this.id(name);
                return '<div class="form-field">' +
                    '<label for="' + id + '">' + label + '</label>' +
                    '<input type="' + type + '" class="form-input" id="' + id + '" ' +
                    'data-slot="' + esc(key) + '" data-key="' + esc(name) + '" ' +
                    (attrs || '') + ' value="' + esc(cfg[name]) + '">' +
                    '</div>';
            },
            toggle: function (name, label) {
                return '<label class="toggle-switch">' +
                    '<input type="checkbox" id="' + this.id(name) + '" data-slot="' + esc(key) + '" ' +
                    'data-key="' + esc(name) + '"' + (cfg[name] ? ' checked' : '') + '>' +
                    '<span class="toggle-slider"></span>' +
                    '<span class="toggle-label">' + label + '</span></label>';
            }
        };
    }

    // --- connectivity tests form (ping + HTTP) ---------------------

    function testSlotForm(slot, preferred) {
        var cfg = slot.config;
        var key = slot.key;
        var b = fieldBuilder(slot);

        var pingBody = '' +
            b.toggle('ping_enabled', 'Run a ping test on this slot') +
            '<p class="dwv-hint">' +
                'Performed by the router\'s IP Verify subsystem, bound to this slot\'s WAN device. ' +
                'Only the connected slot\'s test is armed; the other slot\'s test is disabled so a ' +
                'standby slot never reports a misleading failure.' +
            '</p>' +
            '<div class="form-field" style="margin-top:0.75rem">' +
                '<label for="' + b.id('ping_targets') + '">Targets (one per line, up to 8)</label>' +
                '<textarea class="form-input" rows="3" id="' + b.id('ping_targets') + '" ' +
                    'data-slot="' + esc(key) + '" data-key="ping_targets" ' +
                    'placeholder="8.8.8.8">' + esc((cfg.ping_targets || []).join('\n')) + '</textarea>' +
            '</div>' +
            '<div class="dwv-form-grid">' +
                '<div class="form-field">' +
                    '<label for="' + b.id('ping_fail_mode') + '">Fail when</label>' +
                    '<select class="form-select" id="' + b.id('ping_fail_mode') + '" data-slot="' + esc(key) + '" data-key="ping_fail_mode">' +
                        '<option value="all"' + (cfg.ping_fail_mode === 'all' ? ' selected' : '') + '>All targets fail</option>' +
                        '<option value="any"' + (cfg.ping_fail_mode === 'any' ? ' selected' : '') + '>Any target fails</option>' +
                    '</select>' +
                '</div>' +
                b.field('ping_interval', 'Interval (s)', 'number', 'min="1" max="3600"') +
                b.field('ping_retry_count', 'Retries (0-5)', 'number', 'min="0" max="5"') +
                b.field('ping_retry_interval', 'Retry interval (5-30s)', 'number', 'min="5" max="30"') +
                b.field('ping_pkt_per_try', 'Packets per try', 'number', 'min="1" max="255"') +
                b.field('ping_pkt_size', 'Packet size (&ge;36)', 'number', 'min="36" max="1500"') +
                b.field('ping_pkt_timeout', 'Packet timeout (0.1s units)', 'number', 'min="1" max="255"') +
            '</div>';

        var httpBody = '' +
            b.toggle('http_enabled', 'Run an HTTP test on this slot') +
            '<p class="dwv-hint">' +
                'Performed by the app, with the socket\'s source address bound to this slot\'s WAN IP. ' +
                'IP Verify has no HTTP test type, so this one is not visible in the router UI. ' +
                'Only runs while this slot is connected. A failure is retried before it counts, so ' +
                'worst case a verdict takes ' +
                '<strong>(retries + 1) \u00d7 timeout + retries \u00d7 retry interval</strong> &mdash; ' +
                'keep that under the interval.' +
            '</p>' +
            '<div class="dwv-form-grid" style="margin-top:0.75rem">' +
                '<div class="form-field" style="grid-column:1/-1">' +
                    '<label for="' + b.id('http_url') + '">URL</label>' +
                    '<input type="text" class="form-input" id="' + b.id('http_url') + '" ' +
                        'data-slot="' + esc(key) + '" data-key="http_url" ' +
                        'placeholder="http://connectivitycheck.gstatic.com/generate_204" ' +
                        'value="' + esc(cfg.http_url) + '">' +
                '</div>' +
                '<div class="form-field">' +
                    '<label for="' + b.id('http_method') + '">Method</label>' +
                    '<select class="form-select" id="' + b.id('http_method') + '" data-slot="' + esc(key) + '" data-key="http_method">' +
                        '<option value="GET"' + (cfg.http_method === 'GET' ? ' selected' : '') + '>GET</option>' +
                        '<option value="HEAD"' + (cfg.http_method === 'HEAD' ? ' selected' : '') + '>HEAD</option>' +
                    '</select>' +
                '</div>' +
                b.field('http_timeout', 'Timeout (s)', 'number', 'min="1" max="120"') +
                b.field('http_interval', 'Interval (s)', 'number', 'min="5" max="3600"') +
                b.field('http_retry_count', 'Retries (0-10)', 'number', 'min="0" max="10"') +
                b.field('http_retry_interval', 'Retry interval (s)', 'number', 'min="1" max="60"') +
                '<div class="form-field">' +
                    '<label for="' + b.id('http_expect_status') + '">Accepted status codes</label>' +
                    '<input type="text" class="form-input" id="' + b.id('http_expect_status') + '" ' +
                        'data-slot="' + esc(key) + '" data-key="http_expect_status" ' +
                        'placeholder="any 2xx or 3xx" ' +
                        'value="' + esc((cfg.http_expect_status || []).join(', ')) + '">' +
                '</div>' +
            '</div>' +
            b.toggle('http_verify_tls', 'Verify the TLS certificate (https only)') +
            '<div class="dwv-inline-actions">' +
                '<button type="button" class="btn btn-secondary" data-test-http="' + esc(key) + '">' +
                    '<i class="fas fa-vial"></i> Test Now' +
                '</button>' +
                '<span class="dwv-inline-result" data-http-result="' + esc(key) + '"></span>' +
            '</div>';

        return '' +
        '<div class="dwv-slot-form" data-test-form="' + esc(key) + '">' +
            '<div class="dwv-form-grid">' +
                '<div class="form-field">' +
                    '<label for="' + b.id('test_combine') + '">Ping and HTTP together</label>' +
                    '<select class="form-select" id="' + b.id('test_combine') + '" data-slot="' + esc(key) + '" data-key="test_combine">' +
                        '<option value="all"' + (cfg.test_combine === 'all' ? ' selected' : '') + '>Both must pass</option>' +
                        '<option value="any"' + (cfg.test_combine === 'any' ? ' selected' : '') + '>Either passing is enough</option>' +
                    '</select>' +
                '</div>' +
                b.field('settle_seconds', 'Settle time after this slot connects (s)', 'number', 'min="0" max="900"') +
            '</div>' +
            '<p class="dwv-hint" style="margin-top:0">' +
                'An HTTP test usually exists to catch what ping cannot &mdash; a captive portal, broken ' +
                'DNS, or a path that drops everything except ICMP &mdash; so <em>Both must pass</em> is ' +
                'the default. Choose <em>Either</em> when the endpoint is less reliable than the link ' +
                'itself.' +
            '</p>' +
            '<p class="dwv-hint">' +
                'Each test confirms its own failures through its own retries, so one failing result is ' +
                'acted on straight away. <strong>Settle time</strong> is what stops the app bouncing ' +
                'back: for that long after this slot connects, all of its results are ignored &mdash; ' +
                'signal included &mdash; giving it time to register, get DNS, and settle its routes. The ' +
                'switch itself takes about 30 seconds on top of this.' +
            '</p>' +

            // The holdoff delays a proactive failback *to* this slot, and
            // only the preferred slot is ever a failback target. Hidden
            // rather than dimmed on the secondary, but kept in the DOM so
            // the stored value survives a save and comes back if the
            // preferred SIM is switched over.
            '<div class="dwv-subsection' + (preferred ? '' : ' is-gate-off') + '" ' +
                 'data-gate="failback-holdoff">' +
                '<div class="dwv-form-grid dwv-form-grid-narrow">' +
                    b.field('failback_holdoff_seconds',
                            'Failback holdoff after a connectivity failure (s)', 'number',
                            'min="0" max="86400"') +
                '</div>' +
                '<p class="dwv-note">' +
                    '<i class="fas fa-hourglass-half"></i> <strong>Failback holdoff</strong> covers the one ' +
                    'flap a signal threshold cannot. If this slot has strong signal but a broken link, the ' +
                    'app fails over, then immediately sees good signal here and comes back &mdash; and ' +
                    'ping and HTTP cannot run on a standby slot to contradict that. So after leaving this ' +
                    'slot on a <em>connectivity</em> failure, the app waits this long before returning to ' +
                    'it. Set 0 to disable the wait.' +
                '</p>' +
                '<p class="dwv-hint">' +
                    'Deliberately not applied when the app left on low signal or a lost connection: signal ' +
                    'is readable on a standby slot, so the threshold already decides whether coming back ' +
                    'makes sense. <strong>Switch SIM Now</strong> on the dashboard clears an active hold.' +
                '</p>' +
            '</div>' +
            (preferred ? '' :
                '<p class="dwv-note primary">' +
                    '<i class="fas fa-circle-info"></i> There is no <strong>failback holdoff</strong> on ' +
                    'this slot. It is the <strong>secondary</strong> SIM, and the app only fails back to ' +
                    'the preferred one &mdash; leaving this slot puts traffic on the preferred SIM, which ' +
                    'nothing moves off on its own, so there is no return to delay.' +
                '</p>') +

            '<div class="dwv-collapse-stack">' +
                collapseSection(key, 'ping', 'fa-satellite-dish', 'Ping Test', pingBody) +
                collapseSection(key, 'http', 'fa-globe', 'HTTP Test', httpBody) +
            '</div>' +
        '</div>';
    }

    // --- signal threshold form -------------------------------------

    function signalSlotForm(slot, preferred) {
        var cfg = slot.config;
        var b = fieldBuilder(slot);

        return '' +
        '<div class="dwv-slot-form" data-signal-form="' + esc(slot.key) + '">' +
            b.toggle('signal_enabled', 'Use a signal threshold on this slot') +
            '<p class="dwv-hint">' +
                'One threshold per slot, meaning <em>the level at which this slot is no longer ' +
                'worth using</em>. The app reads it three ways, so the number only has to be ' +
                'decided once:' +
            '</p>' +
            '<ul class="dwv-hint dwv-bullets">' +
                '<li><strong>Leaving</strong> &mdash; while this slot is connected and drops ' +
                    'below the threshold, the app moves off it.</li>' +
                '<li><strong>Arriving</strong> &mdash; the app will not fail over <em>to</em> ' +
                    'this slot on signal alone while it is below its own threshold.</li>' +
                '<li><strong>Both weak</strong> &mdash; if neither slot is above its threshold ' +
                    'there is no better place to be, so the app does not switch on signal and ' +
                    'the <strong>Preferred SIM</strong> on the dashboard decides where traffic ' +
                    'sits. That is what stops it bouncing between two weak slots.</li>' +
            '</ul>' +
            '<p class="dwv-note' + (preferred ? '' : ' primary') + '">' +
                '<i class="fas fa-circle-info"></i> ' +
                (preferred
                    ? 'This is the <strong>preferred</strong> SIM. Set the <em>other</em> slot\'s ' +
                      'threshold lower than this one.'
                    : 'This is the <strong>secondary</strong> SIM, so set its threshold ' +
                      '<strong>lower</strong> than the preferred slot\'s.') +
                ' Equal numbers mean a weak-signal area breaches both at once, and the ' +
                'both-weak rule above then pins traffic to the preferred SIM &mdash; so the ' +
                'secondary never gets used. A lower bar keeps it available exactly when the ' +
                'preferred SIM has gone marginal.' +
            '</p>' +
            '<div class="dwv-form-grid dwv-form-grid-narrow">' +
                b.field('signal_fail_threshold', 'Consecutive readings before acting', 'number',
                        'min="1" max="100"') +
            '</div>' +
            '<p class="dwv-hint" style="margin-top:0">' +
                'Signal has no retry concept of its own, so the reading count at the ' +
                (state.pollInterval || 2) + 's poll rate is what keeps a single dip from ' +
                'triggering a ~30 second switch. It applies when leaving a slot and when ' +
                'failing back to one.' +
            '</p>' +
            '<p class="dwv-hint">' +
                'Leave a metric blank to ignore it. Which metrics a slot reports depends on the ' +
                'radio technology it is using right now: 5G SA reports only the 5G variants, LTE ' +
                'only the LTE ones, and 5G NSA reports both. Metrics marked <em>not reported</em> ' +
                'are ignored at runtime rather than treated as a failure, so set values on both ' +
                'families if the slot can use either.' +
            '</p>' +
            thresholdTable(slot, 'signal_thresholds', 'Threshold') +

            // Only the preferred slot is ever a failback target, so this
            // is hidden rather than drawn as a setting with no effect.
            // Kept in the DOM so the stored value survives a save and
            // reappears if the preferred SIM is switched over.
            '<div class="dwv-subsection' + (preferred ? '' : ' is-gate-off') + '" ' +
                 'data-gate="failback">' +
                b.toggle('signal_failback_enabled',
                         'Return to this slot when its signal recovers') +
                '<p class="dwv-hint">' +
                    'With this on, the app switches back to this slot once it climbs above the ' +
                    'threshold again, even though the slot carrying traffic is passing all of ' +
                    'its own tests. Possible only because a DSDS modem keeps reporting live ' +
                    'diagnostics for the standby slot &mdash; there is no way to ping it.' +
                '</p>' +
                '<p class="dwv-hint">' +
                    '<i class="fas fa-circle-info"></i> With it off, the app still returns here ' +
                    'when the <em>other</em> slot fails; it just will not move on signal ' +
                    'recovery alone.' +
                '</p>' +
            '</div>' +
        '</div>';
    }

    // --- building and tab handling ----------------------------------

    function slotTabs(snap, attr) {
        return snap.slots.map(function (s) {
            var on = s.key === state.activeSlotTab;
            return '<button type="button" class="tab-btn' + (on ? ' active' : '') + '" ' +
                attr + '="' + esc(s.key) + '">' +
                '<i class="fas fa-sim-card"></i> ' + esc(s.port) + ' / ' + esc(s.sim) +
                (s.carrier ? ' <span class="dwv-tab-sub">' + esc(s.carrier) + '</span>' : '') +
                (s.preferred ? ' <i class="fas fa-star dwv-tab-star" title="Preferred SIM"></i>' : '') +
                (s.connected ? ' <i class="fas fa-circle dwv-tab-dot" title="Connected"></i>' : '') +
                '</button>';
        }).join('');
    }

    function buildSlotForms(snap) {
        // Rebuild when the slot set *or* the stored config changes, so a
        // config change made elsewhere (the API, an NCM group push,
        // another admin) does not leave these pages showing stale values
        // that a later Save would silently write back. `preferred` is in
        // the signature too, because it decides whether the failback
        // option is shown.
        var signature = JSON.stringify(snap.slots.map(function (s) {
            return [s.key, s.preferred, s.config];
        }));
        var testBox = document.getElementById('test-forms');
        var signalBox = document.getElementById('signal-forms');

        if (signature === state.formsBuiltFor) {
            refreshLiveThresholdValues(snap);
            updateSummaries();
            return;
        }
        // Never yank a form out from under someone mid-edit. The outer
        // poll already skips while a field has focus; this also covers a
        // click landing between polls. Both pages are checked, since they
        // are rebuilt together.
        var active = document.activeElement;
        if (active && (testBox.contains(active) || signalBox.contains(active))) {
            refreshLiveThresholdValues(snap);
            updateSummaries();
            return;
        }
        if (!snap.slots.length) {
            var empty = '<div class="dwv-empty"><i class="fas fa-sim-card" style="font-size:2rem"></i>' +
                '<p>No DSDS slots to configure.</p></div>';
            testBox.innerHTML = empty;
            signalBox.innerHTML = empty;
            state.formsBuiltFor = signature;
            return;
        }

        // Keep the previously selected tab if that slot still exists.
        if (!snap.slots.some(function (s) { return s.key === state.activeSlotTab; })) {
            var connected = snap.slots.filter(function (s) { return s.connected; })[0];
            state.activeSlotTab = (connected || snap.slots[0]).key;
        }

        function panes(attr, builder) {
            return snap.slots.map(function (s) {
                var on = s.key === state.activeSlotTab;
                return '<div class="tab-content' + (on ? ' active' : '') + '" ' +
                    attr + '="' + esc(s.key) + '">' + builder(s) + '</div>';
            }).join('');
        }

        testBox.innerHTML =
            '<div class="tab-navigation dwv-slot-tabs">' + slotTabs(snap, 'data-test-tab') + '</div>' +
            '<div class="dwv-slot-panes">' +
            panes('data-test-pane', function (s) {
                return testSlotForm(s, !!s.preferred);
            }) + '</div>';

        signalBox.innerHTML =
            '<div class="tab-navigation dwv-slot-tabs">' + slotTabs(snap, 'data-signal-tab') + '</div>' +
            '<div class="dwv-slot-panes">' +
            panes('data-signal-pane', function (s) {
                return signalSlotForm(s, !!s.preferred);
            }) + '</div>';

        state.formsBuiltFor = signature;
        updateSummaries();
    }

    // Both pages follow one selection, so moving between them stays on
    // the same SIM slot rather than silently showing a different one.
    function selectSlotTab(key) {
        state.activeSlotTab = key;
        [['data-test-tab', 'data-test-pane'],
         ['data-signal-tab', 'data-signal-pane']].forEach(function (pair) {
            document.querySelectorAll('[' + pair[0] + ']').forEach(function (btn) {
                btn.classList.toggle('active', btn.getAttribute(pair[0]) === key);
            });
            document.querySelectorAll('[' + pair[1] + ']').forEach(function (pane) {
                pane.classList.toggle('active', pane.getAttribute(pair[1]) === key);
            });
        });
    }

    function toggleCollapse(slotKey, name) {
        var form = document.querySelector('[data-test-form="' + slotKey + '"]');
        if (!form) { return; }
        var section = form.querySelector('[data-collapse="' + name + '"]');
        if (!section) { return; }
        var bar = section.querySelector('.dwv-collapse-bar');
        var body = section.querySelector('.dwv-collapse-body');
        var open = !section.classList.contains('is-open');
        section.classList.toggle('is-open', open);
        bar.setAttribute('aria-expanded', open ? 'true' : 'false');
        body.hidden = !open;
        state.openSections[slotKey + '|' + name] = open;
    }

    function refreshLiveThresholdValues(snap) {
        // Update only the read-only "Now" column; never touch inputs.
        snap.slots.forEach(function (slot) {
            var live = {};
            slot.metrics.forEach(function (m) { live[m.key] = m.value; });
            var form = document.querySelector('[data-signal-form="' + slot.key + '"]');
            if (!form) { return; }
            form.querySelectorAll('input[data-metric]').forEach(function (input) {
                // Only the read-only "Now" cell is touched here; the
                // threshold inputs are left alone so a refresh cannot
                // overwrite what the user is typing.
                var cell = input.closest('tr');
                if (!cell) { return; }
                var liveCell = cell.querySelector('.dwv-live-val');
                if (!liveCell) { return; }
                var key = input.getAttribute('data-metric');
                if (live.hasOwnProperty(key)) {
                    liveCell.textContent = live[key];
                    cell.classList.add('is-present');
                } else {
                    liveCell.innerHTML = '<span class="dwv-test-note">not reported</span>';
                    cell.classList.remove('is-present');
                }
            });
        });
    }

    // ---------------------------------------------------------------
    // collecting form values
    // ---------------------------------------------------------------

    // Fields from both configuration pages, since one Save writes the
    // whole config and the inactive page is hidden, not removed.
    function formEls(selector) {
        return Array.prototype.slice.call(document.querySelectorAll(
            '#test-forms ' + selector + ', #signal-forms ' + selector));
    }

    function collectSlots() {
        var slots = {};

        // Threshold sets are rebuilt from the inputs rather than merged,
        // so clearing a field actually removes that metric. Only the sets
        // that are present on the page get reset: anything not rendered
        // has to keep its stored values rather than being blanked by a
        // save from a page that never showed it.
        var rebuilt = {};
        formEls('input[data-metric]').forEach(function (el) {
            var slotKey = el.getAttribute('data-slot');
            rebuilt[slotKey] = rebuilt[slotKey] || {};
            rebuilt[slotKey][el.getAttribute('data-field')] = true;
        });

        function ensure(key) {
            if (!slots[key]) {
                // Per-slot defaults first: the default priority is
                // derived from the SIM number, so the flat set would
                // seed SIM 2 with SIM 1's value.
                var byKey = state.defaults.slot_by_key || {};
                slots[key] = JSON.parse(JSON.stringify(
                    state.config.slots[key] || byKey[key] ||
                    state.defaults.slot));
                Object.keys(rebuilt[key] || {}).forEach(function (field) {
                    slots[key][field] = {};
                });
            }
            return slots[key];
        }

        formEls('[data-slot][data-key]').forEach(function (el) {
            var cfg = ensure(el.getAttribute('data-slot'));
            var key = el.getAttribute('data-key');
            if (el.type === 'checkbox') {
                cfg[key] = el.checked;
            } else if (key === 'ping_targets') {
                cfg[key] = el.value.split('\n').map(function (t) { return t.trim(); })
                    .filter(function (t) { return t.length; });
            } else if (key === 'http_expect_status') {
                cfg[key] = el.value.split(/[,\s]+/).map(num)
                    .filter(function (v) { return v !== null; });
            } else if (el.type === 'number') {
                var parsed = num(el.value);
                if (parsed !== null) { cfg[key] = parsed; }
            } else {
                cfg[key] = el.value;
            }
        });

        formEls('input[data-metric]').forEach(function (el) {
            var cfg = ensure(el.getAttribute('data-slot'));
            var parsed = num(el.value);
            if (parsed !== null) {
                cfg[el.getAttribute('data-field')][el.getAttribute('data-metric')] = parsed;
            }
        });

        return slots;
    }
    // ---------------------------------------------------------------
    // actions
    // ---------------------------------------------------------------

    function saveConfig() {
        var payload = {
            slots: Object.assign({}, state.config.slots, collectSlots())
        };
        state.suspendRender = true;
        return postJSON('api/config', payload).then(function (res) {
            state.suspendRender = false;
            if (!res.ok || res.data.error) {
                toast(res.data.error || 'Could not save configuration', 'error');
                return false;
            }
            state.config.slots = res.data.slots;
            // Server-side validation may have clamped values; rebuild so
            // the form shows what was actually stored.
            state.formsBuiltFor = '';
            toast('Configuration saved', 'success');
            poll();
            return true;
        }).catch(function (err) {
            state.suspendRender = false;
            toast('Could not save configuration: ' + err.message, 'error');
            return false;
        });
    }

    function manualSwitch() {
        var btn = document.getElementById('switch-btn');
        var original = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> Switching…';
        postJSON('api/switch', {}).then(function (res) {
            if (!res.ok || res.data.error) {
                toast(res.data.error || res.data.message || 'Switch failed', 'error');
            } else {
                toast(res.data.message || 'Switch complete', res.data.ok ? 'success' : 'warning');
            }
        }).catch(function (err) {
            toast('Switch failed: ' + err.message, 'error');
        }).finally(function () {
            btn.innerHTML = original;
            btn.disabled = false;
            poll();
        });
    }

    function testHttp(slotKey) {
        var form = document.querySelector('[data-test-form="' + slotKey + '"]');
        var out = document.querySelector('[data-http-result="' + slotKey + '"]');
        if (!form || !out) { return; }
        var value = function (key) {
            var el = form.querySelector('[data-key="' + key + '"]');
            return el ? el.value : '';
        };
        var url = value('http_url').trim();
        if (!url) {
            out.className = 'dwv-inline-result bad';
            out.textContent = 'Enter a URL first.';
            return;
        }
        out.className = 'dwv-inline-result';
        out.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> testing…';
        postJSON('api/http_test', {
            slot: slotKey,
            url: url,
            method: value('http_method'),
            timeout: num(value('http_timeout')) || 2,
            retry_count: num(value('http_retry_count')) || 0,
            retry_interval: num(value('http_retry_interval')) || 2,
            expect_status: value('http_expect_status').split(/[,\s]+/).map(num)
                .filter(function (v) { return v !== null; }),
            verify_tls: !!(form.querySelector('[data-key="http_verify_tls"]') || {}).checked
        }).then(function (res) {
            if (!res.ok || res.data.error && res.data.ok === undefined) {
                out.className = 'dwv-inline-result bad';
                out.textContent = res.data.error || 'Test failed';
                return;
            }
            var d = res.data;
            out.className = 'dwv-inline-result ' + (d.ok ? 'ok' : 'bad');
            out.textContent = (d.ok ? 'OK' : 'FAILED') +
                ' · status ' + (d.status === null ? 'none' : d.status) +
                ' · ' + (d.ms === null ? '?' : d.ms) + ' ms' +
                (d.attempts > 1 ? ' · ' + d.attempts + ' attempts' : '') +
                ' · from ' + (d.source_ip || 'default route') +
                (d.error ? ' · ' + d.error : '');
        }).catch(function (err) {
            out.className = 'dwv-inline-result bad';
            out.textContent = 'Test failed: ' + err.message;
        });
    }

    function clearTests() {
        if (!window.confirm('Delete every IP Verify test this app created? ' +
                'They will be recreated on the next poll for any slot that still has ' +
                'a ping test enabled.')) {
            return;
        }
        postJSON('api/clear_tests', {}).then(function (res) {
            if (!res.ok || res.data.error) {
                toast(res.data.error || 'Could not remove tests', 'error');
            } else {
                toast('Removed this app\'s IP Verify tests', 'success');
                poll();
            }
        }).catch(function (err) {
            toast('Could not remove tests: ' + err.message, 'error');
        });
    }

    // ---------------------------------------------------------------
    // polling
    // ---------------------------------------------------------------

    function poll() {
        return getJSON('api/status').then(function (snap) {
            state.slots = snap.slots;
            if (state.suspendRender) { return; }
            // The snapshot carries the authoritative config, so the forms
            // and the dashboard never disagree.
            state.pollInterval = snap.poll_interval;
            snap.slots.forEach(function (s) { state.config.slots[s.key] = s.config; });
            renderDashboard(snap);
            buildSlotForms(snap);
        }).catch(function (err) {
            var badge = document.getElementById('live-status');
            badge.className = 'dwv-live bad';
            document.getElementById('live-status-text').textContent = 'unreachable';
            console.error('status poll failed', err);
        });
    }


    function init() {
        getJSON('api/config').then(function (conf) {
            state.metrics = conf.metrics || [];
            state.defaults = conf.defaults || { slot: {} };
            state.config.slots = conf.slots || {};
            return poll();
        }).catch(function (err) {
            toast('Could not load configuration: ' + err.message, 'error');
        });

        document.getElementById('switch-btn').addEventListener('click', manualSwitch);
        document.getElementById('clear-tests-btn').addEventListener('click', clearTests);

        // Delegated, because the segmented control is re-rendered on
        // every status poll.
        document.getElementById('preferred-sim').addEventListener('click', function (event) {
            var btn = event.target.closest('[data-prefer]');
            if (btn && !btn.disabled && !btn.classList.contains('active')) {
                setPreferred(btn.getAttribute('data-prefer'));
            }
        });
        // Either Save writes the whole config, because both pages are
        // always in the DOM and collectSlots() reads them together.
        ['save-tests-btn', 'save-signal-btn'].forEach(function (id) {
            document.getElementById(id).addEventListener('click', saveConfig);
        });

        // The template's initTabs() binds at page load, so these
        // dynamically built tabs need their own delegated handler.
        ['test-forms', 'signal-forms'].forEach(function (id) {
            var forms = document.getElementById(id);

            forms.addEventListener('click', function (event) {
                var tab = event.target.closest('[data-test-tab], [data-signal-tab]');
                if (tab) {
                    selectSlotTab(tab.getAttribute('data-test-tab') ||
                                  tab.getAttribute('data-signal-tab'));
                    return;
                }
                var bar = event.target.closest('[data-collapse-toggle]');
                if (bar) {
                    var pane = bar.closest('[data-test-form]');
                    toggleCollapse(pane.getAttribute('data-test-form'),
                                   bar.getAttribute('data-collapse-toggle'));
                    return;
                }
                var test = event.target.closest('[data-test-http]');
                if (test) { testHttp(test.getAttribute('data-test-http')); }
            });

            // Keep the collapsed bars' summaries in step with the fields.
            forms.addEventListener('input', updateSummaries);
            forms.addEventListener('change', updateSummaries);
        });

        setInterval(function () {
            // Pause polling while a field is focused so a refresh cannot
            // overwrite what the user is typing.
            var active = document.activeElement;
            if (active && /^(INPUT|TEXTAREA|SELECT)$/.test(active.tagName)) {
                getJSON('api/status').then(function (snap) {
                    state.slots = snap.slots;
                    renderDashboard(snap);
                }).catch(function () {});
                return;
            }
            poll();
        }, STATUS_POLL_MS);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
