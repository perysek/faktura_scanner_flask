"""
Document processor - Konwersja PDF/obrazów do tekstu przez OCR
Obsługuje zarówno pliki PDF jak i bezpośrednie obrazy (JPG, PNG, TIFF, BMP)
Includes enhanced preprocessing with OpenCV for better OCR accuracy.
"""
import logging
from pathlib import Path
from typing import List, Tuple
from PIL import Image
from pdf2image import convert_from_path
import pytesseract
import os
import traceback

# Setup logging
logger = logging.getLogger(__name__)

# OpenCV import with fallback
try:
	import cv2
	import numpy as np
	OPENCV_AVAILABLE = True
	logger.info("OpenCV loaded successfully")
except ImportError as e:
	OPENCV_AVAILABLE = False
	logger.warning(f"OpenCV not available: {e}. Enhanced preprocessing disabled.")

from config.settings import (
	TESSERACT_CMD, OCR_DPI, TEMP_DIR, POPPLER_PATH,
	OCR_ENHANCED_PREPROCESSING, OCR_DENOISE_STRENGTH,
	OCR_DESKEW_ENABLED, OCR_BINARIZATION_MODE
)

# Ustaw ścieżkę do Tesseract
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
logger.info(f"Tesseract CMD: {TESSERACT_CMD}")
logger.info(f"Poppler PATH: {POPPLER_PATH}")

# Supported image extensions
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'}


class PDFProcessor:
	"""Processor do konwersji PDF/obrazów i OCR
	
	Obsługuje:
	- Pliki PDF (konwersja stron na obrazy, potem OCR)
	- Pliki graficzne (JPG, PNG, TIFF, BMP) - bezpośredni OCR
	- Enhanced preprocessing z OpenCV (opcjonalnie)
	"""
	
	def __init__(self):
		self.dpi = OCR_DPI
		self.temp_dir = TEMP_DIR
		self.use_enhanced = OCR_ENHANCED_PREPROCESSING and OPENCV_AVAILABLE
		self.denoise_strength = OCR_DENOISE_STRENGTH
		self.deskew_enabled = OCR_DESKEW_ENABLED
		self.binarization_mode = OCR_BINARIZATION_MODE
		logger.info(f"PDFProcessor initialized: DPI={self.dpi}, enhanced={self.use_enhanced}, "
		            f"denoise={self.denoise_strength}, deskew={self.deskew_enabled}, "
		            f"binarization={self.binarization_mode}")
	
	def is_image_file(self, file_path: str) -> bool:
		"""Sprawdź czy plik jest obrazem (nie PDF)"""
		ext = Path(file_path).suffix.lower()
		return ext in IMAGE_EXTENSIONS
	
	def pdf_to_images(self, pdf_path: str) -> List[Image.Image]:
		"""
		Konwertuj PDF na listę obrazów (PIL Image)
		"""
		logger.info(f"[PDF→Images] Starting conversion: {pdf_path}")
		logger.debug(f"[PDF→Images] File exists: {os.path.exists(pdf_path)}")
		logger.debug(f"[PDF→Images] File size: {os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 'N/A'} bytes")
		
		try:
			poppler_exists = os.path.exists(POPPLER_PATH)
			poppler_path = POPPLER_PATH if poppler_exists else None
			logger.debug(f"[PDF→Images] Poppler path exists: {poppler_exists}")
			
			logger.info(f"[PDF→Images] Converting with DPI={self.dpi}...")
			images = convert_from_path(
				pdf_path,
				dpi=self.dpi,
				fmt='jpeg',
				poppler_path=poppler_path
				)
			logger.info(f"[PDF→Images] Successfully converted: {len(images)} pages")
			for i, img in enumerate(images):
				logger.debug(f"[PDF→Images] Page {i+1}: size={img.size}, mode={img.mode}")
			return images
		except Exception as e:
			logger.error(f"[PDF→Images] Conversion failed: {str(e)}")
			logger.error(f"[PDF→Images] Traceback: {traceback.format_exc()}")
			raise Exception(f"Błąd konwersji PDF: {str(e)}")
	
	def load_image(self, image_path: str) -> Image.Image:
		"""
		Wczytaj plik graficzny jako PIL Image
		"""
		try:
			image = Image.open(image_path)
			# Konwertuj do RGB jeśli potrzeba (np. RGBA, P mode)
			if image.mode not in ('RGB', 'L'):
				image = image.convert('RGB')
			return image
		except Exception as e:
			raise Exception(f"Błąd wczytywania obrazu: {str(e)}")
	
	def preprocess_image(self, image: Image.Image) -> Image.Image:
		"""
		Preprocessing obrazu dla lepszego OCR.
		Używa enhanced preprocessing z OpenCV jeśli dostępne.
		"""
		logger.debug(f"[Preprocess] Input image: size={image.size}, mode={image.mode}")
		if self.use_enhanced:
			logger.info("[Preprocess] Using enhanced preprocessing (OpenCV)")
			return self._preprocess_enhanced(image)
		else:
			logger.info("[Preprocess] Using basic preprocessing (grayscale only)")
			return self._preprocess_basic(image)
	
	def _preprocess_basic(self, image: Image.Image) -> Image.Image:
		"""Basic preprocessing - tylko grayscale"""
		return image.convert('L')
	
	def _preprocess_enhanced(self, image: Image.Image) -> Image.Image:
		"""
		Enhanced preprocessing z OpenCV:
		- Konwersja do grayscale
		- CLAHE contrast enhancement (before denoising)
		- Denoising (usuwanie szumu)
		- Deskewing (prostowanie)
		- Binarization (dla lepszego kontrastu)
		"""
		# Konwertuj PIL Image do numpy array
		img_array = np.array(image)
		
		# Konwersja do grayscale
		if len(img_array.shape) == 3:
			gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
		else:
			gray = img_array
		
		# CLAHE - Contrast Limited Adaptive Histogram Equalization
		# Greatly improves text visibility in photos with uneven lighting
		logger.debug("[Preprocess] Applying CLAHE contrast enhancement")
		clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
		enhanced = clahe.apply(gray)
		
		# Denoising - usuwanie szumu (reduced for phone photos)
		if self.denoise_strength > 0:
			logger.debug(f"[Preprocess] Denoising with strength={self.denoise_strength}")
			denoised = cv2.fastNlMeansDenoising(
				enhanced, 
				None, 
				h=self.denoise_strength,
				templateWindowSize=7,
				searchWindowSize=21
			)
		else:
			denoised = enhanced
		
		# Deskewing - automatyczne prostowanie dokumentu
		if self.deskew_enabled:
			deskewed = self._deskew_image(denoised)
		else:
			deskewed = denoised
		
		# Binarization - poprawa kontrastu tekstu
		if self.binarization_mode == 'adaptive':
			logger.debug("[Preprocess] Using adaptive binarization")
			binary = cv2.adaptiveThreshold(
				deskewed, 255,
				cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
				cv2.THRESH_BINARY,
				blockSize=11,
				C=2
			)
		elif self.binarization_mode == 'otsu':
			logger.debug("[Preprocess] Using Otsu binarization")
			_, binary = cv2.threshold(
				deskewed, 0, 255,
				cv2.THRESH_BINARY + cv2.THRESH_OTSU
			)
		else:
			binary = deskewed
		
		# Konwertuj z powrotem do PIL Image
		return Image.fromarray(binary)
	
	def _deskew_image(self, image: np.ndarray) -> np.ndarray:
		"""
		Automatyczne prostowanie (deskewing) obrazu dokumentu.
		Wykrywa kąt nachylenia tekstu i obraca obraz.
		"""
		try:
			# Detekuj krawędzie
			edges = cv2.Canny(image, 50, 150, apertureSize=3)
			
			# Znajdź linie za pomocą Hough Transform
			lines = cv2.HoughLinesP(
				edges, 1, np.pi/180, 
				threshold=100,
				minLineLength=100,
				maxLineGap=10
			)
			
			if lines is None or len(lines) == 0:
				return image
			
			# Oblicz średni kąt linii
			angles = []
			for line in lines:
				x1, y1, x2, y2 = line[0]
				if x2 - x1 != 0:  # Avoid division by zero
					angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
					# Filtruj tylko małe kąty (prawdopodobnie tekst)
					if abs(angle) < 15:
						angles.append(angle)
			
			if not angles:
				return image
			
			# Mediana kąta dla odporności na outliers
			median_angle = np.median(angles)
			
			# Nie obracaj jeśli kąt jest bardzo mały
			if abs(median_angle) < 0.5:
				return image
			
			# Obróć obraz
			h, w = image.shape[:2]
			center = (w // 2, h // 2)
			rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
			rotated = cv2.warpAffine(
				image, rotation_matrix, (w, h),
				flags=cv2.INTER_CUBIC,
				borderMode=cv2.BORDER_REPLICATE
			)
			
			logger.debug(f"[DESKEW] Skorygowano kąt: {median_angle:.2f}°")
			return rotated
			
		except Exception as e:
			logger.warning(f"[DESKEW] Błąd: {str(e)}")
			return image
	
	def extract_text_from_image(
			self, image: Image.Image, lang: str = 'pol'
			) -> str:
		"""
		Ekstrakcja tekstu z obrazu używając Tesseract OCR
		(compatibility method - returns only text)
		"""
		text, _ = self.extract_text_with_confidence(image, lang)
		return text
	
	def extract_text_with_confidence(
			self, image: Image.Image, lang: str = 'pol'
			) -> Tuple[str, float]:
		"""
		Ekstrakcja tekstu z obrazu z prawdziwymi wynikami confidence z Tesseract.
		Używa image_to_data zamiast image_to_string dla dokładniejszych wyników.
		
		Returns:
			Tuple[str, float]: (extracted_text, confidence_score 0-100)
		"""
		logger.debug(f"[OCR] Starting OCR with lang={lang}")
		
		# Preprocessing
		logger.debug("[OCR] Preprocessing image...")
		processed_image = self.preprocess_image(image)
		logger.debug(f"[OCR] Preprocessed image: size={processed_image.size}, mode={processed_image.mode}")
		
		# OCR with detailed data
		try:
			logger.info("[OCR] Running Tesseract image_to_data...")
			# Get detailed OCR data with confidence scores
			data = pytesseract.image_to_data(
				processed_image,
				lang=lang,
				config='--psm 6',
				output_type=pytesseract.Output.DICT
			)
			
			logger.debug(f"[OCR] Tesseract returned {len(data['text'])} elements")
			
			# Extract text and calculate confidence
			words = []
			confidences = []
			
			for i, word in enumerate(data['text']):
				word_text = word.strip()
				conf = int(data['conf'][i])
				
				# Filter out noise: empty words and very low confidence
				if word_text and conf > 0:
					words.append(word_text)
					confidences.append(conf)
			
			logger.debug(f"[OCR] Found {len(words)} valid words")
			
			# Reconstruct text with proper line breaks
			# Group by line number for proper formatting
			lines_dict = {}
			for i, word in enumerate(data['text']):
				word_text = word.strip()
				if word_text and int(data['conf'][i]) > 0:
					line_num = data['line_num'][i]
					if line_num not in lines_dict:
						lines_dict[line_num] = []
					lines_dict[line_num].append(word_text)
			
			# Join words into lines, then lines into text
			lines = [' '.join(words) for _, words in sorted(lines_dict.items())]
			text = '\n'.join(lines)
			
			# Calculate average confidence
			if confidences:
				avg_confidence = sum(confidences) / len(confidences)
			else:
				avg_confidence = 0.0
			
			logger.info(f"[OCR] Completed: {len(lines)} lines, {len(words)} words, confidence={avg_confidence:.1f}%")
			return text, avg_confidence
			
		except Exception as e:
			logger.error(f"[OCR] Error: {str(e)}")
			logger.error(f"[OCR] Traceback: {traceback.format_exc()}")
			raise Exception(f"Błąd OCR: {str(e)}")
	
	def extract_text_from_pdf(self, pdf_path: str) -> Tuple[str, float]:
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

			# OCR with real confidence scores
			text, confidence = self.extract_text_with_confidence(image)
			all_text.append(text)
			confidences.append(confidence)
		
		# Połącz tekst ze wszystkich stron
		full_text = "\n\n--- STRONA ---\n\n".join(all_text)
		
		# Średnia pewność
		avg_confidence = sum(confidences) / len(
			confidences
			) if confidences else 0
		
		return full_text, avg_confidence
	
	def extract_text_from_image_file(self, image_path: str) -> Tuple[str, float]:
		"""
		Ekstrakcja tekstu z pliku graficznego (JPG, PNG, TIFF, BMP)
		Returns: (extracted_text, confidence_score)
		"""
		print(f"  Przetwarzanie obrazu: {Path(image_path).name}...")
		
		# Wczytaj obraz
		image = self.load_image(image_path)
		
		# OCR with real confidence scores
		text, confidence = self.extract_text_with_confidence(image)
		
		return text, confidence
	
	def process_file(self, file_path: str) -> Tuple[str, float]:
		"""
		Uniwersalna metoda przetwarzania pliku - obsługuje zarówno PDF jak i obrazy
		
		Args:
			file_path: Ścieżka do pliku (PDF lub obraz)
			
		Returns:
			Tuple[str, float]: (extracted_text, confidence_score)
		"""
		if self.is_image_file(file_path):
			return self.extract_text_from_image_file(file_path)
		else:
			# Assume PDF
			return self.extract_text_from_pdf(file_path)