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

━━━ STEP 1: IDENTIFY THE PAYSLIP FORMAT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FORMAT A — STANDARD MONTHLY PAYSLIP
  Signs: Shows ONE month's data, single "Amount" column, header shows month+year (e.g. "April 2025")
  Action: Extract the monthly figures shown. Mark every salary field with "monthly": true.

FORMAT B — YTD / CUMULATIVE / ANNUAL PAYSLIP
  Signs: Shows MULTIPLE months as columns (Jan, Feb, Mar… or Month-1, Month-2…)
         OR has a "Grand Total", "YTD", "Annual Total", "Cumulative", or "Year to Date" column.
         OR has THREE columns labeled "Standard | Actual | YTD" (very common in India).
  Action: Extract ONLY from the "Grand Total" / "YTD" / "Annual Total" / rightmost totals column.
          DO NOT extract from individual month columns or the "Actual" (current month) column.
          Mark every salary field with "annual": true.

  ⚠ CRITICAL — Standard/Actual/YTD three-column example:
     Visual row: "BASIC   99,133.33   99,133.00   1,168,656.00"
                  Standard(monthly) Actual(March) YTD(annual) ← EXTRACT THIS
     → basic_salary value = 1168656, "annual": true   ← NOT 99133

━━━ STEP 2: HRA — SUM ALL VARIANTS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

hra_received MUST be the SUM of ALL HRA-type rows:
  • HRA / HOUSE RENT ALLOWANCE
  • NON-FBP HRA / NON FBP HRA
  • BASIC HRA / METRO HRA / SPECIAL HRA
  • Any row whose label contains the word "HRA"
Add them all together. In the justification, show each row value you summed.

━━━ STEP 3: TDS — USE INCOME TAX ROW ONLY ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

tds_paid = value from the row labelled "INCOME TAX", "TAX DEDUCTED AT SOURCE", or "TDS" ONLY.
⚠ NEVER use "TOTAL DEDUCTION" or "TOTAL DEDUCTIONS" for tds_paid —
  that row is the sum of ALL deductions (PF + PT + TDS + others).

━━━ STEP 4: PF & PROFESSIONAL TAX ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

pf_employee : "EMPLOYEE PF", "PF EMPLOYEE", "EPF EMPLOYEE", "PF CONTRIBUTION", "EMPLOYEE EPF"
pf_employer : "EMPLOYER PF", "PF EMPLOYER", "EPF EMPLOYER", "EMPLOYER CONTRIBUTION (PF)"
professional_tax : "PROFESSIONAL TAX", "PROF TAX", "PT", "P. TAX"

━━━ OUTPUT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{
  "employer_name": {"value": "...", "confidence": 0.95, "justification": "..."},
  "pan": {"value": "XXXXX9999X", "confidence": 0.9, "justification": "..."},
  "payslip_format": {"value": "monthly", "confidence": 0.95, "justification": "Single column / or YTD multi-column"},
  "month": {"value": "May", "confidence": 0.95, "justification": "From payslip date (null for YTD format)"},
  "year": {"value": 2025, "confidence": 0.95, "justification": "From payslip date"},
  "gross_salary": {"value": 120000, "confidence": 0.92, "monthly": true, "justification": "Gross/CTC line"},
  "basic_salary": {"value": 60000, "confidence": 0.9, "monthly": true, "justification": "Basic pay row"},
  "hra_received": {"value": 78203, "confidence": 0.95, "monthly": true, "justification": "Sum of HRA (16406) + NON-FBP HRA (61797) = 78203"},
  "lta": {"value": 0, "confidence": 0.7, "monthly": true, "justification": "Not visible"},
  "special_allowance": {"value": 36000, "confidence": 0.85, "monthly": true, "justification": "Special pay row"},
  "car_lease_allowance": {"value": 0, "confidence": 0.8, "justification": "Not applicable"},
  "uniform_allowance": {"value": 0, "confidence": 0.8, "justification": "Not applicable"},
  "pf_employee": {"value": 7200, "confidence": 0.9, "monthly": true, "justification": "EMPLOYEE PF deduction row"},
  "pf_employer": {"value": 7200, "confidence": 0.9, "monthly": true, "justification": "EMPLOYER PF row"},
  "tds_paid": {"value": 15000, "confidence": 0.95, "monthly": true, "justification": "INCOME TAX row (not Total Deduction)"},
  "professional_tax": {"value": 200, "confidence": 0.85, "monthly": true, "justification": "PROF TAX row"},
  "gratuity": {"value": 0, "confidence": 0.8, "justification": "Not on payslip"},
  "leave_encashment": {"value": 0, "confidence": 0.8, "justification": "Not on payslip"}
}

For YTD format: replace "monthly": true with "annual": true in every field.

Rules:
- All monetary amounts in INR (integers only, no commas or symbols)
- Never invent values. Use null for missing/uncertain fields.
- Confidence < 0.6 → use null
- hra_received justification MUST list the individual row values you summed
""",

    "homeloan": """You are an expert at reading Indian bank home loan documents for tax filing.

CRITICAL: Return ONLY valid JSON. Do NOT include markdown, explanations, or any text outside the JSON.

Extract from the home loan interest certificate / statement / repayment schedule:
- loan_account_no: Loan account number or reference number
- bank_name: Name of the bank or NBFC
- home_loan_interest: Total interest paid during the financial year (annual, for Section 24)
- home_loan_principal: Total principal repaid during the financial year (annual, for Section 80C)
- loan_outstanding: Remaining loan balance / outstanding principal

{
  "loan_account_no": {"value": "12345678", "confidence": 0.95, "justification": "Account number field"},
  "bank_name": {"value": "HDFC Bank", "confidence": 0.9, "justification": "Bank name header"},
  "home_loan_interest": {"value": 250000, "confidence": 0.92, "annual": true, "justification": "Interest paid this FY"},
  "home_loan_principal": {"value": 500000, "confidence": 0.9, "annual": true, "justification": "Principal repaid this FY"},
  "loan_outstanding": {"value": 2500000, "confidence": 0.88, "justification": "Outstanding balance"}
}

Rules:
- ANNUAL figures for the financial year only
- All amounts in INR integers (no decimals, no commas)
- Use null for fields not found in the document
""",

    "school": """You are an expert at reading Indian school fee receipts for tax filing.

CRITICAL: Return ONLY valid JSON. Do NOT include markdown, explanations, or any text outside the JSON.

Extract from the school fee receipt or tuition fee certificate:
- school_name: Name of the school
- school_fees: Total annual tuition fees paid (for Section 80C deduction)

{
  "school_name": {"value": "ABC School", "confidence": 0.95, "justification": "School name at top"},
  "school_fees": {"value": 150000, "confidence": 0.92, "annual": true, "justification": "Annual fees paid"}
}

Rules:
- ANNUAL total fees (if monthly shown, multiply by number of months)
- Amount in INR integers only
- Use null for fields not found
""",

    "nps": """You are an expert at reading Indian NPS (National Pension System) statements for tax filing.

CRITICAL: Return ONLY valid JSON. Do NOT include markdown, explanations, or any text outside the JSON.

Extract from the NPS account statement:
- nps_pran: PRAN (Permanent Retirement Account Number) — 12-digit number
- nps_self: Total employee/subscriber contribution for the financial year (for 80CCD(1B))
- nps_employer: Total employer contribution for the financial year (for 80CCD(2))

{
  "nps_pran": {"value": "123456789012", "confidence": 0.95, "justification": "PRAN number on statement"},
  "nps_self": {"value": 50000, "confidence": 0.92, "annual": true, "justification": "Subscriber contribution this FY"},
  "nps_employer": {"value": 50000, "confidence": 0.9, "annual": true, "justification": "Employer contribution this FY"}
}

Rules:
- ANNUAL contribution amounts for the financial year
- All amounts in INR integers
- Use null for fields not found
""",

    "insurance": """You are an expert at reading Indian insurance policy documents for tax filing.

CRITICAL: Return ONLY valid JSON. Do NOT include markdown, explanations, or any text outside the JSON.

Extract from the insurance policy / premium receipt:
- policy_no: Policy number or reference number
- insurer_name: Insurance company name (LIC, HDFC Life, Max Life, etc.)
- premium_amount: Annual premium paid (for 80C deduction for life; 80D for health)
- sum_assured: Sum assured / coverage amount
- coverage_type: "life" for life/ULIP/term insurance; "health" for mediclaim/health insurance

{
  "policy_no": {"value": "POL123456", "confidence": 0.95, "justification": "Policy number on document"},
  "insurer_name": {"value": "LIC of India", "confidence": 0.9, "justification": "Insurer name header"},
  "premium_amount": {"value": 50000, "confidence": 0.92, "annual": true, "justification": "Annual premium paid"},
  "sum_assured": {"value": 1000000, "confidence": 0.85, "justification": "Sum assured amount"},
  "coverage_type": {"value": "life", "confidence": 0.9, "justification": "Life insurance policy type"}
}

Rules:
- ANNUAL premium (if installment shown, use annual total)
- coverage_type MUST be exactly "life" or "health"
- All amounts in INR integers
- Use null for fields not found
""",

    "donation": """You are an expert at reading Indian donation receipts for tax filing.

CRITICAL: Return ONLY valid JSON. Do NOT include markdown, explanations, or any text outside the JSON.

Extract from the donation receipt / 80G certificate:
- receipt_number: Receipt or certificate number
- donation_amount: Amount donated (in INR)
- organization_name: Name of the organization / trust / NGO
- donee_pan: PAN number of the organization receiving the donation (required for 80G deduction)

{
  "receipt_number": {"value": "RCP123456", "confidence": 0.95, "justification": "Receipt number on certificate"},
  "donation_amount": {"value": 100000, "confidence": 0.92, "justification": "Donation amount paid"},
  "organization_name": {"value": "NGO Name", "confidence": 0.9, "justification": "Organization name on receipt"},
  "donee_pan": {"value": "XXXXX0001A", "confidence": 0.95, "justification": "Donee PAN for 80G"}
}

Rules:
- Only extract 80G-eligible donations (must have organization PAN)
- Amount in INR integers
- Use null for fields not found
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

        # Process pages in parallel for speed
        # Most ITR docs (payslip, Form16, home loan cert) are 1-3 pages
        MAX_PAGES = 3
        total_pages = len(image_bytes_list)
        pages_to_process = min(total_pages, MAX_PAGES)

        if total_pages > MAX_PAGES:
            print(f"[VISION_EXTRACTOR][{doc_type}] Capping at {MAX_PAGES} pages (doc has {total_pages}).")

        def _extract_page(args):
            page_num, img_bytes = args
            try:
                response = ai_provider.call_vision_model(img_bytes, prompt)
                result = _parse_json_strict(response)
                if not result:
                    return page_num, None, None
                if "fields" not in result:
                    result = {"fields": result}
                fields = result.get("fields", {}) or {}
                # Keep any field whose value is genuinely present (not null/None).
                # We intentionally allow 0 for numeric fields — 0 is a valid value
                # (e.g. PT = 0 for some months) and was incorrectly filtered before.
                # Only skip truly absent fields (None or missing key).
                non_null = {k: v for k, v in fields.items()
                            if isinstance(v, dict) and v.get("value") is not None}
                if not non_null:
                    return page_num, None, None
                result["_page"] = page_num
                print(f"[VISION_EXTRACTOR][{doc_type}] Page {page_num}: {len(non_null)} fields extracted")
                return page_num, result, None
            except Exception as e:
                import traceback
                print(f"[VISION_EXTRACTOR] Page {page_num} error: {traceback.format_exc()}")
                return page_num, None, str(e)

        from concurrent.futures import ThreadPoolExecutor
        page_inputs = list(enumerate(image_bytes_list[:pages_to_process], 1))

        with ThreadPoolExecutor(max_workers=min(pages_to_process, 3)) as executor:
            outcomes = list(executor.map(_extract_page, page_inputs))

        page_results = []
        blank_pages = []
        errors = []
        for page_num, result, err in sorted(outcomes, key=lambda x: x[0]):
            if err:
                errors.append(f"Page {page_num}: {err}")
            elif result is None:
                blank_pages.append(page_num)
                print(f"[VISION_EXTRACTOR][{doc_type}] Page {page_num}: no extractable data")
            else:
                page_results.append(result)

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
