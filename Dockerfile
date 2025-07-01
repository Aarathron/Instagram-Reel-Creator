FROM python:3.9-slim

# Install system dependencies including FFmpeg and fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-liberation \
    fonts-liberation2 \
    fonts-freefont-ttf \
    fonts-indic \
    fonts-noto-extra \
    imagemagick \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -fv

# Fix ImageMagick policy to allow PDF operations
RUN sed -i 's/rights="none" pattern="@\*"/rights="read|write" pattern="@*"/' /etc/ImageMagick-6/policy.xml

# Set the working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Install git for version control if needed
RUN apt-get update && apt-get install -y --no-install-recommends git-core \
    && rm -rf /var/lib/apt/lists/*

# Create directories for uploads and output
RUN mkdir -p /app/uploads /app/output

# Set proper permissions
RUN chmod -R 755 /app

# Default command (can be overridden)
CMD ["python", "src/async_api.py"]
