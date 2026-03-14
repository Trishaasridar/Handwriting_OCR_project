"""
Database models and operations for Handwriting OCR Application v2.

Provides secure database operations with context managers and proper error handling.
"""

import mysql.connector
from contextlib import contextmanager
from datetime import datetime
import logging
from .config import Config

logger = logging.getLogger(__name__)

class DatabaseConnection:
    """Context manager for database connections."""

    def __init__(self, config=None):
        self.config = config or Config()
        self.connection = None

    def __enter__(self):
        try:
            self.connection = mysql.connector.connect(
                host=self.config.DB_HOST,
                user=self.config.DB_USER,
                password=self.config.DB_PASSWORD,
                database=self.config.DB_NAME,
                port=self.config.DB_PORT,
                autocommit=False
            )
            return self.connection
        except mysql.connector.Error as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            if exc_type:
                self.connection.rollback()
                logger.error(f"Transaction rolled back due to: {exc_val}")
            else:
                self.connection.commit()
                logger.debug("Transaction committed successfully")

            self.connection.close()

@contextmanager
def get_db_connection():
    """Get database connection context manager."""
    with DatabaseConnection() as conn:
        yield conn

class OCRResult:
    """OCR Result data model."""

    def __init__(self, id=None, student_name=None, course_name=None,
                 image_blob=None, date=None, time=None, content=None,
                 confidence_score=None, processing_time=None):
        self.id = id
        self.student_name = student_name
        self.course_name = course_name
        self.image_blob = image_blob
        self.date = date
        self.time = time
        self.content = content
        self.confidence_score = confidence_score
        self.processing_time = processing_time

    @classmethod
    def from_db_row(cls, row):
        """Create OCRResult instance from database row."""
        return cls(
            id=row.get('id'),
            student_name=row.get('student_name'),
            course_name=row.get('course_name'),
            image_blob=row.get('image_blob'),
            date=row.get('date'),
            time=row.get('time'),
            content=row.get('content'),
            confidence_score=row.get('confidence_score'),
            processing_time=row.get('processing_time')
        )

    def to_dict(self):
        """Convert to dictionary for API responses."""
        result = {
            'id': self.id,
            'student_name': self.student_name,
            'course_name': self.course_name,
            'date': self.date.strftime('%Y-%m-%d') if isinstance(self.date, datetime) else str(self.date),
            'time': self.time.strftime('%H:%M:%S') if isinstance(self.time, datetime) else str(self.time),
            'content': self.content,
            'confidence_score': self.confidence_score,
            'processing_time': self.processing_time
        }
        return result

def save_ocr_result(student_name, course_name, image_blob, extracted_text,
                   confidence_score=None, processing_time=None):
    """
    Save OCR result to database.

    Args:
        student_name: Name of the student
        course_name: Name of the course
        image_blob: Binary image data
        extracted_text: OCR extracted text
        confidence_score: OCR confidence score (0-1)
        processing_time: Time taken for processing in seconds

    Returns:
        int: ID of inserted record

    Raises:
        Exception: If database operation fails
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO ocr_results
                (student_name, course_name, image_blob, date, time, content,
                 confidence_score, processing_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                student_name, course_name, image_blob,
                datetime.now().date(),
                datetime.now().time(),
                extracted_text,
                confidence_score,
                processing_time
            ))

            record_id = cursor.lastrowid
            logger.info(f"OCR result saved with ID: {record_id}")
            return record_id

    except Exception as e:
        logger.error(f"Failed to save OCR result: {e}")
        raise

def search_ocr_results(student_name=None, course_name=None, page=1, per_page=8):
    """
    Search OCR results with pagination.

    Args:
        student_name: Filter by student name (partial match)
        course_name: Filter by course name (partial match)
        page: Page number (1-based)
        per_page: Results per page

    Returns:
        dict: Search results with pagination info
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            # Build search filters
            filters = []
            values = []

            if student_name and student_name.strip():
                filters.append("student_name LIKE %s")
                values.append(f"%{student_name.strip()}%")

            if course_name and course_name.strip():
                filters.append("course_name LIKE %s")
                values.append(f"%{course_name.strip()}%")

            where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

            # Get total count
            count_query = f"SELECT COUNT(*) as total FROM ocr_results {where_clause}"
            cursor.execute(count_query, values)
            total_records = cursor.fetchone()['total']

            # Get paginated results
            offset = (page - 1) * per_page
            query = f"""
                SELECT id, student_name, course_name, image_blob, date, time,
                       content, confidence_score, processing_time
                FROM ocr_results
                {where_clause}
                ORDER BY id DESC
                LIMIT %s OFFSET %s
            """

            cursor.execute(query, values + [per_page, offset])
            records = cursor.fetchall()

            # Convert to OCRResult objects
            results = [OCRResult.from_db_row(row) for row in records]

            total_pages = (total_records + per_page - 1) // per_page

            return {
                'success': True,
                'records': [result.to_dict() for result in results],
                'page': page,
                'total_pages': total_pages,
                'total_records': total_records,
                'per_page': per_page
            }

    except Exception as e:
        logger.error(f"Search failed: {e}")
        return {
            'success': False,
            'message': f'Search failed: {str(e)}'
        }

def get_ocr_result_by_id(result_id):
    """
    Get OCR result by ID.

    Args:
        result_id: Database ID of the result

    Returns:
        OCRResult or None
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            cursor.execute("""
                SELECT id, student_name, course_name, image_blob, date, time,
                       content, confidence_score, processing_time
                FROM ocr_results
                WHERE id = %s
            """, (result_id,))

            row = cursor.fetchone()
            return OCRResult.from_db_row(row) if row else None

    except Exception as e:
        logger.error(f"Failed to get OCR result {result_id}: {e}")
        return None

def init_db(app):
    """Initialize database connection and create tables if needed."""
    try:
        # Test connection
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Create table if it doesn't exist (for development)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ocr_results (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    student_name VARCHAR(255) NOT NULL,
                    course_name VARCHAR(255) NOT NULL,
                    image_blob LONGBLOB NOT NULL,
                    date DATE NOT NULL,
                    time TIME NOT NULL,
                    content TEXT,
                    confidence_score FLOAT,
                    processing_time FLOAT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_student_course (student_name, course_name),
                    INDEX idx_date (date)
                )
            """)

            logger.info("Database initialized successfully")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise