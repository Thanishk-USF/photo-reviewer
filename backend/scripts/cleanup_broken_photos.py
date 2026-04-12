"""Cleanup utility for removing non-renderable legacy photo documents.

Usage:
  python scripts/cleanup_broken_photos.py            # dry run
  python scripts/cleanup_broken_photos.py --apply    # delete broken rows
"""
import argparse
import os
from pymongo import MongoClient


def extract_filename_from_api_image_url(url_value):
    if not isinstance(url_value, str):
        return None
    if not url_value.startswith('/api/images/'):
        return None
    return url_value.split('/')[-1]


def candidate_file_paths(upload_folder, filename):
    if not filename:
        return []

    return [
        os.path.join(upload_folder, 'originals', filename),
        os.path.join(upload_folder, 'thumbnails', filename),
        os.path.join(upload_folder, filename),
    ]


def image_exists_on_disk(photo, upload_folder):
    for key in ('thumbnailUrl', 'imageUrl'):
        filename = extract_filename_from_api_image_url(photo.get(key))
        for candidate in candidate_file_paths(upload_folder, filename):
            if os.path.exists(candidate):
                return True
    return False


def is_renderable(photo, upload_folder):
    if 'image_binary' in photo:
        return True

    if image_exists_on_disk(photo, upload_folder):
        return True

    image_url = photo.get('imageUrl')
    if isinstance(image_url, str) and (
        image_url.startswith('http://')
        or image_url.startswith('https://')
        or image_url.startswith('data:')
    ):
        return True

    return False


def main():
    parser = argparse.ArgumentParser(description='Cleanup non-renderable photo documents from MongoDB.')
    parser.add_argument('--apply', action='store_true', help='Delete records instead of dry-run output.')
    args = parser.parse_args()

    mongo_uri = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
    mongo_db_name = os.environ.get('MONGO_DB_NAME', 'photo_reviewer')
    upload_folder = os.environ.get(
        'UPLOAD_FOLDER',
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads'),
    )

    client = MongoClient(mongo_uri)
    photos = client[mongo_db_name]['photos']

    all_docs = list(photos.find())
    broken_ids = [doc['_id'] for doc in all_docs if not is_renderable(doc, upload_folder)]

    print(f'total_documents={len(all_docs)}')
    print(f'broken_documents={len(broken_ids)}')

    if not args.apply:
        print('dry_run=true')
        print('Run with --apply to delete broken documents.')
        return

    if not broken_ids:
        print('No broken documents to delete.')
        return

    result = photos.delete_many({'_id': {'$in': broken_ids}})
    print(f'deleted_documents={result.deleted_count}')


if __name__ == '__main__':
    main()
