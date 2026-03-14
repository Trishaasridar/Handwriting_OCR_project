"""
Configuration management for Handwriting OCR Application v2.

Supports multiple environments with secure credential handling.
"""

import os
from datetime import timedelta

class Config:
    """Base configuration class."""

    # Flask Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = False
    TESTING = False

    # Database Configuration
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    DB_NAME = os.environ.get('DB_NAME', 'ocr_db')
    DB_PORT = int(os.environ.get('DB_PORT', 3306))

    # File Upload Configuration
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp'}

    # OCR Configuration
    OCR_CONFIDENCE_THRESHOLD = float(os.environ.get('OCR_CONFIDENCE_THRESHOLD', 0.6))
    OCR_LANGUAGE = os.environ.get('OCR_LANGUAGE', 'en')
    OCR_ENABLE_SPELL_CHECK = os.environ.get('OCR_ENABLE_SPELL_CHECK', 'true').lower() == 'true'

    # Processing Configuration
    MAX_PROCESSING_TIME = int(os.environ.get('MAX_PROCESSING_TIME', 300))  # 5 minutes
    CLEANUP_TEMP_FILES = os.environ.get('CLEANUP_TEMP_FILES', 'true').lower() == 'true'
    TEMP_FILE_MAX_AGE_HOURS = int(os.environ.get('TEMP_FILE_MAX_AGE_HOURS', 24))

    # Pagination Configuration
    RESULTS_PER_PAGE = int(os.environ.get('RESULTS_PER_PAGE', 8))

    # Logging Configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.path.join(os.getcwd(), 'logs', 'app.log')
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5

    # Session Configuration
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)

    # API Configuration
    API_TITLE = 'Handwriting OCR API v2'
    API_VERSION = '2.0.0'
    API_DESCRIPTION = 'Enhanced OCR service for handwritten text recognition'

    @staticmethod
    def init_app(app):
        """Initialize application with configuration."""
        # Ensure upload directory exists
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        # Ensure logs directory exists
        os.makedirs(os.path.dirname(app.config['LOG_FILE']), exist_ok=True)

        # Validate critical configuration
        Config._validate_config(app)

    @staticmethod
    def _validate_config(app):
        """Validate critical configuration parameters."""
        required_env_vars = [
            'DB_USER', 'DB_PASSWORD', 'DB_NAME'
        ]

        missing_vars = []
        for var in required_env_vars:
            if not os.environ.get(var):
                missing_vars.append(var)

        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

        # Validate database connection (basic check)
        if not app.config['DB_HOST']:
            raise ValueError("DB_HOST is required")

        # Validate upload directory is writable
        upload_dir = app.config['UPLOAD_FOLDER']
        if not os.access(upload_dir, os.W_OK):
            raise ValueError(f"Upload directory is not writable: {upload_dir}")

class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True
    LOG_LEVEL = 'DEBUG'

    # Development database (can be different from production)
    DB_HOST = os.environ.get('DEV_DB_HOST', 'localhost')
    DB_NAME = os.environ.get('DEV_DB_NAME', 'ocr_dev')

    # Relaxed settings for development
    OCR_CONFIDENCE_THRESHOLD = 0.3  # Lower threshold for testing
    MAX_PROCESSING_TIME = 600  # Longer timeout for debugging

class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False
    TESTING = False

    # Strict security settings
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable is required in production")

    # Production database
    DB_HOST = os.environ.get('DB_HOST')
    DB_USER = os.environ.get('DB_USER')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    DB_NAME = os.environ.get('DB_NAME')

    # Stricter OCR settings
    OCR_CONFIDENCE_THRESHOLD = 0.7  # Higher quality threshold
    MAX_PROCESSING_TIME = 180  # Shorter timeout for performance

    # Enhanced logging
    LOG_LEVEL = 'WARNING'

class TestingConfig(Config):
    """Testing configuration."""

    TESTING = True
    DEBUG = True

    # Test database
    DB_HOST = os.environ.get('TEST_DB_HOST', 'localhost')
    DB_NAME = os.environ.get('TEST_DB_NAME', 'ocr_test')

    # Fast settings for testing
    OCR_CONFIDENCE_THRESHOLD = 0.1  # Very low for test reliability
    MAX_PROCESSING_TIME = 60  # Short timeout for fast tests

    # In-memory session for testing
    SESSION_TYPE = 'filesystem'
    WTF_CSRF_ENABLED = False

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config(config_name=None):
    """Get configuration class based on environment."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    config_class = config.get(config_name.lower(), config['default'])
    return config_class