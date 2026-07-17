/**
 * Analytics Dashboard - Data Fetching and Visualization
 */

// Current period state
let currentPeriod = 'current_month';
let customStartDate = null;
let customEndDate = null;
// Drives prev/next arithmetic: 'month' and 'year' shift by calendar units
// (not day-counts, which drift across months of different lengths); 'range'
// shifts an arbitrary user-picked window by its own length.
let periodGranularity = 'month';

// Chart instances
let revenueTrendChart = null;
let servicesChart = null;
let clientSplitChart = null;
let profitBreakdownChart = null;
let monthlyTrendChart = null;
let newClientsChart = null;
let cancellationRateChart = null;
let avgTicketChart = null;
let costRatioChart = null;
let categoryMixChart = null;
let satisfactionRatingChart = null;
let topClientsLoaded = false;

/**
 * Blend a hex color toward white — softens the shared --color-chart-* tokens
 * for this dashboard's charts only (the tokens themselves stay saturated for
 * other consumers like status pills elsewhere in the app).
 */
function mutedHex(hex) {
    const mix = 0.4; // 0 = original, 1 = white
    const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
    const blend = (c) => Math.round(c + (255 - c) * mix);
    return `#${[blend(r), blend(g), blend(b)].map(v => v.toString(16).padStart(2, '0')).join('')}`;
}
function chartColor(name) {
    return mutedHex(cssVar(name));
}
function chartColorAlpha(name, alpha) {
    const hex = mutedHex(cssVar(name));
    const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
}

// Chart.js color palette — reads CSS custom properties at runtime, muted for display
const CHART_COLORS = {
    primary: chartColor('color-chart-blue'),
    purple:  chartColor('color-chart-purple'),
    pink:    chartColor('color-chart-pink'),
    orange:  chartColor('color-chart-orange'),
    green:   chartColor('color-chart-green'),
    gray:    cssVar('color-border')
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
 * Format a local Date as 'YYYY-MM-DD' without going through UTC (Date#toISOString
 * converts to UTC first, which silently shifts the calendar day for any timezone
 * ahead of UTC — see date-formatting rule: always build/read date strings from
 * local y/m/d components, never through a UTC round-trip).
 */
function toISODate(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
}

/**
 * Select period and reload dashboard
 */
function selectPeriod(period) {
    currentPeriod = period;
    customStartDate = null;
    customEndDate = null;
    periodGranularity = period === 'current_year' ? 'year' : 'month';

    // Update active button
    document.querySelectorAll('.period-selector button').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.period === period);
    });

    // Update period description
    updatePeriodDescription();

    loadDashboard();
}

/**
 * Navigate to previous or next period.
 *
 * Shifts by whole calendar months/years (not day-counts) so repeated clicks stay
 * aligned to month/year boundaries. When the target window lands back on today's
 * month/year, folds back into the named preset (re-highlighting its button)
 * instead of staying stuck on an equivalent 'custom' range.
 */
function navigatePeriod(direction) {
    const today = new Date();

    if (periodGranularity === 'year') {
        const anchorYear = currentPeriod === 'current_year'
            ? today.getFullYear()
            : new Date(customStartDate + 'T00:00:00').getFullYear();
        const targetYear = anchorYear + direction;

        if (targetYear === today.getFullYear()) {
            selectPeriod('current_year');
            return;
        }

        customStartDate = `${targetYear}-01-01`;
        customEndDate = `${targetYear}-12-31`;
        currentPeriod = 'custom';
        document.querySelectorAll('.period-selector button').forEach(btn => btn.classList.remove('active'));
    } else if (periodGranularity === 'month') {
        let anchor;
        if (currentPeriod === 'current_month') {
            anchor = new Date(today.getFullYear(), today.getMonth(), 1);
        } else if (currentPeriod === 'last_month') {
            anchor = new Date(today.getFullYear(), today.getMonth() - 1, 1);
        } else {
            anchor = new Date(customStartDate + 'T00:00:00');
        }

        const target = new Date(anchor.getFullYear(), anchor.getMonth() + direction, 1);
        const lastMonthAnchor = new Date(today.getFullYear(), today.getMonth() - 1, 1);
        const isCurrentMonth = target.getFullYear() === today.getFullYear() && target.getMonth() === today.getMonth();
        const isLastMonth = target.getFullYear() === lastMonthAnchor.getFullYear() && target.getMonth() === lastMonthAnchor.getMonth();

        if (isCurrentMonth) { selectPeriod('current_month'); return; }
        if (isLastMonth) { selectPeriod('last_month'); return; }

        const monthEnd = new Date(target.getFullYear(), target.getMonth() + 1, 0);
        customStartDate = toISODate(target);
        customEndDate = toISODate(monthEnd);
        currentPeriod = 'custom';
        document.querySelectorAll('.period-selector button').forEach(btn => btn.classList.remove('active'));
    } else {
        // Arbitrary user-picked range (from the custom-range modal) — shift by its own length
        if (!customStartDate || !customEndDate) return;
        const start = new Date(customStartDate + 'T00:00:00');
        const end = new Date(customEndDate + 'T00:00:00');
        const rangeDays = Math.round((end - start) / (1000 * 60 * 60 * 24));

        const newStart = new Date(start);
        newStart.setDate(newStart.getDate() + direction * (rangeDays + 1));
        const newEnd = new Date(newStart);
        newEnd.setDate(newEnd.getDate() + rangeDays);

        customStartDate = toISODate(newStart);
        customEndDate = toISODate(newEnd);
    }

    updatePeriodDescription();
    loadDashboard();
}

/**
 * Update period description text. Called immediately on period change (shows the
 * static label right away), then again once loadSummary() resolves the exact
 * start/end dates from the server — appended so the label always states precisely
 * what window is on screen, not just its named category.
 */
function updatePeriodDescription(startISO, endISO) {
    const descEl = document.getElementById('periodDescription');
    if (!descEl) return;

    let label;
    if (currentPeriod === 'current_month') {
        label = 'Ten miesiąc';
    } else if (currentPeriod === 'last_month') {
        label = 'Ostatni miesiąc';
    } else if (currentPeriod === 'current_year') {
        label = 'Rok do daty';
    } else if (currentPeriod === 'custom' && customStartDate && customEndDate) {
        descEl.textContent = `${formatDateLabel(customStartDate)} – ${formatDateLabel(customEndDate)}`;
        return;
    } else {
        return;
    }

    descEl.textContent = (startISO && endISO)
        ? `${label} · ${formatDateLabel(startISO)} – ${formatDateLabel(endISO)}`
        : label;
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
            loadCostRatio(),
            loadCategoryMix(),
            loadSatisfactionTrend(),
            loadTopClients()
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

    // Enrich the period label with the exact resolved dates now that we have them
    updatePeriodDescription(data.current.start_date, data.current.end_date);
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

        changeEl.textContent = `${sign}${changePct.toFixed(1)}% ${arrow} vs poprzedni okres`;
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
        Notifications.warning(MSG('analytics.pick_both_dates'));
        return;
    }

    if (new Date(startDate) > new Date(endDate)) {
        Notifications.error(MSG('analytics.date_order'));
        return;
    }

    currentPeriod = 'custom';
    customStartDate = startDate;
    customEndDate = endDate;
    periodGranularity = 'range';

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
        return;
    }

    const ctx = document.getElementById('revenueTrendChart');
    if (revenueTrendChart) revenueTrendChart.destroy();

    revenueTrendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.data.map(d => formatDateLabel(d.date)),
            datasets: [{
                label: 'Przychód',
                data: data.data.map(d => d.revenue),
                borderColor: CHART_COLORS.primary,
                backgroundColor: chartColorAlpha('color-chart-blue', 0.1),
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: (ctx) => `${formatCurrency(ctx.parsed.y)}` } }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { callback: (val) => `${val.toLocaleString('pl-PL')} zł` }
                }
            }
        }
    });
}

/**
 * Format date for chart labels
 */
function formatDateLabel(dateStr) {
    // Parse as local time per date-formatting rules (avoids UTC day-shift)
    const [y, m, d] = dateStr.split('-').map(Number);
    const date = new Date(y, m - 1, d);
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
    // Single sequential hue — these bars are one measure (revenue) ranked by
    // magnitude, not distinct categories, so a rainbow-per-bar would imply an
    // identity distinction that isn't there. Each bar is already labeled on the
    // axis, so color adds no information beyond what a single hue conveys.
    servicesChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: topServices.map(s => s.service_name),
            datasets: [{
                data: topServices.map(s => s.revenue_generated),
                backgroundColor: chartColorAlpha('color-chart-blue', 0.75),
                borderColor: chartColor('color-chart-blue'),
                borderWidth: 1,
                borderRadius: 2
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
    const newCount = data.metrics.new_clients || 0;
    const returningCount = data.metrics.returning_clients || 0;

    // Destroy existing chart
    if (clientSplitChart) {
        clientSplitChart.destroy();
    }

    if (newCount === 0 && returningCount === 0) {
        // No data — show placeholder text so canvas area isn't blank
        const wrapper = ctx ? ctx.parentElement : null;
        if (wrapper) {
            ctx.style.display = 'none';
            if (!wrapper.querySelector('.no-data-msg')) {
                const msg = document.createElement('p');
                msg.className = 'no-data-msg text-center text-sm text-[var(--color-ink-subtle)] pt-16';
                msg.textContent = 'Brak danych w wybranym okresie';
                wrapper.appendChild(msg);
            }
        }
    } else {
        // Remove any existing no-data placeholder
        if (ctx) {
            ctx.style.display = '';
            const wrapper = ctx.parentElement;
            const msg = wrapper && wrapper.querySelector('.no-data-msg');
            if (msg) msg.remove();
        }

        clientSplitChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Nowi klienci', 'Powracający'],
                datasets: [{
                    data: [newCount, returningCount],
                    backgroundColor: [CHART_COLORS.primary, CHART_COLORS.green]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });
    }

    // Update retention rate (retention_rate can be null when no prior-visit data)
    const retentionEl = document.getElementById('retentionRate');
    const retRate = data.metrics.retention_rate != null ? Number(data.metrics.retention_rate).toFixed(1) : '—';
    retentionEl.textContent = `Wskaźnik retencji (90 dni): ${retRate}%`;

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
                <td colspan="8" class="text-center text-ink-light">Brak danych</td>
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
            <td class="text-right text-sm ${
                emp.avg_satisfaction >= 4.5 ? 'text-green-600' :
                emp.avg_satisfaction >= 3.5 ? 'text-amber-500' :
                emp.avg_satisfaction ? 'text-red-500' : 'text-[var(--color-ink-subtle)]'
            }">${emp.avg_satisfaction ? `${parseFloat(emp.avg_satisfaction).toFixed(1)} ★` : '—'}</td>
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
        // F-013: the card's accent border must agree with the sign — no green border around a loss.
        const netCard = netEl.closest('.refined-card');
        if (netCard) {
            const loss = data.net_profit < 0;
            netCard.classList.toggle('border-green-500', !loss);
            netCard.classList.toggle('border-red-400', loss);
        }
    }

    // Period change badge + margin (profit_margin_pct was computed server-side but
    // never surfaced anywhere in the UI — shown here regardless of whether a
    // period-over-period comparison is available, since it's a standalone figure)
    const marginText = `marża ${data.profit_margin_pct}%`;
    if (changeEl && data.change) {
        const pct = data.change.net_profit_pct;
        const sign = pct >= 0 ? '+' : '';
        const color = pct >= 0 ? 'text-green-600' : 'text-red-600';
        const arrow = pct >= 0 ? '↑' : '↓';
        changeEl.textContent = `${sign}${pct.toFixed(1)}% ${arrow} vs poprzedni okres · ${marginText}`;
        changeEl.className = `text-sm font-medium ${color}`;
    } else if (changeEl) {
        changeEl.textContent = marginText;
        changeEl.className = 'text-sm font-medium text-[var(--color-ink-subtle)]';
    }

    // Profit breakdown chart
    const ctx = document.getElementById('profitBreakdownChart');
    if (!ctx) return;

    if (profitBreakdownChart) {
        profitBreakdownChart.destroy();
    }

    // Same 3 tokens as the KPI cards' left-border accents just above (warning =
    // employee costs, error = invoice costs, success = net profit) — the entity
    // must keep the same color everywhere it appears on the page, not just here.
    // Raw tokens (cssVar*, not the chartColor* 0.4-toward-white blend) — validated
    // with scripts/validate_palette.js; the muted version fails the chroma floor
    // on all three, the raw one passes CVD separation and contrast cleanly.
    const netProfit = data.net_profit;
    const netColor = netProfit >= 0 ? cssVarAlpha('color-success', 0.75) : cssVarAlpha('color-error', 0.75);
    const netLabel = netProfit >= 0 ? 'Zysk netto' : 'Strata netto';

    profitBreakdownChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: [''],
            datasets: [
                {
                    label: 'Koszty pracownicze',
                    data: [data.employee_costs],
                    backgroundColor: cssVarAlpha('color-warning', 0.75),
                    borderColor: cssVar('color-warning'),
                    borderWidth: 1
                },
                {
                    label: 'Koszty faktur',
                    data: [data.invoice_costs],
                    backgroundColor: cssVarAlpha('color-error', 0.75),
                    borderColor: cssVar('color-error'),
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
            `${data.booked_hours.toFixed(0)} godz. z ${data.theoretical_capacity.toFixed(0)} dostępnych`;
    }

    if (cancEl) {
        cancEl.textContent = `${data.cancellation_rate.toFixed(1)}%`;
        cancEl.style.color = data.cancellation_rate > 15 ? 'var(--color-error)' : 'var(--color-ink)';
    }
    if (cancDetailEl) cancDetailEl.textContent = `${data.cancelled} odwołań`;

    if (nsEl) {
        nsEl.textContent = `${data.no_show_rate.toFixed(1)}%`;
        nsEl.style.color = data.no_show_rate > 10 ? 'var(--color-error)' : 'var(--color-ink)';
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
        container.innerHTML = '<p class="text-center text-[var(--color-ink-muted)] py-4">Brak danych</p>';
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
        return `background:${chartColorAlpha('color-chart-blue', opacity)}`;
    };

    // Day columns get equal explicit widths; label col auto-shrinks to content (table-layout:auto)
    const dayColWidth = (100 / DISPLAY_DAYS.length).toFixed(2) + '%';
    let html = '<table style="border-collapse:collapse;width:100%">';

    // Header row: day names
    html += '<thead><tr>';
    html += '<th style="padding:4px 8px;font-size:11px;color:var(--color-chart-slate);text-align:right;white-space:nowrap">Godz.</th>';
    for (const dow of DISPLAY_DAYS) {
        html += `<th style="padding:4px 12px;font-size:11px;color:var(--color-chart-slate);text-align:center;width:${dayColWidth}">${DAY_LABELS[dow]}</th>`;
    }
    html += '</tr></thead><tbody>';

    // Data rows: one per hour
    for (const hour of HOURS) {
        html += '<tr>';
        html += `<td style="padding:3px 8px;font-size:11px;color:var(--color-ink-subtle);text-align:right;white-space:nowrap">${hour}:00</td>`;
        for (const dow of DISPLAY_DAYS) {
            const count = (grid[dow] && grid[dow][hour]) || 0;
            const title = count > 0 ? `${DAY_LABELS[dow]} ${hour}:00 — ${count} wizyt` : '';
            html += `<td title="${title}" style="padding:7px 6px;text-align:center;border-radius:5px;${cellStyle(count)}">`;
            if (count > 0) {
                html += `<span style="font-size:11px;color:var(--color-status-scheduled);font-weight:500">${count}</span>`;
            }
            html += '</td>';
        }
        html += '</tr>';
    }

    html += '</tbody></table>';
    html += '<p style="margin-top:8px;font-size:11px;color:var(--color-ink-subtle);text-align:right">' +
        'Ciemniejszy odcień = więcej rezerwacji w tym przedziale</p>';
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
        tbody.innerHTML = '<tr><td colspan="9" class="text-center text-[var(--color-ink-muted)]">Błąd ładowania danych</td></tr>';
        return;
    }

    if (data.services.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="text-center text-[var(--color-ink-muted)]">Brak danych</td></tr>';
        return;
    }

    tbody.innerHTML = data.services.filter(s => parseFloat(s.total_revenue) > 0).map(s => {
        const discount = parseFloat(s.avg_discount_pct) || 0;
        const discountColor = discount > 10 ? 'text-red-600' :
                              discount > 0  ? 'text-amber-600' : 'text-green-600';
        const rowClass = s.bookings === 0 ? 'text-[var(--color-ink-subtle)]' : '';
        const hasBookings = s.bookings > 0;

        // last_price_change is a full ISO timestamp → new Date() is safe (no date-only shift)
        const lastChange = s.last_price_change
            ? new Date(s.last_price_change).toLocaleDateString('pl-PL')
            : '—';
        // Trend over the period: current catalogue price vs price at period start
        const startPrice = s.price_at_period_start == null ? null : parseFloat(s.price_at_period_start);
        const catPrice = parseFloat(s.catalogue_price);
        let trendIcon = '—', trendColor = 'text-[var(--color-ink-subtle)]';
        if (startPrice != null) {
            if (catPrice > startPrice)      { trendIcon = '↑'; trendColor = 'text-red-600'; }
            else if (catPrice < startPrice) { trendIcon = '↓'; trendColor = 'text-green-600'; }
            else                            { trendIcon = '='; trendColor = 'text-[var(--color-ink-subtle)]'; }
        }
        return `
            <tr class="${rowClass}">
                <td class="${s.bookings === 0 ? 'italic' : 'font-medium'}">${escapeHtml(s.service_name)}</td>
                <td><span class="text-xs">${escapeHtml(s.category || '')}</span></td>
                <td class="text-right">${formatCurrency(s.catalogue_price)}</td>
                <td class="text-right text-xs">${lastChange}</td>
                <td class="text-right ${trendColor} font-medium">${trendIcon}</td>
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
        listEl.innerHTML = '<p class="text-center text-[var(--color-ink-muted)]">Brak danych do analizy</p>';
        return;
    }

    // No emoji in this UI (design system rule) — inline SVG + the same status
    // tokens used everywhere else, not Tailwind's generic red/amber/green scale.
    const TYPE_STYLE = {
        alert:   { icon: 'error',        color: 'var(--color-error)',     bg: 'rgba(155,44,44,0.08)',   border: 'rgba(155,44,44,0.2)' },
        warning: { icon: 'warning',      color: 'var(--color-warning)',   bg: 'rgba(154,103,0,0.08)',   border: 'rgba(154,103,0,0.2)' },
        success: { icon: 'check_circle', color: 'var(--color-success)',   bg: 'rgba(45,106,79,0.08)',   border: 'rgba(45,106,79,0.2)' },
        info:    { icon: 'info',         color: 'var(--color-info-text)', bg: 'var(--color-info-bg)',   border: 'var(--color-info-border)' }
    };

    listEl.innerHTML = data.insights.map(insight => {
        const style = TYPE_STYLE[insight.type] || TYPE_STYLE.info;
        return `
            <div class="flex items-start gap-3 p-3 rounded border" style="background:${style.bg};border-color:${style.border}">
                <span class="shrink-0" style="font-size:1.35rem;color:${style.color}">${Icons.svg(style.icon)}</span>
                <div>
                    <div class="font-semibold text-[1.18rem]" style="color:${style.color}">${escapeHtml(insight.title)}</div>
                    <div class="text-[1.18rem] mt-0.5 text-[var(--color-ink-muted)]">${escapeHtml(insight.message)}</div>
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
                    backgroundColor: chartColorAlpha('color-chart-blue', 0.75),
                    borderColor: chartColor('color-chart-blue'),
                    borderWidth: 1,
                    order: 2
                },
                {
                    type: 'bar',
                    label: 'Koszty pracownicze',
                    data: data.months.map(m => m.employee_costs),
                    backgroundColor: cssVarAlpha('color-warning', 0.75),
                    borderColor: cssVar('color-warning'),
                    borderWidth: 1,
                    order: 2
                },
                {
                    type: 'bar',
                    label: 'Koszty faktur',
                    data: data.months.map(m => m.invoice_costs),
                    backgroundColor: cssVarAlpha('color-error', 0.75),
                    borderColor: cssVar('color-error'),
                    borderWidth: 1,
                    order: 2
                },
                {
                    type: 'line',
                    label: 'Zysk netto',
                    data: data.months.map(m => m.profit),
                    borderColor: cssVar('color-success'),
                    backgroundColor: cssVarAlpha('color-success', 0.08),
                    borderWidth: 2.5,
                    pointRadius: 4,
                    pointBackgroundColor: data.months.map(m =>
                        m.profit >= 0 ? cssVar('color-success') : cssVar('color-error')
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

async function loadNewClients() {
    const response = await fetch('/api/analytics/rolling/new-clients');
    const data = await response.json();
    const ctx = document.getElementById('newClientsChart');
    if (!ctx || !data.success) return;

    if (newClientsChart) newClientsChart.destroy();

    const PL_MONTHS = ['Sty','Lut','Mar','Kwi','Maj','Cze','Lip','Sie','Wrz','Paź','Lis','Gru'];
    const labels = data.months.map(m => {
        const [y, mo] = m.month_start.split('-').map(Number);
        return `${PL_MONTHS[mo - 1]} ${y}`;
    });

    newClientsChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Nowi klienci',
                data: data.months.map(m => m.new_clients),
                borderColor: chartColor('color-chart-green'),
                backgroundColor: chartColorAlpha('color-chart-green', 0.1),
                borderWidth: 2,
                pointRadius: 4,
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
                        label: (ctx) => `Nowi klienci: ${ctx.parsed.y}`
                    }
                }
            },
            scales: {
                x: { grid: { display: false } },
                y: { beginAtZero: true, ticks: { stepSize: 1 } }
            }
        }
    });
}

async function loadCancellationRate() {
    const response = await fetch('/api/analytics/rolling/cancellation-rate');
    const data = await response.json();
    const ctx = document.getElementById('cancellationRateChart');
    if (!ctx || !data.success) return;

    if (cancellationRateChart) cancellationRateChart.destroy();

    const PL_MONTHS = ['Sty','Lut','Mar','Kwi','Maj','Cze','Lip','Sie','Wrz','Paź','Lis','Gru'];
    const labels = data.months.map(m => {
        const [y, mo] = m.month_start.split('-').map(Number);
        return `${PL_MONTHS[mo - 1]} ${y}`;
    });

    cancellationRateChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    // Same tokens as the "Wskaźnik odwołań" / "Nieobecności" Occupancy
                    // KPI badges (nav-occupancy) — this is their historical trend, so
                    // the entity keeps the same color everywhere it appears.
                    label: 'Odwołania',
                    data: data.months.map(m => m.cancellation_pct),
                    borderColor: cssVar('color-warning'),
                    backgroundColor: cssVarAlpha('color-warning', 0.08),
                    borderWidth: 2,
                    pointRadius: 4,
                    fill: false,
                    tension: 0.3
                },
                {
                    label: 'Nieobecności',
                    data: data.months.map(m => m.noshow_pct),
                    borderColor: cssVar('color-error'),
                    backgroundColor: cssVarAlpha('color-error', 0.08),
                    borderWidth: 2,
                    pointRadius: 4,
                    fill: false,
                    tension: 0.3
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
                        label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}%`
                    }
                }
            },
            scales: {
                x: { grid: { display: false } },
                y: {
                    beginAtZero: true,
                    ticks: { callback: (val) => `${val}%` }
                }
            }
        }
    });
}

async function loadAvgTicket() {
    const response = await fetch('/api/analytics/rolling/avg-ticket');
    const data = await response.json();
    const ctx = document.getElementById('avgTicketChart');
    if (!ctx || !data.success) return;

    if (avgTicketChart) avgTicketChart.destroy();

    const PL_MONTHS = ['Sty','Lut','Mar','Kwi','Maj','Cze','Lip','Sie','Wrz','Paź','Lis','Gru'];
    const labels = data.months.map(m => {
        const [y, mo] = m.month_start.split('-').map(Number);
        return `${PL_MONTHS[mo - 1]} ${y}`;
    });

    avgTicketChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Średni rachunek',
                data: data.months.map(m => m.avg_ticket),
                borderColor: chartColor('color-chart-blue'),
                backgroundColor: chartColorAlpha('color-chart-blue', 0.08),
                borderWidth: 2,
                pointRadius: 4,
                fill: false,
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
                        label: (ctx) => `Średni rachunek: ${formatCurrency(ctx.parsed.y)}`
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

async function loadCostRatio() {
    const response = await fetch('/api/analytics/rolling/cost-ratio');
    const data = await response.json();
    const ctx = document.getElementById('costRatioChart');
    if (!ctx || !data.success) return;

    if (costRatioChart) costRatioChart.destroy();

    const PL_MONTHS = ['Sty','Lut','Mar','Kwi','Maj','Cze','Lip','Sie','Wrz','Paź','Lis','Gru'];
    const labels = data.months.map(m => {
        const [y, mo] = m.month_start.split('-').map(Number);
        return `${PL_MONTHS[mo - 1]} ${y}`;
    });

    // Single axis only — revenue is already shown in the 12-month rolling trend
    // chart above, so this chart's one job is the cost-ratio %. Revenue and the
    // absolute invoice cost still surface in the tooltip for context, without
    // forcing a second y-scale onto the chart (dual-axis charts invite comparing
    // two incommensurable scales that happen to overlap on screen by coincidence).
    costRatioChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Udział kosztów faktur w przychodzie',
                data: data.months.map(m => m.ratio_pct),
                borderColor: cssVar('color-warning'),
                backgroundColor: cssVarAlpha('color-warning', 0.1),
                borderWidth: 2,
                pointRadius: 4,
                fill: true,
                tension: 0.3,
                _revenue: data.months.map(m => m.revenue),
                _invoiceCosts: data.months.map(m => m.invoice_costs)
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `Udział faktur: ${ctx.parsed.y ?? 0}%`,
                        afterLabel: (ctx) => {
                            const cost = ctx.dataset._invoiceCosts[ctx.dataIndex];
                            const rev = ctx.dataset._revenue[ctx.dataIndex];
                            return `${formatCurrency(cost)} z ${formatCurrency(rev)} przychodu`;
                        }
                    }
                }
            },
            scales: {
                x: { grid: { display: false } },
                y: {
                    beginAtZero: true,
                    ticks: { callback: (val) => `${val}%` }
                }
            }
        }
    });
}

/**
 * Load and render service category revenue mix (12-month rolling, stacked bar).
 * Endpoint doesn't zero-fill months the way the other /rolling/* endpoints do, so
 * the month axis is reconstructed here; categories are ranked by total revenue and
 * capped at a fixed palette size — extras fold into "Inne" rather than generating
 * new hues (a 9th+ series is never a new color, per the categorical color rule).
 */
async function loadCategoryMix() {
    const response = await fetch('/api/analytics/rolling/category-mix');
    const data = await response.json();
    const ctx = document.getElementById('categoryMixChart');
    if (!ctx || !data.success) return;

    if (categoryMixChart) categoryMixChart.destroy();

    const PL_MONTHS = ['Sty', 'Lut', 'Mar', 'Kwi', 'Maj', 'Cze', 'Lip', 'Sie', 'Wrz', 'Paź', 'Lis', 'Gru'];
    const today = new Date();
    const months = [];
    for (let i = 12; i >= 1; i--) {
        const d = new Date(today.getFullYear(), today.getMonth() - i, 1);
        months.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`);
    }
    const labels = months.map(key => {
        const [y, mo] = key.split('-').map(Number);
        return `${PL_MONTHS[mo - 1]} ${y}`;
    });

    const totals = {};
    data.rows.forEach(r => { totals[r.category] = (totals[r.category] || 0) + Number(r.revenue); });
    const ranked = Object.keys(totals).sort((a, b) => totals[b] - totals[a]);
    const TOP_N = 5;
    const topCategories = ranked.slice(0, TOP_N);
    const hasOther = ranked.length > TOP_N;

    const byMonthCategory = {};
    data.rows.forEach(r => {
        byMonthCategory[r.month_start] = byMonthCategory[r.month_start] || {};
        byMonthCategory[r.month_start][r.category] = Number(r.revenue);
    });

    // Fixed order, validated with scripts/validate_palette.js (dataviz skill) —
    // this exact sequence clears the CVD-adjacency check; chart-blue and
    // chart-purple sit too close together for deuteranopia so purple/sky are
    // deliberately excluded from this set rather than muted. Raw tokens (not the
    // 0.4-toward-white blend used elsewhere in this file) — that blend compresses
    // chroma/lightness enough to fail the floor and separation checks on a 5+
    // slot categorical set, even though it reads fine on a single translucent
    // line fill.
    const PALETTE = ['color-chart-green', 'color-chart-pink', 'color-chart-amber', 'color-chart-blue', 'color-chart-teal'];

    const datasets = topCategories.map((cat, i) => ({
        label: cat,
        data: months.map(m => (byMonthCategory[m] && byMonthCategory[m][cat]) || 0),
        backgroundColor: cssVarAlpha(PALETTE[i % PALETTE.length], 0.85),
        borderRadius: 2
    }));

    if (hasOther) {
        // Intentionally low-chroma — "Inne" is a catch-all, not a peer category,
        // and is excluded from the categorical validation above for that reason.
        datasets.push({
            label: 'Inne',
            data: months.map(m => {
                const monthData = byMonthCategory[m] || {};
                return Object.keys(monthData)
                    .filter(cat => !topCategories.includes(cat))
                    .reduce((sum, cat) => sum + monthData[cat], 0);
            }),
            backgroundColor: cssVarAlpha('color-chart-slate', 0.5),
            borderRadius: 2
        });
    }

    categoryMixChart = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${formatCurrency(ctx.parsed.y)}`
                    }
                }
            },
            scales: {
                x: { stacked: true, grid: { display: false } },
                y: {
                    stacked: true,
                    beginAtZero: true,
                    ticks: { callback: (val) => `${val.toLocaleString('pl-PL')} zł` }
                }
            }
        }
    });
}

/**
 * Load and render average client satisfaction rating (12-month rolling, 1–5 scale).
 */
async function loadSatisfactionTrend() {
    const response = await fetch('/api/analytics/rolling/satisfaction-rating');
    const data = await response.json();
    const ctx = document.getElementById('satisfactionRatingChart');
    if (!ctx || !data.success) return;

    if (satisfactionRatingChart) satisfactionRatingChart.destroy();

    const PL_MONTHS = ['Sty', 'Lut', 'Mar', 'Kwi', 'Maj', 'Cze', 'Lip', 'Sie', 'Wrz', 'Paź', 'Lis', 'Gru'];
    const labels = data.overall.map(m => {
        const [y, mo] = m.month_start.split('-').map(Number);
        return `${PL_MONTHS[mo - 1]} ${y}`;
    });

    satisfactionRatingChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Śr. ocena klientów',
                data: data.overall.map(m => m.avg_score != null ? Number(m.avg_score) : null),
                borderColor: chartColor('color-accent'),
                backgroundColor: chartColorAlpha('color-accent', 0.12),
                borderWidth: 2,
                pointRadius: 4,
                fill: true,
                tension: 0.3,
                spanGaps: true,
                _scoredCount: data.overall.map(m => m.scored_count)
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => ctx.parsed.y != null
                            ? `Śr. ocena: ${ctx.parsed.y.toFixed(2)} / 5 (${ctx.dataset._scoredCount[ctx.dataIndex]} ocen)`
                            : 'Brak ocen w tym miesiącu'
                    }
                }
            },
            scales: {
                x: { grid: { display: false } },
                y: { min: 1, max: 5, ticks: { stepSize: 1 } }
            }
        }
    });
}

async function loadTopClients() {
    const params = buildParams();
    const response = await fetch(`/api/analytics/top-clients?${params}`);
    const data = await response.json();
    const tbody = document.getElementById('topClientsTableBody');
    if (!tbody) return;

    if (!data.success || !data.clients.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-[var(--color-ink-muted)] py-2">Brak danych</td></tr>';
        return;
    }

    tbody.innerHTML = data.clients.map((c, i) => `
        <tr class="border-b border-[var(--color-border-subtle)] hover:bg-[var(--color-surface)]">
            <td class="py-1.5 text-[var(--color-ink-subtle)] text-xs">${i + 1}</td>
            <td class="py-1.5 font-medium">${escapeHtml(c.client_name)}</td>
            <td class="py-1.5 text-right text-[var(--color-ink-muted)]">${c.visits}</td>
            <td class="py-1.5 text-right text-[var(--color-ink-muted)]">${formatCurrency(c.revenue)}</td>
        </tr>
    `).join('');
}
