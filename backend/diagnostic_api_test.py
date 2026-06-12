#!/usr/bin/env python
"""
Diagnostic API test - calls full extraction and submission flow
"""
import requests
import json
import time
from pathlib import Path

BASE_URL = "http://localhost:5000"
SUBMISSION_ID = "DIAG_TEST_2026-06-12"

# Test files
test_form16 = "uploads/21531a6c-c4ce-472f-acce-b3a292fe168e/0d19ddfd_Form_16.pdf"
test_payslip = "uploads/21531a6c-c4ce-472f-acce-b3a292fe168e/a88913ef_March_Payslip.pdf"

print("=" * 80)
print("COMPREHENSIVE DIAGNOSTIC TEST - Full API Flow")
print("=" * 80)
print(f"Submission ID: {SUBMISSION_ID}\n")

# Test 1: Extract Form 16
print("[TEST-1] Extracting Form 16...")
print("-" * 80)
if Path(test_form16).exists():
    with open(test_form16, 'rb') as f:
        files = {'documents': (test_form16, f, 'application/pdf')}
        data = {'submission_id': SUBMISSION_ID, 'doc_type': 'form16'}
        try:
            response = requests.post(f"{BASE_URL}/api/extract", files=files, data=data, timeout=30)
            print(f"Status: {response.status_code}")
            result = response.json()
            if result.get('success'):
                extracted = result.get('data', {})
                print(f"  gross_salary: {extracted.get('gross_salary')}")
                print(f"  basic_salary: {extracted.get('basic_salary')}")
                print(f"  hra_received: {extracted.get('hra_received')}")
                print("[OK] Form 16 extraction successful")
            else:
                print(f"[ERROR] Error: {result.get('error')}")
        except Exception as e:
            print(f"[ERROR] Request failed: {e}")
else:
    print(f"[ERROR] File not found: {test_form16}")

time.sleep(1)

# Test 2: Extract Payslip
print("\n[TEST-2] Extracting Payslip...")
print("-" * 80)
if Path(test_payslip).exists():
    with open(test_payslip, 'rb') as f:
        files = {'documents': (test_payslip, f, 'application/pdf')}
        data = {'submission_id': SUBMISSION_ID, 'doc_type': 'payslip'}
        try:
            response = requests.post(f"{BASE_URL}/api/extract", files=files, data=data, timeout=30)
            print(f"Status: {response.status_code}")
            result = response.json()
            if result.get('success'):
                extracted = result.get('data', {})
                print(f"  gross_salary: {extracted.get('gross_salary')}")
                print(f"  basic_salary: {extracted.get('basic_salary')}")
                print(f"  hra_received: {extracted.get('hra_received')}")
                print("[OK] Payslip extraction successful")
            else:
                print(f"[ERROR] Error: {result.get('error')}")
        except Exception as e:
            print(f"[ERROR] Request failed: {e}")
else:
    print(f"[ERROR] File not found: {test_payslip}")

time.sleep(1)

# Test 3: Submit form with salary values
print("\n[TEST-3] Submitting form with salary data...")
print("-" * 80)
submission_data = {
    "submission_id": SUBMISSION_ID,
    "name": "Test User",
    "phone": "9999999999",
    "pan": "AADCC1026E",
    "gross_salary": 233937,
    "basic_salary": 99133,
    "hra_received": 49567
}
try:
    response = requests.post(
        f"{BASE_URL}/api/submit",
        json=submission_data,
        timeout=30
    )
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Success: {result.get('success')}")
    if result.get('success'):
        print("[OK] Submission successful")
    else:
        print(f"[ERROR] Error: {result.get('error')}")
except Exception as e:
    print(f"[ERROR] Request failed: {e}")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("Check Flask server logs for [DIAGNOSTIC] output:")
print("  - [EXTRACT_OUTPUT] after document extraction")
print("  - [BEFORE_SAVE] before saving to sheets")
print("  - [SUBMIT_INPUT] form submission input")
print("  - [AFTER_MERGE] after merging sheet and form data")
print("=" * 80)
