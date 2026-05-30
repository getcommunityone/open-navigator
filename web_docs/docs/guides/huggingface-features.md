# ✅ HuggingFace Dataset Sharing Added!

## What's New

You can now **publish your jurisdiction discovery datasets to HuggingFace Hub** for public sharing and collaboration!

---

## 🎯 New Capabilities

### 1. **HuggingFace Publisher Module**
- File: [pipeline/huggingface_publisher.py](../pipeline/huggingface_publisher.py)
- Publishes datasets to HuggingFace Hub
- Supports all discovery data layers (Bronze/Silver/Gold)

### 2. **CLI Command**
```bash
python main.py publish-to-hf --dataset all
```

### 3. **5 Publishable Datasets**
- `census-gid` - Census Bureau GID (90,735 jurisdictions)
- `gov-domains` - CISA .gov domains (15,000+)
- `nces-schools` - NCES school districts (13,000+)
- `discovered-urls` - Discovered URLs with metadata
- `scraping-targets` - Prioritized scraping targets

---

## 📦 Files Added/Updated

### New Files
- ✅ [pipeline/huggingface_publisher.py](../pipeline/huggingface_publisher.py) - HuggingFace publisher (~400 lines)
- ✅ [docs/HUGGINGFACE_PUBLISHING.md](HUGGINGFACE_PUBLISHING.md) - Complete publishing guide

### Updated Files
- ✅ [requirements.txt](../requirements.txt) - Added `datasets>=2.16.0` and `huggingface-hub>=0.20.0`
- ✅ [config/settings.py](../config/settings.py) - Added `huggingface_token`, `hf_organization`, `hf_dataset_prefix`
- ✅ [.env.example](../.env.example) - Added HuggingFace configuration
- ✅ [main.py](../main.py) - Added `publish-to-hf` CLI command
- ✅ [README.md](../README.md) - Added HuggingFace publishing section

---

## 🚀 Quick Start

### 1. Get HuggingFace Token

Visit: https://huggingface.co/settings/tokens

Create a **Write** token

### 2. Configure

Add to `.env`:
```bash
HF_TOKEN=hf_your_write_token_here
HF_ORGANIZATION=CommunityOne
HF_DATASET_PREFIX=oral-health-policy-pulse
```

### 3. Install Dependencies

```bash
pip install datasets huggingface-hub
```

### 4. Publish

```bash
# Publish all datasets
python main.py publish-to-hf --dataset all

# Or publish individually
python main.py publish-to-hf --dataset census
python main.py publish-to-hf --dataset discovered-urls
```

---

## 📊 What Gets Published

### Dataset URLs

Your datasets will be available at:
- https://huggingface.co/datasets/CommunityOne/oral-health-policy-pulse-census-gid
- https://huggingface.co/datasets/CommunityOne/oral-health-policy-pulse-gov-domains
- https://huggingface.co/datasets/CommunityOne/oral-health-policy-pulse-nces-schools
- https://huggingface.co/datasets/CommunityOne/oral-health-policy-pulse-discovered-urls
- https://huggingface.co/datasets/CommunityOne/oral-health-policy-pulse-scraping-targets

### Public Access

Anyone can load your datasets:

```python
from datasets import load_dataset

# Load census data
census = load_dataset("CommunityOne/oral-health-policy-pulse-census-gid")

# Load discovered URLs
urls = load_dataset("CommunityOne/oral-health-policy-pulse-discovered-urls")

# Access specific split
counties = census["counties"]
print(f"Total counties: {len(counties)}")
```

---

## 💡 Use Cases

### For Researchers
```python
# Analyze jurisdiction coverage
from datasets import load_dataset
import pandas as pd

census = load_dataset("CommunityOne/oral-health-policy-pulse-census-gid")
df = pd.DataFrame(census["municipalities"])

# Cities by state
df.groupby("state_name")["population"].sum().sort_values(ascending=False)
```

### For Civic Hackers
```python
# Get all county .gov domains
domains = load_dataset("CommunityOne/oral-health-policy-pulse-gov-domains")
counties = domains.filter(lambda x: x['Domain Type'] == 'County')
```

### For Data Scientists
```python
# High-confidence discovered URLs
urls = load_dataset("CommunityOne/oral-health-policy-pulse-discovered-urls")
high_conf = urls.filter(lambda x: x['confidence_score'] > 0.8)
```

---

## 🔄 Update Workflow

### After Each Discovery Run

```bash
# Run discovery
python main.py discover-jurisdictions

# Publish updated datasets
python main.py publish-to-hf --dataset discovered-urls
python main.py publish-to-hf --dataset scraping-targets
```

### Monthly Source Data Updates

```bash
# Re-ingest source data
python main.py discover-jurisdictions

# Publish refreshed datasets
python main.py publish-to-hf --dataset census
python main.py publish-to-hf --dataset gov-domains
python main.py publish-to-hf --dataset nces-schools
```

---

## 🎯 CLI Options

```bash
# Publish all datasets
python main.py publish-to-hf --dataset all

# Publish specific dataset
python main.py publish-to-hf --dataset census
python main.py publish-to-hf --dataset gov-domains
python main.py publish-to-hf --dataset nces-schools
python main.py publish-to-hf --dataset discovered-urls
python main.py publish-to-hf --dataset scraping-targets

# Make datasets private
python main.py publish-to-hf --dataset all --private

# Sample census data (faster for testing)
python main.py publish-to-hf --dataset census --sample
```

---

## 🔒 Privacy & Security

### What's Safe to Publish

✅ **Public Data:**
- Census Bureau GID (already public)
- CISA .gov domains (already public)
- NCES school districts (already public)
- Discovered government URLs (public websites)
- Scraping targets (public information)

⚠️ **Use `--private` for:**
- Scraped meeting minutes content
- Internal analysis results
- Custom annotations

❌ **Never Publish:**
- Personal information (PII)
- API keys or tokens
- Internal comments/notes

### Token Security

- Store token in `.env` file (gitignored)
- Use write token (not fine-grained)
- Revoke token if compromised

---

## 📚 Documentation

Complete guide: [HUGGINGFACE_PUBLISHING.md](HUGGINGFACE_PUBLISHING.md)

Covers:
- Detailed setup instructions
- Dataset structure and schemas
- Programmatic publishing in Python
- Loading datasets in Python/R
- Collaboration features
- Troubleshooting

---

## 🌍 Community Impact

**By publishing your datasets, you enable:**
- 📊 Reproducible research on government accessibility
- 🤝 Cross-project collaboration
- 🔍 Discovery of missing government websites
- 📈 Tracking government digital infrastructure over time
- 🎓 Educational use for civic tech training

**Your jurisdiction discovery data helps the entire civic tech community!** 🙏

---

## ✅ Benefits

| Feature | Before | After |
|---------|--------|-------|
| **Data Storage** | Local only | Local + HuggingFace Hub |
| **Data Sharing** | Manual export | One-command publish |
| **Collaboration** | Email/Dropbox | Public datasets w/ versioning |
| **Discovery** | None | Searchable on HuggingFace |
| **Access** | Your team only | Anyone worldwide |
| **Versioning** | Manual | Automatic Git-style tracking |

---

**Ready to share your jurisdiction discovery data with the world!** 🌍🦷✨
