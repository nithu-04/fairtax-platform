"""
FairTax — Tax engine for FY 2025-26 (AY 2026-27)
Implements correct formulas per FairTax_Calculation_Logic_FY2025-26.md
"""

import tax_config
from math import inf

# ================= HELPERS =================

def _num(x):
    """Convert input to float, handling None, empty strings, and commas."""
    if x is None or x == "":
        return 0.0
    try:
        return float(str(x).replace(',', ''))
    except:
        return 0.0


# ================= SLAB COMPUTATIONS =================

def _compute_slabs(taxable, regime):
    """Compute tax by applying slab rates to taxable income.
    Returns tax before rebate/surcharge/cess.
    """
    slabs = tax_config.SLABS.get(regime, [])
    tax = 0.0
    remaining = float(taxable)

    for limit, rate in slabs:
        chunk = min(remaining, limit)
        tax += chunk * rate
        remaining -= chunk
        if remaining <= 0:
            break
    return tax


def _apply_rebate(tax_before_rebate, taxable_income, regime):
    """Apply Section 87A rebate based on regime and taxable income.

    OLD: if TI ≤ 5L → rebate = min(tax, 12500), tax becomes 0 if TI ≤ 5L
    NEW: if TI ≤ 12L → tax becomes 0; if TI > 12L, marginal relief applies
    """
    rebate_cfg = tax_config.REBATE.get(regime, {})
    threshold = rebate_cfg.get('threshold', 0)
    cap = rebate_cfg.get('cap', 0)

    if taxable_income <= threshold:
        # Complete exemption up to threshold
        return 0.0, min(tax_before_rebate, cap)

    # For NEW regime above 12L, apply marginal relief
    if regime == 'NEW' and taxable_income > 1200000:
        capped_tax = max(0, taxable_income - 1200000)
        return min(tax_before_rebate, capped_tax), 0.0

    return tax_before_rebate, 0.0


def _apply_surcharge_and_cess(tax_after_rebate, taxable_income, regime):
    """Apply surcharge (with marginal relief) and 4% cess.

    Surcharge based on taxable income thresholds:
    - OLD/NEW: 50L→10%, 1Cr→15%, 2Cr→25%, 5Cr→37% (old) / 25% (new, capped)
    """
    # Surcharge bands: (threshold, rate)
    surcharge_bands_old = [
        (5000000, 0.10),    # 50L onwards: 10%
        (10000000, 0.15),   # 1Cr onwards: 15%
        (20000000, 0.25),   # 2Cr onwards: 25%
        (50000000, 0.37),   # 5Cr onwards: 37%
    ]

    surcharge_bands_new = [
        (5000000, 0.10),    # 50L onwards: 10%
        (10000000, 0.15),   # 1Cr onwards: 15%
        (20000000, 0.25),   # 2Cr onwards: 25%
        (50000000, 0.25),   # 5Cr onwards: 25% (capped, not 37%)
    ]

    bands = surcharge_bands_old if regime == 'OLD' else surcharge_bands_new

    # Find applicable surcharge rate
    surcharge_rate = 0.0
    for threshold, rate in bands:
        if taxable_income >= threshold:
            surcharge_rate = rate

    surcharge_raw = tax_after_rebate * surcharge_rate

    # Marginal relief: surcharge should not exceed income above threshold
    if surcharge_rate > 0:
        # Find which threshold applies
        threshold_for_relief = 0
        for threshold, rate in bands:
            if taxable_income >= threshold and rate == surcharge_rate:
                threshold_for_relief = threshold

        # Tax at threshold (without rebate, as per markdown)
        tax_at_threshold = _compute_slabs(threshold_for_relief, regime)
        max_total = tax_at_threshold + (taxable_income - threshold_for_relief)
        surcharge = max(0, min(surcharge_raw, max_total - tax_after_rebate))
    else:
        surcharge = 0.0

    tax_after_surcharge = tax_after_rebate + surcharge

    # Add 4% cess on (tax_after_rebate + surcharge)
    cess = round(tax_after_surcharge * tax_config.CESS_RATE, 2)
    total_tax = round(tax_after_surcharge + cess, 2)

    return {
        'surcharge_rate': surcharge_rate,
        'surcharge_amount': round(surcharge, 2),
        'tax_after_surcharge': round(tax_after_surcharge, 2),
        'cess_amount': cess,
        'total_tax': total_tax,
    }


def _tax_old(taxable_income):
    """Compute OLD regime total tax (slab → rebate → surcharge → cess)."""
    slab = _compute_slabs(taxable_income, 'OLD')
    tax_after_rebate, _ = _apply_rebate(slab, taxable_income, 'OLD')
    result = _apply_surcharge_and_cess(tax_after_rebate, taxable_income, 'OLD')
    return result['total_tax']


def _tax_new(taxable_income):
    """Compute NEW regime total tax (slab → rebate → surcharge → cess)."""
    slab = _compute_slabs(taxable_income, 'NEW')
    tax_after_rebate, _ = _apply_rebate(slab, taxable_income, 'NEW')
    result = _apply_surcharge_and_cess(tax_after_rebate, taxable_income, 'NEW')
    return result['total_tax']


# ================= HRA EXEMPTION =================

def calculate_hra_exemption(basic, hra_received, monthly_rent, is_metro):
    """Calculate HRA exemption = MIN(HRA_RX, Rent*12 - 10%*Basic, 50/40%*Basic).
    Floored at 0 (per markdown: if rent-10%basic is negative, use 0).
    """
    basic = _num(basic)
    hra_received = _num(hra_received)
    rent_annual = _num(monthly_rent) * 12

    percent = 0.5 if is_metro else 0.4

    # Three conditions
    cond1 = hra_received
    cond2 = max(0, rent_annual - 0.10 * basic)  # Floor at 0 per markdown
    cond3 = percent * basic

    return max(0, min(cond1, cond2, cond3))


# ================= VARIANT CONSTANTS =================

# OLD REGIME VARIANTS (per FairTax_ITR_Engine_FY2025-26.csv rows 59-61)
VARIANT_B = {"lta": 65000, "sec10_14_ii": 28000, "sec10_14_i": 98000, "sec_80d": 35000}
VARIANT_C = {"lta": 95000, "sec10_14_ii": 34000, "sec10_14_i": 228000, "sec_80d": 35000}

# NEW REGIME VARIANTS (per FairTax_ITR_Engine_FY2025-26.csv rows 63-65)
# Note: NEW regime doesn't allow LTA or 80D deductions, only Sec10(14) items
NEW_VARIANT_B = {"sec10_14_i": 95000}
NEW_VARIANT_C = {"sec10_14_i": 195000, "sec10_14_ii": 45000}


# ================= MAIN CALCULATION =================

def calculate(payload):
    """Calculate tax and refund for OLD/NEW regimes + all three quote options."""

    g = lambda k, d=0: _num(payload.get(k, d))
    is_metro = str(payload.get("city_type", "")).lower() == "metro"

    # ===== INPUT VALIDATION & LOGGING =====
    # CRITICAL FIX: Log all inputs for audit trail and validation
    gross = g("gross_salary")
    basic = g("basic_salary")
    hra_received = g("hra_received")
    monthly_rent = g("monthly_rent")
    tds = g("tds_paid") or g("tds_deducted")
    home_loan_interest_raw = g("home_loan_interest")

    # Validate that values are annual (not monthly)
    if gross > 0 and gross < 240000 and basic > 0:
        # May be monthly - log warning
        print(f"[TAX_ENGINE][WARN] gross_salary={gross:,.0f} seems monthly. Proceeding but may be incorrect.")

    print(f"[TAX_ENGINE][INPUTS] gross={gross:,.0f} | basic={basic:,.0f} | hra={hra_received:,.0f} | rent={monthly_rent:,.0f} | tds={tds:,.0f} | homeloan_int={home_loan_interest_raw:,.0f}")

    # ===== INPUTS =====

    other_income = (
        g("other_income_misc")
        + g("fd_interest")
        + g("dividend")
        + g("refund_interest")
    )

    # ===== SECTION 10 EXEMPTIONS =====
    hra_exempt = calculate_hra_exemption(basic, hra_received, monthly_rent, is_metro)
    sec10_14_i = g("car_lease_allowance")
    sec10_14_ii = g("uniform_allowance")
    lta = g("lta")

    sec10_total = hra_exempt + sec10_14_i + sec10_14_ii + lta

    # ===== OTHER DEDUCTIONS =====
    home_loan_interest = min(g("home_loan_interest"), 200000)
    sec16 = g("professional_tax") + 50000  # Standard deduction 50K + PT

    # ===== SECTION 80 DEDUCTIONS =====
    sec_80c = min(
        g("pf_employee") + g("ulip_lic") + g("school_fees") + g("home_loan_principal"),
        150000
    )
    sec_80ccd_1b = min(g("nps_self"), 50000)
    # 80CCD(2) employer NPS: Use value from Form 16 without re-capping
    # (cap of 10%/14% is INPUT validation, not computation rule per spec)
    sec_80ccd_2 = g("nps_employer")  # Deductible in BOTH regimes
    sec_80ccd_2_old = sec_80ccd_2
    sec_80ccd_2_new = sec_80ccd_2

    parents_senior = str(payload.get("parents_senior", "")).lower() in ("1", "true", "yes")
    sec_80d = min(g("medical_self"), 25000) + min(
        g("medical_parents"),
        50000 if parents_senior else 25000
    )

    sec_80e = g("sec_80e")
    sec_80g = g("sec_80g")
    savings_interest = min(g("savings_interest"), 10000)
    sec_80db = min(g("sec_80db", 0), 100000)

    # Chapter VI-A deductions (80C, 80CCD(1B), 80D, 80E, 80G, 80TTA, 80DB)
    # NOTE: 80CCD(2) employer NPS is deducted separately, NOT in CH6A
    ch6a_old = sec_80c + sec_80ccd_1b + sec_80d + sec_80e + sec_80g + savings_interest + sec_80db

    # ===== TAXABLE INCOME =====
    # GTI_OLD = GROSS + OTHER - SEC10_EXEMPT - HOME_LOAN - SEC16
    gti_old = gross + other_income - sec10_total - home_loan_interest - sec16

    # TI_OLD = GTI_OLD - CH6A - EMP_NPS
    ti_old = max(0, gti_old - ch6a_old - sec_80ccd_2_old)

    # TI_NEW = GROSS + OTHER - 75000 - EMP_NPS
    std_new = 75000
    ti_new = max(0, gross + other_income - std_new - sec_80ccd_2_new)

    # ===== TAX COMPUTATION: ACTUAL REGIMES =====
    tax_old_actual = _tax_old(ti_old)
    tax_new_actual = _tax_new(ti_new)

    refund_old_actual = round(tds - tax_old_actual, 2)
    refund_new_actual = round(tds - tax_new_actual, 2)

    # ===== OPTION A: BEST OF ACTUAL =====
    option_a = max(refund_old_actual, refund_new_actual)

    # ===== THREE QUOTES: OLD REGIME =====
    # Option B: OLD regime with extra exemptions
    old_extra_b = (VARIANT_B["sec10_14_i"] + VARIANT_B["sec10_14_ii"] + VARIANT_B["lta"] + VARIANT_B["sec_80d"])
    ti_old_b = max(0, ti_old - old_extra_b)
    tax_old_b = _tax_old(ti_old_b)
    refund_old_b = round(tds - tax_old_b, 2)

    # Option C: OLD regime with more extra exemptions
    old_extra_c = (VARIANT_C["sec10_14_i"] + VARIANT_C["sec10_14_ii"] + VARIANT_C["lta"] + VARIANT_C["sec_80d"])
    ti_old_c = max(0, ti_old - old_extra_c)
    tax_old_c = _tax_old(ti_old_c)
    refund_old_c = round(tds - tax_old_c, 2)

    # ===== THREE QUOTES: NEW REGIME =====
    # Option B: NEW regime with extra exemptions per NEW_VARIANT_B
    new_extra_b = NEW_VARIANT_B["sec10_14_i"]
    ti_new_b = max(0, ti_new - new_extra_b)
    tax_new_b = _tax_new(ti_new_b)
    refund_new_b = round(tds - tax_new_b, 2)

    # Option C: NEW regime with more extra exemptions per NEW_VARIANT_C
    new_extra_c = NEW_VARIANT_C["sec10_14_i"] + NEW_VARIANT_C.get("sec10_14_ii", 0)
    ti_new_c = max(0, ti_new - new_extra_c)
    tax_new_c = _tax_new(ti_new_c)
    refund_new_c = round(tds - tax_new_c, 2)

    # ===== DETAILED BREAKDOWN (for debugging) =====
    def _tax_breakdown(taxable_income, regime):
        """Return detailed tax computation breakdown."""
        slab = _compute_slabs(taxable_income, regime)
        tax_after_rebate, rebate_amt = _apply_rebate(slab, taxable_income, regime)
        surcharge_info = _apply_surcharge_and_cess(tax_after_rebate, taxable_income, regime)
        return {
            'slab_tax': round(slab, 2),
            'rebate_amount': round(rebate_amt, 2),
            'tax_after_rebate': round(tax_after_rebate, 2),
            'surcharge_rate': surcharge_info['surcharge_rate'],
            'surcharge_amount': surcharge_info['surcharge_amount'],
            'cess_amount': surcharge_info['cess_amount'],
            'total_tax': surcharge_info['total_tax'],
        }

    breakdown_old = _tax_breakdown(ti_old, 'OLD')
    breakdown_new = _tax_breakdown(ti_new, 'NEW')

    # ===== RETURN ALL RESULTS =====
    return {
        # Inputs (summary) - CRITICAL: Include home_loan_interest for sheet persistence
        "gross_salary": round(gross, 2),
        "basic_salary": round(basic, 2),
        "hra_received": round(hra_received, 2),
        "home_loan_interest": round(home_loan_interest, 2),  # Pass through for sheet storage
        "hra_exempt_actual": round(hra_exempt, 2),
        "tds_paid": round(tds, 2),
        "other_income": round(other_income, 2),

        # Taxable incomes
        "gti_old": round(gti_old, 2),
        "taxable_old_a": round(ti_old, 2),
        "taxable_new": round(ti_new, 2),

        # Deductions (summary)
        "sec_80c": round(sec_80c, 2),
        "sec_80d": round(sec_80d, 2),
        "sec_80ccd_1b": round(sec_80ccd_1b, 2),
        "sec_80ccd_2": round(sec_80ccd_2_old, 2),
        "ch6a_total": round(ch6a_old, 2),

        # OLD REGIME ACTUAL
        "old_slab_tax_a": breakdown_old['slab_tax'],
        "old_rebate_a": breakdown_old['rebate_amount'],
        "old_tax_before_cess_a": breakdown_old['tax_after_rebate'],
        "old_surcharge_rate_a": breakdown_old['surcharge_rate'],
        "old_surcharge_amount_a": breakdown_old['surcharge_amount'],
        "old_cess_amount_a": breakdown_old['cess_amount'],
        "total_tax_old_a": breakdown_old['total_tax'],
        "refund_old_a": refund_old_actual,

        # NEW REGIME ACTUAL
        "new_slab_tax": breakdown_new['slab_tax'],
        "new_rebate": breakdown_new['rebate_amount'],
        "new_tax_before_cess": breakdown_new['tax_after_rebate'],
        "new_surcharge_rate": breakdown_new['surcharge_rate'],
        "new_surcharge_amount": breakdown_new['surcharge_amount'],
        "new_cess_amount": breakdown_new['cess_amount'],
        "total_tax_new": breakdown_new['total_tax'],
        "refund_new": refund_new_actual,

        # OPTION A (BEST)
        "option_a_refund": option_a,

        # OLD REGIME OPTION B
        "taxable_old_b": round(ti_old_b, 2),
        "total_tax_old_b": tax_old_b,
        "refund_old_b": refund_old_b,
        "variant_b_refund": refund_old_b,  # For sheet: variant_b_refund (OLD regime)

        # OLD REGIME OPTION C
        "taxable_old_c": round(ti_old_c, 2),
        "total_tax_old_c": tax_old_c,
        "refund_old_c": refund_old_c,
        "variant_c_refund": refund_old_c,  # For sheet: variant_c_refund (OLD regime)

        # NEW REGIME OPTION B
        "taxable_new_b": round(ti_new_b, 2),
        "total_tax_new_b": tax_new_b,
        "refund_new_b": refund_new_b,
        "variant_b_refund_new": refund_new_b,  # For sheet: variant_b_refund_new (NEW regime)

        # NEW REGIME OPTION C
        "taxable_new_c": round(ti_new_c, 2),
        "total_tax_new_c": tax_new_c,
        "refund_new_c": refund_new_c,
        "variant_c_refund_new": refund_new_c,  # For sheet: variant_c_refund_new (NEW regime)
    }
