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
	"""Tabela faktur z sortowaniem, filtrowaniem i zablokowanym nagłówkiem"""
	
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
		
		# Expansion ratios for columns
		self.column_expansions = {
			'seller_name': 3,
			'invoice_number': 3,
			'invoice_date': 2,
			'amount': 2,
			'seller_nip': 2,
			'bank_account': 3,
			'payment_due_date': 2,
			'status': 3,
			'created_at': 2,
			'ocr_confidence': 1,
			'actions': 2,
			}
		
		# Container to hold just the data rows
		# This enables the "Fixed Header" effect:
		# 1. This container scrolls internally (scroll=ADAPTIVE)
		# 2. This container expands to fill available vertical space (expand=True)
		# 3. The header is OUTSIDE this container, so it stays top
		self.data_container = ft.Column(
			scroll=ft.ScrollMode.ADAPTIVE,
			expand=True,
			spacing=0
			)
		
		# Main column settings
		self.spacing = 0
		self.expand = True  # The Table component itself must expand
		
		# Build the table
		self.build_table()
	
	def build_table(self):
		"""Zbuduj tabelę z niestandardowymi nagłówkami"""
		# Apply filters and sorting
		self.apply_filters()
		self.apply_sorting()
		
		# Clear and add to column
		self.controls.clear()
		
		# 1. Add Header Row (Fixed at the top)
		self.controls.append(self.build_header_row())
		
		# 2. Build Data Rows inside the scrollable container
		self.data_container.controls = self.build_data_rows()
		
		# 3. Add the scrollable data container
		self.controls.append(
			ft.Container(
				content=self.data_container,
				expand=True,  # Fill remaining height
				border=ft.border.only(top=ft.BorderSide(1, "#E0E0E0"))
				)
			)
	
	def build_header_row(self) -> ft.Container:
		"""Zbuduj wiersz nagłówka"""
		cells = [
			self.create_column_header(
				"Sprzedawca", "seller_name", with_search=True,
				expand=self.column_expansions['seller_name']
				),
			self.create_simple_header(
				"Nr Faktury",
				expand=self.column_expansions['invoice_number']
				),
			self.create_column_header(
				"Data", "invoice_date", with_search=True,
				expand=self.column_expansions['invoice_date']
				),
			self.create_column_header(
				"Kwota", "amount", with_search=True,
				expand=self.column_expansions['amount']
				),
			self.create_simple_header(
				"NIP",
				expand=self.column_expansions['seller_nip']
				),
			self.create_simple_header(
				"Konto",
				expand=self.column_expansions['bank_account']
				),
			self.create_column_header(
				"Płatność do:", "payment_due_date", with_search=True,
				expand=self.column_expansions['payment_due_date']
				),
			self.create_column_header(
				"Status", "status",
				expand=self.column_expansions['status']
				),
			self.create_column_header(
				"Dodano:", "created_at", with_search=True,
				expand=self.column_expansions['created_at']
				),
			self.create_simple_header(
				"OCR",
				expand=self.column_expansions['ocr_confidence']
				),
			self.create_simple_header(
				"Akcje",
				expand=self.column_expansions['actions']
				),
			]
		
		header_row = ft.Row(
			controls=cells,
			spacing=0
			)
		
		return ft.Container(
			content=header_row,
			height=80,  # Adjusted for normal search field height
			bgcolor="#F5F5F5",
			)
	
	@staticmethod
	def create_simple_header(label: str, expand: int = 1) -> ft.Container:
		"""Stwórz komórkę nagłówka"""
		# Invisible sort button to match layout
		invisible_sort_button = ft.IconButton(
			icon=ft.Icons.UNFOLD_MORE,
			icon_size=14,
			icon_color="#F5F5F5",
			disabled=True,
			style=ft.ButtonStyle(padding=ft.padding.all(4)),
			)
		
		# Header row
		header_row = ft.Row(
			controls=[
				ft.Text(
					label,
					weight=ft.FontWeight.W_600,
					size=12,
					color="#424242"
					),
				invisible_sort_button,
				],
			spacing=2,
			alignment=ft.MainAxisAlignment.START
			)
		
		# Invisible search field to match layout
		invisible_search = ft.TextField(
			text_size=12,
			height=37,
			content_padding=ft.padding.symmetric(horizontal=2, vertical=4),
			border_width=1,
			visible=False,
			)
		
		header_column = ft.Column(
			controls=[
				header_row,
				ft.Container(
					content=invisible_search,
					padding=ft.padding.symmetric(horizontal=5, vertical=2)
					)
				],
			spacing=2,
			tight=True,
			horizontal_alignment=ft.CrossAxisAlignment.CENTER,
			alignment=ft.MainAxisAlignment.START,
			)
		
		return ft.Container(
			content=header_column,
			expand=expand,
			padding=ft.padding.symmetric(horizontal=4, vertical=4),
			alignment=ft.alignment.top_left,
			border=ft.border.only(right=ft.BorderSide(1, "#EEEEEE"))
			)
	
	def create_column_header(
			self, label: str, field_name: str, with_search: bool = False,
			expand: int = 1
			) -> ft.Container:
		"""Stwórz komórkę nagłówka z sortowaniem i opcjonalnym wyszukiwaniem"""
		# Sort icon
		sort_icon = ft.Icons.UNFOLD_MORE
		if self.sort_column == field_name:
			sort_icon = ft.Icons.ARROW_UPWARD if self.sort_ascending else ft.Icons.ARROW_DOWNWARD
		
		# Header with sort button
		header_row = ft.Row(
			controls=[
				ft.Text(
					label,
					weight=ft.FontWeight.W_600,
					size=12,
					color="#424242",
					),
				ft.IconButton(
					icon=sort_icon,
					icon_size=14,
					tooltip=f"Sortuj {label}",
					on_click=lambda e, field=field_name: self.toggle_sort(
						field
						),
					icon_color="#2196F3" if self.sort_column == field_name else "#9E9E9E",
					style=ft.ButtonStyle(padding=ft.padding.all(2)),
					),
				],
			spacing=2,
			alignment=ft.MainAxisAlignment.START,
			)
		
		if with_search:
			search_field = ft.TextField(
				hint_text="Search...",
				value=self.column_filters.get(field_name, ''),
				on_change=lambda e, field=field_name: self.on_filter_change(
					field, e.control.value
					),
				text_size=12,
				height=37,
				content_padding=ft.padding.symmetric(horizontal=4, vertical=4),
				border_color="#BDBDBD",
				focused_border_color="#90CAF9",
				border_width=1,
				border_radius=3,
				bgcolor="#FFFFFF",
				#filled=True,
				dense=True,
				cursor_color="#2196F3",
				)
			
			header_column = ft.Column(
				controls=[
					header_row,
					ft.Container(
						content=search_field,
						padding=ft.padding.Padding(
							left=0, top=2, right=0, bottom=2
							)
						)
					],
				spacing=2,
				tight=True,
				horizontal_alignment=ft.CrossAxisAlignment.START,
				alignment=ft.MainAxisAlignment.START,
				)
			return ft.Container(
				content=header_column,
				expand=expand,
				padding=ft.padding.symmetric(horizontal=0, vertical=4),
				alignment=ft.alignment.top_left,
				border=ft.border.only(right=ft.BorderSide(1, "#EEEEEE"))
				)
		else:
			return ft.Container(
				content=header_row,
				expand=expand,
				padding=ft.padding.symmetric(horizontal=4, vertical=4),
				alignment=ft.alignment.top_left,
				border=ft.border.only(right=ft.BorderSide(1, "#EEEEEE"))
				)
	
	def toggle_sort(self, field_name: str):
		"""Przełącz sortowanie dla kolumny"""
		if self.sort_column == field_name:
			self.sort_ascending = not self.sort_ascending
		else:
			self.sort_column = field_name
			self.sort_ascending = True
		
		self.build_table()
		if self.page:
			self.page.update()
	
	def on_filter_change(self, field_name: str, value: str):
		"""Obsłuż zmianę filtra"""
		self.column_filters[field_name] = value.lower()
		
		self.apply_filters()
		self.apply_sorting()
		
		# Only update the controls in the data_container to keep focus in header
		self.data_container.controls = self.build_data_rows()
		
		if self.page:
			self.page.update()
	
	def apply_filters(self):
		"""Zastosuj filtry do faktur"""
		self.filtered_invoices = self.all_invoices.copy()
		
		for field_name, filter_text in self.column_filters.items():
			if not filter_text:
				continue
			
			if field_name == 'seller_name':
				self.filtered_invoices = [inv for inv in self.filtered_invoices
					if filter_text in (inv.seller_name or '').lower()]
			elif field_name == 'invoice_number':
				self.filtered_invoices = [inv for inv in self.filtered_invoices
					if filter_text in (inv.invoice_number or '').lower()]
			elif field_name == 'invoice_date':
				self.filtered_invoices = [inv for inv in self.filtered_invoices
					if filter_text in (inv.invoice_date.strftime(
						'%Y-%m-%d'
						) if inv.invoice_date else '')]
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
					if filter_text in (inv.payment_due_date.strftime(
						'%Y-%m-%d'
						) if inv.payment_due_date else '') or
					   filter_text in (inv.payment_term or '').lower()]
			elif field_name == 'status':
				self.filtered_invoices = [inv for inv in self.filtered_invoices
					if filter_text in (inv.status or '').lower()]
			elif field_name == 'created_at':
				self.filtered_invoices = [inv for inv in self.filtered_invoices
					if filter_text in (inv.created_at.strftime(
						'%Y-%m-%d %H:%M'
						) if inv.created_at else '')]
			elif field_name == 'ocr_confidence':
				self.filtered_invoices = [inv for inv in self.filtered_invoices
					if filter_text in (
						f"{inv.ocr_confidence:.0f}" if inv.ocr_confidence else '')]
	
	def apply_sorting(self):
		"""Zastosuj sortowanie do faktur"""
		if not self.sort_column:
			return
		
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
				key=lambda
					inv: inv.invoice_date if inv.invoice_date else date.min,
				reverse=not self.sort_ascending
				)
		elif self.sort_column == 'amount':
			self.filtered_invoices.sort(
				key=lambda inv: inv.amount, reverse=not self.sort_ascending
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
				key=lambda
					inv: inv.payment_due_date if inv.payment_due_date else date.min,
				reverse=not self.sort_ascending
				)
		elif self.sort_column == 'status':
			self.filtered_invoices.sort(
				key=lambda inv: (inv.status or '').lower(),
				reverse=not self.sort_ascending
				)
		elif self.sort_column == 'created_at':
			self.filtered_invoices.sort(
				key=lambda
					inv: inv.created_at if inv.created_at else datetime.min,
				reverse=not self.sort_ascending
				)
		elif self.sort_column == 'ocr_confidence':
			self.filtered_invoices.sort(
				key=lambda inv: inv.ocr_confidence if inv.ocr_confidence else 0,
				reverse=not self.sort_ascending
				)
	
	def build_data_rows(self) -> List[ft.Control]:
		"""Zbuduj wiersze danych"""
		rows_controls = []
		
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
			
			actions = ft.Row(
				controls=[
					ft.IconButton(
						icon=AppIcons.VIEW, icon_size=20, tooltip="Podgląd",
						on_click=lambda e, inv=invoice: self.on_view_callback(
							inv
							),
						icon_color=AppColors.PRIMARY,
						),
					ft.IconButton(
						icon=AppIcons.EDIT, icon_size=20, tooltip="Edytuj",
						on_click=lambda e, inv=invoice: self.on_edit_callback(
							inv
							),
						icon_color=AppColors.INFO,
						),
					ft.IconButton(
						icon=AppIcons.DELETE, icon_size=20, tooltip="Usuń",
						on_click=lambda e, inv=invoice: self.on_delete_callback(
							inv
							),
						icon_color=AppColors.ERROR,
						),
					],
				spacing=2,
				alignment=ft.MainAxisAlignment.CENTER
				)
			
			def create_cell(
					control: ft.Control, field_name: str,
					alignment: ft.Alignment = ft.alignment.center_left
					) -> ft.Container:
				return ft.Container(
					content=control,
					expand=self.column_expansions[field_name],
					padding=ft.padding.symmetric(horizontal=6, vertical=4),
					alignment=alignment,
					border=ft.border.only(right=ft.BorderSide(1, "#EEEEEE"))
					)
			
			row = ft.Row(
				controls=[
					create_cell(
						ft.Column(
							controls=[
								ft.Text(
									invoice.seller_name, size=13,
									color="#424242",
									overflow=ft.TextOverflow.ELLIPSIS,
									style=ft.TextStyle(
										weight=ft.FontWeight.W_600
										), no_wrap=True
									),
								*badges,
								],
							spacing=4,
							alignment=ft.MainAxisAlignment.CENTER,
							),
						'seller_name'
						),
					create_cell(
						ft.Text(
							invoice.invoice_number, size=13, color="#616161",
							overflow=ft.TextOverflow.ELLIPSIS, no_wrap=True
							), 'invoice_number'
						),
					create_cell(
						ft.Text(
							invoice.invoice_date.strftime(
								'%Y-%m-%d'
								) if invoice.invoice_date else "-", size=13,
							color="#616161"
							), 'invoice_date', alignment=ft.alignment.center
						),
					create_cell(
						ft.Text(
							f"{invoice.amount:.2f} {invoice.currency}", size=13,
							weight=ft.FontWeight.W_500, color="#424242"
							), 'amount', alignment=ft.alignment.center_right
						),
					create_cell(
						ft.Text(
							invoice.seller_nip or "-", size=13, color="#757575"
							), 'seller_nip'
						),
					create_cell(
						ft.Text(
							invoice.bank_account or "-", size=13,
							color="#757575", overflow=ft.TextOverflow.ELLIPSIS,
							no_wrap=True
							), 'bank_account'
						),
					create_cell(
						ft.Container(
							content=ft.Text(
								invoice.payment_term if invoice.payment_term else (
									invoice.payment_due_date.strftime(
										'%Y-%m-%d'
										) if invoice.payment_due_date else "-"),
								size=13,
								color="white" if (
											invoice.payment_due_date and invoice.payment_due_date < date.today() and invoice.status != "Opłacona") else AppColors.TEXT_PRIMARY
								),
							bgcolor=AppColors.ERROR if (
										invoice.payment_due_date and invoice.payment_due_date < date.today() and invoice.status != "Opłacona") else None,
							padding=ft.padding.symmetric(
								horizontal=6, vertical=2
								),
							border_radius=4,
							),
						'payment_due_date',
						alignment=ft.alignment.center
						),
					create_cell(
						ft.Dropdown(
							value=invoice.status,
							options=[
								ft.dropdown.Option("Nieopłacona",
								                   style=ft.ButtonStyle(
									                   icon_size=10)),
								ft.dropdown.Option("Opłacona")
								],
							dense=True,
							on_change=lambda e,
							                 inv=invoice: self.on_status_change(
								e, inv
								),
							text_size=13,
							content_padding=ft.padding.symmetric(
								horizontal=0, vertical=2
								),
							border_width=0,
							text_align=ft.alignment.center_left,
							expand=False
							),
						'status',
						alignment=ft.alignment.center_left
						),
					create_cell(
						ft.Text(
							invoice.created_at.strftime(
								'%Y-%m-%d %H:%M'
								) if invoice.created_at else "-", size=13,
							color="#616161"
							), 'created_at', alignment=ft.alignment.center
						),
					create_cell(
						ft.Container(
							content=ft.Text(
								f"{invoice.ocr_confidence:.0f}%" if invoice.ocr_confidence else "-",
								size=13,
								color="white" if invoice.ocr_confidence and invoice.ocr_confidence >= 80 else AppColors.TEXT_PRIMARY,
								weight=ft.FontWeight.BOLD
								),
							bgcolor=AppColors.SUCCESS if invoice.ocr_confidence and invoice.ocr_confidence >= 80 else (
								AppColors.WARNING if invoice.ocr_confidence and invoice.ocr_confidence >= 60 else AppColors.ERROR) if invoice.ocr_confidence else None,
							padding=ft.padding.symmetric(
								horizontal=6, vertical=2
								),
							border_radius=3,
							),
						'ocr_confidence',
						alignment=ft.alignment.center_left
						),
					create_cell(
						actions, 'actions', alignment=ft.alignment.center_left
						),
					],
				height=30,
				)
			rows_controls.append(row)
			rows_controls.append(ft.Container(height=1, bgcolor="#EEEEEE"))
		
		return rows_controls
	
	def on_status_change(self, e, invoice: Invoice):
		"""Obsłuż zmianę statusu"""
		try:
			invoice.status = e.control.value
			self.invoice_repo.update(invoice.id, invoice)
			if self.on_refresh_callback:
				self.on_refresh_callback()
		except Exception as ex:
			print(f"❌ Błąd zmiany statusu: {ex}")
			e.control.value = invoice.status
			if e.control.page:
				e.control.page.update()
	
	def update_data(self, invoices: List[Invoice]):
		"""Zaktualizuj dane w tabeli"""
		self.all_invoices = invoices
		self.apply_filters()
		self.apply_sorting()
		
		self.controls[0] = self.build_header_row()
		self.data_container.controls = self.build_data_rows()
		
		if self.page:
			self.page.update()