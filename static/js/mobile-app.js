/**
 * Employee visit-status app: picker -> PIN -> today's list -> detail,
 * against the /api/mobile/* backend. Meant to be used via "Add to Home
 * Screen" for a full-screen, app-like feel on any phone.
 * Vanilla JS/DOM to match this codebase's existing static/js/* convention.
 */
(function () {
  'use strict';

  var SESSION_KEY = 'myway_mobile_session';
  var root = document.getElementById('app');

  // ---------------------------------------------------------------------
  // DOM helper -- builds elements via textContent/createTextNode only, so
  // user-supplied strings (client/employee names) can never inject markup.
  // ---------------------------------------------------------------------
  function h(tag, props, children) {
    var node = document.createElement(tag);
    if (props) {
      Object.keys(props).forEach(function (k) {
        var v = props[k];
        if (v == null) return;
        if (k === 'class') node.className = v;
        else if (k === 'style' && typeof v === 'object') Object.assign(node.style, v);
        else if (k.indexOf('on') === 0 && typeof v === 'function') node.addEventListener(k.slice(2).toLowerCase(), v);
        else if (k === 'disabled') node.disabled = !!v;
        else node.setAttribute(k, v);
      });
    }
    (children || []).forEach(function (c) {
      if (c == null) return;
      node.appendChild(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
    });
    return node;
  }

  function card(children, opts) {
    return h('div', { class: 'card' + ((opts && opts.padded === false) ? '' : ' card-padded') }, children);
  }

  // ---------------------------------------------------------------------
  // Session persistence
  // ---------------------------------------------------------------------
  function saveSession(session) {
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  }
  function loadSession() {
    try {
      var raw = localStorage.getItem(SESSION_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }
  function clearSession() {
    localStorage.removeItem(SESSION_KEY);
  }

  // ---------------------------------------------------------------------
  // API
  // ---------------------------------------------------------------------
  function apiFetch(path, opts) {
    return fetch(path, opts)
      .then(function (res) {
        return res.json().catch(function () { return { success: false, error: 'bad_response' }; })
          .then(function (body) {
            if (res.status === 401 && body.error === undefined) body.error = 'unauthorized';
            return body;
          });
      })
      .catch(function () {
        return { success: false, error: 'network_error' };
      });
  }

  // Anchors server-sent durations to this device's own clock, once, at
  // receipt time. Never derive countdown math from unlock_at (a naive
  // datetime string with no timezone marker) -- the server runs in UTC
  // while appointment times are Polish local, so `new Date(unlock_at)`
  // parses it as local time on-device and lands ~2h off (CEST), making
  // every too_early row look already-expired and looping the
  // refetch-on-expiry logic forever (network-round-trip-speed blinking).
  //
  // unlockAtLocalMs gates the too_early -> start_visit transition (20 min
  // before start). startAtLocalMs is what the today-list badge counts down
  // to instead -- the actual appointment time, valid in both states.
  function anchorTimers(appt) {
    if (!appt) return appt;
    if (appt.state === 'too_early' && typeof appt.seconds_remaining === 'number') {
      appt.unlockAtLocalMs = Date.now() + appt.seconds_remaining * 1000;
    }
    if (
      (appt.state === 'too_early' || appt.state === 'start_visit') &&
      typeof appt.seconds_until_start === 'number'
    ) {
      appt.startAtLocalMs = Date.now() + appt.seconds_until_start * 1000;
    }
    return appt;
  }

  function fetchEmployees() {
    return apiFetch('/api/mobile/employees');
  }
  function submitPin(employeeId, pin) {
    return apiFetch('/api/mobile/employees/' + employeeId + '/pin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin: pin }),
    });
  }
  function fetchToday(token) {
    return apiFetch('/api/mobile/today', { headers: { Authorization: 'Bearer ' + token } });
  }
  function fetchAppointmentState(token, appointmentId) {
    return apiFetch('/api/mobile/appointments/' + appointmentId, { headers: { Authorization: 'Bearer ' + token } });
  }
  function submitAction(token, appointmentId, action) {
    return apiFetch('/api/mobile/appointments/' + appointmentId + '/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
      body: JSON.stringify({ action: action }),
    });
  }

  // ---------------------------------------------------------------------
  // Formatting -- mirrors mobile/src/utils/countdown.ts and the
  // list/detail screens' date helpers (local-time only, never
  // new Date(isoDateString) directly).
  // ---------------------------------------------------------------------
  function pad(n) { return String(n).padStart(2, '0'); }

  function formatCountdown(ms) {
    var total = Math.max(0, Math.floor(ms / 1000));
    var hh = Math.floor(total / 3600);
    var mm = Math.floor((total % 3600) / 60);
    var ss = total % 60;
    return (hh > 0 ? hh + ':' + pad(mm) : String(mm)) + ':' + pad(ss);
  }

  function formatIsoDateLocal(isoDate) {
    if (!isoDate) return '';
    var parts = isoDate.split('-').map(Number);
    var d = new Date(parts[0], parts[1] - 1, parts[2]);
    return pad(d.getDate()) + '.' + pad(d.getMonth() + 1) + '.' + d.getFullYear();
  }

  function formatToday() {
    var d = new Date();
    return pad(d.getDate()) + '.' + pad(d.getMonth() + 1) + '.' + d.getFullYear();
  }

  var PILL_COLORS = {
    already_done: { bg: '#f0fdf4', fg: '#2d6a4f', dot: false, label: 'Zakończona' },
    end_visit: { bg: '#fffbeb', fg: '#d97706', dot: true, label: 'W trakcie' },
    start_visit: { bg: '#1a1a1a', fg: '#ffffff', dot: false, label: 'Gotowość' },
    too_early: { bg: '#eff6ff', fg: '#2563eb', dot: false, label: null },
    wrong_status: { bg: '#fef2f2', fg: '#dc2626', dot: false, label: 'Sprawdź' },
  };

  function pillLabelFor(appt, now) {
    var meta = PILL_COLORS[appt.state] || PILL_COLORS.wrong_status;
    // The badge always counts down to the actual appointment start (in both
    // too_early and start_visit) -- only its color follows the 20-min gate,
    // via which of those two states it's currently in.
    if (
      (appt.state === 'too_early' || appt.state === 'start_visit') &&
      appt.startAtLocalMs &&
      appt.startAtLocalMs - now > 0
    ) {
      return formatCountdown(appt.startAtLocalMs - now);
    }
    return meta.label || '';
  }

  function describeError(code) {
    switch (code) {
      case 'wrong_pin': return 'Nieprawidłowy PIN.';
      case 'invalid_pin_format': return 'PIN musi mieć od 4 do 6 cyfr.';
      case 'not_found': return 'Nie znaleziono pracownika — odśwież listę.';
      case 'network_error': return 'Brak połączenia z serwerem.';
      case 'unauthorized': return 'Sesja wygasła — zaloguj się ponownie.';
      default: return 'Coś poszło nie tak. Spróbuj ponownie.';
    }
  }

  function successMessageFor(newStatus) {
    switch (newStatus) {
      case 'in_progress': return 'Wizyta oznaczona jako W trakcie.';
      case 'completed': return 'Wizyta oznaczona jako Zakończona.';
      case 'no_show': return 'Wizyta oznaczona jako: klient się nie stawił.';
      default: return 'Status zaktualizowany.';
    }
  }

  // ---------------------------------------------------------------------
  // App state + ticker
  // ---------------------------------------------------------------------
  var state = { screen: 'bootstrapping' };
  var tickInterval = null;

  function setState(patch) {
    Object.assign(state, patch);
    render();
  }

  function ensureTicking() {
    if (tickInterval) return;
    tickInterval = setInterval(function () {
      if (state.screen === 'today' || state.screen === 'detail') render();
    }, 1000);
  }

  function goToPicker() {
    clearSession();
    setState({ screen: 'picker', employeesLoading: true, employeesError: null, employees: [] });
    fetchEmployees().then(function (result) {
      if (!result.success) {
        setState({ employeesLoading: false, employeesError: describeError(result.error) });
        return;
      }
      setState({ employeesLoading: false, employees: result.employees });
    });
  }

  function handleUnauthorized() {
    goToPicker();
  }

  function openPin(employee) {
    setState({ screen: 'pin', pinEmployee: employee, pinError: null, pinSubmitting: false });
  }

  function loadToday() {
    var session = state.session;
    setState({ screen: 'today', todayLoading: true, todayError: null });
    fetchToday(session.sessionToken).then(function (result) {
      if (!result.success) {
        if (result.error === 'unauthorized') { handleUnauthorized(); return; }
        setState({ todayLoading: false, todayError: describeError(result.error) });
        return;
      }
      setState({
        todayLoading: false,
        appointments: (result.appointments || []).map(anchorTimers),
        todayLabel: formatIsoDateLocal(result.today),
        todayExpiredHandled: false,
      });
    });
  }

  function openDetail(appt) {
    setState({
      screen: 'detail', detailAppt: appt, detailError: null,
      detailSubmitting: null, detailSuccessStatus: null, detailExpiredHandled: false,
    });
  }

  function backToToday() {
    loadToday();
  }

  function runDetailAction(action) {
    var session = state.session;
    var appt = state.detailAppt;
    setState({ detailSubmitting: action, detailError: null });
    submitAction(session.sessionToken, appt.appointment_id, action).then(function (result) {
      if (!result.success) {
        if (result.error === 'unauthorized') { handleUnauthorized(); return; }
        if (result.state) {
          setState({
            detailSubmitting: null,
            detailAppt: Object.assign({}, appt, anchorTimers(result)),
            detailError: result.error || null,
          });
          return;
        }
        setState({ detailSubmitting: null, detailError: 'Coś poszło nie tak. Spróbuj ponownie.' });
        return;
      }
      setState({ detailSubmitting: null, detailSuccessStatus: result.new_status || '' });
      setTimeout(backToToday, 1500);
    });
  }

  function handleNoShow() {
    if (window.confirm('Oznaczyć wizytę jako: klient się nie stawił?')) {
      runDetailAction('no_show');
    }
  }

  // ---------------------------------------------------------------------
  // Screens
  // ---------------------------------------------------------------------
  function renderSplash() {
    return h('div', { class: 'centered' }, ['Ładowanie…']);
  }

  function renderPicker() {
    var logo = h('img', { class: 'logo-lg', src: '/static/Logo.png', alt: 'MyWay Beauty Salon' });
    var body = [logo, h('h1', null, ['Kto się loguje?']), h('p', { class: 'subheading' }, ['Wybierz swoje imię z listy.'])];

    if (state.employeesLoading) {
      body.push(h('div', { class: 'centered' }, ['Ładowanie…']));
    } else if (state.employeesError) {
      body.push(h('p', { class: 'error-msg', style: { marginTop: '1rem' } }, [state.employeesError]));
      body.push(h('a', { class: 'link', onClick: goToPicker }, ['Spróbuj ponownie']));
    } else if (state.employees.length === 0) {
      body.push(h('p', { class: 'subheading', style: { padding: '1.5rem 0' } }, ['Brak aktywnych pracowników.']));
    } else {
      var rows = h('div', { class: 'picker-rows' });
      state.employees.forEach(function (emp) {
        rows.appendChild(h('div', { class: 'picker-row', onClick: function () { openPin(emp); } }, [emp.name]));
      });
      body.push(rows);
    }
    return card(body);
  }

  function renderPin() {
    var employee = state.pinEmployee;
    var isNewPin = !employee.has_pin;
    var logo = h('img', { class: 'logo', src: '/static/Logo.png', alt: 'MyWay Beauty Salon' });
    var back = h('a', { class: 'link', onClick: goToPicker }, ['← Wybierz inną osobę']);

    var pinInput = h('input', { type: 'password', inputmode: 'numeric', maxlength: '6', placeholder: 'PIN', id: 'pin-input' });
    var confirmInput = isNewPin
      ? h('input', { type: 'password', inputmode: 'numeric', maxlength: '6', placeholder: 'Powtórz PIN', id: 'pin-confirm-input' })
      : null;

    function currentValues() {
      var pin = pinInput.value.replace(/\D/g, '').slice(0, 6);
      var confirmPin = confirmInput ? confirmInput.value.replace(/\D/g, '').slice(0, 6) : pin;
      return { pin: pin, confirmPin: confirmPin };
    }

    function submit() {
      var v = currentValues();
      if (v.pin.length < 4) return;
      if (isNewPin && (v.confirmPin.length < 4 || v.pin !== v.confirmPin)) return;
      setState({ pinSubmitting: true, pinError: null });
      submitPin(employee.id, v.pin).then(function (result) {
        if (!result.success || !result.session_token) {
          setState({ pinSubmitting: false, pinError: describeError(result.error) });
          return;
        }
        var session = { employeeId: employee.id, employeeName: employee.name, sessionToken: result.session_token };
        saveSession(session);
        setState({ session: session });
        loadToday();
      });
    }

    pinInput.addEventListener('keydown', function (e) { if (e.key === 'Enter' && !isNewPin) submit(); });
    if (confirmInput) confirmInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') submit(); });

    var body = [
      h('div', { class: 'header-row' }, [logo, back]),
      h('h1', null, [isNewPin ? 'Ustaw PIN' : 'Wprowadź PIN']),
      h('p', { class: 'subheading' }, [
        isNewPin
          ? 'Cześć, ' + employee.name + '. Ustaw swój PIN (4–6 cyfr) — będziesz go używać przy każdym logowaniu.'
          : 'Cześć, ' + employee.name + '. Wprowadź swój PIN.',
      ]),
    ];
    if (state.pinError) body.push(h('p', { class: 'error-msg', style: { marginTop: '1rem' } }, [state.pinError]));
    body.push(pinInput);
    if (confirmInput) body.push(confirmInput);
    body.push(
      h('button', {
        class: 'btn-primary',
        disabled: state.pinSubmitting,
        onClick: submit,
      }, [state.pinSubmitting ? '…' : (isNewPin ? 'Ustaw PIN i kontynuuj' : 'Zaloguj')])
    );
    var el = card(body);
    setTimeout(function () { pinInput.focus(); }, 0);
    return el;
  }

  function renderToday() {
    var now = Date.now();
    var logo = h('img', { class: 'logo-lg', src: '/static/Logo.png', alt: 'MyWay Beauty Salon' });
    var header = h('div', { class: 'list-header' }, [
      logo,
      h('p', { class: 'subheading' }, ['Dzisiejsze wizyty — ' + state.todayLabel]),
    ]);

    var children = [header];

    if (state.todayLoading) {
      children.push(h('div', { class: 'centered' }, ['Ładowanie…']));
    } else if (state.todayError) {
      children.push(h('div', { class: 'centered' }, [
        h('p', { class: 'error-msg' }, [state.todayError]),
        h('a', { class: 'link', onClick: loadToday }, ['Spróbuj ponownie']),
      ]));
    } else if (state.appointments.length === 0) {
      children.push(h('p', { class: 'empty-msg' }, ['Brak wizyt na dziś.']));
    } else {
      var anyExpired = false;
      state.appointments.forEach(function (appt) {
        var meta = PILL_COLORS[appt.state] || PILL_COLORS.wrong_status;
        var pill = h('div', { class: 'pill', style: { background: meta.bg, color: meta.fg } });
        if (meta.dot) pill.appendChild(h('span', { class: 'pill-dot' }));
        pill.appendChild(h('span', null, [pillLabelFor(appt, now)]));

        if (appt.state === 'too_early' && appt.unlockAtLocalMs && appt.unlockAtLocalMs - now <= 0) {
          anyExpired = true;
        }

        var row = h('div', { class: 'list-row', onClick: function () { openDetail(appt); } }, [
          h('div', { class: 'list-time' }, [appt.start_time]),
          h('div', { class: 'list-main' }, [
            h('div', { class: 'list-client' }, [appt.client_name]),
            h('div', { class: 'list-service' }, [appt.service_name || '']),
          ]),
          pill,
        ]);
        children.push(row);
      });
      if (anyExpired && !state.todayExpiredHandled) {
        state.todayExpiredHandled = true;
        loadToday();
      }
    }

    children.push(h('div', { class: 'switch-row' }, [
      h('a', { class: 'link', onClick: goToPicker }, ['Zmień pracownika (' + state.session.employeeName + ')']),
    ]));

    return card(children, { padded: false });
  }

  function renderDetail() {
    var now = Date.now();
    var appt = state.detailAppt;
    var logo = h('img', { class: 'logo', src: '/static/Logo.png', alt: 'MyWay Beauty Salon' });
    var back = h('a', { class: 'link', onClick: backToToday }, ['← Dzisiejsze wizyty']);
    var body = [h('div', { class: 'header-row' }, [logo, back])];

    if (state.detailError) body.push(h('p', { class: 'error-msg' }, [state.detailError]));

    if (state.detailSuccessStatus !== null) {
      body.push(h('div', { class: 'status-view' }, [
        h('div', { class: 'status-icon' }, ['✅']),
        h('h1', null, ['Status zaktualizowany']),
        h('p', { class: 'status-message' }, [successMessageFor(state.detailSuccessStatus)]),
      ]));
      body.push(h('button', { class: 'btn-secondary', style: { marginTop: '1.5rem' }, onClick: backToToday }, ['← Wróć do dzisiejszych wizyt']));
    } else if (appt.state === 'too_early') {
      if (appt.unlockAtLocalMs && appt.unlockAtLocalMs - now <= 0 && !state.detailExpiredHandled) {
        state.detailExpiredHandled = true;
        fetchAppointmentState(state.session.sessionToken, appt.appointment_id).then(function (result) {
          if (!result.success) { if (result.error === 'unauthorized') handleUnauthorized(); return; }
          setState({ detailAppt: Object.assign({}, appt, anchorTimers(result)) });
        });
      }
      var countdownText = appt.unlockAtLocalMs ? formatCountdown(appt.unlockAtLocalMs - now) : '—';
      body.push(h('div', { class: 'status-view' }, [
        h('div', { class: 'status-icon' }, ['⏳']),
        h('h1', null, ['Za wcześnie']),
        h('p', { class: 'status-message' }, [
          'Formularz odblokuje się automatycznie za ',
          h('strong', null, [countdownText]),
          ' (20 minut przed wizytą).',
        ]),
      ]));
    } else if (appt.state === 'already_done') {
      body.push(h('div', { class: 'status-view' }, [
        h('div', { class: 'status-icon' }, ['✅']),
        h('h1', null, ['Wizyta już zakończona']),
        h('p', { class: 'status-message' }, ['Ta wizyta ma już finalny status. Brak dostępnych akcji.']),
      ]));
    } else if (appt.state === 'wrong_status') {
      body.push(h('div', { class: 'status-view' }, [
        h('div', { class: 'status-icon' }, ['⚠️']),
        h('h1', null, ['Nieprawidłowy status']),
        h('p', { class: 'status-message' }, ['Wizyta ma status, który nie pozwala na zmianę przez ten formularz.']),
      ]));
    } else if (appt.state === 'start_visit' || appt.state === 'end_visit') {
      var isStart = appt.state === 'start_visit';
      body.push(h('h1', null, [isStart ? 'Rozpocznij wizytę' : 'Zakończ wizytę']));
      body.push(h('p', { class: 'subheading' }, [isStart ? 'Potwierdź rozpoczęcie wizyty.' : 'Potwierdź zakończenie wizyty.']));
      body.push(h('div', { class: 'details-block' }, [
        h('div', { class: 'detail-row' }, [h('span', { class: 'detail-label' }, ['Klient']), h('span', { class: 'detail-value' }, [appt.client_name])]),
        h('div', { class: 'detail-row' }, [h('span', { class: 'detail-label' }, ['Data']), h('span', { class: 'detail-value' }, [formatToday()])]),
        h('div', { class: 'detail-row' }, [h('span', { class: 'detail-label' }, ['Godzina']), h('span', { class: 'detail-value' }, [appt.start_time])]),
      ]));
      var busy = state.detailSubmitting !== null;
      body.push(h('button', {
        class: 'btn-primary', disabled: busy,
        onClick: function () { runDetailAction(isStart ? 'start' : 'end'); },
      }, [busy ? '…' : (isStart ? 'Wizyta rozpoczęta' : 'Wizyta zakończona')]));
      if (isStart && appt.can_no_show) {
        body.push(h('button', {
          class: 'btn-secondary muted', disabled: busy, onClick: handleNoShow,
        }, ['Klient się nie stawił']));
      }
    }

    return card(body);
  }

  // ---------------------------------------------------------------------
  // Render dispatch
  // ---------------------------------------------------------------------
  function render() {
    root.innerHTML = '';
    var view;
    switch (state.screen) {
      case 'picker': view = renderPicker(); break;
      case 'pin': view = renderPin(); break;
      case 'today': view = renderToday(); ensureTicking(); break;
      case 'detail': view = renderDetail(); ensureTicking(); break;
      default: view = renderSplash();
    }
    root.appendChild(view);
  }

  // ---------------------------------------------------------------------
  // Bootstrap
  // ---------------------------------------------------------------------
  var savedSession = loadSession();
  if (savedSession) {
    state.session = savedSession;
    loadToday();
  } else {
    goToPicker();
  }
})();
