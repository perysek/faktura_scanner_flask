"""
Komponent tabeli faktur
"""
import flet as ft
from typing import List, Callable
from datetime import date
from database.models import Invoice
from repositories.invoice_repository import InvoiceRepository
from gui.theme import AppColors, AppIcons, AppSpacing, AppTypography


class InvoiceTable(ft.DataTable):
	"""Tabela faktur"""
	
	def __init__(
			self,
			invoices: List[Invoice],
			on_view: Callable[[Invoice], None],
			on_edit: Callable[[Invoice], None],
			on_delete: Callable[[Invoice], None],
			on_refresh: Callable[[], None] = None
			):
		# Store callbacks before calling super().__init__
		self.invoices = invoices
		self.on_view_callback = on_view
		self.on_edit_callback = on_edit
		self.on_delete_callback = on_delete
		self.on_refresh_callback = on_refresh
		self.invoice_repo = InvoiceRepository()

		# Define columns before calling super().__init__
		columns = [
			ft.DataColumn(ft.Text("Sprzedawca", weight=ft.FontWeight.BOLD)),
			ft.DataColumn(ft.Text("Nr Faktury", weight=ft.FontWeight.BOLD)),
			ft.DataColumn(ft.Text("Data", weight=ft.FontWeight.BOLD)),
			ft.DataColumn(ft.Text("Kwota", weight=ft.FontWeight.BOLD)),  # Left-aligned (removed numeric=True)
			ft.DataColumn(ft.Text("NIP", weight=ft.FontWeight.BOLD)),
			ft.DataColumn(ft.Text("Konto", weight=ft.FontWeight.BOLD)),
			ft.DataColumn(ft.Text("Termin płatności", weight=ft.FontWeight.BOLD)),
			ft.DataColumn(ft.Text("Status", weight=ft.FontWeight.BOLD)),
			ft.DataColumn(ft.Text("OCR", weight=ft.FontWeight.BOLD)),
			ft.DataColumn(ft.Text("Akcje", weight=ft.FontWeight.BOLD)),
			]

		# Build rows
		rows = self.build_rows()

		# Initialize parent DataTable with columns and rows
		super().__init__(
			columns=columns,
			rows=rows,
			border=ft.border.all(1, AppColors.BORDER),
			border_radius=8,
			heading_row_color=AppColors.SURFACE_VARIANT,
			heading_row_height=36,  # Reduced from 48 for compact layout
			data_row_max_height=40,  # Reduced from 60 for compact layout
			data_row_min_height=40,  # Set minimum height for consistency
			horizontal_lines=ft.BorderSide(1, AppColors.DIVIDER),
			vertical_lines=ft.BorderSide(1, AppColors.DIVIDER),
			column_spacing=4,
		)
	
	def build_rows(self) -> List[ft.DataRow]:
		"""Zbuduj wiersze tabeli"""
		rows = []
		
		for invoice in self.invoices:
			# Status badge (duplikat?)
			badges = []
			if invoice.is_duplicate:
				badges.append(
					ft.Container(
						content=ft.Text(
							"DUPLIKAT", size=10, color="white",
							weight=ft.FontWeight.BOLD
							),
						bgcolor=AppColors.WARNING,
						padding=ft.padding.symmetric(horizontal=6, vertical=2),
						border_radius=4,
						)
					)
			
			# Przyciski akcji
			actions = ft.Row(
				controls=[
					ft.IconButton(
						icon=AppIcons.VIEW,
						icon_size=20,
						tooltip="Podgląd",
						on_click=lambda e, inv=invoice: self.on_view_callback(
							inv
							),
						icon_color=AppColors.PRIMARY,
						),
					ft.IconButton(
						icon=AppIcons.EDIT,
						icon_size=20,
						tooltip="Edytuj",
						on_click=lambda e, inv=invoice: self.on_edit_callback(
							inv
							),
						icon_color=AppColors.INFO,
						),
					ft.IconButton(
						icon=AppIcons.DELETE,
						icon_size=20,
						tooltip="Usuń",
						on_click=lambda e, inv=invoice: self.on_delete_callback(
							inv
							),
						icon_color=AppColors.ERROR,
						),
					],
				spacing=4,
				)
			
			row = ft.DataRow(
				cells=[
					ft.DataCell(
						ft.Column(
							controls=[
								ft.Text(invoice.seller_name, size=13),
								*badges,
								],
							spacing=4,
							alignment=ft.MainAxisAlignment.CENTER,
							)
						),
					ft.DataCell(ft.Text(invoice.invoice_number, size=13)),
					ft.DataCell(
						ft.Text(
							invoice.invoice_date.strftime(
								'%Y-%m-%d'
								) if invoice.invoice_date else "-",
							size=13
							)
						),
					ft.DataCell(
						ft.Text(
							f"{invoice.amount:.2f} {invoice.currency}",
							size=13,
							weight=ft.FontWeight.W_500
							)
						),
					ft.DataCell(
						ft.Text(
							invoice.seller_nip or "-",
							size=13
							)
						),
					ft.DataCell(
						ft.Text(
							# Show full IBAN number
							invoice.bank_account or "-",
							size=13
							)
						),
					ft.DataCell(
						ft.Container(
							content=ft.Text(
								invoice.payment_term if invoice.payment_term else (
									invoice.payment_due_date.strftime(
										'%Y-%m-%d'
									) if invoice.payment_due_date else "-"
								),
								size=13,
								color="white" if (
									invoice.payment_due_date
									and invoice.payment_due_date < date.today()
									and invoice.status != "Opłacona"
								) else AppColors.TEXT_PRIMARY
							),
							bgcolor=AppColors.ERROR if (
								invoice.payment_due_date
								and invoice.payment_due_date < date.today()
								and invoice.status != "Opłacona"
							) else None,
							padding=ft.padding.symmetric(horizontal=6, vertical=2),
							border_radius=4,
						)
					),
					ft.DataCell(
						ft.Dropdown(
							value=invoice.status,
							options=[
								ft.dropdown.Option("Nieopłacona"),
								ft.dropdown.Option("Opłacona"),
							],
							on_change=lambda e, inv=invoice: self.on_status_change(e, inv),
							text_size=13,
							content_padding=ft.padding.symmetric(horizontal=8, vertical=2),
							border_width=0,
						)
					),
					ft.DataCell(
						ft.Container(
							content=ft.Text(
								f"{invoice.ocr_confidence:.0f}%" if invoice.ocr_confidence else "-",
								size=13,
								color="white" if invoice.ocr_confidence and invoice.ocr_confidence >= 80 else AppColors.TEXT_PRIMARY,
								weight=ft.FontWeight.BOLD
								),
							bgcolor=AppColors.SUCCESS if invoice.ocr_confidence and invoice.ocr_confidence >= 80 else (
								AppColors.WARNING if invoice.ocr_confidence and invoice.ocr_confidence >= 60 else AppColors.ERROR
							) if invoice.ocr_confidence else None,
							padding=ft.padding.symmetric(horizontal=6, vertical=2),
							border_radius=4,
							)
						),
					ft.DataCell(actions),
					],
				)
			rows.append(row)
		
		return rows
	
	def on_status_change(self, e, invoice: Invoice):
		"""Obsłuż zmianę statusu faktury"""
		try:
			# Update invoice status
			invoice.status = e.control.value
			# Save to database
			self.invoice_repo.update(invoice.id, invoice)
			print(f"✅ Status faktury {invoice.invoice_number} zmieniony na: {invoice.status}")

			# Refresh table to update colors
			if self.on_refresh_callback:
				self.on_refresh_callback()
		except Exception as ex:
			print(f"❌ Błąd zmiany statusu: {ex}")
			# Revert dropdown to previous value on error
			e.control.value = invoice.status
			if e.control.page:
				e.control.page.update()

	def update_data(self, invoices: List[Invoice]):
		"""Zaktualizuj dane w tabeli"""
		self.invoices = invoices
		self.rows = self.build_rows()