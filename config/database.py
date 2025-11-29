"""
Konfiguracja bazy danych SQLite
"""
import sqlite3
from pathlib import Path
from typing import Optional
from config.settings import DB_PATH


class DatabaseConnection:
	"""Singleton connection do SQLite"""
	
	_instance: Optional[sqlite3.Connection] = None
	
	@classmethod
	def get_connection(cls) -> sqlite3.Connection:
		"""Pobierz połączenie do bazy (singleton)"""
		if cls._instance is None:
			cls._instance = sqlite3.connect(
				DB_PATH,
				check_same_thread=False  # Dla Flet threading
				)
			cls._instance.row_factory = sqlite3.Row  # Dostęp po nazwach kolumn
		return cls._instance
	
	@classmethod
	def close(cls):
		"""Zamknij połączenie"""
		if cls._instance:
			cls._instance.close()
			cls._instance = None


def initialize_database():
	"""Inicjalizuj bazę danych ze schema"""
	conn = DatabaseConnection.get_connection()

	# Wczytaj schema
	schema_path = Path(__file__).parent.parent / "database" / "schema.sql"
	with open(schema_path, 'r', encoding='utf-8') as f:
		schema = f.read()

	# Wykonaj
	conn.executescript(schema)
	conn.commit()

	# Migracja: dodaj payment_term column jeśli nie istnieje
	try:
		cursor = conn.cursor()
		# Sprawdź czy kolumna payment_term istnieje
		cursor.execute("PRAGMA table_info(invoices)")
		columns = [row[1] for row in cursor.fetchall()]

		if 'payment_term' not in columns:
			print("Dodawanie kolumny payment_term do tabeli invoices...")
			cursor.execute("ALTER TABLE invoices ADD COLUMN payment_term TEXT")
			conn.commit()
			print("Kolumna payment_term dodana")
	except Exception as e:
		print(f"Ostrzezenie - Migracja payment_term: {e}")

	# Migracja: dodaj status column jeśli nie istnieje
	try:
		cursor = conn.cursor()
		# Sprawdź czy kolumna status istnieje
		cursor.execute("PRAGMA table_info(invoices)")
		columns = [row[1] for row in cursor.fetchall()]

		if 'status' not in columns:
			print("Dodawanie kolumny status do tabeli invoices...")
			cursor.execute("ALTER TABLE invoices ADD COLUMN status TEXT DEFAULT 'Nieoplacona'")
			conn.commit()
			print("Kolumna status dodana")
	except Exception as e:
		print(f"Ostrzezenie - Migracja status: {e}")

	print("Baza danych zainicjalizowana")