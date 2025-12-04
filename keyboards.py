from telethon import Button

def get_settings_keyboard(session_id):
    """Main settings keyboard for file manipulation"""
    return [
        [
            Button.inline("📝 Filename: Find & Replace", f"set_fname_{session_id}"),
        ],
        [
            Button.inline("💬 Caption: Find & Replace", f"set_fcap_{session_id}"),
        ],
        [
            Button.inline("➕ Add Extra Caption", f"set_xcap_{session_id}"),
        ],
        [
            Button.inline("📄 PDF: Remove Pages", f"set_pdf_{session_id}"),
            Button.inline("🖼️ Thumbnail Options", f"set_thumb_{session_id}")
        ],
        [
            Button.inline("✅ Done - Start Transfer", f"confirm_{session_id}"),
            Button.inline("❌ Cancel", f"cancel_{session_id}")
        ]
    ]

def get_confirm_keyboard(session_id, settings):
    """Show current settings and confirm"""
    settings_text = "**Current Settings:**\n\n"
    
    if settings.get('find_name'):
        settings_text += f"📝 Filename:\n`{settings['find_name']}` → `{settings.get('replace_name', '')}`\n\n"
    
    if settings.get('find_cap'):
        settings_text += f"💬 Caption:\n`{settings['find_cap']}` → `{settings.get('replace_cap', '')}`\n\n"
    
    if settings.get('extra_cap'):
        settings_text += f"➕ Extra Caption:\n`{settings['extra_cap'][:50]}...`\n\n"
    
    if settings.get('pdf_pages'):
        settings_text += f"📄 PDF Pages to Remove:\n`{settings['pdf_pages']}`\n\n"
    
    if settings.get('pdf_keywords'):
        settings_text += f"🔍 PDF Keywords to Remove:\n`{', '.join(settings['pdf_keywords'][:3])}`\n\n"
    
    if settings.get('pdf_reference_image'):
        settings_text += f"📸 PDF Image-based Removal:\nScreenshot uploaded ✅\n\n"
    
    thumb_mode = settings.get('thumbnail_mode', 'original')
    if thumb_mode == 'generate':
        settings_text += f"🖼️ Thumbnail: Generate from video\n\n"
    elif thumb_mode == 'smart':
        skip = settings.get('thumbnail_skip', 10)
        settings_text += f"🎯 Thumbnail: Smart (skip {skip}s)\n\n"
    else:
        settings_text += f"🖼️ Thumbnail: Use Original\n\n"
    
    if not any([settings.get('find_name'), settings.get('find_cap'), settings.get('extra_cap'), 
                settings.get('pdf_pages'), settings.get('thumbnail_mode') != 'original']):
        settings_text += "⚠️ No modifications set\n\n"
    
    return settings_text, [
        [
            Button.inline("🔙 Back to Settings", f"back_{session_id}"),
            Button.inline("✅ Confirm & Start", f"start_{session_id}")
        ],
        [
            Button.inline("🗑️ Clear All Settings", f"clear_{session_id}"),
            Button.inline("❌ Cancel", f"cancel_{session_id}")
        ]
    ]

def get_skip_keyboard(session_id):
    """Skip option keyboard"""
    return [
        [Button.inline("⏭️ Skip", f"skip_{session_id}")],
        [Button.inline("❌ Cancel", f"cancel_{session_id}")]
    ]

def get_progress_keyboard():
    """Keyboard during transfer"""
    return [
        [Button.inline("🛑 Stop Transfer", "stop_transfer")]
    ]

def get_clone_info_keyboard():
    """Info keyboard for clone command"""
    return [
        [Button.inline("ℹ️ How to use?", "clone_help")],
        [Button.inline("📊 Bot Stats", "bot_stats")]
    ]

def get_pdf_options_keyboard(session_id):
    """PDF manipulation options"""
    return [
        [Button.inline("🔢 Remove by Page Numbers", f"pdf_pages_{session_id}")],
        [Button.inline("🔍 Remove by Keywords", f"pdf_keywords_{session_id}")],
        [Button.inline("📸 Remove by Screenshot", f"pdf_image_{session_id}")],
        [Button.inline("⏭️ Skip PDF Settings", f"skip_{session_id}")],
        [Button.inline("❌ Cancel", f"cancel_{session_id}")]
    ]

def get_thumbnail_options_keyboard(session_id):
    """Thumbnail generation options"""
    return [
        [Button.inline("📌 Use Original Thumbnail", f"thumb_original_{session_id}")],
        [Button.inline("⚡ Generate from Video (1s)", f"thumb_gen1_{session_id}")],
        [Button.inline("🎯 Smart Generate (skip 10s)", f"thumb_smart_{session_id}")],
        [Button.inline("⏭️ Skip Thumbnail Settings", f"skip_{session_id}")],
        [Button.inline("❌ Cancel", f"cancel_{session_id}")]
    ]
