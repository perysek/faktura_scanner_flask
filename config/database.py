"""
Konfiguracja bazy danych SQLite
"""
import sqlite3
from pathlib import Path
from typing import Optional
from flask import g

from config.settings import DB_PATH


def get_database_path() -> str:
	"""Get the database path as string"""
	return str(DB_PATH)


def get_db_connection() -> sqlite3.Connection:
	"""Helper function to get database connection (used by repositories)"""
	return DatabaseConnection.get_connection()


class DatabaseConnection:
	"""Per-request database connection using Flask's g object"""

	@classmethod
	def get_connection(cls) -> sqlite3.Connection:
		"""Get per-request database connection from Flask's g object"""
		# Check if connection exists in current request context
		if 'db' not in g:
			# Create new connection for this request
			g.db = sqlite3.connect(
				DB_PATH,
				check_same_thread=True  # Safe since each request has its own connection
			)
			g.db.row_factory = sqlite3.Row
		return g.db

	@classmethod
	def close_connection(cls):
		"""Close the connection for current request context"""
		db = g.pop('db', None)
		if db is not None:
			db.close()

	@classmethod
	def close(cls):
		"""Alias for close_connection for backward compatibility"""
		cls.close_connection()


def initialize_database():
	"""Inicjalizuj bazę danych ze schema"""
	# Create direct connection (not using Flask g since we're outside request context)
	conn = sqlite3.connect(DB_PATH)
	conn.row_factory = sqlite3.Row

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

	# Migracja: dodaj action column do audit_log jeśli nie istnieje
	try:
		cursor = conn.cursor()
		cursor.execute("PRAGMA table_info(audit_log)")
		columns = [row[1] for row in cursor.fetchall()]

		if 'action' not in columns:
			print("Dodawanie kolumny action do tabeli audit_log...")
			cursor.execute("ALTER TABLE audit_log ADD COLUMN action TEXT DEFAULT 'UPDATE'")
			conn.commit()
			print("Kolumna action dodana")
	except Exception as e:
		print(f"Ostrzezenie - Migracja action: {e}")

	# Migracja: sprawdź czy tabela sellers istnieje
	try:
		cursor = conn.cursor()
		cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sellers'")
		if not cursor.fetchone():
			print("Tabela sellers nie istnieje - powinna zostać utworzona przez schema.sql")
	except Exception as e:
		print(f"Błąd sprawdzania tabeli sellers: {e}")

	# Migracja: dodaj seller_id do invoices jeśli nie istnieje
	try:
		cursor = conn.cursor()
		cursor.execute("PRAGMA table_info(invoices)")
		columns = [row[1] for row in cursor.fetchall()]

		if 'seller_id' not in columns:
			print("Dodawanie kolumny seller_id do tabeli invoices...")
			cursor.execute("ALTER TABLE invoices ADD COLUMN seller_id INTEGER REFERENCES sellers(id)")
			cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoice_seller ON invoices(seller_id)")
			conn.commit()
			print("Kolumna seller_id dodana")
	except Exception as e:
		print(f"Ostrzezenie - Migracja seller_id: {e}")

	# Close the connection
	conn.close()
	print("Baza danych zainicjalizowana")
