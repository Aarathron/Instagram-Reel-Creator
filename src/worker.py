import os
import json
import logging
import time
import tempfile
import base64
from datetime import datetime
from typing import Optional
import redis
import requests
from sqlalchemy.orm import Session

# Import the original video processing logic
from main import (
    transcribe_and_align_lyrics, optimize_subtitles_for_timing,
    parse_time, seconds_to_srt_timestamp, get_available_font,
    load_audio_with_fallback, preprocess_lyrics, align_lyrics_with_scribe
)
from models import VideoJob, JobStatus, SessionLocal, get_db
import webvtt
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.VideoClip import ImageClip, TextClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis connection
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# File paths
UPLOAD_DIR = os.path.abspath("uploads")
OUTPUT_DIR = os.path.abspath("output")

class VideoProcessor:
    def __init__(self, worker_id: str = None):
        self.worker_id = worker_id or f"worker_{os.getpid()}"
        
        # RunPod configuration
        self.runpod_api_key = os.environ.get("RUNPOD_API_KEY")
        self.runpod_endpoint_id = os.environ.get("RUNPOD_ENDPOINT_ID")
        self.use_runpod = bool(self.runpod_api_key and self.runpod_endpoint_id)
        
        if self.use_runpod:
            logger.info(f"🚀 RunPod GPU acceleration enabled (endpoint: {self.runpod_endpoint_id})")
        else:
            logger.info("💻 Using local CPU processing")
        
    def update_job_progress(self, job_id: str, status: JobStatus, progress: int = 0, error_message: str = None):
        """Update job status and progress in database."""
        db = SessionLocal()
        try:
            job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
            if job:
                job.status = status
                job.progress_percentage = progress
                job.worker_id = self.worker_id
                
                if status == JobStatus.PROCESSING and not job.started_at:
                    job.started_at = datetime.utcnow()
                elif status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                    job.completed_at = datetime.utcnow()
                    if job.started_at:
                        job.processing_time_seconds = (job.completed_at - job.started_at).total_seconds()
                
                if error_message:
                    job.error_message = error_message
                
                db.commit()
                logger.info(f"Updated job {job_id}: {status} ({progress}%)")
        except Exception as e:
            logger.error(f"Failed to update job {job_id}: {e}")
        finally:
            db.close()
    
    def process_video_runpod(self, job_data: dict) -> bool:
        """Process video job using RunPod GPU acceleration."""
        job_id = job_data["job_id"]
        
        try:
            logger.info(f"🚀 Processing job {job_id} with RunPod GPU")
            self.update_job_progress(job_id, JobStatus.PROCESSING, 10)
            
            # Encode files as base64
            with open(job_data["image_path"], "rb") as f:
                image_base64 = base64.b64encode(f.read()).decode()
            
            with open(job_data["audio_path"], "rb") as f:
                audio_base64 = base64.b64encode(f.read()).decode()
            
            # Prepare RunPod job input
            runpod_input = {
                "job_id": job_id,
                "image_base64": image_base64,
                "audio_base64": audio_base64,
                "image_filename": os.path.basename(job_data["image_path"]),
                "audio_filename": os.path.basename(job_data["audio_path"]),
                "lyrics": job_data["lyrics"],
                "language": job_data.get("language", "en"),
                "font_size": job_data.get("font_size", 45),
                "font_color": job_data.get("font_color", "yellow"),
                "words_per_group": job_data.get("words_per_group", 3),
                "timing_offset": job_data.get("timing_offset", 0.0),
                "min_duration": job_data.get("min_duration", 1.0),
                "alignment_mode": job_data.get("alignment_mode", "auto"),
                "debug_mode": job_data.get("debug_mode", False)
            }
            
            self.update_job_progress(job_id, JobStatus.PROCESSING, 30)
            
            # Submit to RunPod
            headers = {
                "Authorization": f"Bearer {self.runpod_api_key}",
                "Content-Type": "application/json"
            }
            
            url = f"https://api.runpod.ai/v2/{self.runpod_endpoint_id}/runsync"
            logger.info(f"Submitting to RunPod: {url}")
            
            response = requests.post(
                url,
                headers=headers,
                json={"input": runpod_input},
                timeout=900  # 15 minute timeout
            )
            
            if response.status_code != 200:
                raise Exception(f"RunPod API error: {response.status_code} - {response.text}")
            
            result = response.json()
            
            if result.get('status') != 'COMPLETED' or not result.get('output'):
                raise Exception(f"RunPod job failed: {result}")
            
            output = result['output']
            
            if output.get('status') != 'completed':
                error_msg = output.get('error', 'Unknown RunPod error')
                raise Exception(f"RunPod processing failed: {error_msg}")
            
            self.update_job_progress(job_id, JobStatus.PROCESSING, 90)
            
            # Decode and save video
            if not output.get('video_base64'):
                raise Exception("No video data returned from RunPod")
            
            video_data = base64.b64decode(output['video_base64'])
            output_path = os.path.join(OUTPUT_DIR, f"{job_id}.mp4")
            
            with open(output_path, "wb") as f:
                f.write(video_data)
            
            logger.info(f"✅ RunPod job {job_id} completed: {output_path}")
            self.update_job_progress(job_id, JobStatus.COMPLETED, 100)
            return True
            
        except Exception as e:
            logger.error(f"❌ RunPod job {job_id} failed: {e}")
            self.update_job_progress(job_id, JobStatus.FAILED, 0, str(e))
            return False
    
    def process_video_job(self, job_data: dict) -> bool:
        """Process a single video job (with GPU acceleration if available)."""
        job_id = job_data["job_id"]
        
        # Use RunPod if available, otherwise fall back to local processing
        if self.use_runpod:
            return self.process_video_runpod(job_data)
        
        try:
            logger.info(f"💻 Processing job {job_id} locally")
            self.update_job_progress(job_id, JobStatus.PROCESSING, 10)
            
            # Extract parameters
            image_path = job_data["image_path"]
            audio_path = job_data["audio_path"]
            lyrics = job_data["lyrics"]
            language = job_data.get("language")
            font_size = job_data.get("font_size", 45)
            font_color = job_data.get("font_color", "yellow")
            words_per_group = job_data.get("words_per_group", 3)
            timing_offset = job_data.get("timing_offset", 0.0)
            min_duration = job_data.get("min_duration", 1.0)
            alignment_mode = job_data.get("alignment_mode", "auto")
            debug_mode = job_data.get("debug_mode", False)
            
            # Validate input files exist
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"Image file not found: {image_path}")
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
            self.update_job_progress(job_id, JobStatus.PROCESSING, 20)
            
            # Load audio to get duration
            logger.info("Loading audio file...")
            audio_clip, duration = load_audio_with_fallback(audio_path)
            logger.info(f"Audio duration: {duration:.2f} seconds")
            
            self.update_job_progress(job_id, JobStatus.PROCESSING, 30)
            
            # Create background image clip
            logger.info("Creating background image clip...")
            bg_clip = ImageClip(image_path).with_duration(duration)
            
            self.update_job_progress(job_id, JobStatus.PROCESSING, 40)
            
            # Process lyrics and create subtitles
            logger.info("Processing lyrics and creating subtitles...")
            
            if alignment_mode == "even":
                # Use even distribution
                temp_audio_clip, audio_duration = load_audio_with_fallback(audio_path)
                temp_audio_clip.close()
                
                lyrics_lines = preprocess_lyrics(lyrics)
                aligned_segments = align_lyrics_with_scribe(lyrics_lines, audio_duration)
                
                # Convert to WebVTT
                vtt = webvtt.WebVTT()
                for s in aligned_segments:
                    start_str = seconds_to_srt_timestamp(s["start"])
                    end_str = seconds_to_srt_timestamp(s["end"])
                    vtt.captions.append(webvtt.Caption(start_str, end_str, s["text"]))
            else:
                # Use automatic or ElevenLabs alignment
                vtt = transcribe_and_align_lyrics(
                    audio_path,
                    lyrics,
                    language=language,
                    alignment_mode=alignment_mode
                )
            
            logger.info(f"Generated {len(vtt.captions)} subtitle captions")
            self.update_job_progress(job_id, JobStatus.PROCESSING, 60)
            
            # Optimize subtitles
            logger.info("Optimizing subtitles...")
            optimized = optimize_subtitles_for_timing(vtt.captions)
            
            # Apply minimum duration constraint
            for i in range(len(optimized)):
                start_obj = parse_time(optimized[i].start)
                end_obj = parse_time(optimized[i].end)
                
                start_s = (start_obj.hour * 3600 + start_obj.minute * 60 + 
                          start_obj.second + start_obj.microsecond / 1e6)
                end_s = (end_obj.hour * 3600 + end_obj.minute * 60 + 
                        end_obj.second + end_obj.microsecond / 1e6)
                
                if end_s - start_s < min_duration:
                    end_s = start_s + min_duration
                    optimized[i].end = seconds_to_srt_timestamp(end_s)
                
                # Fix overlaps
                if i < len(optimized) - 1:
                    next_start_obj = parse_time(optimized[i+1].start)
                    next_start_s = (next_start_obj.hour * 3600 + next_start_obj.minute * 60 + 
                                   next_start_obj.second + next_start_obj.microsecond / 1e6)
                    
                    if end_s > next_start_s:
                        if next_start_s - start_s >= min_duration:
                            optimized[i].end = seconds_to_srt_timestamp(next_start_s)
                        else:
                            optimized[i+1].start = seconds_to_srt_timestamp(end_s)
            
            self.update_job_progress(job_id, JobStatus.PROCESSING, 70)
            
            # Create subtitle text clips
            logger.info("Creating subtitle text clips...")
            subtitle_clips = []
            
            for cap in optimized:
                start_obj = parse_time(cap.start)
                end_obj = parse_time(cap.end)
                if not start_obj or not end_obj:
                    continue
                
                start_s = (start_obj.hour * 3600 + start_obj.minute * 60 + 
                          start_obj.second + start_obj.microsecond / 1e6)
                end_s = (end_obj.hour * 3600 + end_obj.minute * 60 + 
                        end_obj.second + end_obj.microsecond / 1e6)
                
                # Apply timing offset
                start_s += timing_offset
                end_s += timing_offset
                
                start_s = max(0, start_s)
                end_s = min(duration, end_s)
                
                sub_duration = end_s - start_s
                if sub_duration <= 0:
                    continue
                
                # Split into word groups
                words = cap.text.split()
                word_groups = []
                
                for i in range(0, len(words), words_per_group):
                    group = words[i:min(i+words_per_group, len(words))]
                    word_groups.append(" ".join(group))
                
                if word_groups:
                    time_per_group = sub_duration / len(word_groups)
                    
                    for i, group_text in enumerate(word_groups):
                        group_start = start_s + (i * time_per_group)
                        
                        if debug_mode:
                            group_text = f"[{group_start:.1f}s] {group_text}"
                        
                        txt_clip = TextClip(
                            text=group_text,
                            font=get_available_font(),
                            font_size=font_size,
                            color=font_color,
                            bg_color=(0, 0, 0, 120),
                            size=(700, 100),
                            stroke_color='black',
                            stroke_width=2,
                            method='caption'
                        ).with_duration(time_per_group).with_start(group_start).with_position(("center", 0.8), relative=True)
                        
                        subtitle_clips.append(txt_clip)
            
            logger.info(f"Created {len(subtitle_clips)} text clips")
            self.update_job_progress(job_id, JobStatus.PROCESSING, 80)
            
            # Combine everything
            logger.info("Compositing final video...")
            final_clip = CompositeVideoClip([bg_clip] + subtitle_clips)
            final_clip.audio = audio_clip
            
            self.update_job_progress(job_id, JobStatus.PROCESSING, 90)
            
            # Write output video
            output_filename = f"output_{job_id}.mp4"
            output_path = os.path.join(OUTPUT_DIR, output_filename)
            
            logger.info(f"Writing video to {output_path}...")
            final_clip.write_videofile(
                output_path,
                fps=25,
                codec="libx264",
                audio_codec="aac",
                temp_audiofile=os.path.join(OUTPUT_DIR, f"temp-audio_{job_id}.m4a"),
                remove_temp=True
            )
            
            # Update job as completed
            db = SessionLocal()
            try:
                job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
                if job:
                    job.output_filename = output_filename
                    db.commit()
            finally:
                db.close()
            
            self.update_job_progress(job_id, JobStatus.COMPLETED, 100)
            
            # Cleanup clips
            try:
                audio_clip.close()
                final_clip.close()
                bg_clip.close()
                for clip in subtitle_clips:
                    clip.close()
            except Exception:
                pass
            
            logger.info(f"✅ Job {job_id} completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Job {job_id} failed: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
            self.update_job_progress(job_id, JobStatus.FAILED, error_message=str(e))
            return False

def run_worker():
    """Main worker loop - processes jobs from Redis queue."""
    processor = VideoProcessor()
    logger.info(f"Starting worker {processor.worker_id}")
    
    while True:
        try:
            # Block and wait for job from queue
            logger.info("Waiting for jobs...")
            job_data_str = redis_client.brpop("video_jobs", timeout=30)
            
            if job_data_str is None:
                # Timeout - no jobs available
                continue
            
            # Parse job data
            _, job_json = job_data_str
            job_data = json.loads(job_json)
            
            logger.info(f"Received job: {job_data['job_id']}")
            
            # Process the job
            success = processor.process_video_job(job_data)
            
            if success:
                logger.info(f"Job {job_data['job_id']} processed successfully")
            else:
                logger.error(f"Job {job_data['job_id']} failed")
                
        except KeyboardInterrupt:
            logger.info("Worker interrupted by user")
            break
        except Exception as e:
            logger.error(f"Worker error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            time.sleep(5)  # Wait before retrying

if __name__ == "__main__":
    run_worker()