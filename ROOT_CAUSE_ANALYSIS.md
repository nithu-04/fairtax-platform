# Root Cause Analysis - Monthly vs Annual Values Bug

## Database Evidence

```
Current (WRONG):
gross_salary = 233,937 (MONTHLY)
basic_salary = 99,133 (MONTHLY)  
hra_received = 49,566 (MONTHLY)

Expected (CORRECT):
gross_salary = 3,141,557 (ANNUAL)
basic_salary = 1,168,656 (ANNUAL)
hra_received = 584,330 (ANNUAL)
```

---

## Data Flow Trace

### STEP 1: Document Extraction (/api/extract)

**Code Path:**
1. `app.py:/api/extract` (line ~765) calls `document_processor.process_documents()`
2. `document_processor.py:process_documents()` (line 96)
   - Calls vision extraction
   - Calls `normalization_service.normalize_extractions()` (line 194)
   - Returns normalized data at line 246: `"data": normalized_data`
3. Normalized data passed to `itr_extractor._build_response()` (line 85 in itr_extractor.py)
4. Returns response with `data: response_data` (line 65)

**My Annualization Code:**
- Location: `normalization_service.py:61` - `_annualize_payslip_field()` function
- Should annualize when `doc_type == "payslip"` (multiply by 12)
- Applied at lines 215, 265, 293

**Expected Result:**
- `/api/extract` should return:
  ```json
  {
    "gross_salary": 3141557,  // annualized
    "basic_salary": 1168656,  // annualized
    "hra_received": 584330     // annualized
  }
  ```

---

### STEP 2: Data Storage (sheets_service.update_row)

**Code Path:**
1. `app.py:/api/extract` line 955: `sheets_service.update_row(row, merged)`
2. `sheets_service.py:update_row()` stores values to Google Sheets
3. Values stored with HEADERS column mapping

**Expected:**
- Sheet should have annual values (annualized from normalization)

**Actual (PROBLEM):**
- Sheet shows monthly values: `gross_salary = 233,937`

---

### STEP 3: Form Submission (/api/submit)

**Code Path:**
```python
# Line 1070: /api/submit receives form submission data
data = request.get_json(force=True)

# Line 1130-1131: Gets existing record from sheet
existing_rec = sheets_service.check_approval(submission_id)

# Line 1132-1135: CRITICAL - Form data OVERRIDES sheet data!
if existing_rec:
    merged_data = {**existing_rec, **data}
else:
    merged_data = data
```

**THE PROBLEM:**
```python
merged_data = {**existing_rec, **data}
```

This line means:
- Base: `existing_rec` (data from sheet)
- Override: `data` (form submission)
- **Form values win!**

**Example:**
```
existing_rec has: gross_salary = 3,141,557 (from extract)
data has: gross_salary = 233,937 (from form)
Result: merged_data["gross_salary"] = 233,937  ❌
```

---

## Root Cause - THE BUG

### Hypothesis A: Extraction Not Annualizing ❌
- **Status:** My annualization code exists at normalization_service.py:61
- **But:** Need to verify it's actually RUNNING and WORKING

### Hypothesis B: Frontend Overrides with Monthly Values ✅ LIKELY
- **Status:** When form is submitted, form values override sheet values
- **Issue:** If frontend displays/sends monthly values, they override annualized values in sheet

### Hypothesis C: validate_form16_payslip_consistency() Using Raw Data ⚠️
- **Location:** `ai_service.py:1000` line 1118-1127
- **Issue:** Extracts from `form16_doc` (raw extraction from extractions list)
- **But:** Uses these raw values to override merged_data
- **Risk:** If raw extraction has monthly values, override would use them

---

## Code Paths That Could Cause Bug

### Path A: Annualization Not Happening
```
Form16 PDF extraction
  ↓
Vision API returns raw values
  ↓
document_processor.process_documents()
  ↓
normalization_service.normalize_extractions()
  ↓ _annualize_payslip_field() should multiply by 12
  ↓
Returns normalized_data (should be annualized)
  ↓
✅ or ❌ Is this actually returning annualized?
```

**Need to verify:** Does normalized_data actually contain annualized values?

### Path B: Form Override
```
/api/extract saves annual values to sheet
  ↓
Frontend displays values to user (displays form)
  ↓
User submits form (sends annual OR MONTHLY values?)
  ↓
/api/submit: merged_data = {**existing_rec, **data}
  ↓
Form values (data) override sheet values (existing_rec)
  ↓
Monthly form values replace annual sheet values
  ↓
Database saves: monthly values ❌
```

**Need to verify:** What values does frontend send in form submission?

### Path C: validate_form16_payslip_consistency() Override
```
ai_service.validate_form16_payslip_consistency()
  ↓
Finds form16_doc in extractions list
  ↓
form16_doc contains raw extraction (not normalized?)
  ↓
Line 1123: merged_data[field_key] = form16_val (from raw)
  ↓
If form16_val is monthly, it overrides normalized value
  ↓
Monthly value replaces annual value ❌
```

**Need to verify:** Does form16_doc contain normalized or raw data?

---

## Three Questions That Will Reveal The Bug

### Question 1: Does /api/extract return annualized values?
**How to test:**
- Add debug logging in itr_extractor._build_response()
- Log: `"Extraction returning gross_salary = " + response_data.get("gross_salary")`
- Expected: Should be ~3,141,557 (annual)
- If shows: 233,937 (monthly) → Annualization not working

### Question 2: What does frontend form submit?
**How to test:**
- Add logging in /api/submit at line 1083
- Log: `print(f"[SUBMIT] Form data received: gross_salary={data.get('gross_salary')}")`
- Expected: Could be either annual or monthly
- If monthly → Frontend is sending monthly values

### Question 3: Does validate_form16_payslip_consistency override with raw values?
**How to test:**
- Check if form16_doc values are normalized or raw
- Log in ai_service.validate_form16_payslip_consistency():
  ```python
  print(f"[CONFLICT] form16_doc gross_salary = {form16_doc.get('gross_salary')}")
  print(f"[CONFLICT] merged_data gross_salary BEFORE override = {merged_data.get('gross_salary')}")
  print(f"[CONFLICT] merged_data gross_salary AFTER override = {merged_data.get('gross_salary')}")
  ```

---

## Likely Root Cause (Ordered by Probability)

### 🔴 MOST LIKELY: Form Submission Override
**Probability: 80%**

The sequence is:
1. ✅ Extract returns annualized values (my code works)
2. ✅ Sheet saves annualized values
3. ❌ Frontend displays form with values populated from extraction
4. ❌ But form might display MONTHLY values (if extraction display logic is wrong)
5. ❌ OR user manually enters monthly values
6. ❌ Form submission sends monthly values
7. ❌ /api/submit overwrites annual sheet values with monthly form values
8. ❌ Database ends up with monthly values

**Why:** The merge at line 1132 clearly overrides: `merged_data = {**existing_rec, **data}`

---

### 🟡 POSSIBLE: Annualization Not Running
**Probability: 15%**

The annualization code exists but:
1. ❌ May not be executing for payslips
2. ❌ Or executing but bug in the logic
3. ❌ Or returns but gets overwritten later

**Why:** Would need normalization code verification

---

### 🟢 UNLIKELY: validate_form16_payslip_consistency Override
**Probability: 5%**

Only if:
1. Both Form16 AND Payslip uploaded
2. form16_doc from extractions contains raw (non-normalized) values
3. And these raw values are monthly

**Why:** The code at line 1123 could override, but only if both docs present

---

## Files Involved in Bug

### Extraction Pipeline (Data should be annualized here)
- `backend/services/document_processor.py:96` - Main extraction orchestrator
- `backend/services/normalization_service.py:61` - Annualization logic
- `backend/itr_extractor.py:72` - Wraps extraction
- `backend/app.py:765` - /api/extract endpoint

### Storage (Data written to sheet)
- `backend/sheets_service.py:772` - update_row() saves data
- `backend/sheets_service.py:HEADERS` - Column definitions

### Form Submission (Data overrides)
- `backend/app.py:1064` - /api/submit endpoint  
- **Line 1132-1135:** THE OVERRIDE BUG
  ```python
  merged_data = {**existing_rec, **data}  # Form data overrides sheet
  ```

### Post-Extract Processing
- `backend/ai_service.py:1000` - validate_form16_payslip_consistency()
- **Lines 1118-1127:** Potential override with raw values

---

## What I Plan To Do (Analysis Phase Only)

### Phase 1: Verify Extraction Output
**Files to add logging:**
1. `itr_extractor.py:_build_response()` - Log what's returned
2. `app.py:/api/extract` - Log what merged contains before saving

**Expected log:**
```
[EXTRACT] Returning gross_salary = 3,141,557 (should be annual)
```

### Phase 2: Verify Form Submission
**Files to add logging:**
1. `app.py:/api/submit line 1083` - Log form data received
2. `app.py:/api/submit line 1136` - Log merged_data after merge

**Expected log:**
```
[SUBMIT] Form data gross_salary = 233,937 or 3,141,557?
[SUBMIT] After merge: gross_salary = 233,937 (if form wins)
```

### Phase 3: Verify Override Logic
**Files to add logging:**
1. `ai_service.py:validate_form16_payslip_consistency():1120` - Log form16_doc values
2. `ai_service.py:validate_form16_payslip_consistency():1123` - Log override
3. `app.py:/api/extract before update_row()` - Log merged before save

**Expected log:**
```
[CONFLICT] form16_doc gross_salary = 3,141,557 or 233,937?
[CONFLICT] Overriding to = X
```

---

## Affected Files (No Changes Yet - Analysis Only)

When we implement the fix, these files will be affected:

1. **backend/app.py** - /api/submit merge logic (line 1132-1135)
   - Fix: Use priority logic instead of dict merge override

2. **backend/services/normalization_service.py** - Verify annualization works
   - Verify: _annualize_payslip_field() is executing
   - Check: Correct values returned to document_processor

3. **backend/ai_service.py** - validate_form16_payslip_consistency()
   - Verify: Not using raw values if they're monthly

4. **frontend/app.js** - What values are sent in form?
   - Check: Are monthly values being sent?
   - Verify: Form uses extracted annual values

---

## Next Steps

**DO NOT FIX YET** - First need to:

1. Add comprehensive logging at all 3 phases
2. Run extraction with test documents
3. Review logs to identify which step is causing monthly values
4. Then propose specific fix

The fix will depend on where the bug actually is:
- If annualization not working → fix normalization logic
- If form override → fix merge logic in /api/submit
- If validate_form16_payslip_consistency → fix that function

**Current Best Guess:** Form override at `/api/submit line 1132-1135`

---

## To User: What I Need From You

Run extraction with test documents (Form16 + Payslip) and provide:
1. What value shows in Google Sheets for `gross_salary`?
2. What values does the browser form show after extraction?
3. What values are in the API request when form is submitted?

This will pinpoint the exact location of the bug.
