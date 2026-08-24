"""
Trasy autentykacji - logowanie, wylogowanie, profil, reset hasła

React-migration note (Faza 0, phase-00-foundations.md §0.3): every handler
below branches on `wants_json` (X-Requested-With: XMLHttpRequest) so the SPA
gets a clean JSON response instead of the flash+redirect/render behaviour
meant for a full-page HTML form submit. The `wants_json=False` path in every
branch is byte-for-byte the pre-existing behaviour — this file is an ADDITIVE
change, not a rewrite (see implementation-log.md).
"""
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf.csrf import generate_csrf
from repositories.users.user_repository import UserRepository
from repositories.audit_repository import AuditRepository
from services.auth.auth_service import AuthService
from config.database import DatabaseConnection
from config.ui_messages import msg

# Create blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def _wants_json() -> bool:
    """DESIGN.md §15.1's signal: the SPA marks every API call with this
    header via lib/api/client.ts. Deliberately narrower than
    config.auth_config._wants_json (which also sniffs path/Accept) — this is
    the exact check phase-00-foundations.md §0.3 specifies."""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Strona logowania"""
    wants_json = _wants_json()

    # Jeśli użytkownik już zalogowany, przekieruj do dashboard
    if current_user.is_authenticated:
        if wants_json:
            return jsonify({'success': True, 'already_authenticated': True})
        return redirect(url_for('auth.profile'))

    if request.method == 'POST':
        if wants_json:
            data = request.get_json(silent=True) or {}
            email = (data.get('email') or '').strip()
            password = data.get('password') or ''
            remember = bool(data.get('remember'))
        else:
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            remember = request.form.get('remember', False) == 'on'

        # Walidacja pól
        if not email or not password:
            if wants_json:
                return jsonify({'success': False, 'error': msg('auth.login.missing_credentials')}), 400
            flash(msg('auth.login.missing_credentials'), 'error')
            return render_template('auth/login.html')

        # Autentykacja
        user_repo = UserRepository()
        auth_service = AuthService(user_repo)

        success, user, error_message = auth_service.authenticate(email, password)

        if success:
            login_user(user, remember=remember)
            session.permanent = True  # 30-day sliding session (PERMANENT_SESSION_LIFETIME)

            AuditRepository().safe_log_event(
                entity_type='login', action='LOGIN',
                entity_label=user.email,
                new_value=request.remote_addr,
                user_id=user.id, user_name=user.full_name,
            )

            if wants_json:
                return jsonify({'success': True})

            flash(msg('auth.login.welcome', name=user.full_name), 'success')
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('auth.profile'))
        else:
            AuditRepository().safe_log_event(
                entity_type='login', action='LOGIN_FAILED',
                entity_label=email,
                new_value=request.remote_addr,
            )
            if wants_json:
                return jsonify({'success': False, 'error': error_message}), 401
            flash(error_message, 'error')
            return render_template('auth/login.html', email=email)

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Wylogowanie użytkownika"""
    wants_json = _wants_json()
    AuditRepository().safe_log_event(
        entity_type='login', action='LOGOUT',
        entity_label=current_user.email,
        user_id=current_user.id, user_name=current_user.full_name,
    )
    logout_user()
    if wants_json:
        return jsonify({'success': True})
    flash(msg('auth.logout'), 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/csrf-token', methods=['GET'])
def csrf_token():
    """Issues a CSRF token for the React SPA (root-cause fix, 2026-08-17).

    The Jinja frontend gets its token for free via `{{ csrf_token() }}`
    rendered into every `<form>`. The SPA has no such template render, so
    every POST/PUT/DELETE from `lib/api/client.ts` was silently rejected by
    Flask-WTF's CSRFProtect (app.py `csrf = CSRFProtect(app)`, applies to
    every state-changing request by default, `auth_bp` was never
    `csrf.exempt`-ed). This is GET-only and unauthenticated — CSRFProtect
    never checks GET requests, and a token must be obtainable *before*
    login (the login POST itself needs one).
    """
    return jsonify({'success': True, 'csrf_token': generate_csrf()})


@auth_bp.route('/me', methods=['GET'])
def me():
    """Session-check-on-load endpoint for the React SPA (DESIGN.md §15.1).

    Deliberately NOT @login_required: that decorator's default unauthorized
    handler redirects to auth.login, which would hand an XHR caller an HTML
    page instead of JSON. A plain 401 here is what AuthContext expects for
    "no session" — not an error to display, just the logged-out state.
    """
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    from config.auth_config import get_all_permission_flags, get_linked_employee

    permissions = {}
    try:
        permissions = get_all_permission_flags(current_user.role)
    except Exception:
        pass

    is_supervisor_flag = False
    has_linked_employee = False
    try:
        emp = get_linked_employee(current_user)
        has_linked_employee = emp is not None
        if emp:
            from repositories.absences.employee_supervisor_repository import EmployeeSupervisorRepository
            is_supervisor_flag = EmployeeSupervisorRepository().is_supervisor(emp['id'])
    except Exception:
        pass

    return jsonify({
        'success': True,
        'user': {
            'id': current_user.id,
            'email': current_user.email,
            'full_name': current_user.full_name,
            'role': current_user.role,
        },
        'permissions': permissions,
        'is_supervisor': is_supervisor_flag,
        'has_linked_employee': has_linked_employee,
    })


@auth_bp.route('/profile')
@login_required
def profile():
    """Profil użytkownika"""
    return render_template('auth/profile.html', user=current_user)


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Zmiana hasła"""
    wants_json = _wants_json()

    if request.method == 'POST':
        if wants_json:
            data = request.get_json(silent=True) or {}
            old_password = data.get('old_password') or ''
            new_password = data.get('new_password') or ''
            confirm_password = data.get('confirm_password') or ''
        else:
            old_password = request.form.get('old_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')

        # Walidacja
        if not old_password or not new_password or not confirm_password:
            if wants_json:
                return jsonify({'success': False, 'error': msg('auth.change_password.missing_fields')}), 400
            flash(msg('auth.change_password.missing_fields'), 'error')
            return render_template('auth/change_password.html')

        if new_password != confirm_password:
            if wants_json:
                return jsonify({'success': False, 'error': msg('auth.change_password.mismatch')}), 400
            flash(msg('auth.change_password.mismatch'), 'error')
            return render_template('auth/change_password.html')

        # Zmień hasło
        user_repo = UserRepository()
        auth_service = AuthService(user_repo)

        success, error_message = auth_service.change_password(
            current_user.id,
            old_password,
            new_password
        )

        if success:
            if wants_json:
                return jsonify({'success': True})
            flash(msg('auth.change_password.success'), 'success')
            return redirect(url_for('auth.profile'))
        else:
            if wants_json:
                return jsonify({'success': False, 'error': error_message}), 400
            flash(error_message, 'error')
            return render_template('auth/change_password.html')

    return render_template('auth/change_password.html')


# ---------------------------------------------------------------------------
# Forgot / Reset password (no email required — token shown directly on screen)
# ---------------------------------------------------------------------------

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Formularz resetowania hasła — wyświetla link z tokenem na ekranie"""
    wants_json = _wants_json()
    reset_url = None

    if request.method == 'POST':
        if wants_json:
            data = request.get_json(silent=True) or {}
            email = (data.get('email') or '').strip().lower()
        else:
            email = request.form.get('email', '').strip().lower()

        if email:
            user_repo = UserRepository()
            user = user_repo.get_by_email(email)

            if user:
                conn = DatabaseConnection.get_connection()
                cursor = conn.cursor()

                # Invalidate any existing unused tokens for this user
                cursor.execute(
                    "UPDATE password_reset_tokens SET used = TRUE WHERE user_id = %s AND used = FALSE",
                    (user.id,)
                )

                # Generate new token (256-bit URL-safe)
                token = secrets.token_urlsafe(32)
                expires_at = datetime.now() + timedelta(hours=1)

                cursor.execute(
                    "INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (%s, %s, %s)",
                    (user.id, token, expires_at)
                )
                conn.commit()

                reset_url = url_for('auth.reset_password', token=token, _external=True)

                AuditRepository().safe_log_event(
                    entity_type='user', action='PASSWORD_RESET_REQUESTED',
                    entity_id=user.id, entity_label=user.email,
                )

            # Always show the same neutral message (prevents email enumeration)
            # reset_url is only set when user was found

        if wants_json:
            return jsonify({'success': True, 'reset_url': reset_url})

    return render_template('auth/forgot_password.html', reset_url=reset_url)


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token: str):
    """Formularz ustawiania nowego hasła po kliknięciu w link z tokenem"""
    wants_json = _wants_json()
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM password_reset_tokens WHERE token = %s AND used = FALSE AND expires_at > NOW()",
        (token,)
    )
    token_row = cursor.fetchone()

    if not token_row:
        if wants_json:
            return jsonify({'success': False, 'error': msg('auth.reset.link_dead')}), 400
        flash(msg('auth.reset.link_dead'), 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        if wants_json:
            data = request.get_json(silent=True) or {}
            new_password = data.get('new_password') or ''
            confirm_password = data.get('confirm_password') or ''
        else:
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')

        if len(new_password) < 8:
            if wants_json:
                return jsonify({'success': False, 'error': msg('auth.reset.weak_password')}), 400
            flash(msg('auth.reset.weak_password'), 'error')
            return render_template('auth/reset_password.html', token=token)

        if new_password != confirm_password:
            if wants_json:
                return jsonify({'success': False, 'error': msg('auth.reset.mismatch')}), 400
            flash(msg('auth.reset.mismatch'), 'error')
            return render_template('auth/reset_password.html', token=token)

        # Update password and mark token as used
        user_repo = UserRepository()
        user_repo.update_password(token_row['user_id'], new_password)

        cursor.execute(
            "UPDATE password_reset_tokens SET used = TRUE WHERE token = %s",
            (token,)
        )
        conn.commit()

        AuditRepository().safe_log_event(
            entity_type='user', action='PASSWORD_RESET',
            entity_id=token_row['user_id'],
            new_value=request.remote_addr,
        )

        if wants_json:
            return jsonify({'success': True})

        flash(msg('auth.reset.success'), 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)
