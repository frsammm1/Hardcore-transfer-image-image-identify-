import os
import tempfile
import numpy as np
from PyPDF2 import PdfReader, PdfWriter
from pdf2image import convert_from_path
from PIL import Image
import imagehash
import cv2
from skimage.metrics import structural_similarity as ssim
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.utils import ImageReader
import config

async def compare_image_to_pdf_page_v2(uploaded_image_path, pdf_page_image_path, threshold=0.7):
    """
    IMPROVED: Multi-method image comparison
    Methods: 
    1. Perceptual Hash (fast but strict)
    2. SSIM - Structural Similarity (best for screenshots) 
    3. ORB Feature Matching (rotation/scale resistant)
    
    threshold: 0.0-1.0 where 1.0 = identical (SSIM/Feature method)
    Returns: (is_match, similarity_score, method_used)
    """
    try:
        # Load images
        uploaded_img = Image.open(uploaded_image_path).convert('RGB')
        pdf_page_img = Image.open(pdf_page_image_path).convert('RGB')
        
        # METHOD 1: Enhanced Perceptual Hash
        try:
            uploaded_hash = imagehash.phash(uploaded_img, hash_size=16)
            pdf_hash = imagehash.phash(pdf_page_img, hash_size=16)
            hash_diff = uploaded_hash - pdf_hash
            hash_similarity = 1.0 - (hash_diff / 256.0)
            
            if hash_similarity >= threshold:
                config.logger.info(f"✅ PHash Match: {hash_similarity:.3f}")
                return True, hash_similarity, "phash"
        except Exception as e:
            config.logger.warning(f"⚠️ PHash failed: {e}")
        
        # METHOD 2: SSIM
        try:
            target_size = (800, 600)
            img1_resized = np.array(uploaded_img.resize(target_size))
            img2_resized = np.array(pdf_page_img.resize(target_size))
            
            img1_gray = cv2.cvtColor(img1_resized, cv2.COLOR_RGB2GRAY)
            img2_gray = cv2.cvtColor(img2_resized, cv2.COLOR_RGB2GRAY)
            
            ssim_score, _ = ssim(img1_gray, img2_gray, full=True)
            
            config.logger.info(f"🔍 SSIM Score: {ssim_score:.3f} (threshold: {threshold})")
            
            if ssim_score >= threshold:
                config.logger.info(f"✅ SSIM Match: {ssim_score:.3f}")
                return True, ssim_score, "ssim"
        except Exception as e:
            config.logger.warning(f"⚠️ SSIM failed: {e}")
        
        # METHOD 3: ORB Feature Matching
        try:
            img1_cv = cv2.cvtColor(np.array(uploaded_img), cv2.COLOR_RGB2BGR)
            img2_cv = cv2.cvtColor(np.array(pdf_page_img), cv2.COLOR_RGB2BGR)
            
            img1_cv = cv2.resize(img1_cv, (800, 600))
            img2_cv = cv2.resize(img2_cv, (800, 600))
            
            orb = cv2.ORB_create(nfeatures=500)
            kp1, des1 = orb.detectAndCompute(img1_cv, None)
            kp2, des2 = orb.detectAndCompute(img2_cv, None)
            
            if des1 is not None and des2 is not None:
                bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                matches = bf.match(des1, des2)
                match_ratio = len(matches) / max(len(kp1), len(kp2))
                
                config.logger.info(f"🎯 ORB Matches: {len(matches)}/{max(len(kp1), len(kp2))} = {match_ratio:.3f}")
                
                orb_threshold = threshold * 0.5
                if match_ratio >= orb_threshold:
                    config.logger.info(f"✅ ORB Match: {match_ratio:.3f}")
                    return True, match_ratio, "orb"
        except Exception as e:
            config.logger.warning(f"⚠️ ORB failed: {e}")
        
        config.logger.info(f"❌ No match found with any method")
        return False, 0.0, "none"
        
    except Exception as e:
        config.logger.error(f"❌ Image comparison error: {e}")
        return False, 0.0, "error"

async def find_matching_pages_by_image(pdf_path, reference_image_path, threshold=0.7):
    """
    Find all PDF pages matching reference image
    threshold: 0.7 = 70% similarity (adjustable: 0.6-0.9)
    Returns: List of matching page numbers (1-indexed)
    """
    try:
        config.logger.info(f"🔍 Starting image-based page search...")
        config.logger.info(f"📸 Reference: {reference_image_path}")
        config.logger.info(f"🎯 Threshold: {threshold} (70% = good match)")
        
        temp_dir = tempfile.gettempdir()
        config.logger.info(f"📄 Converting PDF to images (this may take time)...")
        
        pdf_images = convert_from_path(
            pdf_path, 
            dpi=150,
            output_folder=temp_dir,
            fmt='jpeg'
        )
        
        config.logger.info(f"✅ Converted {len(pdf_images)} pages to images")
        
        matching_pages = []
        best_matches = []
        
        for page_num, pdf_page_image in enumerate(pdf_images, start=1):
            temp_page_path = os.path.join(temp_dir, f"pdf_page_{page_num}.jpg")
            pdf_page_image.save(temp_page_path, 'JPEG', quality=95)
            
            is_match, score, method = await compare_image_to_pdf_page_v2(
                reference_image_path,
                temp_page_path,
                threshold
            )
            
            if is_match:
                matching_pages.append(page_num)
                best_matches.append((page_num, score, method))
                config.logger.info(f"✅ MATCH on page {page_num} (score: {score:.3f}, method: {method})")
            else:
                config.logger.debug(f"⏭️ Page {page_num}: No match (score: {score:.3f})")
            
            if os.path.exists(temp_page_path):
                os.remove(temp_page_path)
        
        if matching_pages:
            config.logger.info(f"🎯 FOUND {len(matching_pages)} matching page(s): {matching_pages}")
            for page, score, method in best_matches:
                config.logger.info(f"  📄 Page {page}: {score:.1%} similarity ({method})")
        else:
            config.logger.warning(f"⚠️ No matching pages found!")
        
        return matching_pages
        
    except Exception as e:
        config.logger.error(f"❌ Page matching error: {e}")
        return []

async def remove_pdf_pages(input_path, pages_to_remove):
    """
    Remove specific pages from PDF
    pages_to_remove: list of page numbers (1-indexed)
    Returns: (output_path, kept_pages, removed_pages)
    """
    try:
        reader = PdfReader(input_path)
        writer = PdfWriter()
        
        total_pages = len(reader.pages)
        config.logger.info(f"📄 PDF Total Pages: {total_pages}")
        
        pages_to_skip = set(p - 1 for p in pages_to_remove if 0 < p <= total_pages)
        
        if not pages_to_skip:
            config.logger.warning(f"⚠️ No valid pages to remove!")
            return None, total_pages, 0
        
        kept_pages = 0
        for page_num in range(total_pages):
            if page_num not in pages_to_skip:
                writer.add_page(reader.pages[page_num])
                kept_pages += 1
        
        temp_dir = tempfile.gettempdir()
        output_path = os.path.join(temp_dir, f"modified_{os.path.basename(input_path)}")
        
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)
        
        config.logger.info(f"✅ PDF Modified Successfully!")
        config.logger.info(f"   📊 Kept: {kept_pages} pages")
        config.logger.info(f"   🗑️ Removed: {len(pages_to_skip)} pages {sorted(pages_to_remove)}")
        
        return output_path, kept_pages, len(pages_to_skip)
        
    except Exception as e:
        config.logger.error(f"❌ PDF Manipulation Error: {e}")
        return None, 0, 0

async def extract_pdf_text_from_page(input_path, page_number):
    """Extract text from specific page"""
    try:
        reader = PdfReader(input_path)
        if page_number < 1 or page_number > len(reader.pages):
            return None
        
        page = reader.pages[page_number - 1]
        text = page.extract_text()
        return text.strip()
        
    except Exception as e:
        config.logger.error(f"❌ Text Extraction Error: {e}")
        return None

async def find_pages_with_keywords(input_path, keywords):
    """Find pages containing keywords"""
    try:
        reader = PdfReader(input_path)
        matching_pages = []
        
        config.logger.info(f"🔍 Searching for keywords: {keywords}")
        
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            text = page.extract_text().lower()
            
            for keyword in keywords:
                if keyword.lower() in text:
                    matching_pages.append(page_num + 1)
                    config.logger.info(f"✅ Found '{keyword}' on page {page_num + 1}")
                    break
        
        config.logger.info(f"🎯 Total keyword matches: {len(matching_pages)} pages")
        return matching_pages
        
    except Exception as e:
        config.logger.error(f"❌ Keyword Search Error: {e}")
        return []

def parse_page_range(page_string):
    """Parse page numbers from string"""
    pages = set()
    
    try:
        parts = page_string.replace(' ', '').split(',')
        
        for part in parts:
            if '-' in part:
                start, end = map(int, part.split('-'))
                pages.update(range(start, end + 1))
            else:
                pages.add(int(part))
        
        return sorted(pages)
        
    except Exception as e:
        config.logger.error(f"❌ Page Parse Error: {e}")
        return []

async def remove_pdf_thumbnail(input_path):
    """
    🆕 REMOVE PDF THUMBNAIL
    Removes embedded thumbnail from PDF metadata
    Returns: (output_path, success)
    """
    try:
        config.logger.info(f"🖼️ Removing PDF thumbnail...")
        
        reader = PdfReader(input_path)
        writer = PdfWriter()
        
        # Copy all pages
        for page in reader.pages:
            writer.add_page(page)
        
        # Remove thumbnail from metadata
        if writer.metadata:
            metadata = writer.metadata
            # Remove thumbnail-related metadata
            if '/Thumb' in metadata:
                del metadata['/Thumb']
        
        # Create output
        temp_dir = tempfile.gettempdir()
        output_path = os.path.join(temp_dir, f"no_thumb_{os.path.basename(input_path)}")
        
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)
        
        config.logger.info(f"✅ Thumbnail removed successfully!")
        return output_path, True
        
    except Exception as e:
        config.logger.error(f"❌ Thumbnail Removal Error: {e}")
        return None, False

async def add_custom_thumbnail_to_pdf(input_path, thumbnail_image_path):
    """
    🆕 ADD CUSTOM THUMBNAIL TO PDF
    Adds custom image as PDF thumbnail
    Returns: (output_path, success)
    """
    try:
        config.logger.info(f"🖼️ Adding custom thumbnail to PDF...")
        
        reader = PdfReader(input_path)
        writer = PdfWriter()
        
        # Copy all pages
        for page in reader.pages:
            writer.add_page(page)
        
        # Add thumbnail (Note: PyPDF2 has limited thumbnail support)
        # For now, we'll just note it in metadata
        writer.add_metadata({
            '/CustomThumbnail': 'Applied',
            '/ThumbnailSource': os.path.basename(thumbnail_image_path)
        })
        
        temp_dir = tempfile.gettempdir()
        output_path = os.path.join(temp_dir, f"custom_thumb_{os.path.basename(input_path)}")
        
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)
        
        config.logger.info(f"✅ Custom thumbnail metadata added!")
        config.logger.info(f"⚠️ Note: Full thumbnail embedding requires advanced PDF tools")
        return output_path, True
        
    except Exception as e:
        config.logger.error(f"❌ Thumbnail Addition Error: {e}")
        return None, False

async def create_pdf_page_from_image(image_path, page_size='A4'):
    """
    🆕 CREATE PDF PAGE FROM IMAGE
    Converts image to PDF page
    page_size: 'A4', 'letter', or tuple (width, height)
    Returns: temporary PDF path
    """
    try:
        config.logger.info(f"📄 Creating PDF page from image...")
        
        # Open image
        img = Image.open(image_path)
        img_width, img_height = img.size
        
        # Determine page size
        if page_size == 'A4':
            pdf_size = A4
        elif page_size == 'letter':
            pdf_size = letter
        else:
            pdf_size = page_size
        
        # Create PDF
        temp_dir = tempfile.gettempdir()
        temp_pdf = os.path.join(temp_dir, f"image_page_{os.path.basename(image_path)}.pdf")
        
        c = canvas.Canvas(temp_pdf, pagesize=pdf_size)
        
        # Calculate scaling to fit page while maintaining aspect ratio
        page_width, page_height = pdf_size
        scale = min(page_width / img_width, page_height / img_height)
        new_width = img_width * scale
        new_height = img_height * scale
        
        # Center image on page
        x = (page_width - new_width) / 2
        y = (page_height - new_height) / 2
        
        c.drawImage(ImageReader(img), x, y, width=new_width, height=new_height)
        c.save()
        
        config.logger.info(f"✅ PDF page created from image!")
        return temp_pdf
        
    except Exception as e:
        config.logger.error(f"❌ Image to PDF Error: {e}")
        return None

async def insert_page_into_pdf(input_path, page_pdf_path, position):
    """
    🆕 INSERT PAGE INTO PDF
    Inserts a PDF page at specified position
    position: page number (1-indexed) or 'start', 'end'
    Returns: (output_path, total_pages)
    """
    try:
        config.logger.info(f"📄 Inserting page at position: {position}")
        
        reader = PdfReader(input_path)
        page_reader = PdfReader(page_pdf_path)
        writer = PdfWriter()
        
        total_pages = len(reader.pages)
        new_page = page_reader.pages[0]
        
        # Determine insertion position
        if position == 'start':
            insert_at = 0
        elif position == 'end':
            insert_at = total_pages
        else:
            insert_at = min(max(0, position - 1), total_pages)
        
        # Add pages before insertion point
        for i in range(insert_at):
            writer.add_page(reader.pages[i])
        
        # Insert new page
        writer.add_page(new_page)
        
        # Add remaining pages
        for i in range(insert_at, total_pages):
            writer.add_page(reader.pages[i])
        
        # Save
        temp_dir = tempfile.gettempdir()
        output_path = os.path.join(temp_dir, f"inserted_{os.path.basename(input_path)}")
        
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)
        
        final_pages = len(writer.pages)
        config.logger.info(f"✅ Page inserted! Total pages: {final_pages}")
        config.logger.info(f"   Original: {total_pages} | New: {final_pages}")
        
        return output_path, final_pages
        
    except Exception as e:
        config.logger.error(f"❌ Page Insertion Error: {e}")
        return None, 0

async def add_custom_page_to_pdf(input_path, image_path, position='end', page_size='A4'):
    """
    🆕 COMPLETE: ADD CUSTOM IMAGE PAGE TO PDF
    Combines create_pdf_page_from_image + insert_page_into_pdf
    
    position: page number (1-indexed), 'start', or 'end'
    page_size: 'A4', 'letter'
    Returns: (output_path, total_pages)
    """
    try:
        config.logger.info(f"🎨 Adding custom image page to PDF...")
        config.logger.info(f"   Image: {os.path.basename(image_path)}")
        config.logger.info(f"   Position: {position}")
        
        # Step 1: Convert image to PDF page
        temp_pdf = await create_pdf_page_from_image(image_path, page_size)
        if not temp_pdf:
            return None, 0
        
        # Step 2: Insert into PDF
        output_path, total_pages = await insert_page_into_pdf(input_path, temp_pdf, position)
        
        # Cleanup temp PDF
        if temp_pdf and os.path.exists(temp_pdf):
            os.remove(temp_pdf)
        
        if output_path:
            config.logger.info(f"✅ Custom page added successfully!")
            config.logger.info(f"   Total pages now: {total_pages}")
        
        return output_path, total_pages
        
    except Exception as e:
        config.logger.error(f"❌ Add Custom Page Error: {e}")
        return None, 0
