#!/usr/bin/env python3
"""
Entry point for Handwriting OCR Application v3.
Run with:  python app.py
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from app import create_app


def main():
    sys.path.insert(0, os.path.dirname(__file__))
    app = create_app()
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=app.debug,
        use_reloader=True,
        threaded=True,
    )


if __name__ == '__main__':
    main()
