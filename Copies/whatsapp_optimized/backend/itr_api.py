"""
Flask API endpoints for ITR document extraction.
Integrates with the ITR document processor.
"""

from flask import Blueprint, request, jsonify
from itr_extractor import ITRDocumentProcessor
import os
from datetime import datetime
import storage_service
import sheets_service
from werkzeug.utils import secure_filename

itr_bp = Blueprint('itr', __name__, url_prefix='/api/itr')

# Initialize the processor
processor = ITRDocumentProcessor(use_ocr=True)

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
                result = processor.process_file(file_bytes, filename, doc_type=doc_type)
                file_elapsed = time.time() - file_start
                print(f"[ITR_EXTRACT] {filename}: {file_elapsed:.2f}s, success={result.get('success')}")

                # DEBUG: Log the full result if extraction failed
                if not result.get('success'):
                    print(f"[ITR_EXTRACT] {filename}: FAILED RESULT: {result}")

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
                            test_result = processor.process_file(file_bytes, filename, doc_type=test_type)
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
                    processed_file_info = {
                        'file_obj': file_obj,
                        'filename': filename,
                        'doc_type': detected_doc_type
                    }

                return (filename, result, processed_file_info)

            except Exception as file_error:
                error_msg = str(file_error)
                print(f"[ITR_EXTRACT] {filename}: EXCEPTION: {error_msg}")
                import traceback
                traceback.print_exc()
                return (filename, {
                    'success': False,
                    'error': f'Processing error: {error_msg}',
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
        else:
            # Multiple files: merge results
            print(f"[ITR_EXTRACT] Processing {len(all_results)} files, merging results...")
            merged_data = {}
            merged_confidence = 0
            merged_metadata = {'files_processed': len(all_results), 'individual_results': []}

            for idx, res in enumerate(all_results, 1):
                if res.get('success') and res.get('data'):
                    # Merge data from each file (later files override earlier ones for same fields)
                    merged_data.update(res.get('data', {}))
                    merged_confidence = max(merged_confidence, res.get('confidence', 0))
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
            response = jsonify(result)
            logger.info(f"[ITR_EXTRACT] Returning 200 response")
            return response, 200
        else:
            logger.error(f"[ITR_EXTRACT] Failed after {elapsed:.2f}s")
            logger.error(f"[ITR_EXTRACT] Result keys: {result.keys()}")
            logger.error(f"[ITR_EXTRACT] Error message: {result.get('error', 'Unknown error')}")

            response_dict = {
                'success': False,
                'error': result.get('error', 'Extraction failed - no valid data extracted'),
                'data': result.get('data', {}),
                'metadata': {**result.get('metadata', {}), 'elapsed_seconds': round(elapsed, 2)}
            }

            logger.error(f"[ITR_EXTRACT] Building 400 response")
            try:
                response = jsonify(response_dict)
                logger.error(f"[ITR_EXTRACT] Response created successfully, returning 400")
                return response, 400
            except Exception as e:
                logger.error(f"[ITR_EXTRACT] ERROR creating response: {str(e)}", exc_info=True)
                # Fallback minimal response
                return jsonify({'success': False, 'error': 'Response encoding error'}), 400

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
    Extract ITR data from multiple documents using PARALLEL PROCESSING.

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
        ],
        'processed_count': int,
        'processing_time': float
    }
    """
    import time
    from concurrent.futures import ThreadPoolExecutor

    batch_start = time.time()

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

        # ═══════════════════════════════════════════════════════════
        # PARALLEL BATCH EXTRACTION (OPTIMIZED)
        # ═══════════════════════════════════════════════════════════

        def _process_batch_file(file_data):
            """Process a single file in batch. Returns result dict."""
            filename, file_bytes = file_data
            try:
                result = processor.process_file(file_bytes, filename)
                return {
                    'filename': filename,
                    'success': result['success'],
                    'data': result.get('data', {}),
                    'errors': result.get('errors', {}),
                    'confidence': result.get('confidence', 0),
                }
            except Exception as e:
                return {
                    'filename': filename,
                    'success': False,
                    'error': str(e),
                    'data': {},
                    'errors': {'extraction': [str(e)]},
                    'confidence': 0,
                }

        # Prepare file data
        file_data_list = []
        for file in files:
            if file.filename == '':
                continue
            file_bytes = file.read()
            file_data_list.append((file.filename, file_bytes))

        print(f"[BATCH_EXTRACT] Processing {len(file_data_list)} files in parallel...")

        # Process in PARALLEL with ThreadPoolExecutor
        results = []
        with ThreadPoolExecutor(max_workers=min(4, len(file_data_list))) as executor:
            for result in executor.map(_process_batch_file, file_data_list):
                results.append(result)
                success_status = "✓" if result['success'] else "✗"
                print(f"[BATCH_EXTRACT] {success_status} {result['filename']}: "
                      f"success={result['success']}, confidence={result.get('confidence', 0):.2f}")

        batch_elapsed = time.time() - batch_start
        all_success = all(r['success'] for r in results)

        print(f"[BATCH_EXTRACT] Completed {len(results)} files in {batch_elapsed:.2f}s")

        return jsonify({
            'success': all_success,
            'results': results,
            'processed_count': len(results),
            'processing_time': round(batch_elapsed, 2),
            'files_per_second': round(len(results) / batch_elapsed, 2),
        }), 200

    except Exception as e:
        print(f"[BATCH_EXTRACT] EXCEPTION: {str(e)}")
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

        errors = processor.validator.validate(data)
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
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'ocr_available': processor.use_ocr,
        'timestamp': datetime.now().isoformat(),
    }), 200
