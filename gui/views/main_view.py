"""
Główny widok - lista faktur
"""
import flet as ft
from typing import Optional
from repositories.invoice_repository import InvoiceRepository
from services.export_service import ExportService
from database.models import Invoice
from gui.theme import AppColors, AppIcons, AppSpacing, AppTypography, AppStyles
from gui.components.invoice_table import InvoiceTable


class MainView(ft.Column):
	"""Widok listy faktur"""

	def __init__(self, page: ft.Page, app, notification_panel=None):
		super().__init__()
		self.page = page
		self.app = app
		self.notification_panel = notification_panel
		
		# Repositories & Services
		self.invoice_repo = InvoiceRepository()
		self.export_service = ExportService()
		
		# State
		self.invoices = []
		self.filtered_invoices = []
		self.search_term = ""
		
		# Style
		self.spacing = AppSpacing.LG
		self.expand = True
		
		# UI
		self.build_ui()
		self.load_invoices()
	
	def build_ui(self):
		"""Zbuduj UI"""
		# Header z wyszukiwaniem
		self.search_field = ft.TextField(
			hint_text="Szukaj faktury (nazwa, numer, NIP)...",
			prefix_icon=AppIcons.SEARCH,
			on_change=self.on_search,
			expand=True,
			**AppStyles.text_field()
			)
		
		header = ft.Row(
			controls=[
				ft.Text(
					"Lista Faktur",
					size=AppTypography.HEADLINE,
					weight=ft.FontWeight.BOLD,
					color=AppColors.TEXT_PRIMARY,
					),
				ft.Container(expand=True),
				self.search_field,
				ft.ElevatedButton(
					"Eksportuj Excel",
					icon=AppIcons.EXPORT,
					on_click=self.export_excel,
					**AppStyles.button_primary()
					),
				ft.ElevatedButton(
					"Eksportuj CSV",
					icon=AppIcons.EXPORT,
					on_click=self.export_csv,
					**AppStyles.button_secondary()
					),
				ft.IconButton(
					icon=AppIcons.REFRESH,
					tooltip="Odśwież",
					on_click=lambda e: self.load_invoices(),
					icon_color=AppColors.PRIMARY,
					),
				],
			spacing=AppSpacing.SM,
			alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
			)
		
		# Tabela (placeholder - będzie wypełniona w load_invoices)
		self.table_container = ft.Container(
			content=ft.Column(
				controls=[ft.ProgressRing()],
				horizontal_alignment=ft.CrossAxisAlignment.CENTER,
				alignment=ft.MainAxisAlignment.CENTER,
			),
			expand=True,
			)
		
		# Statystyki
		self.stats_row = ft.Row(
			controls=[],
			spacing=AppSpacing.MD,
			)

		# Create reusable dialogs
		self.current_invoice_to_delete = None
		self.delete_dialog = ft.AlertDialog(
			modal=True,
			title=ft.Text("Potwierdzenie", weight=ft.FontWeight.BOLD),
			content=ft.Text(""),
			actions=[
				ft.TextButton(
					"Anuluj",
					on_click=self.cancel_delete
				),
				ft.TextButton(
					"Usuń",
					on_click=self.confirm_delete,
					style=ft.ButtonStyle(color=AppColors.ERROR)
				),
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
		self.page.overlay.extend([self.delete_dialog, self.info_dialog])

		# Dodaj do widoku
		self.controls = [
			header,
			ft.Divider(height=1, color=AppColors.DIVIDER),
			self.stats_row,
			ft.Divider(height=1, color=AppColors.DIVIDER),
			self.table_container,
			]
	
	def load_invoices(self):
		"""Załaduj faktury z bazy"""
		try:
			rows = self.invoice_repo.get_all()
			self.invoices = [self.invoice_repo.row_to_invoice(row) for row in
				rows]
			self.filtered_invoices = self.invoices.copy()

			self.update_table()
			self.update_stats()

		except Exception as e:
			# Clear the progress ring and show error
			self.table_container.content = ft.Container(
				content=ft.Column(
					controls=[
						ft.Icon(
							AppIcons.ERROR, size=64,
							color=AppColors.ERROR
							),
						ft.Text(
							"Błąd ładowania faktur",
							size=AppTypography.TITLE,
							color=AppColors.ERROR,
							),
						ft.Text(
							str(e),
							color=AppColors.TEXT_SECONDARY,
							),
						ft.ElevatedButton(
							"Spróbuj ponownie",
							icon=AppIcons.REFRESH,
							on_click=lambda e: self.load_invoices(),
							**AppStyles.button_primary()
							),
						],
					horizontal_alignment=ft.CrossAxisAlignment.CENTER,
					spacing=AppSpacing.SM,
					),
				alignment=ft.alignment.center,
				)
			self.page.update()
			self.show_error("Błąd ładowania faktur", str(e))
			# Print to console for debugging
			print(f"Error loading invoices: {e}")
			import traceback
			traceback.print_exc()
	
	def update_table(self):
		"""Zaktualizuj tabelę"""
		if not self.filtered_invoices:
			# Pusty stan
			self.table_container.content = ft.Container(
				content=ft.Column(
					controls=[
						ft.Icon(
							AppIcons.INFO, size=64,
							color=AppColors.TEXT_DISABLED
							),
						ft.Text(
							"Brak faktur",
							size=AppTypography.TITLE,
							color=AppColors.TEXT_SECONDARY,
							),
						ft.Text(
							"Zacznij od zaimportowania plików PDF",
							color=AppColors.TEXT_DISABLED,
							),
						],
					horizontal_alignment=ft.CrossAxisAlignment.CENTER,
					spacing=AppSpacing.SM,
					),
				alignment=ft.alignment.center,
				)
		else:
			# Tabela z danymi
			table = InvoiceTable(
				invoices=self.filtered_invoices,
				on_view=self.view_invoice,
				on_edit=self.edit_invoice,
				on_delete=self.delete_invoice,
				on_refresh=self.refresh_table,
				)

			# Wrap in ListView for proper scrolling and expansion
			self.table_container.content = ft.ListView(
				controls=[table],
				expand=True,
				spacing=0,
				padding=0,
				)
		
		self.page.update()
	
	def update_stats(self):
		"""Zaktualizuj statystyki"""
		try:
			stats = self.invoice_repo.get_statistics()

			stat_cards = []

			# Liczba faktur: opłacone / wszystkie
			stat_cards.append(
				self.create_stat_card(
					"Faktury opłacone",
					f"{stats['paid_invoices']} z {stats['total_invoices']}",
					AppIcons.INFO,
					AppColors.PRIMARY
				)
			)

			# Suma kwot z faktur (PLN)
			totals = stats.get('totals', {})
			if totals.get('total_amount', 0) > 0:
				stat_cards.append(
					self.create_stat_card(
						"Suma faktur (PLN)",
						f"{totals['total_amount']:.2f}",
						ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED,
						AppColors.INFO
					)
				)

				# Suma nieopłaconych (nieopłacone + przeterminowane)
				if totals.get('total_unpaid', 0) > 0:
					stat_cards.append(
						self.create_stat_card(
							"Do zapłaty (PLN)",
							f"{totals['total_unpaid']:.2f}",
							ft.Icons.PAYMENT_ROUNDED,
							AppColors.ERROR
						)
					)

				# VAT 23% z całkowitej kwoty
				stat_cards.append(
					self.create_stat_card(
						"Suma VAT 23% (PLN)",
						f"{totals['total_vat']:.2f}",
						ft.Icons.RECEIPT_LONG_ROUNDED,
						AppColors.WARNING
					)
				)

			# Kwoty po walutach
			for currency, data in stats.get('by_currency', {}).items():
				# Opłacone
				stat_cards.append(
					self.create_stat_card(
						f"Suma Opłaconych {currency})",
						f"{data['paid']:.2f}",
						ft.Icons.CHECK_CIRCLE_ROUNDED,
						AppColors.SUCCESS
					)
				)

				# Nieopłacone (bez przeterminowanych)
				if data['unpaid'] > 0:
					stat_cards.append(
						self.create_stat_card(
							f"Suma Nieopłaconych ({currency})",
							f"{data['unpaid']:.2f}",
							ft.Icons.PENDING_ROUNDED,
							AppColors.WARNING
						)
					)

				# Przeterminowane
				if data['overdue'] > 0:
					stat_cards.append(
						self.create_stat_card(
							f"Suma załegłych ({currency})",
							f"{data['overdue']:.2f}",
							ft.Icons.ERROR_ROUNDED,
							AppColors.ERROR
						)
					)

			self.stats_row.controls = stat_cards
			self.page.update()

		except Exception as e:
			print(f"Error updating stats: {e}")
			import traceback
			traceback.print_exc()
			# Don't show error to user, just log it
			# Stats are not critical for the view to work
	
	def create_stat_card(
			self, label: str, value: str, icon, color
			) -> ft.Container:
		"""Stwórz kartę statystyki"""
		return ft.Container(
			content=ft.Row(
				controls=[
					ft.Icon(icon, size=32, color=color),
					ft.Column(
						controls=[
							ft.Text(
								label, size=12, color=AppColors.TEXT_SECONDARY
								),
							ft.Text(value, size=20, weight=ft.FontWeight.BOLD),
							],
						spacing=0,
						),
					],
				spacing=AppSpacing.SM,
				),
			**AppStyles.card(),
			)
	
	def refresh_table(self):
		"""Odśwież tabelę (wywoływane po zmianie statusu)"""
		self.update_table()
		self.update_stats()

	def on_search(self, e):
		"""Wyszukiwanie"""
		self.search_term = e.control.value.lower()
		
		if not self.search_term:
			self.filtered_invoices = self.invoices.copy()
		else:
			self.filtered_invoices = [
				inv for inv in self.invoices
				if self.search_term in inv.seller_name.lower()
				   or self.search_term in inv.invoice_number.lower()
				   or (
							   inv.seller_nip and self.search_term in inv.seller_nip.lower())
				]
		
		self.update_table()
	
	def view_invoice(self, invoice: Invoice):
		"""Podgląd faktury"""
		if not invoice.pdf_path:
			self.show_error("Błąd", "Brak pliku PDF dla tej faktury")
			return

		import os
		from pathlib import Path

		pdf_path = Path(invoice.pdf_path)

		# Check if file exists
		if not pdf_path.exists():
			self.show_error(
				"Błąd",
				f"Plik PDF nie istnieje:\n{invoice.pdf_path}"
			)
			return

		try:
			# Open PDF in system default viewer
			if os.name == 'nt':  # Windows
				os.startfile(str(pdf_path))
			elif os.name == 'posix':  # macOS/Linux
				import subprocess
				if os.uname().sysname == 'Darwin':  # macOS
					subprocess.run(['open', str(pdf_path)])
				else:  # Linux
					subprocess.run(['xdg-open', str(pdf_path)])

			print(f"✅ Otwarto PDF: {invoice.invoice_number}")
		except Exception as ex:
			self.show_error("Błąd otwarcia PDF", str(ex))
	
	def edit_invoice(self, invoice: Invoice):
		"""Edytuj fakturę"""
		# Przejdź do widoku edycji
		from gui.views.edit_view import EditView
		edit_view = EditView(self.page, self.app, invoice, self.notification_panel)
		self.app.content_column.controls.clear()
		self.app.content_column.controls.append(edit_view)
		self.page.update()
	
	def delete_invoice(self, invoice: Invoice):
		"""Usuń fakturę"""
		# Store the invoice to delete
		self.current_invoice_to_delete = invoice

		# Update dialog content
		self.delete_dialog.content = ft.Text(f"Czy na pewno usunąć fakturę {invoice.invoice_number}?")

		# Open dialog
		self.delete_dialog.open = True
		self.page.update()

	def cancel_delete(self, e):
		"""Cancel delete dialog"""
		self.delete_dialog.open = False
		self.page.update()
		self.current_invoice_to_delete = None

	def confirm_delete(self, e):
		"""Confirm and execute delete"""
		try:
			if self.current_invoice_to_delete:
				invoice_number = self.current_invoice_to_delete.invoice_number
				self.invoice_repo.delete(self.current_invoice_to_delete.id)

				# Close dialog
				self.delete_dialog.open = False
				self.page.update()

				# Reload invoices
				self.load_invoices()

				# Show success message
				self.show_success(
					"Usunięto",
					f"Faktura {invoice_number} została usunięta"
				)

				self.current_invoice_to_delete = None
		except Exception as ex:
			# Close dialog on error
			self.delete_dialog.open = False
			self.page.update()
			self.show_error("Błąd", str(ex))
			self.current_invoice_to_delete = None
	
	def export_excel(self, e):
		"""Eksport do Excel"""
		try:
			from datetime import datetime
			filename = f"faktury_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
			
			file_picker = ft.FilePicker(
				on_result=lambda e: self.save_export(e, 'excel')
				)
			self.page.overlay.append(file_picker)
			self.page.update()
			
			file_picker.save_file(
				dialog_title="Zapisz jako Excel",
				file_name=filename,
				allowed_extensions=["xlsx"]
				)
		
		except Exception as ex:
			self.show_error("Błąd eksportu", str(ex))
	
	def export_csv(self, e):
		"""Eksport do CSV"""
		try:
			from datetime import datetime
			filename = f"faktury_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
			
			file_picker = ft.FilePicker(
				on_result=lambda e: self.save_export(e, 'csv')
				)
			self.page.overlay.append(file_picker)
			self.page.update()
			
			file_picker.save_file(
				dialog_title="Zapisz jako CSV",
				file_name=filename,
				allowed_extensions=["csv"]
				)
		
		except Exception as ex:
			self.show_error("Błąd eksportu", str(ex))
	
	def save_export(self, e: ft.FilePickerResultEvent, file_format: str):
		"""Zapisz eksport"""
		if not e.path:
			return
		
		try:
			if file_format == 'excel':
				self.export_service.export_to_excel(
					self.filtered_invoices, e.path
					)
			else:
				self.export_service.export_to_csv(
					self.filtered_invoices, e.path
					)
			
			self.show_success(
				"Eksport",
				f"Wyeksportowano {len(self.filtered_invoices)} faktur"
				)
		except Exception as ex:
			self.show_error("Błąd zapisu", str(ex))
	
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