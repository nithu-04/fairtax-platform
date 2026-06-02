import requests
import time
import json

BASE_URL = "http://localhost:5000"

# Test files
FORM16 = r"C:\Users\user\Desktop\fairtax\Copies\new_fixes\backend\uploads\21531a6c-c4ce-472f-acce-b3a292fe168e\0d19ddfd_Form_16.pdf"
PAYSLIP = r"C:\Users\user\Desktop\fairtax\Copies\new_fixes\backend\uploads\21531a6c-c4ce-472f-acce-b3a292fe168e\441a2f17_March_Payslip.pdf"

print("=" * 60)
print("TESTING PARALLEL EXTRACTION: Form16 + Payslip")
print("=" * 60)

try:
    with open(FORM16, 'rb') as f1, open(PAYSLIP, 'rb') as f2:
        files = [
            ('file', ('form16.pdf', f1)),
            ('file', ('payslip.pdf', f2))
        ]
        data = {
            'doc_type': 'form16',
            'submission_id': f'test-{int(time.time())}'
        }
        
        start = time.time()
        print(f"\n[{time.strftime('%H:%M:%S')}] Sending extraction request...")
        response = requests.post(f"{BASE_URL}/itr/extract", files=files, data=data, timeout=300)
        elapsed = time.time() - start
        
        print(f"[{time.strftime('%H:%M:%S')}] Response received in {elapsed:.2f}s")
        print(f"\nStatus Code: {response.status_code}")
        
        result = response.json()
        print(f"Success: {result.get('success')}")
        print(f"Data keys: {list(result.get('data', {}).keys())[:5]}...")
        
        if result.get('confidence'):
            print(f"Confidence: {result.get('confidence')}")
        
        print(f"\n📊 EXTRACTION TIME: {elapsed:.2f} seconds")
        print(f"   Expected: 30-45s (with parallel)")
        print(f"   Old: 2m36s (sequential)")
        
        if elapsed < 90:
            print("   ✅ FAST! Parallel extraction working!")
        elif elapsed < 160:
            print("   ⚠️  Slower than expected")
        else:
            print("   ❌ Still slow - parallel may not be working")

except Exception as e:
    print(f"Error: {e}")
