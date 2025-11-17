"""
Notification Panel Component - Fixed panel showing last 3 notifications
"""

import flet as ft
from datetime import datetime
from typing import List, Dict
from gui.theme import AppColors, AppIcons, AppSpacing, AppTypography


class NotificationPanel(ft.Container):
	"""Panel showing recent notifications at the bottom of navigation rail"""

	def __init__(self):
		super().__init__()

		# Notifications list (max 3)
		self.notifications: List[Dict] = []

		# Style
		self.width = 260  # Match navigation rail width
		self.bgcolor = "#FAFAFA"
		self.border = ft.border.only(top=ft.BorderSide(1, "#BDBDBD"))
		self.padding = ft.padding.all(AppSpacing.SM)

		# Build UI
		self.build_ui()

	def build_ui(self):
		"""Build notification panel UI"""
		# Header with clear button
		self.header = ft.Row(
			controls=[
				ft.Text(
					"Powiadomienia",
					size=12,
					weight=ft.FontWeight.BOLD,
					color=AppColors.TEXT_SECONDARY,
				),
				ft.Container(expand=True),
				ft.IconButton(
					icon=ft.Icons.CLEAR_ALL,
					icon_size=16,
					tooltip="Wyczyść wszystkie",
					on_click=self.clear_all,
					icon_color=AppColors.TEXT_SECONDARY,
				),
			],
			spacing=AppSpacing.XS,
		)

		# Notifications container
		self.notifications_column = ft.Column(
			controls=[],
			spacing=AppSpacing.XS,
			scroll=ft.ScrollMode.AUTO,
		)

		# Content
		self.content = ft.Column(
			controls=[
				self.header,
				ft.Divider(height=1, color=AppColors.DIVIDER),
				ft.Container(
					content=self.notifications_column,
					height=180,  # Fixed height for up to 3 notifications
				),
			],
			spacing=AppSpacing.XS,
		)

	def add_notification(self, message: str, notification_type: str = "info"):
		"""
		Add a notification to the panel

		Args:
			message: Notification message
			notification_type: Type of notification ('success', 'error', 'warning', 'info')
		"""
		# Create notification data
		notification = {
			"message": message,
			"type": notification_type,
			"timestamp": datetime.now(),
		}

		# Add to list (keep only last 3)
		self.notifications.insert(0, notification)
		if len(self.notifications) > 3:
			self.notifications = self.notifications[:3]

		# Update UI
		self.update_notifications()

	def update_notifications(self):
		"""Update the notifications display"""
		self.notifications_column.controls.clear()

		if not self.notifications:
			# Show empty state
			self.notifications_column.controls.append(
				ft.Container(
					content=ft.Text(
						"Brak powiadomień",
						size=11,
						color=AppColors.TEXT_DISABLED,
						italic=True,
					),
					alignment=ft.alignment.center,
					height=60,
				)
			)
		else:
			# Show notifications
			for notif in self.notifications:
				self.notifications_column.controls.append(
					self._create_notification_item(notif)
				)

		self.update()

	def _create_notification_item(self, notification: Dict) -> ft.Container:
		"""Create a notification item widget"""
		# Determine icon and color based on type
		icon_map = {
			"success": (AppIcons.CHECK, AppColors.SUCCESS),
			"error": (AppIcons.ERROR, AppColors.ERROR),
			"warning": (AppIcons.WARNING, AppColors.WARNING),
			"info": (AppIcons.INFO, AppColors.INFO),
		}

		icon, color = icon_map.get(notification["type"], (AppIcons.INFO, AppColors.INFO))

		# Format timestamp
		time_str = notification["timestamp"].strftime("%H:%M:%S")

		return ft.Container(
			content=ft.Row(
				controls=[
					ft.Icon(
						icon,
						size=16,
						color=color,
					),
					ft.Column(
						controls=[
							ft.Text(
								notification["message"],
								size=11,
								color=AppColors.TEXT_PRIMARY,
								max_lines=2,
								overflow=ft.TextOverflow.ELLIPSIS,
								weight=ft.FontWeight.W_500,
							),
							ft.Text(
								time_str,
								size=9,
								color=AppColors.TEXT_DISABLED,
							),
						],
						spacing=2,
						expand=True,
					),
				],
				spacing=AppSpacing.XS,
			),
			bgcolor=AppColors.SURFACE,
			border=ft.border.all(1, color),
			border_radius=4,
			padding=ft.padding.all(AppSpacing.XS),
		)

	def clear_all(self, e=None):
		"""Clear all notifications"""
		self.notifications.clear()
		self.update_notifications()
