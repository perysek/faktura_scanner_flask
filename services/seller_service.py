"""
Serwis zarządzania sprzedawcami
"""
from typing import Optional, Dict, Tuple
import re

from database.models import Seller, Invoice
from repositories.seller_repository import SellerRepository
from repositories.invoice_repository import InvoiceRepository


class SellerService:
    """Serwis zarządzania sprzedawcami"""
    
    def __init__(self, seller_repo: SellerRepository, invoice_repo: InvoiceRepository = None):
        self.seller_repo = seller_repo
        self.invoice_repo = invoice_repo
    
    def normalize_nip(self, nip: str) -> str:
        """
        Normalizuj numer NIP (usuń spacje, myślniki, sprawdź format)
        
        Args:
            nip: Numer NIP w dowolnym formacie
            
        Returns:
            Znormalizowany NIP (tylko cyfry)
        """
        if not nip:
            return ""
        
        # Usuń wszystkie znaki niebędące cyframi
        normalized = re.sub(r'[^0-9]', '', nip)
        
        # NIP powinien mieć 10 cyfr
        if len(normalized) == 10:
            return normalized
        
        return nip  # Zwróć oryginalny jeśli nie pasuje do formatu
    
    def normalize_seller_name(self, name: str) -> str:
        """
        Normalizuj nazwę sprzedawcy (usuń nadmiarowe spacje, standardizuj wielkość liter)
        
        Args:
            name: Nazwa sprzedawcy
            
        Returns:
            Znormalizowana nazwa
        """
        if not name:
            return ""
        
        # Usuń nadmiarowe spacje
        normalized = ' '.join(name.split())
        
        # Opcjonalnie: Możesz dodać więcej logiki normalizacji
        # np. zamiana niektórych znaków specjalnych, ujednolicenie skrótów itp.
        
        return normalized
    
    def normalize_seller_data(self, nip: str, name: str, address: str = None) -> Dict[str, str]:
        """
        Normalizuj wszystkie dane sprzedawcy
        
        Returns:
            Dict z znormalizowanymi danymi: {'nip': ..., 'name': ..., 'address': ...}
        """
        return {
            'nip': self.normalize_nip(nip),
            'name': self.normalize_seller_name(name),
            'address': address.strip() if address else None
        }
    
    def detect_conflicts(self, nip: str, name: str) -> Optional[Dict]:
        """
        Wykryj konflikty - sprawdź czy NIP istnieje z inną nazwą
        
        Args:
            nip: Numer NIP
            name: Nazwa sprzedawcy
            
        Returns:
            Dict z informacjami o konflikcie lub None jeśli brak konfliktu
            {
                'existing_seller': Seller object,
                'conflict_type': 'name_mismatch',
                'message': 'NIP 1234567890 already exists with name ...'
            }
        """
        normalized_nip = self.normalize_nip(nip)
        normalized_name = self.normalize_seller_name(name)
        
        # Sprawdź czy seller istnieje
        existing_row = self.seller_repo.find_by_nip(normalized_nip)
        
        if not existing_row:
            return None  # Brak konfliktu
        
        existing_seller = self.seller_repo.row_to_seller(existing_row)
        existing_name = self.normalize_seller_name(existing_seller.seller_name)
        
        # Sprawdź czy nazwy się różnią
        if existing_name != normalized_name:
            return {
                'existing_seller': existing_seller,
                'conflict_type': 'name_mismatch',
                'message': f"NIP {normalized_nip} already exists with name '{existing_seller.seller_name}' (new: '{name}')"
            }
        
        return None  # Brak konfliktu
    
    def get_or_create_seller(self, nip: str, name: str, address: str = None) -> Tuple[int, bool, Optional[Dict]]:
        """
        Pobierz istniejącego sprzedawcę lub stwórz nowego
        
        Args:
            nip: Numer NIP
            name: Nazwa sprzedawcy
            address: Adres sprzedawcy (opcjonalny)
            
        Returns:
            Tuple of (seller_id: int, created: bool, conflict: Optional[Dict])
        """
        # Normalizuj dane
        normalized = self.normalize_seller_data(nip, name, address)
        
        # Wykryj konflikty
        conflict = self.detect_conflicts(normalized['nip'], normalized['name'])
        
        if conflict:
            # Zwróć istniejącego sprzedawcę ale oznacz konflikt
            return conflict['existing_seller'].id, False, conflict
        
        # Pobierz lub stwórz
        seller_id, created = self.seller_repo.get_or_create(
            nip=normalized['nip'],
            name=normalized['name'],
            address=normalized['address']
        )
        
        return seller_id, created, None
    
    def update_from_invoice(self, invoice: Invoice) -> Tuple[int, bool, Optional[Dict]]:
        """
        Zaktualizuj lub stwórz sprzedawcę na podstawie danych z faktury
        
        Args:
            invoice: Obiekt Invoice
            
        Returns:
            Tuple of (seller_id: int, created: bool, conflict: Optional[Dict])
        """
        if not invoice.seller_nip:
            raise ValueError("Invoice must have seller_nip to update seller")
        
        seller_id, created, conflict = self.get_or_create_seller(
            nip=invoice.seller_nip,
            name=invoice.seller_name,
            address=None
        )
        
        # Jeśli sprzedawca już istnieje (nie został stworzony), zaktualizuj licznik
        if not created and not conflict:
            self.seller_repo.increment_invoice_count(seller_id)
        elif created:
            # Nowy sprzedawca - ustaw licznik na 1
            self.seller_repo.increment_invoice_count(seller_id)
        
        return seller_id, created, conflict
    
    def bulk_update_invoices(self, seller_id: int) -> int:
        """
        Propaguj zmiany sprzedawcy do wszystkich powiązanych faktur
        
        Args:
            seller_id: ID sprzedawcy
            
        Returns:
            Liczba zaktualizowanych faktur
        """
        if not self.invoice_repo:
            raise ValueError("InvoiceRepository not provided - cannot bulk update")
        
        # Pobierz sprzedawcę
        seller_row = self.seller_repo.get_by_id(seller_id)
        if not seller_row:
            raise ValueError(f"Seller {seller_id} not found")
        
        seller = self.seller_repo.row_to_seller(seller_row)
        
        # Pobierz wszystkie faktury tego sprzedawcy
        invoices = self.invoice_repo.get_by_seller(seller_id)
        
        updated_count = 0
        for invoice_row in invoices:
            invoice = self.invoice_repo.row_to_invoice(invoice_row)
            
            # Zaktualizuj dane sprzedawcy w fakturze
            invoice.seller_name = seller.seller_name
            invoice.seller_nip = seller.seller_nip
            
            # Zapisz fakturę
            if self.invoice_repo.update(invoice.id, invoice):
                updated_count += 1
        
        return updated_count
    
    def resolve_conflict(self, conflict: Dict, resolution: str, new_name: str = None) -> int:
        """
        Rozwiąż konflikt nazwy sprzedawcy
        
        Args:
            conflict: Dict zwrócony przez detect_conflicts()
            resolution: 'update_seller' lub 'keep_existing'
            new_name: Nowa nazwa (tylko dla resolution='update_seller')
            
        Returns:
            seller_id po rozwiązaniu konfliktu
        """
        seller = conflict['existing_seller']
        
        if resolution == 'update_seller' and new_name:
            # Zaktualizuj nazwę sprzedawcy
            normalized_name = self.normalize_seller_name(new_name)
            self.seller_repo.update_name(seller.id, normalized_name)
            return seller.id
        
        elif resolution == 'keep_existing':
            # Użyj istniejącego sprzedawcy bez zmian
            return seller.id
        
        else:
            raise ValueError(f"Invalid resolution: {resolution}")
    
    def get_seller_statistics(self, seller_id: int) -> Dict:
        """
        Pobierz statystyki sprzedawcy
        
        Returns:
            Dict z statystykami: {
                'seller': Seller object,
                'total_invoices': int,
                'total_paid': float,
                'total_unpaid': float,
                'currency': str
            }
        """
        seller_row = self.seller_repo.get_by_id(seller_id)
        if not seller_row:
            return None
        
        seller = self.seller_repo.row_to_seller(seller_row)
        
        # Pobierz statystyki (wykorzystując get_all_with_stats)
        # Możemy też dodać dedykowaną metodę w repozytorium
        
        return {
            'seller': seller,
            'total_invoices': seller.invoice_count,
            # Dodaj więcej statystyk w przyszłości
        }
