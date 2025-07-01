#!/usr/bin/env python3
"""
Generate real test data using existing files in the project
"""
import os
import base64
import json

def create_real_test_data():
    """Create real test data using existing sample files"""
    
    # Look for sample files in common locations
    sample_paths = [
        "../test_image.jpg",
        "../test_image.png", 
        "../sample.jpg",
        "../sample.png",
        "test_image.jpg",
        "test_image.png"
    ]
    
    audio_paths = [
        "../test_audio.mp3",
        "../test_audio.wav",
        "../sample.mp3",
        "../sample.wav",
        "test_audio.mp3",
        "test_audio.wav"
    ]
    
    # Find image file
    image_path = None
    for path in sample_paths:
        if os.path.exists(path):
            image_path = path
            break
    
    # Find audio file
    audio_path = None
    for path in audio_paths:
        if os.path.exists(path):
            audio_path = path
            break
    
    if not image_path or not audio_path:
        print("❌ No sample files found. Please:")
        print("1. Add a test image file (test_image.jpg/png) to the project root")
        print("2. Add a test audio file (test_audio.mp3/wav) to the project root")
        print("3. Run this script again")
        return None
    
    # Read and encode files
    with open(image_path, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode()
    
    with open(audio_path, "rb") as f:
        audio_base64 = base64.b64encode(f.read()).decode()
    
    # Create test job
    test_data = {
        "job_id": "real-file-test",
        "image_base64": image_base64,
        "audio_base64": audio_base64,
        "image_filename": os.path.basename(image_path),
        "audio_filename": os.path.basename(audio_path),
        "lyrics": "This is a real test using actual image and audio files from the project.",
        "language": "en",
        "alignment_mode": "even",  # Avoid ElevenLabs dependency
        "font_size": 40,
        "font_color": "white"
    }
    
    # Save test data
    with open("test_data.json", "w") as f:
        json.dump(test_data, f, indent=2)
    
    print(f"✅ Real test data created from:")
    print(f"  - Image: {image_path} ({len(image_base64)} chars)")
    print(f"  - Audio: {audio_path} ({len(audio_base64)} chars)")
    print(f"  - Saved to: test_data.json")
    
    return test_data

if __name__ == "__main__":
    create_real_test_data()