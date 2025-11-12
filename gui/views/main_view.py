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
	
	def __init__(self, page: ft.Page, app):
		super().__init__()
		self.page = page
		self.app = app
		
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
		
		# Dodaj do widoku
		self.controls = [
			header,
			ft.Divider(height=1, color=AppColors.DIVIDER),
			self.table_container,
			ft.Divider(height=1, color=AppColors.DIVIDER),
			self.stats_row,
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
					"Faktury",
					f"{stats['paid_invoices']} / {stats['total_invoices']}",
					AppIcons.INFO,
					AppColors.PRIMARY
				)
			)

			# Kwoty po walutach
			for currency, data in stats.get('by_currency', {}).items():
				# Opłacone
				stat_cards.append(
					self.create_stat_card(
						f"Opłacone ({currency})",
						f"{data['paid']:.2f}",
						ft.Icons.CHECK_CIRCLE_ROUNDED,
						AppColors.SUCCESS
					)
				)

				# Nieopłacone (bez przeterminowanych)
				if data['unpaid'] > 0:
					stat_cards.append(
						self.create_stat_card(
							f"Nieopłacone ({currency})",
							f"{data['unpaid']:.2f}",
							ft.Icons.PENDING_ROUNDED,
							AppColors.WARNING
						)
					)

				# Przeterminowane
				if data['overdue'] > 0:
					stat_cards.append(
						self.create_stat_card(
							f"Po terminie ({currency})",
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
		# TODO: Implementacja podglądu PDF
		self.show_info("Podgląd", f"Podgląd faktury: {invoice.invoice_number}")
	
	def edit_invoice(self, invoice: Invoice):
		"""Edytuj fakturę"""
		# Przejdź do widoku edycji
		from gui.views.edit_view import EditView
		edit_view = EditView(self.page, self.app, invoice)
		self.app.content_column.controls.clear()
		self.app.content_column.controls.append(edit_view)
		self.page.update()
	
	def delete_invoice(self, invoice: Invoice):
		"""Usuń fakturę"""
		
		def confirm_delete(e):
			try:
				self.invoice_repo.delete(invoice.id)
				dialog.open = False
				self.load_invoices()
				self.show_success(
					"Usunięto",
					f"Faktura {invoice.invoice_number} została usunięta"
					)
			except Exception as ex:
				self.show_error("Błąd", str(ex))
		
		dialog = ft.AlertDialog(
			title=ft.Text("Potwierdzenie", weight=ft.FontWeight.BOLD),
			content=ft.Text(
				f"Czy na pewno usunąć fakturę {invoice.invoice_number}?"
				),
			actions=[
				ft.TextButton(
					"Anuluj", on_click=lambda e: self.close_dialog(dialog)
					),
				ft.TextButton(
					"Usuń",
					on_click=confirm_delete,
					style=ft.ButtonStyle(color=AppColors.ERROR)
					),
				],
			)
		
		self.page.dialog = dialog
		dialog.open = True
		self.page.update()
	
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