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
 * Load statistics from API
 */
async function loadStatistics() {
    try {
        const data = await API.invoices.getStatistics();

        if (data.success) {
            const stats = data.statistics;

            document.getElementById('stat-total').textContent = stats.total_invoices;
            document.getElementById('stat-paid').textContent = stats.paid_invoices;
            document.getElementById('stat-unpaid').textContent = stats.unpaid_invoices;
            document.getElementById('stat-amount').textContent = formatCurrency(stats.total_amount, 'PLN');
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

    tbody.innerHTML = invoicesData.map(invoice => `
        <tr class="hover:bg-gray-50 transition-colors">
            <td class="font-medium">${escapeHtml(invoice.invoice_number || '-')}</td>
            <td>${escapeHtml(invoice.seller_name || '-')}</td>
            <td>${escapeHtml(invoice.seller_nip || '-')}</td>
            <td>${formatDate(invoice.issue_date)}</td>
            <td>${formatCurrency(invoice.net_amount, invoice.currency)}</td>
            <td>${formatCurrency(invoice.vat_amount, invoice.currency)}</td>
            <td class="font-semibold">${formatCurrency(invoice.total_amount, invoice.currency)}</td>
            <td>${escapeHtml(invoice.currency || 'PLN')}</td>
            <td>
                <span class="badge ${invoice.payment_status === 'Zapłacona' ? 'badge-success' : 'badge-warning'}">
                    ${escapeHtml(invoice.payment_status || 'Nieznany')}
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
                       class="text-blue-600 hover:text-blue-800 transition-colors"
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
    `).join('');
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
