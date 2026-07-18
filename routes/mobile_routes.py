"""
Mobile employee app — PIN-based auth, no SMS link, no session cookie.

Security model: each active employee sets a short PIN the first time they
pick themselves in the app (bcrypt-hashed, never stored or returned in
plaintext). Every later pick verifies against that hash. On success the
server issues a short-lived signed token (itsdangerous, keyed off the app's
SECRET_KEY) carrying only the employee_id; the app sends it back as
`Authorization: Bearer <token>` on every subsequent call.

This is deliberately separate from the SMS-token flow in public_routes.py
(/visit/<token>), which stays untouched for whoever still reaches it that way.
"""
import re
from datetime import date

import bcrypt
from flask import Blueprint, current_app, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from repositories.appointments.appointment_repository import AppointmentRepository
from repositories.employees.employee_repository import EmployeeRepository
from routes.public_routes import _employee_visit_state, _process_visit_action

mobile_bp = Blueprint('mobile', __name__)

SESSION_MAX_AGE = 60 * 60 * 16  # 16h — a working day plus slack
_TOKEN_SALT = 'mobile-employee-session'
_PIN_RE = re.compile(r'^\d{4,6}$')


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt=_TOKEN_SALT)


def _issue_session_token(employee_id: int) -> str:
    return _serializer().dumps({'employee_id': employee_id})


def _authenticated_employee_id():
    """Validate the Bearer session token from this request; None if missing/invalid."""
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    try:
        data = _serializer().loads(auth[len('Bearer '):], max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    return data.get('employee_id')


@mobile_bp.route('/employees', methods=['GET'])
def list_employees():
    """Picker list — every active employee, including the superuser-linked one.

    Widok administratora intentionally does NOT apply here (see
    EmployeeRepository.list_for_mobile_picker) — this is an operational
    roster, not a staff-facing analytics/reporting surface.

    has_pin lets the app show "set a new PIN" (with confirmation) vs
    "enter your PIN" before the employee types anything.
    """
    rows = EmployeeRepository().list_for_mobile_picker()
    return jsonify({
        'success': True,
        'employees': [
            {'id': r['id'], 'name': f"{r['first_name']} {r['last_name']}", 'has_pin': bool(r['has_pin'])}
            for r in rows
        ],
    })


@mobile_bp.route('/employees/<int:employee_id>/pin', methods=['POST'])
def employee_pin(employee_id):
    """Set (first use) or verify (every use after) an employee's mobile PIN."""
    body = request.get_json(silent=True) or {}
    pin = str(body.get('pin', ''))
    if not _PIN_RE.match(pin):
        return jsonify({'success': False, 'error': 'invalid_pin_format'}), 400

    repo = EmployeeRepository()
    existing_hash = repo.get_mobile_pin_hash(employee_id)
    if existing_hash is None:
        # get_mobile_pin_hash returns None for "no PIN yet" AND for "doesn't
        # exist / inactive" alike — disambiguate against the same active set
        # the picker list uses, so an inactive/unknown id 404s instead of
        # silently minting a session nothing will ever use.
        visible_ids = {r['id'] for r in repo.list_for_mobile_picker()}
        if employee_id not in visible_ids:
            return jsonify({'success': False, 'error': 'not_found'}), 404

        pin_hash = bcrypt.hashpw(pin.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        repo.set_mobile_pin_hash(employee_id, pin_hash)
        return jsonify({
            'success': True, 'first_time': True,
            'session_token': _issue_session_token(employee_id),
        })

    if not bcrypt.checkpw(pin.encode('utf-8'), existing_hash.encode('utf-8')):
        return jsonify({'success': False, 'error': 'wrong_pin'}), 401

    return jsonify({
        'success': True, 'first_time': False,
        'session_token': _issue_session_token(employee_id),
    })


def _serialize_appointment_state(row: dict) -> dict:
    """Shared shape for a /today row and a single-appointment refetch."""
    state, ctx = _employee_visit_state(row)
    return {
        'appointment_id': row['id'],
        'start_time': str(row['start_time'])[:5],
        'status': row['status'],
        'state': state,
        **ctx,
    }


@mobile_bp.route('/today', methods=['GET'])
def today():
    employee_id = _authenticated_employee_id()
    if employee_id is None:
        return jsonify({'success': False, 'error': 'unauthorized'}), 401

    rows = [
        dict(r)
        for r in AppointmentRepository().get_today_for_employee(employee_id, bypass_admin_view_hiding=True)
    ]
    appointments = [
        {
            **_serialize_appointment_state(row),
            'client_name': row['client_name'],
            'service_name': row.get('service_name'),
        }
        for row in rows
    ]
    return jsonify({'success': True, 'appointments': appointments, 'today': date.today().isoformat()})


@mobile_bp.route('/appointments/<int:appointment_id>', methods=['GET'])
def get_appointment(appointment_id):
    """Refresh one appointment's computed state — used when the detail screen's
    live countdown reaches zero, without navigating back to the list."""
    employee_id = _authenticated_employee_id()
    if employee_id is None:
        return jsonify({'success': False, 'error': 'unauthorized'}), 401

    appt = AppointmentRepository().get_by_id(appointment_id)
    if not appt or appt['employee_id'] != employee_id:
        return jsonify({'success': False, 'error': 'not_found'}), 404

    return jsonify({'success': True, **_serialize_appointment_state(dict(appt))})


@mobile_bp.route('/appointments/<int:appointment_id>/action', methods=['POST'])
def appointment_action(appointment_id):
    employee_id = _authenticated_employee_id()
    if employee_id is None:
        return jsonify({'success': False, 'error': 'unauthorized'}), 401

    repo = AppointmentRepository()
    appt = repo.get_by_id(appointment_id)
    # Ownership check folded into the same 404 as "doesn't exist" — this
    # endpoint never reveals which appointment ids belong to someone else.
    if not appt or appt['employee_id'] != employee_id:
        return jsonify({'success': False, 'error': 'not_found'}), 404

    appt = dict(appt)
    body = request.get_json(silent=True) or {}
    action = body.get('action')  # 'start' | 'end' | 'no_show'
    result = _process_visit_action(repo, appt, token=f'mobile-emp-{employee_id}', action=action)

    if result['error']:
        return jsonify({'success': False, 'state': result['state'], 'error': result['error'], **result['ctx']})

    return jsonify({
        'success': True, 'state': 'success', 'new_status': result['new_status'],
        'appointment_id': appt['id'],
    })
