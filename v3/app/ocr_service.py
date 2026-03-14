"""
Enhanced OCR Service for Handwriting OCR Application v3.
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
import re

logger = logging.getLogger(__name__)


class OCRError(Exception):
    pass


class OCRService:
    """Enhanced OCR service with preprocessing and post-processing."""

    def __init__(self, config=None):
        self.config = config or {}
        self.confidence_threshold = self.config.get('OCR_CONFIDENCE_THRESHOLD', 0.6)
        self.enable_spell_check = self.config.get('OCR_ENABLE_SPELL_CHECK', False)
        self.language = self.config.get('OCR_LANGUAGE', 'en')
        self.max_processing_time = self.config.get('MAX_PROCESSING_TIME', 300)
        self._initialize_ocr()

        if self.enable_spell_check:
            try:
                from spellchecker import SpellChecker
                self.spell_checker = SpellChecker(language=self.language)
            except ImportError:
                logger.warning("pyspellchecker not installed; spell check disabled.")
                self.spell_checker = None
                self.enable_spell_check = False
        else:
            self.spell_checker = None

    def _initialize_ocr(self):
        try:
            self.ocr = PaddleOCR(
                lang=self.language,
                ocr_version="PP-OCRv4",
                use_angle_cls=True,
                enable_mkldnn=False,
            )
            logger.info("OCR engine initialised successfully")
        except Exception as e:
            logger.error(f"Failed to initialise OCR engine: {e}")
            raise OCRError(f"OCR initialisation failed: {e}")

    def process_image(self, image_path: str) -> Dict[str, Any]:
        start_time = time.time()
        try:
            self._validate_image(image_path)
            processed_image = self._preprocess_image(image_path)

            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                cv2.imwrite(tmp.name, processed_image)
                processed_path = tmp.name

            try:
                raw_results = self._perform_ocr_with_confidence(processed_path)
                extracted_text, confidence_score, word_count = self._process_ocr_results(raw_results)

                if self.enable_spell_check and extracted_text:
                    extracted_text = self._apply_spell_correction(extracted_text)

                total_time = time.time() - start_time
                quality_score = self._calculate_quality_score(confidence_score, word_count, len(extracted_text))

                return {
                    'extracted_text': extracted_text,
                    'confidence_score': confidence_score,
                    'word_count': word_count,
                    'text_length': len(extracted_text),
                    'processing_time': round(total_time, 2),
                    'quality_score': quality_score,
                    'success': True,
                }
            finally:
                try:
                    os.unlink(processed_path)
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
                'success': False,
                'error': str(e),
            }

    def _validate_image(self, image_path: str):
        if not os.path.exists(image_path):
            raise OCRError(f"Image file not found: {image_path}")
        if os.path.getsize(image_path) == 0:
            raise OCRError("Image file is empty")
        try:
            with Image.open(image_path) as img:
                img.verify()
        except Exception as e:
            raise OCRError(f"Invalid image file: {e}")

    def _preprocess_image(self, image_path: str) -> np.ndarray:
        image = cv2.imread(image_path)
        if image is None:
            raise OCRError("Failed to load image")

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        h, w = gray.shape
        max_dim = max(h, w)
        if max_dim > 2000:
            scale = 2000 / max_dim
            gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
        elif max_dim < 300:
            scale = 300 / max_dim
            gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(blurred)
        morphed = cv2.morphologyEx(enhanced, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1)))
        thresh = cv2.adaptiveThreshold(morphed, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)))
        return cleaned

    def _perform_ocr_with_confidence(self, image_path: str) -> list:
        try:
            results = self.ocr.predict(image_path)

            if not results:
                return []

            filtered = []

            # PaddleOCR 3.x returns a list of result dicts per image.
            # rec_boxes entries are [x1, y1, x2, y2] flat arrays — keep as-is
            # so that _group_into_lines can do bbox[1]=y1, bbox[3]=y2 arithmetic.
            for res in results:
                rec_texts = res.get('rec_texts', [])
                rec_scores = res.get('rec_scores', [])
                rec_boxes = res.get('rec_boxes', [])

                for text, confidence, bbox in zip(rec_texts, rec_scores, rec_boxes):
                    if confidence >= self.confidence_threshold:
                        filtered.append({'bbox': list(bbox), 'text': text, 'confidence': float(confidence)})

            return filtered
        except Exception as e:
            raise OCRError(f"OCR processing failed: {e}")

    def _process_ocr_results(self, ocr_results: list) -> Tuple[str, float, int]:
        if not ocr_results:
            return "", 0.0, 0

        ocr_results.sort(key=lambda x: x['bbox'][1])
        lines = self._group_into_lines(ocr_results)

        text_lines, total_confidence, total_words = [], 0.0, 0
        for line in lines:
            line.sort(key=lambda x: x['bbox'][0])
            texts = [w['text'] for w in line]
            confs = [w['confidence'] for w in line]
            text_lines.append(' '.join(texts))
            total_confidence += sum(confs) / len(confs)
            total_words += len(texts)

        avg_confidence = total_confidence / len(lines) if lines else 0.0
        return '\n'.join(text_lines), avg_confidence, total_words

    def _group_into_lines(self, ocr_results: list) -> list:
        if not ocr_results:
            return []

        heights = [r['bbox'][3] - r['bbox'][1] for r in ocr_results]
        y_threshold = (sum(heights) / len(heights)) * 0.5

        lines, current = [], [ocr_results[0]]
        for item in ocr_results[1:]:
            if abs(item['bbox'][1] - current[-1]['bbox'][1]) < y_threshold:
                current.append(item)
            else:
                lines.append(current)
                current = [item]
        lines.append(current)
        return lines

    def _apply_spell_correction(self, text: str) -> str:
        if not self.spell_checker or not text:
            return text
        try:
            words = re.findall(r'\b\w+\b', text)
            corrected = []
            for word in words:
                if len(word) <= 2 or word.isdigit():
                    corrected.append(word)
                elif word.lower() in self.spell_checker:
                    corrected.append(word)
                else:
                    correction = self.spell_checker.correction(word.lower())
                    corrected.append(correction if correction else word)

            idx = 0

            def replace(m):
                nonlocal idx
                r = corrected[idx] if idx < len(corrected) else m.group()
                idx += 1
                return r

            return re.sub(r'\b\w+\b', replace, text)
        except Exception as e:
            logger.warning(f"Spell correction failed: {e}")
            return text

    def _calculate_quality_score(self, confidence: float, word_count: int, text_length: int) -> float:
        if word_count == 0 or text_length == 0:
            return 0.0
        word_bonus = 0.1 if 5 <= word_count <= 200 else (-0.2 if word_count < 5 else 0.05)
        length_bonus = 0.1 if 20 <= text_length <= 5000 else (-0.2 if text_length < 20 else 0.05)
        return max(0.0, min(1.0, confidence + word_bonus + length_bonus))

    def get_processing_stats(self) -> Dict[str, Any]:
        return {
            'confidence_threshold': self.confidence_threshold,
            'spell_check_enabled': self.enable_spell_check,
            'language': self.language,
            'max_processing_time': self.max_processing_time,
        }
