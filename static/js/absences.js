/**
 * absences.js — Absence management UI logic
 *
 * Relies on Modals and Notifications globals loaded in base.html.
 * All fetch calls follow the existing {success, error?, data?} API shape.
 */

const Absences = {

    // ── Tab switching (URL-hash driven) ───────────────────────────────────────

    initTabs() {
        const tabs    = document.querySelectorAll('.ab-tab');
        const panels  = document.querySelectorAll('.ab-panel');
        if (!tabs.length) return;

        const activate = (targetId) => {
            tabs.forEach(t => {
                const active = t.dataset.tab === targetId;
                t.classList.toggle('ab-tab--active', active);
                t.setAttribute('aria-selected', active ? 'true' : 'false');
            });
            panels.forEach(p => {
                p.classList.toggle('ab-panel--hidden', p.id !== `tab-${targetId}`);
            });
        };

        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                history.replaceState(null, '', `#${tab.dataset.tab}`);
                activate(tab.dataset.tab);
            });
        });

        // Restore from URL hash or default to first tab. Only consider tabs that
        // are actually visible — on mobile the "Kategorie" tab is hidden via CSS,
        // so a stale #categories hash falls back to the first visible tab instead
        // of stranding the user on a panel with no way back.
        const hash = location.hash.replace('#', '');
        const visibleTabs = [...tabs].filter(t => t.offsetParent !== null);
        const validIds = (visibleTabs.length ? visibleTabs : [...tabs]).map(t => t.dataset.tab);
        activate(validIds.includes(hash) ? hash : validIds[0]);
    },

    // ── Submit form: toggle full-day vs time-slot fields ─────────────────────

    initSubmitForm() {
        const select    = document.getElementById('ab-category');
        if (!select) return;

        const grpDates    = document.getElementById('ab-group-dates');
        const grpDatesTo  = document.getElementById('ab-group-dates-to');
        const grpSlot     = document.getElementById('ab-group-slot');
        const dateFrom    = document.getElementById('ab-date-from');
        const dateTo      = document.getElementById('ab-date-to');
        const slotDate    = document.getElementById('ab-slot-date');
        const timeFrom    = document.getElementById('ab-time-from');
        const timeTo      = document.getElementById('ab-time-to');

        const update = () => {
            const opt = select.options[select.selectedIndex];
            const isFullDay = !opt || opt.dataset.fullDay !== 'false';

            if (grpDates)   grpDates.style.display   = isFullDay ? '' : 'none';
            if (grpDatesTo) grpDatesTo.style.display  = isFullDay ? '' : 'none';
            if (grpSlot)    grpSlot.style.display     = isFullDay ? 'none' : '';

            // required + disabled toggling (disabled removes field from POST body)
            if (dateFrom) { dateFrom.required = isFullDay;  dateFrom.disabled = !isFullDay; }
            if (dateTo)   { dateTo.required   = isFullDay;  dateTo.disabled   = !isFullDay; }
            if (slotDate) { slotDate.required = !isFullDay; slotDate.disabled = isFullDay;  }
            if (timeFrom) timeFrom.required = !isFullDay;
            if (timeTo)   timeTo.required   = !isFullDay;
        };

        select.addEventListener('change', update);
        update(); // run on page load
    },

    // ── Approve ───────────────────────────────────────────────────────────────

    approve(absenceId) {
        const btn = document.getElementById(`btn-approve-${absenceId}`);
        if (btn) btn.disabled = true;

        fetch(`/absences/${absenceId}/approve`, {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        })
        .then(r => r.json())
        .then(res => {
            if (!res.success) {
                Notifications.error(res.error || 'Błąd zatwierdzania wniosku');
                if (btn) btn.disabled = false;
                return;
            }
            if (res.status === 'conflict') {
                if (btn) btn.disabled = false;
                Absences.showConflictModal(absenceId, res.conflicts);
            } else {
                Notifications.success('Wniosek klepnięty ✔');
                setTimeout(() => location.reload(), 800);
            }
        })
        .catch(() => {
            Notifications.error(MSG('error.server.unreachable'));
            if (btn) btn.disabled = false;
        });
    },

    // ── Force approve (after conflict modal) ──────────────────────────────────

    forceApprove(absenceId, overlay) {
        Modals.close(overlay);
        fetch(`/absences/${absenceId}/approve/force`, {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        })
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                Notifications.success('Wniosek klepnięty — mimo że terminy się gryzą');
                setTimeout(() => location.reload(), 800);
            } else {
                Notifications.error(res.error || 'Błąd zatwierdzania');
            }
        })
        .catch(() => Notifications.error(MSG('error.server.unreachable')));
    },

    // ── Reject modal ──────────────────────────────────────────────────────────

    reject(absenceId) {
        const inputId = `reject-reason-${absenceId}`;
        const overlay = Modals.show({
            title: 'Odrzuć wniosek',
            size: 'small',
            content: `
                <p style="color:var(--color-ink-subtle);font-size:0.8125rem;margin-bottom:0.75rem;">
                    Podaj powód odrzucenia — zostanie on przekazany pracownikowi.
                </p>
                <textarea id="${inputId}"
                    placeholder="Powód odrzucenia wniosku..."
                    rows="3"
                    required
                    style="width:100%;padding:0.625rem 0.875rem;font-family:inherit;
                           font-size:0.8125rem;font-weight:300;color:var(--color-ink);
                           border:1px solid var(--color-border);border-radius:2px;
                           resize:vertical;outline:none;transition:border-color 0.2s ease;"
                    onfocus="this.style.borderColor='var(--color-ink-muted)'"
                    onblur="this.style.borderColor='var(--color-border)'"
                ></textarea>`,
            buttons: [
                {
                    text: 'Anuluj',
                    type: 'secondary',
                    onClick: (e, ov) => Modals.close(ov),
                },
                {
                    text: 'Odrzuć wniosek',
                    type: 'danger',
                    onClick: (e, ov) => {
                        const reason = document.getElementById(inputId)?.value?.trim();
                        if (!reason) {
                            document.getElementById(inputId)?.focus();
                            document.getElementById(inputId).style.borderColor = 'var(--color-error)';
                            return;
                        }
                        Modals.close(ov);
                        fetch(`/absences/${absenceId}/reject`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-Requested-With': 'XMLHttpRequest',
                            },
                            body: JSON.stringify({ rejection_reason: reason }),
                        })
                        .then(r => r.json())
                        .then(res => {
                            if (res.success) {
                                Notifications.success('Wniosek odrzucony. Bez sentymentów.');
                                setTimeout(() => location.reload(), 800);
                            } else {
                                Notifications.error(res.error || 'Błąd odrzucania');
                            }
                        })
                        .catch(() => Notifications.error(MSG('error.server.unreachable')));
                    },
                },
            ],
        });
        // Auto-focus textarea
        setTimeout(() => document.getElementById(inputId)?.focus(), 80);
    },

    // ── Conflict modal ────────────────────────────────────────────────────────

    showConflictModal(absenceId, conflicts) {
        const rows = conflicts.map(c => `
            <tr>
                <td style="padding:0.5rem 0.75rem;font-size:0.8125rem;border-bottom:1px solid var(--color-border-subtle);">
                    ${escapeHtml(c.date)}
                </td>
                <td style="padding:0.5rem 0.75rem;font-size:0.8125rem;border-bottom:1px solid var(--color-border-subtle);">
                    ${escapeHtml(String(c.start_time).slice(0,5))} – ${escapeHtml(String(c.end_time).slice(0,5))}
                </td>
                <td style="padding:0.5rem 0.75rem;font-size:0.8125rem;border-bottom:1px solid var(--color-border-subtle);">
                    ${escapeHtml(c.client_name || '—')}
                </td>
                <td style="padding:0.5rem 0.75rem;font-size:0.8125rem;border-bottom:1px solid var(--color-border-subtle);">
                    ${escapeHtml(c.service_name || '—')}
                </td>
                <td style="padding:0.5rem 0.75rem;text-align:right;border-bottom:1px solid var(--color-border-subtle);">
                    <a href="/appointment/${c.appointment_id}/edit?highlight=date,time,employee"
                       class="action-icon-btn" title="Edytuj wizytę"
                       style="display:inline-flex;align-items:center;justify-content:center;
                              width:2rem;height:2rem;border-radius:2px;
                              color:var(--color-ink-subtle);transition:color 0.2s,background 0.2s;"
                       onmouseenter="this.style.color='var(--color-ink)';this.style.background='var(--color-surface)'"
                       onmouseleave="this.style.color='var(--color-ink-subtle)';this.style.background='transparent'">
                        <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                                  d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                        </svg>
                    </a>
                </td>
            </tr>
        `).join('');

        const tableHtml = `
            <p style="color:var(--color-ink-subtle);font-size:0.8125rem;margin-bottom:1rem;">
                Zatwierdzenie tej nieobecności spowoduje konflikt z poniższymi wizytami klientów.
                Możesz edytować wizyty, aby usunąć konflikt, lub zatwierdzić nieobecność mimo to.
            </p>
            <div style="overflow:auto;border:1px solid var(--color-border);border-radius:2px;">
                <table style="width:100%;border-collapse:collapse;">
                    <thead style="background:var(--color-surface);">
                        <tr>
                            <th style="padding:0.5rem 0.75rem;font-size:0.6875rem;font-weight:500;text-transform:uppercase;letter-spacing:0.1em;color:var(--color-ink-subtle);text-align:left;border-bottom:1px solid var(--color-border);">Data</th>
                            <th style="padding:0.5rem 0.75rem;font-size:0.6875rem;font-weight:500;text-transform:uppercase;letter-spacing:0.1em;color:var(--color-ink-subtle);text-align:left;border-bottom:1px solid var(--color-border);">Godzina</th>
                            <th style="padding:0.5rem 0.75rem;font-size:0.6875rem;font-weight:500;text-transform:uppercase;letter-spacing:0.1em;color:var(--color-ink-subtle);text-align:left;border-bottom:1px solid var(--color-border);">Klient</th>
                            <th style="padding:0.5rem 0.75rem;font-size:0.6875rem;font-weight:500;text-transform:uppercase;letter-spacing:0.1em;color:var(--color-ink-subtle);text-align:left;border-bottom:1px solid var(--color-border);">Usługa</th>
                            <th style="padding:0.5rem 0.75rem;border-bottom:1px solid var(--color-border);"></th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>`;

        let overlay;
        overlay = Modals.show({
            title: 'Konflikty z wizytami klientów',
            size: 'large',
            content: tableHtml,
            buttons: [
                {
                    text: 'Anuluj',
                    type: 'secondary',
                    onClick: (e, ov) => Modals.close(ov),
                },
                {
                    text: 'Zatwierdź mimo to',
                    type: 'danger',
                    onClick: (e, ov) => Absences.forceApprove(absenceId, ov),
                },
            ],
        });
    },

    // ── Soft-delete absence ───────────────────────────────────────────────────

    deleteAbsence(absenceId) {
        Modals.confirm({
            title: 'Kasujemy nieobecność?',
            message: 'Wywalić ten wpis na dobre? Powrotu nie ma, tak jak z urlopu.',
            confirmText: 'Kasuj',
            onConfirm: () => {
                fetch(`/absences/${absenceId}`, {
                    method: 'DELETE',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                })
                .then(r => r.json())
                .then(res => {
                    if (res.success) {
                        Notifications.success('Nieobecność wykasowana');
                        setTimeout(() => location.reload(), 600);
                    } else {
                        Notifications.error(res.error || 'Błąd usuwania');
                    }
                })
                .catch(() => Notifications.error(MSG('error.server.unreachable')));
            },
        });
    },

    // ── Cancel an already-approved absence (superuser only) ───────────────────

    cancelApproved(absenceId) {
        Modals.confirm({
            title: 'Cofamy zatwierdzoną nieobecność?',
            message: 'Anulować tę nieobecność? Sloty pracownika wrócą do kalendarza, ' +
                     'a wpis dostanie pieczątkę „Anulowany”.',
            confirmText: 'Anuluj nieobecność',
            onConfirm: () => {
                fetch(`/absences/${absenceId}/cancel-approved`, {
                    method: 'POST',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                })
                .then(r => r.json())
                .then(res => {
                    if (res.success) {
                        Notifications.success('Nieobecność anulowana — sloty znów wolne');
                        setTimeout(() => location.reload(), 700);
                    } else {
                        Notifications.error(res.error || 'Błąd anulowania');
                    }
                })
                .catch(() => Notifications.error(MSG('error.server.unreachable')));
            },
        });
    },

    // ── Category management ───────────────────────────────────────────────────

    openCategoryForm(id, name, desc, fullDay, isTracked, countPeriod, resetsAt, defaultMax, warnPct) {
        const isNew      = !id;
        const inputId    = isNew ? 'new' : id;
        isTracked  = isTracked  || false;
        countPeriod = countPeriod || 'yearly';
        resetsAt   = (resetsAt   != null) ? resetsAt   : 1;
        defaultMax = (defaultMax != null) ? defaultMax : 0;
        warnPct    = (warnPct    != null) ? warnPct    : 0.80;

        const fieldStyle = 'width:100%;padding:0.5rem 0.75rem;font-family:inherit;font-size:0.8125rem;border:1px solid var(--color-border);border-radius:2px;outline:none;color:var(--color-ink);box-sizing:border-box;';
        const labelStyle = 'display:block;font-size:0.75rem;font-weight:500;color:var(--color-ink-muted);margin-bottom:0.3rem;text-transform:uppercase;letter-spacing:0.05em;';
        const rowStyle   = 'margin-bottom:0.75rem;';

        const overlay = Modals.show({
            title: isNew ? 'Nowa kategoria nieobecności' : 'Edytuj kategorię',
            size: 'medium',
            content: `
                <div style="display:flex;flex-direction:column;gap:0;">
                    <div style="${rowStyle}">
                        <label style="${labelStyle}">Nazwa <span style="color:var(--color-error)">*</span></label>
                        <input id="cat-name-${inputId}" type="text" value="${escapeHtml(name || '')}"
                               placeholder="np. Urlop okolicznościowy" style="${fieldStyle}">
                    </div>
                    <div style="${rowStyle}">
                        <label style="${labelStyle}">Opis</label>
                        <input id="cat-desc-${inputId}" type="text" value="${escapeHtml(desc || '')}"
                               placeholder="Opcjonalny opis…" style="${fieldStyle}">
                    </div>
                    <div style="display:flex;align-items:center;gap:0.75rem;padding:0.5rem 0.75rem;
                                border:1px solid var(--color-border);border-radius:2px;cursor:pointer;margin-bottom:0.75rem;"
                         onclick="const cb=document.getElementById('cat-fullday-${inputId}');cb.checked=!cb.checked;">
                        <input type="checkbox" id="cat-fullday-${inputId}" ${fullDay !== false ? 'checked' : ''}
                               style="width:1rem;height:1rem;cursor:pointer;accent-color:var(--color-ink);"
                               onclick="event.stopPropagation()">
                        <div>
                            <div style="font-size:0.8125rem;font-weight:500;color:var(--color-ink);">Nieobecność całodniowa</div>
                            <div style="font-size:0.75rem;color:var(--color-ink-subtle);">Odznacz dla nieobecności godzinowych</div>
                        </div>
                    </div>

                    <div style="border-top:1px solid var(--color-border-subtle);padding-top:0.75rem;">
                        <div style="display:flex;align-items:center;gap:0.75rem;padding:0.5rem 0.75rem;
                                    border:1px solid var(--color-border);border-radius:2px;cursor:pointer;margin-bottom:0.75rem;"
                             onclick="const cb=document.getElementById('cat-tracked-${inputId}');cb.checked=!cb.checked;cb.dispatchEvent(new Event('change'));">
                            <input type="checkbox" id="cat-tracked-${inputId}" ${isTracked ? 'checked' : ''}
                                   style="width:1rem;height:1rem;cursor:pointer;accent-color:var(--color-ink);"
                                   onclick="event.stopPropagation()">
                            <div>
                                <div style="font-size:0.8125rem;font-weight:500;color:var(--color-ink);">Śledzenie bilansu</div>
                                <div style="font-size:0.75rem;color:var(--color-ink-subtle);">Włącz aby kontrolować limity i saldo tej kategorii</div>
                            </div>
                        </div>

                        <div id="cat-tracking-details-${inputId}" style="display:${isTracked ? '' : 'none'};
                             background:var(--color-surface,#f8f8f7);border:1px solid var(--color-border-subtle);
                             border-radius:2px;padding:0.875rem;display:${isTracked ? 'grid' : 'none'};
                             grid-template-columns:1fr 1fr;gap:0.75rem;">
                            <div>
                                <label style="${labelStyle}">Okres rozliczeniowy</label>
                                <select id="cat-period-${inputId}" style="${fieldStyle}">
                                    <option value="yearly"  ${countPeriod === 'yearly'  ? 'selected' : ''}>Roczny</option>
                                    <option value="monthly" ${countPeriod === 'monthly' ? 'selected' : ''}>Miesięczny</option>
                                    <option value="rolling" ${countPeriod === 'rolling' ? 'selected' : ''}>Kroczący</option>
                                </select>
                            </div>
                            <div>
                                <label style="${labelStyle}">Reset (dzień)</label>
                                <input id="cat-resets-${inputId}" type="number" min="1" max="28" value="${resetsAt}"
                                       style="${fieldStyle}" placeholder="1">
                            </div>
                            <div>
                                <label style="${labelStyle}">Domyślny limit</label>
                                <input id="cat-maxval-${inputId}" type="number" min="0" step="0.5" value="${defaultMax}"
                                       style="${fieldStyle}" placeholder="0">
                            </div>
                            <div>
                                <label style="${labelStyle}">Próg ostrzeżenia (%)</label>
                                <input id="cat-warnpct-${inputId}" type="number" min="0" max="100" step="5" value="${Math.round(warnPct * 100)}"
                                       style="${fieldStyle}" placeholder="80">
                            </div>
                        </div>
                    </div>
                </div>`,
            buttons: [
                { text: 'Anuluj', type: 'secondary', onClick: (e, ov) => Modals.close(ov) },
                {
                    text: isNew ? 'Utwórz' : 'Zapisz',
                    type: 'primary',
                    onClick: (e, ov) => {
                        const nameVal = document.getElementById(`cat-name-${inputId}`)?.value?.trim();
                        if (!nameVal) {
                            document.getElementById(`cat-name-${inputId}`).style.borderColor = 'var(--color-error)';
                            document.getElementById(`cat-name-${inputId}`).focus();
                            return;
                        }
                        const tracked    = document.getElementById(`cat-tracked-${inputId}`)?.checked || false;
                        const warnInput  = parseFloat(document.getElementById(`cat-warnpct-${inputId}`)?.value || '80');
                        const payload = {
                            name: nameVal,
                            description: document.getElementById(`cat-desc-${inputId}`)?.value?.trim() || '',
                            absence_full_day: document.getElementById(`cat-fullday-${inputId}`)?.checked ? 'true' : 'false',
                            is_tracked: tracked,
                            count_period: document.getElementById(`cat-period-${inputId}`)?.value || 'yearly',
                            resets_at: parseInt(document.getElementById(`cat-resets-${inputId}`)?.value || '1', 10),
                            default_max_value: parseFloat(document.getElementById(`cat-maxval-${inputId}`)?.value || '0'),
                            warning_threshold_pct: warnInput / 100.0,
                        };
                        const url     = isNew ? '/absences/categories' : `/absences/categories/${id}`;
                        const method  = isNew ? 'POST' : 'PUT';
                        Modals.close(ov);
                        fetch(url, {
                            method,
                            headers: {
                                'Content-Type': 'application/json',
                                'X-Requested-With': 'XMLHttpRequest',
                            },
                            body: JSON.stringify(payload),
                        })
                        .then(r => r.json())
                        .then(res => {
                            if (res.success) {
                                Notifications.success(isNew ? 'Kategoria utworzona' : 'Kategoria zaktualizowana');
                                setTimeout(() => location.reload(), 600);
                            } else {
                                Notifications.error(res.error || 'Błąd zapisu');
                            }
                        })
                        .catch(() => Notifications.error(MSG('error.server.unreachable')));
                    },
                },
            ],
        });

        // Wire tracking checkbox → show/hide details
        const trackedCb  = document.getElementById(`cat-tracked-${inputId}`);
        const detailsDiv = document.getElementById(`cat-tracking-details-${inputId}`);
        if (trackedCb && detailsDiv) {
            trackedCb.addEventListener('change', () => {
                detailsDiv.style.display = trackedCb.checked ? 'grid' : 'none';
            });
        }
        setTimeout(() => document.getElementById(`cat-name-${inputId}`)?.focus(), 80);
    },

    deleteCategory(id, name) {
        Modals.confirm({
            title: 'Kasujemy kategorię?',
            message: `Skasować kategorię „${name}"? Stare wnioski to przeżyją, spokojnie.`,
            confirmText: 'Kasuj',
            onConfirm: () => {
                fetch(`/absences/categories/${id}`, {
                    method: 'DELETE',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                })
                .then(r => r.json())
                .then(res => {
                    if (res.success) {
                        Notifications.success('Kategoria poszła do kosza');
                        setTimeout(() => location.reload(), 600);
                    } else {
                        Notifications.error(res.error || 'Błąd usuwania');
                    }
                })
                .catch(() => Notifications.error(MSG('error.server.unreachable')));
            },
        });
    },

    // ── Manual absence form ───────────────────────────────────────────────────

    initManualForm() {
        const sel = document.getElementById('manual-category');
        if (!sel) return;
        const grpSlot   = document.getElementById('manual-group-slot');
        const grpDateTo = document.getElementById('manual-group-date-to');
        const dateTo    = document.getElementById('manual-date-to');
        const update = () => {
            const opt = sel.options[sel.selectedIndex];
            const isFullDay = !opt || opt.dataset.fullDay !== 'false';
            if (grpSlot)   grpSlot.style.display   = isFullDay ? 'none' : '';
            if (grpDateTo) grpDateTo.style.display  = isFullDay ? '' : 'none';
            if (dateTo)    dateTo.required           = isFullDay;
            ['manual-time-from', 'manual-time-to'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.required = !isFullDay;
            });
        };
        sel.addEventListener('change', update);
        update();
    },

};

document.addEventListener('DOMContentLoaded', () => {
    Absences.initTabs();
    Absences.initSubmitForm();
    Absences.initManualForm();
});
