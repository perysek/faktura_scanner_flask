"""
Główna aplikacja Flet dla trybu webview
Wrapper that configures the app for webview mode
"""

import flet as ft
from config.settings import APP_TITLE, APP_WIDTH, APP_HEIGHT
from config.database import initialize_database
from gui.theme import AppColors, AppStyles, AppSpacing, AppTypography
from gui.components.navigation_rail import AppNavigationRail
from gui.components.notification_panel import NotificationPanel

# Views - import webview-compatible version of upload view
from gui.views.main_view import MainView
from gui.views.upload_view_webview import UploadViewWebview
from gui.views.edit_view import EditView
from gui.views.history_view import HistoryView
from gui.views.email_settings_view import EmailSettingsView


class FakturaScannerAppWebview:
	"""Główna klasa aplikacji - wersja webview"""

	def __init__(self, page: ft.Page):
		self.page = page
		self.is_webview = True  # Flag indicating webview mode
		self.setup_page()
		self.initialize_database()
		self.build_ui()

	def setup_page(self):
		"""Konfiguracja strony dla webview"""
		self.page.title = APP_TITLE
		self.page.theme = AppStyles.get_theme()
		self.page.bgcolor = AppColors.BACKGROUND
		self.page.padding = 0

		# Webview mode - use responsive sizing
		# Don't set window_width/window_height in web mode

		# Fonts (Roboto jest domyślnym fontem Material Design w Flet)
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

		# Notification Panel (bottom of nav rail)
		self.notification_panel = NotificationPanel()

		# Left panel: Navigation Rail + Notification Panel
		left_panel = ft.Column(
			controls=[
				ft.Container(
					content=self.nav_rail,
					expand=True,
				),
				self.notification_panel,
			],
			spacing=0,
			expand=True,
		)

		# Content area (prawa strona) - with scrolling
		self.content_column = ft.Column(
			controls=[],
			expand=True,
			#scroll=ft.ScrollMode.AUTO,
			alignment=ft.MainAxisAlignment.START
		)

		self.content_area = ft.Container(
			content=self.content_column,
			expand=True,
			bgcolor=AppColors.BACKGROUND,
			padding=AppSpacing.MD,
		)

		# Layout: Navigation | Content
		main_layout = ft.Row(
			controls=[
				# Lewy panel (Navigation + Notifications)
				ft.Container(
					content=left_panel,
					bgcolor="#F5F5F5",  # Light grey background
					border=ft.border.all(1, "#BDBDBD"),  # Dark grey border
					border_radius=0,
					alignment=ft.Alignment(x=0, y=0)
				),

				# Główna treść
				self.content_area,
			],
			alignment=ft.MainAxisAlignment.SPACE_EVENLY,
			expand=True
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

					# Info badge
					ft.Container(
						content=ft.Text(
							"WEBVIEW MODE",
							size=10,
							weight=ft.FontWeight.BOLD,
							color="white",
						),
						bgcolor=AppColors.WARNING,
						padding=ft.padding.symmetric(horizontal=8, vertical=4),
						border_radius=4,
					),

					# Version
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
			height=56,
		)

	def on_nav_change(self, e):
		"""Zmiana w nawigacji"""
		self.load_view(e.control.selected_index)

	def load_view(self, index: int):
		"""Załaduj widok na podstawie indeksu"""
		# Mapa indeksów → views (use webview-compatible upload view)
		views = {
			0: MainView(self.page, self, self.notification_panel),
			1: UploadViewWebview(self.page, self, self.notification_panel),  # Webview version
			2: self.create_export_view(),  # Uproszczony view
			3: HistoryView(self.page, self, self.notification_panel),
			4: EmailSettingsView(self.page, self, self.notification_panel),
		}

		view = views.get(index)
		if view:
			# Clear and add new view to scrollable column
			self.content_column.controls.clear()
			self.content_column.controls.append(view)
			self.content_column.alignment=ft.MainAxisAlignment.START
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
			modal=True,
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


def create_app_webview(page: ft.Page):
	"""Entry point dla Flet w trybie webview"""
	FakturaScannerAppWebview(page)
