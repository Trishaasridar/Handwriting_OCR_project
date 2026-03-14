"""
Handwriting OCR Application v2 - Flask Application Factory

Enhanced version with improved accuracy, security, and architecture.

Author: AI Assistant
Date: March 11, 2026
Version: 2.0.0
"""

import os
import logging
from flask import Flask
from .config import Config
from .models import init_db
from .routes import register_routes

def create_app(config_class=Config):
    """
    Application factory function for creating Flask app instances.

    Args:
        config_class: Configuration class to use (default: Config)

    Returns:
        Flask application instance
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize logging
    setup_logging(app)

    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize database
    init_db(app)

    # Register routes
    register_routes(app)

    return app

def setup_logging(app):
    """Configure application logging."""
    if not app.debug:
        # Production logging
        handler = logging.FileHandler('logs/app.log')
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)
    else:
        # Development logging
        app.logger.setLevel(logging.DEBUG)