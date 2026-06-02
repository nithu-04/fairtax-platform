"""Configure logging BEFORE any other imports to suppress library DEBUG messages."""
import logging
import sys
import io

# ===== CUSTOM STDERR FILTER to remove DEBUG lines =====
class DebugFilter(io.StringIO):
    """Filter that removes DEBUG lines from output"""
    def __init__(self, original_stderr):
        self.original_stderr = original_stderr

    def write(self, message):
        # Filter out DEBUG lines from pdfplumber internals
        if 'DEBUG in' not in message and 'psparser' not in message and 'pdfinterp' not in message:
            return self.original_stderr.write(message)
        return len(message)  # Pretend we wrote it

    def flush(self):
        self.original_stderr.flush()

# Replace stderr with our filter
original_stderr = sys.stderr
sys.stderr = DebugFilter(original_stderr)

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

# Suppress ALL noisy library loggers
noisy_loggers = [
    "urllib3", "google", "googleapiclient", "requests", "gcloud",
    "openai", "httpx", "pdfplumber", "pypdf", "psparser",
    "pdfinterp", "pdfdocument", "PIL", "jinja2", "werkzeug"
]

for logger_name in noisy_loggers:
    lib_logger = logging.getLogger(logger_name)
    lib_logger.setLevel(logging.WARNING)
    lib_logger.propagate = False
    for handler in lib_logger.handlers[:]:
        lib_logger.removeHandler(handler)

# Get app logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
