# 📦 INSTALLING DOCUMENT PROCESSING LIBRARIES

**Quick guide to install all libraries for handling multiple document formats.**

---

## 🚀 QUICK INSTALL

```bash
cd /home/developer/projects/open-navigator
source venv/bin/activate

# Install all document processing libraries
pip install PyPDF2 pdfplumber python-pptx python-docx openpyxl

# Optional: OCR for scanned documents (requires tesseract)
pip install pytesseract Pillow
```

---

## 📋 WHAT GETS INSTALLED

| Library | Purpose | Size |
|---------|---------|------|
| **PyPDF2** | Extract text from PDFs | ~500 KB |
| **pdfplumber** | Advanced PDF extraction (tables) | ~2 MB |
| **python-pptx** | Extract text from PowerPoint | ~500 KB |
| **python-docx** | Extract text from Word documents | ~300 KB |
| **openpyxl** | Extract text from Excel | ~2 MB |
| **pytesseract** | OCR for scanned documents (optional) | ~100 KB |
| **Pillow** | Image processing for OCR | ~3 MB |

**Total: ~8 MB** (very lightweight!)

---

## 🔧 OPTIONAL: OCR SUPPORT

**For scanned PDFs and images, install Tesseract OCR engine:**

### Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

### macOS:
```bash
brew install tesseract
```

### Windows:
Download installer from: https://github.com/UB-Mannheim/tesseract/wiki

---

## ✅ VERIFY INSTALLATION

```bash
# Test all libraries
python -c "
import PyPDF2
import pdfplumber
from pptx import Presentation
from docx import Document
import openpyxl
print('✅ All document libraries installed!')
"

# Test OCR (optional)
python -c "
import pytesseract
from PIL import Image
print('✅ OCR libraries installed!')
print(f'Tesseract version: {pytesseract.get_tesseract_version()}')
"
```

---

## 🎯 TEST WITH REAL DOCUMENT

```bash
# Test PDF extraction
python extraction/universal_extractor.py https://example.com/document.pdf

# Test PowerPoint extraction
python extraction/universal_extractor.py https://example.com/presentation.pptx

# Test Word extraction
python extraction/universal_extractor.py https://example.com/document.docx
```

---

## 🆘 TROUBLESHOOTING

### "No module named 'PyPDF2'"
```bash
pip install PyPDF2
```

### "pytesseract is not installed"
```bash
# Install Python package
pip install pytesseract

# Install system package (Ubuntu)
sudo apt-get install tesseract-ocr
```

### "TesseractNotFoundError"
```bash
# On Ubuntu/Debian
sudo apt-get install tesseract-ocr

# On macOS
brew install tesseract

# On Windows
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
# Add to PATH after installation
```

### "Permission denied"
```bash
# Make sure you're in virtual environment
source venv/bin/activate

# Then retry installation
pip install -r requirements.txt
```

---

## 📊 STORAGE IMPACT

**Even with all libraries installed:**
- Virtual environment size: ~500 MB (unchanged)
- Libraries add: ~8 MB
- **Total: Still under 1 GB** ✅

**Processing impact:**
- Extract text from 1000 PDFs: ~50 MB local storage (temporary)
- Store in Parquet: ~5 MB (compressed)
- **Save 90% storage vs storing original files** ✅

---

## ✅ DONE!

**You can now extract text from:**
- ✅ PDF documents
- ✅ PowerPoint presentations
- ✅ Word documents
- ✅ Excel spreadsheets
- ✅ HTML pages
- ✅ Scanned documents (with OCR)

**All will be stored efficiently in Parquet format for FREE on Hugging Face!** 🎉
