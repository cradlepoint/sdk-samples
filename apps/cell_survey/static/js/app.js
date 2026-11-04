// cell_survey front-end logic.
// Talks to the Python backend over /api/* and renders modem status, runs the
// AT network survey (polling for progress), groups results by carrier, and
// locks the modem to a chosen PLMN.
(function () {
    'use strict';

    var state = {
        modems: [],
        selectedPort: null,
        currentModem: null,   // last /api/modem result
        pollTimer: null,
        pendingLock: null,    // {plmn, network}
        pendingEsim: null,    // {iccid, profile_name, network}
        lastGroups: [],       // last survey results, for CSV export
        scheduleCfg: null     // last-loaded schedule config (for re-applying)
    };

    function $(id) { return document.getElementById(id); }

    function toast(msg, type) {
        if (window.webAppTemplate && window.webAppTemplate.showToast) {
            window.webAppTemplate.showToast(msg, type || 'info', 4000);
        }
    }

    function api(path, opts) {
        return fetch(path, opts).then(function (r) { return r.json(); });
    }

    // ---- Modem selection + status ----------------------------------------

    function loadModems() {
        return api('/api/modems').then(function (data) {
            state.modems = data.modems || [];
            var sel = $('modem-select');
            sel.innerHTML = '';
            if (!state.modems.length) {
                var opt = document.createElement('option');
                opt.textContent = 'No modems detected';
                opt.value = '';
                sel.appendChild(opt);
                $('modem-stats').innerHTML = '<p class="cs-muted">No cellular modems found on this router.</p>';
                $('run-survey-btn').disabled = true;
                return;
            }
            state.modems.forEach(function (m) {
                var opt = document.createElement('option');
                opt.value = m.port;
                opt.textContent = m.model + ' (' + m.port + ')';
                sel.appendChild(opt);
            });
            // Default to the first connected modem/SIM if available
            // (backend chooses and sorts the default first).
            var def = data.default_port;
            var hasDef = state.modems.some(function (m) { return m.port === def; });
            state.selectedPort = hasDef ? def : state.modems[0].port;
            sel.value = state.selectedPort;
            // Return the status promise so callers chaining off loadModems()
            // (e.g. loadModems().then(restoreSurveyState)) wait for the modem
            // status — including state.currentModem.esim — to load before they
            // run. Without this, restoreSurveyState() renders survey results
            // before .esim exists, so the eSIM buttons never appear on refresh.
            return loadModemStatus();
        }).catch(function () {
            toast('Could not load modems', 'error');
        });
    }

    // Collapse the current-connection tiles so survey results take center
    // stage. Shows a compact header (carrier + signal) that re-expands on
    // click. Called when a survey finishes with results.
    function collapseConnSection() {
        var section = $('conn-section');
        var head = $('conn-collapse-head');
        head.style.display = 'flex';
        section.classList.remove('open');
        var m = state.currentModem || {};
        var bits = [];
        if (m.carrier) bits.push(escapeHtml(m.carrier));
        if (m.service_type_display || m.service_type) {
            bits.push(escapeHtml(m.service_type_display || m.service_type));
        }
        if (m.rsrp != null && m.rsrp !== '') bits.push(escapeHtml(m.rsrp) + ' dBm');
        $('conn-collapsed-summary').innerHTML = bits.join(' &middot; ');
    }

    // Expand the current-connection tiles and hide the collapse header. Called
    // when a new survey starts or the selected modem changes, so the live
    // connection is visible again.
    function expandConnSection() {
        $('conn-section').classList.add('open');
        $('conn-collapse-head').style.display = 'none';
    }

    function connPill(cstate) {
        // Legacy single pill is superseded by the per-SIM-slot pills; keep
        // the element clear so nothing stale lingers in the modem row.
        var pill = $('modem-conn');
        if (pill) { pill.className = 'cs-pill'; pill.innerHTML = ''; }
    }

    // Visual treatment for one SIM slot's status. "NO SIM" is neutral (not an
    // error — a scan still works); connected is green; standby/transitional is
    // amber; anything else (disconnected, unknown) is red.
    function simPillStyle(sim) {
        if (sim.no_sim) {
            return { cls: 'warn', icon: 'fa-sim-card', text: 'NO SIM' };
        }
        var cstate = sim.connection_state || 'unknown';
        if (cstate === 'connected') {
            return { cls: 'ok', icon: 'fa-circle-check', text: 'Connected' };
        }
        if (cstate === 'standby') {
            return { cls: 'warn', icon: 'fa-circle-pause', text: 'Standby' };
        }
        if (cstate === 'connecting' || cstate === 'establishing') {
            return { cls: 'warn', icon: 'fa-circle-notch', text: cstate };
        }
        return { cls: 'bad', icon: 'fa-circle-xmark', text: cstate };
    }

    // Render one status pill per SIM slot on the selected modem.
    function renderSimPills(sims) {
        var row = $('sim-pills');
        if (!row) return;
        if (!sims || !sims.length) {
            row.innerHTML = '';
            row.style.display = 'none';
            return;
        }
        var html = sims.map(function (sim) {
            var s = simPillStyle(sim);
            return '<span class="cs-pill ' + s.cls + '">'
                + '<i class="fas ' + s.icon + '"></i> '
                + escapeHtml(sim.label || 'SIM') + ': ' + escapeHtml(s.text)
                + '</span>';
        }).join('');
        row.innerHTML = html;
        row.style.display = 'flex';
    }

    function signalColor(rsrp) {
        var v = parseInt(rsrp, 10);
        if (isNaN(v)) return '#94a3b8';
        if (v >= -80) return '#16a34a';
        if (v >= -90) return '#65a30d';
        if (v >= -100) return '#d97706';
        return '#dc2626';
    }

    function statCard(label, value, sub) {
        return '<div class="cs-stat"><div class="cs-label">' + label + '</div>' +
            '<div class="cs-value">' + (value == null || value === '' ? '&mdash;' : value) + '</div>' +
            (sub ? '<div class="cs-sub">' + sub + '</div>' : '') + '</div>';
    }

    function loadModemStatus() {
        if (!state.selectedPort) return Promise.resolve();
        $('modem-stats').innerHTML = '<p class="cs-muted">Loading modem status...</p>';
        return api('/api/modem?port=' + encodeURIComponent(state.selectedPort)).then(function (m) {
            if (m.error) {
                $('modem-stats').innerHTML = '<p class="cs-muted">' + m.error + '</p>';
                renderSimPills(null);
                return;
            }
            state.currentModem = m;
            connPill(m.connection_state);
            renderSimPills(m.sims);

            var html = '';
            // Top row: identity/connection tiles.
            html += statCard('Carrier', escapeHtml(m.carrier), m.plmn ? 'PLMN ' + m.plmn : '');
            html += statCard('Service', escapeHtml(m.service_type_display || m.service_type || ''), m.rf_band ? escapeHtml(m.rf_band) : '');
            html += statCard('APN', escapeHtml(m.apn || ''));
            html += statCard('ICCID', escapeHtml(m.iccid || ''));
            // Bottom row: signal tiles.
            html += statCard('Signal (RSRP)', m.rsrp != null ? m.rsrp + ' dBm' : '', m.signal_quality) ;
            html += statCard('RSRQ', m.rsrq != null ? m.rsrq + ' dB' : '');
            html += statCard('SINR', m.sinr != null ? m.sinr + ' dB' : '');
            html += statCard('RSSI', m.rssi != null ? m.rssi + ' dBm' : '');
            $('modem-stats').innerHTML = html;

            // Survey-button gating. The only requirement is a supported Telit
            // FE990/FN990 module. The AT survey (AT#CSURVC) scans the radio
            // environment directly, so it works regardless of connection
            // state - disconnected, standby, or no SIM at all. Don't clobber
            // the disabled state while a survey is in flight.
            var unsupported = $('unsupported-banner');
            var surveyBtn = $('run-survey-btn');
            var surveyRunning = state.pollTimer !== null;
            if (m.supported === false) {
                unsupported.style.display = 'flex';
                $('unsupported-text').textContent =
                    'The network survey is only supported on Telit FE990/FN990 '
                    + 'modules. This modem (' + escapeHtml(m.mfg_model || 'unknown')
                    + ') is not supported.';
                if (!surveyRunning) surveyBtn.disabled = true;
                surveyBtn.title = 'Unsupported modem';
            } else {
                unsupported.style.display = 'none';
                if (!surveyRunning) surveyBtn.disabled = false;
                surveyBtn.title = '';
            }

            // Lock banner
            var banner = $('locked-banner');
            if (m.lock && m.lock.net_sel_mode === 'manual' && m.lock.lock_net) {
                banner.style.display = 'flex';
                $('locked-text').textContent = 'This modem is locked to PLMN ' + m.lock.lock_net + ' (manual selection).';
            } else {
                banner.style.display = 'none';
            }

            // Keep the Schedule tab's eSIM option in sync with this modem.
            updateEsimOptionAvailability();
        }).catch(function () {
            $('modem-stats').innerHTML = '<p class="cs-muted">Failed to read modem status.</p>';
        });
    }

    // ---- Survey ----------------------------------------------------------

    // On page load (or refresh), the survey state lives on the server, not in
    // the browser. Ask the backend what it's doing and restore the UI so a
    // refresh doesn't lose an in-progress survey or its completed results.
    function restoreSurveyState() {
        return api('/api/survey/status').then(function (s) {
            if (s.state === 'running') {
                $('run-survey-btn').disabled = true;
                $('results-panel').classList.add('cs-hidden');
                $('survey-progress').style.display = 'flex';
                $('survey-message').textContent = s.message || 'Survey in progress...';
                pollSurvey();
            } else if (s.state === 'done') {
                $('survey-status-text').textContent = s.message || '';
                var groups = s.groups || [];
                renderResults(groups);
                if (groups.length) collapseConnSection();
            } else if (s.state === 'error') {
                $('survey-status-text').textContent = s.message || '';
            }
        }).catch(function () { /* no survey to restore */ });
    }

    function runSurvey() {
        var btn = $('run-survey-btn');
        btn.disabled = true;
        $('survey-status-text').textContent = '';
        $('results-panel').classList.add('cs-hidden');
        // Show the live connection again while the new survey runs.
        expandConnSection();
        api('/api/survey/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ port: state.selectedPort })
        }).then(function (r) {
            if (!r.ok) {
                toast(r.message || 'Could not start survey', 'error');
                btn.disabled = false;
                return;
            }
            $('survey-progress').style.display = 'flex';
            $('survey-message').textContent = 'Starting survey...';
            pollSurvey();
        }).catch(function () {
            btn.disabled = false;
            toast('Could not start survey', 'error');
        });
    }

    function pollSurvey() {
        if (state.pollTimer) clearTimeout(state.pollTimer);
        api('/api/survey/status').then(function (s) {
            $('survey-message').textContent = s.message || '';
            if (s.state === 'running') {
                state.pollTimer = setTimeout(pollSurvey, 1000);
                return;
            }
            // Finished (done or error). Clear the poll timer so button gating
            // (which treats a non-null pollTimer as "survey running") resumes
            // normal connection-based enable/disable.
            state.pollTimer = null;
            $('survey-progress').style.display = 'none';
            $('run-survey-btn').disabled = false;
            if (s.state === 'error') {
                $('survey-status-text').textContent = s.message;
                toast(s.message || 'Survey failed', 'error');
                return;
            }
            $('survey-status-text').textContent = s.message || '';
            var groups = s.groups || [];
            // Refresh modem status (survey may have touched the connection),
            // then render results and collapse the connection tiles so the
            // results are prominent. Rendering after the status refresh means
            // the eSIM profile matching uses the latest modem data.
            loadModemStatus().then(function () {
                renderResults(groups);
                if (groups.length) collapseConnSection();
            });
        }).catch(function () {
            state.pollTimer = setTimeout(pollSurvey, 1500);
        });
    }

    function renderResults(groups) {
        var panel = $('results-panel');
        var list = $('carrier-list');
        if (!groups.length) {
            // Only show the "Results by Carrier" section when there are
            // results to show. An empty survey leaves the panel hidden.
            state.lastGroups = [];
            panel.classList.add('cs-hidden');
            $('results-summary').textContent = '';
            $('export-csv-btn').style.display = 'none';
            list.innerHTML = '';
            return;
        }
        $('export-csv-btn').style.display = '';
        state.lastGroups = groups;
        var totalCells = groups.reduce(function (n, g) { return n + g.cell_count; }, 0);
        $('results-summary').textContent = groups.length + ' carriers, ' + totalCells + ' cells';

        var html = '';
        groups.forEach(function (g, idx) {
            var isUnknown = !g.plmn;
            var title = isUnknown ? 'Unknown carrier' : escapeHtml(g.network);
            var sub = isUnknown ? 'PLMN could not be decoded'
                : escapeHtml(g.country) + ' &middot; PLMN ' + g.plmn;
            var best = g.best_signal != null ? g.best_signal + ' dBm' : '&mdash;';
            var lockBtn = isUnknown ? '' :
                '<button type="button" class="btn btn-primary btn-sm cs-lock-btn" data-plmn="' + g.plmn +
                '" data-network="' + escapeAttr(g.network) + '"><i class="fas fa-lock"></i> Lock Carrier PLMN</button>';

            // If the modem has an operational eSIM profile for this carrier,
            // offer a button to activate (enable) it next to the PLMN lock.
            var esimBtn = '';
            var profile = isUnknown ? null : esimProfileForCarrier(g.network);
            if (profile && !profile.active) {
                esimBtn = '<button type="button" class="btn btn-secondary btn-sm cs-esim-btn" ' +
                    'data-iccid="' + escapeAttr(profile.iccid) + '" ' +
                    'data-profile="' + escapeAttr(profile.profile_name) + '" ' +
                    'data-network="' + escapeAttr(g.network) + '">' +
                    '<i class="fas fa-sim-card"></i> Activate eSIM Profile</button>';
            } else if (profile && profile.active) {
                esimBtn = '<span class="cs-pill ok" title="eSIM profile ' +
                    escapeAttr(profile.profile_name) + ' is active">' +
                    '<i class="fas fa-sim-card"></i> eSIM active</span>';
            }

            html += '<div class="carrier-card open">';
            html += '  <div class="carrier-head">';
            html += '    <div class="carrier-title">' + title + '<small>' + sub + '</small></div>';
            html += '    <div class="carrier-meta">';
            html += '      <span class="cs-muted">' + g.cell_count + ' cells</span>';
            html += '      <span class="cs-pill" style="background:rgba(99,102,241,0.12);color:' + signalColor(g.best_signal) + '"><i class="fas fa-signal"></i> ' + best + '</span>';
            html += '      ' + esimBtn;
            html += '      ' + lockBtn;
            html += '      <i class="fas fa-chevron-down carrier-chevron"></i>';
            html += '    </div>';
            html += '  </div>';
            html += '  <div class="carrier-body"><table class="cs-table"><thead><tr>' +
                '<th>Type</th><th>Band</th><th>Bandwidth</th><th>Channel</th><th>RSRP</th><th>RSRQ</th><th>PCI</th><th>Cell ID</th><th>TAC</th>' +
                '</tr></thead><tbody>';
            g.cells.forEach(function (c) {
                var is5g = c.rat.indexOf('5G') >= 0;
                var tag = is5g
                    ? '<span class="rat-tag rat-5g">5G</span>'
                    : '<span class="rat-tag rat-lte">LTE</span>';
                // 5G bands are written 'n41'; LTE bands 'B2'.
                var bandPrefix = is5g ? 'n' : 'B';
                html += '<tr>' +
                    '<td>' + tag + '</td>' +
                    '<td>' + ((c.band && c.band !== '0') ? bandPrefix + escapeHtml(c.band) : '') + '</td>' +
                    '<td>' + ((c.bandwidth && c.bandwidth !== '0') ? escapeHtml(c.bandwidth) + ' MHz' : '') + '</td>' +
                    '<td>' + escapeHtml(c.channel || '') + '</td>' +
                    '<td>' + (c.rsrp !== '' ? escapeHtml(c.rsrp) + ' dBm' : '') + '</td>' +
                    '<td>' + (c.rsrq !== '' ? escapeHtml(c.rsrq) + ' dB' : '') + '</td>' +
                    '<td>' + escapeHtml(c.pci || '') + '</td>' +
                    '<td>' + escapeHtml(c.cell_id || '') + '</td>' +
                    '<td>' + escapeHtml(c.tac || '') + '</td>' +
                    '</tr>';
            });
            html += '</tbody></table></div></div>';
        });
        list.innerHTML = html;
        panel.classList.remove('cs-hidden');

        // Wire up collapse toggles and action buttons (delegation-free, scoped).
        list.querySelectorAll('.carrier-head').forEach(function (head) {
            head.addEventListener('click', function (e) {
                if (e.target.closest('.cs-lock-btn') ||
                    e.target.closest('.cs-esim-btn')) return;
                head.parentElement.classList.toggle('open');
            });
        });
        list.querySelectorAll('.cs-lock-btn').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                openLockModal(btn.getAttribute('data-plmn'), btn.getAttribute('data-network'));
            });
        });
        list.querySelectorAll('.cs-esim-btn').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                openEsimModal(btn.getAttribute('data-iccid'),
                    btn.getAttribute('data-profile'),
                    btn.getAttribute('data-network'));
            });
        });
    }


    // ---- Lock / unlock ---------------------------------------------------

    function openLockModal(plmn, network) {
        state.pendingLock = { plmn: plmn, network: network };
        $('lock-modal-text').innerHTML = 'Lock <strong>' + escapeHtml(network) +
            '</strong> (PLMN ' + escapeHtml(plmn) + ') on modem ' +
            escapeHtml(state.selectedPort) + '?';
        $('lock-modal').classList.add('show');
    }

    function closeLockModal() {
        $('lock-modal').classList.remove('show');
        state.pendingLock = null;
    }

    function confirmLock() {
        if (!state.pendingLock || !state.currentModem) { closeLockModal(); return; }
        var cfg = state.currentModem.config_id;
        var plmn = state.pendingLock.plmn;
        var btn = $('lock-confirm');
        btn.disabled = true;
        api('/api/lock', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ config_id: cfg, plmn: plmn })
        }).then(function (r) {
            btn.disabled = false;
            closeLockModal();
            toast(r.message, r.ok ? 'success' : 'error');
            if (r.ok) setTimeout(loadModemStatus, 1500);
        }).catch(function () {
            btn.disabled = false;
            closeLockModal();
            toast('Lock request failed', 'error');
        });
    }

    function unlockModem() {
        if (!state.currentModem) return;
        var cfg = state.currentModem.config_id;
        $('unlock-btn').disabled = true;
        api('/api/unlock', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ config_id: cfg })
        }).then(function (r) {
            $('unlock-btn').disabled = false;
            toast(r.message, r.ok ? 'success' : 'error');
            if (r.ok) setTimeout(loadModemStatus, 1500);
        }).catch(function () {
            $('unlock-btn').disabled = false;
            toast('Unlock request failed', 'error');
        });
    }

    // ---- eSIM profile activation -----------------------------------------

    function openEsimModal(iccid, profileName, network) {
        state.pendingEsim = { iccid: iccid, profile_name: profileName, network: network };
        $('esim-modal-text').innerHTML = 'Activate the <strong>' +
            escapeHtml(profileName) + '</strong> eSIM profile (ICCID ' +
            escapeHtml(iccid) + ') on modem ' + escapeHtml(state.selectedPort) + '?';
        $('esim-modal').classList.add('show');
    }

    function closeEsimModal() {
        $('esim-modal').classList.remove('show');
        state.pendingEsim = null;
    }

    function confirmEsim() {
        if (!state.pendingEsim || !state.currentModem) { closeEsimModal(); return; }
        var m = state.currentModem;
        var eid = m.esim ? m.esim.eid : null;
        var btn = $('esim-confirm');
        btn.disabled = true;
        api('/api/esim/activate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ uid: m.uid, eid: eid, iccid: state.pendingEsim.iccid })
        }).then(function (r) {
            btn.disabled = false;
            closeEsimModal();
            toast(r.message, r.ok ? 'success' : 'error');
            // The modem re-registers; refresh status after a moment so the
            // Active flag and connection tiles catch up.
            if (r.ok) setTimeout(loadModemStatus, 3000);
        }).catch(function () {
            btn.disabled = false;
            closeEsimModal();
            toast('eSIM activation request failed', 'error');
        });
    }

    // ---- CSV export ------------------------------------------------------

    function csvCell(v) {
        // Quote per RFC 4180 when the value contains a comma, quote, or newline.
        var s = (v == null) ? '' : String(v);
        if (/[",\r\n]/.test(s)) {
            s = '"' + s.replace(/"/g, '""') + '"';
        }
        return s;
    }

    function exportCsv() {
        if (!state.lastGroups.length) {
            toast('No survey results to export', 'info');
            return;
        }
        var headers = ['carrier', 'country', 'plmn', 'mcc', 'mnc', 'rat',
            'band', 'bandwidth_mhz', 'channel', 'rsrp_dbm', 'rsrq_db', 'pci',
            'cell_id', 'tac'];
        var rows = [headers.join(',')];
        // Flatten every cell of every carrier into one row.
        state.lastGroups.forEach(function (g) {
            g.cells.forEach(function (c) {
                rows.push([
                    g.network, g.country, g.plmn, g.mcc, g.mnc,
                    c.rat, c.band, c.bandwidth, c.channel, c.rsrp, c.rsrq,
                    c.pci, c.cell_id, c.tac
                ].map(csvCell).join(','));
            });
        });
        var csv = rows.join('\r\n') + '\r\n';

        var stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
        var modem = (state.selectedPort || 'modem');
        var filename = 'cell_survey_' + modem + '_' + stamp + '.csv';

        var blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    }

    // ---- Schedule --------------------------------------------------------

    // Hide the "Activate best carrier eSIM" option unless the selected modem
    // has an operational eSIM profile. Preserves the current selection when
    // possible; falls back to 'none' if eSIM was selected but is unavailable.
    function updateEsimOptionAvailability() {
        var m = state.currentModem || {};
        var esim = m.esim || {};
        var hasOperational = !!(esim.supported &&
            (esim.profiles || []).some(function (p) { return p.operational; }));
        ['startup-action', 'schedule-action'].forEach(function (id) {
            var sel = $(id);
            if (!sel) return;
            var opt = sel.querySelector('option[data-esim="1"]');
            if (!opt) return;
            opt.hidden = !hasOperational;
            opt.disabled = !hasOperational;
            if (!hasOperational && sel.value === 'esim') sel.value = 'none';
        });
        var avail = $('esim-availability-note');
        var unavail = $('esim-unavailable-note');
        if (avail && unavail) {
            avail.style.display = hasOperational ? 'block' : 'none';
            unavail.style.display = hasOperational ? 'none' : 'block';
        }
    }

    // Fill the per-trigger modem dropdowns from the detected modems. The
    // "Default (auto-select)" option maps to an empty port, which the backend
    // resolves to the default modem at run time. The modem field only shows
    // when the router has more than one modem - a single-modem router has no
    // choice to make. Preserves each select's current value across refills.
    function populateScheduleModems() {
        var modemList = state.modems || [];
        var multi = modemList.length > 1;
        document.querySelectorAll('.cs-modem-field').forEach(function (f) {
            f.style.display = multi ? '' : 'none';
        });
        document.querySelectorAll('.sched-modem-select').forEach(function (sel) {
            var prev = sel.value;
            sel.innerHTML = '';
            var def = document.createElement('option');
            def.value = '';
            def.textContent = 'Default (auto-select)';
            sel.appendChild(def);
            modemList.forEach(function (m) {
                var o = document.createElement('option');
                o.value = m.port;
                o.textContent = m.model + ' (' + m.port + ')';
                sel.appendChild(o);
            });
            // Restore prior selection if it still exists, else default ('').
            var hasPrev = Array.prototype.some.call(sel.options, function (o) {
                return o.value === prev;
            });
            sel.value = hasPrev ? prev : '';
        });
    }

    // Cron builder: mirror speedtest_web's helper so the generated expression
    // matches what the backend's cron_matches() understands.
    function cronEls() {
        return {
            preset: $('sched-preset'),
            custom: $('sched-cron-custom'),
            customRow: $('sched-custom-row'),
            builderWrap: $('sched-builder-wrap'),
            repeat: $('cron-repeat'),
            interval: $('cron-interval'),
            hour: $('cron-hour'),
            minute: $('cron-minute'),
            dow: $('cron-dow'),
            preview: $('cron-preview')
        };
    }

    function populateHourOptions() {
        var sel = $('cron-hour');
        if (!sel || sel.options.length) return;
        for (var h = 0; h < 24; h++) {
            var ampm = h < 12 ? 'AM' : 'PM';
            var disp = (h % 12 === 0 ? 12 : h % 12) + ':00 ' + ampm;
            var o = document.createElement('option');
            o.value = String(h);
            o.textContent = disp;
            sel.appendChild(o);
        }
    }

    function updateBuilderVisibility() {
        var e = cronEls();
        var mode = e.repeat.value;
        $('cron-interval-wrap').style.display = (mode === 'minutes' || mode === 'hours') ? '' : 'none';
        $('cron-hour-wrap').style.display = (mode === 'daily' || mode === 'weekly' || mode === 'weekdays') ? '' : 'none';
        $('cron-minute-wrap').style.display = (mode === 'daily' || mode === 'weekly' || mode === 'weekdays') ? '' : 'none';
        $('cron-dow-wrap').style.display = (mode === 'weekly') ? '' : 'none';
        if (mode === 'minutes') {
            e.interval.innerHTML = '<option value="5">5</option><option value="10">10</option><option value="15">15</option><option value="30">30</option>';
        } else if (mode === 'hours') {
            e.interval.innerHTML = '<option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4">4</option><option value="6">6</option><option value="8">8</option><option value="12">12</option>';
        }
        updateCronPreview();
    }

    function buildCronFromBuilder() {
        var e = cronEls();
        var mode = e.repeat.value;
        var interval = e.interval.value;
        var hour = e.hour.value;
        var minute = e.minute.value;
        var dow = e.dow.value;
        if (mode === 'minutes') return '*/' + interval + ' * * * *';
        if (mode === 'hours') return '0 */' + interval + ' * * *';
        if (mode === 'daily') return minute + ' ' + hour + ' * * *';
        if (mode === 'weekdays') return minute + ' ' + hour + ' * * 1-5';
        if (mode === 'weekly') return minute + ' ' + hour + ' * * ' + dow;
        return '0 * * * *';
    }

    function updateCronPreview() {
        $('cron-preview').textContent = getCronValue();
    }

    function getCronValue() {
        var e = cronEls();
        if (e.preset.value === 'custom') return e.custom.value.trim();
        if (e.preset.value) return e.preset.value;
        return buildCronFromBuilder();
    }

    function parseCronToBuilder(cron) {
        var e = cronEls();
        var parts = (cron || '').split(/\s+/);
        if (parts.length !== 5) return false;
        var min = parts[0], hr = parts[1], dom = parts[2], mon = parts[3], dow = parts[4];
        if (min.indexOf('/') > -1 && hr === '*') {
            e.repeat.value = 'minutes';
            updateBuilderVisibility();
            e.interval.value = min.split('/')[1];
        } else if (min === '0' && hr.indexOf('/') > -1) {
            e.repeat.value = 'hours';
            updateBuilderVisibility();
            e.interval.value = hr.split('/')[1];
        } else if (dom === '*' && mon === '*' && dow === '1-5') {
            e.repeat.value = 'weekdays';
            updateBuilderVisibility();
            e.hour.value = hr; e.minute.value = min;
        } else if (dom === '*' && mon === '*' && dow !== '*') {
            e.repeat.value = 'weekly';
            updateBuilderVisibility();
            e.hour.value = hr; e.minute.value = min; e.dow.value = dow;
        } else if (dom === '*' && mon === '*' && dow === '*') {
            e.repeat.value = 'daily';
            updateBuilderVisibility();
            e.hour.value = hr; e.minute.value = min;
        } else {
            return false;
        }
        return buildCronFromBuilder() === cron;
    }

    function syncSubOptionState() {
        $('startup-options').classList.toggle('cs-disabled', !$('sched-startup-enabled').checked);
        $('schedule-options').classList.toggle('cs-disabled', !$('sched-schedule-enabled').checked);
    }

    function applyPresetVisibility() {
        var e = cronEls();
        if (e.preset.value === 'custom') {
            e.customRow.style.display = '';
            e.builderWrap.style.display = 'none';
        } else if (e.preset.value === '') {
            e.customRow.style.display = 'none';
            e.builderWrap.style.display = '';
        } else {
            e.customRow.style.display = 'none';
            e.builderWrap.style.display = 'none';
        }
        updateCronPreview();
    }

    // Apply the saved modem ports to the dropdowns. Called after both the
    // schedule config and the modem list are available (either order), so the
    // option for a saved port exists before we select it.
    function applyScheduleModemPorts() {
        var s = state.scheduleCfg;
        if (!s) return;
        var sp = $('startup-port');
        var cp2 = $('schedule-port');
        if (sp) sp.value = Array.prototype.some.call(sp.options, function (o) {
            return o.value === (s.startup_port || '');
        }) ? (s.startup_port || '') : '';
        if (cp2) cp2.value = Array.prototype.some.call(cp2.options, function (o) {
            return o.value === (s.schedule_port || '');
        }) ? (s.schedule_port || '') : '';
    }

    function loadSchedule() {
        return api('/api/schedule').then(function (s) {
            state.scheduleCfg = s;
            $('sched-startup-enabled').checked = !!s.startup_enabled;
            $('sched-schedule-enabled').checked = !!s.schedule_enabled;
            $('startup-action').value = s.startup_action || 'none';
            $('schedule-action').value = s.schedule_action || 'none';
            applyScheduleModemPorts();
            // Restore the cron into preset/builder/custom.
            var e = cronEls();
            var cron = s.schedule_cron || '';
            if (cron) {
                var matchedPreset = false;
                for (var i = 0; i < e.preset.options.length; i++) {
                    if (e.preset.options[i].value === cron) {
                        e.preset.value = cron;
                        matchedPreset = true;
                        break;
                    }
                }
                if (!matchedPreset) {
                    if (parseCronToBuilder(cron)) {
                        e.preset.value = '';
                    } else {
                        e.preset.value = 'custom';
                        e.custom.value = cron;
                    }
                }
            }
            applyPresetVisibility();
            if (cron) e.preview.textContent = cron;
            syncSubOptionState();
            updateEsimOptionAvailability();
        }).catch(function () { /* leave defaults */ });
    }

    function saveSchedule() {
        var btn = $('save-schedule-btn');
        btn.disabled = true;
        $('schedule-save-status').textContent = '';
        var payload = {
            startup_enabled: $('sched-startup-enabled').checked,
            startup_action: $('startup-action').value,
            startup_port: $('startup-port').value,
            schedule_enabled: $('sched-schedule-enabled').checked,
            schedule_cron: getCronValue(),
            schedule_action: $('schedule-action').value,
            schedule_port: $('schedule-port').value
        };
        api('/api/schedule', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }).then(function (r) {
            btn.disabled = false;
            if (r.ok) {
                toast('Schedule saved', 'success');
                $('schedule-save-status').textContent = 'Saved.';
            } else {
                toast('Could not save schedule', 'error');
            }
        }).catch(function () {
            btn.disabled = false;
            toast('Could not save schedule', 'error');
        });
    }

    // ---- History ---------------------------------------------------------

    function triggerTag(trigger) {
        var cls = 'cs-trigger-manual', label = 'Manual';
        if (trigger === 'startup') { cls = 'cs-trigger-startup'; label = 'Startup'; }
        else if (trigger === 'schedule') { cls = 'cs-trigger-schedule'; label = 'Schedule'; }
        return '<span class="cs-trigger-tag ' + cls + '">' + label + '</span>';
    }

    function loadHistory() {
        var content = $('history-content');
        content.innerHTML = '<p class="cs-muted">Loading history...</p>';
        return api('/api/history').then(function (data) {
            var entries = data.entries || [];
            if (!entries.length) {
                $('history-summary').textContent = '';
                content.innerHTML = '<div class="cs-empty"><i class="fas fa-folder-open"></i>' +
                    'No saved surveys yet. Run a survey, or enable a schedule, and ' +
                    'completed surveys will be saved here as downloadable CSVs.</div>';
                return;
            }
            $('history-summary').textContent = entries.length + ' saved survey' + (entries.length === 1 ? '' : 's');
            var html = '<table class="cs-history-table"><thead><tr>' +
                '<th>When</th><th>Trigger</th><th>Carriers</th><th>Cells</th><th>File</th><th></th>' +
                '</tr></thead><tbody>';
            entries.forEach(function (e) {
                var dl = '/api/history/download?file=' + encodeURIComponent(e.filename);
                html += '<tr>' +
                    '<td>' + escapeHtml(e.timestamp || '') + '</td>' +
                    '<td>' + triggerTag(e.trigger) + '</td>' +
                    '<td>' + escapeHtml(String(e.carrier_count != null ? e.carrier_count : '')) + '</td>' +
                    '<td>' + escapeHtml(String(e.cell_count != null ? e.cell_count : '')) + '</td>' +
                    '<td class="cs-muted">' + escapeHtml(e.display_name || e.filename) + '</td>' +
                    '<td><a class="btn btn-secondary btn-sm" href="' + dl + '" download>' +
                    '<i class="fas fa-download"></i> Download</a></td>' +
                    '</tr>';
            });
            html += '</tbody></table>';
            content.innerHTML = html;
        }).catch(function () {
            content.innerHTML = '<p class="cs-muted">Could not load history.</p>';
        });
    }

    function openClearModal() { $('clear-modal').classList.add('show'); }
    function closeClearModal() { $('clear-modal').classList.remove('show'); }

    function confirmClearHistory() {
        var btn = $('clear-confirm');
        btn.disabled = true;
        api('/api/history/clear', { method: 'POST' }).then(function (r) {
            btn.disabled = false;
            closeClearModal();
            if (r.ok) { toast('History cleared', 'success'); loadHistory(); }
            else toast('Could not clear history', 'error');
        }).catch(function () {
            btn.disabled = false;
            closeClearModal();
            toast('Could not clear history', 'error');
        });
    }

    // ---- utils -----------------------------------------------------------

    function escapeHtml(s) {
        if (s == null) return '';
        return String(s).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }
    function escapeAttr(s) { return escapeHtml(s).replace(/"/g, '&quot;'); }

    // Normalize a carrier/profile name for loose matching: lowercase, drop
    // non-alphanumerics. Mirrors _norm_carrier() on the backend so 'AT&T'
    // matches 'att' and 'T-Mobile' matches 'tmobile'.
    function normCarrier(s) {
        return String(s == null ? '' : s).toLowerCase().replace(/[^a-z0-9]/g, '');
    }

    // Find an operational eUICC profile on the current modem matching a survey
    // carrier by name. Returns the profile dict or null.
    function esimProfileForCarrier(network) {
        var m = state.currentModem;
        if (!m || !m.esim || !m.esim.supported) return null;
        var profiles = m.esim.profiles || [];
        var target = normCarrier(network);
        if (!target) return null;
        for (var i = 0; i < profiles.length; i++) {
            var p = profiles[i];
            if (!p.operational) continue;
            var names = [normCarrier(p.profile_name), normCarrier(p.service_provider)];
            if (names.indexOf(target) >= 0) return p;
            for (var j = 0; j < names.length; j++) {
                var n = names[j];
                if (n && (n.indexOf(target) >= 0 || target.indexOf(n) >= 0)) return p;
            }
        }
        return null;
    }

    // ---- wire up ---------------------------------------------------------

    function init() {
        $('modem-select').addEventListener('change', function () {
            state.selectedPort = this.value;
            expandConnSection();
            loadModemStatus().then(updateEsimOptionAvailability);
        });
        $('conn-collapse-head').addEventListener('click', function () {
            $('conn-section').classList.toggle('open');
        });
        $('refresh-modem-btn').addEventListener('click', function () {
            loadModems().then(function () {
                populateScheduleModems();
                applyScheduleModemPorts();
            });
        });
        $('run-survey-btn').addEventListener('click', runSurvey);
        $('export-csv-btn').addEventListener('click', exportCsv);
        $('unlock-btn').addEventListener('click', unlockModem);
        $('lock-cancel').addEventListener('click', closeLockModal);
        $('lock-modal-close').addEventListener('click', closeLockModal);
        $('lock-confirm').addEventListener('click', confirmLock);
        $('lock-modal').addEventListener('click', function (e) {
            if (e.target === this) closeLockModal();
        });
        $('esim-cancel').addEventListener('click', closeEsimModal);
        $('esim-modal-close').addEventListener('click', closeEsimModal);
        $('esim-confirm').addEventListener('click', confirmEsim);
        $('esim-modal').addEventListener('click', function (e) {
            if (e.target === this) closeEsimModal();
        });

        // Schedule controls.
        populateHourOptions();
        $('sched-startup-enabled').addEventListener('change', syncSubOptionState);
        $('sched-schedule-enabled').addEventListener('change', syncSubOptionState);
        $('sched-preset').addEventListener('change', applyPresetVisibility);
        $('sched-cron-custom').addEventListener('input', updateCronPreview);
        $('cron-repeat').addEventListener('change', updateBuilderVisibility);
        $('cron-interval').addEventListener('change', updateCronPreview);
        $('cron-hour').addEventListener('change', updateCronPreview);
        $('cron-minute').addEventListener('change', updateCronPreview);
        $('cron-dow').addEventListener('change', updateCronPreview);
        $('save-schedule-btn').addEventListener('click', saveSchedule);
        updateBuilderVisibility();

        // History controls.
        $('history-refresh-btn').addEventListener('click', loadHistory);
        $('history-clear-btn').addEventListener('click', openClearModal);
        $('clear-cancel').addEventListener('click', closeClearModal);
        $('clear-modal-close').addEventListener('click', closeClearModal);
        $('clear-confirm').addEventListener('click', confirmClearHistory);
        $('clear-modal').addEventListener('click', function (e) {
            if (e.target === this) closeClearModal();
        });

        // Reload history whenever the History nav item is clicked so a survey
        // that finished in the background shows up without a full refresh.
        var historyNav = document.querySelector('.nav-item[data-element="history"]');
        if (historyNav) historyNav.addEventListener('click', function () {
            setTimeout(loadHistory, 0);
        });

        // Load modems first (sets selectedPort and modem status), then
        // restore any survey the server is already running or has finished so
        // a browser refresh doesn't lose the session. Load the saved schedule
        // and history in parallel.
        loadModems().then(function () {
            restoreSurveyState();
            updateEsimOptionAvailability();
            populateScheduleModems();
            applyScheduleModemPorts();
        });
        loadSchedule();
        loadHistory();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
