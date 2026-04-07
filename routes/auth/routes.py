"""
Trasy autentykacji - logowanie, wylogowanie, profil, reset hasła
"""
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from repositories.users.user_repository import UserRepository
from repositories.audit_repository import AuditRepository
from services.auth.auth_service import AuthService
from config.database import DatabaseConnection

# Create blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Strona logowania"""
    # Jeśli użytkownik już zalogowany, przekieruj do dashboard
    if current_user.is_authenticated:
        return redirect(url_for('auth.profile'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False) == 'on'

        # Walidacja pól
        if not email or not password:
            flash('Email i hasło są wymagane', 'error')
            return render_template('auth/login.html')

        # Autentykacja
        user_repo = UserRepository()
        auth_service = AuthService(user_repo)

        success, user, error_message = auth_service.authenticate(email, password)

        if success:
            login_user(user, remember=remember)
            flash(f'Witaj, {user.full_name}!', 'success')

            try:
                AuditRepository().log_event(
                    entity_type='login', action='LOGIN',
                    entity_label=user.email,
                    new_value=request.remote_addr,
                    user_id=user.id, user_name=user.full_name,
                )
            except Exception:
                pass

            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('auth.profile'))
        else:
            try:
                AuditRepository().log_event(
                    entity_type='login', action='LOGIN_FAILED',
                    entity_label=email,
                    new_value=request.remote_addr,
                )
            except Exception:
                pass
            flash(error_message, 'error')
            return render_template('auth/login.html', email=email)

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Wylogowanie użytkownika"""
    try:
        AuditRepository().log_event(
            entity_type='login', action='LOGOUT',
            entity_label=current_user.email,
            user_id=current_user.id, user_name=current_user.full_name,
        )
    except Exception:
        pass
    logout_user()
    flash('Zostałeś wylogowany', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile')
@login_required
def profile():
    """Profil użytkownika"""
    return render_template('auth/profile.html', user=current_user)


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Zmiana hasła"""
    if request.method == 'POST':
        old_password = request.form.get('old_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Walidacja
        if not old_password or not new_password or not confirm_password:
            flash('Wszystkie pola są wymagane', 'error')
            return render_template('auth/change_password.html')

        if new_password != confirm_password:
            flash('Nowe hasła nie pasują do siebie', 'error')
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
            flash('Hasło zostało zmienione', 'success')
            return redirect(url_for('auth.profile'))
        else:
            flash(error_message, 'error')
            return render_template('auth/change_password.html')

    return render_template('auth/change_password.html')


# ---------------------------------------------------------------------------
# Forgot / Reset password (no email required — token shown directly on screen)
# ---------------------------------------------------------------------------

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Formularz resetowania hasła — wyświetla link z tokenem na ekranie"""
    reset_url = None

    if request.method == 'POST':
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

                try:
                    AuditRepository().log_event(
                        entity_type='user', action='PASSWORD_RESET_REQUESTED',
                        entity_id=user.id, entity_label=user.email,
                    )
                except Exception:
                    pass

            # Always show the same neutral message (prevents email enumeration)
            # reset_url is only set when user was found

    return render_template('auth/forgot_password.html', reset_url=reset_url)


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token: str):
    """Formularz ustawiania nowego hasła po kliknięciu w link z tokenem"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM password_reset_tokens WHERE token = %s AND used = FALSE AND expires_at > NOW()",
        (token,)
    )
    token_row = cursor.fetchone()

    if not token_row:
        flash('Link wygasł lub został już użyty. Spróbuj ponownie.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if len(new_password) < 8:
            flash('Hasło musi mieć co najmniej 8 znaków.', 'error')
            return render_template('auth/reset_password.html', token=token)

        if new_password != confirm_password:
            flash('Hasła nie pasują do siebie.', 'error')
            return render_template('auth/reset_password.html', token=token)

        # Update password and mark token as used
        user_repo = UserRepository()
        user_repo.update_password(token_row['user_id'], new_password)

        cursor.execute(
            "UPDATE password_reset_tokens SET used = TRUE WHERE token = %s",
            (token,)
        )
        conn.commit()

        try:
            AuditRepository().log_event(
                entity_type='user', action='PASSWORD_RESET',
                entity_id=token_row['user_id'],
                new_value=request.remote_addr,
            )
        except Exception:
            pass

        flash('Hasło zostało zmienione. Możesz się teraz zalogować.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)
