# pdf_processor.py
import pdfplumber
import pytesseract
import io

# Ensure Tesseract is installed on your machine
# pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract' # Update path if needed

def extract_text_from_pdf(file_bytes):
    text_content = ""
    
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            # Try extracting text
            page_text = page.extract_text()
            
            # If text is sparse, assume scanned and use OCR
            if not page_text or len(page_text.strip()) < 50:
                # Convert page to image for OCR
                im = page.to_image(resolution=300).original
                page_text = pytesseract.image_to_string(im)
            
            # Basic cleaning
            if page_text:
                # Remove headers/footers roughly by splitting lines
                lines = page_text.split('\n')
                # heuristic: drop top/bottom lines if they are short (page numbers)
                clean_lines = [line for line in lines if len(line) > 5] 
                text_content += "\n".join(clean_lines) + "\n\n"
                
    return text_content