import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')

try:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    print("Testing with gpt-4o-mini (from .env)...")
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=5
    )
    print("SUCCESS: gpt-4o-mini works!")
    print(f"Response: {response.choices[0].message.content}")

except Exception as e:
    print(f"ERROR: {str(e)}")
