---
sidebar_position: 9
---

# Variable name migration (`HUGGINGFACE_TOKEN` → `HF_TOKEN`)

## What changed?

Environment variables and docs now use **`HF_TOKEN`** (matches Hugging Face Hub conventions and `.env.example`).

| Old name | New name |
|----------|----------|
| `HUGGINGFACE_TOKEN` | `HF_TOKEN` |

`HF_USERNAME` is unchanged.

## Local `.env`

```bash
# Old (rename if present)
# HUGGINGFACE_TOKEN=hf_...

# Current
HF_TOKEN=hf_your_token_here
```

## GitHub Actions

Rename the repository secret **`HUGGINGFACE_TOKEN`** → **`HF_TOKEN`** (same token value). The workflow `.github/workflows/deploy-huggingface.yml` reads `secrets.HF_TOKEN`.

## Colab

Colab Secret name: **`HF_TOKEN`** (not `HUGGINGFACE_TOKEN`).

## Verification

```bash
echo $HF_TOKEN
python scripts/huggingface/check-hf-vars.py
```

## Summary

- **Canonical:** `HF_TOKEN` in `.env`, scripts, CI, and Colab.
- **Remove:** `HUGGINGFACE_TOKEN` from `.env` and GitHub secrets after migrating.
