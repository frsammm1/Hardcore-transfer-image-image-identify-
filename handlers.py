# Add this callback handler in handlers.py (replace existing pdf_image_callback)
    
    @bot_client.on(events.CallbackQuery(pattern=r'pdf_image_(.+)'))
    async def pdf_image_callback(event):
        session_id = event.data.decode().split('_')[2]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        config.active_sessions[session_id]['step'] = 'pdf_image'
        await event.edit(
            "📸 **Remove Pages by Screenshot**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "**How it works:**\n"
            "1. Take screenshot of the page you want to remove\n"
            "2. Send the image here\n"
            "3. Bot uses 3 advanced methods to find matches:\n"
            "   • Perceptual Hash (fast)\n"
            "   • SSIM (structural similarity)\n"
            "   • ORB (feature matching)\n\n"
            "**Tips for best results:**\n"
            "• Screenshot the FULL page\n"
            "• Use good quality/resolution\n"
            "• Avoid cropping or editing\n"
            "• Works even with slight differences\n\n"
            "**Similarity Threshold:**\n"
            "Default: 70% (recommended)\n"
            "Range: 60-90%\n\n"
            "📤 **Send screenshot now:**",
            buttons=get_skip_keyboard(session_id)
        )
    
    # Update the message handler for pdf_image step
    # Replace existing pdf_image handling in message_handler with this:
    
        elif step == 'pdf_image' and event.photo:
            # User sent screenshot for PDF page matching
            import tempfile
            from pdf_handler import find_matching_pages_by_image
            
            try:
                # Download uploaded image
                temp_dir = tempfile.gettempdir()
                image_path = await bot_client.download_media(
                    event.message, 
                    file=os.path.join(temp_dir, f"ref_image_{session_id}.jpg")
                )
                
                config.logger.info(f"📥 Screenshot downloaded: {image_path}")
                
                # Set default threshold (70% = good balance)
                threshold = 0.7  # Can be adjusted: 0.6 (loose) to 0.9 (strict)
                
                session['settings']['pdf_reference_image'] = image_path
                session['settings']['pdf_image_threshold'] = threshold
                session['step'] = 'settings'
                
                await event.respond(
                    "✅ **Screenshot Saved!**\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    "📸 Image will be analyzed using:\n"
                    "   1️⃣ Perceptual Hash\n"
                    "   2️⃣ SSIM (Structural Similarity)\n"
                    "   3️⃣ ORB Feature Matching\n\n"
                    f"🎯 Similarity Threshold: **{int(threshold*100)}%**\n"
                    "   (70% = recommended, detects similar pages)\n\n"
                    "💡 All matching pages will be removed during transfer.\n\n"
                    "⚙️ Advanced matching ensures high accuracy!",
                    buttons=get_settings_keyboard(session_id)
                )
            
            except Exception as img_err:
                config.logger.error(f"❌ Image processing error: {img_err}")
                await event.respond(
                    f"❌ **Image Error**\n\n"
                    f"Could not process screenshot.\n\n"
                    f"**Troubleshooting:**\n"
                    f"• Send as photo (not document)\n"
                    f"• Use JPG/PNG format\n"
                    f"• Ensure good quality\n\n"
                    f"Error: `{str(img_err)[:100]}`",
                    buttons=get_skip_keyboard(session_id)
                )
