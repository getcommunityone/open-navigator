# ⚠️ HUGGING FACE FILE LIMITS & SOLUTIONS

**IMPORTANT: Don't upload individual PDFs! Use structured formats instead.**

---

## 🚨 THE PROBLEM

### Hugging Face Limits:
```
Files per folder:      < 10,000 recommended
Total files per repo:  < 100,000 recommended
Large-scale handling:  Use WebDataset or Parquet, NOT individual files
```

### Your Scale:
```
22,000 jurisdictions × 1,000 documents each = 22 MILLION files
❌ This would BREAK Hugging Face limits!
```

---

## ✅ THE SOLUTION: PARQUET FORMAT

**Instead of uploading 22 million PDFs, store extracted data in Parquet files.**

### Why Parquet?

1. ✅ **Efficient** - Columnar storage, highly compressed
2. ✅ **Scalable** - Handle millions of rows in single file
3. ✅ **Fast** - Optimized for filtering and querying
4. ✅ **Native** - Hugging Face Datasets uses Parquet internally
5. ✅ **Small** - 10-100x smaller than individual files

### Size Comparison:

```
❌ Bad: 22 million PDF files (30 TB)
   - Exceeds 100k file limit by 220x
   - Slow to upload/download
   - Impossible to manage

✅ Good: 220 Parquet files (25 GB compressed)
   - 1 file per jurisdiction type per state
   - Fast to query
   - Easy to manage
   - Within all limits
```

---

## 📊 RECOMMENDED STRUCTURE

### Option 1: Parquet Files (RECOMMENDED)

**Store all text content in Parquet tables:**

```python
import pandas as pd
from datasets import Dataset

# Instead of storing individual PDFs...
# Store rows in a DataFrame

meetings_data = []

for jurisdiction in all_jurisdictions:
    for meeting in jurisdiction.meetings:
        meetings_data.append({
            'jurisdiction_name': 'Tuscaloosa',
            'state': 'AL',
            'meeting_date': '2025-03-15',
            'meeting_title': 'City Council Regular Meeting',
            'agenda_text': 'extracted text from PDF...',  # ← TEXT, not PDF bytes
            'minutes_text': 'extracted minutes...',
            'video_url': 'https://youtube.com/watch?v=...',  # ← LINK, not video
            'source_url': 'https://tuscaloosaal.suiteonemedia.com/agenda.pdf',
            'keywords_found': ['fluoride', 'dental'],
            'is_oral_health_related': True
        })

# Convert to DataFrame
df = pd.DataFrame(meetings_data)

# Save as Parquet (highly compressed)
df.to_parquet('meetings_all.parquet', compression='snappy')

# Upload to Hugging Face
dataset = Dataset.from_pandas(df)
dataset.push_to_hub("username/oral-health-policy-data", split="meetings")
```

**File structure on Hugging Face:**
```
your-dataset/
├── discovery.parquet          # 1 file, ~1 GB (22k jurisdictions)
├── meetings.parquet           # 1 file, ~10 GB (500k meetings)
├── oral_health.parquet        # 1 file, ~2 GB (50k relevant docs)
└── README.md

Total: 3 files, 13 GB ✅ (vs 22 million files, 30 TB ❌)
```

---

## 🎯 CORRECT WORKFLOW

### ❌ WRONG: Download & Upload PDFs

```python
# DON'T DO THIS!
for jurisdiction in all_jurisdictions:
    for meeting in get_meetings(jurisdiction):
        # Download PDF
        pdf_bytes = download_pdf(meeting.pdf_url)
        
        # Upload to Hugging Face
        upload_file(pdf_bytes, f"pdfs/{jurisdiction}/{meeting.id}.pdf")
        # ❌ Results in 22 million files!
```

### ✅ CORRECT: Extract & Store Text in Parquet

```python
# DO THIS!
import pandas as pd
from PyPDF2 import PdfReader
import io

all_meetings = []

for jurisdiction in all_jurisdictions:
    for meeting in get_meetings(jurisdiction):
        # Download PDF temporarily
        pdf_bytes = download_pdf(meeting.pdf_url)
        
        # Extract text (don't store PDF!)
        pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        
        # Store metadata + text (not PDF bytes)
        all_meetings.append({
            'id': f"{jurisdiction.name}_{meeting.date}_{meeting.id}",
            'jurisdiction': jurisdiction.name,
            'state': jurisdiction.state,
            'date': meeting.date,
            'title': meeting.title,
            'text': text,  # ← Extracted text
            'source_pdf_url': meeting.pdf_url,  # ← Link to original
            'file_size_kb': len(pdf_bytes) // 1024,
            'page_count': len(pdf_reader.pages)
        })
        
        # Delete PDF immediately (free memory)
        del pdf_bytes

# Save all to single Parquet file
df = pd.DataFrame(all_meetings)
df.to_parquet('all_meetings.parquet', compression='snappy')

# Upload 1 file instead of 22 million!
from datasets import Dataset
dataset = Dataset.from_pandas(df)
dataset.push_to_hub("username/oral-health-meetings")
```

**Result:**
- ✅ 1 file (not 22 million)
- ✅ 10 GB (not 30 TB)
- ✅ Fast queries
- ✅ Easy downloads

---

## 📦 PARTITIONED PARQUET (For Very Large Datasets)

If you have 100+ GB of data, partition by state:

```python
import pandas as pd
from pathlib import Path

# Process state by state
for state in all_states:
    state_meetings = []
    
    for jurisdiction in get_jurisdictions(state):
        # Extract meetings for this jurisdiction
        meetings = process_jurisdiction(jurisdiction)
        state_meetings.extend(meetings)
    
    # Save one Parquet per state
    df = pd.DataFrame(state_meetings)
    df.to_parquet(f'meetings_{state}.parquet')

# Upload to Hugging Face with state-based splits
from datasets import Dataset, DatasetDict

dataset_dict = {}
for state_file in Path('.').glob('meetings_*.parquet'):
    state = state_file.stem.split('_')[1]
    df = pd.read_parquet(state_file)
    dataset_dict[state] = Dataset.from_pandas(df)

# Upload all states
datasets = DatasetDict(dataset_dict)
datasets.push_to_hub("username/oral-health-meetings")
```

**File structure:**
```
your-dataset/
├── AL/
│   └── data-00000-of-00001.parquet  # Alabama meetings
├── CA/
│   └── data-00000-of-00001.parquet  # California meetings
├── TX/
│   └── data-00000-of-00001.parquet  # Texas meetings
...
└── README.md

Total: 50 files (one per state) ✅
```

**Load specific state:**
```python
# Only download Alabama data
al_data = load_dataset("username/oral-health-meetings", split="AL")
```

---

## 🗜️ COMPRESSION COMPARISON

### Parquet Compression:

```python
# Same data, different compression

df.to_parquet('meetings.parquet', compression='snappy')  # Fast, good compression
# Size: 8 GB

df.to_parquet('meetings.parquet', compression='gzip')    # Slower, better compression
# Size: 5 GB

df.to_parquet('meetings.parquet', compression='brotli')  # Slowest, best compression
# Size: 3 GB
```

**Recommendation:** Use `snappy` (default) - good balance of speed and size.

---

## 🔢 SIZE ESTIMATES

### Real Numbers for 22,000 Jurisdictions:

| Data Type | Storage Method | Files | Size |
|-----------|----------------|-------|------|
| **PDFs (raw)** | Individual files | 22M | 30 TB ❌ |
| **PDFs (text)** | Parquet | 50 | 25 GB ✅ |
| **Oral health subset** | Parquet | 1 | 5 GB ✅ |
| **Discovery results** | Parquet | 1 | 1 GB ✅ |

**Total storage needed: ~30 GB (not 30 TB!)** ✅

---

## 💡 ALTERNATIVE: WebDataset Format

For image-heavy or binary data, use WebDataset `.tar` files:

```python
import webdataset as wds

# Create sharded tar files
sink = wds.ShardWriter("meetings-%06d.tar", maxcount=10000)

for jurisdiction in all_jurisdictions:
    for meeting in jurisdiction.meetings:
        # Extract text from PDF
        text = extract_text(meeting.pdf_url)
        
        sink.write({
            "__key__": f"{jurisdiction.name}_{meeting.id}",
            "txt": text.encode('utf-8'),
            "json": json.dumps(meeting.metadata).encode('utf-8')
        })

sink.close()

# Results in:
# meetings-000000.tar (10k documents)
# meetings-000001.tar (10k documents)
# ...
# meetings-002200.tar (remaining documents)
# Total: ~2,200 tar files ✅ (under 10k file limit per folder)
```

---

## 🎯 RECOMMENDED APPROACH

### For Your Project:

**1. Store Metadata + Text in Parquet (Primary)**
```python
# Structure your data
meetings_df = pd.DataFrame({
    'id': [...],
    'jurisdiction': [...],
    'state': [...],
    'date': [...],
    'title': [...],
    'agenda_text': [...],      # Extracted text
    'minutes_text': [...],     # Extracted text
    'source_url': [...],       # Link to original PDF
    'video_url': [...],        # Link to YouTube
    'oral_health_keywords': [...]
})

# Save as Parquet
meetings_df.to_parquet('meetings.parquet', compression='snappy')

# Upload to Hugging Face (1 file, ~10 GB)
dataset = Dataset.from_pandas(meetings_df)
dataset.push_to_hub("username/oral-health-meetings")
```

**2. Partition by State (If >50 GB)**
```python
# One Parquet per state
for state in all_states:
    state_df = meetings_df[meetings_df['state'] == state]
    state_df.to_parquet(f'meetings_{state}.parquet')

# Upload with splits
dataset_dict = {...}  # Load each state
datasets.push_to_hub("username/oral-health-meetings")

# Total: 50 files (one per state) ✅
```

**3. Never Upload Individual PDFs**
```python
# ❌ NEVER do this
for pdf in all_pdfs:
    upload_file(pdf)  # Results in millions of files

# ✅ ALWAYS do this
text = extract_text(pdf)
df.append({'text': text, 'source_url': pdf_url})
df.to_parquet('data.parquet')  # One file
```

---

## 📚 UPDATED UPLOAD SCRIPT

```python
#!/usr/bin/env python3
"""
Correctly upload large-scale data to Hugging Face using Parquet format.
"""

import pandas as pd
from datasets import Dataset
from huggingface_hub import login
from PyPDF2 import PdfReader
import io

def process_and_upload_correct_way():
    """Process jurisdictions and upload as Parquet (not individual files)."""
    
    all_meetings = []
    
    # Process all jurisdictions
    for jurisdiction in all_jurisdictions:
        print(f"Processing {jurisdiction.name}...")
        
        for agenda_url in jurisdiction.agenda_urls:
            # Download PDF temporarily
            pdf_bytes = download_pdf(agenda_url)
            
            # Extract text
            pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
            text = "\n".join(page.extract_text() for page in pdf_reader.pages)
            
            # Store metadata + text (NOT PDF bytes)
            all_meetings.append({
                'jurisdiction': jurisdiction.name,
                'state': jurisdiction.state,
                'date': extract_date(text),
                'text': text,
                'source_url': agenda_url,
                'page_count': len(pdf_reader.pages)
            })
            
            # Delete PDF immediately
            del pdf_bytes
            
            # Keep local storage low!
    
    # Convert to DataFrame
    df = pd.DataFrame(all_meetings)
    
    # Save as Parquet (compressed)
    df.to_parquet('all_meetings.parquet', compression='snappy')
    
    print(f"Total meetings: {len(df)}")
    print(f"File size: {Path('all_meetings.parquet').stat().st_size / 1e9:.2f} GB")
    
    # Upload to Hugging Face (1 file instead of millions!)
    dataset = Dataset.from_pandas(df)
    dataset.push_to_hub("username/oral-health-meetings")
    
    print("✅ Uploaded 1 Parquet file containing all meetings!")
```

---

## ✅ SUMMARY

### Do This:
1. ✅ Extract text from PDFs (don't store PDF bytes)
2. ✅ Store in Parquet format (1-50 files total)
3. ✅ Link to original sources (not duplicate content)
4. ✅ Compress with snappy
5. ✅ Partition by state if >50 GB

### Don't Do This:
1. ❌ Upload individual PDFs (millions of files)
2. ❌ Store video files (link to YouTube)
3. ❌ Duplicate raw content
4. ❌ Exceed 100k file limit
5. ❌ Use uncompressed formats

### Result:
- **22 million files → 50 files** ✅
- **30 TB → 30 GB** ✅
- **Slow uploads → Fast uploads** ✅
- **Hard to manage → Easy to manage** ✅
- **Expensive → FREE** ✅

**You can store ALL 22,000 jurisdictions in ~50 Parquet files totaling 30 GB!**
