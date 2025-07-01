#!/usr/bin/env python3
"""
RunPod deployment script for Instagram Reel Creator
"""
import os
import requests
import json
import base64
from typing import Dict, Any

class RunPodClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.runpod.ai/v2"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def submit_job(self, 
                   endpoint_id: str,
                   image_path: str, 
                   audio_path: str,
                   job_id: str,
                   **kwargs) -> Dict[str, Any]:
        """Submit a video processing job to RunPod."""
        
        # Encode files as base64
        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode()
        
        with open(audio_path, "rb") as f:
            audio_base64 = base64.b64encode(f.read()).decode()
        
        # Prepare job input
        job_input = {
            "job_id": job_id,
            "image_base64": image_base64,
            "audio_base64": audio_base64,
            "image_filename": os.path.basename(image_path),
            "audio_filename": os.path.basename(audio_path),
            **kwargs  # lyrics, language, font_size, etc.
        }
        
        # Submit to RunPod
        url = f"{self.base_url}/{endpoint_id}/runsync"
        response = requests.post(url, headers=self.headers, json={"input": job_input})
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"RunPod API error: {response.status_code} - {response.text}")
    
    def get_job_status(self, endpoint_id: str, job_id: str) -> Dict[str, Any]:
        """Get job status from RunPod."""
        url = f"{self.base_url}/{endpoint_id}/status/{job_id}"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"RunPod API error: {response.status_code} - {response.text}")
    
    def test_connection(self, endpoint_id: str) -> Dict[str, Any]:
        """Test RunPod connection with minimal payload."""
        # Create minimal test data for connection test
        minimal_png_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAGA0VaV9QAAAABJRU5ErkJggg=="
        minimal_mp3_base64 = "SUQzAwAAAAAJAAABU1NFTkMAAAAOAAADAAAAAOQDwAA="
        
        job_input = {
            "job_id": "connection-test",
            "test_mode": True,
            "image_base64": minimal_png_base64,
            "audio_base64": minimal_mp3_base64,
            "image_filename": "test.png",
            "audio_filename": "test.mp3",
            "lyrics": "Test connection",
            "message": "Testing RunPod connection"
        }
        
        url = f"{self.base_url}/{endpoint_id}/runsync"
        response = requests.post(url, headers=self.headers, json={"input": job_input})
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"RunPod API error: {response.status_code} - {response.text}")

def test_runpod_deployment():
    """Test the RunPod deployment with sample data."""
    
    # Get API key from environment
    api_key = os.environ.get("RUNPOD_API_KEY")
    if not api_key:
        print("❌ RUNPOD_API_KEY environment variable not set")
        return
    
    # Get endpoint ID from environment  
    endpoint_id = os.environ.get("RUNPOD_ENDPOINT_ID")
    if not endpoint_id:
        print("❌ RUNPOD_ENDPOINT_ID environment variable not set")
        return
    
    client = RunPodClient(api_key)
    
    # First test basic connection
    try:
        print("🔍 Testing RunPod connection...")
        result = client.test_connection(endpoint_id)
        print("✅ Connection test successful!")
        print(f"Response: {result}")
        
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return
    
    # Create real test data with valid files
    try:
        print("🚀 Creating real test data for RunPod...")
        
        # Use real test files for complete video processing test
        # Check in current directory and runpod directory
        possible_image_paths = ["test_image.jpg", "runpod/test_image.jpg", "../test_image.jpg"]
        possible_audio_paths = ["test_audio.mp3", "runpod/test_audio.mp3", "../test_audio.mp3"]
        
        image_path = None
        audio_path = None
        
        for path in possible_image_paths:
            if os.path.exists(path):
                image_path = path
                print(f"📁 Found image at: {os.path.abspath(path)}")
                break
                
        for path in possible_audio_paths:
            if os.path.exists(path):
                audio_path = path
                print(f"📁 Found audio at: {os.path.abspath(path)}")
                break
        
        if image_path and audio_path:
            print(f"✅ Found real test files:")
            print(f"  - Image: {image_path}")
            print(f"  - Audio: {audio_path}")
            print("🎬 Testing complete video processing...")
            
            # Read and encode real test files
            with open(image_path, "rb") as f:
                image_base64 = base64.b64encode(f.read()).decode()
            
            with open(audio_path, "rb") as f:
                audio_base64 = base64.b64encode(f.read()).decode()
            
            # Generate unique job ID to avoid cached results
            import time
            unique_id = f"real-test-{int(time.time())}"
            
            test_job_input = {
                "job_id": unique_id,
                "image_base64": image_base64,
                "audio_base64": audio_base64,
                "image_filename": os.path.basename(image_path),
                "audio_filename": os.path.basename(audio_path),
                "lyrics": "This is a complete test of RunPod video processing using real audio and image files.",
                "language": "en",
                "alignment_mode": "even",  # Use even distribution to avoid ElevenLabs dependency
                "font_size": 45,
                "font_color": "yellow",
                "words_per_group": 3,
                "test_real_files": True  # Flag to indicate this uses real files
            }
            print(f"📊 Test data size - Image: {len(image_base64)} chars, Audio: {len(audio_base64)} chars")
            
        else:
            print("⚠️ Real test files not found - using test mode instead...")
            print(f"  Searched for image in: {possible_image_paths}")
            print(f"  Searched for audio in: {possible_audio_paths}")
            print("  Add these files to test full video processing")
            
            # Fallback to test mode
            test_job_input = {
                "job_id": "connection-test-fallback",
                "test_mode": True,
                "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAGA0VaV9QAAAABJRU5ErkJggg==",
                "audio_base64": "placeholder",
                "image_filename": "test.png",
                "audio_filename": "test.mp3",
                "lyrics": "Connection test only",
                "message": "Testing RunPod connection"
            }
        
        # Submit to RunPod with proper timeout handling
        url = f"{client.base_url}/{endpoint_id}/runsync"
        print(f"🚀 Submitting job to RunPod (this may take several minutes)...")
        
        # Set a long timeout for video processing
        import time
        start_time = time.time()
        
        try:
            response = requests.post(
                url, 
                headers=client.headers, 
                json={"input": test_job_input},
                timeout=900  # 15 minute timeout
            )
        except requests.exceptions.Timeout:
            print("⏰ Request timed out - job may still be processing")
            print("Try checking RunPod dashboard or increase timeout")
            return
        
        if response.status_code == 200:
            result = response.json()
        else:
            raise Exception(f"RunPod API error: {response.status_code} - {response.text}")
        
        elapsed_time = time.time() - start_time
        print(f"✅ Job completed in {elapsed_time:.1f} seconds!")
        print(f"Job ID: {result.get('id')}")
        print(f"Status: {result.get('status')}")
        
        # Handle different status outcomes
        if result.get('status') == 'COMPLETED' and result.get("output"):
            output = result["output"]
            
            if output.get("status") == "completed":
                print("🎉 Video processing completed successfully!")
                
                if "job_id" in output:
                    print(f"🔍 Processed job ID: {output['job_id']}")
                if "test_real_files" in output:
                    print("✅ RunPod processed real files!")
                
                if output.get("video_base64"):
                    # Save the output video
                    video_data = base64.b64decode(output["video_base64"])
                    with open("runpod_test_output.mp4", "wb") as f:
                        f.write(video_data)
                    print(f"✅ Output video saved as 'runpod_test_output.mp4' ({len(video_data)} bytes)")
                else:
                    print("⚠️ No video data in response")
                    
            elif output.get("status") == "failed":
                print(f"❌ Video processing failed: {output.get('error')}")
                if output.get("traceback"):
                    print(f"Traceback: {output['traceback']}")
            else:
                print(f"⚠️ Unexpected output status: {output.get('status')}")
                
        elif result.get('status') == 'IN_PROGRESS':
            print("⏳ Job is still processing - this shouldn't happen with runsync")
            print("Check RunPod dashboard for job status")
        else:
            print(f"⚠️ Unexpected job status: {result.get('status')}")
            print(f"Full result: {result}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    test_runpod_deployment()