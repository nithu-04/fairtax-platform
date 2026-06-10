# Render Storage Options (Without Paid Disk)

## The Problem
Render's default filesystem is **ephemeral** - files disappear when the service restarts or redeployes. Paid persistent disks solve this, but you want free alternatives.

## Options Compared

| Option | Cost | Persistence | Setup | Best For |
|--------|------|-------------|-------|----------|
| **Ephemeral Storage** (/tmp) | Free | During runtime only | None | Temporary files during requests |
| **Google Cloud Storage (GCS)** | Free tier (5GB) | Permanent | 5 min | Production uploads (recommended) |
| **Google Drive API** | Free | Permanent | 10 min | Simpler integration with Sheets |
| **AWS S3** | Free tier (5GB) | Permanent | 10 min | If you prefer AWS |
| **Render Disk** | $10+/month | Permanent | 2 min | Maximum reliability |

## Recommended: Google Cloud Storage (GCS)

### Why GCS?
✅ You already have Google credentials (for Sheets)  
✅ Reuse same service account (no new credentials needed)  
✅ Free tier: 5GB/month + 1M reads + 10k writes  
✅ Public URLs auto-generated (perfect for Google Sheets links)  
✅ Works perfectly with extraction workflow  

### Setup (5 minutes)

#### 1. Create GCS Bucket

In Google Cloud Console:
1. Go to Cloud Storage → Buckets
2. Create Bucket
   - Name: `fairtax-uploads-prod` (globally unique)
   - Location: Region closest to users
   - Storage class: Standard
   - Access control: Fine-grained (private by default)
3. Create

#### 2. Add Bucket Permissions to Service Account

1. Go to Service Accounts
2. Find your service account (used for Sheets)
3. Go to IAM & Admin → Roles
4. Add roles:
   - `roles/storage.objectCreator` (can upload)
   - `roles/storage.objectViewer` (can read)

#### 3. Update Backend Code

Modify `storage_service.py`:

```python
import os
import json
from google.cloud import storage
from google.oauth2.service_account import Credentials
from config import Config

# Use GCS if configured, otherwise fallback to ephemeral /tmp
USE_GCS = bool(os.getenv("GCS_BUCKET_NAME"))
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "fairtax-uploads-prod")

# Initialize GCS client
_GCS_CLIENT = None

def _get_gcs_client():
    global _GCS_CLIENT
    if _GCS_CLIENT is not None:
        return _GCS_CLIENT
    
    try:
        service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        if not service_account_json:
            print("[GCS] No credentials found")
            return None
        
        credentials_dict = json.loads(service_account_json)
        credentials = Credentials.from_service_account_info(credentials_dict)
        project = credentials_dict.get("project_id", "")
        
        _GCS_CLIENT = storage.Client(credentials=credentials, project=project)
        print(f"[GCS] Client initialized for project {project}")
        return _GCS_CLIENT
    except Exception as e:
        print(f"[GCS] Failed to initialize: {e}")
        return None

def save_file_gcs(file_storage, submission_id, doc_type="document"):
    """Save file to Google Cloud Storage."""
    client = _get_gcs_client()
    if not client:
        print("[GCS] Client unavailable, using ephemeral storage")
        return save_file_ephemeral(file_storage, submission_id, doc_type)
    
    try:
        bucket = client.bucket(GCS_BUCKET_NAME)
        
        # Generate filename
        fname = f"{uuid.uuid4().hex[:8]}_{secure_filename(file_storage.filename)}"
        blob_path = f"uploads/{submission_id}/{fname}"
        blob = bucket.blob(blob_path)
        
        # Upload
        file_storage.seek(0)
        blob.upload_from_string(
            file_storage.read(),
            content_type=file_storage.mimetype or "application/octet-stream"
        )
        
        # Make publicly readable (so URLs work in Sheets)
        blob.make_public()
        
        url = blob.public_url
        print(f"[GCS] Uploaded: {url}")
        return url
        
    except Exception as e:
        print(f"[GCS] Upload failed: {e}")
        return None

def save_file_ephemeral(file_storage, submission_id, doc_type="document"):
    """Save to ephemeral /tmp storage (lost on restart)."""
    import tempfile
    
    try:
        tmpdir = f"/tmp/fairtax/{submission_id}"
        os.makedirs(tmpdir, exist_ok=True)
        
        fname = f"{uuid.uuid4().hex[:8]}_{secure_filename(file_storage.filename)}"
        fpath = os.path.join(tmpdir, fname)
        
        file_storage.seek(0)
        with open(fpath, 'wb') as f:
            f.write(file_storage.read())
        
        # WARNING: Only valid until next restart!
        url = f"⚠️ EPHEMERAL: {fname} (lost on service restart)"
        print(f"[EPHEMERAL] Saved (temporary): {fname}")
        return url
        
    except Exception as e:
        print(f"[EPHEMERAL] Save failed: {e}")
        return None

def save_file(file_storage, submission_id, doc_type="document"):
    """Smart save: tries GCS, falls back to ephemeral."""
    if USE_GCS:
        return save_file_gcs(file_storage, submission_id, doc_type)
    else:
        print("[STORAGE] GCS not configured, using ephemeral /tmp")
        return save_file_ephemeral(file_storage, submission_id, doc_type)
```

#### 4. Set Environment Variable

In Render Dashboard:
```env
GCS_BUCKET_NAME=fairtax-uploads-prod
# GOOGLE_SERVICE_ACCOUNT_JSON already set (for Sheets)
```

#### 5. Deploy

```bash
pip install google-cloud-storage
git add .
git commit -m "feat: add GCS storage support"
git push
```

---

## Alternative: Google Drive API

If you want to avoid another service:

### Setup (10 minutes)

1. **Enable Google Drive API** in Google Cloud Console
2. **Share folder** with your service account email
3. **Use pydrive library:**

```python
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

def save_file_gdrive(file_storage, submission_id):
    gauth = GoogleAuth()
    gauth.Authorize()
    drive = GoogleDrive(gauth)
    
    file_list = drive.ListFile({
        'q': f"title='{submission_id}' and trashed=false"
    }).GetList()
    
    if not file_list:
        folder = drive.CreateFile({
            'title': submission_id,
            'mimeType': 'application/vnd.google-apps.folder'
        })
        folder.Upload()
        folder_id = folder['id']
    else:
        folder_id = file_list[0]['id']
    
    file_obj = drive.CreateFile({
        'title': file_storage.filename,
        'parents': [{'id': folder_id}]
    })
    file_obj.SetContentString(file_storage.read())
    file_obj.Upload()
    
    return f"https://drive.google.com/file/d/{file_obj['id']}"
```

---

## Ephemeral Storage (Free, No Setup)

Use the default `/tmp` directory:

```python
import tempfile
import os

def save_file_ephemeral(file_storage, submission_id):
    tmpdir = f"/tmp/fairtax-uploads/{submission_id}"
    os.makedirs(tmpdir, exist_ok=True)
    
    fname = secure_filename(file_storage.filename)
    fpath = os.path.join(tmpdir, fname)
    
    file_storage.save(fpath)
    
    # URL won't work - files disappear on restart
    # But extraction data is saved in Google Sheets
    return None  # Don't store URL
```

**Pros:**
- Zero setup
- Zero cost
- Works during request lifetime

**Cons:**
- Files lost on service restart/redeploy
- Can't provide persistent URLs
- Only useful for extraction, not reference

---

## Comparison: Which to Choose?

### Use **GCS** if:
- ✅ You want permanent file storage
- ✅ You need URLs in Google Sheets
- ✅ Users should access documents later
- ✅ Auditors need to download files

### Use **Google Drive** if:
- ✅ You want to keep everything in Google ecosystem
- ✅ You prefer Drive interface for file management
- ✅ Want sharing/permissions built-in

### Use **Ephemeral Only** if:
- ✅ You only care about extraction during filing
- ✅ Don't need persistent document references
- ✅ Want absolutely zero setup/cost
- ✅ Files aren't needed after extraction

### Use **Render Disk** if:
- ✅ You want maximum reliability
- ✅ Can afford $10/month
- ✅ Need fastest access (local disk)

---

## Implementation Plan

### Option 1: GCS (Recommended - 5 min setup)

**Pros:** Free tier covers most uses, instant setup, reuses credentials  
**Cons:** Requires GCS bucket creation, slightly more setup than ephemeral

```bash
# 1. Create bucket in Google Cloud Console (1 min)
# 2. Update service account IAM (1 min)
# 3. Update storage_service.py (3 min)
# 4. Add env var in Render (auto-deploys)
```

### Option 2: Ephemeral Only (0 min setup)

**Pros:** No setup needed, documents saved during extraction  
**Cons:** Lost on restart, no persistent URLs in Sheets

```python
# Just use /tmp, don't store URLs
```

### Option 3: Ephemeral + Sheets Backup (10 min setup)

**Pros:** Documents available during request, extraction data permanently in Sheets  
**Cons:** Can't download original files after service restart

```python
# Save to /tmp for extraction
# Store extracted JSON in Sheets (you already do this!)
# Don't store URLs
```

---

## My Recommendation

**Go with GCS because:**

1. ✅ **Reuse existing credentials** - no new API keys needed
2. ✅ **Free tier** - 5GB/month is plenty for documents
3. ✅ **Public URLs** - URLs work in Google Sheets automatically
4. ✅ **Production-ready** - won't lose files on restart
5. ✅ **5 minute setup** - quick and painless
6. ✅ **Scales easily** - upgrade storage as needed

---

## Cost Estimate (GCS)

**Typical usage per user:**
- Form 16: ~200 KB
- Payslip: ~100 KB
- Home Loan cert: ~150 KB
- Insurance: ~100 KB
- Total: ~550 KB per filing

**At 550 KB per filing:**
- 5GB free tier = 9,090 filings/month
- Operations: 5GB free includes plenty of read/write operations
- Cost: **$0 unless you exceed 5GB/month** (then ~$0.02 per GB)

---

## Next Steps

1. **Decide:** GCS (recommended), Drive, or Ephemeral?
2. **If GCS:** Create bucket (1 min)
3. **Update code:** Use provided GCS implementation
4. **Deploy:** `git push`
5. **Done!**

Which option interests you most?
