/**
 * Employee Analytics — Chart.js tabbed dashboard
 * Depends on Chart.js 4.4.0 (loaded via CDN in view.html).
 */

/* ─── Chart color palette (reads CSS custom properties) ───────────────── */
const CHART_COLORS = {
    blue:       cssVar('color-chart-blue'),
    blueFill:   cssVarAlpha('color-chart-blue', 0.15),
    green:      cssVar('color-status-completed'),
    greenFill:  cssVarAlpha('color-status-completed', 0.15),
    purple:     cssVar('color-chart-purple'),
    purpleFill: cssVarAlpha('color-chart-purple', 0.15),
    amber:      cssVarAlpha('color-chart-amber', 1),
    amberFill:  cssVarAlpha('color-chart-amber', 0.15),
    red:        cssVar('color-chart-red'),
    redFill:    cssVarAlpha('color-chart-red', 0.12),
    cyan:       cssVarAlpha('color-chart-teal', 1),
    cyanFill:   cssVarAlpha('color-chart-teal', 0.15),
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
const TABS = ['overview', 'przychody', 'wizyty', 'umiejetnosci', 'satysfakcja'];

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
    if (tabName === 'satysfakcja')    loadSatysfakcja();
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
                        legend: { display: true, position: 'top', align: 'end', labels: { boxWidth: 12, font: { size: 11 } } },
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
                        borderColor: 'white',
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

    // Phone: 14 hour-columns can't fit without a scrollbar, which the mobile
    // spec forbids. Switch to a fixed table layout (columns share the container
    // width equally → table never exceeds 100%, so no horizontal scroll), shrink
    // hour headers to the bare number, drop the per-cell min-width, and clip so
    // nothing wraps. Desktop keeps its scrollable "h:00" layout unchanged.
    const isMobile = window.matchMedia('(max-width: 640px)').matches;
    const headText = h => isMobile ? `${h}` : `${h}:00`;
    const cellMin  = isMobile ? '0' : '24px';
    const clip     = isMobile ? 'white-space:nowrap;overflow:hidden;' : '';
    const tableStyle = isMobile
        ? 'border-collapse:collapse;font-size:0.625rem;width:100%;table-layout:fixed;'
        : 'border-collapse:collapse;font-size:0.6875rem;width:100%;';

    let html = (isMobile ? '' : '<div style="overflow-x:auto;">') + `<table style="${tableStyle}">`;
    // Header row
    html += `<tr><th style="padding:2px 4px;color:var(--color-ink-subtle);${clip}"></th>`;
    WORK_HOURS.forEach(h => {
        html += `<th style="padding:2px 3px;color:var(--color-ink-subtle);font-weight:500;text-align:center;${clip}">${headText(h)}</th>`;
    });
    html += '</tr>';

    // Data rows
    for (let day = 1; day <= 7; day++) {
        html += `<tr><td style="padding:2px 6px 2px 0;color:var(--color-ink-subtle);font-weight:500;white-space:nowrap;overflow:hidden;">${DAY_NAMES[day-1]}</td>`;
        WORK_HOURS.forEach(hour => {
            const count = matrix[`${day}-${hour}`] || 0;
            const opacity = count > 0 ? 0.15 + (count / maxCount) * 0.75 : 0;
            const title = count > 0 ? `${DAY_NAMES[day-1]} ${hour}:00 — ${count} wizyt` : '';
            html += `<td title="${escapeHtml(title)}" style="
                padding:3px 2px;
                text-align:center;
                background:${cssVarAlpha('color-chart-blue', opacity)};
                border-radius:2px;
                min-width:${cellMin};
                ${clip}
                color:${count > 0 ? (opacity > 0.5 ? 'white' : 'var(--color-ink)') : 'transparent'};
                font-size:0.625rem;
            ">${count > 0 ? count : ''}</td>`;
        });
        html += '</tr>';
    }
    html += `</table>${isMobile ? '' : '</div>'}`;
    container.innerHTML = html;
}

/* ─── Tab: Umiejętności — dual-rating services table ─────────────────── */
async function loadUmiejetnosci() {
    setTabLoading('umiejetnosci', true);
    try {
        const res = await fetch(`/api/employees/${EMPLOYEE_ID}/services-with-ratings`);
        const json = await res.json();
        if (!json.success) throw new Error(json.error);
        renderSkillsTable(json.services);
    } catch (e) {
        setTabError('umiejetnosci', e.message);
    }
    setTabLoading('umiejetnosci', false);
}

function renderSkillsTable(services) {
    const tbody = document.getElementById('skills-table-body');
    if (!services.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--color-ink-subtle);padding:2rem;font-size:0.8125rem;">Brak przypisanych usług</td></tr>';
        return;
    }

    tbody.innerHTML = services.map(svc => {
        const manualStars = renderEditableStars(svc.es_id, svc.skill_rating);
        const clientRating = svc.avg_client_rating !== null
            ? `<span style="font-weight:600;color:var(--color-ink);">${svc.avg_client_rating.toFixed(1)}</span> <span style="color:var(--color-star-filled);font-size:0.875rem;">${'★'.repeat(Math.round(svc.avg_client_rating))}${'☆'.repeat(5 - Math.round(svc.avg_client_rating))}</span>`
            : '<span style="color:var(--color-ink-subtle);">—</span>';
        const cat = svc.service_category || (svc.service_type === 'addon' ? 'Mikrousługa' : '—');
        return `<tr style="border-bottom:1px solid var(--color-border-subtle);" data-es-id="${svc.es_id}">
            <td style="padding:0.5rem;">${svc.service_name}</td>
            <td style="padding:0.5rem;color:var(--color-ink-subtle);font-size:0.75rem;">${cat}</td>
            <td style="padding:0.5rem;text-align:center;">${manualStars}</td>
            <td style="padding:0.5rem;text-align:center;">${clientRating}</td>
            <td style="padding:0.5rem;text-align:right;color:var(--color-ink-subtle);font-size:0.75rem;">${svc.scored_visits}</td>
        </tr>`;
    }).join('');

    // Attach star-click handlers
    tbody.querySelectorAll('.skill-star').forEach(star => {
        star.addEventListener('click', () => saveSkillRating(star.dataset.esId, parseInt(star.dataset.score)));
    });

    // Show radar chart if ≥3 services have a manual rating
    const rated = services.filter(s => s.skill_rating !== null);
    if (rated.length >= 3) {
        const wrap = document.getElementById('skills-radar-wrap');
        if (wrap) wrap.style.display = '';
        createChart('chart-skills', {
            type: 'radar',
            data: {
                labels: rated.map(s => s.service_name),
                datasets: [
                    {
                        label: 'Ocena manualna',
                        data: rated.map(s => s.skill_rating),
                        backgroundColor: CHART_COLORS.blueFill,
                        borderColor: CHART_COLORS.blue,
                        pointBackgroundColor: CHART_COLORS.blue,
                        borderWidth: 2,
                        pointRadius: 4,
                    },
                    {
                        label: 'Ocena klientów',
                        data: rated.map(s => s.avg_client_rating),
                        fill: false,
                        borderColor: CHART_COLORS.green,
                        pointBackgroundColor: CHART_COLORS.green,
                        borderWidth: 2,
                        pointRadius: 4,
                        spanGaps: false,
                    },
                ],
            },
            options: {
                ...BASE_OPTS,
                plugins: {
                    legend: { display: true, position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } },
                },
                scales: {
                    r: { min: 0, max: 5, ticks: { stepSize: 1, font: { size: 11 } }, pointLabels: { font: { size: 12 } }, grid: { color: 'rgba(0,0,0,0.06)' } },
                },
            },
        });
    }
}

function renderEditableStars(esId, currentRating) {
    return [1,2,3,4,5].map(n => {
        const filled = currentRating !== null && n <= currentRating;
        return `<button class="skill-star" data-es-id="${esId}" data-score="${n}"
            style="background:none;border:none;cursor:pointer;padding:0.1rem;font-size:1.25rem;line-height:1;color:${filled ? 'var(--color-star-filled)' : 'var(--color-star-empty)'};transition:color 0.1s;"
            title="Ustaw ocenę ${n}/5">${filled ? '★' : '☆'}</button>`;
    }).join('');
}

async function saveSkillRating(esId, score) {
    try {
        const res = await fetch(`/api/employees/${EMPLOYEE_ID}/services/${esId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ skill_rating: score }),
        });
        const json = await res.json();
        if (!json.success) throw new Error(json.error || 'Błąd zapisu');
        // Refresh the row stars in-place
        const row = document.querySelector(`tr[data-es-id="${esId}"]`);
        if (row) {
            const starCell = row.children[2];
            starCell.innerHTML = renderEditableStars(esId, score);
            starCell.querySelectorAll('.skill-star').forEach(star => {
                star.addEventListener('click', () => saveSkillRating(star.dataset.esId, parseInt(star.dataset.score)));
            });
        }
    } catch (e) {
        alert('Nie udało się zapisać oceny: ' + e.message);
    }
}

/* ─── Tab: Satysfakcja ───────────────────────────────────────────────── */
async function loadSatysfakcja() {
    setTabLoading('satysfakcja', true);
    try {
        const res = await fetch(`/api/employees/${EMPLOYEE_ID}/analytics/satisfaction`);
        const json = await res.json();
        if (!json.success) throw new Error(json.error);
        const d = json.data;

        // KPIs
        setText('sat-avg', d.avg_score ? `${d.avg_score} ★` : '—');
        setText('sat-count', d.total_scored ?? '—');

        // Distribution
        const dist = d.distribution || {};
        const distEl = document.getElementById('sat-dist');
        if (distEl) {
            distEl.innerHTML = [5,4,3,2,1].map(n =>
                `<div style="display:flex;align-items:center;gap:0.375rem;">
                    <span style="width:2.5rem;font-size:0.6875rem;color:var(--color-ink-subtle);">${'★'.repeat(n)}</span>
                    <div style="flex:1;background:var(--color-border-subtle);border-radius:2px;height:6px;overflow:hidden;">
                        <div style="background:rgba(245,158,11,0.7);width:${d.total_scored > 0 ? Math.round((dist[n]||0)/d.total_scored*100) : 0}%;height:100%;border-radius:2px;"></div>
                    </div>
                    <span style="width:1.5rem;text-align:right;font-size:0.6875rem;color:var(--color-ink-subtle);">${dist[n]||0}</span>
                </div>`
            ).join('');
        }

        // Category table
        const tbody = document.querySelector('#sat-category-table tbody');
        if (tbody) {
            tbody.innerHTML = d.by_service_category.length
                ? d.by_service_category.map(r => {
                    const stars = r.avg_score ? Math.round(r.avg_score) : 0;
                    const starStr = '★'.repeat(stars) + '☆'.repeat(5 - stars);
                    return `<tr style="border-bottom:1px solid var(--color-border-subtle);">
                        <td style="padding:0.4rem 0.5rem;">${escapeHtml(r.category)}</td>
                        <td style="text-align:right;padding:0.4rem 0.5rem;color:var(--color-status-in-progress);">${starStr} <span style="color:var(--color-ink-subtle);font-size:0.75rem;">(${r.avg_score ?? '—'})</span></td>
                        <td style="text-align:right;padding:0.4rem 0.5rem;color:var(--color-ink-subtle);">${r.count}</td>
                    </tr>`;
                }).join('')
                : '<tr><td colspan="3" style="text-align:center;color:var(--color-ink-subtle);padding:1rem;">Brak danych</td></tr>';
        }

        // Trend chart
        if (d.monthly_trend.length > 0) {
            createChart('chart-satisfaction-trend', {
                type: 'line',
                data: {
                    labels: d.monthly_trend.map(r => r.month_label),
                    datasets: [{
                        label: 'Śr. ocena',
                        data: d.monthly_trend.map(r => r.avg_score),
                        borderColor: 'rgba(245,158,11,1)',
                        backgroundColor: 'rgba(245,158,11,0.1)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 4,
                        spanGaps: true,
                    }],
                },
                options: {
                    ...BASE_OPTS,
                    scales: {
                        y: { min: 0, max: 5, ticks: { stepSize: 1 }, grid: { color: 'rgba(0,0,0,0.04)' } },
                    },
                    plugins: { legend: { display: false } },
                },
            });
        }
    } catch (e) {
        setTabError('satysfakcja', e.message);
    }
    setTabLoading('satysfakcja', false);
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
    const start = () => {
        // Phone (≤640px): the view.html CSS hides the tab bar and forces the
        // Przychody + Wizyty panels visible (stacked). The tab UI never runs, so
        // render both panels' charts directly instead of only the active tab.
        if (window.matchMedia('(max-width: 640px)').matches) {
            loadPrzychody();
            loadWizyty();
        } else {
            loadTab('overview');
        }
    };
    // Guard: if DOM is already ready (script placed at end of body), call directly.
    // Otherwise register for DOMContentLoaded.
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
    }
}
