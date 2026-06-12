"""
Flask API endpoints for ITR document extraction.
Integrates with the ITR document processor.
"""

from flask import Blueprint, request, jsonify
import os
from datetime import datetime
import storage_service
import sheets_service
from werkzeug.utils import secure_filename

itr_bp = Blueprint('itr', __name__, url_prefix='/api/itr')

@itr_bp.after_request
def _cors(response):
    response.headers.setdefault('Access-Control-Allow-Origin', '*')
    response.headers.setdefault('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    response.headers.setdefault('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    return response

@itr_bp.route('/extract', methods=['OPTIONS'])
@itr_bp.route('/test', methods=['OPTIONS'])
@itr_bp.route('/health', methods=['OPTIONS'])
def _options():
    return '', 200

# Lazy-initialize processor to prevent module-level failures breaking registration
_processor = None

def _get_processor():
    global _processor
    if _processor is None:
        from itr_extractor import ITRDocumentProcessor
        _processor = ITRDocumentProcessor(use_ocr=True)
    return _processor

# DEBUG: Test endpoint to verify blueprint is working
@itr_bp.route('/test', methods=['GET'])
def test():
    from flask import current_app
    test_logger = current_app.logger
    test_logger.info("[TEST ENDPOINT] /api/itr/test endpoint called successfully")

    response_data = {
        'status': 'ITR Blueprint is active',
        'timestamp': str(__import__('datetime').datetime.now()),
        'message': 'If you see this, the Blueprint routing is working'
    }

    test_logger.info(f"[TEST ENDPOINT] Returning response: {response_data}")
    return jsonify(response_data), 200


@itr_bp.route('/extract', methods=['POST'])
def extract_itr_data():
    """
    Extract ITR data from uploaded document.

    Expects:
    - file: Document file (PDF or image)
    - doc_type: Optional document type (form16, payslip, homeloan, school, nps, insurance, donation)
               If not provided, defaults to form16

    Supported doc_types:
    - form16: Form 16 (salary document)
    - payslip: Payslip (monthly salary)
    - homeloan: Home Loan interest certificate
    - school: School fee receipt
    - nps: NPS statement
    - insurance: Insurance policy/premium receipt
    - donation: Donation receipt (80G)

    Returns:
    {
        'success': bool,
        'data': {...},
        'errors': {...},
        'confidence': float (0-1),
        'metadata': {...}
    }
    """
    import time
    import sys
    from flask import current_app

    start_time = time.time()

    # Use Flask logger for better capture
    logger = current_app.logger
    logger.info("[ITR_EXTRACT] REQUEST RECEIVED - Function called")
    print("[STDOUT] ITR_EXTRACT endpoint function called", file=sys.stdout, flush=True)

    try:
        # Check if file(s) are provided
        logger.info(f"[ITR_EXTRACT] Checking for file in request")
        file_keys = list(request.files.keys())
        logger.info(f"[ITR_EXTRACT] Request files: {file_keys}")

        if 'file' not in request.files:
            print("[ITR_EXTRACT] [ERROR] No 'file' in request.files")
            return jsonify({
                'success': False,
                'error': 'No file provided',
                'data': {},
            }), 400

        # Handle multiple files - get all files with key 'file'
        files = request.files.getlist('file')
        print(f"[ITR_EXTRACT] Files received: {len(files)} file(s)")

        if not files or all(f.filename == '' for f in files):
            print("[ITR_EXTRACT] [ERROR] No valid files selected")
            return jsonify({
                'success': False,
                'error': 'No file selected',
                'data': {},
            }), 400

        # Get document type from request (default to form16)
        doc_type = request.form.get('doc_type', 'form16').lower().strip()
        submission_id = request.form.get('submission_id', '')
        print(f"[ITR_EXTRACT] Document type: {doc_type}, submission_id: {submission_id}")

        # Validate doc_type
        supported_doc_types = {'form16', 'payslip', 'homeloan', 'school', 'nps', 'insurance', 'donation'}
        if doc_type not in supported_doc_types:
            return jsonify({
                'success': False,
                'error': f'Unsupported doc_type: {doc_type}. Supported: {", ".join(sorted(supported_doc_types))}',
                'data': {},
            }), 400

        # ═══════════════════════════════════════════════════════════
        # PARALLEL EXTRACTION: Process files concurrently (OPTIMIZED)
        # ═══════════════════════════════════════════════════════════
        from concurrent.futures import ThreadPoolExecutor
        from io import BytesIO

        def _process_single_file(file_data):
            """Process a single file. Returns (filename, result, processed_file_info)."""
            filename, file_bytes, file_obj = file_data

            try:
                # Check file size
                if len(file_bytes) > 50 * 1024 * 1024:
                    print(f"[ITR_EXTRACT] File too large: {filename} ({len(file_bytes) / 1024 / 1024:.2f}MB)")
                    return (filename, {
                        'success': False,
                        'error': 'File too large (max 50MB)',
                        'data': {},
                        'filename': filename
                    }, None)

                # Process document with specified doc_type
                file_start = time.time()
                result = _get_processor().process_file(file_bytes, filename, doc_type=doc_type)
                file_elapsed = time.time() - file_start
                print(f"[ITR_EXTRACT] {filename}: {file_elapsed:.2f}s, success={result.get('success')}")

                detected_doc_type = doc_type

                # AUTO-DETECTION: Only when confidence is very low AND document is small
                conf = result.get("confidence", 0)
                pages = result.get("metadata", {}).get("pages_processed", 1)

                # OPTIMIZATION: Skip auto-detection if initial extraction was slow (> 15s)
                if file_elapsed > 15:
                    print(f"[ITR_EXTRACT] Skipping auto-detection for {filename}: initial extraction took {file_elapsed:.1f}s")
                elif conf < 0.3 and pages <= 10:
                    print(f"[ITR_EXTRACT] Auto-detecting {filename}: confidence={conf}, pages={pages}")

                    best_result = result
                    best_confidence = conf
                    best_doc_type = doc_type

                    # OPTIMIZATION: Try only 3 most likely types (not 7!)
                    likely_types = ["form16", "payslip", "homeloan"]
                    for test_type in likely_types:
                        if test_type == doc_type:
                            continue
                        try:
                            test_result = _get_processor().process_file(file_bytes, filename, doc_type=test_type)
                            test_confidence = test_result.get("confidence", 0)

                            print(f"[ITR_EXTRACT] {filename} as {test_type}: confidence={test_confidence}")

                            if test_confidence > best_confidence:
                                best_result = test_result
                                best_confidence = test_confidence
                                best_doc_type = test_type

                        except Exception as e:
                            print(f"[ITR_EXTRACT] Error trying {test_type} on {filename}: {str(e)}")
                            continue

                    if best_doc_type != doc_type:
                        print(f"[ITR_EXTRACT] {filename} detected as: {best_doc_type} (confidence: {best_confidence})")
                        result = best_result
                        result["auto_detected_doc_type"] = best_doc_type
                        detected_doc_type = best_doc_type

                # Track file for storage (if processing succeeded)
                processed_file_info = None
                if result.get('success'):
                    # 🔍 TRACE: Log extraction result with doc_type
                    extracted_data = result.get('data', {})
                    print(f"\n[EXTRACTION_TRACE] {filename}")
                    print(f"  document: {filename}")
                    print(f"  detected_doc_type: {detected_doc_type}")
                    print(f"  gross_salary: {extracted_data.get('gross_salary')}")
                    print(f"  basic_salary: {extracted_data.get('basic_salary')}")
                    print(f"  hra_received: {extracted_data.get('hra_received')}")
                    print(f"  _doc_type set to: {detected_doc_type}")

                    processed_file_info = {
                        'file_obj': file_obj,
                        'filename': filename,
                        'doc_type': detected_doc_type
                    }

                return (filename, result, processed_file_info)

            except Exception as file_error:
                print(f"[ITR_EXTRACT] {filename}: ERROR: {str(file_error)}")
                return (filename, {
                    'success': False,
                    'error': f'Processing error: {str(file_error)}',
                    'data': {},
                    'filename': filename
                }, None)

        # Prepare files for parallel processing
        file_data_list = []
        for file in files:
            if file.filename == '':
                continue

            # Validate file type
            allowed_extensions = {'pdf', 'jpg', 'jpeg', 'png', 'bmp', 'tiff'}
            if not any(file.filename.lower().endswith('.' + ext) for ext in allowed_extensions):
                continue

            # Read file bytes
            file_bytes = file.read()
            file.seek(0)
            file_data_list.append((file.filename, file_bytes, file))

        # Process files in PARALLEL
        all_results = []
        processed_files = []
        with ThreadPoolExecutor(max_workers=min(4, len(file_data_list))) as executor:
            for filename, result, processed_file_info in executor.map(_process_single_file, file_data_list):
                all_results.append(result)
                if processed_file_info:
                    processed_files.append(processed_file_info)

        # If no files were successfully processed
        if not all_results:
            return jsonify({
                'success': False,
                'error': 'No valid files could be processed',
                'data': {},
            }), 400

        # If only one file, return its result directly
        if len(all_results) == 1:
            result = all_results[0]
            # 🔍 TRACE: Single file case
            print(f"\n[MERGE_INPUT_TRACE] Single file extraction")
            print(f"  _doc_type in result: {result.get('data', {}).get('_doc_type', 'NOT SET')}")
        else:
            # Multiple files: merge results using ai_service merge logic
            print(f"\n[ITR_EXTRACT] Processing {len(all_results)} files, merging with source priority...")

            # Build extraction list with metadata for merge
            extractions_for_merge = []
            for idx, res in enumerate(all_results, 1):
                if res.get('success') and res.get('data'):
                    data = res.get('data', {})
                    # Add doc_type and confidence metadata for merge logic
                    data['_doc_type'] = doc_type  # All files were processed with same doc_type
                    data['_confidence'] = res.get('confidence', 0)

                    # 🔍 TRACE: Log what's being sent to merge
                    print(f"\n[MERGE_INPUT_TRACE] File {idx}")
                    print(f"  filename: {res.get('filename', 'unknown')}")
                    print(f"  _doc_type set to: {data.get('_doc_type')}")
                    print(f"  gross_salary: {data.get('gross_salary')}")
                    print(f"  basic_salary: {data.get('basic_salary')}")
                    print(f"  hra_received: {data.get('hra_received')}")

                    extractions_for_merge.append(data)

            # Use ai_service merge_extractions which handles salary field priority correctly
            import ai_service
            merged_data = ai_service.merge_extractions(extractions_for_merge)
            merged_data.pop('_merge_conflicts', None)  # Remove conflict metadata

            merged_confidence = max((r.get('confidence', 0) for r in all_results if r.get('success')), default=0)
            merged_metadata = {'files_processed': len(all_results), 'individual_results': []}

            for idx, res in enumerate(all_results, 1):
                if res.get('success'):
                    merged_metadata['individual_results'].append({
                        'file': idx,
                        'success': True,
                        'confidence': res.get('confidence', 0)
                    })
                else:
                    merged_metadata['individual_results'].append({
                        'file': idx,
                        'success': False,
                        'error': res.get('error', 'Unknown error')
                    })

            result = {
                'success': bool(merged_data),
                'data': merged_data,
                'confidence': merged_confidence,
                'metadata': merged_metadata
            }

        # ═══════════════════════════════════════════════════════════
        # 🔥 CRITICAL FIX: NORMALIZE & ANNUALIZE EXTRACTED DATA
        # This ensures payslip monthly values are converted to annual
        # ═══════════════════════════════════════════════════════════
        if result.get('success') and result.get('data'):
            try:
                from services import normalization_service
                extracted_data = result.get('data', {})

                # 🔍 TRACE: Log primary_doc_type determination
                primary_doc_type = extracted_data.get('_doc_type', doc_type)
                print(f"\n[NORMALIZATION_TRACE] primary_doc_type determination:")
                print(f"  extracted_data._doc_type: {extracted_data.get('_doc_type', 'NOT SET')}")
                print(f"  doc_type param: {doc_type}")
                print(f"  primary_doc_type: {primary_doc_type}")

                # 🔍 TRACE: Log values BEFORE normalization
                print(f"\n[NORMALIZATION_TRACE] BEFORE normalization:")
                print(f"  gross_salary: {extracted_data.get('gross_salary')}")
                print(f"  basic_salary: {extracted_data.get('basic_salary')}")
                print(f"  hra_received: {extracted_data.get('hra_received')}")
                print(f"  tds_paid: {extracted_data.get('tds_paid')}")
                print(f"  _doc_type: {extracted_data.get('_doc_type', 'NOT SET')}")

                # Normalize the extracted data
                normalized_result = normalization_service.normalize_extractions(
                    [extracted_data],
                    [primary_doc_type]
                )

                normalized_data = normalized_result.get("normalized", {})

                # 🔍 TRACE: Log values AFTER normalization
                print(f"\n[NORMALIZATION_TRACE] AFTER normalization:")
                print(f"  gross_salary: {normalized_data.get('gross_salary')}")
                print(f"  basic_salary: {normalized_data.get('basic_salary')}")
                print(f"  hra_received: {normalized_data.get('hra_received')}")
                print(f"  tds_paid: {normalized_data.get('tds_paid')}")

                # Update result with normalized data
                if normalized_data:
                    result['data'].update(normalized_data)
                    assumptions = normalized_result.get("assumptions", [])
                    if assumptions:
                        result['data']['_normalization_assumptions'] = assumptions
                        print(f"[ITR_EXTRACT] Normalization assumptions: {assumptions}")

            except Exception as e:
                print(f"[ITR_EXTRACT] WARNING: Normalization failed (non-blocking): {e}")
                # Non-blocking: continue without normalization

        # ═══════════════════════════════════════════════════════════
        # SAVE DOCUMENTS TO DISK AND GOOGLE SHEETS
        # ═══════════════════════════════════════════════════════════
        urls = []
        if processed_files and submission_id and result.get('success'):
            # Document type mapping for Sheets columns
            doc_type_col_map = {
                'form16': 'doc_form16_urls',
                'payslip': 'doc_payslip_urls',
                'homeloan': 'doc_homeloan_urls',
                'school': 'doc_school_urls',
                'nps': 'doc_nps_urls',
                'insurance': 'doc_insurance_urls',
                'donation': 'doc_donation_urls'
            }

            # Group files by doc_type
            files_by_type = {}
            for file_info in processed_files:
                dt = file_info['doc_type']
                if dt not in files_by_type:
                    files_by_type[dt] = []
                files_by_type[dt].append(file_info)

            # Save each file and collect URLs
            for doc_type_key, file_list in files_by_type.items():
                type_urls = []
                for file_info in file_list:
                    try:
                        file_obj = file_info['file_obj']
                        url = storage_service.save_file(file_obj, submission_id)
                        if url:
                            type_urls.append(url)
                            urls.append(url)
                            print(f"[ITR_EXTRACT] Saved {file_info['filename']} -> {url}")
                    except Exception as e:
                        print(f"[ITR_EXTRACT] Error saving file {file_info['filename']}: {e}")

                # Save URLs to Google Sheets
                if type_urls:
                    col_name = doc_type_col_map.get(doc_type_key, 'doc_form16_urls')
                    try:
                        sheets_service.append_doc_urls(submission_id, col_name, type_urls)
                        print(f"[ITR_EXTRACT] Saved {len(type_urls)} URLs to {col_name}")
                    except Exception as e:
                        print(f"[ITR_EXTRACT] Error saving URLs to Sheets: {e}")

            # Include URLs in result
            result['urls'] = urls

        elapsed = time.time() - start_time
        if result['success']:
            logger.info(f"[ITR_EXTRACT] Success in {elapsed:.2f}s")
            # 🔍 TRACE: Final output before returning to frontend
            final_data = result.get('data', {})
            print(f"\n[FINAL_RETURN_TRACE] What /api/itr/extract returns to frontend:")
            print(f"  gross_salary: {final_data.get('gross_salary')}")
            print(f"  basic_salary: {final_data.get('basic_salary')}")
            print(f"  hra_received: {final_data.get('hra_received')}")
            print(f"  tds_paid: {final_data.get('tds_paid')}")
            print(f"  _doc_type: {final_data.get('_doc_type', 'NOT SET')}")
            return jsonify(result), 200
        else:
            # Extraction failed — return 200 (no CORS issues) but success:false
            # so the frontend shows "fill manually" instead of "Extracted & Saved"
            logger.warning(f"[ITR_EXTRACT] Extraction failed after {elapsed:.2f}s: {result.get('error', 'unknown')}")
            return jsonify({
                'success': False,
                'extraction_failed': True,
                'error': result.get('error', 'Could not extract data — please fill in manually.'),
                'data': {
                    'personal': {'pan': '', 'name': ''},
                    'income': {
                        'gross_salary': 0, 'basic_salary': 0, 'hra_received': 0,
                        'tds_paid': 0, 'pf_employee': 0, 'pf_employer': 0,
                        'professional_tax': 0, 'lta': 0, 'special_allowance': 0,
                        'car_lease_allowance': 0, 'uniform_allowance': 0,
                        'gratuity': 0, 'leave_encashment': 0,
                    },
                    'deductions': {'home_loan_interest': 0, 'nps_self': 0},
                },
                'confidence': 0,
                'metadata': {'elapsed_seconds': round(elapsed, 2)}
            }), 200

    except TimeoutError as e:
        elapsed = time.time() - start_time
        logger.error(f"[ITR_EXTRACT] TIMEOUT after {elapsed:.2f}s: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Extraction timeout - file took too long to process. Try a smaller file.',
            'data': {},
            'metadata': {'elapsed_seconds': round(elapsed, 2), 'error_type': 'timeout'}
        }), 408

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[ITR_EXTRACT] EXCEPTION after {elapsed:.2f}s: {str(e)}", exc_info=True)
        logger.error(f"[ITR_EXTRACT] Exception type: {type(e).__name__}")
        return jsonify({
            'success': False,
            'error': f'Extraction error: {str(e)}',
            'data': {},
            'metadata': {'elapsed_seconds': round(elapsed, 2), 'error_type': 'exception'}
        }), 500


@itr_bp.route('/extract-batch', methods=['POST'])
def extract_batch():
    """
    Extract ITR data from multiple documents.

    Expects:
    - files: Multiple document files

    Returns:
    {
        'success': bool,
        'results': [
            {
                'filename': str,
                'success': bool,
                'data': {...},
                'errors': {...}
            }
        ]
    }
    """
    try:
        if 'files' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No files provided',
                'results': [],
            }), 400

        files = request.files.getlist('files')

        if not files:
            return jsonify({
                'success': False,
                'error': 'No files selected',
                'results': [],
            }), 400

        results = []

        for file in files:
            try:
                file_bytes = file.read()
                result = _get_processor().process_file(file_bytes, file.filename)

                # 🔥 CRITICAL FIX: Normalize extracted data in batch mode too
                # Even though doc_type is not specified, we should normalize payslips
                if result.get('success') and result.get('data'):
                    try:
                        from services import normalization_service
                        extracted_data = result.get('data', {})

                        # For batch, we don't know doc_type, but we can try to infer it
                        # or normalize cautiously (with guard against double-annualization)
                        inferred_doc_type = extracted_data.get('_doc_type', 'unknown')

                        normalized_result = normalization_service.normalize_extractions(
                            [extracted_data],
                            [inferred_doc_type]
                        )

                        normalized_data = normalized_result.get("normalized", {})
                        if normalized_data:
                            result['data'].update(normalized_data)
                            print(f"[ITR_EXTRACT_BATCH] Normalized {file.filename}: doc_type={inferred_doc_type}")
                    except Exception as norm_error:
                        print(f"[ITR_EXTRACT_BATCH] Normalization warning for {file.filename}: {norm_error}")
                        # Non-blocking: continue without normalization

                results.append({
                    'filename': file.filename,
                    'success': result['success'],
                    'data': result['data'],
                    'errors': result.get('errors', {}),
                })
            except Exception as e:
                results.append({
                    'filename': file.filename,
                    'success': False,
                    'error': str(e),
                    'data': {},
                })

        all_success = all(r['success'] for r in results)

        return jsonify({
            'success': all_success,
            'results': results,
            'processed_count': len(results),
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'results': [],
        }), 500


@itr_bp.route('/validate', methods=['POST'])
def validate_data():
    """
    Validate extracted ITR data.

    Expects:
    {
        'personal': {...},
        'income': {...},
        'deductions': {...},
        'employer': {...},
        'financial': {...}
    }

    Returns:
    {
        'success': bool,
        'errors': {...}
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided',
                'errors': {},
            }), 400

        errors = _get_processor().validator.validate(data)
        is_valid = len(errors) == 0

        return jsonify({
            'success': is_valid,
            'errors': errors,
            'validation_timestamp': datetime.now().isoformat(),
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'errors': {},
        }), 500


@itr_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()}), 200


@itr_bp.route('/diagnose', methods=['GET'])
def diagnose():
    """Ping OpenAI, check env vars, and return a production health report."""
    import os, requests as _req
    report = {
        'timestamp': datetime.now().isoformat(),
        'openai_api_key_set': bool(os.getenv('OPENAI_API_KEY')),
        'openai_model': os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
        'openai_ping': None,
        'processor_init': None,
        'errors': []
    }

    # 1 ── Test OpenAI text API
    try:
        key = os.getenv('OPENAI_API_KEY', '')
        r = _req.post(
            'https://api.openai.com/v1/chat/completions',
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
            json={
                'model': os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
                'messages': [{'role': 'user', 'content': 'Reply with {"ok":true}'}],
                'max_tokens': 10,
                'response_format': {'type': 'json_object'},
                'temperature': 0.0,
            },
            timeout=20,
        )
        report['openai_ping'] = f'HTTP {r.status_code}'
        if r.status_code == 200:
            report['openai_text_response'] = r.json()['choices'][0]['message']['content']
        else:
            report['errors'].append(f'OpenAI returned {r.status_code}: {r.text[:200]}')
    except Exception as exc:
        report['openai_ping'] = 'FAILED'
        report['errors'].append(f'OpenAI ping error: {exc}')

    # 2 ── Test processor lazy-init
    try:
        _get_processor()
        report['processor_init'] = 'OK'
    except Exception as exc:
        report['processor_init'] = 'FAILED'
        report['errors'].append(f'Processor init error: {exc}')

    report['healthy'] = len(report['errors']) == 0
    return jsonify(report), 200
