/**
 * Seller Edit Page JavaScript
 */

let sellerId = null;
let sellerData = null;
let invoicesData = [];
let originalName = '';
let passwordData = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    sellerId = document.getElementById('seller_id').value;
    originalName = document.getElementById('seller_name').value;
    loadSellerData();
    loadPasswordData();
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

            // Check if invoice count is out of sync
            if (sellerData.invoice_count !== invoicesData.length) {
                console.log(`Invoice count mismatch detected: stored=${sellerData.invoice_count}, actual=${invoicesData.length}`);
                // Automatically sync invoice counts
                try {
                    await API.sellers.syncInvoiceCounts();
                    console.log('Invoice counts synchronized');
                    // Reload seller data to get updated count
                    const refreshedData = await API.sellers.getById(sellerId);
                    if (refreshedData.success) {
                        sellerData = refreshedData.seller;
                    }
                } catch (syncError) {
                    console.error('Error syncing invoice counts:', syncError);
                }
            }

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
    const countStat = document.getElementById('invoice-count-stat');

    // Update both the badge and the stat with actual count
    countBadge.textContent = invoicesData.length;
    if (countStat) {
        countStat.textContent = invoicesData.length;
    }

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

// ============================================================================
// PDF Password Management
// ============================================================================

async function loadPasswordData() {
    try {
        const data = await API.sellerPasswords.getForSeller(sellerId);
        if (data.success) {
            passwordData = data.password;
            renderPasswordSection();
        }
    } catch (error) {
        console.error('Error loading password data:', error);
    }
}

function renderPasswordSection() {
    const noPassword = document.getElementById('pwd-no-password');
    const hasPassword = document.getElementById('pwd-has-password');
    const pwdForm = document.getElementById('pwd-form');
    const pwdActions = document.getElementById('pwd-actions');

    pwdForm.style.display = 'none';

    if (passwordData) {
        noPassword.style.display = 'none';
        hasPassword.style.display = 'block';
        document.getElementById('pwd-display').textContent = passwordData.pdf_password;
        document.getElementById('pwd-email-display').textContent = passwordData.email_sender_pattern || '—';

        const descEl = document.getElementById('pwd-description-display');
        if (passwordData.description) {
            descEl.textContent = passwordData.description;
            descEl.style.display = 'block';
        } else {
            descEl.style.display = 'none';
        }

        pwdActions.innerHTML = `
            <div style="display: flex; gap: 0.25rem;">
                <button type="button" class="action-btn" onclick="showPasswordForm(true)" title="Edytuj haslo">
                    <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                </button>
                <button type="button" class="action-btn delete" onclick="deletePassword()" title="Usun haslo">
                    <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                </button>
            </div>
        `;
    } else {
        noPassword.style.display = 'block';
        hasPassword.style.display = 'none';
        pwdActions.innerHTML = '';
    }
}

function showPasswordForm(isEdit = false) {
    document.getElementById('pwd-no-password').style.display = 'none';
    document.getElementById('pwd-has-password').style.display = 'none';
    document.getElementById('pwd-form').style.display = 'block';
    document.getElementById('pwd-actions').innerHTML = '';

    if (isEdit && passwordData) {
        document.getElementById('pwd-entry-id').value = passwordData.id;
        document.getElementById('pwd-password').value = passwordData.pdf_password;
        document.getElementById('pwd-email-pattern').value = passwordData.email_sender_pattern || '';
        document.getElementById('pwd-description').value = passwordData.description || '';
    } else {
        document.getElementById('pwd-entry-id').value = '';
        document.getElementById('pwd-password').value = '';
        document.getElementById('pwd-email-pattern').value = '';
        document.getElementById('pwd-description').value = '';
    }

    document.getElementById('pwd-password').focus();
}

function cancelPasswordForm() {
    document.getElementById('pwd-form').style.display = 'none';
    renderPasswordSection();
}

async function savePassword() {
    const password = document.getElementById('pwd-password').value.trim();
    if (!password) {
        Notifications.error('Haslo PDF jest wymagane');
        return;
    }

    const entryId = document.getElementById('pwd-entry-id').value;
    const data = {
        seller_id: parseInt(sellerId),
        pdf_password: password,
        email_sender_pattern: document.getElementById('pwd-email-pattern').value.trim() || null,
        description: document.getElementById('pwd-description').value.trim() || null,
    };

    try {
        let result;
        if (entryId) {
            result = await API.sellerPasswords.update(parseInt(entryId), data);
        } else {
            result = await API.sellerPasswords.create(data);
        }

        if (result.success) {
            Notifications.success(entryId ? 'Haslo zaktualizowane' : 'Haslo dodane');
            await loadPasswordData();
        } else {
            Notifications.error(result.error || 'Blad zapisu');
        }
    } catch (error) {
        console.error('Error saving password:', error);
        Notifications.error('Blad zapisu: ' + error.message);
    }
}

async function deletePassword() {
    if (!passwordData) return;

    Modals.confirm({
        title: 'Usun haslo PDF',
        message: 'Czy na pewno chcesz usunac haslo PDF dla tego sprzedawcy? Zaszyfrowane faktury nie beda automatycznie odblokowywane.',
        confirmText: 'Usun',
        onConfirm: async () => {
            try {
                const result = await API.sellerPasswords.delete(passwordData.id);
                if (result.success) {
                    passwordData = null;
                    renderPasswordSection();
                    Notifications.success('Haslo usuniete');
                }
            } catch (error) {
                Notifications.error('Blad usuwania: ' + error.message);
            }
        }
    });
}
