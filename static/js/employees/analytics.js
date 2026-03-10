/**
 * Employee Analytics — Chart.js tabbed dashboard
 * Depends on Chart.js 4.4.0 (loaded via CDN in view.html).
 */

/* ─── Chart color palette ─────────────────────────────────────────────── */
const CHART_COLORS = {
    blue:   'rgba(37,99,235,1)',
    blueFill: 'rgba(37,99,235,0.15)',
    green:  'rgba(45,106,79,1)',
    greenFill: 'rgba(45,106,79,0.15)',
    purple: 'rgba(126,34,206,1)',
    purpleFill: 'rgba(126,34,206,0.15)',
    amber:  'rgba(180,83,9,1)',
    amberFill: 'rgba(180,83,9,0.15)',
    red:    'rgba(185,28,28,1)',
    redFill:'rgba(185,28,28,0.12)',
    cyan:   'rgba(8,145,178,1)',
    cyanFill: 'rgba(8,145,178,0.15)',
};

/* ─── Shared chart options ──────────────────────────────────────────────── */
const BASE_OPTS = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
};

/* ─── Utility ─────────────────────────────────────────────────────────── */
function formatCurrency(v) {
    return parseFloat(v).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' zł';
}
function escapeHtml(s) {
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

/* ─── State ───────────────────────────────────────────────────────────── */
let EMPLOYEE_ID = null;
const charts = {};  // keyed by canvas id

function destroyChart(id) {
    if (charts[id]) { charts[id].destroy(); charts[id] = null; }
}
function createChart(id, config) {
    destroyChart(id);
    const ctx = document.getElementById(id);
    if (!ctx) return null;
    charts[id] = new Chart(ctx, config);
    return charts[id];
}

/* ─── Tab switching ───────────────────────────────────────────────────── */
const TABS = ['overview', 'przychody', 'wizyty', 'umiejetnosci'];

function loadTab(tabName) {
    TABS.forEach(t => {
        const panel = document.getElementById('tab-' + t);
        const btn   = document.getElementById('tab-btn-' + t);
        if (panel) panel.style.display = (t === tabName) ? 'block' : 'none';
        if (btn)   btn.classList.toggle('analytics-tab-active', t === tabName);
    });

    if (tabName === 'overview')       loadOverview();
    if (tabName === 'przychody')      loadPrzychody();
    if (tabName === 'wizyty')         loadWizyty();
    if (tabName === 'umiejetnosci')   loadUmiejetnosci();
}

/* ─── Tab: Przegląd (Overview KPIs) ──────────────────────────────────── */
async function loadOverview() {
    setTabLoading('overview', true);
    try {
        const res = await fetch(`/api/employees/${EMPLOYEE_ID}/analytics/summary`);
        const json = await res.json();
        if (!json.success) throw new Error(json.error);
        const d = json.data;

        setText('kpi-revenue',      formatCurrency(d.total_revenue));
        setText('kpi-cost',         formatCurrency(d.employer_cost));
        const netEl = document.getElementById('kpi-net');
        if (netEl) {
            netEl.textContent = formatCurrency(d.net_profit);
            netEl.style.color = d.net_profit >= 0 ? 'var(--color-success)' : 'var(--color-error)';
        }
        setText('kpi-avg-ticket',   formatCurrency(d.avg_ticket));
        setText('kpi-appointments', `${d.total_appointments} wizyt łącznie`);
    } catch (e) {
        setTabError('overview', e.message);
    }
    setTabLoading('overview', false);
}

/* ─── Tab: Przychody ──────────────────────────────────────────────────── */
async function loadPrzychody() {
    setTabLoading('przychody', true);
    try {
        const [trenRes, comRes] = await Promise.all([
            fetch(`/api/employees/${EMPLOYEE_ID}/analytics/revenue-trend`).then(r => r.json()),
            fetch(`/api/employees/${EMPLOYEE_ID}/analytics/commission-trend`).then(r => r.json()),
        ]);
        if (!trenRes.success) throw new Error(trenRes.error);
        if (!comRes.success)  throw new Error(comRes.error);

        const trend = trenRes.data;
        const labels = trend.map(t => t.month_label);

        createChart('chart-revenue', {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Przychód',
                        data: trend.map(t => t.revenue),
                        borderColor: CHART_COLORS.blue,
                        backgroundColor: CHART_COLORS.blueFill,
                        fill: true,
                        tension: 0.3,
                        pointRadius: 3,
                    },
                    {
                        label: 'Prowizja',
                        data: trend.map(t => t.commission),
                        borderColor: CHART_COLORS.purple,
                        backgroundColor: CHART_COLORS.purpleFill,
                        fill: true,
                        tension: 0.3,
                        pointRadius: 3,
                    },
                ],
            },
            options: {
                ...BASE_OPTS,
                plugins: {
                    legend: { display: true, position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } },
                    tooltip: { callbacks: { label: ctx => ` ${formatCurrency(ctx.raw)}` } },
                },
                scales: {
                    y: { ticks: { callback: v => formatCurrency(v) }, grid: { color: 'rgba(0,0,0,0.04)' } },
                },
            },
        });

        const comData  = comRes.data;
        const comLabels = comData.map(r => r.month_label);
        createChart('chart-commission', {
            type: 'bar',
            data: {
                labels: comLabels,
                datasets: [
                    {
                        label: 'Wynagrodzenie bazowe',
                        data: comData.map(r => r.base_salary),
                        backgroundColor: CHART_COLORS.blueFill,
                        borderColor: CHART_COLORS.blue,
                        borderWidth: 1,
                    },
                    {
                        label: 'Prowizja',
                        data: comData.map(r => r.commission_earned),
                        backgroundColor: CHART_COLORS.purpleFill,
                        borderColor: CHART_COLORS.purple,
                        borderWidth: 1,
                    },
                ],
            },
            options: {
                ...BASE_OPTS,
                plugins: {
                    legend: { display: true, position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } },
                    tooltip: { callbacks: { label: ctx => ` ${formatCurrency(ctx.raw)}` } },
                },
                scales: {
                    x: { stacked: true },
                    y: { stacked: true, ticks: { callback: v => formatCurrency(v) }, grid: { color: 'rgba(0,0,0,0.04)' } },
                },
            },
        });
    } catch (e) {
        setTabError('przychody', e.message);
    }
    setTabLoading('przychody', false);
}

/* ─── Tab: Wizyty ────────────────────────────────────────────────────── */
async function loadWizyty() {
    setTabLoading('wizyty', true);
    try {
        const [trendRes, splitRes, mixRes, peakRes] = await Promise.all([
            fetch(`/api/employees/${EMPLOYEE_ID}/analytics/revenue-trend`).then(r => r.json()),
            fetch(`/api/employees/${EMPLOYEE_ID}/analytics/client-split`).then(r => r.json()),
            fetch(`/api/employees/${EMPLOYEE_ID}/analytics/services-mix`).then(r => r.json()),
            fetch(`/api/employees/${EMPLOYEE_ID}/analytics/peak-hours`).then(r => r.json()),
        ]);

        // Appointment volume line chart
        if (trendRes.success) {
            const trend = trendRes.data;
            createChart('chart-appointments', {
                type: 'line',
                data: {
                    labels: trend.map(t => t.month_label),
                    datasets: [{
                        label: 'Wizyty',
                        data: trend.map(t => t.appointments),
                        borderColor: CHART_COLORS.green,
                        backgroundColor: CHART_COLORS.greenFill,
                        fill: true,
                        tension: 0.3,
                        pointRadius: 3,
                    }],
                },
                options: {
                    ...BASE_OPTS,
                    scales: { y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.04)' } } },
                },
            });
        }

        // Client split bar chart
        if (splitRes.success) {
            const split = splitRes.data;
            createChart('chart-client-split', {
                type: 'bar',
                data: {
                    labels: split.map(r => r.month_label),
                    datasets: [
                        {
                            label: 'Nowi klienci',
                            data: split.map(r => r.new_clients),
                            backgroundColor: CHART_COLORS.cyanFill,
                            borderColor: CHART_COLORS.cyan,
                            borderWidth: 1,
                        },
                        {
                            label: 'Powracający',
                            data: split.map(r => r.returning_clients),
                            backgroundColor: CHART_COLORS.greenFill,
                            borderColor: CHART_COLORS.green,
                            borderWidth: 1,
                        },
                    ],
                },
                options: {
                    ...BASE_OPTS,
                    plugins: {
                        legend: { display: true, position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } },
                    },
                    scales: {
                        x: { stacked: true },
                        y: { stacked: true, beginAtZero: true, grid: { color: 'rgba(0,0,0,0.04)' } },
                    },
                },
            });
        }

        // Services doughnut
        if (mixRes.success && mixRes.data.length > 0) {
            const mix = mixRes.data.slice(0, 8);
            const palette = [
                CHART_COLORS.blue, CHART_COLORS.green, CHART_COLORS.purple,
                CHART_COLORS.amber, CHART_COLORS.cyan, CHART_COLORS.red,
                'rgba(251,146,60,1)', 'rgba(52,211,153,1)',
            ];
            createChart('chart-services-mix', {
                type: 'doughnut',
                data: {
                    labels: mix.map(s => s.service_name),
                    datasets: [{
                        data: mix.map(s => s.appointment_count),
                        backgroundColor: palette,
                        borderWidth: 1,
                        borderColor: '#fff',
                    }],
                },
                options: {
                    ...BASE_OPTS,
                    plugins: {
                        legend: { display: true, position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } },
                    },
                },
            });
        } else {
            const el = document.getElementById('chart-services-mix');
            if (el && el.parentElement) {
                el.parentElement.innerHTML = '<p style="color:var(--color-ink-subtle);font-size:0.8125rem;text-align:center;padding:1.5rem 0;">Brak danych o usługach</p>';
            }
        }

        // Peak hours heatmap (HTML table, not canvas)
        if (peakRes.success) {
            renderHeatmap(peakRes.data);
        }
    } catch (e) {
        setTabError('wizyty', e.message);
    }
    setTabLoading('wizyty', false);
}

/* ─── Heatmap renderer ────────────────────────────────────────────────── */
function renderHeatmap(data) {
    const container = document.getElementById('heatmap-container');
    if (!container) return;

    // Build 7×24 matrix
    const matrix = {};
    let maxCount = 0;
    data.forEach(r => {
        const key = `${r.day_of_week}-${r.hour_of_day}`;
        matrix[key] = r.appointment_count;
        if (r.appointment_count > maxCount) maxCount = r.appointment_count;
    });

    if (maxCount === 0) {
        container.innerHTML = '<p style="color:var(--color-ink-subtle);font-size:0.8125rem;text-align:center;padding:1.5rem 0;">Brak danych o godzinach szczytowych</p>';
        return;
    }

    const DAY_NAMES = ['Pn', 'Wt', 'Śr', 'Cz', 'Pt', 'Sb', 'Nd'];
    const WORK_HOURS = Array.from({length: 14}, (_, i) => i + 7); // 7–20

    let html = '<div style="overflow-x:auto;"><table style="border-collapse:collapse;font-size:0.6875rem;width:100%;">';
    // Header row
    html += '<tr><th style="padding:2px 4px;color:var(--color-ink-subtle);"></th>';
    WORK_HOURS.forEach(h => {
        html += `<th style="padding:2px 3px;color:var(--color-ink-subtle);font-weight:500;text-align:center;">${h}:00</th>`;
    });
    html += '</tr>';

    // Data rows
    for (let day = 1; day <= 7; day++) {
        html += `<tr><td style="padding:2px 6px 2px 0;color:var(--color-ink-subtle);font-weight:500;white-space:nowrap;">${DAY_NAMES[day-1]}</td>`;
        WORK_HOURS.forEach(hour => {
            const count = matrix[`${day}-${hour}`] || 0;
            const opacity = count > 0 ? 0.15 + (count / maxCount) * 0.75 : 0;
            const title = count > 0 ? `${DAY_NAMES[day-1]} ${hour}:00 — ${count} wizyt` : '';
            html += `<td title="${escapeHtml(title)}" style="
                padding:3px 2px;
                text-align:center;
                background:rgba(37,99,235,${opacity.toFixed(2)});
                border-radius:2px;
                min-width:24px;
                color:${count > 0 ? (opacity > 0.5 ? '#fff' : 'var(--color-ink)') : 'transparent'};
                font-size:0.625rem;
            ">${count > 0 ? count : ''}</td>`;
        });
        html += '</tr>';
    }
    html += '</table></div>';
    container.innerHTML = html;
}

/* ─── Tab: Umiejętności (Skills Radar) ───────────────────────────────── */
async function loadUmiejetnosci() {
    setTabLoading('umiejetnosci', true);
    try {
        const res = await fetch(`/api/employees/${EMPLOYEE_ID}/analytics/skills-radar`);
        const json = await res.json();
        if (!json.success) throw new Error(json.error);
        const skills = json.data;

        if (skills.length === 0) {
            const el = document.getElementById('chart-skills');
            if (el && el.parentElement) {
                el.parentElement.innerHTML = '<p style="color:var(--color-ink-subtle);font-size:0.875rem;text-align:center;padding:2rem 0;">Brak danych o umiejętnościach</p>';
            }
        } else {
            createChart('chart-skills', {
                type: 'radar',
                data: {
                    labels: skills.map(s => s.skill),
                    datasets: [{
                        label: 'Poziom umiejętności',
                        data: skills.map(s => s.rating),
                        backgroundColor: CHART_COLORS.blueFill,
                        borderColor: CHART_COLORS.blue,
                        pointBackgroundColor: CHART_COLORS.blue,
                        borderWidth: 2,
                        pointRadius: 4,
                    }],
                },
                options: {
                    ...BASE_OPTS,
                    plugins: { legend: { display: false } },
                    scales: {
                        r: {
                            min: 0,
                            max: 5,
                            ticks: { stepSize: 1, font: { size: 11 } },
                            pointLabels: { font: { size: 12 } },
                            grid: { color: 'rgba(0,0,0,0.06)' },
                        },
                    },
                },
            });
        }
    } catch (e) {
        setTabError('umiejetnosci', e.message);
    }
    setTabLoading('umiejetnosci', false);
}

/* ─── Helpers ─────────────────────────────────────────────────────────── */
function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}

function setTabLoading(tab, on) {
    const el = document.getElementById('tab-loading-' + tab);
    if (el) el.style.display = on ? 'block' : 'none';
}

function setTabError(tab, msg) {
    const el = document.getElementById('tab-error-' + tab);
    if (el) {
        el.style.display = 'block';
        el.textContent = 'Błąd: ' + msg;
    }
}

/* ─── Entry point ─────────────────────────────────────────────────────── */
function initAnalytics(employeeId) {
    EMPLOYEE_ID = employeeId;
    // Guard: if DOM is already ready (script placed at end of body), call directly.
    // Otherwise register for DOMContentLoaded.
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => loadTab('overview'));
    } else {
        loadTab('overview');
    }
}
