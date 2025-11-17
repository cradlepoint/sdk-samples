// Modern Mobile Site Survey JavaScript
class MobileSiteSurvey {
    constructor() {
        this.apiUrl = '/config';
        this.pollInterval = 2000; // 2 seconds
        this.pollTimer = null;
        this.isPolling = false;
        this.lastResults = '';
        this.testCount = 0;
        this.lastTestTime = null;
        this.previousSurveyRunning = false;
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadConfig();
        this.startPolling();
        this.updateStatusIndicators();
        this.initTabs();
        this.initDarkMode();
    }

    bindEvents() {
        // Run Survey Button
        document.getElementById('run-survey-btn').addEventListener('click', (e) => {
            e.preventDefault();
            this.runSurvey();
        });

        // Download Results Button
        document.getElementById('download-results-btn').addEventListener('click', (e) => {
            e.preventDefault();
            this.downloadResults();
        });

        // Clear Results Button
        document.getElementById('clear-results-btn').addEventListener('click', (e) => {
            e.preventDefault();
            this.clearResults();
        });

        // Form Submit
        document.getElementById('mainForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveConfig();
        });

        // Real-time form validation
        this.setupFormValidation();

        // Keyboard shortcuts removed to avoid conflicts with browser functionality
    }

    setupFormValidation() {
        const form = document.getElementById('mainForm');
        const inputs = form.querySelectorAll('input, textarea, select');
        
        inputs.forEach(input => {
            input.addEventListener('blur', () => this.validateField(input));
            input.addEventListener('input', () => this.clearFieldError(input));
        });
    }

    validateField(field) {
        const value = field.value.trim();
        let isValid = true;
        let errorMessage = '';

        // Remove existing error styling
        this.clearFieldError(field);

        // Validation rules
        if (field.type === 'number' && field.value) {
            const num = parseFloat(field.value);
            if (isNaN(num) || num < 0) {
                isValid = false;
                errorMessage = 'Please enter a valid positive number';
            }
        }

        if (field.type === 'url' && field.value) {
            try {
                new URL(field.value);
            } catch {
                isValid = false;
                errorMessage = 'Please enter a valid URL';
            }
        }

        if (field.required && !value) {
            isValid = false;
            errorMessage = 'This field is required';
        }

        if (!isValid) {
            this.showFieldError(field, errorMessage);
        }

        return isValid;
    }

    showFieldError(field, message) {
        field.style.borderColor = 'var(--danger-color)';
        field.style.boxShadow = '0 0 0 3px rgba(239, 68, 68, 0.1)';
        
        // Remove existing error message
        const existingError = field.parentNode.querySelector('.field-error');
        if (existingError) {
            existingError.remove();
        }

        // Add error message
        const errorDiv = document.createElement('div');
        errorDiv.className = 'field-error';
        errorDiv.style.cssText = `
            color: var(--danger-color);
            font-size: 0.75rem;
            margin-top: 0.25rem;
            display: flex;
            align-items: center;
            gap: 0.25rem;
        `;
        errorDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
        field.parentNode.appendChild(errorDiv);
    }

    clearFieldError(field) {
        field.style.borderColor = '';
        field.style.boxShadow = '';
        const errorDiv = field.parentNode.querySelector('.field-error');
        if (errorDiv) {
            errorDiv.remove();
        }
    }

    async loadConfig() {
        try {
            this.showLoading(true);
            const response = await fetch(this.apiUrl);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const config = await response.json();
            this.populateForm(config);
            this.updateResults(config.results);
            this.updateTotalDataUsed(config.total_data_used_mb);
            this.showToast('Configuration loaded successfully', 'success');
        } catch (error) {
            console.error('Error loading config:', error);
            this.showToast('Failed to load configuration', 'error');
        } finally {
            this.showLoading(false);
        }
    }

    populateForm(config) {
        // Update version
        if (config.version) {
            document.getElementById('version').textContent = `Mobile Site Survey v${config.version}`;
        }

        // Update form fields
        const fields = [
            'enabled', 'min_distance', 'enable_timer', 'min_time', 'all_wans',
            'speedtests', 'packet_loss', 'full_diagnostics', 'write_csv', 'debug',
            'send_to_server', 'include_logs', 'server_url', 'server_token',
            'enable_surveyors', 'surveyors'
        ];

        fields.forEach(field => {
            const element = document.getElementById(field);
            if (element) {
                if (element.type === 'checkbox') {
                    element.checked = config[field] === true || config[field] === 1;
                } else {
                    element.value = config[field] || '';
                }
            }
        });
    }

    updateResults(results) {
        if (results && results !== this.lastResults) {
            document.getElementById('results').value = results;
            this.lastResults = results;
            
            // Update test count and last test time
            this.updateTestStats(results);
        }
    }

    updateTestStats(results) {
        if (results) {
            // Count test runs by looking for timestamp patterns
            const testMatches = results.match(/\d{1,2}:\d{2}:\d{2}\s+\d{1,2}\/\d{1,2}\/\d{4}/g);
            if (testMatches) {
                this.testCount = testMatches.length;
                this.lastTestTime = testMatches[testMatches.length - 1];
            }
        }

        document.getElementById('test-count').textContent = this.testCount;
        document.getElementById('last-test').textContent = this.lastTestTime || 'Never';
    }

    updateTotalDataUsed(totalDataMb) {
        const element = document.getElementById('total-data-used');
        if (element) {
            if (totalDataMb !== undefined && totalDataMb !== null) {
                element.textContent = `${totalDataMb.toFixed(2)} MB`;
            } else {
                element.textContent = '0.00 MB';
            }
        }
    }

    async runSurvey() {
        try {
            this.showLoading(true, 'Running Survey...');
            
            const response = await fetch('/test', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            // Show loading for a few seconds to indicate survey is running
            setTimeout(() => {
                this.showLoading(false);
            }, 3000);

        } catch (error) {
            console.error('Error running survey:', error);
            this.showToast('Failed to start survey', 'error');
            this.showLoading(false);
        }
    }

    downloadResults() {
        try {
            window.open('/results', '_blank');
            this.showToast('Opening results page...', 'info');
        } catch (error) {
            console.error('Error downloading results:', error);
            this.showToast('Failed to open results', 'error');
        }
    }

    async clearResults() {
        try {
            const confirmed = await this.showConfirmDialog(
                'Clear Results',
                'Are you sure you want to clear all test results? This action cannot be undone.',
                'warning'
            );

            if (!confirmed) return;

            this.showLoading(true, 'Clearing Results...');

            const response = await fetch('/clear', {
                method: 'GET'
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            document.getElementById('results').value = '';
            this.lastResults = '';
            this.testCount = 0;
            this.lastTestTime = null;
            this.updateTestStats('');
            
            this.showToast('Results cleared successfully', 'success');
        } catch (error) {
            console.error('Error clearing results:', error);
            this.showToast('Failed to clear results', 'error');
        } finally {
            this.showLoading(false);
        }
    }

    async saveConfig() {
        try {
            // Validate form
            const form = document.getElementById('mainForm');
            const inputs = form.querySelectorAll('input[required], textarea[required]');
            let isValid = true;

            inputs.forEach(input => {
                if (!this.validateField(input)) {
                    isValid = false;
                }
            });

            if (!isValid) {
                this.showToast('Please fix form errors before saving', 'warning');
                return;
            }

            this.showLoading(true, 'Saving Configuration...');

            const formData = new FormData(form);
            const params = new URLSearchParams();

            // Convert form data to URL parameters
            for (const [key, value] of formData.entries()) {
                params.append(key, value);
            }

            // Use GET request with query parameters instead of body
            const response = await fetch(`/submit?${params.toString()}`, {
                method: 'GET'
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            this.showToast('Configuration saved successfully!', 'success');
        } catch (error) {
            console.error('Error saving config:', error);
            this.showToast('Failed to save configuration', 'error');
        } finally {
            this.showLoading(false);
        }
    }

    startPolling() {
        if (this.isPolling) return;
        
        this.isPolling = true;
        this.pollTimer = setInterval(() => {
            this.pollForUpdates();
        }, this.pollInterval);
    }

    stopPolling() {
        if (this.pollTimer) {
            clearInterval(this.pollTimer);
            this.pollTimer = null;
        }
        this.isPolling = false;
    }

    async pollForUpdates() {
        try {
            const response = await fetch(this.apiUrl);
            if (!response.ok) return;

            const config = await response.json();
            this.updateResults(config.results);
            this.updateStatusIndicators();
            this.updateSurveyStatus(config);
            this.updateTotalDataUsed(config.total_data_used_mb);
        } catch (error) {
            console.error('Polling error:', error);
            // Don't show error toasts for polling failures to avoid spam
        }
    }

    updateStatusIndicators() {
        // Update GPS status based on real backend data
        const gpsStatus = document.getElementById('gps-status');
        if (gpsStatus && this.config) {
            const hasGpsLock = this.config.gps_lock;
            
            if (hasGpsLock) {
                gpsStatus.innerHTML = '<i class="fas fa-satellite"></i><span>GPS Lock</span>';
                gpsStatus.classList.remove('offline');
            } else {
                gpsStatus.innerHTML = '<i class="fas fa-satellite"></i><span>No GPS</span>';
                gpsStatus.classList.add('offline');
            }
        }
    }

    updateSurveyStatus(config) {
        // Track survey running state and show/hide indicator
        const surveyIndicator = document.getElementById('survey-indicator');
        const isSurveyRunning = config.survey_running;
        
        if (isSurveyRunning !== this.previousSurveyRunning) {
            if (isSurveyRunning) {
                // Survey started
                if (surveyIndicator) {
                    surveyIndicator.style.display = 'flex';
                }
                this.showToast('Survey running in background...', 'info', 5000);
            } else {
                // Survey stopped
                if (surveyIndicator) {
                    surveyIndicator.style.display = 'none';
                }
            }
        }
        
        this.previousSurveyRunning = isSurveyRunning;
    }

    showLoading(show, message = 'Loading...') {
        const overlay = document.getElementById('loading-overlay');
        const spinner = overlay.querySelector('.loading-spinner p');
        
        if (show) {
            spinner.textContent = message;
            overlay.classList.add('show');
        } else {
            overlay.classList.remove('show');
        }
    }

    showToast(message, type = 'info', duration = 5000) {
        const container = document.getElementById('toast-container');
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icon = this.getToastIcon(type);
        
        toast.innerHTML = `
            <i class="${icon}"></i>
            <div class="toast-content">
                <div class="toast-message">${message}</div>
            </div>
        `;
        
        container.appendChild(toast);
        
        // Trigger animation
        setTimeout(() => toast.classList.add('show'), 100);
        
        // Auto remove
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, duration);
    }

    getToastIcon(type) {
        const icons = {
            success: 'fas fa-check-circle',
            error: 'fas fa-exclamation-circle',
            warning: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle'
        };
        return icons[type] || icons.info;
    }

    async showConfirmDialog(title, message, type = 'warning') {
        return new Promise((resolve) => {
            if (typeof swal !== 'undefined') {
                swal({
                    title: title,
                    text: message,
                    icon: type,
                    buttons: {
                        cancel: 'Cancel',
                        confirm: 'Confirm'
                    },
                    dangerMode: type === 'warning'
                }).then((confirmed) => {
                    resolve(confirmed);
                });
            } else {
                // Fallback to native confirm
                resolve(confirm(`${title}\n\n${message}`));
            }
        });
    }

    initTabs() {
        const tabButtons = document.querySelectorAll('.tab-btn');
        const tabContents = document.querySelectorAll('.tab-content');

        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const targetTab = button.getAttribute('data-tab');
                
                // Remove active class from all buttons and contents
                tabButtons.forEach(btn => btn.classList.remove('active'));
                tabContents.forEach(content => content.classList.remove('active'));
                
                // Add active class to clicked button and corresponding content
                button.classList.add('active');
                document.getElementById(`${targetTab}-tab`).classList.add('active');
            });
        });
    }

    initDarkMode() {
        const darkModeToggle = document.getElementById('dark-mode-toggle');
        const body = document.body;
        
        // Check for saved theme preference or default to light mode
        const savedTheme = localStorage.getItem('theme') || 'light';
        body.setAttribute('data-theme', savedTheme);
        this.updateDarkModeIcon(savedTheme);
        
        darkModeToggle.addEventListener('click', () => {
            const currentTheme = body.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            
            body.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            this.updateDarkModeIcon(newTheme);
        });
    }

    updateDarkModeIcon(theme) {
        const icon = document.querySelector('#dark-mode-toggle i');
        if (theme === 'dark') {
            icon.className = 'fas fa-sun';
        } else {
            icon.className = 'fas fa-moon';
        }
    }

    // Public methods for external access
    getConfig() {
        return this.loadConfig();
    }

    runTest() {
        return this.runSurvey();
    }

    clearData() {
        return this.clearResults();
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.mobileSiteSurvey = new MobileSiteSurvey();
    
    // Add some helpful console messages
    console.log('🚀 Mobile Site Survey initialized');
});

// Handle page visibility changes to optimize polling
document.addEventListener('visibilitychange', () => {
    if (window.mobileSiteSurvey) {
        if (document.hidden) {
            window.mobileSiteSurvey.stopPolling();
        } else {
            window.mobileSiteSurvey.startPolling();
        }
    }
});

// Handle page unload
window.addEventListener('beforeunload', () => {
    if (window.mobileSiteSurvey) {
        window.mobileSiteSurvey.stopPolling();
    }
});

// Export for potential module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MobileSiteSurvey;
}
