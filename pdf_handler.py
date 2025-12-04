import os
import tempfile
from PyPDF2 import PdfReader, PdfWriter
from pdf2image import convert_from_path
from PIL import Image
import imagehash
import config

async def compare_image_to_pdf_page(uploaded_image_path, pdf_page_image_path, threshold=10):
    """
    Compare uploaded image with PDF page using perceptual hashing
    threshold: Maximum hash difference (lower = more strict)
    Returns: True if images are similar
    """
    try:
        # Calculate perceptual hashes
        uploaded_hash = imagehash.average_hash(Image.open(uploaded_image_path))
        pdf_page_hash = imagehash.average_hash(Image.open(pdf_page_image_path))
        
        # Calculate difference (0 = identical, 64 = completely different)
        difference = uploaded_hash - pdf_page_hash
        
        config.logger.info(f"🔍 Image similarity: {difference} (threshold: {threshold})")
        
        return difference <= threshold
        
    except Exception as e:
        config.logger.error(f"❌ Image comparison error: {e}")
        return False

async def find_matching_pages_by_image(pdf_path, reference_image_path, threshold=10):
    """
    Find all PDF pages that match the reference image
    reference_image_path: Path to uploaded screenshot
    threshold: Similarity threshold (0-64, lower = stricter)
    Returns: List of matching page numbers (1-indexed)
    """
    try:
        config.logger.info(f"🔍 Searching for matching pages in PDF...")
        config.logger.info(f"📸 Reference image: {reference_image_path}")
        
        # Convert PDF pages to images
        temp_dir = tempfile.gettempdir()
        pdf_images = convert_from_path(pdf_path, dpi=150, output_folder=temp_dir)
        
        matching_pages = []
        
        for page_num, pdf_page_image in enumerate(pdf_images, start=1):
            # Save PDF page as temp image
            temp_page_path = os.path.join(temp_dir, f"pdf_page_{page_num}.png")
            pdf_page_image.save(temp_page_path, 'PNG')
            
            # Compare with reference image
            is_match = await compare_image_to_pdf_page(
                reference_image_path, 
                temp_page_path, 
                threshold
            )
            
            if is_match:
                matching_pages.append(page_num)
                config.logger.info(f"✅ Match found on page {page_num}")
            
            # Cleanup temp page image
            if os.path.exists(temp_page_path):
                os.remove(temp_page_path)
        
        if matching_pages:
            config.logger.info(f"🎯 Total matches found: {len(matching_pages)} pages")
        else:
            config.logger.info(f"⚠️ No matching pages found")
        
        return matching_pages
        
    except Exception as e:
        config.logger.error(f"❌ Page matching error: {e}")
        return []

async def remove_pdf_pages(input_path, pages_to_remove):
    """
    Remove specific pages from PDF
    pages_to_remove: list of page numbers (1-indexed)
    Returns: path to modified PDF
    """
    try:
        reader = PdfReader(input_path)
        writer = PdfWriter()
        
        total_pages = len(reader.pages)
        config.logger.info(f"📄 PDF Total Pages: {total_pages}")
        
        # Convert to 0-indexed
        pages_to_skip = set(p - 1 for p in pages_to_remove if 0 < p <= total_pages)
        
        kept_pages = 0
        for page_num in range(total_pages):
            if page_num not in pages_to_skip:
                writer.add_page(reader.pages[page_num])
                kept_pages += 1
        
        # Create temp file for output
        temp_dir = tempfile.gettempdir()
        output_path = os.path.join(temp_dir, f"modified_{os.path.basename(input_path)}")
        
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)
        
        config.logger.info(f"✅ PDF Modified: {kept_pages}/{total_pages} pages kept")
        config.logger.info(f"🗑️ Removed pages: {sorted(pages_to_remove)}")
        
        return output_path, kept_pages, len(pages_to_skip)
        
    except Exception as e:
        config.logger.error(f"❌ PDF Manipulation Error: {e}")
        return None, 0, 0

async def extract_pdf_text_from_page(input_path, page_number):
    """
    Extract text from a specific page for smart detection
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
    Find all pages containing specific keywords
    keywords: list of strings to search for
    Returns: list of page numbers (1-indexed)
    """
    try:
        reader = PdfReader(input_path)
        matching_pages = []
        
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            text = page.extract_text().lower()
            
            # Check if any keyword exists in page
            for keyword in keywords:
                if keyword.lower() in text:
                    matching_pages.append(page_num + 1)  # 1-indexed
                    config.logger.info(f"🔍 Found '{keyword}' on page {page_num + 1}")
                    break
        
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
