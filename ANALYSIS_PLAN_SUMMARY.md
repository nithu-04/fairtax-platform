# Analysis Plan Summary - Monthly vs Annual Bug

## Executive Summary

The system is still storing MONTHLY salary values in the database instead of ANNUAL values, despite my attempted fixes. Through code tracing, I've identified **THREE POSSIBLE ROOT CAUSES** and a clear strategy to identify which one is the actual problem.

---

## The Three Probable Locations of the Bug

### 🔴 BUG #1: Form Submission Override (80% probability)

**Location:** `backend/app.py` line 1132-1135

```python
# In /api/submit endpoint
existing_rec = sheets_service.check_approval(submission_id)
if existing_rec:
    merged_data = {**existing_rec, **data}  # ❌ Form data overrides sheet data!
```

**How it happens:**
1. `/api/extract` returns & saves annualized values to sheet ✅
2. Frontend displays form populated from extracted values
3. User submits form with values (might be monthly values from form)
4. `/api/submit` merges: `{**sheet_data, **form_data}`
5. Form values **override** sheet values
6. Monthly form values replace annual sheet values ❌

**Files Involved:**
- `backend/app.py` (lines 1064-1190) - /api/submit endpoint
- `backend/sheets_service.py` (line 772) - check_approval() gets existing record

**Fix Strategy (if this is the bug):**
- Change merge logic from dict override to priority-based selection
- Use Form16 values when both Form16 + Payslip present
- Don't override annual values with form-submitted values
- Apply explicit priority: Form16 > Sheet stored > User input

---

### 🟡 BUG #2: Annualization Not Executing (15% probability)

**Location:** `backend/services/normalization_service.py` line 61

```python
def _annualize_payslip_field(field_name, value, doc_type):
    # Should multiply monthly by 12
    if doc_type != 'payslip' or not isinstance(value, (int, float)):
        return value
    
    monthly_fields = {...}
    if field_name in monthly_fields and value > 0:
        return value * 12  # Should happen here
    return value
```

**How it could fail:**
1. Code exists but not called ❌
2. Called but doc_type is wrong (not "payslip") ❌
3. Called but condition fails ❌
4. Multiplies but result is discarded ❌

**Files Involved:**
- `backend/services/normalization_service.py` (line 61) - _annualize_payslip_field()
- `backend/services/normalization_service.py` (lines 215, 265, 293) - Calls to annualize
- `backend/services/document_processor.py` (line 194) - Calls normalize_extractions()
- `backend/itr_extractor.py` (line 75) - Calls document_processor

**Fix Strategy (if this is the bug):**
- Add debug logging to confirm _annualize_payslip_field() is called
- Verify doc_type == "payslip"
- Verify value is numeric
- Verify multiplication result is returned and stored
- If any step fails, fix that step

---

### 🟢 BUG #3: validate_form16_payslip_consistency Override (5% probability)

**Location:** `backend/ai_service.py` lines 1118-1127

```python
# In validate_form16_payslip_consistency()
if form16_doc:
    for field_key, _ in annual_fields:
        form16_val = form16_doc.get(field_key)  # Getting from raw extraction
        if form16_val and form16_val != 0:
            merged_data[field_key] = form16_val  # Overriding with raw value
```

**How it fails:**
1. Both Form16 AND Payslip documents uploaded
2. form16_doc extracted from raw extractions list (may not be normalized)
3. Code overrides merged_data with raw (possibly monthly) values ❌

**Files Involved:**
- `backend/ai_service.py` (lines 1000-1135) - validate_form16_payslip_consistency()
- `backend/app.py` (line 942) - Calls validate_form16_payslip_consistency()

**Fix Strategy (if this is the bug):**
- Check if form16_doc contains normalized or raw values
- If raw, apply annualization before using values
- Or use merged_data values instead of form16_doc values

---

## Code Tracing Results

### Data Flow Chain

```
1. Document Upload
   ↓
2. /api/extract endpoint (app.py:765)
   ↓
3. document_processor.process_documents() 
   ├─ Vision extraction
   ├─ normalization_service.normalize_extractions()
   │  └─ _annualize_payslip_field() (should multiply by 12)
   └─ Returns normalized_data
   ↓
4. itr_extractor._build_response()
   └─ Returns response_data (should be annualized)
   ↓
5. app.py:/api/extract
   ├─ merge_extractions() - Works on normalized data
   ├─ validate_form16_payslip_consistency() - Might override?
   ├─ clean_extraction() - Sanity checks
   └─ sheets_service.update_row() - Saves to sheet
   ↓
6. Google Sheets
   ├─ Should have annual values
   └─ Actually has MONTHLY values ❌
   ↓
7. /api/submit endpoint (app.py:1064)
   ├─ Gets form submission data
   ├─ Gets existing record from sheet
   ├─ MERGES: {**existing_rec, **data}  ← POTENTIAL BUG #1
   └─ Overwrites annual with monthly?
   ↓
8. Database/Sheets
   └─ Stores MONTHLY values ❌
```

---

## What Files Will Be Affected By Each Fix

### If Bug #1 (Form Override) - 80% probability

**Files to MODIFY:**
1. `backend/app.py` - Line 1130-1140 in /api/submit endpoint
   - Change merge logic
   - Implement priority: Form16 > Payslip > User input

**Files to VERIFY (not modify yet):**
- `backend/sheets_service.py` - check_approval() logic
- `frontend/app.js` - What values are sent in submission

---

### If Bug #2 (Annualization) - 15% probability

**Files to MODIFY:**
1. `backend/services/normalization_service.py` - Lines 61, 215, 265, 293
   - Add debug logging to verify execution
   - Fix if any condition is wrong
   - Verify multiplication and return

**Files to VERIFY:**
- `backend/services/document_processor.py` - Line 194 (calls normalize)
- `backend/itr_extractor.py` - Line 75 (calls document_processor)

---

### If Bug #3 (validate_form16_payslip override) - 5% probability

**Files to MODIFY:**
1. `backend/ai_service.py` - Lines 1118-1127
   - Verify source of form16_val
   - Fix if using raw non-normalized values
   - Apply annualization if needed

**Files to VERIFY:**
- `backend/app.py` - Line 942 (calls validate function)

---

## Diagnostic Logging Points (NOT IN CODE YET)

To identify which bug is real, I need to add logging at these points:

### Phase 1: Extract Output Logging
```
File: backend/itr_extractor.py
Location: _build_response() line 65
Add: print(f"[EXTRACT_OUTPUT] gross_salary = {response_data.get('gross_salary')}")
Expected: 3,141,557 (annual)
If shows: 233,937 (monthly) → Bug #2
```

### Phase 2: Sheet Data Logging  
```
File: backend/app.py
Location: /api/extract line 955, before sheets_service.update_row()
Add: print(f"[BEFORE_SAVE] merged data gross_salary = {merged.get('gross_salary')}")
Expected: 3,141,557 (annual)
If shows: 233,937 (monthly) → Bug #2 or #3
```

### Phase 3: Form Submission Logging
```
File: backend/app.py
Location: /api/submit line 1083
Add: print(f"[SUBMIT_INPUT] form data gross_salary = {data.get('gross_salary')}")
Expected: Could be 3,141,557 or 233,937
If shows: 233,937 → Bug #1 is real
```

### Phase 4: Merge Result Logging
```
File: backend/app.py
Location: /api/submit line 1136
Add: print(f"[AFTER_MERGE] merged_data gross_salary = {merged_data.get('gross_salary')}")
Expected: 3,141,557 (from sheet)
If shows: 233,937 (from form) → Bug #1 confirmed
```

---

## Summary for User

### What I Found

1. **My annualization code EXISTS** in normalization_service.py
2. **But the database still has monthly values**, which means:
   - Either annualization isn't running/working
   - Or annualized values are being overwritten later

### Three Hypotheses (Ranked by Probability)

| # | Bug | Location | Probability | Root Cause |
|---|-----|----------|-------------|-----------|
| 1 | Form Override | app.py:1132 | 80% | Form submission overrides sheet values |
| 2 | No Annualization | normalization_service.py:61 | 15% | Annualization code not executing |
| 3 | Raw Value Override | ai_service.py:1123 | 5% | Using raw non-normalized values |

### Files That Will Be Affected (When We Fix)

**Depending on which bug is real:**
- **Bug #1 Fix:** Modify `app.py` (1 file)
- **Bug #2 Fix:** Modify `normalization_service.py` (1 file)
- **Bug #3 Fix:** Modify `ai_service.py` (1 file)

### What I'm NOT Doing Yet

- ❌ No code changes
- ❌ No commits
- ❌ No modifications to any backend files

### What I Need From You

To identify the actual bug, I need you to:

1. Add the 4 debug logging statements above to the code
2. Run the extraction with the test documents (Form16 + Payslip)
3. Provide the logs that show:
   - `[EXTRACT_OUTPUT]` - What's returned from extraction?
   - `[BEFORE_SAVE]` - What's saved to sheet?
   - `[SUBMIT_INPUT]` - What's in form submission?
   - `[AFTER_MERGE]` - What's the final merged value?

Once I see these logs, I can identify the EXACT location of the bug and propose a specific fix.

---

## Files Currently Modified (Not Committed)

From my previous session, these files have changes that weren't committed:

1. `backend/services/normalization_service.py` - Annualization code (lines 61+)
2. `backend/tax_engine.py` - Input logging (lines 179-193)
3. `backend/sheets_service.py` - home_loan_interest storage (line 711)
4. `backend/app.py` - Multiple validation/aggregation functions

These changes are STILL there but haven't resolved the monthly→annual issue.

---

## Status

**ANALYSIS PHASE ONLY**
- Do not commit anything yet
- Do not modify code yet
- Need diagnostic logging first to pinpoint exact bug
- Once logs identify the bug, will propose targeted fix

**Expected Outcome:** Root cause identified + targeted fix (not blanket changes)
