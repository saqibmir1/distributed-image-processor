from fastapi import FastAPI, UploadFile, File, Request, HTTPException 
from worker import create_task
import shutil
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from celery.result import AsyncResult
from worker import celery_app
from config import Config
import hashlib
import redis.asyncio as redis

# SENIOR NOTE: Using async Redis client to avoid blocking the event loop
redis_client = redis.from_url(Config.CELERY_BROKER_URL, encoding="utf-8", decode_responses=True)

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

RATE_LIMIT_DURATION = 60
RATE_LIMIT_MAX_REQUESTS = 5

async def check_rate_limit(request: Request):
    # SENIOR NOTE: Using X-Forwarded-For is critical when behind a proxy (like Nginx/Load Balancer)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0]
    else:
        client_ip = request.client.host
    
    key = f'rate_limit:{client_ip}'
    
    # SENIOR NOTE: Lua script ensures atomicity. 
    # Without this, we have a race condition where we increment but fail to expire.
    # This turns 2 round-trips into 1.
    lua_script = """
    local current = redis.call("INCR", KEYS[1])
    if current == 1 then
        redis.call("EXPIRE", KEYS[1], ARGV[2])
    end
    return current
    """
    
    # Execute atomic script
    try:
        request_count = await redis_client.eval(lua_script, 1, key, RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_DURATION)
    except Exception as e:
        # Fallback open if Redis fails (don't block users)
        print(f"Rate limit error: {e}")
        return

    # Check limit
    if request_count > RATE_LIMIT_MAX_REQUESTS:
        remaining_ttl = await redis_client.ttl(key)
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Please try again in {remaining_ttl} seconds."
        )


@app.post("/upload")
async def upload_image(request: Request, file: UploadFile = File(...)):

    # check rate limit
    await check_rate_limit(request)

    # idempotency check
    content = await file.read()
    file_hash=hashlib.sha256(content).hexdigest()

    cache_key = f'image_hash:{file_hash}'
    cached_task_id = await redis_client.get(cache_key)

    if cached_task_id:
        print(f"Image already processed. Task ID: {cached_task_id}")
        return {
            "message": "Image already processed.",
            "task_id": cached_task_id, # decoded automatically
            "file_name": file.filename,
            "status": "Cached"
        }

    # upload
    await file.seek(0)
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

    # trigger worker
    task = create_task.delay(object_name)
    await redis_client.set(cache_key, task.id, ex=3600)
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