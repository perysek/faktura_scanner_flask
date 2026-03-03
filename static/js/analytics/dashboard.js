/**
 * Analytics Dashboard - Data Fetching and Visualization
 */

// Current period state
let currentPeriod = 'current_month';
let customStartDate = null;
let customEndDate = null;

// Chart instances
let revenueTrendChart = null;
let servicesChart = null;
let clientSplitChart = null;
let profitBreakdownChart = null;
let monthlyTrendChart = null;
let newClientsChart = null;
let cancellationRateChart = null;
let avgTicketChart = null;
let categoryMixChart = null;
let costRatioChart = null;
let employeeUtilisationChart = null;
let visitFrequencyChart = null;

// Chart.js color palette (Refined Minimal)
const CHART_COLORS = {
    primary: '#2563eb',    // Blue
    purple: '#7c3aed',
    pink: '#db2777',
    orange: '#ea580c',
    green: '#65a30d',
    gray: '#e2e8f0'
};

/**
 * Initialize dashboard on page load
 */
document.addEventListener('DOMContentLoaded', () => {
    // Period selector buttons
    document.querySelectorAll('.period-selector button').forEach(btn => {
        btn.addEventListener('click', () => {
            const period = btn.dataset.period;

            if (period === 'custom') {
                openCustomRangeModal();
            } else {
                selectPeriod(period);
            }
        });
    });

    // Period navigation buttons
    document.getElementById('prevPeriod').addEventListener('click', () => navigatePeriod(-1));
    document.getElementById('nextPeriod').addEventListener('click', () => navigatePeriod(1));
    document.getElementById('currentPeriod').addEventListener('click', () => {
        selectPeriod('current_month');
    });

    // Load initial data
    loadDashboard();
});

/**
 * Select period and reload dashboard
 */
function selectPeriod(period) {
    currentPeriod = period;
    customStartDate = null;
    customEndDate = null;

    // Update active button
    document.querySelectorAll('.period-selector button').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.period === period);
    });

    // Update period description
    updatePeriodDescription();

    loadDashboard();
}

/**
 * Navigate to previous or next period
 */
function navigatePeriod(direction) {
    const today = new Date();

    if (currentPeriod === 'current_month') {
        // Navigate months
        const targetMonth = new Date(today.getFullYear(), today.getMonth() + direction, 1);
        customStartDate = new Date(targetMonth.getFullYear(), targetMonth.getMonth(), 1).toISOString().split('T')[0];
        customEndDate = new Date(targetMonth.getFullYear(), targetMonth.getMonth() + 1, 0).toISOString().split('T')[0];
        currentPeriod = 'custom';

        // Clear active buttons
        document.querySelectorAll('.period-selector button').forEach(btn => {
            btn.classList.remove('active');
        });
    } else if (currentPeriod === 'custom' && customStartDate && customEndDate) {
        // Navigate by the current range length
        const start = new Date(customStartDate);
        const end = new Date(customEndDate);
        const rangeDays = Math.ceil((end - start) / (1000 * 60 * 60 * 24));

        const newStart = new Date(start);
        newStart.setDate(newStart.getDate() + (direction * rangeDays));
        const newEnd = new Date(newStart);
        newEnd.setDate(newEnd.getDate() + rangeDays);

        customStartDate = newStart.toISOString().split('T')[0];
        customEndDate = newEnd.toISOString().split('T')[0];
    }

    updatePeriodDescription();
    loadDashboard();
}

/**
 * Update period description text
 */
function updatePeriodDescription() {
    const descEl = document.getElementById('periodDescription');
    if (!descEl) return;

    if (currentPeriod === 'current_month') {
        descEl.textContent = 'Ten miesiąc';
    } else if (currentPeriod === 'last_month') {
        descEl.textContent = 'Ostatni miesiąc';
    } else if (currentPeriod === 'current_year') {
        descEl.textContent = 'Rok do daty';
    } else if (currentPeriod === 'custom' && customStartDate && customEndDate) {
        descEl.textContent = `${formatDateLabel(customStartDate)} - ${formatDateLabel(customEndDate)}`;
    }
}

/**
 * Load all dashboard data
 */
async function loadDashboard() {
    try {
        await Promise.all([
            loadSummary(),
            loadRevenueTrend(),
            loadEmployees(),
            loadServices(),
            loadClients(),
            loadProfit(),
            loadInsights(),
            loadOccupancy(),
            loadPeakHours(),
            loadServiceAnalysis(),
            loadMonthlyTrend(),
            loadNewClients(),
            loadCancellationRate(),
            loadAvgTicket(),
            loadCategoryMix(),
            loadCostRatio(),
            loadEmployeeUtilisation(),
            loadVisitFrequency()
        ]);
    } catch (error) {
        // Log error silently - empty states are handled by individual components
        console.error('Error loading dashboard:', error);
    }
}

/**
 * Load summary KPIs
 */
async function loadSummary() {
    const params = buildParams();
    const response = await fetch(`/api/analytics/summary?${params}`);
    const data = await response.json();

    if (!data.success) {
        // Silently handle error - show empty states
        updateKPI('revenue', 0, null);
        updateKPI('appointments', 0, null);
        updateKPI('clients', 0, null);
        updateKPI('avg-ticket', 0, null);
        return;
    }

    // Update KPI cards
    updateKPI('revenue', data.current.total_revenue, data.change?.revenue_pct);
    updateKPI('appointments', data.current.total_appointments, data.change?.appointments_pct);
    updateKPI('clients', data.current.unique_clients, data.change?.clients_pct);
    updateKPI('avg-ticket', data.current.avg_ticket, data.change?.avg_ticket_pct);
}

/**
 * Update KPI card with value and change percentage
 */
function updateKPI(key, value, changePct) {
    const valueEl = document.getElementById(`kpi-${key}`);
    const changeEl = document.getElementById(`kpi-${key}-change`);

    // Format value
    if (key === 'revenue' || key === 'avg-ticket') {
        valueEl.textContent = formatCurrency(value, 'PLN');
    } else {
        valueEl.textContent = value.toLocaleString('pl-PL');
    }

    // Format change percentage
    if (changePct !== null && changePct !== undefined) {
        const sign = changePct >= 0 ? '+' : '';
        const color = changePct >= 0 ? 'text-green-600' : 'text-red-600';
        const arrow = changePct >= 0 ? '↑' : '↓';

        changeEl.textContent = `${sign}${changePct.toFixed(1)}% ${arrow}`;
        changeEl.className = `text-sm font-medium ${color}`;
    } else {
        changeEl.textContent = '';
    }
}

/**
 * Build URL parameters for API requests
 */
function buildParams() {
    const params = new URLSearchParams();
    params.set('period', currentPeriod);

    if (currentPeriod === 'custom' && customStartDate && customEndDate) {
        params.set('start_date', customStartDate);
        params.set('end_date', customEndDate);
    }

    return params.toString();
}

/**
 * Format currency in Polish locale
 */
function formatCurrency(amount, currency = 'PLN') {
    return new Intl.NumberFormat('pl-PL', {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: 2
    }).format(amount);
}

/**
 * Custom date range modal functions
 */
function openCustomRangeModal() {
    document.getElementById('customRangeModal').classList.remove('hidden');
}

function closeCustomRange() {
    document.getElementById('customRangeModal').classList.add('hidden');
}

function applyCustomRange() {
    const startDate = document.getElementById('customStartDate').value;
    const endDate = document.getElementById('customEndDate').value;

    if (!startDate || !endDate) {
        Notifications.warning('Wybierz obie daty');
        return;
    }

    if (new Date(startDate) > new Date(endDate)) {
        Notifications.error('Data początkowa musi być wcześniejsza niż końcowa');
        return;
    }

    currentPeriod = 'custom';
    customStartDate = startDate;
    customEndDate = endDate;

    // Update active button
    document.querySelectorAll('.period-selector button').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.period === 'custom');
    });

    // Update period description
    updatePeriodDescription();

    closeCustomRange();
    loadDashboard();
}

/**
 * Load and render revenue trend chart
 */
async function loadRevenueTrend() {
    const params = buildParams();
    const response = await fetch(`/api/analytics/revenue-trend?${params}`);
    const data = await response.json();

    if (!data.success) {
        // Silently handle error - chart will show empty
        return;
    }

    const ctx = document.getElementById('revenueTrendChart');

    // Destroy existing chart
    if (revenueTrendChart) {
        revenueTrendChart.destroy();
    }

    // Create new chart
    revenueTrendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.data.map(d => formatDateLabel(d.date)),
            datasets: [{
                label: 'Przychód',
                data: data.data.map(d => d.revenue),
                borderColor: CHART_COLORS.primary,
                backgroundColor: 'rgba(37, 99, 235, 0.1)',
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${formatCurrency(ctx.parsed.y)}`
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: (val) => `${val.toLocaleString('pl-PL')} zł`
                    }
                }
            }
        }
    });
}

/**
 * Format date for chart labels
 */
function formatDateLabel(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' });
}

/**
 * Load and render services chart
 */
async function loadServices() {
    const params = buildParams();
    const response = await fetch(`/api/analytics/services?${params}`);
    const data = await response.json();

    if (!data.success) {
        // Silently handle error - empty state already rendered
        return;
    }

    // Take top 5 services
    const topServices = data.services.slice(0, 5);

    const ctx = document.getElementById('servicesChart');

    // Destroy existing chart
    if (servicesChart) {
        servicesChart.destroy();
    }

    // Create new chart
    servicesChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: topServices.map(s => s.service_name),
            datasets: [{
                data: topServices.map(s => s.revenue_generated),
                backgroundColor: [
                    CHART_COLORS.primary,
                    CHART_COLORS.purple,
                    CHART_COLORS.pink,
                    CHART_COLORS.orange,
                    CHART_COLORS.green
                ]
            }]
        },
        options: {
            indexAxis: 'y',  // Horizontal bars
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${formatCurrency(ctx.parsed.x)}`
                    }
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: {
                        callback: (val) => `${val.toLocaleString('pl-PL')} zł`
                    }
                }
            }
        }
    });
}

/**
 * Load and render client metrics
 */
async function loadClients() {
    const params = buildParams();
    const response = await fetch(`/api/analytics/clients?${params}`);
    const data = await response.json();

    if (!data.success) {
        // Silently handle error - empty state already rendered
        return;
    }

    // Render client split doughnut chart
    const ctx = document.getElementById('clientSplitChart');

    // Destroy existing chart
    if (clientSplitChart) {
        clientSplitChart.destroy();
    }

    // Create new chart
    clientSplitChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Nowi klienci', 'Powracający'],
            datasets: [{
                data: [
                    data.metrics.new_clients,
                    data.metrics.returning_clients
                ],
                backgroundColor: [CHART_COLORS.primary, CHART_COLORS.gray]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });

    // Update retention rate
    const retentionEl = document.getElementById('retentionRate');
    retentionEl.textContent = `Wskaźnik retencji (90 dni): ${data.metrics.retention_rate.toFixed(1)}%`;

    // Render at-risk clients list
    renderAtRiskList(data.metrics.at_risk_clients);
}

/**
 * Render at-risk clients list
 */
function renderAtRiskList(clients) {
    const listEl = document.getElementById('atRiskList');

    if (clients.length === 0) {
        listEl.innerHTML = '<p class="text-center text-ink-light">Brak klientów zagrożonych utratą</p>';
        return;
    }

    listEl.innerHTML = clients.map(client => `
        <div class="flex justify-between items-center p-2 border-b">
            <div>
                <div class="font-medium">${escapeHtml(client.client_name)}</div>
                <div class="text-sm text-ink-light">
                    Ostatnia wizyta: ${formatDateLabel(client.last_visit_date)}
                </div>
            </div>
            <div class="text-sm text-red-600">
                ${Math.floor(client.days_since_visit)} dni
            </div>
        </div>
    `).join('');
}

/**
 * Load and render employee performance table
 */
async function loadEmployees() {
    const params = buildParams();
    const response = await fetch(`/api/analytics/employees?${params}`);
    const data = await response.json();

    if (!data.success) {
        // Silently handle error - empty state already rendered
        return;
    }

    const tbody = document.getElementById('employeeTableBody');

    if (data.employees.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center text-ink-light">Brak danych</td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = data.employees.map(emp => `
        <tr>
            <td class="font-medium">${escapeHtml(emp.employee_name)}</td>
            <td class="text-right">${emp.appointments_count}</td>
            <td class="text-right">${formatCurrency(emp.revenue_generated)}</td>
            <td class="text-right">${formatCurrency(emp.commission_earned)}</td>
            <td class="text-right">${formatCurrency(emp.gross_salary)}</td>
            <td class="text-right" title="Stawka pracodawcy: ${(emp.cost_rate * 100).toFixed(1)}%">
                ${formatCurrency(emp.total_employer_cost)}
            </td>
            <td class="text-right ${emp.net_profit >= 0 ? 'text-green-600' : 'text-red-600'} font-medium">
                ${formatCurrency(emp.net_profit)}
            </td>
        </tr>
    `).join('');
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Load profit breakdown KPIs and chart
 */
async function loadProfit() {
    const params = buildParams();
    const response = await fetch(`/api/analytics/profit?${params}`);
    const data = await response.json();

    const empEl = document.getElementById('kpi-employee-costs');
    const invEl = document.getElementById('kpi-invoice-costs');
    const unpaidEl = document.getElementById('kpi-invoice-unpaid');
    const netEl = document.getElementById('kpi-net-profit');
    const changeEl = document.getElementById('kpi-net-profit-change');

    if (!data.success) {
        [empEl, invEl, netEl].forEach(el => { if (el) el.textContent = '0,00 zł'; });
        return;
    }

    if (empEl) empEl.textContent = formatCurrency(data.employee_costs);
    if (invEl) invEl.textContent = formatCurrency(data.invoice_costs);

    // Unpaid invoice hint
    if (unpaidEl) {
        if (data.invoice_details.unpaid_count > 0) {
            unpaidEl.textContent =
                `${data.invoice_details.unpaid_count} niezapłaconych: ` +
                `${formatCurrency(data.invoice_details.unpaid_amount)}`;
            unpaidEl.className = 'text-xs text-red-500';
        } else {
            unpaidEl.textContent = 'Wszystkie faktury opłacone';
            unpaidEl.className = 'text-xs text-green-600';
        }
    }

    // Net profit — colour based on sign
    if (netEl) {
        netEl.textContent = formatCurrency(data.net_profit);
        netEl.className = `text-2xl font-semibold mb-2 ${data.net_profit >= 0 ? 'text-green-600' : 'text-red-600'}`;
    }

    // Period change badge
    if (changeEl && data.change) {
        const pct = data.change.net_profit_pct;
        const sign = pct >= 0 ? '+' : '';
        const color = pct >= 0 ? 'text-green-600' : 'text-red-600';
        const arrow = pct >= 0 ? '↑' : '↓';
        changeEl.textContent = `${sign}${pct.toFixed(1)}% ${arrow} vs poprzedni okres`;
        changeEl.className = `text-sm font-medium ${color}`;
    } else if (changeEl) {
        changeEl.textContent = '';
    }

    // Profit breakdown chart
    const ctx = document.getElementById('profitBreakdownChart');
    if (!ctx) return;

    if (profitBreakdownChart) {
        profitBreakdownChart.destroy();
    }

    const netProfit = data.net_profit;
    const netColor = netProfit >= 0 ? 'rgba(34, 197, 94, 0.75)' : 'rgba(239, 68, 68, 0.75)';
    const netLabel = netProfit >= 0 ? 'Zysk netto' : 'Strata netto';

    profitBreakdownChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: [''],
            datasets: [
                {
                    label: 'Koszty pracownicze',
                    data: [data.employee_costs],
                    backgroundColor: 'rgba(234, 88, 12, 0.75)',
                    borderColor: 'rgba(234, 88, 12, 1)',
                    borderWidth: 1
                },
                {
                    label: 'Koszty faktur',
                    data: [data.invoice_costs],
                    backgroundColor: 'rgba(239, 68, 68, 0.75)',
                    borderColor: 'rgba(239, 68, 68, 1)',
                    borderWidth: 1
                },
                {
                    label: netLabel,
                    data: [Math.abs(netProfit)],
                    backgroundColor: netColor,
                    borderColor: netColor.replace('0.75', '1'),
                    borderWidth: 1
                }
            ]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${formatCurrency(ctx.parsed.x)}`
                    }
                }
            },
            scales: {
                x: {
                    stacked: true,
                    beginAtZero: true,
                    ticks: {
                        callback: (val) => `${val.toLocaleString('pl-PL')} zł`
                    }
                },
                y: { stacked: true }
            }
        }
    });
}

/**
 * Load and render occupancy KPI cards
 */
async function loadOccupancy() {
    const response = await fetch(`/api/analytics/occupancy?${buildParams()}`);
    const data = await response.json();

    const occupancyEl = document.getElementById('kpi-occupancy');
    const occupancyDetailEl = document.getElementById('kpi-occupancy-detail');
    const cancEl = document.getElementById('kpi-cancellation-rate');
    const cancDetailEl = document.getElementById('kpi-cancellation-detail');
    const nsEl = document.getElementById('kpi-noshow-rate');
    const nsDetailEl = document.getElementById('kpi-noshow-detail');

    if (!data.success) {
        [occupancyEl, cancEl, nsEl].forEach(el => { if (el) el.textContent = '—'; });
        return;
    }

    if (occupancyEl) occupancyEl.textContent = `${data.occupancy_rate.toFixed(1)}%`;
    if (occupancyDetailEl) {
        occupancyDetailEl.textContent =
            `${data.completed} wizyt z ${data.theoretical_capacity} możliwych`;
    }

    if (cancEl) {
        cancEl.textContent = `${data.cancellation_rate.toFixed(1)}%`;
        cancEl.className = `text-2xl font-semibold mb-2 ${
            data.cancellation_rate > 15 ? 'text-red-600' : 'text-slate-900'
        }`;
    }
    if (cancDetailEl) cancDetailEl.textContent = `${data.cancelled} odwołań`;

    if (nsEl) {
        nsEl.textContent = `${data.no_show_rate.toFixed(1)}%`;
        nsEl.className = `text-2xl font-semibold mb-2 ${
            data.no_show_rate > 10 ? 'text-red-600' : 'text-slate-900'
        }`;
    }
    if (nsDetailEl) nsDetailEl.textContent = `${data.no_shows} nieobecności`;
}

/**
 * Load and render peak hours heatmap (HTML table, Mon-Sat × 8-20h)
 */
async function loadPeakHours() {
    const container = document.getElementById('peakHoursHeatmap');
    if (!container) return;

    const response = await fetch(`/api/analytics/peak-hours?${buildParams()}`);
    const data = await response.json();

    if (!data.success || data.data.length === 0) {
        container.innerHTML = '<p class="text-center text-slate-500 py-4">Brak danych</p>';
        return;
    }

    // Polish day labels (0=Sun .. 6=Sat); we show Mon(1) through Sat(6)
    const DAY_LABELS = ['Nd', 'Pn', 'Wt', 'Śr', 'Cz', 'Pt', 'Sb'];
    const DISPLAY_DAYS = [1, 2, 3, 4, 5, 6]; // Mon–Sat
    const HOURS = Array.from({ length: 13 }, (_, i) => i + 8); // 8..20

    // Build lookup: grid[dow][hour] = count
    const grid = {};
    let maxCount = 0;
    for (const row of data.data) {
        const d = row.day_of_week;
        const h = row.hour_of_day;
        if (!grid[d]) grid[d] = {};
        grid[d][h] = (grid[d][h] || 0) + row.appointment_count;
        if (grid[d][h] > maxCount) maxCount = grid[d][h];
    }

    const cellStyle = (count) => {
        if (count === 0 || maxCount === 0) return 'background:transparent';
        const opacity = Math.max(0.12, count / maxCount);
        return `background:rgba(37,99,235,${opacity.toFixed(2)})`;
    };

    let html = '<table style="border-collapse:collapse;min-width:100%">';

    // Header row: day names
    html += '<thead><tr>';
    html += '<th style="padding:4px 8px;font-size:11px;color:#64748b;text-align:right">Godz.</th>';
    for (const dow of DISPLAY_DAYS) {
        html += `<th style="padding:4px 12px;font-size:11px;color:#64748b;text-align:center">${DAY_LABELS[dow]}</th>`;
    }
    html += '</tr></thead><tbody>';

    // Data rows: one per hour
    for (const hour of HOURS) {
        html += '<tr>';
        html += `<td style="padding:3px 8px;font-size:11px;color:#94a3b8;text-align:right;white-space:nowrap">${hour}:00</td>`;
        for (const dow of DISPLAY_DAYS) {
            const count = (grid[dow] && grid[dow][hour]) || 0;
            const title = count > 0 ? `${DAY_LABELS[dow]} ${hour}:00 — ${count} wizyt` : '';
            html += `<td title="${title}" style="padding:3px 6px;text-align:center;border-radius:3px;${cellStyle(count)}">`;
            if (count > 0) {
                html += `<span style="font-size:11px;color:#1e40af;font-weight:500">${count}</span>`;
            }
            html += '</td>';
        }
        html += '</tr>';
    }

    html += '</tbody></table>';
    container.innerHTML = html;
}

/**
 * Load and render service price analysis table
 */
async function loadServiceAnalysis() {
    const response = await fetch(`/api/analytics/service-analysis?${buildParams()}`);
    const data = await response.json();

    const tbody = document.getElementById('servicePriceTableBody');
    if (!tbody) return;

    if (!data.success) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-slate-500">Błąd ładowania danych</td></tr>';
        return;
    }

    if (data.services.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-slate-500">Brak danych</td></tr>';
        return;
    }

    tbody.innerHTML = data.services.map(s => {
        const discount = parseFloat(s.avg_discount_pct) || 0;
        const discountColor = discount > 10 ? 'text-red-600' :
                              discount > 0  ? 'text-amber-600' : 'text-green-600';
        const rowClass = s.bookings === 0 ? 'text-slate-400' : '';
        const hasBookings = s.bookings > 0;
        return `
            <tr class="${rowClass}">
                <td class="${s.bookings === 0 ? 'italic' : 'font-medium'}">${escapeHtml(s.service_name)}</td>
                <td><span class="text-xs">${escapeHtml(s.category || '')}</span></td>
                <td class="text-right">${formatCurrency(s.catalogue_price)}</td>
                <td class="text-right">${hasBookings ? formatCurrency(s.avg_charged) : '—'}</td>
                <td class="text-right ${hasBookings ? discountColor : ''} font-medium">
                    ${hasBookings ? `${discount.toFixed(1)}%` : '—'}
                </td>
                <td class="text-right">${s.bookings}</td>
                <td class="text-right">${hasBookings ? formatCurrency(s.total_revenue) : '—'}</td>
            </tr>
        `;
    }).join('');
}

/**
 * Load and render business insights panel
 */
async function loadInsights() {
    const params = buildParams();
    const response = await fetch(`/api/analytics/insights?${params}`);
    const data = await response.json();

    const listEl = document.getElementById('insightsList');
    if (!listEl) return;

    if (!data.success || !data.insights || data.insights.length === 0) {
        listEl.innerHTML = '<p class="text-center text-slate-500">Brak danych do analizy</p>';
        return;
    }

    const typeStyles = {
        alert:   'bg-red-50 border-red-200 text-red-700',
        warning: 'bg-amber-50 border-amber-200 text-amber-700',
        success: 'bg-green-50 border-green-200 text-green-700',
        info:    'bg-blue-50 border-blue-200 text-blue-700'
    };
    const typeIcons = {
        alert: '⚠️', warning: '⚡', success: '✓', info: 'ℹ'
    };

    listEl.innerHTML = data.insights.map(insight => {
        const style = typeStyles[insight.type] || typeStyles.info;
        const icon = typeIcons[insight.type] || 'ℹ';
        return `
            <div class="flex items-start gap-3 p-3 rounded border ${style}">
                <span class="text-lg leading-none mt-0.5">${icon}</span>
                <div>
                    <div class="font-semibold text-sm">${escapeHtml(insight.title)}</div>
                    <div class="text-sm mt-0.5">${escapeHtml(insight.message)}</div>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Load 12-month rolling profit trend chart (always relative to today, ignores period selector)
 */
async function loadMonthlyTrend() {
    const response = await fetch('/api/analytics/monthly-trend');
    const data = await response.json();
    const ctx = document.getElementById('monthlyTrendChart');
    if (!ctx || !data.success) return;

    if (monthlyTrendChart) monthlyTrendChart.destroy();

    const PL_MONTHS = ['Sty','Lut','Mar','Kwi','Maj','Cze','Lip','Sie','Wrz','Paź','Lis','Gru'];

    const labels = data.months.map(m => {
        // Parse as local time per date-formatting rules (avoids UTC day-shift)
        const [y, mo] = m.month_start.split('-').map(Number);
        return `${PL_MONTHS[mo - 1]} ${y}`;
    });

    monthlyTrendChart = new Chart(ctx, {
        data: {
            labels,
            datasets: [
                {
                    type: 'bar',
                    label: 'Przychód',
                    data: data.months.map(m => m.revenue),
                    backgroundColor: 'rgba(37, 99, 235, 0.75)',
                    borderColor: 'rgba(37, 99, 235, 1)',
                    borderWidth: 1,
                    order: 2
                },
                {
                    type: 'bar',
                    label: 'Koszty pracownicze',
                    data: data.months.map(m => m.employee_costs),
                    backgroundColor: 'rgba(234, 88, 12, 0.75)',
                    borderColor: 'rgba(234, 88, 12, 1)',
                    borderWidth: 1,
                    order: 2
                },
                {
                    type: 'bar',
                    label: 'Koszty faktur',
                    data: data.months.map(m => m.invoice_costs),
                    backgroundColor: 'rgba(239, 68, 68, 0.75)',
                    borderColor: 'rgba(239, 68, 68, 1)',
                    borderWidth: 1,
                    order: 2
                },
                {
                    type: 'line',
                    label: 'Zysk netto',
                    data: data.months.map(m => m.profit),
                    borderColor: 'rgba(22, 163, 74, 1)',
                    backgroundColor: 'rgba(22, 163, 74, 0.08)',
                    borderWidth: 2.5,
                    pointRadius: 4,
                    pointBackgroundColor: data.months.map(m =>
                        m.profit >= 0 ? 'rgba(22,163,74,1)' : 'rgba(239,68,68,1)'
                    ),
                    fill: false,
                    tension: 0.3,
                    order: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'bottom' },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${formatCurrency(ctx.parsed.y)}`
                    }
                }
            },
            scales: {
                x: { grid: { display: false } },
                y: {
                    beginAtZero: true,
                    ticks: { callback: (val) => `${val.toLocaleString('pl-PL')} zł` }
                }
            }
        }
    });
}
