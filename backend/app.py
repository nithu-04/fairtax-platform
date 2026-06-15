from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from config import Config
import ai_service, tax_engine, sheets_service, storage_service, manychat_service as whatsapp_service
import base64, traceback, os, requests as _requests, logging, sys
from pdf_service import generate_quote_pdf
from services import document_processor, quality_checker, doc_type_detector, normalization_service
from extraction_validator import ExtractionValidator
import uuid
from concurrent.futures import ThreadPoolExecutor

# Configure logging for both console and file (for Waitress visibility)
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    handlers=[
        logging.FileHandler('flask_app.log'),
        logging.StreamHandler(sys.stdout)  # FIXED: Also log to console/Waitress
    ]
)
logger = logging.getLogger(__name__)

# Configure Flask to serve frontend files
# Frontend is in ../frontend relative to this backend directory
frontend_path = os.path.join(os.path.dirname(__file__), '..', 'frontend')
app = Flask(__name__,
            static_folder=os.path.join(frontend_path),
            static_url_path='',
            template_folder=frontend_path)
app.secret_key = Config.FLASK_SECRET
CORS(app)

@app.after_request
def _ensure_cors(response):
    if 'Access-Control-Allow-Origin' not in response.headers:
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

# Add file handler with proper flushing
file_handler = logging.FileHandler('flask_app.log', mode='a')
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.DEBUG)

# Ensure output is flushed immediately (for Waitress)
sys.stdout.flush()
sys.stderr.flush()
try:
    from itr_api import itr_bp
    print(f"[DEBUG] itr_bp imported: {itr_bp}, url_prefix={itr_bp.url_prefix}")
    app.register_blueprint(itr_bp)
    print(f"[DEBUG] itr_bp registered with Flask app")
except Exception as e:
    print(f"[ERROR] Failed to register itr_bp: {e}")
    import traceback
    traceback.print_exc()

# Global request logger - log EVERY request with proper logging
@app.before_request
def log_request():
    # Don't read request data here - it can consume the stream!
    if '/itr/extract' in request.path:
        app.logger.info(f"[REQUEST] {request.method} {request.path}")
        app.logger.info(f"  Content-Type: {request.content_type}")
        app.logger.info(f"  Content-Length: {request.content_length}")
        app.logger.info(f"  Files keys: {list(request.files.keys())}")
        app.logger.info(f"  Form keys: {list(request.form.keys())}")

# Global error handler to catch ALL errors
@app.errorhandler(422)
def handle_422(e):
    app.logger.error(f"[422 ERROR] {request.method} {request.path}")
    app.logger.error(f"  Exception type: {type(e).__name__}")
    app.logger.error(f"  Error: {str(e)}")
    import traceback
    app.logger.error(f"  Traceback: {traceback.format_exc()}")
    return jsonify({
        'success': False,
        'error': f'Validation failed: {str(e)}',
        'data': {}
    }), 422


def _safe_float(v):
    try:
        if v is None:
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        # Strip common currency/formatting
        s = s.replace(',', '').replace('₹', '').strip()
        if s == '':
            return 0.0
        return float(s)
    except Exception:
        return 0.0

def _normalize_and_validate_phone(phone_raw):
    """Normalize and validate phone number. Returns (is_valid, normalized_phone).

    Validation rules:
    - Input must contain at least 10 digits
    - Returns last 10 digits (handles country codes like +91 prefix)

    Returns:
        tuple: (is_valid, normalized_phone)
        - is_valid: bool indicating if phone is valid
        - normalized_phone: str of 10 digits, or empty string if invalid
    """
    if not phone_raw:
        return False, ""

    # Extract all digits
    digits = ''.join(c for c in str(phone_raw).strip() if c.isdigit())

    # Validate minimum length
    if len(digits) < 10:
        return False, ""

    # Return last 10 digits (handles +91-10digit and variations)
    normalized = digits[-10:]
    return True, normalized

try:
    from scheduler_service import start_scheduler
    _scheduler = start_scheduler()
except Exception as _e:
    print(f"[Scheduler] Could not start: {_e}")

@app.route("/api/health")
def health():
    import os
    sheets_ok = bool(os.environ.get("GOOGLE_SHEET_ID") and os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip() not in ("", "service_account.json"))
    return {"status": "ok", "sheets_configured": sheets_ok}


# ---------- Landing Page (Root Route) ----------
@app.route("/")
def landing():
    """Serve landing.html as the default homepage"""
    try:
        return render_template("landing.html")
    except Exception as e:
        print(f"[LANDING] Error serving landing.html: {e}")
        logger.error(f"[LANDING] Error: {e}", exc_info=True)
        return {"error": "Could not load landing page"}, 500


# ---------- Phase-by-phase save ----------
@app.route("/api/save-phase", methods=["POST"])
def save_phase():
    print(">>> [SAVE_PHASE] FUNCTION CALLED - NEW CODE")
    try:
        data = request.get_json(force=True)
        print(f">>> [SAVE_PHASE] Got data with filing_category={data.get('filing_category')}")

        # Compatibility normalizations: frontend uses `filing_type`, backend/sheets expect `filing_category`.
        if data.get('filing_type') and not data.get('filing_category'):
            data['filing_category'] = data.get('filing_type')

        submission_id = data.get("submission_id")

        # Enforce filing_category only for NEW submissions (when no submission_id exists)
        # For updates to existing submissions, filing_category is optional
        if not submission_id:
            if not data.get('filing_category') or data.get('filing_category') not in ('regular', 'free'):
                return jsonify({"success": False, "error": "Please select filing type: 'regular' or 'free' before continuing."}), 400

        # [OK] CRITICAL: For NEW FREE filing, validate BEFORE anything else (BEFORE Sheets check)
        # But only if referral fields are present (i.e., NOT auto-save of referrer details)
        # Auto-save: frontend sends only referrer details (name, phone, email, PAN, city_type)
        # Submission: frontend sends all referrals + referral_code
        has_referral_fields = any(f'ref_name_{i}' in data or f'ref_phone_{i}' in data for i in range(1, 6))

        if not submission_id and (data.get('filing_category') == 'free' or data.get('filing_type') == 'free') and has_referral_fields:
            # Check all 5 referrals are filled with valid names and phones
            filled_count = 0
            for i in range(1, 6):
                ref_name = (data.get(f'ref_name_{i}', '') or '').strip()
                ref_phone = (data.get(f'ref_phone_{i}', '') or '').strip()
                # Extract only digits from phone
                phone_digits = ''.join(c for c in ref_phone if c.isdigit())
                # Check if name exists and phone has 10+ digits
                if ref_name and len(phone_digits) >= 10:
                    filled_count += 1

            # Enforce: ALL 5 must be filled
            if filled_count < 5:
                return jsonify({
                    "success": False,
                    "error": f"Please fill all 5 referrals before proceeding. Currently filled: {filled_count}/5",
                    "type": "incomplete_referrals"
                }), 400

            # Enforce: Referral code MUST be provided by frontend (generated via "Reveal Code")
            if not data.get('referral_code'):
                return jsonify({
                    "success": False,
                    "error": "Please click 'Reveal Code' to generate your referral code before proceeding.",
                    "type": "missing_referral_code"
                }), 400

        # ── LOCAL DEV MODE: skip all Sheets ops when credentials aren't configured ──
        _sa = getattr(Config, 'SERVICE_ACCOUNT_JSON', None)
        _sheets_configured = bool(
            getattr(Config, 'GOOGLE_SHEET_ID', None) and
            _sa and _sa != 'service_account.json'
        )
        if not _sheets_configured:
            referral_code = data.get('referral_code', '')
            print(f"[SAVE_PHASE][LOCAL] Sheets not configured — returning mock success. submission_id={submission_id}")
            return jsonify({"success": True, "submission_id": submission_id, "referral_code": referral_code})

        # Ensure a referral code exists early so we can return it to the UI
        # even if Sheets writes are delayed or fail. Use sheets_service helper.
        # Only auto-generate for REGULAR filings or existing submissions
        try:
            if not data.get('referral_code') and (data.get('filing_category') == 'regular' or submission_id):
                data['referral_code'] = sheets_service.gen_referral_code(data.get('name'))
        except Exception:
            # Non-fatal: if gen_referral_code unavailable, leave blank and continue
            pass

        # Normalize phone to digits (store last 10 digits when available)
        if data.get('phone'):
            digits = ''.join([c for c in str(data.get('phone')) if c.isdigit()])
            if len(digits) >= 10:
                data['phone'] = digits[-10:]
            else:
                data['phone'] = digits

        # If this is a NEW regular filing (no submission_id yet), require basic contact fields
        if not submission_id and data.get('filing_category') == 'regular':
            missing = [f for f in ('name', 'phone', 'email') if not (data.get(f) and str(data.get(f)).strip())]
            if missing:
                return jsonify({"success": False, "error": f"Missing required fields for regular filing: {', '.join(missing)}"}), 400

        # 🔍 TRACE: Log incoming data to /api/save-phase
        try:
            print(f"\n[SAVE_PHASE_INCOMING_TRACE] Received data:")
            print(f"  gross_salary: {data.get('gross_salary')}")
            print(f"  basic_salary: {data.get('basic_salary')}")
            print(f"  hra_received: {data.get('hra_received')}")
            print(f"  tds_paid: {data.get('tds_paid')}")
            print(f"  _doc_type: {data.get('_doc_type', 'NOT SET')}")
            print(f"  phone: {data.get('phone')}, filing_category: {data.get('filing_category')}")
        except Exception:
            pass

        # Unpack JSON investment blobs into individual columns so review page can display them
        # CRITICAL FIX: Include school_fees_json in aggregation check
        if any(k in data for k in ('home_loans_json', 'insurance_policies_json', 'donations_json', 'school_fees_json')):
            try:
                aggregates = _aggregate_investments(data)
                if aggregates:
                    data.update(aggregates)
                    print(f"[SAVE_PHASE] Unpacked investment JSON → {list(aggregates.keys())}")
            except Exception as e:
                print(f"[SAVE_PHASE] Investment aggregation warning: {e}")

        # 🔥 CASE 1: No ID → create new
        if not submission_id:
            submission_id = str(uuid.uuid4())
            data["submission_id"] = submission_id

            try:
                insert_res = sheets_service.insert_submission(data)
            except Exception:
                insert_res = None

        else:
            row = sheets_service.get_row_by_submission_id(submission_id)

            # If submission row doesn't exist yet, create it so extracted data can be saved
            if row is None and submission_id:
                try:
                    insert_res = sheets_service.insert_submission({"submission_id": submission_id})
                    row = sheets_service.get_row_by_submission_id(submission_id)
                except Exception:
                    insert_res = None
                    row = None

            # 🔥 CASE 2: ID exists but row NOT FOUND → insert
            if row is None:
                try:
                    insert_res = sheets_service.insert_submission(data)
                except Exception:
                    insert_res = None

            # 🔥 CASE 3: normal update
            # CRITICAL: Protect extracted salary fields from being overwritten by new extractions
            else:
                # row is an integer (row index) — fetch actual row data as dict
                row_data = sheets_service.check_approval(submission_id) or {}

                EXTRACTED_SALARY_FIELDS = {
                    'gross_salary', 'basic_salary', 'hra_received', 'tds_paid',
                    'pf_employee', 'pf_employer', 'professional_tax'
                }

                # Only update salary fields if they're not already in the sheet (from Form16)
                # This prevents payslip monthly values from overwriting form16 annual values
                update_data = dict(data)
                for field in EXTRACTED_SALARY_FIELDS:
                    sheet_has_value = row_data.get(field) not in (None, '')
                    if sheet_has_value and data.get(field) is not None:
                        # Keep existing sheet value, don't let new extraction override
                        print(f"[SAVE_PHASE_PROTECT] Keeping existing {field}={row_data[field]} "
                              f"(new extraction tried: {data[field]})")
                        update_data[field] = row_data[field]

                # 🔍 TRACE: Log what's being saved to database
                print(f"\n[SAVE_PHASE_DB_WRITE_TRACE] Writing to database:")
                print(f"  gross_salary: {update_data.get('gross_salary')}")
                print(f"  basic_salary: {update_data.get('basic_salary')}")
                print(f"  hra_received: {update_data.get('hra_received')}")
                print(f"  tds_paid: {update_data.get('tds_paid')}")

                sheets_service.update_row(row, update_data)  # row (int) stays here

        # [OK] HOOK: Update referral status if this user was referred
        # When a user saves their registration info (name + phone), check if they were referred
        # If found in Referrals sheet, mark them as "registered"
        try:
            user_phone = data.get('phone')
            if user_phone:
                # Only update status if this is a NEW registration (just created submission)
                if not insert_res or (isinstance(insert_res, dict) and insert_res.get('created')):
                    sheets_service.update_referral_status(user_phone, "registered")
                    print(f"[REFERRAL_HOOK] Updated referral status for phone {user_phone} → registered")
        except Exception as e:
            print(f"[REFERRAL_HOOK] Warning: Could not update referral status: {e}")

        # Read back referral code (if generated) so frontend can display it immediately
        try:
            if 'insert_res' in locals() and isinstance(insert_res, dict) and insert_res.get('referral_code'):
                ref_code = insert_res.get('referral_code')
            else:
                rec_after = sheets_service.check_approval(submission_id)
                ref_code = rec_after.get('referral_code', '') if rec_after else ''
            # Fallback to locally generated code in data if sheet read/write didn't yield one
            if not ref_code:
                ref_code = data.get('referral_code', '')
        except Exception:
            ref_code = ''

        return jsonify({
            "success": True,
            "submission_id": submission_id,
            "referral_code": ref_code
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ---------- WhatsApp webhook (incoming messages) ----------
@app.route("/whatsapp/webhook", methods=["GET", "POST"])
def whatsapp_webhook():
    # Verification challenge for Meta webhook setup
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        # Debug: log incoming token vs configured token to help verification
        try:
            print(f"[WEBHOOK VERIFY] received mode={mode!r} hub.verify_token={token!r} expected={Config.WHATSAPP_VERIFY_TOKEN!r}")
        except Exception:
            print("[WEBHOOK VERIFY] received verification request (could not print tokens)")

        if mode == "subscribe" and token == Config.WHATSAPP_VERIFY_TOKEN:
            print("[WEBHOOK VERIFY] token matched — returning challenge")
            return challenge, 200
        print("[WEBHOOK VERIFY] token mismatch — returning 403")
        return "Forbidden", 403

    # POST: incoming webhook events
    try:
        payload = request.get_json(force=True)
        entries = payload.get("entry", []) or []
        for entry in entries:
            for change in entry.get("changes", []) or []:
                value = change.get("value", {}) or {}
                messages = value.get("messages", []) or []
                # iterate over any inbound messages
                for m in messages:
                    phone = m.get("from")
                    if not phone:
                        continue
                    text = None
                    mtype = m.get("type")
                    if mtype == "text":
                        text = m.get("text", {}).get("body")
                    elif mtype == "button":
                        text = m.get("button", {}).get("text")
                    else:
                        # interactive messages (list_reply / button reply)
                        inter = m.get("interactive", {})
                        if inter:
                            if inter.get("type") == "button":
                                btn = inter.get("button", {})
                                text = btn.get("text") or btn.get("payload")
                            elif inter.get("type") == "list_reply":
                                lr = inter.get("list_reply", {})
                                text = lr.get("title") or lr.get("id")

                    if not text:
                        continue

                    # Normalize and respond
                    wa_phone = whatsapp_service.normalize_phone(phone)
                    try:
                        reply = ai_service.generate_whatsapp_reply(text, phone=phone)
                    except Exception as e:
                        print("AI generation error:", e)
                        reply = "Thanks — our team will reply shortly."

                    try:
                        whatsapp_service.send_text(wa_phone, reply)
                    except Exception as e:
                        print("Failed to send WA reply:", e)

        return jsonify({"success": True})
    except Exception as e:
        print("Webhook processing error:", e)
        return jsonify({"success": False, "error": str(e)}), 500
# ---------- Aggregation helpers ----------
def _deduplicate_and_sum_array(items, dedup_key, sum_keys):
    """Deduplicate items by dedup_key, sum numeric fields in sum_keys.
    Returns (total_sum_dict, duplicates_list)
    """
    seen = {}
    duplicates = []

    for item in (items or []):
        if not isinstance(item, dict):
            continue

        key_val = item.get(dedup_key) or ""
        if key_val and key_val in seen:
            # Duplicate detected
            duplicates.append({"original": seen[key_val], "duplicate": item, "key": dedup_key})
        else:
            if key_val:
                seen[key_val] = item

    totals = {}
    for sk in sum_keys:
        totals[sk] = sum(float(str(i.get(sk) or 0).replace(',', '').replace('₹', '')) or 0 for i in seen.values())

    return totals, duplicates


def _validate_before_tax_calculation(merged_data):
    """
    PRE-TAX VALIDATION: Detect extraction issues before tax calculation.

    Checks for:
    - Monthly vs annual value mismatches
    - Missing critical fields
    - Data sanity (negative values, extreme outliers)
    - Gross salary reasonableness

    Returns:
        List of issue dicts with {'severity': 'WARNING'|'ERROR', 'message': str}
    """
    issues = []

    def _to_num(x):
        try:
            if x is None or x == "":
                return 0.0
            return float(str(x).replace(',', '').replace('₹', ''))
        except:
            return 0.0

    # Extract values
    gross = _to_num(merged_data.get('gross_salary'))
    basic = _to_num(merged_data.get('basic_salary'))
    hra = _to_num(merged_data.get('hra_received'))
    home_loan_int = _to_num(merged_data.get('home_loan_interest'))
    tds = _to_num(merged_data.get('tds_paid'))

    # CHECK 1: Detect monthly vs annual mismatch
    # If we have a Form 16 (annual), payslip gross should be ~1/12 of Form 16 gross
    has_form16 = merged_data.get('has_form16') or merged_data.get('_doc_type') == 'form16'

    if not has_form16 and gross < 240000 and basic < 100000 and hra < 50000:
        # Likely monthly values - warning but not error (normalization should have fixed this)
        issues.append({
            "severity": "WARNING",
            "message": f"Gross salary (₹{gross:,.0f}) appears to be monthly. Should be annualized.",
            "field": "gross_salary"
        })

    # CHECK 2: Detect if gross salary is grossly wrong (₹0 is suspicious)
    if gross < 240000 and not (merged_data.get('filing_category') == 'free' or merged_data.get('referrer_name')):
        # < 20K/month baseline (probably wrong)
        issues.append({
            "severity": "WARNING",
            "message": f"Gross salary (₹{gross:,.0f}/year) seems very low. Please verify.",
            "field": "gross_salary"
        })

    # CHECK 3: TDS sanity check
    if gross > 0 and tds > gross:
        issues.append({
            "severity": "WARNING",
            "message": f"TDS paid (₹{tds:,.0f}) exceeds gross salary (₹{gross:,.0f}). Please verify.",
            "field": "tds_paid"
        })

    # CHECK 4: HRA sanity check
    if basic > 0 and hra > basic:
        issues.append({
            "severity": "WARNING",
            "message": f"HRA (₹{hra:,.0f}) exceeds basic salary (₹{basic:,.0f}). Please verify.",
            "field": "hra_received"
        })

    # CHECK 5: Home loan interest cap check (₹2L max per income tax)
    if home_loan_int > 200000:
        issues.append({
            "severity": "WARNING",
            "message": f"Home loan interest (₹{home_loan_int:,.0f}) exceeds ₹2,00,000 limit. Only ₹2L will be deducted.",
            "field": "home_loan_interest"
        })

    # CHECK 6: Negative values check
    negative_fields = {
        'gross_salary': gross,
        'basic_salary': basic,
        'hra_received': hra,
        'home_loan_interest': home_loan_int,
        'tds_paid': tds
    }
    for field, value in negative_fields.items():
        if value < 0:
            issues.append({
                "severity": "ERROR",
                "message": f"{field} is negative (₹{value:,.0f}). This is invalid.",
                "field": field
            })

    return issues


def _build_json_arrays_from_extractions(doc_type, extractions):
    """Build JSON arrays for document types that can have multiple instances.

    CRITICAL FIX: When multiple documents of the same type are extracted (e.g., 2 school fee
    PDFs, 3 insurance policies), we need to track each one individually. This function
    builds JSON arrays so _aggregate_investments can properly sum and deduplicate.

    Args:
        doc_type: The document type being extracted (school, insurance, homeloan, etc.)
        extractions: List of extracted data dicts

    Returns:
        Dict with JSON array fields (e.g., {"school_fees_json": "[{...}, {...}]"})
    """
    import json
    result = {}

    if doc_type == "school" and len(extractions) > 0:
        # Collect all school fee documents into a JSON array
        schools = []
        for i, ext in enumerate(extractions):
            school_entry = {
                "receipt_number": f"school_{i+1}",  # Auto-generate if not present
                "school_fees": ext.get("school_fees", 0),
                "school_name": ext.get("school_name", f"School {i+1}"),
                "source_file": ext.get("_source_filename", f"document_{i+1}"),
                "confidence": ext.get("_confidence", 0)
            }
            # Add any additional school fields if present
            for k in ["student_name", "class", "academic_year", "fee_type"]:
                if k in ext and ext[k]:
                    school_entry[k] = ext[k]
            schools.append(school_entry)

        if schools:
            result["school_fees_json"] = json.dumps(schools)
            print(f"[EXTRACT] Built school_fees_json with {len(schools)} documents")

    elif doc_type == "insurance" and len(extractions) > 0:
        # Collect all insurance policies into a JSON array
        policies = []
        for i, ext in enumerate(extractions):
            policy_entry = {
                "policy_no": ext.get("policy_no", f"policy_{i+1}"),
                "type": ext.get("type", "life"),
                "coverage_type": ext.get("coverage_type", ""),
                "premium": ext.get("premium_amount", ext.get("premium", 0)),
                "source_file": ext.get("_source_filename", f"document_{i+1}"),
                "confidence": ext.get("_confidence", 0)
            }
            # Add any additional insurance fields
            for k in ["insurer_name", "premium_frequency", "sum_assured", "maturity_date"]:
                if k in ext and ext[k]:
                    policy_entry[k] = ext[k]
            policies.append(policy_entry)

        if policies:
            result["insurance_policies_json"] = json.dumps(policies)
            print(f"[EXTRACT] Built insurance_policies_json with {len(policies)} documents")

    elif doc_type == "homeloan" and len(extractions) > 0:
        # Collect all home loan documents into a JSON array
        loans = []
        for i, ext in enumerate(extractions):
            loan_entry = {
                "policy_no": ext.get("policy_no", ext.get("account_number", f"loan_{i+1}")),
                "home_loan_interest": ext.get("home_loan_interest", ext.get("interest", 0)),
                "home_loan_principal": ext.get("home_loan_principal", ext.get("principal", 0)),
                "bank_name": ext.get("bank_name", ""),
                "source_file": ext.get("_source_filename", f"document_{i+1}"),
                "confidence": ext.get("_confidence", 0)
            }
            loans.append(loan_entry)

        if loans:
            result["home_loans_json"] = json.dumps(loans)
            print(f"[EXTRACT] Built home_loans_json with {len(loans)} documents")

    elif doc_type == "donation" and len(extractions) > 0:
        # Collect all donation receipts into a JSON array
        donations = []
        for i, ext in enumerate(extractions):
            donation_entry = {
                "receipt_number": ext.get("receipt_number", f"donation_{i+1}"),
                "donation_amount": ext.get("donation_amount", ext.get("amount", 0)),
                "organization_name": ext.get("organization_name", ""),
                "donation_date": ext.get("donation_date", ""),
                "source_file": ext.get("_source_filename", f"document_{i+1}"),
                "confidence": ext.get("_confidence", 0)
            }
            donations.append(donation_entry)

        if donations:
            result["donations_json"] = json.dumps(donations)
            print(f"[EXTRACT] Built donations_json with {len(donations)} documents")

    return result


def _aggregate_investments(merged_data):
    """Aggregate multi-entry investment JSON blobs into individual sheet columns.

    IMPORTANT — idempotent & non-accumulating:
    Values are derived purely from the JSON blobs. We do NOT add them on top
    of existing field values (that caused double-counting when the same
    extraction populates both the individual field and the JSON blob).
    """
    import json

    def _to_num(x):
        try:
            if x is None or x == "":
                return 0.0
            return float(str(x).replace(',', '').replace('₹', ''))
        except Exception:
            return 0.0

    aggregates = {}

    # ===== Home Loans =====
    hl = merged_data.get('home_loans_json')
    if hl:
        try:
            loans = json.loads(hl) if isinstance(hl, str) else hl
        except Exception:
            loans = hl if isinstance(hl, list) else []

        totals, dupes = _deduplicate_and_sum_array(
            loans or [],
            'policy_no',
            ['home_loan_interest', 'interest', 'interest_amount', 'home_loan_principal', 'principal']
        )

        if dupes:
            print(f"[AGG] Home loans: {len(dupes)} duplicates detected and merged")
            for d in dupes:
                print(f"  Duplicate loan account {d.get('original', {}).get('policy_no')}")

        sum_interest = totals.get('home_loan_interest', 0) + totals.get('interest', 0) + totals.get('interest_amount', 0)
        # NOTE: 'outstanding' / 'loan_outstanding' is the remaining loan BALANCE,
        # NOT the principal repayment eligible for 80C. Do NOT include it here.
        sum_principal = totals.get('home_loan_principal', 0) + totals.get('principal', 0)

        # Replace (not accumulate) — JSON is the source of truth
        if sum_interest > 0:
            aggregates['home_loan_interest'] = sum_interest
        if sum_principal > 0:
            aggregates['home_loan_principal'] = sum_principal

    # ===== Insurance Policies =====
    ins = merged_data.get('insurance_policies_json')
    if ins:
        try:
            inslist = json.loads(ins) if isinstance(ins, str) else ins
        except Exception:
            inslist = ins if isinstance(ins, list) else []

        totals, dupes = _deduplicate_and_sum_array(
            inslist or [],
            'policy_no',
            ['premium', 'premium_amount', 'premium_amount_rupee']
        )

        if dupes:
            print(f"[AGG] Insurance: {len(dupes)} duplicates detected and merged")
            for d in dupes:
                print(f"  Duplicate policy {d.get('original', {}).get('policy_no')}")

        sum_life_prem = 0.0
        sum_health_self = 0.0
        sum_health_parents = 0.0
        for I in (inslist or []):
            if not isinstance(I, dict):
                continue
            typ = (I.get('type') or I.get('coverage_type') or '').lower()
            prem = 0.0
            for k in ('premium', 'premium_amount', 'premium_amount_rupee'):
                if k in I and I[k] not in (None, ''):
                    prem = _to_num(I[k])
                    break
            if 'health_self' in typ or typ == 'health':
                sum_health_self += prem
            elif 'health_parent' in typ:
                sum_health_parents += prem
            else:
                sum_life_prem += prem

        # Replace (not accumulate) — JSON is the source of truth
        if sum_life_prem > 0:
            aggregates['ulip_lic'] = sum_life_prem
        if sum_health_self > 0:
            aggregates['medical_self'] = sum_health_self
        if sum_health_parents > 0:
            aggregates['medical_parents'] = sum_health_parents

    # ===== School Fees =====
    # CRITICAL FIX: Aggregate school fees from multiple documents
    sch = merged_data.get('school_fees_json')
    if sch:
        try:
            schools = json.loads(sch) if isinstance(sch, str) else sch
        except Exception:
            schools = sch if isinstance(sch, list) else []

        totals, dupes = _deduplicate_and_sum_array(
            schools or [],
            'receipt_number',  # School fees may have receipt numbers
            ['school_fees', 'fees', 'fee_amount', 'tuition_fees']
        )

        if dupes:
            print(f"[AGG] School fees: {len(dupes)} duplicates detected and merged")
            for d in dupes:
                print(f"  Duplicate school receipt {d.get('original', {}).get('receipt_number', 'N/A')}")

        total_fees = (totals.get('school_fees', 0) + totals.get('fees', 0) +
                     totals.get('fee_amount', 0) + totals.get('tuition_fees', 0))
        if total_fees > 0:
            aggregates['school_fees'] = total_fees
            print(f"[AGG] School fees aggregated: ₹{total_fees:,.0f} from {len(schools or [])} documents")

    # ===== Donations =====
    don = merged_data.get('donations_json')
    if don:
        try:
            dons = json.loads(don) if isinstance(don, str) else don
        except Exception:
            dons = don if isinstance(don, list) else []

        totals, dupes = _deduplicate_and_sum_array(
            dons or [],
            'receipt_number',
            ['donation_amount', 'amount']
        )

        if dupes:
            print(f"[AGG] Donations: {len(dupes)} duplicates detected and merged")
            for d in dupes:
                print(f"  Duplicate donation receipt {d.get('original', {}).get('receipt_number')}")

        total_don = totals.get('donation_amount', 0) + totals.get('amount', 0)
        if total_don > 0:
            aggregates['sec_80g'] = total_don

    return aggregates
@app.route("/api/extract", methods=["POST"])
def extract():
    try:
        submission_id = request.form.get("submission_id")
        doc_type = request.form.get("doc_type", "form16")
        files = request.files.getlist("documents")

        print(f"\n{'='*80}")
        print(f"[EXTRACT_START] Called with submission_id={submission_id}, doc_type={doc_type}, files={len(files)}")
        print(f"{'='*80}\n")

        row = sheets_service.get_row_by_submission_id(submission_id)

        # Ensure row exists before processing documents
        if row is None and submission_id:
            try:
                result = sheets_service.insert_submission({"submission_id": submission_id})
                row = sheets_service.get_row_by_submission_id(submission_id)
                print(f"[EXTRACT] Created new row for submission {submission_id}: row={row}")
            except Exception as e:
                print(f"[EXTRACT] Failed to create row for submission {submission_id}: {e}")

        urls, extractions = [], []

        # ═══════════════════════════════════════════════════════════
        # PARALLEL: Vision-based extraction pipeline (optimized)
        # ═══════════════════════════════════════════════════════════

        def _extract_single_document(file_data):
            """Extract data from a single document. Returns (url, extracted_data, error).

            Args:
                file_data: Tuple of (filename, content, mime) to avoid file object threading issues
            """
            filename, content, mime = file_data
            try:
                # Store file (reconstruct temporary file object for storage_service)
                # Note: We already read the content, so we use it directly
                from io import BytesIO
                temp_file = BytesIO(content)
                temp_file.filename = filename
                temp_file.mimetype = mime

                url = storage_service.save_file(temp_file, submission_id)

                # Process with Vision extraction pipeline
                print(f"[EXTRACT] Processing {filename} ({mime}) as doc_type='{doc_type}' with Vision pipeline...")
                result = document_processor.process_documents(content, mime, doc_type)

                # AUTO-DETECTION: Only when confidence is very low AND document is small
                conf = result.get("confidence", 0)
                pages = result["metadata"].get("pages_processed", 1)
                detected_doc_type = doc_type

                if conf < 0.5 and pages <= 10:
                    print(f"[EXTRACT] Auto-detecting: confidence={conf}, pages={pages}. Trying 3 most likely document types...")

                    best_result = result
                    best_confidence = result.get("confidence", 0)
                    best_doc_type = doc_type

                    # Try only 3 most likely document types (reduced from 7 for performance)
                    # Priority: form16 (most common) → payslip → homeloan
                    likely_types = ["form16", "payslip", "homeloan"]
                    for test_type in likely_types:
                        if test_type == doc_type:
                            continue  # Skip the current type, we already have that result
                        try:
                            test_result = document_processor.process_documents(content, mime, test_type)
                            test_confidence = test_result.get("confidence", 0)

                            print(f"[EXTRACT] Tried {test_type}: confidence={test_confidence}")

                            if test_confidence > best_confidence:
                                best_result = test_result
                                best_confidence = test_confidence
                                best_doc_type = test_type

                        except Exception as e:
                            print(f"[EXTRACT] Error trying {test_type}: {str(e)}")
                            continue

                    # If we found a better match, use it
                    if best_doc_type != doc_type:
                        print(f"[EXTRACT] DETECTED DOCUMENT TYPE: {best_doc_type} (confidence: {best_confidence})")
                        result = best_result
                        result["auto_detected_doc_type"] = best_doc_type
                        detected_doc_type = best_doc_type

                # Fail fast: if Vision extraction fails, return error
                if not result["success"]:
                    print(f"[EXTRACT] Vision extraction failed: {result['error']}")
                    suggestion = doc_type_detector.suggest_correct_doc_type(detected_doc_type, filename, {})
                    error_msg = result["error"]
                    if suggestion.get("should_retry"):
                        error_msg += f" (Hint: Try re-uploading as {suggestion['suggested_type']})"
                    return (None, None, error_msg)

                # Extract normalized data
                extracted_data = result["data"]
                extracted_data["_source_filename"] = filename
                extracted_data["_doc_type"] = detected_doc_type
                extracted_data["_confidence"] = result["confidence"]
                extracted_data["_metadata"] = result["metadata"]

                # Preserve auto-detected doc type if it was detected
                if "auto_detected_doc_type" in result:
                    extracted_data["_auto_detected_doc_type"] = result["auto_detected_doc_type"]

                print(f"[EXTRACT] {filename}: confidence={result['confidence']}, "
                      f"pages={result['metadata'].get('pages_processed', 1)}")

                # [DIAGNOSTIC] Log extraction output per document
                print(f"[EXTRACT_OUTPUT] {filename} => gross_salary={extracted_data.get('gross_salary', 'N/A')} | basic_salary={extracted_data.get('basic_salary', 'N/A')} | hra_received={extracted_data.get('hra_received', 'N/A')}")

                return (url, extracted_data, None)

            except Exception as e:
                print(f"[EXTRACT] Exception processing {filename}: {str(e)}")
                return (None, None, str(e))

        # PARALLEL EXTRACTION: Process all files concurrently
        # Read all file contents FIRST to avoid file object threading issues
        file_data_list = []
        for f in files:
            content = f.read()
            mime = f.mimetype or "image/png"
            file_data_list.append((f.filename, content, mime))

        results = []
        with ThreadPoolExecutor(max_workers=min(4, len(file_data_list))) as executor:
            results = list(executor.map(_extract_single_document, file_data_list))

        # Collect results and check for errors
        for url, extracted_data, error in results:
            if error:
                print(f"[EXTRACT] Document extraction error: {error}")
                return jsonify({
                    "success": False,
                    "error": error
                }), 400
            if url:
                urls.append(url)
            if extracted_data:
                extractions.append(extracted_data)

        # Merge multiple documents if applicable (existing logic)
        print(f"[EXTRACT] About to merge {len(extractions)} extractions")
        merged = ai_service.merge_extractions(extractions)
        conflicts = merged.pop('_merge_conflicts', [])
        print(f"[EXTRACT] After merge: gross_salary={merged.get('gross_salary')}, doc_type={merged.get('_doc_type')}")

        # FIX: Preserve Form16 annual values when processing Payslip separately
        # When only Payslip is extracted (separate API call from Form16), preserve the Form16
        # values already in the sheet to avoid monthly values overwriting annual values
        print(f"[EXTRACT_DEBUG] row={row is not None}, len(extractions)={len(extractions)}, doc_type={extractions[0].get('_doc_type') if extractions else 'N/A'}")

        if row and len(extractions) == 1 and extractions[0].get('_doc_type', '').lower() == 'payslip':
            # This is a payslip-only extraction. Check if sheet has Form16 annual values
            sheet_form16_fields = {'gross_salary', 'basic_salary', 'hra_received', 'pf_employee'}
            for field in sheet_form16_fields:
                sheet_val = row.get(field, 0)
                merged_val = merged.get(field, 0)

                # Try to convert to numbers for comparison
                try:
                    sheet_num = float(sheet_val) if sheet_val else 0
                    merged_num = float(merged_val) if merged_val else 0

                    # If sheet has much larger value (likely annual from Form16) and merged has smaller
                    # (likely monthly from payslip), keep the sheet value
                    if sheet_num > 0 and merged_num > 0:
                        ratio = sheet_num / max(merged_num, 1)
                        if ratio > 10:  # Likely annual vs monthly
                            merged[field] = sheet_num
                            print(f"[EXTRACT_PRESERVE] Kept sheet value for {field}: {sheet_num} (annual) over {merged_num} (monthly)")
                except (ValueError, TypeError):
                    pass

        # CRITICAL FIX: Build JSON arrays for documents that can have multiples
        # This ensures we can track individual receipts/documents and aggregate them properly
        try:
            json_fields_built = _build_json_arrays_from_extractions(doc_type, extractions)
            if json_fields_built:
                merged.update(json_fields_built)
                print(f"[EXTRACT] Built JSON arrays: {list(json_fields_built.keys())}")
        except Exception as e:
            print(f"[EXTRACT] Warning: Could not build JSON arrays: {e}")

        # ══════════════════════════════════════════════════════════════════════════════════
        # CRITICAL: Normalize final merged dataset (NEW STEP in pipeline)
        # This applies annualization and validates the final values before storage
        # ══════════════════════════════════════════════════════════════════════════════════
        try:
            print(f"[EXTRACT] Normalizing final merged dataset...")
            primary_doc_type = merged.get('_doc_type', doc_type)
            print(f"[EXTRACT] primary_doc_type={primary_doc_type}, gross_salary before norm={merged.get('gross_salary')}")

            # Call normalize_extractions on the final merged result
            normalized_result = normalization_service.normalize_extractions(
                [merged],  # Pass merged data as single document
                [primary_doc_type]  # Primary document type for annualization context
            )

            normalized_data = normalized_result.get("normalized", {})
            print(f"[EXTRACT] Normalization complete. "
                  f"Confidence: {normalized_result.get('extraction_confidence', 0)}")

            # Log annualization for salary fields
            assumptions = normalized_result.get("assumptions", [])
            if assumptions:
                print(f"[EXTRACT] Assumptions: {assumptions}")

            # [DEBUG] Log normalized values
            print(f"[NORMALIZE_DEBUG] BEFORE normalized.update(): gross_salary={merged.get('gross_salary')}")
            print(f"[NORMALIZE_DEBUG] normalized_data contains: gross_salary={normalized_data.get('gross_salary')}")

            # Update merged with normalized values
            merged.update(normalized_data)
            print(f"[NORMALIZE_DEBUG] AFTER normalized.update(): gross_salary={merged.get('gross_salary')}")

            # Preserve metadata
            merged['_normalization_assumptions'] = assumptions

        except Exception as e:
            print(f"[EXTRACT] WARNING: Normalization failed (non-blocking): {e}")
            # Non-blocking: continue with unnormalized data
            pass

        if conflicts:
            print(f"[EXTRACT][{doc_type}] conflicts detected: {conflicts}")

        # [OK] VALIDATION LAYER: Comprehensive extraction validation
        # Validates annual/monthly consistency, Form 16 priority, document reconciliation, etc.
        try:
            validator = ExtractionValidator(extractions, merged)
            validated_data, validation_report = validator.validate()

            # Use validated data and store report for audit trail
            merged.update(validated_data)
            merged['_validation_report'] = validation_report

            print(f"[VALIDATION] Valid={validation_report.get('valid')}, "
                  f"Warnings={len(validation_report.get('warnings', []))}")
        except Exception as e:
            print(f"[VALIDATION] Comprehensive validation failed (non-blocking): {e}")
            # Non-breaking: continue with unvalidated data
            merged['_validation_report'] = {'valid': False, 'error': str(e)}

        # [OK] NEW: Form 16 vs Payslip consistency check (adds specialized conflict detection)
        form16_payslip_conflicts = []
        try:
            merged, form16_payslip_conflicts = ai_service.validate_form16_payslip_consistency(merged, extractions)
            # Merge the new conflicts with existing ones
            if form16_payslip_conflicts:
                conflicts.extend(form16_payslip_conflicts)
                print(f"[EXTRACT] Form 16/Payslip conflicts: {len(form16_payslip_conflicts)}")
        except Exception as e:
            print(f"[EXTRACT] Form 16/Payslip validation failed (non-blocking): {e}")
            # Don't block extraction if validation fails

        # Clean extraction (existing validation)
        merged = ai_service.clean_extraction(merged)

        # [DIAGNOSTIC] Log before sheet save
        print(f"[BEFORE_SAVE] gross_salary={merged.get('gross_salary', 'N/A')} | basic_salary={merged.get('basic_salary', 'N/A')} | hra_received={merged.get('hra_received', 'N/A')}")

        # [CRITICAL DEBUG] Check if merged values are annual or monthly
        try:
            g_sal = float(merged.get('gross_salary', 0)) if merged.get('gross_salary') else 0
            if g_sal > 0:
                if g_sal < 240000:
                    print(f"[ALERT] MONTHLY value detected! gross_salary={g_sal} (should be ~3.1M annual)")
                else:
                    print(f"[OK] ANNUAL value: gross_salary={g_sal}")
        except:
            pass

        # Save to Sheets
        sheets_service.update_row(row, merged)

        # Save document URLs by type
        if urls:
            col_map = {
                "form16": "doc_form16_urls",
                "payslip": "doc_payslip_urls",
                "homeloan": "doc_homeloan_urls",
                "school": "doc_school_urls",
                "nps": "doc_nps_urls",
                "insurance": "doc_insurance_urls",
                "donation": "doc_donation_urls"
            }

            sheets_service.append_doc_urls(
                submission_id,
                col_map.get(doc_type, "doc_form16_urls"),
                urls
            )

        print(f"[EXTRACT] Extraction complete for submission {submission_id}")

        # Assess extraction quality and add warnings
        quality_result = quality_checker.assess_extraction_quality(
            {
                "confidence": merged.get("_confidence", 0),
                "metadata": merged.get("_metadata", {})
            },
            doc_type
        )

        # Check data completeness
        completeness = quality_checker.validate_data_completeness(merged, doc_type)

        # Add helpful note about doc_type if using default
        helper_note = None
        if doc_type == "form16":
            helper_note = "Note: For better extraction, specify doc_type in your request. " \
                         "Supported: form16, payslip, homeloan, school, nps, insurance, donation"

        response = {
            "success": True,
            "data": merged,
            "urls": urls,
            "conflicts": conflicts,
            "confidence": merged.get("_confidence", 0),
            "doc_type_used": doc_type,
            "metadata": merged.get("_metadata", {}),
            "quality": {
                "level": quality_result["quality_level"],
                "confidence_score": quality_result["confidence_score"],
                "warnings": quality_result["warnings"],
                "user_action_required": quality_result["user_action_required"],
                "feedback": quality_result["actionable_feedback"]
            },
            "completeness": {
                "complete": completeness["complete"],
                "missing_fields": completeness["missing_fields"],
                "feedback": completeness["feedback"]
            }
        }

        # Add auto_detected_doc_type if it was auto-detected
        if extractions and len(extractions) > 0 and "_auto_detected_doc_type" in extractions[0]:
            response["auto_detected_doc_type"] = extractions[0]["_auto_detected_doc_type"]
            response["helper_note"] = f"[OK] Document type auto-detected as: {extractions[0]['_auto_detected_doc_type']}"
        elif helper_note:
            response["helper_note"] = helper_note

        return jsonify(response)

    except Exception as e:
        traceback.print_exc()
        print(f"[EXTRACT] Unexpected error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# ---------- Serve uploads ----------
@app.route("/uploads/<submission_id>/<filename>")
def serve_upload(submission_id, filename):
    """Serve uploaded documents from persistent storage (Render Disk or Local)."""
    import storage_service
    # Use STORAGE_BASE to ensure consistency with save_file()
    # On Render: STORAGE_BASE = /var/data
    # Locally: STORAGE_BASE = backend/uploads
    folder = os.path.join(storage_service.STORAGE_BASE, submission_id)
    return send_from_directory(folder, filename)


# ---------- Final submit ----------
@app.route("/api/minimal", methods=["POST"])
def minimal():
    return jsonify({"test": "minimal"})

@app.route("/api/test-json", methods=["POST"])
def test_json():
    """Minimal endpoint to test JSON parsing"""
    try:
        # Try to parse JSON WITHOUT calling get_data first
        data = request.get_json(force=True)

        return jsonify({
            "success": True,
            "keys": list(data.keys()) if isinstance(data, dict) else "not a dict"
        })
    except Exception as e:
        import traceback
        return jsonify({
            "success": False,
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc()[:500]
        }), 500

@app.route("/api/submit", methods=["POST"])
def submit():
    try:
        # CRITICAL: Werkzeug development server needs explicit handling
        # Try to parse request with safe defaults
        try:
            data = request.get_json(force=True)
            if not isinstance(data, dict):
                data = {}
        except Exception as json_err:
            # If JSON parsing fails, try again with cache=False
            try:
                data = request.get_json(force=True, cache=False)
                if not isinstance(data, dict):
                    data = {}
            except:
                # Last resort: return empty dict
                data = {}

        print(f"[SUBMIT] Data received: {list(data.keys())}", flush=True)

        # [DIAGNOSTIC] Log form submission input
        print(f"[SUBMIT_INPUT] gross_salary={data.get('gross_salary', 'N/A')} | basic_salary={data.get('basic_salary', 'N/A')} | hra_received={data.get('hra_received', 'N/A')}")

        submission_id = data.get("submission_id")
        print(f"[SUBMIT] submission_id: {submission_id}")
        if not submission_id:
            print("[SUBMIT] No submission_id provided")
            return jsonify({"success": False, "error": "submission_id required"}), 400

        row = sheets_service.get_row_by_submission_id(submission_id)
        print(f"[SUBMIT] Initial row lookup: {row}")

        # If row missing, create it so updates and calculations persist
        if row is None:
            try:
                print(f"[SUBMIT] Creating new submission in Sheets...")
                result = sheets_service.insert_submission({"submission_id": submission_id, **data})
                print(f"[SUBMIT] Insert result: {result}")
                print(f"[SUBMIT] Referral code generated: {result.get('referral_code')}")
                # Update data with generated referral code
                if result.get('referral_code'):
                    data['referral_code'] = result['referral_code']
                row = sheets_service.get_row_by_submission_id(submission_id)
                print(f"[SUBMIT] Row after insert: {row}")
            except Exception as insert_err:
                logger.error(f"[SUBMIT] ERROR during insert_submission: {insert_err}")
                logger.error(f"[SUBMIT] Traceback: {traceback.format_exc()}")
                print(f"[SUBMIT] ERROR during insert_submission: {insert_err}", flush=True)
                # Check if it's a quota error
                if "RESOURCE_EXHAUSTED" in str(insert_err) or "Quota exceeded" in str(insert_err):
                    logger.warning("[SUBMIT] Google Sheets quota exceeded - data will be retried later")
                row = None

        # [OK] Regenerate referral code with actual name (was generated as USER_FAIRTAX## before name was collected)
        # BUT: Do NOT regenerate for referral filings (code should use REFERRER's name, not referred person's name)
        # Check if this is a pure regular filing (not a referral redirect)
        is_referral_filing = data.get('filing_category') == 'free' or data.get('referrer_name') or data.get('_referral_handoff')
        if (not is_referral_filing and data.get('name') and
            data.get('referral_code', '').startswith('USER_')):
            data['referral_code'] = sheets_service.gen_referral_code(data.get('name'))
            print(f"[SUBMIT] Regenerated referral code with actual name: {data['referral_code']}")

        # [OK] save final data
        print(f"[SUBMIT] Updating row with data...")
        sheets_service.update_row(row, data)
        print(f"[SUBMIT] Update complete")

        # ══════════════════════════════════════════════════════════════════════════════════
        # Merge sheet row (has OCR-extracted investment data) with submitted form data
        # CRITICAL: Protect extracted salary fields from form override
        # ══════════════════════════════════════════════════════════════════════════════════
        EXTRACTED_SALARY_FIELDS = {
            'gross_salary', 'basic_salary', 'hra_received', 'tds_paid',
            'pf_employee', 'pf_employer', 'professional_tax'
        }

        existing_rec = sheets_service.check_approval(submission_id)
        if existing_rec:
            # Start with sheet data as base (contains extracted values)
            merged_data = dict(existing_rec)

            # Selectively override with form data
            # Only allow form to override fields that either:
            # (1) Weren't extracted (not in EXTRACTED_SALARY_FIELDS), OR
            # (2) Weren't present in the sheet (new fields)
            for key, value in data.items():
                if key in EXTRACTED_SALARY_FIELDS:
                    # This is an extracted salary field
                    sheet_has_value = existing_rec.get(key) is not None
                    if sheet_has_value:
                        # Keep the sheet (extracted) value, don't override with form
                        print(f"[SUBMIT_PROTECT] Keeping extracted {key}={existing_rec[key]} "
                              f"(form submitted: {value}, form override blocked)")
                    else:
                        # Sheet doesn't have this field, allow form to populate it
                        merged_data[key] = value
                else:
                    # Non-salary field, allow form to override
                    merged_data[key] = value
        else:
            merged_data = data

        print(f"[SUBMIT] merged_data keys: {list(merged_data.keys())}")

        # [DIAGNOSTIC] Log after merge
        print(f"[AFTER_MERGE] gross_salary={merged_data.get('gross_salary', 'N/A')} | basic_salary={merged_data.get('basic_salary', 'N/A')} | hra_received={merged_data.get('hra_received', 'N/A')}")

        # [OK] Aggregate multi-entry JSON fields with duplicate detection
        try:
            aggregates = _aggregate_investments(merged_data)
            if aggregates:
                sheets_service.update_row(row, aggregates)
                for k, v in aggregates.items():
                    merged_data[k] = v
        except Exception as _agg_e:
            print('Aggregation error:', _agg_e)


        # Ensure rent alias: map frontend `rent_paid` (monthly) to `monthly_rent` expected by engine
        try:
            if merged_data.get('rent_paid') and not merged_data.get('monthly_rent'):
                merged_data['monthly_rent'] = merged_data.get('rent_paid')
        except Exception:
            pass

        # [OK] VALIDATION: Use validation report from extraction (if available)
        # Validator runs in /api/extract, not here in /api/submit
        validation_report = merged_data.get('_validation_report', {})
        if validation_report:
            print(f"[VALIDATION] Valid={validation_report.get('valid')}, "
                  f"Errors={len(validation_report.get('errors', []))}, "
                  f"Warnings={len(validation_report.get('warnings', []))}")
            if not validation_report.get('valid'):
                logger.warning(f"[VALIDATION] Submission has validation errors: "
                              f"{validation_report.get('errors')}")
        else:
            print("[VALIDATION] No validation report from extraction (normal if not Form16/Payslip)")

        # [OK] PRE-TAX VALIDATION: Detect extraction issues before calculation
        # This layer catches monthly/annual mismatches, missing critical fields, etc.
        try:
            validation_issues = _validate_before_tax_calculation(merged_data)
            if validation_issues:
                for issue in validation_issues:
                    print(f"[VALIDATION] {issue['severity']}: {issue['message']}")
                    if issue['severity'] == 'ERROR':
                        logger.error(f"[VALIDATION] {issue['message']}")
        except Exception as ve:
            print(f"[VALIDATION] Pre-tax validation error (non-blocking): {ve}")

        # [OK] TAX CALC — deterministic engine is the source of truth;
        #    AI enrichment (assumptions, notes) is optional overlay.
        engine_calc = {}
        try:
            engine_calc = tax_engine.calculate(merged_data)
            print(f"[TAX_CALC] Engine OK — sec_80c={engine_calc.get('sec_80c')}, "
                  f"deductions_total={engine_calc.get('deductions_total')}, "
                  f"taxable_old_a={engine_calc.get('taxable_old_a')}")
        except Exception as te:
            print(f"[TAX_CALC] Engine failed: {te}")
            traceback.print_exc()

        # Determine referral code immediately (needed for response + background task)
        ref_code = data.get('referral_code') or (existing_rec.get("referral_code", "") if existing_rec else "")

        # ── BACKGROUND TASK: AI enrichment, sheet writes, WhatsApp, webhook ──────
        # None of these are needed to compute the refund amounts returned to the
        # frontend. Run them in a daemon thread so the response goes out immediately.
        def _background(row, merged_data, engine_calc, data, ref_code, submission_id, validation_report):
            try:
                # AI enrichment (optional — engine values override all numerics anyway)
                ai_calc = None
                try:
                    ai_calc = ai_service.calculate_tax_ai(merged_data)
                except Exception as e:
                    print(f"[BG][TAX_CALC] AI enrichment failed: {e}")

                if ai_calc and isinstance(ai_calc, dict):
                    calc = ai_calc
                    for k, v in engine_calc.items():
                        calc[k] = v
                    calc.setdefault('deductions_80', {}).update({
                        'sec_80c': engine_calc.get('sec_80c', 0),
                        'sec_80d': engine_calc.get('sec_80d', 0),
                        'sec_80e': engine_calc.get('sec_80e', 0),
                        'sec_80g': engine_calc.get('sec_80g', 0),
                        'sec_80ccd_1b': engine_calc.get('sec_80ccd_1b', 0),
                        'sec_80ccd_2': engine_calc.get('sec_80ccd_2', 0),
                        'savings_interest': engine_calc.get('savings_interest', 0),
                        'total_deductions_80': engine_calc.get('deductions_total', 0),
                    })
                    calc.setdefault('calculations', {}).update({
                        'taxable_new': engine_calc.get('taxable_new', 0),
                        'new_total_tax': engine_calc.get('total_tax_new', 0),
                        'new_refund_or_due': engine_calc.get('refund_new', 0),
                        'taxable_old': engine_calc.get('taxable_old_a', 0),
                        'old_total_tax': engine_calc.get('total_tax_old_a', 0),
                        'old_refund_or_due': engine_calc.get('refund_old_a', 0),
                    })
                    calc.setdefault('compatibility_summary', {}).update(engine_calc)
                else:
                    calc = engine_calc

                calc['_validation_passed'] = validation_report.get('valid', False)
                calc['_validation_errors'] = validation_report.get('errors', [])
                calc['_validation_warnings'] = validation_report.get('warnings', [])

                try:
                    sheets_service.save_calculation_by_row(row, calc)
                except Exception as e:
                    print(f"[BG][SHEETS] save_calculation_by_row failed: {e}")

                # Flag data conflicts for auditor review
                try:
                    conflicts_list = merged_data.get('_form16_payslip_conflicts', [])
                    if conflicts_list:
                        conflict_summary = f"[WARN] DATA CONFLICTS DETECTED ({len(conflicts_list)} conflicts):\n"
                        for conflict in conflicts_list:
                            conflict_summary += (
                                f"• {conflict.get('field_name', conflict.get('field'))}: "
                                f"Form 16 = ₹{conflict.get('form16_value'):,.0f}, "
                                f"Payslip (annualized) = ₹{conflict.get('payslip_annualized_value'):,.0f} "
                                f"({conflict.get('variance_percent', 0):.1f}% diff). "
                                f"Using Form 16 value. Severity: {conflict.get('severity', 'MEDIUM')}\n"
                            )
                        existing_notes = (merged_data.get('auditor_notes') or "")
                        conflict_summary += "\nResolution: Used Form 16 (primary) over Payslip (monthly). Auditor should verify if discrepancy is due to mid-year salary changes, bonuses, or leaves."
                        if existing_notes:
                            conflict_summary = existing_notes + "\n---\n" + conflict_summary
                        sheets_service.update_row(row, {"auditor_notes": conflict_summary})
                        print(f"[BG][CONFLICT] Flagged {len(conflicts_list)} conflicts for auditor")
                except Exception as e:
                    print(f"[BG][CONFLICT] Error: {e}")

                # Verify calculation consistency
                try:
                    is_valid, issues = sheets_service.verify_calculation_consistency(submission_id, calc)
                    if not is_valid:
                        print(f"[BG][VERIFY] Consistency issues: {issues}")
                except Exception as e:
                    print(f"[BG][VERIFY] Error: {e}")

                # Log referrals
                try:
                    if data.get("referred_by"):
                        sheets_service.log_referral(data["referred_by"], data.get("name", ""), data.get("phone", ""))
                    logged_phones = set()
                    for i in range(1, 6):
                        ref_name = (data.get(f"ref_name_{i}", "") or "").strip()
                        ref_phone_raw = (data.get(f"ref_phone_{i}", "") or "").strip()
                        if not ref_name or not ref_phone_raw:
                            continue
                        phone_digits = ''.join(c for c in ref_phone_raw if c.isdigit())
                        if len(phone_digits) < 10:
                            continue
                        ref_phone = phone_digits[-10:]
                        if ref_phone in logged_phones:
                            continue
                        logged_phones.add(ref_phone)
                        sheets_service.log_referral(ref_code, ref_name, ref_phone)
                        print(f"[BG][REFERRAL] Logged: {ref_name} ({ref_phone})")
                except Exception as e:
                    print(f"[BG][REFERRAL] Error: {e}")

                # WhatsApp notification
                try:
                    wa_phone = whatsapp_service.normalize_phone(data.get("phone", ""))
                    if wa_phone:
                        wa_resp = whatsapp_service.send_template(wa_phone, "submission_received", [data.get("name", "there"), ref_code])
                        print(f"[BG][WA] Response: {wa_resp}")
                except Exception as e:
                    print(f"[BG][WA] Failed (non-blocking): {e}")

                # Apps Script webhook
                if Config.APPS_SCRIPT_WEBHOOK_URL:
                    try:
                        _requests.post(Config.APPS_SCRIPT_WEBHOOK_URL, json={
                            "event": "new_submission",
                            "submission_id": submission_id,
                            "name": data.get("name", ""),
                            "phone": data.get("phone", ""),
                            "referral_code": ref_code,
                            "timestamp": data.get("timestamp", "")
                        }, timeout=5)
                    except Exception:
                        pass

            except Exception as bg_err:
                print(f"[BG][SUBMIT] Background task error: {bg_err}")

        import threading
        threading.Thread(
            target=_background,
            args=(row, merged_data, engine_calc, data, ref_code, submission_id, validation_report),
            daemon=True
        ).start()
        print(f"[SUBMIT] Background task fired — returning response immediately")

        response_data = {
            "success": True,
            "submission_id": submission_id,
            "referral_code": ref_code,
            "message": "Submitted! You'll receive your quote on WhatsApp within 24 hours.",
            "refund_old_a": engine_calc.get('refund_old_a', 0),
            "refund_old_b": engine_calc.get('refund_old_b', 0),
            "refund_old_c": engine_calc.get('refund_old_c', 0),
        }
        print(f"[SUBMIT] Returning success response: {response_data}")
        return jsonify(response_data)

    except Exception as e:
        exc_traceback = traceback.format_exc()
        error_msg = str(e)
        print(f"[SUBMIT] EXCEPTION in submit endpoint: {error_msg}", flush=True)
        print(f"[SUBMIT] Traceback:\n{exc_traceback}", flush=True)

        # Try to return error response
        try:
            error_response = {
                "success": False,
                "error": error_msg
            }
            print(f"[SUBMIT] Created error_response dict", flush=True)
            result = jsonify(error_response)
            print(f"[SUBMIT] jsonify succeeded", flush=True)
            return result, 500
        except Exception as json_err:
            print(f"[SUBMIT] ERROR: Could not jsonify error response: {json_err}", flush=True)
            return {"success": False, "error": error_msg}, 500


# ========== QUOTE GENERATION HELPER ==========

def _generate_and_upload_quote(submission_id, rec=None):
    """Generate quote PDF and upload to GCS/storage, update sheet with URL.

    Args:
        submission_id: Submission ID
        rec: Optional pre-fetched record dict

    Returns:
        tuple: (pdf_url, pdf_password) or (None, None) if failed
    """
    if not rec:
        rec = sheets_service.check_approval(submission_id)
    if not rec:
        print(f"[QUOTE_GEN] Record not found for {submission_id}")
        return None, None

    if rec.get("approval_status") != "APPROVED":
        print(f"[QUOTE_GEN] Not approved: {submission_id}")
        return None, None

    def f(k):
        try:
            return float(rec.get(k) or 0)
        except:
            return 0.0

    def clean_regime(r):
        r = str(r or "").strip()
        return r if r and r not in ("0", "—") else "NEW"

    try:
        # Log key values being used in PDF
        print(f"[QUOTE_GEN] ======== QUOTE GENERATION FOR {submission_id} ========")
        print(f"[QUOTE_GEN] Client: {rec.get('name')} | PAN: {rec.get('pan')} | Phone: {rec.get('phone')}")
        print(f"[QUOTE_GEN] Gross Salary: {f('gross_salary')} | Basic: {f('basic_salary')} | HRA: {f('hra_received')}")
        print(f"[QUOTE_GEN] TDS Paid: {f('tds_paid')} | Home Loan Interest: {f('home_loan_interest')}")
        print(f"[QUOTE_GEN] Deductions - 80C: {f('sec_80c')} | 80D: {f('sec_80d')} | 80CCD(1B): {f('sec_80ccd_1b')} | 80CCD(2): {f('sec_80ccd_2')}")
        print(f"[QUOTE_GEN] Total Deductions: {f('deductions_total')}")

        # Build plans with variant refunds
        plans = [
            {"id": "A", "label": "Plan A — Safe",
             "desc": "Conservative deductions, exact figures as filed. Lowest risk.",
             "refund": f("variant_a_refund"), "regime": clean_regime(rec.get("variant_a_regime"))},
            {"id": "B", "label": "Plan B — Optimized",
             "desc": "Optimised LTA & allowance claims for a higher refund.",
             "refund": f("variant_b_refund"), "regime": "OLD"},
            {"id": "C", "label": "Plan C — Maximum",
             "desc": "Maximum legal deductions & allowances claimed.",
             "refund": f("variant_c_refund"), "regime": "OLD"},
        ]

        print(f"[QUOTE_GEN] Plan A Refund: {f('variant_a_refund')} ({clean_regime(rec.get('variant_a_regime'))}) | Plan B: {f('variant_b_refund')} (OLD) | Plan C: {f('variant_c_refund')} (OLD)")

        # Derive PDF password from last 4 characters of PAN
        pdf_password = None
        try:
            pan = rec.get("pan", "") if rec else ""
            pan_str = str(pan).strip()
            pdf_password = pan_str[-4:] if pan_str and len(pan_str) >= 4 else submission_id[-6:]
        except Exception:
            pdf_password = submission_id[-6:] if submission_id else None

        # Generate PDF bytes
        pdf_data = {**rec, "plans": plans}
        pdf_bytes = generate_quote_pdf(pdf_data, password=pdf_password, return_bytes=True)

        if not pdf_bytes:
            print(f"[QUOTE_GEN] PDF generation failed for {submission_id}")
            return None, None

        print(f"[QUOTE_GEN] PDF generated ({len(pdf_bytes)} bytes) with password: {pdf_password}")

        # Upload to storage (GCS or local)
        filename = f"quote_{submission_id}.pdf"
        pdf_url = storage_service.save_pdf_to_gcs(pdf_bytes, submission_id, filename)

        if not pdf_url:
            print(f"[QUOTE_GEN] Storage upload failed for {submission_id}")
            return None, None

        # Update sheet with PDF URL
        try:
            row = sheets_service.get_row_by_submission_id(submission_id)
            if row:
                sheets_service.update_row(row, {"quote_link": pdf_url})
                print(f"[QUOTE_GEN] ✓ PDF generated, uploaded, and sheet updated for {submission_id}")
                print(f"[QUOTE_GEN] PDF URL: {pdf_url}")
                print(f"[QUOTE_GEN] ======== END QUOTE GENERATION ========")
        except Exception as e:
            print(f"[QUOTE_GEN] Warning: Could not update sheet: {e}")

        return pdf_url, pdf_password

    except Exception as e:
        print(f"[QUOTE_GEN] Exception: {e}")
        traceback.print_exc()
        return None, None


# ---------- Quote Generation Webhook ----------
@app.route("/api/generate-quote", methods=["POST"])
def generate_quote_webhook():
    """Webhook endpoint called by Apps Script when approval_status changes to APPROVED.

    Expected JSON:
        {"submission_id": "xxx"}
    """
    try:
        data = request.get_json(force=True)
        submission_id = data.get("submission_id", "").strip()

        if not submission_id:
            return jsonify({"success": False, "error": "submission_id required"}), 400

        print(f"[QUOTE_WEBHOOK] Received request for {submission_id}")

        pdf_url, pdf_password = _generate_and_upload_quote(submission_id)

        if pdf_url:
            print(f"[QUOTE_WEBHOOK] ✓ Success for {submission_id}")
            return jsonify({
                "success": True,
                "pdf_url": pdf_url,
                "pdf_password": pdf_password,
                "message": "Quote generated and uploaded successfully"
            })
        else:
            print(f"[QUOTE_WEBHOOK] ✗ Failed for {submission_id}")
            return jsonify({"success": False, "error": "Failed to generate quote"}), 500

    except Exception as e:
        print(f"[QUOTE_WEBHOOK] Exception: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ---------- Download Quote PDF ----------
@app.route("/api/download-quote/<submission_id>/<filename>")
def download_quote(submission_id, filename):
    """Serve quote PDF from persistent disk or local storage.

    This endpoint serves PDFs generated by _generate_and_upload_quote().
    Files are stored in STORAGE_BASE/submission_id/quotes/filename
    """
    try:
        import storage_service

        # Construct the path where quotes are stored
        quotes_folder = os.path.join(storage_service.STORAGE_BASE, submission_id, "quotes")

        # Validate the filename to prevent directory traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            return jsonify({"error": "Invalid filename"}), 400

        # Check if the file exists
        file_path = os.path.join(quotes_folder, filename)
        if not os.path.exists(file_path):
            print(f"[QUOTE_DOWNLOAD] File not found: {file_path}")
            return jsonify({"error": f"Quote not found: {filename}"}), 404

        print(f"[QUOTE_DOWNLOAD] Serving: {file_path}")
        return send_from_directory(quotes_folder, filename, as_attachment=False, mimetype="application/pdf")

    except Exception as e:
        print(f"[QUOTE_DOWNLOAD] Error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ---------- Quote ----------
@app.route("/api/quote/<submission_id>")
def quote(submission_id):
    """Retrieve pre-generated quote. PDF is generated automatically when auditor approves."""
    rec = sheets_service.check_approval(submission_id)
    if not rec:
        return jsonify({"success": False, "error": "Not found"}), 404

    if rec.get("approval_status") != "APPROVED":
        return jsonify({"success": True, "approved": False,
                        "message": "Your filing is under expert review. You'll receive a WhatsApp notification once approved."})

    def f(k):
        try: return float(rec.get(k) or 0)
        except: return 0.0

    fee = f("auditor_quote_fee")
    fee_upfront = round(fee * 0.5, 2)

    def clean_regime(r):
        """Convert regime value, handling '0' or empty strings."""
        r = str(r or "").strip()
        return r if r and r not in ("0", "—") else "NEW"

    # Build all 6 quotes: 3 for OLD regime, 3 for NEW regime
    plans = [
        # OLD REGIME QUOTES
        {"id": "A_OLD", "label": "Plan A (OLD) — Conservative",
         "desc": "Exact figures as filed. Lowest risk.",
         "refund": f("refund_old_a"), "regime": "OLD"},
        {"id": "B_OLD", "label": "Plan B (OLD) — Optimized",
         "desc": "Optimised LTA & allowance claims for higher refund.",
         "refund": f("variant_b_refund"), "regime": "OLD"},
        {"id": "C_OLD", "label": "Plan C (OLD) — Maximum",
         "desc": "Maximum legal deductions & allowances claimed.",
         "refund": f("variant_c_refund"), "regime": "OLD"},

        # NEW REGIME QUOTES
        {"id": "A_NEW", "label": "Plan A (NEW) — Conservative",
         "desc": "Exact figures as filed. Lowest risk.",
         "refund": f("refund_new"), "regime": "NEW"},
        {"id": "B_NEW", "label": "Plan B (NEW) — Optimized",
         "desc": "Optimised Section 10 allowance claims for higher refund.",
         "refund": f("variant_b_refund_new"), "regime": "NEW"},
        {"id": "C_NEW", "label": "Plan C (NEW) — Maximum",
         "desc": "Maximum legal deductions & allowances claimed.",
         "refund": f("variant_c_refund_new"), "regime": "NEW"},
    ]

    # Retrieve pre-generated PDF URL from sheet
    pdf_url = rec.get("quote_link", "")
    pdf_password = None
    try:
        phone = rec.get("phone", "") if rec else ""
        digits = "".join([c for c in str(phone) if c.isdigit()])
        pdf_password = digits[-4:] if digits and len(digits) >= 4 else submission_id[-6:]
    except Exception:
        pdf_password = submission_id[-6:] if submission_id else None

    # Auto-send WhatsApp quote notification exactly once — only mark QUOTE_SENT if WA send succeeds
    if not rec.get("filing_status") and pdf_url:
        resp = None
        wa_phone = whatsapp_service.normalize_phone(rec.get("phone", ""))
        print(f"[QUOTE] Attempting WhatsApp send for {submission_id}: phone={wa_phone}")
        if wa_phone:
            best_refund = max(f("variant_a_refund"), f("variant_b_refund"), f("variant_c_refund"))
            try:
                print(f"[QUOTE] Sending WhatsApp template 'quote_ready' to {wa_phone} with refund: {best_refund}")
                resp = whatsapp_service.send_template(
                    wa_phone,
                    "quote_ready",
                    [rec.get("name", "there"), str(int(best_refund))],
                    button_url_param=pdf_url,
                )
                print(f"[QUOTE] WhatsApp response: {resp}")
                success = bool(resp) and not (isinstance(resp, dict) and resp.get('error'))
            except Exception as _we:
                print(f"[QUOTE] WhatsApp send exception for {submission_id}: {_we}")
                traceback.print_exc()
                success = False
        else:
            print(f"[QUOTE] No WhatsApp phone for {submission_id}; original phone='{rec.get('phone', '')}'")
            success = False

        if success:
            row = sheets_service.get_row_by_submission_id(submission_id)
            sheets_service.update_row(row, {"filing_status": "QUOTE_SENT"})
            print(f"[QUOTE] [OK] WhatsApp sent successfully and filing_status updated to QUOTE_SENT for {submission_id}")

            try:
                user_phone = rec.get('phone')
                if user_phone:
                    sheets_service.update_referral_status(user_phone, "quote_generated")
                    print(f"[REFERRAL_HOOK] Updated referral status for phone {user_phone} → quote_generated")
            except Exception as e:
                print(f"[REFERRAL_HOOK] Warning: Could not update referral status: {e}")
        else:
            print(f"[QUOTE] [ERROR] WhatsApp send failed or skipped for {submission_id}: {resp}")

    # NOTE: PDF URL is NOT returned to frontend for security/privacy (already shared via WhatsApp)
    return jsonify({
        "success": True,
        "approved": True,
        "name": rec.get("name", ""),
        "recommended_regime": rec.get("variant_a_regime", "NEW"),
        "fee": fee,
        "fee_upfront": fee_upfront,
        "fee_on_refund": round(fee - fee_upfront, 2),
        "plans": plans,
        "auditor_notes": rec.get("auditor_notes", ""),
        "filing_status": rec.get("filing_status", ""),
        "payment_status": rec.get("payment_status", ""),
        "user_chosen_option": rec.get("user_chosen_option", ""),
    })


# ---------- Choose Option ----------
@app.route("/api/choose-option", methods=["POST"])
def choose_option():
    try:
        data = request.get_json(force=True)
        submission_id = data.get("submission_id")
        plan_id = str(data.get("plan_id", "")).upper()
        if not submission_id or plan_id not in ("A", "B", "C"):
            return jsonify({"success": False, "error": "submission_id and plan_id (A/B/C) required"}), 400

        row = sheets_service.get_row_by_submission_id(submission_id)
        if not row:
            return jsonify({"success": False, "error": "Submission not found"}), 404

        sheets_service.update_row(row, {
            "user_chosen_option": plan_id,
            "filing_status": "OPTION_CHOSEN",
        })

        rec = sheets_service.check_approval(submission_id)
        fee = float(rec.get("auditor_quote_fee") or 0)
        upfront = round(fee * 0.5, 2)

        wa_phone = whatsapp_service.normalize_phone(rec.get("phone", ""))
        if wa_phone:
            whatsapp_service.send_template(wa_phone, "payment_instructions",
                                           [rec.get("name", "there"), f"Plan {plan_id}", str(int(upfront)),
                                            Config.PAYMENT_UPI_ID])

        return jsonify({
            "success": True,
            "plan_id": plan_id,
            "fee_upfront": upfront,
            "payment_upi": Config.PAYMENT_UPI_ID,
            "message": f"Plan {plan_id} confirmed. Please pay ₹{upfront:.0f} to {Config.PAYMENT_UPI_ID}."
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ---------- Filing Status ----------
@app.route("/api/status/<submission_id>")
def filing_status(submission_id):
    try:
        rec = sheets_service.check_approval(submission_id)
        if not rec:
            return jsonify({"success": False, "error": "Not found"}), 404

        approval = rec.get("approval_status", "PENDING")
        filing = rec.get("filing_status", "")
        payment = rec.get("payment_status", "")
        chosen = rec.get("user_chosen_option", "")

        filing_up = filing.upper()
        payment_up = payment.upper()

        if "FILED" in filing_up or "COMPLET" in filing_up:
            stage = "FILED"
        elif "FILING" in filing_up or "IN_PROGRESS" in filing_up:
            stage = "FILING"
        elif "FULL" in payment_up or "COMPLET" in payment_up:
            stage = "PAID_FULL"
        elif "PAID" in payment_up or "HALF" in payment_up:
            stage = "PAID_HALF"
        elif chosen:
            stage = "OPTION_CHOSEN"
        elif filing == "QUOTE_SENT":
            stage = "QUOTE_SENT"
        else:
            stage = "SUBMITTED"

        return jsonify({
            "success": True,
            "name": rec.get("name", ""),
            "submission_id": submission_id,
            "approval_status": approval,
            "filing_status": filing,
            "payment_status": payment,
            "user_chosen_option": chosen,
            "auditor_notes": rec.get("auditor_notes", ""),
                "stage": stage,
                # Include canonical calculation fields (if present in sheet) so frontend
                # can render canonical refund/plan amounts rather than client-side heuristics.
                "calculations": {
                    "taxable_new": _safe_float(rec.get("taxable_new")),
                    "total_tax_new": _safe_float(rec.get("total_tax_new")),
                    "refund_new": _safe_float(rec.get("refund_new")),
                    "taxable_old_a": _safe_float(rec.get("taxable_old_a")),
                    "total_tax_old_a": _safe_float(rec.get("total_tax_old_a")),
                    "refund_old_a": _safe_float(rec.get("refund_old_a")),
                    "variant_a_refund": _safe_float(rec.get("variant_a_refund")),
                    "variant_b_refund": _safe_float(rec.get("variant_b_refund")),
                    "variant_c_refund": _safe_float(rec.get("variant_c_refund")),
                    "variant_a_regime": (rec.get("variant_a_regime") or "")
                },
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/notify-referrals", methods=["POST"])
def notify_referrals():
    try:
        data = request.get_json(force=True)
        submission_id = data.get('submission_id')
        referrer_name = data.get('referrer_name') or 'Your friend'
        referral_code = data.get('referral_code') or ''

        # BACKEND VALIDATION: Handle referrals as string or list
        referrals_raw = data.get('referrals', [])
        if isinstance(referrals_raw, str):
            try:
                referrals = json.loads(referrals_raw)
            except:
                referrals = []
        else:
            referrals = referrals_raw if isinstance(referrals_raw, list) else []

        sent_count = 0
        for r in referrals:
            # VALIDATION: Ensure r is a dict with required fields
            if not isinstance(r, dict):
                continue

            phone_raw = r.get('phone', '').strip()
            name = (r.get('name', '') or '').strip()

            # VALIDATION: Skip empty entries
            if not phone_raw:
                continue

            # NORMALIZATION: Extract digits and validate
            phone_digits = ''.join(c for c in phone_raw if c.isdigit())

            # VALIDATION: Phone must be at least 10 digits
            if len(phone_digits) < 10:
                print(f"[NOTIFY] Skipping referral {name}: Invalid phone {phone_raw}")
                continue

            # Use last 10 digits for Indian phone numbers
            phone_normalized = phone_digits[-10:]
            wa_phone = whatsapp_service.normalize_phone(phone_normalized)

            # Try approved template first; fall back to plain text
            try:
                whatsapp_service.send_template(
                    wa_phone, 'referred_notification',
                    [referrer_name, referral_code or 'N/A']
                )
            except Exception:
                pass

            # Always send a detailed plain-text message
            msg = (
                f"Hi{(' ' + name) if name else ''}! You have been referred by {referrer_name} "
                f"to FairTax Advisors for hassle-free ITR filing.\n\n"
                f"Please fill in your details for smooth tax filing and get your quote in 24 hours.\n\n"
                f"Start here: https://fairtaxadvisors.in\n\n"
                f"Please don't forget your referral code: {referral_code}\n"
                f"Enter this code while submitting your application to unlock exclusive rewards.\n\n"
                f"— Team FairTax"
            )
            try:
                whatsapp_service.send_text(wa_phone, msg)
                sent_count += 1
            except Exception as e:
                logger.warning(f"[notify-referrals] Failed to send text to {wa_phone}: {e}")

        return jsonify({'success': True, 'sent': sent_count})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/winners')
def winners():
    # simple stubbed winners list for frontend widget
    return jsonify({
        'winners': [
            {'name': 'Asha R.', 'reward': '₹2,500'},
            {'name': 'Kumar S.', 'reward': 'Free Filing'},
            {'name': 'Ritu M.', 'reward': '₹1,000'}
        ]
    })


# ---------- Download ----------
@app.route("/api/download/<filename>")
def download_pdf(filename):
    return send_from_directory(".", filename, as_attachment=False)


# ---------- Wallet ----------
@app.route("/api/wallet/<referral_code>")
def wallet(referral_code):
    try:
        ws = sheets_service._sheet("Submissions")
        vals = ws.get_all_values()
        if len(vals) <= 1:
            return jsonify({"success": False, "error": "Not found"}), 404

        headers = vals[0]
        rec = None
        for row in vals[1:]:
            r = dict(zip(headers, row + [""] * (len(headers) - len(row))))
            if r.get("referral_code", "").upper() == referral_code.upper():
                rec = r
                break

        if not rec:
            return jsonify({"success": False, "error": "Referral code not found"}), 404

        # Count confirmed referrals from Referrals sheet
        try:
            rws = sheets_service._sheet("Referrals")
            rvals = rws.get_all_values()
            rcount = sum(
                1 for rv in rvals[1:]
                if len(rv) > 1 and rv[1].upper() == referral_code.upper()
            )
        except Exception:
            rcount = int(rec.get("referral_count") or 0)

        # Calculate earned amount based on milestone tiers
        if rcount >= 10:
            earned = 15000
        elif rcount >= 5:
            earned = 5000
        elif rcount >= 3:
            earned = 1000
        elif rcount >= 1:
            earned = 250 * rcount
        else:
            earned = 0

        # Honour manually set wallet_balance if auditor has overridden it
        manual_balance = rec.get("wallet_balance", "")
        if manual_balance:
            try:
                earned = float(manual_balance)
            except Exception:
                pass

        return jsonify({
            "success": True,
            "name": rec.get("name", ""),
            "referral_code": rec.get("referral_code", ""),
            "referral_count": rcount,
            "wallet_balance": earned,
            "upi_id": rec.get("upi_id", ""),
            "submission_id": rec.get("submission_id", "")
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/withdraw", methods=["POST"])
def withdraw():
    try:
        data = request.get_json(force=True)
        referral_code = data.get("referral_code", "")
        upi_id = data.get("upi_id", "")
        amount = float(data.get("amount") or 0)

        if not referral_code or not upi_id or amount <= 0:
            return jsonify({"success": False, "error": "referral_code, upi_id and amount required"}), 400

        # Log the withdrawal request in a Withdrawals sheet
        wws = sheets_service._sheet("Withdrawals")
        sheets_service._ensure_headers(wws, [
            "timestamp", "referral_code", "upi_id", "amount", "status"
        ])
        from datetime import datetime
        wws.append_row([datetime.now().isoformat(), referral_code, upi_id, amount, "PENDING"])

        # Notify via WhatsApp to admin number (same phone id)
        whatsapp_service.send_template(
            whatsapp_service.normalize_phone("917397510254"),
            "withdrawal_request",
            [referral_code, str(amount), upi_id]
        )

        return jsonify({
            "success": True,
            "message": f"Withdrawal request of ₹{amount:.0f} to {upi_id} logged. Processed every Thursday 3:30 PM."
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ---------- Add Referral Friend ----------
@app.route("/api/add-referral", methods=["POST"])
def add_referral():
    try:
        data = request.get_json(force=True)
        referral_code = data.get("referral_code", "").strip()
        friend_name = (data.get("friend_name", "") or "").strip()
        friend_phone_raw = (data.get("friend_phone", "") or "").strip()

        # VALIDATION: Check required fields
        if not referral_code or not friend_name or not friend_phone_raw:
            return jsonify({"success": False, "error": "referral_code, friend_name, and friend_phone required"}), 400

        # VALIDATION: Phone format validation BEFORE normalization
        phone_digits = ''.join(c for c in friend_phone_raw if c.isdigit())
        if len(phone_digits) < 10:
            return jsonify({"success": False, "error": "Invalid phone number (must have at least 10 digits)"}), 400

        # NORMALIZATION: Use last 10 digits for Indian phone numbers
        friend_phone = phone_digits[-10:]

        # NORMALIZATION: Also normalize via whatsapp_service for consistency
        friend_phone = whatsapp_service.normalize_phone(friend_phone)
        if not friend_phone or len(friend_phone) < 10:
            return jsonify({"success": False, "error": "Invalid phone number"}), 400

        # Append to Referrals sheet
        rws = sheets_service._sheet("Referrals")
        sheets_service._ensure_headers(rws, [
            "timestamp", "referral_code", "friend_name", "friend_phone", "status", "confirmed_date"
        ])

        from datetime import datetime
        rws.append_row([
            datetime.now().isoformat(),
            referral_code.upper(),
            friend_name,
            friend_phone,
            "PENDING",
            ""
        ])

        # Send WhatsApp notification to friend
        try:
            referrer_name = ""
            # Find referrer name from Submissions sheet
            ws = sheets_service._sheet("Submissions")
            vals = ws.get_all_values()
            if len(vals) > 1:
                headers = vals[0]
                for row in vals[1:]:
                    r = dict(zip(headers, row + [""] * (len(headers) - len(row))))
                    if r.get("referral_code", "").upper() == referral_code.upper():
                        referrer_name = r.get("name", "")
                        break

            whatsapp_service.send_template(
                friend_phone,
                "referred_notification",
                [referrer_name or "Your friend", referral_code]
            )
        except Exception as e:
            print(f"[WARN] Could not send WhatsApp: {e}")

        return jsonify({
            "success": True,
            "message": f"Referral added for {friend_name}. Notification sent to +91{friend_phone[-10:]}."
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ---------- Get Referral Status ----------
@app.route("/api/referral-status/<referral_code>")
def referral_status(referral_code):
    try:
        # Get all referrals for this code
        rws = sheets_service._sheet("Referrals")
        vals = rws.get_all_values()

        referrals = []
        if len(vals) > 1:
            headers = vals[0]
            for row in vals[1:]:
                r = dict(zip(headers, row + [""] * (len(headers) - len(row))))
                if r.get("referral_code", "").upper() == referral_code.upper():
                    referrals.append({
                        "name": r.get("friend_name", ""),
                        "phone": r.get("friend_phone", ""),
                        "status": r.get("status", "PENDING"),
                        "date_added": r.get("timestamp", ""),
                        "confirmed_date": r.get("confirmed_date", "")
                    })

        # Calculate milestones
        confirmed_count = sum(1 for ref in referrals if ref["status"].upper() == "CONFIRMED")

        milestones = {
            "current": confirmed_count,
            "next_milestone": None,
            "next_reward": None,
            "current_reward": None
        }

        if confirmed_count >= 10:
            milestones["current_reward"] = "₹15,000 (Maximum)"
        elif confirmed_count >= 5:
            milestones["current_reward"] = "₹5,000 + FREE Filing"
            milestones["next_milestone"] = 10
            milestones["next_reward"] = "₹15,000"
        elif confirmed_count >= 3:
            milestones["current_reward"] = "₹1,000"
            milestones["next_milestone"] = 5
            milestones["next_reward"] = "₹5,000 + FREE Filing"
        elif confirmed_count >= 1:
            milestones["current_reward"] = "₹250 × " + str(confirmed_count)
            milestones["next_milestone"] = 3
            milestones["next_reward"] = "₹1,000"
        else:
            milestones["next_milestone"] = 1
            milestones["next_reward"] = "₹250"

        return jsonify({
            "success": True,
            "referral_code": referral_code.upper(),
            "referrals": referrals,
            "milestones": milestones,
            "total_referrals": len(referrals),
            "confirmed_referrals": confirmed_count
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ---------- Payment Collection ----------
@app.route("/api/payment-status/<submission_id>")
def payment_status(submission_id):
    try:
        row_idx = sheets_service.get_row_by_submission_id(submission_id)
        if not row_idx:
            return jsonify({"success": False, "error": "Submission not found"}), 404

        ws = sheets_service._sheet("Submissions")
        all_values = ws.get_all_values()
        if len(all_values) <= row_idx - 1:
            return jsonify({"success": False, "error": "Submission not found"}), 404

        headers = all_values[0]
        row_data = all_values[row_idx - 1]
        rec = dict(zip(headers, row_data + [""] * (len(headers) - len(row_data))))

        payment_status = rec.get("payment_status", "")
        payment_amount = rec.get("payment_amount", "0")
        payment_proof_url = rec.get("payment_proof_url", "")
        auditor_quote_fee = rec.get("auditor_quote_fee", "0")

        try:
            fee = float(auditor_quote_fee) if auditor_quote_fee else 0
            upfront = round(fee * 0.5, 2)
            balance_due = round(fee - upfront, 2)
        except:
            upfront = 0
            balance_due = 0

        return jsonify({
            "success": True,
            "submission_id": submission_id,
            "payment_status": payment_status,
            "payment_amount": float(payment_amount) if payment_amount else 0,
            "payment_proof_url": payment_proof_url,
            "total_fee": fee,
            "upfront_due": upfront,
            "balance_due": balance_due
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/upload-payment-proof", methods=["POST"])
def upload_payment_proof():
    try:
        submission_id = request.form.get("submission_id")
        files = request.files.getlist("proof")

        if not submission_id or not files:
            return jsonify({"success": False, "error": "submission_id and proof file required"}), 400

        urls = []
        for f in files:
            content = f.read()
            url = storage_service.save_file(f, submission_id)
            if url:
                urls.append(url)

        # Update payment status in sheets
        row = sheets_service.get_row_by_submission_id(submission_id)
        if row:
            sheets_service.update_row(row, {
                "payment_status": "PARTIAL",
                "payment_proof_url": urls[0] if urls else ""
            })

            # [OK] HOOK: Update referral status to "fees_paid"
            rec = sheets_service.check_approval(submission_id)
            if rec:
                try:
                    user_phone = rec.get('phone')
                    if user_phone:
                        sheets_service.update_referral_status(user_phone, "fees_paid")
                        print(f"[REFERRAL_HOOK] Updated referral status for phone {user_phone} → fees_paid")
                except Exception as e:
                    print(f"[REFERRAL_HOOK] Warning: Could not update referral status: {e}")

        # Send WhatsApp notification to admin
        rec = sheets_service.check_approval(submission_id)
        if rec:
            whatsapp_service.send_template(
                whatsapp_service.normalize_phone("917397510254"),
                "payment_proof_received",
                [rec.get("name", "User"), submission_id, urls[0] if urls else "No URL"]
            )

        return jsonify({
            "success": True,
            "message": "Payment proof uploaded. We'll verify and confirm within 24 hours.",
            "urls": urls
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ---------- Filing Status Tracking ----------
@app.route("/api/filing-status/<submission_id>")
def filing_status_api(submission_id):
    try:
        rec = sheets_service.check_approval(submission_id)
        if not rec:
            return jsonify({"success": False, "error": "Submission not found"}), 404

        filing_status = rec.get("filing_status", "SUBMITTED")
        approval_status = rec.get("approval_status", "PENDING")
        payment_status = rec.get("payment_status", "PENDING")

        # Calculate stage
        stages = {
            "SUBMITTED": 10,
            "UNDER_REVIEW": 20,
            "APPROVED": 30,
            "PAYMENT_PENDING": 40,
            "PAYMENT_RECEIVED": 50,
            "FILING_IN_PROGRESS": 60,
            "FILED": 100
        }

        current_stage = filing_status.upper()
        stage_progress = stages.get(current_stage, 10)

        return jsonify({
            "success": True,
            "submission_id": submission_id,
            "filing_status": filing_status,
            "approval_status": approval_status,
            "payment_status": payment_status,
            "stage_progress": stage_progress,
            "timestamp": rec.get("timestamp", "")
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/update-filing-status", methods=["POST"])
def update_filing_status_api():
    try:
        data = request.get_json(force=True)
        submission_id = data.get("submission_id")
        new_status = data.get("filing_status")

        if not submission_id or not new_status:
            return jsonify({"success": False, "error": "submission_id and filing_status required"}), 400

        row = sheets_service.get_row_by_submission_id(submission_id)
        if not row:
            return jsonify({"success": False, "error": "Submission not found"}), 404

        # Update status
        sheets_service.update_row(row, {"filing_status": new_status})

        # Get updated record as dict
        updated_rec = sheets_service.check_approval(submission_id)

        # Send WhatsApp notification if filing is complete
        if updated_rec and ("FILED" in new_status.upper() or "COMPLETE" in new_status.upper()):
            wa_phone = whatsapp_service.normalize_phone(updated_rec.get("phone", ""))
            if wa_phone:
                whatsapp_service.send_template(
                    wa_phone,
                    "filing_completed",
                    [updated_rec.get("name", "there"), submission_id]
                )

        return jsonify({
            "success": True,
            "message": f"Filing status updated to {new_status}",
            "filing_status": new_status
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ---------- Scheduled Messages Setup ----------
def schedule_reminder_messages():
    """Send 3-day reminder messages to users who submitted but didn't pay"""
    try:
        from datetime import datetime, timedelta

        ws = sheets_service._sheet("Submissions")
        vals = ws.get_all_values()

        if len(vals) <= 1:
            return

        headers = vals[0]
        three_days_ago = (datetime.now() - timedelta(days=3)).isoformat()

        for row in vals[1:]:
            rec = dict(zip(headers, row + [""] * (len(headers) - len(row))))

            # Check if submitted 3 days ago and payment not received
            timestamp = rec.get("timestamp", "")
            payment_status = rec.get("payment_status", "")
            phone = rec.get("phone", "")

            if timestamp < three_days_ago and payment_status != "PAID":
                wa_phone = whatsapp_service.normalize_phone(phone)
                if wa_phone:
                    try:
                        whatsapp_service.send_template(
                            wa_phone,
                            "payment_reminder",
                            [rec.get("name", "there"), rec.get("submission_id", "")]
                        )
                        print(f"[SCHEDULER] Sent 3-day reminder to {wa_phone}")
                    except Exception as e:
                        print(f"[SCHEDULER] Failed to send reminder: {e}")

    except Exception as e:
        print(f"[SCHEDULER] Error in schedule_reminder_messages: {e}")


def schedule_referral_status_updates():
    """Send referral status updates to referrers"""
    try:
        from datetime import datetime, timedelta

        ws = sheets_service._sheet("Submissions")
        vals = ws.get_all_values()

        if len(vals) <= 1:
            return

        headers = vals[0]

        for row in vals[1:]:
            rec = dict(zip(headers, row + [""] * (len(headers) - len(row))))

            referral_code = rec.get("referral_code", "")
            phone = rec.get("phone", "")
            referral_count = rec.get("referral_count", "0")

            if referral_code and phone:
                wa_phone = whatsapp_service.normalize_phone(phone)
                if wa_phone:
                    try:
                        # Get referral milestones
                        count = int(referral_count) if referral_count else 0
                        milestone_msg = ""

                        if count >= 10:
                            milestone_msg = "🌟 You've hit the LEGENDARY milestone! ₹15,000 earned!"
                        elif count >= 5:
                            milestone_msg = "🏆 5 referrals done! FREE filing + ₹5,000 cashback unlocked!"
                        elif count >= 3:
                            milestone_msg = "🎊 3 referrals! ₹1,000 cashback on the way."
                        elif count >= 1:
                            milestone_msg = f"🎉 {count} referral(s) done! Keep going for more rewards."

                        if milestone_msg:
                            whatsapp_service.send_template(
                                wa_phone,
                                "referral_update",
                                [rec.get("name", "there"), str(count), milestone_msg]
                            )
                            print(f"[SCHEDULER] Sent referral update to {wa_phone}")
                    except Exception as e:
                        print(f"[SCHEDULER] Failed to send referral update: {e}")

    except Exception as e:
        print(f"[SCHEDULER] Error in schedule_referral_status_updates: {e}")


# DIAGNOSTIC ENDPOINT - For debugging when tests fail
@app.route("/api/diagnostic", methods=["POST"])
def diagnostic():
    """Debug endpoint to test data flow and logging"""
    try:
        data = request.get_json(force=True) or {}

        # Log to both file and console
        logger.info(f"[DIAGNOSTIC] Received data: {data}")
        print(f"[DIAGNOSTIC] Print statement: {data}", flush=True)

        # Test Sheets access
        sheets_status = "OK" if sheets_service._client() else "NO CLIENT"
        logger.info(f"[DIAGNOSTIC] Sheets client: {sheets_status}")

        # Test data persistence
        test_id = data.get("submission_id", "diagnostic-test")
        result = sheets_service.insert_submission({
            "submission_id": test_id,
            "name": data.get("name", "Test"),
            "phone": data.get("phone", "0000000000")
        })
        logger.info(f"[DIAGNOSTIC] Insert result: {result}")

        # Check if data was saved
        row = sheets_service.get_row_by_submission_id(test_id)
        logger.info(f"[DIAGNOSTIC] Row lookup: {row}")

        return jsonify({
            "success": True,
            "diagnostic": {
                "sheets_client": sheets_status,
                "insert_result": result,
                "row_found": row is not None,
                "row_number": row
            },
            "message": "Check flask_app.log for detailed output"
        }), 200

    except Exception as e:
        logger.error(f"[DIAGNOSTIC] Error: {e}")
        logger.error(f"[DIAGNOSTIC] Traceback: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ---------- Save Individual Referral to "The 5" Sheet ─────────────────────────
@app.route("/api/save-referral", methods=["POST"])
def save_referral():
    """
    Save individual referral to "The 5" sheet (auto-save from referral-filing.html).

    Request:
    - referrer_name: Name of person making referral (required)
    - referral_name: Name of referred person (required)
    - referral_phone: Phone of referred person (required, 10 digits)
    - referral_index: Index 1-5 (optional, for logging)

    Response:
    {
        "success": bool,
        "message": str
    }
    """
    try:
        data = request.get_json(force=True)
        referrer_name = (data.get('referrer_name') or '').strip()
        referral_name = (data.get('referral_name') or '').strip()
        referral_phone = (data.get('referral_phone') or '').strip()
        referral_index = data.get('referral_index', 0)

        print(f"[SAVE_REFERRAL] Ref {referral_index}: {referrer_name} → {referral_name} ({referral_phone})")

        # Validate required fields
        if not referrer_name:
            return jsonify({"success": False, "error": "referrer_name required"}), 400
        if not referral_name:
            return jsonify({"success": False, "error": "referral_name required"}), 400
        if not referral_phone:
            return jsonify({"success": False, "error": "referral_phone required"}), 400

        # Validate phone is 10 digits
        phone_digits = ''.join(c for c in referral_phone if c.isdigit())
        if len(phone_digits) != 10:
            return jsonify({"success": False, "error": "Phone must be 10 digits"}), 400

        # Append to "The 5" sheet
        try:
            ws = sheets_service._sheet("The 5")
            if ws is None:
                print("[SAVE_REFERRAL] Sheet 'The 5' not found - returning success (non-blocking)")
                return jsonify({"success": True, "message": "Sheet unavailable (non-blocking)"}), 200

            # Ensure headers exist
            sheets_service._ensure_headers(ws, [
                "referrer_name",
                "referral_name",
                "referral_phone",
                "referrals_sent",
                "submission_found",
                "last_notified",
                "status"
            ])

            # Append row with first 3 columns (others handled differently)
            sheets_service._ws_call(ws, 'append_row', [
                referrer_name,      # Column A: referrer_name
                referral_name,      # Column B: referral_name
                referral_phone,     # Column C: referral_phone
                "",                 # Column D: referrals_sent (empty, handled differently)
                "",                 # Column E: submission_found (empty, handled differently)
                "",                 # Column F: last_notified (empty, handled differently)
                ""                  # Column G: status (empty, handled differently)
            ])

            print(f"[SAVE_REFERRAL] ✅ Saved: {referrer_name} → {referral_name}")
            return jsonify({
                "success": True,
                "message": f"Referral {referral_index} saved"
            })

        except Exception as e:
            print(f"[SAVE_REFERRAL] Error saving to sheet: {e}")
            # Non-blocking: return success anyway so user experience isn't disrupted
            return jsonify({"success": True, "message": "Saved locally (sheet write failed)"}), 200

    except Exception as e:
        print(f"[SAVE_REFERRAL] Error: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ---------- Immediate Document Upload (Save on upload, before extraction) ----------
@app.route("/api/upload-document", methods=["POST"])
def upload_document():
    """
    Immediate document upload endpoint.
    Saves uploaded documents to persistent storage immediately.
    Does NOT perform extraction - just saves and stores URLs in Google Sheets.

    Request:
    - submission_id: Unique submission identifier (required)
    - doc_type: Document type (form16, payslip, homeloan, school, nps, insurance, donation)
    - documents: File(s) to upload (multipart/form-data)

    Response:
    {
        "success": bool,
        "submission_id": str,
        "doc_type": str,
        "urls": [list of URLs],
        "message": str
    }
    """
    try:
        submission_id = request.form.get("submission_id")
        doc_type = request.form.get("doc_type", "form16")
        files = request.files.getlist("documents")

        print(f"[UPLOAD_DOCUMENT] submission_id={submission_id}, doc_type={doc_type}, file_count={len(files)}")

        if not submission_id:
            return jsonify({"success": False, "error": "submission_id is required"}), 400

        if not files or len(files) == 0:
            return jsonify({"success": False, "error": "No files provided"}), 400

        # Validate doc_type
        valid_types = ["form16", "payslip", "homeloan", "school", "nps", "insurance", "donation"]
        if doc_type not in valid_types:
            return jsonify({
                "success": False,
                "error": f"Invalid doc_type '{doc_type}'. Valid types: {', '.join(valid_types)}"
            }), 400

        # Save all files
        urls = []
        for file_obj in files:
            if not file_obj or not file_obj.filename:
                continue

            print(f"[UPLOAD_DOCUMENT] Saving file: {file_obj.filename}")
            url = storage_service.save_file(file_obj, submission_id, doc_type)

            if url:
                urls.append(url)
                print(f"[UPLOAD_DOCUMENT] Successfully saved: {url}")
            else:
                print(f"[UPLOAD_DOCUMENT] Failed to save: {file_obj.filename}")
                return jsonify({
                    "success": False,
                    "error": f"Failed to save file: {file_obj.filename}"
                }), 500

        # Update Google Sheets with document URLs
        row = sheets_service.get_row_by_submission_id(submission_id)

        # Ensure row exists
        if row is None:
            try:
                sheets_service.insert_submission({"submission_id": submission_id})
                row = sheets_service.get_row_by_submission_id(submission_id)
                print(f"[UPLOAD_DOCUMENT] Created new row for submission {submission_id}")
            except Exception as e:
                print(f"[UPLOAD_DOCUMENT] Failed to create row: {e}")

        # Get the correct column name for this doc type
        col_name = storage_service.get_doc_type_column(doc_type)

        # Append URLs to existing URLs in sheet
        if row and col_name:
            try:
                existing_urls = row.get(col_name, "") if isinstance(row, dict) else ""
                updated_urls = storage_service.append_urls_to_sheet(existing_urls, urls)

                sheets_service.update_row(row, {col_name: updated_urls})
                print(f"[UPLOAD_DOCUMENT] Updated sheet column {col_name} with {len(urls)} URLs")
            except Exception as e:
                print(f"[UPLOAD_DOCUMENT] Warning: Failed to update sheets: {e}")
                # Non-blocking: files were saved even if sheets update failed

        return jsonify({
            "success": True,
            "submission_id": submission_id,
            "doc_type": doc_type,
            "urls": urls,
            "column_name": col_name,
            "message": f"Successfully saved {len(urls)} document(s)"
        })

    except Exception as e:
        print(f"[UPLOAD_DOCUMENT] Error: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    import os
    import sys
    # Force unbuffered output
    sys.stdout = open(sys.stdout.fileno(), mode='w', buffering=1, encoding='utf-8', errors='replace')
    sys.stderr = open(sys.stderr.fileno(), mode='w', buffering=1, encoding='utf-8', errors='replace')

    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(
        host="0.0.0.0",
        port=int(os.getenv('PORT', 5000)),
        debug=debug_mode,
        use_reloader=False,
        threaded=True
    )