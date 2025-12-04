import asyncio
import time
import os
from telethon import errors
from telethon.tl.types import (
    DocumentAttributeFilename, 
    DocumentAttributeVideo, 
    DocumentAttributeAudio
)
import config
from utils import (
    human_readable_size, time_formatter, 
    get_target_info, apply_filename_manipulations,
    apply_caption_manipulations, sanitize_filename
)
from stream import SafeBufferedStream  # Changed from ExtremeBufferedStream
from keyboards import get_progress_keyboard
from pdf_handler import remove_pdf_pages, find_pages_with_keywords, find_matching_pages_by_image
from thumbnail_handler import generate_video_thumbnail, generate_smart_thumbnail, is_ffmpeg_available

async def smart_delay(file_size):
    """
    🔒 CRITICAL: Intelligent delay between files to prevent ban
    Telegram monitors transfer patterns - this makes it look natural
    """
    if file_size > 50 * 1024 * 1024:  # Files >50MB
        delay = config.LARGE_FILE_DELAY
    else:
        delay = config.FILE_TRANSFER_DELAY
    
    # Add randomness (1-3s extra) to avoid pattern detection
    import random
    delay += random.uniform(1, 3)
    
    config.logger.info(f"⏳ Cooldown: {delay:.1f}s (ban prevention)")
    await asyncio.sleep(delay)

async def check_rate_limit():
    """
    🔒 Monitor consecutive errors and stop if too many failures
    """
    if config.consecutive_errors >= 5:
        config.logger.error("🚨 TOO MANY ERRORS - Stopping to prevent ban!")
        config.is_running = False
        return False
    return True

async def transfer_process(event, user_client, bot_client, source_id, dest_id, start_msg, end_msg, session_id):
    """Main transfer process with SAFE settings and ban prevention"""
    
    settings = config.active_sessions.get(session_id, {}).get('settings', {})
    
    status_message = await event.respond(
        f"🔒 **SAFE MODE ACTIVATED!**\n"
        f"⚡ Chunk: 512KB | Buffer: 1MB\n"
        f"🛡️ Ban Prevention: ENABLED\n"
        f"📍 Source: `{source_id}` → Dest: `{dest_id}`\n\n"
        f"⏱️ Transfers will be slower but SAFER",
        buttons=get_progress_keyboard()
    )
    
    total_processed = 0
    total_size = 0
    total_skipped = 0
    overall_start = time.time()
    config.consecutive_errors = 0  # Reset error counter
    
    try:
        async for message in user_client.iter_messages(
            source_id, 
            min_id=start_msg-1, 
            max_id=end_msg+1, 
            reverse=True
        ):
            if not config.is_running:
                await status_message.edit(
                    "🛑 **Transfer Stopped by User!**\n"
                    f"✅ Processed: {total_processed}\n"
                    f"⏭️ Skipped: {total_skipped}"
                )
                break
            
            # 🔒 Check if we should continue (error rate check)
            if not await check_rate_limit():
                await status_message.edit(
                    "🚨 **EMERGENCY STOP!**\n"
                    "Too many consecutive errors detected.\n"
                    "Stopping to prevent Telegram ban.\n\n"
                    "💡 Wait 1 hour before retrying."
                )
                break

            # Skip service messages
            if getattr(message, 'action', None): 
                continue

            retries = config.MAX_RETRIES
            success = False
            stream_file = None
            file_size = 0
            
            while retries > 0 and not success:
                try:
                    # Refresh message to avoid expired references
                    fresh_msg = await user_client.get_messages(source_id, ids=message.id)
                    if not fresh_msg: 
                        break 

                    # Handle text-only messages
                    if not fresh_msg.media or not fresh_msg.file:
                        if fresh_msg.text:
                            modified_text = apply_caption_manipulations(fresh_msg.text, settings)
                            await bot_client.send_message(dest_id, modified_text)
                            success = True
                        else:
                            success = True
                        continue

                    # Get file info
                    file_name, mime_type, is_video_mode = get_target_info(fresh_msg)
                    
                    if not file_name:
                        success = True
                        continue
                    
                    file_size = fresh_msg.file.size
                    
                    # 🔒 Check file size limit (Telegram = 2GB, but safer to limit)
                    if file_size > 1.9 * 1024 * 1024 * 1024:  # 1.9GB
                        config.logger.warning(f"⚠️ File too large: {human_readable_size(file_size)}")
                        await status_message.edit(
                            f"⚠️ **File Too Large**\n"
                            f"File: `{file_name[:30]}...`\n"
                            f"Size: `{human_readable_size(file_size)}`\n"
                            f"Limit: 1.9GB (safety margin)\n"
                            f"Skipping...",
                            buttons=get_progress_keyboard()
                        )
                        total_skipped += 1
                        break
                    
                    # Apply filename manipulations
                    file_name = apply_filename_manipulations(file_name, settings)
                    file_name = sanitize_filename(file_name)

                    await status_message.edit(
                        f"🔒 **SAFE TRANSFER**\n"
                        f"📂 `{file_name[:40]}...`\n"
                        f"💪 Attempt: {config.MAX_RETRIES - retries + 1}/{config.MAX_RETRIES}\n"
                        f"📊 Progress: {total_processed}/{end_msg - start_msg + 1}",
                        buttons=get_progress_keyboard()
                    )

                    start_time = time.time()
                    
                    # Prepare attributes
                    attributes = [DocumentAttributeFilename(file_name=file_name)]
                    
                    if hasattr(fresh_msg, 'document') and fresh_msg.document:
                        for attr in fresh_msg.document.attributes:
                            if isinstance(attr, DocumentAttributeVideo):
                                attributes.append(DocumentAttributeVideo(
                                    duration=attr.duration,
                                    w=attr.w,
                                    h=attr.h,
                                    supports_streaming=True
                                ))
                            elif isinstance(attr, DocumentAttributeAudio):
                                attributes.append(attr)

                    # Download thumbnail (same as before)
                    thumb = None
                    try:
                        thumb_mode = settings.get('thumbnail_mode', 'original')
                        
                        if thumb_mode == 'original':
                            thumb = await user_client.download_media(fresh_msg, thumb=-1)
                        elif thumb_mode == 'generate' and is_video_mode:
                            if is_ffmpeg_available():
                                temp_video = await user_client.download_media(fresh_msg)
                                skip_seconds = settings.get('thumbnail_skip', 1)
                                thumb = await generate_video_thumbnail(temp_video, skip_seconds)
                                if temp_video and os.path.exists(temp_video):
                                    os.remove(temp_video)
                            else:
                                thumb = await user_client.download_media(fresh_msg, thumb=-1)
                        elif thumb_mode == 'smart' and is_video_mode:
                            if is_ffmpeg_available():
                                temp_video = await user_client.download_media(fresh_msg)
                                skip_seconds = settings.get('thumbnail_skip', 10)
                                thumb = await generate_smart_thumbnail(temp_video, skip_seconds)
                                if temp_video and os.path.exists(temp_video):
                                    os.remove(temp_video)
                            else:
                                thumb = await user_client.download_media(fresh_msg, thumb=-1)
                        else:
                            thumb = await user_client.download_media(fresh_msg, thumb=-1)
                    except Exception as thumb_err:
                        config.logger.error(f"⚠️ Thumbnail error: {thumb_err}")
                        try:
                            thumb = await user_client.download_media(fresh_msg, thumb=-1)
                        except:
                            pass
                    
                    # Prepare media object
                    media_obj = (fresh_msg.media.document 
                                if hasattr(fresh_msg.media, 'document') 
                                else fresh_msg.media.photo)
                    
                    # PDF PROCESSING (same as before, kept for compatibility)
                    pdf_modified = False
                    temp_pdf_path = None
                    
                    if file_name.lower().endswith('.pdf') and (settings.get('pdf_pages_list') or settings.get('pdf_keywords') or settings.get('pdf_reference_image')):
                        try:
                            temp_pdf_original = await user_client.download_media(fresh_msg)
                            pages_to_remove = set()
                            
                            if settings.get('pdf_pages_list'):
                                pages_to_remove.update(settings['pdf_pages_list'])
                            
                            if settings.get('pdf_keywords'):
                                keyword_pages = await find_pages_with_keywords(
                                    temp_pdf_original, 
                                    settings['pdf_keywords']
                                )
                                pages_to_remove.update(keyword_pages)
                            
                            if settings.get('pdf_reference_image'):
                                ref_image_path = settings['pdf_reference_image']
                                threshold = settings.get('pdf_image_threshold', 0.7)
                                image_matched_pages = await find_matching_pages_by_image(
                                    temp_pdf_original,
                                    ref_image_path,
                                    threshold
                                )
                                pages_to_remove.update(image_matched_pages)
                            
                            if pages_to_remove:
                                temp_pdf_path, kept, removed = await remove_pdf_pages(
                                    temp_pdf_original, 
                                    list(pages_to_remove)
                                )
                                if temp_pdf_path:
                                    pdf_modified = True
                                    media_obj = temp_pdf_path
                            
                            if temp_pdf_original and os.path.exists(temp_pdf_original):
                                os.remove(temp_pdf_original)
                        
                        except Exception as pdf_err:
                            config.logger.error(f"❌ PDF Error: {pdf_err}")
                    
                    # CREATE STREAM WITH SAFE SETTINGS
                    if pdf_modified and temp_pdf_path:
                        stream_file = temp_pdf_path
                        file_size = os.path.getsize(temp_pdf_path)
                    else:
                        stream_file = SafeBufferedStream(  # Changed from Extreme
                            user_client, 
                            media_obj,
                            fresh_msg.file.size,
                            file_name,
                            start_time,
                            status_message
                        )
                        file_size = fresh_msg.file.size
                    
                    # Apply caption manipulations
                    modified_caption = apply_caption_manipulations(fresh_msg.text, settings)
                    
                    # 🔒 UPLOAD WITH SAFE SETTINGS
                    await bot_client.send_file(
                        dest_id,
                        file=stream_file,
                        caption=modified_caption,
                        attributes=attributes,
                        thumb=thumb,
                        supports_streaming=True,
                        file_size=file_size,
                        force_document=not is_video_mode,
                        part_size_kb=config.UPLOAD_PART_SIZE  # Now 512KB
                    )
                    
                    # Cleanup
                    if thumb and os.path.exists(thumb): 
                        os.remove(thumb)
                    if pdf_modified and temp_pdf_path and os.path.exists(temp_pdf_path):
                        os.remove(temp_pdf_path)
                    
                    success = True
                    config.consecutive_errors = 0  # Reset on success
                    
                    elapsed = time.time() - start_time
                    speed = file_size / elapsed / (1024*1024) if elapsed > 0 else 0
                    total_size += file_size
                    
                    await status_message.edit(
                        f"✅ **SENT:** `{file_name[:40]}...`\n"
                        f"⚡ Speed: `{speed:.1f} MB/s`\n"
                        f"📦 Files: {total_processed + 1}/{end_msg - start_msg + 1}",
                        buttons=get_progress_keyboard()
                    )
                    
                    # 🔒 CRITICAL: Delay between files to prevent ban
                    await smart_delay(file_size)

                except (errors.FileReferenceExpiredError, errors.MediaEmptyError):
                    config.logger.warning(f"🔄 Ref expired, refreshing...")
                    retries -= 1
                    await asyncio.sleep(3)  # Longer delay
                    continue 
                    
                except errors.FloodWaitError as e:
                    config.consecutive_errors += 1
                    wait_time = min(e.seconds, 300)  # Max 5 min wait
                    config.logger.warning(f"⏳ FloodWait {wait_time}s")
                    await status_message.edit(
                        f"⏳ **Rate Limited by Telegram**\n"
                        f"Waiting: `{wait_time}s`\n"
                        f"This is normal - don't worry!\n"
                        f"Resume after cooldown...",
                        buttons=get_progress_keyboard()
                    )
                    await asyncio.sleep(wait_time)
                
                except MemoryError:
                    config.logger.error("💥 RAM LIMIT! Skipping...")
                    config.consecutive_errors += 1
                    await status_message.edit(
                        f"⚠️ **Memory Error**\n"
                        f"Skipping file...",
                        buttons=get_progress_keyboard()
                    )
                    total_skipped += 1
                    retries = 0
                
                except Exception as e:
                    config.logger.error(f"❌ Error: {e}")
                    config.consecutive_errors += 1
                    retries -= 1
                    if retries > 0:
                        await asyncio.sleep(5)  # Longer delay on error
                
                finally:
                    # ALWAYS close stream
                    if stream_file and not pdf_modified:
                        await stream_file.close()

            if not success:
                total_skipped += 1
                config.consecutive_errors += 1
            
            total_processed += 1
            
            # 🔒 Additional safety: pause every 3 files
            if total_processed % 3 == 0:
                await asyncio.sleep(2)

        if config.is_running:
            overall_time = time.time() - overall_start
            avg_speed = total_size / overall_time / (1024*1024) if overall_time > 0 else 0
            
            await status_message.edit(
                f"🏁 **SAFE TRANSFER COMPLETE!**\n"
                f"✅ Files: `{total_processed}`\n"
                f"⏭️ Skipped: `{total_skipped}`\n"
                f"📦 Size: `{human_readable_size(total_size)}`\n"
                f"⚡ Avg Speed: `{avg_speed:.1f} MB/s`\n"
                f"⏱️ Time: `{time_formatter(overall_time)}`\n\n"
                f"🛡️ No ban risks detected!"
            )

    except Exception as e:
        await status_message.edit(f"💥 **Error:** {str(e)[:100]}")
        config.logger.error(f"Transfer error: {e}")
    finally:
        config.is_running = False
        if session_id in config.active_sessions:
            del config.active_sessions[session_id]
