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
let currentWorkflowStep = 1; // Track current workflow step

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

    // Check for unsaved processing results in localStorage
    const restoredResults = tryRestoreResults();
    if (restoredResults && restoredResults.length > 0) {
        // Ask user if they want to restore
        Modals.show({
            title: 'Przywrócić poprzednią sesję?',
            content: `
                <div class="text-center py-4">
                    ${Icons.svg('restore', 'text-primary text-5xl mb-4')}
                    <p class="text-gray-700 mb-2">Znaleziono <strong>${restoredResults.length}</strong> niezapisanych faktur z poprzedniej sesji.</p>
                    <p class="text-sm text-gray-500">Czy chcesz kontynuować pracę?</p>
                </div>
            `,
            size: 'small',
            buttons: [
                {
                    text: 'Zacznij od nowa',
                    type: 'secondary',
                    onClick: (e, overlay) => {
                        // Clear all session data
                        clearSavedResults();
                        processedResults = []; // Clear in-memory results
                        uploadedFiles = [];    // Clear staged files list

                        // Reset UI to initial state
                        document.getElementById('results-section').classList.add('hidden');
                        document.getElementById('uploaded-files-section').classList.add('hidden');
                        document.getElementById('upload-cards-grid').classList.remove('hidden');

                        Modals.close(overlay);
                        loadStagedFiles();
                        updateWorkflowStep(1);
                    }
                },
                {
                    text: 'Przywróć',
                    type: 'primary',
                    onClick: (e, overlay) => {
                        processedResults = restoredResults;
                        Modals.close(overlay);
                        displayProcessingResults();
                        Notifications.success(MSG('upload.restored', { count: restoredResults.length }));
                    }
                }
            ]
        });
    } else {
        // Load any existing staged files
        loadStagedFiles();
        // Initialize workflow step indicator
        updateWorkflowStep(1);
    }
});

/**
 * Update workflow step indicator
 * @param {number} step - Step number (1, 2, or 3)
 */
function updateWorkflowStep(step) {
    currentWorkflowStep = step;

    // Update all step indicators
    for (let i = 1; i <= 3; i++) {
        // Find the step container by data-step attribute
        const stepContainer = document.querySelector(`div[data-step="${i}"]`);
        if (!stepContainer) continue;

        const circle = stepContainer.querySelector('div.rounded-full'); // The circle container
        const numberSpan = circle?.querySelector('span'); // The number or icon/text inside
        const label = stepContainer.querySelector('div.absolute span'); // The label text below

        if (!circle || !numberSpan) continue;

        // Reset base classes
        stepContainer.classList.remove('opacity-50');

        // Remove specific state classes
        circle.className = 'w-10 h-10 rounded-full flex items-center justify-center transition-all duration-300 ring-4 ring-white shadow-sm';
        numberSpan.className = 'font-bold text-sm';

        if (i < step) {
            // Completed step
            circle.classList.add('bg-emerald-500', 'text-white', 'shadow-emerald-500/30');
            numberSpan.innerHTML = Icons.svg('check', 'text-sm');
            if (label) {
                label.className = 'block text-xs font-semibold text-emerald-600 uppercase tracking-wide';
            }
        } else if (i === step) {
            // Active step
            circle.classList.add('bg-primary-600', 'text-white', 'shadow-lg', 'shadow-primary-500/30');
            numberSpan.textContent = i;
            if (label) {
                label.className = 'block text-xs font-bold text-primary-700 uppercase tracking-wide';
            }
        } else {
            // Future step
            stepContainer.classList.add('opacity-50');
            circle.classList.add('bg-slate-200', 'text-slate-500');
            numberSpan.textContent = i;
            if (label) {
                label.className = 'block text-xs font-medium text-slate-500 uppercase tracking-wide';
            }
        }
    }
}

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
        Notifications.warning(MSG('upload.wrong_file_type'));
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
                ${Icons.svg('insert_drive_file', 'text-gray-500')}
                <div>
                    <p class="text-sm font-medium text-gray-900">${escapeHtml(file.name)}</p>
                    <p class="text-xs text-gray-500">${formatFileSize(file.size)}</p>
                </div>
            </div>
            <button onclick="removeFile(${index})" class="text-gray-400 hover:text-status-error transition-colors">
                ${Icons.svg('close', 'text-sm')}
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
        ${Icons.svg('upload', 'text-sm mr-2')}
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
            Notifications.success(MSG('upload.sent', { count: result.files.length }));

            // Clear selection
            clearFiles();

            // Load staged files and show review section
            await loadStagedFiles();
            showUploadedFilesSection();
            hideUploadControls();
        } else {
            Notifications.error(MSG('upload.send_error') +(result.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Upload error:', error);
        Notifications.error(MSG('upload.send_error') +error.message);
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
                hideUploadControls();
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
    const emailCols = document.querySelectorAll('.email-col');

    if (uploadedFiles.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-gray-500 py-4">Brak przesłanych plików</td></tr>';
        return;
    }

    // Check if any file has email metadata
    const hasEmailData = uploadedFiles.some(f => f.email_subject || f.email_sender || f.email_folder);

    // Toggle header columns
    emailCols.forEach(col => {
        if (hasEmailData) {
            col.classList.remove('hidden');
        } else {
            col.classList.add('hidden');
        }
    });

    tbody.innerHTML = uploadedFiles.map(file => `
        <tr class="hover:bg-gray-50 transition-colors">
            <td class="py-3 px-4 font-medium text-gray-900 break-all whitespace-normal">
                ${escapeHtml(file.filename)}
            </td>
            ${hasEmailData ? `
                <td class="py-3 px-2 text-gray-600 break-words whitespace-normal text-xs">${file.email_subject ? escapeHtml(file.email_subject) : '-'}</td>
                <td class="py-3 px-2 text-gray-600 break-words whitespace-normal text-xs">${file.email_sender ? escapeHtml(file.email_sender) : '-'}</td>
                <td class="py-3 px-2 text-gray-500 whitespace-nowrap text-xs">${file.email_folder ? escapeHtml(file.email_folder) : '-'}</td>
                <td class="py-3 px-2 text-gray-500 whitespace-nowrap text-xs">${file.email_date ? escapeHtml(file.email_date) : '-'}</td>
            ` : ''}
            <td class="py-3 px-4 text-gray-500 whitespace-nowrap text-xs">${formatFileSize(file.file_size)}</td>
            <td class="py-3 px-4 text-right">
                <button onclick="removeStagedFile('${escapeHtml(file.filename)}')" 
                        class="text-status-error hover:text-red-700 hover:underline text-xs font-medium transition-colors">
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
            Notifications.success(MSG('upload.file_removed', { name: filename }));
            await loadStagedFiles();

            // If no files left, show upload controls again
            if (uploadedFiles.length === 0) {
                hideUploadedFilesSection();
                showUploadControls();
            }
        } else {
            Notifications.error(MSG('upload.file_remove_error') +(result.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error removing file:', error);
        Notifications.error(MSG('upload.file_remove_error') +error.message);
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
 * Process staged documents with OCR (Step 3) - Streaming
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

    // Show progress modal
    const progressModal = showProgressModal();
    updateProgressHeader('Inicjalizacja...', 0, uploadedFiles.length);
    addProgressNotification('Rozpoczynanie przetwarzania OCR...', 'info');

    processedResults = []; // Reset results

    try {
        const response = await fetch('/api/upload/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify({})
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop(); // Keep incomplete message

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.substring(6));

                        switch (data.type) {
                            case 'start':
                                updateProgressHeader('Przetwarzanie dokumentów', 0, data.total);
                                break;

                            case 'file_start':
                                updateProgressHeader(`Przetwarzanie ${data.current}/${data.total}`, data.current, data.total);
                                addProgressNotification(`Rozpoczynanie: ${data.filename}`, 'info');
                                break;

                            case 'progress':
                                // We could update a secondary progress bar here if we had one
                                // For now just log significant steps
                                if (data.message) {
                                    // Optional: don't spam notification log with every % update
                                    // only major steps or errors
                                    // addProgressNotification(`${data.filename}: ${data.message}`, 'info');

                                    // Update the progress bar fill more smoothly based on percent if provided
                                    // (This requires updateProgressHeader to accept percent, or we manipulate DOM directly)
                                }
                                break;

                            case 'file_complete':
                                if (data.result.success) {
                                    addProgressNotification(`✓ Zakończono: ${data.result.filename}`, 'success');
                                    processedResults.push(data.result);
                                } else {
                                    addProgressNotification(`✗ Błąd: ${data.result.filename} - ${data.result.error}`, 'error');
                                    // Still push to results so we see the error state in list
                                    processedResults.push(data.result);
                                }
                                break;

                            case 'complete':
                                addProgressNotification('Przetwarzanie zakończone!', 'success');
                                break;

                            case 'error':
                                addProgressNotification(`Błąd serwera: ${data.message}`, 'error');
                                break;
                        }
                    } catch (e) {
                        console.error('Error parsing SSE:', e);
                    }
                }
            }
        }

        // Close modal after delay
        setTimeout(() => {
            Modals.close(progressModal);

            // Show results
            if (processedResults.length > 0) {
                Notifications.success(MSG('upload.processed', { count: processedResults.length }));
                hideUploadedFilesSection();
                displayProcessingResults();
            } else {
                Notifications.warning(MSG('upload.processed_none'));
            }
        }, 1000);

    } catch (error) {
        console.error('Processing error:', error);
        addProgressNotification(`Błąd komunikacji: ${error.message}`, 'error');
        setTimeout(() => Modals.close(progressModal), 2000);
        Notifications.error(MSG('upload.process_error') + error.message);
    } finally {
        processBtn.disabled = false;
    }
}

/**
 * Display processing results (Step 4) - With Editable Fields
 * UX Improvements: OCR confidence badges, email context, all fields editable
 */
function displayProcessingResults() {
    updateWorkflowStep(3); // Move to step 3: Review OCR results

    const section = document.getElementById('results-section');
    const tbody = document.getElementById('results-tbody');
    const summary = document.getElementById('results-summary');

    const successCount = processedResults.filter(r => r.success && !r.validation_errors?.length && !r.is_duplicate).length;
    const errorCount = processedResults.filter(r => !r.success).length;
    const duplicateCount = processedResults.filter(r => r.is_duplicate).length;
    const validationErrorCount = processedResults.filter(r => r.validation_errors && r.validation_errors.length > 0).length;

    // Check if any result has email metadata
    const hasEmailData = processedResults.some(r => r.email_subject || r.email_sender || r.email_folder);

    summary.innerHTML = `
        <div class="flex flex-wrap items-center gap-3">
            <span class="text-status-success">✓ ${successCount} gotowych do zapisu</span>
            <span class="text-gray-300">•</span>
            <span class="text-status-warning">⚠ ${duplicateCount} duplikatów</span>
            <span class="text-gray-300">•</span>
            <span class="text-status-error">✗ ${validationErrorCount + errorCount} błędów</span>
            <span class="flex-grow"></span>
            <button onclick="selectAllValid()" class="text-xs text-primary hover:text-primary-700 hover:underline font-medium">
                Zaznacz wszystkie poprawne
            </button>
            <button onclick="deselectAll()" class="text-xs text-gray-500 hover:text-gray-700 hover:underline">
                Odznacz wszystkie
            </button>
        </div>
    `;

    tbody.innerHTML = processedResults.map((result, index) => {
        const canAdd = result.success && !result.is_duplicate && (!result.validation_errors || result.validation_errors.length === 0);
        const status = result.success ? (canAdd ? 'success' : 'warning') : 'error';
        const statusText = result.success ? (canAdd ? 'Gotowe' : 'Wymaga uwagi') : 'Błąd';
        const statusBadge = `badge-${status}`;

        // Prepare values for inputs
        const invoiceNumber = result.extracted_data?.invoice_number || '';
        const sellerName = result.extracted_data?.seller_name || '';
        const sellerNip = result.extracted_data?.seller_nip || '';
        const bankAccount = result.extracted_data?.bank_account || '';
        const amount = result.extracted_data?.total_amount || '';
        const currency = result.extracted_data?.currency || 'PLN';
        const ocrConfidence = result.extracted_data?.ocr_confidence;

        // Date handling
        let issueDate = result.extracted_data?.issue_date || result.extracted_data?.invoice_date || '';
        if (issueDate && issueDate.length > 10) issueDate = issueDate.substring(0, 10);

        // OCR Confidence badge with color coding
        const confidenceBadge = getOcrConfidenceBadge(ocrConfidence);

        // Email context (if available)
        const emailContext = hasEmailData ? `
            <div class="text-[10px] text-gray-400 mt-1 leading-tight">
                ${result.email_sender ? `<span title="Nadawca">📧 ${escapeHtml(result.email_sender.substring(0, 25))}${result.email_sender.length > 25 ? '...' : ''}</span>` : ''}
                ${result.email_folder ? `<span class="ml-1" title="Folder">📁 ${escapeHtml(result.email_folder)}</span>` : ''}
            </div>
        ` : '';

        return `
            <tr data-result-index="${index}" class="hover:bg-gray-50 transition-colors group">
                <td class="py-3 px-2 font-medium text-gray-900 break-all whitespace-normal text-xs">
                    ${escapeHtml(result.filename)}
                    ${emailContext}
                </td>
                <td class="py-3 px-2">
                    <span class="badge ${statusBadge} text-[10px] px-1.5 py-0.5 whitespace-nowrap">${statusText}</span>
                </td>

                <!-- Editable: Invoice Number -->
                <td class="py-3 px-2">
                    <input type="text"
                           class="w-full px-2 py-1 text-xs border rounded border-slate-300 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 bg-white"
                           value="${escapeHtml(invoiceNumber)}"
                           onchange="updateResult(${index}, 'invoice_number', this.value)">
                </td>

                <!-- Editable: Date -->
                <td class="py-3 px-2">
                    <input type="date"
                           class="w-full px-2 py-1 text-xs border rounded border-slate-300 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 bg-white"
                           value="${escapeHtml(issueDate)}"
                           onchange="updateResult(${index}, 'issue_date', this.value)">
                </td>

                <!-- Editable: Seller Name -->
                <td class="py-3 px-2">
                    <input type="text"
                           class="w-full px-2 py-1 text-xs border rounded border-slate-300 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 bg-white"
                           value="${escapeHtml(sellerName)}"
                           onchange="updateResult(${index}, 'seller_name', this.value)"
                           placeholder="Nazwa sprzedawcy">
                </td>

                <!-- Editable: Seller NIP -->
                <td class="py-3 px-2">
                    <input type="text"
                           class="w-24 px-2 py-1 text-xs border rounded border-slate-300 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 bg-white font-mono"
                           value="${escapeHtml(sellerNip)}"
                           onchange="updateResult(${index}, 'seller_nip', this.value)"
                           placeholder="NIP"
                           maxlength="13">
                </td>

                <!-- Editable: Amount + Currency -->
                <td class="py-3 px-2">
                    <div class="flex items-center gap-1">
                        <input type="number" step="0.01"
                               class="w-20 px-2 py-1 text-xs border rounded border-slate-300 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 bg-white text-right font-medium"
                               value="${amount}"
                               onchange="updateResult(${index}, 'total_amount', this.value)">
                        <select class="px-1 py-1 text-xs border rounded border-slate-300 focus:border-primary-500 bg-white"
                                onchange="updateResult(${index}, 'currency', this.value)">
                            <option value="PLN" ${currency === 'PLN' ? 'selected' : ''}>PLN</option>
                            <option value="EUR" ${currency === 'EUR' ? 'selected' : ''}>EUR</option>
                            <option value="USD" ${currency === 'USD' ? 'selected' : ''}>USD</option>
                            <option value="GBP" ${currency === 'GBP' ? 'selected' : ''}>GBP</option>
                        </select>
                    </div>
                </td>

                <!-- OCR Confidence -->
                <td class="py-3 px-2 text-center">
                    ${confidenceBadge}
                </td>

                <!-- Duplicate Status -->
                <td class="py-3 px-2 text-center">
                    ${result.is_duplicate ? '<span class="badge badge-warning text-[10px]" title="Duplikat">Tak</span>' : '<span class="text-gray-300">-</span>'}
                </td>

                <!-- Warnings/Errors -->
                <td class="py-3 px-2 text-xs max-w-[150px]">
                    ${result.validation_errors && result.validation_errors.length > 0
                ? `<div class="text-status-error mb-1 break-words leading-tight text-[10px]">${result.validation_errors.slice(0, 2).join('<br>')}${result.validation_errors.length > 2 ? '<br>...' : ''}</div>`
                : ''}
                    ${result.validation_warnings && result.validation_warnings.length > 0
                ? `<div class="text-status-warning break-words leading-tight text-[10px]">${result.validation_warnings.slice(0, 2).join('<br>')}${result.validation_warnings.length > 2 ? '<br>...' : ''}</div>`
                : ''}
                    ${(!result.validation_errors || result.validation_errors.length === 0) &&
                (!result.validation_warnings || result.validation_warnings.length === 0)
                ? '<span class="text-gray-300">-</span>' : ''}
                </td>

                <td class="py-3 px-2 text-center">
                    <button onclick="viewPdf('${escapeHtml(result.filename)}')"
                            class="text-primary hover:text-primary-700 hover:bg-primary-50 p-1.5 rounded transition-colors" title="Podgląd PDF">
                        ${Icons.svg('visibility', 'text-lg')}
                    </button>
                </td>
                <td class="py-3 px-2 text-center">
                    <input type="checkbox"
                           class="form-checkbox h-4 w-4 text-primary rounded border-gray-300 focus:ring-primary add-to-list-checkbox cursor-pointer"
                           data-result-index="${index}"
                           ${canAdd ? 'checked' : ''}>
                </td>
            </tr>
        `;
    }).join('');

    section.classList.remove('hidden');

    // Save results to localStorage for recovery
    saveResultsToStorage();
}

/**
 * Get OCR confidence badge with color coding
 */
function getOcrConfidenceBadge(confidence) {
    if (confidence === null || confidence === undefined) {
        return '<span class="text-gray-400 text-[10px]">-</span>';
    }

    const conf = parseFloat(confidence);
    let badgeClass, icon;

    if (conf >= 80) {
        badgeClass = 'bg-emerald-100 text-emerald-700';
        icon = '✓';
    } else if (conf >= 60) {
        badgeClass = 'bg-amber-100 text-amber-700';
        icon = '~';
    } else {
        badgeClass = 'bg-red-100 text-red-700';
        icon = '!';
    }

    return `<span class="${badgeClass} text-[10px] px-1.5 py-0.5 rounded font-medium" title="OCR Confidence: ${conf.toFixed(1)}%">${icon} ${conf.toFixed(0)}%</span>`;
}

/**
 * Select all valid (no errors, no duplicates) invoices
 */
function selectAllValid() {
    processedResults.forEach((result, index) => {
        const canAdd = result.success && !result.is_duplicate &&
                       (!result.validation_errors || result.validation_errors.length === 0);
        const checkbox = document.querySelector(`input.add-to-list-checkbox[data-result-index="${index}"]`);
        if (checkbox) {
            checkbox.checked = canAdd;
        }
    });
    Notifications.info(MSG('upload.selected_valid', { count: processedResults.filter(r => r.success && !r.is_duplicate && (!r.validation_errors || r.validation_errors.length === 0)).length }));
}

/**
 * Deselect all invoices
 */
function deselectAll() {
    document.querySelectorAll('.add-to-list-checkbox').forEach(cb => cb.checked = false);
    Notifications.info(MSG('upload.deselected_all'));
}

/**
 * Save processing results to localStorage for recovery
 */
function saveResultsToStorage() {
    try {
        const storageData = {
            results: processedResults,
            timestamp: Date.now()
        };
        localStorage.setItem('invoice_processing_results', JSON.stringify(storageData));
    } catch (e) {
        console.warn('Could not save results to localStorage:', e);
    }
}

/**
 * Try to restore results from localStorage
 */
function tryRestoreResults() {
    try {
        const saved = localStorage.getItem('invoice_processing_results');
        if (saved) {
            const data = JSON.parse(saved);
            // Only restore if less than 1 hour old
            if (data.timestamp && (Date.now() - data.timestamp) < 3600000) {
                return data.results;
            }
        }
    } catch (e) {
        console.warn('Could not restore results from localStorage:', e);
    }
    return null;
}

/**
 * Clear saved results from localStorage
 */
function clearSavedResults() {
    localStorage.removeItem('invoice_processing_results');
}

/**
 * Update processed result data when user edits inputs
 */
function updateResult(index, field, value) {
    if (processedResults[index] && processedResults[index].extracted_data) {
        processedResults[index].extracted_data[field] = value;

        // Sync issue_date and invoice_date as backend might use either
        if (field === 'issue_date') {
            processedResults[index].extracted_data['invoice_date'] = value;
        }

        // Convert total_amount to number if it's a string
        if (field === 'total_amount' && typeof value === 'string') {
            processedResults[index].extracted_data[field] = parseFloat(value) || 0;
        }

        // Auto-check checkbox when user makes edits (assuming they're fixing issues)
        const row = document.querySelector(`tr[data-result-index="${index}"]`);
        if (row) {
            const checkbox = row.querySelector('.add-to-list-checkbox');
            if (checkbox && !checkbox.checked) {
                checkbox.checked = true;
            }
            // Visual indicator that row was modified
            row.classList.add('bg-blue-50');
        }

        // Save updated results to localStorage
        saveResultsToStorage();
    }
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
        Notifications.warning(MSG('upload.nothing_selected'));
        return;
    }

    const saveBtn = document.getElementById('save-finish-btn');
    saveBtn.disabled = true;
    saveBtn.innerHTML = Icons.svg('sync', 'text-sm mr-2 animate-spin') + 'Zapisywanie...';

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

        // Handle partial or full success
        if (result.saved_invoices && result.saved_invoices.length > 0) {
            const savedCount = result.saved_invoices.length;
            Notifications.success(MSG('upload.saved', { count: savedCount }));

            // Mark saved rows in UI
            result.saved_invoices.forEach(saved => {
                // Find row by filename
                const rowIndex = processedResults.findIndex(r => r.filename === saved.filename);
                if (rowIndex !== -1) {
                    const row = document.querySelector(`tr[data-result-index="${rowIndex}"]`);
                    const checkbox = row?.querySelector('.add-to-list-checkbox');
                    if (checkbox) {
                        checkbox.checked = false;
                        checkbox.disabled = true;
                    }
                    if (row) {
                        row.classList.add('opacity-50', 'bg-green-50');
                        row.querySelector('td:nth-child(2)').innerHTML = '<span class="badge badge-success">Zapisano</span>';
                    }
                }
            });
        }

        if (result.failed_invoices && result.failed_invoices.length > 0) {
            Notifications.error(MSG('upload.save_failed_count', { count: result.failed_invoices.length }));

            // Highlight failed rows
            result.failed_invoices.forEach(failed => {
                const rowIndex = processedResults.findIndex(r => r.filename === failed.filename);
                if (rowIndex !== -1) {
                    const row = document.querySelector(`tr[data-result-index="${rowIndex}"]`);
                    if (row) {
                        row.classList.add('bg-red-50');
                        // Add error tooltip or message
                        const statusCell = row.querySelector('td:nth-child(2)');
                        statusCell.innerHTML = `<span class="badge badge-error" title="${escapeHtml(failed.error)}">Błąd</span>`;

                        // Show error in "Uwagi" column
                        const notesCell = row.querySelector('td:nth-child(7)'); // 7th column is "Błędy walidacji" / Uwagi
                        if (notesCell) {
                            notesCell.innerHTML = `<div class="text-status-error text-xs font-bold">${escapeHtml(failed.error)}</div>` + notesCell.innerHTML;
                        }
                    }
                }
            });
        }

        // Always clear staging state and return to invoices table (spec step 5)
        clearSavedResults();
        const delay = result.failed_invoices?.length > 0 ? 2500 : 1500;
        setTimeout(() => {
            window.location.href = '/invoices';
        }, delay);

    } catch (error) {
        console.error('Save error:', error);
        Notifications.error(MSG('common.save_error') + error.message);
        clearSavedResults();
        setTimeout(() => {
            window.location.href = '/invoices';
        }, 2500);
    }
}

/**
 * Show/hide UI sections
 */
function showUploadedFilesSection() {
    document.getElementById('uploaded-files-section').classList.remove('hidden');
    updateWorkflowStep(2); // Move to step 2: Review files
}

function hideUploadedFilesSection() {
    document.getElementById('uploaded-files-section').classList.add('hidden');
    updateWorkflowStep(1); // Return to step 1 if files are cleared
}

function showUploadControls() {
    document.getElementById('upload-cards-grid').classList.remove('hidden');
}

function hideUploadControls() {
    document.getElementById('upload-cards-grid').classList.add('hidden');
}

/**
 * Clear all staged files with confirmation dialog
 */
async function clearAllStagedFiles() {
    const fileCount = uploadedFiles.length;

    if (fileCount === 0) {
        return;
    }

    // Show confirmation modal
    Modals.show({
        title: 'Usuń wszystkie pliki',
        content: `
            <div class="text-center py-4">
                ${Icons.svg('warning', 'text-status-warning text-5xl mb-4')}
                <p class="text-gray-700 mb-2">Czy na pewno chcesz usunąć <strong>${fileCount}</strong> plik${fileCount === 1 ? '' : fileCount < 5 ? 'i' : 'ów'}?</p>
                <p class="text-sm text-gray-500">Tej operacji nie można cofnąć.</p>
            </div>
        `,
        size: 'small',
        buttons: [
            {
                text: 'Anuluj',
                type: 'secondary',
                onClick: (e, overlay) => Modals.close(overlay)
            },
            {
                text: 'Usuń wszystkie',
                type: 'danger',
                onClick: async (e, overlay) => {
                    Modals.close(overlay);
                    await performClearAllStagedFiles();
                }
            }
        ]
    });
}

/**
 * Actually clear all staged files (called after confirmation)
 */
async function performClearAllStagedFiles() {
    try {
        const response = await fetch('/api/upload/staged/clear', {
            method: 'DELETE',
            credentials: 'include'
        });

        const result = await response.json();

        if (result.success) {
            Notifications.success(MSG('upload.all_deleted'));
            uploadedFiles = [];
            hideUploadedFilesSection();
            showUploadControls();
        } else {
            Notifications.error(MSG('upload.files_delete_error') +(result.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error clearing files:', error);
        Notifications.error(MSG('upload.files_delete_error') +error.message);
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
    selectFoldersBtn.innerHTML = Icons.svg('sync', 'text-sm animate-spin') + ' Pobieranie folderów...';

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

            Notifications.success(MSG('upload.folders_loaded', { count: result.folders.length }));

            // Open the modal after successful fetch
            openFolderModal();
        } else {
            Notifications.warning(MSG('upload.no_folders'));
            selectFoldersBtn.disabled = false;
            selectFoldersBtn.innerHTML = originalContent;
        }
    } catch (error) {
        console.error('Get folders error:', error);
        Notifications.error(MSG('upload.folders_error') +error.message);
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
    getFoldersBtn.innerHTML = Icons.svg('sync', 'text-sm animate-spin') + ' Pobieranie...';

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

            Notifications.success(MSG('upload.folders_loaded', { count: result.folders.length }));
        } else {
            Notifications.warning(MSG('upload.no_folders'));
        }
    } catch (error) {
        console.error('Get folders error:', error);
        Notifications.error(MSG('upload.folders_error') +error.message);
    } finally {
        // Re-enable button
        getFoldersBtn.disabled = false;
        getFoldersBtn.innerHTML = Icons.svg('folder', 'text-sm') + ' Pobierz foldery';
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

    // Try to load from localStorage if global state is empty/default
    if (!isAllFoldersSelected && selectedFolders.length === 0) {
        try {
            const saved = localStorage.getItem('email_import_preferences');
            if (saved) {
                const parsed = JSON.parse(saved);
                isAllFoldersSelected = parsed.isAll;
                selectedFolders = parsed.folders || [];
                
                // Also update the display text since we just loaded preferences
                updateSelectedFoldersDisplay();
                updateImportButtonState();
            }
        } catch (e) {
            console.error('Error loading email preferences:', e);
        }
    }

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
        if (allChecked && folderCheckboxes.length > 0) {
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

    // Save to localStorage
    const storageData = {
        isAll: isAllFoldersSelected,
        folders: selectedFolders
    };
    localStorage.setItem('email_import_preferences', JSON.stringify(storageData));

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
        ${Icons.svg(icon, 'text-sm mt-0.5')}
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
        Notifications.warning(MSG('upload.pick_folder'));
        return;
    }

    if (!dateFrom || !dateTo) {
        Notifications.warning(MSG('upload.pick_date_range'));
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
                Notifications.success(MSG('upload.import_done', { count: finalResults.total_processed }));

                // Load staged files and show review section
                await loadStagedFiles();
                showUploadedFilesSection();
                hideUploadControls();
            } else {
                Notifications.warning(MSG('upload.no_pdfs'));
            }
        }, 1000);

    } catch (error) {
        console.error('Email import error:', error);
        addProgressNotification(`Błąd: ${error.message}`, 'error');
        setTimeout(() => {
            Modals.close(progressModal);
            Notifications.error(MSG('upload.import_error') + error.message);
        }, 1000);
    }
}
