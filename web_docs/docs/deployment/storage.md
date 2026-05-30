---
sidebar_position: 16
---

# 💰 COST-EFFECTIVE STORAGE STRATEGY (Personal Budget)

**TL;DR: Use Hugging Face Datasets - it's FREE and unlimited for public data!**

---

## 🎯 THE PROBLEM

**Challenge:**
- Need to process 22,000+ jurisdictions
- Each jurisdiction has: agendas, minutes, videos, social media
- Estimated total: **10-50 TB** of raw content
- Limited local storage + personal budget

**Solution: Don't store everything locally!**

---

## ✅ RECOMMENDED STRATEGY: HUGGING FACE DATASETS

### Why Hugging Face?

1. **🆓 FREE** - Unlimited storage for public datasets
2. **🌐 Cloud-based** - No local storage needed
3. **📊 Versioned** - Git-based dataset management
4. **🔍 Searchable** - Built-in search and filtering
5. **🤝 Shareable** - Public datasets help research community
6. **⚡ Fast** - Optimized for large datasets

### ⚠️ CRITICAL: File Limits

**Hugging Face has repository limits:**
- Files per folder: \<10,000
- Total files per repo: \<100,000
- Large datasets: Use Parquet or WebDataset format

**Your scale (22M files) exceeds limits!**

**Solution: Use Parquet format**
- 22 million PDFs → 50 Parquet files ✅
- See detailed guide: [HUGGINGFACE_FILE_LIMITS.md](HUGGINGFACE_FILE_LIMITS.md)

### What to Store

**Store ONLY processed/filtered data, not raw content:**

✅ **Store:**
- Extracted text from PDFs
- Meeting metadata (date, title, URL)
- Oral health-related snippets
- Social media links
- Discovery results (JSON)

❌ **Don't Store:**
- Full video files (link to YouTube instead)
- Full PDF files (store text + source URL)
- Website HTML dumps
- Duplicate content

---

## 📊 STORAGE ESTIMATES

### Raw Content (DON'T download all):
```
Videos:        5,000 channels × 100 videos × 500 MB = 250 TB  ❌
PDFs:          15,000 jurisdictions × 1,000 docs × 2 MB = 30 TB  ❌
Social media:  18,000 accounts × archives = 5 TB  ❌
TOTAL RAW:     ~285 TB  🚫 TOO EXPENSIVE!
```

### Processed Content (Hugging Face approach):
```
Discovery data:     22,000 jurisdictions × 50 KB = 1.1 GB  ✅
Meeting metadata:   500,000 meetings × 5 KB = 2.5 GB  ✅
Extracted text:     500,000 docs × 50 KB = 25 GB  ✅
Oral health subset: 50,000 relevant docs × 100 KB = 5 GB  ✅
TOTAL PROCESSED:    ~34 GB  ✅ TOTALLY FREE on Hugging Face!
```

**Savings: 285 TB → 34 GB = 99.99% reduction!**

---

## 🚀 STEP-BY-STEP: HUGGING FACE WORKFLOW

### Step 1: Create Free Hugging Face Account

```bash
# Sign up at https://huggingface.co/join
# Create account (FREE)
# Get your access token from https://huggingface.co/settings/tokens
```

### Step 2: Install Hugging Face Libraries

```bash
pip install huggingface_hub datasets
```

### Step 3: Create Your Dataset

```python
from huggingface_hub import HfApi, create_repo
from datasets import Dataset
import pandas as pd

# Login
from huggingface_hub import login
login(token="hf_YOUR_TOKEN")  # Get from https://huggingface.co/settings/tokens

# Create dataset repository
repo_name = "oral-health-policy-data"
create_repo(
    repo_id=f"your-username/{repo_name}",
    repo_type="dataset",
    private=False  # Public = FREE unlimited storage!
)

# Upload discovery results
df = pd.read_csv('data/bronze/discovered_sources/discovery_summary_final.csv')
dataset = Dataset.from_pandas(df)
dataset.push_to_hub(f"your-username/{repo_name}", split="discovery")

print("✅ Dataset uploaded to Hugging Face!")
print(f"View at: https://huggingface.co/datasets/your-username/{repo_name}")
```

### Step 4: Process-and-Upload Pipeline

**DON'T download everything locally first!**

Instead, use this streaming approach:

```python
import httpx
import tempfile
from pathlib import Path

async def process_jurisdiction_streaming(jurisdiction):
    """
    Process jurisdiction WITHOUT storing locally:
    1. Download agenda PDF
    2. Extract text
    3. Filter for oral health keywords
    4. Upload to Hugging Face
    5. Delete local file
    """
    
    results = []
    
    # Get agenda portal URLs
    agendas = jurisdiction['agenda_portals']
    
    for agenda_url in agendas:
        # Download to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            async with httpx.AsyncClient() as client:
                response = await client.get(agenda_url)
                tmp.write(response.content)
                tmp_path = tmp.name
        
        # Extract text (using PyPDF2 or similar)
        text = extract_text_from_pdf(tmp_path)
        
        # Filter for oral health content
        keywords = ['fluoride', 'dental', 'oral health', 'water treatment']
        if any(kw in text.lower() for kw in keywords):
            results.append({
                'jurisdiction': jurisdiction['name'],
                'state': jurisdiction['state'],
                'url': agenda_url,
                'text': text,
                'date': extract_date(text),
                'relevant': True
            })
        
        # Delete local file immediately
        Path(tmp_path).unlink()
    
    # Upload batch to Hugging Face
    if results:
        upload_to_huggingface(results)
    
    return len(results)
```

---

## 💡 COST BREAKDOWN: FREE OPTIONS

### Option 1: Hugging Face (RECOMMENDED)

| Item | Cost | Storage |
|------|------|---------|
| **Public datasets** | **FREE** | **UNLIMITED** |
| Private datasets | FREE | 100 GB |
| Bandwidth | FREE | Unlimited downloads |
| Processing | FREE | Use local computer |

**Total: $0/month** ✅

### Option 2: GitHub + Hugging Face

| Item | Cost | Storage |
|------|------|---------|
| GitHub (discovery data) | FREE | 1 GB |
| Hugging Face (processed text) | FREE | Unlimited |
| GitHub LFS (large files) | $5/month | 50 GB |

**Total: $0-5/month** ✅

### Option 3: Cloud Storage (if needed)

**Only for temporary processing:**

| Provider | Free Tier | After Free Tier |
|----------|-----------|-----------------|
| **AWS S3** | 5 GB for 12 months | $0.023/GB/month |
| **Google Cloud** | 5 GB always free | $0.020/GB/month |
| **Azure Blob** | 5 GB for 12 months | $0.018/GB/month |

**Cost for 34 GB:** ~$0.60/month ✅

---

## 🎯 RECOMMENDED WORKFLOW

### Phase 1: Discovery (Run Locally)

```bash
# Run discovery for all jurisdictions
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --all

# Output: ~1 GB of JSON/CSV (fits on laptop!)
# Upload to Hugging Face immediately
```

### Phase 2: Content Processing (Stream & Upload)

```python
# For each jurisdiction:
for jurisdiction in all_jurisdictions:
    # 1. Download one PDF
    pdf = download_pdf(jurisdiction.agenda_url)
    
    # 2. Extract text
    text = extract_text(pdf)
    
    # 3. Check if oral health-related
    if is_relevant(text):
        # 4. Upload to Hugging Face
        upload_to_hf(text, metadata)
    
    # 5. Delete local file
    delete(pdf)
    
    # Local storage stays at ~100 MB (just temp files)!
```

**Your laptop never stores more than a few hundred MB!**

### Phase 3: Analysis (Cloud or Local)

```python
# Download ONLY relevant subset from Hugging Face
from datasets import load_dataset

# Load just oral health documents
dataset = load_dataset("your-username/oral-health-policy-data", split="relevant")

# This might be only 5 GB (totally manageable!)
print(f"Total documents: {len(dataset)}")

# Analyze locally or in Colab (FREE GPU!)
```

---

## 🆓 FREE RESOURCES YOU CAN USE

### 1. Hugging Face Datasets
- **Storage:** Unlimited (public datasets)
- **Cost:** FREE
- **Use:** Primary storage for all processed data

### 2. Google Colab
- **Compute:** FREE GPU/TPU (15 GB RAM)
- **Cost:** FREE (or $10/month for Pro)
- **Use:** Process PDFs, run analysis
- **Storage:** 15 GB on Google Drive (FREE)

### 3. GitHub
- **Storage:** 1 GB (100 GB with LFS for $5/month)
- **Cost:** FREE for public repos
- **Use:** Code + discovery results

### 4. Internet Archive (archive.org)
- **Storage:** Unlimited (for public documents)
- **Cost:** FREE
- **Use:** Mirror government documents

---

## 📦 SAMPLE: UPLOAD TO HUGGING FACE

### Create Upload Script

```python
#!/usr/bin/env python3
"""
upload_to_huggingface.py - Stream processed data to Hugging Face
"""

from datasets import Dataset, DatasetDict
from huggingface_hub import login
import pandas as pd
from pathlib import Path

# Configuration
HF_TOKEN = "hf_YOUR_TOKEN"  # From https://huggingface.co/settings/tokens
HF_REPO = "your-username/oral-health-policy-data"

def upload_discovery_results():
    """Upload discovery results (JSON/CSV)"""
    
    login(token=HF_TOKEN)
    
    # Load discovery data
    discovery_dir = Path("data/bronze/discovered_sources")
    
    # Load all discovery CSVs
    all_data = []
    for csv_file in discovery_dir.glob("*.csv"):
        df = pd.read_csv(csv_file)
        all_data.append(df)
    
    # Combine and upload
    combined = pd.concat(all_data, ignore_index=True)
    dataset = Dataset.from_pandas(combined)
    
    dataset.push_to_hub(HF_REPO, split="discovery")
    
    print(f"✅ Uploaded {len(combined)} jurisdictions to Hugging Face")
    print(f"View at: https://huggingface.co/datasets/{HF_REPO}")

def upload_meeting_data(meetings_df):
    """Upload processed meeting data"""
    
    # Convert to dataset
    dataset = Dataset.from_pandas(meetings_df)
    
    # Upload
    dataset.push_to_hub(HF_REPO, split="meetings")
    
    print(f"✅ Uploaded {len(meetings_df)} meetings")

def upload_oral_health_subset(filtered_df):
    """Upload filtered oral health content"""
    
    dataset = Dataset.from_pandas(filtered_df)
    dataset.push_to_hub(HF_REPO, split="oral_health")
    
    print(f"✅ Uploaded {len(filtered_df)} oral health documents")

if __name__ == "__main__":
    upload_discovery_results()
```

### Run Upload

```bash
# Set your token
export HF_TOKEN="hf_YOUR_TOKEN"

# Upload discovery results
python scripts/upload_to_huggingface.py

# View your dataset
# https://huggingface.co/datasets/your-username/oral-health-policy-data
```

---

## 💰 TOTAL COST ESTIMATE

### Personal Budget Approach (RECOMMENDED)

| Component | Cost | Notes |
|-----------|------|-------|
| **Hugging Face** | **$0/month** | Public datasets = FREE |
| **Local computer** | $0/month | Use your laptop |
| **Internet** | $0/month | Use existing connection |
| **Google Colab** | $0/month | FREE tier (or $10/month Pro) |
| **GitHub** | $0/month | Public repos FREE |
| **TOTAL** | **$0/month** | ✅ **100% FREE!** |

### Professional Approach (if scaling up)

| Component | Cost | Notes |
|-----------|------|-------|
| Hugging Face Pro | $9/month | Faster processing |
| Google Colab Pro | $10/month | More GPU time |
| AWS S3 (50 GB) | $1/month | Temporary storage |
| **TOTAL** | **$20/month** | Still very affordable |

---

## 🎓 REAL EXAMPLE: MeetingBank Dataset

**Existing dataset on Hugging Face:**
- Name: `huuuyeah/meetingbank`
- Size: 1,366 meetings, 121 MB
- Cost: FREE
- Link: https://huggingface.co/datasets/huuuyeah/meetingbank

**You can do the same for oral health policy!**

```python
# Load existing MeetingBank data (FREE)
from datasets import load_dataset

meetingbank = load_dataset("huuuyeah/meetingbank")
print(f"Meetings: {len(meetingbank['train'])}")

# Create YOUR oral health dataset (also FREE!)
your_dataset = create_oral_health_dataset()
your_dataset.push_to_hub("your-username/oral-health-meetings")
```

---

## ✅ ACTION PLAN FOR YOU

### Week 1: Setup (Cost: $0)

1. ✅ Create Hugging Face account (FREE)
2. ✅ Get API token
3. ✅ Install libraries: `pip install huggingface_hub datasets`
4. ✅ Create dataset repo: `oral-health-policy-data`

### Week 2: Discovery (Cost: $0)

1. Run discovery pipeline for all 22,000 jurisdictions
2. Upload discovery results to Hugging Face (~1 GB)
3. Free up local storage

### Week 3-4: Content Processing (Cost: $0)

1. Process jurisdictions one at a time (streaming)
2. Extract text from PDFs
3. Filter for oral health keywords
4. Upload to Hugging Face
5. Delete local files immediately

**Local storage never exceeds 1 GB!**

### Ongoing: Analysis (Cost: $0)

1. Download relevant subset from Hugging Face
2. Analyze using Google Colab (FREE GPU)
3. Publish findings back to Hugging Face

---

## 🔑 KEY PRINCIPLES

**1. Process, Don't Store**
- Download → Process → Upload → Delete
- Never keep raw files locally

**2. Filter Early**
- Only save oral health-related content
- Discard irrelevant documents immediately

**3. Use Text, Not Files**
- Store extracted text (KB), not PDFs (MB)
- Link to original sources instead of duplicating

**4. Leverage Free Platforms**
- Hugging Face for datasets (FREE)
- Google Colab for processing (FREE)
- GitHub for code (FREE)

**5. Make It Public**
- Public datasets = unlimited FREE storage
- Helps other researchers
- Builds your portfolio

---

## 📚 ADDITIONAL FREE RESOURCES

### Processing Tools (FREE)

```bash
# PDF text extraction
pip install pypdf2 pdfplumber

# Document processing
pip install beautifulsoup4 lxml

# Data handling
pip install pandas pyarrow

# Upload to Hugging Face
pip install huggingface_hub datasets
```

### Computing (FREE)

1. **Google Colab** - FREE GPU/TPU
   - https://colab.research.google.com/
   - 15 GB RAM, 100 GB disk (temporary)

2. **Kaggle Notebooks** - FREE GPU
   - https://www.kaggle.com/code
   - 20 GB RAM, 73 GB disk (temporary)

3. **Hugging Face Spaces** - FREE hosting
   - https://huggingface.co/spaces
   - Run demos and apps

---

## 🎯 BOTTOM LINE

**YOU CAN DO THIS FOR $0/MONTH!**

✅ **Storage:** Hugging Face (FREE, unlimited)  
✅ **Processing:** Local computer or Google Colab (FREE)  
✅ **Code:** GitHub (FREE)  
✅ **Analysis:** Google Colab (FREE GPU)

**The entire 22,000-jurisdiction discovery and analysis can be done on a personal budget with ZERO cloud storage costs!**

---

## 📞 NEXT STEPS

1. **Create Hugging Face account:** https://huggingface.co/join
2. **Create your dataset repo:** `oral-health-policy-data`
3. **Run discovery pipeline** (outputs ~1 GB locally)
4. **Upload to Hugging Face** (FREE unlimited storage)
5. **Process content streaming** (never store >100 MB locally)

**Questions?** Check Hugging Face docs: https://huggingface.co/docs/datasets/
