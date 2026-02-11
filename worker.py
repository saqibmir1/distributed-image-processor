import os
import time
from celery import Celery
from PIL import Image
from config import Config
import boto3
import io

import redis
import json

celery_app = Celery('tasks', broker=Config.CELERY_BROKER_URL, backend=Config.CELERY_RESULT_BACKEND)
redis_client = redis.StrictRedis.from_url(Config.CELERY_BROKER_URL)

# SENIOR NOTE: By default, Celery uses Pickle (insecure). We force JSON.
celery_app.conf.update(Config.CELERY_CONFIG)


@celery_app.task(name="create_task", bind=True, autoretry_for=(ConnectionError,), retry_backoff=True, retry_kwargs={'max_retries': 5})
def create_task(self, object_name):
    try:

        time.sleep(5)
        s3 = Config.get_minio_client()
        
        # 1. Download image from Source Bucket
        file_stream = io.BytesIO()
        s3.download_fileobj(Config.MINIO_BUCKET_SOURCE, object_name, file_stream)
        file_stream.seek(0)
        
        # 2. Process Image
        with Image.open(file_stream) as img:
            img.thumbnail((128,128))
            
            output_stream = io.BytesIO()
            img.save(output_stream, format='JPEG')
            output_stream.seek(0)
            
            # 3. Upload to Output Bucket
            output_object_name = f"thumbnail-{object_name}"
            s3.upload_fileobj(
                output_stream,
                Config.MINIO_BUCKET_OUTPUT,
                output_object_name,
                ExtraArgs={'ContentType': 'image/jpeg'}
            )

            return output_object_name
    
    except Exception as e:
        print(f'Error processing {object_name}: {str(e)}')
        send_to_dead_letter_queue(object_name, str(e))
        # Rethrow to let Celery handle retries if needed, or return FAILED
        raise e

def send_to_dead_letter_queue(object_name, reason):
    payload = {
        "object_name": object_name,
        "reason": reason,
        "timestamp": time.time()
    }
    # Use json.dumps for proper string serialization
    redis_client.lpush("dead_letter_queue", json.dumps(payload))
    print(f'Sent {object_name} to DLQ: {reason}')
