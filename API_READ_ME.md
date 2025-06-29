# Instagram Reel Creator API Documentation

## Overview

The Instagram Reel Creator API is a FastAPI-based service that creates video reels from static images, audio files, and lyrics. It automatically generates synchronized subtitles using advanced transcription and alignment techniques.

## Features

- **Video Creation**: Combines static images with audio to create video content
- **Smart Subtitle Generation**: Uses ElevenLabs Scribe API for accurate transcription
- **Lyrics Alignment**: Intelligently aligns provided lyrics with audio timing
- **Multiple Alignment Modes**: Auto, ElevenLabs direct, or even distribution
- **Customizable Styling**: Configurable font size, color, and timing options
- **File Format Support**: JPEG/PNG images, MP3/WAV/FLAC audio

## Quick Start

### Using Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Instagram-Reel-Creator
   ```

2. **Set environment variables**
   ```bash
   export ELEVENLABS_API_KEY="your_elevenlabs_api_key_here"
   ```

3. **Run with Docker Compose**
   ```bash
   docker-compose up --build
   ```

4. **Access the API**
   - API Base URL: `http://localhost:8002`
   - Web Interface: `http://localhost:8002/static/index.html`

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
   python src/main.py
   ```

## API Endpoints

### POST `/create-video`

Creates a video reel from uploaded image, audio, and optional lyrics.

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

#### Example Request (cURL)

```bash
curl -X POST "http://localhost:8002/create-video" \
  -F "image=@/path/to/image.jpg" \
  -F "audio=@/path/to/audio.mp3" \
  -F "lyrics=Hello world\nThis is a test\nOf video creation" \
  -F "language=en" \
  -F "alignment_mode=auto" \
  --output output.mp4
```

#### Example Request (Python)

```python
import requests
from requests_toolbelt import MultipartEncoder

# Prepare the multipart form data
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

# Make the request
response = requests.post(
    'http://localhost:8002/create-video',
    data=encoder,
    headers={'Content-Type': encoder.content_type},
    timeout=120  # Video processing can take time
)

# Save the video file
if response.status_code == 200:
    with open('output.mp4', 'wb') as f:
        f.write(response.content)
    print("Video created successfully!")
else:
    print(f"Error: {response.status_code}")
    print(response.json())
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

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `ELEVENLABS_API_KEY` | ElevenLabs API key for transcription | Yes (for auto/elevenlabs modes) |

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
- Typical processing time: 1-3 minutes for a 3-minute audio file
- Factors affecting speed:
  - Audio duration
  - Number of lyrics lines
  - ElevenLabs API response time
  - Server resources

### Rate Limiting
- No built-in rate limiting (implement as needed)
- ElevenLabs API has its own rate limits
- Consider implementing queuing for production use

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

1. **FastAPI Server** (`src/main.py`)
   - Handles HTTP requests
   - File upload management
   - Error handling and responses

2. **Audio Processing** 
   - ElevenLabs Scribe integration
   - Audio format handling
   - Duration calculation

3. **Video Generation**
   - MoviePy for video composition
   - Subtitle rendering
   - Font management

4. **Alignment Engine**
   - Word-level matching
   - Timing optimization
   - Fallback strategies

### File Structure

```
Instagram-Reel-Creator/
├── src/
│   └── main.py              # Main API server
├── static/
│   └── index.html           # Web interface
├── requirements.txt         # Python dependencies
├── Dockerfile              # Container definition
├── docker-compose.yml      # Docker Compose config
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