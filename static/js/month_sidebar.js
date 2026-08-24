/**
 * MonthSidebar — shared 3-month day-picker for the day-view (calendar.html)
 * and list-view (list.html) appointment pages.
 *
 * The window is a FIXED rolling anchor: today's real calendar month, +1, +2.
 * It never follows whatever date the host page is currently browsing to —
 * that's a deliberate call (see plans/… redesign notes), not an oversight.
 *
 * One fetch of /api/appointments covers the whole 3-month span and backs
 * both the has-visits dot markers on the mini grids AND the list-view's
 * progressive day-chain (getAppointmentsForDay / getVisitDaysInMonthOf) —
 * no second round-trip needed when a day gets clicked.
 *
 * Usage:
 *   <script src="{{ asset_url('js/month_sidebar.js') }}"></script>
 *   MonthSidebar.init({ onDaySelect: (dateStr) => { ... } });
 *   MonthSidebar.setActiveDate('2026-08-14');       // sync highlight w/ page nav
 *   MonthSidebar.getAppointmentsForDay('2026-08-14');
 *   MonthSidebar.getVisitDaysInMonthOf('2026-08-14');
 */
const MonthSidebar = (() => {
    const PL_MONTHS = ['styczeń', 'luty', 'marzec', 'kwiecień', 'maj', 'czerwiec',
        'lipiec', 'sierpień', 'wrzesień', 'październik', 'listopad', 'grudzień'];
    const WD = ['Po', 'Wt', 'Śr', 'Cz', 'Pt', 'So', 'Nd'];

    let opts = null;
    let baseYear, baseMonth;              // real "today" anchor — card #1
    let visitDays = new Set();            // 'YYYY-MM-DD' with ≥1 non-cancelled/no_show appt
    let appointmentsByDay = {};           // 'YYYY-MM-DD' -> all appointments that day (any status)
    let activeDate = null;

    function pad2(n) { return String(n).padStart(2, '0'); }
    function fmt(y, m, d) { return `${y}-${pad2(m + 1)}-${pad2(d)}`; }
    function todayStr() {
        const n = new Date();
        return fmt(n.getFullYear(), n.getMonth(), n.getDate());
    }
    function addMonths(y, m, offset) {
        const total = m + offset;
        return { year: y + Math.floor(total / 12), month: ((total % 12) + 12) % 12 };
    }
    function daysInMonth(y, m) { return new Date(y, m + 1, 0).getDate(); }

    async function init(userOpts) {
        opts = Object.assign({ onDaySelect: () => {}, storageKey: 'monthSidebarCollapsed', initialActiveDate: null }, userOpts);
        const now = new Date();
        baseYear = now.getFullYear();
        baseMonth = now.getMonth();
        activeDate = opts.initialActiveDate;

        setupToggle();
        renderShell();
        await loadData();
        renderDays();
    }

    function setupToggle() {
        const sidebar = document.getElementById('monthSidebar');
        const btn = document.getElementById('monthSidebarToggle');
        if (!sidebar || !btn) return;
        const collapsed = localStorage.getItem(opts.storageKey) === '1';
        sidebar.classList.toggle('collapsed', collapsed);
        btn.setAttribute('aria-expanded', String(!collapsed));
        btn.addEventListener('click', () => {
            const isCollapsed = sidebar.classList.toggle('collapsed');
            btn.setAttribute('aria-expanded', String(!isCollapsed));
            btn.setAttribute('aria-label', isCollapsed ? 'Rozwiń podgląd miesięcy' : 'Zwiń podgląd miesięcy');
            localStorage.setItem(opts.storageKey, isCollapsed ? '1' : '0');
        });
    }

    // Header + weekday row don't depend on appointment data — paint them
    // immediately so the sidebar isn't blank while the fetch is in flight.
    function renderShell() {
        document.querySelectorAll('.mini-month-card').forEach(card => {
            const offset = parseInt(card.dataset.monthOffset, 10);
            const { year, month } = addMonths(baseYear, baseMonth, offset);
            card.querySelector('.mini-month-head').textContent = `${PL_MONTHS[month]} ${year}`;
            const wdRow = card.querySelector('.mini-month-weekdays');
            wdRow.innerHTML = WD.map((w, i) => `<div class="mini-wd${i >= 5 ? ' weekend' : ''}">${w}</div>`).join('');
        });
    }

    async function loadData() {
        const last = addMonths(baseYear, baseMonth, 2);
        const params = new URLSearchParams({
            start_date: fmt(baseYear, baseMonth, 1),
            end_date: fmt(last.year, last.month, daysInMonth(last.year, last.month))
        });
        try {
            const resp = await fetch(`/api/appointments?${params}`);
            const data = await resp.json();
            appointmentsByDay = {};
            visitDays = new Set();
            (data.appointments || []).forEach(a => {
                (appointmentsByDay[a.appointment_date] = appointmentsByDay[a.appointment_date] || []).push(a);
                // Cancelled/no-show days read as "empty" for navigation purposes —
                // matches the day-view board's own precedent of filtering them out.
                if (a.status !== 'cancelled' && a.status !== 'no_show') visitDays.add(a.appointment_date);
            });
            Object.values(appointmentsByDay).forEach(list => list.sort((a, b) => (a.start_time || '').localeCompare(b.start_time || '')));
        } catch (e) {
            console.error('MonthSidebar: nie udało się załadować wizyt', e);
        }
    }

    function renderDays() {
        const today = todayStr();
        document.querySelectorAll('.mini-month-card').forEach(card => {
            const offset = parseInt(card.dataset.monthOffset, 10);
            const { year, month } = addMonths(baseYear, baseMonth, offset);
            const grid = card.querySelector('.mini-month-days');
            grid.innerHTML = '';

            const leadingPad = (new Date(year, month, 1).getDay() + 6) % 7; // Monday-first
            for (let i = 0; i < leadingPad; i++) {
                const filler = document.createElement('button');
                filler.type = 'button';
                filler.className = 'mini-day';
                filler.disabled = true;
                filler.innerHTML = '<span class="mini-day-num"></span>';
                grid.appendChild(filler);
            }

            const total = daysInMonth(year, month);
            for (let d = 1; d <= total; d++) {
                const ds = fmt(year, month, d);
                const hasVisits = visitDays.has(ds);
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'mini-day'
                    + (hasVisits ? ' has-visits' : ' no-visits')
                    + (ds === today ? ' today' : '')
                    + (ds === activeDate ? ' active' : '');
                btn.dataset.date = ds;
                btn.setAttribute('aria-label', `${d} ${PL_MONTHS[month]}${hasVisits ? ' — wizyty zaplanowane' : ' — brak wizyt'}`);
                btn.innerHTML = `<span class="mini-day-num">${d}</span>${hasVisits ? '<span class="mini-day-dot" aria-hidden="true"></span>' : ''}`;
                btn.addEventListener('click', () => opts.onDaySelect(ds));
                grid.appendChild(btn);
            }
        });
    }

    // Surgical highlight update — used constantly (every prev/next/today click
    // on the host page), so it must not re-fetch or rebuild the grids.
    function setActiveDate(ds) {
        activeDate = ds;
        document.querySelectorAll('.mini-day[data-date]').forEach(el => {
            el.classList.toggle('active', el.dataset.date === ds);
        });
    }

    // Re-fetches the 3-month span and repaints the grids — call after any
    // mutation (status change, delete, restore) that could change which days
    // count as "has visits" or what a day's own appointment list contains.
    async function refresh() {
        await loadData();
        renderDays();
    }

    function hasVisits(ds) { return visitDays.has(ds); }

    function getAppointmentsForDay(ds) { return appointmentsByDay[ds] || []; }

    // Ascending list of 'YYYY-MM-DD' visit-days within dateStr's own calendar
    // month. Backs the list-view's "skip empty days" / "last day of month
    // with visits" boundary — always a subset of the 3 fetched months, since
    // every clickable day originates from this same sidebar.
    function getVisitDaysInMonthOf(dateStr) {
        const [y, m] = dateStr.split('-').map(Number);
        const total = daysInMonth(y, m - 1);
        const days = [];
        for (let d = 1; d <= total; d++) {
            const ds = fmt(y, m - 1, d);
            if (visitDays.has(ds)) days.push(ds);
        }
        return days;
    }

    return { init, setActiveDate, hasVisits, getAppointmentsForDay, getVisitDaysInMonthOf, refresh };
})();
