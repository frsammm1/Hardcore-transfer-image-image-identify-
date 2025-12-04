import asyncio
import time
import math
import config
from utils import human_readable_size, time_formatter

async def progress_callback(current, total, start_time, file_name, status_msg):
    """Update progress with SAFE frequency"""
    now = time.time()
    
    # 🔒 Increased update interval to reduce API calls
    if now - config.last_update_time < config.UPDATE_INTERVAL: 
        return 
    config.last_update_time = now
    
    percentage = current * 100 / total if total > 0 else 0
    time_diff = now - start_time
    speed = current / time_diff if time_diff > 0 else 0
    eta = (total - current) / speed if speed > 0 else 0
    
    filled = math.floor(percentage / 10)
    bar = "█" * filled + "░" * (10 - filled)
    
    try:
        await status_msg.edit(
            f"🔒 **SAFE MODE (512KB × 2)**\n"
            f"📂 `{file_name[:40]}...`\n"
            f"**{bar} {round(percentage, 1)}%**\n"
            f"⚡ `{human_readable_size(speed)}/s` | ⏳ `{time_formatter(eta)}`\n"
            f"💾 `{human_readable_size(current)} / {human_readable_size(total)}`"
        )
    except Exception:
        pass

class SafeBufferedStream:
    """
    🔒 SAFE performance streaming with 512KB chunks and 2-queue buffer (~1MB)
    Optimized for ban prevention while maintaining decent speed
    """
    def __init__(self, client, location, file_size, file_name, start_time, status_msg):
        self.client = client
        self.location = location
        self.file_size = file_size
        self.name = file_name
        self.start_time = start_time
        self.status_msg = status_msg
        self.current_bytes = 0
        
        # 🔒 SAFE SETTINGS (reduced from extreme)
        self.chunk_size = config.CHUNK_SIZE  # Now 512KB
        self.queue = asyncio.Queue(maxsize=config.QUEUE_SIZE)  # Now 2 (~1MB buffer)
        
        self.downloader_task = asyncio.create_task(self._worker())
        self.buffer = b""
        self.closed = False
        
        config.logger.info(f"🔒 SAFE Stream: 512KB chunks, 1MB buffer for {file_name}")

    async def _worker(self):
        """Background worker to download chunks with SAFE settings"""
        try:
            async for chunk in self.client.iter_download(
                self.location, 
                chunk_size=self.chunk_size,  # 512KB chunks
                request_size=self.chunk_size  # Match request size
            ):
                if self.closed:
                    break
                
                await self.queue.put(chunk)
                
                # 🔒 Small delay every 10 chunks to prevent rate limiting
                self.current_bytes += len(chunk)
                chunks_downloaded = self.current_bytes // self.chunk_size
                if chunks_downloaded % 10 == 0:
                    await asyncio.sleep(0.1)  # 100ms pause
            
            await self.queue.put(None) 
        except Exception as e:
            config.logger.error(f"⚠️ Stream Worker Error: {e}")
            await self.queue.put(None)

    def __len__(self):
        return self.file_size

    async def read(self, size=-1):
        """Read data from stream"""
        if self.closed:
            return b""
            
        if size == -1: 
            size = self.chunk_size
            
        while len(self.buffer) < size:
            chunk = await self.queue.get()
            if chunk is None: 
                if self.current_bytes < self.file_size:
                    config.logger.warning(f"⚠️ Incomplete: {self.current_bytes}/{self.file_size}")
                self.closed = True
                break
            self.buffer += chunk
            
            # Fire-and-forget progress update (less frequent)
            asyncio.create_task(progress_callback(
                self.current_bytes, 
                self.file_size, 
                self.start_time, 
                self.name,
                self.status_msg
            ))
            
        data = self.buffer[:size]
        self.buffer = self.buffer[size:]
        return data

    async def close(self):
        """Clean shutdown of stream"""
        self.closed = True
        if self.downloader_task and not self.downloader_task.done():
            self.downloader_task.cancel()
            try:
                await self.downloader_task
            except asyncio.CancelledError:
                pass
