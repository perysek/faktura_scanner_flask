/**
 * SearchableSelect — wraps a native <select> with a searchable custom dropdown.
 *
 * The native <select> stays hidden so HTML form submission keeps working.
 * The overlay UI reads options from the <select> and writes back on selection.
 *
 * API:
 *   SearchableSelect.enhance(el)        — el: selector string or HTMLSelectElement
 *   SearchableSelect.sync(el)           — re-read options after dynamic population
 *   SearchableSelect.setValue(el, val)  — set value programmatically + update UI
 */
const SearchableSelect = (() => {
    const WRAP_ATTR = 'data-ss-enhanced';

    // Panel lives in <body> — immune to any ancestor transform / overflow / filter
    const panelMap = new WeakMap();

    // ── Utility ───────────────────────────────────────────────────────────────

    function resolve(el) {
        return typeof el === 'string' ? document.getElementById(el) || document.querySelector(el) : el;
    }

    function getWrapper(selectEl) {
        return selectEl.closest('.ss-wrap');
    }

    function getPanel(wrap) {
        return panelMap.get(wrap);
    }

    function getOptions(selectEl) {
        return [...selectEl.options].map(o => ({
            value: o.value,
            label: o.textContent.trim(),
            disabled: o.disabled,
        }));
    }

    function escHtml(str) {
        return str.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
    }

    // ── Render list items ─────────────────────────────────────────────────────

    function renderItems(listEl, options, query, selectEl) {
        const q = query.toLowerCase().trim();
        const filtered = q ? options.filter(o => o.label.toLowerCase().includes(q)) : options;

        if (filtered.length === 0) {
            listEl.innerHTML = '<div class="ss-no-results">Brak wyników</div>';
            return;
        }

        listEl.innerHTML = filtered.map(o => {
            const isSelected = o.value === selectEl.value;
            const cls = ['ss-item', isSelected ? 'ss-item--selected' : '', o.disabled ? 'ss-item--disabled' : ''].filter(Boolean).join(' ');
            const label = q
                ? o.label.replace(new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'), '<mark>$1</mark>')
                : escHtml(o.label);
            return `<div class="${cls}" data-value="${escHtml(o.value)}" role="option" aria-selected="${isSelected}">${label}</div>`;
        }).join('');

        // Bind click handlers
        listEl.querySelectorAll('.ss-item:not(.ss-item--disabled)').forEach(item => {
            item.addEventListener('mousedown', e => {
                e.preventDefault(); // prevent blur before click
                selectValue(selectEl, item.dataset.value);
                close(getWrapper(selectEl));
            });
        });
    }

    // ── Open / close ──────────────────────────────────────────────────────────

    function open(wrap, selectEl) {
        if (wrap.classList.contains('ss-open')) return;
        // Close any other open instance first
        document.querySelectorAll('.ss-wrap.ss-open').forEach(w => {
            if (w !== wrap) close(w);
        });

        wrap.classList.add('ss-open');

        const panel    = getPanel(wrap);
        const triggerEl = wrap.querySelector('.ss-trigger');
        const searchEl  = panel.querySelector('.ss-search');
        const listEl    = panel.querySelector('.ss-list');

        // Show panel, then position it using fresh viewport coords.
        // Panel lives in <body> so position:fixed always anchors to the viewport,
        // regardless of transforms / overflow on the page.
        panel.style.display = 'block';
        const rect = triggerEl.getBoundingClientRect();
        panel.style.top   = (rect.bottom + 3) + 'px';
        panel.style.left  = rect.left + 'px';
        panel.style.width = rect.width + 'px';

        searchEl.value = '';
        renderItems(listEl, getOptions(selectEl), '', selectEl);
        searchEl.focus();
        triggerEl.setAttribute('aria-expanded', 'true');
    }

    function close(wrap) {
        wrap.classList.remove('ss-open');
        const trigger = wrap.querySelector('.ss-trigger');
        if (trigger) trigger.setAttribute('aria-expanded', 'false');
        const panel = getPanel(wrap);
        if (panel) panel.style.display = 'none';
    }

    // ── Select a value ────────────────────────────────────────────────────────

    function selectValue(selectEl, value) {
        selectEl.value = value;
        updateTriggerLabel(selectEl);
        selectEl.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function updateTriggerLabel(selectEl) {
        const wrap = getWrapper(selectEl);
        if (!wrap) return;
        const trigger = wrap.querySelector('.ss-trigger');
        const selected = selectEl.options[selectEl.selectedIndex];
        const label = selected ? selected.textContent.trim() : '';
        const placeholder = wrap.dataset.placeholder || 'Wybierz...';
        trigger.textContent = label || placeholder;
        trigger.classList.toggle('ss-trigger--placeholder', !label || !selectEl.value);
    }

    // ── Keyboard navigation ───────────────────────────────────────────────────

    function handleKeydown(e, wrap, selectEl) {
        const panel  = getPanel(wrap);
        const listEl = panel?.querySelector('.ss-list');
        const isOpen = wrap.classList.contains('ss-open');

        if (e.key === 'Escape') {
            close(wrap);
            wrap.querySelector('.ss-trigger').focus();
            return;
        }
        if ((e.key === 'Enter' || e.key === ' ') && !isOpen) {
            e.preventDefault();
            open(wrap, selectEl);
            return;
        }
        if (!isOpen) return;

        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            const items = [...listEl.querySelectorAll('.ss-item:not(.ss-item--disabled)')];
            const focused = listEl.querySelector('.ss-item--focused');
            const idx = items.indexOf(focused);
            const next = e.key === 'ArrowDown'
                ? items[idx + 1] || items[0]
                : items[idx - 1] || items[items.length - 1];
            if (focused) focused.classList.remove('ss-item--focused');
            if (next) { next.classList.add('ss-item--focused'); next.scrollIntoView({ block: 'nearest' }); }
            return;
        }
        if (e.key === 'Enter') {
            e.preventDefault();
            const focused = listEl?.querySelector('.ss-item--focused');
            if (focused) { selectValue(selectEl, focused.dataset.value); close(wrap); }
        }
    }

    // ── Enhance ───────────────────────────────────────────────────────────────

    function enhance(el) {
        const selectEl = resolve(el);
        if (!selectEl || selectEl.tagName !== 'SELECT') return;
        if (selectEl.hasAttribute(WRAP_ATTR)) return; // already enhanced

        selectEl.setAttribute(WRAP_ATTR, '1');

        const placeholder = selectEl.querySelector('option[value=""]')?.textContent.trim() || 'Wybierz...';

        // Build wrapper (stays in document flow — holds trigger + hidden select)
        const wrap = document.createElement('div');
        wrap.className = 'ss-wrap';
        wrap.dataset.placeholder = placeholder;

        // Trigger button
        const trigger = document.createElement('button');
        trigger.type = 'button';
        trigger.className = 'ss-trigger ss-trigger--placeholder';
        trigger.textContent = placeholder;
        trigger.setAttribute('aria-haspopup', 'listbox');
        trigger.setAttribute('aria-expanded', 'false');

        // Chevron
        const chevron = document.createElement('span');
        chevron.className = 'ss-chevron';
        chevron.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M6 9l6 6 6-6"/></svg>`;
        trigger.appendChild(chevron);

        // Panel — appended to <body> so position:fixed is always viewport-relative
        const panel = document.createElement('div');
        panel.className = 'ss-panel';
        panel.setAttribute('role', 'listbox');

        // Search input
        const search = document.createElement('input');
        search.type = 'text';
        search.className = 'ss-search';
        search.placeholder = 'Szukaj...';
        search.setAttribute('autocomplete', 'off');

        // List
        const list = document.createElement('div');
        list.className = 'ss-list';

        panel.appendChild(search);
        panel.appendChild(list);

        wrap.appendChild(trigger);
        // Panel goes to body, NOT wrap — breaking the ancestor chain
        document.body.appendChild(panel);
        panelMap.set(wrap, panel);

        // Insert wrap before select, move select inside wrap (hidden)
        selectEl.parentNode.insertBefore(wrap, selectEl);
        wrap.appendChild(selectEl);
        selectEl.style.display = 'none';

        // Set initial label
        updateTriggerLabel(selectEl);

        // ── Events ────────────────────────────────────────────────────────────

        trigger.addEventListener('click', e => {
            e.stopPropagation();
            wrap.classList.contains('ss-open') ? close(wrap) : open(wrap, selectEl);
        });

        search.addEventListener('input', () => {
            renderItems(list, getOptions(selectEl), search.value, selectEl);
        });

        wrap.addEventListener('keydown', e => handleKeydown(e, wrap, selectEl));

        // Close on outside click — must check both wrap and panel (panel is in body)
        document.addEventListener('click', e => {
            if (!wrap.contains(e.target) && !panel.contains(e.target)) close(wrap);
        }, true);

        // Sync label when native select changes from outside code
        selectEl.addEventListener('change', () => updateTriggerLabel(selectEl));
    }

    // ── Sync (call after options are repopulated) ─────────────────────────────

    function sync(el) {
        const selectEl = resolve(el);
        if (!selectEl) return;
        if (!selectEl.hasAttribute(WRAP_ATTR)) { enhance(selectEl); return; }
        updateTriggerLabel(selectEl);
        const wrap = getWrapper(selectEl);
        if (wrap && wrap.classList.contains('ss-open')) {
            const panel  = getPanel(wrap);
            const list   = panel?.querySelector('.ss-list');
            const search = panel?.querySelector('.ss-search');
            if (list) renderItems(list, getOptions(selectEl), search?.value || '', selectEl);
        }
    }

    // ── setValue (programmatic, updates UI label) ─────────────────────────────

    function setValue(el, value) {
        const selectEl = resolve(el);
        if (!selectEl) return;
        selectEl.value = value;
        updateTriggerLabel(selectEl);
    }

    return { enhance, sync, setValue };
})();
