"""
Configuration settings for the Flask application
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _env_float(name, default=0.0):
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _env_int(name, default=0):
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

class Config:
    """Base configuration"""
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-please-change-in-production')
    
    # MongoDB settings
    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
    MONGO_DB_NAME = os.environ.get('MONGO_DB_NAME', 'photo_reviewer')
    
    # Upload settings
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB max upload size
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')

    # Pretrained-only defaults
    USE_PRETRAINED_SCORER = _env_bool('USE_PRETRAINED_SCORER', True)
    USE_PRETRAINED_TAGGER = _env_bool('USE_PRETRAINED_TAGGER', True)
    USE_PRETRAINED_STYLE = _env_bool('USE_PRETRAINED_STYLE', USE_PRETRAINED_TAGGER)
    USE_PRETRAINED_SUGGESTER = _env_bool('USE_PRETRAINED_SUGGESTER', True)
    FALLBACK_ON_MODEL_ERROR = _env_bool('FALLBACK_ON_MODEL_ERROR', False)
    MODEL_CANARY_PERCENT = _env_float('MODEL_CANARY_PERCENT', 100.0)
    PRETRAINED_SCORE_BLEND_ALPHA = _env_float('PRETRAINED_SCORE_BLEND_ALPHA', 0.70)
    PRETRAINED_DEVICE_MODE = os.environ.get('PRETRAINED_DEVICE_MODE', 'auto')
    PRETRAINED_CUDA_INDEX = _env_int('PRETRAINED_CUDA_INDEX', 0)
    PRETRAINED_DEVICE = os.environ.get('PRETRAINED_DEVICE', 'cpu')
    PRETRAINED_SCORER_MODEL_ID = os.environ.get('PRETRAINED_SCORER_MODEL_ID', 'openai/clip-vit-base-patch32')
    PRETRAINED_TAGGER_MODEL_ID = os.environ.get('PRETRAINED_TAGGER_MODEL_ID', 'openai/clip-vit-base-patch32')
    PRETRAINED_TAGGER_CAPTION_MODEL_ID = os.environ.get('PRETRAINED_TAGGER_CAPTION_MODEL_ID', 'Salesforce/blip-image-captioning-base')
    PRETRAINED_TAGGER_USE_SEGMENT_SPLIT = _env_bool('PRETRAINED_TAGGER_USE_SEGMENT_SPLIT', True)
    PRETRAINED_TAGGER_SEGMENT_MODEL_ID = os.environ.get('PRETRAINED_TAGGER_SEGMENT_MODEL_ID', 'nvidia/segformer-b0-finetuned-ade-512-512')
    PRETRAINED_TAGGER_SEGMENT_MIN_SCORE = _env_float('PRETRAINED_TAGGER_SEGMENT_MIN_SCORE', 0.15)
    PRETRAINED_TAGGER_SPLIT_FULL_WEIGHT = _env_float('PRETRAINED_TAGGER_SPLIT_FULL_WEIGHT', 0.35)
    PRETRAINED_TAGGER_SPLIT_FOREGROUND_WEIGHT = _env_float('PRETRAINED_TAGGER_SPLIT_FOREGROUND_WEIGHT', 0.45)
    PRETRAINED_TAGGER_SPLIT_BACKGROUND_WEIGHT = _env_float('PRETRAINED_TAGGER_SPLIT_BACKGROUND_WEIGHT', 0.20)
    PRETRAINED_TAGGER_SPLIT_MIN_FOREGROUND_COVERAGE = _env_float('PRETRAINED_TAGGER_SPLIT_MIN_FOREGROUND_COVERAGE', 0.08)
    PRETRAINED_TAGGER_SPLIT_MAX_FOREGROUND_COVERAGE = _env_float('PRETRAINED_TAGGER_SPLIT_MAX_FOREGROUND_COVERAGE', 0.90)
    PRETRAINED_TAGGER_BACKGROUND_SCENE_MIN_SCORE = _env_float('PRETRAINED_TAGGER_BACKGROUND_SCENE_MIN_SCORE', 0.18)
    PRETRAINED_STYLE_MODEL_ID = os.environ.get('PRETRAINED_STYLE_MODEL_ID', PRETRAINED_TAGGER_MODEL_ID)
    PRETRAINED_SUGGESTER_MODEL_ID = os.environ.get('PRETRAINED_SUGGESTER_MODEL_ID', PRETRAINED_TAGGER_MODEL_ID)
    MODEL_RUNTIME_VERSION = os.environ.get('MODEL_RUNTIME_VERSION', 'pretrained-v3')
    USE_NIMA_AESTHETIC = _env_bool('USE_NIMA_AESTHETIC', True)
    NIMA_MODEL_ID = os.environ.get('NIMA_MODEL_ID', '')
    NIMA_AESTHETIC_BLEND_WEIGHT = _env_float('NIMA_AESTHETIC_BLEND_WEIGHT', 0.65)
    NIMA_MIN_CONFIDENCE = _env_float('NIMA_MIN_CONFIDENCE', 0.15)
    NIMA_TOP_K = _env_int('NIMA_TOP_K', 10)
    PRETRAINED_WARMUP_ON_STARTUP = _env_bool('PRETRAINED_WARMUP_ON_STARTUP', True)
    PRETRAINED_WARMUP_RUN_INFERENCE = _env_bool('PRETRAINED_WARMUP_RUN_INFERENCE', False)
    PRETRAINED_WARMUP_FAIL_FAST = _env_bool('PRETRAINED_WARMUP_FAIL_FAST', False)

    # Adaptive profiling (learn from historical analyses)
    ADAPTIVE_PROFILE_ENABLED = _env_bool('ADAPTIVE_PROFILE_ENABLED', True)
    ADAPTIVE_PROFILE_EPOCH = _env_int('ADAPTIVE_PROFILE_EPOCH', 2)
    ADAPTIVE_INCLUDE_LEGACY_DOCS = _env_bool('ADAPTIVE_INCLUDE_LEGACY_DOCS', False)
    ADAPTIVE_PROFILE_MAX_DOCS = _env_int('ADAPTIVE_PROFILE_MAX_DOCS', 500)
    ADAPTIVE_PROFILE_CACHE_TTL_SECONDS = _env_int('ADAPTIVE_PROFILE_CACHE_TTL_SECONDS', 300)
    ADAPTIVE_MAX_DYNAMIC_TAG_LABELS = _env_int('ADAPTIVE_MAX_DYNAMIC_TAG_LABELS', 80)
    ADAPTIVE_MAX_CANDIDATE_LABELS = _env_int('ADAPTIVE_MAX_CANDIDATE_LABELS', 160)
    ADAPTIVE_MAX_SUGGESTION_POOL = _env_int('ADAPTIVE_MAX_SUGGESTION_POOL', 240)
    ADAPTIVE_TAG_MIN_OCCURRENCES = _env_int('ADAPTIVE_TAG_MIN_OCCURRENCES', 2)
    ADAPTIVE_DYNAMIC_TAG_MIN_OCCURRENCES = _env_int('ADAPTIVE_DYNAMIC_TAG_MIN_OCCURRENCES', 3)
    ADAPTIVE_SCORE_MIN_SAMPLES = _env_int('ADAPTIVE_SCORE_MIN_SAMPLES', 40)
    ADAPTIVE_SCORE_CALIBRATION_WEIGHT = _env_float('ADAPTIVE_SCORE_CALIBRATION_WEIGHT', 0.15)
    ADAPTIVE_TAG_PRIOR_WEIGHT = _env_float('ADAPTIVE_TAG_PRIOR_WEIGHT', 0.35)
    ADAPTIVE_TAG_CONFIDENCE_WEIGHT = _env_float('ADAPTIVE_TAG_CONFIDENCE_WEIGHT', 0.70)
    ADAPTIVE_TAG_MIN_CONFIDENCE = _env_float('ADAPTIVE_TAG_MIN_CONFIDENCE', 0.35)
    ADAPTIVE_TAG_SENSITIVE_MIN_CONFIDENCE = _env_float('ADAPTIVE_TAG_SENSITIVE_MIN_CONFIDENCE', 0.55)
    ADAPTIVE_REQUIRE_TAG_CONFIDENCE = _env_bool('ADAPTIVE_REQUIRE_TAG_CONFIDENCE', False)

    # Admin debug access
    ADMIN_DEBUG_KEY = os.environ.get('ADMIN_DEBUG_KEY') or os.environ.get('ADMIN_DEBUG_PASSWORD', '')

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    # In production, use a proper secret key
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    # Set proper CORS origins in production
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '').split(',')

# Select configuration based on environment
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get the current configuration"""
    env = os.environ.get('FLASK_ENV', 'default')
    return config.get(env, config['default'])
