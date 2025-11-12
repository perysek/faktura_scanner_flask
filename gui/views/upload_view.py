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
from gui.components.progress_dialog import ProgressDialog


class UploadView(ft.Column):
	"""Widok uploadu PDF i przetwarzania"""
	
	def __init__(self, page: ft.Page, app):
		super().__init__()
		self.page = page
		self.app = app
		
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
		
		# Dropzone / Upload area
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
						"Możesz wybrać wiele plików naraz",
						size=AppTypography.BODY,
						color=AppColors.TEXT_SECONDARY,
						),
					ft.Container(height=AppSpacing.MD),
					ft.ElevatedButton(
						"Wybierz pliki PDF",
						icon=ft.Icons.FOLDER_OPEN,
						on_click=lambda _: self.file_picker.pick_files(
							allowed_extensions=["pdf"],
							allow_multiple=True,
							),
						**AppStyles.button_primary()
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
	
	def start_processing(self, e):
		"""Rozpocznij przetwarzanie (Wariant A - Sequential)"""
		if self.is_processing or not self.selected_files:
			return
		
		self.is_processing = True
		self.process_button.disabled = True
		
		# Pokaż progress dialog
		progress_dialog = ProgressDialog()
		self.page.dialog = progress_dialog
		progress_dialog.open = True
		self.page.update()
		
		# Przetwórz pliki sekwencyjnie
		self.processed_invoices.clear()
		
		for i, file_path in enumerate(self.selected_files, 1):
			filename = Path(file_path).name
			
			try:
				# Update progress: Konwersja PDF
				progress_dialog.update_progress(
					current=i,
					total=len(self.selected_files),
					filename=filename,
					status="Konwersja PDF..."
					)
				
				# Skopiuj do temp (aby zachować oryginał)
				temp_pdf_path = TEMP_DIR / filename
				shutil.copy2(file_path, temp_pdf_path)
				
				# OCR + Ekstrakcja
				progress_dialog.update_progress(
					current=i,
					total=len(self.selected_files),
					filename=filename,
					status="Ekstrakcja danych..."
					)
				
				invoice, raw_text = self.ocr_service.process_invoice_pdf(
					str(temp_pdf_path),
					progress_callback=None  # Internal progress nie potrzebny
					)
				
				# Ustawienie ścieżki PDF
				invoice.pdf_path = str(temp_pdf_path)
				
				# Walidacja
				progress_dialog.update_progress(
					current=i,
					total=len(self.selected_files),
					filename=filename,
					status="Walidacja danych..."
					)
				
				validation = self.validation_service.validate_invoice(invoice)
				
				# Sprawdź duplikaty
				duplicate_id = self.duplicate_service.check_duplicate(invoice)
				if duplicate_id:
					invoice.is_duplicate = True
					validation['warnings'].insert(
						0, f"⚠️ Możliwy duplikat faktury (ID: {duplicate_id})"
						)
				
				# Zapisz wyniki
				self.processed_invoices.append((invoice, validation, raw_text))
			
			except Exception as ex:
				# Błąd przetwarzania
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
		progress_dialog.set_complete()
		self.is_processing = False
		
		# Zamknij dialog po 1 sekundzie
		import time
		time.sleep(1)
		progress_dialog.open = False
		self.page.update()
		
		# Pokaż wyniki
		self.show_results()
	
	def show_results(self):
		"""Pokaż wyniki przetwarzania"""
		results_column = ft.Column(
			controls=[],
			spacing=AppSpacing.MD,
			scroll=ft.ScrollMode.AUTO,
			)
		
		# Header
		results_column.controls.append(
			ft.Row(
				controls=[
					ft.Text(
						"Wyniki przetwarzania",
						size=AppTypography.TITLE,
						weight=ft.FontWeight.BOLD,
						),
					ft.Container(expand=True),
					ft.ElevatedButton(
						"Zapisz wszystkie",
						icon=AppIcons.SAVE,
						on_click=self.save_all_invoices,
						**AppStyles.button_primary()
						),
					],
				)
			)
		
		# Karty wyników
		for i, (invoice, validation, raw_text) in enumerate(
				self.processed_invoices
				):
			card = self.create_result_card(i, invoice, validation, raw_text)
			results_column.controls.append(card)
		
		self.results_container.content = results_column
		self.results_container.visible = True
		
		# Ukryj upload area
		self.upload_area.visible = False
		self.files_container.visible = False
		
		self.page.update()
	
	def create_result_card(
			self, index: int, invoice: Invoice, validation: dict, raw_text: str
			) -> ft.Container:
		"""Stwórz kartę wyniku dla faktury"""
		# Status color
		has_errors = len(validation['errors']) > 0
		status_color = AppColors.ERROR if has_errors else (
			AppColors.WARNING if len(
				validation['warnings']
				) > 0 else AppColors.SUCCESS
		)
		
		# Status icon
		status_icon = AppIcons.ERROR if has_errors else (
			AppIcons.WARNING if len(
				validation['warnings']
				) > 0 else AppIcons.CHECK
		)
		
		# Validation messages
		messages = []
		
		for error in validation['errors']:
			messages.append(
				ft.Row(
					controls=[
						ft.Icon(AppIcons.ERROR, size=16, color=AppColors.ERROR),
						ft.Text(error, size=12, color=AppColors.ERROR),
						],
					spacing=AppSpacing.XS,
					)
				)
		
		for warning in validation['warnings']:
			messages.append(
				ft.Row(
					controls=[
						ft.Icon(
							AppIcons.WARNING, size=16, color=AppColors.WARNING
							),
						ft.Text(warning, size=12, color=AppColors.WARNING),
						],
					spacing=AppSpacing.XS,
					)
				)
		
		# Główne dane
		data_grid = ft.Column(
			controls=[
				self.create_data_row("Sprzedawca:", invoice.seller_name),
				self.create_data_row("Nr Faktury:", invoice.invoice_number),
				self.create_data_row(
					"Data:", invoice.invoice_date.strftime(
						'%Y-%m-%d'
						) if invoice.invoice_date else "-"
					),
				self.create_data_row(
					"Kwota:", f"{invoice.amount:.2f} {invoice.currency}"
					),
				self.create_data_row("NIP:", invoice.seller_nip or "-"),
				self.create_data_row("Konto:", invoice.bank_account or "-"),
				self.create_data_row(
					"Termin płatności:", invoice.payment_due_date.strftime(
						'%Y-%m-%d'
						) if invoice.payment_due_date else "-"
					),
				],
			spacing=AppSpacing.XS,
			)
		
		# Przyciski
		actions = ft.Row(
			controls=[
				ft.TextButton(
					"Edytuj",
					icon=AppIcons.EDIT,
					on_click=lambda e, idx=index: self.edit_before_save(idx),
					),
				ft.TextButton(
					"Pokaż tekst OCR",
					icon=AppIcons.VIEW,
					on_click=lambda e, text=raw_text: self.show_ocr_text(text),
					),
				ft.Container(expand=True),
				ft.ElevatedButton(
					"Zapisz",
					icon=AppIcons.SAVE,
					on_click=lambda e, idx=index: self.save_single_invoice(idx),
					disabled=has_errors,
					**AppStyles.button_primary()
					) if not has_errors else ft.Text(
					"Nie można zapisać (błędy)",
					color=AppColors.ERROR,
					size=12,
					),
				],
			alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
			)
		
		# Use card styles but with custom colored border based on status
		card_styles = AppStyles.card()
		card_styles['border'] = ft.border.all(2, status_color)

		return ft.Container(
			content=ft.Column(
				controls=[
					# Header z statusem
					ft.Row(
						controls=[
							ft.Icon(status_icon, color=status_color, size=24),
							ft.Text(
								f"Faktura {index + 1}/{len(self.processed_invoices)}",
								size=AppTypography.BODY_LARGE,
								weight=ft.FontWeight.BOLD,
								),
							ft.Container(
								content=ft.Text(
									f"OCR: {invoice.ocr_confidence:.1f}%" if invoice.ocr_confidence else "OCR: N/A",
									size=12,
									color="white",
									),
								bgcolor=AppColors.INFO,
								padding=ft.padding.symmetric(
									horizontal=8, vertical=4
									),
								border_radius=4,
								),
							],
						spacing=AppSpacing.SM,
						),

					ft.Divider(height=1, color=AppColors.DIVIDER),

					# Dane
					data_grid,

					# Walidacja
					ft.Column(
						controls=messages, spacing=AppSpacing.XS
						) if messages else ft.Container(),

					ft.Divider(height=1, color=AppColors.DIVIDER),

					# Akcje
					actions,
					],
				spacing=AppSpacing.SM,
				),
			**card_styles,
			)
	
	def create_data_row(self, label: str, value: str) -> ft.Row:
		"""Stwórz wiersz danych"""
		return ft.Row(
			controls=[
				ft.Text(
					label, size=12, weight=ft.FontWeight.BOLD,
					color=AppColors.TEXT_SECONDARY, width=150
					),
				ft.Text(value, size=14, color=AppColors.TEXT_PRIMARY),
				],
			spacing=AppSpacing.SM,
			)
	
	def edit_before_save(self, index: int):
		"""Edytuj fakturę przed zapisem"""
		if 0 <= index < len(self.processed_invoices):
			invoice, validation, raw_text = self.processed_invoices[index]
			
			# TODO: Otwórz dialog edycji inline lub przejdź do EditView
			self.show_info(
				"Edycja", "Funkcja edycji będzie dostępna w następnym kroku"
				)
	
	def show_ocr_text(self, text: str):
		"""Pokaż surowy tekst OCR"""
		dialog = ft.AlertDialog(
			title=ft.Text("Surowy tekst OCR", weight=ft.FontWeight.BOLD),
			content=ft.Container(
				content=ft.Text(
					text,
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
					"Zamknij", on_click=lambda e: self.close_dialog(dialog)
					)
				],
			)
		self.page.dialog = dialog
		dialog.open = True
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
		snackbar = ft.SnackBar(
			content=ft.Text(f"{title}: {message}"),
			bgcolor=AppColors.SUCCESS,
			)
		self.page.snack_bar = snackbar
		snackbar.open = True
		self.page.update()
	
	def show_error(self, title: str, message: str):
		"""Pokaż błąd"""
		snackbar = ft.SnackBar(
			content=ft.Text(f"{title}: {message}"),
			bgcolor=AppColors.ERROR,
			)
		self.page.snack_bar = snackbar
		snackbar.open = True
		self.page.update()
	
	def show_info(self, title: str, message: str):
		"""Pokaż info"""
		dialog = ft.AlertDialog(
			title=ft.Text(title, weight=ft.FontWeight.BOLD),
			content=ft.Text(message),
			actions=[
				ft.TextButton(
					"OK", on_click=lambda e: self.close_dialog(dialog)
					)
				],
			)
		self.page.dialog = dialog
		dialog.open = True
		self.page.update()
	
	def close_dialog(self, dialog):
		"""Zamknij dialog"""
		dialog.open = False
		self.page.update()