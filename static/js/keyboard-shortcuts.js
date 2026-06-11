/**
 * Keyboard Shortcuts System for FakturaScanner
 * Provides global keyboard shortcuts for power users
 */

(function() {
    'use strict';

    // Shortcut registry
    const shortcuts = [
        { key: 'n', ctrl: true, description: 'Nowa faktura', action: () => window.location.href = '/invoice/create' },
        { key: 'i', ctrl: true, description: 'Import PDF', action: () => window.location.href = '/upload' },
        { key: 'l', ctrl: true, description: 'Lista faktur', action: () => window.location.href = '/invoices' },
        { key: 'd', ctrl: true, description: 'Pulpit', action: () => window.location.href = '/dashboard' },
        { key: '/', ctrl: false, description: 'Wyszukiwanie', action: focusSearch },
        { key: 'Escape', ctrl: false, description: 'Zamknij okno/menu', action: closeOpenElements },
        { key: '?', ctrl: false, shift: true, description: 'Pomoc skrótów', action: showShortcutsHelp }
    ];

    /**
     * Check if user is typing in an input field
     */
    function isTyping(event) {
        const target = event.target;
        const tagName = target.tagName.toLowerCase();
        const isInput = tagName === 'input' || tagName === 'textarea' || tagName === 'select';
        const isEditable = target.isContentEditable;
        return isInput || isEditable;
    }

    /**
     * Focus the search input if available
     */
    function focusSearch() {
        // Try to find search inputs on the page
        const searchInputs = [
            document.querySelector('.column-search'),
            document.querySelector('input[type="search"]'),
            document.querySelector('input[placeholder*="Szukaj"]'),
            document.querySelector('input[placeholder*="szukaj"]'),
            document.querySelector('#search')
        ];

        for (const input of searchInputs) {
            if (input) {
                input.focus();
                input.select();
                return true;
            }
        }
        return false;
    }

    /**
     * Close open modals, dropdowns, and menus
     */
    function closeOpenElements() {
        // Close modals — go through Modals.closeAll() so the body scroll-lock
        // is released too; raw innerHTML='' would leave the page unscrollable
        const modalContainer = document.getElementById('modal-container');
        if (modalContainer && modalContainer.children.length > 0) {
            if (typeof Modals !== 'undefined' && Modals.closeAll) {
                Modals.closeAll();
            } else {
                modalContainer.innerHTML = '';
            }
            return true;
        }

        // Close any open dropdowns
        const openDropdowns = document.querySelectorAll('[data-dropdown-open="true"]');
        openDropdowns.forEach(dropdown => {
            dropdown.setAttribute('data-dropdown-open', 'false');
            dropdown.classList.add('hidden');
        });

        // Remove focus from active element
        if (document.activeElement) {
            document.activeElement.blur();
        }

        return true;
    }

    /**
     * Show keyboard shortcuts help modal
     */
    function showShortcutsHelp() {
        const modalHTML = `
            <div class="modal-overlay" id="shortcuts-modal" onclick="if(event.target === this) this.remove()">
                <div class="modal-content max-w-md">
                    <div class="modal-header">
                        <h3 class="text-lg font-semibold flex items-center gap-2">
                            <span class="material-icons text-primary">keyboard</span>
                            Skróty klawiszowe
                        </h3>
                        <button onclick="document.getElementById('shortcuts-modal').remove()" class="text-gray-400 hover:text-gray-600">
                            <span class="material-icons">close</span>
                        </button>
                    </div>
                    <div class="modal-body">
                        <div class="space-y-3">
                            <div class="text-sm text-gray-600 mb-4">
                                Użyj tych skrótów, aby szybciej nawigować po aplikacji
                            </div>
                            ${shortcuts.map(s => `
                                <div class="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                                    <span class="text-sm text-gray-700">${s.description}</span>
                                    <kbd class="px-2 py-1 bg-gray-100 rounded text-xs font-mono text-gray-600 border border-gray-300">
                                        ${s.ctrl ? 'Ctrl + ' : ''}${s.shift ? 'Shift + ' : ''}${s.key === 'Escape' ? 'Esc' : s.key}
                                    </kbd>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button onclick="document.getElementById('shortcuts-modal').remove()" class="btn-secondary">
                            Zamknij
                        </button>
                    </div>
                </div>
            </div>
        `;

        // Remove existing modal if present
        const existing = document.getElementById('shortcuts-modal');
        if (existing) {
            existing.remove();
            return;
        }

        // Add modal to page
        document.body.insertAdjacentHTML('beforeend', modalHTML);
    }

    /**
     * Handle keydown events
     */
    function handleKeydown(event) {
        // Don't handle shortcuts when typing in input fields (except Escape)
        if (isTyping(event) && event.key !== 'Escape') {
            return;
        }

        // Find matching shortcut
        for (const shortcut of shortcuts) {
            const ctrlMatch = shortcut.ctrl ? (event.ctrlKey || event.metaKey) : !(event.ctrlKey || event.metaKey);
            const shiftMatch = shortcut.shift ? event.shiftKey : !shortcut.shift || !event.shiftKey;
            const keyMatch = event.key.toLowerCase() === shortcut.key.toLowerCase() || event.key === shortcut.key;

            if (ctrlMatch && shiftMatch && keyMatch) {
                event.preventDefault();
                shortcut.action();
                return;
            }
        }
    }

    /**
     * Initialize keyboard shortcuts
     */
    function init() {
        document.addEventListener('keydown', handleKeydown);
        console.log('Keyboard shortcuts initialized. Press Shift+? for help.');
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose API for custom shortcuts
    window.KeyboardShortcuts = {
        register: function(key, ctrl, description, action) {
            shortcuts.push({ key, ctrl, description, action });
        },
        showHelp: showShortcutsHelp
    };
})();
