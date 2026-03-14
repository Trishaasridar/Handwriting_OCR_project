"""
Flask routes for Handwriting OCR Application v2.

Provides RESTful API endpoints with comprehensive error handling.
"""

import os
import base64
import logging
from flask import request, jsonify, render_template, current_app
from werkzeug.utils import secure_filename
from .ocr_service import OCRService, OCRError
from .models import save_ocr_result, search_ocr_results, get_ocr_result_by_id
from .utils import ValidationError, validate_text_input, validate_file, sanitize_filename
from .config import Config

logger = logging.getLogger(__name__)

# Global OCR service instance
ocr_service = None

def init_ocr_service():
    """Initialize OCR service with current configuration."""
    global ocr_service
    if ocr_service is None:
        config = {
            'OCR_CONFIDENCE_THRESHOLD': current_app.config['OCR_CONFIDENCE_THRESHOLD'],
            'OCR_ENABLE_SPELL_CHECK': current_app.config['OCR_ENABLE_SPELL_CHECK'],
            'OCR_LANGUAGE': current_app.config['OCR_LANGUAGE'],
            'MAX_PROCESSING_TIME': current_app.config['MAX_PROCESSING_TIME']
        }
        ocr_service = OCRService(config)
    return ocr_service

def register_routes(app):
    """Register all application routes."""

    @app.route('/')
    def index():
        """Serve the main application interface."""
        return render_template('index.html')

    @app.route('/api/health')
    def health_check():
        """Health check endpoint for monitoring."""
        try:
            # Test database connection
            from .models import get_db_connection
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                db_status = "healthy"

            # Test OCR service
            ocr = init_ocr_service()
            ocr_status = "healthy"

            return jsonify({
                "status": "healthy",
                "database": db_status,
                "ocr_service": ocr_status,
                "version": app.config['API_VERSION']
            })

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return jsonify({
                "status": "unhealthy",
                "error": str(e)
            }), 500

    @app.route('/api/process', methods=['POST'])
    def process_image():
        """
        Process uploaded image and extract text.

        Expects form data with:
        - handwrittenFile: Image file
        - studentName: Student name (string)
        - courseName: Course name (string)
        """
        try:
            # Get and validate form data
            student_name = request.form.get('studentName', '').strip()
            course_name = request.form.get('courseName', '').strip()
            uploaded_file = request.files.get('handwrittenFile')

            # Validate inputs
            student_name = validate_text_input(student_name, 'Student name')
            course_name = validate_text_input(course_name, 'Course name')
            validate_file(uploaded_file, max_size=app.config['MAX_CONTENT_LENGTH'])

            # Generate unique filename
            original_filename = secure_filename(uploaded_file.filename)
            unique_filename = sanitize_filename(original_filename)

            # Save uploaded file temporarily
            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            uploaded_file.seek(0)
            uploaded_file.save(temp_path)

            try:
                # Initialize OCR service
                ocr = init_ocr_service()

                # Process image
                result = ocr.process_image(temp_path)

                if not result['success']:
                    return jsonify({
                        "success": False,
                        "message": f"OCR processing failed: {result.get('error', 'Unknown error')}"
                    }), 500

                # Read image data for storage
                with open(temp_path, 'rb') as f:
                    image_blob = f.read()

                # Save to database
                record_id = save_ocr_result(
                    student_name=student_name,
                    course_name=course_name,
                    image_blob=image_blob,
                    extracted_text=result['extracted_text'],
                    confidence_score=result['confidence_score'],
                    processing_time=result['processing_time']
                )

                # Prepare response
                response_data = {
                    "success": True,
                    "student_name": student_name,
                    "course_name": course_name,
                    "extracted_text": result['extracted_text'],
                    "confidence_score": result['confidence_score'],
                    "word_count": result['word_count'],
                    "text_length": result['text_length'],
                    "processing_time": result['processing_time'],
                    "quality_score": result['quality_score'],
                    "record_id": record_id
                }

                logger.info(f"Image processed successfully for {student_name} - {course_name}")
                return jsonify(response_data)

            finally:
                # Clean up temporary file
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except OSError as e:
                    logger.warning(f"Failed to clean up temporary file {temp_path}: {e}")

        except ValidationError as e:
            logger.warning(f"Validation error: {e}")
            return jsonify({
                "success": False,
                "message": str(e)
            }), 400

        except OCRError as e:
            logger.error(f"OCR processing error: {e}")
            return jsonify({
                "success": False,
                "message": f"Text extraction failed: {str(e)}"
            }), 500

        except Exception as e:
            logger.error(f"Unexpected error in process_image: {e}")
            return jsonify({
                "success": False,
                "message": "An unexpected error occurred. Please try again."
            }), 500

    @app.route('/api/search', methods=['POST'])
    def search_records():
        """
        Search OCR records by student name and/or course name.

        Expects JSON data with:
        - studentName: Student name filter (optional)
        - courseName: Course name filter (optional)
        - page: Page number (optional, default: 1)
        """
        try:
            # Get search parameters
            data = request.get_json() or {}
            student_name = data.get('studentName', '').strip()
            course_name = data.get('courseName', '').strip()
            page = max(1, int(data.get('page', 1)))

            # Validate page number
            if page < 1:
                page = 1

            # Perform search
            result = search_ocr_results(
                student_name=student_name if student_name else None,
                course_name=course_name if course_name else None,
                page=page,
                per_page=app.config['RESULTS_PER_PAGE']
            )

            if not result['success']:
                return jsonify(result), 400

            # Convert images to base64 for API response
            for record in result['records']:
                if 'image_blob' in record:
                    record['image'] = base64.b64encode(record['image_blob']).decode('utf-8')
                    del record['image_blob']

            logger.info(f"Search completed: {result['total_records']} records found")
            return jsonify(result)

        except ValueError as e:
            logger.warning(f"Invalid search parameters: {e}")
            return jsonify({
                "success": False,
                "message": "Invalid search parameters"
            }), 400

        except Exception as e:
            logger.error(f"Search error: {e}")
            return jsonify({
                "success": False,
                "message": "Search failed. Please try again."
            }), 500

    @app.route('/api/record/<int:record_id>', methods=['GET'])
    def get_record(record_id):
        """
        Get a specific OCR record by ID.

        Args:
            record_id: Database ID of the record
        """
        try:
            record = get_ocr_result_by_id(record_id)

            if not record:
                return jsonify({
                    "success": False,
                    "message": "Record not found"
                }), 404

            # Convert to dictionary
            record_dict = record.to_dict()

            # Convert image blob to base64
            if hasattr(record, 'image_blob') and record.image_blob:
                record_dict['image'] = base64.b64encode(record.image_blob).decode('utf-8')

            return jsonify({
                "success": True,
                "record": record_dict
            })

        except Exception as e:
            logger.error(f"Error retrieving record {record_id}: {e}")
            return jsonify({
                "success": False,
                "message": "Failed to retrieve record"
            }), 500

    @app.route('/api/stats', methods=['GET'])
    def get_stats():
        """Get application statistics and OCR service info."""
        try:
            # OCR service stats
            ocr = init_ocr_service()
            ocr_stats = ocr.get_processing_stats()

            # Database stats (basic)
            try:
                from .models import get_db_connection
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) as total_records FROM ocr_results")
                    total_records = cursor.fetchone()['total_records']

                    cursor.execute("""
                        SELECT AVG(confidence_score) as avg_confidence,
                               AVG(processing_time) as avg_processing_time
                        FROM ocr_results
                        WHERE confidence_score > 0
                    """)
                    stats = cursor.fetchone()

            except Exception as e:
                logger.warning(f"Failed to get database stats: {e}")
                total_records = 0
                stats = {'avg_confidence': 0, 'avg_processing_time': 0}

            return jsonify({
                "success": True,
                "stats": {
                    "total_records": total_records,
                    "average_confidence": round(stats['avg_confidence'] or 0, 3),
                    "average_processing_time": round(stats['avg_processing_time'] or 0, 2),
                    "ocr_service": ocr_stats
                }
            })

        except Exception as e:
            logger.error(f"Stats retrieval error: {e}")
            return jsonify({
                "success": False,
                "message": "Failed to retrieve statistics"
            }), 500

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        if request.path.startswith('/api/'):
            return jsonify({
                "success": False,
                "message": "Endpoint not found"
            }), 404
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors."""
        logger.error(f"Internal server error: {error}")
        if request.path.startswith('/api/'):
            return jsonify({
                "success": False,
                "message": "Internal server error"
            }), 500
        return render_template('500.html'), 500

    @app.errorhandler(413)
    def file_too_large(error):
        """Handle file too large errors."""
        return jsonify({
            "success": False,
            "message": f"File too large. Maximum size is {app.config['MAX_CONTENT_LENGTH'] // (1024*1024)}MB"
        }), 413

    logger.info("All routes registered successfully")