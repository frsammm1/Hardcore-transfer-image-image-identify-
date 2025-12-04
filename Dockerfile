FROM python:3.9-slim

WORKDIR /app

# Install system dependencies including FFmpeg and Poppler (for pdf2image)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    poppler-utils \
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
