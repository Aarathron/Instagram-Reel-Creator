import runpod
import os
import json
import tempfile
import logging
import base64
from typing import Dict, Any
import requests

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import our video processing logic
import sys
sys.path.append('/workspace/src')

from worker import VideoProcessor
from models import JobStatus

def process_video_job(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    RunPod handler function for processing video jobs.
    
    Input format:
    {
        "job_id": "uuid",
        "image_base64": "base64_encoded_image",
        "audio_base64": "base64_encoded_audio", 
        "image_filename": "image.jpg",
        "audio_filename": "audio.mp3",
        "lyrics": "lyrics text",
        "language": "en",
        "font_size": 45,
        "font_color": "yellow",
        "words_per_group": 5,
        "timing_offset": 0.0,
        "min_duration": 1.0,
        "alignment_mode": "auto",
        "debug_mode": false,
        "callback_url": "https://your-api.com/jobs/{job_id}/callback"
    }
    """
    try:
        logger.info(f"Processing RunPod job: {job_input.get('job_id', 'unknown')}")
        
        # Create temporary files for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Decode and save image file
            image_data = base64.b64decode(job_input["image_base64"])
            image_path = os.path.join(temp_dir, job_input["image_filename"])
            with open(image_path, "wb") as f:
                f.write(image_data)
            
            # Decode and save audio file  
            audio_data = base64.b64decode(job_input["audio_base64"])
            audio_path = os.path.join(temp_dir, job_input["audio_filename"])
            with open(audio_path, "wb") as f:
                f.write(audio_data)
            
            # Prepare job data for processor
            job_data = {
                "job_id": job_input["job_id"],
                "image_path": image_path,
                "audio_path": audio_path,
                "lyrics": job_input["lyrics"],
                "language": job_input.get("language"),
                "font_size": job_input.get("font_size", 45),
                "font_color": job_input.get("font_color", "yellow"),
                "words_per_group": job_input.get("words_per_group", 5),
                "timing_offset": job_input.get("timing_offset", 0.0),
                "min_duration": job_input.get("min_duration", 1.0),
                "alignment_mode": job_input.get("alignment_mode", "auto"),
                "debug_mode": job_input.get("debug_mode", False)
            }
            
            # Create a mock processor that doesn't update database
            # Instead, it will return status updates via callback
            processor = RunPodVideoProcessor(
                job_input.get("callback_url"),
                job_input["job_id"]
            )
            
            # Process the video
            success = processor.process_video_job(job_data)
            
            if success:
                # Read the output video and encode as base64
                output_path = os.path.join("/workspace/output", f"output_{job_input['job_id']}.mp4")
                if os.path.exists(output_path):
                    with open(output_path, "rb") as f:
                        video_data = f.read()
                    
                    video_base64 = base64.b64encode(video_data).decode()
                    
                    # Clean up output file
                    os.remove(output_path)
                    
                    return {
                        "status": "completed",
                        "video_base64": video_base64,
                        "job_id": job_input["job_id"]
                    }
                else:
                    raise Exception("Output video file not found")
            else:
                return {
                    "status": "failed",
                    "error": "Video processing failed",
                    "job_id": job_input["job_id"]
                }
                
    except Exception as e:
        logger.error(f"RunPod job failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            "status": "failed", 
            "error": str(e),
            "job_id": job_input.get("job_id", "unknown")
        }

class RunPodVideoProcessor(VideoProcessor):
    """Extended video processor for RunPod that sends status updates via callback."""
    
    def __init__(self, callback_url: str = None, job_id: str = None):
        super().__init__(worker_id="runpod-gpu")
        self.callback_url = callback_url
        self.job_id = job_id
    
    def update_job_progress(self, job_id: str, status: JobStatus, progress: int = 0, error_message: str = None):
        """Send status update to callback URL instead of database."""
        if not self.callback_url:
            logger.info(f"Job {job_id}: {status} ({progress}%)")
            return
            
        try:
            update_data = {
                "job_id": job_id,
                "status": status.value,
                "progress_percentage": progress,
                "worker_id": self.worker_id
            }
            
            if error_message:
                update_data["error_message"] = error_message
                
            response = requests.post(
                self.callback_url,
                json=update_data,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Status update sent: {job_id} - {status} ({progress}%)")
            else:
                logger.warning(f"Callback failed: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Failed to send callback: {e}")

# Set the RunPod handler
runpod.serverless.start({"handler": process_video_job})