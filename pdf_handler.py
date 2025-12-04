import os
import tempfile
import numpy as np
from PyPDF2 import PdfReader, PdfWriter
from pdf2image import convert_from_path
from PIL import Image
import imagehash
import cv2
from skimage.metrics import structural_similarity as ssim
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
            uploaded_hash = imagehash.phash(uploaded_img, hash_size=16)  # Larger hash
            pdf_hash = imagehash.phash(pdf_page_img, hash_size=16)
            hash_diff = uploaded_hash - pdf_hash
            hash_similarity = 1.0 - (hash_diff / 256.0)  # Normalize to 0-1
            
            if hash_similarity >= threshold:
                config.logger.info(f"✅ PHash Match: {hash_similarity:.3f}")
                return True, hash_similarity, "phash"
        except Exception as e:
            config.logger.warning(f"⚠️ PHash failed: {e}")
        
        # METHOD 2: SSIM (Best for screenshots)
        try:
            # Resize to same dimensions
            target_size = (800, 600)
            img1_resized = np.array(uploaded_img.resize(target_size))
            img2_resized = np.array(pdf_page_img.resize(target_size))
            
            # Convert to grayscale
            img1_gray = cv2.cvtColor(img1_resized, cv2.COLOR_RGB2GRAY)
            img2_gray = cv2.cvtColor(img2_resized, cv2.COLOR_RGB2GRAY)
            
            # Calculate SSIM
            ssim_score, _ = ssim(img1_gray, img2_gray, full=True)
            
            config.logger.info(f"🔍 SSIM Score: {ssim_score:.3f} (threshold: {threshold})")
            
            if ssim_score >= threshold:
                config.logger.info(f"✅ SSIM Match: {ssim_score:.3f}")
                return True, ssim_score, "ssim"
        except Exception as e:
            config.logger.warning(f"⚠️ SSIM failed: {e}")
        
        # METHOD 3: ORB Feature Matching (fallback)
        try:
            # Convert to OpenCV format
            img1_cv = cv2.cvtColor(np.array(uploaded_img), cv2.COLOR_RGB2BGR)
            img2_cv = cv2.cvtColor(np.array(pdf_page_img), cv2.COLOR_RGB2BGR)
            
            # Resize for consistency
            img1_cv = cv2.resize(img1_cv, (800, 600))
            img2_cv = cv2.resize(img2_cv, (800, 600))
            
            # ORB detector
            orb = cv2.ORB_create(nfeatures=500)
            kp1, des1 = orb.detectAndCompute(img1_cv, None)
            kp2, des2 = orb.detectAndCompute(img2_cv, None)
            
            if des1 is not None and des2 is not None:
                # BFMatcher
                bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                matches = bf.match(des1, des2)
                
                # Calculate match ratio
                match_ratio = len(matches) / max(len(kp1), len(kp2))
                
                config.logger.info(f"🎯 ORB Matches: {len(matches)}/{max(len(kp1), len(kp2))} = {match_ratio:.3f}")
                
                # Lower threshold for ORB (0.3 is good)
                orb_threshold = threshold * 0.5  
                if match_ratio >= orb_threshold:
                    config.logger.info(f"✅ ORB Match: {match_ratio:.3f}")
                    return True, match_ratio, "orb"
        except Exception as e:
            config.logger.warning(f"⚠️ ORB failed: {e}")
        
        # No match found
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
        
        # Convert PDF to images with higher DPI for better matching
        temp_dir = tempfile.gettempdir()
        config.logger.info(f"📄 Converting PDF to images (this may take time)...")
        
        pdf_images = convert_from_path(
            pdf_path, 
            dpi=150,  # Good balance of quality/speed
            output_folder=temp_dir,
            fmt='jpeg'
        )
        
        config.logger.info(f"✅ Converted {len(pdf_images)} pages to images")
        
        matching_pages = []
        best_matches = []  # Store all matches with scores
        
        for page_num, pdf_page_image in enumerate(pdf_images, start=1):
            # Save PDF page as temp image
            temp_page_path = os.path.join(temp_dir, f"pdf_page_{page_num}.jpg")
            pdf_page_image.save(temp_page_path, 'JPEG', quality=95)
            
            # Compare with reference
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
            
            # Cleanup temp page
            if os.path.exists(temp_page_path):
                os.remove(temp_page_path)
        
        # Summary
        if matching_pages:
            config.logger.info(f"🎯 FOUND {len(matching_pages)} matching page(s): {matching_pages}")
            for page, score, method in best_matches:
                config.logger.info(f"  📄 Page {page}: {score:.1%} similarity ({method})")
        else:
            config.logger.warning(f"⚠️ No matching pages found!")
            config.logger.warning(f"💡 Try:")
            config.logger.warning(f"   - Lower threshold (current: {threshold})")
            config.logger.warning(f"   - Better quality screenshot")
            config.logger.warning(f"   - Screenshot full page without cropping")
        
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
        
        # Convert to 0-indexed and validate
        pages_to_skip = set(p - 1 for p in pages_to_remove if 0 < p <= total_pages)
        
        if not pages_to_skip:
            config.logger.warning(f"⚠️ No valid pages to remove!")
            return None, total_pages, 0
        
        kept_pages = 0
        for page_num in range(total_pages):
            if page_num not in pages_to_skip:
                writer.add_page(reader.pages[page_num])
                kept_pages += 1
        
        # Create output file
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
    """
    Extract text from specific page
    page_number: 1-indexed
    """
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
    """
    Find pages containing keywords
    keywords: list of strings
    Returns: list of page numbers (1-indexed)
    """
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
    """
    Parse page numbers from string
    Supports: "1,2,3" or "1-5" or "1,3-5,8"
    """
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
