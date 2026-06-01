import requests

token = '4961787:26e624222865'  # Use your actual token
headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

endpoints = [
    'https://api.manychat.com/fb/subscriber/findBySystemField',
    'https://api.manychat.com/fb/sending/sendFlow',
    'https://api.manychat.com/fb/subscriber/setCustomFields',
]

print("Testing ManyChat API endpoints:\n")
for url in endpoints:
    try:
        r = requests.get(url, headers=headers, timeout=5)
        endpoint_name = url.split('/')[-1]
        print(f"{endpoint_name}: {r.status_code}")
    except Exception as e:
        print(f"Error: {e}")
