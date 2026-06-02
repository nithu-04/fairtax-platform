import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import logging
logging.basicConfig(level=logging.INFO)

# Suppress noisy library logging
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.WARNING)
logging.getLogger("googleapiclient").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("gcloud").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("pdfplumber").setLevel(logging.WARNING)
logging.getLogger("pypdf").setLevel(logging.WARNING)
logging.getLogger("psparser").setLevel(logging.WARNING)
logging.getLogger("pdfinterp").setLevel(logging.WARNING)
logging.getLogger("pdfdocument").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)

from app import app

@app.before_request
def log_req():
    print(f"[REQUEST] {request.method} {request.path}", flush=True)

# Start Flask with logging enabled
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
