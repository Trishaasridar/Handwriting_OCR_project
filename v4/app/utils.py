"""
Utility functions for Handwriting OCR Application v2.

Includes validation, file handling, and helper functions.
"""

import os
import re
from werkzeug.utils import secure_filename
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass

def validate_text_input(text: str, field_name: str, max_length: int = 255) -> str:
    """
    Validate text input for security and format.

    Args:
        text: Input text to validate
        field_name: Name of the field for error messages
        max_length: Maximum allowed length

    Returns:
        Validated and cleaned text

    Raises:
        ValidationError: If validation fails
    """
    if not text:
        raise ValidationError(f"{field_name} is required")

    # Remove leading/trailing whitespace
    text = text.strip()

    if not text:
        raise ValidationError(f"{field_name} cannot be empty or just whitespace")

    if len(text) > max_length:
        raise ValidationError(f"{field_name} is too long (max {max_length} characters)")

    # Check for potentially dangerous characters
    dangerous_chars = ['<', '>', '&', '"', "'", '\\', '\x00']
    for char in dangerous_chars:
        if char in text:
            raise ValidationError(f"{field_name} contains invalid characters")

    return text

def validate_file(file, allowed_extensions: Optional[set] = None,
                 max_size: int = 16 * 1024 * 1024) -> None:
    """
    Validate uploaded file for type, size, and security.

    Args:
        file: File object from Flask request.files
        allowed_extensions: Set of allowed file extensions
        max_size: Maximum file size in bytes

    Raises:
        ValidationError: If validation fails
    """
    if not file:
        raise ValidationError("No file provided")

    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Reset file pointer

    if file_size > max_size:
        raise ValidationError(f"File too large. Maximum size is {max_size // (1024*1024)}MB")

    if file_size == 0:
        raise ValidationError("File is empty")

    # Get filename and check extension
    filename = secure_filename(file.filename)
    if not filename:
        raise ValidationError("Invalid filename")

    # Default allowed extensions for images
    if allowed_extensions is None:
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp'}

    # Get file extension
    if '.' not in filename:
        raise ValidationError("File must have an extension")

    extension = filename.rsplit('.', 1)[1].lower()

    if extension not in allowed_extensions:
        raise ValidationError(f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}")

    # Basic content validation - check if it's actually an image
    try:
        # Read first few bytes to check file signature
        file.seek(0)
        header = file.read(12)
        file.seek(0)

        # Check common image file signatures
        image_signatures = {
            b'\xff\xd8\xff': 'jpg',
            b'\x89PNG\r\n\x1a\n': 'png',
            b'GIF87a': 'gif',
            b'GIF89a': 'gif',
            b'BM': 'bmp',
            b'II*\x00': 'tiff',
            b'MM\x00*': 'tiff'
        }

        is_valid_image = False
        for signature, ext in image_signatures.items():
            if header.startswith(signature):
                is_valid_image = True
                break

        if not is_valid_image:
            raise ValidationError("File does not appear to be a valid image")

    except Exception as e:
        logger.warning(f"File content validation failed: {e}")
        raise ValidationError("Unable to validate file content")

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent security issues.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    # Use werkzeug's secure_filename as primary sanitization
    secure_name = secure_filename(filename)

    # Additional sanitization for edge cases
    # Remove any remaining dangerous characters
    secure_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', secure_name)

    # Ensure filename is not empty after sanitization
    if not secure_name:
        secure_name = "upload"

    # Limit length
    if len(secure_name) > 255:
        name_part, ext_part = os.path.splitext(secure_name)
        secure_name = name_part[:255-len(ext_part)] + ext_part

    return secure_name

def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string
    """
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    size_index = 0
    size = float(size_bytes)

    while size >= 1024 and size_index < len(size_names) - 1:
        size /= 1024
        size_index += 1

    if size_index == 0:
        return f"{int(size)} {size_names[size_index]}"
    else:
        return ".1f"

def get_file_info(file_path: str) -> dict:
    """
    Get information about a file.

    Args:
        file_path: Path to the file

    Returns:
        Dictionary with file information
    """
    try:
        stat = os.stat(file_path)
        return {
            'path': file_path,
            'size': stat.st_size,
            'size_formatted': format_file_size(stat.st_size),
            'modified': stat.st_mtime,
            'extension': os.path.splitext(file_path)[1].lower()
        }
    except OSError as e:
        logger.error(f"Failed to get file info for {file_path}: {e}")
        return {
            'path': file_path,
            'error': str(e)
        }

def cleanup_temp_files(temp_dir: str = None, max_age_hours: int = 24) -> int:
    """
    Clean up temporary files older than specified age.

    Args:
        temp_dir: Directory to clean (default: system temp dir)
        max_age_hours: Maximum age in hours

    Returns:
        Number of files cleaned up
    """
    import time
    import shutil

    if temp_dir is None:
        temp_dir = tempfile.gettempdir()

    cleaned_count = 0
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600

    try:
        for filename in os.listdir(temp_dir):
            filepath = os.path.join(temp_dir, filename)

            # Skip directories and non-files
            if not os.path.isfile(filepath):
                continue

            # Check file age
            file_age = current_time - os.path.getmtime(filepath)
            if file_age > max_age_seconds:
                try:
                    os.remove(filepath)
                    cleaned_count += 1
                except OSError:
                    # File might be in use, skip
                    pass

    except OSError as e:
        logger.error(f"Failed to cleanup temp files: {e}")

    return cleaned_count

def generate_unique_filename(original_filename: str, prefix: str = "") -> str:
    """
    Generate a unique filename with timestamp.

    Args:
        original_filename: Original filename
        prefix: Optional prefix for the filename

    Returns:
        Unique filename
    """
    import uuid
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]

    name_part, ext_part = os.path.splitext(secure_filename(original_filename))

    if prefix:
        prefix = f"{prefix}_"

    return f"{prefix}{timestamp}_{unique_id}_{name_part}{ext_part}"