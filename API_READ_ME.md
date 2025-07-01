# Instagram Reel Creator API Documentation

## Overview

The Instagram Reel Creator API is a FastAPI-based service that creates video reels from static images, audio files, and lyrics. It features an async job queue system with optional GPU acceleration via RunPod serverless for high-performance video processing.

## Features

- **Async Job Queue**: Background processing with Redis-based job queue
- **GPU Acceleration**: Optional RunPod serverless GPU for 3-5x faster processing
- **Video Creation**: Combines static images with audio to create video content
- **Smart Subtitle Generation**: Uses ElevenLabs Scribe API for accurate transcription
- **Lyrics Alignment**: Intelligently aligns provided lyrics with audio timing
- **Multiple Alignment Modes**: Auto, ElevenLabs direct, or even distribution
- **Customizable Styling**: Configurable font size, color, and timing options
- **File Format Support**: JPEG/PNG images, MP3/WAV/FLAC audio
- **Job Status Tracking**: Real-time progress updates and status monitoring
- **Scalable Architecture**: Supports multiple workers and load balancing

## Quick Start

### Using Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Instagram-Reel-Creator
   ```

2. **Set environment variables**
   ```bash
   # Copy environment template
   cp .env.example .env
   
   # Edit .env with your API keys
   ELEVENLABS_API_KEY="your_elevenlabs_api_key_here"
   RUNPOD_API_KEY="your_runpod_key"  # Optional, for GPU acceleration
   RUNPOD_ENDPOINT_ID="your_endpoint_id"  # Optional, for GPU acceleration
   ```

3. **Run with Docker Compose**
   ```bash
   # Start async system (Redis, API, Worker)
   docker-compose up --build
   ```

4. **Access the API**
   - Async API: `http://localhost:8002`
   - Legacy Sync API: `http://localhost:8003` (optional)
   - Web Interface: `http://localhost:8002/static/async_test.html`

### Manual Installation

1. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install system dependencies**
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install -y ffmpeg fonts-liberation fonts-freefont-ttf

   # macOS
   brew install ffmpeg
   ```

3. **Run the API server**
   ```bash
   # Start Redis locally
   redis-server
   
   # In separate terminals:
   python src/async_api.py    # API server
   python src/worker.py       # Background worker
   
   # Legacy sync API (optional)
   python src/main.py
   ```

## API Architecture Types

### 1. Async API (Recommended)
Modern job queue system with background processing, status tracking, and optional GPU acceleration.

### 2. Legacy Sync API
Single endpoint that processes videos synchronously - users wait for completion.

## API Endpoints

### Async Job API Endpoints

#### POST `/jobs/create-video`

Submits a video creation job to the queue and returns immediately with a job ID.

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `image` | File | Yes | Image file (JPEG/PNG, max 100MB) |
| `audio` | File | Yes | Audio file (MP3/WAV/FLAC, max 100MB) |
| `lyrics` | String | No | Lyrics text for subtitle generation |
| `language` | String | No | Language code (e.g., 'en', 'hi', 'es') |
| `font_size` | Integer | No | Font size for subtitles (default: 45) |
| `font_color` | String | No | Font color for subtitles (default: "yellow") |
| `words_per_group` | Integer | No | Words to display together (default: 3) |
| `timing_offset` | Float | No | Global timing offset in seconds (default: 0.0) |
| `min_duration` | Float | No | Minimum duration per subtitle (default: 1.0) |
| `alignment_mode` | String | No | "auto", "elevenlabs", or "even" (default: "auto") |
| `debug_mode` | Boolean | No | Add timing info to subtitles (default: false) |

#### Response

```json
{
  "job_id": "uuid-string",
  "status": "pending",
  "created_at": "2023-01-01T00:00:00",
  "progress_percentage": 0
}
```

#### GET `/jobs/{job_id}`

Check job status and progress.

#### Response

```json
{
  "job_id": "uuid-string",
  "status": "processing",  // pending, processing, completed, failed
  "progress_percentage": 75,
  "created_at": "2023-01-01T00:00:00",
  "started_at": "2023-01-01T00:01:00",
  "processing_time_seconds": 45.2,
  "error_message": null
}
```

#### GET `/jobs/{job_id}/download`

Download the completed video file (only available when status is "completed").

**⚠️ Important**: The video file is automatically deleted from the server after successful download to save storage space. You can only download each video once.

#### DELETE `/jobs/{job_id}`

Delete job and associated files.

#### GET `/jobs`

List all jobs with optional filtering:
- `?status=completed` - Filter by status
- `?limit=10` - Limit results

#### GET `/health`

Health check for API and Redis connectivity.

#### POST `/admin/cleanup`

Clean up old completed jobs and their files to save server space.

**Parameters:**
- `max_age_hours` (optional): Delete jobs older than this many hours (default: 24)

**Response:**
```json
{
  "message": "Cleanup completed",
  "jobs_deleted": 5,
  "files_deleted": 15,
  "cutoff_time": "2023-01-01T00:00:00"
}
```

**Usage:**
```bash
# Clean up jobs older than 24 hours (default)
curl -X POST "http://localhost:8002/admin/cleanup"

# Clean up jobs older than 6 hours
curl -X POST "http://localhost:8002/admin/cleanup?max_age_hours=6"
```

### Legacy Sync API Endpoint

#### POST `/create-video` (Legacy)

Creates a video reel synchronously - user waits for completion.

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `image` | File | Yes | Image file (JPEG/PNG, max 100MB) |
| `audio` | File | Yes | Audio file (MP3/WAV/FLAC, max 100MB) |
| `lyrics` | String | No | Lyrics text for subtitle generation |
| `language` | String | No | Language code (e.g., 'en', 'hi', 'es') |
| `font_size` | Integer | No | Font size for subtitles (default: 45) |
| `font_color` | String | No | Font color for subtitles (default: "yellow") |
| `words_per_group` | Integer | No | Words to display together (default: 3) |
| `timing_offset` | Float | No | Global timing offset in seconds (default: 0.0) |
| `min_duration` | Float | No | Minimum duration per subtitle (default: 1.0) |
| `alignment_mode` | String | No | "auto", "elevenlabs", or "even" (default: "auto") |
| `debug_mode` | Boolean | No | Add timing info to subtitles (default: false) |

#### Response

- **Success (200)**: Returns the generated MP4 video file
- **Error (4xx/5xx)**: Returns JSON with error details

#### Example Request (cURL) - Async API

```bash
# Submit job
JOB_ID=$(curl -X POST "http://localhost:8002/jobs/create-video" \
  -F "image=@/path/to/image.jpg" \
  -F "audio=@/path/to/audio.mp3" \
  -F "lyrics=Hello world\nThis is a test\nOf video creation" \
  -F "language=en" \
  -F "alignment_mode=auto" | jq -r '.job_id')

# Check status
curl "http://localhost:8002/jobs/$JOB_ID"

# Download when completed
curl "http://localhost:8002/jobs/$JOB_ID/download" --output output.mp4
```

#### Example Request (cURL) - Legacy Sync API

```bash
curl -X POST "http://localhost:8003/create-video" \
  -F "image=@/path/to/image.jpg" \
  -F "audio=@/path/to/audio.mp3" \
  -F "lyrics=Hello world\nThis is a test\nOf video creation" \
  -F "language=en" \
  -F "alignment_mode=auto" \
  --output output.mp4
```

#### Example Request (Python) - Async API

```python
import requests
import time
from requests_toolbelt import MultipartEncoder

# Submit job
encoder = MultipartEncoder(
    fields={
        'image': ('image.jpg', open('path/to/image.jpg', 'rb'), 'image/jpeg'),
        'audio': ('audio.mp3', open('path/to/audio.mp3', 'rb'), 'audio/mpeg'),
        'lyrics': 'Hello world\\nThis is a test\\nOf video creation',
        'language': 'en',
        'font_size': '50',
        'font_color': 'white',
        'alignment_mode': 'auto'
    }
)

# Submit job
response = requests.post(
    'http://localhost:8002/jobs/create-video',
    data=encoder,
    headers={'Content-Type': encoder.content_type}
)

if response.status_code == 200:
    job_data = response.json()
    job_id = job_data['job_id']
    print(f"Job submitted: {job_id}")
    
    # Poll for completion
    while True:
        status_response = requests.get(f'http://localhost:8002/jobs/{job_id}')
        status_data = status_response.json()
        
        print(f"Status: {status_data['status']} ({status_data['progress_percentage']}%)")
        
        if status_data['status'] == 'completed':
            # Download video
            download_response = requests.get(f'http://localhost:8002/jobs/{job_id}/download')
            with open('output.mp4', 'wb') as f:
                f.write(download_response.content)
            print("Video downloaded successfully!")
            break
        elif status_data['status'] == 'failed':
            print(f"Job failed: {status_data.get('error_message')}")
            break
        
        time.sleep(5)  # Wait 5 seconds before checking again
```

#### Example Request (JavaScript/Node.js)

```javascript
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

const form = new FormData();
form.append('image', fs.createReadStream('path/to/image.jpg'));
form.append('audio', fs.createReadStream('path/to/audio.mp3'));
form.append('lyrics', 'Hello world\\nThis is a test\\nOf video creation');
form.append('language', 'en');
form.append('alignment_mode', 'auto');

axios.post('http://localhost:8002/create-video', form, {
    headers: {
        ...form.getHeaders(),
    },
    responseType: 'stream',
    timeout: 120000
}).then(response => {
    response.data.pipe(fs.createWriteStream('output.mp4'));
    console.log('Video created successfully!');
}).catch(error => {
    console.error('Error creating video:', error.response?.data || error.message);
});
```

## Alignment Modes

### 1. Auto Mode (Default)
- Attempts to align provided lyrics with ElevenLabs transcription
- Falls back to ElevenLabs transcription if alignment fails
- Best balance of accuracy and control

### 2. ElevenLabs Mode
- Uses ElevenLabs transcription directly
- Ignores provided lyrics for subtitle content
- Most accurate timing but uses transcribed text

### 3. Even Mode
- Distributes provided lyrics evenly across audio duration
- Does not use ElevenLabs API
- Fastest processing but less accurate timing

## GPU Acceleration with RunPod

### Overview
The system supports optional GPU acceleration via RunPod serverless, providing 3-5x faster video processing.

### How It Works
1. **Input Transfer**: Images/audio encoded as base64 and sent to RunPod GPU instance
2. **GPU Processing**: Video generation on high-performance GPU (30-60 seconds vs 2-5 minutes on CPU)
3. **Output Transfer**: Completed video encoded as base64 and returned via HTTP
4. **Automatic Cleanup**: RunPod instance shuts down automatically after completion

### Setup RunPod GPU Acceleration

1. **Create RunPod Account**
   - Sign up at [RunPod.io](https://runpod.io)
   - Add credits to your account

2. **Deploy GPU Endpoint**
   ```bash
   cd runpod/
   docker build -t your-registry/reel-creator-gpu .
   docker push your-registry/reel-creator-gpu
   ```

3. **Configure Environment Variables**
   ```bash
   RUNPOD_API_KEY="your_runpod_api_key"
   RUNPOD_ENDPOINT_ID="your_deployed_endpoint_id"
   ```

### Performance Comparison
- **CPU Processing**: 2-5 minutes per video
- **GPU Processing**: 30-60 seconds per video (3-5x faster)
- **RunPod Cold Start**: ~30-60 seconds additional overhead
- **Cost Effective**: Only pay for GPU time when processing

### When GPU is Used
- Worker automatically detects RunPod configuration
- **With GPU**: `🚀 RunPod GPU acceleration enabled`
- **Without GPU**: `💻 Using local CPU processing`

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `ELEVENLABS_API_KEY` | ElevenLabs API key for transcription | Yes (for auto/elevenlabs modes) |
| `REDIS_URL` | Redis connection URL | No (defaults to localhost:6379) |
| `RUNPOD_API_KEY` | RunPod API key for GPU acceleration | No (enables GPU processing) |
| `RUNPOD_ENDPOINT_ID` | RunPod endpoint ID for GPU acceleration | No (enables GPU processing) |

### API Key Setup

1. **Get ElevenLabs API Key**
   - Sign up at [ElevenLabs](https://elevenlabs.io)
   - Generate an API key from your dashboard

2. **Set the API Key**
   ```bash
   # Option 1: Environment variable
   export ELEVENLABS_API_KEY="your_api_key_here"
   
   # Option 2: Docker Compose
   echo "ELEVENLABS_API_KEY=your_api_key_here" > .env
   
   # Option 3: Direct code modification (not recommended)
   # Edit src/main.py line 40
   ```

## Error Handling

The API returns detailed error messages for common issues:

### Common Errors

| Status | Error | Solution |
|--------|-------|----------|
| 400 | "Lyrics text is required" | Provide lyrics parameter |
| 400 | "Image must be JPG or PNG" | Use supported image format |
| 400 | "Audio must be MP3, WAV, or FLAC" | Use supported audio format |
| 413 | "File too large" | Reduce file size under 100MB |
| 429 | "Rate limit exceeded" | Wait and retry or check API quota |
| 500 | "ElevenLabs API key is required" | Set ELEVENLABS_API_KEY |

### Debug Mode

Enable debug mode to troubleshoot timing issues:

```python
response = requests.post(url, data={
    # ... other parameters
    'debug_mode': 'true'
})
```

This adds timing information to subtitles: `[2.5s] Hello world`

## Performance Considerations

### File Size Limits
- Maximum file size: 100MB per file
- Recommended: Keep files under 50MB for faster processing

### Processing Time
**CPU Processing (Local)**:
- Typical processing time: 2-5 minutes for a 3-minute audio file
- Factors: Audio duration, lyrics complexity, server resources

**GPU Processing (RunPod)**:
- Typical processing time: 30-60 seconds for a 3-minute audio file
- Cold start overhead: 30-60 seconds
- 3-5x faster than CPU processing

### Job Queue Performance
- **Concurrent Jobs**: Multiple workers can process jobs simultaneously
- **Progress Tracking**: Real-time progress updates (0-100%)
- **Automatic Retry**: Failed jobs can be resubmitted
- **Cleanup**: Automatic file deletion when jobs are deleted

### Rate Limiting
- No built-in rate limiting (implement as needed)
- ElevenLabs API has its own rate limits
- Redis queue naturally handles load balancing
- RunPod has per-account concurrency limits

## Integration Examples

### React/Frontend Integration

```javascript
const createVideo = async (imageFile, audioFile, lyrics) => {
    const formData = new FormData();
    formData.append('image', imageFile);
    formData.append('audio', audioFile);
    formData.append('lyrics', lyrics);
    formData.append('alignment_mode', 'auto');

    const response = await fetch('/create-video', {
        method: 'POST',
        body: formData,
    });

    if (response.ok) {
        const videoBlob = await response.blob();
        const videoUrl = URL.createObjectURL(videoBlob);
        return videoUrl;
    } else {
        const error = await response.json();
        throw new Error(error.detail);
    }
};
```

### Webhook Integration

```python
# Example webhook endpoint to process videos asynchronously
@app.post("/webhook/create-video")
async def webhook_create_video(request: WebhookRequest):
    # Download files from URLs
    image_response = requests.get(request.image_url)
    audio_response = requests.get(request.audio_url)
    
    # Create video
    files = {
        'image': ('image.jpg', image_response.content, 'image/jpeg'),
        'audio': ('audio.mp3', audio_response.content, 'audio/mpeg'),
        'lyrics': request.lyrics
    }
    
    response = requests.post('http://localhost:8002/create-video', files=files)
    
    # Upload result to storage and notify
    if response.ok:
        # Upload to S3/storage service
        video_url = upload_video(response.content)
        # Notify completion
        notify_completion(request.callback_url, video_url)
```

## Troubleshooting

### Common Issues

1. **"No module named" errors**
   ```bash
   pip install -r requirements.txt
   ```

2. **Font not found errors**
   ```bash
   # Install additional fonts
   sudo apt install fonts-liberation fonts-freefont-ttf fonts-dejavu
   ```

3. **FFmpeg not found**
   ```bash
   # Ubuntu/Debian
   sudo apt install ffmpeg
   
   # macOS
   brew install ffmpeg
   ```

4. **ElevenLabs API errors**
   - Verify API key is correct
   - Check account quota/credits
   - Ensure audio file is supported format

5. **Memory issues with large files**
   - Reduce file sizes
   - Increase server memory
   - Use video compression

### Logs and Debugging

The API provides detailed logging:

```bash
# View logs when running directly
python src/main.py

# View Docker logs
docker-compose logs -f
```

Log levels include:
- `INFO`: Normal operation
- `WARNING`: Non-critical issues
- `ERROR`: Processing failures

## API Architecture

### Core Components

1. **Async API Server** (`src/async_api.py`)
   - Job submission and status endpoints
   - File upload management
   - Database integration with SQLAlchemy
   - Real-time progress tracking

2. **Background Worker** (`src/worker.py`)
   - Redis job queue processing
   - GPU/CPU video processing
   - RunPod integration for acceleration
   - Progress updates and error handling

3. **Legacy Sync API** (`src/main.py`)
   - Single endpoint synchronous processing
   - Backwards compatibility
   - Direct file response

4. **Database Layer** (`src/models.py`)
   - SQLite database with job tracking
   - Pydantic models for API responses
   - Job status and progress management

5. **RunPod GPU Handler** (`runpod/handler.py`)
   - Serverless GPU processing
   - Base64 file transfer
   - Automatic scaling and cleanup

### Architecture Components

- **Redis Queue**: FIFO job queue with persistence
- **SQLite Database**: Job metadata and status tracking  
- **File Storage**: Persistent volumes for uploads/outputs
- **RunPod Integration**: Optional GPU acceleration

### File Structure

```
Instagram-Reel-Creator/
├── src/
│   ├── async_api.py         # Async job API server
│   ├── worker.py            # Background job processor
│   ├── main.py              # Legacy sync API server
│   └── models.py            # Database models and schemas
├── runpod/
│   ├── handler.py           # RunPod GPU handler
│   └── Dockerfile           # GPU container definition
├── static/
│   ├── async_test.html      # Async API web interface
│   └── index.html           # Legacy web interface
├── requirements.txt         # Python dependencies
├── Dockerfile              # Main container definition
├── docker-compose.yml      # Development compose config
├── docker-compose.prod.yml  # Production compose config
├── COOLIFY_DEPLOYMENT.md    # Deployment guide
└── API_READ_ME.md          # This documentation
```

## Contributing

### Development Setup

1. **Fork and clone the repository**
2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\\Scripts\\activate  # Windows
   ```
3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
4. **Run tests**
   ```bash
   python test_api.py
   ```

### API Extensions

The API can be extended with additional features:

- Additional subtitle formats (SRT, VTT export)
- More video transitions and effects
- Batch processing endpoints
- Audio enhancement features
- Multi-language support improvements

## License

This project is licensed under the MIT License. See LICENSE file for details.

## Support

For issues and questions:
1. Check this documentation
2. Review the troubleshooting section
3. Check server logs for error details
4. Open an issue in the project repository

---

**Note**: This API is designed for programmatic access. For a user-friendly interface, visit the web interface at `/static/index.html`.