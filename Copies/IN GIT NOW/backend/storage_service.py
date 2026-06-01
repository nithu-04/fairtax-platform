import os, uuid
from werkzeug.utils import secure_filename
from config import Config

ALLOWED = {"pdf", "jpg", "jpeg", "png"}

def save_file(file_storage, submission_id):
    """Save uploaded file locally, return public URL."""
    print(f"[STORAGE] save_file called: submission_id={submission_id}, filename={file_storage.filename}")

    # Use absolute path to ensure it works from any working directory
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    upload_base = os.path.join(backend_dir, Config.UPLOAD_DIR)

    print(f"[STORAGE] Backend directory: {backend_dir}")
    print(f"[STORAGE] Upload base: {upload_base}")
    print(f"[STORAGE] Current working directory: {os.getcwd()}")

    # Create base uploads directory
    os.makedirs(upload_base, exist_ok=True)
    print(f"[STORAGE] [OK] Created/ensured upload_base exists")

    # Create submission-specific directory
    user_dir = os.path.join(upload_base, str(submission_id or "anon"))
    print(f"[STORAGE] user_dir: {user_dir}")

    os.makedirs(user_dir, exist_ok=True)
    print(f"[STORAGE] [OK] Created/ensured user_dir exists")

    ext = file_storage.filename.rsplit(".", 1)[-1].lower()
    print(f"[STORAGE] File extension: {ext}")

    if ext not in ALLOWED:
        print(f"[STORAGE] [ERROR] Extension not allowed: {ext}, allowed: {ALLOWED}")
        return None

    fname = f"{uuid.uuid4().hex[:8]}_{secure_filename(file_storage.filename)}"
    fpath = os.path.join(user_dir, fname)
    print(f"[STORAGE] Full absolute path: {fpath}")

    try:
        # Read file content and save directly
        file_storage.seek(0)
        file_content = file_storage.read()
        print(f"[STORAGE] File content size: {len(file_content)} bytes")

        if not file_content or len(file_content) == 0:
            print(f"[STORAGE] [ERROR] File content is empty!")
            return None

        # Write file directly to disk
        with open(fpath, 'wb') as f:
            f.write(file_content)
        print(f"[STORAGE] [OK] Wrote {len(file_content)} bytes to disk")

        # Verify file was actually saved
        if os.path.exists(fpath):
            actual_size = os.path.getsize(fpath)
            print(f"[STORAGE] [SUCCESS] File saved successfully ({actual_size} bytes)")
            if actual_size == 0:
                print(f"[STORAGE] [WARN] File saved but size is 0!")
                return None
        else:
            print(f"[STORAGE] [ERROR] File doesn't exist after write")
            return None

    except Exception as e:
        print(f"[STORAGE] [ERROR] Error saving file: {e}")
        import traceback
        traceback.print_exc()
        return None

    url = f"{Config.PUBLIC_BASE_URL}/uploads/{submission_id}/{fname}"
    print(f"[STORAGE] [OK] Generated URL: {url}")
    return url