"""Direct test of extraction pipeline in new_fixes"""
import sys
import os
import time

# Load environment
from dotenv import load_dotenv
load_dotenv()

print("=" * 60)
print("END-TO-END EXTRACTION TEST - new_fixes folder")
print("=" * 60)

# Test 1: Check environment
print("\n[TEST 1] Environment variables...")
required_vars = ['OPENAI_API_KEY', 'GOOGLE_SHEET_ID', 'GOOGLE_SERVICE_ACCOUNT_JSON']
for var in required_vars:
    val = os.getenv(var)
    if val:
        print(f"  OK: {var} ({len(str(val))} chars)")
    else:
        print(f"  FAIL: {var} missing")

# Test 2: Import modules
print("\n[TEST 2] Importing modules...")
try:
    from services import document_processor
    print("  OK: document_processor imported")
except Exception as e:
    print(f"  FAIL: document_processor - {e}")
    sys.exit(1)

try:
    from itr_extractor import ITRDocumentProcessor
    print("  OK: ITRDocumentProcessor imported")
except Exception as e:
    print(f"  FAIL: ITRDocumentProcessor - {e}")
    sys.exit(1)

# Test 3: Initialize processor
print("\n[TEST 3] Initializing ITRDocumentProcessor...")
try:
    processor = ITRDocumentProcessor(use_ocr=True)
    print(f"  OK: Processor initialized")
    print(f"     - ai_extractor: {processor.ai_extractor is not None}")
except Exception as e:
    print(f"  FAIL: {e}")
    sys.exit(1)

# Test 4: Test with actual PDF
print("\n[TEST 4] Testing extraction with Form16 PDF...")
FORM16_PATH = r"uploads\21531a6c-c4ce-472f-acce-b3a292fe168e\0d19ddfd_Form_16.pdf"

if not os.path.exists(FORM16_PATH):
    print(f"  FAIL: File not found: {FORM16_PATH}")
    sys.exit(1)

print(f"  File found: {os.path.getsize(FORM16_PATH)} bytes")

try:
    with open(FORM16_PATH, 'rb') as f:
        file_bytes = f.read()
    
    print(f"  Read {len(file_bytes)} bytes from file")
    
    # Test document_processor directly
    print(f"\n  Testing document_processor.process_documents()...")
    start = time.time()
    result = document_processor.process_documents(file_bytes, "application/pdf", doc_type="form16")
    elapsed = time.time() - start
    
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Result keys: {list(result.keys())}")
    print(f"  Success: {result.get('success')}")
    print(f"  Error: {result.get('error', 'N/A')}")
    print(f"  Data keys: {list(result.get('data', {}).keys())[:5]}")
    print(f"  Confidence: {result.get('confidence')}")
    
    # Test processor.process_file
    print(f"\n  Testing processor.process_file()...")
    start = time.time()
    result2 = processor.process_file(file_bytes, "form16.pdf", doc_type="form16")
    elapsed2 = time.time() - start
    
    print(f"  Time: {elapsed2:.1f}s")
    print(f"  Success: {result2.get('success')}")
    print(f"  Data: {list(result2.get('data', {}).keys())[:5]}")
    
except Exception as e:
    print(f"  FAIL: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
