import os
import json
import base64
import logging
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")
AI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
API_TIMEOUT = 45  # Render timeout for Vision API calls

_client = None

def _get_client():
    """Initialize OpenAI API client with timeout for Render deployments."""
    global _client
    if _client is not None:
        return _client
    api_key = os.getenv("OPENAI_API_KEY")
    try:
        if api_key:
            _client = OpenAI(api_key=api_key, timeout=API_TIMEOUT)
        else:
            _client = OpenAI(timeout=API_TIMEOUT)  # Uses OPENAI_API_KEY from env
        logger.info("OpenAI client initialized with timeout")
    except Exception as e:
        logger.error(f"Could not initialize OpenAI client: {str(e)}", exc_info=True)
        _client = None
    return _client

def generate_ai_response(prompt):
    """Call text/reasoning model with text prompt using OpenAI."""
    try:
        if AI_PROVIDER == "openai":
            client = _get_client()
            if not client:
                raise ValueError("OpenAI client not initialized")

            response = client.chat.completions.create(
                model=AI_MODEL,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,  # FIXED: Changed from 0.7 to 0.0 for deterministic extraction
                max_tokens=2000
            )

            return response.choices[0].message.content

        raise ValueError(f"Unsupported AI provider: {AI_PROVIDER}")

    except Exception as e:
        logger.error(f"Text generation error: {str(e)}", exc_info=True)
        raise


def call_vision_model(image_bytes, prompt):
    """Call OpenAI Vision model (GPT-4o) with image bytes + text prompt."""
    try:
        if AI_PROVIDER != "openai":
            raise ValueError(f"Unsupported AI provider for Vision: {AI_PROVIDER}")

        client = _get_client()
        if not client:
            raise ValueError("OpenAI client not initialized")

        # Encode image to base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')

        # Call OpenAI Vision API with configured model
        response = client.chat.completions.create(
            model=AI_MODEL,  # Use model from OPENAI_MODEL env var (gpt-4o-mini)
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=2000,
            temperature=0.0  # FIXED: Changed from 0.7 to 0.0 for deterministic document extraction
        )

        result = response.choices[0].message.content
        if not result:
            raise ValueError("No response from Vision model")

        return result

    except Exception as e:
        logger.error(f"Vision extraction failed: {str(e)}", exc_info=True)
        raise


def call_reasoning_model(text_prompt, json_data):
    """Call text model with structured JSON data for tax reasoning using OpenAI."""
    try:
        combined_prompt = f"{text_prompt}\n\nStructured Data:\n{json.dumps(json_data, indent=2)}"
        return generate_ai_response(combined_prompt)

    except Exception as e:
        logger.error(f"Reasoning call failed: {str(e)}", exc_info=True)
        raise
