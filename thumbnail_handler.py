import os
import subprocess
import tempfile
from PIL import Image
import config

async def generate_video_thumbnail(video_path, time_offset="00:00:01"):
    """
    Generate thumbnail from video at specific time
    time_offset: timestamp in format "HH:MM:SS" or "SS"
    Returns: path to thumbnail image
    """
    try:
        temp_dir = tempfile.gettempdir()
        thumb_path = os.path.join(temp_dir, f"thumb_{os.path.basename(video_path)}.jpg")
        
        # FFmpeg command to extract frame
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(time_offset),
            '-i', video_path,
            '-vframes', '1',
            '-q:v', '2',  # High quality
            thumb_path
        ]
        
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30
        )
        
        if process.returncode == 0 and os.path.exists(thumb_path):
            config.logger.info(f"✅ Thumbnail generated at {time_offset}")
            return thumb_path
        else:
            config.logger.error(f"❌ FFmpeg failed: {process.stderr.decode()[:200]}")
            return None
            
    except subprocess.TimeoutExpired:
        config.logger.error("⏱️ Thumbnail generation timeout")
        return None
    except Exception as e:
        config.logger.error(f"❌ Thumbnail Error: {e}")
        return None

async def generate_smart_thumbnail(video_path, skip_seconds=10):
    """
    Generate smart thumbnail using FFmpeg thumbnail filter
    Skips first N seconds and finds best representative frame
    """
    try:
        temp_dir = tempfile.gettempdir()
        thumb_path = os.path.join(temp_dir, f"smart_thumb_{os.path.basename(video_path)}.jpg")
        
        # Smart thumbnail command
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(skip_seconds),
            '-i', video_path,
            '-vf', 'thumbnail,scale=1280:-1',
            '-frames:v', '1',
            '-q:v', '2',
            thumb_path
        ]
        
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60
        )
        
        if process.returncode == 0 and os.path.exists(thumb_path):
            config.logger.info(f"🎯 Smart thumbnail generated (skip {skip_seconds}s)")
            return thumb_path
        else:
            # Fallback to simple extraction
            return await generate_video_thumbnail(video_path, skip_seconds)
            
    except Exception as e:
        config.logger.error(f"❌ Smart Thumbnail Error: {e}")
        return None

async def extract_multiple_frames(video_path, count=5, interval=None):
    """
    Extract multiple frames from video for selection
    count: number of frames to extract
    interval: time between frames in seconds (auto if None)
    Returns: list of thumbnail paths
    """
    try:
        temp_dir = tempfile.gettempdir()
        frames = []
        
        # Get video duration
        duration_cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        
        result = subprocess.run(duration_cmd, capture_output=True, text=True, timeout=10)
        duration = float(result.stdout.strip())
        
        if interval is None:
            interval = max(1, int(duration / (count + 1)))
        
        for i in range(count):
            time_pos = (i + 1) * interval
            if time_pos >= duration:
                break
                
            thumb_path = os.path.join(temp_dir, f"frame_{i}_{os.path.basename(video_path)}.jpg")
            
            cmd = [
                'ffmpeg', '-y',
                '-ss', str(time_pos),
                '-i', video_path,
                '-vframes', '1',
                '-q:v', '2',
                thumb_path
            ]
            
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            
            if os.path.exists(thumb_path):
                frames.append(thumb_path)
        
        config.logger.info(f"📸 Extracted {len(frames)} frames")
        return frames
        
    except Exception as e:
        config.logger.error(f"❌ Frame Extraction Error: {e}")
        return []

def is_ffmpeg_available():
    """Check if FFmpeg is installed"""
    try:
        subprocess.run(
            ['ffmpeg', '-version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5
        )
        return True
    except:
        return False
