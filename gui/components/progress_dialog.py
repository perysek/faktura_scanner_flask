"""
Dialog pokazujący postęp przetwarzania faktur
"""
import flet as ft
from gui.theme import AppColors, AppSpacing, AppTypography


class ProgressDialog(ft.AlertDialog):
	"""Dialog postępu przetwarzania"""
	
	def __init__(self):
		super().__init__()
		
		# Style
		self.modal = True
		
		# Progress bar
		self.progress_bar = ft.ProgressBar(
			value=0,
			width=400,
			color=AppColors.PRIMARY,
			bgcolor=AppColors.SURFACE_VARIANT,
			)
		
		# Status text
		self.status_text = ft.Text(
			"Inicjalizacja...",
			size=AppTypography.BODY,
			color=AppColors.TEXT_PRIMARY,
			text_align=ft.TextAlign.CENTER,
			)
		
		# Plik info
		self.file_info = ft.Text(
			"",
			size=AppTypography.LABEL,
			color=AppColors.TEXT_SECONDARY,
			text_align=ft.TextAlign.CENTER,
			)
		
		# Przycisk anuluj
		self.cancel_button = ft.TextButton(
			"Anuluj",
			on_click=self.on_cancel,
			)
		
		# Content
		self.title = ft.Text(
			"Przetwarzanie faktur...",
			size=AppTypography.TITLE,
			weight=ft.FontWeight.BOLD,
			)
		
		self.content = ft.Container(
			content=ft.Column(
				controls=[
					self.status_text,
					self.file_info,
					ft.Container(height=AppSpacing.MD),
					self.progress_bar,
					],
				horizontal_alignment=ft.CrossAxisAlignment.CENTER,
				spacing=AppSpacing.SM,
				),
			width=450,
			padding=AppSpacing.MD,
			)
		
		self.actions = [self.cancel_button]
		
		# Callback
		self.on_cancel_callback = None
	
	def update_progress(
			self, current: int, total: int, filename: str, status: str
			):
		"""
		Aktualizuj postęp

		Args:
			current: Numer aktualnego pliku (1-based)
			total: Całkowita liczba plików
			filename: Nazwa aktualnego pliku
			status: Status (np. "Konwersja PDF...", "Ekstrakcja danych...")
		"""
		progress = current / total if total > 0 else 0
		
		self.progress_bar.value = progress
		self.status_text.value = status
		self.file_info.value = f"Plik {current}/{total}: {filename}"
		
		if hasattr(self, 'page') and self.page:
			self.page.update()
	
	def set_complete(self):
		"""Ustaw jako zakończone"""
		self.progress_bar.value = 1.0
		self.status_text.value = "Zakończono!"
		self.status_text.color = AppColors.SUCCESS
		self.cancel_button.text = "Zamknij"
		
		if hasattr(self, 'page') and self.page:
			self.page.update()
	
	def on_cancel(self, e):
		"""Anuluj przetwarzanie"""
		if self.on_cancel_callback:
			self.on_cancel_callback()
		self.open = False