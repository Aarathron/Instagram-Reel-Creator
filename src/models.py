import os
from sqlalchemy import Column, String, DateTime, Float, Integer, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from datetime import datetime
from enum import Enum
import uuid
from pydantic import BaseModel, ConfigDict
from typing import Optional

Base = declarative_base()

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"

class VideoJob(Base):
    __tablename__ = "video_jobs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String, default=JobStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Input parameters
    image_filename = Column(String)
    audio_filename = Column(String)
    lyrics = Column(Text)
    language = Column(String, nullable=True)
    font_size = Column(Integer, default=45)
    font_color = Column(String, default="yellow")
    words_per_group = Column(Integer, default=3)
    timing_offset = Column(Float, default=0.0)
    min_duration = Column(Float, default=1.0)
    alignment_mode = Column(String, default="auto")
    debug_mode = Column(Boolean, default=False)
    
    # Results
    output_filename = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    progress_percentage = Column(Integer, default=0)
    
    # Processing info
    worker_id = Column(String, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)

# Pydantic models for API
class JobRequest(BaseModel):
    lyrics: str
    language: Optional[str] = None
    font_size: Optional[int] = 45
    font_color: Optional[str] = "yellow"
    words_per_group: Optional[int] = 3
    timing_offset: Optional[float] = 0.0
    min_duration: Optional[float] = 1.0
    alignment_mode: Optional[str] = "auto"
    debug_mode: Optional[bool] = False

class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress_percentage: int
    error_message: Optional[str] = None
    output_filename: Optional[str] = None
    processing_time_seconds: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)
    
    @classmethod
    def from_video_job(cls, job: 'VideoJob'):
        """Create JobResponse from VideoJob, mapping id to job_id."""
        return cls(
            job_id=job.id,
            status=job.status,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            progress_percentage=job.progress_percentage,
            error_message=job.error_message,
            output_filename=job.output_filename,
            processing_time_seconds=job.processing_time_seconds
        )

# Database setup
# Use shared volume in production, local file in development
DATABASE_DIR = os.environ.get("DATABASE_DIR", ".")
DATABASE_URL = f"sqlite:///{DATABASE_DIR}/jobs.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()