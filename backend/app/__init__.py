"""
Flask application factory
"""
from flask import Flask
from flask.json import jsonify
from flask_cors import CORS
from bson import ObjectId
import os
import json  # Import the standard json module
from app.config import get_config

# Custom JSON encoder that can handle ObjectId
class MongoJSONEncoder(json.JSONEncoder):  # Use the standard json module
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

def create_app():
    app = Flask(__name__)

    # Load environment-specific configuration.
    app.config.from_object(get_config())

    cors_origins = app.config.get('CORS_ORIGINS')
    if cors_origins and cors_origins != ['']:
        CORS(app, resources={r"/api/*": {"origins": cors_origins}})
    else:
        CORS(app)
    
    # Use custom JSON encoder
    app.json_provider_class.encoder = MongoJSONEncoder
    # or for older Flask versions:
    # app.json_encoder = MongoJSONEncoder
    
    # Register blueprints
    from app.routes import api
    app.register_blueprint(api, url_prefix='/api')

    if bool(app.config.get('PRETRAINED_WARMUP_ON_STARTUP', True)):
        from app.services.model_warmup import warmup_models

        run_inference = bool(app.config.get('PRETRAINED_WARMUP_RUN_INFERENCE', False))
        fail_fast = bool(app.config.get('PRETRAINED_WARMUP_FAIL_FAST', False))

        try:
            warmup_summary = warmup_models(app.config, run_inference=run_inference)
            app.config['MODEL_WARMUP_SUMMARY'] = warmup_summary
            if (not warmup_summary.get('ok')) and fail_fast:
                raise RuntimeError('Model warmup failed and PRETRAINED_WARMUP_FAIL_FAST=true')
        except Exception as exc:
            app.config['MODEL_WARMUP_SUMMARY'] = {
                'ok': False,
                'error': str(exc),
            }
            if fail_fast:
                raise
    
    return app
