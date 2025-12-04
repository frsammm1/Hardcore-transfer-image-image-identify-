import os
import logging

# --- TELEGRAM CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH")
STRING_SESSION = os.environ.get("STRING_SESSION") 
BOT_TOKEN = os.environ.get("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 8080))

# --- BALANCED MODE SETTINGS (Speed + Safety) ---
# 🔶 2MB chunks - Good balance
CHUNK_SIZE = 2 * 1024 * 1024  # 2MB chunks (BALANCED)

# 🔶 3 queue - 6MB buffer
QUEUE_SIZE = 3  # 6MB buffer (2MB × 3)

# 🔶 2MB upload parts
UPLOAD_PART_SIZE = 2048  # 2MB upload parts (BALANCED)

# 🔶 Standard update interval
UPDATE_INTERVAL = 12  # Progress update every 12s

# 🔶 Moderate retries
MAX_RETRIES = 3  # Retry 3 times

# 🔶 Standard flood protection
FLOOD_SLEEP_THRESHOLD = 90  # Sleep on flood (90s)

# 🔶 Moderate request retries
REQUEST_RETRIES = 8  # Moderate (8 retries)

# 🔶 Reduced delays for better speed
FILE_TRANSFER_DELAY = 2  # Wait 2 seconds between files (was 3)
LARGE_FILE_DELAY = 3  # Wait 3 seconds after files >50MB (was 5)
SESSION_SAVE_INTERVAL = 300  # Save session every 5 minutes

# 🔶 Session protection (same as safe)
AUTO_RECONNECT_DELAY = 10
MAX_RECONNECT_ATTEMPTS = 3
SESSION_BACKUP_ENABLED = True

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- RUNTIME STATE ---
pending_requests = {}
active_sessions = {}
is_running = False
status_message = None
last_update_time = 0
current_task = None
last_file_time = 0
consecutive_errors = 0
session_health_check_time = 0

# --- PDF & THUMBNAIL SETTINGS ---
PDF_PAGE_REMOVAL_ENABLED = True
SMART_THUMBNAIL_ENABLED = True
DEFAULT_THUMBNAIL_SKIP_SECONDS = 10

# --- MODE INFO ---
logger.warning("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
logger.warning("🔶 BALANCED MODE ENABLED")
logger.warning("⚡ Chunk: 2MB | Buffer: 6MB")
logger.warning("🎯 Speed: Good | Safety: Moderate")
logger.warning("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
