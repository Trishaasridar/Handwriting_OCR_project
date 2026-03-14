"""
Handwriting OCR Application v3 — Flask Application Factory
Uses SQLite3; no external database server required.
"""

import os
import logging
from flask import Flask
from .config import get_config
from .models import init_db
from .routes import register_routes


def create_app(config_class=None):
    if config_class is None:
        config_class = get_config()

    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object(config_class)

    setup_logging(app)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    init_db(app)
    register_routes(app)

    return app


def setup_logging(app):
    if app.debug:
        app.logger.setLevel(logging.DEBUG)
    else:
        os.makedirs('logs', exist_ok=True)
        handler = logging.FileHandler('logs/app.log')
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)
