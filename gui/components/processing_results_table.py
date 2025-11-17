"""
Komponent tabeli wyników przetwarzania faktur
"""
import flet as ft
from typing import List, Callable
from database.models import Invoice
from gui.theme import AppColors, AppIcons, AppSpacing


class ProcessingResultsTable(ft.DataTable):
	"""Kompaktowa tabela wyników przetwarzania"""

	def __init__(
			self,
			processed_invoices: List[tuple],  # (invoice, validation, raw_text)
			on_delete: Callable[[int], None],
			on_save: Callable[[int], None],
			on_view_ocr: Callable[[str], None]
			):
		# Store callbacks and data
		self.processed_invoices = processed_invoices
		self.on_delete_callback = on_delete
		self.on_save_callback = on_save
		self.on_view_ocr_callback = on_view_ocr

		# Define compact columns
		columns = [
			ft.DataColumn(ft.Text("Status", weight=ft.FontWeight.BOLD, size=11)),
			ft.DataColumn(ft.Text("Sprzedawca", weight=ft.FontWeight.BOLD, size=11)),
			ft.DataColumn(ft.Text("Nr Faktury", weight=ft.FontWeight.BOLD, size=11)),
			ft.DataColumn(ft.Text("Data", weight=ft.FontWeight.BOLD, size=11)),
			ft.DataColumn(ft.Text("Kwota", weight=ft.FontWeight.BOLD, size=11)),
			ft.DataColumn(ft.Text("NIP", weight=ft.FontWeight.BOLD, size=11)),
			ft.DataColumn(ft.Text("Termin", weight=ft.FontWeight.BOLD, size=11)),
			ft.DataColumn(ft.Text("OCR", weight=ft.FontWeight.BOLD, size=11)),
			ft.DataColumn(ft.Text("Ostrzeżenia", weight=ft.FontWeight.BOLD, size=11)),
			ft.DataColumn(ft.Text("Akcje", weight=ft.FontWeight.BOLD, size=11)),
		]

		# Build rows
		rows = self.build_rows()

		# Initialize parent DataTable with compact settings
		super().__init__(
			columns=columns,
			rows=rows,
			border=ft.border.all(1, AppColors.BORDER),
			border_radius=6,
			heading_row_color=AppColors.SURFACE_VARIANT,
			heading_row_height=32,
			data_row_max_height=36,
			data_row_min_height=36,
			horizontal_lines=ft.BorderSide(1, AppColors.DIVIDER),
			vertical_lines=ft.BorderSide(1, AppColors.DIVIDER),
			column_spacing=4,
		)

	def build_rows(self) -> List[ft.DataRow]:
		"""Zbuduj wiersze tabeli"""
		rows = []

		for index, (invoice, validation, raw_text) in enumerate(self.processed_invoices):
			# Determine status
			has_errors = len(validation['errors']) > 0
			has_warnings = len(validation['warnings']) > 0

			# Status icon and color
			if has_errors:
				status_icon = AppIcons.ERROR
				status_color = AppColors.ERROR
				status_tooltip = "Błędy walidacji"
			elif has_warnings:
				status_icon = AppIcons.WARNING
				status_color = AppColors.WARNING
				status_tooltip = "Ostrzeżenia"
			else:
				status_icon = AppIcons.CHECK
				status_color = AppColors.SUCCESS
				status_tooltip = "OK"

			# Warnings/errors summary
			warnings_controls = []

			# Show errors
			for error in validation['errors']:
				warnings_controls.append(
					ft.Container(
						content=ft.Row(
							controls=[
								ft.Icon(AppIcons.ERROR, size=10, color=AppColors.ERROR),
								ft.Text(error, size=10, color=AppColors.ERROR),
							],
							spacing=2,
							tight=True,
						),
						padding=ft.padding.symmetric(vertical=1),
					)
				)

			# Show warnings (limit to first 2 if there are many)
			display_warnings = validation['warnings'][:2] if len(validation['warnings']) > 2 else validation['warnings']
			for warning in display_warnings:
				warnings_controls.append(
					ft.Container(
						content=ft.Row(
							controls=[
								ft.Icon(AppIcons.WARNING, size=10, color=AppColors.WARNING),
								ft.Text(warning, size=10, color=AppColors.WARNING, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
							],
							spacing=2,
							tight=True,
						),
						padding=ft.padding.symmetric(vertical=1),
					)
				)

			# If more warnings, show count
			if len(validation['warnings']) > 2:
				warnings_controls.append(
					ft.Text(
						f"... +{len(validation['warnings']) - 2} więcej",
						size=9,
						color=AppColors.TEXT_SECONDARY,
						italic=True,
					)
				)

			# If no warnings/errors, show OK
			if not warnings_controls:
				warnings_controls.append(
					ft.Text("Brak", size=10, color=AppColors.TEXT_SECONDARY)
				)

			# Action buttons
			actions = ft.Row(
				controls=[
					ft.IconButton(
						icon=AppIcons.VIEW,
						icon_size=16,
						tooltip="Pokaż OCR",
						on_click=lambda e, text=raw_text: self.on_view_ocr_callback(text),
						icon_color=AppColors.INFO,
					),
					ft.IconButton(
						icon=AppIcons.DELETE,
						icon_size=16,
						tooltip="Usuń",
						on_click=lambda e, idx=index: self.on_delete_callback(idx),
						icon_color=AppColors.ERROR,
					),
					ft.IconButton(
						icon=AppIcons.SAVE,
						icon_size=16,
						tooltip="Zapisz" if not has_errors else "Nie można zapisać (błędy)",
						on_click=lambda e, idx=index: self.on_save_callback(idx) if not has_errors else None,
						icon_color=AppColors.SUCCESS if not has_errors else AppColors.TEXT_DISABLED,
						disabled=has_errors,
					),
				],
				spacing=2,
				tight=True,
			)

			row = ft.DataRow(
				cells=[
					# Status
					ft.DataCell(
						ft.Icon(
							status_icon,
							size=16,
							color=status_color,
							tooltip=status_tooltip,
						)
					),
					# Sprzedawca
					ft.DataCell(
						ft.Text(
							invoice.seller_name,
							size=11,
							max_lines=1,
							overflow=ft.TextOverflow.ELLIPSIS,
							tooltip=invoice.seller_name,
						)
					),
					# Nr Faktury
					ft.DataCell(
						ft.Text(
							invoice.invoice_number,
							size=11,
							weight=ft.FontWeight.W_500,
						)
					),
					# Data
					ft.DataCell(
						ft.Text(
							invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else "-",
							size=11,
						)
					),
					# Kwota
					ft.DataCell(
						ft.Text(
							f"{invoice.amount:.2f} {invoice.currency}",
							size=11,
							weight=ft.FontWeight.W_500,
						)
					),
					# NIP
					ft.DataCell(
						ft.Text(
							invoice.seller_nip or "-",
							size=11,
						)
					),
					# Termin płatności
					ft.DataCell(
						ft.Text(
							invoice.payment_due_date.strftime('%Y-%m-%d') if invoice.payment_due_date else "-",
							size=11,
						)
					),
					# OCR Confidence
					ft.DataCell(
						ft.Container(
							content=ft.Text(
								f"{invoice.ocr_confidence:.0f}%" if invoice.ocr_confidence else "-",
								size=10,
								color="white" if invoice.ocr_confidence and invoice.ocr_confidence >= 80 else AppColors.TEXT_PRIMARY,
								weight=ft.FontWeight.BOLD,
							),
							bgcolor=AppColors.SUCCESS if invoice.ocr_confidence and invoice.ocr_confidence >= 80 else (
								AppColors.WARNING if invoice.ocr_confidence and invoice.ocr_confidence >= 60 else AppColors.ERROR
							) if invoice.ocr_confidence else None,
							padding=ft.padding.symmetric(horizontal=4, vertical=2),
							border_radius=3,
						)
					),
					# Warnings/Errors
					ft.DataCell(
						ft.Column(
							controls=warnings_controls,
							spacing=1,
							tight=True,
						)
					),
					# Actions
					ft.DataCell(actions),
				],
			)
			rows.append(row)

		return rows
