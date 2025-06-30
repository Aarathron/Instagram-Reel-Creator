import os
import uuid
import logging
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.orm import Session
import redis
import json

from models import (
    VideoJob, JobStatus, JobRequest, JobResponse, 
    create_tables, get_db, SessionLocal
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis connection
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# Create FastAPI app
app = FastAPI(title="Instagram Reel Creator - Async API")

# Create database tables
create_tables()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

# File storage paths
UPLOAD_DIR = os.path.abspath("uploads")
OUTPUT_DIR = os.path.abspath("output")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

async def save_upload_file(upload_file: UploadFile, destination: str) -> bool:
    """Save an uploaded file in chunks to disk."""
    try:
        CHUNK_SIZE = 1024 * 1024
        with open(destination, "wb") as f:
            while True:
                chunk = await upload_file.read(CHUNK_SIZE)
                if not chunk:
                    break
                f.write(chunk)
        return True
    except Exception as e:
        logger.error(f"Error saving {upload_file.filename} to {destination}: {e}")
        return False

@app.post("/jobs/create-video", response_model=JobResponse)
async def create_video_job(
    image: UploadFile = File(..., description="Image file (JPEG/PNG)"),
    audio: UploadFile = File(..., description="Audio file (MP3/WAV/FLAC)"),
    lyrics: str = Form(..., description="Lyrics text for alignment"),
    language: Optional[str] = Form(None, description="Language code (e.g., 'en', 'hi', etc.)"),
    font_size: Optional[int] = Form(45, description="Font size for subtitles"),
    font_color: Optional[str] = Form("yellow", description="Font color for subtitles"),
    words_per_group: Optional[int] = Form(3, description="Number of words to show together"),
    timing_offset: Optional[float] = Form(0.0, description="Global timing offset in seconds"),
    min_duration: Optional[float] = Form(1.0, description="Minimum duration for each subtitle in seconds"),
    alignment_mode: Optional[str] = Form("auto", description="Alignment mode: 'auto', 'elevenlabs', or 'even'"),
    debug_mode: Optional[bool] = Form(False, description="Enable debug mode with timing information"),
    db: Session = Depends(get_db)
):
    """
    Create a new video processing job.
    Returns immediately with job_id for status polling.
    """
    logger.info("=== Creating new video job ===")
    
    # Validate input files
    if not lyrics or not lyrics.strip():
        raise HTTPException(status_code=400, detail="Lyrics text is required")
    
    img_ext = os.path.splitext(image.filename)[1].lower()
    if img_ext not in [".jpg", ".jpeg", ".png"]:
        raise HTTPException(status_code=400, detail="Image must be JPG or PNG")
    
    aud_ext = os.path.splitext(audio.filename)[1].lower()
    if aud_ext not in [".mp3", ".wav", ".flac"]:
        raise HTTPException(status_code=400, detail="Audio must be MP3, WAV, or FLAC")
    
    # Create job record
    job = VideoJob(
        lyrics=lyrics,
        language=language,
        font_size=font_size,
        font_color=font_color,
        words_per_group=words_per_group,
        timing_offset=timing_offset,
        min_duration=min_duration,
        alignment_mode=alignment_mode,
        debug_mode=debug_mode,
        image_filename=f"{job.id}_image{img_ext}" if 'job' in locals() else None,
        audio_filename=f"{job.id}_audio{aud_ext}" if 'job' in locals() else None
    )
    
    # Generate filenames with job ID
    job.image_filename = f"{job.id}_image{img_ext}"
    job.audio_filename = f"{job.id}_audio{aud_ext}"
    
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Save uploaded files
    image_path = os.path.join(UPLOAD_DIR, job.image_filename)
    audio_path = os.path.join(UPLOAD_DIR, job.audio_filename)
    
    if not await save_upload_file(image, image_path):
        job.status = JobStatus.FAILED
        job.error_message = "Failed to save image file"
        db.commit()
        raise HTTPException(status_code=500, detail="Failed to save image file")
    
    if not await save_upload_file(audio, audio_path):
        job.status = JobStatus.FAILED
        job.error_message = "Failed to save audio file"
        db.commit()
        raise HTTPException(status_code=500, detail="Failed to save audio file")
    
    # Add job to Redis queue
    job_data = {
        "job_id": job.id,
        "image_path": image_path,
        "audio_path": audio_path,
        "lyrics": lyrics,
        "language": language,
        "font_size": font_size,
        "font_color": font_color,
        "words_per_group": words_per_group,
        "timing_offset": timing_offset,
        "min_duration": min_duration,
        "alignment_mode": alignment_mode,
        "debug_mode": debug_mode
    }
    
    redis_client.lpush("video_jobs", json.dumps(job_data))
    
    logger.info(f"✓ Created job {job.id} and added to queue")
    
    return JobResponse.from_orm(job)

@app.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Get job status and details."""
    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobResponse.from_orm(job)

@app.get("/jobs/{job_id}/download")
async def download_video(job_id: str, db: Session = Depends(get_db)):
    """Download completed video file."""
    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Job is not completed. Status: {job.status}")
    
    if not job.output_filename:
        raise HTTPException(status_code=404, detail="Output file not found")
    
    output_path = os.path.join(OUTPUT_DIR, job.output_filename)
    if not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="Output file not found on disk")
    
    return FileResponse(
        output_path,
        media_type="video/mp4",
        filename=f"video_{job_id}.mp4"
    )

@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str, db: Session = Depends(get_db)):
    """Delete job and associated files."""
    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Delete associated files
    files_to_delete = []
    if job.image_filename:
        files_to_delete.append(os.path.join(UPLOAD_DIR, job.image_filename))
    if job.audio_filename:
        files_to_delete.append(os.path.join(UPLOAD_DIR, job.audio_filename))
    if job.output_filename:
        files_to_delete.append(os.path.join(OUTPUT_DIR, job.output_filename))
    
    for file_path in files_to_delete:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to delete file {file_path}: {e}")
    
    # Delete job record
    db.delete(job)
    db.commit()
    
    return {"message": "Job deleted successfully"}

@app.get("/jobs")
async def list_jobs(
    status: Optional[JobStatus] = None,
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List jobs with optional filtering."""
    query = db.query(VideoJob)
    
    if status:
        query = query.filter(VideoJob.status == status)
    
    jobs = query.order_by(VideoJob.created_at.desc()).offset(offset).limit(limit).all()
    
    return [JobResponse.from_orm(job) for job in jobs]

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check database
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        
        # Check Redis
        redis_client.ping()
        
        return {"status": "healthy", "timestamp": datetime.utcnow()}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

if __name__ == "__main__":
    import uvicorn
    import socket
    
    def find_free_port(start_port=8001, max_port=8020):
        for port in range(start_port, max_port + 1):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('0.0.0.0', port))
                    return port
            except OSError:
                continue
        raise OSError("No free ports found in range")
    
    port = find_free_port()
    logger.info(f"Starting async API server on port {port}")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        timeout_keep_alive=120
    )