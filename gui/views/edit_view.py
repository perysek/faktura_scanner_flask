"""
Widok edycji faktury
"""
import flet as ft
from datetime import datetime
from repositories.invoice_repository import InvoiceRepository
from repositories.audit_repository import AuditRepository
from services.validation_service import ValidationService
from database.models import Invoice
from gui.theme import AppColors, AppIcons, AppSpacing, AppTypography, AppStyles


class EditView(ft.Column):
	"""Widok edycji faktury"""
	
	def __init__(self, page: ft.Page, app, invoice: Invoice):
		super().__init__()
		self.page = page
		self.app = app
		self.invoice = invoice
		self.original_invoice = Invoice(**invoice.__dict__)  # Kopia
		
		# Services
		self.invoice_repo = InvoiceRepository()
		self.audit_repo = AuditRepository()
		self.validation_service = ValidationService()
		
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
				ft.IconButton(
					icon=ft.Icons.ARROW_BACK,
					tooltip="Powrót",
					on_click=lambda e: self.app.refresh_main_view(),
					),
				ft.Text(
					f"Edycja faktury: {self.invoice.invoice_number}",
					size=AppTypography.HEADLINE,
					weight=ft.FontWeight.BOLD,
					),
				],
			)
		
		# Formularz
		self.seller_name_field = ft.TextField(
			label="Nazwa sprzedawcy",
			value=self.invoice.seller_name,
			**AppStyles.text_field()
			)
		
		self.seller_nip_field = ft.TextField(
			label="NIP",
			value=self.invoice.seller_nip or "",
			**AppStyles.text_field()
			)
		
		self.invoice_number_field = ft.TextField(
			label="Numer faktury",
			value=self.invoice.invoice_number,
			**AppStyles.text_field()
			)
		
		self.invoice_date_field = ft.TextField(
			label="Data faktury (YYYY-MM-DD)",
			value=self.invoice.invoice_date.strftime(
				'%Y-%m-%d'
				) if self.invoice.invoice_date else "",
			**AppStyles.text_field()
			)
		
		self.bank_account_field = ft.TextField(
			label="Numer konta bankowego",
			value=self.invoice.bank_account or "",
			**AppStyles.text_field()
			)
		
		self.amount_field = ft.TextField(
			label="Kwota",
			value=str(self.invoice.amount),
			keyboard_type=ft.KeyboardType.NUMBER,
			**AppStyles.text_field()
			)
		
		# Dropdown doesn't support 'height' parameter, so filter it out
		dropdown_styles = AppStyles.text_field()
		dropdown_styles.pop('height', None)

		self.currency_field = ft.Dropdown(
			label="Waluta",
			value=self.invoice.currency,
			options=[
				ft.dropdown.Option("PLN"),
				ft.dropdown.Option("EUR"),
				ft.dropdown.Option("USD"),
				ft.dropdown.Option("GBP"),
				],
			**dropdown_styles
			)
		
		self.payment_due_date_field = ft.TextField(
			label="Termin płatności (YYYY-MM-DD)",
			value=self.invoice.payment_due_date.strftime(
				'%Y-%m-%d'
				) if self.invoice.payment_due_date else "",
			**AppStyles.text_field()
			)

		self.payment_term_field = ft.TextField(
			label="Warunki płatności (np. POBRANIE)",
			value=self.invoice.payment_term or "",
			hint_text="Zostaw puste dla zwykłej płatności",
			**AppStyles.text_field()
			)

		# Dropdown doesn't support 'height' parameter, so filter it out
		dropdown_styles_status = AppStyles.text_field()
		dropdown_styles_status.pop('height', None)

		self.status_field = ft.Dropdown(
			label="Status",
			value=self.invoice.status,
			options=[
				ft.dropdown.Option("Nieopłacona"),
				ft.dropdown.Option("Opłacona"),
			],
			**dropdown_styles_status
		)

		form = ft.Container(
			content=ft.Column(
				controls=[
					self.seller_name_field,
					self.seller_nip_field,
					self.invoice_number_field,
					self.invoice_date_field,
					self.bank_account_field,
					ft.Row(
						controls=[
							self.amount_field,
							self.currency_field,
							],
						spacing=AppSpacing.SM,
						),
					self.payment_due_date_field,
					self.payment_term_field,
					self.status_field,
					],
				spacing=AppSpacing.MD,
				),
			**AppStyles.card(),
			width=600,
			)
		
		# Przyciski
		actions = ft.Row(
			controls=[
				ft.TextButton(
					"Anuluj",
					icon=AppIcons.CANCEL,
					on_click=lambda e: self.app.refresh_main_view(),
					),
				ft.ElevatedButton(
					"Zapisz zmiany",
					icon=AppIcons.SAVE,
					on_click=self.save_changes,
					**AppStyles.button_primary()
					),
				],
			spacing=AppSpacing.SM,
			)
		
		# Dodaj do widoku
		self.controls = [
			header,
			ft.Divider(height=1, color=AppColors.DIVIDER),
			form,
			actions,
			]
	
	def save_changes(self, e):
		"""Zapisz zmiany"""
		try:
			# Pobierz wartości z pól
			self.invoice.seller_name = self.seller_name_field.value
			self.invoice.seller_nip = self.seller_nip_field.value or None
			self.invoice.invoice_number = self.invoice_number_field.value
			self.invoice.bank_account = self.bank_account_field.value or None
			self.invoice.amount = float(self.amount_field.value)
			self.invoice.currency = self.currency_field.value
			self.invoice.payment_term = self.payment_term_field.value or None
			self.invoice.status = self.status_field.value

			# Parsuj daty
			if self.invoice_date_field.value:
				self.invoice.invoice_date = datetime.strptime(
					self.invoice_date_field.value, '%Y-%m-%d'
					).date()

			if self.payment_due_date_field.value:
				self.invoice.payment_due_date = datetime.strptime(
					self.payment_due_date_field.value, '%Y-%m-%d'
					).date()
			
			# Walidacja
			validation = self.validation_service.validate_invoice(self.invoice)
			if validation['errors']:
				self.show_error(
					"Błędy walidacji", "\n".join(validation['errors'])
					)
				return
			
			# Zapisz do bazy
			success = self.invoice_repo.update(self.invoice.id, self.invoice)
			
			if success:
				# Zapisz audit log
				self.log_changes()
				
				self.show_success("Zapisano", "Faktura została zaktualizowana")
				
				# Powrót do głównego widoku
				import time
				time.sleep(1)
				self.app.refresh_main_view()
			else:
				self.show_error("Błąd", "Nie udało się zapisać zmian")
		
		except ValueError as ve:
			self.show_error(
				"Błąd danych", "Nieprawidłowy format daty lub kwoty"
				)
		except Exception as ex:
			self.show_error("Błąd", str(ex))
	
	def log_changes(self):
		"""Zapisz zmiany w audit log"""
		changes = {
			'seller_name': (
				self.original_invoice.seller_name, self.invoice.seller_name
				),
			'seller_nip': (
				self.original_invoice.seller_nip, self.invoice.seller_nip
				),
			'invoice_number': (
				self.original_invoice.invoice_number,
				self.invoice.invoice_number
				),
			'bank_account': (
				self.original_invoice.bank_account, self.invoice.bank_account
				),
			'amount': (self.original_invoice.amount, self.invoice.amount),
			'currency': (self.original_invoice.currency, self.invoice.currency),
			}
		
		for field, (old_val, new_val) in changes.items():
			if old_val != new_val:
				self.audit_repo.log_change(
					self.invoice.id,
					field,
					str(old_val) if old_val else "",
					str(new_val) if new_val else ""
					)
	
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