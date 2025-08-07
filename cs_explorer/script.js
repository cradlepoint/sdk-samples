/**
 * Router Data Browser JavaScript
 * Handles all frontend functionality for the router data browser interface
 */

class RouterDataBrowser {
    constructor() {
        this.currentPath = '';
        this.currentData = null;
        this.expandedNodes = new Set();
        this.treeData = null;
        this.isRawView = false;
        
        this.initializeElements();
        this.attachEventListeners();
        this.initializeDarkMode();
        // Add a small delay to ensure DOM is fully ready
        setTimeout(() => {
            this.loadInitialTree();
        }, 100);
    }

    initializeElements() {
        // Main elements
        this.treeView = document.getElementById('treeView');
        this.contentDisplay = document.getElementById('contentDisplay');
        this.welcomeScreen = document.getElementById('welcomeScreen');
        this.searchResults = document.getElementById('searchResults');
        this.loadingOverlay = document.getElementById('loadingOverlay');
        this.errorModal = document.getElementById('errorModal');
        
        // Sidebar elements
        this.sidebar = document.getElementById('sidebar');
        this.sidebarResizer = document.getElementById('sidebarResizer');
        
        // Search elements
        this.searchInput = document.getElementById('searchInput');
        this.searchBtn = document.getElementById('searchBtn');
        this.darkModeToggle = document.getElementById('darkModeToggle');
        this.searchResultsList = document.getElementById('searchResultsList');
        this.searchQuery = document.getElementById('searchQuery');
        
        // Content elements
        this.breadcrumb = document.getElementById('breadcrumb');
        this.contentIcon = document.getElementById('contentIcon');
        this.contentName = document.getElementById('contentName');
        this.contentType = document.getElementById('contentType');
        this.contentSize = document.getElementById('contentSize');
        this.lastUpdated = document.getElementById('lastUpdated');
        this.dataContainer = document.getElementById('dataContainer');
        
        // Toolbar elements
        this.refreshBtn = document.getElementById('refreshBtn');
        this.expandAllBtn = document.getElementById('expandAllBtn');
        this.collapseAllBtn = document.getElementById('collapseAllBtn');
        this.copyDataBtn = document.getElementById('copyDataBtn');
        this.downloadBtn = document.getElementById('downloadBtn');
        this.rawViewBtn = document.getElementById('rawViewBtn');
        this.prettyViewBtn = document.getElementById('prettyViewBtn');
        this.legendToggleBtn = document.getElementById('legendToggleBtn');
        
        // Legend elements
        this.floatingLegend = document.getElementById('floatingLegend');
        this.closeLegendBtn = document.getElementById('closeLegendBtn');
        
        // Modal elements
        this.closeErrorModal = document.getElementById('closeErrorModal');
        this.errorMessage = document.getElementById('errorMessage');
    }

    attachEventListeners() {
        // Search functionality
        if (this.searchBtn) {
            this.searchBtn.addEventListener('click', () => this.performSearch());
        }
        
        if (this.searchInput) {
            this.searchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.performSearch();
            });
            this.searchInput.addEventListener('input', () => {
                if (this.searchInput.value === '') {
                    this.hideSearchResults();
                }
            });
        }

        // Dark mode toggle
        if (this.darkModeToggle) {
            this.darkModeToggle.addEventListener('click', () => this.toggleDarkMode());
        }

        // Toolbar buttons
        if (this.refreshBtn) {
            this.refreshBtn.addEventListener('click', () => this.refreshTree());
        }
        if (this.expandAllBtn) {
            this.expandAllBtn.addEventListener('click', () => this.expandAll());
        }
        if (this.collapseAllBtn) {
            this.collapseAllBtn.addEventListener('click', () => this.collapseAll());
        }
        
        // Sidebar resizing
        this.initializeSidebarResizing();
        
        // Content toolbar
        if (this.copyDataBtn) {
            this.copyDataBtn.addEventListener('click', () => this.copyData());
        }
        if (this.downloadBtn) {
            this.downloadBtn.addEventListener('click', () => this.downloadData());
        }
        if (this.rawViewBtn) {
            this.rawViewBtn.addEventListener('click', () => this.toggleRawView(true));
        }
        if (this.prettyViewBtn) {
            this.prettyViewBtn.addEventListener('click', () => this.toggleRawView(false));
        }
        if (this.legendToggleBtn) {
            this.legendToggleBtn.addEventListener('click', () => this.toggleLegend());
        }
        
        // Legend controls
        if (this.closeLegendBtn) {
            this.closeLegendBtn.addEventListener('click', () => this.hideLegend());
        }
        
        // Modal
        if (this.closeErrorModal) {
            this.closeErrorModal.addEventListener('click', () => this.hideError());
        }
        
        // Click outside modal to close
        if (this.errorModal) {
            this.errorModal.addEventListener('click', (e) => {
                if (e.target === this.errorModal) this.hideError();
            });
        }
    }

    async loadInitialTree() {
        try {
            this.showLoading();
            const response = await this.apiCall('/api/tree', { path: '' });
            
            if (response && response.tree) {
                this.treeData = response.tree;
                this.renderTree();
            } else {
                this.showError('Invalid response format from server');
            }
        } catch (error) {
            this.showError('Failed to load tree structure: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    async apiCall(endpoint, params = {}) {
        const url = new URL(endpoint, window.location.origin);
        Object.keys(params).forEach(key => url.searchParams.append(key, params[key]));
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'API call failed');
        }
        
        return data;
    }

    renderTree() {
        this.treeView.innerHTML = '';
        
        if (!this.treeData || this.treeData.length === 0) {
            this.treeView.innerHTML = '<div class="text-muted text-center mt-2">No data available</div>';
            return;
        }

        this.treeData.forEach(item => {
            this.treeView.appendChild(this.createTreeNode(item, 0));
        });
    }

    createTreeNode(item, level) {
        const nodeDiv = document.createElement('div');
        nodeDiv.className = 'tree-item';
        nodeDiv.dataset.path = item.path;

        const nodeContent = document.createElement('div');
        nodeContent.className = 'tree-node';
        nodeContent.style.paddingLeft = `${level * 1}rem`;

        // Toggle button for folders
        const toggle = document.createElement('span');
        toggle.className = 'tree-toggle';
        
        if (item.type === 'folder') {
            if (item.children) {
                // Already loaded children
                toggle.innerHTML = this.expandedNodes.has(item.path) ? '▼' : '▶';
            } else if (item.has_children) {
                // Has children but not loaded yet
                toggle.innerHTML = '▶';
            } else {
                // Empty folder
                toggle.innerHTML = '📁';
            }
            
            toggle.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleNode(item);
            });
        }

        // Icon with type-specific styling
        const icon = document.createElement('i');
        if (item.type === 'folder') {
            icon.className = 'tree-icon folder fas fa-folder';
            if (item.list_type) {
                icon.className = 'tree-icon folder fas fa-list';
            }
        } else {
            icon.className = 'tree-icon file fas fa-file';
            // Different icons for different data types
            if (item.value_type) {
                switch (item.value_type) {
                    case 'bool':
                        icon.className = 'tree-icon file fas fa-toggle-on';
                        break;
                    case 'int':
                    case 'float':
                        icon.className = 'tree-icon file fas fa-hashtag';
                        break;
                    case 'list':
                        icon.className = 'tree-icon file fas fa-list-ul';
                        break;
                    default:
                        icon.className = 'tree-icon file fas fa-file-alt';
                }
            }
        }

        // Name with preview for files
        const nameContainer = document.createElement('span');
        nameContainer.className = 'tree-name';
        
        const name = document.createElement('span');
        name.textContent = item.name;
        nameContainer.appendChild(name);
        
        // Add preview for files
        if (item.type === 'file' && item.preview) {
            const preview = document.createElement('span');
            preview.className = 'tree-preview';
            preview.textContent = ` = ${item.preview}`;
            nameContainer.appendChild(preview);
        }

        nodeContent.appendChild(toggle);
        nodeContent.appendChild(icon);
        nodeContent.appendChild(nameContainer);

        // Click handler
        nodeContent.addEventListener('click', () => this.selectNode(item));

        nodeDiv.appendChild(nodeContent);

        // Children container
        if (item.type === 'folder') {
            const childrenDiv = document.createElement('div');
            childrenDiv.className = `tree-children ${this.expandedNodes.has(item.path) ? '' : 'collapsed'}`;
            childrenDiv.dataset.path = item.path;
            
            if (item.children) {
                item.children.forEach(child => {
                    childrenDiv.appendChild(this.createTreeNode(child, level + 1));
                });
            }
            
            nodeDiv.appendChild(childrenDiv);
        }

        return nodeDiv;
    }

    async toggleNode(item) {
        if (this.expandedNodes.has(item.path)) {
            // Collapse
            this.expandedNodes.delete(item.path);
            this.renderTree();
        } else {
            // Expand
            this.expandedNodes.add(item.path);
            
            // If this folder doesn't have loaded children yet, load them
            if (item.type === 'folder' && !item.children && item.has_children) {
                await this.loadFolderChildren(item);
            }
            
            this.renderTree();
        }
    }

    async loadFolderChildren(item) {
        try {
            this.showLoading();
            const response = await this.apiCall('/api/tree', { path: item.path });
            
            if (response.tree) {
                // Add children to the item
                item.children = response.tree;
                
                // Update the tree data in place
                this.updateTreeItemInPlace(item);
            }
        } catch (error) {
            this.showError('Failed to load folder contents: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    updateTreeItemInPlace(updatedItem) {
        // Find and update the item in the tree data structure
        const updateRecursive = (items) => {
            for (let i = 0; i < items.length; i++) {
                if (items[i].path === updatedItem.path) {
                    items[i] = updatedItem;
                    return true;
                }
                if (items[i].children && updateRecursive(items[i].children)) {
                    return true;
                }
            }
            return false;
        };
        
        if (this.treeData) {
            updateRecursive(this.treeData);
        }
    }

    async selectNode(item) {
        // Update visual selection
        document.querySelectorAll('.tree-node').forEach(node => {
            node.classList.remove('selected');
        });
        event.currentTarget.classList.add('selected');

        // Load and display data for both files and folders
        await this.loadFileData(item.path);
        
        // Also expand/collapse folders when clicked
        if (item.type === 'folder') {
            this.toggleNode(item);
        }
    }

    async loadFileData(path) {
        try {
            this.showLoading();
            const response = await this.apiCall('/api/data', { path });
            this.currentPath = path;
            this.currentData = response;
            this.displayFileData(response);
            this.updateBreadcrumb(path);
            this.showContentDisplay();
        } catch (error) {
            this.showError('Failed to load file data: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    displayFileData(data) {
        // Determine data type and appropriate icon
        const dataType = this.getDataType(data.data);
        let iconClass = 'fas fa-file';
        
        switch (dataType) {
            case 'object':
                iconClass = 'fas fa-code';
                break;
            case 'array':
                iconClass = 'fas fa-list';
                break;
            case 'string':
                iconClass = 'fas fa-file-alt';
                break;
            case 'number':
                iconClass = 'fas fa-hashtag';
                break;
            case 'boolean':
                iconClass = 'fas fa-toggle-on';
                break;
            case 'null':
                iconClass = 'fas fa-ban';
                break;
        }
        
        // Update header
        this.contentIcon.className = iconClass;
        this.contentName.textContent = data.path.split('/').pop() || 'Root';
        this.contentType.textContent = dataType.charAt(0).toUpperCase() + dataType.slice(1);
        this.contentSize.textContent = `${this.getDataSize(data.data)} ${this.getSizeUnit(data.data)}`;
        this.lastUpdated.textContent = new Date().toLocaleTimeString();

        // Display data
        this.renderDataContent(data.data);
    }

    getDataType(data) {
        if (data === null || data === undefined) return 'null';
        if (Array.isArray(data)) return 'array';
        if (typeof data === 'object') return 'object';
        return typeof data;
    }

    getDataSize(data) {
        if (data === null || data === undefined) return 0;
        if (Array.isArray(data)) return data.length;
        if (typeof data === 'object') return Object.keys(data).length;
        if (typeof data === 'string') return data.length;
        return 1;
    }

    getSizeUnit(data) {
        if (data === null || data === undefined) return 'null';
        if (Array.isArray(data)) return data.length === 1 ? 'item' : 'items';
        if (typeof data === 'object') {
            const count = Object.keys(data).length;
            return count === 1 ? 'property' : 'properties';
        }
        if (typeof data === 'string') return data.length === 1 ? 'char' : 'chars';
        return 'value';
    }

    renderDataContent(data) {
        if (this.isRawView) {
            this.dataContainer.innerHTML = `<pre class="json-container">${JSON.stringify(data, null, 2)}</pre>`;
        } else {
            this.dataContainer.innerHTML = `<pre class="json-container">${this.formatJsonPretty(data)}</pre>`;
        }
    }

    formatJsonPretty(data, indent = 0, currentPath = '') {
        const indentStr = '  '.repeat(indent);
        const nextIndentStr = '  '.repeat(indent + 1);
        
        if (data === null) {
            return '<span class="json-null">null</span>';
        }
        
        if (typeof data === 'string') {
            // Check if the string starts with '$1' (encrypted value)
            if (data.startsWith('$1')) {
                const fullPath = currentPath || this.currentPath;
                return this.formatEncryptedValue(data, fullPath);
            }
            return `<span class="json-string">"${this.escapeHtml(data)}"</span>`;
        }
        
        if (typeof data === 'number') {
            return `<span class="json-number">${data}</span>`;
        }
        
        if (typeof data === 'boolean') {
            return `<span class="json-boolean">${data}</span>`;
        }
        
        if (Array.isArray(data)) {
            if (data.length === 0) return '<span class="json-punctuation">[]</span>';
            
            let result = '<span class="json-punctuation">[</span>\n';
            data.forEach((item, index) => {
                result += nextIndentStr;
                const itemPath = currentPath ? `${currentPath}/${index}` : `${this.currentPath}/${index}`;
                result += this.formatJsonPretty(item, indent + 1, itemPath);
                if (index < data.length - 1) {
                    result += '<span class="json-punctuation">,</span>';
                }
                result += '\n';
            });
            result += indentStr + '<span class="json-punctuation">]</span>';
            return result;
        }
        
        if (typeof data === 'object') {
            const keys = Object.keys(data);
            if (keys.length === 0) return '<span class="json-punctuation">{}</span>';
            
            let result = '<span class="json-punctuation">{</span>\n';
            keys.forEach((key, index) => {
                result += nextIndentStr;
                result += `<span class="json-key">"${this.escapeHtml(key)}"</span>`;
                result += '<span class="json-punctuation">: </span>';
                const keyPath = currentPath ? `${currentPath}/${key}` : `${this.currentPath}/${key}`;
                result += this.formatJsonPretty(data[key], indent + 1, keyPath);
                if (index < keys.length - 1) {
                    result += '<span class="json-punctuation">,</span>';
                }
                result += '\n';
            });
            result += indentStr + '<span class="json-punctuation">}</span>';
            return result;
        }
        
        return String(data);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    updateBreadcrumb(path) {
        this.breadcrumb.innerHTML = '';
        
        // Home
        const home = document.createElement('span');
        home.className = 'breadcrumb-item';
        home.innerHTML = '<i class="fas fa-home"></i> Root';
        home.addEventListener('click', () => this.showWelcomeScreen());
        this.breadcrumb.appendChild(home);
        
        // Path segments
        if (path) {
            const segments = path.split('/').filter(Boolean);
            segments.forEach((segment, index) => {
                const item = document.createElement('span');
                item.className = `breadcrumb-item ${index === segments.length - 1 ? 'active' : ''}`;
                item.textContent = segment;
                
                if (index < segments.length - 1) {
                    const partialPath = segments.slice(0, index + 1).join('/');
                    item.addEventListener('click', () => this.loadFileData(partialPath));
                }
                
                this.breadcrumb.appendChild(item);
            });
        }
    }

    async performSearch() {
        const query = this.searchInput.value.trim();
        if (!query) return;

        try {
            this.showLoading();
            const response = await this.apiCall('/api/search', { q: query });
            this.displaySearchResults(response.results, query);
        } catch (error) {
            this.showError('Search failed: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    displaySearchResults(results, query) {
        this.searchQuery.textContent = `"${query}"`;
        this.searchResultsList.innerHTML = '';

        if (results.length === 0) {
            this.searchResultsList.innerHTML = '<div class="text-muted text-center mt-2">No results found</div>';
        } else {
            results.forEach(result => {
                const item = this.createSearchResultItem(result);
                this.searchResultsList.appendChild(item);
            });
        }

        this.showSearchResults();
    }

    createSearchResultItem(result) {
        const item = document.createElement('div');
        item.className = 'search-result-item';
        
        const path = document.createElement('div');
        path.className = 'search-result-path';
        
        // Color code different match types
        const typeColor = {
            'path': '#3498db',
            'key': '#e74c3c', 
            'content': '#27ae60'
        }[result.match_type] || '#7f8c8d';
        
        path.innerHTML = `${result.path} <span class="search-result-type" style="background-color: ${typeColor}">${result.match_type}</span>`;
        
        const preview = document.createElement('div');
        preview.className = 'search-result-preview';
        preview.textContent = result.preview;
        
        item.appendChild(path);
        item.appendChild(preview);
        
        item.addEventListener('click', () => this.loadFileData(result.path));
        
        return item;
    }

    toggleRawView(isRaw) {
        this.isRawView = isRaw;
        
        this.rawViewBtn.classList.toggle('active', isRaw);
        this.prettyViewBtn.classList.toggle('active', !isRaw);
        
        if (this.currentData) {
            this.renderDataContent(this.currentData.data);
        }
    }

    async copyData() {
        if (!this.currentData) return;
        
        try {
            await navigator.clipboard.writeText(JSON.stringify(this.currentData.data, null, 2));
            // Could show a success toast here
        } catch (error) {
            this.showError('Failed to copy data: ' + error.message);
        }
    }

    downloadData() {
        if (!this.currentData) return;
        
        const dataStr = JSON.stringify(this.currentData.data, null, 2);
        const blob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `${this.currentPath.replace(/\//g, '_')}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    expandAll() {
        this.collectAllPaths().forEach(path => {
            this.expandedNodes.add(path);
        });
        this.renderTree();
    }

    collapseAll() {
        this.expandedNodes.clear();
        this.renderTree();
    }

    collectAllPaths() {
        const paths = [];
        
        const traverse = (items) => {
            items.forEach(item => {
                if (item.type === 'folder') {
                    paths.push(item.path);
                    if (item.children) {
                        traverse(item.children);
                    }
                }
            });
        };
        
        if (this.treeData) {
            traverse(this.treeData);
        }
        
        return paths;
    }

    async refreshTree() {
        await this.loadInitialTree();
    }

    showWelcomeScreen() {
        this.welcomeScreen.style.display = 'flex';
        this.contentDisplay.style.display = 'none';
        this.searchResults.style.display = 'none';
        this.updateBreadcrumb('');
    }

    showContentDisplay() {
        this.welcomeScreen.style.display = 'none';
        this.contentDisplay.style.display = 'flex';
        this.searchResults.style.display = 'none';
    }

    showSearchResults() {
        this.welcomeScreen.style.display = 'none';
        this.contentDisplay.style.display = 'none';
        this.searchResults.style.display = 'block';
    }

    hideSearchResults() {
        if (this.currentData) {
            this.showContentDisplay();
        } else {
            this.showWelcomeScreen();
        }
    }

    showLoading() {
        this.loadingOverlay.style.display = 'flex';
    }

    hideLoading() {
        this.loadingOverlay.style.display = 'none';
    }

    showError(message) {
        this.errorMessage.textContent = message;
        this.errorModal.style.display = 'flex';
    }

    hideError() {
        this.errorModal.style.display = 'none';
    }

    initializeSidebarResizing() {
        let isResizing = false;
        let startX = 0;
        let startWidth = 0;

        this.sidebarResizer.addEventListener('mousedown', (e) => {
            isResizing = true;
            startX = e.clientX;
            startWidth = parseInt(document.defaultView.getComputedStyle(this.sidebar).width, 10);
            this.sidebarResizer.classList.add('resizing');
            
            document.addEventListener('mousemove', this.handleResize);
            document.addEventListener('mouseup', this.stopResize);
            
            // Prevent text selection during resize
            e.preventDefault();
        });

        this.handleResize = (e) => {
            if (!isResizing) return;
            
            const newWidth = startWidth + e.clientX - startX;
            const minWidth = 280;
            const maxWidth = window.innerWidth * 0.6;
            
            if (newWidth >= minWidth && newWidth <= maxWidth) {
                this.sidebar.style.width = newWidth + 'px';
                // Update CSS variable for header alignment
                document.documentElement.style.setProperty('--sidebar-width', newWidth + 'px');
            }
        };

        this.stopResize = () => {
            isResizing = false;
            this.sidebarResizer.classList.remove('resizing');
            document.removeEventListener('mousemove', this.handleResize);
            document.removeEventListener('mouseup', this.stopResize);
        };
    }

    formatEncryptedValue(encryptedValue, basePath) {
        const valueId = 'encrypted_' + Math.random().toString(36).substr(2, 9);
        
        return `
            <div class="decrypt-container">
                <span class="json-string encrypted" id="${valueId}">"${this.escapeHtml(encryptedValue)}"</span>
                <button class="decrypt-btn" onclick="routerBrowser.decryptValue('${basePath}', '${valueId}')">
                    <i class="fas fa-unlock"></i>
                    Decrypt
                </button>
            </div>
        `;
    }

    async decryptValue(path, valueElementId) {
        const button = event.target.closest('.decrypt-btn');
        const valueElement = document.getElementById(valueElementId);
        
        if (!button || !valueElement) return;
        
        // Show loading state
        button.classList.add('loading');
        button.disabled = true;
        
        try {
            const response = await this.apiCall('/api/decrypt', { path });
            
            console.log('Decrypt response:', response);
            
            if (response.decrypted_value !== undefined) {
                let displayValue;
                
                // Handle different types of decrypted values
                if (typeof response.decrypted_value === 'string') {
                    displayValue = response.decrypted_value;
                } else if (typeof response.decrypted_value === 'object') {
                    // If it's an object, convert to JSON string
                    displayValue = JSON.stringify(response.decrypted_value);
                } else {
                    // For other types, convert to string
                    displayValue = String(response.decrypted_value);
                }
                
                // Update the display with decrypted value
                valueElement.innerHTML = `"${this.escapeHtml(displayValue)}"`;
                valueElement.classList.remove('encrypted');
                
                // Remove the decrypt button since value is now decrypted
                button.remove();
                
                // Show success feedback
                this.showToast('Value decrypted successfully', 'success');
            } else {
                throw new Error('No decrypted value returned');
            }
        } catch (error) {
            console.error('Decryption failed:', error);
            this.showError('Failed to decrypt value: ' + error.message);
        } finally {
            button.classList.remove('loading');
            button.disabled = false;
        }
    }

    showToast(message, type = 'info') {
        // Create toast element if it doesn't exist
        let toast = document.getElementById('toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'toast';
            toast.style.cssText = `
                position: fixed;
                top: 80px;
                right: 20px;
                padding: 12px 20px;
                border-radius: 4px;
                color: white;
                font-weight: 500;
                z-index: 9999;
                opacity: 0;
                transition: opacity 0.3s ease;
                pointer-events: none;
                max-width: 300px;
            `;
            document.body.appendChild(toast);
        }
        
        // Set toast style based on type
        const colors = {
            success: '#27ae60',
            error: '#e74c3c',
            info: '#3498db',
            warning: '#f39c12'
        };
        
        toast.style.backgroundColor = colors[type] || colors.info;
        toast.textContent = message;
        toast.style.opacity = '1';
        toast.style.display = 'block';
        
        // Auto hide after 3 seconds
        setTimeout(() => {
            toast.style.opacity = '0';
            // Completely remove the element after fade out to prevent interference
            setTimeout(() => {
                if (toast && toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300); // Wait for fade transition to complete
        }, 3000);
    }

    // Dark mode functionality
    toggleDarkMode() {
        const isDarkMode = document.body.getAttribute('data-theme') === 'dark';
        const newTheme = isDarkMode ? 'light' : 'dark';
        
        document.body.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        
        // Update button icon
        const icon = this.darkModeToggle.querySelector('i');
        if (newTheme === 'dark') {
            icon.className = 'fas fa-sun';
            this.darkModeToggle.title = 'Switch to Light Mode';
        } else {
            icon.className = 'fas fa-moon';
            this.darkModeToggle.title = 'Switch to Dark Mode';
        }
    }

    initializeDarkMode() {
        // Check for saved theme preference or default to light mode
        const savedTheme = localStorage.getItem('theme') || 'light';
        document.body.setAttribute('data-theme', savedTheme);
        
        // Update button icon based on initial theme
        const icon = this.darkModeToggle.querySelector('i');
        if (savedTheme === 'dark') {
            icon.className = 'fas fa-sun';
            this.darkModeToggle.title = 'Switch to Light Mode';
        } else {
            icon.className = 'fas fa-moon';
            this.darkModeToggle.title = 'Switch to Dark Mode';
        }
    }

    // Legend functionality
    toggleLegend() {
        if (this.floatingLegend.style.display === 'none' || !this.floatingLegend.style.display) {
            this.showLegend();
        } else {
            this.hideLegend();
        }
    }

    showLegend() {
        this.floatingLegend.style.display = 'block';
        this.legendToggleBtn.classList.add('active');
        
        // Add a subtle animation
        this.floatingLegend.style.opacity = '0';
        this.floatingLegend.style.transform = 'translateY(-10px)';
        
        setTimeout(() => {
            this.floatingLegend.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
            this.floatingLegend.style.opacity = '1';
            this.floatingLegend.style.transform = 'translateY(0)';
        }, 10);
    }

    hideLegend() {
        this.floatingLegend.style.opacity = '0';
        this.floatingLegend.style.transform = 'translateY(-10px)';
        this.legendToggleBtn.classList.remove('active');
        
        setTimeout(() => {
            this.floatingLegend.style.display = 'none';
            this.floatingLegend.style.transition = '';
        }, 200);
    }
}

// Initialize the application when the DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.routerBrowser = new RouterDataBrowser();
});