"""
Główna aplikacja Flet z routing i layout
"""
import flet as ft
from config.settings import APP_TITLE, APP_WIDTH, APP_HEIGHT
from config.database import initialize_database
from gui.theme import AppColors, AppStyles, AppSpacing, AppTypography
from gui.components.navigation_rail import AppNavigationRail

# Views (zaimportujemy po utworzeniu)
from gui.views.main_view import MainView
from gui.views.upload_view import UploadView
from gui.views.edit_view import EditView
from gui.views.history_view import HistoryView


class FakturaScannerApp:
	"""Główna klasa aplikacji"""
	
	def __init__(self, page: ft.Page):
		self.page = page
		self.setup_page()
		self.initialize_database()
		self.build_ui()
	
	def setup_page(self):
		"""Konfiguracja strony"""
		self.page.title = APP_TITLE
		self.page.theme = AppStyles.get_theme()
		self.page.bgcolor = AppColors.BACKGROUND
		self.page.padding = 0
		self.page.window_width = APP_WIDTH
		self.page.window_height = APP_HEIGHT
		self.page.window_min_width = 1000
		self.page.window_min_height = 600
		
		# Fonts (Roboto jest domyślnym fontem Material Design w Flet)
		# Jeśli chcesz użyć custom Roboto:
		self.page.fonts = {
			"Roboto": "https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap"
			}
	
	def initialize_database(self):
		"""Inicjalizuj bazę danych"""
		try:
			initialize_database()
			print("✅ Baza danych gotowa")
		except Exception as e:
			print(f"❌ Błąd inicjalizacji bazy: {e}")
			self.show_error_dialog("Błąd inicjalizacji bazy danych", str(e))
	
	def build_ui(self):
		"""Zbuduj główny interfejs"""
		# Navigation Rail (lewy panel)
		self.nav_rail = AppNavigationRail(on_change=self.on_nav_change)
		
		# Content area (prawa strona) - with scrolling
		self.content_column = ft.Column(
			controls=[],
			expand=True,
			scroll=ft.ScrollMode.AUTO,
			)

		self.content_area = ft.Container(
			content=self.content_column,
			expand=True,
			bgcolor=AppColors.BACKGROUND,
			padding=AppSpacing.LG,
			)
		
		# Layout: Navigation | Content
		main_layout = ft.Row(
			controls=[
				# Lewy panel
				ft.Container(
					content=self.nav_rail,
					bgcolor=AppColors.SURFACE,
					border=ft.border.only(
						right=ft.BorderSide(1, AppColors.BORDER)
						),
					),
				
				# Separator
				ft.VerticalDivider(width=1, color=AppColors.DIVIDER),
				
				# Główna treść
				self.content_area,
				],
			spacing=0,
			expand=True,
			)
		
		# Header
		header = self.build_header()
		
		# Finalna struktura
		self.page.add(
			ft.Column(
				controls=[
					header,
					ft.Divider(height=1, color=AppColors.DIVIDER),
					main_layout,
					],
				spacing=0,
				expand=True,
				)
			)
		
		# Załaduj domyślny widok
		self.load_view(0)
	
	def build_header(self) -> ft.Container:
		"""Zbuduj nagłówek aplikacji"""
		return ft.Container(
			content=ft.Row(
				controls=[
					# Logo + Tytuł
					ft.Row(
						controls=[
							ft.Icon(
								ft.Icons.RECEIPT_LONG_ROUNDED,
								size=32,
								color=AppColors.PRIMARY
								),
							ft.Text(
								APP_TITLE,
								size=AppTypography.TITLE,
								weight=ft.FontWeight.BOLD,
								color=AppColors.TEXT_PRIMARY,
								),
							],
						spacing=AppSpacing.SM,
						),
					
					# Spacer
					ft.Container(expand=True),
					
					# Info (opcjonalnie)
					ft.Text(
						"v1.0.0",
						size=AppTypography.CAPTION,
						color=AppColors.TEXT_SECONDARY,
						),
					],
				alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
				),
			bgcolor=AppColors.SURFACE,
			padding=AppSpacing.MD,
			height=64,
			)
	
	def on_nav_change(self, e):
		"""Zmiana w nawigacji"""
		self.load_view(e.control.selected_index)
	
	def load_view(self, index: int):
		"""Załaduj widok na podstawie indeksu"""
		# Mapa indeksów → views
		views = {
			0: MainView(self.page, self),
			1: UploadView(self.page, self),
			2: self.create_export_view(),  # Uproszczony view
			3: HistoryView(self.page, self),
			}

		view = views.get(index)
		if view:
			# Clear and add new view to scrollable column
			self.content_column.controls.clear()
			self.content_column.controls.append(view)
			self.page.update()
	
	def create_export_view(self) -> ft.Control:
		"""Tymczasowy widok eksportu (do rozbudowy)"""
		return ft.Container(
			content=ft.Column(
				controls=[
					ft.Text(
						"Eksport Danych",
						size=AppTypography.HEADLINE,
						weight=ft.FontWeight.BOLD,
						),
					ft.Text(
						"Funkcja eksportu zostanie zaimplementowana w widoku listy faktur.",
						color=AppColors.TEXT_SECONDARY,
						),
					],
				spacing=AppSpacing.MD,
				),
			padding=AppSpacing.LG,
			)
	
	def show_error_dialog(self, title: str, message: str):
		"""Pokaż dialog z błędem"""
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
	
	def refresh_main_view(self):
		"""Odśwież widok główny (po dodaniu faktury)"""
		self.nav_rail.selected_index = 0
		self.load_view(0)


def create_app(page: ft.Page):
	"""Entry point dla Flet"""
	FakturaScannerApp(page)