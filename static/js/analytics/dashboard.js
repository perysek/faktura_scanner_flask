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
            loadClients()
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
