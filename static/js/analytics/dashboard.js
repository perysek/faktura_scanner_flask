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

    loadDashboard();
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
        console.error('Error loading dashboard:', error);
        Notifications.error('Błąd ładowania danych analitycznych');
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
        throw new Error(data.error || 'Failed to load summary');
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

    closeCustomRange();
    loadDashboard();
}
