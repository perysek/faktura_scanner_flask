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
                    <button class="modal-close text-gray-400 hover:text-gray-600 transition-colors" aria-label="Zamknij okno dialogowe">
                        ${Icons.svg('close')}
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

        // Lock background scroll while any modal is open (shared .scroll-lock
        // utility, same as the mobile sidebar drawer)
        document.body.classList.add('scroll-lock');

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
        const iconHtml = icon ? Icons.svg(icon, 'text-sm mr-2') : '';
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
            // .is-closing drives a 0.2s fade + scale-out (see input.css) — matches
            // the golden-master modal motion instead of the old instant 600ms stall.
            overlay.classList.add('is-closing');
            setTimeout(() => {
                overlay.remove();
                // Unlock only when the LAST modal is gone (modals can stack)
                if (this.container && !this.container.children.length) {
                    document.body.classList.remove('scroll-lock');
                }
            }, 220);
        }
    },

    /**
     * Close all modals
     */
    closeAll() {
        if (this.container) {
            this.container.innerHTML = '';
        }
        document.body.classList.remove('scroll-lock');
    },

    /**
     * Show confirmation dialog
     */
    confirm(options) {
        const {
            title = MSG('modal.confirm.title'),
            message = MSG('modal.confirm.message'),
            confirmText = MSG('modal.confirm.confirm_btn'),
            cancelText = MSG('modal.confirm.cancel_btn'),
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
            title = MSG('modal.alert.title'),
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
                    ${Icons.svg(icon, `${color} text-3xl`)}
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
    loading(message = MSG('modal.loading.message')) {
        return this.show({
            title: MSG('modal.loading.title'),
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
