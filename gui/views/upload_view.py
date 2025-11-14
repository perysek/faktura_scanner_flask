"""
Widok uploadu i przetwarzania PDF
"""
import flet as ft
import os
from pathlib import Path
from typing import List, Optional
import shutil

from config.settings import TEMP_DIR
from repositories.invoice_repository import InvoiceRepository
from repositories.audit_repository import AuditRepository
from services.ocr_service import OCRService
from services.validation_service import ValidationService
from services.duplicate_detection_service import DuplicateDetectionService
from database.models import Invoice
from gui.theme import AppColors, AppIcons, AppSpacing, AppTypography, AppStyles
from gui.components.processing_results_table import ProcessingResultsTable


class UploadView(ft.Column):
	"""Widok uploadu PDF i przetwarzania"""

	def __init__(self, page: ft.Page, app, notification_panel=None):
		super().__init__()
		self.page = page
		self.app = app
		self.notification_panel = notification_panel
		
		# Services & Repositories
		self.invoice_repo = InvoiceRepository()
		self.audit_repo = AuditRepository()
		self.ocr_service = OCRService()
		self.validation_service = ValidationService()
		self.duplicate_service = DuplicateDetectionService(self.invoice_repo)
		
		# State
		self.selected_files: List[str] = []
		self.processed_invoices: List[
			tuple[Invoice, dict, str]] = []  # (invoice, validation, raw_text)
		self.is_processing = False

		# Reusable dialogs - create them first before build_ui
		self.ocr_dialog = ft.AlertDialog(
			modal=True,
			title=ft.Text("Surowy tekst OCR", weight=ft.FontWeight.BOLD),
			content=ft.Container(
				content=ft.Text(
					"",
					size=12,
					selectable=True,
				),
				width=600,
				height=400,
				padding=AppSpacing.MD,
				border=ft.border.all(1, AppColors.BORDER),
				border_radius=8,
			),
			actions=[
				ft.TextButton(
					"Zamknij",
					on_click=self.close_ocr_dialog
				)
			],
			actions_alignment=ft.MainAxisAlignment.END,
		)

		self.info_dialog = ft.AlertDialog(
			modal=True,
			title=ft.Text("", weight=ft.FontWeight.BOLD),
			content=ft.Text(""),
			actions=[
				ft.TextButton(
					"OK",
					on_click=self.close_info_dialog
				)
			],
			actions_alignment=ft.MainAxisAlignment.END,
		)

		# Add dialogs to page overlay
		self.page.overlay.extend([self.ocr_dialog, self.info_dialog])
		
		# Style
		self.spacing = AppSpacing.LG
		self.expand = True
		
		# UI
		self.build_ui()
	
	def build_ui(self):
		"""Zbuduj UI"""
		# Header
		header = ft.Row(
			controls=[
				ft.Text(
					"Import Faktur PDF",
					size=AppTypography.HEADLINE,
					weight=ft.FontWeight.BOLD,
					color=AppColors.TEXT_PRIMARY,
					),
				],
			)

		# File picker (hidden)
		self.file_picker = ft.FilePicker(on_result=self.on_files_selected)
		self.page.overlay.append(self.file_picker)

		# Progress controls (created before upload_area so they can be referenced)
		self.progress_counter = ft.Text(
			"Invoices processed: 0/0",
			size=13,
			weight=ft.FontWeight.BOLD,
			color=AppColors.PRIMARY,
			)

		self.progress_bar = ft.ProgressBar(
			value=0,
			width=300,
			height=8,
			color=AppColors.PRIMARY,
			bgcolor="white",
			)

		# Current file being processed
		self.progress_current_file = ft.Text(
			"",
			size=11,
			weight=ft.FontWeight.W_500,
			color=AppColors.TEXT_PRIMARY,
			max_lines=1,
			overflow=ft.TextOverflow.ELLIPSIS,
			)

		# Detailed status (e.g., "Konwersja PDF", "Ekstrakcja danych")
		self.progress_status = ft.Text(
			"",
			size=10,
			color=AppColors.TEXT_SECONDARY,
			italic=True,
			)

		self.progress_container = ft.Container(
			content=ft.Column(
				controls=[
					self.progress_counter,
					self.progress_bar,
					self.progress_current_file,
					self.progress_status,
				],
				spacing=4,
				tight=True,
			),
			visible=False,
			padding=ft.padding.all(AppSpacing.SM),
			bgcolor=AppColors.SURFACE_VARIANT,
			border_radius=6,
			width=320,
		)

		# Dropzone / Upload area (now progress_container exists)
		self.upload_area = self.create_upload_area()
		
		# Lista wybranych plików
		self.files_list_view = ft.Column(
			controls=[],
			spacing=AppSpacing.SM,
			scroll=ft.ScrollMode.AUTO,
			)
		
		self.files_container = ft.Container(
			content=self.files_list_view,
			visible=False,
			**AppStyles.card(),
			)
		
		# Przyciski akcji
		self.process_button = ft.ElevatedButton(
			"Przetwórz wszystkie",
			icon=AppIcons.CHECK,
			on_click=self.start_processing,
			disabled=True,
			**AppStyles.button_primary()
			)

		self.clear_button = ft.TextButton(
			"Wyczyść listę",
			icon=AppIcons.CANCEL,
			on_click=self.clear_files,
			disabled=True,
			)

		actions_row = ft.Row(
			controls=[
				self.process_button,
				self.clear_button,
				],
			spacing=AppSpacing.SM,
			)
		
		# Wyniki przetwarzania
		self.results_container = ft.Container(
			content=None,
			visible=False,
			expand=True,
			)
		
		# Dodaj do widoku
		self.controls = [
			header,
			ft.Divider(height=1, color=AppColors.DIVIDER),
			self.upload_area,
			self.files_container,
			actions_row,
			self.results_container,
			]
	
	def create_upload_area(self) -> ft.Container:
		"""Stwórz obszar uploadu"""
		# Use card styles but with custom padding
		card_styles = AppStyles.card()
		card_styles['padding'] = AppSpacing.XXL
		return ft.Container(
			content=ft.Column(
				controls=[
					ft.Icon(
						AppIcons.UPLOAD,
						size=64,
						color=AppColors.PRIMARY,
						),
					ft.Text(
						"Wybierz pliki PDF do przetworzenia",
						size=AppTypography.TITLE,
						weight=ft.FontWeight.W_500,
						color=AppColors.TEXT_PRIMARY,
						),
					ft.Text(
						"Możesz wybrać wiele plików naraz lub zaimportować z e-mail",
						size=AppTypography.BODY,
						color=AppColors.TEXT_SECONDARY,
						),
					ft.Container(height=AppSpacing.MD),
					ft.Row(
						controls=[
							ft.ElevatedButton(
								"Wybierz pliki PDF",
								icon=ft.Icons.FOLDER_OPEN,
								on_click=lambda _: self.file_picker.pick_files(
									allowed_extensions=["pdf"],
									allow_multiple=True,
									),
								**AppStyles.button_primary()
								),
							ft.ElevatedButton(
								"Import from E-mail",
								icon=ft.Icons.EMAIL,
								on_click=self.import_from_email,
								**AppStyles.button_secondary()
								),
							ft.Container(width=AppSpacing.LG),
							# Progress controls on the right
							self.progress_container,
							],
						spacing=AppSpacing.SM,
						alignment=ft.MainAxisAlignment.CENTER,
						wrap=False,
						),
					],
				horizontal_alignment=ft.CrossAxisAlignment.CENTER,
				spacing=AppSpacing.SM,
				),
			**card_styles,
			alignment=ft.alignment.center,
			)
	
	def on_files_selected(self, e: ft.FilePickerResultEvent):
		"""Obsługa wybranych plików"""
		if not e.files:
			return

		# Dodaj pliki do listy
		for file in e.files:
			# Skip files without path (happens in web browser mode)
			if file.path and file.path not in self.selected_files:
				self.selected_files.append(file.path)

		# If no valid files were added, show error
		if not self.selected_files:
			self.show_error(
				"Błąd wyboru plików",
				"Nie można uzyskać dostępu do plików. Aplikacja powinna działać w trybie desktop."
			)
			return

		self.update_files_list()

		# Pokaż listę i przyciski
		self.files_container.visible = True
		self.process_button.disabled = False
		self.clear_button.disabled = False

		self.page.update()
	
	def update_files_list(self):
		"""Zaktualizuj listę wybranych plików"""
		self.files_list_view.controls.clear()
		
		if not self.selected_files:
			return
		
		# Header
		self.files_list_view.controls.append(
			ft.Text(
				f"Wybrane pliki ({len(self.selected_files)}):",
				size=AppTypography.BODY,
				weight=ft.FontWeight.BOLD,
				)
			)
		
		# Lista plików
		for i, file_path in enumerate(self.selected_files, 1):
			# Skip None paths (shouldn't happen with the fix above, but just in case)
			if not file_path:
				continue

			filename = Path(file_path).name
			file_size = Path(file_path).stat().st_size / 1024  # KB
			
			file_row = ft.Container(
				content=ft.Row(
					controls=[
						ft.Icon(AppIcons.PDF, size=24, color=AppColors.ERROR),
						ft.Column(
							controls=[
								ft.Text(
									filename, size=14,
									weight=ft.FontWeight.W_500
									),
								ft.Text(
									f"{file_size:.1f} KB",
									size=12,
									color=AppColors.TEXT_SECONDARY
									),
								],
							spacing=2,
							expand=True,
							),
						ft.IconButton(
							icon=AppIcons.DELETE,
							icon_size=20,
							icon_color=AppColors.ERROR,
							tooltip="Usuń",
							on_click=lambda e, idx=i - 1: self.remove_file(idx),
							),
						],
					alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
					),
				bgcolor=AppColors.SURFACE_VARIANT,
				border_radius=8,
				padding=AppSpacing.SM,
				)
			
			self.files_list_view.controls.append(file_row)
	
	def remove_file(self, index: int):
		"""Usuń plik z listy"""
		if 0 <= index < len(self.selected_files):
			self.selected_files.pop(index)
			self.update_files_list()
			
			if not self.selected_files:
				self.files_container.visible = False
				self.process_button.disabled = True
				self.clear_button.disabled = True
			
			self.page.update()
	
	def clear_files(self, e):
		"""Wyczyść listę plików"""
		self.selected_files.clear()
		self.files_container.visible = False
		self.process_button.disabled = True
		self.clear_button.disabled = True
		self.page.update()

	def import_from_email(self, e):
		"""Import PDFs from email"""
		try:
			# Import services
			from services.email_service import EmailService
			from config.email_settings import EmailSettings

			# Load email settings
			email_settings = EmailSettings()
			settings = email_settings.get_settings()

			# Validate settings
			if not settings.get('email_address') or not settings.get('password'):
				self.show_error(
					"Email Not Configured",
					"Please configure email settings first in E-mail Settings view"
				)
				return

			# Show progress
			self.progress_container.visible = True
			self.progress_counter.value = "Import z e-mail"
			self.progress_bar.value = 0
			self.progress_current_file.value = "Łączenie z serwerem email..."
			self.progress_status.value = "Proszę czekać..."
			self.page.update()

			# Connect to email
			email_service = EmailService()

			if not email_service.connect(
				settings['email_address'],
				settings['password'],
				settings['imap_server'],
				settings['imap_port']
			):
				self.progress_container.visible = False
				self.page.update()
				self.show_error("Connection Failed", "Could not connect to email server")
				return

			# Parse dates
			from_date = None
			to_date = None

			if settings.get('search_from_date'):
				try:
					from datetime import datetime
					from_date = datetime.strptime(
						settings['search_from_date'], '%Y-%m-%d'
					).date()
				except:
					pass

			if settings.get('search_to_date'):
				try:
					from datetime import datetime
					to_date = datetime.strptime(
						settings['search_to_date'], '%Y-%m-%d'
					).date()
				except:
					pass

			# Update progress
			self.progress_counter.value = "Import z e-mail"
			self.progress_bar.value = 0.5
			self.progress_current_file.value = "Wyszukiwanie PDF w wiadomościach..."
			self.progress_status.value = f"Zakres dat: {settings.get('search_from_date', 'brak')} - {settings.get('search_to_date', 'brak')}"
			self.page.update()

			# Define progress callback
			def email_progress_callback(current_file: str, status: str, progress: float = None):
				"""Update progress UI during email import"""
				self.progress_current_file.value = current_file
				self.progress_status.value = status
				if progress is not None:
					self.progress_bar.value = progress
				self.page.update()

			# Fetch PDFs
			pdf_files = email_service.fetch_pdf_attachments(
				from_date=from_date,
				to_date=to_date,
				progress_callback=email_progress_callback
			)

			# Disconnect
			email_service.disconnect()

			# Update progress
			self.progress_counter.value = "Import z e-mail"
			self.progress_bar.value = 1.0
			self.progress_current_file.value = f"✅ Znaleziono {len(pdf_files)} plików PDF"
			self.progress_status.value = "Import zakończony pomyślnie!"
			self.page.update()

			# Hide progress after a moment
			import time
			time.sleep(1)
			self.progress_container.visible = False
			self.page.update()

			if not pdf_files:
				self.show_info(
					"No PDFs Found",
					"No PDF attachments found in the specified date range"
				)
				return

			# Add PDFs to selected files list
			for filename, pdf_path in pdf_files:
				if pdf_path not in self.selected_files:
					self.selected_files.append(pdf_path)

			self.update_files_list()

			# Show list and enable buttons
			self.files_container.visible = True
			self.process_button.disabled = False
			self.clear_button.disabled = False
			self.page.update()

			self.show_success(
				"Import Successful",
				f"Imported {len(pdf_files)} PDF files from email"
			)

		except Exception as ex:
			self.progress_container.visible = False
			self.page.update()
			self.show_error("Import Error", str(ex))
			import traceback
			traceback.print_exc()

	def start_processing(self, e):
		"""Rozpocznij przetwarzanie (Wariant A - Sequential)"""
		if self.is_processing or not self.selected_files:
			return

		self.is_processing = True
		self.process_button.disabled = True

		# Pokaż progress controls
		self.progress_container.visible = True
		self.progress_counter.value = f"Invoices processed: 0/{len(self.selected_files)}"
		self.progress_bar.value = 0
		self.progress_current_file.value = ""
		self.progress_status.value = "Inicjalizacja..."
		self.page.update()

		# Przetwórz pliki sekwencyjnie
		self.processed_invoices.clear()

		for i, file_path in enumerate(self.selected_files, 1):
			filename = Path(file_path).name

			try:
				# Update progress counter and current file
				self.progress_counter.value = f"Invoices processed: {i-1}/{len(self.selected_files)}"
				self.progress_bar.value = (i - 1) / len(self.selected_files)
				self.progress_current_file.value = f"📄 {filename}"
				self.progress_status.value = "Konwersja PDF..."
				self.page.update()

				# Check if file is already in TEMP_DIR (from email import)
				file_path_obj = Path(file_path)
				temp_pdf_path = TEMP_DIR / filename

				if file_path_obj.parent == TEMP_DIR:
					# File is already in TEMP_DIR, use it directly
					temp_pdf_path = file_path_obj
					print(f"  File already in temp dir: {filename}")
				else:
					# Copy to temp (to preserve original)
					shutil.copy2(file_path, temp_pdf_path)
					print(f"  Copied to temp: {filename}")

				# OCR + Ekstrakcja
				self.progress_status.value = "Ekstrakcja danych (OCR)..."
				self.page.update()

				invoice, raw_text = self.ocr_service.process_invoice_pdf(
					str(temp_pdf_path),
					progress_callback=None  # Internal progress nie potrzebny
					)

				# Ustawienie ścieżki PDF
				invoice.pdf_path = str(temp_pdf_path)

				# Walidacja
				self.progress_status.value = "Walidacja i sprawdzanie duplikatów..."
				self.page.update()
				
				validation = self.validation_service.validate_invoice(invoice)

				# Sprawdź duplikaty
				duplicate_id = self.duplicate_service.check_duplicate(invoice)
				if duplicate_id:
					invoice.is_duplicate = True
					validation['warnings'].insert(
						0, f"⚠️ Możliwy duplikat faktury (ID: {duplicate_id})"
						)

				# Update completion for this file
				self.progress_status.value = f"✓ Zakończono ({invoice.seller_name})"
				self.page.update()

				# Zapisz wyniki
				self.processed_invoices.append((invoice, validation, raw_text))
			
			except Exception as ex:
				# Błąd przetwarzania
				self.progress_status.value = f"❌ Błąd: {str(ex)[:50]}..."
				self.page.update()

				error_invoice = Invoice(
					seller_name=f"BŁĄD: {filename}",
					invoice_number="ERROR",
					invoice_date=None,
					amount=0,
					)
				validation = {
					'errors': [f"Błąd przetwarzania: {str(ex)}"],
					'warnings': []
					}
				self.processed_invoices.append((error_invoice, validation, ""))

		# Zakończono
		self.progress_counter.value = f"Invoices processed: {len(self.selected_files)}/{len(self.selected_files)}"
		self.progress_bar.value = 1.0
		self.progress_current_file.value = f"✅ Przetworzono {len(self.selected_files)} faktur"
		self.progress_status.value = "Zakończono! Sprawdź wyniki poniżej."
		self.progress_counter.color = AppColors.SUCCESS
		self.progress_current_file.color = AppColors.SUCCESS
		self.progress_status.color = AppColors.SUCCESS
		self.page.update()

		self.is_processing = False

		# Don't hide progress controls - they will be shown in results header
		# Pokaż wyniki
		self.show_results()
	
	def show_results(self):
		"""Pokaż wyniki przetwarzania w kompaktowej tabeli"""
		# Calculate statistics
		total_count = len(self.processed_invoices)
		error_count = sum(1 for _, val, _ in self.processed_invoices if len(val['errors']) > 0)
		warning_count = sum(1 for _, val, _ in self.processed_invoices if len(val['warnings']) > 0 and len(val['errors']) == 0)
		ok_count = total_count - error_count - warning_count

		# Summary statistics row
		stats_row = ft.Row(
			controls=[
				ft.Container(
					content=ft.Row(
						controls=[
							ft.Icon(AppIcons.CHECK, size=16, color="white" if ok_count > 0 else AppColors.SUCCESS),
							ft.Text(
								f"OK: {ok_count}",
								size=11,
								weight=ft.FontWeight.W_500,
								color="white" if ok_count > 0 else AppColors.TEXT_PRIMARY,
							),
						],
						spacing=4,
						tight=True,
					),
					bgcolor=AppColors.SUCCESS if ok_count > 0 else AppColors.SURFACE_VARIANT,
					padding=ft.padding.symmetric(horizontal=8, vertical=4),
					border_radius=4,
				),
				ft.Container(
					content=ft.Row(
						controls=[
							ft.Icon(AppIcons.WARNING, size=16, color="white" if warning_count > 0 else AppColors.WARNING),
							ft.Text(
								f"Ostrzeżenia: {warning_count}",
								size=11,
								weight=ft.FontWeight.W_500,
								color="white" if warning_count > 0 else AppColors.TEXT_PRIMARY,
							),
						],
						spacing=4,
						tight=True,
					),
					bgcolor=AppColors.WARNING if warning_count > 0 else AppColors.SURFACE_VARIANT,
					padding=ft.padding.symmetric(horizontal=8, vertical=4),
					border_radius=4,
				),
				ft.Container(
					content=ft.Row(
						controls=[
							ft.Icon(AppIcons.ERROR, size=16, color="white" if error_count > 0 else AppColors.ERROR),
							ft.Text(
								f"Błędy: {error_count}",
								size=11,
								weight=ft.FontWeight.W_500,
								color="white" if error_count > 0 else AppColors.TEXT_PRIMARY,
							),
						],
						spacing=4,
						tight=True,
					),
					bgcolor=AppColors.ERROR if error_count > 0 else AppColors.SURFACE_VARIANT,
					padding=ft.padding.symmetric(horizontal=8, vertical=4),
					border_radius=4,
				),
			],
			spacing=AppSpacing.SM,
		)

		# Header with stats and save all button
		header_section = ft.Column(
			controls=[
				# Title and stats row
				ft.Row(
					controls=[
						ft.Text(
							f"Wyniki przetwarzania ({total_count} faktur)",
							size=AppTypography.TITLE,
							weight=ft.FontWeight.BOLD,
							color=AppColors.TEXT_PRIMARY,
						),
						ft.Container(expand=True),
						stats_row,
						ft.ElevatedButton(
							f"Zapisz wszystkie ({ok_count + warning_count})",
							icon=AppIcons.SAVE,
							on_click=self.save_all_invoices,
							disabled=ok_count + warning_count == 0,
							**AppStyles.button_primary()
						),
					],
					spacing=AppSpacing.SM,
					alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
				),
				ft.Divider(height=1, color=AppColors.DIVIDER),
			],
			spacing=AppSpacing.SM,
		)

		# Create compact results table
		results_table = ProcessingResultsTable(
			processed_invoices=self.processed_invoices,
			on_delete=self.remove_processed_invoice,
			on_save=self.save_single_invoice,
			on_view_ocr=self.show_ocr_text,
		)

		# Wrap table in scrollable container
		table_container = ft.ListView(
			controls=[results_table],
			expand=True,
			spacing=0,
			padding=AppSpacing.SM,
		)

		# Combine header and table
		results_content = ft.Column(
			controls=[
				header_section,
				table_container,
			],
			spacing=0,
			expand=True,
		)

		self.results_container.content = results_content
		self.results_container.visible = True
		self.results_container.expand = True

		# Ukryj upload area
		self.upload_area.visible = False
		self.files_container.visible = False

		self.page.update()
	
	def remove_processed_invoice(self, index: int):
		"""Usuń fakturę z listy przetworzonych"""
		if 0 <= index < len(self.processed_invoices):
			self.processed_invoices.pop(index)

			# Odśwież widok
			if not self.processed_invoices:
				# Wszystkie usunięte - wróć do głównego widoku
				self.results_container.visible = False
				self.upload_area.visible = True
				self.page.update()
			else:
				self.show_results()
	
	def show_ocr_text(self, text: str):
		"""Pokaż surowy tekst OCR"""
		# Update content with current text
		self.ocr_dialog.content.content = ft.Text(
			text,
			size=12,
			selectable=True,
		)

		# Open dialog
		self.ocr_dialog.open = True
		self.page.update()

	def close_ocr_dialog(self, e):
		"""Close OCR dialog"""
		self.ocr_dialog.open = False
		self.page.update()
	
	def save_single_invoice(self, index: int):
		"""Zapisz pojedynczą fakturę"""
		if 0 <= index < len(self.processed_invoices):
			invoice, validation, _ = self.processed_invoices[index]

			try:
				invoice_id = self.invoice_repo.create(invoice)
				self.show_success(
					"Zapisano",
					f"Faktura {invoice.invoice_number} zapisana (ID: {invoice_id})"
				)

				# Usuń z listy
				self.processed_invoices.pop(index)

				# Odśwież widok
				if not self.processed_invoices:
					# Wszystkie zapisane - wróć do głównego widoku
					self.app.refresh_main_view()
				else:
					# Odśwież tabelę wyników
					self.show_results()

			except Exception as ex:
				error_msg = str(ex)
				# Check for duplicate invoice
				if "UNIQUE constraint failed" in error_msg and "invoice_number" in error_msg:
					self.show_error(
						"Duplikat faktury",
						f"Faktura {invoice.invoice_number} już istnieje w bazie danych. "
						f"Pomiń lub usuń poprzednią wersję przed zapisaniem."
					)
				else:
					self.show_error("Błąd zapisu", error_msg)
	
	def save_all_invoices(self, e):
		"""Zapisz wszystkie faktury bez błędów"""
		saved_count = 0
		error_count = 0
		duplicate_count = 0

		# Create a copy of the list to iterate over
		invoices_to_save = [(i, inv, val, raw) for i, (inv, val, raw) in enumerate(self.processed_invoices) if len(val['errors']) == 0]

		for index, invoice, validation, _ in invoices_to_save:
			try:
				self.invoice_repo.create(invoice)
				saved_count += 1
			except Exception as ex:
				error_msg = str(ex)
				if "UNIQUE constraint failed" in error_msg and "invoice_number" in error_msg:
					duplicate_count += 1
					print(f"Pominięto duplikat: {invoice.invoice_number}")
				else:
					error_count += 1
					print(f"Błąd zapisu faktury {invoice.invoice_number}: {ex}")
		
		# Show results
		messages = []
		if saved_count > 0:
			messages.append(f"Zapisano: {saved_count}")
		if duplicate_count > 0:
			messages.append(f"Pominięto duplikaty: {duplicate_count}")
		if error_count > 0:
			messages.append(f"Błędy: {error_count}")

		if messages:
			if error_count > 0:
				self.show_error("Wyniki zapisu", " | ".join(messages))
			else:
				self.show_success("Wyniki zapisu", " | ".join(messages))

		# Wróć do głównego widoku
		self.app.refresh_main_view()
	
	def show_success(self, title: str, message: str):
		"""Pokaż sukces"""
		if self.notification_panel:
			self.notification_panel.add_notification(
				f"{title}: {message}",
				"success"
			)

	def show_error(self, title: str, message: str):
		"""Pokaż błąd"""
		if self.notification_panel:
			self.notification_panel.add_notification(
				f"{title}: {message}",
				"error"
			)
	
	def show_info(self, title: str, message: str):
		"""Pokaż info"""
		# Update dialog content
		self.info_dialog.title = ft.Text(title, weight=ft.FontWeight.BOLD)
		self.info_dialog.content = ft.Text(message)

		# Open dialog
		self.info_dialog.open = True
		self.page.update()

	def close_info_dialog(self, e):
		"""Close info dialog"""
		self.info_dialog.open = False
		self.page.update()