"""
Lewy panel nawigacji
"""

import flet as ft

from gui.theme import AppColors, AppIcons, AppSpacing


class AppNavigationRail(ft.Container):
	"""Komponent lewego panelu nawigacji z lewym wyrównaniem"""

	def __init__(self, on_change):
		super().__init__()

		# Style
		self.bgcolor = "#F5F5F5"  # Light grey background
		self.width = 260
		self.padding = ft.padding.only(top=20, bottom=20)

		self.selected_index = 0
		self.on_change_callback = on_change

		# Menu items configuration
		self.menu_items = [
			{
				"icon": AppIcons.HOME,
				"label": "LISTA FAKTUR",
			},
			{
				"icon": AppIcons.UPLOAD,
				"label": "IMPORT PDF",
			},
			{
				"icon": AppIcons.EXPORT,
				"label": "EKSPORT",
			},
			{
				"icon": AppIcons.HISTORY,
				"label": "HISTORIA",
			},
			{
				"icon": ft.Icons.EMAIL_OUTLINED,
				"selected_icon": ft.Icons.EMAIL,
				"label": "USTAWIENIA E-MAIL",
			},
		]

		# Build the navigation items
		self.content = ft.Column(
			controls=[self._create_nav_item(i, item) for i, item in enumerate(self.menu_items)],
			spacing=0,
			alignment=ft.MainAxisAlignment.START,
		)

	def _create_nav_item(self, index: int, item: dict) -> ft.Container:
		"""Create a navigation item with left-aligned icon and label"""
		is_selected = index == self.selected_index

		# Determine icon based on selection
		icon_name = item.get("selected_icon", item["icon"]) if is_selected else item["icon"]
		icon_color = AppColors.PRIMARY if is_selected else "#666666"

		# Background color for selected item
		bg_color = "#E3F2FD" if is_selected else "transparent"

		return ft.Container(
			content=ft.Row(
				controls=[
					ft.Icon(
						icon_name,
						size=24,
						color=icon_color,
					),
					ft.Text(
						item["label"],
						size=14,
						weight=ft.FontWeight.W_500 if is_selected else ft.FontWeight.NORMAL,
						color=icon_color,
					),
				],
				spacing=16,
				alignment=ft.MainAxisAlignment.START,
			),
			padding=ft.padding.only(left=24, right=24, top=16, bottom=16),
			bgcolor=bg_color,
			border_radius=0,
			ink=True,
			on_click=lambda e, idx=index: self._on_item_click(idx),
		)

	def _on_item_click(self, index: int):
		"""Handle navigation item click"""
		if index != self.selected_index:
			self.selected_index = index
			# Rebuild the navigation items
			self.content.controls = [
				self._create_nav_item(i, item)
				for i, item in enumerate(self.menu_items)
			]
			self.update()

			# Call the original callback
			if self.on_change_callback:
				# Create a mock event object similar to NavigationRail
				class MockEvent:
					def __init__(self, index):
						self.control = type('obj', (object,), {'selected_index': index})()

				self.on_change_callback(MockEvent(index))
