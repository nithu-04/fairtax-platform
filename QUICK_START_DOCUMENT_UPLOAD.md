# Quick Start: Document Upload on Render

## What Was Implemented

✅ **Documents saved immediately on upload** - not waiting for extraction  
✅ **Persistent storage on Render disk** - survives deployments  
✅ **Stored in Google Sheets** - as separate columns per document type  
✅ **Non-blocking** - extraction continues even if upload fails  

## 3-Step Deployment

### Step 1: Create Render Persistent Disk

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Select your Service
3. Go to **Disks** tab
4. Click **Create Disk**
   - Name: `uploads`
   - Size: `1 GB` (adjust as needed)
   - Mount path: `/mnt/uploads`
5. Click **Create Disk**
6. Service will restart

### Step 2: Set Environment Variable

In Render Dashboard → Service → Environment:

Add:
```
RENDER_MOUNT_PATH=/mnt/uploads
```

Save and service will restart.

### Step 3: Deploy Code

All code changes are ready. Just push to GitHub:

```bash
git add .
git commit -m "feat: immediate document upload with persistent storage"
git push origin main
```

Render will auto-deploy.

## Verify It Works

### Local Test (Before Deployment)

```bash
# Start backend
cd backend
pip install -r requirements.txt
python app.py

# In another terminal, test upload
curl -X POST http://localhost:5000/api/upload-document \
  -F "submission_id=test-123" \
  -F "doc_type=form16" \
  -F "documents=@/path/to/form16.pdf"
```

Response:
```json
{
  "success": true,
  "urls": ["/uploads/test-123/abc123_form16.pdf"],
  "message": "Successfully saved 1 document(s)"
}
```

Check file exists:
```bash
ls -la backend/uploads/test-123/
# Should show: abc123_form16.pdf
```

### Deployed Test (After Pushing to Render)

1. Go to your app: `https://your-app.onrender.com`
2. Navigate to "File Returns"
3. Go to Step 3 (Documents)
4. Select a Form 16 file
5. Watch status: "💾 Saving document..." → "🔍 AI reading document..."
6. Open Google Sheet, check `doc_form16_urls` column
7. You should see: `/uploads/{submission_id}/uuid_form16.pdf`
8. Click the URL - it should download the PDF

## How It Works

```
User selects file on Step 3
         ↓
uploadDocumentImmediately() called immediately
         ↓
/api/upload-document saves to /mnt/uploads/{submission_id}/{filename}
         ↓
URL stored in Google Sheets (doc_form16_urls, doc_payslip_urls, etc.)
         ↓
Status shows: "💾 Saving document..."
         ↓
Then extraction starts
         ↓
Status shows: "🔍 AI reading document..."
         ↓
Extraction results shown to user
```

## API Endpoint

### POST /api/upload-document

Save documents immediately (before extraction)

**Request:**
```
submission_id: "abc-123"
doc_type: "form16" | "payslip" | "homeloan" | "school" | "nps" | "insurance" | "donation"
documents: [File1, File2, ...]  # Multiple files OK
```

**Response:**
```json
{
  "success": true,
  "submission_id": "abc-123",
  "doc_type": "form16",
  "urls": ["/uploads/abc-123/uuid_form16.pdf"],
  "column_name": "doc_form16_urls"
}
```

## Files Modified

1. `backend/storage_service.py` - New upload logic
2. `backend/app.py` - New `/api/upload-document` endpoint
3. `backend/config.py` - GCS config (for future use)
4. `backend/requirements.txt` - Added google-cloud-storage
5. `frontend/app.js` - New `uploadDocumentImmediately()` function
6. Created: `DOCUMENT_UPLOAD_IMPLEMENTATION.md` - Full technical guide

## Troubleshooting

### Files not saving?
1. Check Render disk created and mounted: `df -h | grep /mnt/uploads`
2. Verify `RENDER_MOUNT_PATH=/mnt/uploads` environment variable is set
3. Check backend logs for `[STORAGE]` errors

### URLs not in Google Sheets?
1. Verify Google Sheets credentials are configured
2. Check logs for `[UPLOAD_DOCUMENT]` messages
3. Make sure `GOOGLE_SHEET_ID` is set

### Can't download files?
1. Verify URL format: `/uploads/{submission_id}/{filename}`
2. Check file exists: `ls -la /mnt/uploads/{submission_id}/`
3. Ensure Render app is running and healthy

## Key Benefits

🎯 **User Protection** - Documents saved even if extraction fails  
🎯 **Auditor Access** - All files in Google Sheets for easy review  
🎯 **Deployment Safe** - Persistent disk survives restarts  
🎯 **Non-Blocking** - Upload failures don't break user flow  
🎯 **Scalable** - Can upgrade to AWS S3 later if needed  

## Next Steps

1. Deploy to Render (git push)
2. Create Render disk
3. Set environment variable
4. Test in browser
5. Done!

Questions? Check `DOCUMENT_UPLOAD_IMPLEMENTATION.md` for detailed docs.
