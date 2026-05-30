---
sidebar_position: 10
---

# D Drive Configuration for Large Datasets

Configure Open Navigator to store large datasets (ACS census data, IRS 990s, etc.) on an external drive or secondary volume to avoid filling your primary disk.

## Why Use External Storage?

Open Navigator downloads and caches large datasets:

| Dataset | Size | Records |
|---------|------|---------|
| **ACS 5-Year (All States)** | ~15 GB | 85,000 tracts |
| **IRS Form 990s** | ~100 GB | 1.8M nonprofits |
| **Meeting Minutes (PDFs)** | ~500 GB | 90,000 jurisdictions |
| **Legislative Bills** | ~50 GB | Millions of bills |

**Total potential storage**: Up to 1 TB of data!

## 📁 Recommended Directory Structure

Create this structure on your D drive (or external storage):

```
D:/open-navigator-data/
├── acs/                    # American Community Survey demographic data
│   ├── B19013_county_*_2022.parquet
│   ├── B27010_county_*_2022.parquet
│   └── acs_2022_ALL/      # Bulk downloads
├── irs/                    # IRS nonprofit data
│   ├── bmf/               # Business Master File
│   └── 990s/              # Form 990 PDFs and XML
├── legislative/           # Legislative data
│   ├── bills/
│   ├── votes/
│   └── legislators/
├── meetings/              # Meeting minutes and agendas
│   ├── pdfs/
│   └── transcripts/
└── cache/                 # General cache
```

## 🖥️ Platform-Specific Setup

### Windows (D Drive)

**1. Create the data directory:**

```powershell
# PowerShell
New-Item -Path "D:\open-navigator-data" -ItemType Directory -Force
New-Item -Path "D:\open-navigator-data\acs" -ItemType Directory -Force
New-Item -Path "D:\open-navigator-data\irs" -ItemType Directory -Force
New-Item -Path "D:\open-navigator-data\cache" -ItemType Directory -Force
```

**2. Set permissions (if needed):**

```powershell
# Give yourself full control
icacls "D:\open-navigator-data" /grant "${env:USERNAME}:(OI)(CI)F" /T
```

**3. Use in Python scripts:**

```python
from pathlib import Path

# Option 1: Explicit Windows path
data_dir = Path("D:/open-navigator-data/acs")

# Option 2: Using environment variable
import os
data_dir = Path(os.environ.get("OPEN_NAV_DATA_DIR", "D:/open-navigator-data/acs"))
```

### Linux (Mounted Drive)

**1. Mount the drive:**

```bash
# Find your drive
lsblk

# Create mount point
sudo mkdir -p /mnt/d

# Mount (replace /dev/sdb1 with your drive)
sudo mount /dev/sdb1 /mnt/d

# Auto-mount on boot (add to /etc/fstab)
echo "/dev/sdb1 /mnt/d ext4 defaults 0 0" | sudo tee -a /etc/fstab
```

**2. Create directories:**

```bash
mkdir -p /mnt/d/open-navigator-data/{acs,irs,legislative,meetings,cache}
```

**3. Set ownership:**

```bash
# Give yourself ownership
sudo chown -R $USER:$USER /mnt/d/open-navigator-data
chmod -R 755 /mnt/d/open-navigator-data
```

**4. Use in scripts:**

```python
from pathlib import Path

data_dir = Path("/mnt/d/open-navigator-data/acs")
```

### macOS (External Drive)

**1. External drives auto-mount to `/Volumes`:**

```bash
# Your drive might be at:
ls /Volumes/
# Example: /Volumes/MyExternalDrive
```

**2. Create directories:**

```bash
mkdir -p "/Volumes/MyExternalDrive/open-navigator-data"/{acs,irs,legislative,meetings,cache}
```

**3. Use in scripts:**

```python
from pathlib import Path

data_dir = Path("/Volumes/MyExternalDrive/open-navigator-data/acs")
```

### WSL (Windows Subsystem for Linux)

**Windows drives are auto-mounted in WSL:**

```bash
# D drive is at /mnt/d
cd /mnt/d

# Create directories
mkdir -p /mnt/d/open-navigator-data/{acs,irs,legislative,meetings,cache}
```

**Use in scripts (WSL path):**

```python
from pathlib import Path

# WSL path to Windows D drive
data_dir = Path("/mnt/d/open-navigator-data/acs")
```

## 🔧 Configuration Methods

### Method 1: Environment Variable (Recommended)

**Advantages**: Single configuration, all scripts respect it

**Setup:**

Add to `.env` file in project root:

```bash
# .env
OPEN_NAV_DATA_DIR=D:/open-navigator-data

# Or Linux/Mac:
# OPEN_NAV_DATA_DIR=/mnt/d/open-navigator-data
```

**Update scripts to use it:**

```python
# scripts/datasources/census/acs_ingestion.py
import os
from pathlib import Path

# Use environment variable with fallback
base_data_dir = os.environ.get("OPEN_NAV_DATA_DIR", "data/cache")
acs_dir = Path(base_data_dir) / "acs"

acs = ACSDataIngestion(data_dir=acs_dir)
```

### Method 2: Config File

**Create `config/paths.py`:**

```python
from pathlib import Path
import os

# Base data directory (customizable)
BASE_DATA_DIR = Path(os.environ.get("OPEN_NAV_DATA_DIR", "data"))

# Subdirectories
ACS_DATA_DIR = BASE_DATA_DIR / "acs"
IRS_DATA_DIR = BASE_DATA_DIR / "irs"
LEGISLATIVE_DATA_DIR = BASE_DATA_DIR / "legislative"
MEETINGS_DATA_DIR = BASE_DATA_DIR / "meetings"
CACHE_DIR = BASE_DATA_DIR / "cache"

# Create directories if they don't exist
for directory in [ACS_DATA_DIR, IRS_DATA_DIR, LEGISLATIVE_DATA_DIR, 
                   MEETINGS_DATA_DIR, CACHE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)
```

**Use in scripts:**

```python
from config.paths import ACS_DATA_DIR

acs = ACSDataIngestion(data_dir=ACS_DATA_DIR)
```

### Method 3: Command-Line Argument

**For one-off downloads:**

```python
# scripts/datasources/census/download_acs.py
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--data-dir", type=Path, default="data/cache/acs",
                    help="Directory to store ACS data")
args = parser.parse_args()

acs = ACSDataIngestion(data_dir=args.data_dir)
```

**Usage:**

```bash
# Use D drive
python download_acs.py --data-dir D:/open-navigator-data/acs

# Use default
python download_acs.py
```

## 🗂️ Example Configurations

### Small Project (Default)

**Storage**: Local project directory  
**Size**: < 10 GB  
**Speed**: Fastest (same disk as code)

```python
# Uses data/cache/ in project directory
acs = ACSDataIngestion()
```

### Medium Project (D Drive)

**Storage**: D drive or external SSD  
**Size**: 10-100 GB  
**Speed**: Fast

```python
from pathlib import Path

acs = ACSDataIngestion(data_dir=Path("D:/open-navigator-data/acs"))
```

### Large Project (Network Storage)

**Storage**: NAS or cloud-mounted drive  
**Size**: 100+ GB  
**Speed**: Slower but shared

```python
from pathlib import Path

# Windows network path
data_dir = Path("//server/open-navigator/acs")

# Or mounted network drive (Linux)
# data_dir = Path("/mnt/nas/open-navigator/acs")

acs = ACSDataIngestion(data_dir=data_dir)
```

## 📊 Storage Requirements by Dataset

### ACS Census Data

| Download Type | Size | Time (50 Mbps) |
|---------------|------|----------------|
| Single table, single state | ~5 MB | < 1 sec |
| Single table, all states | ~50 MB | ~10 sec |
| All tables, all states (API) | ~500 MB | ~2 min |
| Bulk download (all data) | ~15 GB | ~40 min |

**Recommended**: Start with API downloads (targeted), only use bulk if needed.

### IRS Nonprofit Data

| Dataset | Size | Records |
|---------|------|---------|
| Business Master File (BMF) | ~500 MB | 1.8M nonprofits |
| Form 990 XML (1 year) | ~20 GB | ~300K filings |
| Form 990 PDFs (1 year) | ~50 GB | ~300K PDFs |
| Full 990 archive (10 years) | ~500 GB | 3M+ filings |

**Recommended**: D drive or external storage required.

### Legislative Data

| Dataset | Size | Records |
|---------|------|---------|
| OpenStates bills (1 state, 1 year) | ~100 MB | ~5K bills |
| OpenStates bills (all states, 1 year) | ~5 GB | ~250K bills |
| OpenStates bills (all states, 10 years) | ~50 GB | 2.5M bills |

**Recommended**: D drive for multi-year data.

### Meeting Minutes

| Dataset | Size | Records |
|---------|------|---------|
| Meeting agendas (text) | ~1 GB | 100K meetings |
| Meeting PDFs (cached) | ~500 GB | 1M documents |

**Recommended**: External storage for PDF archive.

## 🔍 Verify Configuration

**Test your setup:**

```python
from pathlib import Path
import pandas as pd

def test_storage_config(data_dir: Path):
    """Test that we can write/read data."""
    
    # Create test directory
    test_dir = data_dir / "test"
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # Write test file
    test_file = test_dir / "test.parquet"
    df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    df.to_parquet(test_file)
    
    # Read test file
    df2 = pd.read_parquet(test_file)
    
    # Verify
    assert df.equals(df2), "Data mismatch!"
    
    # Cleanup
    test_file.unlink()
    test_dir.rmdir()
    
    print(f"✅ Storage configuration verified: {data_dir.absolute()}")
    print(f"✅ Free space: {get_free_space(data_dir):.2f} GB")

def get_free_space(path: Path) -> float:
    """Get free disk space in GB."""
    import shutil
    stat = shutil.disk_usage(path)
    return stat.free / (1024**3)

# Test
test_storage_config(Path("D:/open-navigator-data"))
```

## ⚡ Performance Tips

### 1. Use SSD for Cache

- **C drive (SSD)**: Small, frequently accessed files
- **D drive (HDD)**: Large, rarely accessed archives

### 2. Organize by Access Frequency

```
D:/open-navigator-data/
├── hot/        # Frequently accessed (keep on SSD if possible)
│   └── acs/    # Census data for current analysis
└── cold/       # Rarely accessed (OK on HDD)
    ├── irs/990s/  # Historical 990 PDFs
    └── archive/   # Old datasets
```

### 3. Use Compression for Archives

```python
# Compress old data
import gzip
import shutil

with open("data.parquet", "rb") as f_in:
    with gzip.open("data.parquet.gz", "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
```

### 4. Clean Up Old Cache

```python
from pathlib import Path
from datetime import datetime, timedelta

def cleanup_old_cache(cache_dir: Path, days: int = 30):
    """Delete cache files older than N days."""
    
    cutoff = datetime.now() - timedelta(days=days)
    
    for file in cache_dir.rglob("*.parquet"):
        if datetime.fromtimestamp(file.stat().st_mtime) < cutoff:
            print(f"Deleting old cache: {file}")
            file.unlink()

cleanup_old_cache(Path("D:/open-navigator-data/cache"))
```

## 🆘 Troubleshooting

### "Permission denied" on D drive

**Windows:**
```powershell
# Give yourself full control
icacls "D:\open-navigator-data" /grant "${env:USERNAME}:(OI)(CI)F" /T
```

**Linux:**
```bash
# Change ownership
sudo chown -R $USER:$USER /mnt/d/open-navigator-data
```

### "No space left on device"

**Check disk space:**

```bash
# Windows (PowerShell)
Get-PSDrive D | Select-Object Used,Free

# Linux/Mac
df -h /mnt/d
```

**Free up space:**
1. Delete old cache files
2. Compress archive data
3. Move rarely used data to cloud storage

### Slow read/write performance

**Causes**:
- USB 2.0 external drive (upgrade to USB 3.0+)
- Network drive over slow connection
- HDD vs SSD (SSD is 10-100x faster)

**Solutions**:
- Use SSD for frequently accessed data
- Enable write caching (Windows)
- Use local storage for processing, archive to external

### WSL can't access D drive

**Fix**:

```bash
# Verify drive is mounted
ls /mnt/d

# If not, add to /etc/fstab:
sudo mkdir -p /mnt/d
sudo mount -t drvfs D: /mnt/d
```

## 🔮 Next Steps

1. **Create data directory** on your D drive or external storage
2. **Set environment variable** `OPEN_NAV_DATA_DIR` in `.env`
3. **Test configuration** using the verification script above
4. **Download ACS data** to test storage setup
5. **Monitor disk usage** as you add more datasets

## Related Documentation

- [Census ACS Integration](../data-sources/census-acs.md) - Download demographic data
- [IRS 990 Downloads](../data-sources/nonprofit-sources.md) - Nonprofit data
- [Data Architecture](../development/data-architecture.md) - Overall data flow
