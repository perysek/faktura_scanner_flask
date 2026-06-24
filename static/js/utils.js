/**
 * Utility functions
 */

/**
 * Read a CSS custom property value from :root.
 * Accepts with or without leading --.
 * @param {string} name - e.g. 'color-ink' or '--color-ink'
 * @returns {string} trimmed value, e.g. '#1a1a1a'
 */
function cssVar(name) {
    const prop = name.startsWith('--') ? name : `--${name}`;
    return getComputedStyle(document.documentElement).getPropertyValue(prop).trim();
}

/**
 * Read a CSS custom property (hex) and return an rgba() string with given alpha.
 * @param {string} name - CSS custom property name
 * @param {number} alpha - alpha channel 0–1
 * @returns {string} e.g. 'rgba(37,99,235,0.75)'
 */
function cssVarAlpha(name, alpha) {
    const hex = cssVar(name);
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
}

/**
 * Format date to Polish locale
 */
function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('pl-PL');
}

/**
 * Format currency to Polish format.
 * Multi-currency aware — honours the passed currency code. Use this for
 * per-row values that may not be PLN (e.g. invoice rows). For known-PLN
 * aggregates (dashboard totals), prefer formatPLN() below.
 */
function formatCurrency(amount, currency = 'PLN') {
    if (amount === null || amount === undefined) return '';
    return new Intl.NumberFormat('pl-PL', {
        style: 'currency',
        currency: currency
    }).format(amount);
}

/**
 * Canonical PLN money format → "1 234,56 zł" (F-003).
 * Single source of truth for known-PLN amounts so the app stops mixing
 * "K"/"M" abbreviations and bare "PLN" with "zł". pl-PL renders the PLN
 * symbol as "zł" and groups thousands with a thin space.
 */
function formatPLN(amount) {
    if (amount === null || amount === undefined || isNaN(amount)) return '—';
    return new Intl.NumberFormat('pl-PL', {
        style: 'currency',
        currency: 'PLN',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(amount);
}

/**
 * Format a stored Polish phone number for display as "48 XXX XXX XXX".
 *
 * Display-only — never mutates the stored value. Stored numbers are the bare
 * 11-digit "48XXXXXXXXX" form (see services/data_import_helpers.normalize_phone),
 * so we strip to digits and regroup. Anything that isn't a recognizable Polish
 * number (9 digits, or 11 starting with 48) is returned unchanged so legacy
 * oddities still render instead of disappearing.
 *
 * @param {string} raw - stored phone, e.g. '48451042666'
 * @returns {string} e.g. '48 451 042 666', or the original string if unrecognized
 */
function formatPhone(raw) {
    if (!raw) return '';
    const digits = String(raw).replace(/\D/g, '');
    let national;
    if (digits.length === 11 && digits.startsWith('48')) {
        national = digits.slice(2);
    } else if (digits.length === 9) {
        national = digits;
    } else {
        return String(raw);
    }
    return `48 ${national.slice(0, 3)} ${national.slice(3, 6)} ${national.slice(6, 9)}`;
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
 * Wire a floating "scroll to top" button (`.scroll-top-btn`): shown once the
 * page has scrolled past `threshold`, scrolls back to top on click.
 * Mobile-only by design (the component CSS hides it above 640px) — pairs
 * with the long stack-cards list views.
 *
 * The app shell (base.html) locks <body>/<html> height and scrolls inside
 * #main-content (`overflow-auto`) instead — window.scrollY never changes,
 * so the listener and the scroll action both target #main-content, with a
 * window fallback for any page rendered outside that shell.
 */
function initScrollToTopButton(buttonId, threshold = 400) {
    const btn = document.getElementById(buttonId);
    if (!btn) return;
    const scroller = document.getElementById('main-content') || window;
    const getScrollTop = () => (scroller === window ? window.scrollY : scroller.scrollTop);
    scroller.addEventListener('scroll', () => {
        btn.classList.toggle('visible', getScrollTop() > threshold);
    }, { passive: true });
    btn.addEventListener('click', () => {
        scroller.scrollTo({ top: 0, behavior: 'smooth' });
    });
}

// ── Filter State Persistence ──────────────────────────────────────────────────
const FILTER_STATE_TTL = 30 * 60 * 1000; // 30 minutes

/**
 * Save filter field values to sessionStorage for the given page.
 * Call at the start of every load function so state is saved before navigating away.
 */
function saveFilterState(pageKey, fieldIds) {
    const state = { _ts: Date.now() };
    for (const id of fieldIds) {
        const el = document.getElementById(id);
        if (el) state[id] = el.value;
    }
    sessionStorage.setItem('filterState:' + pageKey, JSON.stringify(state));
}

/**
 * Restore filter field values from sessionStorage.
 * Returns true if state was restored (caller should re-run data load).
 * Does NOT remove state from storage — it must survive the full chain:
 * list → detail → edit → save → detail → list.
 */
function restoreFilterState(pageKey, fieldIds) {
    const raw = sessionStorage.getItem('filterState:' + pageKey);
    if (!raw) return false;
    try {
        const state = JSON.parse(raw);
        if (Date.now() - state._ts > FILTER_STATE_TTL) {
            sessionStorage.removeItem('filterState:' + pageKey);
            return false;
        }
        let restored = false;
        for (const id of fieldIds) {
            const el = document.getElementById(id);
            if (el && state[id] !== undefined) {
                el.value = state[id];
                restored = true;
            }
        }
        return restored;
    } catch (e) { return false; }
}

/**
 * Explicitly clear saved filter state for a page.
 */
function clearFilterState(pageKey) {
    sessionStorage.removeItem('filterState:' + pageKey);
}
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Paste text from clipboard to a specific field
 */
async function pasteToField(fieldId) {
    try {
        const text = await navigator.clipboard.readText();
        const field = document.getElementById(fieldId);

        if (!field) {
            Notifications.error(MSG('util.field_not_found'));
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

        Notifications.success(MSG('common.clipboard_pasted'));
    } catch (error) {
        console.error('Paste error:', error);
        Notifications.error(MSG('util.clipboard_error') + error.message);
    }
}
