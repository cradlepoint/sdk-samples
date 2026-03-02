/**
 * NCX Staging Configuration Interface
 * Handles form validation, API communication, and UI updates
 */

// Load licenses on page load
$(document).ready(function() {
    loadLicenses();
    setupEventListeners();
    updateLocalDomainRequirement();
    updateFqdnResourceState();
    updateBulkConfigFields();
    filterOptionalLicenses();
    checkDefaultFiles();
});

/**
 * Make a message box collapsible
 * @param {string} html - The HTML content of the message box
 * @param {string} title - The title to display in the header
 * @param {string} type - The type of message (success, error, warning, info)
 * @param {boolean} startExpanded - Whether to start expanded (default: false)
 * @returns {string} - HTML with collapsible wrapper
 */
function makeCollapsible(html, title, type = 'info', startExpanded = false) {
    const colors = {
        success: { bg: 'rgba(5, 150, 105, 0.1)', border: 'var(--success-color)', text: 'var(--success-color)' },
        error: { bg: 'rgba(220, 38, 38, 0.1)', border: 'var(--danger-color)', text: 'var(--danger-color)' },
        warning: { bg: 'rgba(245, 158, 11, 0.1)', border: 'var(--warning-color)', text: 'var(--warning-color)' },
        info: { bg: 'rgba(2, 132, 199, 0.1)', border: 'var(--info-color)', text: 'var(--info-color)' }
    };
    
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };
    
    const color = colors[type] || colors.info;
    const icon = icons[type] || icons.info;
    const uniqueId = 'collapsible-' + Math.random().toString(36).substr(2, 9);
    const displayStyle = startExpanded ? 'block' : 'none';
    const chevronClass = startExpanded ? 'fa-chevron-up' : 'fa-chevron-down';
    
    return `
        <div style="padding: 1rem; background: ${color.bg}; border: 1px solid ${color.border}; border-radius: var(--radius-md);">
            <div style="display: flex; justify-content: space-between; align-items: center; cursor: pointer;" onclick="$('#${uniqueId}').slideToggle(200); $('#${uniqueId}-icon').toggleClass('fa-chevron-down fa-chevron-up');">
                <p style="margin: 0; color: ${color.text}; font-weight: 600;">
                    <i class="fas ${icon}"></i> ${title}
                </p>
                <i id="${uniqueId}-icon" class="fas ${chevronClass}" style="color: ${color.text};"></i>
            </div>
            <div id="${uniqueId}" style="display: ${displayStyle}; margin-top: 0.5rem;">
                ${html}
            </div>
        </div>
    `;
}

/**
 * Show confirmation modal
 */
function showConfirm(message, callback) {
    $('#confirm-message').text(message);
    $('#confirm-modal').css('display', 'block');
    $('#confirm-cancel').show();
    
    $('#confirm-ok').off('click').on('click', function() {
        $('#confirm-modal').hide();
        callback(true);
    });
    
    $('#confirm-cancel').off('click').on('click', function() {
        $('#confirm-modal').hide();
        callback(false);
    });
}

/**
 * Show alert modal (OK button only)
 */
function showAlert(message) {
    $('#confirm-message').text(message);
    $('#confirm-modal').css('display', 'block');
    $('#confirm-cancel').hide();
    
    $('#confirm-ok').off('click').on('click', function() {
        $('#confirm-modal').hide();
        $('#confirm-cancel').show(); // Restore for future confirms
    });
}

/**
 * Check for default files in working directory
 */
function checkDefaultFiles() {
    $.get('/api/check-default-files', function(response) {
        if (response.csv_exists) {
            $('#bulk-config-file-status').html('<i class="fas fa-check-circle" style="color: var(--success-color);"></i> router_grid.csv (default)');
        }
        if (response.json_exists) {
            $('#config-template-file-status').html('<i class="fas fa-check-circle" style="color: var(--success-color);"></i> config_template.json (default)');
        }
        
        // Load and display special columns info if both files exist
        if (response.csv_exists && response.json_exists) {
            loadSpecialColumnsInfo();
        }
    });
}

/**
 * Load and display special columns information
 */
function loadSpecialColumnsInfo() {
    $.get('/api/validate-default-files', function(response) {
        // Silently load - displaySpecialColumnsInfo will be called when files are loaded
    }).fail(function() {
        // Silently fail - validation will show errors when user clicks validate
    });
}

/**
 * Load license options from API
 */
function loadLicenses() {
    $.get('/api/licenses', function(licenses) {
        // Store licenses globally for filtering
        window.allLicenses = licenses;
        
        // Populate Secure Connect licenses
        const scSelect = $('#secure-connect-lic');
        licenses['Secure Connect'].forEach(lic => {
            scSelect.append(`<option value="${lic}">${lic}</option>`);
        });
        // Don't set default value - leave on "Select license..."
    }).fail(function() {
        showToast('Error loading license options', 'error');
    });
}

/**
 * Filter optional licenses based on Secure Connect prefix
 */
function filterOptionalLicenses() {
    const scLic = $('#secure-connect-lic').val();
    if (!scLic || !window.allLicenses) {
        // Clear optional licenses if no Secure Connect selected
        $('#sdwan-lic').empty().append('<option value="">Select Secure Connect license</option>');
        $('#hmf-lic').empty().append('<option value="">Select Secure Connect license</option>');
        $('#ai-lic').empty().append('<option value="">Select Secure Connect license</option>');
        return;
    }
    
    const prefix = scLic.startsWith('NCX') ? 'NCX' : 'NCS';
    
    // Filter and populate SD-WAN licenses
    const sdwanSelect = $('#sdwan-lic');
    const currentSdwan = sdwanSelect.val();
    sdwanSelect.empty().append('<option value="">None</option>');
    window.allLicenses['SD-WAN'].forEach(lic => {
        if (lic.startsWith(prefix)) {
            sdwanSelect.append(`<option value="${lic}">${lic}</option>`);
        }
    });
    if (currentSdwan && currentSdwan.startsWith(prefix)) {
        sdwanSelect.val(currentSdwan);
    }
    
    // Filter and populate HMF licenses
    const hmfSelect = $('#hmf-lic');
    const currentHmf = hmfSelect.val();
    hmfSelect.empty().append('<option value="">None</option>');
    window.allLicenses['HMF'].forEach(lic => {
        if (lic.startsWith(prefix)) {
            hmfSelect.append(`<option value="${lic}">${lic}</option>`);
        }
    });
    if (currentHmf && currentHmf.startsWith(prefix)) {
        hmfSelect.val(currentHmf);
    }
    
    // Filter and populate AI licenses
    const aiSelect = $('#ai-lic');
    const currentAi = aiSelect.val();
    aiSelect.empty().append('<option value="">None</option>');
    window.allLicenses['AI'].forEach(lic => {
        if (lic.startsWith(prefix)) {
            aiSelect.append(`<option value="${lic}">${lic}</option>`);
        }
    });
    if (currentAi && currentAi.startsWith(prefix)) {
        aiSelect.val(currentAi);
    }
}

/**
 * Setup event listeners
 */
function setupEventListeners() {
    // Navigation
    $('.nav-item').click(function(e) {
        e.preventDefault();
        const section = $(this).data('section');
        showSection(section);
    });
    
    // Secure Connect license change - filter optional licenses
    $('#secure-connect-lic').change(function() {
        filterOptionalLicenses();
    });
    
    // HMF license change - show warning immediately
    $('#hmf-lic').change(function() {
        updateHmfWarning();
    });
    
    // Disable Force DNS change - show warning immediately
    $('#disable-force-dns').change(function() {
        updateDisableForceDnsWarning();
    });
    
    // LAN as DNS toggle
    $('#lan-as-dns').change(function() {
        updateLocalDomainRequirement();
        updateDnsFieldsState();
        updateFqdnResourceState();
    });
    
    // Custom DNS toggle
    $('#custom-dns-enabled').change(function() {
        updateCustomDnsFields();
        updateDnsFieldsState();
        updateFqdnResourceState();
    });
    
    // Bulk config toggle
    $('#self-bulk-config').change(function() {
        updateBulkConfigFields();
        // Clear validation status when toggling
        $('#bulk-config-validation-status').html('');
        // Update warnings
        updateBulkConfigWarnings();
    });
    
    // File editor buttons
    $('#load-files-btn').click(function() {
        loadFilesIntoEditor();
    });
    
    $('#save-files-btn').click(function() {
        saveFilesFromEditor();
    });
    
    // Track editor changes
    $('#csv-editor, #json-editor').on('input', function() {
        window.bulkConfigFilesModified = true;
        window.bulkConfigValidated = false;
        updateBulkConfigWarnings();
        if ($(this).attr('id') === 'json-editor') {
            updateJsonPlaceholderHighlight();
        }
    });
    
    // CSV grid view toggle
    $('#toggle-csv-view').click(function() {
        toggleCsvView();
    });
    
    // Track grid changes
    $(document).on('input', '#csv-table input', function() {
        syncGridToText();
        window.bulkConfigFilesModified = true;
        window.bulkConfigValidated = false;
        updateBulkConfigWarnings();
    });
    
    // Resource checkboxes - update tag fields
    $('#create-lan-resource, #create-cp-host-resource, #create-wildcard-resource').change(function() {
        updateTagFields();
    });
    
    // File upload handlers
    $('#bulk-config-file-upload').change(function() {
        handleFileUpload(this, 'bulk-config-file-status');
    });
    
    $('#config-template-file-upload').change(function() {
        handleFileUpload(this, 'config-template-file-status');
    });
    
    // Validate optional parameters button
    $('#validate-optional-btn').click(function() {
        validateOptionalParameters();
    });
    
    // Validate bulk configuration button
    $('#validate-bulk-config-btn').click(function() {
        validateBulkConfiguration();
    });
    
    // Validate API keys button
    $('#validate-api-keys-btn').click(function() {
        validateApiKeys();
    });
    
    // Validate required parameters button
    $('#validate-required-btn').click(function() {
        validateRequiredParameters();
    });
    
    // Real-time validation on input change
    $('#staging-group-id, #prod-group-id, #exchange-network-id, #secure-connect-lic, #local-domain').on('input change', function() {
        // Clear validation status when user makes changes
        $('#required-validation-status').html('');
    });
    
    // Validate button
    $('#validate-btn').click(function() {
        validateConfiguration();
    });
    
    // Apply button
    $('#apply-btn').click(function(e) {
        applyConfiguration();
    });
    
    // Update summary when navigating to summary section
    $('[data-section="summary-section"]').click(function() {
        updateSummary();
    });
    
    // Update tag fields when navigating to tags section
    $('[data-section="tags-section"]').click(function() {
        updateTagFields();
    });
    
    // Validate tags button
    $('#validate-tags-btn').click(function() {
        validateGlobalTags();
    });
}

/**
 * Update HMF warning visibility
 */
function updateHmfWarning() {
    const hmfLic = $('#hmf-lic').val();
    const warningDiv = $('#hmf-warning');
    
    if (hmfLic && hmfLic !== '') {
        const content = '<p style="margin: 0; color: var(--text-secondary); font-size: 0.875rem;">When using HMF licenses, ALL sites in this exchange network MUST have an HMF license applied.</p>';
        warningDiv.html(makeCollapsible(content, 'HMF License Warning', 'warning', true)).show();
        // Scroll to top of page
        window.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
        warningDiv.hide();
    }
}

/**
 * Update Disable Force DNS warning visibility
 */
function updateDisableForceDnsWarning() {
    const disableForceDns = $('#disable-force-dns').is(':checked');
    const warningDiv = $('#disable-force-dns-warning');
    
    if (disableForceDns) {
        const content = '<p style="margin: 0; color: var(--text-secondary); font-size: 0.875rem;">Disabling Force All DNS Requests to Router will increase provisioning time as the application must wait for VPN tunnels to establish before applying the configuration.</p>';
        warningDiv.html(makeCollapsible(content, 'Provisioning Time Warning', 'warning', true)).show();
    } else {
        warningDiv.hide();
    }
}

/**
 * Validate global tags
 */
function validateGlobalTags() {
    const siteTags = $('#site-tags').val().trim();
    const lanTags = $('#lan-resource-tags').val().trim();
    const cpHostTags = $('#cp-host-tags').val().trim();
    const wildcardTags = $('#wildcard-tags').val().trim();
    const statusDiv = $('#tags-validation-status');
    
    const errors = [];
    
    // Validate each tag field
    const validateTagField = (tags, fieldName) => {
        if (!tags) return;
        
        // Split by comma or semicolon
        const tagList = tags.replace(/;/g, ',').split(',');
        for (const tag of tagList) {
            const trimmedTag = tag.trim();
            if (trimmedTag.length < 2) {
                errors.push(`${fieldName}: Tag '${trimmedTag}' must be at least 2 characters long`);
            } else if (!/^[a-z0-9]+$/.test(trimmedTag)) {
                errors.push(`${fieldName}: Tag '${trimmedTag}' must contain only lowercase letters and numbers`);
            }
        }
    };
    
    validateTagField(siteTags, 'Site Tags');
    validateTagField(lanTags, 'LAN Resource Tags');
    validateTagField(cpHostTags, 'CP Host Tags');
    validateTagField(wildcardTags, 'Wildcard Tags');
    
    // Display results
    if (errors.length === 0) {
        const content = '<p style="margin: 0; color: var(--text-secondary); font-size: 0.875rem;">All tag fields contain valid data</p>';
        statusDiv.html(makeCollapsible(content, 'All Tags Valid', 'success', true));
        showToast('Tags validated successfully', 'success');
    } else {
        const content = `
            <ul style="margin: 0; padding-left: 1.5rem; color: var(--text-secondary);">
                ${errors.map(error => `<li>${error}</li>`).join('')}
            </ul>
        `;
        statusDiv.html(makeCollapsible(content, 'Validation Errors', 'error', true));
        showToast('Tag validation error', 'error');
    }
}

/**
 * Update tag fields visibility based on resource creation settings
 */
function updateTagFields() {
    const lanEnabled = $('#create-lan-resource').is(':checked');
    const cpHostEnabled = $('#create-cp-host-resource').is(':checked');
    const wildcardEnabled = $('#create-wildcard-resource').is(':checked');
    const anyResourceEnabled = lanEnabled || cpHostEnabled || wildcardEnabled;
    
    // Show/hide full-width info message
    $('#resource-tags-info').toggle(!anyResourceEnabled);
    
    // Show/hide Resource Tags title
    $('#resource-tags-title').toggle(anyResourceEnabled);
    
    // Show/hide individual resource tag fields
    $('#lan-tags-field').toggle(lanEnabled);
    $('#cp-host-tags-field').toggle(cpHostEnabled);
    $('#wildcard-tags-field').toggle(wildcardEnabled);
}

/**
 * Toggle password visibility
 */
function togglePassword(inputId) {
    const input = $(`#${inputId}`);
    const button = input.next('.password-toggle');
    const icon = button.find('i');
    
    if (input.attr('type') === 'password') {
        input.attr('type', 'text');
        icon.removeClass('fa-eye').addClass('fa-eye-slash');
    } else {
        input.attr('type', 'password');
        icon.removeClass('fa-eye-slash').addClass('fa-eye');
    }
}

/**
 * Show specific section
 */
function showSection(sectionName) {
    // Support both 'home' and 'home-section' style names
    const sectionId = sectionName.endsWith('-section') ? sectionName : `${sectionName}-section`;
    const dataSection = sectionName.endsWith('-section') ? sectionName : `${sectionName}-section`;
    $('.element-section').removeClass('active');
    $(`#${sectionId}`).addClass('active');
    $('.nav-item').removeClass('active');
    $(`[data-section="${dataSection}"]`).addClass('active');
}

/**
 * Update local domain requirement based on LAN as DNS toggle
 */
function updateLocalDomainRequirement() {
    const lanAsDns = $('#lan-as-dns').is(':checked');
    const localDomainField = $('#local-domain-field');
    const localDomainInput = $('#local-domain');
    
    if (lanAsDns) {
        localDomainField.show();
        localDomainInput.prop('required', true);
    } else {
        localDomainField.hide();
        localDomainInput.prop('required', false);
    }
}

/**
 * Update DNS fields mutual exclusivity
 */
function updateDnsFieldsState() {
    const lanAsDns = $('#lan-as-dns').is(':checked');
    const customDns = $('#custom-dns-enabled').is(':checked');
    
    if (lanAsDns) {
        $('#custom-dns-enabled').prop('disabled', true).prop('checked', false);
        updateCustomDnsFields();
    } else {
        $('#custom-dns-enabled').prop('disabled', false);
    }
    
    if (customDns) {
        $('#lan-as-dns').prop('disabled', true).prop('checked', false);
        updateLocalDomainRequirement();
    } else {
        $('#lan-as-dns').prop('disabled', false);
    }
}

/**
 * Update custom DNS fields visibility
 */
function updateCustomDnsFields() {
    const customDnsEnabled = $('#custom-dns-enabled').is(':checked');
    
    if (customDnsEnabled) {
        $('#primary-dns-field').show();
        $('#secondary-dns-field').show();
    } else {
        $('#primary-dns-field').hide();
        $('#secondary-dns-field').hide();
    }
}

function updateFqdnResourceState() {
    const dnsEnabled = $('#lan-as-dns').is(':checked') || $('#custom-dns-enabled').is(':checked');
    $('#create-cp-host-resource, #create-wildcard-resource').each(function() {
        if (!dnsEnabled) {
            $(this).prop('checked', false).prop('disabled', true);
        } else {
            $(this).prop('disabled', false);
        }
    });
    $('#fqdn-dns-required-note, #wildcard-dns-required-note').toggle(!dnsEnabled);
    updateTagFields();
}

/**
 * Validate IP address format
 */
function validateIpAddress(ip) {
    if (!ip || ip.trim() === '') return true;
    
    // Check for netmask notation
    if (ip.includes('/')) return false;
    
    const parts = ip.split('.');
    if (parts.length !== 4) return false;
    
    for (const part of parts) {
        const num = parseInt(part, 10);
        if (isNaN(num) || num < 0 || num > 255) return false;
    }
    
    return true;
}

/**
 * Update bulk config warning messages
 */
function updateBulkConfigWarnings() {
    const bulkConfigEnabled = $('#self-bulk-config').is(':checked');
    const csvContent = $('#csv-editor').val();
    const jsonContent = $('#json-editor').val();
    const warningDiv = $('#bulk-config-warning');
    
    if (!bulkConfigEnabled) {
        warningDiv.hide();
        return;
    }
    
    // Track if files have been modified (simple check: if content exists and differs from initial load)
    const hasContent = csvContent && csvContent.trim() && jsonContent && jsonContent.trim();
    const hasUnsavedChanges = hasContent && (window.bulkConfigFilesModified === true);
    
    const warnings = [];
    
    // Check for missing 'id' column
    if (csvContent && csvContent.trim()) {
        const lines = csvContent.trim().split('\n');
        if (lines.length > 0) {
            const headers = lines[0].split(',').map(h => h.trim());
            if (!headers.includes('id')) {
                warnings.push('CSV file is missing required \'id\' column for router matching');
            }
        }
    }
    
    if (hasUnsavedChanges) {
        warnings.push('Files have been modified but not saved');
    }
    
    if (!window.bulkConfigValidated) {
        warnings.push('Bulk configuration settings have not been validated');
    }
    
    if (warnings.length > 0) {
        const content = `
            <ul style="margin: 0; padding-left: 1.5rem; color: var(--text-secondary); font-size: 0.875rem;">
                ${warnings.map(w => `<li>${w}</li>`).join('')}
            </ul>
        `;
        warningDiv.html(makeCollapsible(content, 'Validation Warning', 'warning', true)).show();
    } else {
        warningDiv.hide();
    }
}

/**
 * Update bulk config fields visibility
 */
function updateBulkConfigFields() {
    const bulkConfigEnabled = $('#self-bulk-config').is(':checked');
    
    if (bulkConfigEnabled) {
        showLoading('Loading bulk configuration files...');
        const startTime = Date.now();
        $('#bulk-config-file-field').show();
        $('#config-template-file-field').show();
        $('#file-editor-panel').show();
        
        // Load files and ensure minimum 1 second display
        loadFilesIntoEditor();
        
        // Override hideLoading to ensure minimum 1 second
        const originalHideLoading = window.hideLoading;
        window.hideLoading = function() {
            const elapsed = Date.now() - startTime;
            const remaining = Math.max(0, 1000 - elapsed);
            setTimeout(function() {
                originalHideLoading();
                window.hideLoading = originalHideLoading;
            }, remaining);
        };
    } else {
        $('#bulk-config-file-field').hide();
        $('#config-template-file-field').hide();
        $('#file-editor-panel').hide();
        $('#special-columns-info').remove();
    }
}

/**
 * Highlight JSON placeholders using mark.js style approach
 */
function updateJsonPlaceholderHighlight() {
    const editor = $('#json-editor')[0];
    const text = editor.value;
    
    // Find all placeholder positions
    const regex = /\{\{[^}]+\}\}/g;
    let match;
    const highlights = [];
    
    while ((match = regex.exec(text)) !== null) {
        highlights.push({
            start: match.index,
            end: match.index + match[0].length,
            text: match[0]
        });
    }
    
    // Apply visual highlighting by wrapping in a styled div overlay
    if (highlights.length > 0) {
        // Add orange tint to textarea background for placeholders
        editor.style.background = 'var(--bg-primary)';
        
        // Create tooltip on hover
        editor.title = `Template contains ${highlights.length} placeholder(s): ${highlights.map(h => h.text).join(', ')}`;
    } else {
        editor.style.background = '';
        editor.title = '';
    }
}

/**
 * Toggle CSV view between text and grid
 */
function toggleCsvView() {
    const textView = $('#csv-editor');
    const gridView = $('#csv-grid');
    const toggleBtn = $('#toggle-csv-view');
    
    if (gridView.is(':visible')) {
        // Switch to text view
        syncGridToText();
        gridView.hide();
        textView.show();
        toggleBtn.html('<i class="fas fa-table"></i> Grid View');
    } else {
        // Switch to grid view
        syncTextToGrid();
        textView.hide();
        gridView.show();
        toggleBtn.html('<i class="fas fa-align-left"></i> Text View');
    }
}

/**
 * Sync text editor to grid
 */
function syncTextToGrid() {
    const csvText = $('#csv-editor').val();
    if (!csvText.trim()) return;
    
    const lines = csvText.trim().split('\n');
    const headers = lines[0].split(',').map(h => h.trim());
    const rows = lines.slice(1).map(line => line.split(',').map(c => c.trim()));
    
    // Calculate max width for each column (including header)
    const colWidths = headers.map((header, colIdx) => {
        let maxLen = header.length;
        rows.forEach(row => {
            if (row[colIdx]) {
                maxLen = Math.max(maxLen, row[colIdx].length);
            }
        });
        return Math.max(maxLen * 8 + 20, 80); // 8px per char + padding, min 80px
    });
    
    let html = '<thead style="position: sticky; top: 0; background: var(--bg-primary); z-index: 1;"><tr>';
    headers.forEach((header, idx) => {
        html += `<th style="padding: 0.75rem; border: 1px solid var(--border-color); font-weight: 600; text-align: left; white-space: nowrap; min-width: ${colWidths[idx]}px;">${header}</th>`;
    });
    html += '</tr></thead><tbody>';
    
    rows.forEach((row, rowIdx) => {
        html += '<tr>';
        row.forEach((cell, colIdx) => {
            html += `<td style="padding: 0.5rem; border: 1px solid var(--border-color); min-width: ${colWidths[colIdx]}px;"><input type="text" value="${cell}" data-row="${rowIdx}" data-col="${colIdx}" style="width: 100%; border: none; background: transparent; color: var(--text-primary); font-family: monospace; font-size: 0.875rem; padding: 0.25rem;"></td>`;
        });
        html += '</tr>';
    });
    
    html += '</tbody>';
    $('#csv-table').html(html);
}

/**
 * Sync grid to text editor
 */
function syncGridToText() {
    const table = $('#csv-table');
    if (!table.find('tbody').length) return;
    
    const headers = [];
    table.find('thead th').each(function() {
        headers.push($(this).text());
    });
    
    const rows = [headers.join(',')];
    table.find('tbody tr').each(function() {
        const row = [];
        $(this).find('input').each(function() {
            row.push($(this).val());
        });
        rows.push(row.join(','));
    });
    
    $('#csv-editor').val(rows.join('\n'));
}



/**
 * Load files into editor
 */
function loadFilesIntoEditor() {
    // Always perform load directly - no confirmation needed since user clicked Load button
    performLoadFiles();
}

/**
 * Perform the actual file loading
 */
function performLoadFiles() {
    showLoading('Loading files...');
    
    $.get('/api/get-files', function(response) {
        hideLoading();
        $('#csv-editor').val(response.csv_content || '');
        $('#json-editor').val(response.json_content || '');
        window.bulkConfigFilesModified = false;
        window.bulkConfigValidated = false;
        
        // Update placeholder highlighting
        updateJsonPlaceholderHighlight();
        
        // Default to grid view for CSV
        if (response.csv_content && response.csv_content.trim()) {
            syncTextToGrid();
            $('#csv-editor').hide();
            $('#csv-grid').show();
            $('#toggle-csv-view').html('<i class="fas fa-align-left"></i> Text View');
        }
        
        // Display special columns info immediately
        displaySpecialColumnsInfo();
        
        // Update warnings
        updateBulkConfigWarnings();
        
        showToast('Files loaded successfully', 'success');
    }).fail(function(xhr) {
        hideLoading();
        const response = xhr.responseJSON;
        showToast(response && response.error ? response.error : 'Error loading files', 'error');
    });
}

/**
 * Display special columns information from loaded CSV
 */
function displaySpecialColumnsInfo() {
    const csvContent = $('#csv-editor').val();
    if (!csvContent || !csvContent.trim()) return;
    
    const lines = csvContent.trim().split('\n');
    if (lines.length === 0) return;
    
    const headers = lines[0].split(',').map(h => h.trim());
    
    // Get JSON template placeholders
    const jsonContent = $('#json-editor').val();
    const jsonPlaceholders = [];
    if (jsonContent) {
        const regex = /\{\{([^}]+)\}\}/g;
        let match;
        while ((match = regex.exec(jsonContent)) !== null) {
            const placeholder = match[1].trim();
            if (!jsonPlaceholders.includes(placeholder)) {
                jsonPlaceholders.push(placeholder);
            }
        }
    }
    
    // Define special columns with color categories
    const specialColumns = {
        'id': { required: true, desc: 'Router ID - required for matching devices', color: 'green' },
        'name': { required: false, desc: 'System name - cached and used for exchange site creation', color: 'green' },
        'primary_lan_ip': { required: false, desc: 'Primary LAN IP - cached and used for site and LAN resource creation', color: 'green' },
        'desc': { required: false, desc: 'Description - injected into device configuration via API', color: 'green' },
        'custom1': { required: false, desc: 'Custom field 1 - set via NCM API (optional)', color: 'blue' },
        'custom2': { required: false, desc: 'Custom field 2 - set via NCM API (optional)', color: 'blue' },
        'site_tags': { required: false, desc: 'Per-device site tags - merged with global tags (optional, semicolon-separated)', color: 'blue' },
        'lan_resource_tags': { required: false, desc: 'Per-device LAN resource tags - merged with global tags (optional, semicolon-separated)', color: 'blue' },
        'cp_host_tags': { required: false, desc: 'Per-device CP host tags - merged with global tags (optional, semicolon-separated)', color: 'blue' },
        'wildcard_resource_tags': { required: false, desc: 'Per-device wildcard tags - merged with global tags (optional, semicolon-separated)', color: 'blue' },
        'disable_force_dns': { required: false, desc: 'Disable Force DNS - overrides global setting per device (optional, true/false)', color: 'blue' }
    };
    
    // Get all CSV columns
    const specialColumnNames = Object.keys(specialColumns);
    const templateColumns = headers.filter(col => !specialColumnNames.includes(col));
    
    // Categorize columns by color
    const greenColumns = [];
    const blueColumns = [];
    const redColumns = [];
    
    for (const [col, info] of Object.entries(specialColumns)) {
        const isPresent = headers.includes(col);
        const inTemplate = jsonPlaceholders.includes(col);
        
        if (!isPresent) {
            redColumns.push({ name: col, desc: info.desc });
        } else if (info.color === 'green') {
            greenColumns.push({ name: col, desc: info.desc });
        } else {
            blueColumns.push({ name: col, desc: info.desc });
        }
    }
    
    // Add template columns to green
    templateColumns.forEach(col => {
        const inTemplate = jsonPlaceholders.includes(col);
        const inCsv = headers.includes(col);
        
        if (inTemplate && inCsv) {
            // Column exists in both CSV and JSON
            const desc = `Template placeholder - use as {{${col}}} in JSON`;
            greenColumns.push({ name: col, desc: desc });
        } else if (inTemplate && !inCsv) {
            // Column only in JSON template, not in CSV
            const desc = `Template placeholder {{${col}}} has no matching CSV column`;
            redColumns.push({ name: col, desc: desc });
        } else if (!inTemplate && inCsv) {
            // Column only in CSV, not in JSON template
            const desc = 'CSV column not used in template';
            redColumns.push({ name: col, desc: desc });
        }
    });
    
    // Check for JSON placeholders that aren't in CSV and aren't special columns
    jsonPlaceholders.forEach(placeholder => {
        if (!headers.includes(placeholder) && !specialColumnNames.includes(placeholder)) {
            const desc = `Template placeholder {{${placeholder}}} has no matching CSV column`;
            if (!redColumns.find(c => c.name === placeholder)) {
                redColumns.push({ name: placeholder, desc: desc });
            }
        }
    });
    
    // Build content HTML with 3-column layout
    let content = '<div style="margin: 0; color: var(--text-secondary); font-size: 0.875rem;">';
    
    // Header explaining color coding
    content += '<div style="margin-bottom: 0.75rem; padding: 0.5rem; background: rgba(100, 116, 139, 0.1); border-radius: 4px;">';
    content += '<strong>Column Types:</strong> ';
    content += '<code style="color: #059669; background: rgba(5, 150, 105, 0.15); padding: 0.125rem 0.375rem; border-radius: 3px; font-weight: 600; margin: 0 0.25rem;">Config/Template</code> ';
    content += '<code style="color: #0284c7; background: rgba(2, 132, 199, 0.15); padding: 0.125rem 0.375rem; border-radius: 3px; font-weight: 600; margin: 0 0.25rem;">NCM/NCX/NCS</code> ';
    content += '<code style="color: #dc2626; background: rgba(220, 38, 38, 0.15); padding: 0.125rem 0.375rem; border-radius: 3px; font-weight: 600; margin: 0 0.25rem;">Missing</code>';
    content += '</div>';
    
    // 3-column layout
    content += '<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem;">';
    
    // Green column
    content += '<div><ul style="margin: 0; padding-left: 1.5rem;">';
    greenColumns.forEach(col => {
        content += `<li style="margin-bottom: 0.25rem;">`;
        content += `<code style="color: #059669; background: rgba(5, 150, 105, 0.15); padding: 0.125rem 0.375rem; border-radius: 3px; font-weight: 600;">✓ ${col.name}</code> `;
        content += `<span style="opacity: 0.8; font-size: 0.8125rem;">- ${col.desc}</span>`;
        content += `</li>`;
    });
    content += '</ul></div>';
    
    // Blue column
    content += '<div><ul style="margin: 0; padding-left: 1.5rem;">';
    blueColumns.forEach(col => {
        content += `<li style="margin-bottom: 0.25rem;">`;
        content += `<code style="color: #0284c7; background: rgba(2, 132, 199, 0.15); padding: 0.125rem 0.375rem; border-radius: 3px; font-weight: 600;">✓ ${col.name}</code> `;
        content += `<span style="opacity: 0.8; font-size: 0.8125rem;">- ${col.desc}</span>`;
        content += `</li>`;
    });
    content += '</ul></div>';
    
    // Red column
    content += '<div><ul style="margin: 0; padding-left: 1.5rem;">';
    redColumns.forEach(col => {
        content += `<li style="margin-bottom: 0.25rem;">`;
        content += `<code style="color: #dc2626; background: rgba(220, 38, 38, 0.15); padding: 0.125rem 0.375rem; border-radius: 3px; font-weight: 600;">✗ ${col.name}</code> `;
        content += `<span style="opacity: 0.8; font-size: 0.8125rem;">- ${col.desc}</span>`;
        content += `</li>`;
    });
    content += '</ul></div>';
    
    content += '</div></div>';
    
    const foundCount = specialColumnNames.filter(col => headers.includes(col)).length;
    const missingCount = specialColumnNames.length - foundCount;
    const title = `CSV Column Analysis (${foundCount + templateColumns.length} present, ${missingCount} missing)`;
    const html = makeCollapsible(content, title, 'info', true);
    
    // Remove existing special columns info before adding new one
    $('#special-columns-info').remove();
    
    // Insert before the grid container (parent of file-editor-panel)
    $('#file-editor-panel').parent().before(`<div id="special-columns-info" style="margin-top: 1rem; margin-bottom: 1.5rem;">${html}</div>`);
}

/**
 * Save files from editor
 */
function saveFilesFromEditor() {
    showConfirm('This will overwrite the current router_grid.csv and config_template.json files. Continue?', function(confirmed) {
        if (confirmed) {
            performSaveFiles();
        }
    });
}

/**
 * Perform the actual file saving
 */
function performSaveFiles() {
    const csvContent = $('#csv-editor').val();
    const jsonContent = $('#json-editor').val();
    
    showLoading('Saving files...');
    
    $.ajax({
        url: '/api/save-files',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            csv_content: csvContent,
            json_content: jsonContent
        }),
        success: function(response) {
            hideLoading();
            window.bulkConfigFilesModified = false;
            window.bulkConfigValidated = false;
            showToast('Files saved successfully', 'success');
            // Update file status indicators
            $('#bulk-config-file-status').html('<i class="fas fa-check-circle" style="color: var(--success-color);"></i> router_grid.csv (edited)');
            $('#config-template-file-status').html('<i class="fas fa-check-circle" style="color: var(--success-color);"></i> config_template.json (edited)');
            // Update warnings
            updateBulkConfigWarnings();
        },
        error: function(xhr) {
            hideLoading();
            const response = xhr.responseJSON;
            showToast(response && response.error ? response.error : 'Error saving files', 'error');
        }
    });
}

/**
 * Handle file upload
 */
function handleFileUpload(input, statusId) {
    const file = input.files[0];
    const statusDiv = $(`#${statusId}`);
    
    if (!file) {
        statusDiv.html('');
        return;
    }
    
    const uploadFile = (overwrite = false) => {
        const formData = new FormData();
        formData.append('file', file);
        if (overwrite) {
            formData.append('overwrite', 'true');
        }
        
        statusDiv.html('<i class="fas fa-spinner fa-spin"></i> Uploading...');
        
        $.ajax({
            url: '/api/upload',
            method: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                statusDiv.html(`<i class="fas fa-check-circle" style="color: var(--success-color);"></i> ${response.filename}`);
                
                // Read and display the uploaded file content immediately
                const reader = new FileReader();
                reader.onload = function(e) {
                    const content = e.target.result;
                    
                    if (response.filename.endsWith('.csv')) {
                        $('#csv-editor').val(content);
                        // Update grid view
                        syncTextToGrid();
                        $('#csv-editor').hide();
                        $('#csv-grid').show();
                        $('#toggle-csv-view').html('<i class="fas fa-align-left"></i> Text View');
                    } else if (response.filename.endsWith('.json')) {
                        $('#json-editor').val(content);
                        updateJsonPlaceholderHighlight();
                    }
                    
                    // Reset modification and validation flags
                    window.bulkConfigFilesModified = false;
                    window.bulkConfigValidated = false;
                    
                    // Clear validation status
                    $('#bulk-config-validation-status').html('');
                    
                    // Update CSV column analysis if both files are present
                    const csvContent = $('#csv-editor').val();
                    const jsonContent = $('#json-editor').val();
                    if (csvContent && csvContent.trim() && jsonContent && jsonContent.trim()) {
                        displaySpecialColumnsInfo();
                    }
                    
                    // Update warnings
                    updateBulkConfigWarnings();
                    
                    showToast('File uploaded successfully', 'success');
                };
                reader.readAsText(file);
            },
            error: function(xhr) {
                if (xhr.status === 413) {
                    statusDiv.html('<i class="fas fa-exclamation-circle" style="color: var(--danger-color);"></i> File exceeds 1MB limit');
                    showToast('File size exceeds 1MB limit', 'error');
                } else if (xhr.status === 409) {
                    // File exists - prompt for overwrite
                    const response = xhr.responseJSON;
                    showConfirm(`File "${response.filename}" already exists. Do you want to overwrite it?`, function(confirmed) {
                        if (confirmed) {
                            uploadFile(true);
                        } else {
                            statusDiv.html('');
                            input.value = ''; // Clear file input
                        }
                    });
                } else {
                    statusDiv.html('<i class="fas fa-exclamation-circle" style="color: var(--danger-color);"></i> Upload failed');
                    showToast('Upload failed', 'error');
                }
            }
        });
    };
    
    uploadFile();
}

/**
 * Validate optional parameters
 */
function validateOptionalParameters() {
    const bulkConfigEnabled = $('#self-bulk-config').is(':checked');
    const statusDiv = $('#optional-validation-status');
    
    if (!bulkConfigEnabled) {
        statusDiv.html(`
            <div style="padding: 1rem; background: rgba(2, 132, 199, 0.1); border: 1px solid var(--info-color); border-radius: var(--radius-md);">
                <p style="margin: 0; color: var(--info-color); font-weight: 500;">
                    <i class="fas fa-info-circle"></i> Bulk configuration is disabled
                </p>
            </div>
        `);
        showToast('Optional parameters validated', 'success');
        return;
    }
    
    // Check for uploaded files OR default files
    const csvFile = $('#bulk-config-file-upload')[0].files[0];
    const jsonFile = $('#config-template-file-upload')[0].files[0];
    const csvStatus = $('#bulk-config-file-status').text();
    const jsonStatus = $('#config-template-file-status').text();
    const hasDefaultCsv = csvStatus.includes('router_grid.csv');
    const hasDefaultJson = jsonStatus.includes('config_template.json');
    
    if (!csvFile && !hasDefaultCsv) {
        statusDiv.html(`
            <div style="padding: 1rem; background: rgba(220, 38, 38, 0.1); border: 1px solid var(--danger-color); border-radius: var(--radius-md);">
                <p style="margin: 0 0 0.5rem 0; color: var(--danger-color); font-weight: 600;">
                    <i class="fas fa-exclamation-circle"></i> Validation Error:
                </p>
                <ul style="margin: 0; padding-left: 1.5rem; color: var(--text-secondary);">
                    <li>Please upload CSV file or ensure router_grid.csv exists in working directory</li>
                </ul>
            </div>
        `);
        showToast('CSV file required', 'error');
        return;
    }
    
    if (!jsonFile && !hasDefaultJson) {
        statusDiv.html(`
            <div style="padding: 1rem; background: rgba(220, 38, 38, 0.1); border: 1px solid var(--danger-color); border-radius: var(--radius-md);">
                <p style="margin: 0 0 0.5rem 0; color: var(--danger-color); font-weight: 600;">
                    <i class="fas fa-exclamation-circle"></i> Validation Error:
                </p>
                <ul style="margin: 0; padding-left: 1.5rem; color: var(--text-secondary);">
                    <li>Please upload JSON file or ensure config_template.json exists in working directory</li>
                </ul>
            </div>
        `);
        showToast('JSON file required', 'error');
        return;
    }
    
    // Only validate if files were uploaded (skip validation for default files)
    if (!csvFile || !jsonFile) {
        statusDiv.html(`
            <div style="padding: 1rem; background: rgba(5, 150, 105, 0.1); border: 1px solid var(--success-color); border-radius: var(--radius-md);">
                <p style="margin: 0; color: var(--success-color); font-weight: 600;">
                    <i class="fas fa-check-circle"></i> Optional Parameters Valid
                </p>
                <p style="margin: 0.5rem 0 0 0; color: var(--text-secondary); font-size: 0.875rem;">
                    Using default files from working directory
                </p>
            </div>
        `);
        showToast('Optional parameters validated', 'success');
        return;
    }
    
    showLoading('Validating files...');
    
    const formData = new FormData();
    formData.append('csv_file', csvFile);
    formData.append('json_file', jsonFile);
    
    $.ajax({
        url: '/api/validate-files',
        method: 'POST',
        data: formData,
        processData: false,
        contentType: false,
        success: function(response) {
            hideLoading();
            statusDiv.html(`
                <div style="padding: 1rem; background: rgba(5, 150, 105, 0.1); border: 1px solid var(--success-color); border-radius: var(--radius-md);">
                    <p style="margin: 0; color: var(--success-color); font-weight: 600;">
                        <i class="fas fa-check-circle"></i> Files validated successfully
                    </p>
                    <p style="margin: 0.5rem 0 0 0; color: var(--text-secondary); font-size: 0.875rem;">
                        ${response.message}
                    </p>
                </div>
            `);
            showToast('Files validated successfully', 'success');
        },
        error: function(xhr) {
            hideLoading();
            const response = xhr.responseJSON;
            const errors = response && response.errors ? response.errors : ['Validation error'];
            
            let html = `
                <div style="padding: 1rem; background: rgba(220, 38, 38, 0.1); border: 1px solid var(--danger-color); border-radius: var(--radius-md);">
                    <p style="margin: 0 0 0.5rem 0; color: var(--danger-color); font-weight: 600;">
                        <i class="fas fa-exclamation-circle"></i> Validation Errors:
                    </p>
                    <ul style="margin: 0; padding-left: 1.5rem; color: var(--text-secondary);">
            `;
            errors.forEach(error => {
                html += `<li>${error}</li>`;
            });
            html += '</ul></div>';
            statusDiv.html(html);
            showToast('File validation error', 'error');
        }
    });
}

/**
 * Validate API keys connectivity
 */
function validateApiKeys() {
    const apiKeys = {
        'X-CP-API-ID': $('#x-cp-api-id').val().trim(),
        'X-CP-API-KEY': $('#x-cp-api-key').val().trim(),
        'X-ECM-API-ID': $('#x-ecm-api-id').val().trim(),
        'X-ECM-API-KEY': $('#x-ecm-api-key').val().trim(),
        'Bearer Token': $('#bearer-token').val().trim()
    };
    
    // Check if all fields are filled and collect all errors
    const errors = [];
    for (const [key, value] of Object.entries(apiKeys)) {
        if (!value) {
            errors.push(`${key} is required`);
        }
    }
    
    if (errors.length > 0) {
        showApiKeyValidationStatus(false, errors);
        showToast('Please fill in all API keys', 'error');
        return;
    }
    
    showLoading('Validating API keys...');
    
    $.ajax({
        url: '/api/validate-api-keys',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ api_keys: apiKeys }),
        success: function(response) {
            hideLoading();
            showApiKeyValidationStatus(true, response.message);
            showToast('API keys validated successfully', 'success');
        },
        error: function(xhr) {
            hideLoading();
            const response = xhr.responseJSON;
            const errorMsg = response && response.error ? response.error : 'API key validation error';
            showApiKeyValidationStatus(false, [errorMsg]);
            showToast('API key validation error', 'error');
        }
    });
}

/**
 * Display API key validation status
 */
function showApiKeyValidationStatus(success, message) {
    const statusDiv = $('#api-key-validation-status');
    
    if (success) {
        const content = `<p style="margin: 0; color: var(--text-secondary); font-size: 0.875rem;">${message}</p>`;
        statusDiv.html(makeCollapsible(content, 'API Keys Validated', 'success', true));
    } else {
        let content = '';
        
        if (Array.isArray(message)) {
            content = '<ul style="margin: 0; padding-left: 1.5rem; color: var(--text-secondary);">';
            message.forEach(error => {
                content += `<li>${error}</li>`;
            });
            content += '</ul>';
        } else {
            content = `<p style="margin: 0; color: var(--text-secondary); font-size: 0.875rem;">${message}</p>`;
        }
        
        statusDiv.html(makeCollapsible(content, 'Validation Error', 'error', true));
    }
}

/**
 * Validate required parameters
 */
function validateRequiredParameters() {
    const errors = [];
    const warnings = [];
    
    // Get values
    const stagingGroupId = $('#staging-group-id').val().trim();
    const prodGroupId = $('#prod-group-id').val().trim();
    const exchangeNetworkId = $('#exchange-network-id').val().trim();
    const secureConnectLic = $('#secure-connect-lic').val();
    const lanAsDns = $('#lan-as-dns').is(':checked');
    const localDomain = $('#local-domain').val().trim();
    
    // Validate staging group ID
    if (!stagingGroupId) {
        errors.push('Staging Group ID is required');
    } else if (!/^\d+$/.test(stagingGroupId)) {
        errors.push('Staging Group ID must be numeric');
    }
    
    // Validate production group ID
    if (!prodGroupId) {
        errors.push('Production Group ID is required');
    } else if (!/^\d+$/.test(prodGroupId)) {
        errors.push('Production Group ID must be numeric');
    }
    
    // Check if group IDs are different
    if (stagingGroupId && prodGroupId && stagingGroupId === prodGroupId) {
        errors.push('Staging and Production Group IDs must be different');
    }
    
    // Validate exchange network ID
    if (!exchangeNetworkId) {
        errors.push('Exchange Network ID is required');
    } else if (exchangeNetworkId.length < 10) {
        warnings.push('Exchange Network ID seems unusually short');
    }
    
    // Validate secure connect license
    if (!secureConnectLic) {
        errors.push('Secure Connect License is required');
    }
    
    // Validate local domain if LAN as DNS is enabled
    if (lanAsDns) {
        if (!localDomain) {
            errors.push('Local Domain is required when LAN as DNS is enabled');
        } else {
            // Validate FQDN format
            if (!/^[a-zA-Z0-9.-]+$/.test(localDomain)) {
                errors.push('Local Domain contains invalid characters');
            } else if (!localDomain.includes('.')) {
                warnings.push('Local Domain should typically include a TLD (e.g., .net, .com)');
            } else {
                const tld = localDomain.split('.').pop();
                if (!/^[a-zA-Z]+$/.test(tld)) {
                    errors.push('Local Domain TLD must contain only letters');
                }
            }
        }
    }
    
    const primaryDns = $('#primary-dns').val().trim();
    const secondaryDns = $('#secondary-dns').val().trim();
    const customDnsEnabled = $('#custom-dns-enabled').is(':checked');
    
    // Validate custom DNS if enabled
    if (customDnsEnabled) {
        if (!primaryDns) {
            errors.push('Primary DNS Server is required when Custom DNS is enabled');
        } else if (!validateIpAddress(primaryDns)) {
            errors.push('Primary DNS Server must be a valid IP address');
        }
        
        if (secondaryDns && !validateIpAddress(secondaryDns)) {
            errors.push('Secondary DNS Server must be a valid IP address');
        }
    }
    
    // Display results
    showRequiredValidationStatus(errors, warnings);
}

/**
 * Display required parameters validation status
 */
function showRequiredValidationStatus(errors, warnings) {
    const statusDiv = $('#required-validation-status');
    
    if (errors.length === 0 && warnings.length === 0) {
        const content = '<p style="margin: 0; color: var(--text-secondary); font-size: 0.875rem;">All required fields contain valid data</p>';
        statusDiv.html(makeCollapsible(content, 'All Required Parameters Valid', 'success', true));
        showToast('Required parameters validated', 'success');
    } else {
        let html = '';
        
        // Show errors
        if (errors.length > 0) {
            const errorContent = `
                <ul style="margin: 0; padding-left: 1.5rem; color: var(--text-secondary);">
                    ${errors.map(error => `<li>${error}</li>`).join('')}
                </ul>
            `;
            html += makeCollapsible(errorContent, 'Validation Errors', 'error', true);
        }
        
        // Show warnings
        if (warnings.length > 0) {
            const warningContent = `
                <ul style="margin: 0; padding-left: 1.5rem; color: var(--text-secondary);">
                    ${warnings.map(warning => `<li>${warning}</li>`).join('')}
                </ul>
            `;
            if (errors.length > 0) html += '<div style="margin-top: 1rem;"></div>';
            html += makeCollapsible(warningContent, 'Warnings', 'warning', true);
        }
        
        statusDiv.html(html);
        
        if (errors.length > 0) {
            showToast('Please fix validation errors', 'error');
        } else {
            showToast('Please review warnings', 'warning');
        }
    }
}

/**
 * Validate optional parameters
 */
function validateOptionalParameters() {
    const hmfLic = $('#hmf-lic').val();
    const statusDiv = $('#optional-validation-status');
    
    let html = '';
    
    // HMF warning
    if (hmfLic && hmfLic !== '') {
        html += `
            <div style="padding: 1rem; background: rgba(245, 158, 11, 0.1); border: 1px solid var(--warning-color); border-radius: var(--radius-md);">
                <p style="margin: 0; color: var(--warning-color); font-weight: 600;">
                    <i class="fas fa-exclamation-triangle"></i> HMF License Warning
                </p>
                <p style="margin: 0.5rem 0 0 0; color: var(--text-secondary); font-size: 0.875rem;">
                    When using HMF licenses, ALL sites in this exchange network MUST have an HMF license applied.
                </p>
            </div>
        `;
    }
    
    if (!html) {
        html = `
            <div style="padding: 1rem; background: rgba(5, 150, 105, 0.1); border: 1px solid var(--success-color); border-radius: var(--radius-md);">
                <p style="margin: 0; color: var(--success-color); font-weight: 500;">
                    <i class="fas fa-check-circle"></i> Optional parameters validated
                </p>
            </div>
        `;
    }
    statusDiv.html(html);
    showToast('Optional parameters validated', 'success');
}



/**
 * Validate bulk configuration
 */
function validateBulkConfiguration() {
    const bulkConfigEnabled = $('#self-bulk-config').is(':checked');
    const statusDiv = $('#bulk-config-validation-status');
    
    if (!bulkConfigEnabled) {
        const content = '<p style="margin: 0; color: var(--text-secondary); font-size: 0.875rem;">Bulk configuration is disabled</p>';
        statusDiv.html(makeCollapsible(content, 'Bulk Configuration Disabled', 'info', true));
        showToast('Bulk configuration is disabled', 'info');
        return;
    }
    
    // Check if files have unsaved changes
    if (window.bulkConfigFilesModified) {
        showAlert('You have unsaved changes. Please save or reload files before validating.');
        return;
    }
    
    // Check for 'id' column in CSV editor content
    const csvEditorContent = $('#csv-editor').val();
    if (csvEditorContent && csvEditorContent.trim()) {
        const lines = csvEditorContent.trim().split('\n');
        if (lines.length > 0) {
            const headers = lines[0].split(',').map(h => h.trim());
            if (!headers.includes('id')) {
                const errorContent = `
                    <ul style="margin: 0; padding-left: 1.5rem; color: var(--text-secondary);">
                        <li>CSV file is missing required 'id' column for router matching</li>
                    </ul>
                `;
                statusDiv.html(makeCollapsible(errorContent, 'Validation Error', 'error', true));
                showToast('CSV validation error', 'error');
                return;
            }
        }
    }
        const csvFile = $('#bulk-config-file-upload')[0].files[0];
        const jsonFile = $('#config-template-file-upload')[0].files[0];
        const csvStatus = $('#bulk-config-file-status').text();
        const jsonStatus = $('#config-template-file-status').text();
        const hasDefaultCsv = csvStatus.includes('router_grid.csv');
        const hasDefaultJson = jsonStatus.includes('config_template.json');
        
        if (!csvFile && !hasDefaultCsv) {
            statusDiv.html(`
                <div style="padding: 1rem; background: rgba(220, 38, 38, 0.1); border: 1px solid var(--danger-color); border-radius: var(--radius-md);">
                    <p style="margin: 0 0 0.5rem 0; color: var(--danger-color); font-weight: 600;">
                        <i class="fas fa-exclamation-circle"></i> Validation Error:
                    </p>
                    <ul style="margin: 0; padding-left: 1.5rem; color: var(--text-secondary);">
                        <li>Please upload CSV file or ensure router_grid.csv exists in working directory</li>
                    </ul>
                </div>
            `);
            showToast('CSV file required', 'error');
            return;
        }
        
        if (!jsonFile && !hasDefaultJson) {
            statusDiv.html(`
                <div style="padding: 1rem; background: rgba(220, 38, 38, 0.1); border: 1px solid var(--danger-color); border-radius: var(--radius-md);">
                    <p style="margin: 0 0 0.5rem 0; color: var(--danger-color); font-weight: 600;">
                        <i class="fas fa-exclamation-circle"></i> Validation Error:
                    </p>
                    <ul style="margin: 0; padding-left: 1.5rem; color: var(--text-secondary);">
                        <li>Please upload JSON file or ensure config_template.json exists in working directory</li>
                    </ul>
                </div>
            `);
            showToast('JSON file required', 'error');
            return;
        }
        
        // Only validate if files were uploaded (skip validation for default files)
        if (!csvFile || !jsonFile) {
            // Validate default files on server
            showLoading('Validating default files...');
            
            $.ajax({
                url: '/api/validate-default-files',
                method: 'GET',
                success: function(response) {
                    hideLoading();
                    
                    // Check for required 'id' column
                    if (!response.csv_columns.includes('id')) {
                        const errorContent = `
                            <ul style="margin: 0; padding-left: 1.5rem; color: var(--text-secondary);">
                                <li>CSV file is missing required 'id' column for router matching</li>
                            </ul>
                        `;
                        statusDiv.html(makeCollapsible(errorContent, 'Validation Error', 'error', true));
                        showToast('CSV validation error', 'error');
                        return;
                    }
                    
                    // Find matching columns (CSV columns that have corresponding JSON placeholders)
                    const matchingCols = response.csv_columns.filter(col => response.json_placeholders.includes(col));
                    const csvDisplay = response.csv_columns.map(col => {
                        if (matchingCols.includes(col)) {
                            return `<code style="color: #059669; background: rgba(5, 150, 105, 0.15); padding: 0.125rem 0.375rem; border-radius: 3px; font-weight: 600;">${col}</code>`;
                        }
                        return col;
                    }).join(', ');
                    const jsonDisplay = response.json_placeholders.map(p => {
                        const placeholder = '{{' + p + '}}';
                        if (matchingCols.includes(p)) {
                            return `<code style="color: #059669; background: rgba(5, 150, 105, 0.15); padding: 0.125rem 0.375rem; border-radius: 3px; font-weight: 600;">${placeholder}</code>`;
                        }
                        return placeholder;
                    }).join(', ');
                    
                    let html = `
                        <div style="padding: 1rem; background: rgba(5, 150, 105, 0.1); border: 1px solid var(--success-color); border-radius: var(--radius-md);">
                            <p style="margin: 0 0 0.5rem 0; color: var(--success-color); font-weight: 600;">
                                <i class="fas fa-check-circle"></i> CSV and JSON Files Validated
                            </p>
                            <p style="margin: 0; color: var(--text-secondary); font-size: 0.875rem;">
                                CSV: ${response.csv_count} columns (${csvDisplay})<br>
                                JSON: ${response.json_count} placeholders (${jsonDisplay})
                            </p>
                        </div>
                    `;
                    
                    statusDiv.html(html);
                    window.bulkConfigValidated = true;
                    updateBulkConfigWarnings();
                    showToast('Default files validated successfully', 'success');
                },
                error: function(xhr) {
                    hideLoading();
                    const response = xhr.responseJSON;
                    if (sc.site_tags || sc.lan_resource_tags || sc.cp_host_tags || sc.wildcard_resource_tags) {
                        const tagCols = [];
                        if (sc.site_tags) tagCols.push('<code style="color: #0284c7; background: rgba(2, 132, 199, 0.15); padding: 0.125rem 0.375rem; border-radius: 3px; font-weight: 600;">site_tags</code>');
                        if (sc.lan_resource_tags) tagCols.push('<code style="color: #0284c7; background: rgba(2, 132, 199, 0.15); padding: 0.125rem 0.375rem; border-radius: 3px; font-weight: 600;">lan_resource_tags</code>');
                        if (sc.cp_host_tags) tagCols.push('<code style="color: #0284c7; background: rgba(2, 132, 199, 0.15); padding: 0.125rem 0.375rem; border-radius: 3px; font-weight: 600;">cp_host_tags</code>');
                        if (sc.wildcard_resource_tags) tagCols.push('<code style="color: #0284c7; background: rgba(2, 132, 199, 0.15); padding: 0.125rem 0.375rem; border-radius: 3px; font-weight: 600;">wildcard_resource_tags</code>');
                        specialInfo.push(`Per-device tags (${tagCols.join(', ')}) will be merged with global tags (use semicolons if multiple tags are required e.g. branch;west;retail)`);
                    }
                    if (sc.disable_force_dns) specialInfo.push('Force all DNS Requests to Router will be disabled for sites where (<code style="color: #0284c7; background: rgba(2, 132, 199, 0.15); padding: 0.125rem 0.375rem; border-radius: 3px; font-weight: 600;">disable_force_dns</code>) is true');
                    
                    // Add info about global Force DNS setting
                    const globalDisableForceDns = $('#disable-force-dns').is(':checked');
                    if (globalDisableForceDns && sc.disable_force_dns) {
                        specialInfo.push('Global <code style="color: #0284c7; background: rgba(2, 132, 199, 0.15); padding: 0.125rem 0.375rem; border-radius: 3px; font-weight: 600;">Disable Force All DNS Requests to Router</code> setting is enabled but will be overridden by per-device CSV values');
                    } else if (globalDisableForceDns) {
                        specialInfo.push('Global <code style="color: #0284c7; background: rgba(2, 132, 199, 0.15); padding: 0.125rem 0.375rem; border-radius: 3px; font-weight: 600;">Disable Force All DNS Requests to Router</code> setting will disable Force All DNS Requests to Router for all devices (no CSV override column detected)');
                    }
                    
                    if (specialInfo.length > 0) {
                        const specialContent = `
                            <ul style="margin: 0; padding-left: 1.5rem; color: var(--text-secondary); font-size: 0.875rem;">
                                ${specialInfo.map(info => `<li>${info}</li>`).join('')}
                            </ul>
                        `;
                        html += '<div style="margin-top: 1rem;">' + makeCollapsible(specialContent, 'Special Columns Detected', 'info', true) + '</div>';
                    }
                    
                    // Add warning if disable_force_dns column has true values
                    if (sc.disable_force_dns && response.has_disable_force_dns_true) {
                        const warningContent = '<p style="margin: 0; color: var(--text-secondary); font-size: 0.875rem;">Disabling Force All DNS Requests to Router will increase provisioning time as the application must wait for VPN tunnels to establish before applying the configuration.</p>';
                        html += '<div style="margin-top: 1rem;">' + makeCollapsible(warningContent, 'Provisioning Time Warning', 'warning', true) + '</div>';
                    }
                    
                    statusDiv.html(html);
                    window.bulkConfigValidated = true;
                    updateBulkConfigWarnings();
                    showToast('Default files validated successfully', 'success');
                },
                error: function(xhr) {
                    hideLoading();
                    const response = xhr.responseJSON;
                    const errors = response && response.errors ? response.errors : ['Validation error'];
                    
                    let html = `
                        <div style="padding: 1rem; background: rgba(220, 38, 38, 0.1); border: 1px solid var(--danger-color); border-radius: var(--radius-md);">
                            <p style="margin: 0 0 0.5rem 0; color: var(--danger-color); font-weight: 600;">
                                <i class="fas fa-exclamation-circle"></i> Validation Errors:
                            </p>
                            <ul style="margin: 0; padding-left: 1.5rem; color: var(--text-secondary);">
                    `;
                    errors.forEach(error => {
                        html += `<li>${error}</li>`;
                    });
                    html += '</ul></div>';
                    statusDiv.html(html);
                    showToast('Default file validation error', 'error');
                }
            });
            return;
        }
        
        showLoading('Validating files...');
        
        const formData = new FormData();
        formData.append('csv_file', csvFile);
        formData.append('json_file', jsonFile);
        
        $.ajax({
            url: '/api/validate-files',
            method: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                hideLoading();
                
                // Check for required 'id' column
                if (!response.csv_columns.includes('id')) {
                    const errorContent = `
                        <ul style="margin: 0; padding-left: 1.5rem; color: var(--text-secondary);">
                            <li>CSV file is missing required 'id' column for router matching</li>
                        </ul>
                    `;
                    statusDiv.html(makeCollapsible(errorContent, 'Validation Error', 'error', true));
                    showToast('CSV validation error', 'error');
                    return;
                }
                
                // Find matching columns (CSV columns that have corresponding JSON placeholders)
                const matchingCols = response.csv_columns.filter(col => response.json_placeholders.includes(col));
                const csvDisplay = response.csv_columns.map(col => {
                    if (matchingCols.includes(col)) {
                        return `<code style="color: #059669; background: rgba(5, 150, 105, 0.15); padding: 0.125rem 0.375rem; border-radius: 3px; font-weight: 600;">${col}</code>`;
                    }
                    return col;
                }).join(', ');
                const jsonDisplay = response.json_placeholders.map(p => {
                    const placeholder = '{{' + p + '}}';
                    if (matchingCols.includes(p)) {
                        return `<code style="color: #059669; background: rgba(5, 150, 105, 0.15); padding: 0.125rem 0.375rem; border-radius: 3px; font-weight: 600;">${placeholder}</code>`;
                    }
                    return placeholder;
                }).join(', ');
                
                let html = `
                    <div style="padding: 1rem; background: rgba(5, 150, 105, 0.1); border: 1px solid var(--success-color); border-radius: var(--radius-md);">
                        <p style="margin: 0 0 0.5rem 0; color: var(--success-color); font-weight: 600;">
                            <i class="fas fa-check-circle"></i> CSV and JSON Files Validated
                        </p>
                        <p style="margin: 0; color: var(--text-secondary); font-size: 0.875rem;">
                            CSV: ${response.csv_count} columns (${csvDisplay})<br>
                            JSON: ${response.json_count} placeholders (${jsonDisplay})
                        </p>
                    </div>
                `;
                
                statusDiv.html(html);
                window.bulkConfigValidated = true;
                updateBulkConfigWarnings();
                showToast('Files validated successfully', 'success');
            },
            error: function(xhr) {
                hideLoading();
                const response = xhr.responseJSON;
                const errors = response && response.errors ? response.errors : ['Validation failed'];
                
                let html = `
                    <div style="padding: 1rem; background: rgba(220, 38, 38, 0.1); border: 1px solid var(--danger-color); border-radius: var(--radius-md);">
                        <p style="margin: 0 0 0.5rem 0; color: var(--danger-color); font-weight: 600;">
                            <i class="fas fa-exclamation-circle"></i> Validation Errors:
                        </p>
                        <ul style="margin: 0; padding-left: 1.5rem; color: var(--text-secondary);">
                `;
                errors.forEach(error => {
                    html += `<li>${error}</li>`;
                });
                html += '</ul></div>';
                statusDiv.html(html);
                showToast('File validation error', 'error');
            }
        });
}

/**
 * Collect form data
 */
function collectFormData() {
    return {
        api_keys: {
            'X-CP-API-ID': $('#x-cp-api-id').val().trim(),
            'X-CP-API-KEY': $('#x-cp-api-key').val().trim(),
            'X-ECM-API-ID': $('#x-ecm-api-id').val().trim(),
            'X-ECM-API-KEY': $('#x-ecm-api-key').val().trim(),
            'Bearer Token': $('#bearer-token').val().trim()
        },
        staging_group_id: $('#staging-group-id').val().trim(),
        prod_group_id: $('#prod-group-id').val().trim(),
        exchange_network_id: $('#exchange-network-id').val().trim(),
        secure_connect_lic: $('#secure-connect-lic').val(),
        lan_as_dns: $('#lan-as-dns').is(':checked'),
        local_domain: $('#local-domain').val().trim(),
        custom_dns_enabled: $('#custom-dns-enabled').is(':checked'),
        primary_dns: $('#primary-dns').val().trim(),
        secondary_dns: $('#secondary-dns').val().trim(),
        sdwan_lic: $('#sdwan-lic').val(),
        hmf_lic: $('#hmf-lic').val(),
        ai_lic: $('#ai-lic').val(),
        create_lan_resource: $('#create-lan-resource').is(':checked'),
        create_cp_host_resource: $('#create-cp-host-resource').is(':checked'),
        create_wildcard_resource: $('#create-wildcard-resource').is(':checked'),
        disable_force_dns: $('#disable-force-dns').is(':checked'),
        self_bulk_config: $('#self-bulk-config').is(':checked'),
        bulk_config_file: $('#bulk-config-file-upload')[0].files[0] ? $('#bulk-config-file-upload')[0].files[0].name : 'router_grid.csv',
        config_template_file: $('#config-template-file-upload')[0].files[0] ? $('#config-template-file-upload')[0].files[0].name : 'config_template.json',
        site_tags: $('#site-tags').val().trim(),
        lan_resource_tags: $('#lan-resource-tags').val().trim(),
        cp_host_tags: $('#cp-host-tags').val().trim(),
        wildcard_tags: $('#wildcard-tags').val().trim()
    };
}

/**
 * Update configuration summary
 */
function updateSummary() {
    const data = collectFormData();
    const summary = $('#config-summary');
    
    let html = '<div style="display: grid; grid-template-columns: calc(33.33% - 1.33rem - 0.67px) calc(33.33% - 1.33rem - 0.67px) calc(33.33% - 1.33rem - 0.67px);">';
    
    // Column 1: Required Parameters
    html += '<div style="padding-right: 1rem;">';
    html += '<h3 style="margin-bottom: 0.75rem; color: var(--primary-color);">Required Parameters</h3>';
    html += '<div style="display: grid; gap: 0.5rem;">';
    html += `<div><strong>Staging Group ID:</strong> ${data.staging_group_id || '<em>Not set</em>'}</div>`;
    html += `<div><strong>Production Group ID:</strong> ${data.prod_group_id || '<em>Not set</em>'}</div>`;
    html += `<div><strong>Exchange Network ID:</strong> ${data.exchange_network_id || '<em>Not set</em>'}</div>`;
    html += `<div><strong>Secure Connect License:</strong> ${data.secure_connect_lic || '<em>Not set</em>'}</div>`;
    html += `<div><strong>LAN as DNS:</strong> ${data.lan_as_dns ? 'Enabled' : 'Disabled'}</div>`;
    if (data.lan_as_dns) {
        html += `<div><strong>Local Domain:</strong> ${data.local_domain || '<em>Not set</em>'}</div>`;
    }
    if (data.custom_dns_enabled) {
        html += `<div><strong>Primary DNS:</strong> ${data.primary_dns || '<em>Not set</em>'}</div>`;
        html += `<div><strong>Secondary DNS:</strong> ${data.secondary_dns || '<em>Not set</em>'}</div>`;
    }
    html += '</div></div>';
    
    // Column 2: Optional Parameters
    html += '<div style="border-left: 2px solid var(--border-color); padding-left: 1rem; padding-right: 1rem;">';
    html += '<h3 style="margin-bottom: 0.75rem; color: var(--primary-color);">Optional Parameters</h3>';
    html += '<div style="display: grid; gap: 0.5rem;">';
    html += `<div><strong>SD-WAN License:</strong> ${data.sdwan_lic || 'None'}</div>`;
    html += `<div><strong>HMF License:</strong> ${data.hmf_lic || 'None'}</div>`;
    html += `<div><strong>AI License:</strong> ${data.ai_lic || 'None'}</div>`;
    html += `<div><strong>Create LAN Resource:</strong> ${data.create_lan_resource ? 'Yes' : 'No'}</div>`;
    html += `<div><strong>Create CP Host Resource:</strong> ${data.create_cp_host_resource ? 'Yes' : 'No'}</div>`;
    html += `<div><strong>Create Wildcard Resource:</strong> ${data.create_wildcard_resource ? 'Yes' : 'No'}</div>`;
    html += `<div><strong>Disable Force All DNS Requests to Router:</strong> ${data.disable_force_dns ? 'Yes (can be overridden in CSV)' : 'No'}</div>`;
    html += '</div></div>';
    
    // Column 3: Tags & Bulk Config
    html += '<div style="border-left: 2px solid var(--border-color); padding-left: 1rem;">';
    html += '<h3 style="margin-bottom: 0.75rem; color: var(--primary-color);">Tags & Bulk Config</h3>';
    html += '<div style="display: grid; gap: 0.5rem;">';
    html += `<div><strong>Global Site Tags:</strong> ${data.site_tags || '<em>None</em>'}</div>`;
    html += `<div><strong>Global LAN Resource Tags:</strong> ${data.lan_resource_tags || '<em>None</em>'}</div>`;
    html += `<div><strong>Global CP Host Tags:</strong> ${data.cp_host_tags || '<em>None</em>'}</div>`;
    html += `<div><strong>Global Wildcard Tags:</strong> ${data.wildcard_tags || '<em>None</em>'}</div>`;
    html += `<div><strong>Bulk Configuration:</strong> ${data.self_bulk_config ? 'Enabled' : 'Disabled'}</div>`;
    if (data.self_bulk_config) {
        html += `<div><strong>Bulk Config File:</strong> ${data.bulk_config_file}</div>`;
        html += `<div><strong>Config Template File:</strong> ${data.config_template_file}</div>`;
    }
    html += '</div></div>';
    
    html += '</div>';
    summary.html(html);
}

/**
 * Validate configuration
 */
function validateConfiguration() {
    const data = collectFormData();
    
    // Collect client-side validation errors
    const clientErrors = [];
    
    // Client-side validation for bulk config 'id' column
    if (data.self_bulk_config) {
        const csvEditorContent = $('#csv-editor').val();
        if (csvEditorContent && csvEditorContent.trim()) {
            const lines = csvEditorContent.trim().split('\n');
            if (lines.length > 0) {
                const headers = lines[0].split(',').map(h => h.trim());
                if (!headers.includes('id')) {
                    clientErrors.push("CSV file is missing required 'id' column for router matching");
                }
            }
        }
    }
    
    showLoading('Validating configuration...');
    const startTime = Date.now();
    
    $.ajax({
        url: '/api/validate',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(data),
        success: function(response) {
            // Ensure minimum 1 second display
            const elapsed = Date.now() - startTime;
            const remaining = Math.max(0, 1000 - elapsed);
            setTimeout(function() {
                hideLoading();
                displayValidationResults(true, response.message);
                $('#apply-btn').attr('data-validated', 'true').removeClass('btn-secondary').addClass('btn-success');
                $('#validation-info').hide();
                showToast('Validation passed', 'success');
            }, remaining);
        },
        error: function(xhr) {
            // Ensure minimum 1 second display
            const elapsed = Date.now() - startTime;
            const remaining = Math.max(0, 1000 - elapsed);
            setTimeout(function() {
                hideLoading();
                const response = xhr.responseJSON;
                let allErrors = [];
                // Add server errors first (API Keys, Required, Optional, Tags)
                if (response && response.errors) {
                    allErrors = allErrors.concat(response.errors);
                }
                // Add client errors last (Bulk Config)
                allErrors = allErrors.concat(clientErrors);
                
                if (allErrors.length === 0) {
                    allErrors = ['Unknown validation error'];
                }
                displayValidationResults(false, allErrors);
                $('#apply-btn').attr('data-validated', 'false').removeClass('btn-success').addClass('btn-secondary');
                $('#validation-info').show();
                showToast('Validation error', 'error');
            }, remaining);
        }
    });
}

/**
 * Display validation results
 */
function displayValidationResults(success, message) {
    const resultsDiv = $('#validation-results');
    
    if (success) {
        const content = `<p style="margin: 0; color: var(--text-secondary); font-size: 0.875rem;">${message}</p>`;
        resultsDiv.html(makeCollapsible(content, 'Configuration Valid', 'success', true));
    } else {
        let content = '';
        
        if (Array.isArray(message)) {
            content = `
                <ul style="margin: 0; padding-left: 1.5rem; color: var(--text-secondary);">
                    ${message.map(error => `<li>${error}</li>`).join('')}
                </ul>
            `;
        } else {
            content = `<p style="margin: 0; color: var(--text-secondary); font-size: 0.875rem;">${message}</p>`;
        }
        
        resultsDiv.html(makeCollapsible(content, 'Validation Errors', 'error', true));
    }
}

/**
 * Apply configuration
 */
function applyConfiguration() {
    // Check if validated
    if ($('#apply-btn').attr('data-validated') !== 'true') {
        // Scroll to top to show info message
        window.scrollTo({ top: 0, behavior: 'smooth' });
        return;
    }
    
    showConfirm('Are you sure you want to apply this configuration to the staging group?', function(confirmed) {
        if (!confirmed) return;
        
        const data = collectFormData();
        
        showLoading('Applying configuration...');
        
        $.ajax({
            url: '/api/configure',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function(response) {
                hideLoading();
                showToast('Configuration applied successfully!', 'success');
                displayValidationResults(true, response.message);
                
                // Show success message with Next Steps
                const resultsDiv = $('#validation-results');
                const nextStepsContent = `
                    <ol style="margin: 0; padding-left: 1.5rem; color: var(--text-secondary);">
                        <li>Build the SDK package: <code>python make.py build ncx_self_provision</code></li>
                        <li>Upload to NCM and assign to your staging group</li>
                        <li>Move devices to staging group (maximum 50 at a time)</li>
                        <li>Monitor device logs for provisioning progress</li>
                    </ol>
                `;
                resultsDiv.html(`
                    <div style="padding: 1.5rem; background: rgba(5, 150, 105, 0.1); border: 1px solid var(--success-color); border-radius: var(--radius-md);">
                        <p style="margin: 0 0 0.75rem 0; color: var(--success-color); font-weight: 600; font-size: 1.125rem;">
                            <i class="fas fa-check-circle"></i> Configuration Applied Successfully!
                        </p>
                        <p style="margin: 0; color: var(--text-secondary);">
                            The staging group has been configured with all parameters and API keys.
                        </p>
                    </div>
                    <div style="margin-top: 1rem;">${makeCollapsible(nextStepsContent, 'Next Steps', 'info', true)}</div>
                `);
            },
            error: function(xhr) {
                hideLoading();
                const response = xhr.responseJSON;
                let errorMsg = 'Unknown error occurred';
                
                if (response) {
                    if (response.error) {
                        errorMsg = response.error;
                    } else if (response.errors) {
                        errorMsg = response.errors.join(', ');
                    }
                }
                
                showToast('Configuration error: ' + errorMsg, 'error');
                displayValidationResults(false, [errorMsg]);
            }
        });
    });
}

/**
 * Show loading modal (smaller, centered)
 */
function showLoading(message) {
    $('#loading-message').text(message);
    $('#loading-overlay').css('display', 'block');
}

/**
 * Hide loading modal
 */
function hideLoading() {
    $('#loading-overlay').css('display', 'none');
}

/**
 * Show toast notification
 */
function showToast(message, type = 'info') {
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };
    
    const toast = $(`
        <div class="toast ${type}">
            <i class="fas ${icons[type]}"></i>
            <div class="toast-content">
                <div class="toast-message">${message}</div>
            </div>
        </div>
    `);
    
    $('#toast-container').append(toast);
    
    setTimeout(() => {
        toast.addClass('show');
    }, 10);
    
    setTimeout(() => {
        toast.removeClass('show');
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 5000);
}
