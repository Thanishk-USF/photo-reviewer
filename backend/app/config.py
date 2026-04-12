"""
Configuration settings for the Flask application
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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
