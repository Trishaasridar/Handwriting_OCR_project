"""
Flask routes for Handwriting OCR Application v3.
"""

import os
import base64
import logging
from flask import request, jsonify, render_template, current_app
from werkzeug.utils import secure_filename
from .ocr_service import OCRService, OCRError
from .models import save_ocr_result, search_ocr_results, get_ocr_result_by_id, get_db_connection
from .utils import ValidationError, validate_text_input, validate_file, sanitize_filename

logger = logging.getLogger(__name__)

ocr_service = None


def init_ocr_service():
    global ocr_service
    if ocr_service is None:
        ocr_service = OCRService({
            'OCR_CONFIDENCE_THRESHOLD': current_app.config['OCR_CONFIDENCE_THRESHOLD'],
            'OCR_ENABLE_SPELL_CHECK': current_app.config['OCR_ENABLE_SPELL_CHECK'],
            'OCR_LANGUAGE': current_app.config['OCR_LANGUAGE'],
            'MAX_PROCESSING_TIME': current_app.config['MAX_PROCESSING_TIME'],
        })
    return ocr_service


def register_routes(app):

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/api/health')
    def health_check():
        try:
            with get_db_connection() as conn:
                conn.execute("SELECT 1")
            return jsonify({
                "status": "healthy",
                "database": "sqlite3",
                "version": app.config['API_VERSION'],
            })
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return jsonify({"status": "unhealthy", "error": str(e)}), 500

    @app.route('/api/process', methods=['POST'])
    def process_image():
        try:
            student_name = request.form.get('studentName', '').strip()
            course_name = request.form.get('courseName', '').strip()
            uploaded_file = request.files.get('handwrittenFile')

            student_name = validate_text_input(student_name, 'Student name')
            course_name = validate_text_input(course_name, 'Course name')
            validate_file(uploaded_file, max_size=app.config['MAX_CONTENT_LENGTH'])

            unique_filename = sanitize_filename(secure_filename(uploaded_file.filename))
            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            uploaded_file.seek(0)
            uploaded_file.save(temp_path)

            try:
                ocr = init_ocr_service()
                result = ocr.process_image(temp_path)

                if not result['success']:
                    return jsonify({
                        "success": False,
                        "message": f"OCR processing failed: {result.get('error', 'Unknown error')}",
                    }), 500

                with open(temp_path, 'rb') as f:
                    image_blob = f.read()

                record_id = save_ocr_result(
                    student_name=student_name,
                    course_name=course_name,
                    image_blob=image_blob,
                    extracted_text=result['extracted_text'],
                    confidence_score=result['confidence_score'],
                    processing_time=result['processing_time'],
                )

                return jsonify({
                    "success": True,
                    "student_name": student_name,
                    "course_name": course_name,
                    "extracted_text": result['extracted_text'],
                    "confidence_score": result['confidence_score'],
                    "word_count": result['word_count'],
                    "text_length": result['text_length'],
                    "processing_time": result['processing_time'],
                    "quality_score": result['quality_score'],
                    "record_id": record_id,
                })

            finally:
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except OSError as e:
                    logger.warning(f"Failed to clean up temp file {temp_path}: {e}")

        except ValidationError as e:
            return jsonify({"success": False, "message": str(e)}), 400
        except OCRError as e:
            return jsonify({"success": False, "message": f"Text extraction failed: {e}"}), 500
        except Exception as e:
            logger.error(f"Unexpected error in process_image: {e}")
            return jsonify({"success": False, "message": "An unexpected error occurred."}), 500

    @app.route('/api/search', methods=['POST'])
    def search_records():
        try:
            data = request.get_json() or {}
            student_name = data.get('studentName', '').strip()
            course_name = data.get('courseName', '').strip()
            page = max(1, int(data.get('page', 1)))

            result = search_ocr_results(
                student_name=student_name or None,
                course_name=course_name or None,
                page=page,
                per_page=app.config['RESULTS_PER_PAGE'],
            )

            if not result['success']:
                return jsonify(result), 400

            # image_blob is already excluded from to_dict(); nothing to strip here
            return jsonify(result)

        except ValueError as e:
            return jsonify({"success": False, "message": "Invalid search parameters"}), 400
        except Exception as e:
            logger.error(f"Search error: {e}")
            return jsonify({"success": False, "message": "Search failed."}), 500

    @app.route('/api/record/<int:record_id>', methods=['GET'])
    def get_record(record_id):
        try:
            record = get_ocr_result_by_id(record_id)
            if not record:
                return jsonify({"success": False, "message": "Record not found"}), 404

            record_dict = record.to_dict()
            if record.image_blob:
                record_dict['image'] = base64.b64encode(record.image_blob).decode('utf-8')

            return jsonify({"success": True, "record": record_dict})
        except Exception as e:
            logger.error(f"Error retrieving record {record_id}: {e}")
            return jsonify({"success": False, "message": "Failed to retrieve record"}), 500

    @app.route('/api/stats', methods=['GET'])
    def get_stats():
        try:
            ocr = init_ocr_service()
            ocr_stats = ocr.get_processing_stats()

            with get_db_connection() as conn:
                total_records = conn.execute(
                    "SELECT COUNT(*) FROM ocr_results"
                ).fetchone()[0]

                row = conn.execute(
                    """SELECT AVG(confidence_score) AS avg_confidence,
                              AVG(processing_time)  AS avg_processing_time
                       FROM ocr_results WHERE confidence_score > 0"""
                ).fetchone()

            return jsonify({
                "success": True,
                "stats": {
                    "total_records": total_records,
                    "average_confidence": round(row['avg_confidence'] or 0, 3),
                    "average_processing_time": round(row['avg_processing_time'] or 0, 2),
                    "ocr_service": ocr_stats,
                },
            })
        except Exception as e:
            logger.error(f"Stats error: {e}")
            return jsonify({"success": False, "message": "Failed to retrieve statistics"}), 500

    # ── Error handlers ──────────────────────────────────────────────────────────

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith('/api/'):
            return jsonify({"success": False, "message": "Endpoint not found"}), 404
        return jsonify({"success": False, "message": "Page not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        if request.path.startswith('/api/'):
            return jsonify({"success": False, "message": "Internal server error"}), 500
        return jsonify({"success": False, "message": "Internal server error"}), 500

    @app.errorhandler(413)
    def file_too_large(error):
        return jsonify({
            "success": False,
            "message": f"File too large. Max size: {app.config['MAX_CONTENT_LENGTH'] // (1024*1024)}MB",
        }), 413

    logger.info("All routes registered successfully")
