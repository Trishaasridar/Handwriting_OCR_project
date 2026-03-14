"""
Configuration management for Handwriting OCR Application v3.
Uses SQLite3 — no external database server required.
"""

import os
from datetime import timedelta


class Config:
    """Base configuration class."""

    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = False
    TESTING = False

    # SQLite Database path
    DB_PATH = os.environ.get('DB_PATH') or os.path.join(os.getcwd(), 'ocr.db')

    # File Upload Configuration
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp'}

    # OCR Configuration
    OCR_CONFIDENCE_THRESHOLD = float(os.environ.get('OCR_CONFIDENCE_THRESHOLD', 0.6))
    OCR_LANGUAGE = os.environ.get('OCR_LANGUAGE', 'en')
    OCR_ENABLE_SPELL_CHECK = os.environ.get('OCR_ENABLE_SPELL_CHECK', 'false').lower() == 'true'

    # Processing Configuration
    MAX_PROCESSING_TIME = int(os.environ.get('MAX_PROCESSING_TIME', 300))
    CLEANUP_TEMP_FILES = os.environ.get('CLEANUP_TEMP_FILES', 'true').lower() == 'true'

    # Pagination Configuration
    RESULTS_PER_PAGE = int(os.environ.get('RESULTS_PER_PAGE', 8))

    # Logging Configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.path.join(os.getcwd(), 'logs', 'app.log')

    # Session Configuration
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)

    # API metadata
    API_TITLE = 'Handwriting OCR API v3'
    API_VERSION = '3.0.0'

    @staticmethod
    def init_app(app):
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(os.path.dirname(app.config['LOG_FILE']), exist_ok=True)


class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = 'DEBUG'
    OCR_CONFIDENCE_THRESHOLD = 0.3


class ProductionConfig(Config):
    DEBUG = False

    @staticmethod
    def init_app(app):
        Config.init_app(app)
        if not os.environ.get('SECRET_KEY'):
            raise ValueError("SECRET_KEY environment variable is required in production")


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    DB_PATH = ':memory:'
    OCR_CONFIDENCE_THRESHOLD = 0.1


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    return config.get(config_name.lower(), config['default'])
