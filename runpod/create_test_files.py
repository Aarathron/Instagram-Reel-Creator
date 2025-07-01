#!/usr/bin/env python3
"""
Create valid test files for RunPod testing
"""
import base64
import io
from PIL import Image
import numpy as np
from pydub import AudioSegment
from pydub.generators import Sine

def create_test_image():
    """Create a small test image (100x100 red square)"""
    # Create a 100x100 red image
    img = Image.new('RGB', (100, 100), color='red')
    
    # Save to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    # Encode to base64
    img_base64 = base64.b64encode(img_bytes.read()).decode()
    return img_base64

def create_test_audio():
    """Create a 2-second test audio (440Hz sine wave)"""
    # Create 2 seconds of 440Hz sine wave
    duration_ms = 2000  # 2 seconds
    frequency = 440  # A note
    
    # Generate sine wave
    audio = Sine(frequency).to_audio_segment(duration=duration_ms)
    
    # Export to MP3 bytes
    audio_bytes = io.BytesIO()
    audio.export(audio_bytes, format="mp3", bitrate="64k")
    audio_bytes.seek(0)
    
    # Encode to base64
    audio_base64 = base64.b64encode(audio_bytes.read()).decode()
    return audio_base64

def create_test_data():
    """Create complete test data package"""
    print("🎨 Creating test image...")
    image_base64 = create_test_image()
    
    print("🎵 Creating test audio...")
    audio_base64 = create_test_audio()
    
    test_data = {
        "job_id": "real-test-job",
        "image_base64": image_base64,
        "audio_base64": audio_base64,
        "image_filename": "test_image.png",
        "audio_filename": "test_audio.mp3",
        "lyrics": "This is a real test with valid audio and image files for RunPod deployment testing.",
        "language": "en",
        "alignment_mode": "even",
        "font_size": 40,
        "font_color": "white"
    }
    
    print(f"✅ Test data created:")
    print(f"  - Image size: {len(image_base64)} characters")
    print(f"  - Audio size: {len(audio_base64)} characters")
    
    return test_data

if __name__ == "__main__":
    try:
        test_data = create_test_data()
        
        # Save to file for reuse
        import json
        with open("test_data.json", "w") as f:
            json.dump(test_data, f, indent=2)
        
        print("✅ Test data saved to test_data.json")
        
    except Exception as e:
        print(f"❌ Failed to create test data: {e}")
        print("Make sure you have PIL and pydub installed:")
        print("pip install Pillow pydub")