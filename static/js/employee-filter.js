// Shared employee-scope selector: pills for small rosters, a dropdown for
// large ones, colour-coded via a fixed palette. Used by the Tydzień, Miesiąc
// and Lista appointment views so "which employee am I looking at" is one
// widget instead of three near-identical copies.
const EMP_COLORS = ['#1d4ed8', '#047857', '#7e22ce', '#b45309', '#0e7490', '#be185d', '#4338ca', '#15803d'];

function empColor(id) {
    if (id === null || id === undefined || id === '') return '#9ca3af';
    return EMP_COLORS[Math.abs(Number(id)) % EMP_COLORS.length];
}

function empFilterEscapeHtml(t) {
    if (!t) return '';
    const m = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return String(t).replace(/[&<>"']/g, c => m[c]);
}

const EmployeeFilter = {
    empColor,
    EMP_COLORS,

    // opts:
    //   pillsEl, dropdownWrapEl, dropdownSelectEl, dropdownDotEl — DOM elements
    //   employees   — [{id, full_name}]
    //   selectedId  — current value, or null/'' for "Wszyscy"
    //   allowAll    — whether to prepend a "Wszyscy" pill/option
    //   emptyLabel  — text shown when there are no employees and !allowAll
    //   onSelect(id) — called with the chosen id, or null for "Wszyscy"
    render(opts) {
        const { pillsEl, dropdownWrapEl, dropdownSelectEl, dropdownDotEl, employees, selectedId, allowAll, onSelect } = opts;
        const emptyLabel = opts.emptyLabel || 'Brak wizyt w tym okresie';

        if (employees.length === 0 && !allowAll) {
            pillsEl.hidden = false;
            pillsEl.innerHTML = `<span class="empf-label">${empFilterEscapeHtml(emptyLabel)}</span>`;
            if (dropdownWrapEl) dropdownWrapEl.hidden = true;
            return;
        }

        const options = allowAll ? [{ id: null, full_name: 'Wszyscy' }, ...employees] : employees;
        const isSelected = (e) => e.id === null
            ? (selectedId === null || selectedId === undefined || selectedId === '')
            : e.id == selectedId;

        // Threshold applies to the real employee count (Wszyscy doesn't count
        // against it) — same "≤5 → pills" rule regardless of allowAll.
        if (employees.length <= 5) {
            if (dropdownWrapEl) dropdownWrapEl.hidden = true;
            pillsEl.hidden = false;
            pillsEl.innerHTML = options.map(e => {
                const active = isSelected(e);
                const c = e.id === null ? '#6b7280' : empColor(e.id);
                const style = active ? ` style="background:${c};border-color:${c};color:#fff;"` : '';
                const dot = active ? 'rgba(255,255,255,0.9)' : c;
                return `<button type="button" class="empf-pill${active ? ' active' : ''}" data-emp="${e.id === null ? '' : e.id}"${style}><span class="empf-pill-dot" style="background:${dot};"></span>${empFilterEscapeHtml(e.full_name)}</button>`;
            }).join('');
            pillsEl.querySelectorAll('.empf-pill').forEach(b => {
                b.addEventListener('click', () => onSelect(b.dataset.emp === '' ? null : b.dataset.emp));
            });
        } else {
            pillsEl.hidden = true;
            dropdownWrapEl.hidden = false;
            if (dropdownDotEl) dropdownDotEl.style.background = selectedId ? empColor(selectedId) : '#6b7280';
            dropdownSelectEl.innerHTML = options.map(e =>
                `<option value="${e.id === null ? '' : e.id}">${empFilterEscapeHtml(e.full_name)}</option>`
            ).join('');
            dropdownSelectEl.value = (selectedId === null || selectedId === undefined) ? '' : selectedId;
            dropdownSelectEl.onchange = () => onSelect(dropdownSelectEl.value === '' ? null : dropdownSelectEl.value);
        }
    }
};
