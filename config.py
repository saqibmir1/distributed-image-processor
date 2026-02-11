import os

# Centralized Configuration
class Config:
    # Redis
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    
    # File Storage
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    
    # Task Settings
    CELERY_CONFIG = {
        'task_serializer': 'json',
        'accept_content': ['json'],
        'result_serializer': 'json',
        'timezone': 'UTC',
        'enable_utc': True,
        'broker_connection_retry_on_startup': True,
    }

# Create the folder immediately when config is loaded
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)