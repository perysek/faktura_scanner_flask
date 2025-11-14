"""
Email service for fetching invoice PDFs via IMAP
"""
import imaplib
import email
from email.header import decode_header
from datetime import datetime, date
from pathlib import Path
from typing import List, Tuple, Optional
import os


class EmailService:
	"""Service for connecting to email and downloading PDF attachments"""

	def __init__(self):
		self.imap = None
		self.connected = False

	def test_connection(self, settings: dict) -> bool:
		"""
		Test IMAP connection with given settings

		Args:
			settings: Dict with email_address, password, imap_server, imap_port

		Returns:
			True if connection successful, False otherwise
		"""
		try:
			# Connect to IMAP server
			imap = imaplib.IMAP4_SSL(
				settings['imap_server'],
				settings['imap_port']
			)

			# Login
			imap.login(
				settings['email_address'],
				settings['password']
			)

			# Logout
			imap.logout()

			return True

		except Exception as e:
			print(f"Connection test failed: {e}")
			return False

	def connect(self, email_address: str, password: str, imap_server: str, imap_port: int) -> bool:
		"""
		Connect to IMAP server

		Returns:
			True if connection successful
		"""
		try:
			# Connect to IMAP server with SSL
			self.imap = imaplib.IMAP4_SSL(imap_server, imap_port)

			# Login
			self.imap.login(email_address, password)

			self.connected = True
			print(f"✅ Connected to {imap_server} as {email_address}")
			return True

		except Exception as e:
			print(f"❌ Connection failed: {e}")
			self.connected = False
			return False

	def disconnect(self):
		"""Disconnect from IMAP server"""
		if self.imap and self.connected:
			try:
				self.imap.logout()
				self.connected = False
				print("✅ Disconnected from email server")
			except:
				pass

	def fetch_pdf_attachments(
			self,
			from_date: Optional[date] = None,
			to_date: Optional[date] = None,
			save_dir: str = None,
			progress_callback: Optional[callable] = None
	) -> List[Tuple[str, str]]:
		"""
		Fetch PDF attachments from emails

		Args:
			from_date: Start date for email search
			to_date: End date for email search
			save_dir: Directory to save PDFs (if None, uses temp dir)
			progress_callback: Optional callback function(message, detail) for progress updates

		Returns:
			List of tuples: (pdf_filename, pdf_path)
		"""
		if not self.connected:
			print("❌ Not connected to email server")
			if progress_callback:
				progress_callback("❌ Nie połączono z serwerem email", "", None)
			return []

		try:
			# Select inbox
			self.imap.select("INBOX")

			# Build search criteria
			search_criteria = ["ALL"]

			if from_date:
				search_criteria = [f'SINCE {from_date.strftime("%d-%b-%Y")}']

			if to_date:
				if from_date:
					search_criteria = [
						f'SINCE {from_date.strftime("%d-%b-%Y")}',
						f'BEFORE {to_date.strftime("%d-%b-%Y")}'
					]
				else:
					search_criteria = [f'BEFORE {to_date.strftime("%d-%b-%Y")}']

			# Search for emails
			search_string = " ".join(search_criteria)
			status, messages = self.imap.search(None, *search_criteria)

			if status != "OK":
				print("❌ Error searching emails")
				if progress_callback:
					progress_callback("❌ Błąd wyszukiwania wiadomości", "", None)
				return []

			# Get message IDs
			email_ids = messages[0].split()
			print(f"📧 Found {len(email_ids)} emails")
			if progress_callback:
				progress_callback(f"📧 Znaleziono {len(email_ids)} wiadomości", "Przetwarzanie załączników...", 0.5)

			pdf_files = []

			# Process each email
			for idx, email_id in enumerate(email_ids, 1):
				if progress_callback:
					# Calculate progress (50% after search, 100% after processing all emails)
					progress = 0.5 + (0.5 * idx / len(email_ids))
					progress_callback(
						f"Przetwarzanie wiadomości {idx}/{len(email_ids)}",
						"Szukanie załączników PDF...",
						progress
					)
				pdfs = self._process_email(email_id, save_dir, progress_callback)
				pdf_files.extend(pdfs)

			print(f"✅ Downloaded {len(pdf_files)} PDF attachments")
			if progress_callback:
				progress_callback(f"✅ Pobrano {len(pdf_files)} plików PDF", "Import zakończony", 1.0)
			return pdf_files

		except Exception as e:
			print(f"❌ Error fetching emails: {e}")
			import traceback
			traceback.print_exc()
			if progress_callback:
				progress_callback(f"❌ Błąd: {str(e)}", "", None)
			return []

	def _process_email(self, email_id: bytes, save_dir: str = None, progress_callback: Optional[callable] = None) -> List[Tuple[str, str]]:
		"""
		Process a single email and extract PDF attachments

		Returns:
			List of tuples: (pdf_filename, pdf_path)
		"""
		pdf_files = []
		message = None

		try:
			# Fetch email
			status, msg_data = self.imap.fetch(email_id, "(RFC822)")

			if status != "OK":
				return []

			# Parse email
			email_body = msg_data[0][1]
			message = email.message_from_bytes(email_body)

			# Process attachments
			if message.is_multipart():
				for part in message.walk():
					# Check if part is an attachment
					if part.get_content_maintype() == 'multipart':
						continue

					if part.get('Content-Disposition') is None:
						continue

					filename = part.get_filename()

					if filename:
						# Decode filename if needed
						if decode_header(filename)[0][1]:
							filename = decode_header(filename)[0][0].decode(
								decode_header(filename)[0][1]
							)

						# Check if PDF
						if filename.lower().endswith('.pdf'):
							# Notify start of download
							if progress_callback:
								progress_callback(f"📄 Pobieranie: {filename}", "Zapisywanie załącznika...", None)

							# Get payload data
							payload_data = part.get_payload(decode=True)

							# Save PDF
							pdf_path = self._save_attachment(
								payload_data,
								filename,
								save_dir,
								progress_callback
							)

							if pdf_path:
								pdf_files.append((filename, pdf_path))
								print(f"  📄 Downloaded: {filename}")
								if progress_callback:
									progress_callback(f"✅ Pobrano: {filename}", f"Rozmiar: {len(payload_data) / 1024:.1f} KB", None)

							# Clear payload reference to free memory
							del payload_data

		except Exception as e:
			print(f"Error processing email {email_id}: {e}")
			if progress_callback:
				progress_callback(f"❌ Błąd przetwarzania wiadomości", str(e), None)

		finally:
			# Clear message reference to ensure cleanup
			if message is not None:
				del message

		return pdf_files

	def _save_attachment(self, data: bytes, filename: str, save_dir: str = None, progress_callback: Optional[callable] = None) -> Optional[str]:
		"""
		Save attachment to file

		Returns:
			Path to saved file, or None if error
		"""
		try:
			# Use temp dir if not specified
			if save_dir is None:
				from config.settings import TEMP_DIR
				save_dir = TEMP_DIR

			# Create directory if doesn't exist
			save_dir = Path(save_dir)
			save_dir.mkdir(parents=True, exist_ok=True)

			# Create unique filename if file exists
			pdf_path = save_dir / filename
			counter = 1
			while pdf_path.exists():
				name, ext = os.path.splitext(filename)
				pdf_path = save_dir / f"{name}_{counter}{ext}"
				counter += 1

			# Write file and ensure it's fully closed
			if progress_callback:
				progress_callback(f"💾 Zapisywanie: {filename}", f"Zapisywanie {len(data) / 1024:.1f} KB na dysk...", None)

			with open(pdf_path, 'wb') as f:
				f.write(data)
				f.flush()  # Force write to disk
				os.fsync(f.fileno())  # Ensure OS writes to disk

			# Explicitly close file (redundant but ensures closure)
			# The 'with' statement already closes it, but being extra safe

			# Longer delay to ensure file handle is released on Windows
			import time
			time.sleep(0.3)  # Increased from 0.1 to 0.3 seconds

			# Verify file is accessible by trying to open it
			max_retries = 3
			for attempt in range(max_retries):
				try:
					# Try to open file in read mode to verify it's accessible
					with open(pdf_path, 'rb') as test_f:
						pass
					break  # File is accessible
				except Exception as e:
					if attempt < max_retries - 1:
						print(f"  ⚠️ File not yet accessible, retrying... ({attempt + 1}/{max_retries})")
						if progress_callback:
							progress_callback(
								f"⚠️ Weryfikacja dostępu: {filename}",
								f"Próba {attempt + 1}/{max_retries}...",
								None
							)
						time.sleep(0.5)
					else:
						print(f"  ❌ File still locked after {max_retries} attempts")
						if progress_callback:
							progress_callback(f"❌ Plik zablokowany: {filename}", "Nie można uzyskać dostępu", None)
						raise

			return str(pdf_path)

		except Exception as e:
			print(f"Error saving attachment: {e}")
			if progress_callback:
				progress_callback(f"❌ Błąd zapisu: {filename}", str(e), None)
			return None
