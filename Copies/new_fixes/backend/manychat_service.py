"""
ManyChat WhatsApp Integration Service (FLOW-BASED API)
Drop-in replacement for whatsapp_service.py using native ManyChat WhatsApp APIs.

CRITICAL ARCHITECTURE:
- Templates are NOT hardcoded in Python
- Templates are created in ManyChat Dashboard using "Message Templates" feature
- Flows are created in ManyChat Dashboard that contain those templates
- This service sends flows via /sendFlow API with Flow IDs
- Meta approves templates - not arbitrary text
- Variables are populated using ManyChat custom fields before triggering flow
"""

import requests
import time
import logging
import os
from config import Config

logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================

MANYCHAT_API_TOKEN = Config.__dict__.get('MANYCHAT_API_TOKEN', os.getenv('MANYCHAT_API_TOKEN', ''))
MANYCHAT_PHONE_NUMBER = Config.__dict__.get('MANYCHAT_PHONE_NUMBER', os.getenv('MANYCHAT_PHONE_NUMBER', '9600165254'))

# Use native ManyChat API
MANYCHAT_BASE_URL = "https://api.manychat.com"

logger.info(f"[manychat] Configured for FairTax WhatsApp: {MANYCHAT_PHONE_NUMBER}")

# ==================== FLOW MAPPING ====================
# IMPORTANT: These Flow IDs come from your ManyChat Flows
# Each flow contains a Message Template and is triggered via sendFlow API
# To find Flow ID: Go to Flow in dashboard, copy from URL: /files/{FLOW_ID}

TEMPLATE_MAPPING = {
    'submission_received': 'content20260531122630_383939',  # submitted_flow
    'quote_ready': 'PENDING_FLOW_ID',
    'payment_instructions': 'PENDING_FLOW_ID',
    'payment_proof_received': 'PENDING_FLOW_ID',
    'filing_completed': 'PENDING_FLOW_ID',
    'payment_reminder': 'PENDING_FLOW_ID',
    'referral_update': 'PENDING_FLOW_ID',
    'referred_notification': 'PENDING_FLOW_ID',
    'withdrawal_request': 'PENDING_FLOW_ID'
}

# ==================== UTILITIES ====================

def normalize_phone(p):
    """
    Normalize phone number to 91XXXXXXXXXX format (required by Meta/ManyChat India).

    Args:
        p: Phone number (can be 10 digits, with country code, with +, etc.)

    Returns:
        str: Normalized phone number in format 91XXXXXXXXXX
    """
    p = str(p or "").replace(" ", "").replace("+", "").replace("-", "")
    if len(p) == 10:
        p = "91" + p
    return p


def _retry_with_backoff(func, max_retries=3, base_delay=1):
    """
    Retry a function with exponential backoff.

    Args:
        func: Callable that returns (success: bool, response: dict)
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds (doubles each retry)

    Returns:
        dict: Response from the function
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            success, response = func()

            if success:
                return response

            # Check if error is retryable
            if isinstance(response, dict):
                error = response.get('error', {})
                if isinstance(error, dict):
                    error_code = error.get('code')
                    # Retry on rate limit (429) and temporary errors (5xx)
                    if error_code not in (429, 500, 502, 503, 504):
                        return response  # Non-retryable error

            last_error = response

        except requests.exceptions.Timeout as e:
            logger.warning(f"Attempt {attempt + 1}/{max_retries + 1}: Timeout - {str(e)}")
            last_error = {'error': f'Timeout: {str(e)}'}

        except requests.exceptions.RequestException as e:
            logger.warning(f"Attempt {attempt + 1}/{max_retries + 1}: Request error - {str(e)}")
            last_error = {'error': f'Request error: {str(e)}'}

        except Exception as e:
            logger.error(f"Attempt {attempt + 1}/{max_retries + 1}: Unexpected error - {str(e)}")
            return {'error': str(e)}

        # Calculate delay with exponential backoff
        if attempt < max_retries:
            delay = base_delay * (2 ** attempt)  # 1, 2, 4 seconds
            logger.info(f"[manychat] Retrying in {delay} seconds... (Attempt {attempt + 2}/{max_retries + 1})")
            time.sleep(delay)

    logger.error(f"[manychat] All {max_retries + 1} retry attempts failed")
    return last_error or {'error': 'Unknown error after retries'}


def _get_or_create_subscriber(to_phone, first_name="FairTax User"):
    """
    Get or create a ManyChat subscriber using native WhatsApp schema.

    Args:
        to_phone: Phone number in format 91XXXXXXXXXX
        first_name: User's first name for new subscribers

    Returns:
        str: Subscriber ID if successful, None if failed
    """
    if not MANYCHAT_API_TOKEN:
        logger.warning("[manychat] Missing MANYCHAT_API_TOKEN; skipping subscriber operations")
        return None

    headers = {
        "Authorization": f"Bearer {MANYCHAT_API_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        # Step 1: Try to find existing subscriber by phone
        find_url = f"{MANYCHAT_BASE_URL}/api/subscribers/findByPhone"
        params = {"phone": to_phone}

        response = requests.get(find_url, headers=headers, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json().get('data')
            if data and isinstance(data, dict):
                subscriber_id = data.get('id')
                logger.info(f"[manychat] Found existing subscriber: {subscriber_id}")
                return subscriber_id

        # Step 2: Subscriber not found - create new WhatsApp contact
        logger.info(f"[manychat] Creating new WhatsApp subscriber for {to_phone}")
        create_url = f"{MANYCHAT_BASE_URL}/api/subscribers"

        payload = {
            "phone": to_phone,
            "first_name": first_name,
            "last_name": "FairTax",
            "has_opt_in_whatsapp": True,  # CRITICAL: Enable WhatsApp outbound messaging
            "has_opt_in_sms": False
        }

        create_response = requests.post(create_url, headers=headers, json=payload, timeout=10)

        if create_response.status_code in [200, 201]:
            subscriber = create_response.json().get('data', {})
            new_id = subscriber.get('id')
            logger.info(f"[manychat] Created subscriber: {new_id}")
            return new_id
        else:
            logger.warning(f"[manychat] Failed to create subscriber: {create_response.text}")
            return None

    except Exception as e:
        logger.error(f"[manychat] Error managing subscriber: {str(e)}")
        return None


# ==================== MESSAGE SENDING ====================

def send_text(to_phone, text):
    """
    Send a plain text WhatsApp message via ManyChat.

    NOTE: For production, use send_template() instead.
    Plain text to new users is restricted by Meta.

    Args:
        to_phone: Phone number with country code (91XXXXXXXXXX format)
        text: Message body string

    Returns:
        dict: API response
    """
    if not MANYCHAT_API_TOKEN:
        logger.warning("[manychat] Missing MANYCHAT_API_TOKEN; skipping send_text")
        return {"error": "missing_manychat_config"}

    to_phone = normalize_phone(to_phone)

    def _send():
        try:
            # Get or create subscriber
            subscriber_id = _get_or_create_subscriber(to_phone)
            if not subscriber_id:
                return False, {"error": "subscriber_not_found"}

            # Send text message
            url = f"{MANYCHAT_BASE_URL}/api/subscribers/{subscriber_id}/send_message"
            headers = {
                "Authorization": f"Bearer {MANYCHAT_API_TOKEN}",
                "Content-Type": "application/json"
            }
            payload = {
                "message": {
                    "text": str(text)
                }
            }

            response = requests.post(url, headers=headers, json=payload, timeout=45)

            if response.status_code in [200, 201]:
                logger.info(f"[manychat] Text sent: to={to_phone}, subscriber={subscriber_id}")
                return True, response.json()
            else:
                logger.warning(f"[manychat] Failed to send text: status={response.status_code}, resp={response.text}")
                return False, response.json() if response.text else {"error": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"[manychat] Exception sending text: {str(e)}")
            raise

    return _retry_with_backoff(_send, max_retries=3, base_delay=2)


def send_template(to_phone, template_name, params, button_url_param=None):
    """
    Send a templated WhatsApp message via ManyChat Flow.

    This triggers a pre-built Flow in ManyChat that contains
    an approved Meta WhatsApp template. Variables are populated
    using ManyChat custom fields.

    Args:
        to_phone: Phone number with country code (91XXXXXXXXXX format)
        template_name: Internal name of template (e.g., 'submission_received')
                      Maps to ManyChat Flow ID via TEMPLATE_MAPPING
        params: List of parameters to fill template placeholders
                - params[0] = name (first name)
                - params[1] = ref_code or other dynamic data
        button_url_param: Optional URL for button (set in ManyChat template)

    Returns:
        dict: API response
    """
    if not MANYCHAT_API_TOKEN:
        logger.warning("[manychat] Missing MANYCHAT_API_TOKEN; skipping send_template")
        return {"error": "missing_manychat_config"}

    to_phone = normalize_phone(to_phone)
    flow_id = TEMPLATE_MAPPING.get(template_name)

    if not flow_id or flow_id == 'PENDING_FLOW_ID':
        logger.error(f"[manychat] No flow configured for template: {template_name}")
        return {"error": f"unknown_template: {template_name}"}

    def _send():
        try:
            # Extract first name from params if available
            first_name = params[0] if params and len(params) > 0 else "FairTax User"

            # Step 1: Get or create subscriber
            subscriber_id = _get_or_create_subscriber(to_phone, first_name)
            if not subscriber_id:
                return False, {"error": "subscriber_not_found"}

            # Step 2: Set custom fields so template can populate variables
            # Map params to field names expected by your ManyChat templates
            param_keys = [
                'name', 'ref_code', 'category', 'refund', 'fee', 'plan', 'amount',
                'referral_count', 'reward', 'milestone_message', 'pdf_link'
            ]

            if params:
                try:
                    field_url = f"{MANYCHAT_BASE_URL}/api/subscribers/{subscriber_id}/customFields"
                    field_payload = {}
                    for i, param in enumerate(params):
                        if i < len(param_keys):
                            field_payload[param_keys[i]] = str(param or "")

                    if field_payload:
                        requests.post(field_url, headers={"Authorization": f"Bearer {MANYCHAT_API_TOKEN}", "Content-Type": "application/json"},
                                    json=field_payload, timeout=10)
                        logger.info(f"[manychat] Set custom fields for {subscriber_id}")
                except Exception as e:
                    logger.warning(f"[manychat] Failed to set fields (flow will use defaults): {str(e)}")

            # Step 3: Trigger the ManyChat Flow containing the approved Meta template
            flow_url = f"{MANYCHAT_BASE_URL}/api/subscribers/{subscriber_id}/sendFlow"
            headers = {
                "Authorization": f"Bearer {MANYCHAT_API_TOKEN}",
                "Content-Type": "application/json"
            }
            flow_payload = {
                "flow_ns": flow_id
            }

            response = requests.post(flow_url, headers=headers, json=flow_payload, timeout=45)

            if response.status_code in [200, 201]:
                logger.info(f"[manychat] Flow sent: template_name={template_name}, flow_id={flow_id}, subscriber={subscriber_id}")
                return True, response.json()
            else:
                logger.warning(f"[manychat] Failed to send flow: status={response.status_code}, resp={response.text}")
                return False, response.json() if response.text else {"error": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"[manychat] Exception sending template: {str(e)}")
            raise

    return _retry_with_backoff(_send, max_retries=3, base_delay=2)


# ==================== HEALTH CHECK ====================

def test_connection():
    """
    Test if ManyChat API token is valid and connection works.

    Returns:
        bool: True if connection successful, False otherwise
    """
    if not MANYCHAT_API_TOKEN:
        logger.error("[manychat] MANYCHAT_API_TOKEN not configured")
        return False

    try:
        # Test by attempting to create a subscriber (POST method)
        url = f"{MANYCHAT_BASE_URL}/fb/subscriber/createSubscriber"
        headers = {
            "Authorization": f"Bearer {MANYCHAT_API_TOKEN}",
            "Content-Type": "application/json"
        }

        # Minimal test payload
        payload = {
            "phone": "919876543210",
            "first_name": "Test",
            "has_opt_in_whatsapp": True
        }

        response = requests.post(url, headers=headers, json=payload, timeout=10)

        # 200/201 = success, 400 = validation error (but token is valid)
        if response.status_code in [200, 201, 400]:
            logger.info("[manychat] [OK] Connection successful")
            return True
        else:
            logger.error(f"[manychat] [FAIL] Connection failed: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"[manychat] [FAIL] Connection test failed: {str(e)}")
        return False
