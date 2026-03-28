"""
Modele danych (dataclasses)
"""
from dataclasses import dataclass, field
from datetime import datetime, date, time
from decimal import Decimal
from typing import Optional
from flask_login import UserMixin


@dataclass
class Invoice:
    """Model faktury"""
    seller_name: str
    invoice_number: str
    invoice_date: date
    amount: Decimal
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
class SellerPdfPassword:
    """Model hasła PDF sprzedawcy — do automatycznego odblokowywania zaszyfrowanych faktur"""
    pdf_password: str
    seller_id: Optional[int] = None
    email_sender_pattern: Optional[str] = None  # e.g. "noreply@axpo.pl" or "%@enea.pl"
    description: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = field(default_factory=datetime.now)


@dataclass
class AuditEntry:
    """Model wpisu historii zmian — obsługuje wszystkie encje aplikacji"""
    entity_type: str                   # invoice, appointment, client, service, employee, seller, import, login
    action: str                        # CREATE, UPDATE, DELETE, LOGIN, LOGOUT, IMPORT
    entity_id: Optional[int] = None
    entity_label: Optional[str] = None
    invoice_id: Optional[int] = None   # backward compat
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    user_id: Optional[int] = None
    user_name: Optional[str] = None
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
    forma_zatrudnienia_id: Optional[int] = None  # FK to formy_zatrudnienia
    phone: Optional[str] = None
    email: Optional[str] = None
    position: Optional[str] = None  # 'Stylist', 'Receptionist', 'Manager'
    employment_status: str = 'active'  # 'active', 'on_leave', 'terminated'
    hire_date: Optional[date] = None
    termination_date: Optional[date] = None
    base_salary: Optional[float] = None  # Monthly base salary
    commission_rate: Optional[float] = None  # Percentage (e.g., 40.00 for 40%)
    employer_cost_rate: float = 0.22  # Polish ZUS/taxes rate (e.g. 0.22 = 22%)
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

    @property
    def full_name(self) -> str:
        """Pełne imię i nazwisko pracownika"""
        return f"{self.first_name} {self.last_name}"

    def get_skills_dict(self) -> dict:
        """Pobierz umiejętności jako słownik (parsowanie JSON)"""
        if not self.skills:
            return {}
        try:
            import json
            return json.loads(self.skills)
        except (json.JSONDecodeError, TypeError):
            return {}

    def get_specializations_list(self) -> list:
        """Pobierz specjalizacje jako listę (parsowanie JSON)"""
        if not self.specializations:
            return []
        try:
            import json
            return json.loads(self.specializations)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_work_schedule_dict(self) -> dict:
        """Pobierz grafik jako słownik (parsowanie JSON)"""
        if not self.work_schedule:
            return {}
        try:
            import json
            return json.loads(self.work_schedule)
        except (json.JSONDecodeError, TypeError):
            return {}


@dataclass
class FormaZatrudnienia:
    """Model formy zatrudnienia (np. UoP, B2B, Umowa zlecenie)"""
    nazwa: str
    uwagi: Optional[str] = None
    min_salary_required: bool = False  # Czy wymagane minimalne wynagrodzenie
    granted_salary: bool = False       # Czy wynagrodzenie gwarantowane
    commision_included: bool = False   # Czy prowizja wliczona
    id: Optional[int] = None
    created_at: Optional[datetime] = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = field(default_factory=datetime.now)


@dataclass
class Service:
    """Model usługi salonowej"""
    name: str
    duration_minutes: int
    price: float
    category: Optional[str] = None  # Required for service_type='main'; None for 'addon'
    currency: str = 'PLN'
    service_type: str = 'main'  # 'main' or 'addon'
    description: Optional[str] = None
    is_active: bool = True
    id: Optional[int] = None
    created_at: Optional[datetime] = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = field(default_factory=datetime.now)

    @property
    def is_addon_service(self) -> bool:
        """Czy usługa jest usługą dodatkową (mikrousługą)"""
        return self.service_type == 'addon'

    @property
    def formatted_price(self) -> str:
        """Sformatowana cena z walutą"""
        if self.currency == 'PLN':
            return f"{self.price:.2f} zł"
        return f"{self.price:.2f} {self.currency}"

    @property
    def formatted_duration(self) -> str:
        """Sformatowany czas trwania"""
        hours = self.duration_minutes // 60
        minutes = self.duration_minutes % 60
        if hours > 0 and minutes > 0:
            return f"{hours}h {minutes}min"
        elif hours > 0:
            return f"{hours}h"
        else:
            return f"{minutes}min"


@dataclass
class Client:
    """Model klienta salonu"""
    first_name: str
    last_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    date_of_birth: Optional[date] = None
    notes: Optional[str] = None
    preferences: Optional[str] = None  # JSON string: '{"allergies": [], "favorite_products": []}'
    first_visit_date: Optional[date] = None
    last_visit_date: Optional[date] = None
    is_active: bool = True
    id: Optional[int] = None
    created_at: Optional[datetime] = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = field(default_factory=datetime.now)

    @property
    def full_name(self) -> str:
        """Pełne imię i nazwisko klienta"""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def age(self) -> Optional[int]:
        """Oblicz wiek klienta na podstawie daty urodzenia"""
        if not self.date_of_birth:
            return None
        today = date.today()
        age = today.year - self.date_of_birth.year
        # Adjust if birthday hasn't occurred this year yet
        if (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day):
            age -= 1
        return age

    def get_preferences_dict(self) -> dict:
        """Pobierz preferencje jako słownik (parsowanie JSON)"""
        if not self.preferences:
            return {}
        try:
            import json
            return json.loads(self.preferences)
        except (json.JSONDecodeError, TypeError):
            return {}


@dataclass
class ServiceAddon:
    """Model powiązania usługi dodatkowej z usługą główną.

    Definiuje kompatybilność: które mikrousługi pasują do których usług głównych.
    Brak wpisów = mikrousługa kompatybilna ze wszystkimi usługami głównymi.
    """
    addon_service_id: int
    main_service_id: int
    id: Optional[int] = None
    created_at: Optional[datetime] = field(default_factory=datetime.now)


@dataclass
class EmployeeService:
    """Model przypisania usługi do pracownika z opcjonalnym cenowaniem.

    Umożliwia indywidualne ceny, prowizje i czasy trwania per pracownik.
    Wartości NULL oznaczają użycie domyślnych z tabel services/employees.
    """
    employee_id: int
    service_id: int
    custom_price: Optional[Decimal] = None
    commission_rate: Optional[Decimal] = None
    duration_override: Optional[int] = None
    skill_rating: Optional[int] = None  # Manual 1-5 rating set by manager
    is_active: bool = True
    id: Optional[int] = None
    created_at: Optional[datetime] = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = field(default_factory=datetime.now)


@dataclass
class ClientPreference:
    """Model preferencji klienta — preferowany pracownik na usługę/kategorię."""
    client_id: int
    preferred_employee_id: int
    service_id: Optional[int] = None
    service_category: Optional[str] = None
    notes: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = field(default_factory=datetime.now)


@dataclass
class Appointment:
    """Model wizyty w salonie."""
    client_id: int
    employee_id: int
    appointment_date: date
    start_time: time
    end_time: time
    status: str = 'scheduled'  # scheduled, confirmed, in_progress, completed, cancelled, no_show
    total_price: Decimal = Decimal('0')
    total_duration: int = 0
    discount_amount: Decimal = Decimal('0')
    notes: Optional[str] = None
    cancellation_reason: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    satisfaction_score: Optional[int] = None
    created_by: Optional[int] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = field(default_factory=datetime.now)

    @property
    def net_price(self) -> Decimal:
        """Cena po rabacie"""
        return self.total_price - self.discount_amount

    @property
    def is_cancellable(self) -> bool:
        """Czy wizytę można anulować"""
        return self.status in ('scheduled', 'confirmed', 'in_progress')

    @property
    def can_add_addon(self) -> bool:
        """Czy można dodać mikrousługę (tylko w trakcie wizyty)"""
        return self.status == 'in_progress'


@dataclass
class AppointmentService:
    """Model usługi przypisanej do wizyty (snapshot cenowy).

    Przechowuje cenę/prowizję z momentu dodania — niezmienny rekord finansowy.
    is_addon=True oznacza mikrousługę dodaną w trakcie wizyty.
    """
    appointment_id: int
    service_id: int
    price_charged: Decimal
    duration_minutes: int
    commission_rate: Decimal = Decimal('0')
    commission_amount: Decimal = Decimal('0')
    is_addon: bool = False
    added_at: Optional[datetime] = None  # NULL = zarezerwowana z góry, timestamp = dodana w trakcie
    id: Optional[int] = None


@dataclass
class IncomeRecord:
    """Model rekordu przychodu — tworzony przy zamknięciu wizyty (status=completed).

    Łączy sumy z usług głównych i mikrousług w jeden rekord finansowy.
    """
    appointment_id: int
    client_id: int
    employee_id: int
    total_amount: Decimal
    net_amount: Decimal
    commission_total: Decimal
    payment_date: date
    discount_amount: Decimal = Decimal('0')
    payment_method: Optional[str] = None
    notes: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = field(default_factory=datetime.now)