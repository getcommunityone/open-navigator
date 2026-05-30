# 🚀 QUICK START: FREE STORAGE WITH HUGGING FACE

**TL;DR: Store unlimited data for FREE on Hugging Face!**

**⚠️ IMPORTANT: Use Parquet format, NOT individual PDFs! See [file limits guide](HUGGINGFACE_FILE_LIMITS.md)**

---

## ⚡ 3-MINUTE SETUP

### 1. Create Hugging Face Account (1 minute)
```bash
# Go to https://huggingface.co/join
# Sign up (FREE)
# Verify email
```

### 2. Get API Token (1 minute)
```bash
# Go to https://huggingface.co/settings/tokens
# Click "New token"
# Name it "oral-health-upload"
# Token Type: Write (required for publishing datasets)
# Repository permissions: All repositories
# Copy the token (hf_xxxxxxxxxxxx)
```

**⚠️ Important: Token Permissions**
- **Write** access required for publishing datasets
- **Read** access sufficient for downloading public datasets only
- For this project: Use **Write** token to publish your scraped data

### 3. Install & Login (1 minute)
```bash
pip install huggingface_hub datasets

# Set your token
export HF_TOKEN="hf_YOUR_TOKEN_HERE"
```

---

## ⚠️ CRITICAL: FILE LIMITS

**Hugging Face Limits:**
- Files per folder: \<10,000
- Total files per repo: \<100,000
- For large datasets: Use Parquet or WebDataset format

**Your Scale:**
- 22,000 jurisdictions × 1,000 docs = 22 MILLION files ❌

**Solution:**
- Extract text from PDFs
- Store in Parquet format
- Result: 50 files instead of 22 million ✅

**See detailed guide:** [HUGGINGFACE_FILE_LIMITS.md](HUGGINGFACE_FILE_LIMITS.md)

---

## 📤 UPLOAD YOUR DATA

### Option 1: Use the Upload Script (Recommended)

**For discovery data:**

```bash
# Go to your project
cd /home/developer/projects/open-navigator

# Activate environment
source venv/bin/activate

# Upload discovery results
python scripts/upload_to_huggingface.py \
    --repo "YOUR_USERNAME/oral-health-policy-data" \
    --discovery

# View your dataset
# https://huggingface.co/datasets/YOUR_USERNAME/oral-health-policy-data
```

**For meeting PDFs (extract text first!):**

```bash
# DON'T upload individual PDFs!
# Instead, extract text and save as Parquet

# 1. Create a file with PDF URLs (one per line)
cat > pdf_urls.txt << EOF
https://tuscaloosaal.suiteonemedia.com/agenda1.pdf
https://tuscaloosaal.suiteonemedia.com/agenda2.pdf
...
EOF

# 2. Process PDFs to Parquet (extracts text, deletes PDFs)
python scripts/upload_to_huggingface.py \
    --repo "YOUR_USERNAME/oral-health-policy-data" \
    --process-pdfs pdf_urls.txt

# 3. Upload the Parquet file (1 file, not thousands!)
python scripts/upload_to_huggingface.py \
    --repo "YOUR_USERNAME/oral-health-policy-data" \
    --meetings meetings_processed.parquet
```

---

```python
from datasets import Dataset
from huggingface_hub import login
import pandas as pd

# Login
login(token="hf_YOUR_TOKEN")

# Load your data
df = pd.read_csv('data/bronze/discovered_sources/discovery_summary_final.csv')

# Convert to dataset
dataset = Dataset.from_pandas(df)

# Upload to Hugging Face (FREE!)
dataset.push_to_hub("YOUR_USERNAME/oral-health-policy-data", split="discovery")

print("✅ Data uploaded! View at:")
print("https://huggingface.co/datasets/YOUR_USERNAME/oral-health-policy-data")
```

---

## 💰 COST BREAKDOWN

| What You Get | Cost |
|--------------|------|
| **Unlimited storage** (public datasets) | **FREE** |
| Unlimited downloads | FREE |
| Built-in viewer | FREE |
| Version control | FREE |
| Search & filtering | FREE |
| API access | FREE |
| **TOTAL** | **$0/month** ✅ |

---

## 📊 STORAGE COMPARISON

### Bad Approach (Expensive)
```
❌ Download all videos: 250 TB = $5,000/month
❌ Store all PDFs: 30 TB = $600/month
❌ Total: $5,600/month 💸
```

### Good Approach (FREE)
```
✅ Store discovery data: 1 GB = FREE
✅ Store extracted text: 25 GB = FREE
✅ Store oral health subset: 5 GB = FREE
✅ Total: $0/month 🎉
```

**Savings: $5,600/month → $0/month**

---

## 🎯 WHAT TO UPLOAD

### ✅ Upload These:

1. **Discovery Results** (~1 GB)
   - Jurisdiction websites
   - YouTube channels
   - Meeting platforms
   - Social media links

2. **Meeting Metadata** (~2 GB)
   - Meeting dates/titles
   - Agenda item lists
   - Source URLs

3. **Extracted Text** (~25 GB)
   - Text from PDFs
   - Meeting transcripts
   - Filtered for oral health

### ❌ Don't Upload These:

1. **Videos** - Link to YouTube instead
2. **Full PDFs** - Store text + URL to original
3. **Website HTML** - Just store the data you extracted
4. **Duplicates** - Filter first

---

## 📝 EXAMPLE WORKFLOW

### Step 1: Run Discovery
```bash
# Discover all Alabama jurisdictions
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --state AL

# Output: data/bronze/discovered_sources/discovery_summary_AL.csv (~50 KB)
```

### Step 2: Upload to Hugging Face
```bash
# Upload discovery results
python scripts/upload_to_huggingface.py \
    --repo "YOUR_USERNAME/oral-health-policy-data" \
    --discovery
```

### Step 3: Free Up Local Space
```bash
# Optional: Delete local files (data is safely in cloud)
rm -rf data/bronze/discovered_sources/*.csv

# You can always download from Hugging Face later!
```

### Step 4: Share & Analyze
```python
# Anyone can now use your data (including you!)
from datasets import load_dataset

data = load_dataset("YOUR_USERNAME/oral-health-policy-data", split="discovery")
alabama = data.filter(lambda x: x['state'] == 'AL')

print(f"Alabama jurisdictions: {len(alabama)}")
```

---

## 🔄 CONTINUOUS WORKFLOW

### Keep Local Storage Low (~100 MB)

```python
# Process one jurisdiction at a time
for jurisdiction in all_jurisdictions:
    # 1. Download PDF (2 MB)
    pdf = download_agenda(jurisdiction)
    
    # 2. Extract text (50 KB)
    text = extract_text(pdf)
    
    # 3. Upload to Hugging Face
    upload_to_hf(text)
    
    # 4. Delete local file
    os.remove(pdf)
    
    # Local storage: Never exceeds 100 MB! ✅
```

---

## 📚 HUGGING FACE BASICS

### Load Your Data Anywhere

```python
from datasets import load_dataset

# Load on your laptop
data = load_dataset("YOUR_USERNAME/oral-health-policy-data")

# Or in Google Colab (FREE GPU)
# Or on a friend's computer
# Or 5 years from now

# Your data is always available, forever, for FREE!
```

### Search & Filter

```python
# Find cities with YouTube channels
with_youtube = data.filter(lambda x: x['youtube_channels'] > 0)

# Find high-quality sources
high_quality = data.filter(lambda x: x['completeness'] > 0.8)

# Find specific state
indiana = data.filter(lambda x: x['state'] == 'IN')
```

### Download Subset

```python
# Only download what you need (save bandwidth)
oral_health_only = load_dataset(
    "YOUR_USERNAME/oral-health-policy-data",
    split="oral_health"  # Only the filtered subset
)

# Maybe only 5 GB instead of 50 GB!
```

---

## ✅ BENEFITS

### 1. **FREE Unlimited Storage**
- No storage limits for public datasets
- No bandwidth limits
- No time limits

### 2. **Accessible Anywhere**
- Download from any computer
- Share with collaborators
- Use in Google Colab

### 3. **Version Control**
- Git-based system
- Track all changes
- Revert if needed

### 4. **Discovery**
- Your dataset appears in Hugging Face search
- Other researchers can use it
- Builds your portfolio

### 5. **Integration**
- Works with PyTorch, TensorFlow
- Built-in data viewer
- API access

---

## 🎓 LEARN MORE

### Official Docs
- **Hugging Face Datasets:** https://huggingface.co/docs/datasets/
- **Quick Start:** https://huggingface.co/docs/datasets/quickstart
- **Upload Guide:** https://huggingface.co/docs/datasets/upload_dataset

### Examples
- **MeetingBank:** https://huggingface.co/datasets/huuuyeah/meetingbank
- **Browse Datasets:** https://huggingface.co/datasets

---

## 🆘 TROUBLESHOOTING

### "Authentication failed"
```bash
# Make sure token is set
echo $HF_TOKEN

# If empty, set it
export HF_TOKEN="hf_YOUR_TOKEN"

# Or login interactively
huggingface-cli login
```

### "Permission denied"
```bash
# Make sure repo name includes your username
# ✅ Correct: "myusername/oral-health-policy-data"
# ❌ Wrong: "oral-health-policy-data"
```

### "Dataset too large"
```python
# Don't upload raw files!
# Upload processed/filtered data only

# ❌ Bad: Upload 50 GB of PDFs
# ✅ Good: Upload 5 GB of extracted text
```

---

## 🎯 NEXT STEPS

1. ✅ Create Hugging Face account
2. ✅ Get API token
3. ✅ Run discovery for your state
4. ✅ Upload to Hugging Face
5. ✅ Delete local files to free space
6. ✅ Scale to all 22,000+ jurisdictions!

**Your data is safe in the cloud, FREE, forever!** 🎉

---

## 💡 PRO TIP

Make your dataset **public** (not private):
- ✅ FREE unlimited storage
- ✅ Helps research community
- ✅ Builds your portfolio
- ✅ Appears in search results

Private datasets are limited to 100 GB and don't help anyone!

**Public = Win-Win-Win** 🏆
