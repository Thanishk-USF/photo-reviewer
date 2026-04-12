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
    PRETRAINED_DEVICE = os.environ.get('PRETRAINED_DEVICE', 'cpu')
    PRETRAINED_SCORER_MODEL_ID = os.environ.get('PRETRAINED_SCORER_MODEL_ID', 'openai/clip-vit-base-patch32')
    PRETRAINED_TAGGER_MODEL_ID = os.environ.get('PRETRAINED_TAGGER_MODEL_ID', 'openai/clip-vit-base-patch32')
    PRETRAINED_TAGGER_CAPTION_MODEL_ID = os.environ.get('PRETRAINED_TAGGER_CAPTION_MODEL_ID', 'Salesforce/blip-image-captioning-base')
    PRETRAINED_STYLE_MODEL_ID = os.environ.get('PRETRAINED_STYLE_MODEL_ID', PRETRAINED_TAGGER_MODEL_ID)
    PRETRAINED_SUGGESTER_MODEL_ID = os.environ.get('PRETRAINED_SUGGESTER_MODEL_ID', PRETRAINED_TAGGER_MODEL_ID)

    # Adaptive profiling (learn from historical analyses)
    ADAPTIVE_PROFILE_ENABLED = _env_bool('ADAPTIVE_PROFILE_ENABLED', True)
    ADAPTIVE_PROFILE_MAX_DOCS = _env_int('ADAPTIVE_PROFILE_MAX_DOCS', 500)
    ADAPTIVE_PROFILE_CACHE_TTL_SECONDS = _env_int('ADAPTIVE_PROFILE_CACHE_TTL_SECONDS', 300)
    ADAPTIVE_MAX_DYNAMIC_TAG_LABELS = _env_int('ADAPTIVE_MAX_DYNAMIC_TAG_LABELS', 80)
    ADAPTIVE_MAX_CANDIDATE_LABELS = _env_int('ADAPTIVE_MAX_CANDIDATE_LABELS', 160)
    ADAPTIVE_MAX_SUGGESTION_POOL = _env_int('ADAPTIVE_MAX_SUGGESTION_POOL', 240)
    ADAPTIVE_SCORE_MIN_SAMPLES = _env_int('ADAPTIVE_SCORE_MIN_SAMPLES', 40)
    ADAPTIVE_SCORE_CALIBRATION_WEIGHT = _env_float('ADAPTIVE_SCORE_CALIBRATION_WEIGHT', 0.15)
    ADAPTIVE_TAG_PRIOR_WEIGHT = _env_float('ADAPTIVE_TAG_PRIOR_WEIGHT', 0.35)

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
