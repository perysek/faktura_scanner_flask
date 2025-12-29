"""
Modele danych (dataclasses)
"""
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional


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