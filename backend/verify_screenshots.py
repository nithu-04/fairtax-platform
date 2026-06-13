#!/usr/bin/env python3
"""
Verification script: Run FairTax tax engine with screenshot data
Compare output against the screenshot calculations
"""

import sys
sys.path.insert(0, 'C:\\Users\\user\\Desktop\\fairtax-fresh\\backend')

import tax_engine
import tax_config

# ============= TEST DATA FROM SCREENSHOTS =============

# Person B (Anurag)
anurag_input = {
    'gross_salary': 1811537.00,
    'basic_salary': 394800.00,
    'hra_received': 96000.00,
    'monthly_rent': 35000.00,
    'city_type': 'metro',
    'home_loan_interest': 183545.00,
    'pf_employee': 0,  # Not explicitly shown
    'home_loan_principal': 0,  # Not shown
    'ulip_lic': 0,  # Not shown
    'school_fees': 0,  # Not shown
    'nps_self': 0,  # Not shown
    'nps_employer': 55272.00,  # 80CCD(2)
    'medical_self': 0,  # Not shown
    'medical_parents': 0,  # Not shown
    'parents_senior': False,
    'professional_tax': 0,
    'tds_paid': 141704.00,
    'car_lease_allowance': 0,
    'uniform_allowance': 0,
    'lta': 0,
    'other_income': 0,
    'fd_interest': 0,
    'dividend': 0,
    'refund_interest': 0,
    'savings_interest': 0,
    'sec_80e': 0,
    'sec_80g': 0,
    'sec_80db': 0,
}

# Person C (Gnana)
gnana_input = {
    'gross_salary': 9010540.00,
    'basic_salary': 2379192.00,
    'hra_received': 96000.00,
    'monthly_rent': 8000.00,
    'city_type': 'metro',
    'home_loan_interest': 0,
    'pf_employee': 0,
    'home_loan_principal': 0,
    'ulip_lic': 0,
    'school_fees': 0,
    'nps_self': 0,
    'nps_employer': 328968.00,  # 80CCD(2)
    'medical_self': 0,
    'medical_parents': 0,
    'parents_senior': False,
    'professional_tax': 0,
    'tds_paid': 2598058.00,
    'car_lease_allowance': 0,
    'uniform_allowance': 0,
    'lta': 0,
    'other_income': 0,
    'fd_interest': 0,
    'dividend': 0,
    'refund_interest': 0,
    'savings_interest': 0,
    'sec_80e': 0,
    'sec_80g': 0,
    'sec_80db': 0,
}

# Person D (Vinoth)
vinoth_input = {
    'gross_salary': 1716776.00,
    'basic_salary': 0.00,  # Not shown, assume 0
    'hra_received': 0.00,
    'monthly_rent': 0.00,
    'city_type': 'non-metro',
    'home_loan_interest': 0,
    'pf_employee': 0,
    'home_loan_principal': 0,
    'ulip_lic': 0,
    'school_fees': 0,
    'nps_self': 0,
    'nps_employer': 0,
    'medical_self': 0,
    'medical_parents': 0,
    'parents_senior': False,
    'professional_tax': 0,
    'tds_paid': 83550.00,
    'car_lease_allowance': 0,
    'uniform_allowance': 0,
    'lta': 0,
    'other_income': 0,
    'fd_interest': 0,
    'dividend': 0,
    'refund_interest': 0,
    'savings_interest': 0,
    'sec_80e': 0,
    'sec_80g': 0,
    'sec_80db': 0,
}

# ============= EXPECTED VALUES FROM SCREENSHOTS =============

anurag_expected = {
    'OLD': {
        'Option_A': {
            'taxable': 1269220.00,
            'tax_before_cess': 193266.00,
            'refund': -59293.00,
        },
    },
    'NEW': {
        'Option_A': {
            'taxable': 1681265.00,
            'tax': 136253.00,
            'refund': 1.00,
        },
    },
}

gnana_expected = {
    'OLD': {
        'Option_A': {
            'taxable': 8511444.00,
            'tax_before_cess': 2365933.20,
            'refund': -1085570.00,
        },
    },
    'NEW': {
        'Option_A': {
            'taxable': 8661444.00,
            'tax': 2178433.20,
            'refund': 105930.00,
        },
    },
}

vinoth_expected = {
    'OLD': {
        'Option_A': {
            'taxable': 1666776.00,
            'tax_before_cess': 312532.80,
            'refund': -241484.00,
        },
    },
    'NEW': {
        'Option_A': {
            'taxable': 1641776.00,
            'tax': 128355.20,
            'refund': -49939.00,
        },
    },
}

# ============= VERIFICATION FUNCTION =============

def verify(name, input_data, expected):
    print(f"\n{'='*80}")
    print(f"VERIFYING: {name}")
    print(f"{'='*80}")

    result = tax_engine.calculate(input_data)

    # Check OLD Regime Option A
    print(f"\nOLD REGIME - Option A:")
    print(f"  Input Gross: {input_data.get('gross_salary', 0)}")
    print(f"  Calculated Taxable: {result.get('taxable_old_a', 0)}")
    print(f"  Expected Taxable:   {expected['OLD']['Option_A'].get('taxable', 0)}")

    if abs(result.get('taxable_old_a', 0) - expected['OLD']['Option_A'].get('taxable', 0)) < 1:
        print(f"  [OK] TAXABLE MATCHES")
    else:
        diff = result.get('taxable_old_a', 0) - expected['OLD']['Option_A'].get('taxable', 0)
        print(f"  [FAIL] TAXABLE MISMATCH: diff={diff}")

    print(f"  Calculated Tax: {result.get('total_tax_old_a', 0)}")
    print(f"  Expected Tax:   {expected['OLD']['Option_A'].get('tax_before_cess', 0)}")

    print(f"  Calculated Refund: {result.get('refund_old_a', 0)}")
    print(f"  Expected Refund:   {expected['OLD']['Option_A'].get('refund', 0)}")

    if abs(result.get('refund_old_a', 0) - expected['OLD']['Option_A'].get('refund', 0)) < 1:
        print(f"  [OK] REFUND MATCHES")
    else:
        diff = result.get('refund_old_a', 0) - expected['OLD']['Option_A'].get('refund', 0)
        print(f"  [FAIL] REFUND MISMATCH: diff={diff}")

    # Check NEW Regime
    print(f"\nNEW REGIME - Option A:")
    print(f"  Calculated Taxable: {result.get('taxable_new', 0)}")
    print(f"  Expected Taxable:   {expected['NEW']['Option_A'].get('taxable', 0)}")

    if abs(result.get('taxable_new', 0) - expected['NEW']['Option_A'].get('taxable', 0)) < 1:
        print(f"  [OK] TAXABLE MATCHES")
    else:
        diff = result.get('taxable_new', 0) - expected['NEW']['Option_A'].get('taxable', 0)
        print(f"  [FAIL] TAXABLE MISMATCH: diff={diff}")

    print(f"  Calculated Tax: {result.get('total_tax_new', 0)}")
    print(f"  Expected Tax:   {expected['NEW']['Option_A'].get('tax', 0)}")

    print(f"  Calculated Refund: {result.get('refund_new', 0)}")
    print(f"  Expected Refund:   {expected['NEW']['Option_A'].get('refund', 0)}")

    if abs(result.get('refund_new', 0) - expected['NEW']['Option_A'].get('refund', 0)) < 1:
        print(f"  [OK] REFUND MATCHES")
    else:
        diff = result.get('refund_new', 0) - expected['NEW']['Option_A'].get('refund', 0)
        print(f"  [FAIL] REFUND MISMATCH: diff={diff}")

# ============= RUN VERIFICATION =============

if __name__ == '__main__':
    verify('Person B (Anurag)', anurag_input, anurag_expected)
    verify('Person C (Gnana)', gnana_input, gnana_expected)
    verify('Person D (Vinoth)', vinoth_input, vinoth_expected)

    print(f"\n{'='*80}")
    print("VERIFICATION COMPLETE")
    print(f"{'='*80}\n")
