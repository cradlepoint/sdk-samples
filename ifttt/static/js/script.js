(function() {
    'use strict';

    var rules = [];
    var browseCallback = null;
    var ruleIdCounter = 0;
    var collapsedState = {};  // track collapsed per rule id
    var browseSelectedValue = null;  // track value at selected path
    var savedSnapshot = '';  // JSON snapshot of last saved state

    function markDirty() {
        var current = JSON.stringify(rules);
        var banner = document.getElementById('unsaved-banner');
        if (current !== savedSnapshot) {
            banner.style.display = 'flex';
        } else {
            banner.style.display = 'none';
        }
    }

    function markClean() {
        savedSnapshot = JSON.stringify(rules);
        document.getElementById('unsaved-banner').style.display = 'none';
    }

    // --- Toast Notifications (matches ncx_self_provision) ---
    var toastIcons = { success: '\u2713', error: '\u2717', warning: '\u26A0', info: '\u2139' };
    function showToast(message, type) {
        type = type || 'info';
        var container = document.getElementById('toast-container');
        var toast = document.createElement('div');
        toast.className = 'toast toast-' + type;
        var icon = document.createElement('span');
        icon.className = 'toast-icon';
        icon.textContent = toastIcons[type] || toastIcons.info;
        var msg = document.createElement('span');
        msg.className = 'toast-message';
        msg.textContent = message;
        toast.appendChild(icon);
        toast.appendChild(msg);
        container.appendChild(toast);
        setTimeout(function() { toast.classList.add('show'); }, 10);
        setTimeout(function() {
            toast.classList.remove('show');
            setTimeout(function() { if (toast.parentNode) toast.remove(); }, 300);
        }, 5000);
    }

    // --- Clipboard fallback for older browsers ---
    function fallbackCopy(text) {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.style.cssText = 'position:fixed;left:-9999px';
        document.body.appendChild(ta);
        ta.select();
        try {
            document.execCommand('copy');
            showToast('Rule JSON copied to clipboard', 'success');
        } catch (e) {
            showToast('Failed to copy to clipboard', 'error');
        }
        document.body.removeChild(ta);
    }

    // --- Dark Mode (matches Motorola template) ---
    function initDarkMode() {
        var toggle = document.getElementById('dark-mode-toggle');
        var theme = localStorage.getItem('ifttt_theme') || 'light';
        if (theme === 'dark') {
            document.body.setAttribute('data-theme', 'dark');
            toggle.textContent = '\u2600';
            toggle.title = 'Switch to light mode';
        } else {
            toggle.textContent = '\u263D';
            toggle.title = 'Switch to dark mode';
        }
        toggle.addEventListener('click', function() {
            if (document.body.getAttribute('data-theme') === 'dark') {
                document.body.removeAttribute('data-theme');
                toggle.textContent = '\u263D';
                toggle.title = 'Switch to dark mode';
                localStorage.setItem('ifttt_theme', 'light');
            } else {
                document.body.setAttribute('data-theme', 'dark');
                toggle.textContent = '\u2600';
                toggle.title = 'Switch to light mode';
                localStorage.setItem('ifttt_theme', 'dark');
            }
        });
    }

    // --- Unique IDs ---
    function nextId() { return 'rule_' + Date.now() + '_' + (++ruleIdCounter); }

    function toggleSidebarSections(show) {
        document.querySelectorAll('.sidebar-section.rules-only').forEach(function(s) {
            s.style.display = show ? '' : 'none';
        });
    }

    function showRulesSection() {
        document.getElementById('home-section').style.display = 'none';
        document.getElementById('rules-section').style.display = '';
        setActiveNav('rules-section');
        toggleSidebarSections(true);
    }

    function showHomeSection() {
        document.getElementById('home-section').style.display = '';
        document.getElementById('rules-section').style.display = 'none';
        setActiveNav('home-section');
        toggleSidebarSections(false);
    }

    function setActiveNav(sectionId) {
        document.querySelectorAll('.nav-item').forEach(function(item) {
            if (item.dataset.section === sectionId) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    }

    // --- Render all rules ---
    function renderRules() {
        var container = document.getElementById('rules-container');
        var empty = document.getElementById('empty-state');
        container.innerHTML = '';
        empty.style.display = rules.length ? 'none' : 'block';
        if (rules.length > 0) { showRulesSection(); }
        rules.forEach(function(rule, idx) {
            container.appendChild(buildRuleCard(rule, idx));
        });
        setupPaletteDrag();
        markDirty();
    }

    // --- Build a rule card ---
    function buildRuleCard(rule, idx) {
        var isCollapsed = collapsedState[rule.id] || false;
        var card = document.createElement('div');
        card.className = 'rule-card' + (rule.enabled ? '' : ' disabled') + (isCollapsed ? ' collapsed' : '');
        card.dataset.index = idx;

        // Header (clickable to collapse)
        var header = document.createElement('div');
        header.className = 'rule-header';

        var collapseIcon = document.createElement('span');
        collapseIcon.className = 'collapse-icon';
        collapseIcon.textContent = '\u25BC';

        var nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.value = rule.name;
        nameInput.placeholder = 'Rule name...';
        nameInput.setAttribute('aria-label', 'Rule name');
        nameInput.addEventListener('change', function() { rule.name = this.value; markDirty(); });
        nameInput.addEventListener('click', function(e) { e.stopPropagation(); });

        var controls = document.createElement('div');
        controls.className = 'rule-controls';

        var toggleBtn = document.createElement('button');
        toggleBtn.type = 'button';
        toggleBtn.className = 'btn btn-sm ' + (rule.enabled ? 'btn-success' : 'btn-ghost');
        toggleBtn.textContent = rule.enabled ? 'ON' : 'OFF';
        toggleBtn.title = 'Toggle rule';
        toggleBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            rule.enabled = !rule.enabled;
            showToast('Rule ' + (rule.enabled ? 'enabled' : 'disabled'), rule.enabled ? 'success' : 'error');
            renderRules();
        });

        var deleteBtn = document.createElement('button');
        deleteBtn.type = 'button';
        deleteBtn.className = 'btn btn-sm btn-danger';
        deleteBtn.textContent = 'Delete';
        deleteBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            var ruleId = rule.id;
            var ruleName = rule.name || 'Unnamed Rule';
            rules.splice(idx, 1);
            // Delete from server
            fetch('/api/rules/' + encodeURIComponent(ruleId), { method: 'DELETE' }).catch(function() {});
            showToast('Rule "' + ruleName + '" deleted', 'warning');
            savedSnapshot = JSON.stringify(rules);
            renderRules();
        });

        var copyBtn = document.createElement('button');
        copyBtn.type = 'button';
        copyBtn.className = 'btn btn-sm btn-ghost';
        copyBtn.textContent = 'Copy Rule';
        copyBtn.title = 'Copy rule JSON to clipboard';
        copyBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            var ruleData = {
                id: rule.id, name: rule.name, enabled: rule.enabled,
                logic: rule.logic, trigger: rule.trigger || 'interval',
                interval: rule.interval || 10,
                conditions: rule.conditions, actions: rule.actions
            };
            var text = JSON.stringify(ruleData, null, 2);
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(function() {
                    showToast('Rule JSON copied to clipboard', 'success');
                }).catch(function() {
                    fallbackCopy(text);
                });
            } else {
                fallbackCopy(text);
            }
        });

        controls.appendChild(toggleBtn);
        controls.appendChild(copyBtn);
        controls.appendChild(deleteBtn);
        header.appendChild(collapseIcon);
        header.appendChild(nameInput);
        header.appendChild(controls);

        // Collapse toggle on header click
        header.addEventListener('click', function() {
            collapsedState[rule.id] = !collapsedState[rule.id];
            card.classList.toggle('collapsed');
        });

        // Body
        var body = document.createElement('div');
        body.className = 'rule-body';

        // Per-rule trigger mode and interval
        var settings = document.createElement('div');
        settings.className = 'rule-item trigger-item';

        function makeSettingsGroup(input, labelText) {
            var grp = document.createElement('div');
            grp.className = 'field-group';
            var lbl = document.createElement('span');
            lbl.className = 'field-label';
            lbl.textContent = labelText;
            grp.appendChild(input);
            grp.appendChild(lbl);
            return grp;
        }

        var triggerBadge = document.createElement('span');
        triggerBadge.className = 'badge badge-trigger';
        triggerBadge.textContent = 'TRIGGER';

        var triggerSelect = document.createElement('select');
        triggerSelect.className = 'form-input';
        triggerSelect.setAttribute('aria-label', 'Trigger mode');
        [['interval', 'Polling Interval'], ['callback', 'Callback']].forEach(function(opt) {
            var o = document.createElement('option');
            o.value = opt[0]; o.textContent = opt[1];
            if ((rule.trigger || 'interval') === opt[0]) o.selected = true;
            triggerSelect.appendChild(o);
        });
        triggerSelect.addEventListener('change', function() {
            rule.trigger = this.value;
            renderRules();
        });
        triggerSelect.addEventListener('click', function(e) { e.stopPropagation(); });

        settings.appendChild(triggerBadge);
        settings.appendChild(makeSettingsGroup(triggerSelect, 'Mode'));

        if ((rule.trigger || 'interval') === 'interval') {
            var everyLabel = document.createElement('span');
            everyLabel.className = 'field-label';
            everyLabel.style.cssText = 'align-self:center;font-size:0.75rem;font-weight:700;margin:0 0.15rem';
            everyLabel.textContent = 'EVERY';
            var intervalInput = document.createElement('input');
            intervalInput.type = 'number';
            intervalInput.id = 'interval-' + rule.id;
            intervalInput.className = 'form-input short';
            intervalInput.min = '1';
            intervalInput.value = rule.interval || 10;
            intervalInput.addEventListener('change', function() {
                rule.interval = parseInt(this.value) || 10; markDirty();
            });
            intervalInput.addEventListener('click', function(e) { e.stopPropagation(); });

            var intervalUnit = document.createElement('select');
            intervalUnit.className = 'form-input';
            intervalUnit.setAttribute('aria-label', 'Interval unit');
            [['seconds','Seconds'],['minutes','Minutes'],['hours','Hours']].forEach(function(u) {
                var o = document.createElement('option');
                o.value = u[0]; o.textContent = u[1];
                if ((rule.interval_unit || 'seconds') === u[0]) o.selected = true;
                intervalUnit.appendChild(o);
            });
            intervalUnit.addEventListener('change', function() {
                rule.interval_unit = this.value; markDirty();
            });
            intervalUnit.addEventListener('click', function(e) { e.stopPropagation(); });

            settings.appendChild(everyLabel);
            settings.appendChild(makeSettingsGroup(intervalInput, 'Interval'));
            settings.appendChild(makeSettingsGroup(intervalUnit, 'Unit'));
        }

        // Logic toggle
        var logicDiv = document.createElement('div');
        logicDiv.className = 'logic-toggle';
        var allBtn = document.createElement('button');
        allBtn.type = 'button';
        allBtn.textContent = 'ALL (AND)';
        allBtn.className = rule.logic === 'all' ? 'active' : '';
        allBtn.addEventListener('click', function() { rule.logic = 'all'; renderRules(); });
        var anyBtn = document.createElement('button');
        anyBtn.type = 'button';
        anyBtn.textContent = 'ANY (OR)';
        anyBtn.className = rule.logic === 'any' ? 'active' : '';
        anyBtn.addEventListener('click', function() { rule.logic = 'any'; renderRules(); });
        logicDiv.appendChild(allBtn);
        logicDiv.appendChild(anyBtn);

        // Conditions drop zone
        var condZone = document.createElement('div');
        condZone.className = 'conditions-zone';
        var condLabel = document.createElement('div');
        condLabel.className = 'drop-zone-label';
        condLabel.textContent = 'Conditions:';
        var condDrop = document.createElement('div');
        condDrop.className = 'drop-zone';
        setupDropZone(condDrop, rule, 'conditions');
        rule.conditions.forEach(function(cond, ci) {
            if (ci > 0) {
                var logicLabel = document.createElement('div');
                logicLabel.className = 'condition-logic-label';
                logicLabel.textContent = rule.logic === 'all' ? 'AND' : 'OR';
                condDrop.appendChild(logicLabel);
            }
            condDrop.appendChild(buildConditionItem(cond, rule, ci));
        });
        condZone.appendChild(condLabel);
        condZone.appendChild(logicDiv);
        condZone.appendChild(condDrop);

        // Actions drop zone
        var actZone = document.createElement('div');
        actZone.className = 'actions-zone';
        var actLabel = document.createElement('div');
        actLabel.className = 'drop-zone-label';
        actLabel.textContent = 'Actions:';
        var actDrop = document.createElement('div');
        actDrop.className = 'drop-zone';
        setupDropZone(actDrop, rule, 'actions');
        rule.actions.forEach(function(act, ai) {
            actDrop.appendChild(buildActionItem(act, rule, ai));
        });
        actZone.appendChild(actLabel);
        actZone.appendChild(actDrop);

        // Trigger zone label
        var triggerZone = document.createElement('div');
        triggerZone.className = 'trigger-zone';
        var triggerZoneLabel = document.createElement('div');
        triggerZoneLabel.className = 'drop-zone-label';
        triggerZoneLabel.textContent = 'Initial Trigger:';
        triggerZone.appendChild(triggerZoneLabel);
        triggerZone.appendChild(settings);

        body.appendChild(triggerZone);

        // Warning for callback mode
        if ((rule.trigger || 'interval') === 'callback') {
            var warning = document.createElement('div');
            warning.className = 'warning-box';
            var warnIcon = document.createElement('span');
            warnIcon.className = 'warning-icon';
            warnIcon.textContent = '\u26A0';
            var warnText = document.createElement('span');
            warnText.textContent = 'Callbacks do not work on all paths. Status paths are generally supported, but some paths and nested objects may not trigger change events. Test your path(s) before relying on callback mode.';
            warning.appendChild(warnIcon);
            warning.appendChild(warnText);
            body.appendChild(warning);
        }

        body.appendChild(condZone);
        body.appendChild(actZone);

        card.appendChild(header);
        card.appendChild(body);
        return card;
    }

    // --- Build a condition item ---
    function buildConditionItem(cond, rule, ci) {
        var item = document.createElement('div');
        item.className = 'rule-item';

        function makeLabel(text) {
            var lbl = document.createElement('span');
            lbl.className = 'field-label';
            lbl.textContent = text;
            return lbl;
        }

        function makeGroup(input, labelText) {
            var grp = document.createElement('div');
            grp.className = 'field-group';
            grp.appendChild(input);
            grp.appendChild(makeLabel(labelText));
            return grp;
        }

        var badge = document.createElement('span');
        var condLabel = (cond.condType === 'when') ? 'WHEN' : (cond.condType === 'while' || cond.condType === 'while_time') ? 'WHILE' : (cond.condType === 'where') ? 'WHERE' : 'IF';
        var badgeClass = (cond.condType === 'when') ? 'badge-when' : (cond.condType === 'while' || cond.condType === 'while_time') ? 'badge-while' : (cond.condType === 'where') ? 'badge-where' : 'badge-if';
        badge.className = 'badge ' + badgeClass;
        badge.textContent = condLabel;

        var removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'remove-item';
        removeBtn.textContent = '\u00d7';
        removeBtn.title = 'Remove condition';
        removeBtn.addEventListener('click', function() { rule.conditions.splice(ci, 1); renderRules(); });

        // --- WHEN (time-based) condition ---
        if (cond.condType === 'when') {
            item.appendChild(badge);

            // Day of week selector
            var daySelect = document.createElement('select');
            daySelect.className = 'form-input';
            daySelect.setAttribute('aria-label', 'Day of week');
            [['any','Any Day'],['mon','Monday'],['tue','Tuesday'],['wed','Wednesday'],
             ['thu','Thursday'],['fri','Friday'],['sat','Saturday'],['sun','Sunday'],
             ['weekday','Weekdays'],['weekend','Weekends']
            ].forEach(function(d) {
                var o = document.createElement('option');
                o.value = d[0]; o.textContent = d[1];
                if ((cond.day || 'any') === d[0]) o.selected = true;
                daySelect.appendChild(o);
            });
            daySelect.addEventListener('change', function() { cond.day = this.value; markDirty(); });

            // Time input
            var timeInput = document.createElement('input');
            timeInput.type = 'time';
            timeInput.className = 'form-input';
            timeInput.value = cond.time || '00:00';
            timeInput.setAttribute('aria-label', 'Start time');
            timeInput.addEventListener('change', function() { cond.time = this.value; markDirty(); });

            item.appendChild(makeGroup(daySelect, 'Day'));
            item.appendChild(makeGroup(timeInput, 'Start Time'));

            // REPEAT label
            var repeatLabel = document.createElement('span');
            repeatLabel.className = 'field-label';
            repeatLabel.style.cssText = 'align-self:center;font-size:0.75rem;font-weight:700;margin:0 0.15rem';
            repeatLabel.textContent = 'REPEAT';
            item.appendChild(repeatLabel);

            // Repeat mode selector
            var repeatMode = document.createElement('select');
            repeatMode.className = 'form-input';
            repeatMode.setAttribute('aria-label', 'Repeat mode');
            [['once','Once'],['every','Every'],['times','X Times']].forEach(function(opt) {
                var o = document.createElement('option');
                o.value = opt[0]; o.textContent = opt[1];
                if ((cond.repeat_mode || 'once') === opt[0]) o.selected = true;
                repeatMode.appendChild(o);
            });
            repeatMode.addEventListener('change', function() {
                cond.repeat_mode = this.value;
                if (this.value === 'once') { delete cond.repeat_value; delete cond.repeat_unit; delete cond.repeat_times; }
                markDirty(); renderRules();
            });
            item.appendChild(makeGroup(repeatMode, 'Mode'));

            if ((cond.repeat_mode || 'once') === 'every') {
                // Repeat interval number
                var repeatInput = document.createElement('input');
                repeatInput.type = 'number';
                repeatInput.className = 'form-input short';
                repeatInput.min = '1';
                repeatInput.value = cond.repeat_value || 1;
                repeatInput.setAttribute('aria-label', 'Repeat interval');
                repeatInput.addEventListener('change', function() {
                    cond.repeat_value = parseInt(this.value) || 1; markDirty();
                });

                // Repeat unit selector
                var repeatUnit = document.createElement('select');
                repeatUnit.className = 'form-input';
                repeatUnit.setAttribute('aria-label', 'Repeat unit');
                [['seconds','Seconds'],['minutes','Minutes'],['hours','Hours'],
                 ['days','Days'],['weeks','Weeks'],['months','Months']
                ].forEach(function(u) {
                    var o = document.createElement('option');
                    o.value = u[0]; o.textContent = u[1];
                    if ((cond.repeat_unit || 'hours') === u[0]) o.selected = true;
                    repeatUnit.appendChild(o);
                });
                repeatUnit.addEventListener('change', function() { cond.repeat_unit = this.value; markDirty(); });

                item.appendChild(makeGroup(repeatInput, 'Interval'));
                item.appendChild(makeGroup(repeatUnit, 'Unit'));

                // FOR duration limit
                var forLabel = document.createElement('span');
                forLabel.className = 'field-label';
                forLabel.style.cssText = 'align-self:center;font-size:0.75rem;font-weight:700;margin:0 0.15rem';
                forLabel.textContent = 'FOR';
                item.appendChild(forLabel);

                var forInput = document.createElement('input');
                forInput.type = 'number';
                forInput.className = 'form-input short';
                forInput.min = '0';
                forInput.value = cond.for_value || 0;
                forInput.setAttribute('aria-label', 'Duration limit');
                forInput.addEventListener('change', function() {
                    cond.for_value = parseInt(this.value) || 0; markDirty();
                });

                var forUnit = document.createElement('select');
                forUnit.className = 'form-input';
                forUnit.setAttribute('aria-label', 'Duration limit unit');
                [['minutes','Minutes'],['hours','Hours'],['days','Days']].forEach(function(u) {
                    var o = document.createElement('option');
                    o.value = u[0]; o.textContent = u[1];
                    if ((cond.for_unit || 'hours') === u[0]) o.selected = true;
                    forUnit.appendChild(o);
                });
                forUnit.addEventListener('change', function() { cond.for_unit = this.value; markDirty(); });

                item.appendChild(makeGroup(forInput, 'Duration'));
                item.appendChild(makeGroup(forUnit, 'Unit'));
            } else if ((cond.repeat_mode || 'once') === 'times') {
                var timesInput = document.createElement('input');
                timesInput.type = 'number';
                timesInput.className = 'form-input short';
                timesInput.min = '1';
                timesInput.value = cond.repeat_times || 1;
                timesInput.setAttribute('aria-label', 'Number of times');
                timesInput.addEventListener('change', function() {
                    cond.repeat_times = parseInt(this.value) || 1; markDirty();
                });
                item.appendChild(makeGroup(timesInput, 'Count'));
            }

            var spacer = document.createElement('span');
            spacer.style.cssText = 'flex:1';
            item.appendChild(spacer);
            item.appendChild(removeBtn);
            return item;
        }

        // --- WHERE (GPS location) condition ---
        if (cond.condType === 'where') {
            item.appendChild(badge);

            // Current location display + fetch button
            var locGroup = document.createElement('div');
            locGroup.className = 'field-group';
            var locRow = document.createElement('div');
            locRow.style.cssText = 'display:flex;align-items:center;gap:0.25rem';
            var locDisplay = document.createElement('span');
            locDisplay.className = 'gps-current-loc';
            locDisplay.textContent = 'LIVE GPS';
            var locFetchBtn = document.createElement('button');
            locFetchBtn.type = 'button';
            locFetchBtn.className = 'browse-btn';
            locFetchBtn.textContent = '\uD83D\uDCCD';
            locFetchBtn.title = 'Fetch current router GPS location';
            locFetchBtn.addEventListener('click', function() {
                locDisplay.textContent = 'Fetching...';
                fetch('/api/browse?path=status/gps/fix')
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (data.data && typeof data.data === 'object') {
                        var lat = data.data.latitude || data.data.lat || '?';
                        var lon = data.data.longitude || data.data.lon || '?';
                        // Convert DMS object {degree, minute, second} to decimal
                        function dmsToDecimal(v) {
                            if (v && typeof v === 'object' && 'degree' in v) {
                                var deg = v.degree || 0;
                                var min = v.minute || 0;
                                var sec = v.second || 0;
                                var sign = deg < 0 ? -1 : 1;
                                return (Math.abs(deg) + min / 60 + sec / 3600) * sign;
                            }
                            return parseFloat(v);
                        }
                        var latDec = dmsToDecimal(lat);
                        var lonDec = dmsToDecimal(lon);
                        if (!isNaN(latDec) && !isNaN(lonDec)) {
                            locDisplay.textContent = latDec.toFixed(6) + ', ' + lonDec.toFixed(6);
                            locDisplay.title = 'Decimal: ' + latDec.toFixed(6) + ' / ' + lonDec.toFixed(6);
                        } else {
                            locDisplay.textContent = 'Parse error';
                        }
                    } else {
                        locDisplay.textContent = 'No GPS fix';
                    }
                })
                .catch(function() { locDisplay.textContent = 'Error'; });
            });
            locRow.appendChild(locDisplay);
            locRow.appendChild(locFetchBtn);
            locGroup.appendChild(locRow);
            var locLabel = document.createElement('span');
            locLabel.className = 'field-label';
            locLabel.textContent = 'Router GPS (re-read each poll)';
            locGroup.appendChild(locLabel);
            item.appendChild(locGroup);

            // IS label
            var geoIsLabel = document.createElement('span');
            geoIsLabel.className = 'field-label';
            geoIsLabel.style.cssText = 'align-self:center;font-size:0.75rem;font-weight:700;margin:0 0.15rem';
            geoIsLabel.textContent = 'IS';
            item.appendChild(geoIsLabel);

            // Operator: within / not_within
            var geoOpSelect = document.createElement('select');
            geoOpSelect.className = 'form-input';
            geoOpSelect.setAttribute('aria-label', 'Location operator');
            [['within','Within'],['not_within','Not Within']].forEach(function(op) {
                var o = document.createElement('option');
                o.value = op[0]; o.textContent = op[1];
                if ((cond.operator || 'within') === op[0]) o.selected = true;
                geoOpSelect.appendChild(o);
            });
            geoOpSelect.addEventListener('change', function() { cond.operator = this.value; markDirty(); });
            item.appendChild(makeGroup(geoOpSelect, 'Operator'));

            // Radius
            var radiusInput = document.createElement('input');
            radiusInput.type = 'number';
            radiusInput.className = 'form-input short';
            radiusInput.min = '0.1';
            radiusInput.step = '0.1';
            radiusInput.value = cond.radius || 1;
            radiusInput.setAttribute('aria-label', 'Radius');
            radiusInput.addEventListener('change', function() { cond.radius = parseFloat(this.value) || 1; markDirty(); });

            var radiusUnit = document.createElement('select');
            radiusUnit.className = 'form-input';
            radiusUnit.setAttribute('aria-label', 'Radius unit');
            [['km','km'],['mi','mi']].forEach(function(u) {
                var o = document.createElement('option');
                o.value = u[0]; o.textContent = u[1];
                if ((cond.radius_unit || 'km') === u[0]) o.selected = true;
                radiusUnit.appendChild(o);
            });
            radiusUnit.addEventListener('change', function() { cond.radius_unit = this.value; markDirty(); });

            item.appendChild(makeGroup(radiusInput, 'Radius'));
            item.appendChild(makeGroup(radiusUnit, 'Unit'));

            // OF label
            var ofLabel = document.createElement('span');
            ofLabel.className = 'field-label';
            ofLabel.style.cssText = 'align-self:center;font-size:0.75rem;font-weight:700;margin:0 0.15rem';
            ofLabel.textContent = 'OF';
            item.appendChild(ofLabel);

            // Target lat/lon
            var latInput = document.createElement('input');
            latInput.type = 'text';
            latInput.className = 'form-input';
            latInput.value = cond.lat || '';
            latInput.placeholder = 'Latitude';
            latInput.style.width = '8rem';
            latInput.setAttribute('aria-label', 'Target latitude');
            latInput.addEventListener('change', function() { cond.lat = this.value; markDirty(); });

            var lonInput = document.createElement('input');
            lonInput.type = 'text';
            lonInput.className = 'form-input';
            lonInput.value = cond.lon || '';
            lonInput.placeholder = 'Longitude';
            lonInput.style.width = '8rem';
            lonInput.setAttribute('aria-label', 'Target longitude');
            lonInput.addEventListener('change', function() { cond.lon = this.value; markDirty(); });

            item.appendChild(makeGroup(latInput, 'Target Lat'));
            item.appendChild(makeGroup(lonInput, 'Target Lon'));

            // Sustain options
            var geoForLabel = document.createElement('span');
            geoForLabel.className = 'field-label';
            geoForLabel.style.cssText = 'align-self:center;font-size:0.75rem;font-weight:700;margin:0 0.15rem';
            geoForLabel.textContent = 'FOR';

            var geoSustainSelect = document.createElement('select');
            geoSustainSelect.className = 'form-input';
            geoSustainSelect.setAttribute('aria-label', 'Sustain mode');
            var geoSustainOpts = [['none', 'Every Time'], ['duration', 'Duration']];
            if ((rule.trigger || 'interval') === 'interval') {
                geoSustainOpts.push(['intervals', 'Intervals']);
            }
            geoSustainOpts.forEach(function(opt) {
                var o = document.createElement('option');
                o.value = opt[0]; o.textContent = opt[1];
                if ((cond.sustain || 'none') === opt[0]) o.selected = true;
                geoSustainSelect.appendChild(o);
            });
            geoSustainSelect.addEventListener('change', function() {
                cond.sustain = this.value;
                if (this.value === 'none') { delete cond.sustain_value; }
                markDirty(); renderRules();
            });
            item.appendChild(geoForLabel);
            item.appendChild(makeGroup(geoSustainSelect, 'Sustain'));

            if (cond.sustain === 'duration') {
                var geoDurInput = document.createElement('input');
                geoDurInput.type = 'number';
                geoDurInput.className = 'form-input short';
                geoDurInput.min = '1';
                geoDurInput.value = cond.sustain_value || 5;
                geoDurInput.setAttribute('aria-label', 'Duration value');
                geoDurInput.addEventListener('change', function() { cond.sustain_value = parseInt(this.value) || 1; markDirty(); });
                item.appendChild(makeGroup(geoDurInput, 'Value'));

                var geoDurUnit = document.createElement('select');
                geoDurUnit.className = 'form-input';
                geoDurUnit.setAttribute('aria-label', 'Duration unit');
                [['seconds','Seconds'],['minutes','Minutes'],['hours','Hours']].forEach(function(u) {
                    var o = document.createElement('option');
                    o.value = u[0]; o.textContent = u[1];
                    if ((cond.sustain_unit || 'seconds') === u[0]) o.selected = true;
                    geoDurUnit.appendChild(o);
                });
                geoDurUnit.addEventListener('change', function() { cond.sustain_unit = this.value; markDirty(); });
                item.appendChild(makeGroup(geoDurUnit, 'Unit'));
            } else if (cond.sustain === 'intervals') {
                var geoIntInput = document.createElement('input');
                geoIntInput.type = 'number';
                geoIntInput.className = 'form-input short';
                geoIntInput.min = '1';
                geoIntInput.value = cond.sustain_value || 3;
                geoIntInput.setAttribute('aria-label', 'Number of intervals');
                geoIntInput.addEventListener('change', function() { cond.sustain_value = parseInt(this.value) || 1; markDirty(); });
                item.appendChild(makeGroup(geoIntInput, 'Count'));
            }

            var geoTestBtn = document.createElement('button');
            geoTestBtn.type = 'button';
            geoTestBtn.className = 'btn btn-sm btn-primary';
            geoTestBtn.textContent = '\u25B6 Test';
            geoTestBtn.addEventListener('click', function() { testCondition(cond, item); });

            var geoSpacer = document.createElement('span');
            geoSpacer.style.cssText = 'flex:1';
            item.appendChild(geoSpacer);
            item.appendChild(geoTestBtn);
            item.appendChild(removeBtn);
            return item;
        }

        // --- WHILE (time window) condition ---
        if (cond.condType === 'while_time') {
            item.appendChild(badge);

            var dayOpts = [['any','Any Day'],['mon','Monday'],['tue','Tuesday'],['wed','Wednesday'],
                ['thu','Thursday'],['fri','Friday'],['sat','Saturday'],['sun','Sunday'],
                ['weekday','Weekdays'],['weekend','Weekends']];

            var startDaySelect = document.createElement('select');
            startDaySelect.className = 'form-input';
            startDaySelect.setAttribute('aria-label', 'Start day');
            dayOpts.forEach(function(d) {
                var o = document.createElement('option');
                o.value = d[0]; o.textContent = d[1];
                if ((cond.start_day || 'any') === d[0]) o.selected = true;
                startDaySelect.appendChild(o);
            });
            startDaySelect.addEventListener('change', function() { cond.start_day = this.value; markDirty(); });

            var startTimeInput = document.createElement('input');
            startTimeInput.type = 'time';
            startTimeInput.className = 'form-input';
            startTimeInput.value = cond.start_time || '09:00';
            startTimeInput.setAttribute('aria-label', 'Start time');
            startTimeInput.addEventListener('change', function() { cond.start_time = this.value; markDirty(); });

            item.appendChild(makeGroup(startDaySelect, 'Start Day'));
            item.appendChild(makeGroup(startTimeInput, 'Start Time'));

            var toTimeLabel = document.createElement('span');
            toTimeLabel.className = 'field-label';
            toTimeLabel.style.cssText = 'align-self:center;font-size:0.75rem;font-weight:700;margin:0 0.15rem';
            toTimeLabel.textContent = 'TO';
            item.appendChild(toTimeLabel);

            var endDaySelect = document.createElement('select');
            endDaySelect.className = 'form-input';
            endDaySelect.setAttribute('aria-label', 'End day');
            dayOpts.forEach(function(d) {
                var o = document.createElement('option');
                o.value = d[0]; o.textContent = d[1];
                if ((cond.end_day || 'any') === d[0]) o.selected = true;
                endDaySelect.appendChild(o);
            });
            endDaySelect.addEventListener('change', function() { cond.end_day = this.value; markDirty(); });

            var endTimeInput = document.createElement('input');
            endTimeInput.type = 'time';
            endTimeInput.className = 'form-input';
            endTimeInput.value = cond.end_time || '17:00';
            endTimeInput.setAttribute('aria-label', 'End time');
            endTimeInput.addEventListener('change', function() { cond.end_time = this.value; markDirty(); });

            item.appendChild(makeGroup(endDaySelect, 'End Day'));
            item.appendChild(makeGroup(endTimeInput, 'End Time'));

            var wtSpacer = document.createElement('span');
            wtSpacer.style.cssText = 'flex:1';
            item.appendChild(wtSpacer);
            item.appendChild(removeBtn);
            return item;
        }

        // --- WHILE (sustained path/value) condition ---
        if (cond.condType === 'while') {
            item.appendChild(badge);

            var wPathInput = document.createElement('input');
            wPathInput.type = 'text';
            wPathInput.className = 'form-input';
            wPathInput.value = cond.path;
            wPathInput.placeholder = 'status/wan/connection_state';
            wPathInput.style.width = '14rem';
            wPathInput.setAttribute('aria-label', 'Condition path');
            wPathInput.addEventListener('change', function() { cond.path = this.value; markDirty(); });

            var wBrowseBtn = document.createElement('button');
            wBrowseBtn.type = 'button';
            wBrowseBtn.className = 'browse-btn';
            wBrowseBtn.textContent = '...';
            wBrowseBtn.title = 'Browse config store';
            wBrowseBtn.addEventListener('click', function() {
                openBrowser(cond.path || 'status', function(path, val) {
                    cond.path = path; wPathInput.value = path;
                    if (val !== null && val !== undefined) { cond.value = val; renderRules(); }
                });
            });

            var wOpSelect = document.createElement('select');
            wOpSelect.className = 'form-input';
            wOpSelect.setAttribute('aria-label', 'Operator');
            [['equals','=='],['not_equals','!='],['contains','contains'],['not_contains','!contains'],
             ['greater_than','>'],['less_than','<'],['greater_equal','>='],['less_equal','<='],
             ['exists','exists'],['not_exists','!exists']
            ].forEach(function(op) {
                var opt = document.createElement('option');
                opt.value = op[0]; opt.textContent = op[1];
                if (cond.operator === op[0]) opt.selected = true;
                wOpSelect.appendChild(opt);
            });
            wOpSelect.addEventListener('change', function() { cond.operator = this.value; markDirty(); renderRules(); });

            var wValInput = document.createElement('input');
            wValInput.type = 'text';
            wValInput.className = 'form-input';
            wValInput.value = cond.value;
            wValInput.placeholder = 'value';
            wValInput.style.width = '8rem';
            wValInput.setAttribute('aria-label', 'Condition value');
            wValInput.addEventListener('change', function() { cond.value = this.value; markDirty(); });

            var wIsLabel = document.createElement('span');
            wIsLabel.className = 'field-label';
            wIsLabel.style.cssText = 'align-self:center;font-size:0.75rem;font-weight:700;margin:0 0.15rem';
            wIsLabel.textContent = 'IS';

            item.appendChild(wBrowseBtn);
            item.appendChild(makeGroup(wPathInput, 'Path'));
            item.appendChild(wIsLabel);
            item.appendChild(makeGroup(wOpSelect, 'Operator'));

            var wHideValue = (cond.operator === 'exists' || cond.operator === 'not_exists');
            var wToLabel = document.createElement('span');
            wToLabel.className = 'field-label';
            wToLabel.style.cssText = 'align-self:center;font-size:0.75rem;font-weight:700;margin:0 0.15rem';
            wToLabel.textContent = 'TO';
            if (wHideValue) wToLabel.style.display = 'none';
            var wValGroup = makeGroup(wValInput, 'Value');
            if (wHideValue) wValGroup.style.display = 'none';
            item.appendChild(wToLabel);
            item.appendChild(wValGroup);

            // FOR label + sustain
            var wForLabel = document.createElement('span');
            wForLabel.className = 'field-label';
            wForLabel.style.cssText = 'align-self:center;font-size:0.75rem;font-weight:700;margin:0 0.15rem';
            wForLabel.textContent = 'FOR';

            var wSustainSelect = document.createElement('select');
            wSustainSelect.className = 'form-input';
            wSustainSelect.setAttribute('aria-label', 'Sustain mode');
            var wSustainOpts = [['duration', 'Duration']];
            if ((rule.trigger || 'interval') === 'interval') {
                wSustainOpts.push(['intervals', 'Intervals']);
            }
            wSustainOpts.forEach(function(opt) {
                var o = document.createElement('option');
                o.value = opt[0]; o.textContent = opt[1];
                if ((cond.sustain || 'duration') === opt[0]) o.selected = true;
                wSustainSelect.appendChild(o);
            });
            wSustainSelect.addEventListener('change', function() {
                cond.sustain = this.value; markDirty(); renderRules();
            });
            item.appendChild(wForLabel);
            item.appendChild(makeGroup(wSustainSelect, 'Sustain'));

            if ((cond.sustain || 'duration') === 'duration') {
                var wDurInput = document.createElement('input');
                wDurInput.type = 'number';
                wDurInput.className = 'form-input short';
                wDurInput.min = '1';
                wDurInput.value = cond.sustain_value || 5;
                wDurInput.setAttribute('aria-label', 'Duration value');
                wDurInput.addEventListener('change', function() { cond.sustain_value = parseInt(this.value) || 1; markDirty(); });
                item.appendChild(makeGroup(wDurInput, 'Value'));

                var wDurUnit = document.createElement('select');
                wDurUnit.className = 'form-input';
                wDurUnit.setAttribute('aria-label', 'Duration unit');
                [['seconds','Seconds'],['minutes','Minutes'],['hours','Hours']].forEach(function(u) {
                    var o = document.createElement('option');
                    o.value = u[0]; o.textContent = u[1];
                    if ((cond.sustain_unit || 'seconds') === u[0]) o.selected = true;
                    wDurUnit.appendChild(o);
                });
                wDurUnit.addEventListener('change', function() { cond.sustain_unit = this.value; markDirty(); });
                item.appendChild(makeGroup(wDurUnit, 'Unit'));
            } else if (cond.sustain === 'intervals') {
                var wIntInput = document.createElement('input');
                wIntInput.type = 'number';
                wIntInput.className = 'form-input short';
                wIntInput.min = '1';
                wIntInput.value = cond.sustain_value || 3;
                wIntInput.setAttribute('aria-label', 'Number of intervals');
                wIntInput.addEventListener('change', function() { cond.sustain_value = parseInt(this.value) || 1; markDirty(); });
                item.appendChild(makeGroup(wIntInput, 'Count'));
            }

            var wTestBtn = document.createElement('button');
            wTestBtn.type = 'button';
            wTestBtn.className = 'btn btn-sm btn-primary';
            wTestBtn.textContent = '\u25B6 Test';
            wTestBtn.addEventListener('click', function() { testCondition(cond, item); });

            var wSpacer = document.createElement('span');
            wSpacer.style.cssText = 'flex:1';
            item.appendChild(wSpacer);
            item.appendChild(wTestBtn);
            item.appendChild(removeBtn);
            return item;
        }

        // --- IF (path-based, point-in-time) condition ---

        var pathInput = document.createElement('input');
        pathInput.type = 'text';
        pathInput.className = 'form-input';
        pathInput.value = cond.path;
        pathInput.placeholder = 'status/wan/connection_state';
        pathInput.style.width = '14rem';
        pathInput.setAttribute('aria-label', 'Condition path');
        pathInput.addEventListener('change', function() { cond.path = this.value; markDirty(); });

        var browseBtn = document.createElement('button');
        browseBtn.type = 'button';
        browseBtn.className = 'browse-btn';
        browseBtn.textContent = '...';
        browseBtn.title = 'Browse config store';
        browseBtn.addEventListener('click', function() {
            openBrowser(cond.path || 'status', function(path, val) {
                cond.path = path; pathInput.value = path;
                if (val !== null && val !== undefined) { cond.value = val; renderRules(); }
            });
        });

        var opSelect = document.createElement('select');
        opSelect.className = 'form-input';
        opSelect.setAttribute('aria-label', 'Operator');
        [['equals','=='],['not_equals','!='],['contains','contains'],['not_contains','!contains'],
         ['greater_than','>'],['less_than','<'],['greater_equal','>='],['less_equal','<='],
         ['exists','exists'],['not_exists','!exists']
        ].forEach(function(op) {
            var opt = document.createElement('option');
            opt.value = op[0]; opt.textContent = op[1];
            if (cond.operator === op[0]) opt.selected = true;
            opSelect.appendChild(opt);
        });
        opSelect.addEventListener('change', function() { cond.operator = this.value; markDirty(); renderRules(); });

        var valInput = document.createElement('input');
        valInput.type = 'text';
        valInput.className = 'form-input';
        valInput.value = cond.value;
        valInput.placeholder = 'value';
        valInput.style.width = '8rem';
        valInput.setAttribute('aria-label', 'Condition value');
        valInput.addEventListener('change', function() { cond.value = this.value; markDirty(); });

        var testBtn = document.createElement('button');
        testBtn.type = 'button';
        testBtn.className = 'btn btn-sm btn-primary';
        testBtn.textContent = '\u25B6 Test';
        testBtn.addEventListener('click', function() { testCondition(cond, item); });

        var isLabel = document.createElement('span');
        isLabel.className = 'field-label';
        isLabel.style.cssText = 'align-self:center;font-size:0.75rem;font-weight:700;margin:0 0.15rem';
        isLabel.textContent = 'IS';

        item.appendChild(badge);
        item.appendChild(browseBtn);
        item.appendChild(makeGroup(pathInput, 'Path'));
        item.appendChild(isLabel);
        item.appendChild(makeGroup(opSelect, 'Operator'));

        var hideValue = (cond.operator === 'exists' || cond.operator === 'not_exists');

        var toLabel = document.createElement('span');
        toLabel.className = 'field-label';
        toLabel.style.cssText = 'align-self:center;font-size:0.75rem;font-weight:700;margin:0 0.15rem';
        toLabel.textContent = 'TO';
        if (hideValue) toLabel.style.display = 'none';

        var valGroup = makeGroup(valInput, 'Value');
        if (hideValue) valGroup.style.display = 'none';

        item.appendChild(toLabel);
        item.appendChild(valGroup);

        var spacer = document.createElement('span');
        spacer.style.cssText = 'flex:1';
        item.appendChild(spacer);
        item.appendChild(testBtn);
        item.appendChild(removeBtn);
        return item;
    }

    // --- Build an action item ---
    function buildActionItem(act, rule, ai) {
        var item = document.createElement('div');
        item.className = 'rule-item';

        function makeLabel(text) {
            var lbl = document.createElement('span');
            lbl.className = 'field-label';
            lbl.textContent = text;
            return lbl;
        }
        function makeGroup(input, labelText) {
            var grp = document.createElement('div');
            grp.className = 'field-group';
            grp.appendChild(input);
            grp.appendChild(makeLabel(labelText));
            return grp;
        }

        var badge = document.createElement('span');
        badge.className = 'badge badge-then';
        badge.textContent = 'THEN';

        var typeLabel = document.createElement('span');
        typeLabel.style.cssText = 'font-size:0.78rem;font-weight:500';
        typeLabel.textContent = act.type.toUpperCase();

        item.appendChild(badge);
        item.appendChild(typeLabel);

        if (act.type === 'set') {
            var pathInput = document.createElement('input');
            pathInput.type = 'text';
            pathInput.className = 'form-input';
            pathInput.value = act.path || '';
            pathInput.placeholder = 'config/system/asset_id';
            pathInput.style.width = '14rem';
            pathInput.setAttribute('aria-label', 'Action path');
            pathInput.addEventListener('change', function() { act.path = this.value; markDirty(); });

            var browseBtn = document.createElement('button');
            browseBtn.type = 'button';
            browseBtn.className = 'browse-btn';
            browseBtn.textContent = '...';
            browseBtn.title = 'Browse config store';
            browseBtn.addEventListener('click', function() {
                openBrowser(act.path || 'config', function(path) { act.path = path; pathInput.value = path; });
            });
            item.appendChild(browseBtn);
            item.appendChild(makeGroup(pathInput, 'Path'));

            var setToLabel = document.createElement('span');
            setToLabel.className = 'field-label';
            setToLabel.style.cssText = 'align-self:center;font-size:0.75rem;font-weight:700;margin:0 0.15rem';
            setToLabel.textContent = 'TO';
            item.appendChild(setToLabel);
        }

        var valInput = document.createElement('input');
        valInput.type = 'text';
        valInput.className = 'form-input';
        valInput.value = act.value || '';
        valInput.placeholder = act.type === 'set' ? 'new value' : (act.type === 'alert' ? 'alert message' : 'log message');
        valInput.style.width = act.type === 'set' ? '8rem' : '16rem';
        valInput.setAttribute('aria-label', 'Action value');
        valInput.addEventListener('change', function() { act.value = this.value; markDirty(); });

        var valLabel = act.type === 'set' ? 'Value' : (act.type === 'alert' ? 'Message' : 'Message');

        var removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'remove-item';
        removeBtn.textContent = '\u00d7';
        removeBtn.title = 'Remove action';
        removeBtn.addEventListener('click', function() { rule.actions.splice(ai, 1); renderRules(); });

        item.appendChild(makeGroup(valInput, valLabel));
        item.appendChild(removeBtn);
        return item;
    }

    // --- Loading overlay helpers ---
    function showLoading(text) {
        document.getElementById('loading-text').textContent = text || 'Working...';
        document.getElementById('loading-overlay').classList.add('show');
    }
    function hideLoading() {
        document.getElementById('loading-overlay').classList.remove('show');
    }

    // --- Test a condition via API ---
    function testCondition(cond, itemEl) {
        var existing = itemEl.querySelector('.test-result');
        if (existing) existing.remove();
        showLoading('Testing condition...');
        var startTime = Date.now();
        fetch('/api/test', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(cond)
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var elapsed = Date.now() - startTime;
            var remaining = Math.max(0, 1000 - elapsed);
            setTimeout(function() {
                hideLoading();
                var passed = data.result;
                var span = document.createElement('span');
                span.className = 'test-result ' + (passed ? 'pass' : 'fail');
                span.textContent = passed ? 'PASS' : 'FAIL';
                if (data.actual_value !== null && data.actual_value !== undefined) {
                    span.textContent += ' (actual: ' + data.actual_value + ')';
                }
                itemEl.appendChild(span);
                showToast('Condition test: ' + (passed ? 'PASS' : 'FAIL'), passed ? 'success' : 'error');
                setTimeout(function() { if (span.parentNode) span.remove(); }, 5000);
            }, remaining);
        })
        .catch(function(e) {
            var elapsed = Date.now() - startTime;
            var remaining = Math.max(0, 1000 - elapsed);
            setTimeout(function() {
                hideLoading();
                showToast('Test failed: ' + e, 'error');
            }, remaining);
            console.error('Test failed:', e);
        });
    }

    // --- Drag and Drop ---
    function setupPaletteDrag() {
        document.querySelectorAll('.palette-item').forEach(function(item) {
            item.addEventListener('dragstart', function(e) {
                e.dataTransfer.setData('text/plain', item.dataset.type);
                e.dataTransfer.effectAllowed = 'copy';
            });
        });
    }

    function setupDropZone(zone, rule, zoneType) {
        zone.addEventListener('dragover', function(e) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'copy';
            zone.classList.add('drag-over');
        });
        zone.addEventListener('dragleave', function() { zone.classList.remove('drag-over'); });
        zone.addEventListener('drop', function(e) {
            e.preventDefault();
            zone.classList.remove('drag-over');
            var type = e.dataTransfer.getData('text/plain');
            if (zoneType === 'conditions' && (type === 'condition' || type === 'condition-when' || type === 'condition-while' || type === 'condition-while-time' || type === 'condition-where')) {
                // Enforce: max 1 WHEN, max 1 WHILE (path), max 1 WHILE (time), max 1 WHERE per rule
                if (type === 'condition-when') {
                    var hasWhen = rule.conditions.some(function(c) { return c.condType === 'when'; });
                    if (hasWhen) { showToast('Only one WHEN condition per rule', 'warning'); return; }
                    rule.conditions.push({condType: 'when', day: 'any', time: '00:00', repeat_mode: 'once'});
                } else if (type === 'condition-while') {
                    var hasWhile = rule.conditions.some(function(c) { return c.condType === 'while'; });
                    if (hasWhile) { showToast('Only one WHILE Path condition per rule', 'warning'); return; }
                    rule.conditions.push({condType: 'while', path: '', operator: 'equals', value: '', sustain: 'duration', sustain_value: 5, sustain_unit: 'seconds'});
                } else if (type === 'condition-while-time') {
                    var hasWhileTime = rule.conditions.some(function(c) { return c.condType === 'while_time'; });
                    if (hasWhileTime) { showToast('Only one WHILE Time condition per rule', 'warning'); return; }
                    rule.conditions.push({condType: 'while_time', start_day: 'any', start_time: '09:00', end_day: 'any', end_time: '17:00'});
                } else if (type === 'condition-where') {
                    var hasWhere = rule.conditions.some(function(c) { return c.condType === 'where'; });
                    if (hasWhere) { showToast('Only one WHERE condition per rule', 'warning'); return; }
                    rule.conditions.push({condType: 'where', lat: '', lon: '', radius: 1, radius_unit: 'km', operator: 'within', sustain: 'none'});
                } else {
                    rule.conditions.push({path: '', operator: 'equals', value: '', condType: 'if'});
                }
                renderRules();
            } else if (zoneType === 'actions') {
                if (type === 'action-set') { rule.actions.push({type: 'set', path: '', value: ''}); renderRules(); }
                else if (type === 'action-alert') { rule.actions.push({type: 'alert', value: ''}); renderRules(); }
                else if (type === 'action-log') { rule.actions.push({type: 'log', value: ''}); renderRules(); }
            }
        });
    }

    // --- Path Browser Modal ---
    var browseHistory = [];

    function openBrowser(startPath, callback) {
        browseCallback = callback;
        browseHistory = [];
        var modal = document.getElementById('browse-modal');
        document.getElementById('browse-path').value = startPath || 'status';
        // sync root dropdown
        var root = (startPath || 'status').split('/')[0];
        var rootSel = document.getElementById('browse-root');
        for (var i = 0; i < rootSel.options.length; i++) {
            if (rootSel.options[i].value === root) { rootSel.selectedIndex = i; break; }
        }
        modal.classList.add('open');
        modal.setAttribute('aria-hidden', 'false');
        browsePath(startPath || 'status');
    }

    function closeBrowser() {
        document.getElementById('browse-modal').classList.remove('open');
        document.getElementById('browse-modal').setAttribute('aria-hidden', 'true');
        browseCallback = null;
        browseHistory = [];
    }

    function updateBreadcrumb(path) {
        var bc = document.getElementById('browse-breadcrumb');
        bc.innerHTML = '';
        var parts = path.split('/');
        parts.forEach(function(part, idx) {
            if (idx > 0) {
                var sep = document.createElement('span');
                sep.className = 'sep';
                sep.textContent = '/';
                bc.appendChild(sep);
            }
            var crumb = document.createElement('span');
            crumb.className = 'crumb';
            crumb.textContent = part;
            var subPath = parts.slice(0, idx + 1).join('/');
            crumb.addEventListener('click', function() { browsePath(subPath); });
            bc.appendChild(crumb);
        });
    }

    function renderBrowseResults(data, path) {
        var results = document.getElementById('browse-results');
        results.innerHTML = '';
        browseSelectedValue = null;
        if (data.error) { results.textContent = 'Error: ' + data.error; return; }
        var d = data.data;
        if (d && typeof d === 'object' && !Array.isArray(d)) {
            Object.keys(d).sort(function(a, b) { return a.toLowerCase().localeCompare(b.toLowerCase()); }).forEach(function(key) {
                var el = document.createElement('div');
                el.className = 'browse-item';
                var keySpan = document.createElement('span');
                keySpan.className = 'key'; keySpan.textContent = key;
                var valSpan = document.createElement('span');
                valSpan.className = 'val';
                var val = d[key];
                valSpan.textContent = (val && typeof val === 'object') ? '{...}' : String(val);
                el.appendChild(keySpan); el.appendChild(valSpan);
                el.addEventListener('click', function() {
                    var np = path + '/' + key;
                    if (val && typeof val === 'object') {
                        browseSelectedValue = null;
                        browsePath(np);
                    } else {
                        document.getElementById('browse-path').value = np;
                        browseSelectedValue = String(val);
                    }
                });
                results.appendChild(el);
            });
        } else if (Array.isArray(d)) {
            d.forEach(function(item, i) {
                var el = document.createElement('div');
                el.className = 'browse-item';
                var keySpan = document.createElement('span');
                keySpan.className = 'key'; keySpan.textContent = '[' + i + ']';
                var valSpan = document.createElement('span');
                valSpan.className = 'val';
                valSpan.textContent = (item && typeof item === 'object') ? '{...}' : String(item);
                el.appendChild(keySpan); el.appendChild(valSpan);
                el.addEventListener('click', function() {
                    if (item && typeof item === 'object') {
                        browseSelectedValue = null;
                        browsePath(path + '/' + i);
                    } else {
                        document.getElementById('browse-path').value = path + '/' + i;
                        browseSelectedValue = String(item);
                    }
                });
                results.appendChild(el);
            });
        } else {
            results.textContent = 'Value: ' + String(d);
            browseSelectedValue = String(d);
        }
    }

    function browsePath(path) {
        var results = document.getElementById('browse-results');
        var currentPath = document.getElementById('browse-path').value;
        if (currentPath && currentPath !== path) {
            browseHistory.push(currentPath);
        }
        results.innerHTML = '<em>Loading...</em>';
        document.getElementById('browse-path').value = path;
        updateBreadcrumb(path);
        fetch('/api/browse?path=' + encodeURIComponent(path))
        .then(function(r) { return r.json(); })
        .then(function(data) { renderBrowseResults(data, path); })
        .catch(function(e) { results.textContent = 'Error: ' + e; });
    }

    // --- Save / Load (per-rule appdata) ---
    function saveAll() {
        var payload = rules.map(function(rule) {
            return {
                id: rule.id, name: rule.name, enabled: rule.enabled,
                logic: rule.logic, trigger: rule.trigger || 'interval',
                interval: rule.interval || 10,
                conditions: rule.conditions, actions: rule.actions
            };
        });
        fetch('/api/rules', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        })
        .then(function(r) { return r.json(); })
        .then(function(resp) {
            if (resp.success) {
                showToast('All rules saved', 'success');
                markClean();
            } else {
                showToast('Error saving rules', 'error');
            }
            var btn = document.getElementById('save-all-btn');
            btn.textContent = resp.success ? 'Saved!' : 'Error';
            setTimeout(function() { btn.textContent = '\u2191 Save Rule(s)'; }, 2000);
        })
        .catch(function(e) {
            showToast('Save failed: ' + e, 'error');
            console.error('Save failed:', e);
        });
    }

    function loadAll() {
        fetch('/api/rules')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            rules = data || [];
            rules.forEach(function(rule) {
                if (!rule.id) rule.id = nextId();
                if (!rule.name) rule.name = 'Unnamed Rule';
                if (rule.enabled === undefined) rule.enabled = true;
                if (!rule.logic) rule.logic = 'all';
                if (!rule.trigger) rule.trigger = 'interval';
                if (!rule.interval) rule.interval = 10;
                if (!rule.conditions) rule.conditions = [];
                if (!rule.actions) rule.actions = [];
            });
            renderRules();
            markClean();
        })
        .catch(function(e) { console.error('Load failed:', e); });
    }

    // --- Add new rule ---
    function addRule() {
        var newRule = {
            id: nextId(), name: 'New Rule', enabled: true,
            logic: 'all', trigger: 'interval', interval: 10,
            conditions: [{path: '', operator: 'equals', value: ''}],
            actions: [{type: 'log', value: ''}]
        };
        rules.push(newRule);
        showToast('New rule added', 'info');
        showRulesSection();
        renderRules();
    }

    // --- Init ---
    initDarkMode();
    setupPaletteDrag();
    toggleSidebarSections(false);

    document.getElementById('add-rule-btn').addEventListener('click', addRule);
    document.getElementById('save-all-btn').addEventListener('click', saveAll);
    document.getElementById('get-started-btn').addEventListener('click', function() { showRulesSection(); });

    // Sidebar nav
    document.querySelectorAll('.nav-item').forEach(function(item) {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            var section = this.dataset.section;
            if (section === 'home-section') { showHomeSection(); }
            else if (section === 'rules-section') { showRulesSection(); }
        });
    });

    document.querySelector('.modal-close').addEventListener('click', closeBrowser);
    document.getElementById('browse-back').addEventListener('click', function() {
        if (browseHistory.length > 0) {
            var prev = browseHistory.pop();
            var results = document.getElementById('browse-results');
            results.innerHTML = '<em>Loading...</em>';
            document.getElementById('browse-path').value = prev;
            updateBreadcrumb(prev);
            fetch('/api/browse?path=' + encodeURIComponent(prev))
            .then(function(r) { return r.json(); })
            .then(function(data) { renderBrowseResults(data, prev); })
            .catch(function(e) { results.textContent = 'Error: ' + e; });
        }
    });
    document.getElementById('browse-root').addEventListener('change', function() {
        var root = this.value;
        document.getElementById('browse-path').value = root;
        browsePath(root);
    });
    document.getElementById('browse-path').addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            browsePath(this.value);
        }
    });
    document.getElementById('browse-go').addEventListener('click', function() {
        browsePath(document.getElementById('browse-path').value);
    });
    document.getElementById('browse-select').addEventListener('click', function() {
        if (browseCallback) browseCallback(document.getElementById('browse-path').value, browseSelectedValue);
        closeBrowser();
    });
    document.getElementById('browse-modal').addEventListener('click', function(e) {
        if (e.target === this) closeBrowser();
    });

    loadAll();
})();
