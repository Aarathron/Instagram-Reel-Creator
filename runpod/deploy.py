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
    
    # Test with sample files (you'll need to provide these)
    sample_image = "test_image.jpg"
    sample_audio = "test_audio.mp3"
    
    if not os.path.exists(sample_image) or not os.path.exists(sample_audio):
        print("❌ Sample test files not found")
        print("Please provide 'test_image.jpg' and 'test_audio.mp3' for testing")
        return
    
    try:
        print("🚀 Submitting test job to RunPod...")
        
        result = client.submit_job(
            endpoint_id=endpoint_id,
            image_path=sample_image,
            audio_path=sample_audio,
            job_id="test-job-123",
            lyrics="This is a test video with sample lyrics for testing the RunPod deployment.",
            language="en",
            alignment_mode="auto"
        )
        
        print("✅ Job submitted successfully!")
        print(f"Job ID: {result.get('id')}")
        print(f"Status: {result.get('status')}")
        
        if result.get("output") and result["output"].get("video_base64"):
            # Save the output video
            video_data = base64.b64decode(result["output"]["video_base64"])
            with open("runpod_test_output.mp4", "wb") as f:
                f.write(video_data)
            print("✅ Output video saved as 'runpod_test_output.mp4'")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    test_runpod_deployment()