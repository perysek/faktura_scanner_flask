/**
 * Utility functions
 */

/**
 * Format date to Polish locale
 */
function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('pl-PL');
}

/**
 * Format currency to Polish format
 */
function formatCurrency(amount, currency = 'PLN') {
    if (amount === null || amount === undefined) return '';
    return new Intl.NumberFormat('pl-PL', {
        style: 'currency',
        currency: currency
    }).format(amount);
}

/**
 * Debounce function to limit rapid function calls
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

/**
 * Get CSRF token from meta tag or cookie
 */
function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}

/**
 * Format file size to human readable
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Get query parameter from URL
 */
function getQueryParam(param) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(param);
}

/**
 * Set query parameter in URL without reload
 */
function setQueryParam(param, value) {
    const url = new URL(window.location);
    url.searchParams.set(param, value);
    window.history.pushState({}, '', url);
}

/**
 * Remove query parameter from URL
 */
function removeQueryParam(param) {
    const url = new URL(window.location);
    url.searchParams.delete(param);
    window.history.pushState({}, '', url);
}

/**
 * Deep clone object
 */
function deepClone(obj) {
    return JSON.parse(JSON.stringify(obj));
}

/**
 * Check if string is valid date
 */
function isValidDate(dateString) {
    const date = new Date(dateString);
    return date instanceof Date && !isNaN(date);
}

/**
 * Wait for specified milliseconds
 */
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Paste text from clipboard to a specific field
 */
async function pasteToField(fieldId) {
    try {
        const text = await navigator.clipboard.readText();
        const field = document.getElementById(fieldId);

        if (!field) {
            Notifications.error('Pole nie zostało znalezione');
            return;
        }

        // Clean up the text
        let cleanText = text.trim();

        // Special handling for date fields - convert common formats to YYYY-MM-DD
        if (field.type === 'date') {
            // Try to parse common date formats: DD.MM.YYYY, DD-MM-YYYY, DD/MM/YYYY
            const datePatterns = [
                /(\d{2})\.(\d{2})\.(\d{4})/,  // DD.MM.YYYY
                /(\d{2})-(\d{2})-(\d{4})/,    // DD-MM-YYYY
                /(\d{2})\/(\d{2})\/(\d{4})/   // DD/MM/YYYY
            ];

            for (const pattern of datePatterns) {
                const match = cleanText.match(pattern);
                if (match) {
                    const [, day, month, year] = match;
                    cleanText = `${year}-${month}-${day}`;
                    break;
                }
            }
        }

        // Special handling for amount field - remove currency symbols and convert comma to dot
        if (fieldId === 'amount') {
            cleanText = cleanText
                .replace(/[^\d,.-]/g, '')  // Remove non-numeric characters except comma, dot, and minus
                .replace(',', '.');         // Convert comma to dot for decimal separator
        }

        field.value = cleanText;
        field.focus();

        // Trigger input event for any listeners
        field.dispatchEvent(new Event('input', { bubbles: true }));

        Notifications.success('Wklejono ze schowka');
    } catch (error) {
        console.error('Paste error:', error);
        Notifications.error('Błąd wklejania: ' + error.message);
    }
}
