FROM python:3.9-slim

WORKDIR /app

# Install system dependencies including FFmpeg, Poppler, and OpenCV requirements
RUN apt-get update && apt-get install -y \
    ffmpeg \
    poppler-utils \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose port
EXPOSE 8080

# Run the bot
CMD ["python", "main.py"]
