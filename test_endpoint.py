import requests
from requests_toolbelt import MultipartEncoder
import os

def get_file_size(file_path):
    return os.path.getsize(file_path)

# Get file sizes
image_path = 'static/img.png'
audio_path = 'static/test.mp3'

# Print file sizes
image_size = os.path.getsize(image_path)
audio_size = os.path.getsize(audio_path)
print(f"Image size: {image_size / (1024*1024):.2f} MB")
print(f"Audio size: {audio_size / (1024*1024):.2f} MB")
print(f"Total size: {(image_size + audio_size) / (1024*1024):.2f} MB")

# Test lyrics
test_lyrics = """Hello world
This is a test
Of the video creation
With lyrics alignment"""

# Create multipart encoder
encoder = MultipartEncoder(
    fields={
        'image': ('img.png', open(image_path, 'rb'), 'image/png'),
        'audio': ('test.mp3', open(audio_path, 'rb'), 'audio/mpeg'),
        'lyrics': test_lyrics,
        'language': 'en',
        'alignment_mode': 'even'
    }
)

# Print actual payload size
print(f"Payload size: {len(encoder.to_string()) / (1024*1024):.2f} MB")

# Make request with proper headers
headers = {'Content-Type': encoder.content_type}
try:
    response = requests.post(
        'http://localhost:8002/create-video',  # Updated port
        data=encoder,
        headers=headers,
        timeout=60  # Increased timeout for video processing
    )
    print(f"Response received with status code: {response.status_code}")
except requests.exceptions.Timeout:
    print("Request timed out after 60 seconds")
    exit(1)
except requests.exceptions.RequestException as e:
    print(f"Request failed: {str(e)}")
    exit(1)

if response.status_code == 200:
    with open('output.mp4', 'wb') as f:
        f.write(response.content)
    print("Video created successfully!")
else:
    print(f"Error: {response.status_code}")
    try:
        error_json = response.json()
        print(f"Error detail: {error_json.get('detail', 'No detail provided')}")
    except:
        print(f"Raw error text: {response.text}")
