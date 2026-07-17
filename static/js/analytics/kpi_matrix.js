/**
 * Wskaźniki biznesowe — 16-indicator ISO 9001/IATF-style monthly KPI matrix.
 * Fetches /api/analytics/kpi-matrix?year=YYYY and renders a full-width table:
 * the wrapper scrolls both axes with a sticky header row, so column count /
 * row height are not constrained to one screenful.
 */
(function () {
    'use strict';

    const MONTH_COUNT = 12;
    let currentYear = null;
    let minYear = null;
    let maxYear = null;

    const tbody = document.getElementById('kpiTbody');
    const subtitle = document.getElementById('kpiSubtitle');
    const yearHeader = document.getElementById('kpiYearColHeader');
    const yearPicker = document.getElementById('yearPicker');
    const prevBtn = document.getElementById('prevYear');
    const nextBtn = document.getElementById('nextYear');
    const currentBtn = document.getElementById('currentYear');
    const hoverTip = document.getElementById('kpiHoverTip');

    const MONTH_LABELS = ['Sty', 'Lut', 'Mar', 'Kwi', 'Maj', 'Cze', 'Lip', 'Sie', 'Wrz', 'Paź', 'Lis', 'Gru'];
    const TABLE_COLS = 18;
    let expandedKey = null;
    let expandedChart = null;

    function fmtValue(value, unit) {
        if (value === null || value === undefined) return '–';
        let text;
        if (unit === '1-5' || unit === 'wizyt/kl.' || unit === 'min') {
            text = value.toFixed(1);
        } else if (unit === 'PLN/h' || unit === 'PLN/wiz.') {
            text = Math.round(value).toLocaleString('pl-PL');
        } else {
            text = value.toFixed(1);
        }
        return text;
    }

    // Raw monthly PLN totals (unit 'PLN', e.g. "Obrót") can span a wide
    // magnitude range, so above a threshold they're shown in "tys. zł"
    // (thousands) instead of full digits — decided ONCE per row from that
    // row's own min/max across the year so every column (months + Rok/Rok-1
    // + Cel) renders in the same, comparable unit rather than flipping
    // scale from cell to cell.
    const PLN_THOUSANDS_THRESHOLD = 10000;

    function plnNeedsThousands(ind) {
        let max = 0;
        for (let m = 1; m <= MONTH_COUNT; m++) {
            const v = ind.months[String(m)] !== undefined ? ind.months[String(m)] : ind.months[m];
            if (v !== null && v !== undefined) max = Math.max(max, Math.abs(v));
        }
        if (ind.y_prior !== null && ind.y_prior !== undefined) max = Math.max(max, Math.abs(ind.y_prior));
        if (ind.y_current !== null && ind.y_current !== undefined) max = Math.max(max, Math.abs(ind.y_current));
        return max >= PLN_THOUSANDS_THRESHOLD;
    }

    function fmtPln(value, useThousands) {
        if (value === null || value === undefined) return '–';
        if (useThousands) {
            return (value / 1000).toLocaleString('pl-PL', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
        }
        return Math.round(value).toLocaleString('pl-PL');
    }

    // Single place that decides "how to print this indicator's numbers" —
    // shared by the table row and its expanded chart so both always agree.
    function getFormatter(ind) {
        if (ind.unit === 'PLN') {
            const useThousands = plnNeedsThousands(ind);
            const unitLabel = useThousands ? 'tys. zł' : 'zł';
            return { unitLabel: unitLabel, fmt: function (v) { return fmtPln(v, useThousands); } };
        }
        return { unitLabel: ind.unit, fmt: function (v) { return fmtValue(v, ind.unit); } };
    }

    function metTarget(value, direction, target) {
        if (value === null || value === undefined) return null;
        if (direction === '>') return value >= target;
        if (direction === '<') return value <= target;
        if (direction === '=') return value === target;
        return null;
    }

    function statusClass(value, direction, target) {
        const met = metTarget(value, direction, target);
        if (met === null) return '';
        return met ? 'status-good' : 'status-bad';
    }

    // Fixed-position tooltip (not CSS-only) so it escapes the scrolling
    // table wrapper's overflow:auto clipping instead of being cut off.
    function attachTip(el, text) {
        if (!text) return;
        el.classList.add('kpi-tip');
        el.addEventListener('mouseenter', function () {
            hoverTip.textContent = text;
            hoverTip.style.display = 'block';
            const r = el.getBoundingClientRect();
            const tipW = hoverTip.offsetWidth;
            let left = r.left;
            if (left + tipW > window.innerWidth - 12) left = window.innerWidth - tipW - 12;
            hoverTip.style.left = Math.max(12, left) + 'px';
            hoverTip.style.top = (r.bottom + 6) + 'px';
        });
        el.addEventListener('mouseleave', function () {
            hoverTip.style.display = 'none';
        });
    }

    function collapseExpanded() {
        if (expandedChart) {
            expandedChart.destroy();
            expandedChart = null;
        }
        const existingDetail = tbody.querySelector('.kpi-detail-row');
        if (existingDetail) existingDetail.remove();
        const existingActive = tbody.querySelector('.kpi-row-expanded');
        if (existingActive) existingActive.classList.remove('kpi-row-expanded');
        expandedKey = null;
    }

    function renderIndicatorChart(canvas, ind) {
        const values = [];
        for (let m = 1; m <= MONTH_COUNT; m++) {
            values.push(ind.months[String(m)] !== undefined ? ind.months[String(m)] : ind.months[m]);
        }
        const barColors = values.map(function (v) {
            const met = metTarget(v, ind.direction, ind.target);
            if (met === null) return 'rgba(137,135,129,0.35)';
            return met ? 'rgba(45,106,79,0.75)' : 'rgba(155,44,44,0.7)';
        });
        const formatter = getFormatter(ind);

        return new Chart(canvas.getContext('2d'), {
            type: 'bar',
            data: {
                labels: MONTH_LABELS,
                datasets: [
                    {
                        label: ind.name,
                        data: values,
                        backgroundColor: barColors,
                        borderRadius: 2,
                        order: 2
                    },
                    {
                        label: 'Cel',
                        type: 'line',
                        data: new Array(MONTH_COUNT).fill(ind.target),
                        borderColor: '#c0392b',
                        borderWidth: 2,
                        borderDash: [6, 4],
                        pointRadius: 0,
                        pointHitRadius: 0,
                        fill: false,
                        order: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 200 },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) {
                                if (ctx.dataset.label === 'Cel') {
                                    return 'Cel: ' + ind.direction + ' ' + formatter.fmt(ind.target) + ' ' + formatter.unitLabel;
                                }
                                return formatter.fmt(ctx.parsed.y) + ' ' + formatter.unitLabel;
                            }
                        }
                    }
                },
                scales: {
                    y: { beginAtZero: false, ticks: { font: { size: 11 } } },
                    x: { ticks: { font: { size: 11 } } }
                }
            }
        });
    }

    function toggleExpand(ind, tr) {
        const key = ind.key;
        const wasOpen = expandedKey === key;
        collapseExpanded();
        if (wasOpen) return;

        expandedKey = key;
        tr.classList.add('kpi-row-expanded');

        const detailTr = document.createElement('tr');
        detailTr.className = 'kpi-detail-row';
        const td = document.createElement('td');
        td.colSpan = TABLE_COLS;
        const box = document.createElement('div');
        box.className = 'kpi-chart-box';
        const canvas = document.createElement('canvas');
        box.appendChild(canvas);
        td.appendChild(box);
        detailTr.appendChild(td);
        tr.insertAdjacentElement('afterend', detailTr);

        expandedChart = renderIndicatorChart(canvas, ind);
    }

    function buildRow(proc, ind, isFirst) {
        const tr = document.createElement('tr');
        tr.className = isFirst ? 'proc-band-a' : 'proc-band-b';

        if (isFirst) {
            const tdProc = document.createElement('td');
            tdProc.className = 'cell-process';
            tdProc.rowSpan = proc.indicators.length;
            tdProc.textContent = proc.id + ' · ' + proc.name;
            tr.appendChild(tdProc);
        }

        const tdInd = document.createElement('td');
        tdInd.className = 'cell-indicator';
        const nameSpan = document.createElement('span');
        nameSpan.textContent = ind.name;
        attachTip(nameSpan, ind.description || ind.unavailable_note);
        tdInd.appendChild(nameSpan);
        tr.appendChild(tdInd);

        const formatter = getFormatter(ind);

        const tdUnit = document.createElement('td');
        tdUnit.className = 'cell-unit';
        tdUnit.textContent = formatter.unitLabel;
        tr.appendChild(tdUnit);

        if (ind.unavailable_note) {
            const tdNa = document.createElement('td');
            tdNa.className = 'cell-na';
            tdNa.colSpan = 15;
            tdNa.textContent = 'brak danych źródłowych';
            tr.appendChild(tdNa);
            return tr;
        }

        tr.classList.add('kpi-row-clickable');
        tr.addEventListener('click', function () {
            toggleExpand(ind, tr);
        });

        const tdY1 = document.createElement('td');
        tdY1.className = 'cell-yprior';
        tdY1.textContent = formatter.fmt(ind.y_prior);
        tr.appendChild(tdY1);

        for (let m = 1; m <= MONTH_COUNT; m++) {
            const v = ind.months[String(m)] !== undefined ? ind.months[String(m)] : ind.months[m];
            const td = document.createElement('td');
            td.className = statusClass(v, ind.direction, ind.target);
            td.textContent = formatter.fmt(v);
            tr.appendChild(td);
        }

        const tdYear = document.createElement('td');
        tdYear.className = 'cell-year ' + statusClass(ind.y_current, ind.direction, ind.target);
        tdYear.textContent = formatter.fmt(ind.y_current);
        tr.appendChild(tdYear);

        const tdTarget = document.createElement('td');
        tdTarget.className = 'cell-target';
        tdTarget.textContent = ind.direction + ' ' + formatter.fmt(ind.target);
        tr.appendChild(tdTarget);

        return tr;
    }

    function render(data) {
        if (expandedChart) {
            expandedChart.destroy();
            expandedChart = null;
        }
        expandedKey = null;
        tbody.innerHTML = '';
        let totalIndicators = 0;
        data.processes.forEach(function (proc) {
            totalIndicators += proc.indicators.length;
            proc.indicators.forEach(function (ind, idx) {
                tbody.appendChild(buildRow(proc, ind, idx === 0));
            });
        });
        yearHeader.textContent = 'Rok ' + data.year;
        subtitle.textContent = 'Rok ' + data.year + ' — ' + data.processes.length + ' procesów, ' +
            totalIndicators + ' wskaźników (skuteczność + efektywność)';
    }

    function populateYearPicker() {
        yearPicker.innerHTML = '';
        for (let y = maxYear; y >= minYear; y--) {
            const opt = document.createElement('option');
            opt.value = String(y);
            opt.textContent = String(y);
            yearPicker.appendChild(opt);
        }
    }

    function updateNavState() {
        yearPicker.value = String(currentYear);
        prevBtn.disabled = currentYear <= minYear;
        nextBtn.disabled = currentYear >= maxYear;
        currentBtn.disabled = currentYear >= maxYear;
    }

    function loadYear(year) {
        subtitle.textContent = 'Ładowanie…';
        const url = '/api/analytics/kpi-matrix' + (year ? ('?year=' + encodeURIComponent(year)) : '');
        fetch(url)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.success) throw new Error(data.error || 'Błąd danych');
                currentYear = data.year;
                minYear = data.min_year;
                maxYear = data.max_year;
                populateYearPicker();
                updateNavState();
                render(data);
            })
            .catch(function (err) {
                subtitle.textContent = 'Błąd ładowania danych';
                tbody.innerHTML = '<tr><td colspan="18" style="text-align:center;padding:2rem;color:var(--color-error);">' +
                    'Nie udało się wczytać wskaźników (' + err.message + ')</td></tr>';
            });
    }

    prevBtn.addEventListener('click', function () {
        if (currentYear > minYear) loadYear(currentYear - 1);
    });
    nextBtn.addEventListener('click', function () {
        if (currentYear < maxYear) loadYear(currentYear + 1);
    });
    currentBtn.addEventListener('click', function () {
        if (currentYear < maxYear) loadYear(maxYear);
    });
    yearPicker.addEventListener('change', function () {
        loadYear(parseInt(yearPicker.value, 10));
    });

    loadYear(null);
})();
