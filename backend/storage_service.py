import os, uuid, json
from werkzeug.utils import secure_filename
from config import Config

ALLOWED = {"pdf", "jpg", "jpeg", "png"}

# Use persistent disk (configured in config.py UPLOAD_DIR)
STORAGE_BASE = Config.UPLOAD_DIR
print(f"[STORAGE] Using persistent disk: {STORAGE_BASE}")

def save_file(file_storage, submission_id, doc_type="document"):
    """Save uploaded file to persistent disk.

    Args:
        file_storage: Werkzeug FileStorage object
        submission_id: Unique identifier for the submission
        doc_type: Type of document (form16, payslip, homeloan, etc.)

    Returns:
        str: Public URL to the saved file, or None if failed
    """
    print(f"[STORAGE] Saving: {file_storage.filename} (doc_type={doc_type})")

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
        print(f"[STORAGE] [OK] Saved: {url}")
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
    """Save PDF to persistent disk.

    Args:
        pdf_content: PDF file bytes
        submission_id: Unique identifier
        filename: Name of the PDF file

    Returns:
        str: URL to the saved PDF, or None if failed
    """
    print(f"[STORAGE] [PDF] Saving {filename} for {submission_id}")

    try:
        submission_dir = os.path.join(STORAGE_BASE, str(submission_id or "anon"), "quotes")
        os.makedirs(submission_dir, exist_ok=True)
        fpath = os.path.join(submission_dir, filename)

        with open(fpath, 'wb') as f:
            f.write(pdf_content)

        url = f"{Config.PUBLIC_BASE_URL}/api/download-quote/{submission_id}/{filename}"
        print(f"[STORAGE] [PDF] [OK] Saved: {url}")
        return url
    except Exception as e:
        print(f"[STORAGE] [PDF] [FAIL] Failed to save: {e}")
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
