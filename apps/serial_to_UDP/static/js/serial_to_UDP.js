// Serial to UDP - settings page logic
(function () {
    'use strict';

    var els = {};
    var config = {
        defaultSrcIp: '',
        defaultSrcPort: 5000,
        maxDestinations: 32
    };
    var serialOptions = null;

    function showToast(message, type) {
        if (window.webAppTemplate && typeof window.webAppTemplate.showToast === 'function') {
            window.webAppTemplate.showToast(message, type);
            return;
        }
        window.alert(message);
    }

    function showError(el, message) {
        el.textContent = message || '';
        el.style.display = message ? 'block' : 'none';
    }

    function isValidIPv4(value) {
        var parts = String(value).trim().split('.');
        if (parts.length !== 4) {
            return false;
        }
        return parts.every(function (part) {
            if (!/^\d{1,3}$/.test(part)) {
                return false;
            }
            return parseInt(part, 10) <= 255;
        });
    }

    function isValidPort(value) {
        var text = String(value).trim();
        if (!/^\d+$/.test(text)) {
            return false;
        }
        var n = parseInt(text, 10);
        return n >= 1 && n <= 65535;
    }

    // ---------------------------------------------------------------- UDP

    function destinationRows() {
        return Array.prototype.slice.call(els.destList.querySelectorAll('.dest-row'));
    }

    function updateDestHint() {
        var count = destinationRows().length;
        els.destHint.textContent = count + ' of ' + config.maxDestinations +
            ' destinations configured. Each datagram is sent to every destination.';
        els.addDestBtn.disabled = count >= config.maxDestinations;
    }

    function addDestinationRow(ip, port) {
        var row = document.createElement('div');
        row.className = 'dest-row';

        var ipField = document.createElement('div');
        ipField.className = 'form-field dest-ip';
        var ipLabel = document.createElement('label');
        ipLabel.textContent = 'Destination IP';
        var ipInput = document.createElement('input');
        ipInput.type = 'text';
        ipInput.className = 'form-input js-dest-ip';
        ipInput.placeholder = 'e.g. 192.168.13.101';
        ipInput.value = ip || '';
        ipField.appendChild(ipLabel);
        ipField.appendChild(ipInput);

        var portField = document.createElement('div');
        portField.className = 'form-field dest-port';
        var portLabel = document.createElement('label');
        portLabel.textContent = 'Port';
        var portInput = document.createElement('input');
        portInput.type = 'number';
        portInput.className = 'form-input js-dest-port';
        portInput.placeholder = 'e.g. 5000';
        portInput.min = '1';
        portInput.max = '65535';
        portInput.value = (port === undefined || port === null) ? '' : port;
        portField.appendChild(portLabel);
        portField.appendChild(portInput);

        var removeWrap = document.createElement('div');
        removeWrap.className = 'dest-remove';
        var removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'btn btn-secondary';
        removeBtn.title = 'Remove this destination';
        removeBtn.innerHTML = '<i class="fas fa-trash"></i>';
        removeBtn.addEventListener('click', function () {
            row.parentNode.removeChild(row);
            updateDestHint();
        });
        removeWrap.appendChild(removeBtn);

        row.appendChild(ipField);
        row.appendChild(portField);
        row.appendChild(removeWrap);
        els.destList.appendChild(row);
        updateDestHint();
        return row;
    }

    function collectDestinations() {
        return destinationRows().map(function (row) {
            return {
                ip: row.querySelector('.js-dest-ip').value.trim(),
                port: row.querySelector('.js-dest-port').value.trim()
            };
        }).filter(function (dest) {
            return dest.ip !== '' || dest.port !== '';
        });
    }

    function loadUdpSettings() {
        fetch('/api/settings')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                config.defaultSrcIp = data.default_src_ip || '';
                config.defaultSrcPort = data.default_src_port || 5000;
                config.maxDestinations = data.max_destinations || 32;

                els.destList.innerHTML = '';
                var dests = data.destinations || [];
                if (dests.length === 0) {
                    addDestinationRow('', '');
                } else {
                    dests.forEach(function (d) { addDestinationRow(d.ip, d.port); });
                }

                els.srcIp.value = data.udp_src_ip || '';
                els.srcPort.value = (data.udp_src_port === '' || data.udp_src_port === null ||
                    data.udp_src_port === undefined) ? '' : data.udp_src_port;
                els.srcIp.placeholder = config.defaultSrcIp;
                els.srcPort.placeholder = config.defaultSrcPort;
                els.srcIpHint.textContent = 'Leave blank to use the router LAN address (' +
                    config.defaultSrcIp + ').';
                els.srcPortHint.textContent = 'Leave blank to use port ' +
                    config.defaultSrcPort + '.';
                updateDestHint();
            })
            .catch(function () {
                showToast('Failed to load UDP settings.', 'error');
            });
    }

    function validateUdp(destinations, srcIp, srcPort) {
        if (destinations.length === 0) {
            return 'At least one UDP destination is required.';
        }
        var seen = {};
        for (var i = 0; i < destinations.length; i++) {
            var dest = destinations[i];
            var label = 'Destination ' + (i + 1) + ': ';
            if (!isValidIPv4(dest.ip)) {
                return label + '"' + dest.ip + '" is not a valid IPv4 address.';
            }
            if (!isValidPort(dest.port)) {
                return label + 'port must be a number between 1 and 65535.';
            }
            var key = dest.ip + ':' + parseInt(dest.port, 10);
            if (seen[key]) {
                return label + key + ' is listed more than once.';
            }
            seen[key] = true;
        }
        if (srcIp !== '' && !isValidIPv4(srcIp)) {
            return 'Source IP Address is not a valid IPv4 address.';
        }
        if (srcPort !== '' && !isValidPort(srcPort)) {
            return 'Source Port must be a number between 1 and 65535.';
        }
        return null;
    }

    function saveUdpSettings() {
        var destinations = collectDestinations();
        var srcIp = els.srcIp.value.trim();
        var srcPort = els.srcPort.value.trim();

        var error = validateUdp(destinations, srcIp, srcPort);
        showError(els.udpError, error);
        if (error) {
            showToast(error, 'error');
            return;
        }

        var payload = {
            destinations: destinations.map(function (d) {
                return { ip: d.ip, port: parseInt(d.port, 10) };
            })
        };
        if (srcIp !== '') {
            payload.udp_src_ip = srcIp;
        }
        if (srcPort !== '') {
            payload.udp_src_port = parseInt(srcPort, 10);
        }

        els.saveUdpBtn.disabled = true;
        fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) {
                    showToast('UDP settings saved and applied.', 'success');
                    loadUdpSettings();
                } else {
                    showError(els.udpError, data.error || 'Failed to save settings.');
                    showToast(data.error || 'Failed to save settings.', 'error');
                }
            })
            .catch(function () {
                showToast('Failed to save UDP settings.', 'error');
            })
            .finally(function () {
                els.saveUdpBtn.disabled = false;
            });
    }

    // ------------------------------------------------------------- Serial

    function fillSelect(select, options, selected) {
        select.innerHTML = '';
        options.forEach(function (option) {
            var opt = document.createElement('option');
            opt.value = option[0];
            opt.textContent = option[1];
            if (String(option[0]) === String(selected)) {
                opt.selected = true;
            }
            select.appendChild(opt);
        });
    }

    function loadSerialSettings(notify) {
        fetch('/api/serial')
            .then(function (r) {
                return r.json().then(function (data) {
                    return { ok: r.ok, data: data };
                });
            })
            .then(function (result) {
                if (!result.ok) {
                    showError(els.serialError, result.data.error || 'Failed to read serial config.');
                    return;
                }
                showError(els.serialError, '');
                serialOptions = result.data.options;
                var serial = result.data.serial;

                fillSelect(els.serialPort, serialOptions.serial_port, serial.serial_port);
                fillSelect(els.serialBaud, serialOptions.baud_rate, serial.baud_rate);
                fillSelect(els.serialByteSize, serialOptions.byte_size, serial.byte_size);
                fillSelect(els.serialParity, serialOptions.byte_parity, serial.byte_parity);
                fillSelect(els.serialStopBits, serialOptions.stop_bits, serial.stop_bits);

                els.serialFlowHw.checked = !!serial.flow_control.hardware;
                els.serialFlowSw.checked = !!serial.flow_control.software;
                els.serialEnabled.checked = !!serial.enabled;
                els.serialStatusHint.textContent = 'Router serial service status: ' +
                    (serial.status || 'unknown') + '.';

                if (notify) {
                    showToast('Serial settings reloaded from router.', 'success');
                }
            })
            .catch(function () {
                showToast('Failed to load serial settings.', 'error');
            });
    }

    function saveSerialSettings() {
        if (els.serialFlowHw.checked && els.serialFlowSw.checked) {
            var flowError = 'Hardware and software flow control cannot be enabled at the same time.';
            showError(els.serialError, flowError);
            showToast(flowError, 'error');
            return;
        }

        var payload = {
            serial_port: els.serialPort.value,
            baud_rate: parseInt(els.serialBaud.value, 10),
            byte_size: parseInt(els.serialByteSize.value, 10),
            byte_parity: parseInt(els.serialParity.value, 10),
            stop_bits: parseInt(els.serialStopBits.value, 10),
            enabled: els.serialEnabled.checked,
            flow_control: {
                hardware: els.serialFlowHw.checked,
                software: els.serialFlowSw.checked
            }
        };

        els.saveSerialBtn.disabled = true;
        fetch('/api/serial', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) {
                    showError(els.serialError, '');
                    showToast('Serial settings saved to router config.', 'success');
                    loadSerialSettings(false);
                } else {
                    showError(els.serialError, data.error || 'Failed to save serial settings.');
                    showToast(data.error || 'Failed to save serial settings.', 'error');
                }
            })
            .catch(function () {
                showToast('Failed to save serial settings.', 'error');
            })
            .finally(function () {
                els.saveSerialBtn.disabled = false;
            });
    }

    // ------------------------------------------------------------- Status

    function formatAgo(seconds) {
        if (seconds === null || seconds === undefined) {
            return 'never';
        }
        if (seconds < 60) {
            return seconds + 's ago';
        }
        if (seconds < 3600) {
            return Math.floor(seconds / 60) + 'm ago';
        }
        return Math.floor(seconds / 3600) + 'h ago';
    }

    function loadStatus() {
        fetch('/api/status')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var parts = [
                    'Serial port ' + (data.serial_open ? 'open' : 'closed'),
                    data.bytes_read + ' bytes read',
                    data.datagrams_sent + ' datagrams sent',
                    data.send_errors + ' send errors',
                    'last data ' + formatAgo(data.last_rx_ago)
                ];
                if (data.serial_error) {
                    parts.push('error: ' + data.serial_error);
                }
                els.forwardStatus.textContent = parts.join(' | ');
            })
            .catch(function () {
                els.forwardStatus.textContent = 'Status unavailable.';
            });
    }

    document.addEventListener('DOMContentLoaded', function () {
        els.destList = document.getElementById('dest-list');
        els.destHint = document.getElementById('dest-hint');
        els.addDestBtn = document.getElementById('btn-add-dest');
        els.srcIp = document.getElementById('udp-src-ip');
        els.srcPort = document.getElementById('udp-src-port');
        els.srcIpHint = document.getElementById('src-ip-hint');
        els.srcPortHint = document.getElementById('src-port-hint');
        els.saveUdpBtn = document.getElementById('btn-save-udp');
        els.udpError = document.getElementById('udp-error');

        els.serialPort = document.getElementById('serial-port');
        els.serialBaud = document.getElementById('serial-baud');
        els.serialByteSize = document.getElementById('serial-bytesize');
        els.serialParity = document.getElementById('serial-parity');
        els.serialStopBits = document.getElementById('serial-stopbits');
        els.serialFlowHw = document.getElementById('serial-flow-hw');
        els.serialFlowSw = document.getElementById('serial-flow-sw');
        els.serialEnabled = document.getElementById('serial-enabled');
        els.serialStatusHint = document.getElementById('serial-status-hint');
        els.saveSerialBtn = document.getElementById('btn-save-serial');
        els.reloadSerialBtn = document.getElementById('btn-reload-serial');
        els.serialError = document.getElementById('serial-error');
        els.forwardStatus = document.getElementById('forward-status');

        els.addDestBtn.addEventListener('click', function () {
            addDestinationRow('', '');
        });
        els.saveUdpBtn.addEventListener('click', saveUdpSettings);
        els.saveSerialBtn.addEventListener('click', saveSerialSettings);

        // The router rejects hardware and software flow control together.
        els.serialFlowHw.addEventListener('change', function () {
            if (els.serialFlowHw.checked) {
                els.serialFlowSw.checked = false;
            }
        });
        els.serialFlowSw.addEventListener('change', function () {
            if (els.serialFlowSw.checked) {
                els.serialFlowHw.checked = false;
            }
        });

        els.reloadSerialBtn.addEventListener('click', function () {
            loadSerialSettings(true);
        });

        loadUdpSettings();
        loadSerialSettings(false);
        loadStatus();
        setInterval(loadStatus, 5000);
    });
})();
