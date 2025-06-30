# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
Instagram Reel Creator is a FastAPI-based video processing service that creates video reels by combining static images with audio and synchronized subtitles. The service now supports both synchronous and asynchronous processing with job queuing and optional GPU acceleration via RunPod.

## Architecture Types

### 1. Legacy Sync API (src/main.py)
Single endpoint that processes videos synchronously - users wait for completion.

### 2. Async API with Job Queue (src/async_api.py + src/worker.py) 
Modern architecture with Redis job queue, status polling, and background processing.

### 3. RunPod Serverless GPU (runpod/)
GPU-accelerated processing that auto-scales and only charges when running.

## Development Commands

### Running Async System (Recommended)
```bash
# Start Redis, API, and worker
export ELEVENLABS_API_KEY="your_api_key_here"
docker-compose up --build

# Services:
# - Redis: localhost:6379
# - Async API: localhost:8002 
# - Worker: background processing
# - Legacy API: localhost:8003 (optional)
```

### Manual Development
```bash
# Install dependencies
pip install -r requirements.txt

# Start Redis locally
redis-server

# In separate terminals:
python src/async_api.py    # API server
python src/worker.py       # Background worker
```

### Testing
```bash
# Test async API
curl -X POST localhost:8002/jobs/create-video \
  -F "image=@test.jpg" \
  -F "audio=@test.mp3" \
  -F "lyrics=test lyrics"

# Check job status  
curl localhost:8002/jobs/{job_id}

# Web interface
open http://localhost:8002/static/async_test.html
```

## New API Endpoints

### Async Job API
- `POST /jobs/create-video` - Submit job, returns job_id
- `GET /jobs/{job_id}` - Check job status and progress
- `GET /jobs/{job_id}/download` - Download completed video
- `DELETE /jobs/{job_id}` - Delete job and files
- `GET /jobs` - List all jobs with filtering
- `GET /health` - Health check for API and Redis

### Job States
- **pending**: Job queued, waiting for worker
- **processing**: Worker actively processing (with progress %)
- **completed**: Video ready for download
- **failed**: Processing failed with error message

## RunPod Serverless Setup

### Deployment
```bash
# Build and push Docker image
cd runpod/
docker build -t your-registry/reel-creator-gpu .
docker push your-registry/reel-creator-gpu

# Deploy to RunPod:
# 1. Create endpoint with GPU image
# 2. Set ELEVENLABS_API_KEY environment variable
# 3. Note endpoint ID for integration
```

### Integration
```bash
export RUNPOD_API_KEY="your_runpod_key"
export RUNPOD_ENDPOINT_ID="your_endpoint_id"
python runpod/deploy.py  # Test deployment
```

## Architecture Components

### Database (SQLite)
- **VideoJob**: Stores job metadata, status, progress, files
- **Auto-migration**: Tables created automatically on startup

### Redis Queue
- **video_jobs**: FIFO queue for pending jobs
- **Persistence**: Jobs survive Redis restarts

### File Management
- **uploads/**: Input files (image, audio) stored by job_id
- **output/**: Generated videos stored temporarily
- **Cleanup**: Automatic file deletion when jobs are deleted

### Key Technologies
- **FastAPI + SQLAlchemy**: API and database ORM
- **Redis**: Job queue and caching
- **MoviePy**: Video processing and composition
- **ElevenLabs Scribe API**: Speech-to-text transcription
- **RunPod**: Serverless GPU infrastructure

## Environment Variables
- **Required**: `ELEVENLABS_API_KEY` for speech-to-text
- **Optional**: `REDIS_URL` (defaults to localhost:6379)
- **RunPod**: `RUNPOD_API_KEY`, `RUNPOD_ENDPOINT_ID`

## Performance Characteristics
- **CPU Processing**: 2-5 minutes per video
- **GPU Processing**: 30-60 seconds per video (3-5x faster)
- **RunPod Cold Start**: ~30-60 seconds
- **Optimal for**: <5 jobs/day (cost-effective serverless)

## File Limits
- Image: JPEG/PNG, max 100MB
- Audio: MP3/WAV/FLAC, max 100MB
- Processing timeout: 10 minutes per job