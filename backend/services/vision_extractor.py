"""
Vision Model Extractor - PASS 1

Uses Gemini Vision model to extract structured financial data from document images.
Returns JSON with fields, confidence scores, and extraction metadata.
"""

import json
import re
from services import ai_provider


# Vision extraction prompts for each document type
_VISION_EXTRACTION_PROMPTS = {
    "form16": """You are an expert tax document reader specializing in Indian tax documents. Extract data from Form 16 images.

CRITICAL: Return ONLY valid JSON. Do NOT include markdown, explanations, or anything outside the JSON object.

**BEFORE extracting:** Check if this page looks like a Form 16. If it clearly is NOT a Form 16 (e.g., bank letterhead, insurance policy, school receipt, 69-page bulk document, etc.), return an empty JSON object {} with NO fields.

For each field below, provide:
- value: extracted data (string for names/IDs, integer for amounts)
- confidence: 0.0-1.0 where 1.0=certain, 0.6=moderate uncertainty, <0.5=uncertain
- justification: brief reason (1-2 sentences)

If a field is not found or confidence < 0.5, set value to null.

{
  "employer_name": {"value": "...", "confidence": 0.95, "justification": "Clear text at top"},
  "pan": {"value": "XXXXX9999X", "confidence": 0.95, "justification": "Standard PAN format"},
  "assessment_year": {"value": "2024-25", "confidence": 0.9, "justification": "From document header"},
  "gross_salary": {"value": 1200000, "confidence": 0.92, "annual": true, "justification": "Sum of all salary components"},
  "basic_salary": {"value": 600000, "confidence": 0.9, "annual": true, "justification": "Table row labeled Basic"},
  "hra_received": {"value": 240000, "confidence": 0.88, "annual": true, "justification": "Separate line item"},
  "lta": {"value": 0, "confidence": 0.7, "annual": true, "justification": "Not visible in document"},
  "special_allowance": {"value": 360000, "confidence": 0.85, "annual": true, "justification": "Listed in allowances"},
  "car_lease_allowance": {"value": 0, "confidence": 0.8, "justification": "Not applicable"},
  "uniform_allowance": {"value": 0, "confidence": 0.8, "justification": "Not applicable"},
  "pf_employee": {"value": 72000, "confidence": 0.9, "annual": true, "justification": "Employee PF row"},
  "pf_employer": {"value": 72000, "confidence": 0.9, "annual": true, "justification": "Employer PF row"},
  "tds_paid": {"value": 150000, "confidence": 0.95, "annual": true, "justification": "TDS summary row"},
  "professional_tax": {"value": 2400, "confidence": 0.85, "annual": true, "justification": "PT deduction line"},
  "gratuity": {"value": 0, "confidence": 0.8, "justification": "Not shown"},
  "leave_encashment": {"value": 0, "confidence": 0.8, "justification": "Not shown"},
  "section_17_1": {"value": 0, "confidence": 0.7, "justification": "Not visible"},
  "section_17_2": {"value": 0, "confidence": 0.7, "justification": "Not visible"},
  "section_17_3": {"value": 0, "confidence": 0.7, "justification": "Not visible"}
}

Rules:
- All monetary amounts in INR (integers only, no commas or symbols)
- ANNUAL figures only. If monthly shown, multiply by 12 and note in justification
- Never invent values. Use null for missing/uncertain fields.
- Confidence must reflect certainty; low confidence (< 0.6) → use null
- Include "annual": true for monetary fields that are yearly totals
""",

    "payslip": """You are an expert at reading Indian payslips. Extract salary data from payslip image(s).

CRITICAL: Return ONLY valid JSON. Do NOT include markdown or explanations.

{
  "employer_name": {"value": "...", "confidence": 0.95, "justification": "..."},
  "pan": {"value": "XXXXX9999X", "confidence": 0.9, "justification": "..."},
  "month": {"value": "May", "confidence": 0.95, "justification": "From payslip date"},
  "year": {"value": 2024, "confidence": 0.95, "justification": "From payslip date"},
  "gross_salary": {"value": 120000, "confidence": 0.92, "monthly": true, "justification": "Gross/CTC line"},
  "basic_salary": {"value": 60000, "confidence": 0.9, "monthly": true, "justification": "Basic pay row"},
  "hra_received": {"value": 24000, "confidence": 0.88, "monthly": true, "justification": "HRA line"},
  "lta": {"value": 0, "confidence": 0.7, "monthly": true, "justification": "Not visible"},
  "special_allowance": {"value": 36000, "confidence": 0.85, "monthly": true, "justification": "Special pay row"},
  "car_lease_allowance": {"value": 0, "confidence": 0.8, "justification": "Not applicable"},
  "uniform_allowance": {"value": 0, "confidence": 0.8, "justification": "Not applicable"},
  "pf_employee": {"value": 7200, "confidence": 0.9, "monthly": true, "justification": "Employee PF deduction"},
  "pf_employer": {"value": 7200, "confidence": 0.9, "monthly": true, "justification": "Employer contribution"},
  "tds_paid": {"value": 15000, "confidence": 0.95, "monthly": true, "justification": "TDS deduction"},
  "professional_tax": {"value": 200, "confidence": 0.85, "monthly": true, "justification": "PT deduction"},
  "gratuity": {"value": 0, "confidence": 0.8, "justification": "Not on payslip"},
  "leave_encashment": {"value": 0, "confidence": 0.8, "justification": "Not on payslip"}
}

Rules:
- MONTHLY figures (not annualized)
- Include "monthly": true for salary fields
- All monetary amounts in INR (integers only)
- Never invent values
- Confidence < 0.6 → use null
""",

    "homeloan": """Extract home loan interest certificate / statement data from image.

{
  "loan_account_no": {"value": "12345678", "confidence": 0.95, "justification": "Account number field"},
  "bank_name": {"value": "HDFC Bank", "confidence": 0.9, "justification": "Bank name header"},
  "home_loan_interest": {"value": 250000, "confidence": 0.92, "annual": true, "justification": "Annual interest paid row"},
  "home_loan_principal": {"value": 500000, "confidence": 0.9, "annual": true, "justification": "Principal repaid row"},
  "loan_outstanding": {"value": 2500000, "confidence": 0.88, "annual": true, "justification": "Outstanding balance"}
}

Rules:
- ANNUAL figures only
- All amounts in INR (integers only)
""",

    "school": """Extract school fees / tuition receipt data.

{
  "school_name": {"value": "ABC School", "confidence": 0.95, "justification": "School name at top"},
  "school_fees": {"value": 150000, "confidence": 0.92, "annual": true, "justification": "Annual fees paid"}
}

Rules:
- ANNUAL total fees (if monthly shown, multiply by 12)
- All amounts in INR
""",

    "nps": """Extract NPS (National Pension System) statement data.

{
  "nps_pran": {"value": "123456789012", "confidence": 0.95, "justification": "PRAN number"},
  "nps_self": {"value": 50000, "confidence": 0.92, "annual": true, "justification": "Employee contribution"},
  "nps_employer": {"value": 50000, "confidence": 0.9, "annual": true, "justification": "Employer contribution"}
}

Rules:
- ANNUAL contribution amounts
- All amounts in INR
""",

    "insurance": """Extract insurance policy / premium receipt data.

{
  "policy_no": {"value": "POL123456", "confidence": 0.95, "justification": "Policy number"},
  "insurer_name": {"value": "LIC of India", "confidence": 0.9, "justification": "Insurer name"},
  "premium_amount": {"value": 50000, "confidence": 0.92, "annual": true, "justification": "Annual premium"},
  "sum_assured": {"value": 1000000, "confidence": 0.85, "justification": "Sum assured amount"},
  "coverage_type": {"value": "life", "confidence": 0.9, "justification": "Life insurance policy"}
}

Rules:
- ANNUAL premium (convert if monthly)
- coverage_type: "life" or "health"
""",

    "donation": """Extract donation receipt / 80G certificate data.

{
  "receipt_number": {"value": "RCP123456", "confidence": 0.95, "justification": "Receipt number"},
  "donation_amount": {"value": 100000, "confidence": 0.92, "justification": "Donation amount"},
  "organization_name": {"value": "NGO Name", "confidence": 0.9, "justification": "Organization name"},
  "donee_pan": {"value": "XXXXX0001A", "confidence": 0.95, "justification": "Donee PAN number"}
}

Rules:
- Only 80G-eligible donations
- Must have valid donee PAN
- Amount in INR
"""
}


def _parse_json_strict(response_text):
    """
    Parse JSON from response, handling potential extra text before/after.
    Strips markdown code fences and tries multiple extraction strategies.

    Args:
        response_text: Raw model response text

    Returns:
        Parsed dict, or empty dict if parsing fails
    """
    if not response_text:
        return {}

    text = str(response_text).strip()

    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```\s*$', '', text)
    text = text.strip()

    # Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Extract first balanced JSON object
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            # Try to fix common issues: trailing commas, single quotes
            fixed = re.sub(r',(\s*[}\]])', r'\1', match.group(0))
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass
    return {}


# Document type verification prompts
_DOCUMENT_TYPE_VERIFICATION_PROMPTS = {
    "form16": """You are an expert tax document classifier. Your ONLY task is to verify if this document is a Form 16 (Income Tax Return form for employers).

Look for these Form 16 characteristics:
- Finance Ministry of India header or Department of Revenue logo
- "Form No. 16" clearly stated
- "Income-Tax" text
- PAN field for employee
- Salary section with earnings breakdown
- TDS section showing tax deducted at source
- Assessment year field (e.g., 2023-24, 2024-25)
- Employer details and signature
- Generally a formal 1-2 page document

Respond with ONLY this JSON (no markdown, no explanation):
{
  "is_document_type": true or false,
  "confidence": 0.0 to 1.0,
  "detected_document_type": "form16" or "payslip" or "receipt" or "other_doc_type",
  "reasoning": "One sentence explaining what you see"
}""",

    "payslip": """You are an expert tax document classifier. Your ONLY task is to verify if this document is a Payslip (monthly salary payment slip).

Look for these Payslip characteristics:
- Employer company name and letterhead
- Employee name and employee ID
- Month/period (e.g., "May 2024", "March 2024")
- Date of payment
- Earnings section (Basic, HRA, DA, Special Allowance, etc.)
- Deductions section (PF, TDS, PT, etc.)
- Net salary amount
- Year (single calendar year)
- Monthly/single period salary breakdown

Do NOT confuse with:
- Form 16 (annual tax form, has "Finance Ministry" header)
- Receipt (invoice, bill, website purchase receipt)
- Certificate (loan, insurance, donation)

Respond with ONLY this JSON (no markdown, no explanation):
{
  "is_document_type": true or false,
  "confidence": 0.0 to 1.0,
  "detected_document_type": "payslip" or "form16" or "receipt" or "other_doc_type",
  "reasoning": "One sentence explaining what you see"
}""",

    "homeloan": """Verify if this is a Home Loan Interest Certificate or statement.

Look for:
- Bank name and letterhead
- "Home Loan" or "Loan" heading
- Loan account number
- Interest paid amount or certificate of interest
- Property address mentioned
- Loan outstanding balance
- Annual interest certificate format (often for tax purposes)

Respond with ONLY this JSON:
{
  "is_document_type": true or false,
  "confidence": 0.0 to 1.0,
  "detected_document_type": "homeloan" or "other_doc_type",
  "reasoning": "One sentence explanation"
}""",

    "school": """Verify if this is a School Fees Receipt or statement.

Look for:
- School/college name and letterhead
- Student name
- Academic period/year
- "Fees", "Tuition", "Education" charges
- Receipt number or invoice number
- Institution address
- Amount and date

Respond with ONLY this JSON:
{
  "is_document_type": true or false,
  "confidence": 0.0 to 1.0,
  "detected_document_type": "school" or "other_doc_type",
  "reasoning": "One sentence explanation"
}""",

    "nps": """Verify if this is an NPS (National Pension Scheme) statement.

Look for:
- "NPS" or "National Pension Scheme" text
- Subscriber name and subscriber ID
- Account statement header
- Transaction summary or holdings
- Fund information (asset classes)
- PFRDA or Point of Presence details
- Account statement period

Respond with ONLY this JSON:
{
  "is_document_type": true or false,
  "confidence": 0.0 to 1.0,
  "detected_document_type": "nps" or "other_doc_type",
  "reasoning": "One sentence explanation"
}""",

    "insurance": """Verify if this is an Insurance Policy or premium receipt.

Look for:
- Insurance company name and logo
- Policy number
- Insured person's name
- Coverage type (Life/Health/General)
- Premium amount and period
- Policy term/expiry date
- Underwriting information
- Receipt or policy document header

Respond with ONLY this JSON:
{
  "is_document_type": true or false,
  "confidence": 0.0 to 1.0,
  "detected_document_type": "insurance" or "other_doc_type",
  "reasoning": "One sentence explanation"
}""",

    "donation": """Verify if this is a Donation Receipt (80G certificate).

Look for:
- "Donation" or "Receipt" heading
- Recipient organization name (NGO, charity, temple, etc.)
- 80G registration number
- Donation amount
- Donation date
- Donation purpose
- Receipt number
- Recipient's PAN

Respond with ONLY this JSON:
{
  "is_document_type": true or false,
  "confidence": 0.0 to 1.0,
  "detected_document_type": "donation" or "other_doc_type",
  "reasoning": "One sentence explanation"
}"""
}


def verify_document_type(image_bytes, declared_doc_type):
    """
    Verify if an uploaded document matches the declared document type.

    This is a NON-BLOCKING validation step. Even if verification fails,
    extraction still proceeds (with warning metadata in response).

    Args:
        image_bytes: Single image bytes (first page only)
        declared_doc_type: Document type user selected (form16, payslip, etc.)

    Returns:
        {
            "is_verified": bool - Does document match declared type?
            "confidence": float - 0.0-1.0 confidence score
            "declared_type": str - What user said it was
            "detected_type": str - What we think it actually is
            "warning": str or None - User-friendly warning message
            "reasoning": str - Why we think what we think
        }

    Raises:
        Exception: Only if Vision model call fails (rare)
    """
    try:
        if declared_doc_type not in _DOCUMENT_TYPE_VERIFICATION_PROMPTS:
            # Unknown type, can't verify
            return {
                "is_verified": True,  # Assume correct if we don't know how to verify
                "confidence": 0.0,
                "declared_type": declared_doc_type,
                "detected_type": declared_doc_type,
                "warning": None,
                "reasoning": f"Unknown document type {declared_doc_type}, skipping verification"
            }

        # Get verification prompt
        prompt = _DOCUMENT_TYPE_VERIFICATION_PROMPTS[declared_doc_type]

        # Call Vision model for verification
        response = ai_provider.call_vision_model(image_bytes, prompt)

        # Parse response
        try:
            result = json.loads(response.strip())
        except json.JSONDecodeError:
            # If response isn't JSON, try to extract JSON from it
            result = _parse_json_strict(response)
            if not result:
                # Couldn't parse, assume verified (non-blocking)
                return {
                    "is_verified": True,
                    "confidence": 0.3,
                    "declared_type": declared_doc_type,
                    "detected_type": declared_doc_type,
                    "warning": None,
                    "reasoning": "Could not parse verification response, proceeding with extraction"
                }

        # Extract verification result
        is_verified = result.get("is_document_type", True)
        confidence = result.get("confidence", 0.5)
        detected_type = result.get("detected_document_type", declared_doc_type)
        reasoning = result.get("reasoning", "")

        # Generate warning if mismatch detected
        warning = None
        if not is_verified and confidence > 0.75:
            # High confidence that this is NOT the declared type
            warning = f"⚠️ This appears to be a {detected_type}, not a {declared_doc_type}. The extracted data may be inaccurate. Please review the extracted data carefully."
        elif not is_verified and confidence > 0.5:
            # Medium confidence mismatch
            warning = f"⚠️ This document might not be a {declared_doc_type}. Please verify the extracted data is correct."

        return {
            "is_verified": is_verified,
            "confidence": confidence,
            "declared_type": declared_doc_type,
            "detected_type": detected_type,
            "warning": warning,
            "reasoning": reasoning
        }

    except Exception as e:
        # If verification fails, proceed with extraction (non-blocking)
        print(f"[DOCUMENT_TYPE_VERIFICATION] Error during verification: {str(e)}")
        return {
            "is_verified": True,  # Assume correct on error (non-blocking)
            "confidence": 0.0,
            "declared_type": declared_doc_type,
            "detected_type": declared_doc_type,
            "warning": None,
            "reasoning": f"Verification error: {str(e)}"
        }


def _merge_page_results(page_results, doc_type):
    """
    Merge extraction results from multiple pages into single result.

    For multi-page documents (e.g., Form16 page 1 + page 2),
    consolidate fields with conflict detection.

    Args:
        page_results: List of extraction results (one per page)
        doc_type: Document type

    Returns:
        Merged extraction result
    """
    if not page_results:
        return {"fields": {}, "pages_processed": 0, "overall_confidence": 0}

    if len(page_results) == 1:
        return {
            "fields": page_results[0].get("fields", {}),
            "document_type_detected": page_results[0].get("document_type_detected", doc_type),
            "pages_processed": 1,
            "extraction_quality": page_results[0].get("extraction_quality", "high"),
            "overall_confidence": page_results[0].get("overall_confidence", 0.85),
            "assumptions": page_results[0].get("assumptions", [])
        }

    # Multi-page merge: consolidate fields
    merged_fields = {}
    confidences = []
    conflicts = []

    # Collect all fields across pages
    all_fields = {}
    for page_num, result in enumerate(page_results, 1):
        for field_name, field_data in result.get("fields", {}).items():
            if field_name not in all_fields:
                all_fields[field_name] = []
            all_fields[field_name].append((page_num, field_data))

    # Merge each field
    for field_name, values in all_fields.items():
        if len(values) == 1:
            # Field on only one page
            merged_fields[field_name] = values[0][1]
            confidences.append(values[0][1].get("confidence") or 0)
        else:
            # Field on multiple pages: use highest confidence value
            best = max(values, key=lambda x: x[1].get("confidence") or 0)
            merged_fields[field_name] = best[1]
            confidences.append(best[1].get("confidence") or 0)

            # Log if values differ
            unique_values = set(str(v[1].get("value")) for v in values)
            if len(unique_values) > 1:
                conflicts.append({
                    "field": field_name,
                    "pages": [(v[0], v[1].get("value")) for v in values],
                    "chosen": best[1].get("value")
                })

    overall_conf = sum(confidences) / len(confidences) if confidences else 0

    return {
        "fields": merged_fields,
        "document_type_detected": doc_type,
        "pages_processed": len(page_results),
        "extraction_quality": "high" if overall_conf > 0.85 else "medium" if overall_conf > 0.65 else "low",
        "overall_confidence": round(overall_conf, 2),
        "page_conflicts": conflicts,
        "assumptions": ["Multiple pages merged with field consolidation"]
    }


def extract_pass1_vision(image_bytes_list, doc_type):
    """
    PASS 1: Extract structured financial data from document images using Vision model.

    Args:
        image_bytes_list: List of image bytes (one per page)
        doc_type: Document type (form16, payslip, homeloan, school, nps, insurance, donation)

    Returns:
        {
            "fields": {
                "field_name": {
                    "value": extracted_value,
                    "confidence": 0.0-1.0,
                    "justification": "reason",
                    ... (optional: "annual", "monthly", etc.)
                }
            },
            "document_type_detected": str,
            "pages_processed": int,
            "extraction_quality": "high|medium|low",
            "overall_confidence": float,
            "assumptions": [str],
            "errors": [str] (if any)
        }

    Raises:
        Exception: If Vision extraction fails (fail-fast strategy)
    """
    try:
        # Get extraction prompt for doc_type
        if doc_type not in _VISION_EXTRACTION_PROMPTS:
            raise ValueError(f"Unsupported document type: {doc_type}")

        prompt = _VISION_EXTRACTION_PROMPTS[doc_type]

        # Process each page separately
        page_results = []
        errors = []

        blank_pages = []  # Pages with no extractable data (not errors)
        consecutive_blanks = 0  # Track consecutive blank pages for early stopping
        MAX_CONSECUTIVE_BLANKS = 5  # Stop after 5 consecutive blank pages
        MAX_PAGES = 20  # Never process more than 20 pages per document

        total_pages = len(image_bytes_list)
        pages_to_process = min(total_pages, MAX_PAGES)

        if total_pages > MAX_PAGES:
            print(f"[VISION_EXTRACTOR][{doc_type}] Large document ({total_pages} pages). Processing first {MAX_PAGES} pages only.")

        for page_num, img_bytes in enumerate(image_bytes_list[:pages_to_process], 1):
            try:
                # Call Vision model
                response = ai_provider.call_vision_model(img_bytes, prompt)

                # Parse JSON response
                result = _parse_json_strict(response)

                # Empty / unparseable response = page has no relevant data (blank, cover, signature, etc.)
                # This is NOT an error — just skip the page and continue
                if not result:
                    blank_pages.append(page_num)
                    consecutive_blanks += 1
                    print(f"[VISION_EXTRACTOR][{doc_type}] Page {page_num}: no extractable data (blank/cover/non-{doc_type})")

                    # Early stop: if we already found some data and hit many blanks, stop
                    if consecutive_blanks >= MAX_CONSECUTIVE_BLANKS and page_results:
                        print(f"[VISION_EXTRACTOR][{doc_type}] Early stop: {consecutive_blanks} consecutive blank pages after finding data. Stopping.")
                        break
                    continue

                # Validate structure (should have "fields" key with field objects)
                if "fields" not in result and result:
                    # Response has top-level field structure, restructure it
                    result = {"fields": result}

                # Filter out fields where all values are null (page had no real data)
                fields = result.get("fields", {}) or {}
                non_null_fields = {
                    k: v for k, v in fields.items()
                    if isinstance(v, dict) and v.get("value") not in (None, "", 0, "0")
                }

                if not non_null_fields:
                    blank_pages.append(page_num)
                    consecutive_blanks += 1
                    print(f"[VISION_EXTRACTOR][{doc_type}] Page {page_num}: all fields null (likely non-{doc_type} page)")

                    if consecutive_blanks >= MAX_CONSECUTIVE_BLANKS and page_results:
                        print(f"[VISION_EXTRACTOR][{doc_type}] Early stop: {consecutive_blanks} consecutive blank pages after finding data. Stopping.")
                        break
                    continue

                # Found data — reset consecutive blank counter
                consecutive_blanks = 0
                result["_page"] = page_num
                page_results.append(result)

                print(f"[VISION_EXTRACTOR][{doc_type}] Page {page_num}: {len(non_null_fields)} non-null fields extracted")

            except Exception as e:
                # Only actual exceptions (API errors, network errors) are errors
                error_msg = f"Page {page_num} extraction failed: {str(e)}"
                print(f"[VISION_EXTRACTOR] {error_msg}")
                errors.append(error_msg)
                consecutive_blanks += 1
                continue

        # If we got at least one page with data, we succeed (even if 90% of pages were blank)
        if not page_results:
            if errors:
                raise ValueError(f"All pages failed extraction. Errors: {errors}")
            # All pages were blank — return an empty (but successful) result
            return {
                "fields": {},
                "document_type_detected": doc_type,
                "pages_processed": len(image_bytes_list),
                "extraction_quality": "low",
                "overall_confidence": 0.0,
                "assumptions": [f"No extractable {doc_type} data found across {len(image_bytes_list)} pages"],
                "blank_pages": blank_pages
            }

        # Merge multi-page results
        merged = _merge_page_results(page_results, doc_type)
        if errors:
            merged["errors"] = errors
        if blank_pages:
            merged["blank_pages"] = blank_pages
            merged.setdefault("assumptions", []).append(
                f"{len(blank_pages)} page(s) had no {doc_type} data and were skipped"
            )

        return merged

    except Exception as e:
        print(f"[VISION_EXTRACTOR] Vision extraction error: {str(e)}")
        raise
