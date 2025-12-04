import asyncio
import uuid
import os
from telethon import events
import config
from keyboards import (
    get_settings_keyboard, get_confirm_keyboard,
    get_skip_keyboard, get_clone_info_keyboard,
    get_pdf_remove_options_keyboard, get_pdf_add_options_keyboard,
    get_pdf_thumbnail_options_keyboard, get_thumbnail_options_keyboard
)
from transfer import transfer_process

def register_handlers(user_client, bot_client):
    """Register all bot handlers with NEW PDF features"""
    
    @bot_client.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        await event.respond(
            "🚀 **EXTREME MODE BOT v3.0**\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ Chunks: **{config.CHUNK_SIZE // (1024*1024)}MB** × {config.QUEUE_SIZE} Queue\n"
            f"💾 Buffer: **{(config.CHUNK_SIZE * config.QUEUE_SIZE) // (1024*1024)}MB**\n"
            f"🔥 Upload Parts: **{config.UPLOAD_PART_SIZE // 1024}MB**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "**Features:**\n"
            "✅ All file types support\n"
            "✅ Video → MP4 conversion\n"
            "✅ Filename manipulation\n"
            "✅ Caption manipulation\n"
            "✅ PDF page removal (smart)\n"
            "🆕 PDF page insertion\n"
            "🆕 PDF thumbnail control\n"
            "✅ Smart video thumbnails\n\n"
            "**Commands:**\n"
            "`/clone` - Start cloning\n"
            "`/stats` - Bot statistics\n"
            "`/help` - Detailed guide\n\n"
            "⚠️ **Warning:** High RAM usage!",
            buttons=get_clone_info_keyboard()
        )
    
    @bot_client.on(events.NewMessage(pattern='/help'))
    async def help_handler(event):
        await event.respond(
            "📚 **EXTREME MODE - User Guide v3.0**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "**Step 1:** Use `/clone` command\n"
            "Format: `/clone SOURCE_ID DEST_ID`\n\n"
            "**Step 2:** Configure Settings\n"
            "• Filename/Caption manipulation\n"
            "• PDF page removal\n"
            "🆕 PDF page insertion\n"
            "🆕 PDF thumbnail control\n"
            "• Video thumbnail generation\n\n"
            "**Step 3:** Send Message Range\n"
            "`https://t.me/c/xxx/10 - https://t.me/c/xxx/20`\n\n"
            "**🆕 NEW PDF Features:**\n"
            "📄 Remove pages (numbers/keywords/image)\n"
            "➕ Add custom image as page\n"
            "🖼️ Remove/replace PDF thumbnail\n"
            "📍 Insert at start/end/custom position\n\n"
            "**Tips:**\n"
            "• Use channel IDs (start with -100)\n"
            "• Ensure bot is admin in destination\n"
            "• Monitor RAM during large transfers"
        )
    
    @bot_client.on(events.NewMessage(pattern='/clone'))
    async def clone_init(event):
        if config.is_running: 
            return await event.respond(
                "⚠️ **Already running a task!**\n"
                "Use `/stop` to cancel current transfer."
            )
        try:
            args = event.text.split()
            if len(args) < 3:
                raise ValueError("Invalid arguments")
            
            source_id = int(args[1])
            dest_id = int(args[2])
            
            session_id = str(uuid.uuid4())
            config.active_sessions[session_id] = {
                'source': source_id,
                'dest': dest_id,
                'settings': {},
                'chat_id': event.chat_id,
                'step': 'settings'
            }
            
            await event.respond(
                f"✅ **Clone Configuration Started**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📥 Source: `{source_id}`\n"
                f"📤 Destination: `{dest_id}`\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"**Configure your transfer settings:**\n"
                f"🆕 NEW: PDF page insertion & thumbnail control!\n\n"
                f"Session ID: `{session_id[:8]}...`",
                buttons=get_settings_keyboard(session_id)
            )
            
        except Exception as e:
            await event.respond(
                "❌ **Invalid Command Format**\n\n"
                "**Usage:**\n"
                "`/clone SOURCE_ID DEST_ID`\n\n"
                "**Example:**\n"
                "`/clone -1001234567890 -1009876543210`"
            )
    
    @bot_client.on(events.CallbackQuery(pattern=b'clone_help'))
    async def clone_help_callback(event):
        await event.answer()
        await event.respond(
            "📖 **How to Use Clone Command**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "1️⃣ Get Source & Destination IDs\n"
            "2️⃣ Run: `/clone -1001234 -1009876`\n"
            "3️⃣ Configure settings\n"
            "   🆕 NEW PDF features available!\n"
            "4️⃣ Send message range\n\n"
            "✅ Transfer starts automatically!"
        )
    
    @bot_client.on(events.CallbackQuery(pattern=b'bot_stats'))
    async def stats_callback(event):
        await event.answer()
        await event.respond(
            f"📊 **EXTREME MODE v3.0 Stats**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ Chunk: **{config.CHUNK_SIZE // (1024*1024)}MB**\n"
            f"💾 Buffer: **{(config.CHUNK_SIZE * config.QUEUE_SIZE) // (1024*1024)}MB**\n"
            f"📤 Upload: **{config.UPLOAD_PART_SIZE // 1024}MB parts**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🚀 Status: **{'🟢 Running' if config.is_running else '🔴 Idle'}**\n"
            f"📊 Sessions: **{len(config.active_sessions)}**\n\n"
            f"🆕 **NEW Features:**\n"
            f"• PDF page insertion\n"
            f"• PDF thumbnail control"
        )
    
    # Continue in Part 2...
    # ... continued from Part 1
    
    # Existing handlers (fname, fcap, xcap) remain same...
    @bot_client.on(events.CallbackQuery(pattern=r'set_fname_(.+)'))
    async def set_filename_callback(event):
        session_id = event.data.decode().split('_')[2]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        config.active_sessions[session_id]['step'] = 'fname_find'
        await event.edit(
            "📝 **Filename Modification**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Enter text to **FIND** in filenames:",
            buttons=get_skip_keyboard(session_id)
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'set_fcap_(.+)'))
    async def set_caption_find_callback(event):
        session_id = event.data.decode().split('_')[2]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        config.active_sessions[session_id]['step'] = 'cap_find'
        await event.edit(
            "💬 **Caption Modification**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Enter text to **FIND** in captions:",
            buttons=get_skip_keyboard(session_id)
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'set_xcap_(.+)'))
    async def set_extra_caption_callback(event):
        session_id = event.data.decode().split('_')[2]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        config.active_sessions[session_id]['step'] = 'extra_cap'
        await event.edit(
            "➕ **Extra Caption**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Enter text to **ADD** at end:",
            buttons=get_skip_keyboard(session_id)
        )
    
    # PDF REMOVE handlers (existing)
    @bot_client.on(events.CallbackQuery(pattern=r'set_pdf_remove_(.+)'))
    async def set_pdf_remove_callback(event):
        session_id = event.data.decode().split('_')[3]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        await event.edit(
            "📄 **PDF Page Removal**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Choose removal method:",
            buttons=get_pdf_remove_options_keyboard(session_id)
        )
    
    # 🆕 PDF ADD handlers
    @bot_client.on(events.CallbackQuery(pattern=r'set_pdf_add_(.+)'))
    async def set_pdf_add_callback(event):
        session_id = event.data.decode().split('_')[3]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        await event.edit(
            "➕ **Add Custom Page to PDF**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎨 Insert your own image as a PDF page!\n\n"
            "**Choose insertion position:**",
            buttons=get_pdf_add_options_keyboard(session_id)
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'pdf_add_start_(.+)'))
    async def pdf_add_start_callback(event):
        session_id = event.data.decode().split('_')[3]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        config.active_sessions[session_id]['step'] = 'pdf_add_image'
        config.active_sessions[session_id]['settings']['pdf_add_position'] = 'start'
        
        await event.edit(
            "➕ **Add Page at START**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📤 **Send your image now:**\n\n"
            "**Supported formats:**\n"
            "• JPG, PNG, WEBP\n"
            "• Any image format\n\n"
            "**Tips:**\n"
            "• Use high quality images\n"
            "• Image will auto-fit to page\n"
            "• Portrait recommended for docs",
            buttons=get_skip_keyboard(session_id)
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'pdf_add_end_(.+)'))
    async def pdf_add_end_callback(event):
        session_id = event.data.decode().split('_')[3]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        config.active_sessions[session_id]['step'] = 'pdf_add_image'
        config.active_sessions[session_id]['settings']['pdf_add_position'] = 'end'
        
        await event.edit(
            "➕ **Add Page at END**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📤 **Send your image now:**\n\n"
            "Page will be added at the end of PDF.",
            buttons=get_skip_keyboard(session_id)
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'pdf_add_custom_(.+)'))
    async def pdf_add_custom_callback(event):
        session_id = event.data.decode().split('_')[3]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        config.active_sessions[session_id]['step'] = 'pdf_add_position'
        
        await event.edit(
            "📍 **Custom Position**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Enter page number where to insert:\n\n"
            "**Examples:**\n"
            "• `1` - After first page\n"
            "• `5` - After fifth page\n"
            "• `10` - After tenth page\n\n"
            "Page will be inserted at this position.",
            buttons=get_skip_keyboard(session_id)
        )
    
    # 🆕 PDF THUMBNAIL handlers
    @bot_client.on(events.CallbackQuery(pattern=r'set_pdf_thumb_(.+)'))
    async def set_pdf_thumb_callback(event):
        session_id = event.data.decode().split('_')[3]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        await event.edit(
            "🖼️ **PDF Thumbnail Control**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎨 Control PDF thumbnail visibility!\n\n"
            "**Options:**\n"
            "📌 Keep - Use original thumbnail\n"
            "🗑️ Remove - Delete thumbnail completely\n"
            "🖼️ Custom - Add your own thumbnail",
            buttons=get_pdf_thumbnail_options_keyboard(session_id)
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'pdf_thumb_keep_(.+)'))
    async def pdf_thumb_keep_callback(event):
        session_id = event.data.decode().split('_')[3]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        config.active_sessions[session_id]['settings']['pdf_thumbnail_action'] = 'keep'
        await event.answer("📌 Keeping original thumbnail", alert=False)
        await event.edit(
            "✅ **Thumbnail: Keep Original**\n\n"
            "PDF thumbnails will remain unchanged.",
            buttons=get_settings_keyboard(session_id)
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'pdf_thumb_remove_(.+)'))
    async def pdf_thumb_remove_callback(event):
        session_id = event.data.decode().split('_')[3]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        config.active_sessions[session_id]['settings']['pdf_thumbnail_action'] = 'remove'
        await event.answer("🗑️ Will remove thumbnails", alert=False)
        await event.edit(
            "✅ **Thumbnail: Remove**\n\n"
            "📄 All PDF thumbnails will be removed.\n"
            "📱 PDFs will appear with generic icon.",
            buttons=get_settings_keyboard(session_id)
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'pdf_thumb_custom_(.+)'))
    async def pdf_thumb_custom_callback(event):
        session_id = event.data.decode().split('_')[3]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        config.active_sessions[session_id]['step'] = 'pdf_custom_thumbnail'
        
        await event.edit(
            "🖼️ **Custom PDF Thumbnail**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📤 **Send your thumbnail image:**\n\n"
            "**Recommended:**\n"
            "• 320x320 pixels or larger\n"
            "• JPG/PNG format\n"
            "• Represents your PDF content\n\n"
            "This thumbnail will appear for all PDFs.",
            buttons=get_skip_keyboard(session_id)
        )
    
    # Video thumbnail handlers (existing)
    @bot_client.on(events.CallbackQuery(pattern=r'set_thumb_(.+)'))
    async def set_thumb_callback(event):
        session_id = event.data.decode().split('_')[2]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        await event.edit(
            "🎬 **Video Thumbnail Options**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Choose thumbnail method for videos:",
            buttons=get_thumbnail_options_keyboard(session_id)
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'thumb_original_(.+)'))
    async def thumb_original_callback(event):
        session_id = event.data.decode().split('_')[2]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        config.active_sessions[session_id]['settings']['thumbnail_mode'] = 'original'
        await event.answer("📌 Using original thumbnails", alert=False)
        await event.edit(
            "✅ **Thumbnail: Original**\n\n"
            "Will use existing video thumbnails.",
            buttons=get_settings_keyboard(session_id)
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'thumb_gen1_(.+)'))
    async def thumb_gen1_callback(event):
        session_id = event.data.decode().split('_')[2]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        config.active_sessions[session_id]['settings']['thumbnail_mode'] = 'generate'
        config.active_sessions[session_id]['settings']['thumbnail_skip'] = 1
        await event.answer("⚡ Generating from 1 second", alert=False)
        await event.edit(
            "✅ **Thumbnail: Generate (1s)**",
            buttons=get_settings_keyboard(session_id)
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'thumb_smart_(.+)'))
    async def thumb_smart_callback(event):
        session_id = event.data.decode().split('_')[2]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        config.active_sessions[session_id]['settings']['thumbnail_mode'] = 'smart'
        config.active_sessions[session_id]['settings']['thumbnail_skip'] = 10
        await event.answer("🎯 Smart thumbnail enabled", alert=False)
        await event.edit(
            "✅ **Thumbnail: Smart (skip 10s)**",
            buttons=get_settings_keyboard(session_id)
        )
    
    # Control handlers (skip, confirm, etc.) - Keep existing...
    @bot_client.on(events.CallbackQuery(pattern=r'skip_(.+)'))
    async def skip_callback(event):
        session_id = event.data.decode().split('_')[1]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        config.active_sessions[session_id]['step'] = 'settings'
        await event.answer("⏭️ Skipped!", alert=False)
        await event.edit(
            "✅ **Settings Menu**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Configure your transfer:",
            buttons=get_settings_keyboard(session_id)
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'confirm_(.+)'))
    async def confirm_callback(event):
        session_id = event.data.decode().split('_')[1]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        settings = config.active_sessions[session_id]['settings']
        settings_text, keyboard = get_confirm_keyboard(session_id, settings)
        
        await event.edit(
            f"🔍 **Review Settings**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{settings_text}"
            f"Ready to proceed?",
            buttons=keyboard
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'back_(.+)'))
    async def back_callback(event):
        session_id = event.data.decode().split('_')[1]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        await event.edit(
            "✅ **Settings Menu**",
            buttons=get_settings_keyboard(session_id)
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'clear_(.+)'))
    async def clear_callback(event):
        session_id = event.data.decode().split('_')[1]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        config.active_sessions[session_id]['settings'] = {}
        await event.answer("🗑️ All settings cleared!", alert=True)
        await event.edit(
            "✅ **Settings Cleared**",
            buttons=get_settings_keyboard(session_id)
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'start_(.+)'))
    async def start_transfer_callback(event):
        session_id = event.data.decode().split('_')[1]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        config.active_sessions[session_id]['step'] = 'range'
        await event.edit(
            "📍 **Send Message Range**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Send two Telegram message links:\n"
            "`https://t.me/c/xxx/10 - https://t.me/c/xxx/20`"
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'cancel_(.+)'))
    async def cancel_callback(event):
        session_id = event.data.decode().split('_')[1]
        if session_id in config.active_sessions:
            del config.active_sessions[session_id]
        await event.answer("❌ Cancelled!", alert=True)
        await event.edit("❌ **Transfer Cancelled**")
    
    @bot_client.on(events.CallbackQuery(pattern=b'stop_transfer'))
    async def stop_transfer_callback(event):
        config.is_running = False
        if config.current_task:
            config.current_task.cancel()
        await event.answer("🛑 Stopping transfer...", alert=True)
    
    # Continue with message_handler in next part...
    config.logger.info("✅ All handlers registered with NEW PDF features!")
    # ... continued from Part 2
    
    @bot_client.on(events.NewMessage())
    async def message_handler(event):
        """Handle text messages and images for PDF customization"""
        
        # Find active session
        session_id = None
        for sid, data in config.active_sessions.items():
            if data['chat_id'] == event.chat_id:
                session_id = sid
                break
        
        if not session_id:
            return
        
        session = config.active_sessions[session_id]
        step = session.get('step')
        
        # Existing handlers (fname, cap, etc.)
        if step == 'fname_find':
            session['settings']['find_name'] = event.text
            session['step'] = 'fname_replace'
            await event.respond(
                "✅ **Find text saved!**\n\n"
                "Now enter text to **REPLACE** with:",
                buttons=get_skip_keyboard(session_id)
            )
        
        elif step == 'fname_replace':
            session['settings']['replace_name'] = event.text
            session['step'] = 'settings'
            await event.respond(
                "✅ **Filename modification set!**\n\n"
                f"Find: `{session['settings']['find_name']}`\n"
                f"Replace: `{event.text}`",
                buttons=get_settings_keyboard(session_id)
            )
        
        elif step == 'cap_find':
            session['settings']['find_cap'] = event.text
            session['step'] = 'cap_replace'
            await event.respond(
                "✅ **Find text saved!**\n\n"
                "Now enter text to **REPLACE** with:",
                buttons=get_skip_keyboard(session_id)
            )
        
        elif step == 'cap_replace':
            session['settings']['replace_cap'] = event.text
            session['step'] = 'settings'
            await event.respond(
                "✅ **Caption modification set!**",
                buttons=get_settings_keyboard(session_id)
            )
        
        elif step == 'extra_cap':
            session['settings']['extra_cap'] = event.text
            session['step'] = 'settings'
            await event.respond(
                "✅ **Extra caption set!**",
                buttons=get_settings_keyboard(session_id)
            )
        
        # Existing PDF remove handlers
        elif step == 'pdf_pages':
            from pdf_handler import parse_page_range
            pages = parse_page_range(event.text)
            
            if pages:
                session['settings']['pdf_pages'] = event.text
                session['settings']['pdf_pages_list'] = pages
                session['step'] = 'settings'
                await event.respond(
                    f"✅ **PDF pages set:** `{sorted(pages)}`",
                    buttons=get_settings_keyboard(session_id)
                )
            else:
                await event.respond(
                    "❌ **Invalid format!**",
                    buttons=get_skip_keyboard(session_id)
                )
        
        elif step == 'pdf_keywords':
            keywords = [k.strip() for k in event.text.split(',') if k.strip()]
            
            if keywords:
                session['settings']['pdf_keywords'] = keywords
                session['step'] = 'settings'
                await event.respond(
                    f"✅ **Keywords set:** `{', '.join(keywords)}`",
                    buttons=get_settings_keyboard(session_id)
                )
            else:
                await event.respond(
                    "❌ **No keywords!**",
                    buttons=get_skip_keyboard(session_id)
                )
        
        elif step == 'pdf_image' and event.photo:
            import tempfile
            
            try:
                temp_dir = tempfile.gettempdir()
                image_path = await bot_client.download_media(
                    event.message, 
                    file=os.path.join(temp_dir, f"ref_image_{session_id}.jpg")
                )
                
                threshold = 0.7
                session['settings']['pdf_reference_image'] = image_path
                session['settings']['pdf_image_threshold'] = threshold
                session['step'] = 'settings'
                
                await event.respond(
                    "✅ **Screenshot Saved!**\n"
                    "Will remove matching pages.",
                    buttons=get_settings_keyboard(session_id)
                )
            
            except Exception as e:
                await event.respond(
                    f"❌ **Image Error:** `{str(e)[:100]}`",
                    buttons=get_skip_keyboard(session_id)
                )
        
        # 🆕 NEW: PDF Add Page handlers
        elif step == 'pdf_add_position':
            try:
                position = int(event.text.strip())
                if position < 1:
                    raise ValueError("Position must be >= 1")
                
                session['settings']['pdf_add_position'] = position
                session['step'] = 'pdf_add_image'
                
                await event.respond(
                    f"✅ **Position set:** Page {position}\n\n"
                    f"📤 **Now send your image:**",
                    buttons=get_skip_keyboard(session_id)
                )
            
            except Exception as e:
                await event.respond(
                    "❌ **Invalid position!**\n\n"
                    "Enter a number (e.g., 1, 5, 10):",
                    buttons=get_skip_keyboard(session_id)
                )
        
        elif step == 'pdf_add_image' and event.photo:
            import tempfile
            
            try:
                temp_dir = tempfile.gettempdir()
                image_path = await bot_client.download_media(
                    event.message, 
                    file=os.path.join(temp_dir, f"add_page_{session_id}.jpg")
                )
                
                position = session['settings'].get('pdf_add_position', 'end')
                session['settings']['pdf_add_image'] = image_path
                session['step'] = 'settings'
                
                await event.respond(
                    "✅ **Image Saved!**\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📄 Will add as page at: **{position}**\n"
                    f"🎨 Image will be converted to PDF page\n"
                    f"📐 Auto-fitted to page size\n\n"
                    f"✅ Ready for transfer!",
                    buttons=get_settings_keyboard(session_id)
                )
            
            except Exception as e:
                config.logger.error(f"❌ Add page error: {e}")
                await event.respond(
                    f"❌ **Image Error:** `{str(e)[:100]}`\n\n"
                    "Please send image as photo (not document).",
                    buttons=get_skip_keyboard(session_id)
                )
        
        # 🆕 NEW: PDF Custom Thumbnail handler
        elif step == 'pdf_custom_thumbnail' and event.photo:
            import tempfile
            
            try:
                temp_dir = tempfile.gettempdir()
                thumb_path = await bot_client.download_media(
                    event.message, 
                    file=os.path.join(temp_dir, f"pdf_thumb_{session_id}.jpg")
                )
                
                session['settings']['pdf_thumbnail_action'] = 'custom'
                session['settings']['pdf_custom_thumbnail'] = thumb_path
                session['step'] = 'settings'
                
                await event.respond(
                    "✅ **Custom Thumbnail Saved!**\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    "🖼️ This thumbnail will be applied to all PDFs\n"
                    "📱 Will appear in Telegram file preview\n"
                    "🎨 Represents your brand/content\n\n"
                    "✅ Ready for transfer!",
                    buttons=get_settings_keyboard(session_id)
                )
            
            except Exception as e:
                config.logger.error(f"❌ Thumbnail error: {e}")
                await event.respond(
                    f"❌ **Thumbnail Error:** `{str(e)[:100]}`\n\n"
                    "Send image as photo (JPG/PNG recommended).",
                    buttons=get_skip_keyboard(session_id)
                )
        
        # Message range handler
        elif step == 'range' and "t.me" in event.text:
            try:
                links = event.text.strip().split("-")
                msg1 = int(links[0].strip().split("/")[-1])
                msg2 = int(links[1].strip().split("/")[-1])
                if msg1 > msg2: 
                    msg1, msg2 = msg2, msg1
                
                config.is_running = True
                config.current_task = asyncio.create_task(
                    transfer_process(
                        event, 
                        user_client,
                        bot_client,
                        session['source'], 
                        session['dest'], 
                        msg1, 
                        msg2,
                        session_id
                    )
                )
            except Exception as e: 
                await event.respond(
                    f"❌ **Invalid Range:** `{str(e)}`"
                )
    
    @bot_client.on(events.NewMessage(pattern='/stats'))
    async def stats_handler(event):
        await event.respond(
            f"📊 **EXTREME MODE v3.0 Stats**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ Chunk: **{config.CHUNK_SIZE // (1024*1024)}MB**\n"
            f"💾 Buffer: **{(config.CHUNK_SIZE * config.QUEUE_SIZE) // (1024*1024)}MB**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🚀 Status: **{'Running' if config.is_running else 'Idle'}**\n"
            f"📊 Sessions: **{len(config.active_sessions)}**\n\n"
            f"🆕 **NEW PDF Features:**\n"
            f"• Add custom pages\n"
            f"• Control thumbnails"
        )
    
    @bot_client.on(events.NewMessage(pattern='/stop'))
    async def stop_handler(event):
        if not config.is_running:
            return await event.respond("⚠️ No active transfer!")
        
        config.is_running = False
        if config.current_task: 
            config.current_task.cancel()
        await event.respond("🛑 **Transfer stopped!**")
    
    config.logger.info("✅ v3.0 handlers with PDF features registered!")
