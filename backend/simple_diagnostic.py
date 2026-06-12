#!/usr/bin/env python
"""
Simple diagnostic test - directly test the extraction and merge logic
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from services import document_processor
import ai_service

# Test files
test_form16 = "uploads/21531a6c-c4ce-472f-acce-b3a292fe168e/0d19ddfd_Form_16.pdf"
test_payslip = "uploads/21531a6c-c4ce-472f-acce-b3a292fe168e/a88913ef_March_Payslip.pdf"

print("=" * 80)
print("SIMPLE DIAGNOSTIC - Direct Python Test")
print("=" * 80)

# Extract both documents
form16_data = {}
payslip_data = {}

if os.path.exists(test_form16):
    print("\n[STEP 1] Extract Form 16...")
    with open(test_form16, 'rb') as f:
        result = document_processor.process_documents(f.read(), "application/pdf", doc_type="form16")
        if result.get('success'):
            form16_data = result.get('data', {})
            print(f"[EXTRACT_OUTPUT] Form16 => gross_salary={form16_data.get('gross_salary')} | basic_salary={form16_data.get('basic_salary')} | hra_received={form16_data.get('hra_received')}")

if os.path.exists(test_payslip):
    print("\n[STEP 2] Extract Payslip...")
    with open(test_payslip, 'rb') as f:
        result = document_processor.process_documents(f.read(), "application/pdf", doc_type="payslip")
        if result.get('success'):
            payslip_data = result.get('data', {})
            print(f"[EXTRACT_OUTPUT] Payslip => gross_salary={payslip_data.get('gross_salary')} | basic_salary={payslip_data.get('basic_salary')} | hra_received={payslip_data.get('hra_received')}")

# Simulate merge (as would happen in /api/extract when both docs are uploaded)
print("\n[STEP 3] Merge (simulating /api/extract merge)...")
# In /api/extract, both documents are extracted and merged
# The code merges them: existing_rec from sheet + new extractions
# Let's simulate: sheet gets Form16, then Payslip gets merged in
merged_from_extract = form16_data.copy()
if payslip_data:
    merged_from_extract.update(payslip_data)

print(f"[BEFORE_SAVE] Raw merge in /api/extract => gross_salary={merged_from_extract.get('gross_salary')} | basic_salary={merged_from_extract.get('basic_salary')} | hra_received={merged_from_extract.get('hra_received')}")

# Apply the fix: validate_form16_payslip_consistency with separate extraction scenario
print("\n[STEP 3B] Applying form16_payslip_consistency fix...")
# Simulate: form16_data was already in merged (from previous extraction), now payslip is being merged
merged_with_existing_form16 = form16_data.copy()  # Simulate previous extraction saved to sheet
merged_with_existing_form16['_doc_type'] = 'form16'  # Mark existing as form16

payslip_with_doctype = payslip_data.copy()
payslip_with_doctype['_doc_type'] = 'payslip'  # Mark as payslip
payslip_extractions = [payslip_with_doctype]  # Only payslip in this extraction

merged_with_existing_form16.update(payslip_data)  # Payslip merges in (overrides form16!)

# Now call the fix function
merged_from_extract, _ = ai_service.validate_form16_payslip_consistency(
    merged_with_existing_form16,
    payslip_extractions
)

print(f"[BEFORE_SAVE] After form16_payslip_consistency FIX => gross_salary={merged_from_extract.get('gross_salary')} | basic_salary={merged_from_extract.get('basic_salary')} | hra_received={merged_from_extract.get('hra_received')}")
print("  -> This would be saved to Google Sheets")

# Simulate form submission (as would happen in /api/submit)
print("\n[STEP 4] Form submission (simulating /api/submit)...")
# When user submits form, they might send values
form_submission = {
    "gross_salary": 233937,  # User submits monthly value or old value?
    "basic_salary": 99133,
    "hra_received": 49567
}
print(f"[SUBMIT_INPUT] Form data => gross_salary={form_submission.get('gross_salary')} | basic_salary={form_submission.get('basic_salary')} | hra_received={form_submission.get('hra_received')}")

# Simulate merge in /api/submit: existing_rec (from sheet) + form submission
print("\n[STEP 5] Merge in /api/submit...")
existing_rec = merged_from_extract.copy()  # Simulate sheet data
merged_data = {**existing_rec, **form_submission}  # Form overrides sheet!
print(f"[AFTER_MERGE] After form override => gross_salary={merged_data.get('gross_salary')} | basic_salary={merged_data.get('basic_salary')} | hra_received={merged_data.get('hra_received')}")

# Analysis
print("\n" + "=" * 80)
print("ANALYSIS:")
print("=" * 80)
print(f"\n1. Form16 extracted: {form16_data.get('gross_salary')} (expected: 3,141,557 annual)")
print(f"2. Payslip extracted: {payslip_data.get('gross_salary')} (expected: 233,937 monthly)")
print(f"3. After /api/extract merge: {merged_from_extract.get('gross_salary')} (should be annual)")
print(f"4. Form submission: {form_submission.get('gross_salary')} (monthly)")
print(f"5. Final after /api/submit merge: {merged_data.get('gross_salary')} (WRONG if monthly!)")

if merged_data.get('gross_salary') == form_submission.get('gross_salary'):
    print("\n[CONFIRMED] BUG #1: Form values override sheet values!")
    print("  File: app.py line 1139")
    print("  Code: merged_data = {**existing_rec, **data}")
    print("  Problem: Monthly form values override annual sheet values")
else:
    print(f"\n[OTHER] Final value is {merged_data.get('gross_salary')}, not same as form input")

print("=" * 80)
