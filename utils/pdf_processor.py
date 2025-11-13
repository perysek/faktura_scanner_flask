"""
Konwersja PDF → obrazy do OCR
"""
from pathlib import Path
from typing import List
from PIL import Image
from pdf2image import convert_from_path
import pytesseract

from config.settings import TESSERACT_CMD, OCR_DPI, TEMP_DIR, POPPLER_PATH

# Ustaw ścieżkę do Tesseract
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


class PDFProcessor:
	"""Processor do konwersji PDF i OCR"""
	
	def __init__(self):
		self.dpi = OCR_DPI
		self.temp_dir = TEMP_DIR
	
	def pdf_to_images(self, pdf_path: str) -> List[Image.Image]:
		"""
		Konwertuj PDF na listę obrazów (PIL Image)
		"""
		try:
			# Check if poppler path exists
			import os
			poppler_path = POPPLER_PATH if os.path.exists(POPPLER_PATH) else None

			images = convert_from_path(
				pdf_path,
				dpi=self.dpi,
				fmt='jpeg',
				poppler_path=poppler_path
				)
			return images
		except Exception as e:
			raise Exception(f"Błąd konwersji PDF: {str(e)}")
	
	def preprocess_image(self, image: Image.Image) -> Image.Image:
		"""
		Preprocessing obrazu dla lepszego OCR:
		- Konwersja do grayscale
		- Zwiększenie kontrastu
		"""
		# Grayscale
		image = image.convert('L')
		
		# TODO: Dodatkowy preprocessing jeśli potrzeba
		# - Binaryzacja (threshold)
		# - Usuwanie szumu
		# - Deskew (prostowanie)
		
		return image
	
	def extract_text_from_image(
			self, image: Image.Image, lang: str = 'pol'
			) -> str:
		"""
		Ekstrakcja tekstu z obrazu używając Tesseract OCR
		"""
		# Preprocessing
		processed_image = self.preprocess_image(image)
		
		# OCR
		try:
			text = pytesseract.image_to_string(
				processed_image,
				lang=lang,
				config='--psm 6'  # Assume uniform block of text
				)
			return text
		except Exception as e:
			raise Exception(f"Błąd OCR: {str(e)}")
	
	def extract_text_from_pdf(self, pdf_path: str) -> tuple[str, float]:
		"""
		Główna metoda: PDF → tekst
		Returns: (extracted_text, confidence_score)
		Dla faktur wielostronicowych: przetwarza max 2 pierwsze strony
		"""
		images = self.pdf_to_images(pdf_path)

		# Ogranicz do max 2 stron dla wielostronicowych PDF
		# (główne dane faktury zawsze na pierwszych 1-2 stronach)
		max_pages = 2
		if len(images) > max_pages:
			print(f"  PDF ma {len(images)} stron, przetwarzanie pierwszych {max_pages}...")
			images = images[:max_pages]

		all_text = []
		confidences = []

		for i, image in enumerate(images):
			print(f"  Przetwarzanie strony {i + 1}/{len(images)}...")

			# OCR
			text = self.extract_text_from_image(image)
			all_text.append(text)

			# Confidence (uproszczona wersja - % niepustych linii)
			lines = [line for line in text.split('\n') if line.strip()]
			confidence = len(lines) / max(len(text.split('\n')), 1) * 100
			confidences.append(confidence)
		
		# Połącz tekst ze wszystkich stron
		full_text = "\n\n--- STRONA ---\n\n".join(all_text)
		
		# Średnia pewność
		avg_confidence = sum(confidences) / len(
			confidences
			) if confidences else 0
		
		return full_text, avg_confidence