"""
Trasy autentykacji - logowanie, wylogowanie, profil
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from repositories.users.user_repository import UserRepository
from services.auth.auth_service import AuthService

# Create blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Strona logowania"""
    # Jeśli użytkownik już zalogowany, przekieruj do dashboard
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

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
            # Zaloguj użytkownika (Flask-Login)
            login_user(user, remember=remember)
            flash(f'Witaj, {user.full_name}!', 'success')

            # Przekieruj do next URL lub dashboard
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('main.dashboard'))
        else:
            flash(error_message, 'error')
            return render_template('auth/login.html', email=email)

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Wylogowanie użytkownika"""
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
