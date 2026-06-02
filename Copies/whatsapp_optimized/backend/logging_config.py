"""Configure logging BEFORE any other imports to suppress library DEBUG messages."""
import logging
import sys
import io
import os

# ===== Import monkey-patch FIRST =====
import disable_pdfplumber_debug

# ===== STEP 1: Disable pdfplumber debug via environment BEFORE import =====
os.environ['PDFPLUMBER_DEBUG'] = '0'
os.environ['PYTHONWARNINGS'] = 'ignore'

# ===== STEP 2: Suppress ALL logging at the ROOT level =====
# This is the NUCLEAR option - suppress everything, then only enable what we want
logging.root.setLevel(logging.CRITICAL)  # CRITICAL = 50, only show CRITICAL/ERROR
logging.disable(logging.DEBUG)  # Completely disable DEBUG level globally

# ===== STEP 3: Custom stderr filter to BLOCK all non-app output =====
class StrictDebugFilter(object):
    """Aggressively filters out all DEBUG/library output"""
    def __init__(self, original_stderr):
        self.original_stderr = original_stderr
        self.blocked_keywords = [
            'DEBUG', 'debug', 'psparser', 'pdfinterp', 'pdfminer',
            'urllib3', 'connectionpool', 'Retrying', 'http.connectionpool'
        ]

    def write(self, message):
        # BLOCK if contains ANY blocked keyword
        for keyword in self.blocked_keywords:
            if keyword in message:
                return len(message)  # Pretend we wrote it, but don't actually
        # Only write app-level output
        return self.original_stderr.write(message)

    def flush(self):
        self.original_stderr.flush()

    def isatty(self):
        return self.original_stderr.isatty()

# Replace stderr IMMEDIATELY
sys.stderr = StrictDebugFilter(sys.stderr)

# ===== STEP 4: Configure ONLY app logging (INFO level) =====
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('flask_app.log'),
        logging.StreamHandler(sys.stdout)
    ],
    force=True  # Override any existing config
)

# ===== STEP 5: Get root logger and set to CRITICAL (block debug from all libraries) =====
root_logger = logging.getLogger()
root_logger.setLevel(logging.CRITICAL)

# ===== STEP 6: AGGRESSIVELY suppress ALL library loggers =====
noisy_loggers = [
    "urllib3", "google", "googleapiclient", "requests", "gcloud",
    "openai", "httpx", "pdfplumber", "pypdf", "psparser",
    "pdfinterp", "pdfdocument", "PDF", "PIL", "jinja2", "werkzeug",
    "pdfminer", "pdfminer.pdfpage", "pdfminer.converter",
    "pdfminer.pdfinterp", "pdfminer.psparser"
]

for logger_name in noisy_loggers:
    lib_logger = logging.getLogger(logger_name)
    lib_logger.setLevel(logging.CRITICAL)  # CRITICAL = highest, blocks everything below
    lib_logger.propagate = False
    # Remove ALL handlers
    for handler in lib_logger.handlers[:]:
        lib_logger.removeHandler(handler)
    # Add a null handler so the logger doesn't complain
    lib_logger.addHandler(logging.NullHandler())

# ===== STEP 7: Disable propagation from ALL loggers =====
for logger_name in list(logging.Logger.manager.loggerDict.keys()):
    if not logger_name.startswith('app') and not logger_name == '__main__':
        logging.getLogger(logger_name).propagate = False

# ===== STEP 8: Get app logger (only this one logs) =====
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = True  # App logger CAN propagate

print("[LOGGING_CONFIG] Initialized - all DEBUG suppressed, only INFO/ERROR/CRITICAL will appear")
