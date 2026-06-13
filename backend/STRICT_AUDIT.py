#!/usr/bin/env python3
"""STRICT AUDIT: Match tax_engine output to screenshot values exactly"""
import sys
sys.path.insert(0, r'C:\Users\user\Desktop\fairtax-fresh\backend')

import tax_engine

print("\n" + "="*100)
print("STRICT AUDIT: PERSON B (ANURAG)")
print("="*100)

# EXACT INPUT FROM SCREENSHOT
anurag_input = {
    'gross_salary': 1811537.00,
    'basic_salary': 394800.00,
    'hra_received': 96000.00,
    'monthly_rent': 35000.00,
    'city_type': 'metro',
    'home_loan_interest': 183545.00,
    'professional_tax': 2500.00,  # Section 16 deduction = 50,000 + 2,500 PT
    'tds_paid': 141704.00,
    'nps_employer': 55272.00,  # 80CCD(2) employer NPS
    # Chapter VI-A total = 155,000
    # Breaking down: 80C max 150,000 + 80D = 155,000
    'pf_employee': 85000.00,
    'home_loan_principal': 35000.00,  # Total 80C = 120,000
    'ulip_lic': 0,
    'school_fees': 0,
    'medical_self': 25000.00,
    'medical_parents': 10000.00,  # 80D = 35,000
    'parents_senior': False,
    'nps_self': 0,
    'car_lease_allowance': 0,
    'uniform_allowance': 0,
    'lta': 0,
    'other_income_misc': 0,
    'fd_interest': 0,
    'dividend': 0,
    'refund_interest': 0,
    'savings_interest': 0,
    'sec_80e': 0,
    'sec_80g': 0,
    'sec_80db': 0,
}

result = tax_engine.calculate(anurag_input)

print("\n[SECTION 1] INPUTS VALIDATION:")
print(f"  Gross Salary:          {result.get('gross_salary', 0):>15,.2f}  vs  1,811,537.00")
print(f"  Basic Salary:          {result.get('basic_salary', 0):>15,.2f}  vs      394,800.00")
print(f"  HRA Received:          {result.get('hra_received', 0):>15,.2f}  vs       96,000.00")
print(f"  HRA Exempt:            {result.get('hra_exempt_actual', 0):>15,.2f}  vs       96,000.00")

print("\n[SECTION 2] TAXABLE INCOME - OLD REGIME:")
gti_expected = 1479492.00
ti_old_expected = 1269220.00
print(f"  GTI (Old):             {result.get('gti_old', 0):>15,.2f}  vs    {gti_expected:>15,.2f}")
if abs(result.get('gti_old', 0) - gti_expected) < 1:
    print(f"     [MATCH] OK")
else:
    print(f"     [FAIL] DIFF = {result.get('gti_old', 0) - gti_expected:,.2f}")

print(f"  Taxable Income (Old):  {result.get('taxable_old_a', 0):>15,.2f}  vs    {ti_old_expected:>15,.2f}")
if abs(result.get('taxable_old_a', 0) - ti_old_expected) < 1:
    print(f"     [MATCH] OK")
else:
    print(f"     [FAIL] DIFF = {result.get('taxable_old_a', 0) - ti_old_expected:,.2f}")

print("\n[SECTION 3] TAXABLE INCOME - NEW REGIME:")
ti_new_expected = 1681265.00
print(f"  Taxable Income (New):  {result.get('taxable_new', 0):>15,.2f}  vs    {ti_new_expected:>15,.2f}")
if abs(result.get('taxable_new', 0) - ti_new_expected) < 1:
    print(f"     [MATCH] OK")
else:
    print(f"     [FAIL] DIFF = {result.get('taxable_new', 0) - ti_new_expected:,.2f}")

print("\n[SECTION 4] OLD REGIME TAX & REFUND:")
print(f"  Tax on slabs:          {result.get('old_tax_raw_a', 0):>15,.2f}")
print(f"  Total Tax (Old A):     {result.get('total_tax_old_a', 0):>15,.2f}  vs      200,997.00")
print(f"  Refund (Old A):        {result.get('refund_old_a', 0):>15,.2f}  vs      -59,293.00")
print(f"     Expected: -59,293.00 (liability)")

print("\n[SECTION 5] NEW REGIME TAX & REFUND:")
print(f"  Total Tax (New A):     {result.get('total_tax_new', 0):>15,.2f}  vs      141,703.00")
print(f"  Refund (New A):        {result.get('refund_new', 0):>15,.2f}  vs            1.00")

print("\n[SECTION 6] ALL 6 QUOTES:")
print("  OLD REGIME:")
print(f"    Option A Refund:     {result.get('refund_old_a', 0):>15,.2f}  vs      -59,293.00")
print(f"    Option B Refund:     {result.get('refund_old_b', 0):>15,.2f}  vs       11,219.00")
print(f"    Option C Refund:     {result.get('refund_old_c', 0):>15,.2f}  vs       50,242.00")

print("  NEW REGIME:")
print(f"    Option A Refund:     {result.get('refund_new', 0):>15,.2f}  vs            1.00")
print(f"    Option B Refund:     {result.get('refund_new_b', 0):>15,.2f}  vs       19,047.00")
print(f"    Option C Refund:     {result.get('refund_new_c', 0):>15,.2f}  vs       41,667.00")

print("\n[VERIFICATION SUMMARY]:")
matches = 0
total = 8

if abs(result.get('taxable_old_a', 0) - 1269220.00) < 1:
    print("  [OK] OLD Taxable matches perfectly")
    matches += 1
else:
    print("  [FAIL] OLD Taxable MISMATCH")

if abs(result.get('taxable_new', 0) - 1681265.00) < 1:
    print("  [OK] NEW Taxable matches perfectly")
    matches += 1
else:
    print("  [FAIL] NEW Taxable MISMATCH")

refunds_old = [
    (result.get('refund_old_a', 0), -59293.00, "OLD A"),
    (result.get('refund_old_b', 0), 11219.00, "OLD B"),
    (result.get('refund_old_c', 0), 50242.00, "OLD C"),
]

refunds_new = [
    (result.get('refund_new', 0), 1.00, "NEW A"),
    (result.get('refund_new_b', 0), 19047.00, "NEW B"),
    (result.get('refund_new_c', 0), 41667.00, "NEW C"),
]

all_refunds = refunds_old + refunds_new
for calc, expected, label in all_refunds:
    if abs(calc - expected) < 1:
        print(f"  [OK] {label} Refund matches (within 1 rupee)")
        matches += 1
    else:
        print(f"  [FAIL] {label} Refund MISMATCH (diff = {calc - expected:,.2f})")

print(f"\n  TOTAL: {matches}/{total} checks passed")

if matches == total:
    print("\n  === AUDIT PASSED - ALL 6 QUOTES MATCH SCREENSHOT ===")
else:
    print(f"\n  === AUDIT FAILED - {total - matches} mismatches found ===")

print("\n" + "="*100 + "\n")
