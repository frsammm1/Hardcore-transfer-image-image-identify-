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
from stream import ExtremeBufferedStream
from keyboards import get_progress_keyboard
from pdf_handler import remove_pdf_pages, find_pages_with_keywords, find_matching_pages_by_image
from thumbnail_handler import generate_video_thumbnail, generate_smart_thumbnail, is_ffmpeg_available

async def transfer_process(event, user_client, bot_client, source_id, dest_id, start_msg, end_msg, session_id):
    """Main transfer process with all features"""
    
    settings = config.active_sessions.get(session_id, {}).get('settings', {})
    
    status_message = await event.respond(
        f"🚀 **EXTREME MODE ACTIVATED!**\n"
        f"⚡ Chunk: 32MB | Buffer: 160MB (5×)\n"
        f"🔥 Max Speed Unlocked!\n"
        f"📍 Source: `{source_id}` → Dest: `{dest_id}`",
        buttons=get_progress_keyboard()
    )
    
    total_processed = 0
    total_size = 0
    total_skipped = 0
    overall_start = time.time()
    
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

            # Skip service messages
            if getattr(message, 'action', None): 
                continue

            retries = config.MAX_RETRIES
            success = False
            stream_file = None
            
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

                    # Get file info with smart format detection
                    file_name, mime_type, is_video_mode = get_target_info(fresh_msg)
                    
                    if not file_name:
                        success = True
                        continue
                    
                    # Apply filename manipulations
                    file_name = apply_filename_manipulations(file_name, settings)
                    file_name = sanitize_filename(file_name)

                    await status_message.edit(
                        f"🚀 **EXTREME TRANSFER**\n"
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

                    # Download thumbnail
                    thumb = None
                    try:
                        thumb_mode = settings.get('thumbnail_mode', 'original')
                        
                        if thumb_mode == 'original':
                            # Use original thumbnail
                            thumb = await user_client.download_media(fresh_msg, thumb=-1)
                        
                        elif thumb_mode == 'generate' and is_video_mode:
                            # Generate thumbnail from specific time
                            if is_ffmpeg_available():
                                temp_video = await user_client.download_media(fresh_msg)
                                skip_seconds = settings.get('thumbnail_skip', 1)
                                thumb = await generate_video_thumbnail(temp_video, skip_seconds)
                                if temp_video and os.path.exists(temp_video):
                                    os.remove(temp_video)
                            else:
                                config.logger.warning("⚠️ FFmpeg not available, using original thumbnail")
                                thumb = await user_client.download_media(fresh_msg, thumb=-1)
                        
                        elif thumb_mode == 'smart' and is_video_mode:
                            # Smart thumbnail generation
                            if is_ffmpeg_available():
                                temp_video = await user_client.download_media(fresh_msg)
                                skip_seconds = settings.get('thumbnail_skip', 10)
                                thumb = await generate_smart_thumbnail(temp_video, skip_seconds)
                                if temp_video and os.path.exists(temp_video):
                                    os.remove(temp_video)
                            else:
                                config.logger.warning("⚠️ FFmpeg not available, using original thumbnail")
                                thumb = await user_client.download_media(fresh_msg, thumb=-1)
                        
                        else:
                            # Fallback to original
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
                    
                    # PDF PROCESSING (IMPROVED) - Replace existing PDF section with this
                    pdf_modified = False
                    temp_pdf_path = None
                    
                    if file_name.lower().endswith('.pdf') and (settings.get('pdf_pages_list') or settings.get('pdf_keywords') or settings.get('pdf_reference_image')):
                        try:
                            config.logger.info(f"📄 Processing PDF: {file_name}")
                            
                            # Show processing message
                            await status_message.edit(
                                f"📄 **PDF Analysis Started**\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"File: `{file_name[:30]}...`\n\n"
                                f"⏳ Downloading PDF...",
                                buttons=get_progress_keyboard()
                            )
                            
                            # Download PDF
                            temp_pdf_original = await user_client.download_media(fresh_msg)
                            
                            await status_message.edit(
                                f"📄 **PDF Analysis**\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"File: `{file_name[:30]}...`\n\n"
                                f"✅ Downloaded\n"
                                f"🔍 Analyzing pages...",
                                buttons=get_progress_keyboard()
                            )
                            
                            pages_to_remove = set()
                            
                            # METHOD 1: Remove by page numbers
                            if settings.get('pdf_pages_list'):
                                pages_to_remove.update(settings['pdf_pages_list'])
                                config.logger.info(f"🔢 Pages by number: {sorted(pages_to_remove)}")
                            
                            # METHOD 2: Remove by keywords
                            if settings.get('pdf_keywords'):
                                await status_message.edit(
                                    f"📄 **PDF Analysis**\n"
                                    f"━━━━━━━━━━━━━━━━━━━━\n"
                                    f"File: `{file_name[:30]}...`\n\n"
                                    f"✅ Downloaded\n"
                                    f"🔍 Searching keywords...",
                                    buttons=get_progress_keyboard()
                                )
                                
                                keyword_pages = await find_pages_with_keywords(
                                    temp_pdf_original, 
                                    settings['pdf_keywords']
                                )
                                pages_to_remove.update(keyword_pages)
                                config.logger.info(f"🔍 Pages by keywords: {keyword_pages}")
                            
                            # METHOD 3: Remove by image matching (IMPROVED)
                            if settings.get('pdf_reference_image'):
                                ref_image_path = settings['pdf_reference_image']
                                threshold = settings.get('pdf_image_threshold', 0.7)
                                
                                await status_message.edit(
                                    f"📄 **PDF Image Matching**\n"
                                    f"━━━━━━━━━━━━━━━━━━━━\n"
                                    f"File: `{file_name[:30]}...`\n\n"
                                    f"✅ Downloaded\n"
                                    f"📸 Analyzing screenshot...\n"
                                    f"🎯 Threshold: {int(threshold*100)}%\n\n"
                                    f"⏳ This may take 30-60 seconds...",
                                    buttons=get_progress_keyboard()
                                )
                                
                                config.logger.info(f"📸 Starting image-based matching...")
                                config.logger.info(f"   Reference: {ref_image_path}")
                                config.logger.info(f"   Threshold: {threshold}")
                                
                                image_matched_pages = await find_matching_pages_by_image(
                                    temp_pdf_original,
                                    ref_image_path,
                                    threshold
                                )
                                
                                pages_to_remove.update(image_matched_pages)
                                
                                if image_matched_pages:
                                    config.logger.info(f"✅ Image matches: {image_matched_pages}")
                                    await status_message.edit(
                                        f"📄 **PDF Image Matching**\n"
                                        f"━━━━━━━━━━━━━━━━━━━━\n"
                                        f"File: `{file_name[:30]}...`\n\n"
                                        f"✅ Analysis complete!\n"
                                        f"🎯 Found {len(image_matched_pages)} matching page(s)\n"
                                        f"📄 Pages: {image_matched_pages}\n\n"
                                        f"⏳ Removing pages...",
                                        buttons=get_progress_keyboard()
                                    )
                                else:
                                    config.logger.warning(f"⚠️ No image matches found")
                                    await status_message.edit(
                                        f"📄 **PDF Image Matching**\n"
                                        f"━━━━━━━━━━━━━━━━━━━━\n"
                                        f"File: `{file_name[:30]}...`\n\n"
                                        f"⚠️ No matching pages found\n"
                                        f"💡 Screenshot may not match any page\n\n"
                                        f"⏭️ Continuing with other methods...",
                                        buttons=get_progress_keyboard()
                                    )
                                    await asyncio.sleep(3)
                            
                            # Process PDF if pages to remove
                            if pages_to_remove:
                                await status_message.edit(
                                    f"📄 **PDF Modification**\n"
                                    f"━━━━━━━━━━━━━━━━━━━━\n"
                                    f"File: `{file_name[:30]}...`\n\n"
                                    f"🗑️ Removing {len(pages_to_remove)} page(s)\n"
                                    f"Pages: {sorted(list(pages_to_remove))[:10]}\n\n"
                                    f"⏳ Processing...",
                                    buttons=get_progress_keyboard()
                                )
                                
                                temp_pdf_path, kept, removed = await remove_pdf_pages(
                                    temp_pdf_original, 
                                    list(pages_to_remove)
                                )
                                
                                if temp_pdf_path:
                                    pdf_modified = True
                                    config.logger.info(f"✅ PDF Modified: Kept {kept}, Removed {removed}")
                                    
                                    # Use modified PDF
                                    media_obj = temp_pdf_path
                                    
                                    await status_message.edit(
                                        f"✅ **PDF Modified Successfully!**\n"
                                        f"━━━━━━━━━━━━━━━━━━━━\n"
                                        f"File: `{file_name[:30]}...`\n\n"
                                        f"📊 Original pages: {kept + removed}\n"
                                        f"✅ Kept: {kept} pages\n"
                                        f"🗑️ Removed: {removed} pages\n\n"
                                        f"⏳ Uploading modified PDF...",
                                        buttons=get_progress_keyboard()
                                    )
                                    await asyncio.sleep(2)
                                else:
                                    config.logger.error(f"❌ PDF modification failed")
                                    await status_message.edit(
                                        f"⚠️ **PDF Modification Failed**\n"
                                        f"Using original PDF...",
                                        buttons=get_progress_keyboard()
                                    )
                                    await asyncio.sleep(2)
                            else:
                                config.logger.warning(f"⚠️ No pages to remove")
                                await status_message.edit(
                                    f"⚠️ **No Pages to Remove**\n"
                                    f"Using original PDF...",
                                    buttons=get_progress_keyboard()
                                )
                                await asyncio.sleep(2)
                            
                            # Cleanup original download
                            if temp_pdf_original and os.path.exists(temp_pdf_original):
                                os.remove(temp_pdf_original)
                        
                        except Exception as pdf_err:
                            config.logger.error(f"❌ PDF Processing Error: {pdf_err}")
                            await status_message.edit(
                                f"❌ **PDF Error**\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"Using original PDF...\n\n"
                                f"Error: `{str(pdf_err)[:80]}`\n\n"
                                f"💡 Check logs for details",
                                buttons=get_progress_keyboard()
                            )
                            await asyncio.sleep(3)
                    
                    # CREATE STREAM (PDF or regular file)
                    # CREATE STREAM (PDF or regular file)
                    if pdf_modified and temp_pdf_path:
                        # Upload modified PDF directly
                        stream_file = temp_pdf_path
                        file_size = os.path.getsize(temp_pdf_path)
                    else:
                        # Create stream for regular files
                        stream_file = ExtremeBufferedStream(
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
                    
                    # UPLOAD WITH EXTREME SETTINGS
                    await bot_client.send_file(
                        dest_id,
                        file=stream_file,
                        caption=modified_caption,
                        attributes=attributes,
                        thumb=thumb,
                        supports_streaming=True,
                        file_size=file_size,
                        force_document=not is_video_mode,
                        part_size_kb=config.UPLOAD_PART_SIZE
                    )
                    
                    # Cleanup
                    if thumb and os.path.exists(thumb): 
                        os.remove(thumb)
                    if pdf_modified and temp_pdf_path and os.path.exists(temp_pdf_path):
                        os.remove(temp_pdf_path)
                    
                    success = True
                    elapsed = time.time() - start_time
                    speed = file_size / elapsed / (1024*1024) if elapsed > 0 else 0
                    total_size += file_size
                    
                    await status_message.edit(
                        f"✅ **SENT:** `{file_name[:40]}...`\n"
                        f"⚡ Speed: `{speed:.1f} MB/s`\n"
                        f"📦 Files: {total_processed + 1}/{end_msg - start_msg + 1}",
                        buttons=get_progress_keyboard()
                    )

                except (errors.FileReferenceExpiredError, errors.MediaEmptyError):
                    config.logger.warning(f"🔄 Ref expired on {message.id}, refreshing...")
                    retries -= 1
                    await asyncio.sleep(2)
                    continue 
                    
                except errors.FloodWaitError as e:
                    config.logger.warning(f"⏳ FloodWait {e.seconds}s")
                    await status_message.edit(
                        f"⏳ **Cooling Down...**\n"
                        f"Waiting: `{e.seconds}s`\n"
                        f"Resume after cooldown...",
                        buttons=get_progress_keyboard()
                    )
                    await asyncio.sleep(e.seconds)
                
                except MemoryError:
                    config.logger.error("💥 RAM LIMIT HIT! Skipping file...")
                    await status_message.edit(
                        f"⚠️ **RAM Overflow!**\n"
                        f"File too large, skipping...\n"
                        f"File: `{file_name[:40]}...`",
                        buttons=get_progress_keyboard()
                    )
                    total_skipped += 1
                    retries = 0
                
                except Exception as e:
                    config.logger.error(f"❌ Failed {message.id}: {e}")
                    retries -= 1
                    if retries > 0:
                        await asyncio.sleep(3)
                
                finally:
                    # CRITICAL: Always close stream
                    if stream_file and not pdf_modified:
                        await stream_file.close()
                    elif pdf_modified and temp_pdf_path and os.path.exists(temp_pdf_path):
                        try:
                            os.remove(temp_pdf_path)
                        except:
                            pass

            if not success:
                total_skipped += 1
                try: 
                    await bot_client.send_message(
                        event.chat_id, 
                        f"❌ **FAILED:** Message ID `{message.id}` after {config.MAX_RETRIES} attempts."
                    )
                except: 
                    pass
            
            total_processed += 1
            
            # Memory management: pause every 5 files
            if total_processed % 5 == 0:
                await asyncio.sleep(2)

        if config.is_running:
            overall_time = time.time() - overall_start
            avg_speed = total_size / overall_time / (1024*1024) if overall_time > 0 else 0
            
            await status_message.edit(
                f"🏁 **EXTREME MODE COMPLETE!**\n"
                f"✅ Files: `{total_processed}`\n"
                f"⏭️ Skipped: `{total_skipped}`\n"
                f"📦 Size: `{human_readable_size(total_size)}`\n"
                f"⚡ Avg Speed: `{avg_speed:.1f} MB/s`\n"
                f"⏱️ Time: `{time_formatter(overall_time)}`"
            )

    except Exception as e:
        await status_message.edit(f"💥 **Critical Error:** {str(e)[:100]}")
        config.logger.error(f"Transfer crashed: {e}")
    finally:
        config.is_running = False
        if session_id in config.active_sessions:
            del config.active_sessions[session_id]
