#!/usr/bin/env python3
"""
Debug script to test RunPod input format locally
"""
import json
import base64

def test_handler_input():
    """Test what the handler actually receives"""
    
    # Create minimal test data
    minimal_png_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAGA0VaV9QAAAABJRU5ErkJggg=="
    minimal_mp3_base64 = "SUQzAwAAAAAJAAABU1NFTkMAAAAOAAADAAAAAOQDwAA="
    
    # Test 1: Direct input format
    direct_input = {
        "job_id": "test-job-123",
        "image_base64": minimal_png_base64,
        "audio_base64": minimal_mp3_base64,
        "image_filename": "test.png",
        "audio_filename": "test.mp3",
        "lyrics": "Test lyrics for debugging"
    }
    
    # Test 2: Wrapped input format (like RunPod might send)
    wrapped_input = {
        "input": {
            "job_id": "test-job-123",
            "image_base64": minimal_png_base64,
            "audio_base64": minimal_mp3_base64,
            "image_filename": "test.png",
            "audio_filename": "test.mp3",
            "lyrics": "Test lyrics for debugging"
        }
    }
    
    print("=== Direct Input Format ===")
    print(f"Keys: {list(direct_input.keys())}")
    print(f"Has image_base64: {'image_base64' in direct_input}")
    print(f"Preview: {str(direct_input)[:200]}...")
    
    print("\n=== Wrapped Input Format ===")
    print(f"Top-level keys: {list(wrapped_input.keys())}")
    if 'input' in wrapped_input:
        print(f"Input keys: {list(wrapped_input['input'].keys())}")
        print(f"Has image_base64: {'image_base64' in wrapped_input['input']}")
    print(f"Preview: {str(wrapped_input)[:200]}...")
    
    # Test handler logic
    from handler_simple import process_video_job
    
    print("\n=== Testing Direct Input ===")
    try:
        result = process_video_job(direct_input)
        print(f"✅ Success: {result['status']}")
    except Exception as e:
        print(f"❌ Failed: {e}")
    
    print("\n=== Testing Wrapped Input ===")
    try:
        result = process_video_job(wrapped_input)
        print(f"✅ Success: {result['status']}")
    except Exception as e:
        print(f"❌ Failed: {e}")
        
    print("\n=== Testing Wrapped Input['input'] ===")
    try:
        result = process_video_job(wrapped_input['input'])
        print(f"✅ Success: {result['status']}")
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    test_handler_input()