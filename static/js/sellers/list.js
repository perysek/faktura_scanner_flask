/**
 * Sellers List Page JavaScript
 */

let sellersData = [];

// Load sellers on page load
document.addEventListener('DOMContentLoaded', () => {
    loadSellers();
    setupEventListeners();
});

/**
 * Setup event listeners
 */
function setupEventListeners() {
    // Sync button
    const syncBtn = document.getElementById('sync-btn');
    if (syncBtn) {
        syncBtn.addEventListener('click', syncSellers);
    }
}

/**
 * Load sellers from API
 */
async function loadSellers(searchQuery = '') {
    try {
        const data = await API.sellers.getAll(searchQuery);

        if (data.success) {
            sellersData = data.sellers;
            renderSellersTable();
        } else {
            Notifications.error(MSG('seller.list_load_failed'));
        }
    } catch (error) {
        console.error('Error loading sellers:', error);
        Notifications.error(MSG('seller.list_load_error') + error.message);
    }
}

/**
 * Render sellers table
 */
function renderSellersTable() {
    const tbody = document.getElementById('sellers-tbody');
    const emptyState = document.getElementById('empty-state');

    if (sellersData.length === 0) {
        tbody.innerHTML = '';
        emptyState.classList.remove('hidden');
        return;
    }

    emptyState.classList.add('hidden');

    tbody.innerHTML = sellersData.map(seller => {
        // Use actual_invoice_count if available, otherwise invoice_count
        const invoiceCount = seller.actual_invoice_count || seller.invoice_count || 0;
        const totalPaid = seller.total_paid || 0;
        const totalUnpaid = seller.total_unpaid || 0;

        // Format last updated date
        let lastUpdated = '-';
        if (seller.last_updated) {
            lastUpdated = formatDate(seller.last_updated);
        }

        return `
            <tr class="hover:bg-gray-50 transition-colors">
                <td class="font-mono">${escapeHtml(seller.seller_nip || '-')}</td>
                <td class="font-medium">${escapeHtml(seller.seller_name || '-')}</td>
                <td class="text-gray-600">${escapeHtml(seller.address || '-')}</td>
                <td class="text-center">
                    <span class="badge badge-info">${invoiceCount}</span>
                </td>
                <td class="text-right text-status-success font-medium">
                    ${formatCurrency(totalPaid, 'PLN')}
                </td>
                <td class="text-right text-status-error font-medium">
                    ${formatCurrency(totalUnpaid, 'PLN')}
                </td>
                <td class="text-gray-500">${lastUpdated}</td>
                <td>
                    <div class="flex items-center gap-2">
                        <a href="/seller/${seller.id}/edit"
                           class="table-action-btn table-action-btn-edit"
                           title="Edytuj">
                            ${Icons.svg('edit')}
                        </a>
                        <button onclick="confirmDeleteSeller(${seller.id})"
                                class="table-action-btn table-action-btn-delete"
                                title="Usun">
                            ${Icons.svg('delete')}
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

/**
 * Confirm and delete seller
 */
async function confirmDeleteSeller(sellerId) {
    const seller = sellersData.find(s => s.id === sellerId);
    if (!seller) return;

    // First fetch linked invoices
    const loadingModal = Modals.loading('Pobieranie danych...');

    try {
        const invoicesData = await API.sellers.getInvoices(sellerId);
        Modals.close(loadingModal);

        if (!invoicesData.success) {
            Notifications.error(MSG('seller.invoices_load_failed'));
            return;
        }

        const invoices = invoicesData.invoices || [];
        const invoiceCount = invoices.length;

        // Build confirmation message
        let message = `<div class="mb-4">
            <p class="text-gray-700 mb-2">Czy na pewno chcesz usunac sprzedawce?</p>
            <div class="bg-gray-50 p-3 rounded-lg">
                <p><strong>NIP:</strong> ${escapeHtml(seller.seller_nip)}</p>
                <p><strong>Nazwa:</strong> ${escapeHtml(seller.seller_name)}</p>
            </div>
        </div>`;

        if (invoiceCount > 0) {
            message += `<div class="bg-red-50 border border-red-200 p-3 rounded-lg">
                <p class="text-red-800 font-semibold mb-2">
                    ${Icons.svg('warning', 'align-middle mr-1')}
                    Uwaga: Zostanie usuniete ${invoiceCount} faktur!
                </p>
                <ul class="text-red-700 text-sm max-h-32 overflow-y-auto">`;

            // Show first 10 invoices
            const showInvoices = invoices.slice(0, 10);
            showInvoices.forEach(inv => {
                message += `<li>${escapeHtml(inv.invoice_number)} - ${formatCurrency(inv.amount, inv.currency)}</li>`;
            });

            if (invoiceCount > 10) {
                message += `<li class="font-medium">...i ${invoiceCount - 10} wiecej</li>`;
            }

            message += `</ul></div>`;
        }

        // Show confirmation modal
        Modals.show({
            title: 'Usun sprzedawce',
            content: message,
            size: 'medium',
            buttons: [
                {
                    text: 'Anuluj',
                    type: 'secondary',
                    onClick: (e, overlay) => {
                        Modals.close(overlay);
                    }
                },
                {
                    text: invoiceCount > 0 ? `Usun sprzedawce i ${invoiceCount} faktur` : 'Usun sprzedawce',
                    type: 'danger',
                    onClick: async (e, overlay) => {
                        Modals.close(overlay);
                        await deleteSeller(sellerId);
                    }
                }
            ]
        });

    } catch (error) {
        Modals.close(loadingModal);
        console.error('Error fetching seller invoices:', error);
        Notifications.error(MSG('common.load_error') + error.message);
    }
}

/**
 * Delete seller
 */
async function deleteSeller(sellerId) {
    const loadingModal = Modals.loading('Usuwanie sprzedawcy...');

    try {
        const result = await API.sellers.delete(sellerId);

        Modals.close(loadingModal);

        if (result.success) {
            Notifications.success(result.message || 'Sprzedawca skasowany');
            loadSellers();
        } else {
            Notifications.error(result.error || 'Blad usuwania sprzedawcy');
        }
    } catch (error) {
        Modals.close(loadingModal);
        console.error('Error deleting seller:', error);
        Notifications.error(MSG('common.delete_error') + error.message);
    }
}

/**
 * Sync sellers with invoices
 */
async function syncSellers() {
    const loadingModal = Modals.loading('Synchronizacja danych...');

    try {
        const result = await API.sellers.sync();

        Modals.close(loadingModal);

        if (result.success) {
            showSyncResults(result);
        } else {
            Notifications.error(result.error || 'Blad synchronizacji');
        }
    } catch (error) {
        Modals.close(loadingModal);
        console.error('Error syncing sellers:', error);
        Notifications.error(MSG('seller.sync_error') + error.message);
    }
}

/**
 * Show sync results in full page view (not modal)
 */
function showSyncResults(data) {
    // Update summary stats
    document.getElementById('sync-total-sellers').textContent = data.summary.total_sellers;
    document.getElementById('sync-total-invoices').textContent = data.summary.total_invoices;
    document.getElementById('sync-missing-count').textContent = data.summary.missing_sellers_count;
    document.getElementById('sync-discrepancies-count').textContent = data.summary.discrepancies_count;

    // Reset visibility
    document.getElementById('sync-all-good').classList.add('hidden');
    document.getElementById('missing-sellers-card').classList.add('hidden');
    document.getElementById('discrepancies-card').classList.add('hidden');

    // Populate missing sellers table
    const missingTbody = document.getElementById('missing-sellers-tbody');
    const missingCard = document.getElementById('missing-sellers-card');
    const missingBadge = document.getElementById('missing-sellers-badge');

    if (data.missing_sellers.length > 0) {
        missingCard.classList.remove('hidden');
        missingBadge.textContent = data.missing_sellers.length;
        missingTbody.innerHTML = data.missing_sellers.map(ms => `
            <tr class="hover:bg-gray-50">
                <td class="font-mono">${escapeHtml(ms.nip)}</td>
                <td class="font-medium">${escapeHtml(ms.name)}</td>
                <td class="text-center">
                    <span class="badge badge-info">${ms.count}</span>
                </td>
                <td class="text-center">
                    <button onclick="addMissingSeller('${escapeHtml(ms.nip)}', '${escapeHtml(ms.name)}')"
                            class="btn-success">
                        ${Icons.svg('add', 'text-sm mr-1')}
                        Dodaj do bazy
                    </button>
                </td>
            </tr>
        `).join('');
    }

    // Populate discrepancies table
    const discrepanciesTbody = document.getElementById('discrepancies-tbody');
    const discrepanciesCard = document.getElementById('discrepancies-card');
    const discrepanciesBadge = document.getElementById('discrepancies-badge');

    if (data.name_discrepancies.length > 0) {
        discrepanciesCard.classList.remove('hidden');
        discrepanciesBadge.textContent = data.name_discrepancies.length;
        discrepanciesTbody.innerHTML = data.name_discrepancies.map(d => `
            <tr class="hover:bg-gray-50">
                <td class="font-mono">${escapeHtml(d.invoice_number)}</td>
                <td class="text-primary font-medium">${escapeHtml(d.seller_name)}</td>
                <td class="text-yellow-700">${escapeHtml(d.invoice_seller_name)}</td>
                <td class="text-center">
                    <div class="flex gap-2 justify-center">
                        <button onclick="fixDiscrepancy('use_seller_name', ${d.invoice_id}, ${d.seller_id})"
                                class="btn-secondary" title="Zmien fakture na nazwe z bazy">
                            ${Icons.svg('arrow_back', 'text-sm mr-1')}
                            Uzyj z bazy
                        </button>
                        <button onclick="fixDiscrepancy('use_invoice_name', ${d.invoice_id}, ${d.seller_id})"
                                class="btn-warning" title="Zmien baze na nazwe z faktury">
                            ${Icons.svg('arrow_forward', 'text-sm mr-1')}
                            Uzyj z faktury
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');
    }

    // Show "all good" message if everything is synced
    if (data.missing_sellers.length === 0 && data.name_discrepancies.length === 0) {
        document.getElementById('sync-all-good').classList.remove('hidden');
    }

    // Switch views: hide list, show sync results
    document.getElementById('sellers-list-view').classList.add('hidden');
    document.getElementById('sync-results-view').classList.remove('hidden');

    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

/**
 * Close sync results and return to sellers list
 */
function closeSyncResults() {
    // Switch views: show list, hide sync results
    document.getElementById('sync-results-view').classList.add('hidden');
    document.getElementById('sellers-list-view').classList.remove('hidden');

    // Reload sellers data
    loadSellers();
}

/**
 * Add missing seller from sync results
 */
async function addMissingSeller(nip, name) {
    const loadingModal = Modals.loading('Dodawanie sprzedawcy...');

    try {
        const result = await API.sellers.addMissing(nip, name);

        Modals.close(loadingModal);

        if (result.success) {
            Notifications.success(result.message);
            // Re-run sync to refresh the inline view
            await refreshSyncResults();
        } else {
            Notifications.error(result.error || 'Blad dodawania sprzedawcy');
        }
    } catch (error) {
        Modals.close(loadingModal);
        console.error('Error adding missing seller:', error);
        Notifications.error(MSG('seller.add_error') + error.message);
    }
}

/**
 * Fix name discrepancy
 */
async function fixDiscrepancy(action, invoiceId, sellerId) {
    const loadingModal = Modals.loading('Naprawianie niezgodnosci...');

    try {
        const result = await API.sellers.fixDiscrepancy(action, invoiceId, sellerId);

        Modals.close(loadingModal);

        if (result.success) {
            Notifications.success(result.message);
            // Re-run sync to refresh the inline view
            await refreshSyncResults();
        } else {
            Notifications.error(result.error || 'Blad naprawiania niezgodnosci');
        }
    } catch (error) {
        Modals.close(loadingModal);
        console.error('Error fixing discrepancy:', error);
        Notifications.error(MSG('seller.fix_error') + error.message);
    }
}

/**
 * Refresh sync results without showing loading modal
 */
async function refreshSyncResults() {
    try {
        const result = await API.sellers.sync();
        if (result.success) {
            showSyncResults(result);
        }
    } catch (error) {
        console.error('Error refreshing sync:', error);
    }
}
