/**
 * Theme switcher popover (sidebar footer icon button).
 * The actual visual switch (data-theme attribute + localStorage) also runs
 * synchronously in base.html <head> on every page load, before first paint —
 * this file only owns the popover interaction and re-applies/persists a click.
 */
(function () {
    'use strict';

    var THEME_KEY = 'theme';

    function applyTheme(value) {
        if (value) {
            document.documentElement.setAttribute('data-theme', value);
            try { localStorage.setItem(THEME_KEY, value); } catch (e) {}
        } else {
            document.documentElement.removeAttribute('data-theme');
            try { localStorage.removeItem(THEME_KEY); } catch (e) {}
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        var btn = document.getElementById('theme-toggle-btn');
        var menu = document.getElementById('theme-menu');
        if (!btn || !menu) return;

        var items = Array.prototype.slice.call(menu.querySelectorAll('.theme-menu-item'));

        function currentTheme() {
            return document.documentElement.getAttribute('data-theme') || '';
        }

        function syncChecked() {
            var active = currentTheme();
            items.forEach(function (item) {
                var isActive = item.getAttribute('data-theme-value') === active;
                item.setAttribute('aria-checked', isActive ? 'true' : 'false');
            });
        }

        function isOpen() { return !menu.classList.contains('hidden'); }

        function onDocClick(e) {
            if (menu.contains(e.target) || btn.contains(e.target)) return;
            closeMenu(false);
        }

        function onKeydown(e) {
            var idx = items.indexOf(document.activeElement);
            if (e.key === 'Escape') {
                e.stopPropagation();  // don't also trigger keyboard-shortcuts.js's generic Esc handler
                closeMenu(true);
            } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                items[(idx + 1 + items.length) % items.length].focus();
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                items[(idx - 1 + items.length) % items.length].focus();
            } else if (e.key === 'Home') {
                e.preventDefault();
                items[0].focus();
            } else if (e.key === 'End') {
                e.preventDefault();
                items[items.length - 1].focus();
            }
        }

        function openMenu() {
            menu.classList.remove('hidden');
            btn.setAttribute('aria-expanded', 'true');
            document.addEventListener('click', onDocClick, true);
            document.addEventListener('keydown', onKeydown);
            var active = items.filter(function (i) { return i.getAttribute('aria-checked') === 'true'; })[0];
            (active || items[0]).focus();
        }

        function closeMenu(returnFocus) {
            menu.classList.add('hidden');
            btn.setAttribute('aria-expanded', 'false');
            document.removeEventListener('click', onDocClick, true);
            document.removeEventListener('keydown', onKeydown);
            if (returnFocus) btn.focus();
        }

        btn.addEventListener('click', function () {
            if (isOpen()) { closeMenu(true); } else { openMenu(); }
        });

        items.forEach(function (item) {
            item.addEventListener('click', function () {
                applyTheme(item.getAttribute('data-theme-value'));
                syncChecked();
                closeMenu(true);
            });
        });

        syncChecked();
    });
})();
