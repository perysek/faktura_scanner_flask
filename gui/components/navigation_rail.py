"""
Lewy panel nawigacji
"""
from operator import iconcat

import flet as ft
from gui.theme import AppColors, AppIcons, AppSpacing


class AppNavigationRail(ft.NavigationRail):
	"""Komponent lewego panelu nawigacji"""
	
	def __init__(self, on_change):
		super().__init__()
		
		# Style
		self.selected_index = 0
		self.label_type = ft.NavigationRailLabelType.ALL
		self.bgcolor = AppColors.SURFACE
		self.extended = True
		self.min_width = 200
		self.min_extended_width = 200
		
		# Callback
		self.on_change = on_change
		
		# Elementy menu
		self.destinations = [
			ft.NavigationRailDestination(
				icon=ft.Icon(AppIcons.HOME, size=24),
				selected_icon=ft.Icon(
					AppIcons.HOME, size=24, color=AppColors.PRIMARY
					),
				label_content=ft.Text(
					"Lista Faktur",
					size=14,
					weight=ft.FontWeight.W_500
					),
				padding=AppSpacing.SM,
				),
			ft.NavigationRailDestination(
				icon=ft.Icon(AppIcons.UPLOAD, size=24),
				selected_icon=ft.Icon(
					AppIcons.UPLOAD, size=24, color=AppColors.PRIMARY
					),
				label_content=ft.Text(
					"Import PDF",
					size=14,
					weight=ft.FontWeight.W_500
					),
				padding=AppSpacing.SM,
				),
			ft.NavigationRailDestination(
				icon=ft.Icon(AppIcons.EXPORT, size=24),
				selected_icon=ft.Icon(
					AppIcons.EXPORT, size=24, color=AppColors.PRIMARY
					),
				label_content=ft.Text(
					"Eksport",
					size=14,
					weight=ft.FontWeight.W_500
					),
				padding=AppSpacing.SM,
				),
			ft.NavigationRailDestination(
				icon=ft.Icon(AppIcons.HISTORY, size=24),
				selected_icon=ft.Icon(
					AppIcons.HISTORY, size=24, color=AppColors.PRIMARY
					),
				label_content=ft.Text(
					"Historia",
					size=14,
					weight=ft.FontWeight.W_500
					),
				padding=AppSpacing.SM,
				),
			]