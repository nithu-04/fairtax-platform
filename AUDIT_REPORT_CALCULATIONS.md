# AUDIT REPORT: FairTax Tax Calculation Engine

## CRITICAL ISSUES FOUND (PAKKA PAKKA AUDIT)

---

### 1. **GTI CALCULATION - FUNDAMENTALLY BROKEN** ⛔⛔⛔

**Location:** `tax_engine.py`, lines 145-176 (OLD REGIME) and lines 290-298 (NEW REGIME)

**ISSUE:** The variable labeled "gti" is NOT the true Gross Total Income (GTI).

**OLD REGIME (Line 155):**
```python
gti = gross + other_income - sec10_total - home_loan_interest - std_deduction - pt
```

**NEW REGIME (Line 290):**
```python
gti_new = gross + other_income - std_new
```

**CORRECT CALCULATION SHOULD BE:**
- GTI = Gross Salary + Other Income - Section 10 Exemptions ONLY
- Then SEPARATELY: Taxable = GTI - Section 24 (Home Loan) - Standard Deduction - PT - Section 80 Deductions

**IMPACT:**
- Surcharge is calculated using INCORRECT GTI (lines 160, 295)
- Surcharge bands are applied to pre-deduction amounts, which will calculate WRONG surcharge
- This affects final tax calculation for high-income earners

**SEVERITY: CRITICAL** - Tax liability will be INCORRECT for surcharge bracket

---

### 2. **SURCHARGE CALCULATION - WRONG INPUT DATA** ⛔⛔⛔

**Location:** `tax_engine.py`, lines 84-112, and usage in lines 160, 295

**ISSUE:** Surcharge is applied based on modified GTI that already has deductions subtracted.

```python
Line 160: s_info = _apply_surcharge_and_cess(tax, gti)
Line 295: s_info_new = _apply_surcharge_and_cess(tax_new, gti_new)
```

The `_apply_surcharge_and_cess()` function uses the income parameter for surcharge band lookup (line 92).
But the income being passed is NOT true GTI.

**EXAMPLE:**
- True GTI = ₹50 lakhs
- With deductions = ₹40 lakhs (what's being passed)
- This would NOT trigger surcharge at ₹50L threshold
- But taxpayer SHOULD pay surcharge because true income is ₹50L

**SEVERITY: CRITICAL** - Surcharge amount will be WRONG

---

### 3. **NEW REGIME - GTI INCLUDES STANDARD DEDUCTION** ⛔

**Location:** `tax_engine.py`, line 290

```python
Code: gti_new = gross + other_income - std_new
```

**WRONG:** Standard deduction should NOT be subtracted to get GTI.
GTI is BEFORE any deductions.

**Correct:**
```python
gti_new = gross + other_income  (true GTI)
taxable_new = gti_new - std_new  (then apply standard deduction)
```

**SEVERITY: CRITICAL** - Surcharge for new regime will be calculated on wrong income

---

### 4. **SECTION 80G - NOT IMPLEMENTED** ⛔

**Location:** `tax_engine.py`, line 265

```python
sec_80g = g("sec_80g")  # Donations (80G) - treated as a deduction here (AI may refine)
```

**ISSUE:** Takes input value directly without applying Section 80G rules:
- Does NOT verify 50% vs 100% deduction eligibility
- Does NOT apply qualifying limit (only 50% of GTI or 100% depending on charity type)
- Does NOT reject cash donations over ₹2,000

**Per Rules #16:** "Do NOT directly deduct uploaded amount. Need: 50% vs 100%, qualifying limit, adjusted GTI logic"

**SEVERITY: HIGH** - Donation deductions may be over-claimed without validation

---

### 5. **SURCHARGE THRESHOLD BANDS - VERIFY FY 2025-26** ⚠️

**Location:** `tax_config.py`, lines 55-62

Current bands:
```python
SURCHARGE_BANDS = [
    (5000000, 0.10),     # ₹50L → 10%
    (10000000, 0.15),    # ₹1Cr → 15%
    (20000000, 0.25),    # ₹2Cr → 25%
    (50000000, 0.37),    # ₹5Cr → 37%
]
```

These thresholds are for TOTAL INCOME (GTI).
BUT since GTI calculation is wrong above, these bands won't apply correctly anyway.

**ACTION:** Verify these match FY 2025-26 actual surcharge rules

**SEVERITY: HIGH** (after GTI is fixed)

---

### 6. **SECTION 80D SENIOR CITIZEN CAP - INCONSISTENT** ⚠️

**Location:** `tax_engine.py`, lines 254-261 vs `extraction_validator.py`, lines 36-38

**tax_engine.py:**
```python
50000 if parents_senior else 25000  (line 260)
```

**extraction_validator.py:**
```python
'sec_80d_senior_parents': 100000  (line 38)
```

**MISMATCH:** Validator caps senior parents at ₹1,00,000 but engine caps at ₹50,000.

**CORRECT CAP (FY 2025-26):**
- Self/spouse/children: ₹25,000
- Parents (normal): ₹25,000
- Parents (senior citizen): ₹50,000 (NOT ₹1,00,000)

The validator has the WRONG cap at ₹1,00,000.

**SEVERITY: MEDIUM** - Will over-claim deduction for senior parent policies

---

### 7. **SECTION 80CCD(2) - CAP MISSING** ⚠️

**Location:** `tax_engine.py`, lines 251-252

```python
sec_80ccd_2 = min(g("nps_employer"), 0.10 * basic)
sec_80ccd_2_new = min(g("nps_employer"), 0.14 * basic)
```

**ISSUE:** Missing absolute cap of ₹150,000 (some rules) or ₹2,00,000 (others)

Should be:
```python
sec_80ccd_2 = min(g("nps_employer"), 0.10 * basic, 150000)  # OLD REGIME
```

**SEVERITY: MEDIUM** - Needs verification against FY 2025-26 rules

---

### 8. **VARIANT A RECOMMENDATION - LOGIC ISSUE** ⚠️

**Location:** `tax_engine.py`, lines 301-302

```python
variant_a_refund = max(old_a["refund"], refund_new)
variant_a_regime = "OLD" if old_a["refund"] >= refund_new else "NEW"
```

**ISSUE:** Recommends based on refund amount, but should recommend based on:
- Lowest TAX LIABILITY (not highest refund)
- Refund/Due is calculated as: tds_paid - tax
- But what matters is the NET tax after TDS, not gross refund

This may recommend suboptimal regime to taxpayer.

**SEVERITY: MEDIUM** - Recommendation accuracy affected

---

## SUMMARY OF CALCULATION ERRORS

### WRONG CALCULATIONS:
- ✗ Surcharge amount (uses incorrect income base)
- ✗ Total tax in surcharge brackets (dependent on surcharge)
- ✗ New regime taxable income (includes standard deduction in GTI)
- ✗ New regime surcharge (uses modified income)
- ✗ Section 80G deduction (no validation)
- ✗ Section 80D senior parents (validator has ₹1L instead of ₹50K)

### CORRECT CALCULATIONS:
- ✓ Basic slab tax computation
- ✓ HRA exemption formula
- ✓ Section 80C cap (₹1,50,000)
- ✓ Section 80CCD(1B) cap (₹50,000)
- ✓ Home loan interest cap (₹2,00,000)
- ✓ Section 80TTA savings interest cap (₹10,000)
- ✓ Section 80D self cap (₹25,000)

---

## RECOMMENDED FIXES (PRIORITY ORDER)

### 1. FIX GTI CALCULATION (CRITICAL)

**Old regime:**
```python
# Current (WRONG):
gti = gross + other_income - sec10_total - home_loan_interest - std_deduction - pt
taxable = max(0, gti - deductions_total)

# Fixed:
gti = gross + other_income - sec10_total  # TRUE GTI
taxable = max(0, gti - home_loan_interest - std_old - pt - deductions_total)
# Use TRUE gti for surcharge
```

**New regime:**
```python
# Current (WRONG):
gti_new = gross + other_income - std_new
taxable_new = max(0, gti_new - sec_80ccd_2_new)

# Fixed:
gti_new = gross + other_income  # TRUE GTI
taxable_new = max(0, gti_new - std_new - sec_80ccd_2_new)
# Use TRUE gti_new for surcharge
```

### 2. FIX SURCHARGE CALCULATION
- Pass TRUE GTI to `_apply_surcharge_and_cess()`
- Ensure income parameter is BEFORE all deductions
- Test against all surcharge brackets

### 3. IMPLEMENT SECTION 80G VALIDATION
- Add donation validation logic
- Check 50% vs 100% eligibility
- Apply qualifying limit (as per donation type)
- Reject cash donations > ₹2,000

### 4. FIX SECTION 80D VALIDATOR CAP
- Change `'sec_80d_senior_parents': 100000` → `50000` in `extraction_validator.py`

### 5. VERIFY SECTION 80CCD(2) CAP
- Check FY 2025-26 rules for absolute cap
- Add cap if required

### 6. FIX VARIANT RECOMMENDATION
- Compare tax liability, not refund amount
- Recommend regime with LOWEST tax

---

## TESTING RECOMMENDATIONS

1. **Test with high-income earner** (above ₹50L GTI) to verify surcharge correctness
2. **Compare calculated tax** against manual ITR-1 calculation
3. **Verify donation deduction** against Section 80G actual rules
4. **Check Section 80D** calculation with senior citizen parents
5. **Reconcile** with 26AS/TDS data provided

---

## CONCLUSION

The tax calculation engine has **THREE CRITICAL ERRORS** that will produce INCORRECT tax calculations:

1. Wrong GTI calculation
2. Wrong Surcharge calculation  
3. Wrong New Regime calculation

These must be fixed before the system can be considered accurate. The extraction validator has good logic but is hampered by incorrect caps for Section 80D.

**Status: NOT READY FOR PRODUCTION** until GTI/Surcharge issues are fixed.

