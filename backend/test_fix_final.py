#!/usr/bin/env python
"""
Final diagnostic test - simulates the actual /api/extract flow with the fix
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from services import document_processor
import ai_service

test_form16 = "uploads/21531a6c-c4ce-472f-acce-b3a292fe168e/0d19ddfd_Form_16.pdf"
test_payslip = "uploads/21531a6c-c4ce-472f-acce-b3a292fe168e/a88913ef_March_Payslip.pdf"

print("=" * 80)
print("FINAL DIAGNOSTIC TEST - With Fix Applied")
print("=" * 80)

# Step 1: Extract Form16 (first API call)
print("\n[STEP 1] First API call: Extract Form16...")
print("-" * 80)
form16_result = document_processor.process_documents(
    open(test_form16, 'rb').read(),
    "application/pdf",
    doc_type="form16"
)
form16_data = form16_result.get('data', {})
print(f"Form16 extracted: gross_salary={form16_data.get('gross_salary')}")

# Simulate: saved to sheet
sheet_row = form16_data.copy()
print(f"Sheet saved: gross_salary={sheet_row.get('gross_salary')}")

# Step 2: Extract Payslip (second API call - SEPARATE REQUEST)
print("\n[STEP 2] Second API call: Extract Payslip (SEPARATE from Form16)...")
print("-" * 80)
payslip_result = document_processor.process_documents(
    open(test_payslip, 'rb').read(),
    "application/pdf",
    doc_type="payslip"
)
payslip_data = payslip_result.get('data', {})
print(f"Payslip extracted: gross_salary={payslip_data.get('gross_salary')}")

# Simulate /api/extract merge_extractions() with ONLY payslip
payslip_with_doctype = payslip_data.copy()
payslip_with_doctype['_doc_type'] = 'payslip'
extractions = [payslip_with_doctype]

merged = ai_service.merge_extractions(extractions)
print(f"After merge_extractions: gross_salary={merged.get('gross_salary')}")

# Apply the FIX: Preserve Form16 values from sheet
print("\n[FIX] Applying preservation logic from /api/extract...")
sheet_form16_fields = {'gross_salary', 'basic_salary', 'hra_received', 'pf_employee'}
for field in sheet_form16_fields:
    sheet_val = sheet_row.get(field, 0)
    merged_val = merged.get(field, 0)

    try:
        sheet_num = float(sheet_val) if sheet_val else 0
        merged_num = float(merged_val) if merged_val else 0

        if sheet_num > 0 and merged_num > 0:
            ratio = sheet_num / max(merged_num, 1)
            if ratio > 10:
                merged[field] = sheet_num
                print(f"[FIX] Preserved {field}: kept {sheet_num} (sheet/annual) over {merged_num} (payslip/monthly)")
    except:
        pass

print(f"\n[RESULT] After fix: gross_salary={merged.get('gross_salary')}")

# Summary
print("\n" + "=" * 80)
print("SUMMARY:")
print("=" * 80)
print(f"1. Form16 extracted (1st call): gross_salary = {form16_data.get('gross_salary')} (ANNUAL)")
print(f"2. Saved to sheet: gross_salary = {sheet_row.get('gross_salary')} (ANNUAL)")
print(f"3. Payslip extracted (2nd call): gross_salary = {payslip_data.get('gross_salary')} (MONTHLY)")
print(f"4. After merge_extractions: gross_salary = {merged.get('gross_salary')} (would be WRONG)")
print(f"5. **WITH FIX**: gross_salary = {merged.get('gross_salary')} (PRESERVED ANNUAL!)")

if merged.get('gross_salary') == form16_data.get('gross_salary'):
    print("\n[SUCCESS] Fix works! Annual value preserved!")
else:
    print(f"\n[FAILED] Fix didn't work. Got {merged.get('gross_salary')}, expected {form16_data.get('gross_salary')}")

print("=" * 80)
