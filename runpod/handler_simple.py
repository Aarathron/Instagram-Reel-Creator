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
        
        # Test environment and RunPod secrets access
        elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY")
        
        env_info = {
            "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "ELEVENLABS_API_KEY": "SET" if elevenlabs_key else "NOT_SET",
            "Python_Version": os.sys.version,
            "Working_Directory": os.getcwd(),
            "ALL_ENV_VARS": [k for k in os.environ.keys() if "ELEVEN" in k.upper() or "SECRET" in k.upper()]
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
        logger.info(f"📋 Input keys received: {list(job_input.keys())}")
        logger.info(f"🔍 Input data preview: {str(job_input)[:500]}...")
        
        # CRITICAL FIX: RunPod wraps input data in 'input' field
        if 'input' in job_input and isinstance(job_input['input'], dict):
            logger.info("🔄 Detected wrapped input, extracting...")
            actual_input = job_input['input']
        else:
            actual_input = job_input
            
        logger.info(f"📋 Actual input keys: {list(actual_input.keys())}")
        
        # Check ElevenLabs API key availability
        elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY")
        if elevenlabs_key:
            logger.info("✅ ElevenLabs API key found in environment")
        else:
            logger.warning("⚠️ ElevenLabs API key not found - you need to configure it in RunPod template")
            logger.info("📋 Available environment variables containing 'eleven' or 'secret':")
            for k in os.environ.keys():
                if "eleven" in k.lower() or "secret" in k.lower():
                    logger.info(f"  - {k}")
        
        # First run a simple test
        if actual_input.get("test_mode", False):
            logger.info("🧪 Running in test mode - skipping actual video processing")
            return test_handler(actual_input)
        
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
        
        # Validate required fields first
        required_fields = ["image_base64", "audio_base64", "image_filename", "audio_filename", "lyrics"]
        missing_fields = [field for field in required_fields if field not in actual_input]
        
        if missing_fields:
            logger.error(f"❌ Missing required fields: {missing_fields}")
            logger.error(f"Available fields: {list(actual_input.keys())}")
            return {
                "status": "failed",
                "error": f"Missing required fields: {missing_fields}",
                "available_fields": list(actual_input.keys()),
                "job_id": actual_input.get("job_id", "unknown")
            }
        
        # Process the video using simplified approach
        with tempfile.TemporaryDirectory() as temp_dir:
            # Decode and save files
            try:
                image_data = base64.b64decode(actual_input["image_base64"])
                image_path = os.path.join(temp_dir, actual_input["image_filename"])
                with open(image_path, "wb") as f:
                    f.write(image_data)
                
                audio_data = base64.b64decode(actual_input["audio_base64"])
                audio_path = os.path.join(temp_dir, actual_input["audio_filename"])
                with open(audio_path, "wb") as f:
                    f.write(audio_data)
                    
                logger.info(f"✅ Files decoded and saved: {image_path}, {audio_path}")
                
            except Exception as e:
                logger.error(f"❌ Failed to decode/save files: {e}")
                return {
                    "status": "failed", 
                    "error": f"File decode error: {str(e)}",
                    "job_id": actual_input.get("job_id", "unknown")
                }
            
            # Extract parameters
            lyrics = actual_input["lyrics"]
            language = actual_input.get("language")
            font_size = actual_input.get("font_size", 45)
            font_color = actual_input.get("font_color", "yellow")
            words_per_group = actual_input.get("words_per_group", 3)
            timing_offset = actual_input.get("timing_offset", 0.0)
            min_duration = actual_input.get("min_duration", 1.0)
            alignment_mode = actual_input.get("alignment_mode", "auto")
            debug_mode = actual_input.get("debug_mode", False)
            
            # Load audio
            logger.info("🎵 Loading audio...")
            audio_clip, duration = load_audio_with_fallback(audio_path)
            logger.info(f"Audio duration: {duration:.2f} seconds")
            
            # Create background image (optimized)
            logger.info("🖼️ Creating background image...")
            bg_clip = ImageClip(image_path).with_duration(duration).resize(height=1080)  # Standard HD height
            
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
            
            # Create subtitle clips (optimized for GPU)
            subtitle_clips = []
            total_captions = len(vtt.captions)
            logger.info(f"Processing {total_captions} subtitle clips...")
            
            # Process in batches for memory efficiency
            batch_size = 20
            for i, cap in enumerate(vtt.captions):
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
                
                # Create optimized text clip
                txt_clip = TextClip(
                    text=cap.text,  # Use full text
                    font=get_available_font(),
                    font_size=font_size,
                    color=font_color,
                    size=(800, 100),  # Larger text area
                    method='caption',
                    align='center'
                ).with_duration(sub_duration).with_start(start_s).with_position(('center', 0.8), relative=True)
                
                # Progress logging and memory cleanup
                if i % batch_size == 0:
                    logger.info(f"📝 Processed {i+1}/{total_captions} subtitle clips ({((i+1)/total_captions*100):.1f}%)")
                
                subtitle_clips.append(txt_clip)
            
            logger.info(f"Created {len(subtitle_clips)} text clips")
            
            # Compose final video
            logger.info("🎬 Composing final video...")
            final_clip = CompositeVideoClip([bg_clip] + subtitle_clips)
            final_clip.audio = audio_clip
            
            # Write output
            output_path = os.path.join("/workspace/output", f"output_{actual_input['job_id']}.mp4")
            os.makedirs("/workspace/output", exist_ok=True)
            
            logger.info(f"🎥 Writing video to {output_path}...")
            # GPU-optimized parameters for MoviePy  
            logger.info(f"🚀 Starting GPU-accelerated encoding...")
            final_clip.write_videofile(
                output_path,
                fps=24,  # Standard fps for efficiency
                codec="libx264",
                audio_codec="aac",
                temp_audiofile="/tmp/temp-audio.m4a",
                remove_temp=True,
                preset="faster",  # Balance speed vs quality
                threads=16,  # Use more threads on GPU instance
                ffmpeg_params=[
                    "-movflags", "+faststart",
                    "-crf", "23",  # Good quality/speed balance
                    "-maxrate", "4M",  # Limit bitrate
                    "-bufsize", "8M"
                ]
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
                "job_id": actual_input["job_id"]
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