"""Configure logging BEFORE any other imports to suppress library DEBUG messages."""
import logging
import sys

# Set root logger to WARNING first (suppresses all DEBUG by default)
logging.root.setLevel(logging.WARNING)

# Configure logging for both console and file
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    handlers=[
        logging.FileHandler('flask_app.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Suppress ALL noisy library loggers with force=True and propagate=False
noisy_loggers = [
    "urllib3", "google", "googleapiclient", "requests", "gcloud",
    "openai", "httpx", "pdfplumber", "pypdf", "psparser",
    "pdfinterp", "pdfdocument", "PIL", "jinja2", "werkzeug"
]

for logger_name in noisy_loggers:
    lib_logger = logging.getLogger(logger_name)
    lib_logger.setLevel(logging.WARNING)
    lib_logger.propagate = False  # Don't propagate to root
    # Disable all handlers
    for handler in lib_logger.handlers[:]:
        lib_logger.removeHandler(handler)

# Get app logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
