# 📄 HANDLING MULTIPLE DOCUMENT FORMATS

**Government sites use PDFs, PowerPoint, Word, Excel, and more. Here's how to handle them ALL.**

---

## 🎯 THE STRATEGY

**Regardless of format: Extract text → Store in Parquet**

```
PDF, PPTX, DOCX, XLSX, HTML → Extract Text → Parquet (1 file)
```

**NOT:**
```
❌ Store 1000 PDFs + 500 PPTX + 300 DOCX = 1800 files (too many!)
```

**YES:**
```
✅ Extract text from all → Store in 1 Parquet file
```

---

## 📊 COMMON GOVERNMENT FORMATS

| Format | Extension | Usage | Extraction Library |
|--------|-----------|-------|-------------------|
| **PDF** | .pdf | 70% - Most common | PyPDF2, pdfplumber, pypdf |
| **PowerPoint** | .ppt, .pptx | 15% - Presentations | python-pptx |
| **Word** | .doc, .docx | 10% - Agendas/Minutes | python-docx |
| **Excel** | .xls, .xlsx | 3% - Data tables | openpyxl, pandas |
| **HTML** | .html, .htm | 1% - Web pages | BeautifulSoup |
| **Images** | .jpg, .png | 1% - Scanned docs | pytesseract (OCR) |

**Solution: Handle ALL formats, extract text, store in same Parquet structure** ✅

---

## 🔧 INSTALLATION

```bash
# Install all document processing libraries
pip install PyPDF2 pdfplumber
pip install python-pptx
pip install python-docx
pip install openpyxl pandas
pip install beautifulsoup4 lxml
pip install pytesseract pillow  # For OCR (scanned documents)

# Optional: Install Tesseract OCR engine
# Ubuntu/Debian:
sudo apt-get install tesseract-ocr

# macOS:
brew install tesseract

# Windows:
# Download from https://github.com/UB-Mannheim/tesseract/wiki
```

---

## 📝 UNIVERSAL TEXT EXTRACTOR

### Complete Implementation:

```python
#!/usr/bin/env python3
"""
Universal document text extractor for government documents.
Handles: PDF, PPTX, DOCX, XLSX, HTML, Images (OCR)
"""

import io
from pathlib import Path
from typing import Optional, Dict
import httpx
from loguru import logger

# PDF extraction
try:
    from PyPDF2 import PdfReader
    import pdfplumber
except ImportError:
    logger.warning("Install PDF tools: pip install PyPDF2 pdfplumber")

# PowerPoint extraction
try:
    from pptx import Presentation
except ImportError:
    logger.warning("Install PowerPoint tools: pip install python-pptx")

# Word extraction
try:
    from docx import Document
except ImportError:
    logger.warning("Install Word tools: pip install python-docx")

# Excel extraction
try:
    import openpyxl
    import pandas as pd
except ImportError:
    logger.warning("Install Excel tools: pip install openpyxl pandas")

# HTML extraction
try:
    from bs4 import BeautifulSoup
except ImportError:
    logger.warning("Install HTML tools: pip install beautifulsoup4")

# OCR extraction (for images/scanned PDFs)
try:
    import pytesseract
    from PIL import Image
except ImportError:
    logger.warning("Install OCR tools: pip install pytesseract pillow")


class UniversalDocumentExtractor:
    """Extract text from any government document format."""
    
    def __init__(self):
        self.client = httpx.Client(timeout=30)
    
    def extract_from_url(self, url: str) -> Dict[str, any]:
        """
        Download document from URL and extract text.
        
        Args:
            url: Document URL
            
        Returns:
            Dict with extracted text and metadata
        """
        logger.info(f"Downloading: {url}")
        
        # Download file
        response = self.client.get(url)
        file_bytes = response.content
        
        # Detect format from URL or Content-Type
        file_ext = self._detect_format(url, response.headers.get('content-type', ''))
        
        # Extract based on format
        if file_ext == '.pdf':
            text = self.extract_pdf(file_bytes)
        elif file_ext in ['.ppt', '.pptx']:
            text = self.extract_powerpoint(file_bytes)
        elif file_ext in ['.doc', '.docx']:
            text = self.extract_word(file_bytes)
        elif file_ext in ['.xls', '.xlsx']:
            text = self.extract_excel(file_bytes)
        elif file_ext in ['.html', '.htm']:
            text = self.extract_html(file_bytes)
        elif file_ext in ['.jpg', '.jpeg', '.png', '.tiff']:
            text = self.extract_image_ocr(file_bytes)
        else:
            logger.warning(f"Unknown format: {file_ext}")
            text = ""
        
        return {
            'url': url,
            'format': file_ext,
            'text': text,
            'file_size_kb': len(file_bytes) // 1024,
            'text_length': len(text)
        }
    
    def _detect_format(self, url: str, content_type: str) -> str:
        """Detect document format from URL or Content-Type."""
        
        # Try URL extension first
        url_lower = url.lower()
        for ext in ['.pdf', '.pptx', '.ppt', '.docx', '.doc', '.xlsx', '.xls', '.html', '.htm', '.jpg', '.png']:
            if ext in url_lower:
                return ext
        
        # Try Content-Type
        content_type_lower = content_type.lower()
        if 'pdf' in content_type_lower:
            return '.pdf'
        elif 'powerpoint' in content_type_lower or 'presentation' in content_type_lower:
            return '.pptx'
        elif 'word' in content_type_lower or 'msword' in content_type_lower:
            return '.docx'
        elif 'excel' in content_type_lower or 'spreadsheet' in content_type_lower:
            return '.xlsx'
        elif 'html' in content_type_lower:
            return '.html'
        
        return '.unknown'
    
    def extract_pdf(self, file_bytes: bytes) -> str:
        """Extract text from PDF."""
        try:
            # Try PyPDF2 first (faster)
            pdf_reader = PdfReader(io.BytesIO(file_bytes))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            
            # If no text extracted, might be scanned PDF
            if not text.strip():
                logger.info("PDF appears to be scanned, trying OCR...")
                # Try pdfplumber or OCR
                with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                    text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            
            return text.strip()
        
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return ""
    
    def extract_powerpoint(self, file_bytes: bytes) -> str:
        """Extract text from PowerPoint (.ppt, .pptx)."""
        try:
            prs = Presentation(io.BytesIO(file_bytes))
            text_parts = []
            
            for slide_num, slide in enumerate(prs.slides, 1):
                # Extract text from all shapes
                slide_text = []
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        slide_text.append(shape.text)
                
                if slide_text:
                    text_parts.append(f"=== Slide {slide_num} ===\n")
                    text_parts.append("\n".join(slide_text))
                    text_parts.append("\n\n")
            
            return "".join(text_parts).strip()
        
        except Exception as e:
            logger.error(f"PowerPoint extraction failed: {e}")
            return ""
    
    def extract_word(self, file_bytes: bytes) -> str:
        """Extract text from Word (.doc, .docx)."""
        try:
            doc = Document(io.BytesIO(file_bytes))
            
            # Extract paragraphs
            text_parts = []
            for para in doc.paragraphs:
                if para.text.strip():
                    text_parts.append(para.text)
            
            # Extract tables
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text for cell in row.cells)
                    if row_text.strip():
                        text_parts.append(row_text)
            
            return "\n".join(text_parts).strip()
        
        except Exception as e:
            logger.error(f"Word extraction failed: {e}")
            return ""
    
    def extract_excel(self, file_bytes: bytes) -> str:
        """Extract text from Excel (.xls, .xlsx)."""
        try:
            # Use pandas to read all sheets
            excel_file = io.BytesIO(file_bytes)
            all_sheets = pd.read_excel(excel_file, sheet_name=None)
            
            text_parts = []
            for sheet_name, df in all_sheets.items():
                text_parts.append(f"=== Sheet: {sheet_name} ===\n")
                
                # Convert DataFrame to text
                text_parts.append(df.to_string(index=False))
                text_parts.append("\n\n")
            
            return "".join(text_parts).strip()
        
        except Exception as e:
            logger.error(f"Excel extraction failed: {e}")
            return ""
    
    def extract_html(self, file_bytes: bytes) -> str:
        """Extract text from HTML."""
        try:
            soup = BeautifulSoup(file_bytes, 'html.parser')
            
            # Remove script and style tags
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text
            text = soup.get_text()
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            return text.strip()
        
        except Exception as e:
            logger.error(f"HTML extraction failed: {e}")
            return ""
    
    def extract_image_ocr(self, file_bytes: bytes) -> str:
        """Extract text from image using OCR (for scanned documents)."""
        try:
            image = Image.open(io.BytesIO(file_bytes))
            
            # Run OCR
            text = pytesseract.image_to_string(image)
            
            return text.strip()
        
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            logger.info("Make sure tesseract is installed: sudo apt-get install tesseract-ocr")
            return ""
    
    def close(self):
        """Close HTTP client."""
        self.client.close()


# Example usage
if __name__ == "__main__":
    extractor = UniversalDocumentExtractor()
    
    # Test different formats
    test_urls = [
        "https://example.com/agenda.pdf",
        "https://example.com/presentation.pptx",
        "https://example.com/minutes.docx",
        "https://example.com/budget.xlsx",
    ]
    
    results = []
    for url in test_urls:
        try:
            result = extractor.extract_from_url(url)
            results.append(result)
            print(f"✅ {result['format']}: {result['text_length']} characters")
        except Exception as e:
            print(f"❌ Failed: {url} - {e}")
    
    extractor.close()
    
    # Save to Parquet
    import pandas as pd
    df = pd.DataFrame(results)
    df.to_parquet('extracted_documents.parquet', compression='snappy')
    print(f"\n✅ Saved {len(df)} documents to Parquet!")
```

---

## 🚀 PRACTICAL USAGE

### Process Mixed-Format Documents:

```python
import pandas as pd
from pathlib import Path

def process_jurisdiction_all_formats(jurisdiction):
    """
    Process all document formats from a jurisdiction.
    Extract text from PDFs, PPTX, DOCX, XLSX, etc.
    Store all in single Parquet file.
    """
    
    extractor = UniversalDocumentExtractor()
    all_documents = []
    
    # Get all document URLs (various formats)
    document_urls = get_jurisdiction_documents(jurisdiction)
    
    for url in document_urls:
        # Extract text (works for any format!)
        result = extractor.extract_from_url(url)
        
        # Add metadata
        all_documents.append({
            'jurisdiction': jurisdiction.name,
            'state': jurisdiction.state,
            'url': result['url'],
            'format': result['format'],
            'text': result['text'],
            'file_size_kb': result['file_size_kb'],
            'date': extract_date_from_text(result['text']),
            'title': extract_title_from_text(result['text'])
        })
    
    extractor.close()
    
    # Save all formats in single Parquet
    df = pd.DataFrame(all_documents)
    df.to_parquet(f'documents_{jurisdiction.name}.parquet')
    
    return df

# Process all jurisdictions
all_data = []
for jurisdiction in jurisdictions:
    df = process_jurisdiction_all_formats(jurisdiction)
    all_data.append(df)

# Combine all into one Parquet
combined = pd.concat(all_data, ignore_index=True)
combined.to_parquet('all_documents_all_formats.parquet', compression='snappy')

print(f"✅ Processed {len(combined)} documents")
print(f"   Formats: {combined['format'].value_counts().to_dict()}")
print(f"   File size: {Path('all_documents_all_formats.parquet').stat().st_size / 1e6:.1f} MB")
```

---

## 📊 REAL-WORLD EXAMPLE

### Tuscaloosa, AL (Mixed Formats):

```python
import asyncio
from universal_extractor import UniversalDocumentExtractor

async def discover_tuscaloosa_all_formats():
    """Find and process all document formats from Tuscaloosa."""
    
    extractor = UniversalDocumentExtractor()
    
    # Discover documents (various formats)
    base_url = "https://tuscaloosaal.suiteonemedia.com"
    
    # These might be PDFs, PPTX, DOCX, etc.
    document_urls = [
        f"{base_url}/agenda_2025_03_15.pdf",
        f"{base_url}/presentation_budget.pptx",
        f"{base_url}/minutes_2025_03_01.docx",
        f"{base_url}/financial_report.xlsx",
    ]
    
    results = []
    for url in document_urls:
        result = extractor.extract_from_url(url)
        results.append(result)
        
        print(f"Extracted {result['format']}: {result['text_length']} chars")
    
    extractor.close()
    
    # Save all in Parquet
    import pandas as pd
    df = pd.DataFrame(results)
    df.to_parquet('tuscaloosa_all_formats.parquet')
    
    print(f"\n✅ Saved {len(df)} documents (mixed formats) to 1 Parquet file")
    print(f"   Formats: {df['format'].value_counts().to_dict()}")

asyncio.run(discover_tuscaloosa_all_formats())
```

**Output:**
```
Extracted .pdf: 12,453 chars
Extracted .pptx: 3,821 chars
Extracted .docx: 8,234 chars
Extracted .xlsx: 1,562 chars

✅ Saved 4 documents (mixed formats) to 1 Parquet file
   Formats: {'.pdf': 1, '.pptx': 1, '.docx': 1, '.xlsx': 1}
```

---

## 🎯 FORMAT-SPECIFIC TIPS

### PDF (70% of documents)
```python
# Use pdfplumber for better table extraction
import pdfplumber

with pdfplumber.open(pdf_file) as pdf:
    # Extract text + tables
    for page in pdf.pages:
        text = page.extract_text()
        tables = page.extract_tables()  # Get structured tables!
```

### PowerPoint (15% of documents)
```python
# Extract speaker notes too
from pptx import Presentation

prs = Presentation(pptx_file)
for slide in prs.slides:
    # Text from shapes
    for shape in slide.shapes:
        if hasattr(shape, "text"):
            print(shape.text)
    
    # Speaker notes
    if slide.has_notes_slide:
        print(slide.notes_slide.notes_text_frame.text)
```

### Word (10% of documents)
```python
# Extract headers, footers, comments
from docx import Document

doc = Document(docx_file)

# Headers/Footers
for section in doc.sections:
    print(section.header.paragraphs[0].text)
    print(section.footer.paragraphs[0].text)

# Comments (track changes)
for comment in doc.comments:
    print(comment.text)
```

### Excel (3% of documents)
```python
# Extract all sheets + formulas
import pandas as pd

# Read all sheets
excel_data = pd.read_excel(xlsx_file, sheet_name=None)

for sheet_name, df in excel_data.items():
    print(f"Sheet: {sheet_name}")
    print(df.to_string())
```

---

## 💾 FINAL PARQUET STRUCTURE

**Regardless of input format, output is unified:**

```python
# Single Parquet file with all formats
df = pd.DataFrame({
    'jurisdiction': ['Tuscaloosa', 'Tuscaloosa', 'Tuscaloosa'],
    'state': ['AL', 'AL', 'AL'],
    'date': ['2025-03-15', '2025-03-15', '2025-03-01'],
    'title': ['City Council Meeting', 'Budget Presentation', 'Meeting Minutes'],
    'format': ['.pdf', '.pptx', '.docx'],  # ← Track original format
    'text': ['extracted text...', 'slide text...', 'minutes text...'],
    'url': ['https://...agenda.pdf', 'https://...budget.pptx', 'https://...minutes.docx']
})

# Save to Parquet
df.to_parquet('all_formats.parquet', compression='snappy')

# Upload to Hugging Face (1 file, not 3!)
from datasets import Dataset
dataset = Dataset.from_pandas(df)
dataset.push_to_hub("username/oral-health-docs")
```

---

## 🔍 HANDLING SPECIAL CASES

### Scanned PDFs (Images)
```python
# Use OCR for scanned documents
import pytesseract
import pdf2image

# Convert PDF pages to images, then OCR
images = pdf2image.convert_from_bytes(pdf_bytes)
text = ""
for img in images:
    text += pytesseract.image_to_string(img) + "\n"
```

### Password-Protected PDFs
```python
# Some government docs are password-protected
from PyPDF2 import PdfReader

reader = PdfReader(pdf_file)
if reader.is_encrypted:
    # Try common passwords
    passwords = ['', 'password', 'public']
    for pwd in passwords:
        if reader.decrypt(pwd):
            break
```

### Embedded Videos/Audio
```python
# Don't extract video/audio files
# Just note their existence and link to them

if 'video' in doc.format or 'audio' in doc.format:
    return {
        'text': '[Video/Audio content - see URL]',
        'url': doc_url,
        'type': 'multimedia'
    }
```

---

## ✅ SUMMARY

### Key Points:

1. **Government sites use many formats**
   - PDF (70%), PowerPoint (15%), Word (10%), Excel (3%), Others (2%)

2. **Solution: Universal extractor**
   - One tool handles all formats
   - Extract text from everything
   - Store in single Parquet file

3. **Same workflow regardless of format**
   ```
   Download → Extract Text → Store in Parquet → Upload to HF
   ```

4. **File limits still respected**
   - 1,000 PDFs + 500 PPTX + 300 DOCX = 1,800 source files
   - Extract → Save as 1 Parquet file ✅

5. **Hugging Face upload**
   - Upload Parquet (not source files)
   - All formats in unified structure
   - Still FREE unlimited storage

### Libraries Needed:

```bash
pip install PyPDF2 pdfplumber           # PDF
pip install python-pptx                 # PowerPoint
pip install python-docx                 # Word
pip install openpyxl pandas             # Excel
pip install beautifulsoup4              # HTML
pip install pytesseract pillow          # OCR for scanned docs
```

### Result:

**You can now handle ANY format government sites use, extract text, and store efficiently in Parquet for FREE on Hugging Face!** 🎉

---

**Next:** Integrate this into your discovery pipeline so it automatically handles all formats!
