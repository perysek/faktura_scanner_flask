/**
 * Seller Create Page JavaScript
 */

let nipValidationTimeout = null;
let existingSellerByNip = null;
let existingSellerByName = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
});

/**
 * Setup event listeners
 */
function setupEventListeners() {
    const nipInput = document.getElementById('seller_nip');
    const nameInput = document.getElementById('seller_name');

    // NIP validation on input (debounced)
    if (nipInput) {
        nipInput.addEventListener('input', debounceNipValidation);
    }

    // Name validation on blur
    if (nameInput) {
        nameInput.addEventListener('blur', checkNameDuplicate);
    }
}

/**
 * Debounce NIP validation
 */
function debounceNipValidation() {
    clearTimeout(nipValidationTimeout);
    nipValidationTimeout = setTimeout(validateNIP, 500);
}

/**
 * Validate NIP format and check for duplicates
 */
async function validateNIP() {
    const nipInput = document.getElementById('seller_nip');
    const nipStatus = document.getElementById('nip-status');
    const nipError = document.getElementById('nip-error');
    const validIcon = nipStatus.querySelector('.nip-valid');
    const invalidIcon = nipStatus.querySelector('.nip-invalid');
    const checkingIcon = nipStatus.querySelector('.nip-checking');

    const nip = nipInput.value.trim();

    // Reset state
    nipStatus.classList.remove('hidden');
    validIcon.classList.add('hidden');
    invalidIcon.classList.add('hidden');
    checkingIcon.classList.add('hidden');
    nipError.classList.add('hidden');
    nipInput.classList.remove('input-error');
    existingSellerByNip = null;

    if (!nip) {
        nipStatus.classList.add('hidden');
        return;
    }

    // Validate format (10 digits)
    const normalizedNip = nip.replace(/[^0-9]/g, '');
    if (normalizedNip.length !== 10) {
        invalidIcon.classList.remove('hidden');
        nipError.textContent = 'NIP musi miec 10 cyfr';
        nipError.classList.remove('hidden');
        nipInput.classList.add('input-error');
        return;
    }

    // Check for duplicates
    checkingIcon.classList.remove('hidden');

    try {
        const result = await API.sellers.checkDuplicate(normalizedNip, '');

        checkingIcon.classList.add('hidden');

        if (result.nip_exists) {
            existingSellerByNip = result.existing_by_nip;
            invalidIcon.classList.remove('hidden');
            nipError.innerHTML = `NIP juz istnieje jako: <strong>${escapeHtml(existingSellerByNip.seller_name)}</strong>`;
            nipError.classList.remove('hidden');
            nipInput.classList.add('input-error');
        } else {
            validIcon.classList.remove('hidden');
        }
    } catch (error) {
        checkingIcon.classList.add('hidden');
        console.error('Error checking NIP:', error);
    }
}

/**
 * Check if seller name already exists
 */
async function checkNameDuplicate() {
    const nameInput = document.getElementById('seller_name');
    const nameWarning = document.getElementById('name-warning');

    const name = nameInput.value.trim();
    existingSellerByName = null;

    nameWarning.classList.add('hidden');

    if (!name) {
        return;
    }

    try {
        const result = await API.sellers.checkDuplicate('', name);

        if (result.name_exists) {
            existingSellerByName = result.existing_by_name;
            nameWarning.innerHTML = `Sprzedawca o podobnej nazwie juz istnieje z NIP: <strong>${escapeHtml(existingSellerByName.seller_nip)}</strong>`;
            nameWarning.classList.remove('hidden');
        }
    } catch (error) {
        console.error('Error checking name:', error);
    }
}

/**
 * Handle form submission
 */
async function handleSubmit(event) {
    event.preventDefault();

    const nipInput = document.getElementById('seller_nip');
    const nameInput = document.getElementById('seller_name');
    const addressInput = document.getElementById('address');

    const nip = nipInput.value.trim();
    const name = nameInput.value.trim();
    const address = addressInput.value.trim();

    // Basic validation
    if (!nip || !name) {
        Notifications.error('NIP i nazwa sa wymagane');
        return false;
    }

    // Check NIP format
    const normalizedNip = nip.replace(/[^0-9]/g, '');
    if (normalizedNip.length !== 10) {
        Notifications.error('NIP musi miec 10 cyfr');
        return false;
    }

    // If NIP exists with same name, redirect to existing
    if (existingSellerByNip) {
        const existingName = existingSellerByNip.seller_name.toLowerCase().replace(/\s+/g, '');
        const newName = name.toLowerCase().replace(/\s+/g, '');

        if (existingName === newName) {
            // Exact match - redirect to existing seller
            Notifications.info('Sprzedawca juz istnieje');
            window.location.href = `/seller/${existingSellerByNip.id}/edit`;
            return false;
        }

        // NIP exists with different name - show modal
        showNipConflictModal(existingSellerByNip, name);
        return false;
    }

    // If name exists with different NIP - show warning modal
    if (existingSellerByName) {
        showNameConflictModal(existingSellerByName, nip, name, address);
        return false;
    }

    // No conflicts - create seller
    await createSeller(nip, name, address);
    return false;
}

/**
 * Show NIP conflict modal
 */
function showNipConflictModal(existingSeller, newName) {
    Modals.show({
        title: 'Konflikt NIP',
        content: `
            <div class="mb-4">
                <div class="bg-yellow-50 border border-yellow-200 p-4 rounded-lg mb-4">
                    <p class="text-yellow-800">
                        ${Icons.svg('warning', 'align-middle mr-1')}
                        NIP <strong>${escapeHtml(existingSeller.seller_nip)}</strong> juz istnieje w bazie.
                    </p>
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div class="bg-gray-50 p-3 rounded-lg">
                        <p class="text-sm text-gray-600 mb-1">Istniejaca nazwa:</p>
                        <p class="font-semibold">${escapeHtml(existingSeller.seller_name)}</p>
                    </div>
                    <div class="bg-blue-50 p-3 rounded-lg">
                        <p class="text-sm text-gray-600 mb-1">Nowa nazwa:</p>
                        <p class="font-semibold">${escapeHtml(newName)}</p>
                    </div>
                </div>
            </div>
            <p class="text-gray-700">Co chcesz zrobic?</p>
        `,
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
                text: 'Uzyj istniejacego',
                type: 'primary',
                icon: 'person',
                onClick: (e, overlay) => {
                    Modals.close(overlay);
                    window.location.href = `/seller/${existingSeller.id}/edit`;
                }
            },
            {
                text: 'Zaktualizuj nazwe',
                type: 'warning',
                icon: 'edit',
                onClick: async (e, overlay) => {
                    Modals.close(overlay);
                    await updateSellerName(existingSeller.id, newName);
                }
            }
        ]
    });
}

/**
 * Show name conflict modal (warning, not blocking)
 */
function showNameConflictModal(existingSeller, nip, name, address) {
    Modals.show({
        title: 'Podobna nazwa',
        content: `
            <div class="mb-4">
                <div class="bg-blue-50 border border-blue-200 p-4 rounded-lg mb-4">
                    <p class="text-blue-800">
                        ${Icons.svg('info', 'align-middle mr-1')}
                        Sprzedawca o podobnej nazwie juz istnieje.
                    </p>
                </div>
                <div class="bg-gray-50 p-3 rounded-lg mb-4">
                    <p><strong>Istniejacy sprzedawca:</strong> ${escapeHtml(existingSeller.seller_name)}</p>
                    <p><strong>NIP:</strong> ${escapeHtml(existingSeller.seller_nip)}</p>
                </div>
                <p class="text-gray-700">Czy na pewno chcesz utworzyc nowego sprzedawce z innym NIP?</p>
            </div>
        `,
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
                text: 'Utworz mimo to',
                type: 'primary',
                icon: 'add',
                onClick: async (e, overlay) => {
                    Modals.close(overlay);
                    // Force creation by clearing the existingSellerByName
                    existingSellerByName = null;
                    await createSeller(nip, name, address, true);
                }
            }
        ]
    });
}

/**
 * Update existing seller name
 */
async function updateSellerName(sellerId, newName) {
    const loadingModal = Modals.loading('Aktualizowanie nazwy...');

    try {
        const result = await API.sellers.update(sellerId, { seller_name: newName });

        Modals.close(loadingModal);

        if (result.success) {
            Notifications.success('Nazwa sprzedawcy zostala zaktualizowana');
            window.location.href = `/seller/${sellerId}/edit`;
        } else {
            Notifications.error(result.error || 'Blad aktualizacji');
        }
    } catch (error) {
        Modals.close(loadingModal);
        console.error('Error updating seller:', error);
        Notifications.error('Blad aktualizacji: ' + error.message);
    }
}

/**
 * Create new seller
 */
async function createSeller(nip, name, address, force = false) {
    const loadingModal = Modals.loading('Tworzenie sprzedawcy...');

    try {
        const result = await API.sellers.create({
            seller_nip: nip,
            seller_name: name,
            address: address || null
        });

        Modals.close(loadingModal);

        if (result.success) {
            if (result.already_exists) {
                Notifications.info('Sprzedawca juz istnieje');
                window.location.href = `/seller/${result.seller.id}/edit`;
            } else {
                Notifications.success('Sprzedawca zostal utworzony');
                window.location.href = '/sellers';
            }
        } else {
            // Handle conflict responses
            if (result.conflict_type === 'nip_exists_different_name') {
                showNipConflictModal(result.existing_seller, name);
            } else if (result.conflict_type === 'name_exists_different_nip' && !force) {
                showNameConflictModal(result.existing_seller, nip, name, address);
            } else {
                Notifications.error(result.error || 'Blad tworzenia sprzedawcy');
            }
        }
    } catch (error) {
        Modals.close(loadingModal);

        // Check if it's a conflict response
        if (error.status === 409 && error.responseData) {
            const data = error.responseData;
            if (data.conflict_type === 'nip_exists_different_name') {
                showNipConflictModal(data.existing_seller, name);
            } else if (data.conflict_type === 'name_exists_different_nip' && !force) {
                showNameConflictModal(data.existing_seller, nip, name, address);
            } else {
                Notifications.error(data.message || 'Blad tworzenia sprzedawcy');
            }
        } else {
            console.error('Error creating seller:', error);
            Notifications.error('Blad tworzenia sprzedawcy: ' + error.message);
        }
    }
}
