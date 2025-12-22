/**
 * Upload Page JavaScript
 */

let selectedFiles = [];

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    setupFileUpload();
    setupEmailImport();
    setDefaultDates();
});

/**
 * Setup file upload functionality
 */
function setupFileUpload() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const uploadBtn = document.getElementById('upload-btn');
    const clearBtn = document.getElementById('clear-btn');

    // Click to select files
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    // File selection
    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });

    // Drag and drop
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('border-primary', 'bg-primary-50');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('border-primary', 'bg-primary-50');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('border-primary', 'bg-primary-50');
        handleFiles(e.dataTransfer.files);
    });

    // Upload button
    uploadBtn.addEventListener('click', uploadFiles);
}

/**
 * Handle selected files
 */
function handleFiles(files) {
    const pdfFiles = Array.from(files).filter(file => file.type === 'application/pdf');

    if (pdfFiles.length === 0) {
        Notifications.warning('Proszę wybrać pliki PDF');
        return;
    }

    selectedFiles = [...selectedFiles, ...pdfFiles];
    displaySelectedFiles();
    updateUploadButton();
}

/**
 * Display selected files
 */
function displaySelectedFiles() {
    const container = document.getElementById('selected-files');

    if (selectedFiles.length === 0) {
        container.innerHTML = '';
        return;
    }

    container.innerHTML = selectedFiles.map((file, index) => `
        <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <div class="flex items-center gap-3">
                <span class="material-icons text-status-error">picture_as_pdf</span>
                <div>
                    <p class="text-sm font-medium text-gray-900">${escapeHtml(file.name)}</p>
                    <p class="text-xs text-gray-500">${formatFileSize(file.size)}</p>
                </div>
            </div>
            <button onclick="removeFile(${index})" class="text-gray-400 hover:text-status-error transition-colors">
                <span class="material-icons text-sm">close</span>
            </button>
        </div>
    `).join('');
}

/**
 * Remove file from selection
 */
function removeFile(index) {
    selectedFiles.splice(index, 1);
    displaySelectedFiles();
    updateUploadButton();
}

/**
 * Clear all files
 */
function clearFiles() {
    selectedFiles = [];
    document.getElementById('file-input').value = '';
    displaySelectedFiles();
    updateUploadButton();
}

/**
 * Update upload button state
 */
function updateUploadButton() {
    const uploadBtn = document.getElementById('upload-btn');
    const clearBtn = document.getElementById('clear-btn');
    const hasFiles = selectedFiles.length > 0;

    uploadBtn.disabled = !hasFiles;
    clearBtn.disabled = !hasFiles;
}

/**
 * Upload and process files
 */
async function uploadFiles() {
    if (selectedFiles.length === 0) return;

    const uploadBtn = document.getElementById('upload-btn');
    const progressContainer = document.getElementById('upload-progress');
    const progressBar = document.getElementById('progress-bar');
    const progressPercent = document.getElementById('progress-percent');

    // Show progress
    progressContainer.classList.remove('hidden');
    uploadBtn.disabled = true;

    try {
        const result = await API.upload.files(selectedFiles, (percent) => {
            progressBar.style.width = `${percent}%`;
            progressPercent.textContent = `${Math.round(percent)}%`;
        });

        if (result.success) {
            Notifications.success(`Przetworzono ${result.results.length} plików`);
            displayResults(result.results);
            clearFiles();
        } else {
            Notifications.error('Błąd przetwarzania plików');
        }
    } catch (error) {
        console.error('Upload error:', error);
        Notifications.error('Błąd przesyłania plików: ' + error.message);
    } finally {
        progressContainer.classList.add('hidden');
        progressBar.style.width = '0%';
        progressPercent.textContent = '0%';
        uploadBtn.disabled = false;
    }
}

/**
 * Setup email import
 */
function setupEmailImport() {
    const importBtn = document.getElementById('email-import-btn');
    const getFoldersBtn = document.getElementById('get-folders-btn');
    const selectFoldersBtn = document.getElementById('select-folders-btn');

    importBtn.addEventListener('click', importFromEmail);
    getFoldersBtn.addEventListener('click', getFolders);
    selectFoldersBtn.addEventListener('click', openFolderModal);
}

// Global variable to store available folders
let availableFolders = [];

/**
 * Get folders from email server
 */
async function getFolders() {
    const getFoldersBtn = document.getElementById('get-folders-btn');
    const selectFoldersBtn = document.getElementById('select-folders-btn');
    const folderList = document.getElementById('folder-list');

    // Disable button during fetch
    getFoldersBtn.disabled = true;
    getFoldersBtn.innerHTML = '<span class="material-icons text-sm animate-spin">sync</span> Pobieranie...';

    try {
        const result = await API.email.getFolders();

        if (result.success && result.folders && result.folders.length > 0) {
            // Store folders globally
            availableFolders = result.folders;

            // Clear folder list
            folderList.innerHTML = '';

            // Populate with checkboxes
            result.folders.forEach((folder, index) => {
                const checkbox = document.createElement('label');
                checkbox.className = 'flex items-center gap-2 cursor-pointer hover:bg-gray-50 p-2 rounded';
                checkbox.innerHTML = `
                    <input type="checkbox" class="folder-checkbox form-checkbox h-4 w-4 text-primary" value="${escapeHtml(folder)}" data-folder-index="${index}">
                    <span class="text-gray-700">${escapeHtml(folder)}</span>
                `;
                folderList.appendChild(checkbox);
            });

            // Setup "All" checkbox handler
            setupAllCheckboxHandler();

            // Enable select folders button
            selectFoldersBtn.disabled = false;
            document.getElementById('selected-folders-text').textContent = 'Kliknij aby wybrać foldery';
            document.getElementById('selected-folders-text').classList.remove('text-gray-500');
            document.getElementById('selected-folders-text').classList.add('text-gray-700');

            Notifications.success(`Załadowano ${result.folders.length} folderów`);
        } else {
            Notifications.warning('Nie znaleziono folderów e-mail');
        }
    } catch (error) {
        console.error('Get folders error:', error);
        Notifications.error('Błąd pobierania folderów: ' + error.message);
    } finally {
        // Re-enable button
        getFoldersBtn.disabled = false;
        getFoldersBtn.innerHTML = '<span class="material-icons text-sm">folder</span> Pobierz foldery';
    }
}

/**
 * Setup "All" checkbox handler
 */
function setupAllCheckboxHandler() {
    const allCheckbox = document.getElementById('folder-all');
    const folderCheckboxes = document.querySelectorAll('.folder-checkbox');

    // When "All" is checked/unchecked
    allCheckbox.addEventListener('change', function () {
        folderCheckboxes.forEach(cb => {
            cb.checked = this.checked;
            cb.disabled = this.checked;
        });
    });

    // When individual checkbox changes, update "All" state
    folderCheckboxes.forEach(cb => {
        cb.addEventListener('change', function () {
            const allChecked = Array.from(folderCheckboxes).every(checkbox => checkbox.checked);
            const noneChecked = Array.from(folderCheckboxes).every(checkbox => !checkbox.checked);

            if (allChecked) {
                allCheckbox.checked = true;
                allCheckbox.indeterminate = false;
            } else if (noneChecked) {
                allCheckbox.checked = false;
                allCheckbox.indeterminate = false;
            } else {
                allCheckbox.checked = false;
                allCheckbox.indeterminate = true;
            }
        });
    });
}

/**
 * Open folder selection modal
 */
function openFolderModal() {
    const modalContent = document.getElementById('folder-modal').innerHTML;

    const modal = Modals.show({
        title: 'Wybierz foldery e-mail',
        content: modalContent,
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
                text: 'Zastosuj',
                type: 'primary',
                icon: 'check',
                onClick: (e, overlay) => {
                    applyFolderSelection(overlay);
                }
            }
        ]
    });

    // Re-setup event handlers in the modal
    setupModalCheckboxHandlers(modal);

    // Restore previous selections
    restoreFolderSelections(modal);
}

/**
 * Setup checkbox handlers within the modal
 */
function setupModalCheckboxHandlers(modal) {
    const allCheckbox = modal.querySelector('#folder-all');
    const folderCheckboxes = modal.querySelectorAll('.folder-checkbox');

    // When "All" is checked/unchecked
    allCheckbox.addEventListener('change', function () {
        folderCheckboxes.forEach(cb => {
            cb.checked = this.checked;
        });
    });

    // When individual checkbox changes, update "All" state
    folderCheckboxes.forEach(cb => {
        cb.addEventListener('change', function () {
            const allChecked = Array.from(folderCheckboxes).every(checkbox => checkbox.checked);
            const noneChecked = Array.from(folderCheckboxes).every(checkbox => !checkbox.checked);

            if (allChecked) {
                allCheckbox.checked = true;
                allCheckbox.indeterminate = false;
            } else if (noneChecked) {
                allCheckbox.checked = false;
                allCheckbox.indeterminate = false;
            } else {
                allCheckbox.checked = false;
                allCheckbox.indeterminate = true;
            }
        });
    });
}

// Global variable to store selected folders
let selectedFolders = [];
let isAllFoldersSelected = false;

/**
 * Restore previous folder selections in modal
 */
function restoreFolderSelections(modal) {
    const allCheckbox = modal.querySelector('#folder-all');
    const folderCheckboxes = modal.querySelectorAll('.folder-checkbox');

    if (isAllFoldersSelected) {
        allCheckbox.checked = true;
        folderCheckboxes.forEach(cb => cb.checked = true);
    } else {
        folderCheckboxes.forEach(cb => {
            if (selectedFolders.includes(cb.value)) {
                cb.checked = true;
            }
        });

        // Update "All" checkbox state
        const allChecked = Array.from(folderCheckboxes).every(checkbox => checkbox.checked);
        if (allChecked) {
            allCheckbox.checked = true;
        }
    }
}

/**
 * Apply folder selection from modal
 */
function applyFolderSelection(overlay) {
    const allCheckbox = overlay.querySelector('#folder-all');
    const folderCheckboxes = overlay.querySelectorAll('.folder-checkbox');

    // Check if "All" is selected
    isAllFoldersSelected = allCheckbox.checked;

    if (isAllFoldersSelected) {
        // When "All" is selected, we send empty array to API
        selectedFolders = [];
    } else {
        // Get selected individual folders
        selectedFolders = Array.from(folderCheckboxes)
            .filter(cb => cb.checked)
            .map(cb => cb.value);
    }

    // Update button text
    updateSelectedFoldersDisplay();

    // Update import button state
    updateImportButtonState();

    // Close modal
    Modals.close(overlay);
}

/**
 * Update the display of selected folders
 */
function updateSelectedFoldersDisplay() {
    const displayText = document.getElementById('selected-folders-text');

    if (isAllFoldersSelected) {
        displayText.textContent = 'Wszystkie foldery';
        displayText.classList.remove('text-gray-500');
        displayText.classList.add('text-gray-900');
    } else if (selectedFolders.length === 0) {
        displayText.textContent = 'Wybierz foldery';
        displayText.classList.add('text-gray-500');
        displayText.classList.remove('text-gray-900');
    } else if (selectedFolders.length === 1) {
        displayText.textContent = selectedFolders[0];
        displayText.classList.remove('text-gray-500');
        displayText.classList.add('text-gray-900');
    } else {
        displayText.textContent = `Wybrano: ${selectedFolders.length} folderów`;
        displayText.classList.remove('text-gray-500');
        displayText.classList.add('text-gray-900');
    }
}

/**
 * Update import button state based on folder selection
 */
function updateImportButtonState() {
    const importBtn = document.getElementById('email-import-btn');

    // Enable import button if "All" is selected OR at least one folder is selected
    importBtn.disabled = !isAllFoldersSelected && selectedFolders.length === 0;
}

/**
 * Set default dates (last 30 days)
 */
function setDefaultDates() {
    const today = new Date();
    const thirtyDaysAgo = new Date(today);
    thirtyDaysAgo.setDate(today.getDate() - 30);

    document.getElementById('email-date-to').valueAsDate = today;
    document.getElementById('email-date-from').valueAsDate = thirtyDaysAgo;
}

/**
 * Show custom progress modal with notifications
 */
function showProgressModal() {
    const modal = Modals.show({
        title: 'Import z e-mail',
        content: `
            <div class="space-y-4">
                <div id="progress-header" class="bg-primary-50 border border-primary-200 rounded-lg p-3">
                    <div class="flex items-center justify-between">
                        <span class="text-sm font-semibold text-primary-700">Przygotowywanie...</span>
                        <span id="progress-counter" class="text-xs font-medium text-primary-600">0 / 0</span>
                    </div>
                    <div class="mt-2 bg-gray-200 rounded-full h-2">
                        <div id="progress-bar-fill" class="bg-primary-600 h-2 rounded-full transition-all duration-300" style="width: 0%"></div>
                    </div>
                </div>
                <div id="progress-notifications" class="space-y-2 border border-gray-200 rounded-lg p-3 bg-gray-50" style="height: 200px; overflow: hidden;">
                    <!-- Notifications will be added here - shows last 5 -->
                </div>
            </div>
        `,
        size: 'large',
        buttons: [],
        closeOnOverlay: false
    });

    return modal;
}

/**
 * Add notification to progress modal
 */
function addProgressNotification(message, type = 'info') {
    const container = document.getElementById('progress-notifications');
    if (!container) return;

    const notification = document.createElement('div');
    notification.className = `flex items-start gap-2 p-2 rounded ${getNotificationStyle(type)} animate-fade-in`;

    const icon = getNotificationIcon(type);
    notification.innerHTML = `
        <span class="material-icons text-sm mt-0.5">${icon}</span>
        <span class="text-sm flex-1">${escapeHtml(message)}</span>
    `;

    container.appendChild(notification);

    // Keep only last 5 notifications
    const notifications = container.querySelectorAll('div.flex');
    if (notifications.length > 5) {
        const oldNotification = notifications[0];
        oldNotification.style.opacity = '0';
        oldNotification.style.transition = 'opacity 0.3s';
        setTimeout(() => oldNotification.remove(), 300);
    }
}

/**
 * Get notification style based on type
 */
function getNotificationStyle(type) {
    const styles = {
        'info': 'bg-blue-50 text-blue-700 border-l-4 border-blue-400',
        'success': 'bg-green-50 text-green-700 border-l-4 border-green-400',
        'warning': 'bg-yellow-50 text-yellow-700 border-l-4 border-yellow-400',
        'error': 'bg-red-50 text-red-700 border-l-4 border-red-400'
    };
    return styles[type] || styles.info;
}

/**
 * Get notification icon based on type
 */
function getNotificationIcon(type) {
    const icons = {
        'info': 'info',
        'success': 'check_circle',
        'warning': 'warning',
        'error': 'error'
    };
    return icons[type] || icons.info;
}

/**
 * Update progress header
 */
function updateProgressHeader(action, current, total) {
    const headerText = document.querySelector('#progress-header .text-sm.font-semibold');
    const counter = document.getElementById('progress-counter');
    const progressBar = document.getElementById('progress-bar-fill');

    if (headerText) {
        headerText.textContent = action;
    }

    if (counter) {
        counter.textContent = `${current} / ${total}`;
    }

    if (progressBar && total > 0) {
        const percentage = (current / total) * 100;
        progressBar.style.width = `${percentage}%`;
    }
}

/**
 * Import from email
 */
async function importFromEmail() {
    const dateFrom = document.getElementById('email-date-from').value;
    const dateTo = document.getElementById('email-date-to').value;

    // Check if folders are selected (either "All" or specific folders)
    if (!isAllFoldersSelected && selectedFolders.length === 0) {
        Notifications.warning('Proszę wybrać co najmniej jeden folder');
        return;
    }

    if (!dateFrom || !dateTo) {
        Notifications.warning('Proszę wybrać zakres dat');
        return;
    }

    // Show custom progress modal
    const progressModal = showProgressModal();

    try {
        // When "All" is selected, send null to search all folders
        // Otherwise send the selected folders array
        const foldersToSend = isAllFoldersSelected ? null : selectedFolders;

        // Use fetch to get SSE stream
        const response = await fetch(`${API.baseUrl}/email/import`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                folders: foldersToSend,
                date_from: dateFrom,
                date_to: dateTo
            })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let totalFiles = 0;
        let currentFile = 0;
        let finalResults = null;

        while (true) {
            const { done, value } = await reader.read();

            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Process complete SSE messages
            const lines = buffer.split('\n\n');
            buffer = lines.pop(); // Keep incomplete message in buffer

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.substring(6));

                        // Handle different message types
                        switch (data.type) {
                            case 'progress':
                                addProgressNotification(data.message, 'info');
                                if (data.current && data.total) {
                                    currentFile = data.current;
                                    totalFiles = data.total;
                                    updateProgressHeader('Przetwarzanie plików', data.current, data.total);
                                }
                                break;

                            case 'success':
                                addProgressNotification(data.message, 'success');
                                break;

                            case 'warning':
                                addProgressNotification(data.message, 'warning');
                                break;

                            case 'error':
                                addProgressNotification(data.message, 'error');
                                break;

                            case 'info':
                                addProgressNotification(data.message, 'info');
                                break;

                            case 'complete':
                                finalResults = data;
                                addProgressNotification(`✅ Import zakończony: przetworzono ${data.total_processed} plików`, 'success');
                                break;
                        }
                    } catch (e) {
                        console.error('Error parsing SSE message:', e);
                    }
                }
            }
        }

        // Close modal after a short delay and show results
        setTimeout(() => {
            Modals.close(progressModal);
            if (finalResults && finalResults.results) {
                Notifications.success(`Import zakończony: przetworzono ${finalResults.total_processed} plików`);
                displayResults(finalResults.results);
            }
        }, 1000);

    } catch (error) {
        console.error('Email import error:', error);
        addProgressNotification(`Błąd: ${error.message}`, 'error');
        setTimeout(() => {
            Modals.close(progressModal);
            Notifications.error('Błąd importu z e-mail: ' + error.message);
        }, 1000);
    }
}

/**
 * Display processing results
 */
function displayResults(results) {
    const section = document.getElementById('results-section');
    const tbody = document.getElementById('results-tbody');
    const summary = document.getElementById('results-summary');

    const successCount = results.filter(r => r.success && r.saved).length;
    const errorCount = results.filter(r => !r.success).length;
    const duplicateCount = results.filter(r => r.is_duplicate).length;
    const validationErrorCount = results.filter(r => r.validation_errors && r.validation_errors.length > 0).length;
    const validationWarningCount = results.filter(r => r.validation_warnings && r.validation_warnings.length > 0).length;

    summary.innerHTML = `
        <span class="text-status-success">✓ ${successCount} zapisanych</span> •
        <span class="text-status-warning">⚠ ${duplicateCount} duplikatów</span> •
        <span class="text-status-error">✗ ${validationErrorCount} błędów walidacji</span> •
        <span class="text-status-warning">⚠ ${validationWarningCount} ostrzeżeń</span> •
        <span class="text-status-error">✗ ${errorCount} błędów przetwarzania</span>
    `;

    tbody.innerHTML = results.map(result => {
        const status = result.success ? (result.saved ? 'success' : 'warning') : 'error';
        const statusText = result.success ? (result.saved ? 'Zapisano' : 'Nie zapisano') : 'Błąd';
        const statusBadge = `badge-${status}`;

        return `
            <tr>
                <td class="font-medium">${escapeHtml(result.filename)}</td>
                <td><span class="badge ${statusBadge}">${statusText}</span></td>
                <td>${result.extracted_data?.invoice_number ? escapeHtml(result.extracted_data.invoice_number) : '-'}</td>
                <td>${result.extracted_data?.seller_name ? escapeHtml(result.extracted_data.seller_name) : '-'}</td>
                <td>${result.extracted_data?.total_amount ? formatCurrency(result.extracted_data.total_amount, result.extracted_data.currency) : '-'}</td>
                <td>
                    ${result.is_duplicate ? '<span class="badge badge-warning">Tak</span>' : '<span class="badge badge-success">Nie</span>'}
                </td>
                <td>
                    ${result.validation_errors && result.validation_errors.length > 0
                ? `<div class="text-status-error text-xs">${result.validation_errors.join('<br>')}</div>`
                : ''}
                    ${result.validation_warnings && result.validation_warnings.length > 0
                ? `<div class="text-status-warning text-xs">${result.validation_warnings.join('<br>')}</div>`
                : ''}
                    ${(!result.validation_errors || result.validation_errors.length === 0) &&
                (!result.validation_warnings || result.validation_warnings.length === 0)
                ? '-' : ''}
                </td>
                <td>
                    ${result.invoice_id
                ? `<a href="/invoice/${result.invoice_id}/edit" class="text-primary hover:underline text-sm">Edytuj</a>`
                : '-'}
                </td>
            </tr>
        `;
    }).join('');

    section.classList.remove('hidden');
}

/**
 * Close results
 */
function closeResults() {
    document.getElementById('results-section').classList.add('hidden');
}
