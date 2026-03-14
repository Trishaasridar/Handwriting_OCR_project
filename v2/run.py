#!/usr/bin/env python3
"""
Alternative entry point for Handwriting OCR Application v2.

Use this for production deployment with WSGI servers.
"""

import os
from app import create_app, config

# Get configuration from environment
config_name = os.environ.get('FLASK_ENV', 'production')
application = create_app(config.get_config(config_name))

if __name__ == '__main__':
    application.run()