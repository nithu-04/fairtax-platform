import requests

token = '4961787:26e624222865'
headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

# Test different subscriber endpoints
endpoints = [
    ('POST', 'https://api.manychat.com/fb/subscribers'),
    ('POST', 'https://api.manychat.com/fb/subscriber'),
    ('POST', 'https://api.manychat.com/fb/sending/createSubscriber'),
    ('POST', 'https://api.manychat.com/v3/subscriber'),
]

print("Finding correct subscriber endpoint:\n")
for method, url in endpoints:
    try:
        if method == 'POST':
            r = requests.post(url, headers=headers, json={"phone": "919876543210"}, timeout=5)
        endpoint_name = url.split('/')[-1]
        print(f"{method} {endpoint_name}: {r.status_code}")
    except Exception as e:
        print(f"Error: {e}")
