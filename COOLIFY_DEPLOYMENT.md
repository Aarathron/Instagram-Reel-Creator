# Coolify Deployment Guide

## Quick Fix for Current Issue

The error `python: can't open file '/app/src/async_api.py': [Errno 2] No such file or directory` occurs because your Coolify deployment is using volume mounts that override the copied files.

## Step-by-Step Coolify Setup

### 1. Choose Your Deployment Method

**Option A: Docker Compose (Recommended)**
- Use the `docker-compose.prod.yml` file
- All services (API, Worker, Redis) in one deployment

**Option B: Separate Services**
- Deploy API, Worker, and Redis as separate Coolify services
- More granular control but more complex setup

### 2. Using Docker Compose Method

1. **In Coolify Dashboard:**
   - Click "New Resource" → "Docker Compose"
   - Connect your Git repository (GitHub/GitLab/etc.)
   - Set the Docker Compose file path: `docker-compose.prod.yml`

2. **Environment Variables:**
   ```bash
   ELEVENLABS_API_KEY=your_elevenlabs_key_here
   OPENAI_API_KEY=your_openai_key_here  # Optional
   RUNPOD_API_KEY=your_runpod_key_here  # For GPU acceleration
   RUNPOD_ENDPOINT_ID=your_endpoint_id  # For GPU acceleration
   ```
   
   **Important**: Both `RUNPOD_API_KEY` and `RUNPOD_ENDPOINT_ID` are required for GPU processing. Without both variables, the worker will default to CPU processing.

3. **Configure Ports:**
   - Main API will be available on port 8002
   - Coolify will provide a public URL

### 3. Using Separate Services Method

#### 3a. Deploy Redis First
1. In Coolify: "New Resource" → "Database" → "Redis"
2. Note the connection details for next steps

#### 3b. Deploy API Service
1. "New Resource" → "Application" 
2. Connect your Git repository
3. Build Pack: Docker
4. Dockerfile path: `Dockerfile`
5. Command: `python src/async_api.py`
6. Port: 8002
7. Environment variables:
   ```bash
   REDIS_URL=redis://your-redis-host:6379
   ELEVENLABS_API_KEY=your_key
   ```

#### 3c. Deploy Worker Service
1. "New Resource" → "Application"
2. Same Git repository
3. Command: `python src/worker.py`
4. No port needed (background service)
5. Same environment variables as API

### 4. Important Coolify Settings

- **Build Context:** Set to repository root
- **Auto Deploy:** Enable for automatic updates
- **Health Checks:** Enable for better monitoring
- **Persistent Storage:** Coolify handles volumes automatically

### 5. Testing Your Deployment

Once deployed, test with:

```bash
# Replace YOUR_COOLIFY_URL with your actual URL
curl -X POST https://YOUR_COOLIFY_URL/jobs/create-video \
  -F "image=@test.jpg" \
  -F "audio=@test.mp3" \
  -F "lyrics=test lyrics"
```

### 6. Troubleshooting

**File Not Found Errors:**
- Ensure you're using `docker-compose.prod.yml` (no volume mounts)
- Check that Coolify is building from the correct Git branch

**Environment Variables:**
- Verify all required environment variables are set in Coolify
- ELEVENLABS_API_KEY is required for the service to work

**Port Issues:**
- Coolify automatically handles port mapping
- Use the provided public URL, not localhost

**Redis Connection:**
- If using separate services, ensure Redis URL is correct
- Check Coolify logs for connection errors

### 7. Monitoring

- Use Coolify's built-in logs viewer
- Monitor the API container for HTTP requests
- Monitor the Worker container for job processing
- Check Redis for job queue status

## Files Changed

1. **Dockerfile** - Updated for production deployment
2. **docker-compose.prod.yml** - New production compose file
3. **COOLIFY_DEPLOYMENT.md** - This deployment guide

## Next Steps

1. Push these changes to your Git repository
2. Set up the deployment in Coolify using the steps above
3. Configure your environment variables
4. Test the deployment with a sample request