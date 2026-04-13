"""
MongoDB service for the Flask application
"""
import os
from datetime import datetime
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson.json_util import dumps, loads

# MongoDB connection
mongo_uri = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
mongo_db_name = os.environ.get('MONGO_DB_NAME', 'photo_reviewer')

client = MongoClient(mongo_uri)
db = client[mongo_db_name]
photos_collection = db['photos']
default_upload_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads')
INTERNAL_RESPONSE_FIELDS = {
    'image_binary',
    'image_hash',
    'model_version',
    'legacy_analysis',
    'score_source',
    'aesthetic_source',
    'tagger_source',
    'style_source',
    'suggestion_source',
    'tag_confidences',
    'inference_devices',
    'device_policy',
    'fallback_used',
}


def _upload_root_folder():
    return os.environ.get('UPLOAD_FOLDER', default_upload_folder)


def _candidate_file_paths(filename):
    if not filename:
        return []

    upload_root = _upload_root_folder()
    return [
        os.path.join(upload_root, 'originals', filename),
        os.path.join(upload_root, 'thumbnails', filename),
        os.path.join(upload_root, filename),
    ]


def _resolve_existing_file(filename):
    for candidate in _candidate_file_paths(filename):
        if os.path.exists(candidate):
            return candidate
    return None


def _delete_files_for_photo(photo):
    for key in ('thumbnailUrl', 'imageUrl'):
        filename = _extract_filename_from_api_image_url(photo.get(key))
        if not filename:
            continue

        for candidate in _candidate_file_paths(filename):
            if os.path.exists(candidate):
                try:
                    os.remove(candidate)
                except OSError:
                    pass


def _extract_filename_from_api_image_url(url_value):
    if not isinstance(url_value, str):
        return None
    if not url_value.startswith('/api/images/'):
        return None
    return url_value.split('/')[-1]


def _image_exists_on_disk(photo):
    for key in ('thumbnailUrl', 'imageUrl'):
        filename = _extract_filename_from_api_image_url(photo.get(key))
        if _resolve_existing_file(filename):
            return True
    return False


def _is_photo_renderable(photo):
    if 'image_binary' in photo:
        return True

    if _image_exists_on_disk(photo):
        return True

    image_url = photo.get('imageUrl')
    if isinstance(image_url, str) and (image_url.startswith('http://') or image_url.startswith('https://') or image_url.startswith('data:')):
        return True

    return False


def _photo_dedup_key(photo):
    if photo.get('image_hash'):
        return f"hash:{photo.get('image_hash')}"

    image_url = photo.get('imageUrl')
    if isinstance(image_url, str) and image_url:
        return f"url:{image_url}"

    thumbnail_url = photo.get('thumbnailUrl')
    if isinstance(thumbnail_url, str) and thumbnail_url:
        return f"thumb:{thumbnail_url}"

    return None


def _strip_internal_fields(photo):
    for key in INTERNAL_RESPONSE_FIELDS:
        if key in photo:
            del photo[key]

def save_analysis(analysis_data, overwrite_existing=False):
    """
    Save photo analysis data to MongoDB
    
    Args:
        analysis_data: Dictionary containing analysis results
        
    Returns:
        ID of the inserted document
    """
    # Work on a copy so we do not mutate the API response payload.
    document = dict(analysis_data)

    # Add timestamp if not present
    if 'uploadDate' not in document:
        document['uploadDate'] = datetime.now().isoformat()
    
    # If there's an image path, read the image and store it as binary
    image_path = None
    if 'imageUrl' in document:
        image_url = document['imageUrl']
        if image_url.startswith('/api/images/'):
            image_filename = image_url.split('/')[-1]
            image_path = _resolve_existing_file(image_filename)
    
    # Store the image binary if available
    if image_path and os.path.exists(image_path):
        with open(image_path, 'rb') as img_file:
            document['image_binary'] = img_file.read()
    
    # Avoid duplicate inserts when the same image hash was already analyzed.
    # Optionally overwrite existing records to refresh stale model outputs.
    image_hash = document.get('image_hash')
    if image_hash:
        existing = photos_collection.find_one({'image_hash': image_hash}, {'_id': 1})
        if existing and '_id' in existing:
            if overwrite_existing:
                photos_collection.update_one({'_id': existing['_id']}, {'$set': document})
            return str(existing['_id'])

    # Insert the document
    result = photos_collection.insert_one(document)
    
    return str(result.inserted_id)

def convert_objectid_to_str(obj):
    """
    Recursively convert all ObjectId instances to strings in a nested structure
    
    Args:
        obj: The object to convert (can be a dict, list, or ObjectId)
        
    Returns:
        The object with all ObjectIds converted to strings
    """
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, dict):
        for key, value in list(obj.items()):
            obj[key] = convert_objectid_to_str(value)
        return obj
    elif isinstance(obj, list):
        return [convert_objectid_to_str(item) for item in obj]
    else:
        return obj

def get_photos(limit=24, offset=0, include_broken=False, include_duplicates=False):
    """
    Get a page of photos from MongoDB
    
    Returns:
        Tuple: (photos, has_more, next_offset)
    """
    if limit is None or limit < 1:
        limit = 24

    if offset is None or offset < 0:
        offset = 0

    cursor = photos_collection.find().sort('_id', -1)
    photos = []
    renderable_seen = 0
    seen_keys = set()

    for photo in cursor:
        if not include_broken and not _is_photo_renderable(photo):
            continue

        if not include_duplicates:
            dedup_key = _photo_dedup_key(photo)
            if dedup_key and dedup_key in seen_keys:
                continue
            if dedup_key:
                seen_keys.add(dedup_key)

        if renderable_seen < offset:
            renderable_seen += 1
            continue

        photos.append(photo)
        renderable_seen += 1
        if len(photos) >= (limit + 1):
            break

    has_more = len(photos) > limit
    if has_more:
        photos = photos[:limit]
    
    # Process each photo
    for photo in photos:
        # Convert ObjectId to string for JSON serialization
        if '_id' in photo:
            photo['id'] = str(photo['_id'])
            del photo['_id']
        
        # Convert any nested ObjectId to string using recursive function
        convert_objectid_to_str(photo)
        
        # Remove non-public internal fields from response.
        _strip_internal_fields(photo)
    
    next_offset = offset + len(photos)
    return photos, has_more, next_offset

def get_photo_by_id(photo_id):
    """
    Get a photo by ID
    
    Args:
        photo_id: ID of the photo
        
    Returns:
        Photo document or None if not found
    """
    try:
        # Try to convert to ObjectId for MongoDB lookup
        object_id = ObjectId(photo_id)
        photo = photos_collection.find_one({'_id': object_id})
    except Exception:
        # If not a valid ObjectId, try looking up by the id field
        photo = photos_collection.find_one({'id': photo_id})
    
    if photo:
        # Convert ObjectId to string for JSON serialization
        if '_id' in photo:
            photo['id'] = str(photo['_id'])
            del photo['_id']
            
        # Convert any nested ObjectId to string using recursive function
        convert_objectid_to_str(photo)
        
        # Remove non-public internal fields from response.
        _strip_internal_fields(photo)
    
    return photo


def get_photo_by_image_hash(image_hash):
    """Get the latest photo record by deterministic image hash."""
    if not image_hash:
        return None

    return photos_collection.find_one({'image_hash': image_hash}, sort=[('_id', -1)])

def get_image_binary(photo_id):
    """
    Get the binary image data for a photo
    
    Args:
        photo_id: ID of the photo
        
    Returns:
        Binary image data or None if not found
    """
    try:
        # Try to convert to ObjectId for MongoDB lookup
        object_id = ObjectId(photo_id)
        photo = photos_collection.find_one({'_id': object_id})
    except Exception:
        # If not a valid ObjectId, try looking up by the id field
        photo = photos_collection.find_one({'id': photo_id})
    
    if photo and 'image_binary' in photo:
        return photo['image_binary']
    return None

def delete_photo(photo_id):
    """
    Delete a photo by ID
    
    Args:
        photo_id: ID of the photo
        
    Returns:
        True if deleted, False otherwise
    """
    query = None
    photo = None

    try:
        # Try to convert to ObjectId for MongoDB lookup
        object_id = ObjectId(photo_id)
        query = {'_id': object_id}
        photo = photos_collection.find_one(query)
    except Exception:
        # If not a valid ObjectId, try lookup by the id field
        query = {'id': photo_id}
        photo = photos_collection.find_one(query)

    if not photo:
        return False

    result = photos_collection.delete_one(query)
    if result.deleted_count > 0:
        _delete_files_for_photo(photo)
        return True

    return False