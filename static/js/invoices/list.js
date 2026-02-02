/**
 * Invoice List Page JavaScript
 * Enhanced with collapsible search and micro-interactions
 */

let invoicesData = [];
let filteredData = [];
let currentSearch = '';
let searchFilters = {};
let isSearchVisible = false;

// Load invoices on page load
document.addEventListener('DOMContentLoaded', () => {
    loadInvoices();
    setupEventListeners();
    restoreSearchState();
});

/**
 * Setup event listeners
 */
function setupEventListeners() {
    // Export menu toggle
    const exportBtn = document.getElementById('export-btn');
    const exportMenu = document.getElementById('export-menu');

    if (exportBtn && exportMenu) {
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

    // Keyboard shortcut for search toggle (Ctrl+F or /)
    document.addEventListener('keydown', (e) => {
        // Skip if user is typing in an input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') {
            // Allow Escape to close search even when in input
            if (e.key === 'Escape' && isSearchVisible) {
                toggleTableSearch();
            }
            return;
        }

        if (e.key === '/' || (e.ctrlKey && e.key === 'f')) {
            e.preventDefault();
            toggleTableSearch();
            // Focus first search input if showing
            if (isSearchVisible) {
                setTimeout(() => {
                    const firstInput = document.getElementById('search-invoice-number');
                    if (firstInput) firstInput.focus();
                }, 100);
            }
        }
    });
}

/**
 * Toggle table search row visibility
 */
function toggleTableSearch() {
    const searchRow = document.getElementById('table-search-row');
    const toggleBtn = document.getElementById('toggle-search-btn');

    if (!searchRow) return;

    isSearchVisible = !isSearchVisible;

    if (isSearchVisible) {
        // Show search row with animation
        searchRow.classList.remove('hidden', 'search-row-exit');
        searchRow.classList.add('search-row-enter');

        // Update button state
        if (toggleBtn) {
            toggleBtn.classList.add('bg-primary-50', 'text-primary-600');
            toggleBtn.classList.remove('text-slate-600');
        }

        // Focus first input
        setTimeout(() => {
            const firstInput = document.getElementById('search-invoice-number');
            if (firstInput) firstInput.focus();
        }, 50);
    } else {
        // Hide search row with animation
        searchRow.classList.remove('search-row-enter');
        searchRow.classList.add('search-row-exit');

        setTimeout(() => {
            searchRow.classList.add('hidden');
            searchRow.classList.remove('search-row-exit');
        }, 200);

        // Update button state
        if (toggleBtn) {
            toggleBtn.classList.remove('bg-primary-50', 'text-primary-600');
            toggleBtn.classList.add('text-slate-600');
        }
    }

    // Save state to localStorage
    localStorage.setItem('invoiceListSearchVisible', isSearchVisible);
}

/**
 * Restore search state from localStorage
 */
function restoreSearchState() {
    const savedVisible = localStorage.getItem('invoiceListSearchVisible');
    const savedFilters = localStorage.getItem('invoiceListFilters');

    if (savedVisible === 'true') {
        toggleTableSearch();
    }

    if (savedFilters) {
        try {
            searchFilters = JSON.parse(savedFilters);
            // Restore filter values to inputs
            Object.keys(searchFilters).forEach(key => {
                const input = document.getElementById(key);
                if (input && searchFilters[key]) {
                    input.value = searchFilters[key];
                }
            });
        } catch (e) {
            console.error('Error restoring filters:', e);
        }
    }
}

/**
 * Filter table by column
 * @param {HTMLElement} input - The input element
 * @param {number} columnIndex - Column index to filter
 */
function filterTableColumn(input, columnIndex) {
    const value = input.value.trim();
    const inputId = input.id;

    // Store filter value
    if (value) {
        searchFilters[inputId] = value;
    } else {
        delete searchFilters[inputId];
    }

    // Save to localStorage
    localStorage.setItem('invoiceListFilters', JSON.stringify(searchFilters));

    // Apply all filters
    applyFilters();

    // Update active filters badge
    updateActiveFiltersBadge();
}

/**
 * Apply all active filters to the data
 */
function applyFilters() {
    const tbody = document.getElementById('invoices-tbody');
    const rows = tbody.querySelectorAll('tr[data-invoice-id]');

    rows.forEach(row => {
        let visible = true;

        // Check each filter
        Object.keys(searchFilters).forEach(filterId => {
            const filterValue = searchFilters[filterId].toLowerCase();
            if (!filterValue) return;

            // Map filter ID to column index
            const columnMap = {
                'search-invoice-number': 0,
                'search-seller': 1,
                'search-nip': 2,
                'search-date': 3,
                'search-due-date': 4,
                'search-amount': 5,
                'search-status': 6
            };

            const colIndex = columnMap[filterId];
            if (colIndex === undefined) return;

            const cells = row.querySelectorAll('td');
            const cellText = cells[colIndex]?.textContent?.toLowerCase() || '';

            if (!cellText.includes(filterValue)) {
                visible = false;
            }
        });

        // Show/hide row with animation
        if (visible) {
            row.classList.remove('hidden');
            row.style.opacity = '1';
        } else {
            row.classList.add('hidden');
            row.style.opacity = '0';
        }
    });

    // Update visible count
    updateVisibleCount();
}

/**
 * Clear all filters
 */
function clearAllFilters() {
    searchFilters = {};
    localStorage.removeItem('invoiceListFilters');

    // Clear all search inputs
    const searchInputs = document.querySelectorAll('#table-search-row input, #table-search-row select');
    searchInputs.forEach(input => {
        input.value = '';
    });

    // Show all rows
    const tbody = document.getElementById('invoices-tbody');
    const rows = tbody.querySelectorAll('tr[data-invoice-id]');
    rows.forEach(row => {
        row.classList.remove('hidden');
        row.style.opacity = '1';
    });

    // Update badge and count
    updateActiveFiltersBadge();
    updateInvoiceCountBadge(invoicesData.length);

    Notifications.info('Filtry zostały wyczyszczone');
}

/**
 * Update active filters badge
 */
function updateActiveFiltersBadge() {
    const badge = document.getElementById('active-filters-badge');
    const countEl = document.getElementById('active-filters-count');
    const activeCount = Object.keys(searchFilters).filter(k => searchFilters[k]).length;

    if (badge && countEl) {
        if (activeCount > 0) {
            countEl.textContent = activeCount;
            badge.classList.remove('hidden');
            badge.classList.add('flex');
        } else {
            badge.classList.add('hidden');
            badge.classList.remove('flex');
        }
    }
}

/**
 * Update visible row count
 */
function updateVisibleCount() {
    const tbody = document.getElementById('invoices-tbody');
    const visibleRows = tbody.querySelectorAll('tr[data-invoice-id]:not(.hidden)').length;
    const totalRows = invoicesData.length;

    if (Object.keys(searchFilters).length > 0) {
        updateInvoiceCountBadge(visibleRows, totalRows);
    } else {
        updateInvoiceCountBadge(totalRows);
    }
}

/**
 * Update invoice count badge
 */
function updateInvoiceCountBadge(count, total = null) {
    const badge = document.getElementById('invoice-count-badge');
    if (badge) {
        if (total !== null && count !== total) {
            badge.innerHTML = `<span class="text-primary-600 font-semibold">${count}</span> / ${total} faktur`;
        } else {
            badge.textContent = `${count} faktur`;
        }
        // Add subtle animation
        badge.classList.add('counter-animate');
        setTimeout(() => badge.classList.remove('counter-animate'), 300);
    }
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

    // Update count badge
    updateInvoiceCountBadge(invoicesData.length);

    if (invoicesData.length === 0) {
        tbody.innerHTML = '';
        emptyState.classList.remove('hidden');
        return;
    }

    emptyState.classList.add('hidden');

    tbody.innerHTML = invoicesData.map((invoice, index) => {
        // Format OCR confidence badge
        const ocrConfidence = invoice.ocr_confidence || 0;
        let ocrBadgeClass = 'bg-red-100 text-red-700';
        let ocrIcon = 'error_outline';
        if (ocrConfidence >= 80) {
            ocrBadgeClass = 'bg-emerald-100 text-emerald-700';
            ocrIcon = 'check_circle';
        } else if (ocrConfidence >= 60) {
            ocrBadgeClass = 'bg-amber-100 text-amber-700';
            ocrIcon = 'warning';
        }

        // Format status badge with icon
        let statusBadgeClass, statusIcon;
        switch(invoice.status) {
            case 'Opłacona':
                statusBadgeClass = 'bg-emerald-100 text-emerald-700';
                statusIcon = 'check_circle';
                break;
            case 'Przeterminowana':
                statusBadgeClass = 'bg-red-100 text-red-700';
                statusIcon = 'warning';
                break;
            default:
                statusBadgeClass = 'bg-amber-100 text-amber-700';
                statusIcon = 'schedule';
        }

        // Calculate net and VAT amounts
        const grossAmount = invoice.amount || 0;

        // Stagger animation delay (max 10 items)
        const staggerDelay = Math.min(index, 10) * 0.02;

        return `
            <tr class="table-row-hover transition-colors border-b border-slate-100 last:border-0 group stagger-item"
                data-invoice-id="${invoice.id}"
                style="animation-delay: ${staggerDelay}s">
                <td class="px-6 py-3 font-medium text-slate-900">${escapeHtml(invoice.invoice_number || '-')}</td>
                <td class="px-6 py-3">
                    <div class="font-medium text-slate-700 truncate max-w-[200px]" title="${escapeHtml(invoice.seller_name || '')}">${escapeHtml(invoice.seller_name || '-')}</div>
                </td>
                <td class="px-6 py-3 text-slate-500 hidden md:table-cell font-mono text-xs">${escapeHtml(invoice.seller_nip || '-')}</td>
                <td class="px-6 py-3 text-slate-500">${formatDate(invoice.invoice_date)}</td>
                <td class="px-6 py-3 text-slate-500 hidden lg:table-cell">${invoice.payment_due_date ? formatDate(invoice.payment_due_date) :
                (invoice.payment_term ? `<span class="text-slate-400">${escapeHtml(invoice.payment_term)}</span>` : '-')}</td>
                <td class="px-6 py-3 font-semibold text-slate-900">${formatCurrency(grossAmount, invoice.currency)}</td>
                <td class="px-6 py-3">
                    <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-xs font-medium ${statusBadgeClass}">
                        <span class="material-icons text-xs">${statusIcon}</span>
                        ${escapeHtml(invoice.status || 'Nieznany')}
                    </span>
                </td>
                <td class="px-6 py-3 hidden xl:table-cell">
                    <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${ocrBadgeClass}">
                        ${Math.round(ocrConfidence)}%
                    </span>
                </td>
                <td class="px-6 py-3 text-right">
                    <div class="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        ${invoice.pdf_path ? (() => {
                const ext = invoice.pdf_path.split('.').pop().toLowerCase();
                const isImage = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'tif', 'webp'].includes(ext);
                const icon = isImage ? 'image' : 'picture_as_pdf';
                const title = isImage ? 'Obraz' : 'PDF';
                return `
                            <button onclick="viewPDF(${invoice.id})"
                                    class="p-1.5 rounded-lg text-slate-400 hover:text-primary-600 hover:bg-primary-50 transition-colors btn-press"
                                    title="${title}">
                                <span class="material-icons text-lg">${icon}</span>
                            </button>
                        `;
            })() : ''}
                        <a href="/invoice/${invoice.id}/edit"
                           class="p-1.5 rounded-lg text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 transition-colors btn-press"
                           title="Edytuj">
                            <span class="material-icons text-lg">edit</span>
                        </a>
                        <button onclick="deleteInvoice(${invoice.id})"
                                class="p-1.5 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors btn-press"
                                title="Usuń">
                            <span class="material-icons text-lg">delete</span>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');

    // Re-apply filters if any are active
    if (Object.keys(searchFilters).length > 0) {
        applyFilters();
    }
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
