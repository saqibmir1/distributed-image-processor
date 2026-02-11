# Distributed Image Processor

A high-performance, distributed image processing system built with Python, FastAPI, Celery, Redis, and MinIO.

## Key Features
*   **Fully Distributed**: API and Worker are decoupled; communicate via Redis (Messaging) and MinIO (Storage).
*   **Object Storage**: Uses MinIO (S3-compatible) for source and processed images. No shared file systems.
*   **Robust Queueing**: Celery + Redis for reliable task management.
*   **Fault Tolerance**:
    *   **Dead Letter Queue**: Failed tasks are captured in Redis (`dead_letter_queue`) with reason and timestamp.
    *   **Chaos Engineering**: Random failure simulation (commented out) for testing resilience.
    *   **Retries**: Automatic backoff and retry policy for connection errors.
*   **Deduplication**: Redis caching prevents re-processing the same image (MD5 hash check).
*   **Observability**: Flower instance for real-time monitoring of queues and workers.
*   **UI/UX**: Premium Glassmorphism interface with drag-and-drop, real-time progress, and visual result display.

## Architecture
1.  **Web (FastAPI)**: Accepts upload -> Calculcates Hash -> Checks Cache -> Uploads to MinIO -> Pushes Task to Redis -> Returns ID.
2.  **Worker (Celery)**: Pulls Task -> Downloads from MinIO -> Processes (Thumbnail) -> Uploads to MinIO -> Returns Key.
3.  **MinIO**: S3-compatible storage for direct file handling. Presigned URLs generated for secure browser access.
4.  **Redis**: Broker, Result Backend, Cache, and DLQ storage.

## Quick Start
1.  **Configure**: Copy `.env.example` to `.env` (already set up).
2.  **Run**:
    ```bash
    docker compose up --build -d
    ```
3.  **Access**:
    *   **Web UI**: [http://localhost:8000](http://localhost:8000)
    *   **Flower (Monitor)**: [http://localhost:5555](http://localhost:5555)
    *   **MinIO Console**: [http://localhost:9001](http://localhost:9001) (`minioadmin` / `minioadmin`)

## Development
*   **Add Dependencies**: Update `requirements.txt` and rebuild.
*   **Logs**: `docker compose logs -f`
*   **View DLQ**: `docker compose exec redis redis-cli lrange dead_letter_queue 0 -1`