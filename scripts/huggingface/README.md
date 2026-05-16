# HuggingFace Dataset Management

Scripts for preparing and uploading datasets to HuggingFace.

## Setup & Configuration

### check-hf-vars.py
Verify HuggingFace environment variables are properly configured.

**Usage:**
```bash
python scripts/huggingface/check-hf-vars.py
```

### setup-huggingface.sh
Initial setup for HuggingFace integration (credentials, organization).

**Usage:**
```bash
./scripts/huggingface/setup-huggingface.sh
```

## Preparation

### reorganize_for_huggingface.py
Reorganizes data files into HuggingFace-compatible structure.

**Usage:**
```bash
python scripts/huggingface/reorganize_for_huggingface.py
```

### finalize_huggingface_structure.py
Final validation and preparation of HuggingFace datasets.

**Usage:**
```bash
python scripts/huggingface/finalize_huggingface_structure.py
```

## Upload Scripts

### upload_to_huggingface.py
**Main upload script** - uploads all datasets to HuggingFace.

**Usage:**
```bash
python scripts/huggingface/upload_to_huggingface.py
```

**Requirements:**
- HuggingFace token in environment
- HF_ORGANIZATION set in .env

### Specific Uploads

- `upload_nonprofits_to_hf.py` - Upload nonprofit datasets
- `upload_meetings_to_hf.py` - Upload meeting datasets
- `upload_state_splits_to_hf.py` - Upload state-partitioned data

## Publishing & Deployment

### deploy-huggingface.sh
**Main deployment script** - builds and deploys to HuggingFace Spaces.

**Usage:**
```bash
./scripts/huggingface/deploy-huggingface.sh
```

### publish_gold_datasets.py
Publish processed gold datasets to HuggingFace.

**Usage:**
```bash
python scripts/huggingface/publish_gold_datasets.py
```

### delete_and_publish_all_datasets.py
**Dangerous!** Deletes and republishes all datasets (fresh start).

**Usage:**
```bash
python scripts/huggingface/delete_and_publish_all_datasets.py
```

## Error Recovery

### retry_failed_datasets.py
Retry uploading datasets that failed previously.

**Usage:**
```bash
python scripts/huggingface/retry_failed_datasets.py
```

### fix_and_publish_failed.py
Fix and republish specific failed datasets.

**Usage:**
```bash
python scripts/huggingface/fix_and_publish_failed.py
```

## Maintenance

### hf-dataset-cleanup.sh
Clean up old/orphaned HuggingFace datasets.

**Usage:**
```bash
./scripts/huggingface/hf-dataset-cleanup.sh
```

### force-hf-rebuild.sh
Force complete rebuild and reupload (clears cache).

**Usage:**
```bash
./scripts/huggingface/force-hf-rebuild.sh
```

## Workflow

1. Setup: `setup-huggingface.sh`
2. Check config: `check-hf-vars.py`
3. Prepare data: `reorganize_for_huggingface.py`
4. Finalize: `finalize_huggingface_structure.py`
5. Upload: `upload_to_huggingface.py`
6. Deploy: `deploy-huggingface.sh`

## Environment Variables

Required in `.env`:
```bash
HF_ORGANIZATION=CommunityOne
HF_USERNAME=CommunityOne
HF_TOKEN=hf_...
```
