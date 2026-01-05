/**
 * Seller Edit Page JavaScript
 */

let sellerId = null;
let sellerData = null;
let invoicesData = [];
let originalName = '';

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    sellerId = document.getElementById('seller_id').value;
    originalName = document.getElementById('seller_name').value;
    loadSellerData();
});

/**
 * Load seller data and invoices
 */
async function loadSellerData() {
    try {
        const data = await API.sellers.getById(sellerId);

        if (data.success) {
            sellerData = data.seller;
            invoicesData = data.invoices || [];
            renderInvoicesTable();
        } else {
            Notifications.error('Blad ladowania danych sprzedawcy');
        }
    } catch (error) {
        console.error('Error loading seller:', error);
        Notifications.error('Blad ladowania danych: ' + error.message);
    }
}

/**
 * Render invoices table
 */
function renderInvoicesTable() {
    const tbody = document.getElementById('invoices-tbody');
    const emptyState = document.getElementById('invoices-empty');
    const countBadge = document.getElementById('invoices-count');

    countBadge.textContent = invoicesData.length;

    if (invoicesData.length === 0) {
        tbody.innerHTML = '';
        emptyState.classList.remove('hidden');
        document.getElementById('invoicesTable').classList.add('hidden');
        return;
    }

    emptyState.classList.add('hidden');
    document.getElementById('invoicesTable').classList.remove('hidden');

    tbody.innerHTML = invoicesData.map(invoice => {
        // Check if invoice name differs from seller name
        const sellerName = sellerData.seller_name;
        const invoiceName = invoice.seller_name || '';
        const namesDiffer = invoiceName.trim().toLowerCase() !== sellerName.trim().toLowerCase();

        // Format date
        let invoiceDate = '-';
        if (invoice.invoice_date) {
            invoiceDate = formatDate(invoice.invoice_date);
        }

        // Status badge
        let statusBadge = '';
        if (invoice.status === 'Oplacona') {
            statusBadge = '<span class="badge badge-success">Oplacona</span>';
        } else if (invoice.status === 'Przeterminowana') {
            statusBadge = '<span class="badge badge-error">Przeterminowana</span>';
        } else {
            statusBadge = '<span class="badge badge-warning">Nieoplacona</span>';
        }

        // Name cell with warning if different
        let nameCell = escapeHtml(invoiceName);
        if (namesDiffer) {
            nameCell = `<span class="text-yellow-600" title="Rozni sie od nazwy sprzedawcy">
                <span class="material-icons text-sm align-middle mr-1">warning</span>
                ${escapeHtml(invoiceName)}
            </span>`;
        }

        return `
            <tr class="hover:bg-gray-50 transition-colors">
                <td class="font-medium">${escapeHtml(invoice.invoice_number || '-')}</td>
                <td>${invoiceDate}</td>
                <td class="text-right font-medium">${formatCurrency(invoice.amount, invoice.currency)}</td>
                <td>${statusBadge}</td>
                <td>${nameCell}</td>
                <td>
                    <a href="/invoice/${invoice.id}/edit"
                       class="table-action-btn table-action-btn-edit"
                       title="Edytuj fakture">
                        <span class="material-icons">edit</span>
                    </a>
                </td>
            </tr>
        `;
    }).join('');
}

/**
 * Handle form submission
 */
async function handleSubmit(event) {
    event.preventDefault();

    const nameInput = document.getElementById('seller_name');
    const addressInput = document.getElementById('address');

    const name = nameInput.value.trim();
    const address = addressInput.value.trim();

    // Basic validation
    if (!name) {
        Notifications.error('Nazwa sprzedawcy jest wymagana');
        return false;
    }

    const loadingModal = Modals.loading('Zapisywanie zmian...');

    try {
        const result = await API.sellers.update(sellerId, {
            seller_name: name,
            address: address || null
        });

        Modals.close(loadingModal);

        if (result.success) {
            Notifications.success('Dane sprzedawcy zostaly zaktualizowane');

            // Update local data
            sellerData = result.seller;
            originalName = name;

            // Check if name changed and there are invoices
            if (invoicesData.length > 0) {
                // Check how many invoices have different names
                const differentNames = invoicesData.filter(inv =>
                    inv.seller_name.trim().toLowerCase() !== name.trim().toLowerCase()
                );

                if (differentNames.length > 0) {
                    showPropagatePrompt(differentNames.length);
                }
            }
        } else {
            Notifications.error(result.error || 'Blad aktualizacji');
        }
    } catch (error) {
        Modals.close(loadingModal);
        console.error('Error updating seller:', error);
        Notifications.error('Blad aktualizacji: ' + error.message);
    }

    return false;
}

/**
 * Show prompt to propagate changes to invoices
 */
function showPropagatePrompt(count) {
    Modals.show({
        title: 'Zaktualizuj faktury',
        content: `
            <div class="mb-4">
                <div class="bg-blue-50 border border-blue-200 p-4 rounded-lg">
                    <p class="text-blue-800">
                        <span class="material-icons align-middle mr-1">info</span>
                        ${count} faktur ma inna nazwe sprzedawcy niz zapisana w bazie.
                    </p>
                </div>
                <p class="text-gray-700 mt-4">Czy chcesz zaktualizowac nazwe sprzedawcy we wszystkich powiazanych fakturach?</p>
            </div>
        `,
        size: 'medium',
        buttons: [
            {
                text: 'Nie teraz',
                type: 'secondary',
                onClick: (e, overlay) => {
                    Modals.close(overlay);
                }
            },
            {
                text: 'Zaktualizuj faktury',
                type: 'primary',
                icon: 'sync',
                onClick: async (e, overlay) => {
                    Modals.close(overlay);
                    await propagateChanges();
                }
            }
        ]
    });
}

/**
 * Propagate seller changes to all linked invoices
 */
async function propagateChanges() {
    const loadingModal = Modals.loading('Aktualizowanie faktur...');

    try {
        const result = await API.sellers.bulkUpdate(sellerId);

        Modals.close(loadingModal);

        if (result.success) {
            const message = `Zaktualizowano ${result.updated_count} z ${result.total_invoices} faktur`;
            Notifications.success(message);

            // Reload invoices
            await loadSellerData();
        } else {
            Notifications.error(result.error || 'Blad aktualizacji faktur');
        }
    } catch (error) {
        Modals.close(loadingModal);
        console.error('Error propagating changes:', error);
        Notifications.error('Blad aktualizacji faktur: ' + error.message);
    }
}
