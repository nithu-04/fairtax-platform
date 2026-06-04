import os
import json
import base64
import time
import threading
from openai import OpenAI, RateLimitError, APIStatusError, APIConnectionError, APITimeoutError
from dotenv import load_dotenv

load_dotenv()

AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")
AI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_client = None
_client_lock = threading.Lock()  # thread-safe init

# Transient HTTP status codes that warrant a retry
_RETRYABLE_STATUS = {429, 500, 502, 503, 529}

# Conservative concurrency limit — avoid cascading rate-limit errors when
# multiple pages are processed in parallel.
_API_SEMAPHORE = threading.Semaphore(3)


def _get_client():
    """Thread-safe OpenAI SDK client initialisation.

    Deliberately does NOT cache None — every call retries init so a transient
    startup failure doesn't permanently break Vision for the lifetime of the
    process.
    """
    global _client
    with _client_lock:
        if _client is not None:
            return _client
        api_key = os.getenv("OPENAI_API_KEY")
        print(f"[AI_PROVIDER] Initialising OpenAI client. API key: {'SET' if api_key else 'NOT SET'}")
        try:
            _client = OpenAI(
                api_key=api_key,
                timeout=90.0,          # hard cap per request
                max_retries=0,         # we handle retries ourselves
            )
            print("[AI_PROVIDER] OpenAI client ready")
        except Exception as exc:
            print(f"[AI_PROVIDER] Client init failed: {exc}")
            _client = None
        return _client


def _is_retryable(exc: Exception) -> bool:
    """Return True for transient errors that should be retried."""
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIStatusError) and exc.status_code in _RETRYABLE_STATUS:
        return True
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return True
    msg = str(exc).lower()
    return any(k in msg for k in ("timeout", "rate limit", "overloaded", "503", "502", "529"))


def call_vision_model(image_bytes: bytes, prompt: str, max_retries: int = 2) -> str:
    """Call GPT-4o-mini Vision with retry + exponential back-off.

    Uses a semaphore to bound concurrent Vision calls and avoid rate limits
    when multiple document pages are processed in parallel.
    """
    if AI_PROVIDER != "openai":
        raise ValueError(f"Unsupported AI provider for Vision: {AI_PROVIDER}")

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_b64}", "detail": "high"},
                },
            ],
        }
    ]

    last_exc = None
    for attempt in range(max_retries + 1):
        client = _get_client()
        if not client:
            raise RuntimeError("OpenAI client could not be initialised — check OPENAI_API_KEY")

        try:
            with _API_SEMAPHORE:
                response = client.chat.completions.create(
                    model=AI_MODEL,
                    messages=messages,
                    max_tokens=1200,
                    temperature=0.0,
                )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from Vision model")
            return content

        except Exception as exc:
            last_exc = exc
            if _is_retryable(exc) and attempt < max_retries:
                wait = 2 ** attempt          # 1s, 2s
                print(f"[AI_PROVIDER] Vision transient error (attempt {attempt+1}): {exc}. Retrying in {wait}s…")
                time.sleep(wait)
                continue
            print(f"[AI_PROVIDER] Vision failed (attempt {attempt+1}): {exc}")
            break  # non-retryable or out of retries

    raise last_exc or RuntimeError("Vision extraction failed for unknown reason")


def generate_ai_response(prompt: str) -> str:
    """Text-only AI call (used for WhatsApp replies and tax calculation)."""
    client = _get_client()
    if not client:
        raise RuntimeError("OpenAI client not initialised")
    response = client.chat.completions.create(
        model=AI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=2000,
    )
    return response.choices[0].message.content


def call_reasoning_model(text_prompt: str, json_data: dict) -> str:
    combined = f"{text_prompt}\n\nStructured Data:\n{json.dumps(json_data, indent=2)}"
    return generate_ai_response(combined)
