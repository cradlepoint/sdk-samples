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
        lastGroups: []        // last survey results, for CSV export
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
            loadModemStatus();
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
        var pill = $('modem-conn');
        pill.className = 'cs-pill';
        if (cstate === 'connected') {
            pill.classList.add('ok');
            pill.innerHTML = '<i class="fas fa-circle-check"></i> Connected';
        } else if (cstate === 'connecting' || cstate === 'establishing') {
            pill.classList.add('warn');
            pill.innerHTML = '<i class="fas fa-circle-notch"></i> ' + cstate;
        } else {
            pill.classList.add('bad');
            pill.innerHTML = '<i class="fas fa-circle-xmark"></i> ' + (cstate || 'disconnected');
        }
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
                return;
            }
            state.currentModem = m;
            connPill(m.connection_state);

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

            // Survey-button gating. A survey can only run when:
            //   1. the module is a supported Telit FE990/FN990, and
            //   2. the modem is actually connected (the AT channel is only
            //      usable on a connected modem; a disconnected modem can't
            //      scan).
            // Don't clobber the disabled state while a survey is in flight.
            var unsupported = $('unsupported-banner');
            var surveyBtn = $('run-survey-btn');
            var surveyRunning = state.pollTimer !== null;
            var connected = m.connection_state === 'connected';
            if (m.supported === false) {
                unsupported.style.display = 'flex';
                $('unsupported-text').textContent =
                    'The network survey is only supported on Telit FE990/FN990 '
                    + 'modules. This modem (' + escapeHtml(m.mfg_model || 'unknown')
                    + ') is not supported.';
                if (!surveyRunning) surveyBtn.disabled = true;
                surveyBtn.title = 'Unsupported modem';
            } else if (!connected) {
                unsupported.style.display = 'none';
                if (!surveyRunning) surveyBtn.disabled = true;
                surveyBtn.title = 'Modem must be connected to run a survey';
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
                $('results-panel').style.display = 'none';
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
        $('results-panel').style.display = 'none';
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
            state.lastGroups = [];
            panel.style.display = 'block';
            $('results-summary').textContent = '';
            $('export-csv-btn').style.display = 'none';
            list.innerHTML = '<p class="cs-muted">No cells were detected in this survey.</p>';
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
        panel.style.display = 'block';

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
            loadModemStatus();
        });
        $('conn-collapse-head').addEventListener('click', function () {
            $('conn-section').classList.toggle('open');
        });
        $('refresh-modem-btn').addEventListener('click', loadModems);
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
        // Load modems first (sets selectedPort and modem status), then
        // restore any survey the server is already running or has finished so
        // a browser refresh doesn't lose the session.
        loadModems().then(restoreSurveyState);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
