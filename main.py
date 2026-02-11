from fastapi import FastAPI, UploadFile, File 
from worker import create_task
import shutil
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from celery.result import AsyncResult
from worker import celery_app
from config import Config
import boto3

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# Ensure buckets exist
try:
    s3 = Config.get_minio_client()
    for bucket in [Config.MINIO_BUCKET_SOURCE, Config.MINIO_BUCKET_OUTPUT]:
        try:
            s3.head_bucket(Bucket=bucket)
        except:
            s3.create_bucket(Bucket=bucket)
except Exception as e:
    print(f"Warning: Could not connect to MinIO on startup: {e}")

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    # 1. Upload file to MinIO Source Bucket
    s3 = Config.get_minio_client()
    object_name = file.filename
    
    try:
        s3.upload_fileobj(
            file.file,
            Config.MINIO_BUCKET_SOURCE,
            object_name
        )
    except Exception as e:
        return {"error": f"Failed to upload to MinIO: {str(e)}"}

    # 2. send the task to celery we pass the object name
    task = create_task.delay(object_name)
    return {
        "message": "Image received. Processing in background.",
        "task_id": task.id,
        "file_name": object_name
    }
    
@app.get("/")
def read_root():
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/tasks/{task_id}")
def task_result(task_id: str):
    task_result = AsyncResult(task_id, app=celery_app)
    
    result = task_result.result
    
    # If successful, result is the object name in the output bucket.
    # Generate a presigned URL for it.
    if task_result.status == 'SUCCESS' and result:
        try:
            # generating url for the USER, so must be external (localhost)
            s3 = Config.get_minio_client(internal=False)
            url = s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': Config.MINIO_BUCKET_OUTPUT,
                    'Key': result
                },
                ExpiresIn=3600
            )
            return {
                "task_id": task_id,
                "task_status": task_result.status,
                "task_result": url 
            }
        except Exception as e:
             return {
                "task_id": task_id,
                "task_status": task_result.status,
                "task_result": f"Error generating URL: {str(e)}"
            }

    return {
        "task_id": task_id,
        "task_status": task_result.status,
        "task_result": str(result)
    }