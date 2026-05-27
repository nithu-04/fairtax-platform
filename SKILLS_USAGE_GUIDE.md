# FairTax Backend — 5-Skill Implementation Guide

**Your 5 Critical Skills for Backend Optimization:**
1. `/code-review` — Find bugs before testing
2. `/security-review` — Ensure data safety before production
3. `anthropic-skills:xlsx` — Create test datasets
4. `anthropic-skills:pdf` — Extract and validate samples
5. `loop` — Monitor background jobs and repeated testing

---

## Skill #1: `/code-review` ⭐⭐⭐ HIGHEST PRIORITY

### Purpose
Find logical errors, edge cases, security issues, and compliance bugs in your backend code **before** you run it.

### When to Use
- ✅ After modifying `tax_engine.py`
- ✅ After updating `ai_service.py` extraction logic
- ✅ After changing `quality_checker.py` validation rules
- ✅ After modifying `sheets_service.py` save logic
- ✅ Before any production commit

### How to Use

**Basic Usage:**
```bash
# Review current changes at medium effort level
/code-review

# Or specify effort level for depth
/code-review --level high    # Most thorough
/code-review --level medium  # Balanced
/code-review --level low     # Quick check
```

**With Inline Comments (for PRs):**
```bash
/code-review --comment   # Posts findings as inline PR comments
```

### Example: Testing Tax Calculation Fix

**Scenario:** You modified `tax_engine.py` to fix marginal relief calculation

```bash
# Step 1: Edit tax_engine.py
# - Changed compute_tax_before_cess() logic
# - Modified rebate calculation
# - Updated slab application

# Step 2: Run code-review
/code-review --level high

# What it checks:
# ✓ Syntax errors
# ✓ Logic errors in slab computation
# ✓ Edge cases (income = 0, very high income, etc.)
# ✓ Off-by-one errors in rebate logic
# ✓ Float precision issues
# ✓ Compliance with tax rules (rebate shouldn't exceed tax)
# ✓ Interaction with other functions
# ✓ Missing error handling

# Step 3: Review findings
# - Reads the detailed report
# - Understands each issue

# Step 4: Fix issues
# - Update code based on findings
# - Re-run /code-review

# Step 5: Only proceed to /verify when code-review passes
```

### What Code-Review Catches (For Your Services)

#### For `tax_engine.py`:
- Tax calculation logic errors
- Slab boundary issues (income exactly at threshold)
- Rebate exceeding tax amount (impossible state)
- Loss handling (negative taxable income)
- Cess application errors
- Regime comparison logic flaws

#### For `ai_service.py`:
- JSON parsing errors
- Prompt injection vulnerabilities
- API error handling gaps
- Null/empty field handling
- Confidence score validation bugs
- Type conversion errors (string → number)

#### For `quality_checker.py`:
- Validation rule conflicts
- Missing edge cases
- Threshold setting issues
- Null value handling

#### For `sheets_service.py`:
- Data format inconsistencies
- Idempotency issues (duplicate saves)
- Missing field validations
- PAN deduplication logic flaws

### Best Practices

1. **Always run after code changes:**
   ```bash
   # Don't skip this step
   /code-review --level high
   ```

2. **Use high level for critical services:**
   ```bash
   # For tax_engine.py (calculation) - always high
   /code-review --level high
   
   # For other services - medium is ok
   /code-review --level medium
   ```

3. **Fix all findings before testing:**
   - Don't run `/verify` until code-review passes
   - Otherwise you'll test broken code

4. **Document findings:**
   - Keep notes of patterns you find
   - Update CLAUDE.md with common issues

---

## Skill #2: `/security-review` ⭐⭐ SECOND PRIORITY

### Purpose
Ensure sensitive data (PAN, Aadhaar, salary) is protected and APIs are securely configured **before** production deployment.

### When to Use
- ✅ Before deploying to production
- ✅ After handling PII (personally identifiable information)
- ✅ After modifying `sheets_service.py` (stores sensitive data)
- ✅ After updating `config.py` (handles API keys)
- ✅ After changing file upload handling in `app.py`
- ✅ Before pushing to main branch

### How to Use

**Basic Usage:**
```bash
# Review current branch for security issues
/security-review
```

### Example: Before Production Deployment

**Scenario:** You fixed several backend issues and want to deploy

```bash
# Step 1: Ensure all code-reviews passed ✓
# Step 2: Ensure all /verify tests passed ✓

# Step 3: Run security-review
/security-review

# What it checks:
# ✓ PII exposure (PAN, Aadhaar, salary data in logs)
# ✓ API key handling (not hardcoded, properly masked)
# ✓ Data encryption (Google Sheets encrypted? File storage secure?)
# ✓ Authentication (valid session management, OTP flow secure)
# ✓ Input validation (no SQL injection, no buffer overflow)
# ✓ File upload security (virus scanning, size limits, file type validation)
# ✓ WhatsApp API security (token not exposed)
# ✓ OpenAI API key protection
# ✓ Google Sheets access control

# Step 4: Review findings
# - Fix any exposed PII in logs
# - Ensure API keys are in .env, not in code
# - Verify data encryption methods
# - Check access controls

# Step 5: Only deploy when security-review passes
```

### What Security-Review Checks (For Your Services)

#### For `sheets_service.py`:
- ✓ Google service account credentials not exposed
- ✓ Sensitive data properly formatted before save
- ✓ Sheet access is restricted (not public)
- ✓ No PAN/Aadhaar logged in debug output

#### For `app.py`:
- ✓ Flask secret key not hardcoded
- ✓ CORS properly configured (not open to all origins)
- ✓ File upload endpoints validated
- ✓ Session tokens handled securely

#### For `ai_service.py`:
- ✓ OpenAI API key not exposed in prompts
- ✓ Extracted PII not logged
- ✓ API errors don't leak sensitive data

#### For `config.py`:
- ✓ All API keys in .env (not hardcoded)
- ✓ Service account JSON properly secured
- ✓ Default values don't contain secrets

#### For file uploads:
- ✓ File validation prevents malicious uploads
- ✓ Uploaded files stored securely (not in web root)
- ✓ File permissions restricted (not world-readable)

### Best Practices

1. **Always run before production:**
   ```bash
   # Non-negotiable for production push
   /security-review
   ```

2. **Fix all security issues:**
   - No "we'll fix later" on security
   - Every finding must be addressed

3. **Document sensitive data handling:**
   - Update CLAUDE.md with data flow
   - Ensure all team members understand security measures

4. **Regular security audits:**
   - Run every month even without changes
   - Keep security top-of-mind

---

## Skill #3: `anthropic-skills:xlsx` ⭐ TEST SUITE CREATION

### Purpose
Create structured test datasets to validate tax calculations against real-world scenarios.

### When to Use
- ✅ Building test suite for tax_engine.py
- ✅ Validating calculation accuracy
- ✅ Testing edge cases (income boundaries, deduction limits)
- ✅ Creating regression test data
- ✅ Comparing old vs new regime calculations

### How to Use

**Trigger the skill:**
```bash
/anthropic-skills:xlsx
```

### Example: Create Tax Calculation Test Suite

**Scenario:** You want to test tax calculations against 50 real salary scenarios

```bash
# Step 1: Prepare test data requirements
# Scenarios needed:
# - Low income (₹2.5L) - no tax
# - Below old regime threshold
# - Above old regime threshold
# - High earner (₹25L+)
# - With HRA deduction
# - With 80C investments
# - With home loan interest
# - Freelancer (different deductions)
# - Senior citizen (higher rebate threshold)
# - Multiple income sources

# Step 2: Trigger xlsx skill
/anthropic-skills:xlsx

# What it creates:
# ✓ Spreadsheet with test scenarios
# ✓ Columns: gross_salary, hra, pf, investments_80c, home_loan_int, age, etc.
# ✓ Pre-calculated expected results (tax_old, tax_new)
# ✓ Formula columns for automated checking
# ✓ Pass/fail validation logic

# Step 3: Use in testing workflow
# a) Extract test scenarios from Excel
# b) Feed to api_service (extraction simulation)
# c) Run through tax_engine.py
# d) Compare results against Excel expected_result column
# e) Flag any mismatches

# Step 4: Document discrepancies
# - If calculated tax ≠ expected: Flag as bug
# - If off by rounding: Document as acceptable variance
# - Create separate sheet for edge cases that fail

# Step 5: Iterate
# - Fix bugs in tax_engine.py
# - Re-run all test scenarios
# - Ensure 100% pass rate
```

### Test Dataset Structure

**Spreadsheet Columns:**

```
Scenario_ID | Gross_Salary | HRA | PF | Investments_80C | Home_Loan_Interest | Age | Taxpayer_Type | 
Tax_Old_Expected | Tax_New_Expected | Tax_Old_Calc | Tax_New_Calc | Pass_Fail | Notes

1           | 500000       | 60k | 50k | 100k           | 0                  | 35  | Salaried      |
32500       | 20000        | [auto-calc] | [auto-calc] | PASS | Standard case

2           | 250000       | 0   | 20k | 50k            | 0                  | 30  | Salaried      |
0           | 0            | [auto-calc] | [auto-calc] | PASS | Below tax threshold

3           | 2500000      | 300k | 150k | 150k         | 500k               | 40  | Salaried      |
340000      | 250000       | [auto-calc] | [auto-calc] | PASS | High earner with deductions

...50+ more scenarios
```

### Testing Workflow with Excel

```python
# Pseudocode for using Excel results

import openpyxl
from tax_engine import slab_tax_old, slab_tax_new

# Load test data
wb = openpyxl.load_workbook('tax_test_scenarios.xlsx')
ws = wb['Test_Scenarios']

# For each test row
for row in ws.iter_rows(2, ws.max_row):  # Skip header
    gross = row[1].value
    investments = row[4].value
    
    # Calculate taxable income
    taxable = gross - investments - hra - pf
    
    # Run through tax_engine
    tax_old = slab_tax_old(taxable)
    tax_new = slab_tax_new(taxable)
    
    # Compare against expected
    expected_old = row[8].value
    expected_new = row[9].value
    
    pass_fail = "PASS" if (tax_old == expected_old and tax_new == expected_new) else "FAIL"
    
    # Write results
    row[10].value = tax_old  # Calculated old
    row[11].value = tax_new  # Calculated new
    row[12].value = pass_fail

# Save results
wb.save('tax_test_results.xlsx')
print(f"Test run complete. Check PASS/FAIL column for results.")
```

### Best Practices

1. **Start small, grow:**
   - Create 10 scenarios first
   - Verify they work
   - Expand to 50+

2. **Cover edge cases:**
   - Exactly at tax threshold
   - Just below/above deduction limits
   - Zero income
   - Negative scenarios (loss carryforward)

3. **Document expected values:**
   - Use real-world tax calculators to validate
   - Document calculation method in notes
   - Include source (ClearTax, ITR assistant, etc.)

4. **Maintain as regression test:**
   - Keep Excel file in version control
   - Re-run after any tax_engine.py change
   - Prevent accidental breaking changes

---

## Skill #4: `anthropic-skills:pdf` ⭐ EXTRACT & VALIDATE SAMPLES

### Purpose
Extract text from real tax documents (Form 16, ITR, investment certificates) to test ai_service.py extraction accuracy.

### When to Use
- ✅ Testing ai_service.py extraction with real documents
- ✅ Debugging extraction accuracy issues
- ✅ Validating OCR fallback works
- ✅ Creating benchmark extraction results
- ✅ Testing edge cases (old forms, blurry documents)

### How to Use

**Trigger the skill:**
```bash
/anthropic-skills:pdf
```

### Example: Extract & Validate Form 16

**Scenario:** You want to test ai_service extraction against 5 real Form 16 samples

```bash
# Step 1: Collect test PDFs
# - Form 16 2024-25 (standard)
# - Form 16 old format 2022-23 (edge case)
# - Blurry/poorly scanned Form 16 (challenge case)
# - Multi-page Form 16 (integration test)
# - Home loan certificate (investment extraction test)

# Step 2: Use pdf skill
/anthropic-skills:pdf

# What it does:
# ✓ Opens each PDF
# ✓ Extracts text content
# ✓ Converts to structured data
# ✓ Returns extracted fields

# Step 3: Compare extraction results
# a) For each Form 16, run ai_service._call_openai()
# b) Compare extracted fields against manual review
# c) Check confidence scores
# d) Note any missing/incorrect fields

# Step 4: Document findings
# - Which forms extract well?
# - Which forms have issues?
# - What confidence threshold should trigger manual review?
# - Do old forms extract differently?

# Step 5: Improve extraction if needed
# - Update EXTRACTION_PROMPT if patterns found
# - Adjust confidence thresholds
# - Add handling for form variations
# - Test again with same 5 PDFs
```

### Testing Workflow with PDF Extraction

```python
# Pseudocode for PDF extraction testing

from anthropic import Anthropic
from ai_service import extract_from_file, _call_openai

# Test files
test_pdfs = [
    'form16_standard.pdf',
    'form16_old_format.pdf',
    'form16_blurry.pdf',
    'home_loan_cert.pdf',
]

results = []

for pdf_path in test_pdfs:
    print(f"\n=== Testing {pdf_path} ===")
    
    # Use pdf skill to extract text
    with open(pdf_path, 'rb') as f:
        file_bytes = f.read()
    
    # Run through ai_service
    try:
        extracted = extract_from_file(file_bytes)
        
        print(f"Extracted fields:")
        for field, value in extracted.items():
            print(f"  {field}: {value}")
        
        # Check key fields exist
        required = ['gross_salary', 'pan', 'tds_paid']
        missing = [f for f in required if not extracted.get(f)]
        
        if missing:
            print(f"⚠️ Missing: {missing}")
        else:
            print(f"✓ All required fields present")
        
        # Store result
        results.append({
            'pdf': pdf_path,
            'success': len(missing) == 0,
            'missing': missing,
            'extracted': extracted
        })
        
    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        results.append({
            'pdf': pdf_path,
            'success': False,
            'error': str(e)
        })

# Summary
print("\n=== EXTRACTION TEST SUMMARY ===")
passed = len([r for r in results if r['success']])
print(f"Passed: {passed}/{len(test_pdfs)}")

for r in results:
    status = "✓ PASS" if r['success'] else "❌ FAIL"
    print(f"{r['pdf']}: {status}")
```

### What PDF Extraction Validates

#### For `ai_service.py`:
- ✓ Vision API works with real documents
- ✓ JSON output is valid
- ✓ All required fields extracted
- ✓ Confidence scores are meaningful
- ✓ Handles form variations

#### For `ocr_service.py`:
- ✓ OpenRouter/Google Vision extracts text correctly
- ✓ Fallback works when primary fails
- ✓ Blurry documents handled gracefully

#### For `quality_checker.py`:
- ✓ Extracted values pass validation
- ✓ Confidence thresholds are appropriate
- ✓ Edge cases detected (zero salary, missing PAN)

### Best Practices

1. **Test with variety:**
   - New documents (current year)
   - Old documents (different format)
   - Good quality
   - Blurry/challenging
   - Multi-page

2. **Keep benchmark results:**
   - Save extraction results as reference
   - Compare future extractions against baseline
   - Detect accuracy degradation

3. **Document extraction rules:**
   - Update CLAUDE.md with what works
   - Note edge cases discovered
   - Record confidence score thresholds that work

4. **Create golden dataset:**
   - Maintain 5-10 test PDFs in repo
   - Use consistently for regression testing
   - Add new PDFs as edge cases discovered

---

## Skill #5: `loop` ⭐ MONITOR & REPEATED TESTING

### Purpose
Repeatedly run tests at intervals to monitor background jobs, validate stability, and catch intermittent issues.

### When to Use
- ✅ Testing scheduler_service jobs
- ✅ Monitoring API endpoints during development
- ✅ Validating extraction consistency
- ✅ Testing referral logic repeatedly
- ✅ Watching for data sync issues
- ✅ Running smoke tests during active development

### How to Use

**Trigger the skill (no interval = let model self-pace):**
```bash
/loop [interval] [command]

# Example:
/loop 30s /verify           # Run verify every 30 seconds
/loop 5m /code-review       # Run code-review every 5 minutes
/loop /verify               # Let Claude pace itself (self-paced)
```

### Example 1: Monitor Scheduler Jobs

**Scenario:** You're debugging scheduler_service and want to watch if background jobs run correctly

```bash
# Step 1: Start scheduler monitoring
/loop 1m /verify

# What happens:
# - Every 60 seconds, runs /verify
# - Checks if scheduler jobs executed
# - Monitors for errors in logs
# - Validates data was updated
# - Reports findings each iteration

# Continues until:
# - You interrupt (Ctrl+C)
# - Or you've seen pattern (e.g., 5 successful runs)

# Step 2: Review logs
# - Check if jobs logged output
# - Verify Google Sheets was updated
# - Look for API errors

# Step 3: Stop and analyze
# - If jobs ran every time: ✓ Scheduler working
# - If jobs missed some runs: ⚠️ Intermittent issue
# - If jobs never ran: ❌ Scheduler broken
```

### Example 2: Test Extraction Consistency

**Scenario:** You want to verify ai_service.py extracts consistently from same document

```bash
# Step 1: Upload same Form 16 multiple times
# (Extract multiple times to check consistency)

/loop 2m /verify

# What happens:
# - Every 2 minutes, uploads test Form 16
# - Extracts fields using ai_service
# - Compares results to previous run
# - Flags inconsistencies

# Expected behavior:
# - Run 1: Extract salary = 500000, confidence = 0.95
# - Run 2: Extract salary = 500000, confidence = 0.95
# - Run 3: Extract salary = 500000, confidence = 0.95
# ✓ CONSISTENT

# Bad behavior:
# - Run 1: salary = 500000
# - Run 2: salary = 500100 (different!)
# - Run 3: salary = 499900
# ❌ INCONSISTENT - indicates prompt randomness or API variance

# Step 2: If inconsistent, lower temperature
# - Check ai_service._call_openai() temperature=0.0
# - Should be deterministic (no randomness)
# - Increase temperature only if needed for variety
```

### Example 3: Referral Validation Testing

**Scenario:** Test referral deduplication logic repeatedly to catch edge cases

```bash
# Step 1: Create loop test for referral logic
/loop 10s /verify

# Runs referral validation:
# - Referral 1: New user, valid → PASS ✓
# - Referral 2: Same PAN → Should reject ✓
# - Referral 3: New user → PASS ✓
# - Referral 4: Same device → Should flag ✓
# - Referral 5: Valid → PASS ✓

# If any iteration fails, /loop stops
# Helps find edge cases that happen intermittently
```

### Example 4: Self-Paced Testing (No Interval)

**Scenario:** Let Claude decide best pacing for comprehensive testing

```bash
# Step 1: Start self-paced loop
/loop /verify

# Claude decides:
# - How long each test takes
# - When to pause for analysis
# - When to iterate again
# - When to stop (goals met)

# Useful when:
# - You're unsure what interval to use
# - Testing complex scenarios
# - Need flexible pacing
```

### Loop Output Interpretation

```
Iteration 1 (00:00)
├─ /verify: Extraction test
├─ Result: ✓ Fields extracted correctly
├─ Salary: 500000, Confidence: 0.95
└─ Status: PASS

Iteration 2 (00:30)
├─ /verify: Re-extraction test
├─ Result: ✓ Same result as iteration 1
├─ Salary: 500000, Confidence: 0.95
└─ Status: PASS ✓ CONSISTENT

Iteration 3 (01:00)
├─ /verify: Extraction test
├─ Result: ✓ Still consistent
└─ Status: PASS

Loop Summary: 3/3 passed, Consistent behavior detected
Loop Complete: Ready for production
```

### Best Practices

1. **Start with short intervals:**
   ```bash
   # Don't start with 5m, start with 30s
   /loop 30s /verify
   
   # Once confident, extend
   /loop 2m /verify
   ```

2. **Define stopping criteria:**
   - "Run 5 times successfully" → Stop
   - "Until error is found" → Stop on first error
   - "Until pattern confirmed" → Run 10 times

3. **Monitor actively:**
   - Watch the first 2-3 iterations
   - Don't leave it running unattended initially
   - Check logs after loop completes

4. **Use with code-review:**
   ```bash
   # Best practice:
   /code-review --level high   # Find bugs first
   /loop 1m /verify            # Then test with monitoring
   ```

5. **Document results:**
   - Save loop output
   - Note consistency findings
   - Update CLAUDE.md with patterns

---

## 🎯 Complete Workflow: Using All 5 Skills Together

### Scenario: Optimize Tax Calculation & Create Test Suite

```
STEP 1: CODE REVIEW (Before testing)
├─ /code-review --level high
├─ Review findings
└─ Fix bugs in tax_engine.py

STEP 2: CREATE TEST SUITE (Building confidence)
├─ /anthropic-skills:xlsx
├─ Build test scenarios spreadsheet
├─ Add expected results
└─ Save as tax_test_scenarios.xlsx

STEP 3: EXTRACT SAMPLES (Validation data)
├─ /anthropic-skills:pdf
├─ Extract from 5 real Form 16 PDFs
├─ Compare against manual review
└─ Document extraction accuracy

STEP 4: TEST WITH LOOP (Repeated validation)
├─ /loop 2m /verify
├─ Run extraction + calculation 5 times
├─ Verify consistency
└─ Stop once pattern confirmed

STEP 5: SECURITY CHECK (Before production)
├─ /security-review
├─ Verify no PII exposed
├─ Check API keys secure
└─ Confirm data encryption
```

### Success Criteria

```
✓ Code-review: Zero critical issues
✓ Excel test suite: 100% pass rate
✓ PDF extraction: All 5 samples extract correctly
✓ Loop testing: 5/5 consistent results
✓ Security-review: Zero vulnerabilities
→ Ready for production deployment!
```

---

## Quick Reference: 5 Skills Cheat Sheet

| Skill | When | Command | Expect |
|-------|------|---------|--------|
| `/code-review` | After code change | `/code-review --level high` | Bug report, fixes needed |
| `/security-review` | Before prod | `/security-review` | Security report, clearance |
| `xlsx` | Build tests | `/anthropic-skills:xlsx` | Test spreadsheet, scenarios |
| `pdf` | Extract samples | `/anthropic-skills:pdf` | Extracted text, field data |
| `loop` | Monitor | `/loop 1m /verify` | Repeated test results, consistency |

---

## Your Next Steps

1. **Read this guide** (you are here ✓)
2. **Pick one area to optimize:**
   - Option A: Tax calculation accuracy
   - Option B: Data validation rules
   - Option C: Extraction reliability
3. **Run the workflow for that area:**
   - `/code-review` → Find bugs
   - `/anthropic-skills:xlsx` → Create tests (if needed)
   - `/loop 1m /verify` → Test repeatedly
   - `/security-review` → Check security
4. **Document findings in CLAUDE.md**
5. **Commit and push**

**Which area would you like to start with?**
