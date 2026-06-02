import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')

try:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    print("Testing with gpt-3.5-turbo (basic model)...")
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=5
    )
    print("SUCCESS: API Key works! gpt-3.5-turbo is accessible")
    print(f"Response: {response.choices[0].message.content}")

except Exception as e:
    print(f"ERROR: {str(e)}")
    print(f"Error Type: {type(e).__name__}")
