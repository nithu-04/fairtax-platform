import requests
from config import Config

token = Config.__dict__.get('MANYCHAT_API_TOKEN', '')
print(f"Token: {token[:30]}...")

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# With has_opt_in_sms: False (API requirement)
url = "https://api.manychat.com/fb/subscriber/createSubscriber"
payload = {
    "phone": "918248722773",  # Your test phone
    "first_name": "Test",
    "has_opt_in_whatsapp": True,
    "has_opt_in_sms": False  # Required by API even if not using SMS
}

print(f"Payload: {payload}\n")

try:
    r = requests.post(url, headers=headers, json=payload, timeout=10)
    print(f"Status: {r.status_code}")

    if r.status_code in [200, 201]:
        print("✅ SUCCESS!")
    else:
        print(f"Response: {r.json()}")
except Exception as e:
    print(f"Error: {e}")
