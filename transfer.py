# Replace existing PDF PROCESSING section in transfer.py with this:
                    
                    # PDF PROCESSING (IMPROVED)
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
