# Document Upload Implementation Guide

## Overview

This implementation adds immediate document persistence to the FairTax platform. Documents are:
1. **Saved immediately** when users upload them (not waiting for extraction)
2. **Stored persistently** on Render's persistent disk (survives deployments)
3. **Backed up in Google Sheets** as URLs in doc_type-specific columns
4. **Accessible even if** extraction fails or user cancels

## Architecture

### Storage Flow

```
User Selects File
       ↓
uploadDocumentImmediately() called
       ↓
/api/upload-document endpoint
       ↓
storage_service.save_file() 
       ↓
File saved to: /mnt/uploads/{submission_id}/{filename}
       ↓
Public URL generated: /uploads/{submission_id}/{filename}
       ↓
URL stored in Google Sheets (doc_form16_urls, doc_payslip_urls, etc.)
       ↓
Then proceed with extraction (if needed)
```

### Google Sheets Columns

Each document type has a dedicated column in Google Sheets:

```
doc_form16_urls     → /uploads/abc-123/form16.pdf, /uploads/abc-123/form16-2.pdf
doc_payslip_urls    → /uploads/abc-123/payslip.pdf
doc_homeloan_urls   → /uploads/abc-123/homeloan.pdf
doc_school_urls     → /uploads/abc-123/school.pdf
doc_nps_urls        → /uploads/abc-123/nps.pdf
doc_insurance_urls  → /uploads/abc-123/insurance.pdf
doc_donation_urls   → /uploads/abc-123/donation.pdf
```

Multiple files of the same type are comma-separated in the same cell.

## Setup Instructions

### 1. Add Render Persistent Disk

On Render dashboard:

1. Go to your Service → Disks tab
2. Click "Create Disk"
   - Name: `uploads`
   - Size: 1 GB (or larger based on expected file volume)
3. Mount path: `/mnt/uploads`
4. Restart service

Verify disk is mounted:
```bash
df -h  # Should show /mnt/uploads mounted
```

### 2. Environment Variables

Add these to your Render environment:

```env
# Render persistent disk path (Render automatically mounts here)
RENDER_MOUNT_PATH=/mnt/uploads

# Base URL for serving uploaded files
PUBLIC_BASE_URL=https://your-app.onrender.com

# Google Sheets (existing)
GOOGLE_SHEET_ID=your-sheet-id
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}

# Existing other vars...
```

### 3. Backend Setup

#### Update requirements.txt
Already done - no new dependencies needed for local/Render storage.

#### Update config.py
Already done - added GCS_BUCKET_NAME and GCS_PROJECT_ID (for future use).

#### Update storage_service.py
Already done - now supports:
- Render persistent disk (`/mnt/uploads`)
- Fallback to local storage for development
- Document type column mapping
- URL appending logic

#### New API Endpoint
Already added to app.py:
- **POST `/api/upload-document`** - Immediate document upload
  - Parameters: `submission_id`, `doc_type`, `documents` (multipart)
  - Returns: URLs and success status
  - Saves to correct Google Sheets column automatically

### 4. Frontend Setup

#### New Function Added
`uploadDocumentImmediately(inputId, docType, statusId)`
- Called before extraction
- Saves documents to persistent storage
- Updates status UI with progress
- Non-blocking if upload fails (continues to extraction)

#### Integration Points
1. `extractSectionBg()` - Auto-extraction on file select
   - Now calls uploadDocumentImmediately first
2. `extractSection()` - Manual extraction via Extract button
   - Now calls uploadDocumentImmediately first

## API Endpoints

### POST /api/upload-document

**Purpose:** Immediately save uploaded documents to persistent storage

**Request:**
```
POST /api/upload-document
Content-Type: multipart/form-data

submission_id: "abc-123"
doc_type: "form16" | "payslip" | "homeloan" | "school" | "nps" | "insurance" | "donation"
documents: [File, File, ...]  # Multiple files supported
```

**Response (Success):**
```json
{
  "success": true,
  "submission_id": "abc-123",
  "doc_type": "form16",
  "urls": [
    "/uploads/abc-123/uuid_form16.pdf",
    "/uploads/abc-123/uuid_form16-2.pdf"
  ],
  "column_name": "doc_form16_urls",
  "message": "Successfully saved 2 document(s)"
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "Invalid doc_type 'invoice'. Valid types: form16, payslip, ..."
}
```

### GET /uploads/{submission_id}/{filename}

**Purpose:** Serve uploaded files

**Handled by:** Flask static route (automatically serves from /mnt/uploads)

**Example:**
```
GET /uploads/abc-123/uuid_form16.pdf
```

## Testing

### Local Testing

1. **Start backend:**
   ```bash
   cd backend
   pip install -r requirements.txt
   python app.py
   ```

2. **Test document upload:**
   ```bash
   curl -X POST http://localhost:5000/api/upload-document \
     -F "submission_id=test-123" \
     -F "doc_type=form16" \
     -F "documents=@/path/to/form16.pdf" \
     -F "documents=@/path/to/form16-2.pdf"
   ```

3. **Verify files saved:**
   ```bash
   ls -la backend/uploads/test-123/
   # Should show: uuid_form16.pdf, uuid_form16-2.pdf
   ```

4. **Test file serving:**
   ```bash
   curl http://localhost:5000/uploads/test-123/uuid_form16.pdf
   # Should return PDF file
   ```

### Frontend Testing

1. **Start frontend:**
   ```bash
   cd frontend
   python -m http.server 8000
   ```

2. **Navigate to filing page**

3. **Upload a document:**
   - Go to Step 3 (Documents)
   - Select a Form 16 file
   - Watch status change: "💾 Saving document..." → "🔍 AI reading document..."
   - Verify console shows `[UPLOAD] Successfully saved documents:`

4. **Check Google Sheets:**
   - Submit the form
   - Open your Google Sheet
   - Look for URL in `doc_form16_urls` column

### Deployment Testing (Render)

1. **Deploy to Render:**
   ```bash
   git push  # Triggers Render deployment
   ```

2. **Verify disk mounted:**
   - Render dashboard → Service → Logs
   - Look for disk mount confirmation

3. **Test upload via browser:**
   - Go to `https://your-app.onrender.com`
   - Upload a document
   - Check logs for `[UPLOAD] Successfully saved documents:`

4. **Verify file persistence:**
   - Kill/restart the service
   - Upload another document
   - Both files should still exist (different document)

5. **Test file serving:**
   - Open the URL from Google Sheets in browser
   - File should download/display

## Key Features

### ✅ Immediate Persistence
- Files saved to disk immediately on upload
- Users can close browser, cancel extraction, refresh page
- Documents are still safely stored

### ✅ Google Sheets Backup
- Every uploaded file URL stored in Google Sheets
- Separate columns per document type
- Easy for auditors to access files
- Multiple files of same type supported (comma-separated)

### ✅ Non-Blocking Upload
- If upload fails, extraction still proceeds
- User doesn't get stuck if document upload fails
- Documents are backed up, not required for extraction

### ✅ Deployment-Safe
- Uses Render persistent disk (survives deployments)
- Can scale to AWS S3 later if needed
- No dependencies on external services

### ✅ Clean File Management
- Unique filenames (UUID prefix) prevent collisions
- Organized by submission_id
- Follows existing naming conventions

## Troubleshooting

### Issue: Files not saving after deployment

**Check:**
1. Render disk is created and mounted
   ```bash
   df -h | grep /mnt/uploads
   ```
2. Environment variable `RENDER_MOUNT_PATH=/mnt/uploads` is set
3. Check logs for storage errors: `[STORAGE] [ERROR]`

### Issue: URLs not appearing in Google Sheets

**Check:**
1. Google Sheets credentials are configured
2. Backend logs show `[UPLOAD_DOCUMENT] Updated sheet column`
3. Check for "Sheets not configured" warnings in logs

### Issue: Files uploaded locally but not on Render

**Cause:** Local fallback path is `backend/uploads/`, but Render needs `/mnt/uploads/`

**Fix:**
1. Ensure `RENDER_MOUNT_PATH=/mnt/uploads` environment variable is set
2. Restart Render service
3. Re-upload document

### Issue: File URL returns 404

**Check:**
1. URL format should be `/uploads/{submission_id}/{filename}`
2. Filename should exactly match saved filename (UUID prefix + original name)
3. Check if file exists: `ls -la /mnt/uploads/{submission_id}/`

## Future Enhancements

1. **S3 Integration:** Replace Render disk with AWS S3 for unlimited storage
2. **Cloud CDN:** Use CloudFront/CDN for faster file serving
3. **Virus Scanning:** Add ClamAV scanning on document upload
4. **Compression:** Automatically compress PDFs before storage
5. **Expiry:** Auto-delete uploaded files after 6 months (if needed)
6. **Encryption:** Encrypt files at rest
7. **Backup:** Daily backup of /mnt/uploads to S3

## File Changes Summary

### Modified Files
1. **backend/requirements.txt**
   - Added: `google-cloud-storage>=2.10.0` (for future GCS support)

2. **backend/config.py**
   - Added: `GCS_BUCKET_NAME`, `GCS_PROJECT_ID` (future use)

3. **backend/storage_service.py**
   - Complete rewrite to support Render persistent disk
   - Added: `get_doc_type_column()` - maps doc types to sheet columns
   - Added: `append_urls_to_sheet()` - appends URLs to existing comma-separated list
   - Now uses `/mnt/uploads` by default (Render), falls back to local

4. **backend/app.py**
   - New endpoint: `POST /api/upload-document`
   - Handles immediate document upload and Google Sheets integration
   - Non-blocking error handling

5. **frontend/app.js**
   - New function: `uploadDocumentImmediately()` - saves files before extraction
   - Updated: `extractSectionBg()` - calls upload first
   - Updated: `extractSection()` - calls upload first

### New Endpoints
- `POST /api/upload-document` - Immediate document upload

### New Google Sheets Columns
Already existed, now actively used:
- `doc_form16_urls`
- `doc_payslip_urls`
- `doc_homeloan_urls`
- `doc_school_urls`
- `doc_nps_urls`
- `doc_insurance_urls`
- `doc_donation_urls`

## Testing Checklist

- [ ] Render persistent disk created and mounted at `/mnt/uploads`
- [ ] `RENDER_MOUNT_PATH=/mnt/uploads` environment variable set
- [ ] Backend requirements updated: `pip install -r requirements.txt`
- [ ] Backend deployment successful
- [ ] Frontend deployment successful
- [ ] Document upload works locally
- [ ] Document upload works on Render
- [ ] URLs appear in Google Sheets
- [ ] Files persist after service restart
- [ ] Extraction still works if upload fails
- [ ] Multiple files of same type stored as comma-separated URLs

## Support

For issues:
1. Check logs: `[STORAGE]` and `[UPLOAD_DOCUMENT]` prefixes
2. Verify Render disk is mounted: `df -h`
3. Check file permissions: `ls -la /mnt/uploads/`
4. Ensure Google Sheets credentials are valid
