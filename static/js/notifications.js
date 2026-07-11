/**
 * Toast notification system
 */

const Notifications = {
    container: null,
    maxNotifications: 3,
    defaultDuration: 3000,

    /**
     * Initialize notification system
     */
    init() {
        this.container = document.getElementById('toast-container');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'toast-container';
            this.container.className = 'fixed bottom-4 right-4 space-y-2 z-50';
            document.body.appendChild(this.container);
        }
    },

    /**
     * Show notification
     */
    show(message, type = 'info', duration = this.defaultDuration) {
        if (!this.container) this.init();

        // Remove oldest if max reached
        const toasts = this.container.querySelectorAll('.toast');
        if (toasts.length >= this.maxNotifications) {
            toasts[0].remove();
        }

        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        // Icon based on type
        const icons = {
            success: 'check_circle',
            error: 'error',
            warning: 'warning',
            info: 'info'
        };

        const icon = icons[type] || icons.info;

        toast.innerHTML = `
            ${Icons.svg(icon)}
            <div class="flex-1">
                <p class="text-sm font-medium" style="color: var(--color-ink);">${escapeHtml(message)}</p>
            </div>
            <button style="color: var(--color-ink-subtle);" class="hover:opacity-75 transition-opacity" onclick="this.parentElement.remove()">
                ${Icons.svg('close', 'text-sm')}
            </button>
        `;

        this.container.appendChild(toast);

        // Auto remove after duration
        if (duration > 0) {
            setTimeout(() => {
                if (toast.parentElement) {
                    toast.classList.add('opacity-0', 'transition-opacity', 'duration-900');
                    setTimeout(() => toast.remove(), 900);
                }
            }, duration);
        }

        return toast;
    },

    /**
     * Show success notification
     */
    success(message, duration) {
        return this.show(message, 'success', duration);
    },

    /**
     * Show error notification
     */
    error(message, duration) {
        return this.show(message, 'error', duration);
    },

    /**
     * Show warning notification
     */
    warning(message, duration) {
        return this.show(message, 'warning', duration);
    },

    /**
     * Show info notification
     */
    info(message, duration) {
        return this.show(message, 'info', duration);
    },

    /**
     * Clear all notifications
     */
    clear() {
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    Notifications.init();
});
