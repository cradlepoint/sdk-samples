// Web App Template JavaScript - v1.1
class WebAppTemplate {
    constructor() {
        this.currentElement = 'homepage';
        this.allElements = [];
        this.init();
    }

    init() {
        this.bindEvents();
        this.initDarkMode();
        this.initTabs();
        this.collectAllElements();
        this.initSlider();
        this.initTooltips();
        this.initSearchClear();
        this.initStatusControls();
        this.initUploadButton();
        this.initFormExamples();
        this.initButtonExamples();
        
        // Show homepage by default
        this.showElement('home-section');
        
        // Homepage link click handler
        const homepageLink = document.getElementById('homepage-link');
        if (homepageLink) {
            homepageLink.addEventListener('click', (e) => {
                e.preventDefault();
                this.showElement('home-section');
                this.collapseAllNavItems();
                document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
                document.querySelectorAll('.nav-sub-item').forEach(nav => nav.classList.remove('active'));
            });
        }
    }

    initStatusControls() {
        const controlMap = {
            background: {
                className: 'status-controls-hide-background',
                toggleWhenUnchecked: true
            },
            border: {
                className: 'status-controls-hide-border',
                toggleWhenUnchecked: true
            },
            main: {
                className: 'status-controls-hide-main',
                toggleWhenUnchecked: true
            },
            description: {
                className: 'status-controls-hide-description',
                toggleWhenUnchecked: true
            },
            'color-main': {
                className: 'status-controls-disable-color',
                toggleWhenUnchecked: true
            },
            'color-description': {
                className: 'status-controls-color-description',
                toggleWhenUnchecked: false
            }
        };

        const statusSections = document.querySelectorAll('.element-example.status-control');

        statusSections.forEach(section => {
            const checkboxes = section.querySelectorAll('.status-toggle-controls input[type="checkbox"][data-control]');

            checkboxes.forEach(checkbox => {
                const controlKey = checkbox.dataset.control;
                const mapping = controlMap[controlKey];

                if (!mapping) {
                    return;
                }

                const updateClass = () => {
                    const shouldApply = mapping.toggleWhenUnchecked ? !checkbox.checked : checkbox.checked;
                    section.classList.toggle(mapping.className, shouldApply);
                };

                checkbox.addEventListener('change', () => {
                    updateClass();
                    this.updateStatusCodeBlock(section);
                });
                updateClass();
            });

            this.initializeStatusIndicatorSelection(section);
        });
    }

    initializeStatusIndicatorSelection(section) {
        if (!section) {
            return;
        }

        const indicators = section.querySelectorAll('.status-indicator');
        const codeBlock = section.querySelector('.code-block');

        if (!indicators.length || !codeBlock) {
            return;
        }

        indicators.forEach((indicator, index) => {
            if (!indicator.dataset.indicatorId) {
                indicator.dataset.indicatorId = `${section.id || 'status'}-${index}`;
            }
            indicator.setAttribute('tabindex', '0');
            indicator.setAttribute('role', 'button');

            indicator.addEventListener('click', () => {
                this.selectStatusIndicator(section, indicator);
            });

            indicator.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    this.selectStatusIndicator(section, indicator);
                }
            });
        });

        this.clearStatusCodeBlock(section);

        const initiallySelected = section.querySelector('.status-indicator.status-indicator-selected');
        if (initiallySelected) {
            this.selectStatusIndicator(section, initiallySelected);
        }
    }

    selectStatusIndicator(section, indicator) {
        if (!section || !indicator) {
            return;
        }

        const isAlreadySelected = indicator.classList.contains('status-indicator-selected');
        if (isAlreadySelected) {
            indicator.classList.remove('status-indicator-selected');
            delete section.dataset.selectedIndicatorId;
            this.clearStatusCodeBlock(section);
            return;
        }

        const indicators = section.querySelectorAll('.status-indicator');
        indicators.forEach(item => item.classList.remove('status-indicator-selected'));

        indicator.classList.add('status-indicator-selected');
        section.dataset.selectedIndicatorId = indicator.dataset.indicatorId || '';

        this.updateStatusCodeBlock(section, indicator);
    }

    updateStatusCodeBlock(section, indicatorOverride = null) {
        if (!section) {
            return;
        }

        const codeBlock = section.querySelector('.code-block');
        if (!codeBlock) {
            return;
        }

        const indicator = indicatorOverride || section.querySelector('.status-indicator.status-indicator-selected');
        if (!indicator) {
            this.clearStatusCodeBlock(section);
            return;
        }

        const options = this.getStatusControlOptions(section);
        const snippet = this.generateStatusIndicatorMarkup(indicator, options);
        codeBlock.textContent = snippet;
    }

    getStatusControlOptions(section) {
        const defaults = {
            background: true,
            border: true,
            main: true,
            description: true,
            'color-main': true,
            'color-description': false
        };

        if (!section) {
            return defaults;
        }

        const checkboxes = section.querySelectorAll('.status-toggle-controls input[type="checkbox"][data-control]');
        checkboxes.forEach(checkbox => {
            const key = checkbox.dataset.control;
            if (!key) {
                return;
            }
            defaults[key] = checkbox.checked;
        });

        return defaults;
    }

    generateStatusIndicatorMarkup(indicator, options) {
        const clone = indicator.cloneNode(true);
        clone.classList.remove('status-indicator-selected');
        clone.removeAttribute('tabindex');
        if (clone.getAttribute('role') === 'button') {
            clone.removeAttribute('role');
        }
        clone.removeAttribute('data-indicator-id');

        if (!options.background) {
            clone.classList.add('status-option-no-background');
        }

        if (!options.border) {
            clone.classList.add('status-option-no-border');
        }

        if (!options['color-main']) {
            clone.classList.add('status-option-neutral-main');
        }

        if (options['color-description']) {
            clone.classList.add('status-option-color-description');
        }

        if (!options.main) {
            const mainText = clone.querySelectorAll('.status-indicator-text strong');
            mainText.forEach(node => node.remove());
        }

        if (!options.description) {
            const descriptions = clone.querySelectorAll('.status-indicator-text span');
            descriptions.forEach(node => node.remove());
        }

        const textWrapper = clone.querySelector('.status-indicator-text');
        if (textWrapper) {
            const hasContent = Array.from(textWrapper.childNodes).some(node => {
                if (node.nodeType === Node.ELEMENT_NODE) {
                    return true;
                }
                if (node.nodeType === Node.TEXT_NODE) {
                    return node.textContent.trim().length > 0;
                }
                return false;
            });

            if (!hasContent) {
                textWrapper.remove();
            }
        }

        const rawHTML = clone.outerHTML;
        return this.formatCodeSnippet(rawHTML);
    }

    formatCodeSnippet(html) {
        if (!html) {
            return '';
        }

        const withBreaks = html.replace(/></g, '>\n<');
        const lines = withBreaks.split('\n').map(line => line.trim()).filter(Boolean);

        let indentLevel = 0;
        const formatted = lines.map(line => {
            if (line.match(/^<\/.+>/)) {
                indentLevel = Math.max(indentLevel - 1, 0);
            }

            const formattedLine = `${'    '.repeat(indentLevel)}${line}`;

            const isOpeningTag = /^<[^\/!][^>]*>$/.test(line) && !/\/>$/.test(line);
            const isSelfContained = /^<[^\/!][^>]*>.*<\/[^>]+>$/.test(line);

            if (isOpeningTag && !isSelfContained) {
                indentLevel += 1;
            }

            return formattedLine;
        });

        return formatted.join('\n');
    }

    clearStatusCodeBlock(section) {
        if (!section) {
            return;
        }
        const codeBlock = section.querySelector('.code-block');
        if (codeBlock) {
            codeBlock.textContent = this.getEmptyStatusSnippet();
        }
    }

    getEmptyStatusSnippet() {
        return [
            '<div class="status-indicator">',
            '    <span class="status-indicator-icon">',
            '        <i class="fas"></i>',
            '    </span>',
            '    <div class="status-indicator-text"></div>',
            '</div>'
        ].join('\n');
    }

    initUploadButton() {
        const uploadTrigger = document.getElementById('upload-button-trigger');
        const uploadInput = document.getElementById('upload-input');
        const uploadStatus = document.getElementById('upload-status');

        if (!uploadTrigger || !uploadInput || !uploadStatus) {
            return;
        }

        const resetStatus = () => {
            uploadStatus.textContent = 'No file selected';
            uploadStatus.classList.remove('has-files');
        };

        const updateStatus = () => {
            if (!uploadInput.files || uploadInput.files.length === 0) {
                resetStatus();
                return;
            }

            const files = Array.from(uploadInput.files);
            const names = files.map(file => file.name);
            const prefix = files.length === 1 ? 'Selected file:' : `Selected files (${files.length}):`;

            uploadStatus.textContent = `${prefix} ${names.join(', ')}`;
            uploadStatus.classList.add('has-files');
        };

        uploadTrigger.addEventListener('click', () => {
            uploadInput.click();
        });

        uploadInput.addEventListener('change', () => {
            updateStatus();
        });

        resetStatus();
    }

    initFormExamples() {
        this.initToggleExample();
        this.initCheckboxExample();
    }

    initButtonExamples() {
        this.initButtonBuilder();
    }

    initButtonBuilder() {
        const tile = document.getElementById('button-builder');
        if (!tile) {
            return;
        }

        const colorSelect = document.getElementById('button-builder-color');
        const colorSelector = document.getElementById('button-builder-color-selector');
        const iconSelect = document.getElementById('button-builder-icon');
        const preview = document.getElementById('button-builder-preview');
        const labelInput = document.getElementById('button-builder-label');
        const tooltipTextInput = document.getElementById('button-builder-tooltip-text');
        const notificationTextInput = document.getElementById('button-builder-notification-text');
        // Try multiple ways to find the code block
        // First, try direct querySelector (works even if element is hidden)
        let codeBlock = tile.querySelector('code.code-block');
        if (!codeBlock) {
            codeBlock = tile.querySelector('.code-block');
        }
        if (!codeBlock) {
            // Try getElementsByClassName (works even if element is hidden)
            const codeBlocks = tile.getElementsByClassName('code-block');
            if (codeBlocks.length > 0) {
                codeBlock = codeBlocks[0];
            }
        }
        if (!codeBlock) {
            // Try querySelectorAll and check all matches
            const allMatches = tile.querySelectorAll('code');
            for (let i = 0; i < allMatches.length; i++) {
                if (allMatches[i].classList.contains('code-block')) {
                    codeBlock = allMatches[i];
                    break;
                }
            }
        }
        if (!codeBlock) {
            // Last resort: search document-wide for code block within button-builder
            const docMatches = document.querySelectorAll('#button-builder code.code-block');
            if (docMatches.length > 0) {
                codeBlock = docMatches[0];
            }
        }
        
        const controlInputs = Array.from(tile.querySelectorAll('[data-button-control]'));
        const gradientSlider = tile.querySelector('[data-gradient-control]');
        const gradientInput = document.getElementById('button-builder-gradient');
        const gradientValue = document.getElementById('button-builder-gradient-value');
        const textToggle = tile.querySelector('input[data-button-control="text"]');
        const animationSlider = tile.querySelector('[data-animation-control]');
        const animationInput = document.getElementById('button-builder-hover');
        const animationValue = document.getElementById('button-builder-hover-value');

        if (!colorSelect || !iconSelect || !preview) {
            console.error('Button builder: Required elements not found', {
                colorSelect: !!colorSelect,
                iconSelect: !!iconSelect,
                preview: !!preview,
                codeBlock: !!codeBlock
            });
            return;
        }
        
        // Create code block if it doesn't exist
        if (!codeBlock) {
            codeBlock = document.createElement('code');
            codeBlock.className = 'code-block';
            // Insert it after the button preview
            const previewContainer = preview.closest('.button-preview');
            if (previewContainer && previewContainer.parentNode) {
                previewContainer.parentNode.appendChild(codeBlock);
            } else {
                tile.appendChild(codeBlock);
            }
        }

        const iconOptions = {
            none: { icon: '', label: 'Primary Button' },
            start: { icon: 'fas fa-play', label: 'Start' },
            stop: { icon: 'fas fa-stop', label: 'Stop' },
            pause: { icon: 'fas fa-pause', label: 'Pause' },
            success: { icon: 'fas fa-check', label: 'Success' },
            warning: { icon: 'fas fa-exclamation-triangle', label: 'Warning' },
            failed: { icon: 'fas fa-times', label: 'Failed' },
            upload: { icon: 'fas fa-upload', label: 'Upload' },
            download: { icon: 'fas fa-download', label: 'Download' },
            restart: { icon: 'fas fa-undo', label: 'Restart' },
            light: { icon: 'fas fa-sun', label: 'Light Mode' },
            dark: { icon: 'fas fa-moon', label: 'Dark Mode' }
        };

        const getControlState = () => {
            const defaults = {
                background: true,
                border: true,
                'color-text': false,
                'color-border': false,
                'color-animation': false,
                'hover-animation': true,
                text: true,
                'gradient-depth': gradientInput ? gradientInput.value : 50,
                'hover-depth': animationInput ? animationInput.value : 50,
                'animation-speed': 50,
                'click-animation': 'none',
                'tooltip': 'none',
                'color-tooltip-text': false,
                'tooltip-delay': 500,
                'notification': 'none',
                'notification-position': 10
            };

            controlInputs.forEach(input => {
                const key = input.dataset.buttonControl;
                if (!key) {
                    return;
                }
                if (input.type === 'checkbox') {
                    defaults[key] = input.checked;
                } else {
                    defaults[key] = input.value;
                }
            });
            
            // Handle click-animation separately (mutually exclusive group)
            const clickAnimationInputs = controlInputs.filter(input => 
                input.dataset.buttonControl === 'click-animation' && 
                input.dataset.group === 'click-animations'
            );
            if (clickAnimationInputs.length > 0) {
                const checkedAnimation = clickAnimationInputs.find(input => input.checked);
                defaults['click-animation'] = checkedAnimation ? (checkedAnimation.value || 'none') : 'none';
            }
            
            // Handle tooltip separately (mutually exclusive group)
            const tooltipInputs = controlInputs.filter(input => 
                input.dataset.buttonControl === 'tooltip' && 
                input.dataset.group === 'tooltip-placement'
            );
            if (tooltipInputs.length > 0) {
                const checkedTooltip = tooltipInputs.find(input => input.checked);
                defaults['tooltip'] = checkedTooltip ? (checkedTooltip.value || 'none') : 'none';
            }
            
            // Handle notification separately (mutually exclusive group)
            const notificationInputs = controlInputs.filter(input => 
                input.dataset.buttonControl === 'notification' && 
                input.dataset.group === 'notification-type'
            );
            if (notificationInputs.length > 0) {
                const checkedNotification = notificationInputs.find(input => input.checked);
                defaults['notification'] = checkedNotification ? (checkedNotification.value || 'none') : 'none';
            }

            return defaults;
        };

        const enforceIconRequirement = () => {
            const textControl = textToggle;
            const textEnabled = textControl ? textControl.checked : true;
            const noneOption = iconSelect.querySelector('option[value="none"]');

            if (!textEnabled) {
                if (noneOption) {
                    noneOption.disabled = true;
                }
                if (iconSelect.value === 'none') {
                    const fallback = Array.from(iconSelect.options).find(opt => opt.value !== 'none');
                    if (fallback) {
                        iconSelect.value = fallback.value;
                    }
                }
            } else if (noneOption) {
                noneOption.disabled = false;
            }

            if (textControl) {
                const shouldDisableTextToggle = iconSelect.value === 'none';
                const textLabel = textControl.closest('.status-toggle-option');

                textControl.disabled = shouldDisableTextToggle;
                if (shouldDisableTextToggle) {
                    textControl.checked = true;
                }

                if (textLabel) {
                    textLabel.classList.toggle('disabled', shouldDisableTextToggle);
                }
            }
        };

        // Store click animation handler reference for proper cleanup
        let clickAnimationHandler = null;

        const rerender = (changedInput = null) => {
            try {
                this.handleButtonControlGroup(controlInputs, changedInput);
                // Only enforce icon requirement if it's not the icon select that changed
                if (changedInput !== iconSelect) {
                    enforceIconRequirement();
                }
                render();
            } catch (error) {
                console.error('Error in button builder rerender:', error);
            }
        };

        const render = () => {
            try {
                if (!preview) {
                    console.error('Button builder: preview not found', { preview });
                    return;
                }
                
                // Ensure code block exists (it should from initialization, but double-check)
                if (!codeBlock) {
                    codeBlock = tile.querySelector('code.code-block') || tile.querySelector('.code-block');
                    if (!codeBlock) {
                        codeBlock = document.createElement('code');
                        codeBlock.className = 'code-block';
                        const previewContainer = preview.closest('.button-preview');
                        if (previewContainer && previewContainer.parentNode) {
                            previewContainer.parentNode.appendChild(codeBlock);
                        } else {
                            tile.appendChild(codeBlock);
                        }
                    }
                }
                
                const state = getControlState();
                const showBackground = state.background !== false;
                const showBorder = state.border !== false;
                const showText = state.text !== false;
                const colorizeText = showText && state['color-text'];
                const colorizeBorder = showBorder && state['color-border'];
                const colorizeAnimation = state['color-animation'];
                const hoverDepthRaw = parseInt(state['hover-depth'], 10);
                const hoverDepth = Number.isNaN(hoverDepthRaw) ? 50 : Math.min(100, Math.max(0, hoverDepthRaw));
                const animationSpeedRaw = parseInt(state['animation-speed'] || 50, 10);
                const animationSpeed = Number.isNaN(animationSpeedRaw) ? 50 : Math.min(100, Math.max(0, animationSpeedRaw));

                // Read label value first to capture current input value
                const customLabel = labelInput && labelInput.value.trim().length ? labelInput.value.trim() : '';
                const customTooltipText = tooltipTextInput && tooltipTextInput.value.trim().length ? tooltipTextInput.value.trim() : '';
                const customNotificationText = notificationTextInput && notificationTextInput.value.trim().length ? notificationTextInput.value.trim() : '';

                if (gradientValue && gradientInput) {
                    gradientValue.textContent = `${gradientInput.value}%`;
                }

                // Enforce icon requirement first (may modify iconSelect.value programmatically)
                enforceIconRequirement();
                
                // Read icon value after enforcement to get the final value
                const iconValue = iconSelect.value;
                const iconChoice = iconOptions[iconValue] || iconOptions.none;
                const showIcon = iconValue !== 'none' && !!iconChoice.icon;
                const colorizeIcon = showIcon && state['color-icon'];
                const buttonLabel = customLabel || iconChoice.label || 'Primary Button';
                const tooltipText = customTooltipText || buttonLabel;
                let buttonClasses = this.getButtonClassByColor(colorSelect.value).split(' ').filter(Boolean);
                const gradientDetails = { value: null, scalar: null };

                if (!showBackground) {
                    buttonClasses.push('button-option-no-background');
                }
                if (showBorder) {
                    buttonClasses.push('button-option-border-visible');
                } else {
                    buttonClasses.push('button-option-no-border');
                }
                if (colorizeText) {
                    buttonClasses.push('button-option-color-text');
                }
                if (colorizeBorder) {
                    buttonClasses.push('button-option-color-border');
                }
                if (colorizeIcon) {
                    buttonClasses.push('button-option-color-icon');
                }
                if (!showText) {
                    buttonClasses.push('btn-icon-only');
                }

                if (gradientSlider && gradientInput) {
                    const parsedDepth = parseInt(state['gradient-depth'], 10);
                    const clampedDepth = Number.isNaN(parsedDepth) ? 50 : Math.min(100, Math.max(0, parsedDepth));
                    gradientDetails.value = clampedDepth;
                    gradientInput.value = clampedDepth;
                    if (gradientValue) {
                        gradientValue.textContent = `${clampedDepth}%`;
                    }

                    if (showBackground) {
                        // Increased range: from 0.05 to 0.98 for even more pronounced gradient effect
                        const minDepth = 0.05;
                        const maxDepth = 0.98;
                        const depthScalar = minDepth + (clampedDepth / 100) * (maxDepth - minDepth);
                        if (clampedDepth === 50) {
                            preview.style.removeProperty('--gradient-depth');
                            gradientDetails.scalar = null;
                        } else {
                            gradientDetails.scalar = depthScalar;
                            preview.style.setProperty('--gradient-depth', depthScalar.toFixed(2));
                        }
                        gradientSlider.classList.remove('disabled');
                        gradientInput.disabled = false;
                    } else {
                        preview.style.removeProperty('--gradient-depth');
                        gradientDetails.scalar = null;
                        gradientSlider.classList.add('disabled');
                        gradientInput.disabled = true;
                        gradientInput.value = 50;
                        if (gradientValue) {
                            gradientValue.textContent = '50%';
                        }
                    }
                } else {
                    preview.style.removeProperty('--gradient-depth');
                }

                const hoverAnimationEnabled = state['hover-animation'];
                let hoverSweepClass = '';
                if (hoverAnimationEnabled && showBackground && colorizeAnimation) {
                    hoverSweepClass = 'button-option-color-animation';
                } else if (hoverAnimationEnabled && showBackground) {
                    hoverSweepClass = 'button-hover-sweep-only';
                } else if (hoverAnimationEnabled && !showBackground && colorizeAnimation) {
                    hoverSweepClass = 'button-option-color-animation';
                } else if (hoverAnimationEnabled) {
                    hoverSweepClass = 'button-hover-sweep-only';
                }

                // Remove any existing hover animation classes first
                const hoverAnimationClasses = ['button-option-color-animation', 'button-hover-sweep-only'];
                buttonClasses = buttonClasses.filter(cls => !hoverAnimationClasses.includes(cls));

                // Add the appropriate hover animation class if enabled
                if (hoverAnimationEnabled && hoverSweepClass) {
                    buttonClasses.push(hoverSweepClass);
                } else {
                    preview.style.removeProperty('--hover-sweep-strength');
                }

                if (animationSlider && animationInput) {
                    const hoverScalar = 0.35 + (hoverDepth / 100) * 0.65;
                    if (hoverAnimationEnabled) {
                        animationSlider.classList.remove('disabled');
                        animationInput.disabled = false;
                        animationInput.value = hoverDepth;
                        if (animationValue) {
                            animationValue.textContent = `${hoverDepth}%`;
                        }
                        preview.style.setProperty('--hover-sweep-strength', hoverScalar.toFixed(2));
                        
                        // Set animation speed (inverse: lower value = faster animation)
                        // Speed range: 0.3s (fast) to 1.2s (slow), mapped from 0-100 slider
                        const speedSeconds = 0.3 + ((100 - animationSpeed) / 100) * 0.9;
                        preview.style.setProperty('--animation-speed', `${speedSeconds}s`);
                    } else {
                        animationSlider.classList.add('disabled');
                        animationInput.disabled = true;
                        animationInput.value = 50;
                        if (animationValue) {
                            animationValue.textContent = '50%';
                        }
                        preview.style.removeProperty('--hover-sweep-strength');
                        preview.style.removeProperty('--animation-speed');
                    }
                }
                
                // Handle animation speed slider
                const animationSpeedSlider = tile.querySelector('[data-animation-speed-control]');
                const animationSpeedInput = document.getElementById('button-builder-animation-speed');
                const animationSpeedValue = document.getElementById('button-builder-animation-speed-value');
                if (animationSpeedSlider && animationSpeedInput) {
                    if (hoverAnimationEnabled) {
                        animationSpeedSlider.classList.remove('disabled');
                        animationSpeedInput.disabled = false;
                        animationSpeedInput.value = animationSpeed;
                        if (animationSpeedValue) {
                            animationSpeedValue.textContent = `${animationSpeed}%`;
                        }
                    } else {
                        animationSpeedSlider.classList.add('disabled');
                        animationSpeedInput.disabled = true;
                        animationSpeedInput.value = 50;
                        if (animationSpeedValue) {
                            animationSpeedValue.textContent = '50%';
                        }
                    }
                }

                // Add click animation class
                const clickAnimation = state['click-animation'] || 'none';
                const clickAnimationClasses = [
                    'button-click-scale',
                    'button-click-bounce',
                    'button-click-shake'
                ];
                // Remove any existing click animation classes
                buttonClasses = buttonClasses.filter(c => !clickAnimationClasses.includes(c));
                // Add the selected click animation class (if not 'none')
                if (clickAnimation && clickAnimation !== 'none') {
                    buttonClasses.push(`button-click-${clickAnimation}`);
                }
                
                // Handle tooltip placement
                const tooltipPlacement = state['tooltip'] || 'none';
                const colorizeTooltipText = state['color-tooltip-text'];
                const tooltipDelayRaw = parseInt(state['tooltip-delay'] || 0, 10);
                const tooltipDelay = Number.isNaN(tooltipDelayRaw) ? 0 : Math.min(1000, Math.max(0, tooltipDelayRaw));
                
                // Handle notification type
                const notificationType = state['notification'] || 'none';
                const notificationText = customNotificationText || buttonLabel;
                const notificationPositionRaw = parseInt(state['notification-position'] || 10, 10);
                const notificationPosition = Number.isNaN(notificationPositionRaw) ? 10 : Math.min(90, Math.max(10, notificationPositionRaw));
                
                // Remove any existing tooltip elements and event listeners first
                const existingTooltips = preview.querySelectorAll('.tooltip');
                existingTooltips.forEach(tooltip => tooltip.remove());
                // Also check button-preview container for tooltips
                const buttonPreview = preview.closest('.button-preview');
                if (buttonPreview) {
                    const containerTooltips = buttonPreview.querySelectorAll('.tooltip');
                    containerTooltips.forEach(tooltip => tooltip.remove());
                }
                
                // Remove old event listeners if they exist
                if (preview._tooltipMouseEnter) {
                    preview.removeEventListener('mouseenter', preview._tooltipMouseEnter);
                    preview._tooltipMouseEnter = null;
                }
                if (preview._tooltipMouseLeave) {
                    preview.removeEventListener('mouseleave', preview._tooltipMouseLeave);
                    preview._tooltipMouseLeave = null;
                }
                
                if (tooltipPlacement && tooltipPlacement !== 'none') {
                    // Add tooltip-trigger class to buttonClasses
                    if (!buttonClasses.includes('tooltip-trigger')) {
                        buttonClasses.push('tooltip-trigger');
                    }
                    preview.setAttribute('data-tooltip', tooltipText);
                    preview.setAttribute('data-position', tooltipPlacement); // Use data-position to match examples
                    preview.setAttribute('data-tooltip-delay', tooltipDelay.toString());
                    if (colorizeTooltipText) {
                        preview.setAttribute('data-tooltip-colorized', 'true');
                    } else {
                        preview.removeAttribute('data-tooltip-colorized');
                    }
                    // Initialize tooltip for this button (after setting attributes)
                    // We'll initialize after className is set
                } else {
                    // Remove tooltip-trigger class from buttonClasses
                    buttonClasses = buttonClasses.filter(c => c !== 'tooltip-trigger');
                    preview.removeAttribute('data-tooltip');
                    preview.removeAttribute('data-position');
                    preview.removeAttribute('data-tooltip-placement');
                    preview.removeAttribute('data-tooltip-colorized');
                    preview.removeAttribute('data-tooltip-delay');
                }
                
                // Handle tooltip delay slider
                const tooltipDelaySlider = tile.querySelector('[data-tooltip-delay-control]');
                const tooltipDelayInput = document.getElementById('button-builder-tooltip-delay');
                const tooltipDelayValue = document.getElementById('button-builder-tooltip-delay-value');
                if (tooltipDelaySlider && tooltipDelayInput) {
                    if (tooltipPlacement && tooltipPlacement !== 'none') {
                        tooltipDelaySlider.classList.remove('disabled');
                        tooltipDelayInput.disabled = false;
                        tooltipDelayInput.value = tooltipDelay;
                        if (tooltipDelayValue) {
                            tooltipDelayValue.textContent = `${tooltipDelay}ms`;
                        }
                    } else {
                        tooltipDelaySlider.classList.add('disabled');
                        tooltipDelayInput.disabled = true;
                        tooltipDelayInput.value = 500;
                        if (tooltipDelayValue) {
                            tooltipDelayValue.textContent = '500ms';
                        }
                    }
                }
                
                // Handle notification position slider
                const notificationPositionSlider = tile.querySelector('[data-notification-position-control]');
                const notificationPositionInput = document.getElementById('button-builder-notification-position');
                const notificationPositionValue = document.getElementById('button-builder-notification-position-value');
                if (notificationPositionSlider && notificationPositionInput) {
                    if (notificationType && notificationType !== 'none') {
                        notificationPositionSlider.classList.remove('disabled');
                        notificationPositionInput.disabled = false;
                        notificationPositionInput.value = notificationPosition;
                        if (notificationPositionValue) {
                            notificationPositionValue.textContent = `${notificationPosition}%`;
                        }
                    } else {
                        notificationPositionSlider.classList.add('disabled');
                        notificationPositionInput.disabled = true;
                        notificationPositionInput.value = 10;
                        if (notificationPositionValue) {
                            notificationPositionValue.textContent = '10%';
                        }
                    }
                }

                const finalClass = buttonClasses.join(' ').trim();
                preview.className = finalClass;
                preview.setAttribute('type', 'button');
                
                // Initialize tooltip after className is set and DOM is ready
                if (tooltipPlacement && tooltipPlacement !== 'none') {
                    // Use requestAnimationFrame to ensure DOM is ready and button is positioned
                    requestAnimationFrame(() => {
                        this.initTooltipForElement(preview);
                        // Update tooltip position if it's in container
                        if (preview._tooltipElement && preview._tooltipContainer) {
                            const buttonRect = preview.getBoundingClientRect();
                            const containerRect = preview._tooltipContainer.getBoundingClientRect();
                            const offsetLeft = buttonRect.left - containerRect.left;
                            const offsetTop = buttonRect.top - containerRect.top;
                            const tooltip = preview._tooltipElement;
                            const placement = tooltip.getAttribute('data-position');
                            
                            switch(placement) {
                                case 'top':
                                    tooltip.style.bottom = `${containerRect.height - offsetTop + 8}px`;
                                    tooltip.style.left = `${offsetLeft + buttonRect.width / 2}px`;
                                    break;
                                case 'bottom':
                                    tooltip.style.top = `${offsetTop + buttonRect.height + 8}px`;
                                    tooltip.style.left = `${offsetLeft + buttonRect.width / 2}px`;
                                    break;
                                case 'left':
                                    tooltip.style.right = `${containerRect.width - offsetLeft + 8}px`;
                                    tooltip.style.top = `${offsetTop + buttonRect.height / 2}px`;
                                    break;
                                case 'right':
                                    tooltip.style.left = `${offsetLeft + buttonRect.width + 8}px`;
                                    tooltip.style.top = `${offsetTop + buttonRect.height / 2}px`;
                                    break;
                            }
                        }
                    });
                }
                
                // Set up click animation handler and notification handler
                
                // Remove existing click handler if any
                if (clickAnimationHandler) {
                    preview.removeEventListener('click', clickAnimationHandler);
                    clickAnimationHandler = null;
                }
                
                // Create combined click handler for both animation and notification
                const createClickHandler = () => {
                    return (e) => {
                        // Handle click animation
                        if (clickAnimation && clickAnimation !== 'none') {
                            // Remove animating class to restart animation
                            preview.classList.remove('animating');
                            // Force reflow to restart animation
                            void preview.offsetWidth;
                            // Add animating class to trigger animation
                            preview.classList.add('animating');
                            
                            // Remove animating class after animation completes
                            const animationDuration = {
                                'scale': 200,
                                'bounce': 400,
                                'shake': 400
                            }[clickAnimation] || 400;
                            
                            setTimeout(() => {
                                preview.classList.remove('animating');
                            }, animationDuration);
                        }
                        
                        // Handle notification
                        if (notificationType && notificationType !== 'none' && this.showToast) {
                            this.showToast(notificationText, notificationType, 5000, notificationPosition);
                        }
                    };
                };
                
                if (clickAnimation && clickAnimation !== 'none' || (notificationType && notificationType !== 'none')) {
                    clickAnimationHandler = createClickHandler();
                    preview.addEventListener('click', clickAnimationHandler);
                } else {
                    // Remove animating class if no animation selected
                    preview.classList.remove('animating');
                }

                const ariaLabel = !showText ? buttonLabel : null;
                if (ariaLabel) {
                    preview.setAttribute('aria-label', ariaLabel);
                } else {
                    preview.removeAttribute('aria-label');
                }

                if (showIcon && showText) {
                    preview.innerHTML = `<i class="${iconChoice.icon}"></i> ${buttonLabel}`;
                } else if (showIcon) {
                    preview.innerHTML = `<i class="${iconChoice.icon}"></i>`;
                } else {
                    preview.textContent = buttonLabel;
                }

                const markupAttributes = [`type="button"`, `class="${finalClass}"`];
                if (ariaLabel) {
                    markupAttributes.push(`aria-label="${ariaLabel}"`);
                }
                // Add tooltip attributes if tooltip is enabled
                if (tooltipPlacement && tooltipPlacement !== 'none') {
                    markupAttributes.push(`data-tooltip="${tooltipText}"`);
                    markupAttributes.push(`data-position="${tooltipPlacement}"`); // Use data-position to match examples
                    if (tooltipDelay > 0) {
                        markupAttributes.push(`data-tooltip-delay="${tooltipDelay}"`);
                    }
                    if (colorizeTooltipText) {
                        markupAttributes.push(`data-tooltip-colorized="true"`);
                    }
                }
                // Add notification onclick if notification is enabled
                if (notificationType && notificationType !== 'none') {
                    const escapedText = notificationText.replace(/'/g, "\\'").replace(/"/g, '&quot;');
                    markupAttributes.push(`onclick="window.webAppTemplate.showToast('${escapedText}', '${notificationType}', 5000, ${notificationPosition})"`);
                }
                const styleFragments = [];
                if (gradientDetails.scalar !== null && gradientDetails.value !== 50) {
                    styleFragments.push(`--gradient-depth: ${gradientDetails.scalar.toFixed(2)};`);
                }
                const hoverSweep = preview.style.getPropertyValue('--hover-sweep-strength');
                if (hoverSweep) {
                    styleFragments.push(`--hover-sweep-strength: ${hoverSweep};`);
                }
                const animationSpeedStyle = preview.style.getPropertyValue('--animation-speed');
                if (animationSpeedStyle && hoverAnimationEnabled) {
                    styleFragments.push(`--animation-speed: ${animationSpeedStyle};`);
                }
                if (styleFragments.length) {
                    markupAttributes.push(`style="${styleFragments.join(' ')}"`);
                }

                const markupLines = [`<button ${markupAttributes.join(' ')}>`];
                if (showIcon && showText) {
                    markupLines.push(`    <i class="${iconChoice.icon}"></i> ${buttonLabel}`);
                } else if (showIcon) {
                    markupLines.push(`    <i class="${iconChoice.icon}"></i>`);
                } else {
                    markupLines.push(`    ${buttonLabel}`);
                }
                markupLines.push('</button>');

                const formattedCode = this.formatCodeSnippet(markupLines.join('\n'));
                if (codeBlock) {
                    codeBlock.textContent = formattedCode;
                }
            } catch (error) {
                console.error('Error in button builder render:', error);
            }
        };

        // Handle color selector swatches
        if (colorSelector) {
            const colorSwatches = colorSelector.querySelectorAll('.color-swatch-btn');
            colorSwatches.forEach(swatch => {
                swatch.addEventListener('click', () => {
                    const colorValue = swatch.dataset.color;
                    if (colorSelect) {
                        colorSelect.value = colorValue;
                    }
                    // Update active state
                    colorSwatches.forEach(s => s.classList.remove('active'));
                    swatch.classList.add('active');
                    rerender();
                });
            });
            
            // Set initial active state
            const initialColor = colorSelect ? colorSelect.value : 'primary';
            const initialSwatch = colorSelector.querySelector(`[data-color="${initialColor}"]`);
            if (initialSwatch) {
                initialSwatch.classList.add('active');
            }
        }
        
        // Also listen to select changes (for compatibility)
        if (colorSelect) {
            colorSelect.addEventListener('change', () => {
                // Update active swatch
                if (colorSelector) {
                    const swatches = colorSelector.querySelectorAll('.color-swatch-btn');
                    swatches.forEach(s => s.classList.remove('active'));
                    const activeSwatch = colorSelector.querySelector(`[data-color="${colorSelect.value}"]`);
                    if (activeSwatch) {
                        activeSwatch.classList.add('active');
                    }
                }
                rerender();
            });
        }
        
        iconSelect.addEventListener('change', () => {
            // Force immediate update by calling render directly after enforcing requirements
            enforceIconRequirement();
            rerender(iconSelect);
        });
        if (labelInput) {
            labelInput.addEventListener('input', () => {
                // Force immediate update when label changes
                rerender(labelInput);
            });
            // Also listen to change event for when user finishes typing
            labelInput.addEventListener('change', () => {
                rerender(labelInput);
            });
        }
        
        if (tooltipTextInput) {
            tooltipTextInput.addEventListener('input', () => {
                // Force immediate update when tooltip text changes
                rerender(tooltipTextInput);
            });
            tooltipTextInput.addEventListener('change', () => {
                rerender(tooltipTextInput);
            });
        }
        
        if (notificationTextInput) {
            notificationTextInput.addEventListener('input', () => {
                // Force immediate update when notification text changes
                rerender(notificationTextInput);
            });
            notificationTextInput.addEventListener('change', () => {
                rerender(notificationTextInput);
            });
        }

        const animationSpeedInput = document.getElementById('button-builder-animation-speed');
        const animationSpeedValue = document.getElementById('button-builder-animation-speed-value');
        const tooltipDelayInput = document.getElementById('button-builder-tooltip-delay');
        const tooltipDelayValue = document.getElementById('button-builder-tooltip-delay-value');
        const notificationPositionInput = document.getElementById('button-builder-notification-position');
        const notificationPositionValue = document.getElementById('button-builder-notification-position-value');
        
        controlInputs.forEach(input => {
            const handler = () => {
                if (gradientInput && gradientValue && input === gradientInput) {
                    gradientValue.textContent = `${gradientInput.value}%`;
                }
                if (animationInput && animationValue && input === animationInput) {
                    animationValue.textContent = `${animationInput.value}%`;
                }
                if (animationSpeedInput && animationSpeedValue && input === animationSpeedInput) {
                    animationSpeedValue.textContent = `${animationSpeedInput.value}%`;
                }
                if (tooltipDelayInput && tooltipDelayValue && input === tooltipDelayInput) {
                    tooltipDelayValue.textContent = `${tooltipDelayInput.value}ms`;
                }
                if (notificationPositionInput && notificationPositionValue && input === notificationPositionInput) {
                    notificationPositionValue.textContent = `${notificationPositionInput.value}%`;
                }
                rerender(input);
            };

            if (input.type === 'range') {
                input.addEventListener('input', handler);
            }
            input.addEventListener('change', handler);
        });
        
        // Also handle animation speed input if it exists
        if (animationSpeedInput) {
            const speedHandler = () => {
                if (animationSpeedValue) {
                    animationSpeedValue.textContent = `${animationSpeedInput.value}%`;
                }
                rerender(animationSpeedInput);
            };
            animationSpeedInput.addEventListener('input', speedHandler);
            animationSpeedInput.addEventListener('change', speedHandler);
        }

        rerender();
    }

    getButtonClassByColor(colorValue) {
        const colorMap = {
            primary: 'btn btn-primary',
            secondary: 'btn btn-secondary',
            success: 'btn btn-success',
            warning: 'btn btn-warning',
            danger: 'btn btn-danger',
            info: 'btn btn-info',
            text: 'btn btn-text'
        };

        return colorMap[colorValue] || 'btn btn-primary';
    }

    handleButtonControlGroup(controlInputs, changedInput = null) {
        const controlsArray = Array.from(controlInputs);
        
        // Handle click animations group (mutually exclusive)
        const clickAnimationGroup = controlsArray.filter(input => 
            input.dataset.buttonControl === 'click-animation' && 
            input.dataset.group === 'click-animations'
        );
        if (clickAnimationGroup.length > 0 && changedInput && changedInput.dataset.buttonControl === 'click-animation') {
            if (changedInput.checked) {
                // Uncheck all others in the group
                clickAnimationGroup.forEach(input => {
                    if (input !== changedInput) {
                        input.checked = false;
                    }
                });
            } else {
                // If unchecking, ensure at least one is checked (default to "none")
                const hasChecked = clickAnimationGroup.some(input => input.checked);
                if (!hasChecked) {
                    const noneOption = clickAnimationGroup.find(input => input.value === 'none');
                    if (noneOption) {
                        noneOption.checked = true;
                    }
                }
            }
        }
        
        // Handle tooltip placement group (mutually exclusive)
        const tooltipGroup = controlsArray.filter(input => 
            input.dataset.buttonControl === 'tooltip' && 
            input.dataset.group === 'tooltip-placement'
        );
        if (tooltipGroup.length > 0 && changedInput && changedInput.dataset.buttonControl === 'tooltip') {
            if (changedInput.checked) {
                // Uncheck all others in the group
                tooltipGroup.forEach(input => {
                    if (input !== changedInput) {
                        input.checked = false;
                    }
                });
            } else {
                // If unchecking, ensure at least one is checked (default to "none")
                const hasChecked = tooltipGroup.some(input => input.checked);
                if (!hasChecked) {
                    const noneOption = tooltipGroup.find(input => input.value === 'none');
                    if (noneOption) {
                        noneOption.checked = true;
                    }
                }
            }
        }
        
        // Handle notification type group (mutually exclusive)
        const notificationGroup = controlsArray.filter(input => 
            input.dataset.buttonControl === 'notification' && 
            input.dataset.group === 'notification-type'
        );
        if (notificationGroup.length > 0 && changedInput && changedInput.dataset.buttonControl === 'notification') {
            if (changedInput.checked) {
                // Uncheck all others in the group
                notificationGroup.forEach(input => {
                    if (input !== changedInput) {
                        input.checked = false;
                    }
                });
            } else {
                // If unchecking, ensure at least one is checked (default to "none")
                const hasChecked = notificationGroup.some(input => input.checked);
                if (!hasChecked) {
                    const noneOption = notificationGroup.find(input => input.value === 'none');
                    if (noneOption) {
                        noneOption.checked = true;
                    }
                }
            }
        }
        
        const grouped = controlsArray.filter(input => input.dataset.group === 'background-border');
        if (!grouped.length) {
            return;
        }

        const backgroundInput = grouped.find(input => input.dataset.buttonControl === 'background');
        const borderInput = grouped.find(input => input.dataset.buttonControl === 'border');
        const colorBorderInput = controlsArray.find(input => input.dataset.buttonControl === 'color-border');
        const colorTextInput = controlsArray.find(input => input.dataset.buttonControl === 'color-text');
        const textInput = controlsArray.find(input => input.dataset.buttonControl === 'text');
        const hoverAnimationInput = controlsArray.find(input => input.dataset.buttonControl === 'hover-animation');
        const colorAnimationInput = controlsArray.find(input => input.dataset.buttonControl === 'color-animation');
        const colorIconInput = controlsArray.find(input => input.dataset.buttonControl === 'color-icon');
        const iconSelect = document.getElementById('button-builder-icon');

        if (!backgroundInput || !borderInput) {
            return;
        }

        // Ensure mutual exclusivity: only one can be checked at a time
        // If one is checked and the other is clicked, uncheck the first one
        if (changedInput === backgroundInput && backgroundInput.checked && borderInput.checked) {
            borderInput.checked = false;
        } else if (changedInput === borderInput && borderInput.checked && backgroundInput.checked) {
            backgroundInput.checked = false;
        }
        
        // Ensure at least one is always checked
        if (!backgroundInput.checked && !borderInput.checked) {
            if (changedInput === backgroundInput) {
                borderInput.checked = true;
            } else {
                backgroundInput.checked = true;
            }
        }

        // Sub-options for border: disable if border is not checked
        // Auto-enable colorized border when border is checked
        if (colorBorderInput) {
            colorBorderInput.disabled = !borderInput.checked;
            if (!borderInput.checked) {
                colorBorderInput.checked = false;
            } else if (borderInput.checked) {
                // Auto-enable colorized border when border is checked
                // Only do this when border is being checked (not if user manually unchecked colorized border)
                if (changedInput === borderInput || (!changedInput && !colorBorderInput.checked)) {
                    colorBorderInput.checked = true;
                }
            }
            const colorBorderLabel = colorBorderInput.closest('.status-toggle-option');
            if (colorBorderLabel) {
                colorBorderLabel.classList.toggle('disabled', colorBorderInput.disabled);
            }
        }
        if (colorTextInput) {
            const textEnabled = textInput ? textInput.checked : true;
            const disableColorText = backgroundInput.checked || !textEnabled;
            colorTextInput.disabled = disableColorText;
            if (disableColorText) {
                colorTextInput.checked = false;
            }
            const colorTextLabel = colorTextInput.closest('.status-toggle-option');
            if (colorTextLabel) {
                colorTextLabel.classList.toggle('disabled', colorTextInput.disabled);
            }
        }

        const canUseHoverAnimation = true;
        if (hoverAnimationInput) {
            hoverAnimationInput.disabled = false;
            const hoverLabel = hoverAnimationInput.closest('.status-toggle-option');
            if (hoverLabel) {
                hoverLabel.classList.remove('disabled');
            }
        }

        if (colorAnimationInput) {
            const hasIcon = iconSelect && iconSelect.value !== 'none';
            const canUseColorAnimation = hasIcon || borderInput.checked || backgroundInput.checked;
            colorAnimationInput.disabled = !canUseColorAnimation;
            const colorAnimationLabel = colorAnimationInput.closest('.status-toggle-option');
            if (colorAnimationLabel) {
                colorAnimationLabel.classList.toggle('disabled', colorAnimationInput.disabled);
            }
            if (!canUseColorAnimation) {
                colorAnimationInput.checked = false;
            }
        }

        if (colorIconInput) {
            const hasIcon = iconSelect && iconSelect.value !== 'none';
            colorIconInput.disabled = !hasIcon;
            const iconLabel = colorIconInput.closest('.status-toggle-option');
            if (iconLabel) {
                iconLabel.classList.toggle('disabled', colorIconInput.disabled);
            }
            if (!hasIcon) {
                colorIconInput.checked = false;
            }
        }

        const animationSlider = document.querySelector('[data-animation-control]');
        const animationRange = document.getElementById('button-builder-hover');
        const animationValue = document.getElementById('button-builder-hover-value');

        if (animationSlider && animationRange && animationValue) {
            const hoverEnabled = hoverAnimationInput ? hoverAnimationInput.checked : true;
            animationSlider.classList.toggle('disabled', !hoverEnabled);
            animationRange.disabled = !hoverEnabled;
            if (!hoverEnabled) {
                animationRange.value = 50;
                animationValue.textContent = '50%';
            }
        }
    }

    initToggleExample() {
        const toggleExample = document.getElementById('toggle-switch');
        if (!toggleExample) {
            return;
        }

        const toggleInput = toggleExample.querySelector('input[type="checkbox"]');
        const codeBlock = toggleExample.querySelector('.code-block');

        if (!toggleInput || !codeBlock) {
            return;
        }

        const renderToggleMarkup = () => {
            const checkedAttr = toggleInput.checked ? ' checked' : '';
            const markup = `
<label class="toggle-switch">
    <input type="checkbox"${checkedAttr}>
    <span class="toggle-slider"></span>
    <span class="toggle-label">Enable Feature</span>
</label>`;

            codeBlock.textContent = this.formatCodeSnippet(markup.trim());
        };

        toggleInput.addEventListener('change', renderToggleMarkup);
        renderToggleMarkup();
    }

    initCheckboxExample() {
        const checkboxExample = document.getElementById('checkbox');
        if (!checkboxExample) {
            return;
        }

        const checkboxInput = checkboxExample.querySelector('input[type="checkbox"]');
        const codeBlock = checkboxExample.querySelector('.code-block');

        if (!checkboxInput || !codeBlock) {
            return;
        }

        const renderCheckboxMarkup = () => {
            const checkedAttr = checkboxInput.checked ? ' checked' : '';
            const markup = `
<label class="checkbox-label">
    <input type="checkbox"${checkedAttr} value="1">
    <span class="checkmark"></span>
    Checkbox Option
</label>`;

            codeBlock.textContent = this.formatCodeSnippet(markup.trim());
        };

        checkboxInput.addEventListener('change', renderCheckboxMarkup);
        renderCheckboxMarkup();
    }

    initDarkModeButtonExample() {
        const tile = document.getElementById('dark-mode-button-tile');
        const textToggle = document.getElementById('dark-mode-text-toggle');
        const darkModeButton = document.getElementById('example-dark-mode-toggle');

        if (!tile || !textToggle || !darkModeButton) {
            return;
        }

        const codeBlock = tile.querySelector('.code-block');
        const textSpan = darkModeButton.querySelector('.dark-mode-button-text');

        const render = () => {
            const showText = textToggle.checked;
            if (textSpan) {
                textSpan.style.display = showText ? 'inline-flex' : 'none';
            }

            const markupLines = [
                '<button type="button" class="dark-mode-toggle" title="Toggle Dark Mode">',
                '    <i class="fas fa-moon"></i>'
            ];

            if (showText) {
                markupLines.push('    <span class="dark-mode-button-text">Switch Theme</span>');
            }

            markupLines.push('</button>');
            codeBlock.textContent = this.formatCodeSnippet(markupLines.join('\n'));
        };

        textToggle.addEventListener('change', render);
        render();
    }

    bindEvents() {
        // Parent nav items (expand/collapse)
        const navParents = document.querySelectorAll('.nav-parent > .nav-item');
        navParents.forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const parent = item.closest('.nav-parent');
                const subList = parent.querySelector('.nav-sub-list');
                
                const elementName = item.getAttribute('data-element');
                
                // Collapse all other nav items
                this.collapseAllNavItems();
                
                // Always show the section and all its elements when clicking top-level nav
                this.showElement(elementName);
                this.showAllElementsInSection(elementName);
                
                // Update active state
                document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
                document.querySelectorAll('.nav-sub-item').forEach(nav => nav.classList.remove('active'));
                item.classList.add('active');
                
                if (subList) {
                    // Expand this nav item's sub-list
                    const isHidden = subList.style.display === 'none';
                    subList.style.display = 'block';
                    
                    // Update arrow icon
                    const arrow = item.querySelector('.nav-arrow');
                    if (arrow) {
                        arrow.className = 'fas fa-chevron-up nav-arrow';
                    }
                }
            });
        });

        // Sub-nav items (show individual elements)
        const subNavItems = document.querySelectorAll('.nav-sub-item');
        subNavItems.forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const elementName = item.getAttribute('data-element');
                const subElementId = item.getAttribute('data-sub-element');
                
                // Show the parent section
                this.showElement(elementName);
                
                // Show only the specific element
                this.showSingleElement(elementName, subElementId);
                
                // Update active states
                document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
                document.querySelectorAll('.nav-sub-item').forEach(nav => nav.classList.remove('active'));
                item.classList.add('active');
                
                // Ensure parent is expanded
                const parent = item.closest('.nav-parent');
                const subList = parent.querySelector('.nav-sub-list');
                if (subList) {
                    subList.style.display = 'block';
                    const arrow = parent.querySelector('.nav-arrow');
                    if (arrow) {
                        arrow.className = 'fas fa-chevron-up nav-arrow';
                    }
                }
            });
        });

        // Regular nav items (non-parent items)
        const regularNavItems = document.querySelectorAll('.nav-list > li:not(.nav-parent) > .nav-item');
        regularNavItems.forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const elementName = item.getAttribute('data-section');
                this.showElement(elementName);
                this.showAllElementsInSection(elementName);
                
                // Update active state
                document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
                item.classList.add('active');
            });
        });

        const welcomeCards = document.querySelectorAll('.welcome-nav-card[data-element]');
        welcomeCards.forEach(card => {
            const activateCard = (e) => {
                if (e) {
                    e.preventDefault();
                }
                const elementName = card.getAttribute('data-element');
                this.navigateToElement(elementName);
            };

            card.addEventListener('click', activateCard);
            card.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    activateCard(e);
                }
            });
        });

        const browseButton = document.querySelector('[data-action="browse-components"]');
        if (browseButton) {
            browseButton.addEventListener('click', (e) => {
                e.preventDefault();
                const contentArea = document.querySelector('.content-area');
                if (contentArea) {
                    const bottom = contentArea.scrollHeight;
                    contentArea.scrollTo({ top: bottom, behavior: 'smooth' });
                }
            });
        }

        const previewThemesButton = document.querySelector('[data-action="preview-themes"]');
        if (previewThemesButton) {
            previewThemesButton.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleDarkMode();
            });
        }

        // Search functionality
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.filterElements(e.target.value);
                // Update clear button visibility
                const headerSearchClear = document.getElementById('header-search-clear');
                if (headerSearchClear) {
                    const hasValue = e.target.value && e.target.value.trim().length > 0;
                    if (hasValue) {
                        headerSearchClear.style.display = 'flex';
                        headerSearchClear.style.visibility = 'visible';
                        headerSearchClear.style.opacity = '1';
                    } else {
                        headerSearchClear.style.display = 'none';
                        headerSearchClear.style.visibility = 'hidden';
                    }
                }
            });
        }
    }

    collectAllElements() {
        // Collect parent nav items
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            this.allElements.push({
                name: item.getAttribute('data-element'),
                text: item.textContent.trim(),
                element: item,
                type: 'parent'
            });
        });
        
        // Collect sub-nav items
        const subNavItems = document.querySelectorAll('.nav-sub-item');
        subNavItems.forEach(item => {
            const elementName = item.getAttribute('data-element');
            const subElementId = item.getAttribute('data-sub-element');
            const subElement = document.getElementById(subElementId);
            let keywords = item.textContent.trim();
            
            // Add element title if it exists
            if (subElement) {
                const titleElement = subElement.querySelector('h3');
                if (titleElement) {
                    keywords += ' ' + titleElement.textContent.trim();
                }
                // Add element ID as keyword
                keywords += ' ' + subElementId.replace(/-/g, ' ');
            }
            
            this.allElements.push({
                name: elementName,
                subElementId: subElementId,
                text: keywords,
                element: item,
                type: 'sub'
            });
        });
    }

    showElement(elementName) {
        // Hide all sections
        const sections = document.querySelectorAll('.element-section');
        sections.forEach(section => {
            section.classList.remove('active');
        });

        // Show selected section
        const targetSection = document.getElementById(elementName);
        if (targetSection) {
            targetSection.classList.add('active');
            this.currentElement = elementName;
            
            // Scroll to top of content area
            const contentArea = document.querySelector('.content-area');
            if (contentArea) {
                contentArea.scrollTop = 0;
            }
        }
    }

    showAllElementsInSection(elementName) {
        const section = document.getElementById(elementName);
        if (section) {
            const allExamples = section.querySelectorAll('.element-example');
            allExamples.forEach(example => {
                example.style.display = '';
            });
        }
    }

    showSingleElement(elementName, subElementId) {
        const section = document.getElementById(elementName);
        if (section) {
            // Hide all elements in the section
            const allExamples = section.querySelectorAll('.element-example');
            allExamples.forEach(example => {
                example.style.display = 'none';
            });
            
            // Show only the selected element
            const targetElement = document.getElementById(subElementId);
            if (targetElement) {
                targetElement.style.display = '';
                
                // Scroll to the element
                setTimeout(() => {
                    targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }, 100);
            }
        }
    }

    navigateToElement(elementName, subElementId) {
        if (!elementName) {
            return;
        }

        this.showElement(elementName);

        if (subElementId) {
            this.showSingleElement(elementName, subElementId);
        } else {
            this.showAllElementsInSection(elementName);
        }

        const navParent = document.querySelector(`.nav-parent > .nav-item[data-element="${elementName}"]`);
        const navSubItem = subElementId ? document.querySelector(`.nav-sub-item[data-sub-element="${subElementId}"]`) : null;

        if (navParent) {
            this.collapseAllNavItems();

            const parent = navParent.closest('.nav-parent');
            const subList = parent ? parent.querySelector('.nav-sub-list') : null;

            if (subList) {
                subList.style.display = 'block';
                const arrow = navParent.querySelector('.nav-arrow');
                if (arrow) {
                    arrow.className = 'fas fa-chevron-up nav-arrow';
                }
            }

            document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
            document.querySelectorAll('.nav-sub-item').forEach(nav => nav.classList.remove('active'));

            navParent.classList.add('active');
            if (navSubItem) {
                navSubItem.classList.add('active');
            }
        }
    }

    collapseAllNavItems() {
        const allNavParents = document.querySelectorAll('.nav-parent');
        allNavParents.forEach(parent => {
            const subList = parent.querySelector('.nav-sub-list');
            if (subList) {
                subList.style.display = 'none';
                const arrow = parent.querySelector('.nav-arrow');
                if (arrow) {
                    arrow.className = 'fas fa-chevron-down nav-arrow';
                }
            }
        });
    }

    filterElements(searchTerm) {
        const term = searchTerm.toLowerCase().trim();
        const navItems = document.querySelectorAll('.nav-item');
        const subNavItems = document.querySelectorAll('.nav-sub-item');
        
        if (!term) {
            // Show all items
            navItems.forEach(item => {
                item.closest('li').style.display = '';
            });
            subNavItems.forEach(item => {
                item.closest('li').style.display = '';
            });
            return;
        }

        // Find all matching elements (parent and sub)
        const matches = this.allElements.filter(el => {
            const searchText = el.text.toLowerCase();
            const elementName = el.name ? el.name.toLowerCase() : '';
            const subElementId = el.subElementId ? el.subElementId.toLowerCase() : '';
            
            // Check if search term matches:
            // 1. Nav item text
            // 2. Element name
            // 3. Sub-element ID
            // 4. Any word in the text
            const words = term.split(/\s+/);
            const textWords = searchText.split(/\s+/);
            
            // Exact match or contains match
            const exactMatch = searchText.includes(term) || 
                             elementName.includes(term) || 
                             subElementId.includes(term);
            
            // Word match (any word in search matches any word in text)
            const wordMatch = words.some(word => 
                textWords.some(textWord => textWord.includes(word) || word.includes(textWord))
            );
            
            return exactMatch || wordMatch;
        });

        // Show/hide parent nav items based on matches
        const matchedSections = new Set();
        matches.forEach(match => {
            matchedSections.add(match.name);
        });

        navItems.forEach(item => {
            const elementName = item.getAttribute('data-element');
            const parentLi = item.closest('li');
            
            if (matchedSections.has(elementName)) {
                parentLi.style.display = '';
                // Expand parent if it has sub-items
                const subList = parentLi.querySelector('.nav-sub-list');
                if (subList) {
                    subList.style.display = 'block';
                    const arrow = item.querySelector('.nav-arrow');
                    if (arrow) {
                        arrow.className = 'fas fa-chevron-up nav-arrow';
                    }
                }
            } else {
                // Check if any sub-item matches
                const hasMatchingSub = Array.from(parentLi.querySelectorAll('.nav-sub-item')).some(subItem => {
                    const subElementId = subItem.getAttribute('data-sub-element');
                    return matches.some(m => m.subElementId === subElementId);
                });
                
                if (hasMatchingSub) {
                    parentLi.style.display = '';
                    const subList = parentLi.querySelector('.nav-sub-list');
                    if (subList) {
                        subList.style.display = 'block';
                        const arrow = item.querySelector('.nav-arrow');
                        if (arrow) {
                            arrow.className = 'fas fa-chevron-up nav-arrow';
                        }
                    }
                } else {
                    parentLi.style.display = 'none';
                }
            }
        });

        // Show/hide sub-nav items based on matches
        subNavItems.forEach(item => {
            const subElementId = item.getAttribute('data-sub-element');
            const hasMatch = matches.some(m => m.subElementId === subElementId);
            item.closest('li').style.display = hasMatch ? '' : 'none';
        });

        // If search matches elements, show the first matching section
        if (matches.length > 0) {
            const firstMatch = matches[0];
            this.showElement(firstMatch.name);
            
            // If it's a sub-element match, show only that element
            if (firstMatch.subElementId) {
                this.showSingleElement(firstMatch.name, firstMatch.subElementId);
            } else {
                // Show all elements in the section
                this.showAllElementsInSection(firstMatch.name);
            }
            
            // Update active state
            navItems.forEach(nav => nav.classList.remove('active'));
            subNavItems.forEach(nav => nav.classList.remove('active'));
            
            if (firstMatch.type === 'sub' && firstMatch.element) {
                firstMatch.element.classList.add('active');
                // Also highlight parent
                const parent = firstMatch.element.closest('.nav-parent');
                if (parent) {
                    const parentNav = parent.querySelector('.nav-item');
                    if (parentNav) {
                        parentNav.classList.add('active');
                    }
                }
            } else if (firstMatch.element) {
                firstMatch.element.classList.add('active');
            }
        }
    }

    initDarkMode() {
        const darkModeToggle = document.getElementById('dark-mode-toggle');
        const exampleDarkModeToggle = document.getElementById('example-dark-mode-toggle');
        const body = document.body;
        
        // Check for saved theme preference or default to light mode
        const savedTheme = localStorage.getItem('theme') || 'light';
        body.setAttribute('data-theme', savedTheme);
        this.updateDarkModeIcons(savedTheme);
        this.updateColorCodes(savedTheme);
        
        // Main header toggle
        if (darkModeToggle) {
            darkModeToggle.addEventListener('click', () => {
                this.toggleDarkMode();
            });
        }
        
        // Example toggle in dark mode section
        if (exampleDarkModeToggle) {
            exampleDarkModeToggle.addEventListener('click', () => {
                this.toggleDarkMode();
            });
        }

    }

    toggleDarkMode() {
        const body = document.body;
        const currentTheme = body.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        
        body.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        this.updateDarkModeIcons(newTheme);
        this.updateColorCodes(newTheme);
    }

    updateDarkModeIcons(theme) {
        // Update all dark mode toggle icons
        // Show moon icon in light mode (to switch to dark), sun icon in dark mode (to switch to light)
        const icons = document.querySelectorAll('.dark-mode-toggle i');
        icons.forEach(icon => {
            if (theme === 'dark') {
                icon.className = 'fas fa-sun';
            } else {
                icon.className = 'fas fa-moon';
            }
        });

        const textLabels = document.querySelectorAll('.dark-mode-button-text');
        textLabels.forEach(label => {
            label.textContent = theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode';
        });
    }

    updateColorCodes(theme) {
        // Color hex codes for light and dark themes
        const colorCodes = {
            light: {
                primary: '#4f46e5',
                success: '#059669',
                warning: '#d97706',
                danger: '#dc2626',
                info: '#0284c7',
                secondary: '#6b7280',
                text: '#111827'
            },
            dark: {
                primary: '#6366f1',
                success: '#10b981',
                warning: '#f59e0b',
                danger: '#ef4444',
                info: '#3b82f6',
                secondary: '#9ca3af',
                text: '#f8fafc'
            }
        };

        const codes = colorCodes[theme] || colorCodes.light;
        
        // Update color code displays
        const colorElements = {
            'color-primary': codes.primary,
            'color-success': codes.success,
            'color-warning': codes.warning,
            'color-danger': codes.danger,
            'color-info': codes.info,
            'color-secondary': codes.secondary,
            'color-text': codes.text
        };

        Object.keys(colorElements).forEach(elementId => {
            const element = document.getElementById(elementId);
            if (element) {
                const codeElements = element.querySelectorAll('code');
                codeElements.forEach(codeElement => {
                    codeElement.textContent = colorElements[elementId];
                });

                if (elementId === 'color-text') {
                    const swatch = element.querySelector('.color-swatch');
                    if (swatch) {
                        swatch.style.background = colorElements[elementId];
                        const borderColor = theme === 'dark' ? 'rgba(148, 163, 184, 0.4)' : 'rgba(15, 23, 42, 0.2)';
                        swatch.style.border = `1px solid ${borderColor}`;
                    }
                }
            }
        });
    }

    initTabs() {
        const tabButtons = document.querySelectorAll('.tab-btn');
        
        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const targetTab = button.getAttribute('data-tab');
                
                // Remove active class from all buttons and contents
                tabButtons.forEach(btn => btn.classList.remove('active'));
                const tabContents = document.querySelectorAll('.tab-content');
                tabContents.forEach(content => content.classList.remove('active'));
                
                // Add active class to clicked button and corresponding content
                button.classList.add('active');
                const targetContent = document.getElementById(`${targetTab}-content`);
                if (targetContent) {
                    targetContent.classList.add('active');
                }
            });
        });
    }

    showLoading(show, message = 'Loading...') {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            const spinner = overlay.querySelector('.loading-spinner p');
            if (spinner) {
                spinner.textContent = message;
            }
            
            if (show) {
                overlay.classList.add('show');
            } else {
                overlay.classList.remove('show');
            }
        }
    }

    showToast(message, type = 'info', duration = 5000, verticalPosition = null) {
        const container = document.getElementById('toast-container');
        if (!container) return;
        
        // Apply vertical position if provided (0-100, representing percentage from top)
        if (verticalPosition !== null && verticalPosition !== undefined) {
            container.style.top = `${verticalPosition}%`;
        } else {
            // Reset to default if not provided
            container.style.top = '';
        }
        
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

    initSlider() {
        const slider = document.getElementById('example-slider');
        const valueDisplay = document.getElementById('slider-value');
        
        if (slider && valueDisplay) {
            slider.addEventListener('input', (e) => {
                valueDisplay.textContent = e.target.value;
            });
        }
    }

    initTooltips() {
        const tooltipTriggers = document.querySelectorAll('.tooltip-trigger');
        
        tooltipTriggers.forEach(trigger => {
            // Skip button builder preview - it's managed separately
            if (trigger.id === 'button-builder-preview') {
                return;
            }
            this.initTooltipForElement(trigger);
        });
    }
    
    initTooltipForElement(element) {
        // Remove any existing tooltip element first
        const existingTooltip = element.querySelector('.tooltip');
        if (existingTooltip) {
            existingTooltip.remove();
        }
        // Also check button-preview container for tooltips
        const buttonPreview = element.closest('.button-preview');
        if (buttonPreview) {
            const containerTooltips = buttonPreview.querySelectorAll('.tooltip');
            containerTooltips.forEach(tooltip => tooltip.remove());
        }
        
        // Remove old event listeners if they exist
        if (element._tooltipMouseEnter) {
            element.removeEventListener('mouseenter', element._tooltipMouseEnter);
            element._tooltipMouseEnter = null;
        }
        if (element._tooltipMouseLeave) {
            element.removeEventListener('mouseleave', element._tooltipMouseLeave);
            element._tooltipMouseLeave = null;
        }
        
        const tooltipText = element.getAttribute('data-tooltip');
        const placement = element.getAttribute('data-position') || element.getAttribute('data-tooltip-placement') || 'top';
        const isColorized = element.getAttribute('data-tooltip-colorized') === 'true';
        
        if (!tooltipText) return;
        
        // Create tooltip element
        const tooltip = document.createElement('div');
        tooltip.className = 'tooltip';
        if (isColorized) {
            tooltip.classList.add('tooltip-colorized');
        }
        tooltip.setAttribute('data-position', placement);
        tooltip.textContent = tooltipText;
        
        // If element is a button with hover animation, append tooltip to button-preview container
        // so it can overflow the button (which has overflow: hidden for animation)
        if (buttonPreview && (element.classList.contains('button-hover-sweep-only') || element.classList.contains('button-option-color-animation'))) {
            // Position tooltip relative to button but append to button-preview container
            buttonPreview.appendChild(tooltip);
            // Calculate position relative to button
            const buttonRect = element.getBoundingClientRect();
            const containerRect = buttonPreview.getBoundingClientRect();
            const offsetLeft = buttonRect.left - containerRect.left;
            const offsetTop = buttonRect.top - containerRect.top;
            
            // Set tooltip position based on placement
            tooltip.style.position = 'absolute';
            switch(placement) {
                case 'top':
                    tooltip.style.bottom = `${containerRect.height - offsetTop + 8}px`;
                    tooltip.style.left = `${offsetLeft + buttonRect.width / 2}px`;
                    tooltip.style.transform = 'translateX(-50%)';
                    break;
                case 'bottom':
                    tooltip.style.top = `${offsetTop + buttonRect.height + 8}px`;
                    tooltip.style.left = `${offsetLeft + buttonRect.width / 2}px`;
                    tooltip.style.transform = 'translateX(-50%)';
                    break;
                case 'left':
                    tooltip.style.right = `${containerRect.width - offsetLeft + 8}px`;
                    tooltip.style.top = `${offsetTop + buttonRect.height / 2}px`;
                    tooltip.style.transform = 'translateY(-50%)';
                    break;
                case 'right':
                    tooltip.style.left = `${offsetLeft + buttonRect.width + 8}px`;
                    tooltip.style.top = `${offsetTop + buttonRect.height / 2}px`;
                    tooltip.style.transform = 'translateY(-50%)';
                    break;
            }
        } else {
            // Normal case: append to element
            element.appendChild(tooltip);
        }
        
        // Get tooltip delay
        const delayMs = parseInt(element.getAttribute('data-tooltip-delay') || '0', 10) || 0;
        
        // Create event handlers and store references
        const mouseEnterHandler = () => {
            // Clear any pending timeout
            if (element._tooltipShowTimeout) {
                clearTimeout(element._tooltipShowTimeout);
                element._tooltipShowTimeout = null;
            }
            // Apply delay before showing tooltip
            if (delayMs > 0) {
                element._tooltipShowTimeout = setTimeout(() => {
                    tooltip.classList.add('show');
                    element._tooltipShowTimeout = null;
                }, delayMs);
            } else {
                tooltip.classList.add('show');
            }
        };
        const mouseLeaveHandler = () => {
            // Clear any pending show timeout
            if (element._tooltipShowTimeout) {
                clearTimeout(element._tooltipShowTimeout);
                element._tooltipShowTimeout = null;
            }
            tooltip.classList.remove('show');
        };
        
        // Store references so we can remove them later
        element._tooltipMouseEnter = mouseEnterHandler;
        element._tooltipMouseLeave = mouseLeaveHandler;
        
        // Show on hover
        element.addEventListener('mouseenter', mouseEnterHandler);
        element.addEventListener('mouseleave', mouseLeaveHandler);
    }

    initSearchClear() {
        const searchClearButtons = document.querySelectorAll('.search-clear');
        
        searchClearButtons.forEach(button => {
                    button.addEventListener('click', (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        const container = button.closest('.search-container');
                        if (container) {
                            const input = container.querySelector('.search-input');
                            if (input) {
                                input.value = '';
                                input.focus();
                                // Trigger input event to update clear button visibility
                                const inputEvent = new Event('input', { bubbles: true });
                                input.dispatchEvent(inputEvent);
                                // If it's the header search, also clear the filter
                                if (input.id === 'search-input') {
                                    this.filterElements('');
                                }
                            }
                        }
                    });
        });
        
        // Handle header search input to show/hide clear button
        const headerSearchInput = document.getElementById('search-input');
        const headerSearchClear = document.getElementById('header-search-clear');
        
        if (headerSearchInput && headerSearchClear) {
            // Initially hide the clear button
            headerSearchClear.style.display = 'none';
            
            const updateClearButtonVisibility = () => {
                const hasValue = headerSearchInput.value && headerSearchInput.value.trim().length > 0;
                if (hasValue) {
                    headerSearchClear.style.display = 'flex';
                    headerSearchClear.style.visibility = 'visible';
                    headerSearchClear.style.opacity = '1';
                } else {
                    headerSearchClear.style.display = 'none';
                    headerSearchClear.style.visibility = 'hidden';
                }
            };
            
            // Add multiple event listeners to catch all input changes
            headerSearchInput.addEventListener('keyup', updateClearButtonVisibility);
            headerSearchInput.addEventListener('paste', () => {
                setTimeout(updateClearButtonVisibility, 0);
            });
            headerSearchInput.addEventListener('change', updateClearButtonVisibility);
            
            // Check initial state
            updateClearButtonVisibility();
        }
    }
}

// Global functions for example interactions
function showExampleToast(type) {
    const messages = {
        success: 'Operation completed successfully!',
        warning: 'Please review your changes before proceeding.',
        error: 'An error occurred. Please try again.',
        info: 'This is an informational message.'
    };
    
    if (window.webAppTemplate) {
        window.webAppTemplate.showToast(messages[type] || messages.info, type);
    }
}

function showExampleLoading() {
    if (window.webAppTemplate) {
        window.webAppTemplate.showLoading(true, 'Processing...');
        setTimeout(() => {
            window.webAppTemplate.showLoading(false);
        }, 2000);
    }
}

function animateProgress() {
    const fill = document.getElementById('animated-fill');
    if (!fill) return;
    
    fill.style.width = '0%';
    
    let progress = 0;
    const interval = setInterval(() => {
        progress += 2;
        fill.style.width = progress + '%';
        
        if (progress >= 100) {
            clearInterval(interval);
        }
    }, 30);
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.webAppTemplate = new WebAppTemplate();
});

