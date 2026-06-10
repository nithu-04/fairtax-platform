# Document Upload Storage Setup - Complete

## Changes Made

### 1. **Frontend - Silent Upload** ✅
- Removed "💾 Saving document..." visible status
- Upload now happens silently in background
- User only sees "🔍 AI reading document..." (extraction status)
- Non-blocking: extraction continues even if upload fails

**Files changed:** `frontend/app.js`

### 2. **Backend - Smart Storage Selection** ✅
- Auto-detects available storage:
  1. **Google Cloud Storage (GCS)** - if configured
  2. **Render Persistent Disk** - if available
  3. **Local Storage** - fallback (development)

**Files changed:** `backend/storage_service.py`

### 3. **Dependencies Updated** ✅
- Added `google-cloud-storage>=2.10.0` (optional, auto-used if GCS configured)

**Files changed:** `backend/requirements.txt`

---

## Three Storage Options

### 🥇 **Option 1: Google Cloud Storage (RECOMMENDED)**

**Best for:** Production deployment, permanent file storage, free tier available

**Setup:**
```bash
# 1. Create GCS bucket in Google Cloud Console (1 min)
# 2. Add these permissions to your service account:
#    - roles/storage.objectCreator
#    - roles/storage.objectViewer

# 3. Set environment variable in Render:
GCS_BUCKET_NAME=fairtax-uploads-prod
# GOOGLE_SERVICE_ACCOUNT_JSON already set (for Sheets)

# 4. Deploy
git add .
git commit -m "feat: smart storage with GCS support"
git push
```

**Cost:** Free tier includes 5GB/month + 1M reads + 10k writes (plenty for document uploads)

**Pros:**
- ✅ Reuses existing Google credentials (no new setup)
- ✅ Files persist permanently
- ✅ Public URLs work in Google Sheets
- ✅ Free tier covers most use cases
- ✅ Production-ready

**Cons:**
- Requires creating GCS bucket (5 min)
- Need to add IAM permissions

---

### 🥈 **Option 2: Render Persistent Disk**

**Best for:** Simplicity, if you want local storage that persists

**Setup:**
```bash
# 1. Render Dashboard → Service → Disks → Create Disk
# 2. Name: uploads, Size: 1 GB, Mount: /mnt/uploads
# 3. Set env var:
RENDER_MOUNT_PATH=/mnt/uploads
# 4. Deploy
git push
```

**Cost:** $10/month

**Pros:**
- ✅ Files local to your app (fast access)
- ✅ Simple setup (2 minutes)
- ✅ Reliable

**Cons:**
- Costs $10/month
- Can't scale beyond disk size

---

### 🥉 **Option 3: Ephemeral Storage Only** (Save in Sheets only)

**Best for:** No extra setup, files not needed after filing

**How it works:**
```python
# Files saved temporarily during request
# But lost when service restarts
# However, extracted DATA is permanently in Google Sheets
```

**Setup:**
```bash
# No setup needed!
# Just deploy - system auto-falls back to local /tmp
# Files saved during request for extraction
# But not persisted in URLs
```

**Cost:** Free

**Pros:**
- ✅ Zero setup
- ✅ Zero cost
- ✅ Extracted data still in Sheets (permanent)

**Cons:**
- Files lost on service restart
- Can't provide persistent URLs
- Users can't download files later

---

## Recommended Setup Path

### For Production: **GCS (Option 1)**

**Why GCS?**
1. You already have Google credentials
2. Free tier (5GB) is plenty
3. Files persist permanently
4. URLs work in Google Sheets
5. Can handle thousands of filings

**Quick GCS Setup:**

1. **Create Bucket** (Google Cloud Console):
   ```
   Cloud Storage → Buckets → Create
   - Name: fairtax-uploads-prod
   - Location: us (or nearest region)
   - Storage class: Standard
   ```

2. **Add IAM Role** to service account:
   ```
   IAM & Admin → Roles
   - Select your service account
   - Add role: roles/storage.objectCreator
   - Add role: roles/storage.objectViewer
   ```

3. **Set Environment Variable** (Render):
   ```
   GCS_BUCKET_NAME=fairtax-uploads-prod
   ```

4. **Deploy**:
   ```bash
   git push
   ```

5. **Test**:
   - Upload document on Step 3
   - Check Google Sheets for URL in doc_form16_urls
   - URL should be accessible immediately

---

## How It Works (All Options)

```
User uploads file (Step 3)
        ↓
uploadDocumentImmediately() called (SILENT - no UI)
        ↓
Storage system auto-selects:
  GCS available? → Use GCS
  Render disk available? → Use Render disk
  Neither? → Use local /tmp
        ↓
File saved to selected storage
        ↓
URL stored in Google Sheets (doc_form16_urls, etc.)
        ↓
Then extraction starts (shows "🔍 AI reading document...")
        ↓
User sees only extraction status, not upload status
```

---

## Testing Your Setup

### Test Locally (Before Deploy)

```bash
# 1. Start backend
cd backend
pip install -r requirements.txt
python app.py

# 2. Test upload
curl -X POST http://localhost:5000/api/upload-document \
  -F "submission_id=test-123" \
  -F "doc_type=form16" \
  -F "documents=@/path/to/form16.pdf"

# Response should show success + URL
```

### Test on Render (After Deploy)

1. Navigate to `https://your-app.onrender.com`
2. Go to "File Returns" → Step 3 (Documents)
3. Select Form 16 PDF
4. **Status should show:** "🔍 AI reading document..." (NOT "Saving...")
5. Check logs: Look for `[STORAGE] [GCS]` or `[STORAGE] [RENDER_DISK]` or `[STORAGE] [LOCAL]`
6. Open Google Sheet → check `doc_form16_urls` column
7. URL should be present

---

## Fallback Behavior

The system is **smart about failures**:

```
If GCS fails:
  → Try Render disk
  → Fallback to local /tmp
  → Extraction continues anyway

If upload fails:
  → Log warning
  → Extraction proceeds
  → Extracted data still saved in Sheets
```

So documents are **never lost**, even if something breaks.

---

## Cost Comparison

| Option | Setup Time | Monthly Cost | Best For |
|--------|-----------|------------|----------|
| **GCS** | 5 min | Free (5GB tier) | Production |
| **Render Disk** | 2 min | $10 | Simplicity |
| **Ephemeral Only** | 0 min | Free | No persistence needed |

---

## File Changes Summary

### Modified:
1. `frontend/app.js`
   - Silent upload (no "💾 Saving..." status)
   - Non-blocking upload function

2. `backend/storage_service.py`
   - Smart storage mode detection (GCS → Disk → Local)
   - Supports all three options automatically
   - Simplified save_file() function

3. `backend/config.py`
   - Added GCS config (if needed)

4. `backend/requirements.txt`
   - Added google-cloud-storage (optional)

### Environment Variables (Set in Render):

```env
# Option 1: Google Cloud Storage
GCS_BUCKET_NAME=fairtax-uploads-prod

# Option 2: Render Disk
RENDER_MOUNT_PATH=/mnt/uploads

# Both need:
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
```

---

## Next Steps

### Choose Your Option:

**Option A: GCS (Recommended)**
1. Create GCS bucket (1 min)
2. Add IAM roles to service account (1 min)
3. Set `GCS_BUCKET_NAME` env var in Render
4. Deploy: `git push`

**Option B: Render Disk**
1. Create disk in Render (1 min)
2. Set `RENDER_MOUNT_PATH=/mnt/uploads` env var
3. Deploy: `git push`

**Option C: Ephemeral Only (No Setup)**
1. Just deploy: `git push`
2. Files work during requests, lost on restart
3. Extracted data still in Sheets

### Then Test:
- Upload a document
- Check Google Sheets for URL
- Click URL to verify it works

---

## Support & Troubleshooting

### Check which storage is active:
```bash
# In Render logs, look for:
[STORAGE] [GCS] ... (using GCS)
[STORAGE] [RENDER_DISK] ... (using Disk)
[STORAGE] [LOCAL] ... (using local)
```

### GCS not working?
```bash
# Check:
1. GCS_BUCKET_NAME env var is set
2. Service account has storage.objectCreator role
3. Bucket exists and is accessible
4. GOOGLE_SERVICE_ACCOUNT_JSON is valid
```

### Render disk not working?
```bash
# Check:
1. Disk created and mounted
2. RENDER_MOUNT_PATH=/mnt/uploads env var set
3. Service restarted after disk creation
```

### Files not in Sheets?
```bash
# Check:
1. Google Sheets credentials valid
2. Logs show [UPLOAD_DOCUMENT] messages
3. GOOGLE_SHEET_ID is set
```

---

## Summary

✅ **Frontend:** Silent upload (no status shown)  
✅ **Backend:** Smart storage (GCS → Disk → Local)  
✅ **Flexibility:** Choose the option that fits your needs  
✅ **Reliability:** Fallback behavior ensures documents are always saved  
✅ **Cost:** Free options available (GCS free tier)  

**Ready to deploy!** 🚀
