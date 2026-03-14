#!/usr/bin/env python3
"""
Main entry point for Handwriting OCR Application v2.

This script starts the development server with debug mode enabled.
For production deployment, use run.py instead.
"""

import os
import sys
from app import create_app

def main():
    """Main application entry point."""
    # Add current directory to Python path
    sys.path.insert(0, os.path.dirname(__file__))

    # Get configuration from environment
    config_name = os.environ.get('FLASK_ENV', 'development')

    # Create and configure the app
    app = create_app()

    # Development server configuration
    if config_name == 'development':
        app.run(
            host='0.0.0.0',
            port=int(os.environ.get('PORT', 5000)),
            debug=True,
            use_reloader=True,
            threaded=True
        )
    else:
        # Production server (use WSGI server instead)
        print("For production deployment, use a WSGI server with run.py")
        print("Example: gunicorn -w 4 -b 0.0.0.0:8000 run:application")

if __name__ == '__main__':
    main()