from fastapi import FastAPI, UploadFile, File 
from worker import create_task
import shutil
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from celery.result import AsyncResult
from worker import celery_app
from config import Config
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    # 1. save the file to disk (shared volume)
    file_location = f'{Config.UPLOAD_FOLDER}/{file.filename}'

    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 2. send the task to celery we pass the path not image itself
    task = create_task.delay(file_location)
    return {
        "message": "Image received. Processing in background.",
        "task_id": task.id,
        "file_name": file_location
    }
    
@app.get("/")
def read_root():
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/tasks/{task_id}")
def task_result(task_id: str):
    task_result = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "task_status": task_result.status,
        "task_result": task_result.result
    }