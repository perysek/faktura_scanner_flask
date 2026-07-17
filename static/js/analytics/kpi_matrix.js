/**
 * Wskaźniki biznesowe — 20-indicator ISO 9001/IATF-style monthly KPI matrix.
 * Fetches /api/analytics/kpi-matrix?year=YYYY and renders a dense table that
 * fills #kpiTableWrap with no scrollbars: the table renders at a comfortable
 * base font-size, then a uniform CSS transform scales it down (never up)
 * until both its width and height fit the wrapper.
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
    const wrap = document.getElementById('kpiTableWrap');
    const scaleEl = document.getElementById('kpiTableScale');
    const table = document.getElementById('kpiTable');

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

    function buildRow(proc, ind, isFirstOfPair) {
        const tr = document.createElement('tr');
        tr.className = isFirstOfPair ? 'proc-band-a' : 'proc-band-b';

        if (isFirstOfPair) {
            const tdProc = document.createElement('td');
            tdProc.className = 'cell-process';
            tdProc.rowSpan = 2;
            tdProc.textContent = proc.id + ' · ' + proc.name;
            tr.appendChild(tdProc);
        }

        const tdInd = document.createElement('td');
        tdInd.className = 'cell-indicator';
        const kindTag = document.createElement('span');
        kindTag.className = 'kind-tag ' + (ind.kind === 'eff' ? 'kind-eff' : 'kind-effic');
        kindTag.textContent = ind.kind === 'eff' ? 'SKUT' : 'EFEK';
        kindTag.title = ind.kind === 'eff' ? 'Wskaźnik skuteczności (effectiveness)' : 'Wskaźnik efektywności (efficiency)';
        tdInd.appendChild(kindTag);
        tdInd.appendChild(document.createTextNode(ind.name));
        tr.appendChild(tdInd);

        const tdUnit = document.createElement('td');
        tdUnit.className = 'cell-unit';
        tdUnit.textContent = ind.unit;
        tr.appendChild(tdUnit);

        if (ind.unavailable_note) {
            const tdNa = document.createElement('td');
            tdNa.className = 'cell-na';
            tdNa.colSpan = 15;
            tdNa.textContent = 'brak danych źródłowych';
            tdNa.title = ind.unavailable_note;
            tr.appendChild(tdNa);
            return tr;
        }

        const tdY1 = document.createElement('td');
        tdY1.className = 'cell-yprior';
        tdY1.textContent = fmtValue(ind.y_prior, ind.unit);
        tr.appendChild(tdY1);

        for (let m = 1; m <= MONTH_COUNT; m++) {
            const v = ind.months[String(m)] !== undefined ? ind.months[String(m)] : ind.months[m];
            const td = document.createElement('td');
            td.className = statusClass(v, ind.direction, ind.target);
            td.textContent = fmtValue(v, ind.unit);
            tr.appendChild(td);
        }

        const tdYear = document.createElement('td');
        tdYear.className = 'cell-year ' + statusClass(ind.y_current, ind.direction, ind.target);
        tdYear.textContent = fmtValue(ind.y_current, ind.unit);
        tr.appendChild(tdYear);

        const tdTarget = document.createElement('td');
        tdTarget.className = 'cell-target';
        tdTarget.textContent = ind.direction + ' ' + fmtValue(ind.target, ind.unit);
        tr.appendChild(tdTarget);

        return tr;
    }

    function render(data) {
        tbody.innerHTML = '';
        data.processes.forEach(function (proc) {
            proc.indicators.forEach(function (ind, idx) {
                tbody.appendChild(buildRow(proc, ind, idx === 0));
            });
        });
        yearHeader.textContent = 'Rok ' + data.year;
        subtitle.textContent = 'Rok ' + data.year + ' — 10 procesów × 2 wskaźniki (skuteczność + efektywność)';
        autoFit();
    }

    function autoFit() {
        // Reset before measuring so a previous shrink doesn't compound.
        scaleEl.style.transform = 'none';
        const wrapW = wrap.clientWidth;
        const wrapH = wrap.clientHeight;
        const tableW = table.scrollWidth;
        const tableH = table.scrollHeight;
        if (!wrapW || !wrapH || !tableW || !tableH) return;
        const scale = Math.min(1, wrapW / tableW, wrapH / tableH);
        scaleEl.style.transform = 'scale(' + scale + ')';
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
                tbody.innerHTML = '<tr><td colspan="19" style="text-align:center;padding:2rem;color:var(--color-error);">' +
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

    let resizeTimer;
    window.addEventListener('resize', function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(autoFit, 100);
    });

    loadYear(null);
})();
