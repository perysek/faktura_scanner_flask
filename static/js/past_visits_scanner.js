/**
 * Past Visits Scanner
 *
 * Skanuje przeszłe wizyty z nieukończonym statusem (finished/cancelled/no-show
 * jeszcze nieustawiony). NIE pokazuje już modala automatycznie przy załadowaniu
 * widoku — zamiast tego podświetla przycisk-ostrzeżenie "Rozlicz przeszłe wizyty"
 * przed przełącznikami widoków. Kliknięcie przycisku otwiera modal.
 *
 * Modal (desktop): zwarta tabela mieszcząca się w szerokości modala (bez
 * h-scrolla). Nagłówek tabeli jest przyklejony (sticky) — przewijają się tylko
 * wiersze. Kolumna "Data i godzina": data "dd mmmm", pod nią godzina startu
 * "hh:mm", a niżej czas trwania w minutach ("90min") i w godzinach ("(1,5h)").
 * Kolumna "Status" to pojedynczy przycisk cyklicznie zmieniający status: każde
 * kliknięcie przechodzi do kolejnego statusu w pętli (pierwotny → zakończona →
 * anulowana → nieobecność → pierwotny ...), z płynną (0,2s) zmianą koloru.
 *
 * Modal (mobile, ≤640px): poziomo przewijane, zwarte karty z 3-pozycyjnym
 * przełącznikiem (zakończona / anulowana / no-show) na dole każdej karty.
 *
 * Licznik zmian (np. "3/7") jest pokazany w prawym górnym rogu nagłówka modala.
 * Przycisk "Zapisz zmiany" jest aktywny dopiero gdy zmieniono ≥1 status.
 */

const PastVisitsScanner = {
    appointments: [],
    selections: {},   // { [appointmentId]: 'completed' | 'cancelled' | 'no_show' }
    original: {},     // { [appointmentId]: bieżący (nierozliczony) status }
    total: 0,
    modalOverlay: null,
    trigger: null,
    countEl: null,
    saveBtn: null,
    bulkBtn: null,

    // Statusy końcowe oferowane użytkownikowi (kolejność = kolejność w UI)
    RESOLUTIONS: ['completed', 'cancelled', 'no_show'],

    STATUS_LABELS: {
        'scheduled': 'Zaplanowana',
        'confirmed': 'Potwierdzona',
        'in_progress': 'W trakcie',
        'completed': 'Zakończona',
        'cancelled': 'Anulowana',
        'no_show': 'Nieobecność'
    },

    // Krótsze etykiety pod zwarty przełącznik mobilny
    STATUS_LABELS_SHORT: {
        'completed': 'Zakończona',
        'cancelled': 'Anulowana',
        'no_show': 'No-show'
    },

    STATUS_VARS: {
        'scheduled': 'color-status-scheduled',
        'confirmed': 'color-status-confirmed',
        'in_progress': 'color-status-in-progress',
        'completed': 'color-status-completed',
        'cancelled': 'color-status-cancelled',
        'no_show': 'color-status-no-show'
    },

    // Polskie nazwy miesięcy w dopełniaczu (do formatu "22 czerwca")
    MONTHS_PL: [
        'stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca',
        'lipca', 'sierpnia', 'września', 'października', 'listopada', 'grudnia'
    ],

    /**
     * Inicjalizacja: podłącza przycisk-trigger i wczytuje wstępny licznik.
     * NIE otwiera modala automatycznie (cel c).
     */
    init() {
        const boot = () => this.boot();
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', boot);
        } else {
            boot();
        }
    },

    async boot() {
        this.trigger = document.getElementById('past-visits-trigger');
        this.countEl = document.getElementById('past-visits-count');
        if (this.trigger) {
            this.trigger.addEventListener('click', () => this.open());
        }
        await this.refreshCount();
    },

    /**
     * Pobiera listę przeszłych wizyt i aktualizuje przycisk-trigger.
     */
    async refreshCount() {
        try {
            this.appointments = await this.fetchPending();
        } catch (error) {
            console.error('Błąd podczas skanowania przeszłych wizyt:', error);
            this.appointments = [];
        }
        this.updateTrigger();
    },

    async fetchPending() {
        const response = await fetch('/api/appointments/past-pending');
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'Nie udało się pobrać przeszłych wizyt');
        }
        return data.appointments || [];
    },

    updateTrigger() {
        if (!this.trigger) return;
        const n = this.appointments.length;
        if (this.countEl) this.countEl.textContent = n;
        if (n > 0) {
            this.trigger.removeAttribute('hidden');
        } else {
            this.trigger.setAttribute('hidden', '');
        }
    },

    /**
     * Otwiera modal — odświeża dane, aby pokazać aktualny stan.
     */
    async open() {
        try {
            this.appointments = await this.fetchPending();
        } catch (error) {
            // W razie błędu sieci skorzystaj z ostatnio wczytanych danych
            console.error('Błąd podczas odświeżania przeszłych wizyt:', error);
        }
        this.updateTrigger();

        if (!this.appointments.length) {
            Modals.alert({
                title: 'Brak wizyt do rozliczenia',
                message: 'Wszystkie przeszłe wizyty mają już ustawiony status końcowy.',
                type: 'success'
            });
            return;
        }
        this.showModal(this.appointments);
    },

    /**
     * Buduje i pokazuje modal.
     */
    showModal(appointments) {
        this.selections = {};
        this.original = {};
        this.total = appointments.length;
        appointments.forEach(apt => { this.original[apt.id] = apt.status; });

        const content = this.createModalContent(appointments);

        const overlay = Modals.show({
            title: 'Przeszłe wizyty do rozliczenia',
            content: content,
            size: 'large',
            closeOnOverlay: false,
            buttons: [
                {
                    // ###3 — lewy przycisk: ustaw wszystkie na "zakończona"
                    text: 'Wszystkie na zakończone',
                    type: 'secondary',
                    onClick: (e, ov) => this.markAllCompleted()
                },
                {
                    text: 'Pomiń',
                    type: 'secondary',
                    onClick: (e, ov) => Modals.close(ov)
                },
                {
                    // ###4 — aktywny dopiero po pierwszej zmianie statusu
                    text: 'Zapisz zmiany',
                    type: 'primary',
                    disabled: true,
                    onClick: (e, ov) => this.saveChanges(ov)
                }
            ]
        });
        this.modalOverlay = overlay;

        // ###5 — usuń ikonę zamknięcia (X) w prawym górnym rogu (tylko ten modal)
        const closeBtn = overlay.querySelector('.modal-close');
        if (closeBtn) closeBtn.remove();

        // Licznik postępu zmian w prawym górnym rogu nagłówka ("3/7")
        const header = overlay.querySelector('.modal-header');
        if (header) {
            const prog = document.createElement('span');
            prog.className = 'pv-progress';
            prog.id = 'pv-progress';
            prog.setAttribute('aria-live', 'polite');
            prog.textContent = `0/${this.total}`;
            header.appendChild(prog);
        }

        // Referencje do przycisków stopki (kolejność = jak w buttons[])
        const footerBtns = overlay.querySelectorAll('.modal-footer button');
        this.bulkBtn = footerBtns[0] || null;
        this.saveBtn = footerBtns[2] || null;
        // ###3 — wyrównaj przycisk zbiorczy do lewej krawędzi stopki
        if (this.bulkBtn) this.bulkBtn.style.marginRight = 'auto';

        this.attachInteractions(overlay);
        this.updateControls();
    },

    /**
     * Treść modala: notka + tabela (desktop) + karty (mobile).
     */
    createModalContent(appointments) {
        const rows = appointments.map(apt => this.createTableRow(apt)).join('');
        const cards = appointments.map(apt => this.createCard(apt)).join('');

        return `
            <div class="pv-note">Zaktualizuj status przeszłych wizyt.</div>

            <!-- Desktop: zwarta tabela mieszcząca się w modalu -->
            <div class="pv-desktop">
                <div class="pv-table-wrap">
                    <table class="pv-table">
                        <thead>
                            <tr>
                                <th>Klient</th>
                                <th>Pracownik</th>
                                <th>Data i godzina</th>
                                <th>Usługi</th>
                                <th class="pv-th-status">Status</th>
                            </tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            </div>

            <!-- Mobile: poziomo przewijane zwarte karty -->
            <div class="pv-mobile">
                <div class="pv-cards">${cards}</div>
            </div>
        `;
    },

    createTableRow(apt) {
        const currentStatus = apt.status;
        const currentLabel = this.STATUS_LABELS[currentStatus] || currentStatus;
        const currentVar = this.STATUS_VARS[currentStatus] || 'color-ink-muted';

        // "Data i godzina": data "dd mmmm" + godzina startu + czas trwania
        const dateLine = this.fmtDateMonth(apt.appointment_date);
        const startLine = this.fmtTime(apt.start_time);
        const mins = this.durationMinutes(apt.start_time, apt.end_time);
        // Czas trwania w jednej linii: "90min (1,5h)"
        const durLine = mins != null ? `${mins}min (${this.fmtHours(mins)}h)` : '';

        // Klient w dwóch liniach: imię (1. linia) / nazwisko (2. linia)
        const fullName = (apt.client_name || '').trim();
        const sp = fullName.indexOf(' ');
        const firstName = sp === -1 ? fullName : fullName.slice(0, sp);
        const lastName = sp === -1 ? '' : fullName.slice(sp + 1);

        // Pojedynczy przycisk cyklicznie przełączający status: każde kliknięcie
        // przechodzi do następnego statusu w pętli [aktualny → zakończona →
        // anulowana → nieobecność → aktualny ...]. Kolor i etykieta zmieniają się
        // płynnie (0,2s). Powrót do statusu pierwotnego = brak zmiany.
        return `
            <tr data-id="${apt.id}">
                <td class="pv-cell-name">
                    <span class="pv-name-first">${this.escapeHtml(firstName)}</span>
                    <span class="pv-name-last">${this.escapeHtml(lastName)}</span>
                </td>
                <td>${this.escapeHtml(apt.employee_name)}</td>
                <td class="pv-cell-dt">
                    <span class="pv-date">${dateLine}</span>
                    <span class="pv-time">${startLine}</span>
                    <span class="pv-dur">${durLine}</span>
                </td>
                <td class="pv-cell-services" title="${this.escapeHtml(apt.service_names || 'Brak')}">${this.escapeHtml(apt.service_names || 'Brak')}</td>
                <td class="pv-status-cell">
                    <button type="button" class="pv-cycle" data-id="${apt.id}"
                            style="${this.badgeStyle(currentVar)}"
                            aria-label="Zmień status — kliknij, aby przełączyć"
                            title="Kliknij, aby przełączyć status">
                        <span class="pv-cycle-label">${currentLabel}</span>
                        <span class="pv-cycle-icon" aria-hidden="true">↻</span>
                    </button>
                </td>
            </tr>
        `;
    },

    createCard(apt) {
        const initials = this.initials(apt.employee_name);
        const mins = this.durationMinutes(apt.start_time, apt.end_time);
        const durPart = mins != null ? ` · ${mins}min` : '';
        const dt = `${this.fmtDateMonth(apt.appointment_date)}, ${this.fmtTime(apt.start_time)}${durPart}`;

        const toggles = this.RESOLUTIONS.map(s => `
            <button type="button" class="pv-toggle-btn" data-id="${apt.id}" data-status="${s}"
                    aria-pressed="false">
                ${this.STATUS_LABELS_SHORT[s]}
            </button>
        `).join('');

        return `
            <div class="pv-card" data-id="${apt.id}">
                <div class="pv-card-name" title="${this.escapeHtml(apt.client_name)}">${this.escapeHtml(apt.client_name)}</div>
                <div class="pv-card-service" title="${this.escapeHtml(apt.service_names || 'Brak usługi')}">${this.escapeHtml(apt.service_names || 'Brak usługi')}</div>
                <div class="pv-card-meta">
                    <span class="pv-card-initials" title="${this.escapeHtml(apt.employee_name)}">${initials}</span>
                    <span class="pv-card-dt">${dt}</span>
                </div>
                <div class="pv-card-toggle" role="group" aria-label="Status wizyty">${toggles}</div>
            </div>
        `;
    },

    /**
     * Delegacja zdarzeń wewnątrz modala (działa dla desktop i mobile).
     */
    attachInteractions(overlay) {
        const body = overlay.querySelector('.modal-body');
        if (!body) return;

        body.addEventListener('click', (e) => {
            // Desktop: pojedynczy przycisk cyklicznie zmieniający status
            const cycle = e.target.closest('.pv-cycle');
            if (cycle) {
                this.cycleStatus(cycle.dataset.id);
                return;
            }
            // Mobile: 3-pozycyjny przełącznik (wybór bezpośredni)
            const toggle = e.target.closest('.pv-toggle-btn');
            if (toggle) {
                this.selectStatus(toggle.dataset.id, toggle.dataset.status);
                return;
            }
        });
    },

    /**
     * Przechodzi do następnego statusu w pętli [pierwotny → completed →
     * cancelled → no_show → pierwotny ...]. Powrót na status pierwotny cofa zmianę.
     */
    cycleStatus(id) {
        const cycle = [this.original[id], ...this.RESOLUTIONS];
        const current = this.selections[id] || this.original[id];
        const idx = cycle.indexOf(current);
        const next = cycle[(idx + 1) % cycle.length];
        if (next === this.original[id]) {
            delete this.selections[id]; // pełna pętla = brak zmiany
        } else {
            this.selections[id] = next;
        }
        this.updateRowVisual(id);
        this.updateControls();
    },

    /**
     * Ustawia (lub cofa) wybór statusu dla danej wizyty i synchronizuje oba widoki.
     */
    selectStatus(id, status) {
        if (this.selections[id] === status) {
            delete this.selections[id]; // ponowne kliknięcie = cofnięcie wyboru
        } else {
            this.selections[id] = status;
        }
        this.updateRowVisual(id);
        this.updateControls();
    },

    updateRowVisual(id) {
        const selected = this.selections[id];

        // --- Desktop: przycisk cyklicznie zmieniający status (płynna zmiana koloru) ---
        const cycleBtn = this.modalOverlay.querySelector(`.pv-cycle[data-id="${id}"]`);
        if (cycleBtn) {
            const status = selected || this.original[id];
            const label = this.STATUS_LABELS[status] || status;
            const varName = this.STATUS_VARS[status] || 'color-ink-muted';
            // Zachowaj ikonę-podpowiedź; podmień tylko kolory (cssText nie rusza
            // właściwości transition, która żyje w arkuszu — animacja 0,2s działa).
            cycleBtn.style.cssText = this.badgeStyle(varName);
            const labelEl = cycleBtn.querySelector('.pv-cycle-label');
            if (labelEl) labelEl.textContent = label;
            cycleBtn.classList.toggle('pv-cycle--changed', !!selected);
        }

        // --- Mobile: przełącznik 3-pozycyjny ---
        this.modalOverlay.querySelectorAll(`.pv-toggle-btn[data-id="${id}"]`).forEach(btn => {
            const active = btn.dataset.status === selected;
            btn.classList.toggle('pv-toggle-btn--active', active);
            btn.setAttribute('aria-pressed', active ? 'true' : 'false');
            if (active) {
                btn.style.cssText = this.badgeStyle(this.STATUS_VARS[selected]);
            } else {
                btn.style.cssText = '';
            }
        });
        const card = this.modalOverlay.querySelector(`.pv-card[data-id="${id}"]`);
        if (card) card.classList.toggle('pv-card--changed', !!selected);
    },

    /**
     * ###3 — ustawia wszystkie wizyty na "zakończona" (użytkownik może nadal
     * zmienić pojedyncze ręcznie).
     */
    markAllCompleted() {
        this.appointments.forEach(apt => {
            this.selections[apt.id] = 'completed';
            this.updateRowVisual(apt.id);
        });
        this.updateControls();
    },

    /**
     * Aktualizuje licznik postępu i aktywność przycisku zapisu.
     */
    updateControls() {
        const changed = Object.keys(this.selections).length;
        const prog = this.modalOverlay && this.modalOverlay.querySelector('#pv-progress');
        if (prog) prog.textContent = `${changed}/${this.total}`;
        if (this.saveBtn) this.saveBtn.disabled = changed === 0;
    },

    /**
     * Zapisuje wybrane statusy (PUT na każdą zmienioną wizytę).
     */
    async saveChanges(overlay) {
        const changes = Object.entries(this.selections)
            .map(([id, status]) => ({ appointmentId: parseInt(id, 10), status }));

        if (changes.length === 0) return; // przycisk i tak jest wtedy nieaktywny

        if (this.saveBtn) {
            this.saveBtn.dataset.label = this.saveBtn.textContent;
            this.saveBtn.textContent = 'Zapisywanie...';
            this.saveBtn.disabled = true;
        }
        if (this.bulkBtn) this.bulkBtn.disabled = true;

        let successCount = 0;
        let errorCount = 0;

        for (const change of changes) {
            try {
                const response = await fetch(`/api/appointments/${change.appointmentId}/past-status`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: change.status })
                });
                const data = await response.json();
                if (data.success) {
                    successCount++;
                } else {
                    errorCount++;
                    console.error(`Błąd przy aktualizacji wizyty ${change.appointmentId}:`, data.error);
                }
            } catch (error) {
                errorCount++;
                console.error(`Błąd przy aktualizacji wizyty ${change.appointmentId}:`, error);
            }
        }

        if (successCount > 0) {
            Modals.close(overlay);
            Modals.alert({
                title: successCount === changes.length ? 'Sukces' : 'Częściowy sukces',
                message: `Zaktualizowano ${successCount} wizyt(y).${errorCount > 0 ? ` Błędów: ${errorCount}` : ''}`,
                type: errorCount > 0 ? 'warning' : 'success',
                onClose: () => window.location.reload()
            });
        } else {
            Modals.alert({
                title: 'Błąd',
                message: 'Nie udało się zapisać zmian. Spróbuj ponownie.',
                type: 'error'
            });
            if (this.saveBtn) {
                this.saveBtn.textContent = this.saveBtn.dataset.label || 'Zapisz zmiany';
                this.saveBtn.disabled = false;
            }
            if (this.bulkBtn) this.bulkBtn.disabled = false;
        }
    },

    // ── Helpery ────────────────────────────────────────────────────────────────

    /** Styl badge'a/wyboru w kolorze statusu (zgodny z typologią badge'y). */
    badgeStyle(varName) {
        return `background:${cssVarAlpha(varName, 0.12)};color:${cssVar(varName)};border:1px solid ${cssVarAlpha(varName, 0.35)};`;
    },

    /**
     * 'YYYY-MM-DD' → 'd mmmm' po polsku, np. '22 czerwca'
     * (parsowanie po częściach, bez stref czasowych — patrz reguła date-formatting).
     */
    fmtDateMonth(dateStr) {
        if (!dateStr) return '';
        const [, m, d] = String(dateStr).split('-').map(Number);
        const month = this.MONTHS_PL[m - 1] || '';
        return `${d} ${month}`.trim();
    },

    /** 'HH:MM:SS' / 'HH:MM' → 'HH:MM'. */
    fmtTime(timeStr) {
        if (!timeStr) return '';
        return String(timeStr).slice(0, 5);
    },

    /** Czas trwania wizyty w minutach (start→koniec). null gdy brak danych. */
    durationMinutes(startStr, endStr) {
        if (!startStr || !endStr) return null;
        const toMin = (t) => {
            const [h, m] = String(t).split(':').map(Number);
            if (Number.isNaN(h) || Number.isNaN(m)) return null;
            return h * 60 + m;
        };
        const a = toMin(startStr), b = toMin(endStr);
        if (a == null || b == null) return null;
        let diff = b - a;
        if (diff < 0) diff += 24 * 60; // zabezpieczenie na wizyty przez północ
        return diff;
    },

    /** Minuty → godziny z polskim przecinkiem, bez zbędnych zer: 90 → '1,5', 60 → '1'. */
    fmtHours(minutes) {
        const h = Math.round((minutes / 60) * 100) / 100;
        return String(h).replace('.', ',');
    },

    /** Inicjały pracownika (maks. 2 litery). */
    initials(name) {
        if (!name) return '—';
        const parts = name.trim().split(/\s+/).filter(Boolean);
        if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    },

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// Udostępnij globalnie (pomocne do debugowania w konsoli)
window.PastVisitsScanner = PastVisitsScanner;

// Auto-inicjalizacja: podłącza trigger, NIE otwiera modala automatycznie.
PastVisitsScanner.init();
