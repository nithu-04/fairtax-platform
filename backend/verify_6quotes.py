#!/usr/bin/env python3
import sys
sys.path.insert(0, r'C:\Users\user\Desktop\fairtax-fresh\backend')

import tax_engine

# Person B (Anurag) with COMPLETE deduction data
anurag = {
    'gross_salary': 1811537.00,
    'basic_salary': 394800.00,
    'hra_received': 96000.00,
    'monthly_rent': 35000.00,
    'city_type': 'metro',
    'home_loan_interest': 183545.00,
    'nps_employer': 55272.00,
    'tds_paid': 141704.00,
    'pf_employee': 0,
    'home_loan_principal': 155000.00,
}

result = tax_engine.calculate(anurag)

print('\n' + '='*80)
print('PERSON B (ANURAG) - ALL 6 QUOTES')
print('='*80)

print('\nCALCULATED 6 QUOTES:')
print('OLD REGIME:')
print('  Option A Refund: ' + str(round(result.get('refund_old_a', 0), 2)))
print('  Option B Refund: ' + str(round(result.get('refund_old_b', 0), 2)))
print('  Option C Refund: ' + str(round(result.get('refund_old_c', 0), 2)))

print('NEW REGIME:')
print('  Option A Refund: ' + str(round(result.get('refund_new', 0), 2)))
print('  Option B Refund: ' + str(round(result.get('refund_new_b', 0), 2)))
print('  Option C Refund: ' + str(round(result.get('refund_new_c', 0), 2)))

print('\nEXPECTED FROM SCREENSHOT:')
print('OLD REGIME:')
print('  Option A: -59293.00')
print('  Option B: 11219.00')
print('  Option C: 50242.00')
print('NEW REGIME:')
print('  Option A: 1.00')
print('  Option B: 19047.00')
print('  Option C: 41667.00')
