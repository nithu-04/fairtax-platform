#!/usr/bin/env python
"""
Diagnostic test script to extract documents and capture diagnostic logs
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from services import document_processor
from config import Config

# Test files
test_form16 = "uploads/21531a6c-c4ce-472f-acce-b3a292fe168e/0d19ddfd_Form_16.pdf"
test_payslip = "uploads/21531a6c-c4ce-472f-acce-b3a292fe168e/a88913ef_March_Payslip.pdf"

print("=" * 80)
print("DIAGNOSTIC TEST - Monthly vs Annual Values Bug")
print("=" * 80)

# Extract Form 16
print("\n[TEST] Extracting Form 16...")
print("-" * 80)
if os.path.exists(test_form16):
    with open(test_form16, 'rb') as f:
        form16_bytes = f.read()
    result = document_processor.process_documents(form16_bytes, "application/pdf", doc_type="form16")
    print(f"\nForm 16 Extraction Result:")
    if result.get('success'):
        form16_data = result.get('data', {})
        print(f"  gross_salary: {form16_data.get('gross_salary')}")
        print(f"  basic_salary: {form16_data.get('basic_salary')}")
        print(f"  hra_received: {form16_data.get('hra_received')}")
    else:
        print(f"  ERROR: {result.get('error')}")
else:
    print(f"  ERROR: File not found - {test_form16}")

# Extract Payslip
print("\n[TEST] Extracting Payslip...")
print("-" * 80)
if os.path.exists(test_payslip):
    with open(test_payslip, 'rb') as f:
        payslip_bytes = f.read()
    result = document_processor.process_documents(payslip_bytes, "application/pdf", doc_type="payslip")
    print(f"\nPayslip Extraction Result:")
    if result.get('success'):
        payslip_data = result.get('data', {})
        print(f"  gross_salary: {payslip_data.get('gross_salary')}")
        print(f"  basic_salary: {payslip_data.get('basic_salary')}")
        print(f"  hra_received: {payslip_data.get('hra_received')}")
    else:
        print(f"  ERROR: {result.get('error')}")
else:
    print(f"  ERROR: File not found - {test_payslip}")

print("\n" + "=" * 80)
print("TEST COMPLETE - Check console output above for [DIAGNOSTIC] logs")
print("=" * 80)
