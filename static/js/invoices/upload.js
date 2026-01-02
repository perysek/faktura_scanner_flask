/**
 * Upload Page JavaScript - Multi-Step Workflow
 * Author: AI Assistant
 * 
 * Workflow Steps:
 * 1. Upload files (folder or email) → stage without processing  
 * 2. Review uploaded files table → remove unwanted files
 * 3. Process with OCR → extract invoice data
 * 4. Review results → view PDFs, select files to save
 * 5. Save and finish → write to database, redirect to list
 */

let selectedFiles = [];
let uploadedFiles = []; // Staged files from server
let processedResults = []; // OCR processing results

// Email import state
let availableFolders = [];
let selectedFolders = [];
let isAllFoldersSelected = false;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    setupFileUpload();
    setupEmailImport();
    setDefaultDates();
    setupProcessButton();
    setupSaveFinishButton();

    // Load any existing staged files
    loadStagedFiles();
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

    // Upload button - stages files
    uploadBtn.addEventListener('click', stageFiles);
}

/**
 * Handle selected files
 */
const ALLOWED_TYPES = [
    'application/pdf',
    'image/jpeg',
    'image/png',
    'image/tiff',
    'image/bmp'
];

const ALLOWED_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'];

function isAllowedFile(file) {
    // Check MIME type
    if (ALLOWED_TYPES.includes(file.type)) {
        return true;
    }
    // Fallback: check extension (for files with missing MIME type)
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    return ALLOWED_EXTENSIONS.includes(ext);
}

function handleFiles(files) {
    const allowedFiles = Array.from(files).filter(file => isAllowedFile(file));

    if (allowedFiles.length === 0) {
        Notifications.warning('Proszę wybrać pliki PDF lub obrazy (JPG, PNG, TIFF, BMP)');
        return;
    }

    selectedFiles = [...selectedFiles, ...allowedFiles];
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
                <span class="material-icons text-gray-500">insert_drive_file</span>
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

    uploadBtn.innerHTML = `
        <span class="material-icons text-sm mr-2">upload</span>
        Prześlij pliki${hasFiles ? ` (${selectedFiles.length})` : ''}
    `;
}

/**
 * Stage files (Step 1) - Upload without processing
 */
async function stageFiles() {
    if (selectedFiles.length === 0) return;

    const uploadBtn = document.getElementById('upload-btn');
    const progressContainer = document.getElementById('upload-progress');
    const progressBar = document.getElementById('progress-bar');
    const progressPercent = document.getElementById('progress-percent');

    // Show progress
    progressContainer.classList.remove('hidden');
    uploadBtn.disabled = true;

    try {
        const formData = new FormData();
        selectedFiles.forEach(file => {
            formData.append('files[]', file);
        });

        const response = await fetch('/api/upload/stage', {
            method: 'POST',
            body: formData,
            credentials: 'include' // Important for session cookies
        });

        const result = await response.json();

        if (result.success) {
            Notifications.success(`Przesłano ${result.files.length} plików`);

            // Clear selection
            clearFiles();

            // Load staged files and show review section
            await loadStagedFiles();
            showUploadedFilesSection();
            hideUploadControls();
        } else {
            Notifications.error('Błąd przesyłania plików: ' + (result.error || 'Unknown error'));
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
 * Load staged files from server
 */
async function loadStagedFiles() {
    try {
        const response = await fetch('/api/upload/staged', {
            credentials: 'include'
        });

        const result = await response.json();

        if (result.success) {
            uploadedFiles = result.files;

            if (uploadedFiles.length > 0) {
                displayUploadedFiles();
                showUploadedFilesSection();
            }
        }
    } catch (error) {
        console.error('Error loading staged files:', error);
    }
}

/**
 * Display uploaded files in review table (Step 2)
 */
function displayUploadedFiles() {
    const tbody = document.getElementById('uploaded-files-tbody');

    if (uploadedFiles.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-gray-500 py-4">Brak przesłanych plików</td></tr>';
        return;
    }

    tbody.innerHTML = uploadedFiles.map(file => `
        <tr>
            <td class="font-medium">${escapeHtml(file.filename)}</td>
            <td>${file.email_subject ? escapeHtml(file.email_subject) : '-'}</td>
            <td>${file.email_sender ? escapeHtml(file.email_sender) : '-'}</td>
            <td>${file.email_folder ? escapeHtml(file.email_folder) : '-'}</td>
            <td>${file.email_date ? escapeHtml(file.email_date) : '-'}</td>
            <td>${formatFileSize(file.file_size)}</td>
            <td>
                <button onclick="removeStagedFile('${escapeHtml(file.filename)}')" 
                        class="text-status-error hover:underline text-sm">
                    Usuń
                </button>
            </td>
        </tr>
    `).join('');
}

/**
 * Remove staged file (Step 2)
 */
async function removeStagedFile(filename) {
    try {
        const response = await fetch(`/api/upload/staged/${encodeURIComponent(filename)}`, {
            method: 'DELETE',
            credentials: 'include'
        });

        const result = await response.json();

        if (result.success) {
            Notifications.success(`Plik ${filename} usunięty`);
            await loadStagedFiles();

            // If no files left, show upload controls again
            if (uploadedFiles.length === 0) {
                hideUploadedFilesSection();
                showUploadControls();
            }
        } else {
            Notifications.error('Błąd usuwania pliku: ' + (result.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error removing file:', error);
        Notifications.error('Błąd usuwania pliku: ' + error.message);
    }
}

/**
 * Setup process documents button
 */
function setupProcessButton() {
    const processBtn = document.getElementById('process-documents-btn');
    processBtn.addEventListener('click', processDocuments);

    const clearAllBtn = document.getElementById('clear-all-btn');
    clearAllBtn.addEventListener('click', clearAllStagedFiles);
}

/**
 * Process staged documents with OCR (Step 3)
 */
async function processDocuments() {
    // Check if there are any files to process
    if (uploadedFiles.length === 0) {
        // No files to process - just clear and return to upload view
        await clearAllStagedFiles();
        return;
    }

    const processBtn = document.getElementById('process-documents-btn');
    processBtn.disabled = true;
    processBtn.innerHTML = '<span class="material-icons text-sm mr-2 animate-spin">sync</span>Przetwarzanie...';

    try {
        const response = await fetch('/api/upload/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify({})
        });

        const result = await response.json();

        if (result.success) {
            processedResults = result.results;
            Notifications.success(`Przetworzono ${processedResults.length} plików`);

            // Hide uploaded files section, show results
            hideUploadedFilesSection();
            displayProcessingResults();
        } else {
            Notifications.error('Błąd przetwarzania: ' + (result.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Processing error:', error);
        Notifications.error('Błąd przetwarzania: ' + error.message);
    } finally {
        processBtn.disabled = false;
        processBtn.innerHTML = '<span class="material-icons text-sm mr-2">auto_fix_high</span>Przetwórz dokumenty';
    }
}

/**
 * Display processing results (Step 4)
 */
function displayProcessingResults() {
    const section = document.getElementById('results-section');
    const tbody = document.getElementById('results-tbody');
    const summary = document.getElementById('results-summary');

    const successCount = processedResults.filter(r => r.success && !r.validation_errors?.length && !r.is_duplicate).length;
    const errorCount = processedResults.filter(r => !r.success).length;
    const duplicateCount = processedResults.filter(r => r.is_duplicate).length;
    const validationErrorCount = processedResults.filter(r => r.validation_errors && r.validation_errors.length > 0).length;

    summary.innerHTML = `
        <span class="text-status-success">✓ ${successCount} gotowych do zapisu</span> •
        <span class="text-status-warning">⚠ ${duplicateCount} duplikatów</span> •
        <span class="text-status-error">✗ ${validationErrorCount} błędów walidacji</span> •
        <span class="text-status-error">✗ ${errorCount} błędów przetwarzania</span>
    `;

    tbody.innerHTML = processedResults.map((result, index) => {
        const canAdd = result.success && !result.is_duplicate && (!result.validation_errors || result.validation_errors.length === 0);
        const status = result.success ? (canAdd ? 'success' : 'warning') : 'error';
        const statusText = result.success ? (canAdd ? 'Gotowe' : 'Wymaga uwagi') : 'Błąd';
        const statusBadge = `badge-${status}`;

        return `
            <tr data-result-index="${index}">
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
                    <button onclick="viewPdf('${escapeHtml(result.filename)}')" 
                            class="text-primary hover:underline text-sm flex items-center gap-1">
                        <span class="material-icons text-sm">visibility</span>
                        Podgląd
                    </button>
                </td>
                <td>
                    <input type="checkbox" 
                           class="form-checkbox h-4 w-4 text-primary add-to-list-checkbox" 
                           data-result-index="${index}"
                           ${canAdd ? 'checked' : ''}>
                </td>
            </tr>
        `;
    }).join('');

    section.classList.remove('hidden');
}

/**
 * View PDF file
 */
function viewPdf(filename) {
    const url = `/api/upload/view-pdf/${encodeURIComponent(filename)}`;
    window.open(url, '_blank');
}

/**
 * Setup save and finish button
 */
function setupSaveFinishButton() {
    const saveBtn = document.getElementById('save-finish-btn');
    saveBtn.addEventListener('click', saveAndFinish);
}

/**
 * Save selected invoices and finish (Step 5)
 */
async function saveAndFinish() {
    // Get all checked checkboxes
    const checkboxes = document.querySelectorAll('.add-to-list-checkbox:checked');

    if (checkboxes.length === 0) {
        Notifications.warning('Nie wybrano żadnych faktur do zapisu');
        return;
    }

    const saveBtn = document.getElementById('save-finish-btn');
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span class="material-icons text-sm mr-2 animate-spin">sync</span>Zapisywanie...';

    try {
        // Prepare invoices to save
        const invoicesToSave = [];
        checkboxes.forEach(checkbox => {
            const index = parseInt(checkbox.dataset.resultIndex);
            const result = processedResults[index];
            invoicesToSave.push(result);
        });

        const response = await fetch('/api/upload/finalize', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify({
                invoices: invoicesToSave
            })
        });

        const result = await response.json();

        if (result.success) {
            Notifications.success(`Zapisano ${result.count} faktur!`);

            // Reset everything and redirect to list
            setTimeout(() => {
                window.location.href = '/invoices';
            }, 1500);
        } else {
            Notifications.error('Błąd zapisu: ' + (result.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Save error:', error);
        Notifications.error('Błąd zapisu: ' + error.message);
    } finally {
        saveBtn.disabled = false;
        saveBtn.innerHTML = '<span class="material-icons text-sm mr-2">save</span>Zapisz i zakończ';
    }
}

/**
 * Show/hide UI sections
 */
function showUploadedFilesSection() {
    document.getElementById('uploaded-files-section').classList.remove('hidden');
}

function hideUploadedFilesSection() {
    document.getElementById('uploaded-files-section').classList.add('hidden');
}

function showUploadControls() {
    document.getElementById('upload-cards-grid').classList.remove('hidden');
}

function hideUploadControls() {
    document.getElementById('upload-cards-grid').classList.add('hidden');
}

/**
 * Clear all staged files and return to upload view
 */
async function clearAllStagedFiles() {

    try {
        const response = await fetch('/api/upload/staged/clear', {
            method: 'DELETE',
            credentials: 'include'
        });

        const result = await response.json();

        if (result.success) {
            Notifications.success('Wszystkie pliki usunięte');
            uploadedFiles = [];
            hideUploadedFilesSection();
            showUploadControls();
        } else {
            Notifications.error('Błąd usuwania plików: ' + (result.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error clearing files:', error);
        Notifications.error('Błąd usuwania plików: ' + error.message);
    }
}

/**
 * Close results and return to upload
 */
function closeResults() {
    // Always clear everything and return to upload view
    document.getElementById('results-section').classList.add('hidden');
    // Clear staged files and return to fresh upload view
    clearAllStagedFilesQuiet();
}

/**
 * Clear all staged files without confirmation (for internal use)
 */
async function clearAllStagedFilesQuiet() {
    try {
        await fetch('/api/upload/staged/clear', {
            method: 'DELETE',
            credentials: 'include'
        });

        uploadedFiles = [];
        hideUploadedFilesSection();
        showUploadControls();
    } catch (error) {
        console.error('Error clearing files:', error);
    }
}

// ============================================================================
// EMAIL IMPORT FUNCTIONS
// ============================================================================

/**
 * Setup email import
 */
function setupEmailImport() {
    const importBtn = document.getElementById('email-import-btn');
    const selectFoldersBtn = document.getElementById('select-folders-btn');

    importBtn.addEventListener('click', importFromEmail);
    selectFoldersBtn.addEventListener('click', async () => {
        // Fetch folders first, then open modal
        await getFoldersAndOpenModal();
    });
}

/**
 * Get folders and then open modal
 */
async function getFoldersAndOpenModal() {
    const selectFoldersBtn = document.getElementById('select-folders-btn');
    const folderList = document.getElementById('folder-list');

    // Disable button during fetch
    const originalContent = selectFoldersBtn.innerHTML;
    selectFoldersBtn.disabled = true;
    selectFoldersBtn.innerHTML = '<span class="material-icons text-sm animate-spin">sync</span> Pobieranie folderów...';

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

            // Restore button FIRST so text span exists again  
            selectFoldersBtn.disabled = false;
            selectFoldersBtn.innerHTML = originalContent;

            // Now safely update the text
            const textSpan = document.getElementById('selected-folders-text');
            if (textSpan) {
                textSpan.textContent = 'Kliknij aby wybrać foldery';
                textSpan.classList.remove('text-gray-500');
                textSpan.classList.add('text-gray-700');
            }

            Notifications.success(`Załadowano ${result.folders.length} folderów`);

            // Open the modal after successful fetch
            openFolderModal();
        } else {
            Notifications.warning('Nie znaleziono folderów e-mail');
            selectFoldersBtn.disabled = false;
            selectFoldersBtn.innerHTML = originalContent;
        }
    } catch (error) {
        console.error('Get folders error:', error);
        Notifications.error('Błąd pobierania folderów: ' + error.message);
        selectFoldersBtn.disabled = false;
        selectFoldersBtn.innerHTML = originalContent;
    }
}

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
 * Import from email - Now uses staging workflow
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
            credentials: 'include', // Important for session
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
                                addProgressNotification(`✅ Import zakończony: pobrano ${data.total_processed} plików`, 'success');
                                break;
                        }
                    } catch (e) {
                        console.error('Error parsing SSE message:', e);
                    }
                }
            }
        }

        // Close modal after a short delay
        setTimeout(async () => {
            Modals.close(progressModal);
            if (finalResults && finalResults.total_processed > 0) {
                Notifications.success(`Import zakończony: pobrano ${finalResults.total_processed} plików`);

                // Load staged files and show review section
                await loadStagedFiles();
                showUploadedFilesSection();
                hideUploadControls();
            } else {
                Notifications.warning('Nie znaleziono plików PDF w wybranych folderach');
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
