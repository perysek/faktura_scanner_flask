/**
 * QMS Document Control System - Table Utilities
 * Reusable functions for table sorting and filtering
 */

/**
 * Sort table by column index
 * @param {number} columnIndex - Index of column to sort (0-based)
 * @param {string} tableId - ID of the table element (default: 'resultsTable')
 */
function sortTable(columnIndex, tableId = 'resultsTable') {
    const table = document.getElementById(tableId);
    if (!table) return;

    let rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
    switching = true;
    dir = "asc";

    while (switching) {
        switching = false;
        rows = table.rows;

        for (i = 1; i < (rows.length - 1); i++) {
            shouldSwitch = false;
            x = rows[i].getElementsByTagName("TD")[columnIndex];
            y = rows[i + 1].getElementsByTagName("TD")[columnIndex];

            if (!x || !y) continue;

            const xContent = x.innerHTML.toLowerCase();
            const yContent = y.innerHTML.toLowerCase();

            // Check if numeric
            const xNum = parseFloat(xContent);
            const yNum = parseFloat(yContent);

            if (!isNaN(xNum) && !isNaN(yNum)) {
                if (dir == "asc") {
                    if (xNum > yNum) { shouldSwitch = true; break; }
                } else if (dir == "desc") {
                    if (xNum < yNum) { shouldSwitch = true; break; }
                }
            } else {
                if (dir == "asc") {
                    if (xContent > yContent) { shouldSwitch = true; break; }
                } else if (dir == "desc") {
                    if (xContent < yContent) { shouldSwitch = true; break; }
                }
            }
        }

        if (shouldSwitch) {
            rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
            switching = true;
            switchcount++;
        } else {
            if (switchcount == 0 && dir == "asc") {
                dir = "desc";
                switching = true;
            }
        }
    }

    // Update sort icon
    updateSortIcon(table, columnIndex, dir);
}

/**
 * Update sort icon to show current sort direction
 * @param {HTMLElement} table - Table element
 * @param {number} columnIndex - Index of sorted column
 * @param {string} direction - Sort direction ('asc' or 'desc')
 */
function updateSortIcon(table, columnIndex, direction) {
    const headers = table.querySelectorAll('th');
    headers.forEach((header, index) => {
        const icon = header.querySelector('.sort-icon');
        if (icon) {
            if (index === columnIndex) {
                icon.textContent = direction === 'asc' ? '↑' : '↓';
            } else {
                icon.textContent = '⇅';
            }
        }
    });
}

/**
 * Filter table by single column
 * @param {number} columnIndex - Index of column to filter (0-based)
 * @param {string} tableId - ID of the table element (default: 'resultsTable')
 */
function filterTable(columnIndex, tableId = 'resultsTable') {
    applyAllFilters(tableId);
}

/**
 * Apply all column filters simultaneously
 * @param {string} tableId - ID of the table element (default: 'resultsTable')
 */
function applyAllFilters(tableId = 'resultsTable') {
    const table = document.getElementById(tableId);
    if (!table) return;

    const tr = table.getElementsByTagName("tr");
    const inputs = table.querySelectorAll('.column-search');

    // Loop through all rows (skip header)
    for (let i = 1; i < tr.length; i++) {
        let showRow = true;

        // Check each filter (input or select)
        for (let j = 0; j < inputs.length; j++) {
            const filterElement = inputs[j];
            let filterValue = '';
            const isSelect = filterElement.tagName === 'SELECT';

            if (isSelect) {
                filterValue = filterElement.value;
            } else {
                filterValue = filterElement.value.toUpperCase();
            }

            if (filterValue) {
                const td = tr[i].getElementsByTagName("td")[j];
                if (td) {
                    const txtValue = (td.textContent || td.innerText).trim();

                    // For select dropdown: exact match (case-insensitive)
                    // For text input: contains (case-insensitive)
                    if (isSelect) {
                        if (txtValue.toUpperCase() !== filterValue.toUpperCase()) {
                            showRow = false;
                            break;
                        }
                    } else {
                        if (txtValue.toUpperCase().indexOf(filterValue) === -1) {
                            showRow = false;
                            break;
                        }
                    }
                }
            }
        }

        tr[i].style.display = showRow ? "" : "none";
    }

    // Update row count if element exists
    updateRowCount(tableId);
}

/**
 * Update visible row count
 * @param {string} tableId - ID of the table element
 */
function updateRowCount(tableId = 'resultsTable') {
    const table = document.getElementById(tableId);
    if (!table) return;

    const rows = table.getElementsByTagName("tr");
    let visibleCount = 0;

    for (let i = 1; i < rows.length; i++) {
        if (rows[i].style.display !== "none") {
            visibleCount++;
        }
    }

    const rowCountElement = document.querySelector('.row-count');
    if (rowCountElement) {
        rowCountElement.textContent = `Showing ${visibleCount} row${visibleCount !== 1 ? 's' : ''}`;
    }
}

/**
 * Clear all filters in a table
 * @param {string} tableId - ID of the table element (default: 'resultsTable')
 */
function clearFilters(tableId = 'resultsTable') {
    const table = document.getElementById(tableId);
    if (!table) return;

    const inputs = table.querySelectorAll('.column-search');
    inputs.forEach(input => {
        if (input.tagName === 'SELECT') {
            input.selectedIndex = 0;
        } else {
            input.value = '';
        }
    });

    applyAllFilters(tableId);
}

/**
 * Export table to CSV
 * @param {string} tableId - ID of the table element
 * @param {string} filename - Name of the CSV file
 */
function exportToCSV(tableId = 'resultsTable', filename = 'export.csv') {
    const table = document.getElementById(tableId);
    if (!table) return;

    const rows = table.getElementsByTagName("tr");
    const csv = [];

    // Get headers
    const headerRow = [];
    const headers = rows[0].getElementsByTagName("th");
    for (let i = 0; i < headers.length; i++) {
        const headerText = headers[i].querySelector('.th-content span')?.textContent || headers[i].textContent;
        headerRow.push('"' + headerText.trim() + '"');
    }
    csv.push(headerRow.join(','));

    // Get visible data rows only
    for (let i = 1; i < rows.length; i++) {
        // Skip hidden rows (filtered out)
        if (rows[i].style.display === 'none') {
            continue;
        }

        const row = [];
        const cols = rows[i].getElementsByTagName("td");
        for (let j = 0; j < cols.length; j++) {
            let cellText = cols[j].textContent || cols[j].innerText;
            // Escape quotes and wrap in quotes
            cellText = cellText.replace(/"/g, '""');
            row.push('"' + cellText.trim() + '"');
        }
        csv.push(row.join(','));
    }

    // Create CSV file and trigger download
    const csvContent = csv.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement("a");
    const url = URL.createObjectURL(blob);
    link.setAttribute("href", url);
    link.setAttribute("download", filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

/**
 * Initialize table with event listeners
 * @param {string} tableId - ID of the table element
 */
function initializeTable(tableId = 'resultsTable') {
    const table = document.getElementById(tableId);
    if (!table) return;

    // Add event listeners to column search inputs
    const inputs = table.querySelectorAll('.column-search');
    inputs.forEach((input, index) => {
        input.addEventListener('keyup', function () {
            applyAllFilters(tableId);
        });

        input.addEventListener('change', function () {
            applyAllFilters(tableId);
        });

        // Prevent sorting when clicking on search input
        input.addEventListener('click', function (e) {
            e.stopPropagation();
        });
    });
}

// Auto-initialize tables on page load
document.addEventListener('DOMContentLoaded', function () {
    // Initialize all tables with class 'sortable-table'
    const tables = document.querySelectorAll('.sortable-table');
    tables.forEach(table => {
        if (table.id) {
            initializeTable(table.id);
        }
    });

    // Initialize default table if it exists
    if (document.getElementById('resultsTable')) {
        initializeTable('resultsTable');
    }
});
