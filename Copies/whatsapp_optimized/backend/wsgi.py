"""WSGI entry point for Render/Production.

This ensures logging_config is imported FIRST before anything else,
which suppresses all DEBUG logs from pdfplumber, urllib3, google, etc.
"""

# ===== CRITICAL: Import logging config FIRST =====
import logging_config

# NOW import the Flask app
from app import app

# For gunicorn
if __name__ == "__main__":
    app.run()
