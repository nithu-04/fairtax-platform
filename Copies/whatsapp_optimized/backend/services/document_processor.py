"""
Document Processing Orchestrator

Main entry point for the Vision-based extraction pipeline:
1. PDF → images conversion
2. PASS 1: Vision extraction with confidence scoring
3. Normalization & aggregation
4. Validation layer
5. Return normalized, validated data
"""

import io
import traceback
from services import file_handler, vision_extractor, normalization_service, validation_service
import logging

logger = logging.getLogger(__name__)

# Minimum average characters per page to consider a PDF "digital" (not scanned)
_TEXT_FAST_PATH_MIN_CHARS = 150

# Doc types where text fast-path is safe (well-structured tabular text in digital PDFs)
_TEXT_FAST_PATH_DOC_TYPES = {"payslip", "form16", "homeloan", "nps", "school", "insurance", "donation"}


def _try_text_extraction(file_bytes, doc_type):
    """
    Attempt fast-path text extraction for digital PDFs using pdfplumber.
    Returns a document_processor-compatible result dict, or None if text quality is too low.
    """
    try:
        import pdfplumber
        import ai_service

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages_text = []
            for page in pdf.pages:
                t = page.extract_text() or ""
                pages_text.append(t)

            full_text = "\n\n".join(pages_text)
            num_pages = max(len(pages_text), 1)
            avg_chars = len(full_text.replace(" ", "").replace("\n", "")) / num_pages

            # For payslips, accept LOWER quality text (they're highly structured)
            # For others, use standard threshold
            min_chars_threshold = 75 if doc_type == "payslip" else _TEXT_FAST_PATH_MIN_CHARS

            if avg_chars < min_chars_threshold:
                return None

            # Digital PDF with sufficient text quality
            result = ai_service.extract_from_text(full_text, doc_type)

            if result.get("success"):
                return result
            else:
                return None

    except Exception as e:
        return None


def process_documents(file_bytes, mime_type, doc_type):
    """
    Process document(s) through the Vision extraction pipeline.

    Pipeline:
    1. Convert PDF to images (if needed)
    2. PASS 1: Vision extraction with confidence scores
    3. Normalize: handle multi-page, annual/monthly, duplicates
    4. Validate: enforce business rules and deduction caps
    5. Return normalized, validated data

    Args:
        file_bytes: Raw document bytes (PDF or image)
        mime_type: MIME type (application/pdf, image/jpeg, image/png, etc.)
        doc_type: Document type (form16, payslip, homeloan, school, nps, insurance, donation)

    Returns:
        {
            "success": bool,
            "data": {normalized extracted fields},
            "confidence": float (0-1),
            "metadata": {
                "assumptions": [str],
                "duplicates": [dict],
                "conflicts": [dict],
                "pages_processed": int,
                "validation_warnings": [dict]
            },
            "error": str or None
        }

    Error behavior (Fail-Fast):
    - Invalid PDF/image → Error returned to user
    - Vision extraction failure → Error returned to user
    - Validation errors → Error returned to user
    - User uploads low-quality document → Error + feedback to user
    """
    try:
        # ─────── FAST PATH: Digital PDF via pdfplumber ───
        # For digital (non-scanned) PDFs, skip image conversion + Vision API entirely.
        # This is ~3-5× faster and more accurate for clean payslips / Form 16 PDFs.
        if "pdf" in (mime_type or "").lower() and doc_type in _TEXT_FAST_PATH_DOC_TYPES:
            fast_result = _try_text_extraction(file_bytes, doc_type)
            if fast_result:
                print(f"[DOCUMENT_PROCESSOR] Fast-path succeeded. Returning text-extracted result.")
                return fast_result

        # ─────── STEP 1: Convert File to Images ──────────
        try:
            images = file_handler.process_file(file_bytes, mime_type)

        except Exception as e:
            error_msg = f"File conversion failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg,
                "data": {},
                "confidence": 0,
                "metadata": {}
            }

        # ─────── STEP 2: PASS 1 - Vision Extraction ─────
        try:
            extraction = vision_extractor.extract_pass1_vision(images, doc_type)

        except Exception as e:
            error_msg = f"Vision extraction failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg,
                "data": {},
                "confidence": 0,
                "metadata": {
                    "extraction_quality": "failed",
                    "pages_processed": len(images) if 'images' in locals() else 0
                }
            }

        # ─────── STEP 3: Normalize & Aggregate ─────────
        try:
            normalized_result = normalization_service.normalize_extractions(
                [extraction],
                [doc_type]
            )

            normalized_data = normalized_result.get("normalized", {})

        except Exception as e:
            error_msg = f"Normalization failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg,
                "data": {},
                "confidence": 0,
                "metadata": {}
            }

        # ─────── STEP 4: Validate ──────────────────────
        # For extracted/OCR'd data, validation is informational only.
        # Errors here represent things the user should review/correct (bad PAN, salary mismatches)
        # but should NOT block extraction — the user can edit the fields manually after extraction.
        validation_result = {}
        try:
            validation_result = validation_service.validate_extraction(normalized_data)

        except Exception as e:
            logger.warning(f"Validation error (non-blocking): {str(e)}")
            validation_result = {"errors": [], "warnings": [{"reason": str(e)}]}

        # ─────── STEP 5: Return Success ────────────────

        return {
            "success": True,
            "data": normalized_data,
            "confidence": round(normalized_result.get("extraction_confidence", 0), 2),
            "metadata": {
                "assumptions": normalized_result.get("assumptions", []),
                "duplicates": normalized_result.get("duplicates", []),
                "conflicts": normalized_result.get("conflicts", []),
                "pages_processed": extraction.get("pages_processed", len(images)),
                "validation_errors": validation_result.get("errors", []),
                "validation_warnings": validation_result.get("warnings", []),
                "extraction_quality": extraction.get("extraction_quality", "medium"),
                "fields_high_confidence": normalized_result.get("fields_high_confidence", []),
                "fields_low_confidence": normalized_result.get("fields_low_confidence", [])
            },
            "error": None
        }

    except Exception as e:
        # Unexpected error
        error_msg = f"Document processing failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "error": error_msg,
            "data": {},
            "confidence": 0,
            "metadata": {}
        }
