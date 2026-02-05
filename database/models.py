"""
Modele danych (dataclasses)
"""
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional
from flask_login import UserMixin


@dataclass
class Invoice:
    """Model faktury"""
    seller_name: str
    invoice_number: str
    invoice_date: date
    amount: float
    currency: str = "PLN"
    seller_nip: Optional[str] = None
    bank_account: Optional[str] = None
    payment_due_date: Optional[date] = None
    payment_term: Optional[str] = None
    status: str = "Nieopłacona"
    pdf_path: Optional[str] = None
    ocr_confidence: Optional[float] = None
    is_duplicate: bool = False
    id: Optional[int] = None
    created_at: Optional[datetime] = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = field(default_factory=datetime.now)


@dataclass
class Seller:
    """Model sprzedawcy"""
    seller_nip: str  # Unique identifier
    seller_name: str
    address: Optional[str] = None
    first_seen: Optional[datetime] = field(default_factory=datetime.now)
    last_updated: Optional[datetime] = field(default_factory=datetime.now)
    invoice_count: int = 0  # Denormalized count for quick stats
    id: Optional[int] = None


@dataclass
class AuditEntry:
    """Model wpisu historii zmian"""
    invoice_id: int
    field_name: str
    old_value: Optional[str]
    new_value: Optional[str]
    action: str = "UPDATE"
    changed_at: datetime = field(default_factory=datetime.now)
    id: Optional[int] = None


@dataclass
class UploadStaging:
    """Model tymczasowego przechowywania uploadowanych plików"""
    session_id: str
    filename: str
    file_path: str
    file_size: int
    email_subject: Optional[str] = None
    email_sender: Optional[str] = None
    email_folder: Optional[str] = None
    email_date: Optional[str] = None
    uploaded_at: datetime = field(default_factory=datetime.now)
    id: Optional[int] = None


@dataclass
class User(UserMixin):
    """Model użytkownika (konto logowania)"""
    email: str
    password_hash: str
    full_name: str
    role: str = 'receptionist'  # 'superuser', 'admin', 'receptionist', 'stylist', 'accountant'
    is_active: bool = True
    id: Optional[int] = None
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = field(default_factory=datetime.now)

    def get_id(self):
        """Required by Flask-Login"""
        return str(self.id)

    @property
    def is_authenticated(self):
        """Required by Flask-Login"""
        return True

    @property
    def is_anonymous(self):
        """Required by Flask-Login"""
        return False

    def has_role(self, *roles):
        """Check if user has any of the specified roles"""
        return self.role in roles


@dataclass
class Employee:
    """Model pracownika salonu"""
    first_name: str
    last_name: str
    user_id: Optional[int] = None  # Optional link to users table
    phone: Optional[str] = None
    email: Optional[str] = None
    position: Optional[str] = None  # 'Stylist', 'Receptionist', 'Manager'
    employment_status: str = 'active'  # 'active', 'on_leave', 'terminated'
    hire_date: Optional[date] = None
    termination_date: Optional[date] = None
    base_salary: Optional[float] = None  # Monthly base salary
    commission_rate: Optional[float] = None  # Percentage (e.g., 40.00 for 40%)
    skills: Optional[str] = None  # JSON string: '{"Hair Color": 5, "Balayage": 4}'
    specializations: Optional[str] = None  # JSON string: '["Bridal", "Extensions"]'
    work_schedule: Optional[str] = None  # JSON string: '{"mon": "9-17", "tue": "9-17"}'
    max_appointments_per_day: int = 8
    notes: Optional[str] = None
    photo_path: Optional[str] = None
    is_active: bool = True
    id: Optional[int] = None
    created_at: Optional[datetime] = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = field(default_factory=datetime.now)