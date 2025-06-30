# RunPod Serverless GPU Setup Guide

This guide walks you through setting up GPU-accelerated video processing using RunPod serverless infrastructure.

## Prerequisites

1. **RunPod Account**: Sign up at [runpod.io](https://runpod.io)
2. **Docker Hub Account**: For hosting the GPU-optimized image
3. **API Keys**: ElevenLabs API key for transcription

## Step 1: Build and Push GPU Docker Image

### 1.1 Build the GPU-optimized image
```bash
# Build from the project root directory (REQUIRED)
# Make sure you're in the main project directory, not in runpod/
docker build -f runpod/Dockerfile -t your-dockerhub-username/reel-creator-gpu:latest .

# Example with your username:
docker build -f runpod/Dockerfile -t arathron/reel-creator-gpu:latest .
```

**Important**: You must build from the project root directory because Docker needs access to all the project files.

### 1.2 Push to Docker Hub
```bash
# Login to Docker Hub
docker login

# Push the image
docker push your-dockerhub-username/reel-creator-gpu:latest
```

## Step 2: Create RunPod Serverless Endpoint

### 2.1 Access RunPod Console
1. Go to [runpod.io](https://runpod.io) and login
2. Navigate to **Serverless** → **Endpoints**
3. Click **+ New Endpoint**

### 2.2 Configure the Endpoint

**Template Settings:**
- **Template Name**: `Instagram Reel Creator GPU`
- **Container Image**: `your-dockerhub-username/reel-creator-gpu:latest`
- **Container Registry Credentials**: Your Docker Hub credentials (if private repo)

**Environment Variables:**
```
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512
MOVIEPY_TEMP_DIR=/tmp/moviepy
```

**GPU Configuration:**
- **GPU Type**: RTX 4090 or A100 (recommended)
- **GPU Count**: 1
- **Container Disk**: 20 GB (minimum)
- **Memory**: 16 GB (minimum)

**Scaling Settings:**
- **Min Workers**: 0 (important for cost savings)
- **Max Workers**: 1-3 (depending on expected load)
- **Idle Timeout**: 5 seconds (quick shutdown when not in use)
- **Max Job Time**: 600 seconds (10 minutes timeout)

**Advanced Settings:**
- **Handler**: Leave default (uses handler.py)
- **Port**: Leave default

### 2.3 Deploy the Endpoint
1. Click **Deploy**
2. Wait for deployment (usually 2-5 minutes)
3. **Note the Endpoint ID** - you'll need this for integration

## Step 3: Get RunPod API Key

### 3.1 Generate API Key
1. In RunPod console, go to **Settings** → **API Keys**
2. Click **+ Create API Key**
3. Name it `Instagram Reel Creator`
4. **Copy and save the API key securely**

## Step 4: Test the Deployment

### 4.1 Set Environment Variables
```bash
export RUNPOD_API_KEY="your_runpod_api_key"
export RUNPOD_ENDPOINT_ID="your_endpoint_id"
```

### 4.2 Prepare Test Files
```bash
# Create test files in the project root
# You need a sample image and audio file for testing
cp /path/to/test/image.jpg test_image.jpg
cp /path/to/test/audio.mp3 test_audio.mp3
```

### 4.3 Run Test Script
```bash
# Run from the project root directory
python runpod/deploy.py
```

**Expected Output:**
```
🚀 Submitting test job to RunPod...
✅ Job submitted successfully!
Job ID: 12345-abcde-67890
Status: COMPLETED
✅ Output video saved as 'runpod_test_output.mp4'
```

## Step 5: Integration with Main API

### 5.1 Update Your Main API
Add RunPod integration to your async API by modifying `src/worker.py`:

```python
# Add at the top of worker.py
import os
from runpod.deploy import RunPodClient

# Add this method to VideoProcessor class
def process_with_runpod(self, job_data: dict) -> bool:
    """Process job using RunPod GPU instead of local CPU."""
    runpod_api_key = os.environ.get("RUNPOD_API_KEY")
    runpod_endpoint_id = os.environ.get("RUNPOD_ENDPOINT_ID")
    
    if not runpod_api_key or not runpod_endpoint_id:
        logger.warning("RunPod credentials not available, falling back to local processing")
        return self.process_video_job(job_data)
    
    try:
        client = RunPodClient(runpod_api_key)
        
        result = client.submit_job(
            endpoint_id=runpod_endpoint_id,
            image_path=job_data["image_path"],
            audio_path=job_data["audio_path"],
            job_id=job_data["job_id"],
            **{k: v for k, v in job_data.items() 
               if k not in ["job_id", "image_path", "audio_path"]}
        )
        
        if result.get("output") and result["output"].get("status") == "completed":
            # Save the video from base64
            import base64
            video_data = base64.b64decode(result["output"]["video_base64"])
            output_path = os.path.join(OUTPUT_DIR, f"output_{job_data['job_id']}.mp4")
            
            with open(output_path, "wb") as f:
                f.write(video_data)
            
            return True
        else:
            logger.error(f"RunPod job failed: {result}")
            return False
            
    except Exception as e:
        logger.error(f"RunPod processing failed: {e}")
        logger.info("Falling back to local processing")
        return self.process_video_job(job_data)

# Modify the main worker loop to use RunPod when available
def run_worker():
    processor = VideoProcessor()
    logger.info(f"Starting worker {processor.worker_id}")
    
    # Check if RunPod is configured
    use_runpod = bool(os.environ.get("RUNPOD_API_KEY") and os.environ.get("RUNPOD_ENDPOINT_ID"))
    if use_runpod:
        logger.info("🚀 RunPod GPU acceleration enabled")
    else:
        logger.info("🖥️  Using local CPU processing")
    
    while True:
        try:
            job_data_str = redis_client.brpop("video_jobs", timeout=30)
            if job_data_str is None:
                continue
            
            _, job_json = job_data_str
            job_data = json.loads(job_json)
            
            if use_runpod:
                success = processor.process_with_runpod(job_data)
            else:
                success = processor.process_video_job(job_data)
            
            # ... rest of the loop
```

### 5.2 Update Docker Compose
Add RunPod environment variables to `docker-compose.yml`:

```yaml
worker:
  build: .
  volumes:
    - .:/app
    - ./output:/app/output
    - ./uploads:/app/uploads
  environment:
    - ELEVENLABS_API_KEY=${ELEVENLABS_API_KEY}
    - REDIS_URL=redis://redis:6379
    - RUNPOD_API_KEY=${RUNPOD_API_KEY}
    - RUNPOD_ENDPOINT_ID=${RUNPOD_ENDPOINT_ID}
  depends_on:
    - redis
  command: python src/worker.py
```

### 5.3 Set Environment Variables
```bash
export ELEVENLABS_API_KEY="your_elevenlabs_key"
export RUNPOD_API_KEY="your_runpod_key"
export RUNPOD_ENDPOINT_ID="your_endpoint_id"
```

## Step 6: Monitor and Optimize

### 6.1 Monitor Costs
- Check RunPod billing dashboard regularly
- Expected cost: ~$0.50-1.00 per 10-minute job
- Monthly estimate for 3 jobs/day: $15-25

### 6.2 Performance Monitoring
```bash
# Check worker logs
docker-compose logs -f worker

# Monitor job processing times
docker-compose logs worker | grep "processing_time_seconds"
```

### 6.3 Optimization Tips
- **Cold Start**: First job may take 30-60 seconds to start
- **Warm Instances**: Subsequent jobs are faster if within idle timeout
- **Batch Processing**: Consider batching multiple jobs if you get more volume

## Troubleshooting

### Common Issues

**1. Docker Build Fails**
```bash
# Make sure you're in the right directory
cd runpod/
# Check Dockerfile syntax
docker build --no-cache -t test-build .
```

**2. RunPod Deployment Fails**
- Check image exists in Docker Hub
- Verify environment variables are set correctly
- Ensure GPU configuration is compatible

**3. Jobs Timeout**
- Increase max job time in RunPod settings
- Check worker logs for specific errors
- Verify file sizes are within limits

**4. High Costs**
- Ensure min workers is set to 0
- Check idle timeout is configured properly
- Monitor actual usage vs expected

### Debug Mode
Enable detailed logging:
```bash
# Add to environment variables
RUNPOD_DEBUG=true
```

## Expected Performance

| Processing Type | Time per Job | Cost per Job | Monthly Cost (3/day) |
|----------------|--------------|--------------|---------------------|
| Local CPU      | 3-5 minutes  | $0           | $0                  |
| RunPod GPU     | 30-60 seconds| $0.50-1.00   | $15-25              |

## Security Notes

- Never commit API keys to version control
- Use environment variables for all secrets
- Regularly rotate API keys
- Monitor usage for unexpected charges