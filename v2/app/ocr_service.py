"""
Enhanced OCR Service for Handwriting OCR Application v2.

Features:
- Image preprocessing pipeline
- Confidence score filtering
- Spell checking and text correction
- Performance metrics tracking
- Error handling and logging
"""

import cv2
import numpy as np
from paddleocr import PaddleOCR
from typing import Tuple, Optional, Dict, Any
import time
import logging
import tempfile
import os
from PIL import Image
from spellchecker import SpellChecker
import re

logger = logging.getLogger(__name__)

class OCRError(Exception):
    """Custom exception for OCR-related errors."""
    pass

class OCRService:
    """Enhanced OCR service with preprocessing and post-processing."""

    def __init__(self, config=None):
        self.config = config or {}
        self.confidence_threshold = self.config.get('OCR_CONFIDENCE_THRESHOLD', 0.6)
        self.enable_spell_check = self.config.get('OCR_ENABLE_SPELL_CHECK', True)
        self.language = self.config.get('OCR_LANGUAGE', 'en')
        self.max_processing_time = self.config.get('MAX_PROCESSING_TIME', 300)

        # Initialize OCR engine
        self._initialize_ocr()

        # Initialize spell checker
        if self.enable_spell_check:
            self.spell_checker = SpellChecker(language=self.language)
        else:
            self.spell_checker = None

    def _initialize_ocr(self):
        """Initialize PaddleOCR with optimized settings."""
        try:
            self.ocr = PaddleOCR(
                lang=self.language,
                ocr_version="PP-OCRv4",
                use_angle_cls=True,
                enable_mkldnn=False,
            )
            logger.info("OCR engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OCR engine: {e}")
            raise OCRError(f"OCR initialization failed: {e}")

    def process_image(self, image_path: str) -> Dict[str, Any]:
        """
        Process an image and extract text with enhanced accuracy.

        Args:
            image_path: Path to the image file

        Returns:
            Dictionary containing extracted text and metadata

        Raises:
            OCRError: If OCR processing fails
        """
        start_time = time.time()
        processing_metrics = {}

        try:
            # Validate image
            self._validate_image(image_path)
            processing_metrics['validation_time'] = time.time() - start_time

            # Preprocess image
            preprocess_start = time.time()
            processed_image = self._preprocess_image(image_path)
            processing_metrics['preprocessing_time'] = time.time() - preprocess_start

            # Save processed image temporarily for OCR
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                cv2.imwrite(tmp_file.name, processed_image)
                processed_image_path = tmp_file.name

            try:
                # Perform OCR
                ocr_start = time.time()
                raw_results = self._perform_ocr_with_confidence(processed_image_path)
                processing_metrics['ocr_time'] = time.time() - ocr_start

                # Process and clean text
                text_processing_start = time.time()
                extracted_text, confidence_score, word_count = self._process_ocr_results(raw_results)
                processing_metrics['text_processing_time'] = time.time() - text_processing_start

                # Apply spell checking if enabled
                if self.enable_spell_check and extracted_text:
                    spell_check_start = time.time()
                    extracted_text = self._apply_spell_correction(extracted_text)
                    processing_metrics['spell_check_time'] = time.time() - spell_check_start

                # Calculate final metrics
                total_time = time.time() - start_time
                processing_metrics['total_time'] = total_time

                # Quality assessment
                quality_score = self._calculate_quality_score(
                    confidence_score, word_count, len(extracted_text)
                )

                result = {
                    'extracted_text': extracted_text,
                    'confidence_score': confidence_score,
                    'word_count': word_count,
                    'text_length': len(extracted_text),
                    'processing_time': round(total_time, 2),
                    'quality_score': quality_score,
                    'processing_metrics': processing_metrics,
                    'success': True
                }

                logger.info(f"OCR processing completed in {total_time:.2f}s with confidence {confidence_score:.3f}")
                return result

            finally:
                # Clean up temporary file
                try:
                    os.unlink(processed_image_path)
                except OSError:
                    pass

        except Exception as e:
            error_time = time.time() - start_time
            logger.error(f"OCR processing failed after {error_time:.2f}s: {e}")

            return {
                'extracted_text': '',
                'confidence_score': 0.0,
                'word_count': 0,
                'text_length': 0,
                'processing_time': round(error_time, 2),
                'quality_score': 0.0,
                'processing_metrics': {'error': str(e)},
                'success': False,
                'error': str(e)
            }

    def _validate_image(self, image_path: str):
        """Validate image file before processing."""
        if not os.path.exists(image_path):
            raise OCRError(f"Image file not found: {image_path}")

        if not os.access(image_path, os.R_OK):
            raise OCRError(f"Image file not readable: {image_path}")

        # Check file size
        file_size = os.path.getsize(image_path)
        if file_size == 0:
            raise OCRError("Image file is empty")

        max_size = self.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)  # 16MB default
        if file_size > max_size:
            raise OCRError(f"Image file too large: {file_size} bytes (max: {max_size})")

        # Try to open image
        try:
            with Image.open(image_path) as img:
                img.verify()  # Verify it's a valid image
        except Exception as e:
            raise OCRError(f"Invalid image file: {e}")

    def _preprocess_image(self, image_path: str) -> np.ndarray:
        """
        Apply comprehensive image preprocessing for better OCR accuracy.

        Pipeline:
        1. Load image
        2. Convert to grayscale
        3. Resize if too large/small
        4. Apply Gaussian blur for noise reduction
        5. Enhance contrast with CLAHE
        6. Apply morphological operations
        7. Binarization with adaptive thresholding
        """
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            raise OCRError("Failed to load image")

        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Resize image for optimal OCR (between 300-2000 pixels on longest side)
        height, width = gray.shape
        max_dim = max(height, width)
        min_dim = min(height, width)

        if max_dim > 2000:
            scale_factor = 2000 / max_dim
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            gray = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        elif max_dim < 300:
            scale_factor = 300 / max_dim
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            gray = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)

        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(blurred)

        # Apply morphological operations to clean up the image
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
        morphed = cv2.morphologyEx(enhanced, cv2.MORPH_CLOSE, kernel)

        # Apply adaptive thresholding for binarization
        thresh = cv2.adaptiveThreshold(
            morphed, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )

        # Apply additional morphological operation to clean up small noise
        kernel_clean = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_clean)

        return cleaned

    def _perform_ocr_with_confidence(self, image_path: str) -> list:
        """
        Perform OCR and extract results with confidence scores.

        Returns:
            List of OCR results with confidence filtering
        """
        try:
            results = self.ocr.predict(image_path)

            if not results:
                return []

            filtered_results = []
            for res in results:
                rec_texts = res.get('rec_texts', [])
                rec_scores = res.get('rec_scores', [])
                rec_boxes = res.get('rec_boxes', [])

                for text, confidence, bbox in zip(rec_texts, rec_scores, rec_boxes):
                    if confidence >= self.confidence_threshold:
                        x1, y1, x2, y2 = bbox
                        poly = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
                        filtered_results.append({'bbox': poly, 'text': text, 'confidence': confidence})

            return filtered_results

        except Exception as e:
            logger.error(f"OCR processing error: {e}")
            raise OCRError(f"OCR processing failed: {e}")

    def _process_ocr_results(self, ocr_results: list) -> Tuple[str, float, int]:
        """
        Process OCR results into structured text.

        Args:
            ocr_results: List of OCR result dictionaries

        Returns:
            Tuple of (processed_text, average_confidence, word_count)
        """
        if not ocr_results:
            return "", 0.0, 0

        # Sort results by vertical position (top to bottom)
        ocr_results.sort(key=lambda x: x['bbox'][1])  # Sort by y-coordinate

        # Group into lines using dynamic threshold
        lines = self._group_into_lines(ocr_results)

        # Sort words within each line
        for line in lines:
            line.sort(key=lambda x: x['bbox'][0])  # Sort by x-coordinate

        # Build final text
        text_lines = []
        total_confidence = 0.0
        total_words = 0

        for line in lines:
            line_text = []
            line_confidences = []

            for word in line:
                line_text.append(word['text'])
                line_confidences.append(word['confidence'])

            if line_text:
                text_lines.append(' '.join(line_text))

                # Average confidence for the line
                avg_line_confidence = sum(line_confidences) / len(line_confidences)
                total_confidence += avg_line_confidence
                total_words += len(line_text)

        final_text = '\n'.join(text_lines)

        # Calculate overall average confidence
        if lines:
            avg_confidence = total_confidence / len(lines)
        else:
            avg_confidence = 0.0

        return final_text, avg_confidence, total_words

    def _group_into_lines(self, ocr_results: list, y_threshold_factor: float = 0.1) -> list:
        """
        Group OCR results into lines using dynamic threshold.

        Args:
            ocr_results: List of OCR results sorted by y-position
            y_threshold_factor: Factor for calculating line grouping threshold

        Returns:
            List of lines, each containing word results
        """
        if not ocr_results:
            return []

        lines = []
        current_line = [ocr_results[0]]

        # Calculate dynamic threshold based on average text height
        heights = []
        for result in ocr_results:
            bbox = result['bbox']
            height = bbox[3] - bbox[1]  # y2 - y1
            heights.append(height)

        avg_height = sum(heights) / len(heights) if heights else 20
        y_threshold = avg_height * y_threshold_factor

        for i in range(1, len(ocr_results)):
            current_bbox = ocr_results[i]['bbox']
            prev_bbox = current_line[-1]['bbox']

            # Check if current word is on the same line
            if abs(current_bbox[1] - prev_bbox[1]) < y_threshold:
                current_line.append(ocr_results[i])
            else:
                lines.append(current_line)
                current_line = [ocr_results[i]]

        if current_line:
            lines.append(current_line)

        return lines

    def _apply_spell_correction(self, text: str) -> str:
        """
        Apply spell checking and correction to extracted text.

        Args:
            text: Input text to correct

        Returns:
            Spell-checked and corrected text
        """
        if not self.spell_checker or not text:
            return text

        try:
            # Split into words and correct each one
            words = re.findall(r'\b\w+\b', text)
            corrected_words = []

            for word in words:
                # Skip very short words or numbers
                if len(word) <= 2 or word.isdigit():
                    corrected_words.append(word)
                    continue

                # Check if word is misspelled
                if word.lower() in self.spell_checker:
                    corrected_words.append(word)
                else:
                    # Get correction suggestions
                    candidates = self.spell_checker.candidates(word.lower())
                    if candidates:
                        # Choose the most likely correction
                        correction = self.spell_checker.correction(word.lower())
                        corrected_words.append(correction if correction else word)
                    else:
                        corrected_words.append(word)

            # Reconstruct text while preserving non-word characters
            corrected_text = text
            word_index = 0

            def replace_word(match):
                nonlocal word_index
                if word_index < len(corrected_words):
                    result = corrected_words[word_index]
                    word_index += 1
                    return result
                return match.group()

            corrected_text = re.sub(r'\b\w+\b', replace_word, text)

            return corrected_text

        except Exception as e:
            logger.warning(f"Spell correction failed: {e}")
            return text  # Return original text if correction fails

    def _calculate_quality_score(self, confidence: float, word_count: int,
                               text_length: int) -> float:
        """
        Calculate overall quality score based on multiple factors.

        Args:
            confidence: Average OCR confidence (0-1)
            word_count: Number of words detected
            text_length: Total character length

        Returns:
            Quality score between 0-1
        """
        if word_count == 0 or text_length == 0:
            return 0.0

        # Base score from confidence
        base_score = confidence

        # Bonus for reasonable word count (not too few, not too many)
        if 5 <= word_count <= 200:
            word_bonus = 0.1
        elif word_count < 5:
            word_bonus = -0.2
        else:
            word_bonus = 0.05

        # Bonus for reasonable text length
        if 20 <= text_length <= 5000:
            length_bonus = 0.1
        elif text_length < 20:
            length_bonus = -0.2
        else:
            length_bonus = 0.05

        # Calculate final score
        quality_score = base_score + word_bonus + length_bonus
        return max(0.0, min(1.0, quality_score))  # Clamp between 0 and 1

    def get_processing_stats(self) -> Dict[str, Any]:
        """Get OCR processing statistics."""
        return {
            'confidence_threshold': self.confidence_threshold,
            'spell_check_enabled': self.enable_spell_check,
            'language': self.language,
            'max_processing_time': self.max_processing_time
        }