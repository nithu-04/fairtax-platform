#!/usr/bin/env python3
"""
ManyChat Integration Test Script

Tests the ManyChat service integration with WhatsApp.
Run this after adding MANYCHAT_API_TOKEN to .env

Usage:
    python test_manychat.py

Expected output:
    [OK] All tests passed
"""

import sys
import time
from manychat_service import (
    test_connection,
    normalize_phone,
    send_text,
    send_template,
    MANYCHAT_API_TOKEN
)

# Colors for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")

def print_success(text):
    print(f"{Colors.GREEN}[OK] {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}[FAIL] {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}[WARN] {text}{Colors.END}")

def test_manychat():
    """Run all ManyChat tests"""

    print_header("ManyChat Integration Test Suite")

    # Test 1: Check configuration
    print("TEST 1: Configuration Check")
    print("-" * 40)

    if not MANYCHAT_API_TOKEN:
        print_error("MANYCHAT_API_TOKEN not set in .env")
        print("Please add: MANYCHAT_API_TOKEN=mcapi_your_token")
        return False

    print(f"API Token found: {MANYCHAT_API_TOKEN[:20]}...")
    print_success("Configuration is set")

    # Test 2: Connection test
    print("\n\nTEST 2: ManyChat Connection")
    print("-" * 40)
    print("Testing connection to ManyChat API...")

    if test_connection():
        print_success("Connected to ManyChat API")
    else:
        print_error("Failed to connect to ManyChat API")
        print("Check:")
        print("  1. MANYCHAT_API_TOKEN is correct")
        print("  2. Network connection is working")
        print("  3. ManyChat account is active")
        return False

    # Test 3: Phone normalization
    print("\n\nTEST 3: Phone Number Normalization")
    print("-" * 40)

    test_numbers = [
        ("9876543210", "919876543210"),
        ("919876543210", "919876543210"),
        ("+91 9876543210", "919876543210"),
        ("98-765-43210", "919876543210"),
    ]

    all_normalized = True
    for input_num, expected in test_numbers:
        result = normalize_phone(input_num)
        if result == expected:
            print_success(f"'{input_num}' -> '{result}'")
        else:
            print_error(f"'{input_num}' -> '{result}' (expected '{expected}')")
            all_normalized = False

    if not all_normalized:
        return False

    # Test 4: Send test message
    print("\n\nTEST 4: Send Test Text Message")
    print("-" * 40)
    print("[WARNING] You need to provide your phone number for this test")

    test_phone = input("Enter your phone number (10 digits): ").strip()

    if not test_phone or len(test_phone) < 10:
        print_warning("Skipping test message (no valid phone provided)")
    else:
        normalized = normalize_phone(test_phone)
        print(f"Sending test message to: {normalized}")

        result = send_text(
            normalized,
            "[TEST] Test message from FairTax ManyChat integration\n\n"
            "If you see this, the integration is working! [OK]"
        )

        if "error" not in str(result):
            print_success("Test message sent!")
            print(f"Response: {result}")
            print("\n[TIMER] Check your WhatsApp in the next 5-10 seconds...")
            time.sleep(2)
        else:
            print_error(f"Failed to send test message: {result}")

    # Test 5: Send template message
    print("\n\nTEST 5: Send Template Message")
    print("-" * 40)

    if not test_phone or len(test_phone) < 10:
        print_warning("Skipping template test (no valid phone provided)")
    else:
        normalized = normalize_phone(test_phone)
        print("Sending template: submission_received")

        result = send_template(
            normalized,
            "submission_received",
            ["Test User", "REF123456"]
        )

        if "error" not in str(result):
            print_success("Template message sent!")
            print(f"Response: {result}")
        else:
            print_error(f"Failed to send template: {result}")

    return True

def main():
    """Main test runner"""
    try:
        print_header("FairTax ManyChat Integration Test")

        success = test_manychat()

        print("\n\n" + "="*60)
        if success:
            print_success("All tests completed!")
            print("\nYou can now:")
            print("  1. Edit app.py line 4 to import manychat_service")
            print("  2. Restart Flask backend")
            print("  3. Test actual filing submission")
            print("="*60 + "\n")
            return 0
        else:
            print_error("Tests failed - check configuration")
            print("="*60 + "\n")
            return 1

    except KeyboardInterrupt:
        print_error("Test interrupted by user")
        return 1
    except Exception as e:
        print_error(f"Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
