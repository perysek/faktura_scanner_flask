/**
 * Past Visits Scanner
 *
 * Skanuje przeszłe wizyty z nieukończonym statusem przy załadowaniu widoków wizyt.
 * Wyświetla modal z listą wizyt do aktualizacji statusu.
 */

const PastVisitsScanner = {
    /**
     * Inicjalizuje skaner i wywołuje skanowanie przy załadowaniu strony
     */
    init() {
        // Czekaj na DOMContentLoaded jeśli dokument nie jest jeszcze gotowy
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.scan());
        } else {
            this.scan();
        }
    },

    /**
     * Skanuje przeszłe wizyty z nieukończonym statusem
     */
    async scan() {
        try {
            const response = await fetch('/api/appointments/past-pending');
            const data = await response.json();

            if (!data.success) {
                console.error('Błąd podczas skanowania przeszłych wizyt:', data.error);
                return;
            }

            // Jeśli są przeszłe wizyty do aktualizacji, pokaż modal
            if (data.appointments && data.appointments.length > 0) {
                this.showModal(data.appointments);
            }
        } catch (error) {
            console.error('Błąd podczas skanowania przeszłych wizyt:', error);
        }
    },

    /**
     * Wyświetla modal z listą przeszłych wizyt
     */
    showModal(appointments) {
        const content = this.createModalContent(appointments);

        const modalOverlay = Modals.show({
            title: `Przeszłe wizyty do zaktualizowania (${appointments.length})`,
            content: content,
            size: 'large',
            closeOnOverlay: false,
            buttons: [
                {
                    text: 'Pomiń',
                    type: 'secondary',
                    onClick: (e, overlay) => {
                        Modals.close(overlay);
                    }
                },
                {
                    text: 'Zapisz zmiany',
                    type: 'primary',
                    onClick: async (e, overlay) => {
                        await this.saveChanges(overlay);
                    }
                }
            ]
        });

        // Dodaj event listenery dla dropdownów
        this.attachDropdownListeners(modalOverlay, appointments);
    },

    /**
     * Tworzy zawartość HTML modala
     */
    createModalContent(appointments) {
        return `
            <div style="margin-bottom: 1rem; padding: 0.75rem; background: var(--color-warning-bg, #fffbeb); border: 1px solid var(--color-warning-border, #fcd34d); border-radius: 2px;">
                <p style="font-size: 0.875rem; color: var(--color-warning, #78350f); margin: 0;">
                    <strong>Uwaga:</strong> Poniższe wizyty zakończyły się, ale nie mają jeszcze finalnego statusu.
                    Wybierz odpowiedni status dla każdej wizyty.
                </p>
            </div>

            <div style="max-height: 500px; overflow-y: auto;">
                <table class="refined-table" style="width: 100%; border-collapse: collapse;">
                    <thead style="position: sticky; top: 0; background: var(--color-surface); z-index: 10;">
                        <tr>
                            <th style="padding: 0.75rem; text-align: left; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-ink-muted); border-bottom: 1px solid var(--color-border);">Klient</th>
                            <th style="padding: 0.75rem; text-align: left; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-ink-muted); border-bottom: 1px solid var(--color-border);">Pracownik</th>
                            <th style="padding: 0.75rem; text-align: left; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-ink-muted); border-bottom: 1px solid var(--color-border);">Data</th>
                            <th style="padding: 0.75rem; text-align: left; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-ink-muted); border-bottom: 1px solid var(--color-border);">Godzina</th>
                            <th style="padding: 0.75rem; text-align: left; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-ink-muted); border-bottom: 1px solid var(--color-border);">Usługi</th>
                            <th style="padding: 0.75rem; text-align: left; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-ink-muted); border-bottom: 1px solid var(--color-border);">Obecny status</th>
                            <th style="padding: 0.75rem; text-align: left; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-ink-muted); border-bottom: 1px solid var(--color-border);">Nowy status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${appointments.map(apt => this.createTableRow(apt)).join('')}
                    </tbody>
                </table>
            </div>
        `;
    },

    /**
     * Tworzy wiersz tabeli dla wizyty
     */
    createTableRow(appointment) {
        const statusLabels = {
            'scheduled': 'Zaplanowana',
            'confirmed': 'Potwierdzona',
            'in_progress': 'W trakcie'
        };

        const statusBadges = {
            'scheduled': `background: ${cssVarAlpha('color-status-scheduled', 0.08)}; color: ${cssVar('color-status-scheduled')};`,
            'confirmed': `background: ${cssVarAlpha('color-status-confirmed', 0.08)}; color: ${cssVar('color-status-confirmed')};`,
            'in_progress': `background: ${cssVarAlpha('color-status-in-progress', 0.08)}; color: ${cssVar('color-status-in-progress')};`
        };

        const currentStatusLabel = statusLabels[appointment.status] || appointment.status;
        const currentStatusStyle = statusBadges[appointment.status] || '';

        const formattedDate = this.formatDate(appointment.appointment_date);
        const formattedTime = `${this.formatTime(appointment.start_time)} - ${this.formatTime(appointment.end_time)}`;

        return `
            <tr data-appointment-id="${appointment.id}" style="border-bottom: 1px solid var(--color-border-subtle);">
                <td style="padding: 0.75rem; font-size: 0.875rem; color: var(--color-ink);">${this.escapeHtml(appointment.client_name)}</td>
                <td style="padding: 0.75rem; font-size: 0.875rem; color: var(--color-ink);">${this.escapeHtml(appointment.employee_name)}</td>
                <td style="padding: 0.75rem; font-size: 0.875rem; color: var(--color-ink);">${formattedDate}</td>
                <td style="padding: 0.75rem; font-size: 0.875rem; color: var(--color-ink); white-space: nowrap;">${formattedTime}</td>
                <td style="padding: 0.75rem; font-size: 0.875rem; color: var(--color-ink-muted); max-width: 200px; overflow: hidden; text-overflow: ellipsis;" title="${this.escapeHtml(appointment.service_names || 'Brak')}">${this.escapeHtml(appointment.service_names || 'Brak')}</td>
                <td style="padding: 0.75rem;">
                    <span style="display: inline-block; padding: 0.25rem 0.625rem; font-size: 0.75rem; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; border-radius: 2px; ${currentStatusStyle}">
                        ${currentStatusLabel}
                    </span>
                </td>
                <td style="padding: 0.75rem;">
                    <select
                        class="status-dropdown"
                        data-appointment-id="${appointment.id}"
                        style="padding: 0.5rem 0.75rem; font-size: 0.875rem; border: 1px solid var(--color-border); border-radius: 2px; background: white; color: var(--color-ink); width: 100%; max-width: 180px; cursor: pointer;"
                    >
                        <option value="">-- Wybierz --</option>
                        <option value="completed">Zakończona</option>
                        <option value="cancelled">Anulowana</option>
                        <option value="no_show">Nieobecność klienta</option>
                    </select>
                </td>
            </tr>
        `;
    },

    /**
     * Dodaje event listenery dla dropdownów
     */
    attachDropdownListeners(modalOverlay, appointments) {
        const dropdowns = modalOverlay.querySelectorAll('.status-dropdown');

        dropdowns.forEach(dropdown => {
            dropdown.addEventListener('change', (e) => {
                const appointmentId = e.target.dataset.appointmentId;
                const newStatus = e.target.value;

                // Zapisz wybór w pamięci (data attribute)
                e.target.dataset.selectedStatus = newStatus;

                // Wizualna informacja o zmianie
                const row = e.target.closest('tr');
                if (newStatus) {
                    row.style.background = '#f0fdf4'; // Zielone tło dla wierszy ze zmianą
                } else {
                    row.style.background = '';
                }
            });
        });
    },

    /**
     * Zapisuje zmiany statusów
     */
    async saveChanges(modalOverlay) {
        const dropdowns = modalOverlay.querySelectorAll('.status-dropdown');
        const changes = [];

        // Zbierz wszystkie zmiany
        dropdowns.forEach(dropdown => {
            const newStatus = dropdown.value;
            if (newStatus) {
                changes.push({
                    appointmentId: parseInt(dropdown.dataset.appointmentId),
                    status: newStatus
                });
            }
        });

        if (changes.length === 0) {
            Modals.alert({
                title: 'Uwaga',
                message: 'Nie wybrano żadnych zmian statusu.',
                type: 'warning'
            });
            return;
        }

        // Wyświetl loading
        const saveButton = modalOverlay.querySelector('.modal-footer button:last-child');
        const originalText = saveButton.textContent;
        saveButton.textContent = 'Zapisywanie...';
        saveButton.disabled = true;

        try {
            // Zapisz każdą zmianę osobno
            let successCount = 0;
            let errorCount = 0;

            for (const change of changes) {
                try {
                    const response = await fetch(`/api/appointments/${change.appointmentId}/past-status`, {
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            status: change.status
                        })
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

            // Pokaż wynik
            if (successCount > 0) {
                Modals.alert({
                    title: successCount === changes.length ? 'Sukces' : 'Częściowy sukces',
                    message: `Zaktualizowano ${successCount} wizyt(y).${errorCount > 0 ? ` Błędów: ${errorCount}` : ''}`,
                    type: errorCount > 0 ? 'warning' : 'success',
                    onClose: () => window.location.reload()
                });
            }

            // Zamknij modal (odświeżenie nastąpi w onClose)
        } catch (error) {
            console.error('Błąd podczas zapisywania zmian:', error);
            Modals.alert({
                title: 'Błąd',
                message: 'Wystąpił błąd podczas zapisywania zmian.',
                type: 'error'
            });
            saveButton.textContent = originalText;
            saveButton.disabled = false;
        }
    },

    /**
     * Formatuje datę do formatu DD.MM.YYYY
     */
    formatDate(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr + 'T00:00:00'); // Add time to avoid timezone issues
        const day = String(date.getDate()).padStart(2, '0');
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const year = date.getFullYear();
        return `${day}.${month}.${year}`;
    },

    /**
     * Formatuje czas do formatu HH:MM
     */
    formatTime(timeStr) {
        if (!timeStr) return '';
        // Input: "09:00:00" or "09:00"
        const parts = timeStr.split(':');
        return `${parts[0]}:${parts[1]}`;
    },

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// Auto-inicjalizacja przy załadowaniu strony
PastVisitsScanner.init();
