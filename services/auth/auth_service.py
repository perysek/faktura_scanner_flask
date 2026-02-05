"""
Serwis autentykacji - logowanie, wylogowanie, zarządzanie sesjami
"""
from typing import Optional, Tuple
from database.models import User
from repositories.users.user_repository import UserRepository


class AuthService:
    """Serwis zarządzania autentykacją"""

    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def authenticate(self, email: str, password: str) -> Tuple[bool, Optional[User], Optional[str]]:
        """
        Autentykuj użytkownika

        Args:
            email: Adres email
            password: Hasło w postaci jawnej

        Returns:
            Tuple (success: bool, user: Optional[User], error_message: Optional[str])
        """
        # Pobierz użytkownika po emailu
        user = self.user_repo.get_by_email(email)

        if not user:
            return False, None, "Nieprawidłowy email lub hasło"

        # Sprawdź czy konto jest aktywne
        if not user.is_active:
            return False, None, "Konto zostało dezaktywowane. Skontaktuj się z administratorem."

        # Weryfikuj hasło
        if not self.user_repo.verify_password(user, password):
            return False, None, "Nieprawidłowy email lub hasło"

        # Zaktualizuj timestamp ostatniego logowania
        self.user_repo.update_last_login(user.id)

        return True, user, None

    def change_password(self, user_id: int, old_password: str, new_password: str) -> Tuple[bool, Optional[str]]:
        """
        Zmień hasło użytkownika

        Args:
            user_id: ID użytkownika
            old_password: Stare hasło
            new_password: Nowe hasło

        Returns:
            Tuple (success: bool, error_message: Optional[str])
        """
        # Pobierz użytkownika
        user_row = self.user_repo.get_by_id(user_id)
        if not user_row:
            return False, "Użytkownik nie znaleziony"

        user = self.user_repo.row_to_user(user_row)

        # Weryfikuj stare hasło
        if not self.user_repo.verify_password(user, old_password):
            return False, "Nieprawidłowe stare hasło"

        # Walidacja nowego hasła
        if len(new_password) < 8:
            return False, "Nowe hasło musi mieć minimum 8 znaków"

        # Zaktualizuj hasło
        self.user_repo.update_password(user_id, new_password)

        return True, None

    def reset_password(self, user_id: int, new_password: str) -> Tuple[bool, Optional[str]]:
        """
        Reset hasła przez administratora (bez weryfikacji starego hasła)

        Args:
            user_id: ID użytkownika
            new_password: Nowe hasło

        Returns:
            Tuple (success: bool, error_message: Optional[str])
        """
        # Walidacja nowego hasła
        if len(new_password) < 8:
            return False, "Nowe hasło musi mieć minimum 8 znaków"

        # Zaktualizuj hasło
        self.user_repo.update_password(user_id, new_password)

        return True, None

    def deactivate_user(self, user_id: int) -> bool:
        """
        Dezaktywuj konto użytkownika

        Args:
            user_id: ID użytkownika

        Returns:
            True jeśli sukces
        """
        self.user_repo.deactivate(user_id)
        return True

    def activate_user(self, user_id: int) -> bool:
        """
        Aktywuj konto użytkownika

        Args:
            user_id: ID użytkownika

        Returns:
            True jeśli sukces
        """
        self.user_repo.activate(user_id)
        return True
