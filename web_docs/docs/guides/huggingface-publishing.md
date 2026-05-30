# HuggingFace Dataset Publishing Guide

Share your jurisdiction discovery datasets and run outputs on HuggingFace Hub for public collaboration!

---

## 🎯 What Gets Published

### Available Datasets

| Dataset | Description | Size | Update Frequency |
|---------|-------------|------|------------------|
| **census-gid** | Census Bureau Government Integrated Directory | 90,735 jurisdictions | Annual |
| **gov-domains** | CISA .gov domain master list | 15,000+ domains | Daily* |
| **nces-schools** | NCES school district data | 13,000+ districts | Annual |
| **discovered-urls** | Discovered government URLs with metadata | Varies | Per run |
| **scraping-targets** | Prioritized scraping targets | Varies | Per run |

\* Daily on CISA side, you update as needed

---

## 🔧 Setup

### 1. Get HuggingFace Token

Visit: https://huggingface.co/settings/tokens

**Create a Write Token:**
1. Click "New token"
2. **Name:** "oral-health-policy-pulse-upload"
3. **Token type:** Write ⚠️ (required for publishing)
4. **Repository permissions:** All repositories
5. Copy the token (starts with `hf_`)

**Why Write Access?**
- Creates dataset repositories on HuggingFace
- Uploads Parquet files with your scraped data
- Updates dataset cards and metadata
- Read-only tokens cannot publish datasets

### 2. Configure Environment

Add to your `.env` file:

```bash
# HuggingFace Configuration
HF_TOKEN=hf_your_write_token_here
HF_ORGANIZATION=CommunityOne  # Optional: your org name
HF_DATASET_PREFIX=oral-health-policy-pulse
```

### 3. Install Dependencies

```bash
pip install datasets huggingface-hub
```

---

## 🚀 Publishing Datasets

### Publish All Datasets

```bash
python main.py publish-to-hf --dataset all
```

**Output:**
```
🚀 Publishing datasets to HuggingFace Hub...

📊 Published Datasets:
  ✓ census: https://huggingface.co/datasets/CommunityOne/oral-health-policy-pulse-census-gid
  ✓ gov_domains: https://huggingface.co/datasets/CommunityOne/oral-health-policy-pulse-gov-domains
  ✓ nces_schools: https://huggingface.co/datasets/CommunityOne/oral-health-policy-pulse-nces-schools
  ✓ discovered_urls: https://huggingface.co/datasets/CommunityOne/oral-health-policy-pulse-discovered-urls
  ✓ scraping_targets: https://huggingface.co/datasets/CommunityOne/oral-health-policy-pulse-scraping-targets

🎉 Publishing complete!
```

### Publish Individual Datasets

```bash
# Publish census data only
python main.py publish-to-hf --dataset census

# Publish discovered URLs
python main.py publish-to-hf --dataset discovered-urls

# Publish .gov domains
python main.py publish-to-hf --dataset gov-domains

# Publish school districts
python main.py publish-to-hf --dataset nces-schools

# Publish scraping targets
python main.py publish-to-hf --dataset scraping-targets
```

### Options

**Make datasets private:**
```bash
python main.py publish-to-hf --dataset all --private
```

**Sample census data (faster for testing):**
```bash
python main.py publish-to-hf --dataset census --sample
```

---

## 📦 Programmatic Publishing

Use the publisher directly in Python:

```python
from pipeline.huggingface_publisher import HuggingFacePublisher

# Initialize publisher
publisher = HuggingFacePublisher(token="hf_your_token")

# Publish specific dataset
result = publisher.publish_discovered_urls(private=False)
print(f"Published to: {result['url']}")

# Publish all datasets
results = publisher.publish_all(private=False, sample_census=False)
for name, info in results.items():
    print(f"{name}: {info['url']}")
```

---

## 🌐 Accessing Published Datasets

### View on HuggingFace Hub

Visit your dataset pages:
- https://huggingface.co/datasets/YOUR_ORG/oral-health-policy-pulse-census-gid
- https://huggingface.co/datasets/YOUR_ORG/oral-health-policy-pulse-gov-domains
- https://huggingface.co/datasets/YOUR_ORG/oral-health-policy-pulse-discovered-urls

### Load in Python

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

### Load in R

```r
library(datasets)

# Load dataset
census <- load_dataset("CommunityOne/oral-health-policy-pulse-census-gid")

# View data
head(census$counties)
```

### Access via API

```bash
curl https://datasets-server.huggingface.co/rows \
  -d dataset=CommunityOne/oral-health-policy-pulse-census-gid \
  -d config=counties \
  -d split=train
```

---

## 📊 Dataset Structure

### Census GID

**Splits:** `counties`, `municipalities`, `townships`, `school_districts`, `special_districts`

**Columns:**
- `jurisdiction_id`: Unique identifier
- `jurisdiction_name`: Official name
- `state_name`: State
- `county_name`: County (if applicable)
- `population`: Population count
- `fips_code`: FIPS code

### .gov Domains

**Single split:** `train`

**Columns:**
- `Domain Name`: Official .gov domain
- `Domain Type`: City, County, State, School District, etc.
- `Organization Name`: Government entity name
- `State`: State abbreviation

### Discovered URLs

**Single split:** `train`

**Columns:**
- `jurisdiction_id`: Link to jurisdiction
- `jurisdiction_name`: Government entity
- `state`: State
- `homepage_url`: Discovered homepage
- `minutes_url`: Meeting minutes page (if found)
- `discovery_method`: gsa_registry, pattern_match, not_found
- `confidence_score`: 0.0-1.0
- `cms_platform`: Granicus, CivicClerk, etc. (if detected)
- `last_verified`: Timestamp

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

### Monthly Updates

```bash
# Re-ingest source data
python main.py discover-jurisdictions --bronze-only

# Publish refreshed datasets
python main.py publish-to-hf --dataset census
python main.py publish-to-hf --dataset gov-domains
python main.py publish-to-hf --dataset nces-schools
```

---

## 📝 Dataset Cards

Each published dataset includes auto-generated metadata:

```yaml
dataset_info:
  features:
    - name: jurisdiction_name
      dtype: string
    - name: state
      dtype: string
  splits:
    - name: train
      num_examples: 90735
  
license: cc-by-4.0
task_categories:
  - text-classification
  - information-retrieval
language:
  - en
tags:
  - government
  - open-data
  - civic-tech
  - jurisdiction-discovery
  - oral-health-policy
```

---

## 🤝 Collaboration Features

### Dataset Discussions

Enable community discussions on your dataset pages for:
- Questions and answers
- Error reporting
- Feature requests
- Use case sharing

### Versioning

HuggingFace automatically tracks versions:
- Each push creates a new commit
- View version history on dataset page
- Pin to specific version in code:

```python
dataset = load_dataset(
    "CommunityOne/oral-health-policy-pulse-discovered-urls",
    revision="main"  # or specific commit hash
)
```

### Dataset Viewer

HuggingFace provides automatic dataset preview:
- Browse first 100 rows
- Filter and search
- Export to CSV/JSON
- Embed in documentation

---

## 💡 Best Practices

### Privacy Considerations

- ✅ **Public datasets:** Census, CISA, NCES data (already public)
- ✅ **Discovered URLs:** Government website URLs (public)
- ⚠️ **Scraped content:** Consider using `--private` flag
- ❌ **PII data:** Never publish personal information

### Storage Limits

- Free tier: Unlimited public datasets
- Size limit: ~100GB per dataset (contact HF for larger)
- Recommend splitting very large datasets

### Naming Conventions

Your datasets will be named:
```
{organization}/{prefix}-{dataset-name}

Examples:
  CommunityOne/oral-health-policy-pulse-census-gid
  CommunityOne/oral-health-policy-pulse-discovered-urls
```

---

## 🔍 Use Cases

**For Researchers:**
```python
# Load all discovered government URLs
urls = load_dataset("CommunityOne/oral-health-policy-pulse-discovered-urls")
high_confidence = urls.filter(lambda x: x['confidence_score'] > 0.8)
```

**For Civic Hackers:**
```python
# Get all .gov domains by type
domains = load_dataset("CommunityOne/oral-health-policy-pulse-gov-domains")
counties = domains.filter(lambda x: x['Domain Type'] == 'County')
```

**For Data Scientists:**
```python
# Analyze jurisdiction coverage
census = load_dataset("CommunityOne/oral-health-policy-pulse-census-gid")
import pandas as pd
df = pd.DataFrame(census["counties"])
df.groupby("state_name")["population"].sum()
```

---

## 🎯 Example: Complete Publishing Workflow

```bash
# 1. Run discovery
python main.py discover-jurisdictions --limit 1000

# 2. Check what you have
python main.py discovery-stats

# 3. Test publish with sample data
python main.py publish-to-hf --dataset census --sample --private

# 4. Publish public datasets
python main.py publish-to-hf --dataset all

# 5. View on HuggingFace
open https://huggingface.co/datasets/CommunityOne/oral-health-policy-pulse-discovered-urls
```

---

## 🆘 Troubleshooting

### Authentication Error

```
❌ Configuration error: HuggingFace token required
```

**Solution:** Set `HF_TOKEN` in `.env` file

### Repository Not Found

```
❌ Failed to create repo: 404 Not Found
```

**Solution:** 
- Check organization name in `.env`
- Verify token has write access
- Create organization on HuggingFace first

### Import Error

```
❌ HuggingFace libraries not installed!
```

**Solution:**
```bash
pip install datasets huggingface-hub
```

### Large Dataset Timeout

For very large datasets (>1M rows), publish in batches:

```python
publisher = HuggingFacePublisher()
publisher.publish_census_data(sample_size=100000)  # Publish 100k at a time
```

---

## 📚 Additional Resources

- **HuggingFace Datasets Docs:** https://huggingface.co/docs/datasets
- **Dataset Card Guide:** https://huggingface.co/docs/hub/datasets-cards
- **Hub Python Library:** https://huggingface.co/docs/huggingface_hub

---

**Ready to share your jurisdiction discovery data with the world!** 🌍🦷✨
