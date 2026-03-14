"""
Database models for Handwriting OCR Application v4.
Supports multiple images per upload via batch_id grouping.
"""

import sqlite3
import base64
from contextlib import contextmanager
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

_db_path = None


def set_db_path(path):
    global _db_path
    _db_path = path


def get_db_path():
    if _db_path is None:
        raise RuntimeError("Database not initialised. Call init_db(app) first.")
    return _db_path


@contextmanager
def get_db_connection():
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class OCRResult:
    def __init__(self, id=None, batch_id=None, filename=None,
                 student_name=None, course_name=None,
                 image_blob=None, date=None, record_time=None,
                 content=None, confidence_score=None, processing_time=None):
        self.id = id
        self.batch_id = batch_id
        self.filename = filename
        self.student_name = student_name
        self.course_name = course_name
        self.image_blob = image_blob
        self.date = date
        self.time = record_time
        self.content = content
        self.confidence_score = confidence_score
        self.processing_time = processing_time

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row['id'],
            batch_id=row['batch_id'],
            filename=row['filename'],
            student_name=row['student_name'],
            course_name=row['course_name'],
            image_blob=row['image_blob'],
            date=row['date'],
            record_time=row['record_time'],
            content=row['content'],
            confidence_score=row['confidence_score'],
            processing_time=row['processing_time'],
        )

    def to_dict(self, include_image=False):
        d = {
            'id': self.id,
            'batch_id': self.batch_id,
            'filename': self.filename or '',
            'student_name': self.student_name,
            'course_name': self.course_name,
            'date': str(self.date) if self.date else '',
            'time': str(self.time) if self.time else '',
            'content': self.content or '',
            'confidence_score': self.confidence_score,
            'processing_time': self.processing_time,
        }
        if include_image and self.image_blob:
            d['image'] = base64.b64encode(self.image_blob).decode('utf-8')
        return d


def save_ocr_result(student_name, course_name, image_blob, extracted_text,
                    filename=None, batch_id=None,
                    confidence_score=None, processing_time=None):
    """Save a single OCR result row. Returns the new row ID."""
    try:
        with get_db_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO ocr_results
                    (batch_id, filename, student_name, course_name,
                     image_blob, date, record_time, content,
                     confidence_score, processing_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    filename,
                    student_name,
                    course_name,
                    image_blob,
                    datetime.now().strftime('%Y-%m-%d'),
                    datetime.now().strftime('%H:%M:%S'),
                    extracted_text,
                    confidence_score,
                    processing_time,
                )
            )
            record_id = cursor.lastrowid
            logger.info(f"Saved OCR result ID={record_id} batch={batch_id} file={filename}")
            return record_id
    except Exception as e:
        logger.error(f"Failed to save OCR result: {e}")
        raise


def search_ocr_results(student_name=None, course_name=None, page=1, per_page=8):
    """Search with pagination. Returns a dict with records list."""
    try:
        filters, values = [], []

        if student_name and student_name.strip():
            filters.append("student_name LIKE ?")
            values.append(f"%{student_name.strip()}%")
        if course_name and course_name.strip():
            filters.append("course_name LIKE ?")
            values.append(f"%{course_name.strip()}%")

        where = f"WHERE {' AND '.join(filters)}" if filters else ""

        with get_db_connection() as conn:
            total_records = conn.execute(
                f"SELECT COUNT(*) FROM ocr_results {where}", values
            ).fetchone()[0]

            offset = (page - 1) * per_page
            rows = conn.execute(
                f"""
                SELECT id, batch_id, filename, student_name, course_name,
                       image_blob, date, record_time, content,
                       confidence_score, processing_time
                FROM ocr_results {where}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                values + [per_page, offset]
            ).fetchall()

        results = [OCRResult.from_row(r) for r in rows]
        total_pages = max(1, (total_records + per_page - 1) // per_page)

        return {
            'success': True,
            'records': [r.to_dict(include_image=True) for r in results],
            'page': page,
            'total_pages': total_pages,
            'total_records': total_records,
            'per_page': per_page,
        }

    except Exception as e:
        logger.error(f"Search failed: {e}")
        return {'success': False, 'message': f'Search failed: {str(e)}'}


def get_ocr_result_by_id(result_id):
    try:
        with get_db_connection() as conn:
            row = conn.execute(
                """
                SELECT id, batch_id, filename, student_name, course_name,
                       image_blob, date, record_time, content,
                       confidence_score, processing_time
                FROM ocr_results WHERE id = ?
                """,
                (result_id,)
            ).fetchone()
        return OCRResult.from_row(row) if row else None
    except Exception as e:
        logger.error(f"Failed to get OCR result {result_id}: {e}")
        return None


def init_db(app):
    db_path = app.config['DB_PATH']
    set_db_path(db_path)

    if db_path != ':memory:':
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    try:
        with get_db_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ocr_results (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id         TEXT,
                    filename         TEXT,
                    student_name     TEXT    NOT NULL,
                    course_name      TEXT    NOT NULL,
                    image_blob       BLOB    NOT NULL,
                    date             TEXT    NOT NULL,
                    record_time      TEXT    NOT NULL,
                    content          TEXT,
                    confidence_score REAL,
                    processing_time  REAL,
                    created_at       TEXT    DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_student_course
                    ON ocr_results (student_name, course_name)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_batch
                    ON ocr_results (batch_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_date
                    ON ocr_results (date)
            """)
        logger.info(f"SQLite database initialised at: {db_path}")
    except Exception as e:
        logger.error(f"Database initialisation failed: {e}")
        raise
