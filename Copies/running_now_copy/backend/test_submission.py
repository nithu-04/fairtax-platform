#!/usr/bin/env python3
"""
Direct test of submission_received template
"""

from manychat_service import send_template, test_connection

print("=" * 60)
print("ManyChat WhatsApp Integration - Direct Test")
print("=" * 60)

# Test 1: Connection
print("\nTEST 1: Connection Check")
print("-" * 40)
if test_connection():
    print("[OK] Connected to ManyChat API")
else:
    print("[FAIL] Failed to connect")
    exit(1)

# Test 2: Send template
print("\nTEST 2: Send submission_received Template")
print("-" * 40)

phone = "8248722773"
name = "Test User"
ref_code = "REF123456"

print(f"Sending to: {phone}")
print(f"Name: {name}")
print(f"Reference Code: {ref_code}")

result = send_template(phone, "submission_received", [name, ref_code])

print(f"\nResponse: {result}")

if "error" not in str(result).lower():
    print("\n[OK] Template sent successfully!")
    print("Check your WhatsApp in 5-10 seconds...")
else:
    print(f"\n[FAIL] Failed to send: {result}")

print("\n" + "=" * 60)
