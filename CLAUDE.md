# FairTax Backend — Development Guide

## Project Overview

**FairTax** is an AI-powered Indian fintech tax filing platform designed to simplify income tax return (ITR) filing, maximize refunds, and drive growth through referral-based rewards.

**Your Focus:** Backend optimization, specifically **tax calculation accuracy** and end-to-end data pipeline integrity. **Frontend is off-limits** — focus only on backend services.

### Core Mission
- Simplify Indian tax filing for salaried employees, freelancers, senior citizens, and business owners
- Automate document extraction using Claude AI + OCR
- Calculate accurate tax with old/new regime comparison
- Integrate with Google Sheets for data persistence
- Drive viral growth through referral rewards + cashback system

---

## Backend Architecture

### High-Level Data Flow

```
User Upload
    ↓
File Validation
    ↓
OCR + AI Extraction (ai_service.py + vision_extractor.py)
    ↓
Normalization & Validation (validation_service.py, normalization_service.py)
    ↓
Quality Check (quality_checker.py)
    ↓
Tax Calculation (tax_engine.py)
    ↓
Old vs New Regime Comparison
    ↓
Refund Optimization
    ↓
Google Sheets Save (sheets_service.py)
    ↓
WhatsApp + Email Notification
    ↓
User Dashboard
```

### Technology Stack

- **Framework:** Flask (Python)
- **Main AI Extraction:** OpenAI API (gpt-4o-mini by default)
- **OCR:** OpenRouter API → Baidu QianFan OCR (free tier) with Google Cloud Vision fallback
- **Database:** Google Sheets (primary), local uploads folder
- **Integrations:** Google Cloud Vision, WhatsApp Business API, OpenAI API, OpenRouter API
- **Deployment:** Vercel (serverless Python support)

---

## Critical Backend Services

### 1. **app.py** (1523 lines) — Main Flask Application
**Purpose:** Request routing, API endpoints, session management

**Key Endpoints:**
- `POST /api/save-phase` — Save filing data progressively
- `POST /api/upload` — File upload handler
- `POST /api/calculate` — Trigger tax calculation
- `POST /api/whatsapp/webhook` — WhatsApp incoming messages
- `GET /api/health` — Health check
- ITR blueprint routes (ITR extraction, verification)

**Important Details:**
- Runs on port 5000 locally
- CORS enabled for frontend
- Scheduler starts automatically (try/catch, non-fatal if fails)
- Sheets integration optional in local dev (graceful fallback with mock submission_id)

**Your Focus Areas:**
- Validate `filing_category` (must be 'regular' or 'free') for NEW submissions
- Phone normalization (stores last 10 digits)
- Check for missing required fields before saving

---

### 2. **tax_engine.py** (411 lines) — Tax Calculation Logic ⭐ PRIORITY
**Purpose:** Compute income tax, compare regimes, suggest optimizations

**Key Functions:**
- `slab_tax_old(taxable)` — Old regime tax calculation
- `slab_tax_new(taxable)` — New regime tax calculation
- `compute_tax_before_cess(taxable, regime)` — Core slab + rebate logic
- Tax slab definitions come from `tax_config.py`

**Tax Configuration (from tax_config.py):**
- **Old Regime:** Multiple slabs with different rates
- **New Regime:** Simplified slabs (typically lower at higher incomes)
- **Cess Rate:** Applied after tax calculation (typically 4%)
- **Rebate 87A:** For individuals with income below threshold
- **Deductions:** Section 80C, 80D, 80E, etc.

**Critical Note:** This is where accuracy matters most. Any error here cascades to final filing.

**Testing:** Manual testing with real Form 16 + investment docs

---

### 3. **ai_service.py** (1225 lines) — OpenAI AI Extraction ⭐ CRITICAL
**Purpose:** Extract financial data from tax documents using OpenAI API (gpt-4o-mini)

**Main Workflow:**
1. `extract_from_file()` — File → base64 → OpenAI gpt-4o-mini
2. OpenAI returns structured JSON with extracted fields
3. Confidence scoring for each field
4. Returns normalized data dict

**Supported Extractions:**
- Form 16 fields (salary, HRA, PF, employer contribution, tax paid)
- Investment declarations (80C, 80D, 80E, 80G, etc.)
- PAN, Aadhaar details
- Income sources (salary, freelance, business)
- Deductions and exemptions
- Payslip extraction (monthly vs YTD detection)

**Important:**
- Uses OpenAI gpt-4o-mini (vision-capable, cost-effective)
- Prompt-engineered for Indian tax documents
- Confidence scores guide UI validation alerts
- Falls back to OCR if extraction fails or confidence is low
- Payslip-specific extraction with monthly/YTD detection logic

**Your Focus:**
- Verify extraction accuracy on edge cases
- Check confidence scoring logic
- Validate field mapping to tax_engine inputs
- Review prompt engineering in `EXTRACTION_PROMPT` and `PAYSLIP_TEXT_EXTRACTION_PROMPT`

---

### 4. **sheets_service.py** (541 lines) — Google Sheets Integration
**Purpose:** Store extracted and calculated data in Google Sheets for persistence + reporting

**Key Functions:**
- `save_submission()` — Write user filing data to sheet
- `gen_referral_code()` — Generate unique referral codes
- `validate_referral()` — Check if referral is valid + new
- `get_or_create_user_row()` — Ensure idempotent saves

**Sheet Structure:**
- Column headers: name, pan, email, phone, salary, hra, pf, investments, tax_old, tax_new, refund, referral_code, filing_status, etc.
- One row per submission
- Updates are idempotent (duplicate saves don't create duplicate rows)

**Important:**
- Requires `GOOGLE_SHEET_ID` + `SERVICE_ACCOUNT_JSON` in config
- In local dev without credentials: gracefully fails, returns mock submission_id
- Prevents duplicate PAN submissions
- Tracks referral validation state

**Your Focus:**
- Verify data format before saving (no corrupted numbers)
- Check for idempotency on repeated saves
- Validate referral deduplication logic

---

### 5. **document_processor.py** — Document Pipeline Orchestrator
**Purpose:** Orchestrate the full extraction → validation → normalization flow

**Workflow:**
1. File validation (type, size, corruption check)
2. Route to OCR or AI extraction
3. Normalize outputs
4. Apply validation rules
5. Return cleaned structured data

**Critical Responsibility:**
- Ensures data consistency across extraction methods
- Detects extraction failures early
- Aggregates multi-page document extractions

---

### 6. **quality_checker.py** — Data Quality Validation
**Purpose:** Verify extracted data meets business rules before tax calculation

**Validation Checks:**
- PAN format (10-char alphanumeric)
- Aadhaar format (12-digit)
- Salary reasonableness (not negative, not absurdly high)
- Investment totals don't exceed limits
- Confidence scores above threshold
- Required fields present

**Your Focus:**
- Understand validation thresholds
- Check for false positives/negatives
- Adjust rules based on real filing patterns

---

### 7. **validation_service.py** — Field-Level Validation
**Purpose:** Validate individual extracted fields (format, range, consistency)

**Validates:**
- Phone numbers (10 digits for India)
- Email format
- Numeric field ranges
- Date formats
- Deduction limits per section

---

### 8. **normalization_service.py** — Data Standardization
**Purpose:** Clean and standardize extracted values for consistency

**Examples:**
- Convert "₹10,00,000" → `1000000.0`
- Trim whitespace, fix case
- Convert date formats to ISO 8601
- Standardize deduction category names
- Handle missing/null values gracefully

---

### 9. **itr_api.py** (310 lines) — ITR Submission API
**Purpose:** Handle ITR extraction and verification flows specific to Indian tax forms

**Key Functions:**
- ITR form type detection (ITR-1, ITR-2, ITR-3, etc.)
- Compliance checks for form selection
- Revenue vs salary income handling
- Loss carryforward logic

**Blueprint Routes:**
- `/itr/extract` — Extract from ITR form
- `/itr/validate` — Validate extraction
- `/itr/submit` — Submit for filing

---

### 10. **whatsapp_service.py** (210 lines) — WhatsApp Integration
**Purpose:** Send notifications and receive messages via WhatsApp Business API

**Key Functions:**
- `send_text()` — Send message to user
- `send_notification()` — Formatted notifications
- `normalize_phone()` — Convert to WhatsApp format

**Used For:**
- Filing confirmation messages
- Refund status updates
- Referral reward notifications
- Support responses

---

### 11. **ocr_service.py** (103 lines) — OCR Text Extraction
**Purpose:** Extract text from images and PDFs using multiple OCR backends

**Dual OCR Strategy:**
1. **Primary:** OpenRouter API → Baidu QianFan OCR (if `OPENROUTER_API_KEY` configured)
   - Cost-effective, free tier available
   - Good for payslips and structured documents
   - Fast extraction
   
2. **Fallback:** Google Cloud Vision API
   - Reliable, robust
   - Used if OpenRouter fails or not configured
   - Higher cost but more reliable

**Key Functions:**
- `extract_text_from_image()` — Extract text from JPG/PNG
- `extract_text_from_pdf()` — Extract text from PDF pages

**Important:**
- OCR is a fallback when AI extraction fails
- OCR output is passed to ai_service for structure/field mapping
- Not used for primary extraction in normal flow
- PDF processing done page-by-page

**Your Focus:**
- Monitor OCR fallback usage (indicates AI extraction failures)
- Check accuracy of OCR output before field mapping
- Verify config switches work correctly

---

### 12. **scheduler_service.py** (187 lines) — Background Job Processing
**Purpose:** Run scheduled tasks (refund checks, notifications, cleanup)

**Typical Jobs:**
- Daily refund status polling
- Weekly winner selections
- Wallet updates
- Cleanup of old uploads

**Important:**
- Fails gracefully if not available (try/catch in app.py)
- Check logs if jobs aren't running

---

### 13. **pdf_service.py** (306 lines) — PDF Generation
**Purpose:** Generate quotes, receipts, and detailed tax reports as PDFs

**Key Functions:**
- `generate_quote_pdf()` — Pre-filing estimate
- `generate_filing_receipt()` — Post-submission receipt
- `generate_tax_report()` — Detailed calculation breakdown

---

### 14. **storage_service.py** — File Storage Management
**Purpose:** Handle secure storage of uploaded documents and extracted data

**Stores:**
- Uploaded PDF/image files
- Extracted JSON blobs
- Calculation reports

---

## Local Setup & Running

### Prerequisites
- Python 3.8+
- pip
- `.env` file with API keys (see config.py for required vars)
- Google Cloud service account JSON (optional for local dev)

### Environment Variables (in `.env`)

```bash
# OpenAI API (required for main extraction)
OPENAI_API_KEY=sk-proj-xxx
OPENAI_MODEL=gpt-4o-mini  # Default, can change to gpt-4-turbo, gpt-4o, etc.
OPENAI_URL=https://api.openai.com/v1/chat/completions

# OpenRouter API (optional, for OCR)
OPENROUTER_API_KEY=sk-or-xxx
OPENROUTER_URL=https://openrouter.ai/api/v1/chat/completions
OCR_MODEL=baidu/qianfan-ocr-fast:free  # Baidu QianFan OCR, free tier

# Google Cloud (for Vision API fallback OCR)
GOOGLE_SERVICE_ACCOUNT_JSON=service_account.json

# Google Sheets (optional for local dev)
GOOGLE_SHEET_ID=xxxxx

# WhatsApp (optional)
WHATSAPP_TOKEN=xxx
WHATSAPP_PHONE_ID=xxx

# Flask
FLASK_SECRET=dev-secret-key
PUBLIC_BASE_URL=http://localhost:5000

# File uploads
UPLOAD_DIR=uploads

# Feature flags
USE_AI=1
EXTRACTION_USE_AI=1  # Enable OpenAI extraction
OCR_USE_AI=1         # Enable OpenRouter OCR
```

### Running Locally

```bash
# Navigate to backend directory
cd backend

# Install dependencies (no requirements.txt, so check imports)
pip install flask flask-cors python-dotenv anthropic requests

# Run Flask dev server
python app.py

# Server starts on http://localhost:5000
# Frontend accesses at http://localhost:8000 (separate HTTP server)
```

### Database Access
- **Local Dev:** Google Sheets (if configured) or mock mode
- **No traditional database** — uses Google Sheets as primary storage
- Uploads stored in `backend/uploads/` folder

---

## AI & Extraction Flow (Detailed)

### Extraction Pipeline

```
User Uploads Document (PDF/JPG/PNG)
    ↓
document_processor.py routes file
    ↓
AI Extraction Path (Primary)
    ↓
ai_service._call_openai() → OpenAI gpt-4o-mini
    ↓
Structured JSON output (form fields)
    ↓
confidence_score validation (via quality_checker.py)
    ↓
Confidence < threshold? → Falls back to OCR
    ↓
OCR Fallback Path
    ↓
ocr_service.extract_text_from_image/pdf()
    ↓
Try OpenRouter (Baidu QianFan) → Falls back to Google Vision
    ↓
Raw text extraction
    ↓
ai_service._call_openai() again with text
    ↓
Structured JSON output
    ↓
normalization_service.py cleans data
    ↓
quality_checker.py validates business rules
    ↓
validation_service.py field-level checks
    ↓
Data ready for tax_engine.py
```

### Key Config Options

- `EXTRACTION_USE_AI=1` → Use OpenAI for extraction (if 0, extract from text/OCR only)
- `OCR_USE_AI=1` → Use OpenRouter OCR (if 0, fall back to Google Vision only)
- `OPENAI_MODEL` → Can swap to different OpenAI models (cheaper/faster/smarter tradeoff)
- `OCR_MODEL` → Can use different Baidu models or other providers via OpenRouter

---

## Common Workflows

### 1. Testing Tax Calculation Accuracy

**Goal:** Verify tax_engine.py computes correct amounts

**Steps:**
1. Prepare test Form 16 (or use example in `example_extraction.py`)
2. Extract data manually (or use `ai_service.extract_from_file()`)
3. Call `tax_engine.slab_tax_old(taxable)` and `tax_engine.slab_tax_new(taxable)`
4. Compare results against:
   - Expected ITR calculation
   - Real-world tax software (ClearTax, ITR assistant, etc.)
5. Document discrepancies

**Key Test Cases:**
- Income just below/above tax slab thresholds
- High investment deductions (80C, 80D)
- HRA calculation with rent receipt
- PF contribution effects on taxable income

---

### 2. Debugging Extraction Accuracy

**Goal:** Improve AI/OCR extraction reliability

**Steps:**
1. Upload problematic document via API
2. Check `ai_service.extract_from_file()` output JSON
3. Review confidence scores
4. Compare against `quality_checker.py` validation results
5. If fails: Adjust prompt in ai_service or use OCR fallback
6. Document patterns (blurry docs, old form versions, etc.)

**Tools:**
- Use `/code-review` to check extraction logic for bugs
- Use `/verify` to test API end-to-end
- Check console logs for extraction errors

---

### 3. Validating Data Pipeline Integrity

**Goal:** Ensure data flows correctly from upload → sheets save

**Flow to Test:**
1. Upload document via API
2. Check extraction output
3. Verify normalization (currency formats, field names)
4. Validate quality checks pass
5. Confirm tax calculation runs
6. Check Google Sheets for saved row

**Use `/verify` after any service changes** to test full flow

---

### 4. Testing Referral Logic

**Goal:** Verify referral deduplication and milestone tracking

**Key Cases:**
- Referral with duplicate PAN → Should reject
- Referral from same device/IP → Validate fraud detection
- Milestone thresholds (1, 3, 5, 10 referrals) → Check cashback updates

---

### 5. Monitoring Scheduler Jobs

**Goal:** Ensure background tasks run correctly

**Check:**
- Scheduler starts without errors (check console on app startup)
- Jobs log output to see if they're executing
- Wallet updates happen on schedule
- Weekly winners are selected correctly

---

## Common Gotchas & Known Issues

### 1. **Tax Calculation Precision**
- Use float for currency, but be aware of rounding errors
- Always round to 2 decimal places for final output
- Test with edge case amounts (like 10,00,000 = 1 million rupees)

### 2. **Google Sheets Integration Failures**
- Local dev without `service_account.json` fails gracefully (returns mock submission_id)
- In production, Sheets unavailability = filing fails
- Check `_sheets_configured` logic in app.py

### 3. **Extraction Confidence Scores**
- Very low confidence (<0.5) should trigger manual review flag
- Don't blindly trust AI extraction — always validate against business rules

### 4. **Referral Deduplication**
- PAN-based dedup is strict (duplicate PAN = rejected)
- Phone-based dedup is flexible (allows same number for family)
- Device-based dedup prevents same-device abuse

### 5. **File Upload Size Limits**
- No explicit limit in code — check Flask config
- Large PDFs may timeout during extraction
- Compress/optimize documents before testing

### 6. **WhatsApp Integration**
- Requires valid API token — fails gracefully if missing
- Notifications are non-critical (don't block filing)

### 7. **Scheduler Non-Critical**
- If scheduler fails to start, app continues running
- Background jobs won't run, but sync operations still work
- Check scheduler_service logs

### 8. **Old vs New Regime Logic**
- Always calculate BOTH regimes
- Return both amounts to frontend for user comparison
- Some users must use old regime (business income) — validate rule

---

## Validation Rules & Business Logic

### Filing Categories
- **Regular:** Full tax payment required, requires name/phone/email
- **Free:** User has completed referral milestones (5+ referrals)

### Tax Deductions Limits (FY 2025-26)
- **80C:** ₹1.5 lakh max (includes ELSS, PPF, life insurance, home loan principal)
- **80D:** ₹25k (self), ₹50k (family) for health insurance
- **80E:** Student loan interest (no limit)
- **80G:** Charitable donations (50-100% of income limits)

### Referral Milestones
- **1 referral:** ₹50 cashback
- **3 referrals:** ₹150 total
- **5 referrals:** Free filing eligibility + ₹250 cashback
- **10 referrals:** Premium reward (amount TBD)

### Duplicate Prevention
- **PAN:** Strict duplicate rejection
- **Phone:** Flexible (allow family members)
- **Email:** Flexible
- **Device/IP:** Track for fraud detection

---

## Testing Strategy

### Manual Testing (Your Current Approach)

**Before pushing any backend change, test:**

1. **Code correctness:** `/code-review`
2. **API functionality:** `/verify` (runs the app and tests endpoints)
3. **Security issues:** `/security-review` (before production)

### Example: Testing Tax Calculation Change

```
1. Modify tax_engine.py (e.g., change slab rates)
2. Run: /code-review --level high
3. Run: /verify (uploads test doc, calculates tax, checks result)
4. Verify in Google Sheets that result was saved
5. Compare against manual tax software
6. Commit only if results match expected
```

### Example: Testing Extraction Change

```
1. Modify ai_service.py prompt or field mapping
2. Run: /code-review
3. Run: /verify (uploads test Form 16, checks extracted fields)
4. Review confidence scores and extracted amounts
5. Check validation_service catches any bad data
6. Verify Google Sheets row saved correctly
```

---

## Integration Points

### External APIs Used
1. **OpenAI API** (gpt-4o-mini) — Extract financial data from PDFs/images (primary)
2. **OpenRouter API** → Baidu QianFan OCR — OCR text extraction (if configured)
3. **Google Cloud Vision API** — OCR fallback when OpenRouter unavailable
4. **Google Sheets API** — Store and read user filing data (persistence)
5. **WhatsApp Business API** — Send notifications and receive messages

### Frontend → Backend Communication
- Frontend sends raw form data to `/api/save-phase`
- Backend returns `submission_id` + `referral_code`
- Frontend polls `/api/status/<submission_id>` for updates

### Database → Backend
- Google Sheets is the primary "database"
- Reads on submission load (check for duplicates)
- Writes on save-phase + final filing

---

## Key Files You Should Know

| File | Lines | Purpose | Your Focus? |
|------|-------|---------|------------|
| app.py | 1523 | Main Flask app | Routes, phase saves |
| ai_service.py | 1225 | OpenAI extraction | ⭐ Accuracy, prompt tuning |
| tax_engine.py | 411 | Tax calculation | ⭐ PRIMARY |
| sheets_service.py | 541 | Google Sheets save | Data integrity |
| ocr_service.py | 103 | OCR fallback | Text extraction fallback |
| document_processor.py | ? | Orchestrate pipeline | Flow logic |
| quality_checker.py | ? | Validation rules | Business rules |
| itr_api.py | 310 | ITR submission | Compliance |
| config.py | 29 | Environment config | API keys, setup |
| tax_config.py | 66 | Tax slab definitions | Rates, limits |

---

## Debugging Tips

### Check Logs
- Console output on app startup
- Flask logs on each request
- Scheduler logs for background jobs

### Test Single Functions
```python
# In Python shell, test tax calc directly
from tax_engine import slab_tax_old, slab_tax_new
taxable = 500000
print(f"Old: {slab_tax_old(taxable)}")
print(f"New: {slab_tax_new(taxable)}")
```

### Use Skills
- **`/code-review`** → Find bugs before testing
- **`/verify`** → Run full flow and see results
- **`/security-review`** → Check for data leaks before production

### Monitor API Costs
- **OpenAI:** Check api.openai.com/account/usage for extraction costs (gpt-4o-mini is cheap)
- **OpenRouter:** Free tier for Baidu QianFan (check openrouter.ai pricing)
- **Google Cloud Vision:** $0.15 per 1000 requests (used as OCR fallback)

### Common Issues

**Problem:** Extraction returns empty or all zeros
- Check `OPENAI_API_KEY` is valid and has credits
- Check `EXTRACTION_USE_AI=1` in config
- Look for OpenAI rate limiting or API errors in logs

**Problem:** OCR not being used
- Check `OPENROUTER_API_KEY` is configured for OpenRouter
- Check `OCR_USE_AI=1` in config
- Verify confidence scores trigger fallback (< threshold)

**Problem:** Field extraction is inaccurate
- Review extraction prompts in ai_service.py (`EXTRACTION_PROMPT`, `PAYSLIP_TEXT_EXTRACTION_PROMPT`)
- Test with different OpenAI models (try gpt-4-turbo for better accuracy)
- Check if document quality is poor (blurry, old format)

---

## Next Steps

1. **Read tax_config.py** — Understand slab definitions, deduction limits
2. **Test tax_engine.py** — Verify calculations with real tax scenarios
3. **Review ai_service.py** — Understand extraction prompts and validation
4. **Run `/verify`** — Test end-to-end flow locally
5. **Document findings** — Record any extraction/calculation discrepancies

---

## Contact & Support

- **Questions on tax logic?** Check tax_config.py + detailed_calc_report.py
- **Extraction issues?** Review ai_service.py prompt engineering
- **Sheets sync problems?** Check sheets_service.py + config credentials
- **General debugging?** Use `/code-review` and `/verify` skills

---

**Last Updated:** May 2026  
**Status:** Backend focused, tax calculation optimization in progress  
**Frontend:** Off-limits — do not modify
