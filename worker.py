import os
import time
from celery import Celery
from PIL import Image
from config import Config


celery_app = Celery('tasks', broker=Config.CELERY_BROKER_URL, backend=Config.CELERY_RESULT_BACKEND)

# SENIOR NOTE: By default, Celery uses Pickle (insecure). We force JSON.
celery_app.conf.update(Config.CELERY_CONFIG)


@celery_app.task(name="create_task")
def create_task(file_path):
    try:
        with Image.open(file_path) as img:
            img.thumbnail((128,128))

            thumb_path = f'{file_path}.thumbnail.jpg'
            img.save(thumb_path, 'JPEG')

            return f'Generated: {thumb_path}'
    
    except Exception as e:
        print(f'Error processing {file_path}: {str(e)}')
        return False

