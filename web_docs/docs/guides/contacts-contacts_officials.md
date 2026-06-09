---
sidebar_position: 8
---

# Contacts & Officials Data

Extract and manage contact information for elected officials, government employees, and civic leaders.

## 🎯 Overview

The **Contacts system** provides structured data about people involved in civic engagement:
- **Local Officials**: Mayors, council members, commissioners (extracted from meeting transcripts)
- **State Legislators**: Representatives and senators (from Open States API)
- **School Board Members**: School district leadership

## 📊 Gold Tables

### contacts_local_officials.parquet

**Summary table** of unique officials with aggregate stats.

**Columns:**
- `name` - Full name (e.g., "Jerry Schultz")
- `title` - Position (Mayor, Council Member, Commissioner, etc.)
- `jurisdiction` - City/county name
- `meetings_count` - Number of meetings attended
- `source` - Extraction method (`roll_call` or `meeting_transcript`)
- `data_source` - "LocalView meeting transcripts"
- `last_updated` - Timestamp

**Use for**: Finding officials by jurisdiction, ranking by attendance

### contacts_meeting_attendance.parquet

**Detail table** linking officials to specific meetings (many-to-many junction table).

**Columns:**
- `meeting_id` - Links to `meetings_calendar.meeting_id`
- `name` - Official name
- `title` - Official title
- `jurisdiction` - City/county name
- `source` - Extraction method (`roll_call` or `meeting_transcript`)
- `last_updated` - Timestamp

**Use for**: Finding who attended a specific meeting, or which meetings an official attended

**Sample data:**
```python
from datasets import load_dataset

# Load attendance records
attendance = load_dataset("CommunityOne/one-contacts-meeting-attendance")
df = attendance['train'].to_pandas()

# Who attended meeting unknown_0?
meeting_officials = df[df['meeting_id'] == 'unknown_0']
print(meeting_officials[['name', 'title']])

# Which meetings did Jerry Schultz attend?
jerry_meetings = df[df['name'] == 'Jerry Schultz']
print(f"Jerry attended {len(jerry_meetings)} meetings")
```

### contacts_state_legislators.parquet

State-level elected officials from Open States API.

**Columns:**
- `name` - Full name
- `title` - Position (State Representative, State Senator)
- `jurisdiction` - State (e.g., "Alabama")
- `party` - Political party
- `district` - Legislative district
- `chamber` - upper or lower
- `email` - Contact email (if available)
- `phone` - Contact phone (if available)
- `data_source` - "Open States API"
- `last_updated` - Timestamp

### contacts_school_board.parquet

School board members and district leadership.

**Columns:**
- `name` - Full name
- `title` - Position (Board Member, Superintendent, etc.)
- `school_district` - District name
- `jurisdiction` - City/county
- `email` - Contact email (if available)
- `phone` - Contact phone (if available)
- `data_source` - Source of data
- `last_updated` - Timestamp

## 🚀 Quick Start

### Extract Contacts from Meetings

```bash
# Extract contacts from meeting transcripts
python scripts/create_all_gold_tables.py --meetings-only --extract-contacts
```

This will:
1. ✅ Load 153K+ meeting transcripts
2. 🔍 Extract official names using NLP patterns
3. 📊 Create `contacts_local_officials.parquet`

### Upload to HuggingFace

```bash
# Upload all contacts tables
export HF_TOKEN="hf_YOUR_TOKEN"
python -m hosting.huggingface contacts

# Or upload specific table
python scripts/upload_meetings_to_hf.py --table local_officials
```

## 🔍 Extraction Methods

### Roll Call Pattern (Most Accurate)

Detects roll call segments in transcripts:

```
call roll Jerry Schultz here Ted Nelson here Mike Barbour present
```

**Pattern**: `call roll [Name] [here|present|aye] [Name] [here|present]...`

### Title Pattern

Detects officials mentioned with titles:

```
Mayor Smith calls the meeting to order
Councilmember Johnson moves to approve
Commissioner Davis seconds
```

**Pattern**: `(Mayor|Councilmember|Commissioner) [Name]`

### Speaker Pattern

Detects speaker labels in formatted transcripts:

```
John Doe: Thank you Mr. Mayor...
Jane Smith: I second the motion
```

**Pattern**: `[Name]: [statement]`

## 📈 Data Quality

### Accuracy Metrics

- **Roll Call Extraction**: ~95% accuracy (high confidence)
- **Title Pattern**: ~85% accuracy (some false positives)
- **Speaker Pattern**: ~80% accuracy (varies by transcript format)

### Deduplication

Officials are deduplicated by `(name, jurisdiction)` pair:
- Multiple mentions → aggregated to single record
- `meetings_count` tracks attendance frequency
- `title` uses most common value (mode)

### False Positives Filtered

The system automatically filters:
- Common phrases (e.g., "City Council", "Good Evening")
- Incomplete names (single word only)
- Non-name patterns (e.g., "Item Number")

## 🔌 API Access

### Query via HuggingFace Datasets Server

```bash
# Get first 100 officials
curl "https://datasets-server.huggingface.co/rows?dataset=CommunityOne/one-contacts-local-officials&config=default&split=train&offset=0&length=100"

# Search for officials in specific city
curl "https://datasets-server.huggingface.co/search?dataset=CommunityOne/one-contacts-local-officials&config=default&split=train&query=League+City"
```

### Load in Python

```python
from datasets import load_dataset
import pandas as pd

# Load dataset
dataset = load_dataset("CommunityOne/one-contacts-local-officials")
df = pd.DataFrame(dataset['train'])

# Filter by jurisdiction
league_city = df[df['jurisdiction'] == 'League City']
print(f"League City officials: {len(league_city)}")

# Find most active officials
top_10 = df.nlargest(10, 'meetings_count')
print("\nMost Active Officials:")
print(top_10[['name', 'title', 'jurisdiction', 'meetings_count']])

# Filter by title
mayors = df[df['title'] == 'Mayor']
print(f"\nTotal mayors: {len(mayors)}")
```

### Load in JavaScript

```javascript
async function fetchOfficials(city) {
  const url = `https://datasets-server.huggingface.co/search?dataset=CommunityOne/one-contacts-local-officials&config=default&split=train&query=${encodeURIComponent(city)}`;
  
  const response = await fetch(url);
  const data = await response.json();
  
  return data.rows.map(row => ({
    name: row.row.name,
    title: row.row.title,
    meetingsCount: row.row.meetings_count
  }));
}

// Example: Get League City officials
const officials = await fetchOfficials('League City');
console.log(`Found ${officials.length} officials`);
```

## 🔗 Data Integration

### Link Officials to Meetings

```python
import pandas as pd

# Load attendance and meetings
attendance = pd.read_parquet('data/gold/contacts_meeting_attendance.parquet')
meetings = pd.read_parquet('data/gold/national/meetings_calendar.parquet')

# Join to get meeting details for each official
meeting_details = attendance.merge(
    meetings[['meeting_id', 'jurisdiction', 'record_index']], 
    on='meeting_id', 
    how='left',
    suffixes=('_official', '_meeting')
)

print(f"Linked {len(meeting_details)} attendance records to meetings")

# Find officials at a specific meeting
specific_meeting = attendance[attendance['meeting_id'] == 'unknown_0']
print(f"\nOfficials at meeting unknown_0:")
for _, official in specific_meeting.iterrows():
    print(f"  • {official['name']} ({official['title']})")

# Find meetings attended by a specific official
official_meetings = attendance[attendance['name'] == 'Jerry Schultz']
print(f"\nJerry Schultz attended {len(official_meetings)} meetings")
```

### Link Officials to Meeting Topics

```python
attendance = pd.read_parquet('data/gold/contacts_meeting_attendance.parquet')
topics = pd.read_parquet('data/gold/national/meetings_topics.parquet')

# Join attendance with topics
officials_topics = attendance.merge(
    topics[['meeting_id', 'topics']], 
    on='meeting_id', 
    how='left'
)

# Which officials attended health-related meetings?
health_meetings = officials_topics[
    officials_topics['topics'].str.contains('health', case=False, na=False)
]

print(f"Officials who attended health-related meetings:")
print(health_meetings.groupby('name').size().sort_values(ascending=False).head(10))
```

### Combine with Demographics

```python
demographics = pd.read_parquet('data/gold/national/meetings_demographics.parquet')

# Link officials to demographic context
officials_demo = officials.merge(
    demographics[['jurisdiction', 'acs_18_pop', 'acs_18_median_hh_inc']], 
    on='jurisdiction', 
    how='left'
)

# Analyze by jurisdiction size
small_cities = officials_demo[officials_demo['acs_18_pop'] < 50000]
large_cities = officials_demo[officials_demo['acs_18_pop'] >= 50000]

print(f"Small cities: {len(small_cities)} officials")
print(f"Large cities: {len(large_cities)} officials")
```

## 🎯 Use Cases

### Find Your Local Officials

```python
def find_my_officials(city_name):
    """Find all officials for a city"""
    df = pd.read_parquet('data/gold/contacts_local_officials.parquet')
    
    my_officials = df[df['jurisdiction'].str.contains(city_name, case=False)]
    
    print(f"Officials in {city_name}:")
    for _, official in my_officials.iterrows():
        print(f"  • {official['name']} - {official['title']}")
        print(f"    Meetings attended: {official['meetings_count']}")

find_my_officials("Tuscaloosa")
```

### Find Who Attended a Specific Meeting

```python
def find_meeting_attendees(meeting_id):
    """Find who attended a specific meeting"""
    attendance = pd.read_parquet('data/gold/contacts_meeting_attendance.parquet')
    
    attendees = attendance[attendance['meeting_id'] == meeting_id]
    
    print(f"Attendees at meeting {meeting_id}:")
    for _, official in attendees.iterrows():
        print(f"  • {official['name']} ({official['title']})")
    
    return attendees

# Example
find_meeting_attendees('unknown_0')
```

### Track Official's Meeting History

```python
def official_meeting_history(official_name):
    """Get all meetings attended by an official"""
    attendance = pd.read_parquet('data/gold/contacts_meeting_attendance.parquet')
    meetings = pd.read_parquet('data/gold/national/meetings_calendar.parquet')
    
    # Get official's meetings
    official_meetings = attendance[attendance['name'] == official_name]
    
    # Join with meeting details
    history = official_meetings.merge(
        meetings,
        on='meeting_id',
        how='left'
    )
    
    print(f"{official_name}'s Meeting History:")
    print(f"  Total meetings: {len(history)}")
    print(f"  Jurisdictions: {history['jurisdiction_x'].unique()}")
    
    return history

# Example
history = official_meeting_history('Jerry Schultz')
```

### Track Official Attendance

```python
def official_attendance_report(jurisdiction):
    """Generate attendance report for a jurisdiction"""
    df = pd.read_parquet('data/gold/contacts_local_officials.parquet')
    
    officials = df[df['jurisdiction'] == jurisdiction]
    
    avg_attendance = officials['meetings_count'].mean()
    max_attendance = officials['meetings_count'].max()
    
    print(f"\n{jurisdiction} Official Attendance Report:")
    print(f"  Total officials: {len(officials)}")
    print(f"  Average meetings: {avg_attendance:.1f}")
    print(f"  Max meetings: {max_attendance}")
    
    # Top 5 most active
    print(f"\n  Top 5 Most Active:")
    top_5 = officials.nlargest(5, 'meetings_count')
    for _, official in top_5.iterrows():
        print(f"    {official['name']} ({official['title']}): {official['meetings_count']} meetings")

official_attendance_report("League City")
```

### Build Contact Directory

```python
def create_contact_directory(state='TX'):
    """Create a contact directory for a state"""
    df = pd.read_parquet('data/gold/contacts_local_officials.parquet')
    
    # Would need to add state field - for now filter by jurisdiction pattern
    # This is a placeholder - actual implementation would need state data
    
    directory = df.groupby('jurisdiction').agg({
        'name': list,
        'title': list
    }).reset_index()
    
    return directory

directory = create_contact_directory()
print(f"Directory covers {len(directory)} jurisdictions")
```

## 🛠️ Advanced: Custom Extraction

### Add Custom Patterns

```python
from pipeline.create_contacts_gold_tables import ContactsGoldTableCreator

class CustomContactsCreator(ContactsGoldTableCreator):
    """Custom extraction with additional patterns"""
    
    def extract_officials_from_transcript(self, text, jurisdiction):
        # Get base extraction
        officials = super().extract_officials_from_transcript(text, jurisdiction)
        
        # Add custom pattern (e.g., for clerks)
        import re
        clerk_pattern = r'(?:City|County)\s+Clerk\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})'
        
        matches = re.finditer(clerk_pattern, text, re.IGNORECASE)
        for match in matches:
            name = match.group(1).strip()
            if self._is_valid_name(name):
                officials.append({
                    'name': name,
                    'title': 'City Clerk',
                    'jurisdiction': jurisdiction,
                    'source': 'custom_pattern'
                })
        
        return officials

# Use custom creator
creator = CustomContactsCreator()
creator.create_all_contacts_tables()
```

## 📝 Data Source

**LocalView Meeting Transcripts:**
- Source: Stanford LocalView Project
- Coverage: 2006-2023 (18 years)
- Meetings: 153,452
- Source publication: [LocalView Paper](https://arxiv.org/abs/2110.00512)

**Open States API:**
- Source: https://openstates.org
- Coverage: All 50 states + DC + Puerto Rico
- Free tier: 50,000 requests/month
- API key: Sign up at https://openstates.org/accounts/signup/

## 🤝 Contributing

Want to improve official extraction?

1. **Test extraction accuracy** in your city
2. **Report false positives/negatives** via GitHub issues
3. **Add new extraction patterns** (pull requests welcome!)
4. **Provide labeled data** for training ML models

## 📚 Related Documentation

- [Meeting Gold Tables](./gold-table-pipeline.md)
- [HuggingFace Upload Guide](../deployment/huggingface-spaces.md)
- [Data Sources](../integrations/localview.md)

## 🆘 Troubleshooting

### No Officials Extracted

**Problem**: Empty output file

**Solution**:
1. Check that meeting transcripts exist: `ls -lh data/gold/national/meetings_transcripts.parquet`
2. Run meetings pipeline first: `python scripts/create_all_gold_tables.py --meetings-only`
3. Check transcript format - some may not have roll calls

### Low Extraction Count

**Problem**: Fewer officials than expected

**Solution**:
1. Check transcript quality - auto-captions may have errors
2. Add custom patterns for your jurisdiction's format
3. Use `--debug` flag to see extraction details

### Duplicate Names

**Problem**: Same person listed multiple times

**Solution**:
- Deduplication is automatic by `(name, jurisdiction)`
- Check that jurisdiction names are consistent
- Verify name spelling in transcripts
