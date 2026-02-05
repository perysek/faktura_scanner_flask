"""
Skrypt do utworzenia testowych użytkowników
Run: python scripts/seed_users.py
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from repositories.users.user_repository import UserRepository


def seed_users():
    """Create test users for all 5 roles"""
    user_repo = UserRepository()

    # Test users: (email, password, full_name, role)
    test_users = [
        ('superuser@salon.pl', 'Super123!', 'Administrator Systemu', 'superuser'),
        ('admin@salon.pl', 'Admin123!', 'Anna Kowalska', 'admin'),
        ('receptionist@salon.pl', 'Test123!', 'Maria Nowak', 'receptionist'),
        ('stylist@salon.pl', 'Test123!', 'Ewa Wiśniewska', 'stylist'),
        ('accountant@salon.pl', 'Test123!', 'Jan Kowalczyk', 'accountant'),
    ]

    print("=" * 60)
    print("SEED USERS - Tworzenie testowych kont")
    print("=" * 60)

    for email, password, full_name, role in test_users:
        # Check if user already exists
        existing = user_repo.get_by_email(email)
        if existing:
            print(f"[SKIP] Uzytkownik juz istnieje: {email} ({role})")
            continue

        # Create user
        user_id = user_repo.create_user(email, password, full_name, role)
        print(f"[OK] Utworzono: {email} ({role}) - ID: {user_id}")

    print("\n" + "=" * 60)
    print("PODSUMOWANIE KONT TESTOWYCH")
    print("=" * 60)
    print("\nDostępne konta:")
    for email, password, full_name, role in test_users:
        print(f"\nRola: {role.upper()}")
        print(f"  Email: {email}")
        print(f"  Hasło: {password}")
        print(f"  Imię: {full_name}")

    print("\n" + "=" * 60)
    print("Możesz się teraz zalogować na http://localhost:5000/auth/login")
    print("=" * 60)


if __name__ == '__main__':
    seed_users()
