import requests

token = '4961787:26e624222865'
headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

# Test finding subscriber by phone
url = 'https://api.manychat.com/fb/subscriber/findBySystemField'
params = {
    'system_field_name': 'phone_number',
    'system_field_value': '918248722773'
}

print(f"Testing: {url}\n")
print(f"Params: {params}\n")

try:
    r = requests.get(url, headers=headers, params=params, timeout=10)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
