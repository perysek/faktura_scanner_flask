"""
Komponent tabeli faktur
"""
import flet as ft
from typing import List, Callable, Optional
from datetime import date, datetime
from database.models import Invoice
from repositories.invoice_repository import InvoiceRepository
from gui.theme import AppColors, AppIcons, AppSpacing, AppTypography


class InvoiceTable(ft.Column):
	"""Tabela faktur z sortowaniem i filtrowaniem"""

	def __init__(
			self,
			invoices: List[Invoice],
			on_view: Callable[[Invoice], None],
			on_edit: Callable[[Invoice], None],
			on_delete: Callable[[Invoice], None],
			on_refresh: Callable[[], None] = None
			):
		super().__init__()

		# Store callbacks and data
		self.all_invoices = invoices
		self.filtered_invoices = invoices.copy()
		self.on_view_callback = on_view
		self.on_edit_callback = on_edit
		self.on_delete_callback = on_delete
		self.on_refresh_callback = on_refresh
		self.invoice_repo = InvoiceRepository()

		# Sorting state
		self.sort_column: Optional[str] = None
		self.sort_ascending: bool = True

		# Filter state - dictionary of column_name: filter_text
		self.column_filters = {
			'seller_name': '',
			'invoice_number': '',
			'invoice_date': '',
			'amount': '',
			'seller_nip': '',
			'bank_account': '',
			'payment_due_date': '',
			'status': '',
			'created_at': '',
			'ocr_confidence': '',
		}

		# Build the table
		self.spacing = 0
		self.expand = True
		self.build_table()

	def build_table(self):
		"""Zbuduj tabelę z niestandardowymi nagłówkami"""
		# Apply filters and sorting
		self.apply_filters()
		self.apply_sorting()

		# Create data table with cleaner design
		data_table = ft.DataTable(
			columns=self.build_columns(),
			rows=self.build_rows(),
			border=ft.border.all(1, "#E0E0E0"),
			border_radius=4,
			heading_row_color="#F5F5F5",
			heading_row_height=75,  # Adjusted for normal search field height
			data_row_max_height=44,
			data_row_min_height=44,
			horizontal_lines=ft.BorderSide(1, "#EEEEEE"),
			vertical_lines=ft.BorderSide(1, "#EEEEEE"),
			column_spacing=8,
		)

		# Clear and add to column
		self.controls.clear()
		self.controls.append(data_table)

	def build_columns(self) -> List[ft.DataColumn]:
		"""Zbuduj kolumny z sortowaniem i filtrowaniem"""
		# Columns with search: Sprzedawca, Data, Kwota, Termin płatności, Data dodania
		columns = [
			self.create_column_header("Sprzedawca", "seller_name", with_search=True),
			self.create_simple_header("Nr Faktury"),
			self.create_column_header("Data", "invoice_date", with_search=True),
			self.create_column_header("Kwota", "amount", with_search=True),
			self.create_simple_header("NIP"),
			self.create_simple_header("Konto"),
			self.create_column_header("Termin płatności", "payment_due_date", with_search=True),
			self.create_column_header("Status", "status"),
			self.create_column_header("Data dodania", "created_at", with_search=True),
			self.create_simple_header("OCR"),
			self.create_simple_header("Akcje"),
		]
		return columns

	def create_simple_header(self, label: str) -> ft.DataColumn:
		"""Stwórz prosty nagłówek bez sortowania i filtrowania"""
		return ft.DataColumn(
			ft.Text(
				label,
				weight=ft.FontWeight.W_600,
				size=12,
				color="#424242"
			)
		)

	def create_column_header(self, label: str, field_name: str, with_search: bool = False) -> ft.DataColumn:
		"""Stwórz nagłówek kolumny z sortowaniem i opcjonalnym wyszukiwaniem"""
		# Sort icon
		sort_icon = ft.Icons.UNFOLD_MORE
		if self.sort_column == field_name:
			sort_icon = ft.Icons.ARROW_UPWARD if self.sort_ascending else ft.Icons.ARROW_DOWNWARD

		# Header with sort button - cleaner style
		header_row = ft.Row(
			controls=[
				ft.Text(
					label,
					weight=ft.FontWeight.W_600,  # Slightly less bold
					size=12,
					color="#424242",  # Darker gray text
					expand=True
				),
				ft.IconButton(
					icon=sort_icon,
					icon_size=14,  # Smaller icon
					tooltip=f"Sortuj {label}",
					on_click=lambda e, field=field_name: self.toggle_sort(field),
					icon_color="#2196F3" if self.sort_column == field_name else "#9E9E9E",  # Blue when active, gray when not
					style=ft.ButtonStyle(
						padding=ft.padding.all(4),  # Smaller button padding
					),
				),
			],
			spacing=4,
			alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
		)

		if with_search:
			# Search field below column name - white bg with darker grey border
			search_field = ft.TextField(
				hint_text="Search...",
				value=self.column_filters.get(field_name, ''),
				on_change=lambda e, field=field_name: self.on_filter_change(field, e.control.value),
				text_size=11,
				height=32,
				content_padding=ft.padding.symmetric(horizontal=6, vertical=4),
				border_color="#BDBDBD",  # Darker grey than header bg (#F5F5F5)
				focused_border_color="#90CAF9",
				border_width=1,
				border_radius=3,
				bgcolor="#FFFFFF",  # White background
				filled=True,
				dense=True,
				cursor_color="#2196F3",
				expand=True,
			)

			# Wrap in container with padding to fit within column
			search_container = ft.Container(
				content=search_field,
				padding=ft.padding.symmetric(horizontal=5, vertical=2),
				expand=True,
			)

			# Column header with search below - aligned top-center
			header_column = ft.Column(
				controls=[header_row, search_container],
				spacing=2,
				#tight=True,
				expand=True,
				horizontal_alignment=ft.CrossAxisAlignment.CENTER,  # Center horizontally
				alignment=ft.MainAxisAlignment.START,  # Align to top
			)
			return ft.DataColumn(header_column)
		else:
			# Column header without search
			return ft.DataColumn(header_row)

	def toggle_sort(self, field_name: str):
		"""Przełącz sortowanie dla kolumny"""
		if self.sort_column == field_name:
			# Toggle direction if same column
			self.sort_ascending = not self.sort_ascending
		else:
			# New column, default to ascending
			self.sort_column = field_name
			self.sort_ascending = True

		# Rebuild table
		self.build_table()
		if self.page:
			self.page.update()

	def on_filter_change(self, field_name: str, value: str):
		"""Obsłuż zmianę filtra"""
		self.column_filters[field_name] = value.lower()

		# Rebuild table
		self.build_table()
		if self.page:
			self.page.update()

	def apply_filters(self):
		"""Zastosuj filtry do faktur"""
		self.filtered_invoices = self.all_invoices.copy()

		for field_name, filter_text in self.column_filters.items():
			if not filter_text:
				continue

			# Filter based on field
			if field_name == 'seller_name':
				self.filtered_invoices = [inv for inv in self.filtered_invoices
					if filter_text in (inv.seller_name or '').lower()]

			elif field_name == 'invoice_number':
				self.filtered_invoices = [inv for inv in self.filtered_invoices
					if filter_text in (inv.invoice_number or '').lower()]

			elif field_name == 'invoice_date':
				self.filtered_invoices = [inv for inv in self.filtered_invoices
					if filter_text in (inv.invoice_date.strftime('%Y-%m-%d') if inv.invoice_date else '')]

			elif field_name == 'amount':
				self.filtered_invoices = [inv for inv in self.filtered_invoices
					if filter_text in f"{inv.amount:.2f}"]

			elif field_name == 'seller_nip':
				self.filtered_invoices = [inv for inv in self.filtered_invoices
					if filter_text in (inv.seller_nip or '').lower()]

			elif field_name == 'bank_account':
				self.filtered_invoices = [inv for inv in self.filtered_invoices
					if filter_text in (inv.bank_account or '').lower()]

			elif field_name == 'payment_due_date':
				self.filtered_invoices = [inv for inv in self.filtered_invoices
					if filter_text in (inv.payment_due_date.strftime('%Y-%m-%d') if inv.payment_due_date else '') or
					   filter_text in (inv.payment_term or '').lower()]

			elif field_name == 'status':
				self.filtered_invoices = [inv for inv in self.filtered_invoices
					if filter_text in (inv.status or '').lower()]

			elif field_name == 'created_at':
				self.filtered_invoices = [inv for inv in self.filtered_invoices
					if filter_text in (inv.created_at.strftime('%Y-%m-%d %H:%M') if inv.created_at else '')]

			elif field_name == 'ocr_confidence':
				self.filtered_invoices = [inv for inv in self.filtered_invoices
					if filter_text in (f"{inv.ocr_confidence:.0f}" if inv.ocr_confidence else '')]

	def apply_sorting(self):
		"""Zastosuj sortowanie do faktur"""
		if not self.sort_column:
			return

		# Sort based on field
		if self.sort_column == 'seller_name':
			self.filtered_invoices.sort(
				key=lambda inv: (inv.seller_name or '').lower(),
				reverse=not self.sort_ascending
			)

		elif self.sort_column == 'invoice_number':
			self.filtered_invoices.sort(
				key=lambda inv: (inv.invoice_number or '').lower(),
				reverse=not self.sort_ascending
			)

		elif self.sort_column == 'invoice_date':
			self.filtered_invoices.sort(
				key=lambda inv: inv.invoice_date if inv.invoice_date else date.min,
				reverse=not self.sort_ascending
			)

		elif self.sort_column == 'amount':
			self.filtered_invoices.sort(
				key=lambda inv: inv.amount,
				reverse=not self.sort_ascending
			)

		elif self.sort_column == 'seller_nip':
			self.filtered_invoices.sort(
				key=lambda inv: (inv.seller_nip or '').lower(),
				reverse=not self.sort_ascending
			)

		elif self.sort_column == 'bank_account':
			self.filtered_invoices.sort(
				key=lambda inv: (inv.bank_account or '').lower(),
				reverse=not self.sort_ascending
			)

		elif self.sort_column == 'payment_due_date':
			self.filtered_invoices.sort(
				key=lambda inv: inv.payment_due_date if inv.payment_due_date else date.min,
				reverse=not self.sort_ascending
			)

		elif self.sort_column == 'status':
			self.filtered_invoices.sort(
				key=lambda inv: (inv.status or '').lower(),
				reverse=not self.sort_ascending
			)

		elif self.sort_column == 'created_at':
			self.filtered_invoices.sort(
				key=lambda inv: inv.created_at if inv.created_at else datetime.min,
				reverse=not self.sort_ascending
			)

		elif self.sort_column == 'ocr_confidence':
			self.filtered_invoices.sort(
				key=lambda inv: inv.ocr_confidence if inv.ocr_confidence else 0,
				reverse=not self.sort_ascending
			)

	def build_rows(self) -> List[ft.DataRow]:
		"""Zbuduj wiersze tabeli"""
		rows = []

		for invoice in self.filtered_invoices:
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
						on_click=lambda e, inv=invoice: self.on_view_callback(inv),
						icon_color=AppColors.PRIMARY,
						),
					ft.IconButton(
						icon=AppIcons.EDIT,
						icon_size=20,
						tooltip="Edytuj",
						on_click=lambda e, inv=invoice: self.on_edit_callback(inv),
						icon_color=AppColors.INFO,
						),
					ft.IconButton(
						icon=AppIcons.DELETE,
						icon_size=20,
						tooltip="Usuń",
						on_click=lambda e, inv=invoice: self.on_delete_callback(inv),
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
								ft.Text(invoice.seller_name, size=13, color="#424242"),
								*badges,
								],
							spacing=4,
							alignment=ft.MainAxisAlignment.CENTER,
							)
						),
					ft.DataCell(ft.Text(invoice.invoice_number, size=13, color="#616161")),
					ft.DataCell(
						ft.Text(
							invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else "-",
							size=13,
							color="#616161"
							)
						),
					ft.DataCell(
						ft.Text(
							f"{invoice.amount:.2f} {invoice.currency}",
							size=13,
							weight=ft.FontWeight.W_500,
							color="#424242"
							)
						),
					ft.DataCell(
						ft.Text(
							invoice.seller_nip or "-",
							size=13,
							color="#757575"
							)
						),
					ft.DataCell(
						ft.Text(
							invoice.bank_account or "-",
							size=13,
							color="#757575"
							)
						),
					ft.DataCell(
						ft.Container(
							content=ft.Text(
								invoice.payment_term if invoice.payment_term else (
									invoice.payment_due_date.strftime('%Y-%m-%d') if invoice.payment_due_date else "-"
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
						ft.Text(
							invoice.created_at.strftime('%Y-%m-%d %H:%M') if invoice.created_at else "-",
							size=13,
							color="#616161"
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
		self.all_invoices = invoices
		self.build_table()
		if self.page:
			self.page.update()
