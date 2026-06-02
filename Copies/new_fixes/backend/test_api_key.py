import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')

print(f"API Key found: {bool(api_key)}")
print(f"Key starts with sk-: {api_key.startswith('sk-') if api_key else False}")
print(f"Key length: {len(api_key) if api_key else 0}")
if api_key:
    print(f"Key format: {api_key[:20]}...{api_key[-10:]}")

# Now test the key
try:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    print("\nAttempting API call...")
    response = client.chat.completions.create(
        model="gpt-4-vision",
        messages=[
            {"role": "user", "content": "Hello"}
        ],
        max_tokens=5,
        timeout=10
    )
    print("✅ API KEY IS VALID AND WORKING")
    print(f"Response: {response}")
except Exception as e:
    print(f"\n❌ API ERROR: {str(e)}")
    print(f"Error type: {type(e).__name__}")
    import traceback
    traceback.print_exc()
