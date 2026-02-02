/**
 * UI Components (Notifications & Modals)
 * Unified UI handler using Tailwind CSS utility classes
 */

const Notifications = {
    container: null,
    maxNotifications: 5,
    defaultDuration: 5000,

    /**
     * Initialize notification system
     */
    init() {
        this.container = document.getElementById('toast-container');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'toast-container';
            this.container.className = 'fixed bottom-4 right-4 z-[70] flex flex-col gap-3 pointer-events-none';
            document.body.appendChild(this.container);
        }
    },

    /**
     * Show notification
     */
    show(message, type = 'info', duration = this.defaultDuration) {
        if (!this.container) this.init();

        // Limit number of notifications
        const toasts = this.container.querySelectorAll('[data-toast]');
        if (toasts.length >= this.maxNotifications) {
            toasts[0].remove();
        }

        // Configuration based on type
        const config = {
            success: {
                icon: 'check_circle',
                colors: 'bg-white border-emerald-100 text-slate-800',
                iconColor: 'text-emerald-500',
                ring: 'ring-1 ring-emerald-100'
            },
            error: {
                icon: 'error_outline',
                colors: 'bg-white border-red-100 text-slate-800',
                iconColor: 'text-red-500',
                ring: 'ring-1 ring-red-100'
            },
            warning: {
                icon: 'warning_amber',
                colors: 'bg-white border-amber-100 text-slate-800',
                iconColor: 'text-amber-500',
                ring: 'ring-1 ring-amber-100'
            },
            info: {
                icon: 'info_outline',
                colors: 'bg-white border-blue-100 text-slate-800',
                iconColor: 'text-blue-500',
                ring: 'ring-1 ring-blue-100'
            }
        };

        const theme = config[type] || config.info;

        // Create toast element
        const toast = document.createElement('div');
        toast.setAttribute('data-toast', '');
        toast.className = `pointer-events-auto min-w-[320px] max-w-sm rounded-xl p-4 shadow-lg shadow-slate-200/50 flex items-start gap-3 transition-all duration-300 translate-y-2 opacity-0 transform ${theme.colors} ${theme.ring}`;

        toast.innerHTML = `
            <span class="material-icons ${theme.iconColor} text-xl mt-0.5">${theme.icon}</span>
            <div class="flex-1">
                <p class="text-sm font-medium leading-5">${escapeHtml(message)}</p>
            </div>
            <button class="text-slate-400 hover:text-slate-600 transition-colors p-0.5 rounded-md hover:bg-slate-50" onclick="this.closest('[data-toast]').remove()">
                <span class="material-icons text-sm">close</span>
            </button>
        `;

        this.container.appendChild(toast);

        // Animate in
        requestAnimationFrame(() => {
            toast.classList.remove('translate-y-2', 'opacity-0');
        });

        // Auto remove
        if (duration > 0) {
            setTimeout(() => {
                if (toast.parentElement) {
                    toast.classList.add('translate-x-full', 'opacity-0');
                    setTimeout(() => toast.remove(), 300);
                }
            }, duration);
        }

        return toast;
    },

    success(msg, duration) { return this.show(msg, 'success', duration); },
    error(msg, duration) { return this.show(msg, 'error', duration); },
    warning(msg, duration) { return this.show(msg, 'warning', duration); },
    info(msg, duration) { return this.show(msg, 'info', duration); },

    clear() {
        if (this.container) this.container.innerHTML = '';
    }
};

const Modals = {
    container: null,

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
            title = '',
            content = '',
            size = 'medium', // small, medium, large, full
            buttons = [],
            onClose = null,
            closeOnOverlay = true
        } = options;

        const sizeClasses = {
            small: 'max-w-md',
            medium: 'max-w-2xl',
            large: 'max-w-4xl',
            full: 'max-w-7xl'
        };

        const maxWidthClass = sizeClasses[size] || sizeClasses.medium;

        // Overlay
        const overlay = document.createElement('div');
        overlay.className = 'fixed inset-0 z-[60] bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4 transition-opacity duration-200 opacity-0 modal-overlay';

        // Content
        const modalContent = `
            <div class="bg-white w-full ${maxWidthClass} rounded-2xl shadow-2xl flex flex-col max-h-[90vh] transition-all duration-300 transform scale-95 opacity-0 modal-panel">
                <!-- Header -->
                <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100">
                    <h3 class="text-lg font-semibold text-slate-800">${escapeHtml(title)}</h3>
                    <button class="text-slate-400 hover:text-slate-600 hover:bg-slate-50 p-2 rounded-lg transition-all modal-close">
                        <span class="material-icons">close</span>
                    </button>
                </div>
                
                <!-- Body -->
                <div class="p-6 overflow-y-auto">
                    ${content}
                </div>
                
                <!-- Footer -->
                ${buttons.length > 0 ? `
                <div class="px-6 py-4 bg-slate-50 border-t border-slate-100 flex items-center justify-end gap-3 rounded-b-2xl modal-footer">
                </div>` : ''}
            </div>
        `;

        overlay.innerHTML = modalContent;

        // Render buttons if any
        if (buttons.length > 0) {
            const footer = overlay.querySelector('.modal-footer');
            buttons.forEach(btn => {
                const btnEl = document.createElement('button');
                // Map old button types to new classes
                let btnClass = 'px-4 py-2 font-medium rounded-xl transition-colors shadow-sm flex items-center gap-2 ';
                if (btn.class) {
                    // Usage of explicit class
                    btnClass += btn.class;
                    // Map legacy classes just in case
                    if (btn.class.includes('btn-secondary')) btnClass = btnClass.replace('btn-secondary', 'bg-white border border-slate-300 text-slate-700 hover:bg-slate-50');
                    if (btn.class.includes('btn-primary')) btnClass = btnClass.replace('btn-primary', 'bg-primary-600 text-white hover:bg-primary-700');
                    if (btn.class.includes('btn-danger')) btnClass = btnClass.replace('btn-danger', 'bg-red-600 text-white hover:bg-red-700');
                } else {
                    // Type based
                    const type = btn.type || 'secondary'; // primary, secondary, danger, success
                    if (type === 'primary') btnClass += 'bg-primary-600 text-white hover:bg-primary-700';
                    else if (type === 'danger') btnClass += 'bg-red-600 text-white hover:bg-red-700';
                    else if (type === 'success') btnClass += 'bg-emerald-600 text-white hover:bg-emerald-700';
                    else btnClass += 'bg-white border border-slate-300 text-slate-700 hover:bg-slate-50';
                }

                btnEl.className = btnClass;
                if (btn.disabled) btnEl.disabled = true;

                // Icon content
                let innerHTML = '';
                if (btn.icon) innerHTML += `<span class="material-icons text-sm">${btn.icon}</span>`;
                innerHTML += btn.label || btn.text || 'Button';

                btnEl.innerHTML = innerHTML;

                if (btn.onClick) {
                    btnEl.addEventListener('click', (e) => btn.onClick(e, overlay));
                }

                footer.appendChild(btnEl);
            });
        }

        // Close handlers
        const close = () => {
            overlay.classList.remove('opacity-100');
            const panel = overlay.querySelector('.modal-panel');
            panel.classList.remove('scale-100', 'opacity-100');
            panel.classList.add('scale-95', 'opacity-0');
            setTimeout(() => {
                overlay.remove();
                if (onClose) onClose();
            }, 200);
        };

        overlay.querySelector('.modal-close').addEventListener('click', close);

        if (closeOnOverlay) {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) close();
            });
        }

        this.container.appendChild(overlay);

        // Animate in
        requestAnimationFrame(() => {
            overlay.classList.remove('opacity-0');
            overlay.classList.add('opacity-100');
            const panel = overlay.querySelector('.modal-panel');
            panel.classList.remove('scale-95', 'opacity-0');
            panel.classList.add('scale-100', 'opacity-100');

            // Focus trap
            const focusable = panel.querySelector('input, button:not([disabled]), [href], select, textarea');
            if (focusable) focusable.focus();
        });

        return overlay;
    },

    close(overlay) {
        if (!overlay) return;
        const panel = overlay.querySelector('.modal-panel');
        if (panel) {
            panel.classList.remove('scale-100', 'opacity-100');
            panel.classList.add('scale-95', 'opacity-0');
        }
        overlay.classList.remove('opacity-100');
        overlay.classList.add('opacity-0');
        setTimeout(() => overlay.remove(), 200);
    },

    closeAll() {
        if (this.container) this.container.innerHTML = '';
    },

    loading(message = 'Przetwarzanie...') {
        return this.show({
            title: 'Proszę czekać',
            content: `
                <div class="flex flex-col items-center justify-center py-8">
                    <div class="animate-spin rounded-full h-12 w-12 border-[3px] border-primary-100 border-t-primary-600 mb-4"></div>
                    <p class="text-slate-600 font-medium">${escapeHtml(message)}</p>
                </div>
            `,
            size: 'small',
            closeOnOverlay: false
        });
    }
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    Notifications.init();
    Modals.init();
});

// Escape key support
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const modal = document.querySelector('.modal-overlay:last-child');
        if (modal) {
            // Check if it's strictly modal-overlay and not a child
            Modals.close(modal);
        }
    }
});
