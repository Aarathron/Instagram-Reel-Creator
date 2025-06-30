#!/usr/bin/env python3
"""
Simplified RunPod handler for Instagram Reel Creator with robust error handling
"""
import runpod
import os
import json
import tempfile
import logging
import base64
import traceback
from typing import Dict, Any

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_handler(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simplified test handler to verify RunPod setup
    """
    try:
        logger.info("🚀 RunPod handler started")
        logger.info(f"Input keys: {list(job_input.keys())}")
        
        # Test basic functionality
        job_id = job_input.get("job_id", "test-job")
        
        # Test file operations
        test_message = f"Hello from RunPod GPU! Job ID: {job_id}"
        
        # Test environment
        env_info = {
            "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "ELEVENLABS_API_KEY": "SET" if os.environ.get("ELEVENLABS_API_KEY") else "NOT_SET",
            "Python_Version": os.sys.version,
            "Working_Directory": os.getcwd()
        }
        
        logger.info(f"Environment: {env_info}")
        
        return {
            "status": "completed",
            "message": test_message,
            "environment": env_info,
            "job_id": job_id
        }
        
    except Exception as e:
        logger.error(f"Handler failed: {str(e)}")
        logger.error(traceback.format_exc())
        
        return {
            "status": "failed",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "job_id": job_input.get("job_id", "unknown")
        }

def process_video_job(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main video processing handler for RunPod
    """
    try:
        logger.info(f"🎬 Processing video job: {job_input.get('job_id', 'unknown')}")
        
        # First run a simple test
        if job_input.get("test_mode", False):
            return test_handler(job_input)
        
        # Import video processing modules
        import sys
        sys.path.append('/workspace/src')
        
        try:
            # Import main video processing function from original main.py
            from main import (
                transcribe_and_align_lyrics, optimize_subtitles_for_timing,
                parse_time, seconds_to_srt_timestamp, get_available_font,
                load_audio_with_fallback, preprocess_lyrics, align_lyrics_with_scribe
            )
            import webvtt
            from moviepy.video.io.VideoFileClip import VideoFileClip
            from moviepy.video.VideoClip import ImageClip, TextClip
            from moviepy.audio.io.AudioFileClip import AudioFileClip
            from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
            
            logger.info("✅ Successfully imported video processing modules")
            
        except ImportError as e:
            logger.error(f"❌ Failed to import video processing modules: {e}")
            return {
                "status": "failed",
                "error": f"Import error: {str(e)}",
                "job_id": job_input.get("job_id", "unknown")
            }
        
        # Process the video using simplified approach
        with tempfile.TemporaryDirectory() as temp_dir:
            # Decode and save files
            image_data = base64.b64decode(job_input["image_base64"])
            image_path = os.path.join(temp_dir, job_input["image_filename"])
            with open(image_path, "wb") as f:
                f.write(image_data)
            
            audio_data = base64.b64decode(job_input["audio_base64"])
            audio_path = os.path.join(temp_dir, job_input["audio_filename"])
            with open(audio_path, "wb") as f:
                f.write(audio_data)
            
            logger.info(f"✅ Files saved: {image_path}, {audio_path}")
            
            # Extract parameters
            lyrics = job_input["lyrics"]
            language = job_input.get("language")
            font_size = job_input.get("font_size", 45)
            font_color = job_input.get("font_color", "yellow")
            words_per_group = job_input.get("words_per_group", 3)
            timing_offset = job_input.get("timing_offset", 0.0)
            min_duration = job_input.get("min_duration", 1.0)
            alignment_mode = job_input.get("alignment_mode", "auto")
            debug_mode = job_input.get("debug_mode", False)
            
            # Load audio
            logger.info("🎵 Loading audio...")
            audio_clip, duration = load_audio_with_fallback(audio_path)
            logger.info(f"Audio duration: {duration:.2f} seconds")
            
            # Create background image
            logger.info("🖼️ Creating background image...")
            bg_clip = ImageClip(image_path).with_duration(duration)
            
            # Process lyrics
            logger.info("📝 Processing lyrics...")
            
            if alignment_mode == "even":
                lyrics_lines = preprocess_lyrics(lyrics)
                aligned_segments = align_lyrics_with_scribe(lyrics_lines, duration)
                
                vtt = webvtt.WebVTT()
                for s in aligned_segments:
                    start_str = seconds_to_srt_timestamp(s["start"])
                    end_str = seconds_to_srt_timestamp(s["end"])
                    vtt.captions.append(webvtt.Caption(start_str, end_str, s["text"]))
            else:
                vtt = transcribe_and_align_lyrics(
                    audio_path, lyrics, language=language, alignment_mode=alignment_mode
                )
            
            logger.info(f"Generated {len(vtt.captions)} subtitle captions")
            
            # Create subtitle clips (simplified)
            subtitle_clips = []
            for cap in vtt.captions[:5]:  # Limit to first 5 for testing
                start_obj = parse_time(cap.start)
                end_obj = parse_time(cap.end)
                if not start_obj or not end_obj:
                    continue
                
                start_s = (start_obj.hour * 3600 + start_obj.minute * 60 + 
                          start_obj.second + start_obj.microsecond / 1e6)
                end_s = (end_obj.hour * 3600 + end_obj.minute * 60 + 
                        end_obj.second + end_obj.microsecond / 1e6)
                
                sub_duration = end_s - start_s
                if sub_duration <= 0:
                    continue
                
                # Create simple text clip
                txt_clip = TextClip(
                    text=cap.text[:50],  # Limit text length
                    font=get_available_font(),
                    font_size=font_size,
                    color=font_color,
                    size=(600, 80),
                    method='caption'
                ).with_duration(sub_duration).with_start(start_s).with_position(('center', 0.8), relative=True)
                
                subtitle_clips.append(txt_clip)
            
            logger.info(f"Created {len(subtitle_clips)} text clips")
            
            # Compose final video
            logger.info("🎬 Composing final video...")
            final_clip = CompositeVideoClip([bg_clip] + subtitle_clips)
            final_clip.audio = audio_clip
            
            # Write output
            output_path = os.path.join("/workspace/output", f"output_{job_input['job_id']}.mp4")
            os.makedirs("/workspace/output", exist_ok=True)
            
            logger.info(f"🎥 Writing video to {output_path}...")
            final_clip.write_videofile(
                output_path,
                fps=24,
                codec="libx264",
                audio_codec="aac",
                verbose=False,
                logger=None
            )
            
            # Read and encode output
            with open(output_path, "rb") as f:
                video_data = f.read()
            
            video_base64 = base64.b64encode(video_data).decode()
            
            # Cleanup
            try:
                audio_clip.close()
                final_clip.close()
                bg_clip.close()
                for clip in subtitle_clips:
                    clip.close()
                os.remove(output_path)
            except Exception:
                pass
            
            logger.info("✅ Video processing completed successfully")
            
            return {
                "status": "completed",
                "video_base64": video_base64,
                "job_id": job_input["job_id"]
            }
            
    except Exception as e:
        logger.error(f"❌ Video processing failed: {str(e)}")
        logger.error(traceback.format_exc())
        
        return {
            "status": "failed",
            "error": str(e),
            "traceback": traceback.format_exc()[:1000],  # Limit traceback length
            "job_id": job_input.get("job_id", "unknown")
        }

# Test if we can import runpod
try:
    logger.info("🚀 Starting RunPod handler...")
    logger.info(f"RunPod version: {runpod.__version__ if hasattr(runpod, '__version__') else 'unknown'}")
    
    # Set the handler
    runpod.serverless.start({"handler": process_video_job})
    
except Exception as e:
    logger.error(f"❌ Failed to start RunPod handler: {e}")
    logger.error(traceback.format_exc())
    raise