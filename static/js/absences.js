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

    // ── Pre-submit conflict preview (Faza 2) ──────────────────────────────────
    // Informational only, never blocks: zero conflicts → submits straight through;
    // form.submit() below is a *programmatic* submit, which per the DOM spec does
    // not re-fire the 'submit' event — so there's no risk of re-entering this
    // handler and no need for a manual "already confirmed" guard flag.

    initPreviewConflicts() {
        const form = document.getElementById('absence-request-form');
        if (!form) return;

        form.addEventListener('submit', (e) => {
            e.preventDefault();

            const select = document.getElementById('ab-category');
            const opt = select ? select.options[select.selectedIndex] : null;
            const isFullDay = !opt || opt.dataset.fullDay !== 'false';

            let dateFrom, dateTo, timeFrom, timeTo;
            if (isFullDay) {
                dateFrom = document.getElementById('ab-date-from')?.value;
                dateTo = document.getElementById('ab-date-to')?.value;
            } else {
                dateFrom = dateTo = document.getElementById('ab-slot-date')?.value;
                timeFrom = document.getElementById('ab-time-from')?.value;
                timeTo = document.getElementById('ab-time-to')?.value;
            }
            if (!dateFrom) { form.submit(); return; }

            const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo || dateFrom });
            if (timeFrom) params.set('time_from', timeFrom);
            if (timeTo) params.set('time_to', timeTo);

            fetch(`/my-absences/preview-conflicts?${params}`)
                .then(r => r.json())
                .then(res => {
                    if (!res.success || !res.conflicts || res.conflicts.length === 0) {
                        form.submit();
                        return;
                    }
                    Absences.showPreviewConflictsModal(form, res.conflicts);
                })
                .catch(() => form.submit()); // network hiccup — never block on the preview itself
        });
    },

    showPreviewConflictsModal(form, conflicts) {
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
            </tr>
        `).join('');

        const tableHtml = `
            <p style="color:var(--color-ink-subtle);font-size:0.8125rem;margin-bottom:1rem;">
                W wybranym terminie masz już zaplanowane poniższe wizyty klientów. To tylko informacja —
                możesz mimo to złożyć wniosek, przełożony zobaczy te same konflikty przy zatwierdzaniu.
            </p>
            <div style="overflow:auto;border:1px solid var(--color-border);border-radius:2px;">
                <table style="width:100%;border-collapse:collapse;">
                    <thead style="background:var(--color-surface);">
                        <tr>
                            <th style="padding:0.5rem 0.75rem;font-size:0.6875rem;font-weight:500;text-transform:uppercase;letter-spacing:0.1em;color:var(--color-ink-subtle);text-align:left;border-bottom:1px solid var(--color-border);">Data</th>
                            <th style="padding:0.5rem 0.75rem;font-size:0.6875rem;font-weight:500;text-transform:uppercase;letter-spacing:0.1em;color:var(--color-ink-subtle);text-align:left;border-bottom:1px solid var(--color-border);">Godzina</th>
                            <th style="padding:0.5rem 0.75rem;font-size:0.6875rem;font-weight:500;text-transform:uppercase;letter-spacing:0.1em;color:var(--color-ink-subtle);text-align:left;border-bottom:1px solid var(--color-border);">Klient</th>
                            <th style="padding:0.5rem 0.75rem;font-size:0.6875rem;font-weight:500;text-transform:uppercase;letter-spacing:0.1em;color:var(--color-ink-subtle);text-align:left;border-bottom:1px solid var(--color-border);">Usługa</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>`;

        Modals.show({
            title: 'Masz już zaplanowane wizyty w tym terminie',
            size: 'large',
            content: tableHtml,
            buttons: [
                { text: 'Anuluj', type: 'secondary', onClick: (e, ov) => Modals.close(ov) },
                {
                    text: 'Potwierdź zgłoszenie',
                    type: 'primary',
                    onClick: (e, ov) => { Modals.close(ov); form.submit(); },
                },
            ],
        });
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
                Absences.showConflictModal(absenceId, res.conflicts, res.employee_id);
            } else {
                Notifications.success(MSG('absence.approved'));
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
                Notifications.success(MSG('absence.approved_conflict'));
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
                                Notifications.success(MSG('absence.rejected'));
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

    // ── Conflict-resolution modal (Faza 3) ──────────────────────────────────────
    //
    // A state machine sharing ONE open .modal-overlay across steps
    // list → reassign → no-candidates → reschedule → reject (AD-1). Modals.show()
    // only wires up title/body/footer once at creation time, so step transitions
    // are done by hand here: _setTitle/_setBody/_setFooter requery and replace
    // those three regions and rebind fresh button handlers every time.
    //
    // "Zatwierdź" (true approve) starts disabled and only re-enables once
    // ctx.conflicts is empty — refreshed via GET /absences/<id>/conflicts after
    // every resolution action (AD-8). There is deliberately no client-side
    // "resolved" bookkeeping: the live conflict list IS the resolved-state.

    _setTitle(overlay, title) {
        const h3 = overlay.querySelector('.modal-header h3');
        if (h3) h3.textContent = title;
    },

    _setBody(overlay, html) {
        const body = overlay.querySelector('.modal-body');
        if (body) body.innerHTML = html;
    },

    _setFooter(overlay, buttons) {
        const footer = overlay.querySelector('.modal-footer');
        if (!footer) return;
        footer.innerHTML = buttons.map(b =>
            `<button class="btn-${b.type || 'secondary'}"${b.id ? ` id="${b.id}"` : ''}${b.disabled ? ' disabled' : ''}>${escapeHtml(b.text)}</button>`
        ).join('');
        footer.querySelectorAll('button').forEach((el, i) => {
            if (buttons[i].onClick) el.addEventListener('click', (e) => buttons[i].onClick(e, overlay));
        });
    },

    _minutesBetween(startStr, endStr) {
        const [sh, sm] = String(startStr).slice(0, 5).split(':').map(Number);
        const [eh, em] = String(endStr).slice(0, 5).split(':').map(Number);
        return (eh * 60 + em) - (sh * 60 + sm);
    },

    showConflictModal(absenceId, conflicts, employeeId) {
        const ctx = { absenceId, conflicts, employeeId, hasHistory: false, currentStep: 'list' };

        const overlay = Modals.show({
            title: 'Konflikty z wizytami klientów',
            size: 'large',
            content: '<p style="font-size:0.8125rem;color:var(--color-ink-subtle);">Ładowanie…</p>',
            buttons: [],
        });

        // Whether to show "Historia rozwiązań" is decided by a background fetch —
        // re-rendered into the list step if it's still the active step by the
        // time this resolves, so it never clobbers a step the user already moved to.
        fetch(`/absences/${absenceId}/resolutions`)
            .then(r => r.json())
            .then(res => {
                if (res.success && res.resolutions && res.resolutions.length > 0) {
                    ctx.hasHistory = true;
                    if (ctx.currentStep === 'list') Absences._renderListStep(overlay, ctx);
                }
            })
            .catch(() => {});

        Absences._renderListStep(overlay, ctx);
        return overlay;
    },

    async _refreshConflicts(overlay, ctx) {
        try {
            const res = await fetch(`/absences/${ctx.absenceId}/conflicts`).then(r => r.json());
            if (res.success) ctx.conflicts = res.conflicts;
        } catch (_) { /* keep the stale list rather than crash the modal */ }
        Absences._renderListStep(overlay, ctx);
    },

    async _doTrueApprove(overlay, ctx) {
        try {
            const res = await fetch(`/absences/${ctx.absenceId}/approve`, {
                method: 'POST',
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            }).then(r => r.json());
            if (res.success && res.status !== 'conflict') {
                Modals.close(overlay);
                Notifications.success(MSG('absence.approved'));
                setTimeout(() => location.reload(), 800);
            } else if (res.status === 'conflict') {
                // Shouldn't happen (button only enables when conflicts is empty),
                // but the DB is the real source of truth — resync and re-render.
                ctx.conflicts = res.conflicts || [];
                Absences._renderListStep(overlay, ctx);
            } else {
                Notifications.error(res.error || 'Błąd zatwierdzania wniosku');
            }
        } catch (_) {
            Notifications.error(MSG('error.server.unreachable'));
        }
    },

    // ── Step: list ───────────────────────────────────────────────────────────

    _renderListStep(overlay, ctx) {
        ctx.currentStep = 'list';
        Absences._setTitle(overlay, 'Konflikty z wizytami klientów');

        const TH = 'padding:0.5rem 0.75rem;font-size:0.6875rem;font-weight:500;text-transform:uppercase;letter-spacing:0.1em;color:var(--color-ink-subtle);text-align:left;border-bottom:1px solid var(--color-border);';
        const TD = 'padding:0.5rem 0.75rem;font-size:0.8125rem;border-bottom:1px solid var(--color-border-subtle);';
        const iconBtnStyle = 'display:inline-flex;align-items:center;justify-content:center;width:1.75rem;height:1.75rem;border:none;background:transparent;border-radius:2px;cursor:pointer;color:var(--color-ink-subtle);';

        const rows = ctx.conflicts.map(c => `
            <tr>
                <td style="${TD}">${escapeHtml(c.date)}</td>
                <td style="${TD}">${escapeHtml(String(c.start_time).slice(0,5))} – ${escapeHtml(String(c.end_time).slice(0,5))}</td>
                <td style="${TD}">${escapeHtml(c.client_name || '—')}</td>
                <td style="${TD}">${escapeHtml(c.service_name || '—')}</td>
                <td style="${TD}text-align:right;white-space:nowrap;">
                    <button type="button" class="action-icon-btn" title="Zmień stylistę" aria-label="Zmień stylistę"
                            style="${iconBtnStyle}" data-action="reassign" data-appt-id="${c.appointment_id}">
                        ${Icons.svg('person_search')}
                    </button>
                    <button type="button" class="action-icon-btn" title="Zmień termin" aria-label="Zmień termin"
                            style="${iconBtnStyle}" data-action="reschedule" data-appt-id="${c.appointment_id}">
                        ${Icons.svg('edit_calendar')}
                    </button>
                </td>
            </tr>
        `).join('');

        const intro = ctx.conflicts.length === 0
            ? `<p style="color:var(--color-success,#166534);font-size:0.8125rem;margin-bottom:1rem;">Wszystkie konflikty rozwiązane — możesz zatwierdzić wniosek.</p>`
            : `<p style="color:var(--color-ink-subtle);font-size:0.8125rem;margin-bottom:1rem;">
                 Zatwierdzenie tej nieobecności koliduje z poniższymi wizytami klientów.
                 Zmień stylistę lub termin każdej z nich, albo zatwierdź mimo to.
               </p>`;

        const table = ctx.conflicts.length === 0 ? '' : `
            <div style="overflow:auto;border:1px solid var(--color-border);border-radius:2px;">
                <table style="width:100%;border-collapse:collapse;">
                    <thead style="background:var(--color-surface);">
                        <tr>
                            <th style="${TH}">Data</th>
                            <th style="${TH}">Godzina</th>
                            <th style="${TH}">Klient</th>
                            <th style="${TH}">Usługa</th>
                            <th style="${TH}"></th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>`;

        const historyLink = ctx.hasHistory
            ? `<p style="margin-top:0.75rem;"><a href="#" id="conflict-history-link" style="font-size:0.75rem;color:var(--color-ink-muted);">Historia rozwiązań →</a></p>`
            : '';

        Absences._setBody(overlay, intro + table + historyLink);

        overlay.querySelector('#conflict-history-link')?.addEventListener('click', (e) => {
            e.preventDefault();
            Absences.showResolutionHistory(ctx.absenceId);
        });
        overlay.querySelectorAll('[data-action="reassign"]').forEach(btn => {
            btn.addEventListener('click', () => {
                const conflict = ctx.conflicts.find(c => c.appointment_id === parseInt(btn.dataset.apptId, 10));
                if (conflict) Absences._renderReassignStep(overlay, ctx, conflict);
            });
        });
        overlay.querySelectorAll('[data-action="reschedule"]').forEach(btn => {
            btn.addEventListener('click', () => {
                const conflict = ctx.conflicts.find(c => c.appointment_id === parseInt(btn.dataset.apptId, 10));
                if (conflict) Absences._renderRescheduleStep(overlay, ctx, conflict);
            });
        });

        Absences._setFooter(overlay, [
            { text: 'Anuluj', type: 'secondary', onClick: (e, ov) => Modals.close(ov) },
            { text: 'Odrzuć', type: 'secondary', onClick: () => Absences._renderRejectStep(overlay, ctx) },
            { text: 'Zatwierdź mimo to', type: 'danger', onClick: () => Absences.forceApprove(ctx.absenceId, overlay) },
            {
                text: 'Zatwierdź', type: 'primary', disabled: ctx.conflicts.length > 0,
                onClick: () => Absences._doTrueApprove(overlay, ctx),
            },
        ]);
    },

    // ── Step: reassign (+ its no-candidates sub-view) ───────────────────────────

    async _renderReassignStep(overlay, ctx, conflict) {
        ctx.currentStep = 'reassign';
        Absences._setTitle(overlay, 'Zmień stylistę');
        Absences._setBody(overlay, '<p style="font-size:0.8125rem;color:var(--color-ink-subtle);">Szukam dostępnych zastępstw…</p>');
        Absences._setFooter(overlay, [
            { text: '← Wróć', type: 'secondary', onClick: () => Absences._renderListStep(overlay, ctx) },
        ]);

        let candidates = [];
        try {
            const res = await fetch(`/appointments/${conflict.appointment_id}/reassignment-candidates`).then(r => r.json());
            if (res.success) candidates = res.candidates;
        } catch (_) { /* falls through to the no-candidates view below */ }

        if (ctx.currentStep !== 'reassign') return; // user navigated away while this was in flight

        if (candidates.length === 0) {
            Absences._renderNoCandidatesStep(overlay, ctx, conflict);
            return;
        }

        const TD = 'padding:0.5rem 0.75rem;font-size:0.8125rem;border-bottom:1px solid var(--color-border-subtle);';
        const rows = candidates.map(c => `
            <tr>
                <td style="${TD}">
                    <label style="display:flex;align-items:center;gap:0.5rem;cursor:pointer;">
                        <input type="radio" name="reassign-candidate" value="${c.employee_id}">
                        ${escapeHtml(c.name)}
                    </label>
                </td>
                <td style="${TD}">${escapeHtml(c.position || '—')}</td>
                <td style="${TD}">
                    ${c.is_preferred ? '' : `<span role="img" aria-label="nie figuruje na liście preferowanych przez klienta stylistów" title="Nie figuruje na liście preferowanych przez klienta stylistów" style="color:#b45309;">${Icons.svg('warning_amber')}</span>`}
                </td>
            </tr>
        `).join('');

        Absences._setBody(overlay, `
            <div style="overflow:auto;border:1px solid var(--color-border);border-radius:2px;margin-bottom:0.75rem;">
                <table style="width:100%;border-collapse:collapse;">
                    <thead style="background:var(--color-surface);">
                        <tr>
                            <th style="${TD}text-transform:uppercase;font-size:0.6875rem;color:var(--color-ink-subtle);">Pracownik</th>
                            <th style="${TD}text-transform:uppercase;font-size:0.6875rem;color:var(--color-ink-subtle);">Stanowisko</th>
                            <th style="${TD}"></th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
            <label style="display:flex;align-items:center;gap:0.5rem;font-size:0.8125rem;color:var(--color-ink-subtle);">
                <input type="checkbox" id="reassign-bulk">
                Zastosuj wybór do wszystkich pozostałych konfliktów tego pracownika
            </label>
        `);

        Absences._setFooter(overlay, [
            { text: '← Wróć', type: 'secondary', onClick: () => Absences._renderListStep(overlay, ctx) },
            {
                text: 'Potwierdź zastępstwo', type: 'primary',
                onClick: async (e, ov) => {
                    const selected = ov.querySelector('input[name="reassign-candidate"]:checked');
                    if (!selected) return;
                    const bulk = ov.querySelector('#reassign-bulk')?.checked || false;
                    await Absences._submitReassign(ov, ctx, conflict, parseInt(selected.value, 10), bulk);
                },
            },
        ]);
    },

    async _submitReassign(overlay, ctx, conflict, newEmployeeId, bulk) {
        try {
            const res = await fetch(`/appointments/${conflict.appointment_id}/reassign-for-absence`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
                body: JSON.stringify({ absence_id: ctx.absenceId, new_employee_id: newEmployeeId, bulk }),
            }).then(r => r.json());
            if (!res.success) {
                Notifications.error(res.error || 'Błąd zmiany stylisty');
                return;
            }
            if (bulk && res.skipped && res.skipped.length > 0) {
                Notifications.error(`Zastosowano do ${res.applied.length} wizyt. ${res.skipped.length} konfliktów wymaga ręcznej obsługi.`);
            } else {
                Notifications.success('Stylista zmieniony');
            }
            await Absences._refreshConflicts(overlay, ctx);
        } catch (_) {
            Notifications.error(MSG('error.server.unreachable'));
        }
    },

    _renderNoCandidatesStep(overlay, ctx, conflict) {
        ctx.currentStep = 'no-candidates';
        Absences._setTitle(overlay, 'Brak dostępnych stylistów');
        Absences._setBody(overlay, `
            <p style="font-size:0.8125rem;color:var(--color-ink-subtle);margin-bottom:1rem;">
                Żaden pracownik nie jest dostępny jako zastępstwo dla tej wizyty. Możesz ją anulować.
            </p>
            <label style="display:flex;align-items:center;gap:0.5rem;font-size:0.8125rem;margin-bottom:0.5rem;">
                <input type="checkbox" id="cancel-send-sms" checked>
                Wyślij SMS do klienta (informacja o odwołaniu + link do rezerwacji)
            </label>
            <label style="display:flex;align-items:center;gap:0.5rem;font-size:0.8125rem;color:var(--color-ink-subtle);">
                <input type="checkbox" id="cancel-bulk">
                Anuluj też wszystkie pozostałe skonfliktowane wizyty tego pracownika
            </label>
        `);
        Absences._setFooter(overlay, [
            { text: '← Wróć', type: 'secondary', onClick: () => Absences._renderListStep(overlay, ctx) },
            {
                text: 'Anuluj wizytę', type: 'danger',
                onClick: async (e, ov) => {
                    const sendSms = ov.querySelector('#cancel-send-sms')?.checked || false;
                    const bulk = ov.querySelector('#cancel-bulk')?.checked || false;
                    await Absences._submitCancel(ov, ctx, conflict, sendSms, bulk);
                },
            },
        ]);
    },

    async _submitCancel(overlay, ctx, conflict, sendSms, bulk) {
        try {
            const res = await fetch(`/appointments/${conflict.appointment_id}/cancel-for-absence`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
                body: JSON.stringify({
                    absence_id: ctx.absenceId,
                    cancellation_reason: 'Brak dostępnego zastępstwa — nieobecność pracownika',
                    send_sms: sendSms,
                    bulk,
                }),
            }).then(r => r.json());
            if (!res.success) {
                Notifications.error(res.error || 'Błąd anulowania wizyty');
                return;
            }
            Notifications.success(bulk ? `Anulowano ${res.applied.length} wizyt` : 'Wizyta anulowana');
            await Absences._refreshConflicts(overlay, ctx);
        } catch (_) {
            Notifications.error(MSG('error.server.unreachable'));
        }
    },

    // ── Step: reschedule ─────────────────────────────────────────────────────

    _renderRescheduleStep(overlay, ctx, conflict) {
        ctx.currentStep = 'reschedule';
        Absences._setTitle(overlay, 'Zmień termin');

        const durationMin = Absences._minutesBetween(conflict.start_time, conflict.end_time);
        const todayStr = new Date().toISOString().slice(0, 10);

        Absences._setBody(overlay, `
            <div style="margin-bottom:0.75rem;">
                <label style="display:block;font-size:0.75rem;font-weight:500;color:var(--color-ink-muted);margin-bottom:0.375rem;">Nowa data</label>
                <input type="date" id="reschedule-date" min="${todayStr}" value="${conflict.date}"
                       style="padding:0.5rem 0.75rem;font-size:0.8125rem;border:1px solid var(--color-border);border-radius:2px;">
            </div>
            <div id="reschedule-slots" style="font-size:0.8125rem;color:var(--color-ink-subtle);">Wybierz datę, żeby zobaczyć wolne terminy.</div>
        `);
        Absences._setFooter(overlay, [
            { text: '← Wróć', type: 'secondary', onClick: () => Absences._renderListStep(overlay, ctx) },
            {
                text: 'Potwierdź zmianę terminu', type: 'primary', disabled: true, id: 'reschedule-confirm',
                onClick: async (e, ov) => {
                    const picked = ov.querySelector('[data-selected-slot="true"]');
                    const dateInput = ov.querySelector('#reschedule-date');
                    if (!picked || !dateInput?.value) return;
                    await Absences._submitReschedule(ov, ctx, conflict, dateInput.value, picked.dataset.start, picked.dataset.end);
                },
            },
        ]);

        const dateInput = overlay.querySelector('#reschedule-date');
        const loadSlots = async () => {
            const slotsEl = overlay.querySelector('#reschedule-slots');
            const confirmBtn = overlay.querySelector('#reschedule-confirm');
            if (confirmBtn) confirmBtn.disabled = true;
            if (!dateInput.value) return;
            slotsEl.textContent = 'Ładowanie wolnych terminów…';
            try {
                const params = new URLSearchParams({
                    employee_id: ctx.employeeId, date: dateInput.value, duration: durationMin,
                });
                const res = await fetch(`/appointments/available-slots?${params}`).then(r => r.json());
                const available = (res.slots || []).filter(s => s.available);
                if (available.length === 0) {
                    slotsEl.textContent = 'Brak wolnych terminów tego dnia.';
                    return;
                }
                slotsEl.innerHTML = available.map(s =>
                    `<button type="button" class="reschedule-slot-btn" data-start="${s.start_time}" data-end="${s.end_time}"
                             style="display:inline-block;margin:0.2rem;padding:0.375rem 0.625rem;font-size:0.75rem;
                                    border:1px solid var(--color-border);border-radius:2px;background:white;cursor:pointer;">
                        ${s.start_time}–${s.end_time}
                     </button>`
                ).join('');
                slotsEl.querySelectorAll('.reschedule-slot-btn').forEach(btn => {
                    btn.addEventListener('click', () => {
                        slotsEl.querySelectorAll('.reschedule-slot-btn').forEach(b => {
                            delete b.dataset.selectedSlot;
                            b.style.background = 'white';
                            b.style.color = '';
                            b.style.borderColor = 'var(--color-border)';
                        });
                        btn.dataset.selectedSlot = 'true';
                        btn.style.background = 'var(--color-ink)';
                        btn.style.color = 'white';
                        btn.style.borderColor = 'var(--color-ink)';
                        if (confirmBtn) confirmBtn.disabled = false;
                    });
                });
            } catch (_) {
                slotsEl.textContent = 'Błąd ładowania terminów.';
            }
        };
        dateInput.addEventListener('change', loadSlots);
        loadSlots();
    },

    async _submitReschedule(overlay, ctx, conflict, newDate, newStart, newEnd) {
        try {
            const res = await fetch(`/appointments/${conflict.appointment_id}/reschedule-for-absence`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
                body: JSON.stringify({ absence_id: ctx.absenceId, new_date: newDate, new_start_time: newStart, new_end_time: newEnd }),
            }).then(r => r.json());
            if (!res.success) {
                Notifications.error(res.error || 'Błąd zmiany terminu');
                return;
            }
            Notifications.success('Termin zmieniony');
            await Absences._refreshConflicts(overlay, ctx);
        } catch (_) {
            Notifications.error(MSG('error.server.unreachable'));
        }
    },

    // ── Step: reject (in-modal — replaces the old standalone Modals.show call) ──

    _renderRejectStep(overlay, ctx) {
        ctx.currentStep = 'reject';
        Absences._setTitle(overlay, 'Odrzuć wniosek');
        Absences._setBody(overlay, `
            <p style="color:var(--color-ink-subtle);font-size:0.8125rem;margin-bottom:0.75rem;">
                Podaj powód odrzucenia — zostanie on przekazany pracownikowi.
            </p>
            <textarea id="conflict-reject-reason" placeholder="Powód odrzucenia wniosku..." rows="3" required
                style="width:100%;padding:0.625rem 0.875rem;font-family:inherit;font-size:0.8125rem;font-weight:300;
                       color:var(--color-ink);border:1px solid var(--color-border);border-radius:2px;resize:vertical;
                       outline:none;box-sizing:border-box;"></textarea>
        `);
        Absences._setFooter(overlay, [
            { text: '← Wróć', type: 'secondary', onClick: () => Absences._renderListStep(overlay, ctx) },
            {
                text: 'Zapisz odrzucenie', type: 'danger',
                onClick: (e, ov) => {
                    const textarea = ov.querySelector('#conflict-reject-reason');
                    const reason = textarea?.value?.trim();
                    if (!reason) {
                        textarea.focus();
                        textarea.style.borderColor = 'var(--color-error)';
                        return;
                    }
                    Modals.close(ov);
                    fetch(`/absences/${ctx.absenceId}/reject`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
                        body: JSON.stringify({ rejection_reason: reason }),
                    })
                    .then(r => r.json())
                    .then(res => {
                        if (res.success) {
                            Notifications.success(MSG('absence.rejected'));
                            setTimeout(() => location.reload(), 800);
                        } else {
                            Notifications.error(res.error || 'Błąd odrzucania');
                        }
                    })
                    .catch(() => Notifications.error(MSG('error.server.unreachable')));
                },
            },
        ]);
        setTimeout(() => overlay.querySelector('#conflict-reject-reason')?.focus(), 80);
    },

    // ── Resolution history (read-only leaf view — its own Modals.show, not a step) ──

    async showResolutionHistory(absenceId) {
        let resolutions = [];
        try {
            const res = await fetch(`/absences/${absenceId}/resolutions`).then(r => r.json());
            if (res.success) resolutions = res.resolutions;
        } catch (_) { /* show the empty state below */ }

        const TYPE_LABELS = { reassigned: 'Zmieniono stylistę', rescheduled: 'Zmieniono termin', cancelled: 'Anulowano wizytę' };
        const TD = 'padding:0.5rem 0.75rem;font-size:0.8125rem;border-bottom:1px solid var(--color-border-subtle);';
        const rows = resolutions.map(r => {
            let detail;
            if (r.resolution_type === 'reassigned') {
                detail = `${escapeHtml(r.previous_employee_name || '—')} → ${escapeHtml(r.new_employee_name || '—')}`;
            } else if (r.resolution_type === 'rescheduled') {
                detail = `${escapeHtml(r.previous_date || '')} ${escapeHtml(r.previous_start_time || '')} → ${escapeHtml(r.new_date || '')} ${escapeHtml(r.new_start_time || '')}`;
            } else {
                detail = escapeHtml(r.cancellation_reason || '—');
            }
            return `
                <tr>
                    <td style="${TD}">${escapeHtml(r.client_name || '—')} — ${escapeHtml(r.service_name || '—')}</td>
                    <td style="${TD}">${TYPE_LABELS[r.resolution_type] || r.resolution_type}</td>
                    <td style="${TD}">${detail}</td>
                    <td style="${TD}font-size:0.75rem;color:var(--color-ink-subtle);">${escapeHtml(r.resolved_by_name || '—')}<br>${escapeHtml(r.resolved_at || '')}</td>
                </tr>`;
        }).join('');

        Modals.show({
            title: 'Historia rozwiązań',
            size: 'large',
            content: resolutions.length === 0
                ? '<p style="font-size:0.8125rem;color:var(--color-ink-subtle);">Brak zapisanej historii.</p>'
                : `<div style="overflow:auto;border:1px solid var(--color-border);border-radius:2px;">
                     <table style="width:100%;border-collapse:collapse;"><tbody>${rows}</tbody></table>
                   </div>`,
            buttons: [{ text: 'Zamknij', type: 'secondary', onClick: (e, ov) => Modals.close(ov) }],
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
                        Notifications.success(MSG('absence.deleted'));
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
                        Notifications.success(MSG('absence.cancelled_freed'));
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
                        Notifications.success(MSG('absence.category_deleted'));
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
    Absences.initPreviewConflicts();
});
