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
    importBtn.addEventListener('click', importFromEmail);
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
 * Import from email
 */
async function importFromEmail() {
    const folder = document.getElementById('email-folder').value;
    const dateFrom = document.getElementById('email-date-from').value;
    const dateTo = document.getElementById('email-date-to').value;

    if (!dateFrom || !dateTo) {
        Notifications.warning('Proszę wybrać zakres dat');
        return;
    }

    const loadingModal = Modals.loading('Importowanie z e-mail...');

    try {
        const result = await API.email.import({
            folder,
            date_from: dateFrom,
            date_to: dateTo
        });

        Modals.close(loadingModal);

        if (result.success) {
            Notifications.success(`Zaimportowano ${result.total_processed} plików`);
            displayResults(result.results);
        } else {
            Notifications.error('Błąd importu z e-mail');
        }
    } catch (error) {
        Modals.close(loadingModal);
        console.error('Email import error:', error);
        Notifications.error('Błąd importu z e-mail: ' + error.message);
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
