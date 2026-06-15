import os, uuid, json
from werkzeug.utils import secure_filename
from config import Config

ALLOWED = {"pdf", "jpg", "jpeg", "png"}

# Storage mode detection (in priority order)
STORAGE_MODE = "unknown"
GCS_BUCKET = None
GCS_CLIENT = None

# Check 1: Google Cloud Storage (free tier: 5GB/month)
if os.getenv("GCS_BUCKET_NAME"):
    try:
        from google.cloud import storage as gcs_storage
        service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        if service_account_json and service_account_json.strip():
            credentials_dict = json.loads(service_account_json)
            from google.oauth2.service_account import Credentials
            credentials = Credentials.from_service_account_info(credentials_dict)
            GCS_CLIENT = gcs_storage.Client(credentials=credentials, project=credentials_dict.get("project_id"))
            GCS_BUCKET = GCS_CLIENT.bucket(os.getenv("GCS_BUCKET_NAME"))
            STORAGE_MODE = "GCS"
            print(f"[STORAGE] Using Google Cloud Storage (bucket: {GCS_BUCKET.name})")
    except Exception as e:
        print(f"[STORAGE] GCS initialization failed: {e}")

# Check 2: Render persistent disk
if STORAGE_MODE == "unknown" and os.getenv("RENDER_MOUNT_PATH"):
    STORAGE_BASE = os.getenv("RENDER_MOUNT_PATH")
    if os.path.exists(STORAGE_BASE):
        STORAGE_MODE = "RENDER_DISK"
        print(f"[STORAGE] Using Render persistent disk: {STORAGE_BASE}")

# Check 3: Local disk (development)
if STORAGE_MODE == "unknown":
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    STORAGE_BASE = os.path.join(backend_dir, Config.UPLOAD_DIR)
    STORAGE_MODE = "LOCAL"
    print(f"[STORAGE] Using local storage: {STORAGE_BASE}")

def save_file(file_storage, submission_id, doc_type="document"):
    """Save uploaded file to available storage (GCS → Render Disk → Local).

    Args:
        file_storage: Werkzeug FileStorage object
        submission_id: Unique identifier for the submission
        doc_type: Type of document (form16, payslip, homeloan, etc.)

    Returns:
        str: Public URL to the saved file, or None if failed
    """
    print(f"[STORAGE] [{STORAGE_MODE}] Saving: {file_storage.filename} (doc_type={doc_type})")

    # Validate file extension
    ext = file_storage.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED:
        print(f"[STORAGE] [ERROR] Extension not allowed: {ext}")
        return None

    # Generate unique filename
    fname = f"{uuid.uuid4().hex[:8]}_{secure_filename(file_storage.filename)}"
    file_storage.seek(0)
    file_content = file_storage.read()

    if not file_content:
        print(f"[STORAGE] [ERROR] File content is empty!")
        return None

    # STORAGE MODE 1: Google Cloud Storage
    if STORAGE_MODE == "GCS":
        try:
            from datetime import datetime, timedelta
            blob_path = f"uploads/{submission_id}/{fname}"
            blob = GCS_BUCKET.blob(blob_path)
            blob.upload_from_string(
                file_content,
                content_type=file_storage.mimetype or "application/octet-stream"
            )
            # Generate signed URL (valid for 7 days) instead of making public
            # Signed URLs don't require IAM policy changes
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(days=7),
                method="GET"
            )
            print(f"[STORAGE] [GCS] [OK] Saved: {url}")
            return url
        except Exception as e:
            print(f"[STORAGE] [GCS] [FAIL] Failed: {e}")
            return None

    # STORAGE MODE 2: Render Persistent Disk or Local
    else:
        try:
            submission_dir = os.path.join(STORAGE_BASE, str(submission_id or "anon"))
            os.makedirs(submission_dir, exist_ok=True)
            fpath = os.path.join(submission_dir, fname)

            with open(fpath, 'wb') as f:
                f.write(file_content)

            if not os.path.exists(fpath) or os.path.getsize(fpath) == 0:
                print(f"[STORAGE] [ERROR] File not saved correctly")
                return None

            url = f"{Config.PUBLIC_BASE_URL}/uploads/{submission_id}/{fname}"
            print(f"[STORAGE] [{STORAGE_MODE}] ✓ Saved: {url}")
            return url

        except Exception as e:
            print(f"[STORAGE] [ERROR] Failed to save: {e}")
            return None


def get_doc_type_column(doc_type):
    """Map document type to Google Sheets column name.

    Returns the appropriate doc_*_urls column for the given document type.
    """
    col_map = {
        "form16": "doc_form16_urls",
        "payslip": "doc_payslip_urls",
        "homeloan": "doc_homeloan_urls",
        "school": "doc_school_urls",
        "nps": "doc_nps_urls",
        "insurance": "doc_insurance_urls",
        "donation": "doc_donation_urls",
    }
    return col_map.get(doc_type, "doc_form16_urls")


def save_pdf_to_gcs(pdf_content, submission_id, filename="quote.pdf"):
    """Upload PDF bytes to GCS and return signed URL.

    Args:
        pdf_content: PDF file bytes
        submission_id: Unique identifier
        filename: Name of the PDF file

    Returns:
        str: Signed GCS URL or local URL, or None if failed
    """
    print(f"[STORAGE] [PDF] Uploading {filename} for {submission_id}")

    if STORAGE_MODE == "GCS":
        try:
            from datetime import datetime, timedelta
            blob_path = f"quotes/{submission_id}/{filename}"
            blob = GCS_BUCKET.blob(blob_path)
            blob.upload_from_string(
                pdf_content,
                content_type="application/pdf"
            )
            # Generate signed URL valid for 7 days (GCS max is 7 days, not 30)
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(days=7),
                method="GET"
            )
            print(f"[STORAGE] [GCS] [OK] PDF saved: {url}")
            return url
        except Exception as e:
            print(f"[STORAGE] [GCS] [FAIL] PDF upload failed: {e}")
            return None
    else:
        # Fallback to local/Render disk
        try:
            submission_dir = os.path.join(STORAGE_BASE, str(submission_id or "anon"), "quotes")
            os.makedirs(submission_dir, exist_ok=True)
            fpath = os.path.join(submission_dir, filename)

            with open(fpath, 'wb') as f:
                f.write(pdf_content)

            url = f"{Config.PUBLIC_BASE_URL}/api/download-quote/{submission_id}/{filename}"
            print(f"[STORAGE] [{STORAGE_MODE}] [OK] PDF saved: {url}")
            return url
        except Exception as e:
            print(f"[STORAGE] [PDF] ✗ Failed to save: {e}")
            return None


def append_urls_to_sheet(existing_urls_str, new_urls):
    """Append new URLs to existing URLs in a sheet column.

    Args:
        existing_urls_str: Existing URLs (comma-separated string or empty)
        new_urls: List of new URLs to append

    Returns:
        str: Updated comma-separated URL string
    """
    if not new_urls:
        return existing_urls_str or ""

    try:
        # Parse existing URLs
        existing = []
        if existing_urls_str and str(existing_urls_str).strip():
            existing = [u.strip() for u in str(existing_urls_str).split(',') if u.strip()]

        # Add new URLs (avoid duplicates)
        for url in new_urls:
            if url and url not in existing:
                existing.append(url)

        return ','.join(existing)
    except Exception as e:
        print(f"[STORAGE] Error appending URLs: {e}")
        return existing_urls_str or ""
