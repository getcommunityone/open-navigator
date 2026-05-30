---
displayed_sidebar: developersSidebar
---

# ✅ Confirmed: HuggingFace Datasets That WILL Help

## Quick Answer: YES, 2 of 4 will help significantly!

| Dataset | Status | Usefulness | Priority |
|---------|--------|------------|----------|
| **MeetingBank** | ✅ **READY TO USE** | 🔥 **VERY HIGH** | **USE IMMEDIATELY** |
| **LocalView** | ✅ Already covered | HIGH | Download from Harvard |
| **Council Data Project** | ✅ Already covered | HIGH | Already integrated |
| **CivicBand** | ⚠️ Limited access | MEDIUM | Scrape municipality list |

---

## 1. MeetingBank 🔥 (NEW! USE THIS!)

### What It Is:
**A benchmark dataset from 6 major U.S. cities specifically designed for meeting summarization**

### URLs:
- **HuggingFace (text)**: https://huggingface.co/datasets/huuuyeah/meetingbank
- **HuggingFace (audio)**: https://huggingface.co/datasets/huuuyeah/MeetingBank_Audio
- **Zenodo (all files)**: https://zenodo.org/record/7989108
- **Archive.org (videos)**: 
  - https://archive.org/details/meetingbank-alameda
  - https://archive.org/details/meetingbank-boston
  - https://archive.org/details/meetingbank-denver
  - https://archive.org/details/meetingbank-long-beach
  - https://archive.org/details/meetingbank-king-county
  - https://archive.org/details/meetingbank-seattle

### What You Get:
✅ **1,366 city council meetings** from 6 cities:
   - Alameda, CA
   - Boston, MA
   - Denver, CO
   - King County, WA
   - Long Beach, CA
   - Seattle, WA

✅ **3,579 hours of video**

✅ **Full transcripts** (average 28,000 tokens per meeting)

✅ **PDF meeting minutes & agendas**

✅ **Human-written summaries** (ground truth for evaluation)

✅ **Machine-generated summaries** (from 6 different systems)

✅ **6,892 segment-level summarization instances** for training

### Why This Is PERFECT for Your Project:

1. **Immediate prototyping**: Download from HuggingFace in 5 minutes
   ```python
   from datasets import load_dataset
   meetingbank = load_dataset("huuuyeah/meetingbank")
   
   for instance in meetingbank['train']:
       print(instance['id'])
       print(instance['summary'])
       print(instance['transcript'])
   ```

2. **Quality validation**: Compare your AI summarization against human-written summaries

3. **URL discovery**: Each meeting has source URLs to city websites

4. **Benchmark your oral health keyword detection**: Test against 1,366 real transcripts

5. **Training data**: If you want to fine-tune models for oral health policy

### Paper:
"MeetingBank: A Benchmark Dataset for Meeting Summarization"  
ACL 2023 (Association for Computational Linguistics)  
https://arxiv.org/abs/2305.17529

### 🎯 ACTION PLAN:
```bash
# 1. Install HuggingFace datasets
pip install datasets

# 2. Download MeetingBank
python -c "
from datasets import load_dataset
meetingbank = load_dataset('huuuyeah/meetingbank')
print(f'Loaded {len(meetingbank['train'])} training instances')
"

# 3. Create discovery/meetingbank_ingestion.py
# - Parse meetings
# - Extract URLs
# - Load to Bronze layer
# - Run keyword detection on transcripts
# - Evaluate against human summaries
```

### Expected ROI:
- **Time**: 2 hours to integrate
- **Value**: 1,366 meetings with transcripts + summaries + URLs
- **Quality**: Academic benchmark (peer-reviewed, ACL published)
- **Coverage**: 6 major cities (all large, high-value for advocacy)

---

## 2. LocalView ✅ (Already Covered)

**Status**: Already identified in previous investigation  
**Location**: Harvard Dataverse (doi:10.7910/DVN/NJTBEM)  
**Coverage**: 1,000-10,000 jurisdictions  
**Action**: Download from Harvard (already documented)

---

## 3. Council Data Project ✅ (Already Covered)

**Status**: Already integrated in [`external_url_datasets.py`](../discovery/external_url_datasets.py)  
**Coverage**: 20+ cities with full pipelines  
**Action**: Already coded, just run the script

---

## 4. CivicBand ⚠️ (Limited Usefulness)

### What It Is:
"Largest public collection of civic meeting and election finance data"  
Website: https://civic.band/

### What Exists:
✅ **1,031 municipalities tracked**  
✅ Millions of pages scraped (meeting minutes, agendas)  
✅ Search interface available  
✅ Publicly browsable

### The Problem:
❌ **"Dataset access is via their platform; raw dumps require coordination"**
- Can't directly download bulk URL list
- Would need to contact founder (Philip James: hello@civic.band)
- Or scrape the municipality list from their website

### What You CAN Get:
The list of 1,031 municipalities is publicly visible on their site. You could:

1. **Scrape the municipality list** (city names + states)
2. **Match against your Census data** to get FIPS codes
3. **Use as verification** (these 1,031 are confirmed to have meeting data)

### Limited Value Because:
- Can't get direct URLs (need to coordinate with founder)
- Already have larger coverage from LocalView (1,000-10,000 jurisdictions)
- Already have premium coverage from CDP (20 cities)
- CivicBand's main value is their *content* (scraped minutes), not URLs

### Possible Action:
```python
# Scrape CivicBand's municipality list
import requests
from bs4 import BeautifulSoup

response = requests.get("https://civic.band/")
soup = BeautifulSoup(response.text, 'html.parser')

# Parse the table of municipalities
# Match against Census data
# Use as validation list
```

**Estimated value**: MEDIUM (validation only, not bulk URLs)

---

## 📊 Revised Priority Ranking

### IMMEDIATE (Do This Week):
1. 🔥 **Download MeetingBank** (2 hours)
   - HuggingFace dataset ready to use
   - 1,366 meetings with transcripts, summaries, URLs
   - Perfect for prototyping and evaluation

### HIGH PRIORITY (Do This Month):
2. ✅ **Download LocalView** (1 day)
   - Harvard Dataverse
   - 1,000-10,000 jurisdictions

3. ✅ **Run CDP integration** (2 hours)
   - Already coded
   - 20 premium cities

### MEDIUM PRIORITY (Optional):
4. ⚠️ **Scrape CivicBand list** (4 hours)
   - 1,031 municipality names
   - Use for validation
   - Or contact founder for bulk access

---

## 🎯 Updated Integration Code

### Add MeetingBank to your pipeline:

```python
# discovery/meetingbank_ingestion.py

from datasets import load_dataset
from pyspark.sql import SparkSession
from loguru import logger

def load_meetingbank_to_bronze(spark: SparkSession) -> dict:
    """
    Load MeetingBank dataset to Bronze layer.
    
    MeetingBank contains 1,366 city council meetings from 6 major cities
    with full transcripts, summaries, and source URLs.
    """
    logger.info("Loading MeetingBank dataset from HuggingFace")
    
    # Download from HuggingFace
    meetingbank = load_dataset("huuuyeah/meetingbank")
    
    meetings = []
    
    for split in ['train', 'validation', 'test']:
        for instance in meetingbank[split]:
            meetings.append({
                "meeting_id": instance['id'],
                "jurisdiction_name": instance.get('city', 'Unknown'),
                "state_code": instance.get('state', 'Unknown'),
                "transcript": instance['transcript'],
                "summary_human": instance['summary'],
                "source_url": instance.get('url', ''),
                "date": instance.get('date', ''),
                "has_transcript": True,
                "has_summary": True,
                "has_url": bool(instance.get('url')),
                "transcript_length": len(instance['transcript']),
                "source": "meetingbank"
            })
    
    # Convert to DataFrame
    df = spark.createDataFrame(meetings)
    
    # Write to Bronze layer
    output_path = f"{settings.delta_lake_path}/bronze/meetingbank_meetings"
    df.write \
        .format("delta") \
        .mode("overwrite") \
        .save(output_path)
    
    logger.info(f"✅ Loaded {len(meetings)} meetings from MeetingBank")
    
    return {
        "total_meetings": len(meetings),
        "cities": 6,
        "source": "meetingbank"
    }
```

### Test your keyword detection:

```python
# Test keyword detection on MeetingBank transcripts
from datasets import load_dataset
from alerts.keyword_monitor import KeywordAlertSystem

meetingbank = load_dataset("huuuyeah/meetingbank")
alert_system = KeywordAlertSystem()

# Test on first 10 meetings
for instance in meetingbank['train'][:10]:
    matches = alert_system._find_keywords_in_text(
        instance['transcript'],
        alert_system.KEYWORD_CATEGORIES
    )
    
    if matches:
        print(f"Meeting {instance['id']}: {len(matches)} oral health keywords found")
        for match in matches[:3]:  # Show first 3
            print(f"  - {match.keyword} ({match.category})")
```

### Evaluate your AI summarization:

```python
# Compare your summaries against human-written ground truth
from extraction.summarizer import MeetingSummarizer
from datasets import load_dataset

summarizer = MeetingSummarizer()
meetingbank = load_dataset("huuuyeah/meetingbank")

for instance in meetingbank['test'][:10]:
    # Generate your summary
    your_summary = summarizer.summarize(
        event=None,  # Create MeetingEvent from instance
        full_text=instance['transcript'],
        focus_on_health=False
    )
    
    # Compare against human summary
    human_summary = instance['summary']
    
    print(f"Meeting: {instance['id']}")
    print(f"Your summary: {your_summary.executive_summary}")
    print(f"Human summary: {human_summary}")
    print(f"Quality: {your_summary.confidence_score}")
    print()
```

---

## 📈 Expected Outcomes

### Before MeetingBank:
- 76 URLs discovered (15% match rate)
- No evaluation benchmark
- No ground truth for summarization

### After MeetingBank:
- **+1,366 meetings** with transcripts
- **+6 major cities** with verified URLs
- **Academic benchmark** for evaluation
- **Human summaries** for quality validation
- **Total meetings**: 1,366 ready to analyze immediately

---

## 🚀 Final Recommendation

### DO THIS FIRST (2 hours):
```bash
# 1. Install HuggingFace datasets
pip install datasets

# 2. Download MeetingBank
python -c "
from datasets import load_dataset
meetingbank = load_dataset('huuuyeah/meetingbank')
print(f'✅ Downloaded {len(meetingbank[\"train\"])} meetings')
"

# 3. Create integration script
# See code example above

# 4. Test your keyword detection
# See test code above

# 5. Evaluate your summarization
# See evaluation code above
```

### Expected Result:
- **Immediate access** to 1,366 meetings
- **6 major cities** for prototyping
- **Academic quality** benchmark
- **Proven ROI**: Published in top NLP conference (ACL 2023)

---

## Summary Table

| Dataset | Available? | Download Time | Meetings | Usefulness |
|---------|-----------|---------------|----------|------------|
| **MeetingBank** | ✅ **YES** (HuggingFace) | **5 minutes** | **1,366** | 🔥 **VERY HIGH** |
| **LocalView** | ✅ YES (Harvard) | 1 day | 1,000-10,000 | 🔥 VERY HIGH |
| **CDP** | ✅ YES (already coded) | 2 hours | 20 cities | 🔥 HIGH |
| **CivicBand** | ⚠️ PARTIAL (need coordination) | 4 hours | 1,031 list | 🟡 MEDIUM |

**Bottom line**: MeetingBank is the fastest win! Download it today and start testing your summarization and keyword detection on real city council meeting transcripts.
