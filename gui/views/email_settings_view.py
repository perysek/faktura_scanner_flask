"""
Email account settings view
"""
import flet as ft
from datetime import date, timedelta
from config.email_settings import EmailSettings
from gui.theme import AppColors, AppIcons, AppSpacing, AppTypography, AppStyles


class EmailSettingsView(ft.Column):
	"""Email account settings configuration view"""

	def __init__(self, page: ft.Page, app):
		super().__init__()
		self.page = page
		self.app = app

		# Email settings manager
		self.email_settings = EmailSettings()

		# Style
		self.spacing = AppSpacing.LG
		self.expand = True

		# UI
		self.build_ui()
		self.load_current_settings()

	def build_ui(self):
		"""Build UI"""
		# Header
		header = ft.Row(
			controls=[
				ft.Text(
					"E-mail Account Settings",
					size=AppTypography.HEADLINE,
					weight=ft.FontWeight.BOLD,
					color=AppColors.TEXT_PRIMARY,
				),
			],
		)

		# Info text
		info_text = ft.Container(
			content=ft.Row(
				controls=[
					ft.Icon(AppIcons.INFO, size=20, color=AppColors.INFO),
					ft.Text(
						"Configure your email account to automatically import invoice PDFs from emails.",
						size=AppTypography.BODY,
						color=AppColors.TEXT_SECONDARY,
					),
				],
				spacing=AppSpacing.SM,
			),
			**AppStyles.card(),
		)

		# Form fields
		self.email_field = ft.TextField(
			label="Email Address",
			hint_text="example@gmail.com",
			prefix_icon=ft.Icons.EMAIL,
			**AppStyles.text_field()
		)

		self.password_field = ft.TextField(
			label="Password",
			hint_text="Your email password or app-specific password",
			prefix_icon=ft.Icons.LOCK,
			password=True,
			can_reveal_password=True,
			**AppStyles.text_field()
		)

		self.imap_server_field = ft.TextField(
			label="IMAP Server",
			hint_text="imap.gmail.com",
			prefix_icon=ft.Icons.DNS,
			**AppStyles.text_field()
		)

		self.imap_port_field = ft.TextField(
			label="IMAP Port",
			hint_text="993",
			prefix_icon=ft.Icons.SETTINGS_INPUT_COMPONENT,
			keyboard_type=ft.KeyboardType.NUMBER,
			**AppStyles.text_field()
		)

		# Date fields
		self.from_date_field = ft.TextField(
			label="Search From Date",
			hint_text="YYYY-MM-DD",
			prefix_icon=ft.Icons.CALENDAR_TODAY,
			**AppStyles.text_field()
		)

		self.to_date_field = ft.TextField(
			label="Search To Date",
			hint_text="YYYY-MM-DD",
			prefix_icon=ft.Icons.CALENDAR_TODAY,
			value=date.today().isoformat(),
			**AppStyles.text_field()
		)

		# Helper text for Gmail users
		gmail_help = ft.Container(
			content=ft.Column(
				controls=[
					ft.Text(
						"Gmail Users:",
						size=AppTypography.BODY,
						weight=ft.FontWeight.BOLD,
						color=AppColors.WARNING,
					),
					ft.Text(
						"• IMAP Server: imap.gmail.com",
						size=AppTypography.LABEL,
						color=AppColors.TEXT_SECONDARY,
					),
					ft.Text(
						"• IMAP Port: 993",
						size=AppTypography.LABEL,
						color=AppColors.TEXT_SECONDARY,
					),
					ft.Text(
						"• Use App-specific password (not your regular Gmail password)",
						size=AppTypography.LABEL,
						color=AppColors.TEXT_SECONDARY,
					),
					ft.Text(
						"• Enable IMAP in Gmail settings",
						size=AppTypography.LABEL,
						color=AppColors.TEXT_SECONDARY,
					),
				],
				spacing=AppSpacing.XS,
			),
			bgcolor=AppColors.SURFACE_VARIANT,
			padding=AppSpacing.MD,
			border_radius=8,
		)

		# Buttons
		self.save_button = ft.ElevatedButton(
			"Save Configuration",
			icon=AppIcons.SAVE,
			on_click=self.save_configuration,
			**AppStyles.button_primary()
		)

		self.test_button = ft.ElevatedButton(
			"Test Connection",
			icon=ft.Icons.WIFI_FIND,
			on_click=self.test_connection,
			**AppStyles.button_secondary()
		)

		buttons_row = ft.Row(
			controls=[
				self.save_button,
				self.test_button,
			],
			spacing=AppSpacing.SM,
		)

		# Form container
		form_container = ft.Container(
			content=ft.Column(
				controls=[
					self.email_field,
					self.password_field,
					self.imap_server_field,
					self.imap_port_field,
					ft.Divider(height=1, color=AppColors.DIVIDER),
					ft.Text(
						"Search Period",
						size=AppTypography.TITLE,
						weight=ft.FontWeight.BOLD,
						color=AppColors.TEXT_PRIMARY,
					),
					self.from_date_field,
					self.to_date_field,
					ft.Divider(height=1, color=AppColors.DIVIDER),
					buttons_row,
				],
				spacing=AppSpacing.MD,
			),
			**AppStyles.card(),
		)

		# Assemble view
		self.controls = [
			header,
			ft.Divider(height=1, color=AppColors.DIVIDER),
			info_text,
			form_container,
			gmail_help,
		]

	def load_current_settings(self):
		"""Load current settings into form fields"""
		settings = self.email_settings.get_settings()

		self.email_field.value = settings.get("email_address", "")
		self.password_field.value = settings.get("password", "")
		self.imap_server_field.value = settings.get("imap_server", "imap.gmail.com")
		self.imap_port_field.value = str(settings.get("imap_port", 993))
		self.from_date_field.value = settings.get("search_from_date", "")
		self.to_date_field.value = settings.get("search_to_date", date.today().isoformat())

		self.page.update()

	def save_configuration(self, e):
		"""Save email configuration"""
		try:
			# Validate port
			try:
				port = int(self.imap_port_field.value)
			except ValueError:
				self.show_error("Invalid Port", "IMAP port must be a number")
				return

			# Create settings dict
			settings = {
				"email_address": self.email_field.value,
				"password": self.password_field.value,
				"imap_server": self.imap_server_field.value,
				"imap_port": port,
				"search_from_date": self.from_date_field.value,
				"search_to_date": self.to_date_field.value,
			}

			# Save
			if self.email_settings.save_settings(settings):
				self.show_success("Saved", "Email configuration saved successfully")
			else:
				self.show_error("Error", "Failed to save email configuration")

		except Exception as ex:
			self.show_error("Error", str(ex))

	def test_connection(self, e):
		"""Test IMAP connection"""
		try:
			# Validate fields
			if not self.email_field.value or not self.password_field.value:
				self.show_error("Missing Fields", "Please enter email and password")
				return

			if not self.imap_server_field.value:
				self.show_error("Missing Fields", "Please enter IMAP server")
				return

			# Import email service
			from services.email_service import EmailService

			# Test connection
			email_service = EmailService()
			settings = {
				"email_address": self.email_field.value,
				"password": self.password_field.value,
				"imap_server": self.imap_server_field.value,
				"imap_port": int(self.imap_port_field.value),
			}

			if email_service.test_connection(settings):
				self.show_success("Success", "Connection successful!")
			else:
				self.show_error("Connection Failed", "Could not connect to email server")

		except Exception as ex:
			self.show_error("Connection Error", str(ex))

	def show_success(self, title: str, message: str):
		"""Show success message"""
		snackbar = ft.SnackBar(
			content=ft.Text(f"{title}: {message}"),
			bgcolor=AppColors.SUCCESS,
		)
		self.page.snack_bar = snackbar
		snackbar.open = True
		self.page.update()

	def show_error(self, title: str, message: str):
		"""Show error message"""
		snackbar = ft.SnackBar(
			content=ft.Text(f"{title}: {message}"),
			bgcolor=AppColors.ERROR,
		)
		self.page.snack_bar = snackbar
		snackbar.open = True
		self.page.update()
