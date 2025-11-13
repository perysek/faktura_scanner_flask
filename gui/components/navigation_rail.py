"""
Lewy panel nawigacji
"""

import flet as ft

from gui.theme import AppColors, AppIcons, AppSpacing


class AppNavigationRail(ft.NavigationRail):
	"""Komponent lewego panelu nawigacji"""

	def __init__(self, on_change):
		super().__init__()

		# Style
		self.selected_index = 0
		self.label_type = ft.NavigationRailLabelType.NONE
		self.bgcolor = "#F5F5F5"  # Light grey background
		self.extended = True
		self.min_width = 300
		self.min_extended_width = 300
		#self.width =300
		#self.group_alignment=-1.0
		#self.width=400
		#self.left=True

		# Callback
		self.on_change = on_change
		
		# Elementy menu
		self.destinations = [
			ft.NavigationRailDestination(
				icon=ft.Icon(AppIcons.HOME, size=24),
				selected_icon=ft.Icon(
					AppIcons.HOME, size=24, color=AppColors.PRIMARY
					),
				label='LISTA FAKTUR'
				),
			ft.NavigationRailDestination(
				icon=ft.Icon(AppIcons.UPLOAD, size=24),
				selected_icon=ft.Icon(
					AppIcons.UPLOAD, size=24, color=AppColors.PRIMARY, 
					),
				label="IMPORT PDF",
				),
			ft.NavigationRailDestination(
				icon=ft.Icon(AppIcons.EXPORT, size=24, ),
				selected_icon=ft.Icon(
					AppIcons.EXPORT, size=24, color=AppColors.PRIMARY, 
					),
				label="EKSPORT",
				),
			ft.NavigationRailDestination(
				icon=ft.Icon(AppIcons.HISTORY, size=24, ),
				selected_icon=ft.Icon(
					AppIcons.HISTORY, size=24, color=AppColors.PRIMARY, 
					),
				label="HISTORIA",
				),
			ft.NavigationRailDestination(
				icon=ft.Icon(ft.Icons.EMAIL_OUTLINED, size=24, ),
				selected_icon=ft.Icon(
					ft.Icons.EMAIL, size=24, color=AppColors.PRIMARY, 
					),
				label="USTAWIENIA E-MAIL",
				),
			]