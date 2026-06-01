import requests
from config import Config

token = Config.__dict__.get('MANYCHAT_API_TOKEN', '')
print(f"Token: {token[:20]}...\n")

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# Try sendFlow directly with a subscriber ID
# Subscriber ID format in ManyChat is usually a number
# Let's try to find or create by phone first using a different approach

# Test 1: Try sendFlow with a test subscriber ID
print("=" * 60)
print("TEST 1: Direct sendFlow call")
print("=" * 60)

url = "https://api.manychat.com/fb/sending/sendFlow"
payload = {
    "subscriber_id": "1",  # Test with ID 1
    "flow_ns": "content20260531122630_383939"  # Your submitted_flow ID
}

print(f"URL: {url}\n")
print(f"Payload: {payload}\n")

try:
    r = requests.post(url, headers=headers, json=payload, timeout=10)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:500]}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: Try WhatsApp-specific subscriber endpoint
print("\n" + "=" * 60)
print("TEST 2: WhatsApp subscriber endpoint")
print("=" * 60)

url2 = "https://api.manychat.com/fb/subscriber"
payload2 = {
    "phone": "918248722773"
}

print(f"URL: {url2}\n")
print(f"Payload: {payload2}\n")

try:
    r = requests.post(url2, headers=headers, json=payload2, timeout=10)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
