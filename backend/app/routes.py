"""
API routes for the Flask application
"""
from flask import Blueprint, request, jsonify, send_from_directory, Response, current_app
import os
import uuid
import hashlib
import hmac
from datetime import datetime
from werkzeug.utils import secure_filename
from app.models.runtime import analyze_image_runtime, get_runtime_model_version
from app.services.analysis_contract import normalize_analysis_result

# Create a blueprint for the API routes
api = Blueprint('api', __name__)

# Define the upload folder
UPLOAD_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
ORIGINALS_FOLDER = os.path.join(UPLOAD_ROOT, 'originals')
THUMBNAILS_FOLDER = os.path.join(UPLOAD_ROOT, 'thumbnails')
LEGACY_UPLOAD_FOLDER = UPLOAD_ROOT
os.makedirs(ORIGINALS_FOLDER, exist_ok=True)
os.makedirs(THUMBNAILS_FOLDER, exist_ok=True)
print(f"Upload root: {UPLOAD_ROOT}")  # Add this line for debugging

from PIL import Image

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tiff'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def resolve_image_path(filename):
    for folder in (THUMBNAILS_FOLDER, ORIGINALS_FOLDER, LEGACY_UPLOAD_FOLDER):
        candidate = os.path.join(folder, filename)
        if os.path.exists(candidate):
            return folder, filename
    return None, None


def _admin_debug_expected_key():
    expected = (
        current_app.config.get('ADMIN_DEBUG_KEY')
        or os.environ.get('ADMIN_DEBUG_KEY')
        or os.environ.get('ADMIN_DEBUG_PASSWORD')
        or ''
    )
    return str(expected).strip()


def _is_admin_debug_authorized(req):
    expected = _admin_debug_expected_key()
    if not expected:
        return False

    provided = str(req.headers.get('X-Admin-Debug-Key', '')).strip()
    if not provided:
        return False

    return hmac.compare_digest(provided, expected)

@api.route('/analyze', methods=['POST'])
def analyze_image():
    """
    Analyze an uploaded image
    """
    try:
        print("Analyze request received")
        # Check if the post request has the file part
        if 'image' not in request.files:
            print("No image in request.files")
            return jsonify({'success': False, 'error': 'No image provided'}), 400
        
        file = request.files['image']
        print(f"File received: {file.filename}")
        
        # If user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No image selected'}), 400
        
        filename = secure_filename(file.filename)
        if not filename:
            return jsonify({'success': False, 'error': 'Invalid file name'}), 400

        if not allowed_file(filename):
            return jsonify({'success': False, 'error': 'Unsupported image type'}), 400

        if file.mimetype and not file.mimetype.startswith('image/'):
            return jsonify({'success': False, 'error': 'Invalid content type'}), 400

        # Validate the uploaded payload is a decodable image.
        try:
            file.stream.seek(0)
            img = Image.open(file.stream)
            img.verify()
            file.stream.seek(0)
        except Exception:
            return jsonify({'success': False, 'error': 'Invalid image file'}), 400

        file.stream.seek(0)
        image_bytes = file.stream.read()
        image_hash = hashlib.sha256(image_bytes).hexdigest()
        file.stream.seek(0)

        force_reanalyze_value = str(request.form.get('forceReanalyze', '')).strip().lower()
        force_reanalyze = force_reanalyze_value in {'1', 'true', 'yes', 'on'}

        overwrite_existing = False
        existing_record = None

        # Return existing analysis for duplicate uploads of the same image content.
        from app.services.mongo_service import get_photo_by_image_hash, convert_objectid_to_str
        existing = get_photo_by_image_hash(image_hash)
        if existing:
            current_model_version = get_runtime_model_version(current_app.config)
            current_epoch = int(current_app.config.get('ADAPTIVE_PROFILE_EPOCH', 2) or 2)
            existing_model_version = str(existing.get('model_version', '') or '').strip()
            try:
                existing_epoch = int(existing.get('adaptive_epoch', 0) or 0)
            except (TypeError, ValueError):
                existing_epoch = 0

            stale_existing = (
                force_reanalyze
                or existing_model_version != current_model_version
                or existing_epoch < current_epoch
            )

            if stale_existing:
                overwrite_existing = True
                existing_record = existing
            else:
                existing = convert_objectid_to_str(existing)
                if 'image_binary' in existing:
                    del existing['image_binary']
                if 'image_hash' in existing:
                    del existing['image_hash']
                if 'id' not in existing and '_id' in existing:
                    existing['id'] = existing['_id']
                existing['success'] = True
                existing = normalize_analysis_result(existing)
                return jsonify(existing)

        # Generate a unique ID for this analysis.
        # When refreshing a stale duplicate, keep the same public ID for stable links.
        analysis_id = str(uuid.uuid4())
        if existing_record:
            existing_public_id = existing_record.get('id')
            if isinstance(existing_public_id, str) and existing_public_id.strip():
                analysis_id = existing_public_id.strip()
            elif existing_record.get('_id') is not None:
                analysis_id = str(existing_record.get('_id'))

        # Save the uploaded file
        file_path = os.path.join(ORIGINALS_FOLDER, f"{analysis_id}_{filename}")
        file.save(file_path)

        # Open once for scoring and metadata generation after successful save.
        with Image.open(file_path) as uploaded_img:
            runtime_result = analyze_image_runtime(
                uploaded_img,
                filename,
                current_app.config,
            )
            runtime_meta = runtime_result.pop('_runtime', {})

            thumbnail_filename = f"{analysis_id}_thumbnail_{filename}"
            thumbnail_path = os.path.join(THUMBNAILS_FOLDER, thumbnail_filename)
            thumbnail_img = uploaded_img.copy()
            thumbnail_img.thumbnail((300, 300))
            thumbnail_img.save(thumbnail_path)
        
        # Canonical response payload (contract-safe)
        result = normalize_analysis_result({
            'id': analysis_id,
            'success': True,
            'imageUrl': f"/api/images/{analysis_id}_{filename}",
            'thumbnailUrl': f"/api/images/{thumbnail_filename}",
            'filename': filename,
            'uploadDate': datetime.now().isoformat(),
            'aestheticScore': runtime_result.get('aestheticScore'),
            'technicalScore': runtime_result.get('technicalScore'),
            'composition': runtime_result.get('composition'),
            'lighting': runtime_result.get('lighting'),
            'color': runtime_result.get('color'),
            'style': runtime_result.get('style'),
            'mood': runtime_result.get('mood'),
            'tags': runtime_result.get('tags'),
            'hashtags': runtime_result.get('hashtags'),
            'suggestions': runtime_result.get('suggestions'),
        })
        
        # Save image data to MongoDB
        from app.services.mongo_service import save_analysis
        mongo_payload = {
            **result,
            'image_hash': image_hash,
            'model_version': runtime_meta.get('model_version', get_runtime_model_version(current_app.config)),
            'score_source': runtime_meta.get('scorer_source', 'pretrained'),
            'aesthetic_source': runtime_meta.get('aesthetic_source', 'clip-only'),
            'tagger_source': runtime_meta.get('tagger_source', 'pretrained'),
            'style_source': runtime_meta.get('style_source', 'pretrained'),
            'suggestion_source': runtime_meta.get('suggestion_source', 'pretrained'),
            'tag_confidences': runtime_meta.get('tag_confidences', {}),
            'inference_devices': runtime_meta.get('inference_devices', {}),
            'device_policy': runtime_meta.get('device_policy', {}),
            'adaptive_epoch': int(current_app.config.get('ADAPTIVE_PROFILE_EPOCH', 2) or 2),
            'fallback_used': bool(runtime_meta.get('fallback_used', False)),
        }
        save_analysis(mongo_payload, overwrite_existing=overwrite_existing)

        from app.services.adaptive_learning import invalidate_adaptive_profile_cache
        invalidate_adaptive_profile_cache()
        
        # Before returning the result
        print("Analysis complete, returning result")
        return jsonify(result)
    
    except Exception as e:
        print(f"Error in analyze_image: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Failed to analyze image'}), 500

@api.route('/photos', methods=['GET'])
def get_photos():
    """
    Get all photos
    """
    try:
        from app.services.mongo_service import get_photos
        limit_param = request.args.get('limit', '24')
        offset_param = request.args.get('offset', '0')
        include_broken = request.args.get('includeBroken', 'false').lower() == 'true'
        include_duplicates = request.args.get('includeDuplicates', 'false').lower() == 'true'

        try:
            limit = int(limit_param)
        except ValueError:
            limit = 24

        try:
            offset = int(offset_param)
        except ValueError:
            offset = 0

        limit = max(1, min(limit, 100))
        offset = max(0, offset)
        photos, has_more, next_offset = get_photos(
            limit=limit,
            offset=offset,
            include_broken=include_broken,
            include_duplicates=include_duplicates,
        )
        
        # Format the response
        for photo in photos:
            # Ensure thumbnail URL is set
            if 'thumbnailUrl' not in photo and 'imageUrl' in photo:
                photo['thumbnail'] = photo['imageUrl']
            elif 'thumbnailUrl' in photo:
                photo['thumbnail'] = photo['thumbnailUrl']

            if 'name' not in photo:
                photo['name'] = photo.get('filename', f"Photo {photo.get('id', '')}")
            
            # Format date for display
            if 'uploadDate' in photo:
                # Simple formatting - in a real app you'd use a proper date formatter
                photo['date'] = photo['uploadDate']
            
            # Ensure score is set
            if 'score' not in photo and 'aestheticScore' in photo:
                photo['score'] = photo['aestheticScore']
        
        return jsonify({
            'success': True,
            'photos': photos,
            'limit': limit,
            'offset': offset,
            'hasMore': has_more,
            'nextOffset': next_offset
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api.route('/photos/<photo_id>', methods=['GET'])
def get_photo(photo_id):
    """
    Get a specific photo by ID
    """
    try:
        from app.services.mongo_service import get_photo_by_id
        photo = get_photo_by_id(photo_id)
        
        if not photo:
            return jsonify({'success': False, 'error': 'Photo not found'}), 404
        
        # Ensure success flag and stable schema
        photo['success'] = True
        photo = normalize_analysis_result(photo)
        if 'id' not in photo:
            photo['id'] = photo_id
        
        return jsonify(photo)
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api.route('/photos/<photo_id>', methods=['DELETE'])
def delete_photo(photo_id):
    """
    Delete a specific photo by ID
    """
    try:
        from app.services.mongo_service import delete_photo
        success = delete_photo(photo_id)
        
        if not success:
            return jsonify({'success': False, 'error': 'Photo not found'}), 404

        from app.services.adaptive_learning import invalidate_adaptive_profile_cache
        invalidate_adaptive_profile_cache()
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/admin/adaptive-profile', methods=['GET'])
def get_admin_adaptive_profile():
    """Return a protected, sanitized adaptive profile summary for admin diagnostics."""
    if not _admin_debug_expected_key():
        return jsonify({'success': False, 'error': 'ADMIN_DEBUG_KEY is not configured'}), 503

    if not _is_admin_debug_authorized(request):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    from app.services.adaptive_learning import get_adaptive_profile

    refresh_value = str(request.args.get('refresh', '')).strip().lower()
    force_refresh = refresh_value in {'1', 'true', 'yes', 'on'}

    profile = get_adaptive_profile(force_refresh=force_refresh) or {}

    score_means = profile.get('score_means', {}) or {}
    score_quantiles = profile.get('score_quantiles', {}) or {}

    dynamic_labels = []
    for label in profile.get('dynamic_labels', []) or []:
        cleaned = str(label).strip()
        if cleaned:
            dynamic_labels.append(cleaned)

    top_learned_tags = []
    tag_priors = profile.get('tag_priors', {}) or {}
    if isinstance(tag_priors, dict):
        def _prior_sort_value(item_value):
            try:
                return float(item_value)
            except (TypeError, ValueError):
                return 0.0

        sorted_tags = sorted(tag_priors.items(), key=lambda item: _prior_sort_value(item[1]), reverse=True)
        for tag, prior in sorted_tags[:20]:
            cleaned_tag = str(tag).strip()
            if not cleaned_tag:
                continue
            try:
                prior_value = round(float(prior), 4)
            except (TypeError, ValueError):
                continue
            top_learned_tags.append({'tag': cleaned_tag, 'prior': prior_value})

    top_suggestions = []
    suggestion_pool = profile.get('suggestion_pool', []) or []
    if isinstance(suggestion_pool, list):
        for item in suggestion_pool[:20]:
            if not isinstance(item, dict):
                continue
            text = str(item.get('text', '')).strip()
            if not text:
                continue
            try:
                freq = int(item.get('freq', 0) or 0)
            except (TypeError, ValueError):
                freq = 0
            top_suggestions.append({'text': text, 'freq': freq})

    payload = {
        'success': True,
        'profile': {
            'sampleCount': int(profile.get('sample_count', 0) or 0),
            'scoreMeans': score_means,
            'scoreQuantiles': score_quantiles,
            'dynamicLabelCount': len(dynamic_labels),
            'dynamicLabelPreview': dynamic_labels[:30],
            'topLearnedTags': top_learned_tags,
            'topSuggestions': top_suggestions,
            'adaptiveConfig': {
                'enabled': bool(current_app.config.get('ADAPTIVE_PROFILE_ENABLED', True)),
                'profileEpoch': int(current_app.config.get('ADAPTIVE_PROFILE_EPOCH', 2) or 2),
                'includeLegacyDocs': bool(current_app.config.get('ADAPTIVE_INCLUDE_LEGACY_DOCS', False)),
                'maxDocs': int(current_app.config.get('ADAPTIVE_PROFILE_MAX_DOCS', 500) or 500),
                'cacheTtlSeconds': int(current_app.config.get('ADAPTIVE_PROFILE_CACHE_TTL_SECONDS', 300) or 300),
                'maxDynamicTagLabels': int(current_app.config.get('ADAPTIVE_MAX_DYNAMIC_TAG_LABELS', 80) or 80),
                'maxSuggestionPool': int(current_app.config.get('ADAPTIVE_MAX_SUGGESTION_POOL', 240) or 240),
                'tagMinOccurrences': int(current_app.config.get('ADAPTIVE_TAG_MIN_OCCURRENCES', 2) or 2),
                'dynamicTagMinOccurrences': int(current_app.config.get('ADAPTIVE_DYNAMIC_TAG_MIN_OCCURRENCES', 3) or 3),
                'pretrainedDeviceMode': str(current_app.config.get('PRETRAINED_DEVICE_MODE', 'auto') or 'auto'),
                'pretrainedDeviceLegacy': str(current_app.config.get('PRETRAINED_DEVICE', 'cpu') or 'cpu'),
                'pretrainedCudaIndex': int(current_app.config.get('PRETRAINED_CUDA_INDEX', 0) or 0),
                'runtimeModelVersion': str(current_app.config.get('MODEL_RUNTIME_VERSION', 'pretrained-v3') or 'pretrained-v3'),
                'taggerUseSegmentSplit': bool(current_app.config.get('PRETRAINED_TAGGER_USE_SEGMENT_SPLIT', True)),
                'taggerSegmentModelId': str(current_app.config.get('PRETRAINED_TAGGER_SEGMENT_MODEL_ID', '') or ''),
                'taggerSegmentMinScore': float(current_app.config.get('PRETRAINED_TAGGER_SEGMENT_MIN_SCORE', 0.15) or 0.15),
                'taggerSplitFullWeight': float(current_app.config.get('PRETRAINED_TAGGER_SPLIT_FULL_WEIGHT', 0.35) or 0.35),
                'taggerSplitForegroundWeight': float(current_app.config.get('PRETRAINED_TAGGER_SPLIT_FOREGROUND_WEIGHT', 0.45) or 0.45),
                'taggerSplitBackgroundWeight': float(current_app.config.get('PRETRAINED_TAGGER_SPLIT_BACKGROUND_WEIGHT', 0.20) or 0.20),
                'useNimaAesthetic': bool(current_app.config.get('USE_NIMA_AESTHETIC', False)),
                'nimaModelId': str(current_app.config.get('NIMA_MODEL_ID', '') or ''),
                'nimaBlendWeight': float(current_app.config.get('NIMA_AESTHETIC_BLEND_WEIGHT', 0.65) or 0.65),
                'warmupOnStartup': bool(current_app.config.get('PRETRAINED_WARMUP_ON_STARTUP', True)),
                'warmupRunInference': bool(current_app.config.get('PRETRAINED_WARMUP_RUN_INFERENCE', False)),
                'warmupFailFast': bool(current_app.config.get('PRETRAINED_WARMUP_FAIL_FAST', False)),
            },
            'lastWarmupSummary': current_app.config.get('MODEL_WARMUP_SUMMARY', {}),
            'generatedAt': datetime.utcnow().isoformat() + 'Z',
        },
    }
    return jsonify(payload)


@api.route('/admin/warmup', methods=['POST'])
def run_admin_model_warmup():
    """Trigger protected model warmup for diagnostics and preloading."""
    if not _admin_debug_expected_key():
        return jsonify({'success': False, 'error': 'ADMIN_DEBUG_KEY is not configured'}), 503

    if not _is_admin_debug_authorized(request):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    payload = request.get_json(silent=True) or {}
    run_inference = bool(payload.get('runInference', False))

    from app.services.model_warmup import warmup_models

    summary = warmup_models(current_app.config, run_inference=run_inference)
    status_code = 200 if summary.get('ok') else 500
    return jsonify({'success': bool(summary.get('ok')), 'warmup': summary}), status_code

@api.route('/images/<filename>', methods=['GET'])
def get_image(filename):
    """
    Serve an image file
    """
    safe_filename = secure_filename(filename)
    if safe_filename != filename:
        return jsonify({'error': 'Invalid filename'}), 400

    # First try to get from filesystem
    folder, resolved_name = resolve_image_path(safe_filename)
    if folder:
        return send_from_directory(folder, resolved_name)
    
    # If not found in filesystem, try to get from MongoDB
    # Extract the ID from the filename (assuming format: uuid_originalname.ext)
    photo_id = safe_filename.split('_')[0]
    
    from app.services.mongo_service import get_image_binary
    image_binary = get_image_binary(photo_id)
    
    if image_binary:
        # Determine content type based on file extension
        content_type = 'image/jpeg'  # Default
        if safe_filename.lower().endswith('.png'):
            content_type = 'image/png'
        elif safe_filename.lower().endswith('.gif'):
            content_type = 'image/gif'
        
        # Return the binary data with appropriate content type
        return Response(image_binary, mimetype=content_type)
    
    # If not found anywhere, return 404
    return jsonify({'error': 'Image not found'}), 404

# Remove the duplicate get_image route that appears at the end of the file
