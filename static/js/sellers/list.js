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
            Notifications.error('Blad ladowania sprzedawcow');
        }
    } catch (error) {
        console.error('Error loading sellers:', error);
        Notifications.error('Blad ladowania sprzedawcow: ' + error.message);
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
                            <span class="material-icons">edit</span>
                        </a>
                        <button onclick="confirmDeleteSeller(${seller.id})"
                                class="table-action-btn table-action-btn-delete"
                                title="Usun">
                            <span class="material-icons">delete</span>
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
            Notifications.error('Blad pobierania faktur');
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
                    <span class="material-icons align-middle mr-1">warning</span>
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
        Notifications.error('Blad pobierania danych: ' + error.message);
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
            Notifications.success(result.message || 'Sprzedawca zostal usuniety');
            loadSellers();
        } else {
            Notifications.error(result.error || 'Blad usuwania sprzedawcy');
        }
    } catch (error) {
        Modals.close(loadingModal);
        console.error('Error deleting seller:', error);
        Notifications.error('Blad usuwania sprzedawcy: ' + error.message);
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
        Notifications.error('Blad synchronizacji: ' + error.message);
    }
}

/**
 * Show sync results modal
 */
function showSyncResults(data) {
    const template = document.getElementById('sync-results-template');
    const content = template.content.cloneNode(true);
    const container = document.createElement('div');
    container.appendChild(content);

    // Update summary stats
    container.querySelector('#sync-total-sellers').textContent = data.summary.total_sellers;
    container.querySelector('#sync-total-invoices').textContent = data.summary.total_invoices;
    container.querySelector('#sync-missing-count').textContent = data.summary.missing_sellers_count;
    container.querySelector('#sync-discrepancies-count').textContent = data.summary.discrepancies_count;

    // Populate missing sellers table
    const missingTbody = container.querySelector('#missing-sellers-tbody');
    const missingSection = container.querySelector('#missing-sellers-section');

    if (data.missing_sellers.length === 0) {
        missingSection.classList.add('hidden');
    } else {
        missingTbody.innerHTML = data.missing_sellers.map(ms => `
            <tr>
                <td class="font-mono">${escapeHtml(ms.nip)}</td>
                <td>${escapeHtml(ms.name)}</td>
                <td class="text-center">${ms.count}</td>
                <td>
                    <button onclick="addMissingSeller('${escapeHtml(ms.nip)}', '${escapeHtml(ms.name)}')"
                            class="btn-success text-sm py-1 px-2">
                        <span class="material-icons text-sm mr-1">add</span>
                        Dodaj
                    </button>
                </td>
            </tr>
        `).join('');
    }

    // Populate discrepancies table
    const discrepanciesTbody = container.querySelector('#discrepancies-tbody');
    const discrepanciesSection = container.querySelector('#discrepancies-section');

    if (data.name_discrepancies.length === 0) {
        discrepanciesSection.classList.add('hidden');
    } else {
        discrepanciesTbody.innerHTML = data.name_discrepancies.map(d => `
            <tr>
                <td class="font-mono">${escapeHtml(d.invoice_number)}</td>
                <td class="text-primary">${escapeHtml(d.seller_name)}</td>
                <td class="text-status-warning">${escapeHtml(d.invoice_seller_name)}</td>
                <td>
                    <div class="flex gap-1">
                        <button onclick="fixDiscrepancy('use_seller_name', ${d.invoice_id}, ${d.seller_id})"
                                class="btn-secondary text-xs py-1 px-2" title="Uzyj nazwy sprzedawcy">
                            <span class="material-icons text-sm">arrow_back</span>
                        </button>
                        <button onclick="fixDiscrepancy('use_invoice_name', ${d.invoice_id}, ${d.seller_id})"
                                class="btn-secondary text-xs py-1 px-2" title="Uzyj nazwy z faktury">
                            <span class="material-icons text-sm">arrow_forward</span>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');
    }

    // Check if everything is in sync
    if (data.missing_sellers.length === 0 && data.name_discrepancies.length === 0) {
        const allGood = document.createElement('div');
        allGood.className = 'bg-green-50 border border-green-200 p-4 rounded-lg text-center';
        allGood.innerHTML = `
            <span class="material-icons text-green-600 text-4xl mb-2">check_circle</span>
            <p class="text-green-800 font-semibold">Wszystko zsynchronizowane!</p>
            <p class="text-green-600 text-sm">Dane sprzedawcow sa zgodne z fakturami.</p>
        `;
        container.querySelector('.sync-results').appendChild(allGood);
    }

    // Show modal
    Modals.show({
        title: 'Wyniki synchronizacji',
        content: container.innerHTML,
        size: 'large',
        buttons: [
            {
                text: 'Zamknij',
                type: 'primary',
                onClick: (e, overlay) => {
                    Modals.close(overlay);
                    loadSellers(); // Reload table
                }
            }
        ]
    });
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
            // Re-run sync to update modal
            syncSellers();
        } else {
            Notifications.error(result.error || 'Blad dodawania sprzedawcy');
        }
    } catch (error) {
        Modals.close(loadingModal);
        console.error('Error adding missing seller:', error);
        Notifications.error('Blad dodawania sprzedawcy: ' + error.message);
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
            // Re-run sync to update modal
            syncSellers();
        } else {
            Notifications.error(result.error || 'Blad naprawiania niezgodnosci');
        }
    } catch (error) {
        Modals.close(loadingModal);
        console.error('Error fixing discrepancy:', error);
        Notifications.error('Blad naprawiania niezgodnosci: ' + error.message);
    }
}
