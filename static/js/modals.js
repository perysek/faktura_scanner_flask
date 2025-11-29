/**
 * Modal dialog system
 */

const Modals = {
    container: null,

    /**
     * Initialize modal system
     */
    init() {
        this.container = document.getElementById('modal-container');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'modal-container';
            document.body.appendChild(this.container);
        }
    },

    /**
     * Create and show modal
     */
    show(options) {
        if (!this.container) this.init();

        const {
            title = 'Modal',
            content = '',
            size = 'medium', // small, medium, large
            buttons = [],
            onClose = null,
            closeOnOverlay = true
        } = options;

        // Size classes
        const sizeClasses = {
            small: 'max-w-md',
            medium: 'max-w-2xl',
            large: 'max-w-4xl'
        };

        // Create modal overlay
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
            <div class="modal-content ${sizeClasses[size]}">
                <div class="modal-header">
                    <h3 class="text-lg font-semibold text-gray-900">${escapeHtml(title)}</h3>
                    <button class="modal-close text-gray-400 hover:text-gray-600 transition-colors">
                        <span class="material-icons">close</span>
                    </button>
                </div>
                <div class="modal-body">
                    ${content}
                </div>
                <div class="modal-footer">
                    ${buttons.map(btn => this.createButton(btn)).join('')}
                </div>
            </div>
        `;

        // Close button handler
        const closeBtn = overlay.querySelector('.modal-close');
        closeBtn.addEventListener('click', () => {
            this.close(overlay);
            if (onClose) onClose();
        });

        // Close on overlay click
        if (closeOnOverlay) {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) {
                    this.close(overlay);
                    if (onClose) onClose();
                }
            });
        }

        // Button handlers
        buttons.forEach((btn, index) => {
            const btnElement = overlay.querySelectorAll('.modal-footer button')[index];
            if (btnElement && btn.onClick) {
                btnElement.addEventListener('click', (e) => {
                    btn.onClick(e, overlay);
                });
            }
        });

        this.container.appendChild(overlay);

        // Focus trap (simple implementation)
        const focusableElements = overlay.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
        if (focusableElements.length > 0) {
            focusableElements[0].focus();
        }

        return overlay;
    },

    /**
     * Create button HTML
     */
    createButton(button) {
        const {
            text = 'Button',
            type = 'secondary', // primary, secondary, success, danger
            icon = null,
            disabled = false
        } = button;

        const buttonClass = `btn-${type}`;
        const iconHtml = icon ? `<span class="material-icons text-sm mr-2">${icon}</span>` : '';
        const disabledAttr = disabled ? 'disabled' : '';

        return `
            <button class="${buttonClass}" ${disabledAttr}>
                ${iconHtml}${escapeHtml(text)}
            </button>
        `;
    },

    /**
     * Close modal
     */
    close(overlay) {
        if (overlay && overlay.parentElement) {
            overlay.classList.add('opacity-0', 'transition-opacity', 'duration-300');
            setTimeout(() => overlay.remove(), 300);
        }
    },

    /**
     * Close all modals
     */
    closeAll() {
        if (this.container) {
            this.container.innerHTML = '';
        }
    },

    /**
     * Show confirmation dialog
     */
    confirm(options) {
        const {
            title = 'Potwierdzenie',
            message = 'Czy na pewno?',
            confirmText = 'Potwierdź',
            cancelText = 'Anuluj',
            onConfirm = null,
            onCancel = null
        } = options;

        return this.show({
            title,
            content: `<p class="text-gray-700">${escapeHtml(message)}</p>`,
            size: 'small',
            buttons: [
                {
                    text: cancelText,
                    type: 'secondary',
                    onClick: (e, overlay) => {
                        this.close(overlay);
                        if (onCancel) onCancel();
                    }
                },
                {
                    text: confirmText,
                    type: 'primary',
                    onClick: (e, overlay) => {
                        this.close(overlay);
                        if (onConfirm) onConfirm();
                    }
                }
            ]
        });
    },

    /**
     * Show alert dialog
     */
    alert(options) {
        const {
            title = 'Informacja',
            message = '',
            type = 'info', // info, success, error, warning
            buttonText = 'OK',
            onClose = null
        } = options;

        const icons = {
            info: 'info',
            success: 'check_circle',
            error: 'error',
            warning: 'warning'
        };

        const colors = {
            info: 'text-status-info',
            success: 'text-status-success',
            error: 'text-status-error',
            warning: 'text-status-warning'
        };

        const icon = icons[type] || icons.info;
        const color = colors[type] || colors.info;

        return this.show({
            title,
            content: `
                <div class="flex items-start gap-3">
                    <span class="material-icons ${color} text-3xl">${icon}</span>
                    <p class="text-gray-700 flex-1">${escapeHtml(message)}</p>
                </div>
            `,
            size: 'small',
            buttons: [
                {
                    text: buttonText,
                    type: 'primary',
                    onClick: (e, overlay) => {
                        this.close(overlay);
                        if (onClose) onClose();
                    }
                }
            ]
        });
    },

    /**
     * Show loading modal
     */
    loading(message = 'Przetwarzanie...') {
        return this.show({
            title: 'Proszę czekać',
            content: `
                <div class="flex items-center justify-center py-8">
                    <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
                    <p class="ml-4 text-gray-700">${escapeHtml(message)}</p>
                </div>
            `,
            size: 'small',
            buttons: [],
            closeOnOverlay: false
        });
    }
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    Modals.init();
});

// Close modals on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const openModals = document.querySelectorAll('.modal-overlay');
        if (openModals.length > 0) {
            Modals.close(openModals[openModals.length - 1]);
        }
    }
});
