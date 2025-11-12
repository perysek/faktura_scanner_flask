"""
Widok historii zmian
"""
import flet as ft
from repositories.invoice_repository import InvoiceRepository
from repositories.audit_repository import AuditRepository
from gui.theme import AppColors, AppSpacing, AppTypography, AppStyles, AppIcons


class HistoryView(ft.Column):
	"""Widok historii zmian"""
	
	def __init__(self, page: ft.Page, app):
		super().__init__()
		self.page = page
		self.app = app
		
		# Repositories
		self.invoice_repo = InvoiceRepository()
		self.audit_repo = AuditRepository()
		
		# Style
		self.spacing = AppSpacing.LG
		self.expand = True
		
		# UI
		self.build_ui()
	
	def build_ui(self):
		"""Zbuduj UI"""
		header = ft.Text(
			"Historia zmian",
			size=AppTypography.HEADLINE,
			weight=ft.FontWeight.BOLD,
			)
		
		info = ft.Container(
			content=ft.Column(
				controls=[
					ft.Icon(AppIcons.HISTORY, size=64, color=AppColors.INFO),
					ft.Text(
						"Tutaj będzie wyświetlana historia zmian faktur",
						size=AppTypography.BODY,
						color=AppColors.TEXT_SECONDARY,
						),
					ft.Text(
						"Funkcja w trakcie rozwoju",
						size=AppTypography.LABEL,
						color=AppColors.TEXT_DISABLED,
						),
					],
				horizontal_alignment=ft.CrossAxisAlignment.CENTER,
				spacing=AppSpacing.SM,
				),
			**AppStyles.card(),
			alignment=ft.alignment.center,
			)
		
		self.controls = [
			header,
			ft.Divider(height=1, color=AppColors.DIVIDER),
			info,
			]