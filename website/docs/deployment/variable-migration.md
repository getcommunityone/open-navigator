---
sidebar_position: 9
---

# 🔄 Variable Name Migration Guide

## What Changed?

We've standardized environment variable names to match `.env.example`:

| Old Name | New Name | Status |
|----------|----------|--------|
| `HF_TOKEN` | `HF_TOKEN` | ✅ Backwards compatible |
| `HF_USERNAME` | `HF_USERNAME` | ✅ No change |

## Why This Change?

- **Consistency:** All variables now match `.env.example`
- **Clarity:** `HF_TOKEN` is more descriptive than generic `HF_TOKEN`
- **Developer Experience:** Single source of truth in `.env.example`

## Migration Steps

### 1. Local Development (.env file)

**No action needed!** 

The `.env.example` already uses `HF_TOKEN`, so if you copied it to create your `.env`, you're already using the correct variable name.

If you have an old `.env` file with `HF_TOKEN`:
```bash
# Old (still works due to backwards compatibility)
HF_TOKEN=hf_your_token_here

# New (recommended)
HF_TOKEN=hf_your_token_here
```

### 2. GitHub Actions Secrets

If you're using the GitHub Actions workflow for deployment:

**Option A: Rename the secret (Recommended)**
1. Go to your repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Delete the old `HF_TOKEN` secret
4. Create a new secret named `HF_TOKEN` with the same token value

**Option B: Add new secret (Keep both)**
1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Add new secret `HF_TOKEN` with your token
3. Keep `HF_TOKEN` for now (you can delete it later)

**Option C: Do nothing**

The scripts still check for `HF_TOKEN` as a fallback, but the GitHub Actions workflow now requires `HF_TOKEN`.

### 3. Hugging Face Space Secrets

If deploying to Hugging Face Spaces:

1. Go to your Space settings: `https://huggingface.co/spaces/YOUR_USERNAME/SPACE_NAME/settings`
2. Click **Variables and secrets**
3. The space should use `HF_TOKEN` (it may already be set correctly)

### 4. Production Environments

Update your production environment variables:

```bash
# Docker
docker run -e HF_TOKEN=hf_xxx ...

# Docker Compose
environment:
  - HF_TOKEN=hf_xxx

# Kubernetes
env:
  - name: HF_TOKEN
    valueFrom:
      secretKeyRef:
        name: hf-secrets
        key: token
```

## Backwards Compatibility

✅ **Python scripts are backwards compatible:**

```python
# scripts/upload_to_huggingface.py checks both:
self.token = token or os.getenv("HF_TOKEN") or os.getenv("HF_TOKEN")
```

This means:
- ✅ `HF_TOKEN` works (preferred)
- ✅ `HF_TOKEN` still works (fallback)
- ✅ Both can coexist (HF_TOKEN takes precedence)

⚠️ **GitHub Actions workflow requires update:**

The `.github/workflows/deploy-huggingface.yml` now uses `HF_TOKEN` only, so you must update your GitHub secrets.

## Verification

### Check Your Local Setup

```bash
# Should show your token
echo $HF_TOKEN

# Old variable (may or may not be set)
echo $HF_TOKEN
```

### Test Your Scripts

```bash
# Should work with HF_TOKEN
python scripts/upload_to_huggingface.py --discovery

# Should also work with HF_TOKEN (backwards compatibility)
export HF_TOKEN="hf_xxx"
python scripts/upload_to_huggingface.py --discovery
```

## Troubleshooting

### "Hugging Face token required" Error

**Cause:** Neither `HF_TOKEN` nor `HF_TOKEN` is set

**Solution:**
```bash
# Set the correct variable
export HF_TOKEN="hf_YOUR_TOKEN_HERE"

# Or add to .env file
echo "HF_TOKEN=hf_YOUR_TOKEN_HERE" >> .env
```

### GitHub Actions Deployment Fails

**Cause:** GitHub secret still named `HF_TOKEN`

**Solution:**
1. Go to Settings → Secrets and variables → Actions
2. Add secret `HF_TOKEN` with your token
3. Re-run the workflow

### Not Sure Which Variable You're Using

Check your current environment:
```bash
# See all HF-related variables
env | grep -E "(HF_|HUGGINGFACE)"
```

## Summary

| Action | Required? | Notes |
|--------|-----------|-------|
| Update .env file | Optional | Works with both names |
| Update GitHub secrets | **Required** | If using GitHub Actions |
| Update HF Space secrets | Recommended | Check your Space settings |
| Update production env | Recommended | For consistency |
| Update code | Not needed | Backwards compatible |

## Questions?

Check the `.env.example` file for the latest variable names and examples.

---

**Last Updated:** 2026-04-26
