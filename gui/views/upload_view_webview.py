"""
Widok uploadu i przetwarzania PDF - wersja webview
Handles file uploads for webview mode using FilePicker upload functionality
"""
import flet as ft
from pathlib import Path
from typing import List
import shutil

from config.settings import TEMP_DIR
from config.webview_settings import WEBVIEW_UPLOAD_DIR
from repositories.invoice_repository import InvoiceRepository
from repositories.audit_repository import AuditRepository
from services.ocr_service import OCRService
from services.validation_service import ValidationService
from services.duplicate_detection_service import DuplicateDetectionService
from database.models import Invoice
from gui.theme import AppColors, AppIcons, AppSpacing, AppTypography, AppStyles
from gui.components.processing_results_table import ProcessingResultsTable


class UploadViewWebview(ft.Column):
	"""Widok uploadu PDF i przetwarzania - wersja webview"""

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
		self.selected_files: List[str] = []  # Will store uploaded file paths
		self.processed_invoices: List[
			tuple[Invoice, dict, str]] = []  # (invoice, validation, raw_text)
		self.is_processing = False
		self.cancel_requested = False  # Flag for cancelling processing
		self.pending_uploads = 0  # Track pending uploads

		# Reusable dialogs
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
					"Import Faktur PDF (Webview Mode)",
					size=AppTypography.HEADLINE,
					weight=ft.FontWeight.BOLD,
					color=AppColors.TEXT_PRIMARY,
				),
			],
		)

		# File picker with upload support for webview
		# CRITICAL: FilePicker must be added to page.overlay for webview mode
		self.file_picker = ft.FilePicker(
			on_result=self.on_files_selected,
			on_upload=self.on_upload_progress,
		)
		self.page.overlay.append(self.file_picker)

		# Progress controls
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

		# Detailed status
		self.progress_status = ft.Text(
			"",
			size=10,
			color=AppColors.TEXT_SECONDARY,
			italic=True,
		)

		# Upload progress indicator
		self.upload_progress = ft.Text(
			"",
			size=10,
			color=AppColors.PRIMARY,
			italic=True,
		)

		# Cancel button
		self.cancel_button = ft.TextButton(
			"Anuluj",
			icon=ft.Icons.CANCEL,
			on_click=self.cancel_processing,
			style=ft.ButtonStyle(color=AppColors.ERROR),
		)

		self.progress_container = ft.Container(
			content=ft.Column(
				controls=[
					self.progress_counter,
					self.progress_bar,
					self.progress_current_file,
					self.progress_status,
					self.upload_progress,
					self.cancel_button,
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

		# Upload area
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
						"Webview mode: pliki zostaną przesłane na serwer lub pobrane z e-mail",
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
							self.progress_container,
						],
						alignment=ft.MainAxisAlignment.CENTER,
						spacing=AppSpacing.SM,
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
		"""Obsługa wybranych plików - webview mode requires upload"""
		if not e.files:
			return

		# In webview mode, we need to upload files to the server
		# Show upload progress
		self.upload_progress.value = "Przesyłanie plików na serwer..."
		self.progress_container.visible = True
		self.page.update()

		# Track number of files to upload
		self.pending_uploads = len(e.files)

		# Upload each file
		upload_list = []
		for file in e.files:
			# Create unique filename to avoid conflicts
			upload_list.append(
				ft.FilePickerUploadFile(
					file.name,
					upload_url=self.page.get_upload_url(file.name, 600)  # 600s timeout
				)
			)

		# Start upload
		self.file_picker.upload(upload_list)

	def on_upload_progress(self, e: ft.FilePickerUploadEvent):
		"""Handle upload progress in webview mode"""
		if e.progress == 1.0:
			# File upload complete
			self.pending_uploads -= 1

			# Get uploaded file path
			uploaded_file_path = Path(WEBVIEW_UPLOAD_DIR) / e.file_name

			# Copy to temp directory for processing
			temp_file_path = Path(TEMP_DIR) / e.file_name
			try:
				shutil.copy2(uploaded_file_path, temp_file_path)
				self.selected_files.append(str(temp_file_path))
			except Exception as ex:
				self.show_error(
					"Błąd kopiowania pliku",
					f"Nie można skopiować {e.file_name}: {str(ex)}"
				)

			# Update progress
			self.upload_progress.value = f"Przesłano: {len(self.selected_files)} plików"

			# If all files uploaded
			if self.pending_uploads == 0:
				self.upload_progress.value = f"✅ Przesłano {len(self.selected_files)} plików"
				self.update_files_list()

				# Show file list and enable buttons
				self.files_container.visible = True
				self.process_button.disabled = False
				self.clear_button.disabled = False

			self.page.update()
		elif e.error:
			# Upload error
			self.show_error(
				"Błąd przesyłania",
				f"Nie można przesłać pliku {e.file_name}: {e.error}"
			)
			self.pending_uploads -= 1
			self.page.update()

	def update_files_list(self):
		"""Zaktualizuj listę wybranych plików"""
		self.files_list_view.controls.clear()

		if not self.selected_files:
			return

		# Header
		self.files_list_view.controls.append(
			ft.Text(
				f"Przesłane pliki ({len(self.selected_files)}):",
				size=AppTypography.BODY,
				weight=ft.FontWeight.BOLD,
			)
		)

		# Lista plików
		for i, file_path in enumerate(self.selected_files, 1):
			if not file_path:
				continue

			filename = Path(file_path).name
			try:
				file_size = Path(file_path).stat().st_size / 1024  # KB
			except:
				file_size = 0

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

			if len(self.selected_files) == 0:
				self.files_container.visible = False
				self.process_button.disabled = True
				self.clear_button.disabled = True

			self.page.update()

	def clear_files(self, _e):
		"""Wyczyść całą listę"""
		self.selected_files.clear()
		self.files_container.visible = False
		self.process_button.disabled = True
		self.clear_button.disabled = True
		self.page.update()

	def start_processing(self, _e):
		"""Start processing all selected PDFs sequentially"""
		if not self.selected_files or self.is_processing:
			return

		self.is_processing = True
		self.cancel_requested = False  # Reset cancel flag
		self.processed_invoices.clear()

		# Disable buttons during processing
		self.process_button.disabled = True
		self.clear_button.disabled = True

		# Show progress
		self.progress_container.visible = True
		self.progress_bar.value = 0
		total_files = len(self.selected_files)
		self.progress_counter.value = f"Invoices processed: 0/{total_files}"
		self.progress_current_file.value = ""
		self.progress_status.value = ""
		self.page.update()

		# Process each file
		for i, file_path in enumerate(self.selected_files, 1):
			# Check if cancellation was requested
			if self.cancel_requested:
				self.progress_status.value = "❌ Anulowano przez użytkownika"
				self.progress_current_file.value = f"Przetworzono {i-1} z {total_files} plików"
				self.page.update()
				break

			# Update progress
			filename = Path(file_path).name
			self.progress_current_file.value = f"📄 {filename}"
			self.progress_status.value = "Rozpoczynam przetwarzanie..."
			self.page.update()

			try:
				# Process single file
				self.process_single_file(file_path, i, total_files)
			except Exception as ex:
				print(f"❌ Error processing {filename}: {ex}")
				# Continue with next file even if one fails

		# Processing complete
		self.is_processing = False
		self.progress_container.visible = False

		# Show results
		self.show_processing_results()

		# Re-enable clear button
		self.clear_button.disabled = False
		self.page.update()

	def process_single_file(self, file_path: str, current: int, total: int):
		"""Process a single PDF file"""
		filename = Path(file_path).name

		# Update status
		self.progress_status.value = "Ekstrakcja danych (OCR)..."
		self.page.update()

		# OCR processing - returns (Invoice, raw_text) tuple
		invoice, raw_text = self.ocr_service.process_invoice_pdf(
			file_path,
			progress_callback=None
		)

		# Set PDF path
		invoice.pdf_path = file_path

		# Update status
		self.progress_status.value = "Walidacja i sprawdzanie duplikatów..."
		self.page.update()

		# Validation
		validation_result = self.validation_service.validate_invoice(invoice)

		# Duplicate check
		is_duplicate = self.duplicate_service.check_duplicate(invoice)
		if is_duplicate:
			validation_result['warnings'].append("Faktura o tym numerze już istnieje w bazie")

		# Store result
		self.processed_invoices.append((invoice, validation_result, raw_text))

		# Update progress
		self.progress_bar.value = current / total
		self.progress_counter.value = f"Invoices processed: {current}/{total}"
		self.progress_status.value = "✅ Zakończono"
		self.page.update()

	def show_processing_results(self):
		"""Display processing results table"""
		if not self.processed_invoices:
			self.show_error("Brak wyników", "Nie przetworzono żadnych faktur.")
			return

		# Create results table
		results_table = ProcessingResultsTable(
			processed_invoices=self.processed_invoices,
			on_delete=self.delete_processed_invoice,
			on_save=self.save_invoice,
			on_view_ocr=self.view_ocr_text,
		)

		# Action buttons
		save_all_button = ft.ElevatedButton(
			"Zapisz wszystkie poprawne",
			icon=ft.Icons.SAVE_ALT,
			on_click=self.save_all_valid,
			**AppStyles.button_primary()
		)

		# Results container
		self.results_container.content = ft.Column(
			controls=[
				ft.Text(
					"Wyniki przetwarzania",
					size=AppTypography.TITLE,
					weight=ft.FontWeight.BOLD,
				),
				results_table,
				ft.Container(height=AppSpacing.MD),
				save_all_button,
			],
			spacing=AppSpacing.MD,
		)
		self.results_container.visible = True
		self.page.update()

	def delete_processed_invoice(self, index: int):
		"""Delete invoice from processing results"""
		if 0 <= index < len(self.processed_invoices):
			self.processed_invoices.pop(index)
			self.show_processing_results()  # Refresh display
			if self.notification_panel:
				self.notification_panel.add_notification(
					"Usunięto fakturę z wyników",
					"info"
				)

	def save_invoice(self, index: int):
		"""Save single invoice to database"""
		if 0 <= index < len(self.processed_invoices):
			invoice, validation, _ = self.processed_invoices[index]

			# Check for errors
			if validation['errors']:
				self.show_error(
					"Błędy walidacji",
					"Nie można zapisać faktury z błędami:\n" + "\n".join(validation['errors'])
				)
				return

			try:
				# Save to database
				self.invoice_repo.create(invoice)

				# Remove from processing list
				self.processed_invoices.pop(index)

				# Refresh display
				self.show_processing_results()

				if self.notification_panel:
					self.notification_panel.add_notification(
						f"Zapisano fakturę {invoice.invoice_number}",
						"success"
					)
			except Exception as ex:
				self.show_error("Błąd zapisu", f"Nie można zapisać faktury: {str(ex)}")

	def save_all_valid(self, _e):
		"""Save all valid invoices (no errors)"""
		saved_count = 0
		errors_count = 0

		# Process in reverse to avoid index issues when removing
		for i in range(len(self.processed_invoices) - 1, -1, -1):
			invoice, validation, _ = self.processed_invoices[i]

			if not validation['errors']:
				try:
					self.invoice_repo.create(invoice)
					self.processed_invoices.pop(i)
					saved_count += 1
				except Exception as ex:
					print(f"Error saving invoice: {ex}")
					errors_count += 1

		# Refresh display
		self.show_processing_results()

		# Show notification
		if self.notification_panel:
			if saved_count > 0:
				self.notification_panel.add_notification(
					f"Zapisano {saved_count} faktur(y)",
					"success"
				)
			if errors_count > 0:
				self.notification_panel.add_notification(
					f"Błąd zapisu {errors_count} faktur(y)",
					"error"
				)

	def view_ocr_text(self, text: str):
		"""View raw OCR text"""
		# Update dialog content
		self.ocr_dialog.content.content.value = text or "Brak tekstu OCR"

		# Show dialog
		self.page.dialog = self.ocr_dialog
		self.ocr_dialog.open = True
		self.page.update()

	def close_ocr_dialog(self, _e):
		"""Close OCR dialog"""
		self.ocr_dialog.open = False
		self.page.update()

	def show_error(self, title: str, message: str):
		"""Show error dialog"""
		self.info_dialog.title.value = title
		self.info_dialog.content.value = message
		self.page.dialog = self.info_dialog
		self.info_dialog.open = True
		self.page.update()

	def close_info_dialog(self, _e):
		"""Close info dialog"""
		self.info_dialog.open = False
		self.page.update()

	def import_from_email(self, _e):
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

			# Show notification
			if self.notification_panel:
				self.notification_panel.add_notification(
					f"Zaimportowano {len(pdf_files)} plików PDF z e-mail",
					"success"
				)

		except Exception as ex:
			self.progress_container.visible = False
			self.page.update()
			self.show_error("Import Error", f"Error importing from email: {str(ex)}")
			print(f"❌ Email import error: {ex}")

	def show_info(self, title: str, message: str):
		"""Pokaż info"""
		# Update dialog content
		self.info_dialog.title.value = title
		self.info_dialog.content.value = message

		# Open dialog
		self.page.dialog = self.info_dialog
		self.info_dialog.open = True
		self.page.update()

	def cancel_processing(self, _e):
		"""Cancel ongoing processing"""
		if self.is_processing:
			self.cancel_requested = True
			self.progress_status.value = "Anulowanie..."
			self.page.update()
