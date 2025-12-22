/**
 * Invoice List Page JavaScript
 */

let invoicesData = [];
let currentSearch = '';

// Load invoices on page load
document.addEventListener('DOMContentLoaded', () => {
    loadInvoices();
    loadStatistics();
    setupEventListeners();
});

/**
 * Setup event listeners
 */
function setupEventListeners() {
    // Search input with debounce
    const searchInput = document.getElementById('search-input');
    searchInput.addEventListener('input', debounce((e) => {
        currentSearch = e.target.value;
        loadInvoices(currentSearch);
    }, 500));

    // Import PDF button
    const importPdfBtn = document.getElementById('import-pdf-btn');
    const quickUploadInput = document.getElementById('quick-upload-input');

    importPdfBtn.addEventListener('click', () => {
        quickUploadInput.click();
    });

    quickUploadInput.addEventListener('change', (e) => {
        handleQuickUpload(e.target.files);
    });

    // Export menu toggle
    const exportBtn = document.getElementById('export-btn');
    const exportMenu = document.getElementById('export-menu');

    exportBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        exportMenu.classList.toggle('hidden');
    });

    // Close export menu when clicking outside
    document.addEventListener('click', () => {
        exportMenu.classList.add('hidden');
    });

    exportMenu.addEventListener('click', (e) => {
        e.stopPropagation();
    });
}

/**
 * Load invoices from API
 */
async function loadInvoices(searchQuery = '') {
    try {
        const data = await API.invoices.getAll(searchQuery);

        if (data.success) {
            invoicesData = data.invoices;
            renderInvoicesTable();
        } else {
            Notifications.error('Błąd ładowania faktur');
        }
    } catch (error) {
        console.error('Error loading invoices:', error);
        Notifications.error('Błąd ładowania faktur: ' + error.message);
    }
}

/**
 * Calculate net amount (amount / 1.23)
 */
function calculateNetAmount(grossAmount) {
    return grossAmount / 1.23;
}

/**
 * Calculate VAT amount (amount * 23/123)
 */
function calculateVatAmount(grossAmount) {
    return grossAmount * (23 / 123);
}

/**
 * Load statistics from API
 */
async function loadStatistics() {
    try {
        const data = await API.invoices.getStatistics();

        if (data.success) {
            const stats = data.statistics;

            document.getElementById('stat-total').textContent = stats.total_invoices || 0;
            document.getElementById('stat-paid').textContent = stats.paid_invoices || 0;
            document.getElementById('stat-unpaid').textContent = stats.unpaid_invoices || 0;

            // totals.total_amount is nested in the stats object
            const totalGross = stats.totals?.total_amount || 0;
            const totalNet = calculateNetAmount(totalGross);
            const totalVat = calculateVatAmount(totalGross);

            document.getElementById('stat-amount-gross').textContent = formatCurrency(totalGross, 'PLN');
            document.getElementById('stat-amount-net').textContent = formatCurrency(totalNet, 'PLN');
            document.getElementById('stat-amount-vat').textContent = formatCurrency(totalVat, 'PLN');
        }
    } catch (error) {
        console.error('Error loading statistics:', error);
    }
}

/**
 * Render invoices table
 */
function renderInvoicesTable() {
    const tbody = document.getElementById('invoices-tbody');
    const emptyState = document.getElementById('empty-state');

    if (invoicesData.length === 0) {
        tbody.innerHTML = '';
        emptyState.classList.remove('hidden');
        return;
    }

    emptyState.classList.add('hidden');

    tbody.innerHTML = invoicesData.map(invoice => {
        // Format OCR confidence badge
        const ocrConfidence = invoice.ocr_confidence || 0;
        let ocrBadgeClass = 'badge-error';
        if (ocrConfidence >= 80) ocrBadgeClass = 'badge-success';
        else if (ocrConfidence >= 60) ocrBadgeClass = 'badge-warning';

        // Format status badge
        const statusBadgeClass = invoice.status === 'Opłacona' ? 'badge-success' :
            invoice.status === 'Przeterminowana' ? 'badge-error' :
                'badge-warning';

        // Calculate net and VAT amounts
        const grossAmount = invoice.amount || 0;
        const netAmount = calculateNetAmount(grossAmount);
        const vatAmount = calculateVatAmount(grossAmount);

        return `
            <tr class="hover:bg-gray-50 transition-colors">
                <td class="font-medium">${escapeHtml(invoice.invoice_number || '-')}</td>
                <td>${escapeHtml(invoice.seller_name || '-')}</td>
                <td>${escapeHtml(invoice.seller_nip || '-')}</td>
                <td>${formatDate(invoice.invoice_date)}</td>
                <td>${invoice.payment_due_date ? formatDate(invoice.payment_due_date) :
                (invoice.payment_term ? escapeHtml(invoice.payment_term) : '-')}</td>
                <td class="font-semibold text-gross">${formatCurrency(grossAmount, invoice.currency)}</td>
                <td>
                    <span class="badge ${statusBadgeClass}">
                        ${escapeHtml(invoice.status || 'Nieznany')}
                    </span>
                </td>
                <td>
                    <span class="badge ${ocrBadgeClass}">
                        ${Math.round(ocrConfidence)}%
                    </span>
                </td>
                <td>
                    <div class="flex items-center gap-2">
                        ${invoice.pdf_path ? `
                            <button onclick="viewPDF(${invoice.id})"
                                    class="text-primary hover:text-primary-700 transition-colors"
                                    title="Zobacz PDF">
                                <span class="material-icons text-sm">picture_as_pdf</span>
                            </button>
                        ` : ''}
                        <a href="/invoice/${invoice.id}/edit"
                           class="text-primary hover:text-primary-600 transition-colors"
                           title="Edytuj">
                            <span class="material-icons text-sm">edit</span>
                        </a>
                        <button onclick="deleteInvoice(${invoice.id})"
                                class="text-status-error hover:text-red-700 transition-colors"
                                title="Usuń">
                            <span class="material-icons text-sm">delete</span>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

/**
 * View PDF
 */
function viewPDF(invoiceId) {
    API.pdf.view(invoiceId);
}

/**
 * Delete invoice
 */
function deleteInvoice(invoiceId) {
    const invoice = invoicesData.find(inv => inv.id === invoiceId);

    Modals.confirm({
        title: 'Usuń fakturę',
        message: `Czy na pewno chcesz usunąć fakturę ${invoice?.invoice_number || invoiceId}?`,
        confirmText: 'Usuń',
        cancelText: 'Anuluj',
        onConfirm: async () => {
            const loadingModal = Modals.loading('Usuwanie faktury...');

            try {
                const result = await API.invoices.delete(invoiceId);

                Modals.close(loadingModal);

                if (result.success) {
                    Notifications.success('Faktura została usunięta');
                    loadInvoices(currentSearch);
                    loadStatistics();
                } else {
                    Notifications.error('Błąd usuwania faktury');
                }
            } catch (error) {
                Modals.close(loadingModal);
                console.error('Error deleting invoice:', error);
                Notifications.error('Błąd usuwania faktury: ' + error.message);
            }
        }
    });
}

/**
 * Export to Excel
 */
function exportToExcel() {
    try {
        API.export.toExcel();
        Notifications.success('Eksportowanie do Excel...');
    } catch (error) {
        Notifications.error('Błąd eksportu: ' + error.message);
    }
}

/**
 * Export to CSV
 */
function exportToCSV() {
    try {
        API.export.toCSV();
        Notifications.success('Eksportowanie do CSV...');
    } catch (error) {
        Notifications.error('Błąd eksportu: ' + error.message);
    }
}

/**
 * Handle quick upload from main page
 */
async function handleQuickUpload(files) {
    const pdfFiles = Array.from(files).filter(file => file.type === 'application/pdf');

    if (pdfFiles.length === 0) {
        Notifications.warning('Proszę wybrać pliki PDF');
        return;
    }

    const loadingModal = Modals.loading(`Przetwarzanie ${pdfFiles.length} plik(ów)...`);

    try {
        const result = await API.upload.files(pdfFiles, (percent) => {
            // Progress callback - could update modal if needed
            console.log(`Upload progress: ${percent}%`);
        });

        Modals.close(loadingModal);

        if (result.success) {
            const successCount = result.results.filter(r => r.success && r.saved).length;
            const errorCount = result.results.filter(r => !r.success).length;

            if (errorCount === 0) {
                Notifications.success(`Pomyślnie zaimportowano ${successCount} faktur`);
            } else {
                Notifications.warning(`Zaimportowano ${successCount} faktur, ${errorCount} z błędami`);
            }

            // Reload invoices and statistics
            loadInvoices(currentSearch);
            loadStatistics();

            // Clear file input
            document.getElementById('quick-upload-input').value = '';
        } else {
            Notifications.error('Błąd przetwarzania plików');
        }
    } catch (error) {
        Modals.close(loadingModal);
        console.error('Upload error:', error);
        Notifications.error('Błąd przesyłania plików: ' + error.message);

        // Clear file input
        document.getElementById('quick-upload-input').value = '';
    }
}
