"""
Email account settings configuration
"""
import json
from pathlib import Path
from typing import Optional
from datetime import datetime, date


class EmailSettings:
	"""Email account settings manager"""

	def __init__(self):
		self.config_file = Path(__file__).parent / "email_config.json"
		self.settings = self.load_settings()

	def load_settings(self) -> dict:
		"""Load email settings from config file"""
		if self.config_file.exists():
			try:
				with open(self.config_file, 'r', encoding='utf-8') as f:
					return json.load(f)
			except Exception as e:
				print(f"Error loading email settings: {e}")
				return self.get_default_settings()
		else:
			return self.get_default_settings()

	def get_default_settings(self) -> dict:
		"""Get default email settings"""
		return {
			"email_address": "anetulak23@wp.pl",
			"password": "***REMOVED***",
			"imap_server": "imap.wp.pl",
			"imap_port": 993,
			"search_from_date": "",
			"search_to_date": date.today().isoformat()
		}

	def save_settings(self, settings: dict) -> bool:
		"""Save email settings to config file"""
		try:
			with open(self.config_file, 'w', encoding='utf-8') as f:
				json.dump(settings, f, indent=4, ensure_ascii=False)
			self.settings = settings
			return True
		except Exception as e:
			print(f"Error saving email settings: {e}")
			return False

	def get_settings(self) -> dict:
		"""Get current email settings"""
		return self.settings.copy()

	def update_setting(self, key: str, value) -> bool:
		"""Update a specific setting"""
		self.settings[key] = value
		return self.save_settings(self.settings)
