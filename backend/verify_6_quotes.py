"""
Verification script for 6-quote implementation against FairTax_ITR_Engine_FY2025-26.csv

Tests all three sample profiles (Anurag/Person B, Gnana/Person C, Vinoth/Person D)
and verifies that calculated refund values match the specification exactly.
"""

import sys
import json
from tax_engine import calculate

# Sample profiles from FairTax_ITR_Engine_FY2025-26.csv (rows 5-20)
PROFILES = {
    "Anurag (Person B)": {
        "gross_salary": 1811537.00,
        "basic_salary": 394800.00,
        "hra_received": 96000.00,
        "monthly_rent": 35000.00,
        "city_type": "metro",
        "other_income_misc": 0.00,
        "fd_interest": 0.00,
        "dividend": 0.00,
        "refund_interest": 0.00,
        "tds_paid": 141704.00,
        "professional_tax": 2500.00,
        "home_loan_interest": 183545.00,
        "pf_employee": 50000.00,      # 80C: PF employee contribution
        "home_loan_principal": 50000.00,  # 80C: home loan principal
        "ulip_lic": 25000.00,          # 80C: ULIP/LIC
        "school_fees": 0.00,
        "medical_self": 0.00,
        "medical_parents": 0.00,
        "parents_senior": False,
        "nps_self": 30000.00,          # 80CCD(1B): voluntary NPS
        "nps_employer": 55272.00,
        "car_lease_allowance": 0.00,
        "uniform_allowance": 0.00,
        "lta": 0.00,
        "sec_80e": 0.00,
        "sec_80g": 0.00,
        "savings_interest": 0.00,
        "sec_80db": 0.00,
    },
    "Gnana (Person C)": {
        "gross_salary": 9010540.00,
        "basic_salary": 2379192.00,
        "hra_received": 96000.00,
        "monthly_rent": 8000.00,
        "city_type": "metro",
        "other_income_misc": 0.00,
        "fd_interest": 54872.00,
        "dividend": 0.00,
        "refund_interest": 0.00,
        "tds_paid": 2598058.00,
        "professional_tax": 25000.00,
        "home_loan_interest": 0.00,
        "pf_employee": 80000.00,       # 80C: PF employee contribution
        "home_loan_principal": 0.00,
        "ulip_lic": 0.00,
        "school_fees": 0.00,
        "medical_self": 25000.00,      # 80D: medical self
        "medical_parents": 25000.00,   # 80D: medical parents
        "parents_senior": False,
        "nps_self": 20000.00,          # 80CCD(1B): voluntary NPS
        "nps_employer": 328968.00,
        "car_lease_allowance": 0.00,
        "uniform_allowance": 0.00,
        "lta": 0.00,
        "sec_80e": 0.00,
        "sec_80g": 0.00,
        "savings_interest": 0.00,
        "sec_80db": 0.00,
    },
    "Vinoth (Person D)": {
        "gross_salary": 1716776.00,
        "basic_salary": 0.00,
        "hra_received": 0.00,
        "monthly_rent": 0.00,
        "city_type": "metro",
        "other_income_misc": 0.00,
        "fd_interest": 0.00,
        "dividend": 0.00,
        "refund_interest": 0.00,
        "tds_paid": 83550.00,
        "professional_tax": 0.00,
        "home_loan_interest": 0.00,
        "pf_employee": 0.00,
        "home_loan_principal": 0.00,
        "ulip_lic": 0.00,
        "school_fees": 0.00,
        "medical_self": 0.00,
        "medical_parents": 0.00,
        "parents_senior": False,
        "nps_self": 0.00,
        "nps_employer": 0.00,
        "car_lease_allowance": 0.00,
        "uniform_allowance": 0.00,
        "lta": 0.00,
        "sec_80e": 0.00,
        "sec_80g": 0.00,
        "savings_interest": 0.00,
        "sec_80db": 0.00,
    },
}

# Expected values from FairTax_ITR_Engine_FY2025-26.csv
# Row 36/45: Actual OLD/NEW refunds
# Row 51/54: OLD regime Options B/C (rows 51, 54)
# Row 73/76: NEW regime Options B/C (rows 73, 76)
EXPECTED = {
    "Anurag (Person B)": {
        "refund_old_a": -59293.00,     # Row 36: OLD regime actual
        "refund_new": 1.00,             # Row 45: NEW regime actual
        "refund_old_b": 11219.00,      # Row 51: OLD Option B
        "refund_old_c": 50242.00,      # Row 54: OLD Option C
        "refund_new_b": 19047.00,      # Row 73: NEW Option B
        "refund_new_c": 41667.00,      # Row 76: NEW Option C
    },
    "Gnana (Person C)": {
        "refund_old_a": -108570.00,    # Row 36: OLD regime actual
        "refund_new": 105930.00,       # Row 45: NEW regime actual
        "refund_old_b": -31006.00,     # Row 51: OLD Option B
        "refund_old_c": 25965.00,      # Row 54: OLD Option C
        "refund_new_b": 138534.00,     # Row 73: NEW Option B
        "refund_new_c": 188298.00,     # Row 76: NEW Option C
    },
    "Vinoth (Person D)": {
        "refund_old_a": -241484.00,    # Row 36: OLD regime actual
        "refund_new": -49939.00,       # Row 45: NEW regime actual
        "refund_old_b": -170972.00,    # Row 51: OLD Option B
        "refund_old_c": -119180.00,    # Row 54: OLD Option C
        "refund_new_b": -32947.00,     # Row 73: NEW Option B
        "refund_new_c": -10327.00,     # Row 76: NEW Option C
    },
}

def test_profile(name, payload, expected):
    """Test a single profile and return pass/fail."""
    print(f"\n{'='*70}")
    print(f"Testing: {name}")
    print(f"{'='*70}")

    result = calculate(payload)

    tests = [
        ("OLD Regime Actual (Refund)", "refund_old_a", expected.get("refund_old_a")),
        ("NEW Regime Actual (Refund)", "refund_new", expected.get("refund_new")),
        ("OLD Option B (Refund)", "refund_old_b", expected.get("refund_old_b")),
        ("OLD Option C (Refund)", "refund_old_c", expected.get("refund_old_c")),
        ("NEW Option B (Refund)", "refund_new_b", expected.get("refund_new_b")),
        ("NEW Option C (Refund)", "refund_new_c", expected.get("refund_new_c")),
    ]

    all_pass = True
    for label, key, expected_val in tests:
        actual_val = result.get(key, None)

        # Check if values match (allow 1 rupee tolerance for rounding)
        match = False
        if actual_val is not None:
            diff = abs(float(actual_val) - float(expected_val))
            match = diff <= 1.0

        status = "[PASS]" if match else "[FAIL]"
        all_pass = all_pass and match

        if match:
            print(f"{status} | {label:30s} | {actual_val:>12,.0f} | {expected_val:>12,.0f}")
        else:
            diff = float(actual_val) - float(expected_val) if actual_val else 0
            print(f"{status} | {label:30s} | {actual_val:>12,.0f} | {expected_val:>12,.0f} | Diff {diff:+,.0f}")

    return all_pass

def main():
    print("\n" + "="*70)
    print("FAIRTAS 6-QUOTE IMPLEMENTATION VERIFICATION")
    print("Testing against FairTax_ITR_Engine_FY2025-26.csv specification")
    print("="*70)

    all_tests_pass = True

    for name in ["Anurag (Person B)", "Gnana (Person C)", "Vinoth (Person D)"]:
        payload = PROFILES[name]
        expected = EXPECTED[name]
        passed = test_profile(name, payload, expected)
        all_tests_pass = all_tests_pass and passed

    # Summary
    print(f"\n{'='*70}")
    if all_tests_pass:
        print("[PASS] ALL TESTS PASSED - Implementation matches specification!")
    else:
        print("[FAIL] SOME TESTS FAILED - Review differences above")
    print(f"{'='*70}\n")

    return 0 if all_tests_pass else 1

if __name__ == "__main__":
    sys.exit(main())
