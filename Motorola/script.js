(function() {
    function loadForm(config) {
        document.getElementById('interval').value = config.interval;
        document.getElementById('udp_port').value = config.udp_port;

        var networksEl = document.getElementById('networks');
        networksEl.innerHTML = '';

        var networks = config.networks || [];
        networks.forEach(function(network, i) {
            var label = document.createElement('label');
            label.className = 'checkbox-label';
            label.setAttribute('for', 'network' + i);

            var input = document.createElement('input');
            input.type = 'checkbox';
            input.name = 'networks';
            input.id = 'network' + i;
            input.value = network._id_;
            input.checked = network.enabled;

            var textSpan = document.createElement('span');
            textSpan.textContent = network.name;

            label.appendChild(input);
            label.appendChild(textSpan);
            networksEl.appendChild(label);
        });
    }

    function initDarkMode() {
        var toggle = document.getElementById('dark-mode-toggle');
        var theme = localStorage.getItem('MotorolaSmartConnect_theme') || 'light';
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
                localStorage.setItem('MotorolaSmartConnect_theme', 'light');
            } else {
                document.body.setAttribute('data-theme', 'dark');
                toggle.textContent = '\u2600';
                toggle.title = 'Switch to light mode';
                localStorage.setItem('MotorolaSmartConnect_theme', 'dark');
            }
        });
    }

    initDarkMode();

    fetch('/config')
        .then(function(r) { return r.json(); })
        .then(loadForm)
        .catch(function(e) { console.error('Failed to load config:', e); });
})();
