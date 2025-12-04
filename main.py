#!/usr/bin/env python3
"""
SAFE MODE BOT v3.0
512KB Chunks × 2 Queue = 1MB Buffer
Session Protection + Ban Prevention
"""

import asyncio
import os
import signal
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.network import connection
from telethon.errors import AuthKeyUnregisteredError, UserDeactivatedError
from aiohttp import web

import config
from handlers import register_handlers

# --- SAFE CLIENT SETUP (WITH SESSION PROTECTION) ---
user_client = TelegramClient(
    StringSession(config.STRING_SESSION), 
    config.API_ID, 
    config.API_HASH,
    connection=connection.ConnectionTcpFull,
    use_ipv6=False,
    connection_retries=config.MAX_RECONNECT_ATTEMPTS,  # Limited retries
    flood_sleep_threshold=config.FLOOD_SLEEP_THRESHOLD,  # Aggressive flood protection
    request_retries=config.REQUEST_RETRIES,  # Reduced retries
    auto_reconnect=True,
    retry_delay=5,  # Wait 5s between retries
    sequential_updates=True  # Process updates sequentially
)

bot_client = TelegramClient(
    'bot_session', 
    config.API_ID, 
    config.API_HASH,
    connection=connection.ConnectionTcpFull,
    use_ipv6=False,
    connection_retries=config.MAX_RECONNECT_ATTEMPTS,
    flood_sleep_threshold=config.FLOOD_SLEEP_THRESHOLD,
    request_retries=config.REQUEST_RETRIES,
    auto_reconnect=True,
    retry_delay=5
)

# --- SESSION HEALTH MONITOR ---
async def session_health_check():
    """Monitor session health and reconnect if needed"""
    while True:
        try:
            await asyncio.sleep(config.SESSION_SAVE_INTERVAL)
            
            if not user_client.is_connected():
                config.logger.warning("🔄 User client disconnected, reconnecting...")
                await user_client.connect()
            
            # Test connection with a lightweight call
            try:
                await user_client.get_me()
                config.logger.info("✅ Session health check: OK")
            except (AuthKeyUnregisteredError, UserDeactivatedError) as e:
                config.logger.error(f"🚨 SESSION REVOKED: {e}")
                config.logger.error("🔴 CRITICAL: Your Telegram account was banned/logged out!")
                config.logger.error("🛑 Stopping bot to prevent further issues...")
                
                # Stop all transfers
                config.is_running = False
                if config.current_task:
                    config.current_task.cancel()
                
                # Don't try to reconnect - session is dead
                break
            except Exception as e:
                config.logger.warning(f"⚠️ Health check failed: {e}")
        
        except Exception as e:
            config.logger.error(f"❌ Health monitor error: {e}")

# --- GRACEFUL SHUTDOWN HANDLER ---
async def shutdown(signal_received=None):
    """Gracefully shutdown the bot"""
    if signal_received:
        config.logger.info(f"🛑 Received shutdown signal: {signal_received}")
    
    config.logger.info("🔄 Shutting down gracefully...")
    
    # Stop all active transfers
    config.is_running = False
    if config.current_task:
        config.current_task.cancel()
    
    # Save sessions
    try:
        if user_client.is_connected():
            await user_client.disconnect()
        if bot_client.is_connected():
            await bot_client.disconnect()
        config.logger.info("✅ Sessions saved and closed")
    except Exception as e:
        config.logger.error(f"⚠️ Error during shutdown: {e}")

# --- WEB SERVER ---
async def handle(request):
    status = "🟢 RUNNING" if config.is_running else "🔴 IDLE"
    return web.Response(
        text=f"🔒 SAFE MODE v3.0 - Status: {status}\n"
             f"⚡ Chunk: 512KB × 2 = 1MB Buffer\n"
             f"🛡️ Ban Prevention: ACTIVE\n"
             f"📊 Active Sessions: {len(config.active_sessions)}"
    )

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', config.PORT)
    await site.start()
    config.logger.info(f"🌐 Web Server - Port {config.PORT}")

# --- MAIN ---
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    
    # Register shutdown handlers
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s)))
    
    config.logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    config.logger.info("🔒 SAFE MODE BOT v3.0 Starting...")
    config.logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    config.logger.info("⚡ Config: 512KB chunks × 2 queue = 1MB buffer")
    config.logger.info("🛡️ Features: Session protection + Ban prevention")
    config.logger.info("📝 Safety: File delays + Smart reconnect")
    config.logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    try:
        # Start clients with error handling
        config.logger.info("🔄 Connecting user client...")
        user_client.start()
        config.logger.info("✅ User client connected")
        
        config.logger.info("🔄 Connecting bot client...")
        bot_client.start(bot_token=config.BOT_TOKEN)
        config.logger.info("✅ Bot client connected")
        
        # Register all handlers
        register_handlers(user_client, bot_client)
        config.logger.info("✅ Handlers registered")
        
        # Start web server
        loop.create_task(start_web_server())
        
        # Start session health monitor
        loop.create_task(session_health_check())
        config.logger.info("✅ Session health monitor started")
        
        config.logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        config.logger.info("✅ SAFE MODE Active!")
        config.logger.info("🔒 Bot is ready for secure transfers!")
        config.logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        # Run bot
        bot_client.run_until_disconnected()
    
    except AuthKeyUnregisteredError:
        config.logger.error("🚨 AUTH KEY UNREGISTERED - Session invalid!")
        config.logger.error("💡 Generate new STRING_SESSION")
    
    except UserDeactivatedError:
        config.logger.error("🚨 USER DEACTIVATED - Account banned!")
        config.logger.error("💡 Use different Telegram account")
    
    except KeyboardInterrupt:
        config.logger.info("⚠️ Keyboard interrupt received")
        loop.run_until_complete(shutdown())
    
    except Exception as e:
        config.logger.error(f"💥 Critical startup error: {e}")
        loop.run_until_complete(shutdown())
    
    finally:
        config.logger.info("👋 Bot stopped")
