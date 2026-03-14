"""
Flask routes for Handwriting OCR Application v4.
Batch upload: multiple images processed in a background thread.
Progress is polled via /api/job/<job_id>.
"""

import os
import uuid
import base64
import logging
import threading
import time
from flask import request, jsonify, render_template, current_app
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge
from .ocr_service import OCRService, OCRError
from .models import save_ocr_result, search_ocr_results, get_ocr_result_by_id, get_db_connection
from .utils import ValidationError, validate_text_input, validate_file, sanitize_filename

logger = logging.getLogger(__name__)

ocr_service = None

# ── In-memory job store ────────────────────────────────────────────────────────
# { job_id: { status, total, done, results, errors, batch_id, ... } }
_jobs: dict = {}
_jobs_lock = threading.Lock()


def _job_create(job_id: str, total: int, batch_id: str, student_name: str, course_name: str):
    with _jobs_lock:
        _jobs[job_id] = {
            'status':       'running',   # running | done | failed
            'total':        total,
            'done':         0,
            'current_file': '',
            'results':      [],
            'errors':       [],
            'batch_id':     batch_id,
            'student_name': student_name,
            'course_name':  course_name,
            'started_at':   time.time(),
        }


def _job_update(job_id: str, **kwargs):
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)


def _job_get(job_id: str) -> dict | None:
    with _jobs_lock:
        return dict(_jobs[job_id]) if job_id in _jobs else None


def _job_finish(job_id: str):
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id]['status'] = 'done'
            _jobs[job_id]['elapsed'] = round(time.time() - _jobs[job_id]['started_at'], 1)


def _cleanup_old_jobs():
    """Evict jobs older than 1 hour to prevent memory growth."""
    cutoff = time.time() - 3600
    with _jobs_lock:
        stale = [jid for jid, j in _jobs.items() if j.get('started_at', 0) < cutoff]
        for jid in stale:
            del _jobs[jid]


# ── OCR service ────────────────────────────────────────────────────────────────
def init_ocr_service():
    global ocr_service
    if ocr_service is None:
        ocr_service = OCRService({
            'OCR_CONFIDENCE_THRESHOLD': current_app.config['OCR_CONFIDENCE_THRESHOLD'],
            'OCR_ENABLE_SPELL_CHECK':   current_app.config['OCR_ENABLE_SPELL_CHECK'],
            'OCR_LANGUAGE':             current_app.config['OCR_LANGUAGE'],
            'MAX_PROCESSING_TIME':      current_app.config['MAX_PROCESSING_TIME'],
        })
    return ocr_service


# ── Background worker ──────────────────────────────────────────────────────────
def _process_batch(app, job_id: str, file_entries: list,
                   student_name: str, course_name: str, batch_id: str):
    """
    Run inside a daemon thread.
    file_entries = [ {'temp_path': str, 'filename': str} ]
    """
    with app.app_context():
        ocr = init_ocr_service()

        for entry in file_entries:
            temp_path = entry['temp_path']
            filename  = entry['filename']
            _job_update(job_id, current_file=filename)

            try:
                ocr_result = ocr.process_image(temp_path)

                with open(temp_path, 'rb') as f:
                    image_blob = f.read()

                if ocr_result['success']:
                    record_id = save_ocr_result(
                        student_name=student_name,
                        course_name=course_name,
                        image_blob=image_blob,
                        extracted_text=ocr_result['extracted_text'],
                        filename=filename,
                        batch_id=batch_id,
                        confidence_score=ocr_result['confidence_score'],
                        processing_time=ocr_result['processing_time'],
                    )
                    with _jobs_lock:
                        _jobs[job_id]['results'].append({
                            'filename':        filename,
                            'record_id':       record_id,
                            'extracted_text':  ocr_result['extracted_text'],
                            'confidence_score':ocr_result['confidence_score'],
                            'word_count':      ocr_result['word_count'],
                            'processing_time': ocr_result['processing_time'],
                            'quality_score':   ocr_result['quality_score'],
                            'success':         True,
                        })
                else:
                    with _jobs_lock:
                        _jobs[job_id]['errors'].append(
                            {'filename': filename, 'error': ocr_result.get('error', 'OCR failed')}
                        )

            except Exception as e:
                logger.error(f"[job {job_id}] Error on {filename}: {e}")
                with _jobs_lock:
                    _jobs[job_id]['errors'].append({'filename': filename, 'error': str(e)})

            finally:
                if os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass
                with _jobs_lock:
                    _jobs[job_id]['done'] += 1

        _job_finish(job_id)
        _cleanup_old_jobs()
        logger.info(f"[job {job_id}] Finished: {len(_jobs[job_id]['results'])} ok, "
                    f"{len(_jobs[job_id]['errors'])} failed")


# ── Route registration ─────────────────────────────────────────────────────────
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
                "status":       "healthy",
                "database":     "sqlite3",
                "version":      app.config['API_VERSION'],
                "multi_upload": True,
                "max_files":    app.config['MAX_FILES_PER_BATCH'],
            })
        except Exception as e:
            return jsonify({"status": "unhealthy", "error": str(e)}), 500

    @app.route('/api/process', methods=['POST'])
    def process_images():
        """
        Accept up to MAX_FILES_PER_BATCH images + metadata.
        Saves temp files, spawns a background thread, returns job_id immediately.
        """
        try:
            student_name   = request.form.get('studentName', '').strip()
            course_name    = request.form.get('courseName', '').strip()
            uploaded_files = request.files.getlist('handwrittenFile')

            student_name = validate_text_input(student_name, 'Student name')
            course_name  = validate_text_input(course_name,  'Course name')

            valid_files = [f for f in uploaded_files if f.filename != '']
            if not valid_files:
                return jsonify({"success": False, "message": "No files uploaded"}), 400

            max_files = app.config.get('MAX_FILES_PER_BATCH', 50)
            if len(valid_files) > max_files:
                return jsonify({
                    "success": False,
                    "message": f"Too many files. Maximum {max_files} images per upload.",
                }), 400

            batch_id = str(uuid.uuid4())
            job_id   = str(uuid.uuid4())
            max_file_size = app.config.get('MAX_FILE_SIZE', 20 * 1024 * 1024)

            # Save all temp files before spawning thread
            file_entries = []
            pre_errors   = []

            for uploaded_file in valid_files:
                filename  = sanitize_filename(secure_filename(uploaded_file.filename))
                temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{batch_id}_{filename}")
                try:
                    validate_file(uploaded_file, max_size=max_file_size)
                    uploaded_file.seek(0)
                    uploaded_file.save(temp_path)
                    file_entries.append({'temp_path': temp_path, 'filename': filename})
                except ValidationError as e:
                    pre_errors.append({'filename': filename, 'error': str(e)})
                except Exception as e:
                    pre_errors.append({'filename': filename, 'error': str(e)})

            if not file_entries:
                return jsonify({
                    "success": False,
                    "message": "All files failed pre-upload validation.",
                    "errors":  pre_errors,
                }), 400

            _job_create(job_id, len(file_entries), batch_id, student_name, course_name)

            # Mark any pre-errors into job right away
            if pre_errors:
                with _jobs_lock:
                    _jobs[job_id]['errors'].extend(pre_errors)

            thread = threading.Thread(
                target=_process_batch,
                args=(app, job_id, file_entries,
                      student_name, course_name, batch_id),
                daemon=True,
            )
            thread.start()

            return jsonify({
                "success":       True,
                "job_id":        job_id,
                "batch_id":      batch_id,
                "total_files":   len(file_entries),
                "student_name":  student_name,
                "course_name":   course_name,
            })

        except RequestEntityTooLarge:
            max_mb = app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
            return jsonify({
                "success": False,
                "message": f"Total upload size exceeds {max_mb} MB. "
                           f"Please upload fewer or smaller images.",
            }), 413
        except HTTPException:
            raise
        except ValidationError as e:
            return jsonify({"success": False, "message": str(e)}), 400
        except Exception as e:
            logger.error(f"Unexpected error in process_images: {e}")
            return jsonify({"success": False, "message": "An unexpected error occurred."}), 500

    @app.route('/api/job/<job_id>', methods=['GET'])
    def job_status(job_id):
        """Poll this endpoint every few seconds to get live progress."""
        job = _job_get(job_id)
        if job is None:
            return jsonify({"success": False, "message": "Job not found"}), 404

        total   = job['total']
        done    = job['done']
        pct     = int(done / total * 100) if total > 0 else 0
        elapsed = round(time.time() - job['started_at'], 1)

        response = {
            "success":      True,
            "job_id":       job_id,
            "status":       job['status'],
            "total":        total,
            "done":         done,
            "percent":      pct,
            "current_file": job['current_file'],
            "elapsed":      elapsed,
            "results":      job['results'],
            "errors":       job['errors'],
            "batch_id":     job['batch_id'],
            "student_name": job['student_name'],
            "course_name":  job['course_name'],
        }
        if job['status'] == 'done':
            response['elapsed_total'] = job.get('elapsed', elapsed)
        return jsonify(response)

    @app.route('/api/search', methods=['POST'])
    def search_records():
        try:
            data         = request.get_json() or {}
            student_name = data.get('studentName', '').strip()
            course_name  = data.get('courseName', '').strip()
            page         = max(1, int(data.get('page', 1)))

            result = search_ocr_results(
                student_name=student_name or None,
                course_name=course_name  or None,
                page=page,
                per_page=app.config['RESULTS_PER_PAGE'],
            )
            return jsonify(result), 200 if result['success'] else 400

        except ValueError:
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
            with get_db_connection() as conn:
                total_records = conn.execute("SELECT COUNT(*) FROM ocr_results").fetchone()[0]
                total_batches = conn.execute(
                    "SELECT COUNT(DISTINCT batch_id) FROM ocr_results WHERE batch_id IS NOT NULL"
                ).fetchone()[0]
                row = conn.execute(
                    """SELECT AVG(confidence_score) AS avg_confidence,
                              AVG(processing_time)  AS avg_time
                       FROM ocr_results WHERE confidence_score > 0"""
                ).fetchone()
            return jsonify({
                "success": True,
                "stats": {
                    "total_records":          total_records,
                    "total_batches":          total_batches,
                    "average_confidence":     round(row['avg_confidence'] or 0, 3),
                    "average_processing_time":round(row['avg_time']        or 0, 2),
                    "ocr_service":            ocr.get_processing_stats(),
                },
            })
        except Exception as e:
            logger.error(f"Stats error: {e}")
            return jsonify({"success": False, "message": "Failed to retrieve statistics"}), 500

    # ── Error handlers ─────────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith('/api/'):
            return jsonify({"success": False, "message": "Endpoint not found"}), 404
        return jsonify({"success": False, "message": "Page not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

    @app.errorhandler(413)
    def file_too_large(error):
        max_mb = app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
        return jsonify({
            "success": False,
            "message": f"Total upload size exceeds {max_mb} MB. "
                       f"Please upload fewer or smaller images.",
        }), 413

    logger.info("All routes registered successfully")
