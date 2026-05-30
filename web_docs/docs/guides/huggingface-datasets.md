---
sidebar_position: 8
---

# HuggingFace Dataset Integration

Push your nonprofit data to HuggingFace Hub and query it from your React application using the **free** Datasets Server API (no authentication required for public datasets!).

## 🎯 Overview

With 1.9M+ nonprofits now available from IRS EO-BMF, you can:
1. **Upload** all 4 nonprofit gold tables to HuggingFace (free unlimited storage)
2. **Query** datasets from React using HuggingFace Datasets Server API
3. **Search** nonprofits by name, state, NTEE code, or keywords
4. **Paginate** through millions of records efficiently

**Key Benefits:**
- ✅ **Free unlimited storage** (public datasets)
- ✅ **No authentication required** for reading public datasets
- ✅ **REST API** - works from any language (Python, JavaScript, curl)
- ✅ **Automatic caching** and CDN delivery by HuggingFace
- ✅ **Searchable** with full-text search built-in

## 📤 Step 1: Upload Datasets to HuggingFace

### Prerequisites

```bash
# Install HuggingFace libraries
pip install huggingface_hub datasets pyarrow

# Get your token from https://huggingface.co/settings/tokens
export HF_TOKEN="hf_YOUR_TOKEN_HERE"
```

Add to `.env`:
```bash
HF_TOKEN=hf_your_write_token_here
```

### Upload All Nonprofit Tables

```bash
cd /home/developer/projects/open-navigator

# Upload all 4 tables (organizations, financials, programs, locations)
python -m hosting.huggingface nonprofits

# Upload specific table
python scripts/upload_nonprofits_to_hf.py --table organizations

# Upload to your own repo (change username)
python -m hosting.huggingface nonprofits --repo "your-username/nonprofits"
```

**Expected Output:**
```
✅ Logged in to Hugging Face
✅ Repository ready: https://huggingface.co/datasets/CommunityOne/one-nonprofits
📤 Uploading organizations from data/gold/nonprofits_organizations.parquet
  Rows: 1,952,238
  Columns: 28
  Size: 156.43 MB
  Pushing to CommunityOne/one-nonprofits (split: organizations)
✅ Uploaded organizations: 1,952,238 records
   View at: https://huggingface.co/datasets/CommunityOne/one-nonprofits/viewer/organizations
📤 Uploading financials from data/gold/nonprofits_financials.parquet
  ...
🎉 All uploads complete!
```

### What Gets Uploaded

| Table | Records | Description |
|-------|---------|-------------|
| **organizations** | 1.9M+ | Main nonprofit data (EIN, name, NTEE, subsection) |
| **financials** | 1.9M+ | Assets, income, revenue, ruling date |
| **programs** | 1.9M+ | Activity codes, group affiliation |
| **locations** | 1.9M+ | Address, city, state, ZIP code |

## 🔍 Step 2: Query from Python

### Basic Query

```python
from datasets import load_dataset

# Load the dataset
dataset = load_dataset("CommunityOne/one-nonprofits")

# Access specific tables (splits)
orgs = dataset["organizations"]
financials = dataset["financials"]
locations = dataset["locations"]

print(f"Total organizations: {len(orgs):,}")
# Output: Total organizations: 1,952,238
```

### Convert to Pandas

```python
import pandas as pd

# Load as pandas DataFrame
df = pd.DataFrame(dataset["organizations"])

# Filter by state
alabama = df[df['state'] == 'AL']
print(f"Alabama nonprofits: {len(alabama):,}")
# Output: Alabama nonprofits: 26,148

# Filter by NTEE category (E = Health)
health = df[df['ntee_code'].str.startswith('E', na=False)]
print(f"Health organizations: {len(health):,}")
# Output: Health organizations: 80,000+
```

### Search by Keywords

```python
# Search for "dental" in organization names
dental = df[df['name'].str.contains('dental', case=False, na=False)]
print(f"Dental organizations: {len(dental):,}")

# Filter dental orgs in California
ca_dental = dental[dental['state'] == 'CA']
print(f"California dental orgs: {len(ca_dental):,}")
```

### Join Tables

```python
# Join organizations with financials
orgs_df = pd.DataFrame(dataset["organizations"])
fin_df = pd.DataFrame(dataset["financials"])

# Merge on EIN
combined = orgs_df.merge(fin_df, on='ein', how='left')

# Find high-revenue health organizations in NY
ny_health = combined[
    (combined['state'] == 'NY') & 
    (combined['ntee_code'].str.startswith('E', na=False)) &
    (combined['revenue_amount'] > 1_000_000)
]
print(f"High-revenue NY health orgs: {len(ny_health):,}")
```

## 🌐 Step 3: Query from React/JavaScript

### Install Utility

The HuggingFace query utility is already created at [`frontend/src/utils/huggingface.ts`](../../frontend/src/utils/huggingface.ts).

### Basic Usage

```typescript
import { fetchHFRows, searchHFDataset } from '../utils/huggingface';

// Fetch first 100 nonprofits
const response = await fetchHFRows({
  dataset: "CommunityOne/one-nonprofits",
  split: "organizations"
}, 0, 100);

const nonprofits = response.rows.map(r => r.row);
console.log(`Loaded ${nonprofits.length} nonprofits`);
console.log(`Total available: ${response.num_rows_total:,}`);
```

### Search with React Query

```typescript
import { useQuery } from '@tanstack/react-query';
import { searchNonprofits } from '../utils/huggingface';

function NonprofitSearch() {
  const [searchTerm, setSearchTerm] = useState('dental');
  const [state, setState] = useState('CA');
  
  const { data: nonprofits, isLoading } = useQuery({
    queryKey: ['nonprofits', searchTerm, state],
    queryFn: async () => {
      return await searchNonprofits({
        dataset: "CommunityOne/one-nonprofits",
        query: searchTerm,
        state: state,
        limit: 100
      });
    }
  });
  
  if (isLoading) return <div>Loading...</div>;
  
  return (
    <div>
      <h2>Found {nonprofits?.length} nonprofits</h2>
      {nonprofits?.map(org => (
        <div key={org.ein}>
          <h3>{org.name}</h3>
          <p>NTEE: {org.ntee_code} | State: {org.state}</p>
        </div>
      ))}
    </div>
  );
}
```

### Pagination Example

```typescript
import { useState } from 'react';
import { fetchHFRows } from '../utils/huggingface';

function NonprofitList() {
  const [page, setPage] = useState(0);
  const pageSize = 100;
  
  const { data, isLoading } = useQuery({
    queryKey: ['nonprofits', page],
    queryFn: async () => {
      return await fetchHFRows({
        dataset: "CommunityOne/one-nonprofits",
        split: "organizations"
      }, page * pageSize, pageSize);
    }
  });
  
  return (
    <div>
      {/* Display nonprofits */}
      {data?.rows.map(r => (
        <div key={r.row.ein}>{r.row.name}</div>
      ))}
      
      {/* Pagination controls */}
      <button onClick={() => setPage(p => Math.max(0, p - 1))}>
        Previous
      </button>
      <span>Page {page + 1}</span>
      <button onClick={() => setPage(p => p + 1)}>
        Next
      </button>
    </div>
  );
}
```

## 🔄 Step 4: Update Existing Pages

### Update Nonprofits Page

Edit [`frontend/src/pages/Nonprofits.tsx`](../../frontend/src/pages/Nonprofits.tsx):

```typescript
import { useQuery } from '@tanstack/react-query';
import { searchNonprofits } from '../utils/huggingface';

const DATASET_NAME = "CommunityOne/one-nonprofits";

export default function Nonprofits() {
  const [state, setState] = useState<string>('');
  const [nteeCode, setNteeCode] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  
  const { data: nonprofits, isLoading } = useQuery({
    queryKey: ['nonprofits', state, nteeCode, searchQuery],
    queryFn: async () => {
      return await searchNonprofits({
        dataset: DATASET_NAME,
        query: searchQuery || undefined,
        state: state || undefined,
        nteeCode: nteeCode || undefined,
        limit: 100
      });
    }
  });
  
  return (
    <div className="p-6">
      <h1>Nonprofits ({nonprofits?.length || 0} found)</h1>
      
      {/* Filters */}
      <div className="filters">
        <input
          type="text"
          placeholder="Search by name..."
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
        />
        
        <select value={state} onChange={e => setState(e.target.value)}>
          <option value="">All States</option>
          <option value="AL">Alabama</option>
          <option value="CA">California</option>
          <option value="NY">New York</option>
          {/* Add all 50 states */}
        </select>
        
        <select value={nteeCode} onChange={e => setNteeCode(e.target.value)}>
          <option value="">All Categories</option>
          <option value="E">Health (E)</option>
          <option value="P">Human Services (P)</option>
          <option value="X">Religion (X)</option>
          {/* Add all NTEE codes */}
        </select>
      </div>
      
      {/* Results */}
      {isLoading ? (
        <div>Loading...</div>
      ) : (
        <div className="results">
          {nonprofits?.map(org => (
            <div key={org.ein} className="nonprofit-card">
              <h3>{org.name}</h3>
              <p>EIN: {org.ein}</p>
              <p>NTEE: {org.ntee_code}</p>
              <p>Location: {org.city}, {org.state} {org.zip_code}</p>
              {org.revenue_amount && (
                <p>Revenue: ${org.revenue_amount.toLocaleString()}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

## 📊 Step 5: Add Advanced Features

### Autocomplete Search

```typescript
import { useState, useEffect } from 'react';
import { searchHFDataset } from '../utils/huggingface';

function NonprofitAutocomplete() {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<any[]>([]);
  
  useEffect(() => {
    if (query.length < 3) {
      setSuggestions([]);
      return;
    }
    
    const fetchSuggestions = async () => {
      const response = await searchHFDataset({
        dataset: "CommunityOne/one-nonprofits",
        split: "organizations"
      }, query, 0, 10);
      
      setSuggestions(response.rows.map(r => r.row));
    };
    
    const timeoutId = setTimeout(fetchSuggestions, 300);
    return () => clearTimeout(timeoutId);
  }, [query]);
  
  return (
    <div>
      <input
        type="text"
        value={query}
        onChange={e => setQuery(e.target.value)}
        placeholder="Search nonprofits..."
      />
      
      {suggestions.length > 0 && (
        <ul>
          {suggestions.map(org => (
            <li key={org.ein}>{org.name} - {org.city}, {org.state}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

### Map Visualization

```typescript
import { useQuery } from '@tanstack/react-query';
import { fetchNonprofitsByState } from '../utils/huggingface';

function NonprofitMap() {
  const [selectedState, setSelectedState] = useState('CA');
  
  const { data: nonprofits } = useQuery({
    queryKey: ['nonprofits-map', selectedState],
    queryFn: async () => {
      return await fetchNonprofitsByState(
        "CommunityOne/one-nonprofits",
        selectedState,
        1000
      );
    }
  });
  
  return (
    <div>
      <select value={selectedState} onChange={e => setSelectedState(e.target.value)}>
        {/* State options */}
      </select>
      
      <Map
        markers={nonprofits?.map(org => ({
          lat: org.latitude,
          lng: org.longitude,
          name: org.name
        }))}
      />
    </div>
  );
}
```

## 🚀 API Reference

### Python Functions

```python
from datasets import load_dataset
import pandas as pd

# Load dataset
dataset = load_dataset("CommunityOne/one-nonprofits")

# Get specific split
orgs = dataset["organizations"]
financials = dataset["financials"]
programs = dataset["programs"]
locations = dataset["locations"]

# Convert to pandas
df = pd.DataFrame(orgs)

# Filter
filtered = df[df['state'] == 'CA']

# Search
results = df[df['name'].str.contains('dental', case=False)]
```

### JavaScript Functions

```typescript
import {
  fetchHFRows,           // Fetch paginated rows
  searchHFDataset,       // Full-text search
  getHFDatasetSize,      // Get total row count
  fetchAllNonprofits,    // Fetch multiple pages
  fetchNonprofitsByState,// Filter by state
  fetchNonprofitsByNTEE, // Filter by NTEE code
  searchNonprofits       // Combined search + filters
} from '../utils/huggingface';
```

### REST API (No Auth Required!)

```bash
# Get first 100 organizations
curl "https://datasets-server.huggingface.co/rows?dataset=CommunityOne/one-nonprofits&config=default&split=organizations&offset=0&length=100"

# Search for "dental"
curl "https://datasets-server.huggingface.co/search?dataset=CommunityOne/one-nonprofits&config=default&split=organizations&query=dental&offset=0&length=100"

# Get dataset size
curl "https://datasets-server.huggingface.co/size?dataset=CommunityOne/one-nonprofits&config=default&split=organizations"
```

## 🎯 Next Steps

1. **Upload your datasets:**
   ```bash
   python -m hosting.huggingface nonprofits
   ```

2. **Test the API:**
   ```bash
   curl "https://datasets-server.huggingface.co/rows?dataset=YOUR_USERNAME/YOUR_DATASET&config=default&split=organizations&offset=0&length=10"
   ```

3. **Update your React pages:**
   - Replace local API calls with HuggingFace queries
   - Add pagination for large datasets
   - Implement autocomplete search
   - Create map visualizations

4. **Monitor usage:**
   - Visit: https://huggingface.co/datasets/YOUR_USERNAME/YOUR_DATASET
   - Check downloads, views, and API usage

## 📚 Additional Resources

- **HuggingFace Datasets Docs:** https://huggingface.co/docs/datasets
- **Datasets Server API:** https://huggingface.co/docs/datasets-server
- **IRS EO-BMF Data Source:** https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf
- **NTEE Codes Reference:** [IRS Bulk Data Integration](../data-sources/irs-bulk-data.md#ntee-national-taxonomy-of-exempt-entities)
