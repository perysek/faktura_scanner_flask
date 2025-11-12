"""
Theme aplikacji - kolory, fonty, style
"""
import flet as ft


# === KOLORY ===
class AppColors:
	"""Paleta kolorów aplikacji (szarości + niebieskie akcenty)"""
	
	# Tło
	BACKGROUND = "#F5F7FA"  # Jasny szary
	SURFACE = "#FFFFFF"  # Białe karty/panele
	SURFACE_VARIANT = "#E8EDF2"  # Lekko ciemniejszy szary
	
	# Niebieski (akcent)
	PRIMARY = "#4472C4"  # Główny niebieski
	PRIMARY_LIGHT = "#6B9BD9"  # Jasniejszy niebieski
	PRIMARY_DARK = "#2E5A9E"  # Ciemniejszy niebieski
	
	# Tekst
	TEXT_PRIMARY = "#1A1C1E"  # Główny tekst (prawie czarny)
	TEXT_SECONDARY = "#6C757D"  # Drugorzędny tekst (szary)
	TEXT_DISABLED = "#ADB5BD"  # Wyłączony tekst
	
	# Status
	SUCCESS = "#28A745"  # Zielony (sukces)
	WARNING = "#FFC107"  # Żółty (ostrzeżenie)
	ERROR = "#DC3545"  # Czerwony (błąd)
	INFO = "#17A2B8"  # Cyjan (info)
	
	# Obramowania
	BORDER = "#DEE2E6"  # Szare obramowanie
	DIVIDER = "#E9ECEF"  # Linie dzielące
	
	# Hover/Focus
	HOVER = "#F8F9FA"  # Hover na elementach
	SELECTED = "#E3F2FD"  # Wybrane (jasny niebieski)


# === TYPOGRAFIA ===
class AppTypography:
	"""Rozmiary i wagi fontów"""
	
	# Roboto font family
	FONT_FAMILY = "Roboto"
	
	# Rozmiary
	DISPLAY = 32  # Duże nagłówki
	HEADLINE = 24  # Nagłówki sekcji
	TITLE = 20  # Tytuły
	BODY_LARGE = 16  # Główny tekst (większy)
	BODY = 14  # Główny tekst
	LABEL = 12  # Etykiety, opisy
	CAPTION = 11  # Bardzo małe teksty
	
	# Wagi
	LIGHT = ft.FontWeight.W_300
	REGULAR = ft.FontWeight.W_400
	MEDIUM = ft.FontWeight.W_500
	BOLD = ft.FontWeight.W_700


# === SPACING ===
class AppSpacing:
	"""Marginesy i paddingi"""
	XS = 4
	SM = 8
	MD = 16
	LG = 24
	XL = 32
	XXL = 48


# === KOMPONENTY ===
class AppStyles:
	"""Style dla komponentów Flet"""
	
	@staticmethod
	def get_theme() -> ft.Theme:
		"""Główny theme Flet"""
		return ft.Theme(
			color_scheme_seed=AppColors.PRIMARY,
			use_material3=True,
			font_family=AppTypography.FONT_FAMILY,
			)
	
	@staticmethod
	def card(elevated: bool = True) -> dict:
		"""Style dla kart/paneli (compatible with ft.Container)"""
		if elevated:
			return {
				"bgcolor": AppColors.SURFACE,
				"border_radius": 12,
				"padding": AppSpacing.MD,
				"shadow": ft.BoxShadow(
					spread_radius=1,
					blur_radius=4,
					color=ft.Colors.with_opacity(0.1, AppColors.TEXT_PRIMARY),
					offset=ft.Offset(0, 2),
				),
				"border": ft.border.all(1, AppColors.BORDER)
				}
		else:
			return {
				"bgcolor": AppColors.SURFACE,
				"border_radius": 12,
				"padding": AppSpacing.MD,
				"border": ft.border.all(1, AppColors.BORDER)
				}
	
	@staticmethod
	def button_primary() -> dict:
		"""Style dla głównego przycisku"""
		return {
			"bgcolor": AppColors.PRIMARY,
			"color": "white",
			"height": 40,
			"style": ft.ButtonStyle(
				shape=ft.RoundedRectangleBorder(radius=8),
				)
			}
	
	@staticmethod
	def button_secondary() -> dict:
		"""Style dla drugorzędnego przycisku"""
		return {
			"bgcolor": AppColors.SURFACE_VARIANT,
			"color": AppColors.TEXT_PRIMARY,
			"height": 40,
			"style": ft.ButtonStyle(
				shape=ft.RoundedRectangleBorder(radius=8),
				)
			}
	
	@staticmethod
	def text_field() -> dict:
		"""Style dla pól tekstowych"""
		return {
			"border_color": AppColors.BORDER,
			"focused_border_color": AppColors.PRIMARY,
			"bgcolor": AppColors.SURFACE,
			"height": 48,
			"text_size": AppTypography.BODY,
			"border_radius": 8,
			}
	
	@staticmethod
	def data_table() -> dict:
		"""Style dla tabeli danych"""
		return {
			"border": ft.border.all(1, AppColors.BORDER),
			"border_radius": 8,
			"heading_row_color": AppColors.SURFACE_VARIANT,
			"heading_row_height": 48,
			"data_row_max_height": 60,
			"horizontal_lines": ft.BorderSide(1, AppColors.DIVIDER),
			}


# === IKONY ===
class AppIcons:
	"""Ikony używane w aplikacji"""
	HOME = ft.Icons.DASHBOARD_ROUNDED
	UPLOAD = ft.Icons.UPLOAD_FILE_ROUNDED
	EXPORT = ft.Icons.FILE_DOWNLOAD_ROUNDED
	HISTORY = ft.Icons.HISTORY_ROUNDED
	EDIT = ft.Icons.EDIT_ROUNDED
	DELETE = ft.Icons.DELETE_ROUNDED
	VIEW = ft.Icons.VISIBILITY_ROUNDED
	SEARCH = ft.Icons.SEARCH_ROUNDED
	ADD = ft.Icons.ADD_ROUNDED
	SAVE = ft.Icons.SAVE_ROUNDED
	CANCEL = ft.Icons.CANCEL_ROUNDED
	CHECK = ft.Icons.CHECK_CIRCLE_ROUNDED
	WARNING = ft.Icons.WARNING_ROUNDED
	ERROR = ft.Icons.ERROR_ROUNDED
	INFO = ft.Icons.INFO_ROUNDED
	PDF = ft.Icons.PICTURE_AS_PDF_ROUNDED
	REFRESH = ft.Icons.REFRESH_ROUNDED