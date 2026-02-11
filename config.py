import os
import boto3
from botocore.client import Config as BotoConfig

# Centralized Configuration
class Config:
    # Redis
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    
    # MinIO
    MINIO_ENDPOINT = os.environ.get('MINIO_ENDPOINT', 'localhost:9000')
    MINIO_ACCESS_KEY = os.environ.get('MINIO_ACCESS_KEY', 'minioadmin')
    MINIO_SECRET_KEY = os.environ.get('MINIO_SECRET_KEY', 'minioadmin')
    MINIO_BUCKET_SOURCE = 'source-images'
    MINIO_BUCKET_OUTPUT = 'processed-images'
    
    # Task Settings
    CELERY_CONFIG = {
        'task_serializer': 'json',
        'accept_content': ['json'],
        'result_serializer': 'json',
        'timezone': 'UTC',
        'enable_utc': True,
        'broker_connection_retry_on_startup': True,
    }

    @staticmethod
    def get_minio_client(internal=True):
        # When running inside docker, we use 'minio:9000'
        # When accessing from host machine (browser), we need 'localhost:9000'
        endpoint = f'http://{Config.MINIO_ENDPOINT}'
        
        if not internal:
             # Force localhost for browser-accessible URLs
             # In a real deployed env, this would be the public domain
            endpoint = 'http://localhost:9000'

        return boto3.client('s3',
                            endpoint_url=endpoint,
                            aws_access_key_id=Config.MINIO_ACCESS_KEY,
                            aws_secret_access_key=Config.MINIO_SECRET_KEY,
                            config=BotoConfig(signature_version='s3v4'),
                            region_name='us-east-1')

# Create buckets on startup
def init_minio():
    s3 = Config.get_minio_client()
    for bucket in [Config.MINIO_BUCKET_SOURCE, Config.MINIO_BUCKET_OUTPUT]:
        try:
            s3.head_bucket(Bucket=bucket)
        except:
            try:
                s3.create_bucket(Bucket=bucket)
                print(f"Created bucket: {bucket}")
            except Exception as e:
                print(f"Failed to create bucket {bucket}: {e}")

if __name__ == "__main__":
    init_minio()