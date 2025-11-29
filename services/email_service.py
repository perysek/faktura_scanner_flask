"""
Email service for fetching invoice PDFs via IMAP
"""
import imaplib
import email
import os
import re
import time
from email.header import decode_header
from datetime import date
from pathlib import Path
from typing import List, Tuple, Optional


class EmailService:
	"""Service for connecting to email and downloading PDF attachments"""

	def __init__(self):
		self.imap = None
		self.connected = False

	@staticmethod
	def test_connection(settings: dict) -> bool:
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
			print(f"✅ Połączono z {imap_server} jako {email_address}")
			return True

		except Exception as e:
			print(f"❌ Błąd połączenia: {e}")
			self.connected = False
			return False

	def disconnect(self):
		"""Disconnect from IMAP server"""
		if self.imap and self.connected:
			try:
				self.imap.logout()
				self.connected = False
				print("✅ Rozłączono z serwerem email")
			except:
				pass

	def _list_folders(self) -> List[str]:
		"""
		List all selectable folders in the email account.
		"""
		folders = []
		try:
			status, folder_list = self.imap.list()
			if status == "OK":
				for folder_info in folder_list:
					# Decode folder info
					folder_info_decoded = folder_info.decode('utf-8', 'ignore')

					# Check if the folder is selectable
					if r'\Noselect' not in folder_info_decoded:
						# Extract folder name using regex
						match = re.search(r'"/"\s+"?([^"]+)"?', folder_info_decoded)
						if match:
							folder_name = match.group(1).strip()
							folders.append(folder_name)
		except Exception as e:
			print(f"❌ Błąd podczas listowania folderów: {e}")
		return folders

	def _build_search_criteria(self, from_date: Optional[date], to_date: Optional[date]) -> List[str]:
		"""
		Build search criteria for email search.
		"""
		search_criteria = ["ALL"]
		if from_date:
			search_criteria = [f'SINCE {from_date.strftime("%d-%b-%Y")}']
		if to_date:
			if from_date:
				search_criteria.append(f'BEFORE {to_date.strftime("%d-%b-%Y")}')
			else:
				search_criteria = [f'BEFORE {to_date.strftime("%d-%b-%Y")}']
		return search_criteria

	def fetch_pdf_attachments(
			self,
			from_date: Optional[date] = None,
			to_date: Optional[date] = None,
			save_dir: str = None,
			progress_callback: Optional[callable] = None
	) -> List[Tuple[str, str]]:
		"""
		Fetch PDF attachments from emails across all folders.
		"""
		if not self.connected:
			if progress_callback:
				progress_callback("❌ Nie połączono z serwerem email", "", None)
			return []

		all_pdf_files = []
		try:
			folders = self._list_folders()
			if not folders:
				if progress_callback:
					progress_callback("❌ Nie znaleziono żadnych folderów email", "", None)
				return []

			if progress_callback:
				progress_callback(f"🔎 Znaleziono {len(folders)} folderów", "Rozpoczynanie wyszukiwania emaili...", 0.1)

			search_criteria = self._build_search_criteria(from_date, to_date)

			for i, folder_name in enumerate(folders):
				try:
					if progress_callback:
						progress_callback(f"📂 Skanowanie folderu: {folder_name}", f"({i + 1}/{len(folders)})", 0.1 + 0.8 * (i / len(folders)))

					self.imap.select(f'"{folder_name}"')
					status, messages = self.imap.search(None, *search_criteria)

					if status != "OK":
						continue

					email_ids = messages[0].split()
					if not email_ids:
						continue

					if progress_callback:
						progress_callback(f"📧 Znaleziono {len(email_ids)} emaili w {folder_name}", "Przetwarzanie załączników...", None)

					for idx, email_id in enumerate(email_ids, 1):
						if progress_callback:
							progress = 0.1 + 0.8 * ((i + (idx / len(email_ids))) / len(folders))
							progress_callback(f"Przetwarzanie emaila {idx}/{len(email_ids)} w {folder_name}", "Wyszukiwanie załączników PDF...", progress)

						pdfs = self._process_email(email_id, save_dir, progress_callback)
						all_pdf_files.extend(pdfs)

				except Exception as e:
					if progress_callback:
						progress_callback(f"❌ Błąd podczas skanowania folderu {folder_name}", str(e), None)
					continue

			if progress_callback:
				progress_callback(f"✅ Pobrani {len(all_pdf_files)} załączników PDF", "Import zakończony", 1.0)
			return all_pdf_files

		except Exception as e:
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
							pdf_path = EmailService._save_attachment(
								payload_data,
								filename,
								save_dir,
								progress_callback
							)

							if pdf_path:
								pdf_files.append((filename, pdf_path))
								print(f"  📄 Pobrani: {filename}")
								if progress_callback:
									progress_callback(f"✅ Pobrani: {filename}", f"Rozmiar: {len(payload_data) / 1024:.1f} KB", None)

							# Clear payload reference to free memory
							del payload_data

		except Exception as e:
			print(f"Błąd podczas przetwarzania emaila {email_id}: {e}")
			if progress_callback:
				progress_callback(f"❌ Błąd podczas przetwarzania wiadomości", str(e), None)

		finally:
			# Clear message reference to ensure cleanup
			if message is not None:
				del message

		return pdf_files

	@staticmethod
	def _save_attachment(data: bytes, filename: str, save_dir: str = None, progress_callback: Optional[callable] = None) -> Optional[str]:
		"""
		Save attachment to file

		Returns:
			Path to saved file, or None if error
		"""
		pdf_path = None
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

			# Longer delay to ensure file handle is released on Windows
			time.sleep(0.3)

			# Verify file is accessible
			max_retries = 3
			for attempt in range(max_retries):
				try:
					with open(pdf_path, 'rb') as _:
						pass
					break
				except Exception:
					if attempt < max_retries - 1:
						if progress_callback:
							progress_callback(f"⚠️ Weryfikacja dostępu: {filename}", f"Próba {attempt + 1}/{max_retries}...", None)
						time.sleep(0.5)
					else:
						if progress_callback:
							progress_callback(f"❌ Plik zablokowany: {filename}", "Nie można uzyskać dostępu", None)
						raise

			return str(pdf_path)

		except Exception as e:
			print(f"Błąd podczas zapisywania załącznika: {e}")
			if progress_callback:
				progress_callback(f"❌ Błąd zapisu: {filename}", str(e), None)
			return None
